from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

from .genre_normalizer import GenreNormalizer
from .style_normalizer import StyleNormalizer


@dataclass(frozen=True)
class CandidateDTO:
    source: str
    genre_term: Optional[str]
    style_terms: List[str]
    confidence: float  # 0..1


@dataclass
class GenreSupport:
    source: str
    original: str
    normalized: str
    resolved_id: Optional[str]
    resolved_label: Optional[str]
    resolution_status: str
    normalizer_confidence: float
    candidate_confidence: float


@dataclass
class ResolutionResultDTO:
    primary_genre_id: Optional[str]
    primary_genre_label: Optional[str]
    primary_confidence: float
    evidence_count: int
    secondary_genres: List[Tuple[str, Optional[str], float]]
    styles: List[Tuple[str, Optional[str], float]]
    ambiguous: Dict[str, List[str]]
    unknown_terms: List[str]
    warnings: List[str]
    supports: List[Dict[str, Any]]


class MetadataCandidateResolver:
    """In-memory, read-only resolver for genre/style candidates.

    Usage: pass a list of `CandidateDTO` obtained from external sources.
    The resolver uses `GenreNormalizer` to classify terms and produces a
    deterministic `ResolutionResultDTO` without persisting anything.
    """

    def __init__(self, taxonomy_path: str | None = None, style_taxonomy_path: str | None = None, margin: float = 0.15):
        self._normalizer = GenreNormalizer(taxonomy_path)
        self._style_normalizer = StyleNormalizer(style_taxonomy_path)
        self.margin = float(margin)

    def resolve(self, candidates: List[CandidateDTO]) -> ResolutionResultDTO:
        # collect supports per resolved genre id
        supports_by_genre: Dict[Optional[str], List[GenreSupport]] = defaultdict(list)
        ambiguous_map: Dict[str, List[str]] = {}
        unknown_terms: List[str] = []
        warnings: List[str] = []
        supports_out: List[Dict[str, Any]] = []

        # handle empty input: return empty lists, no warnings
        if not candidates:
            return ResolutionResultDTO(None, None, 0.0, 0, [], [], {}, [], [], [])

        # Process each candidate's genre
        for c in candidates:
            if not c.genre_term or not str(c.genre_term).strip():
                # ignore empty/blank genre terms
                continue
            norm = self._normalizer.normalize_term(c.genre_term)
            resolved_id = norm.get("resolved_id")
            status = norm.get("resolution_status")
            normalizer_conf = float(norm.get("confidence", 0.0))

            support = GenreSupport(
                source=c.source,
                original=c.genre_term,
                normalized=norm.get("normalized_text"),
                resolved_id=resolved_id,
                resolved_label=norm.get("resolved_label"),
                resolution_status=status,
                normalizer_confidence=normalizer_conf,
                candidate_confidence=float(c.confidence),
            )

            # store support for diagnostics but drop 'source' from final profile
            d = asdict(support)
            if 'source' in d:
                d.pop('source')
            supports_out.append(d)

            # track
            if status == "unknown":
                unknown_terms.append(c.genre_term)
            elif status == "ambiguous":
                ambiguous_map.setdefault(norm.get("normalized_text"), list(norm.get("candidates", [])))
            else:
                # resolved (exact or alias)
                supports_by_genre[resolved_id].append(support)

        # compute normalized weighted confidence per genre using candidate weights
        genre_scores: Dict[str, float] = {}
        genre_evidence_count: Dict[str, int] = {}
        for gid, supports in supports_by_genre.items():
            sum_w = sum(s.candidate_confidence for s in supports if s.candidate_confidence > 0)
            sum_wc = sum(s.candidate_confidence * s.normalizer_confidence for s in supports if s.candidate_confidence > 0)
            genre_evidence_count[gid] = sum(1 for s in supports if s.candidate_confidence > 0)
            score = float((sum_wc / sum_w) if sum_w > 0 else 0.0)
            genre_scores[gid] = max(0.0, min(1.0, score))

        # add explicit conflict warning when multiple distinct resolved ids are proposed
        if len(genre_scores) > 1:
            warnings.append("Conflict between sources: multiple distinct resolved genres proposed")

        # determine best two
        sorted_genres = sorted(genre_scores.items(), key=lambda kv: kv[1], reverse=True)
        if not sorted_genres:
            return ResolutionResultDTO(None, None, 0.0, 0, [], [], ambiguous_map, unknown_terms, warnings, supports_out)

        best_genre, best_score = sorted_genres[0]
        second_score = sorted_genres[1][1] if len(sorted_genres) > 1 else 0.0

        # if difference less than margin -> conflict (no primary)
        if (best_score - second_score) < self.margin and len(sorted_genres) > 1:
            candidates_ordered = [gid for gid, _ in sorted_genres]
            warnings.append(f"Top genre difference below margin {self.margin}; no primary selected. Candidates: {candidates_ordered}")
            # return ambiguous candidates in ambiguous map under special key
            amb = {"candidates": candidates_ordered}
            return ResolutionResultDTO(None, None, 0.0, 0, [], [], amb, unknown_terms, warnings, supports_out)

        primary_confidence = float(best_score)
        primary_label = None
        primary_evidence_count = genre_evidence_count.get(best_genre, 0)
        if best_genre:
            supports = supports_by_genre.get(best_genre, [])
            if supports:
                primary_label = supports[0].resolved_label

        # secondary genres: other resolved ids
        secondary = []
        for gid, score in sorted_genres[1:]:
            lbl = None
            if supports_by_genre[gid]:
                lbl = supports_by_genre[gid][0].resolved_label
            sum_w = sum(s.candidate_confidence for s in supports_by_genre[gid])
            sum_wc = sum(s.candidate_confidence * s.normalizer_confidence for s in supports_by_genre[gid])
            sc = (sum_wc / sum_w) if sum_w > 0 else 0.0
            secondary.append((gid, lbl, float(sc)))

        # styles: aggregate style_terms using StyleNormalizer
        style_scores_sumw: Dict[str, float] = defaultdict(float)
        style_scores_sumwc: Dict[str, float] = defaultdict(float)
        style_labels: Dict[str, Optional[str]] = {}
        for c in candidates:
            for s in c.style_terms or []:
                if not s or not str(s).strip():
                    continue
                s_norm = self._style_normalizer.normalize_term(s)
                sid = s_norm.get("resolved_id")
                s_conf = float(s_norm.get("confidence", 0.0))
                if sid:
                    style_scores_sumw[sid] += float(c.confidence)
                    style_scores_sumwc[sid] += float(c.confidence) * s_conf
                    style_labels[sid] = s_norm.get("resolved_label")

        styles_out = []
        for sid, sumw in sorted(style_scores_sumw.items(), key=lambda kv: kv[1], reverse=True):
            sumwc = style_scores_sumwc.get(sid, 0.0)
            conf = (sumwc / sumw) if sumw > 0 else 0.0
            styles_out.append((sid, style_labels.get(sid), float(conf)))

        result = ResolutionResultDTO(
            primary_genre_id=best_genre,
            primary_genre_label=primary_label,
            primary_confidence=primary_confidence,
            evidence_count=primary_evidence_count,
            secondary_genres=secondary,
            styles=styles_out,
            ambiguous=ambiguous_map,
            unknown_terms=unknown_terms,
            warnings=warnings,
            supports=supports_out,
        )

        return result

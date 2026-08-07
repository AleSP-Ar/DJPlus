from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from .genre_normalizer import GenreNormalizer
from .metadata_candidate_resolver import CandidateDTO
from .style_normalizer import StyleNormalizer


@dataclass(frozen=True)
class DiscogsReleaseEvidenceDTO:
    raw_genres: Tuple[str, ...]
    raw_styles: Tuple[str, ...]
    confidence: float = 0.8
    release_id: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw_genres", self._normalize_terms(self.raw_genres))
        object.__setattr__(self, "raw_styles", self._normalize_terms(self.raw_styles))
        object.__setattr__(self, "confidence", float(self.confidence))

    @staticmethod
    def _normalize_terms(values: Iterable[str] | None) -> Tuple[str, ...]:
        if not values:
            return ()
        cleaned = []
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                cleaned.append(text)
        return tuple(cleaned)


@dataclass(frozen=True)
class DiscogsClassificationResultDTO:
    candidates: Tuple[CandidateDTO, ...]
    broad_terms: Tuple[str, ...]
    ambiguous_terms: Tuple[str, ...]
    unknown_terms: Tuple[str, ...]


class DiscogsMetadataClassifier:
    """Provider-specific Discogs classification layer.

    This classifier is intentionally separate from the generic resolver.
    It applies GenreNormalizer first, then StyleNormalizer, and emits an
    immutable classification result that preserves broad, ambiguous and
    unknown terms separately.
    """

    _BROAD_GENRE_TERMS = {"electronic", "house", "techno", "trance"}

    def __init__(
        self,
        taxonomy_path: str | None = None,
        style_taxonomy_path: str | None = None,
    ):
        self._genre_normalizer = GenreNormalizer(taxonomy_path)
        self._style_normalizer = StyleNormalizer(style_taxonomy_path)

    def classify(self, evidence: DiscogsReleaseEvidenceDTO) -> DiscogsClassificationResultDTO:
        if not isinstance(evidence, DiscogsReleaseEvidenceDTO):
            raise TypeError("evidence must be DiscogsReleaseEvidenceDTO")

        genre_terms: List[str] = []
        style_terms: List[str] = []
        broad_terms: List[str] = []
        ambiguous_terms: List[str] = []
        unknown_terms: List[str] = []

        seen_genres = set()
        seen_styles = set()

        for term in list(evidence.raw_genres):
            cleaned = self._normalize_input(term)
            if not cleaned:
                continue

            genre_match = self._genre_normalizer.normalize_term(cleaned)
            if genre_match.get("resolved_id"):
                key = self._normalize_diagnostic_key(cleaned)
                if key not in seen_genres:
                    seen_genres.add(key)
                    genre_terms.append(cleaned)
                continue

            if genre_match.get("resolution_status") == "ambiguous":
                ambiguous_terms.append(self._normalize_diagnostic(cleaned))
                continue

            style_match = self._style_normalizer.normalize_term(cleaned)
            if style_match.get("resolved_id"):
                key = self._normalize_diagnostic_key(cleaned)
                if key not in seen_styles:
                    seen_styles.add(key)
                    style_terms.append(cleaned)
                continue

            if style_match.get("status") == "ambiguous":
                ambiguous_terms.append(self._normalize_diagnostic(cleaned))
                continue

            if self._is_broad_term(cleaned):
                broad_terms.append(self._normalize_diagnostic(cleaned))
                continue

            unknown_terms.append(self._normalize_diagnostic(cleaned))

        for term in list(evidence.raw_styles):
            cleaned = self._normalize_input(term)
            if not cleaned:
                continue

            style_match = self._style_normalizer.normalize_term(cleaned)
            if style_match.get("resolved_id"):
                key = self._normalize_diagnostic_key(cleaned)
                if key not in seen_styles:
                    seen_styles.add(key)
                    style_terms.append(cleaned)
                continue

            genre_match = self._genre_normalizer.normalize_term(cleaned)
            if genre_match.get("resolved_id"):
                key = self._normalize_diagnostic_key(cleaned)
                if key not in seen_genres:
                    seen_genres.add(key)
                    genre_terms.append(cleaned)
                continue

            if style_match.get("status") == "ambiguous" or genre_match.get("resolution_status") == "ambiguous":
                ambiguous_terms.append(self._normalize_diagnostic(cleaned))
                continue

            if self._is_broad_term(cleaned):
                broad_terms.append(self._normalize_diagnostic(cleaned))
                continue

            unknown_terms.append(self._normalize_diagnostic(cleaned))

        genre_candidates = [
            CandidateDTO(
                source="discogs",
                genre_term=genre_term,
                style_terms=[],
                confidence=float(evidence.confidence),
            )
            for genre_term in sorted(dict.fromkeys(genre_terms), key=lambda item: item.casefold())
        ]

        style_candidate_terms = sorted(dict.fromkeys(style_terms), key=lambda item: item.casefold())
        candidates = tuple(genre_candidates + ([
            CandidateDTO(
                source="discogs",
                genre_term=None,
                style_terms=style_candidate_terms,
                confidence=float(evidence.confidence),
            )
        ] if style_candidate_terms else []))

        return DiscogsClassificationResultDTO(
            candidates=candidates,
            broad_terms=tuple(dict.fromkeys(broad_terms)),
            ambiguous_terms=tuple(dict.fromkeys(ambiguous_terms)),
            unknown_terms=tuple(dict.fromkeys(unknown_terms)),
        )

    @staticmethod
    def _normalize_input(value: Optional[str]) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _normalize_diagnostic(value: str) -> str:
        if not value:
            return ""
        text = re.sub(r"[^\w\s]", " ", value.casefold())
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _normalize_diagnostic_key(value: str) -> str:
        return DiscogsMetadataClassifier._normalize_diagnostic(value)

    def _is_broad_term(self, term: str) -> bool:
        return self._normalize_diagnostic_key(term) in self._BROAD_GENRE_TERMS


DiscogsRawEvidenceDTO = DiscogsReleaseEvidenceDTO

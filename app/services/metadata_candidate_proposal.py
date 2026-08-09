from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable, Iterable, Optional, Tuple

from .metadata_candidate_resolver import MetadataCandidateResolver, CandidateDTO
from .track_metadata_editor import TrackMetadataDTO


class MetadataCandidateProposalError(ValueError):
    pass


class MetadataProviderError(RuntimeError):
    pass


class MetadataProviderTimeoutError(MetadataProviderError):
    pass


@runtime_checkable
class MetadataCandidateProviderProtocol(Protocol):
    def fetch_candidates(self, current_metadata: TrackMetadataDTO) -> Iterable[CandidateDTO]:
        """Return zero or more candidate records for the given track metadata."""


@dataclass(frozen=True)
class MetadataProposalDTO:
    current_metadata: TrackMetadataDTO
    proposed_primary_genre_id: Optional[str]
    proposed_primary_genre_label: Optional[str]
    proposed_primary_confidence: float
    proposed_evidence_count: int
    candidate_genres: Tuple[Tuple[str, Optional[str], float, int], ...]
    proposed_secondary_genres: Tuple[Tuple[str, Optional[str], float], ...]
    proposed_styles: Tuple[Tuple[str, Optional[str], float], ...]
    conflicts: Tuple[str, ...]
    ambiguous_terms: Tuple[Tuple[str, Tuple[str, ...]], ...]
    unknown_terms: Tuple[str, ...]
    warnings: Tuple[str, ...]
    selectable_fields: Tuple[str, ...] = ("genre", "secondary_genres", "styles", "label")
    proposed_label: Optional[str] = None
    proposed_label_confidence: float = 0.0


class MetadataCandidateProposalService:
    def __init__(self, resolver: MetadataCandidateResolver):
        if not isinstance(resolver, MetadataCandidateResolver):
            raise TypeError("resolver must be MetadataCandidateResolver")
        self._resolver = resolver

    def create_proposal(
        self,
        current_metadata: TrackMetadataDTO,
        providers: Iterable[MetadataCandidateProviderProtocol] | None = None,
    ) -> MetadataProposalDTO:
        if not isinstance(current_metadata, TrackMetadataDTO):
            raise TypeError("current_metadata must be TrackMetadataDTO")

        candidates: list[CandidateDTO] = []
        warnings: list[str] = []
        providers_list = tuple(providers or ())

        for provider in providers_list:
            if not isinstance(provider, MetadataCandidateProviderProtocol):
                raise TypeError("All providers must implement MetadataCandidateProviderProtocol")
            try:
                provider_candidates = provider.fetch_candidates(current_metadata)
            except (MetadataProviderError, MetadataProviderTimeoutError) as error:
                warnings.append(f"Provider failed with {type(error).__name__}")
                continue

            if provider_candidates is None:
                continue
            for candidate in provider_candidates:
                if not isinstance(candidate, CandidateDTO):
                    raise MetadataCandidateProposalError("Provider returned invalid candidate type")
                candidates.append(candidate)

        result = self._resolver.resolve(candidates)

        fallback = self._fallback_primary_genre(candidates) if result.primary_genre_label is None else None

        ambiguous_terms = tuple(
            (term, tuple(values)) for term, values in sorted(result.ambiguous.items())
        )
        unknown_terms = tuple(result.unknown_terms)
        secondary_genres = tuple(result.secondary_genres)
        proposed_styles = tuple(result.styles)
        candidate_genres = tuple(result.candidate_genres if hasattr(result, 'candidate_genres') else ())
        conflicts = tuple(result.conflicts if hasattr(result, 'conflicts') else ())
        labels = sorted(
            ((candidate.confidence, candidate.label.strip()) for candidate in candidates if candidate.label and candidate.label.strip()),
            key=lambda item: (-item[0], item[1].casefold()),
        )

        return MetadataProposalDTO(
            current_metadata=current_metadata,
            proposed_primary_genre_id=result.primary_genre_id or (fallback[0] if fallback else None),
            proposed_primary_genre_label=result.primary_genre_label or (fallback[1] if fallback else None),
            proposed_primary_confidence=result.primary_confidence or (fallback[2] if fallback else 0.0),
            proposed_evidence_count=getattr(result, "evidence_count", 0) or (fallback[3] if fallback else 0),
            candidate_genres=candidate_genres,
            proposed_secondary_genres=secondary_genres,
            proposed_styles=proposed_styles,
            conflicts=conflicts,
            ambiguous_terms=ambiguous_terms,
            unknown_terms=unknown_terms,
            warnings=tuple(warnings + result.warnings),
            proposed_label=labels[0][1] if labels else None,
            proposed_label_confidence=labels[0][0] if labels else 0.0,
        )

    @staticmethod
    def _fallback_primary_genre(candidates):
        """Use a broad DJ category only when no Beatport-visible genre resolved."""
        terms = []
        for candidate in candidates:
            if candidate.genre_term:
                terms.append(str(candidate.genre_term).strip().casefold())
        fallback_terms = {
            "house": ("house", "House"),
            "trance": ("trance", "Trance"),
            "techno": ("techno", "Techno"),
            "electronic": ("edm", "EDM"),
            "edm": ("edm", "EDM"),
            "electronic dance music": ("edm", "EDM"),
        }
        broad_terms = [fallback_terms[term] for term in terms if term in fallback_terms]
        if terms and len(broad_terms) == len(terms):
            genre_id, label = broad_terms[0]
            confidence = max((float(candidate.confidence) for candidate in candidates), default=0.0)
            return genre_id, label, confidence, len(terms)
        return None

from __future__ import annotations

from .discogs_metadata_provider import DiscogsMetadataProvider
from .beatport_metadata_provider import BeatportMetadataProvider
from .metadata_candidate_proposal import MetadataCandidateProposalService, MetadataProposalDTO
from .metadata_candidate_resolver import MetadataCandidateResolver
from .musicbrainz_metadata_provider import MusicBrainzMetadataProvider
from .track_metadata_editor import TrackMetadataDTO


class CombinedMetadataProposalService:
    """Small orchestrator that combines MusicBrainz and Discogs through the existing proposal pipeline."""

    def __init__(
        self,
        resolver: MetadataCandidateResolver | None = None,
        musicbrainz_provider: MusicBrainzMetadataProvider | None = None,
        discogs_provider: DiscogsMetadataProvider | None = None,
        beatport_provider: BeatportMetadataProvider | None = None,
    ):
        self._resolver = resolver or MetadataCandidateResolver(
            taxonomy_path="config/genres-v1.json",
            style_taxonomy_path="config/styles-v1.json",
        )
        if not isinstance(self._resolver, MetadataCandidateResolver):
            raise TypeError("resolver must be MetadataCandidateResolver")

        self._proposal_service = MetadataCandidateProposalService(self._resolver)
        self._musicbrainz_provider = musicbrainz_provider or MusicBrainzMetadataProvider()
        self._discogs_provider = discogs_provider or DiscogsMetadataProvider()
        self._beatport_provider = beatport_provider or BeatportMetadataProvider()

    def create_metadata_proposal(self, track_metadata: TrackMetadataDTO) -> MetadataProposalDTO:
        if not isinstance(track_metadata, TrackMetadataDTO):
            raise TypeError("track_metadata must be TrackMetadataDTO")

        providers = (self._beatport_provider, self._musicbrainz_provider, self._discogs_provider)
        return self._proposal_service.create_proposal(track_metadata, providers)


def create_metadata_proposal(
    track_metadata: TrackMetadataDTO,
    resolver: MetadataCandidateResolver | None = None,
    musicbrainz_provider: MusicBrainzMetadataProvider | None = None,
    discogs_provider: DiscogsMetadataProvider | None = None,
    beatport_provider: BeatportMetadataProvider | None = None,
) -> MetadataProposalDTO:
    service = CombinedMetadataProposalService(
        resolver=resolver,
        musicbrainz_provider=musicbrainz_provider,
        discogs_provider=discogs_provider,
        beatport_provider=beatport_provider,
    )
    return service.create_metadata_proposal(track_metadata)

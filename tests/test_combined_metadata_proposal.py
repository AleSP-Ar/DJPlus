import unittest

from app.services.discogs_metadata_provider import DiscogsMetadataProvider
from app.services.metadata_candidate_proposal import MetadataProviderError
from app.services.metadata_candidate_resolver import MetadataCandidateResolver
from app.services.musicbrainz_metadata_provider import MusicBrainzMetadataProvider
from app.services.provider_transport import ProviderTransport, TransportErrorDTO, TransportRequestDTO, TransportResponseDTO
from app.services.track_metadata_editor import TrackMetadataDTO
from app.services.metadata_proposal_orchestrator import CombinedMetadataProposalService, create_metadata_proposal


class RoutingTransport(ProviderTransport):
    def __init__(self, musicbrainz_payload=None, discogs_payload=None, musicbrainz_error=None, discogs_error=None):
        self.musicbrainz_payload = musicbrainz_payload
        self.discogs_payload = discogs_payload
        self.musicbrainz_error = musicbrainz_error
        self.discogs_error = discogs_error

    def send(self, request: TransportRequestDTO):
        if "musicbrainz.org" in request.url:
            if self.musicbrainz_error is not None:
                return self.musicbrainz_error
            return self._success(self.musicbrainz_payload or {"recordings": []})
        if "discogs.com" in request.url:
            if self.discogs_error is not None:
                return self.discogs_error
            return self._success(self.discogs_payload or {"results": []})
        raise AssertionError(f"Unexpected URL: {request.url}")

    @staticmethod
    def _success(payload):
        return TransportResponseDTO(request_id="test", status_code=200, duration_ms=0, json_body=payload)


class CombinedMetadataProposalServiceTests(unittest.TestCase):
    def setUp(self):
        self.metadata = TrackMetadataDTO(
            track_id=1,
            title="Song Title",
            artist="Artist Name",
            album="Album Name",
            genre="progressive_house",
            rating=0,
            bpm=None,
            key=None,
            energy=0,
        )

    def test_both_providers_coincide(self):
        transport = RoutingTransport(
            musicbrainz_payload={"recordings": [{"score": 100, "genres": [{"name": "Progressive House"}]}]},
            discogs_payload={"results": [{"id": 1, "genre": ["Progressive House"], "style": ["Deep"], "score": 95}]},
        )
        service = CombinedMetadataProposalService(
            resolver=MetadataCandidateResolver(taxonomy_path="config/genres-v1.json", style_taxonomy_path="config/styles-v1.json"),
            musicbrainz_provider=MusicBrainzMetadataProvider(transport=transport),
            discogs_provider=DiscogsMetadataProvider(transport=transport),
        )

        proposal = service.create_metadata_proposal(self.metadata)

        self.assertIsNotNone(proposal.proposed_primary_genre_id)
        self.assertGreater(proposal.proposed_evidence_count, 0)
        self.assertTrue(proposal.proposed_styles)
        self.assertEqual(proposal.conflicts, ())

    def test_providers_disagree(self):
        transport = RoutingTransport(
            musicbrainz_payload={"recordings": [{"score": 100, "genres": [{"name": "Progressive House"}]}]},
            discogs_payload={"results": [{"id": 2, "genre": ["Progressive Trance"], "style": ["Driving"], "score": 90}]},
        )
        service = CombinedMetadataProposalService(
            resolver=MetadataCandidateResolver(taxonomy_path="config/genres-v1.json", style_taxonomy_path="config/styles-v1.json"),
            musicbrainz_provider=MusicBrainzMetadataProvider(transport=transport),
            discogs_provider=DiscogsMetadataProvider(transport=transport),
        )

        proposal = service.create_metadata_proposal(self.metadata)

        self.assertTrue(any("Top genre difference below margin" in warning for warning in proposal.warnings))
        self.assertTrue(proposal.conflicts)

    def test_musicbrainz_failure_uses_discogs(self):
        transport = RoutingTransport(
            musicbrainz_error=TransportErrorDTO("unavailable", "musicbrainz unavailable", True, 0),
            discogs_payload={"results": [{"id": 1, "genre": ["Progressive House"], "style": ["Deep"], "score": 95}]},
        )
        service = CombinedMetadataProposalService(
            resolver=MetadataCandidateResolver(taxonomy_path="config/genres-v1.json", style_taxonomy_path="config/styles-v1.json"),
            musicbrainz_provider=MusicBrainzMetadataProvider(transport=transport),
            discogs_provider=DiscogsMetadataProvider(transport=transport),
        )

        proposal = service.create_metadata_proposal(self.metadata)

        self.assertTrue(any("Provider failed" in warning for warning in proposal.warnings))
        self.assertIsNotNone(proposal.proposed_primary_genre_id)

    def test_discogs_failure_uses_musicbrainz(self):
        transport = RoutingTransport(
            musicbrainz_payload={"recordings": [{"score": 100, "genres": [{"name": "Progressive House"}]}]},
            discogs_error=TransportErrorDTO("unavailable", "discogs unavailable", True, 0),
        )
        service = CombinedMetadataProposalService(
            resolver=MetadataCandidateResolver(taxonomy_path="config/genres-v1.json", style_taxonomy_path="config/styles-v1.json"),
            musicbrainz_provider=MusicBrainzMetadataProvider(transport=transport),
            discogs_provider=DiscogsMetadataProvider(transport=transport),
        )

        proposal = service.create_metadata_proposal(self.metadata)

        self.assertTrue(any("Provider failed" in warning for warning in proposal.warnings))
        self.assertIsNotNone(proposal.proposed_primary_genre_id)

    def test_both_providers_fail(self):
        transport = RoutingTransport(
            musicbrainz_error=TransportErrorDTO("unavailable", "musicbrainz unavailable", True, 0),
            discogs_error=TransportErrorDTO("unavailable", "discogs unavailable", True, 0),
        )
        service = CombinedMetadataProposalService(
            resolver=MetadataCandidateResolver(taxonomy_path="config/genres-v1.json", style_taxonomy_path="config/styles-v1.json"),
            musicbrainz_provider=MusicBrainzMetadataProvider(transport=transport),
            discogs_provider=DiscogsMetadataProvider(transport=transport),
        )

        proposal = service.create_metadata_proposal(self.metadata)

        self.assertEqual(proposal.proposed_primary_genre_id, None)
        self.assertEqual(proposal.proposed_evidence_count, 0)
        self.assertEqual(len(proposal.warnings), 2)

    def test_result_is_deterministic(self):
        transport = RoutingTransport(
            musicbrainz_payload={"recordings": [{"score": 100, "genres": [{"name": "Progressive House"}]}]},
            discogs_payload={"results": [{"id": 1, "genre": ["Progressive House"], "style": ["Deep"], "score": 95}]},
        )
        service = CombinedMetadataProposalService(
            resolver=MetadataCandidateResolver(taxonomy_path="config/genres-v1.json", style_taxonomy_path="config/styles-v1.json"),
            musicbrainz_provider=MusicBrainzMetadataProvider(transport=transport),
            discogs_provider=DiscogsMetadataProvider(transport=transport),
        )

        first = service.create_metadata_proposal(self.metadata)
        second = service.create_metadata_proposal(self.metadata)

        self.assertEqual(first, second)

    def test_module_level_helper_returns_proposal(self):
        proposal = create_metadata_proposal(self.metadata)
        self.assertIsInstance(proposal, type(create_metadata_proposal(self.metadata)))


if __name__ == '__main__':
    unittest.main()

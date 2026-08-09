import unittest
from dataclasses import dataclass
from typing import Iterable

from app.services.metadata_candidate_proposal import (
    MetadataCandidateProposalService,
    MetadataProviderError,
    MetadataCandidateProviderProtocol,
    MetadataProviderTimeoutError,
    MetadataProposalDTO,
)
from app.services.metadata_candidate_resolver import CandidateDTO, MetadataCandidateResolver
from app.services.track_metadata_editor import TrackMetadataDTO


@dataclass(frozen=True)
class MockProvider:
    candidates: tuple[CandidateDTO, ...]
    fail: bool = False
    timeout: bool = False

    def fetch_candidates(self, current_metadata: TrackMetadataDTO) -> Iterable[CandidateDTO]:
        if self.fail:
            raise MetadataProviderError("failure")
        if self.timeout:
            raise MetadataProviderTimeoutError("timeout")
        return self.candidates


class MetadataCandidateProposalTests(unittest.TestCase):

    def test_uses_a_broad_fallback_only_when_no_beatport_visible_genre_resolves(self):
        resolver = MetadataCandidateResolver(taxonomy_path="config/genres-v1.json")
        proposal = MetadataCandidateProposalService(resolver).create_proposal(
            TrackMetadataDTO(1, "Track", "Artist", None, None, 0, None, None, 0),
            [MockProvider((CandidateDTO("test", "Electronic", [], .80),))],
        )
        self.assertEqual((proposal.proposed_primary_genre_id, proposal.proposed_primary_genre_label, proposal.proposed_primary_confidence), ("edm", "EDM", .80))
    def setUp(self):
        resolver = MetadataCandidateResolver(taxonomy_path="config/genres-v1.json")
        self.service = MetadataCandidateProposalService(resolver)
        self.current_metadata = TrackMetadataDTO(
            track_id=1,
            title="Test",
            artist="Artist",
            album="Album",
            genre="progressive_house",
            rating=0,
            bpm=None,
            key=None,
            energy=0,
        )

    def test_two_providers_coincide(self):
        providers = (
            MockProvider((CandidateDTO(source="A", genre_term="Prog House", style_terms=["organic house"], confidence=0.9),)),
            MockProvider((CandidateDTO(source="B", genre_term="progressive_house", style_terms=["deep"], confidence=0.8),)),
        )
        proposal = self.service.create_proposal(self.current_metadata, providers)
        self.assertEqual(proposal.proposed_primary_genre_id, "progressive_house")
        self.assertTrue(any(style[0] == "organic" or style[0] == "deep" for style in proposal.proposed_styles))
        self.assertEqual(proposal.current_metadata.genre, "progressive_house")

    def test_proposes_the_highest_confidence_external_label(self):
        providers = (
            MockProvider((CandidateDTO(source="A", genre_term="Prog House", style_terms=[], confidence=0.8, label="First Label"),)),
            MockProvider((CandidateDTO(source="B", genre_term="Prog House", style_terms=[], confidence=0.9, label="Preferred Label"),)),
        )

        proposal = self.service.create_proposal(self.current_metadata, providers)

        self.assertEqual(proposal.proposed_label, "Preferred Label")

    def test_two_providers_disagree(self):
        providers = (
            MockProvider((CandidateDTO(source="A", genre_term="Prog House", style_terms=[], confidence=0.9),)),
            MockProvider((CandidateDTO(source="B", genre_term="progressive_trance", style_terms=[], confidence=0.9),)),
        )
        proposal = self.service.create_proposal(self.current_metadata, providers)
        self.assertIsNone(proposal.proposed_primary_genre_id)
        self.assertTrue(any("Top genre difference below margin" in w for w in proposal.warnings))
        self.assertEqual(proposal.ambiguous_terms, ())
        self.assertEqual(proposal.conflicts, ("Conflict between sources: multiple distinct resolved genres proposed",))
        self.assertEqual(len(proposal.candidate_genres), 2)
        self.assertGreater(proposal.proposed_evidence_count, 0)

    def test_timeout_generates_warning_and_continues(self):
        providers = (MockProvider((), timeout=True),)
        proposal = self.service.create_proposal(self.current_metadata, providers)
        self.assertTrue(any("Provider failed" in w for w in proposal.warnings))
        self.assertIsNone(proposal.proposed_primary_genre_id)

    def test_metadata_provider_error_allows_continue(self):
        providers = (MockProvider((), fail=True),)
        proposal = self.service.create_proposal(self.current_metadata, providers)
        self.assertTrue(any("Provider failed" in w for w in proposal.warnings))
        self.assertIsNone(proposal.proposed_primary_genre_id)

    def test_runtime_error_propagates(self):
        class BadProvider:
            def fetch_candidates(self, current_metadata: TrackMetadataDTO):
                raise RuntimeError("unexpected")

        with self.assertRaises(RuntimeError):
            self.service.create_proposal(self.current_metadata, providers=(BadProvider(),))

    def test_type_error_internal_provider_propagates(self):
        class BadProvider:
            def fetch_candidates(self, current_metadata: TrackMetadataDTO):
                raise TypeError("bug")

        with self.assertRaises(TypeError):
            self.service.create_proposal(self.current_metadata, providers=(BadProvider(),))

    def test_zero_providers_preserves_empty_output(self):
        proposal = self.service.create_proposal(self.current_metadata, providers=())
        self.assertEqual(proposal.proposed_primary_genre_id, None)
        self.assertEqual(proposal.proposed_evidence_count, 0)
        self.assertEqual(proposal.candidate_genres, ())
        self.assertEqual(proposal.conflicts, ())
        self.assertEqual(proposal.ambiguous_terms, ())
        self.assertEqual(proposal.unknown_terms, ())
        self.assertEqual(proposal.warnings, ())

    def test_provider_partial_data(self):
        providers = (
            MockProvider((CandidateDTO(source="A", genre_term="prog house", style_terms=[], confidence=0.0),)),
        )
        proposal = self.service.create_proposal(self.current_metadata, providers)
        self.assertEqual(proposal.proposed_primary_genre_id, None)
        self.assertEqual(proposal.proposed_evidence_count, 0)

    def test_provider_fails(self):
        providers = (MockProvider((), fail=True),)
        proposal = self.service.create_proposal(self.current_metadata, providers)
        self.assertEqual(proposal.proposed_primary_genre_id, None)
        self.assertTrue(any("Provider failed" in w for w in proposal.warnings))

    def test_timeout_simulated(self):
        providers = (MockProvider((), timeout=True),)
        proposal = self.service.create_proposal(self.current_metadata, providers)
        self.assertEqual(proposal.proposed_primary_genre_id, None)
        self.assertTrue(any("Provider failed" in w for w in proposal.warnings))

    def test_all_providers_fail(self):
        providers = (MockProvider((), fail=True), MockProvider((), fail=True))
        proposal = self.service.create_proposal(self.current_metadata, providers)
        self.assertEqual(proposal.proposed_primary_genre_id, None)
        self.assertEqual(proposal.proposed_evidence_count, 0)
        self.assertEqual(len(proposal.warnings), 2)

    def test_offline_mode(self):
        proposal = self.service.create_proposal(self.current_metadata, providers=())
        self.assertIsNone(proposal.proposed_primary_genre_id)
        self.assertEqual(proposal.proposed_styles, ())

    def test_input_metadata_not_modified(self):
        original = self.current_metadata
        proposal = self.service.create_proposal(original, providers=())
        self.assertIs(proposal.current_metadata, original)
        self.assertEqual(original.genre, "progressive_house")

    def test_genres_and_styles_separated(self):
        providers = (
            MockProvider((CandidateDTO(source="A", genre_term="prog house", style_terms=["deep"], confidence=0.9),)),
        )
        proposal = self.service.create_proposal(self.current_metadata, providers)
        self.assertEqual(proposal.proposed_primary_genre_id, "progressive_house")
        self.assertTrue(all(isinstance(style, tuple) for style in proposal.proposed_styles))

    def test_deterministic_same_input(self):
        providers = (
            MockProvider((CandidateDTO(source="A", genre_term="prog house", style_terms=["deep"], confidence=0.9),)),
        )
        first = self.service.create_proposal(self.current_metadata, providers)
        second = self.service.create_proposal(self.current_metadata, providers)
        self.assertEqual(first, second)


if __name__ == '__main__':
    unittest.main()

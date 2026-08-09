import unittest

from app.services.discogs_metadata_provider import DiscogsMetadataProvider
from app.services.metadata_candidate_proposal import MetadataProviderError, MetadataProviderTimeoutError
from app.services.provider_transport import MockProviderTransport
from app.services.track_metadata_editor import TrackMetadataDTO


class DiscogsMetadataProviderTests(unittest.TestCase):
    def setUp(self):
        self.metadata = TrackMetadataDTO(
            track_id=1,
            title="Song Title",
            artist="Artist Name",
            album="Album Name",
            genre="house",
            rating=0,
            bpm=None,
            key=None,
            energy=0,
        )

    def test_fetch_candidates_returns_candidates_from_json(self):
        json_body = {
            "results": [
                {"id": 1, "title": "Artist - Title", "genre": ["Deep House"], "style": ["Hypnotic"], "score": 95},
                {"id": 2, "title": "Artist - Title", "genre": ["Progressive Trance"], "style": ["Driving"], "score": 85},
            ]
        }
        transport = MockProviderTransport(json_body=json_body)
        provider = DiscogsMetadataProvider(transport=transport)

        candidates = tuple(provider.fetch_candidates(self.metadata))

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].genre_term, "Deep House")
        self.assertEqual(candidates[0].style_terms, ["Hypnotic"])
        self.assertEqual(candidates[0].confidence, 0.95)
        self.assertEqual(candidates[1].genre_term, "Progressive Trance")
        self.assertEqual(candidates[1].style_terms, ["Driving"])

    def test_query_fallback_removes_mix_suffix_and_album(self):
        provider = DiscogsMetadataProvider(transport=MockProviderTransport())
        metadata = TrackMetadataDTO(1, "Directions (Original Mix)", "1979", "Compilation", None, 0, None, None, 0)

        self.assertEqual(
            provider._build_queries(metadata),
            ("Directions (Original Mix) 1979 Compilation", "Directions 1979"),
        )

    def test_remix_fallback_filters_unrelated_releases(self):
        provider = DiscogsMetadataProvider(transport=MockProviderTransport())
        metadata = TrackMetadataDTO(1, "Cola (ARTBAT Remix)", "CamelPhat", None, None, 0, None, None, 0)
        results = [
            {"title": "Camelphat - Dark Matter"},
            {"title": "CamelPhat & Elderbrook - Cola (ARTBAT Remix)"},
        ]

        self.assertEqual(
            provider._matching_results(results, metadata),
            [{"title": "CamelPhat & Elderbrook - Cola (ARTBAT Remix)"}],
        )

    def test_fetch_candidates_ignores_invalid_json(self):
        transport = MockProviderTransport(text_body="not json")
        provider = DiscogsMetadataProvider(transport=transport)

        with self.assertRaises(MetadataProviderError):
            tuple(provider.fetch_candidates(self.metadata))

    def test_fetch_candidates_timeout_raises_metadata_timeout(self):
        transport = MockProviderTransport(scenario="timeout")
        provider = DiscogsMetadataProvider(transport=transport)

        with self.assertRaises(MetadataProviderTimeoutError):
            tuple(provider.fetch_candidates(self.metadata))

    def test_fetch_candidates_unavailable_raises_metadata_error(self):
        transport = MockProviderTransport(scenario="unavailable")
        provider = DiscogsMetadataProvider(transport=transport)

        with self.assertRaises(MetadataProviderError):
            tuple(provider.fetch_candidates(self.metadata))

    def test_fetch_candidates_uses_headers_and_timeout(self):
        transport = MockProviderTransport(json_body={"results": []})
        provider = DiscogsMetadataProvider(transport=transport, user_agent="DJPlus Test/1.0", timeout_seconds=12, access_token="secret-token")

        tuple(provider.fetch_candidates(self.metadata))

        self.assertEqual(len(transport.calls), 1)
        request = transport.calls[0]
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.timeout_ms, 12000)
        self.assertIn("User-Agent", dict(request.headers))
        self.assertIn("Authorization", dict(request.headers))
        self.assertTrue("discogs.com" in request.url)
        self.assertIn("artist=Artist+Name", request.url)
        self.assertIn("track=Song+Title", request.url)

    def test_fetch_candidates_uses_artist_and_clean_track_for_mix_titles(self):
        transport = MockProviderTransport(json_body={
            "results": [{"id": 14507051, "title": "1979 - Where Are You / Directions / Lock 33", "label": ["Soma"], "genre": ["Electronic"], "style": ["Progressive House"], "score": 95}]
        })
        provider = DiscogsMetadataProvider(transport=transport)
        metadata = TrackMetadataDTO(1, "Directions (Original Mix)", "1979", None, None, 0, None, None, 0)

        candidates = tuple(provider.fetch_candidates(metadata))

        self.assertEqual(candidates[0].genre_term, "Progressive House")
        self.assertEqual(candidates[0].label, "Soma")
        self.assertIn("artist=1979", transport.calls[0].url)
        self.assertIn("track=Directions", transport.calls[0].url)

    def test_fetch_candidates_deduplicates_and_orders_deterministically(self):
        json_body = {
            "results": [
                {"id": 1, "title": "Artist - Title", "genre": ["Deep House"], "style": ["Hypnotic"], "score": 0.75},
                {"id": 2, "title": "Artist - Title", "genre": ["Deep House"], "style": ["Hypnotic"], "score": 0.9},
                {"id": 3, "title": "Artist - Title", "genre": ["Progressive Trance"], "style": ["Driving"], "score": 0.8},
            ]
        }
        transport = MockProviderTransport(json_body=json_body)
        provider = DiscogsMetadataProvider(transport=transport)

        candidates = tuple(provider.fetch_candidates(self.metadata))

        self.assertEqual([c.genre_term for c in candidates], ["Deep House", "Progressive Trance"])
        self.assertEqual(candidates[0].style_terms, ["Hypnotic"])

    def test_fetch_candidates_returns_empty_when_no_results(self):
        transport = MockProviderTransport(json_body={"results": []})
        provider = DiscogsMetadataProvider(transport=transport)

        candidates = tuple(provider.fetch_candidates(self.metadata))

        self.assertEqual(candidates, ())

    def test_constructor_does_not_call_transport(self):
        transport = MockProviderTransport(json_body={"results": []})
        DiscogsMetadataProvider(transport=transport)
        self.assertEqual(len(transport.calls), 0)


if __name__ == '__main__':
    unittest.main()

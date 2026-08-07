import unittest
from app.services.musicbrainz_metadata_provider import MusicBrainzMetadataProvider, MusicBrainzAPIClient
from app.services.provider_transport import MockProviderTransport
from app.services.track_metadata_editor import TrackMetadataDTO
from app.services.metadata_candidate_proposal import MetadataProviderError, MetadataProviderTimeoutError


class MusicBrainzMetadataProviderTests(unittest.TestCase):
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
            "recordings": [
                {
                    "score": 95,
                    "genres": [{"name": "progressive_house"}],
                    "tags": [{"name": "electro"}],
                },
                {
                    "score": 80,
                    "genres": [{"name": "deep_house"}],
                },
            ]
        }
        transport = MockProviderTransport(json_body=json_body)
        provider = MusicBrainzMetadataProvider(transport=transport)

        candidates = tuple(provider.fetch_candidates(self.metadata))

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].genre_term, "progressive_house")
        self.assertEqual(candidates[0].confidence, 0.95)
        self.assertEqual(candidates[1].genre_term, "deep_house")
        self.assertEqual(candidates[1].confidence, 0.8)

    def test_fetch_candidates_ignores_invalid_json(self):
        transport = MockProviderTransport(text_body="not json")
        provider = MusicBrainzMetadataProvider(transport=transport)

        with self.assertRaises(MetadataProviderError):
            tuple(provider.fetch_candidates(self.metadata))

    def test_fetch_candidates_timeout_raises_metadata_timeout(self):
        transport = MockProviderTransport(scenario="timeout")
        provider = MusicBrainzMetadataProvider(transport=transport)

        with self.assertRaises(MetadataProviderTimeoutError):
            tuple(provider.fetch_candidates(self.metadata))

    def test_fetch_candidates_unavailable_raises_metadata_error(self):
        transport = MockProviderTransport(scenario="unavailable")
        provider = MusicBrainzMetadataProvider(transport=transport)

        with self.assertRaises(MetadataProviderError):
            tuple(provider.fetch_candidates(self.metadata))

    def test_fetch_candidates_uses_user_agent_and_timeout(self):
        transport = MockProviderTransport(json_body={"recordings": []})
        provider = MusicBrainzMetadataProvider(transport=transport, user_agent="DJPlus Test/1.0", timeout_seconds=12)

        tuple(provider.fetch_candidates(self.metadata))

        self.assertEqual(len(transport.calls), 1)
        request = transport.calls[0]
        self.assertEqual(request.method, "GET")
        self.assertIn("User-Agent", dict(request.headers))
        self.assertEqual(request.headers[0][0], "User-Agent")
        self.assertEqual(request.headers[0][1], "DJPlus Test/1.0")
        self.assertEqual(request.timeout_ms, 12000)
        self.assertTrue("musicbrainz.org/ws/2/recording" in request.url)

    def test_fetch_candidates_deterministic_order(self):
        json_body = {
            "recordings": [
                {"score": 80, "genres": [{"name": "deep_house"}]},
                {"score": 95, "genres": [{"name": "progressive_house"}]},
                {"score": 80, "genres": [{"name": "acid_house"}]},
            ]
        }
        transport = MockProviderTransport(json_body=json_body)
        provider = MusicBrainzMetadataProvider(transport=transport)

        candidates = tuple(provider.fetch_candidates(self.metadata))

        self.assertEqual([c.genre_term for c in candidates], ["progressive_house", "acid_house", "deep_house"])

    def test_fetch_candidates_tags_do_not_generate_style_terms(self):
        json_body = {
            "recordings": [
                {"score": 90, "genres": [{"name": "progressive_house"}], "tags": [{"name": "electro"}]},
            ]
        }
        transport = MockProviderTransport(json_body=json_body)
        provider = MusicBrainzMetadataProvider(transport=transport)

        candidates = tuple(provider.fetch_candidates(self.metadata))

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].genre_term, "progressive_house")
        self.assertEqual(candidates[0].style_terms, [])

    def test_fetch_candidates_tags_without_genres_returns_empty(self):
        json_body = {
            "recordings": [
                {"score": 90, "tags": [{"name": "electro"}]},
            ]
        }
        transport = MockProviderTransport(json_body=json_body)
        provider = MusicBrainzMetadataProvider(transport=transport)

        candidates = tuple(provider.fetch_candidates(self.metadata))

        self.assertEqual(candidates, ())

    def test_rate_limiter_allows_first_request_immediately(self):
        t = MockProviderTransport(json_body={"recordings": []})
        times = [0.0]
        slept = []
        provider = MusicBrainzMetadataProvider(
            transport=t,
            interval_seconds=1.0,
            clock=lambda: times[0],
            sleeper=lambda wait: slept.append(wait),
        )

        provider.fetch_candidates(self.metadata)
        self.assertEqual(slept, [])

    def test_rate_limiter_waits_for_remaining_interval(self):
        t = MockProviderTransport(json_body={"recordings": []})
        current_time = [0.0]
        slept = []

        def clock():
            return current_time[0]

        def sleeper(wait):
            slept.append(wait)
            current_time[0] += wait

        provider = MusicBrainzMetadataProvider(
            transport=t,
            interval_seconds=1.0,
            clock=clock,
            sleeper=sleeper,
        )

        provider.fetch_candidates(self.metadata)
        current_time[0] = 0.5
        provider.fetch_candidates(self.metadata)

        self.assertEqual(slept, [0.5])
        self.assertEqual(len(t.calls), 2)

    def test_rate_limiter_does_not_wait_after_interval(self):
        t = MockProviderTransport(json_body={"recordings": []})
        current_time = [0.0]
        slept = []

        def clock():
            return current_time[0]

        def sleeper(wait):
            slept.append(wait)
            current_time[0] += wait

        provider = MusicBrainzMetadataProvider(
            transport=t,
            interval_seconds=1.0,
            clock=clock,
            sleeper=sleeper,
        )

        provider.fetch_candidates(self.metadata)
        current_time[0] = 1.5
        provider.fetch_candidates(self.metadata)

        self.assertEqual(slept, [])
        self.assertEqual(len(t.calls), 2)

    def test_constructor_does_not_wait_or_call_transport(self):
        t = MockProviderTransport(json_body={"recordings": []})
        provider = MusicBrainzMetadataProvider(
            transport=t,
            interval_seconds=1.0,
            clock=lambda: 0.0,
            sleeper=lambda wait: (_ for _ in ()).throw(AssertionError("sleeper should not be called during constructor")),
        )
        self.assertEqual(len(t.calls), 0)

    def test_result_limit_controls_query_limit(self):
        t = MockProviderTransport(json_body={"recordings": []})
        provider = MusicBrainzMetadataProvider(
            transport=t,
            limit=3,
        )

        provider.fetch_candidates(self.metadata)
        request = t.calls[0]
        self.assertIn("limit=3", request.url)

    def test_duplicate_genres_still_deterministic(self):
        json_body = {
            "recordings": [
                {"score": 90, "genres": [{"name": "progressive_house"}]},
                {"score": 90, "genres": [{"name": "progressive_house"}]},
            ]
        }
        transport = MockProviderTransport(json_body=json_body)
        provider = MusicBrainzMetadataProvider(transport=transport)

        candidates = tuple(provider.fetch_candidates(self.metadata))
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].genre_term, "progressive_house")
        self.assertEqual(candidates[0].style_terms, [])

    def test_search_recordings_raises_when_empty_query(self):
        client = MusicBrainzAPIClient(transport=MockProviderTransport(json_body={"recordings": []}), user_agent="DJPlus/1.0")
        with self.assertRaises(ValueError):
            client.search_recordings("")

    def test_search_recordings_bad_status_raises(self):
        transport = MockProviderTransport(status_code=500, json_body={"error": "oops"})
        client = MusicBrainzAPIClient(transport=transport, user_agent="DJPlus/1.0")
        with self.assertRaises(MetadataProviderError):
            client.search_recordings("query")

    def test_search_recordings_invalid_recordings_field_raises(self):
        transport = MockProviderTransport(json_body={"recordings": "not a list"})
        client = MusicBrainzAPIClient(transport=transport, user_agent="DJPlus/1.0")
        with self.assertRaises(MetadataProviderError):
            client.search_recordings("query")

    def test_search_recordings_transport_error_retries(self):
        transport = MockProviderTransport(scenario="unavailable")
        client = MusicBrainzAPIClient(transport=transport, user_agent="DJPlus/1.0")
        with self.assertRaises(MetadataProviderError):
            client.search_recordings("query")

    def test_provider_does_not_use_http_on_init(self):
        transport = MockProviderTransport(json_body={"recordings": []})
        MusicBrainzMetadataProvider(transport=transport)
        self.assertEqual(len(transport.calls), 0)


if __name__ == '__main__':
    unittest.main()

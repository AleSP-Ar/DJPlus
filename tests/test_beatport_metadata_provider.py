import json
import unittest
import requests
from app.services.beatport_metadata_provider import BeatportHTTPClient, BeatportMetadataProvider
from app.services.metadata_candidate_proposal import MetadataProviderTimeoutError
from app.services.track_metadata_editor import TrackMetadataDTO

class _Response:
    def __init__(self, text="", status_code=200, content=b"", headers=None): self.text, self.status_code, self.content, self.headers = text, status_code, content, headers or {}
class _Session:
    def __init__(self, responses): self.responses = list(responses); self.calls = []
    def get(self, url, **kwargs): self.calls.append((url, kwargs)); response = self.responses.pop(0); return response() if callable(response) else response

class BeatportMetadataProviderTests(unittest.TestCase):
    def setUp(self): self.metadata = TrackMetadataDTO(1, "Cola (ARTBAT Remix)", "CamelPhat", None, None, 0, None, None, 0)
    def _page(self, tracks): return _Response('<script id="__NEXT_DATA__" type="application/json">' + json.dumps({"props": {"pageProps": {"tracks": tracks}}}) + "</script>")
    def test_parses_verified_track_normalizes_classification_and_downloads_cover(self):
        track = {"name": "Cola", "mix_name": "ARTBAT Remix", "artists": [{"name": "CamelPhat"}], "bpm": 124, "key": {"name": "8A"}, "genre": {"name": "Tech House"}, "sub_genre": {"name": "Deep Tech"}, "release": {"name": "Cola", "label": {"name": "Siamese"}}, "image": "https://cdn.example/cover.jpg"}
        session = _Session([self._page([track]), _Response(content=b"jpg", headers={"Content-Type": "image/jpeg"})])
        candidate = tuple(BeatportMetadataProvider(session=session, min_interval_seconds=0).fetch_candidates(self.metadata))[0]
        self.assertTrue(candidate.identity_verified); self.assertEqual(candidate.genre_term, "Tech House"); self.assertEqual(candidate.style_terms, ["Deep Tech"])
        self.assertEqual(candidate.metadata_values["bpm"], 124.0); self.assertEqual(candidate.artwork_data, b"jpg"); self.assertEqual(candidate.metadata_values["label"], "Siamese")
    def test_original_mix_does_not_match_a_remix(self):
        track = {"name": "Cola", "mix_name": "Original Mix", "artists": [{"name": "CamelPhat"}]}
        self.assertEqual(tuple(BeatportMetadataProvider(session=_Session([self._page([track])]), min_interval_seconds=0).fetch_candidates(self.metadata)), ())
    def test_ambiguous_identity_does_not_auto_apply(self):
        first = {"id": 1, "name": "Cola", "mix_name": "ARTBAT Remix", "artists": [{"name": "CamelPhat"}]}; second = dict(first, id=2)
        self.assertEqual(tuple(BeatportMetadataProvider(session=_Session([self._page([first, second])]), min_interval_seconds=0).fetch_candidates(self.metadata)), ())
    def test_cover_failure_keeps_metadata_result(self):
        track = {"name": "Cola", "mix_name": "ARTBAT Remix", "artists": [{"name": "CamelPhat"}], "genre": {"name": "Tech House"}, "image": "https://cdn.example/cover.jpg"}
        result = tuple(BeatportMetadataProvider(session=_Session([self._page([track]), _Response(status_code=404)]), min_interval_seconds=0).fetch_candidates(self.metadata))[0]
        self.assertIsNone(result.artwork_data)
    def test_timeout_is_typed(self):
        def timeout(): raise requests.Timeout()
        with self.assertRaises(MetadataProviderTimeoutError): BeatportMetadataProvider(session=_Session([timeout]), min_interval_seconds=0).fetch_candidates(self.metadata)
    def test_rate_limit_waits_between_requests(self):
        session = _Session([_Response("one"), _Response("two")]); waits = []; now = iter((0.0, 0.1, 0.1, 0.1))
        client = BeatportHTTPClient(session=session, min_interval_seconds=1.0, sleeper=waits.append, clock=lambda: next(now))
        client.get("https://example/one"); client.get("https://example/two"); self.assertEqual(waits, [0.9])

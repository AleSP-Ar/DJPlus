import unittest

from app.services.beatport_metadata_provider import BeatportMetadataProvider
from app.services.provider_transport import MockProviderTransport, TransportResponseDTO
from app.services.track_metadata_editor import TrackMetadataDTO


class BeatportMetadataProviderTests(unittest.TestCase):
    def setUp(self): self.metadata = TrackMetadataDTO(1, "Cola (ARTBAT Remix)", "CamelPhat", None, None, 0, None, None, 0)

    def test_returns_genre_subgenre_and_release_label_from_track_detail(self):
        transport = MockProviderTransport(json_body={"tracks": {"data": [{"id": 42, "name": "Cola (ARTBAT Remix)", "artists": [{"name": "CamelPhat"}]}]}})
        original_send = transport.send
        def send(request):
            if "/catalog/tracks/42/" in request.url:
                transport.calls.append(request)
                return TransportResponseDTO(request.request_id, 200, 1, {}, {"name": "Cola (ARTBAT Remix)", "artists": [{"name": "CamelPhat"}], "genre": {"name": "Tech House"}, "sub_genre": {"name": "Deep Tech"}, "release": {"label": {"name": "Siamese"}}}, None)
            return original_send(request)
        transport.send = send
        candidate = tuple(BeatportMetadataProvider(transport=transport, access_token="token").fetch_candidates(self.metadata))[0]
        self.assertEqual((candidate.genre_term, candidate.style_terms, candidate.label, candidate.confidence), ("Tech House", ["Deep Tech"], "Siamese", .95))
        self.assertTrue(all("Authorization" in dict(request.headers) for request in transport.calls))

    def test_returns_no_candidates_without_an_oauth_token(self):
        self.assertEqual(tuple(BeatportMetadataProvider(transport=MockProviderTransport(), access_token="").fetch_candidates(self.metadata)), ())

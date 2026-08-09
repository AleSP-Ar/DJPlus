"""Beatport catalog provider using the public OAuth API only."""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlencode

from .metadata_candidate_proposal import MetadataCandidateProviderProtocol, MetadataProviderError, MetadataProviderTimeoutError
from .metadata_candidate_resolver import CandidateDTO
from .provider_transport import ProviderTransport, TransportErrorDTO, TransportRequestDTO, TransportResponseDTO
from .discogs_metadata_provider import DiscogsHTTPTransport
from .track_metadata_editor import TrackMetadataDTO


@dataclass(frozen=True)
class BeatportAPIClient:
    transport: ProviderTransport
    access_token: str | None = None
    timeout_seconds: int = 10

    def get(self, path: str, parameters: dict[str, str] | None = None) -> dict[str, Any]:
        if not self.access_token:
            return {}
        url = f"https://api.beatport.com/v4{path}"
        if parameters:
            url = f"{url}?{urlencode(parameters)}"
        response = self.transport.send(TransportRequestDTO(
            request_id=f"beatport-{int(time.time() * 1000)}", method="GET", url=url,
            timeout_ms=self.timeout_seconds * 1000,
            headers={"Accept": "application/json", "Authorization": f"Bearer {self.access_token}"},
        ))
        if isinstance(response, TransportErrorDTO):
            if response.code == "timeout":
                raise MetadataProviderTimeoutError("Beatport request timed out")
            raise MetadataProviderError("Beatport transport error")
        if not isinstance(response, TransportResponseDTO) or response.status_code != 200:
            status = getattr(response, "status_code", "unknown")
            raise MetadataProviderError(f"Beatport returned status {status}")
        if not isinstance(response.json_body, dict):
            raise MetadataProviderError("Beatport returned invalid JSON")
        return response.json_body


class BeatportMetadataProvider(MetadataCandidateProviderProtocol):
    """Find a catalog track and expose its Beatport genre and release label."""

    def __init__(self, transport: ProviderTransport | None = None, access_token: str | None = None, timeout_seconds: int = 10):
        self._client = BeatportAPIClient(
            transport=transport or DiscogsHTTPTransport(),
            access_token=access_token if access_token is not None else os.getenv("BEATPORT_ACCESS_TOKEN"),
            timeout_seconds=timeout_seconds,
        )

    def fetch_candidates(self, current_metadata: TrackMetadataDTO) -> Iterable[CandidateDTO]:
        if not isinstance(current_metadata, TrackMetadataDTO):
            raise TypeError("current_metadata must be TrackMetadataDTO")
        if not self._client.access_token:
            return ()
        query = " ".join(part for part in (current_metadata.artist, current_metadata.title) if part and part.strip())
        if not query:
            return ()
        search = self._client.get("/catalog/search/", {"q": query, "type": "tracks", "per_page": "10"})
        track = self._best_track(self._search_tracks(search), current_metadata)
        if track is None:
            return ()
        track_id = track.get("id")
        detail = self._client.get(f"/catalog/tracks/{track_id}/") if track_id else track
        candidate = self._candidate(detail, current_metadata)
        return (candidate,) if candidate is not None else ()

    @staticmethod
    def _search_tracks(payload: dict[str, Any]) -> list[dict[str, Any]]:
        tracks = payload.get("tracks", payload.get("results", payload.get("data", [])))
        if isinstance(tracks, dict):
            tracks = tracks.get("data", tracks.get("results", []))
        return [item for item in tracks if isinstance(item, dict)] if isinstance(tracks, list) else []

    @classmethod
    def _best_track(cls, tracks: list[dict[str, Any]], metadata: TrackMetadataDTO) -> dict[str, Any] | None:
        expected_title = cls._normal(metadata.title)
        expected_artist = cls._normal(metadata.artist)
        ranked = []
        for track in tracks:
            title = cls._normal(track.get("name") or track.get("title"))
            artists = track.get("artists") or track.get("artist_name") or ""
            artist = cls._normal(" ".join(item.get("name", "") for item in artists) if isinstance(artists, list) else artists)
            score = (2 if expected_title and expected_title in title else 0) + (2 if expected_artist and expected_artist in artist else 0)
            if score:
                ranked.append((score, track))
        return max(ranked, key=lambda item: item[0])[1] if ranked else None

    @classmethod
    def _candidate(cls, track: dict[str, Any], metadata: TrackMetadataDTO) -> CandidateDTO | None:
        genre = track.get("genre") or {}
        sub_genre = track.get("sub_genre") or {}
        release = track.get("release") or {}
        label = release.get("label") or track.get("label") or {}
        genre_name = genre.get("name") if isinstance(genre, dict) else str(genre or "")
        sub_genre_name = sub_genre.get("name") if isinstance(sub_genre, dict) else str(sub_genre or "")
        label_name = label.get("name") if isinstance(label, dict) else str(label or "")
        if not any((genre_name, sub_genre_name, label_name)):
            return None
        confidence = 0.95 if cls._matches(track, metadata) else 0.70
        return CandidateDTO("beatport", genre_name or None, [sub_genre_name] if sub_genre_name else [], confidence, label_name or None)

    @classmethod
    def _matches(cls, track: dict[str, Any], metadata: TrackMetadataDTO) -> bool:
        title = cls._normal(track.get("name") or track.get("title"))
        artists = track.get("artists") or track.get("artist_name") or ""
        artist = cls._normal(" ".join(item.get("name", "") for item in artists) if isinstance(artists, list) else artists)
        return bool(cls._normal(metadata.title) in title and cls._normal(metadata.artist) in artist)

    @staticmethod
    def _normal(value: object) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()

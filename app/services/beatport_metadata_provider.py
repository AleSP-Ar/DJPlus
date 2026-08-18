"""Resilient Beatport search provider, isolated from recommendation scoring."""
from __future__ import annotations
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import quote_plus
import requests
from .metadata_candidate_proposal import MetadataCandidateProviderProtocol, MetadataProviderError, MetadataProviderTimeoutError
from .metadata_candidate_resolver import CandidateDTO
from .track_metadata_editor import TrackMetadataDTO

@dataclass(frozen=True)
class BeatportHTTPResponse:
    text: str
    status_code: int

class BeatportHTTPClient:
    """requests.Session boundary with polite rate limiting and deterministic injection."""
    def __init__(self, session=None, timeout_seconds=10, user_agent="DJPlus/1.0 (+https://github.com/AleSP-Ar/DJPlus)", min_interval_seconds=0.8, sleeper=time.sleep, clock=time.monotonic):
        self.session = session or requests.Session(); self.timeout_seconds = timeout_seconds; self.user_agent = user_agent
        self.min_interval_seconds = min_interval_seconds; self.sleeper = sleeper; self.clock = clock; self._last_request_at = None
    def get(self, url, *, accept="text/html,application/xhtml+xml"):
        if self._last_request_at is not None:
            remaining = self.min_interval_seconds - (self.clock() - self._last_request_at)
            if remaining > 0: self.sleeper(remaining)
        try: response = self.session.get(url, timeout=self.timeout_seconds, headers={"User-Agent": self.user_agent, "Accept": accept})
        except requests.Timeout as error: raise MetadataProviderTimeoutError("Beatport request timed out") from error
        except requests.RequestException as error: raise MetadataProviderError("Beatport transport error") from error
        self._last_request_at = self.clock()
        if response.status_code != 200: raise MetadataProviderError(f"Beatport returned status {response.status_code}")
        return BeatportHTTPResponse(response.text, response.status_code)
    def get_bytes(self, url):
        try: response = self.session.get(url, timeout=self.timeout_seconds, headers={"User-Agent": self.user_agent, "Accept": "image/avif,image/webp,image/*,*/*"})
        except requests.RequestException: return None, None
        if response.status_code != 200 or not response.content: return None, None
        return bytes(response.content), response.headers.get("Content-Type", "image/jpeg").split(";", 1)[0]

class BeatportMetadataProvider(MetadataCandidateProviderProtocol):
    """Beatport is authoritative only after strict artist/title/mix identity validation."""
    def __init__(self, client=None, *, session=None, timeout_seconds=10, user_agent="DJPlus/1.0 (+https://github.com/AleSP-Ar/DJPlus)", min_interval_seconds=0.8):
        self._client = client or BeatportHTTPClient(session, timeout_seconds, user_agent, min_interval_seconds)
    def fetch_candidates(self, current_metadata: TrackMetadataDTO) -> Iterable[CandidateDTO]:
        if not isinstance(current_metadata, TrackMetadataDTO): raise TypeError("current_metadata must be TrackMetadataDTO")
        query = " ".join(item.strip() for item in (current_metadata.artist, current_metadata.title) if item and item.strip())
        if not query: return ()
        tracks = self._extract_tracks(self._client.get(f"https://www.beatport.com/search?q={quote_plus(query)}").text)
        match = self._unique_identity_match(tracks, current_metadata)
        if match is None: return ()
        artwork_url = self._first_text(match, "image", "image_url", "imageUrl", "cover_url", "coverUrl")
        artwork_data, artwork_mime = self._client.get_bytes(artwork_url) if artwork_url else (None, None)
        genre = self._display_value(match.get("genre")); style = self._display_value(match.get("sub_genre") or match.get("subGenre"))
        label = self._display_value(match.get("label") or self._nested(match, "release", "label"))
        return (CandidateDTO("beatport", genre or None, [style] if style else [], 1.0, label or None, True, self._supported_values(match, current_metadata, label), artwork_data, artwork_mime, artwork_url),)
    @classmethod
    def _extract_tracks(cls, html):
        for script in re.findall(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.I | re.S):
            try: tracks = cls._track_nodes(json.loads(script))
            except json.JSONDecodeError: continue
            if tracks: return tracks
        result = []
        for item in re.findall(r'data-track=["\']([^"\']+)["\']', html, re.I):
            try: parsed = json.loads(item.replace("&quot;", '"'))
            except json.JSONDecodeError: continue
            if isinstance(parsed, dict): result.append(parsed)
        return result
    @classmethod
    def _track_nodes(cls, value):
        found = []
        if isinstance(value, dict):
            if cls._first_text(value, "name", "title") and ("artists" in value or "artist" in value or "artist_name" in value): found.append(value)
            for child in value.values(): found.extend(cls._track_nodes(child))
        elif isinstance(value, list):
            for child in value: found.extend(cls._track_nodes(child))
        return found
    @classmethod
    def _unique_identity_match(cls, tracks, metadata):
        matches = [track for track in tracks if cls._identity_matches(track, metadata)]
        unique = {(track.get("id") or (cls._normal(cls._first_text(track, "name", "title")), cls._normal(cls._artist_text(track)), cls._normal(cls._mix_text(track)))): track for track in matches}
        return next(iter(unique.values())) if len(unique) == 1 else None
    @classmethod
    def _identity_matches(cls, track, metadata):
        wanted_title, wanted_mix = cls._split_title(metadata.title); actual_title, actual_mix = cls._split_title(cls._first_text(track, "name", "title"))
        actual_mix = cls._normal(cls._first_text(track, "mix_name", "mixName", "mix") or actual_mix)
        return bool(wanted_title and wanted_title == actual_title and cls._normal(metadata.artist) == cls._normal(cls._artist_text(track)) and wanted_mix == actual_mix)
    @classmethod
    def _supported_values(cls, track, metadata, label):
        values = {"title": cls._first_text(track, "name", "title") or metadata.title, "artist": cls._artist_text(track) or metadata.artist}
        if track.get("bpm") not in (None, ""): values["bpm"] = float(track["bpm"])
        key = cls._display_value(track.get("key")); release = track.get("release") if isinstance(track.get("release"), dict) else {}
        if key: values["key"] = key
        album = cls._first_text(release, "name", "title")
        if album: values["album"] = album
        if label: values["label"] = label
        return values
    @staticmethod
    def _nested(value, *keys):
        for key in keys:
            if not isinstance(value, dict): return None
            value = value.get(key)
        return value
    @classmethod
    def _artist_text(cls, track):
        artists = track.get("artists") or track.get("artist") or track.get("artist_name") or ""
        return ", ".join(cls._display_value(item) for item in artists if cls._display_value(item)) if isinstance(artists, list) else cls._display_value(artists)
    @staticmethod
    def _display_value(value): return str((value.get("name") or value.get("title") or "") if isinstance(value, dict) else value or "").strip()
    @classmethod
    def _first_text(cls, value, *keys):
        for key in keys:
            text = cls._display_value(value.get(key) if isinstance(value, dict) else None)
            if text: return text
        return ""
    @classmethod
    def _mix_text(cls, value): return cls._first_text(value, "mix_name", "mixName", "mix") or cls._split_title(cls._first_text(value, "name", "title"))[1]
    @classmethod
    def _split_title(cls, value):
        match = re.match(r"^(.*?)(?:\s*[\(\[]([^\)\]]+)[\)\]])?$", str(value or "").strip())
        return cls._normal(match.group(1) if match else value), cls._normal(match.group(2) if match and match.group(2) else "")
    @staticmethod
    def _normal(value): return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()

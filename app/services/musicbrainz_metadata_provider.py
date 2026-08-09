from __future__ import annotations

import json
import re
import socket
import time
from threading import Lock
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from dataclasses import dataclass

from .metadata_candidate_proposal import (
    MetadataCandidateProviderProtocol,
    MetadataProviderError,
    MetadataProviderTimeoutError,
)
from .metadata_candidate_resolver import CandidateDTO
from .provider_transport import (
    ProviderTransport,
    TransportErrorDTO,
    TransportRequestDTO,
    TransportResponseDTO,
)
from .track_metadata_editor import TrackMetadataDTO


class MusicBrainzHTTPTransport(ProviderTransport):
    def send(self, request: TransportRequestDTO):
        if not isinstance(request, TransportRequestDTO):
            raise TypeError("MusicBrainzHTTPTransport.send requires TransportRequestDTO.")
        started = time.monotonic()
        headers = dict(request.headers)
        try:
            http_request = Request(request.url, headers=headers, method=request.method.upper())
            with urlopen(http_request, timeout=request.timeout_ms / 1000) as response:
                return self._response(request.request_id, response.status, response.headers, response.read(), started)
        except HTTPError as error:
            return self._response(request.request_id, error.code, error.headers, error.read(), started)
        except (socket.timeout, TimeoutError):
            return TransportErrorDTO("timeout", "MusicBrainz transport timeout.", True, self._duration(started))
        except URLError as error:
            if isinstance(error.reason, socket.timeout):
                return TransportErrorDTO("timeout", "MusicBrainz transport timeout.", True, self._duration(started))
            return TransportErrorDTO("unavailable", "MusicBrainz transport unavailable.", True, self._duration(started))
        except OSError:
            return TransportErrorDTO("unavailable", "MusicBrainz transport unavailable.", True, self._duration(started))

    def _response(self, request_id: str, status_code: int, headers: Any, raw_body: bytes, started: float):
        duration_ms = self._duration(started)
        text = raw_body.decode("utf-8", errors="replace")
        try:
            json_body = json.loads(text) if text.strip() else None
        except json.JSONDecodeError:
            json_body = None
        return TransportResponseDTO(
            request_id=request_id,
            status_code=status_code,
            duration_ms=duration_ms,
            headers=dict(headers.items()),
            json_body=json_body,
            text_body=None if json_body is not None else text,
        )

    @staticmethod
    def _duration(started: float) -> int:
        return int((time.monotonic() - started) * 1000)


@dataclass(frozen=True)
class MusicBrainzAPIClient:
    transport: ProviderTransport
    user_agent: str
    timeout_seconds: int = 10
    result_limit: int = 5
    interval_seconds: float = 1.0
    clock: Callable[[], float] = time.monotonic
    sleeper: Callable[[float], None] = time.sleep

    def __post_init__(self):
        if not isinstance(self.transport, ProviderTransport):
            raise TypeError("transport must implement ProviderTransport")
        if not isinstance(self.user_agent, str) or not self.user_agent.strip():
            raise ValueError("user_agent must be a non-empty string")
        if not isinstance(self.timeout_seconds, int) or self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be a positive integer")
        if not isinstance(self.result_limit, int) or self.result_limit < 1:
            raise ValueError("result_limit must be a positive integer")
        if not isinstance(self.interval_seconds, (int, float)) or self.interval_seconds < 0.0:
            raise ValueError("interval_seconds must be a non-negative number")
        if not callable(self.clock):
            raise TypeError("clock must be callable")
        if not callable(self.sleeper):
            raise TypeError("sleeper must be callable")
        object.__setattr__(self, "_lock", Lock())
        object.__setattr__(self, "_last_request_time", None)

    def search_recordings(self, query: str) -> List[Dict[str, Any]]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")

        params = {
            "query": query,
            "fmt": "json",
            "limit": str(self.result_limit),
            "inc": "artist-credits+releases+tags+genres",
        }
        url = f"https://musicbrainz.org/ws/2/recording?{urlencode(params)}"
        request = TransportRequestDTO(
            request_id=f"musicbrainz-{int(time.time() * 1000)}",
            method="GET",
            url=url,
            timeout_ms=self.timeout_seconds * 1000,
            headers={"User-Agent": self.user_agent},
        )
        self._apply_rate_limiting()
        response = self.transport.send(request)
        object.__setattr__(self, "_last_request_time", self.clock())
        if isinstance(response, TransportErrorDTO):
            if response.code == "timeout":
                raise MetadataProviderTimeoutError("MusicBrainz request timed out")
            raise MetadataProviderError("MusicBrainz transport error")
        if not isinstance(response, TransportResponseDTO):
            raise TypeError("Unexpected transport response type")
        if response.status_code != 200:
            raise MetadataProviderError(f"MusicBrainz returned status {response.status_code}")
        if not isinstance(response.json_body, dict):
            raise MetadataProviderError("MusicBrainz returned invalid JSON")
        recordings = response.json_body.get("recordings")
        if recordings is None:
            raise MetadataProviderError("MusicBrainz response JSON missing recordings")
        if not isinstance(recordings, list):
            raise MetadataProviderError("MusicBrainz response recordings field is invalid")
        return recordings

    def _apply_rate_limiting(self) -> None:
        with self._lock:
            now = self.clock()
            last = self._last_request_time
            if last is None:
                return
            remaining = self.interval_seconds - (now - last)
            if remaining > 0:
                self.sleeper(remaining)


class MusicBrainzMetadataProvider(MetadataCandidateProviderProtocol):
    def __init__(
        self,
        transport: ProviderTransport | None = None,
        user_agent: str = "DJPlus/1.0 (+https://github.com/AleSP-Ar/DJPlus)",
        timeout_seconds: int = 10,
        limit: int = 5,
        interval_seconds: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self._transport = transport if transport is not None else MusicBrainzHTTPTransport()
        self._client = MusicBrainzAPIClient(
            transport=self._transport,
            user_agent=user_agent,
            timeout_seconds=timeout_seconds,
            result_limit=limit,
            interval_seconds=interval_seconds,
            clock=clock,
            sleeper=sleeper,
        )

    def fetch_candidates(self, current_metadata: TrackMetadataDTO) -> Iterable[CandidateDTO]:
        if not isinstance(current_metadata, TrackMetadataDTO):
            raise TypeError("current_metadata must be TrackMetadataDTO")

        for query in self._build_queries(current_metadata):
            recordings = self._client.search_recordings(query)
            candidates = self._extract_candidates(recordings)
            if candidates:
                return candidates
        return []

    def _build_query(self, metadata: TrackMetadataDTO) -> str:
        parts: List[str] = []
        if metadata.title and metadata.title.strip():
            parts.append(f'recording:"{self._escape(metadata.title)}"')
        if metadata.artist and metadata.artist.strip():
            parts.append(f'artist:"{self._escape(metadata.artist)}"')
        if metadata.album and metadata.album.strip():
            parts.append(f'release:"{self._escape(metadata.album)}"')
        return " AND ".join(parts)

    def _build_queries(self, metadata: TrackMetadataDTO) -> tuple[str, ...]:
        strict = self._build_query(metadata)
        clean_title = self._clean_title(metadata.title)
        if not clean_title or clean_title == (metadata.title or "").strip():
            return (strict,) if strict else ()
        fallback_parts: List[str] = []
        if clean_title:
            fallback_parts.append(f'recording:"{self._escape(clean_title)}"')
        if metadata.artist and metadata.artist.strip():
            fallback_parts.append(f'artist:"{self._escape(metadata.artist)}"')
        fallback = " AND ".join(fallback_parts)
        return tuple(dict.fromkeys(query for query in (strict, fallback) if query))

    @staticmethod
    def _clean_title(value: str | None) -> str:
        if not isinstance(value, str):
            return ""
        return re.sub(r"\s*[\(\[][^\)\]]*(?:mix|edit|remix|version)[^\)\]]*[\)\]]\s*$", "", value, flags=re.IGNORECASE).strip()

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace('"', '\\"').strip()

    def _extract_candidates(self, recordings: List[Dict[str, Any]]) -> List[CandidateDTO]:
        candidates: Dict[str, tuple[float, str]] = {}
        for recording in recordings:
            confidence = self._normalize_score(recording.get("score"))
            if confidence <= 0.0:
                continue
            genre_terms = self._extract_genres(recording)
            for term in genre_terms:
                key = term.casefold().strip()
                if not key:
                    continue
                current = candidates.get(key)
                if current is None or confidence > current[0]:
                    candidates[key] = (confidence, term)
        sorted_candidates = sorted(
            candidates.values(),
            key=lambda item: (-item[0], item[1].casefold()),
        )
        return [
            CandidateDTO(source="musicbrainz", genre_term=term, style_terms=[], confidence=confidence)
            for confidence, term in sorted_candidates
        ]

    @staticmethod
    def _extract_genres(recording: Dict[str, Any]) -> List[str]:
        terms: List[str] = []
        items = recording.get("genres")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    name = item.get("name")
                    if isinstance(name, str) and name.strip():
                        terms.append(name.strip())
        return terms

    @staticmethod
    def _normalize_score(score: Any) -> float:
        try:
            value = float(score)
        except (TypeError, ValueError):
            return 0.0
        normalized = value / 100.0
        return max(0.0, min(1.0, normalized))

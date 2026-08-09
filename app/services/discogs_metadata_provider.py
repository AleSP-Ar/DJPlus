from __future__ import annotations

import json
import re
import socket
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .discogs_metadata_classifier import DiscogsMetadataClassifier, DiscogsReleaseEvidenceDTO
from .metadata_candidate_proposal import (
    MetadataCandidateProviderProtocol,
    MetadataProviderError,
    MetadataProviderTimeoutError,
)
from .metadata_candidate_resolver import CandidateDTO
from .provider_transport import ProviderTransport, TransportErrorDTO, TransportRequestDTO, TransportResponseDTO
from .track_metadata_editor import TrackMetadataDTO


class DiscogsHTTPTransport(ProviderTransport):
    def send(self, request: TransportRequestDTO):
        if not isinstance(request, TransportRequestDTO):
            raise TypeError("DiscogsHTTPTransport.send requires TransportRequestDTO.")
        started = time.monotonic()
        headers = dict(request.headers)
        try:
            http_request = Request(request.url, headers=headers, method=request.method.upper())
            with urlopen(http_request, timeout=request.timeout_ms / 1000) as response:
                return self._response(request.request_id, response.status, response.headers, response.read(), started)
        except HTTPError as error:
            return self._response(request.request_id, error.code, error.headers, error.read(), started)
        except (socket.timeout, TimeoutError):
            return TransportErrorDTO("timeout", "Discogs transport timeout.", True, self._duration(started))
        except URLError as error:
            if isinstance(error.reason, socket.timeout):
                return TransportErrorDTO("timeout", "Discogs transport timeout.", True, self._duration(started))
            return TransportErrorDTO("unavailable", "Discogs transport unavailable.", True, self._duration(started))
        except OSError:
            return TransportErrorDTO("unavailable", "Discogs transport unavailable.", True, self._duration(started))

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
class DiscogsAPIClient:
    transport: ProviderTransport
    user_agent: str
    timeout_seconds: int = 10
    access_token: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.transport, ProviderTransport):
            raise TypeError("transport must implement ProviderTransport")
        if not isinstance(self.user_agent, str) or not self.user_agent.strip():
            raise ValueError("user_agent must be a non-empty string")
        if not isinstance(self.timeout_seconds, int) or self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be a positive integer")

    def search_releases(self, query: str = "", *, artist: str | None = None, track: str | None = None) -> List[Dict[str, Any]]:
        if not isinstance(query, str):
            raise ValueError("query must be text")
        if artist is not None and (not isinstance(artist, str) or not artist.strip()):
            raise ValueError("artist must be non-empty text or None")
        if track is not None and (not isinstance(track, str) or not track.strip()):
            raise ValueError("track must be non-empty text or None")
        if not query.strip() and not (artist and track):
            raise ValueError("query or artist and track are required")

        params = {"type": "release", "per_page": "5"}
        if query.strip():
            params["q"] = query.strip()
        if artist:
            params["artist"] = artist.strip()
        if track:
            params["track"] = track.strip()
        url = f"https://api.discogs.com/database/search?{urlencode(params)}"
        request = TransportRequestDTO(
            request_id=f"discogs-{int(time.time() * 1000)}",
            method="GET",
            url=url,
            timeout_ms=self.timeout_seconds * 1000,
            headers=self._headers(),
        )
        response = self.transport.send(request)
        if isinstance(response, TransportErrorDTO):
            if response.code == "timeout":
                raise MetadataProviderTimeoutError("Discogs request timed out")
            raise MetadataProviderError("Discogs transport error")
        if not isinstance(response, TransportResponseDTO):
            raise TypeError("Unexpected transport response type")
        if response.status_code != 200:
            raise MetadataProviderError(f"Discogs returned status {response.status_code}")
        if not isinstance(response.json_body, dict):
            raise MetadataProviderError("Discogs returned invalid JSON")
        results = response.json_body.get("results")
        if results is None:
            raise MetadataProviderError("Discogs response JSON missing results")
        if not isinstance(results, list):
            raise MetadataProviderError("Discogs response results field is invalid")
        return results

    def _headers(self) -> Dict[str, str]:
        headers = {"User-Agent": self.user_agent}
        if self.access_token:
            headers["Authorization"] = f"Discogs token={self.access_token}"
        return headers


class DiscogsMetadataProvider(MetadataCandidateProviderProtocol):
    def __init__(
        self,
        transport: ProviderTransport | None = None,
        user_agent: str = "DJPlus/1.0 (+https://github.com/AleSP-Ar/DJPlus)",
        timeout_seconds: int = 10,
        access_token: Optional[str] = None,
    ):
        self._transport = transport if transport is not None else DiscogsHTTPTransport()
        self._client = DiscogsAPIClient(
            transport=self._transport,
            user_agent=user_agent,
            timeout_seconds=timeout_seconds,
            access_token=access_token,
        )
        self._classifier = DiscogsMetadataClassifier(
            taxonomy_path="config/genres-v1.json",
            style_taxonomy_path="config/styles-v1.json",
        )

    def fetch_candidates(self, current_metadata: TrackMetadataDTO) -> Iterable[CandidateDTO]:
        if not isinstance(current_metadata, TrackMetadataDTO):
            raise TypeError("current_metadata must be TrackMetadataDTO")

        clean_title = self._clean_title(current_metadata.title)
        artist = (current_metadata.artist or "").strip()
        if clean_title and artist:
            results = self._client.search_releases(artist=artist, track=clean_title)
            candidates = self._extract_candidates(results)
            if candidates:
                return candidates

            if clean_title != (current_metadata.title or "").strip():
                for query in self._build_queries(current_metadata):
                    results = self._matching_results(self._client.search_releases(query), current_metadata)
                    candidates = self._extract_candidates(results)
                    if candidates:
                        return candidates
            return []

        for query in self._build_queries(current_metadata):
            results = self._client.search_releases(query)
            candidates = self._extract_candidates(results)
            if candidates:
                return candidates
        return []

    def _build_query(self, metadata: TrackMetadataDTO) -> str:
        parts: List[str] = []
        if metadata.title and metadata.title.strip():
            parts.append(metadata.title.strip())
        if metadata.artist and metadata.artist.strip():
            parts.append(metadata.artist.strip())
        if metadata.album and metadata.album.strip():
            parts.append(metadata.album.strip())
        return " ".join(parts).strip()

    def _build_queries(self, metadata: TrackMetadataDTO) -> tuple[str, ...]:
        strict = self._build_query(metadata)
        clean_title = self._clean_title(metadata.title)
        if not clean_title or clean_title == (metadata.title or "").strip():
            return (strict,) if strict else ()
        fallback = " ".join(
            value.strip()
            for value in (clean_title, metadata.artist or "")
            if isinstance(value, str) and value.strip()
        )
        return tuple(dict.fromkeys(query for query in (strict, fallback) if query))

    @staticmethod
    def _clean_title(value: str | None) -> str:
        if not isinstance(value, str):
            return ""
        return re.sub(r"\s*[\(\[][^\)\]]*(?:mix|edit|remix|version)[^\)\]]*[\)\]]\s*$", "", value, flags=re.IGNORECASE).strip()

    @classmethod
    def _matching_results(cls, results: Iterable[Dict[str, Any]], metadata: TrackMetadataDTO) -> List[Dict[str, Any]]:
        artist = (metadata.artist or "").strip().casefold()
        title = cls._clean_title(metadata.title).casefold()
        if not artist or not title:
            return list(results)
        return [
            result
            for result in results
            if isinstance(result, dict)
            and artist in str(result.get("title", "")).casefold()
            and title in str(result.get("title", "")).casefold()
        ]

    def _extract_candidates(self, results: List[Dict[str, Any]]) -> List[CandidateDTO]:
        deduped: Dict[tuple[str, str], CandidateDTO] = {}
        for result in results:
            evidence = self._coerce_evidence(result)
            if evidence is None:
                continue
            classification = self._classifier.classify(evidence)
            candidate = self._select_release_candidate(
                classification.candidates,
                evidence.confidence,
                self._first_label(result.get("label")),
            )
            if candidate is None:
                continue
            key = (candidate.genre_term or "", "|".join(candidate.style_terms))
            if key not in deduped:
                deduped[key] = candidate
            else:
                existing = deduped[key]
                if candidate.confidence > existing.confidence:
                    deduped[key] = candidate

        ordered = sorted(
            deduped.values(),
            key=lambda item: (
                -item.confidence,
                (item.genre_term or "").casefold(),
                tuple(term.casefold() for term in item.style_terms),
                item.source.casefold(),
            ),
        )
        return ordered

    @staticmethod
    def _select_release_candidate(candidates: Iterable[CandidateDTO], confidence: float, label: Optional[str] = None) -> Optional[CandidateDTO]:
        candidates = list(candidates)
        genre_candidates = [candidate for candidate in candidates if candidate.genre_term is not None]
        style_candidates = [candidate for candidate in candidates if candidate.genre_term is None and candidate.style_terms]

        if not genre_candidates and not style_candidates:
            return None

        genre_term = genre_candidates[0].genre_term if genre_candidates else None
        style_terms: List[str] = []
        for candidate in style_candidates:
            for style_term in candidate.style_terms:
                if style_term not in style_terms:
                    style_terms.append(style_term)

        return CandidateDTO(
            source="discogs",
            genre_term=genre_term,
            style_terms=style_terms,
            confidence=float(confidence),
            label=label,
        )

    @staticmethod
    def _first_label(value: Any) -> Optional[str]:
        values = [value] if isinstance(value, str) else value if isinstance(value, list) else []
        for item in values:
            if isinstance(item, str) and item.strip():
                return item.strip()
        return None

    def _coerce_evidence(self, result: Dict[str, Any]) -> Optional[DiscogsReleaseEvidenceDTO]:
        if not isinstance(result, dict):
            return None

        raw_genres = result.get("genre")
        raw_styles = result.get("style")
        if isinstance(raw_genres, str):
            raw_genres = [raw_genres]
        elif not isinstance(raw_genres, list):
            raw_genres = []
        if isinstance(raw_styles, str):
            raw_styles = [raw_styles]
        elif not isinstance(raw_styles, list):
            raw_styles = []

        confidence = self._normalize_confidence(result.get("score"))
        release_id = result.get("id")
        return DiscogsReleaseEvidenceDTO(
            raw_genres=tuple(str(item).strip() for item in raw_genres if str(item).strip()),
            raw_styles=tuple(str(item).strip() for item in raw_styles if str(item).strip()),
            confidence=confidence,
            release_id=str(release_id) if release_id is not None else None,
        )

    @staticmethod
    def _normalize_confidence(value: Any) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.8
        if score <= 0.0:
            return 0.0
        if score > 1.0:
            return max(0.0, min(1.0, score / 100.0))
        return max(0.0, min(1.0, score))

"""Deterministic, explainable scoring for one recommendation candidate at a time."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Any

from .dj_intelligence_service import DJIntelligenceService


class RecommendationScoringError(ValueError):
    """Raised when recommendation inputs or service contracts are invalid."""


@dataclass(frozen=True)
class RecommendationReasonDTO:
    criterion: str
    contribution: int
    explanation: str

    def __post_init__(self):
        if self.criterion not in {"genre", "key", "bpm", "energy", "history"}:
            raise RecommendationScoringError("El criterio de recomendacion no es valido.")
        if not isinstance(self.contribution, int) or not 0 <= self.contribution <= 100:
            raise RecommendationScoringError("La contribucion debe estar entre 0 y 100.")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise RecommendationScoringError("La razon de recomendacion es obligatoria.")


@dataclass(frozen=True)
class RecommendationScoreDTO:
    reference_track_id: int
    candidate_track_id: int
    score: int
    reasons: tuple[RecommendationReasonDTO, ...]
    confidence: float = 1.0

    def __post_init__(self):
        for name in ("reference_track_id", "candidate_track_id"):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 1:
                raise RecommendationScoringError(f"{name} debe ser un entero positivo.")
        if not isinstance(self.score, int) or not 0 <= self.score <= 100:
            raise RecommendationScoringError("El score de recomendacion debe estar entre 0 y 100.")
        expected_order = ("genre", "key", "bpm", "energy", "history")
        if not isinstance(self.reasons, tuple) or tuple(reason.criterion for reason in self.reasons) != expected_order:
            raise RecommendationScoringError("El score debe incluir razones de genero, key, BPM, energia e historial en orden.")
        if not isinstance(self.confidence, (int, float)) or not 0 <= self.confidence <= 1:
            raise RecommendationScoringError("La confianza debe estar entre 0 y 1.")


class RecommendationScoringEngine:
    """Score one candidate using services only; it never ranks or persists candidates."""

    WEIGHTS = {"genre": 35, "key": 20, "bpm": 15, "energy": 12, "history": 18}

    def __init__(self, dj_intelligence_service, history_service):
        if not isinstance(dj_intelligence_service, DJIntelligenceService):
            raise TypeError("RecommendationScoringEngine requiere DJIntelligenceService.")
        if not callable(getattr(history_service, "count_history", None)):
            raise TypeError("RecommendationScoringEngine requiere HistoryService.")
        self._dj_intelligence_service = dj_intelligence_service
        self._history_service = history_service
        self._compatibilities = self._load_compatibilities()

    def score(self, reference_track, candidate_track):
        reference_id = self._track_id(reference_track, "referencia")
        candidate_id = self._track_id(candidate_track, "candidata")
        self._dj_intelligence_service.evaluate_compatibility(reference_track, candidate_track)
        reasons = (
            self._genre_reason(reference_track, candidate_track),
            self._key_reason(reference_track, candidate_track),
            self._bpm_reason(reference_track, candidate_track),
            self._energy_reason(reference_track, candidate_track),
            self._history_reason(candidate_id),
        )
        score = sum(reason.contribution for reason in reasons)
        score = self._finalize_score(score, reasons)
        if score < 10:
            score = 0
        confidence = self._confidence(reasons, reference_track, candidate_track)
        return RecommendationScoreDTO(reference_id, candidate_id, score, reasons, confidence)

    def _genre_reason(self, reference, candidate):
        reference_genres = self._genre_candidates(reference)
        candidate_genres = self._genre_candidates(candidate)
        reference_styles = self._style_candidates(reference)
        candidate_styles = self._style_candidates(candidate)

        if not reference_genres and not candidate_genres:
            return self._reason("genre", 1.0, "Género no disponible para la recomendación.")
        if not reference_genres or not candidate_genres:
            return self._reason("genre", 1.0, "Género no disponible para la recomendación.")

        strength = self._genre_strength(reference_genres, candidate_genres, reference_styles, candidate_styles)
        contribution = self._genre_contribution(strength)
        if contribution == 35:
            return self._reason("genre", 1.0, "Mismo género o transición estrecha compatible.")
        if contribution == 28:
            return self._reason("genre", 0.8, "Género compatible con afinidad alta.")
        if contribution == 21:
            return self._reason("genre", 0.6, "Género compatible con afinidad media.")
        if contribution == 7:
            return self._reason("genre", 0.2, "Género incompatible; limita el score final.")
        return self._reason("genre", 0.0, "Género incompatible; limita el score final.")

    def _key_reason(self, reference, candidate):
        first, second = self._key(reference), self._key(candidate)
        if first is None or second is None:
            return self._reason("key", 0, "Tonalidad no disponible para la recomendación.")
        if first == second:
            return self._reason("key", 1.0, "Tonalidad compatible.")
        return self._reason("key", 0, "Tonalidad diferente.")

    def _bpm_reason(self, reference, candidate):
        first, second = self._number(reference, "bpm"), self._number(candidate, "bpm")
        if first is None or second is None:
            return self._reason("bpm", 0, "BPM no disponible para la recomendación.")
        difference = abs(first - second)
        if difference <= 2:
            return self._reason("bpm", 1.0, f"BPM muy compatible (diferencia {difference:g}).")
        if difference <= 6:
            return self._reason("bpm", 0.6, f"BPM cercano (diferencia {difference:g}).")
        return self._reason("bpm", 0, f"BPM distante (diferencia {difference:g}).")

    def _energy_reason(self, reference, candidate):
        first, second = self._number(reference, "energy"), self._number(candidate, "energy")
        if first is None or second is None:
            return self._reason("energy", 0, "Energía no disponible para la recomendación.")
        difference = abs(first - second)
        if difference <= 10:
            return self._reason("energy", 1.0, f"Energía similar (diferencia {difference:g}).")
        if difference <= 30:
            return self._reason("energy", 0.5, f"Energía moderadamente cercana (diferencia {difference:g}).")
        return self._reason("energy", 0, f"Energía distante (diferencia {difference:g}).")

    def _history_reason(self, candidate_id):
        count = self._history_service.count_history(candidate_id, "played")
        if not isinstance(count, int) or count < 0:
            raise RecommendationScoringError("HistoryService devolvio un conteo invalido.")
        if count >= 5:
            return self._reason("history", 1.0, f"Historial fuerte: reproducida {count} veces.")
        return self._reason("history", 0, "Sin reproducciones previas registradas.")

    def _reason(self, criterion, ratio, explanation):
        if criterion == "genre":
            if ratio >= 1.0:
                contribution = 35
            elif ratio >= 0.8:
                contribution = 28
            elif ratio >= 0.6:
                contribution = 21
            elif ratio >= 0.2:
                contribution = 7
            else:
                contribution = 7
        else:
            contribution = int(round(self.WEIGHTS[criterion] * ratio))
        return RecommendationReasonDTO(criterion, contribution, explanation)

    def _finalize_score(self, score, reasons):
        genre_reason = next((reason for reason in reasons if reason.criterion == "genre"), None)
        key_reason = next((reason for reason in reasons if reason.criterion == "key"), None)
        bpm_reason = next((reason for reason in reasons if reason.criterion == "bpm"), None)
        energy_reason = next((reason for reason in reasons if reason.criterion == "energy"), None)

        if genre_reason is None or key_reason is None or bpm_reason is None or energy_reason is None:
            return score

        if (
            key_reason.contribution < self.WEIGHTS["key"]
            or bpm_reason.contribution < self.WEIGHTS["bpm"]
            or energy_reason.contribution < self.WEIGHTS["energy"]
        ):
            if genre_reason.contribution <= 7 or "no disponible" in genre_reason.explanation.casefold():
                return 0

        if (
            genre_reason.contribution <= 7
            and key_reason.contribution >= self.WEIGHTS["key"]
            and bpm_reason.contribution >= self.WEIGHTS["bpm"]
            and energy_reason.contribution >= self.WEIGHTS["energy"]
        ):
            return min(score, 69)
        return score

    def _confidence(self, reasons, reference_track, candidate_track):
        available = 0
        for reason in reasons:
            if self._is_available(reason, reference_track, candidate_track):
                available += 1
        confidence = available / len(reasons)
        if not self._has_genre_data(reference_track, candidate_track):
            confidence = max(0.0, confidence - 0.2)
        return round(confidence, 2)

    def _has_genre_data(self, reference_track, candidate_track):
        return bool(self._genre_candidates(reference_track)) or bool(self._genre_candidates(candidate_track))

    def _is_available(self, reason, reference_track, candidate_track):
        if reason.criterion == "genre":
            return self._has_genre_data(reference_track, candidate_track)
        explanation = reason.explanation.casefold()
        return "no disponible" not in explanation

    def _genre_candidates(self, track):
        candidates = []
        primary = self._normalize_token(self._get_track_value(track, "genre"))
        if primary:
            candidates.append(primary)
        secondary_values = self._parse_json_values(self._get_track_value(track, "secondary_genres_json"))
        styles_values = self._parse_json_values(self._get_track_value(track, "styles_json"))
        for raw in secondary_values + styles_values:
            normalized = self._normalize_token(raw)
            if normalized:
                candidates.append(normalized)
        return tuple(dict.fromkeys(candidates))

    def _style_candidates(self, track):
        styles = []
        style_values = self._parse_json_values(self._get_track_value(track, "styles_json"))
        for raw in style_values:
            normalized = self._normalize_token(raw)
            if normalized:
                styles.append(normalized)
        return set(styles)

    def _get_track_value(self, track, attribute):
        if track is None:
            return None
        value = getattr(track, attribute, None)
        if value is None and attribute == "genre":
            for fallback in ("primary_genre", "genre_name", "primary_genre_name"):
                fallback_value = getattr(track, fallback, None)
                if fallback_value is not None:
                    return fallback_value
        return value

    def _genre_strength(self, reference_genres, candidate_genres, reference_styles, candidate_styles):
        if not reference_genres or not candidate_genres:
            return 0.0

        style_overlap = self._style_overlap(reference_styles, candidate_styles)
        best_strength = 0.0
        for reference_genre in reference_genres:
            for candidate_genre in candidate_genres:
                if reference_genre == candidate_genre:
                    return 1.0
                strength = self._compatibility_strength(reference_genre, candidate_genre)
                if strength is None:
                    continue
                best_strength = max(best_strength, strength)

        if best_strength:
            return min(1.0, best_strength + (0.2 if style_overlap else 0.0))
        return 0.2 if style_overlap else 0.0

    def _genre_contribution(self, strength):
        if strength >= 1.0:
            return 35
        if strength >= 0.8:
            return 28
        if strength >= 0.6:
            return 21
        if strength >= 0.2:
            return 7
        return 0

    def _compatibility_strength(self, reference_genre, candidate_genre):
        return self._compatibilities.get(reference_genre, {}).get(candidate_genre)

    def _style_overlap(self, reference_styles, candidate_styles):
        return bool(reference_styles & candidate_styles)

    def _load_compatibilities(self):
        config_path = Path(__file__).resolve().parents[2] / "config" / "genres-v1.json"
        if not config_path.exists():
            return {}
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        compatibilities = data.get("genre_compatibilities") or {}
        normalized = {}
        for left, values in compatibilities.items():
            base_left = self._normalize_token(left)
            if not base_left:
                continue
            normalized[base_left] = {}
            for right, strength in values.items():
                base_right = self._normalize_token(right)
                if not base_right:
                    continue
                normalized[base_left][base_right] = self._strength_value(strength)
        return normalized

    @staticmethod
    def _strength_value(value):
        mapping = {"high": 1.0, "medium_high": 0.8, "medium": 0.6, "low": 0.2, "none": 0.0}
        if value in mapping:
            return mapping[value]
        if isinstance(value, (int, float)):
            return max(0.0, min(1.0, float(value)))
        return 0.0

    @staticmethod
    def _parse_json_values(value):
        if value in (None, ""):
            return []
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError):
                return []
            value = parsed
        if isinstance(value, (list, tuple)):
            result = []
            for item in value:
                if isinstance(item, (list, tuple)) and item:
                    result.append(item[0])
                else:
                    result.append(item)
            return result
        return []

    @staticmethod
    def _normalize_token(value):
        if value is None:
            return ""
        normalized = str(value).strip().casefold()
        normalized = normalized.replace("&", " and ")
        normalized = normalized.replace("/", " ")
        normalized = normalized.replace("-", " ")
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized.replace(" ", "_")

    def _track_id(self, track, label):
        value = getattr(track, "id", None)
        if not isinstance(value, int) or value < 1:
            raise RecommendationScoringError(f"La pista {label} debe tener id positivo.")
        return value

    def _number(self, track, attribute):
        value = getattr(track, attribute, None)
        return float(value) if isinstance(value, Real) and not isinstance(value, bool) else None

    def _key(self, track):
        value = getattr(track, "key", None)
        return value.strip().casefold() if isinstance(value, str) and value.strip() else None

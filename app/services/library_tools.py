"""Bounded assistant tools that coordinate only existing application services."""

from dataclasses import dataclass
import re
import time
from types import MappingProxyType, SimpleNamespace

from .assistant_facade import AssistantActionProposalDTO, AssistantError, AssistantTool, AssistantToolResultDTO
from .optimization_metrics import OperationMetricsDTO, StageTimingDTO


def _result(response, data_used, proposed_actions=()):
    """Create the existing result contract with immutable public data."""
    result = AssistantToolResultDTO(response, dict(data_used), tuple(proposed_actions))
    object.__setattr__(result, "data_used", MappingProxyType(dict(result.data_used)))
    return result


@dataclass(frozen=True)
class LibraryQueryInputDTO:
    query: str | None = None
    load_more: bool = False

    @classmethod
    def from_input(cls, input_data):
        payload = dict(input_data or {})
        if set(payload) - {"query", "load_more"}:
            raise AssistantError("La consulta de biblioteca solo acepta query y load_more.")
        query = payload.get("query")
        if query is not None and (not isinstance(query, str) or not query.strip()):
            raise AssistantError("query debe ser texto no vacio o nulo.")
        load_more = payload.get("load_more", False)
        if not isinstance(load_more, bool):
            raise AssistantError("load_more debe ser booleano.")
        if query is not None and load_more:
            raise AssistantError("Una consulta nueva no puede solicitar load_more.")
        return cls(query.strip() if isinstance(query, str) else None, load_more)


@dataclass(frozen=True)
class NaturalLibraryQueryDTO:
    """Validated existing-library filters inferred deterministically from a user phrase."""

    text: str = ""
    genre: str | None = None
    bpm_min: float | None = None
    bpm_max: float | None = None
    key: str | None = None
    rating_min: int | None = None
    rating_max: int | None = None
    favorite: bool | None = None

    def __post_init__(self):
        if not isinstance(self.text, str):
            raise AssistantError("El texto de busqueda debe ser texto.")
        if self.genre is not None and (not isinstance(self.genre, str) or not self.genre.strip()):
            raise AssistantError("El genero debe ser texto no vacio o nulo.")
        for name in ("bpm_min", "bpm_max"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0):
                raise AssistantError(f"{name} debe ser un BPM positivo o nulo.")
        if self.bpm_min is not None and self.bpm_max is not None and self.bpm_min > self.bpm_max:
            raise AssistantError("El BPM minimo no puede superar el maximo.")
        if self.key is not None and (not isinstance(self.key, str) or not self.key.strip()):
            raise AssistantError("La tonalidad debe ser texto no vacio o nula.")
        for name in ("rating_min", "rating_max"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 5):
                raise AssistantError(f"{name} debe estar entre 1 y 5 o ser nulo.")
        if self.rating_min is not None and self.rating_max is not None and self.rating_min > self.rating_max:
            raise AssistantError("El rating minimo no puede superar el maximo.")
        if self.favorite is not None and not isinstance(self.favorite, bool):
            raise AssistantError("favorite debe ser booleano o nulo.")

    def filters(self):
        return {
            name: value for name, value in {
                "genre": self.genre,
                "bpm_min": self.bpm_min,
                "bpm_max": self.bpm_max,
                "key": self.key,
                "rating_min": self.rating_min,
                "rating_max": self.rating_max,
                "favorite": self.favorite,
            }.items() if value is not None
        }


@dataclass(frozen=True)
class LibrarySearchItemDTO:
    track_id: int | None
    title: str
    artist: str
    album: str

    def __post_init__(self):
        if self.track_id is not None and (not isinstance(self.track_id, int) or isinstance(self.track_id, bool)):
            raise AssistantError("track_id debe ser entero o nulo.")
        if not all(isinstance(value, str) for value in (self.title, self.artist, self.album)):
            raise AssistantError("Los datos de pista deben ser texto.")


@dataclass(frozen=True)
class NaturalLibrarySearchResultDTO:
    interpreted_filters: NaturalLibraryQueryDTO
    total_matches: int
    page_items: tuple[LibrarySearchItemDTO, ...]
    has_more: bool
    page_number: int

    def __post_init__(self):
        if not isinstance(self.interpreted_filters, NaturalLibraryQueryDTO):
            raise AssistantError("El resultado requiere filtros interpretados validos.")
        if not isinstance(self.total_matches, int) or self.total_matches < 0:
            raise AssistantError("El total de coincidencias debe ser entero no negativo.")
        if not isinstance(self.page_items, tuple) or not all(isinstance(item, LibrarySearchItemDTO) for item in self.page_items):
            raise AssistantError("La pagina debe contener items tipados.")
        if not isinstance(self.has_more, bool) or not isinstance(self.page_number, int) or self.page_number < 1:
            raise AssistantError("El estado de pagina no es valido.")


class NaturalLibraryQueryInterpreter:
    """Small deterministic Spanish parser for supported existing LibraryService filters."""

    _FILTER_WORDS = ("bpm", "clave", "key", "tono", "rating", "estrella", "favorit", "genero", "género")

    def interpret(self, query):
        if not isinstance(query, str) or not query.strip():
            return None, "Ingresá una consulta de biblioteca no vacía."
        source = query.strip()
        normalized = source.casefold()
        values = {}
        try:
            self._parse_bpm(normalized, values)
            self._parse_key(normalized, values)
            self._parse_rating(normalized, values)
            self._parse_favorite(normalized, values)
            self._parse_genre(normalized, values)
        except AssistantError as error:
            return None, str(error)
        if any(word in normalized for word in self._FILTER_WORDS) and not values:
            return None, "No pude interpretar los filtros solicitados. Probá, por ejemplo: 'BPM entre 120 y 128'."
        return NaturalLibraryQueryDTO(text=self._text_part(source, normalized, values), **values), None

    def _parse_bpm(self, text, values):
        between = re.search(r"(?:bpm\s*)?(?:entre\s+)(\d+(?:\.\d+)?)\s+(?:y|a)\s+(\d+(?:\.\d+)?)(?:\s*bpm)?", text)
        minimum = re.search(r"(?:bpm\s*)?(?:mayor(?:es)?\s+(?:a|de)|m[aá]s\s+de|desde)\s*(\d+(?:\.\d+)?)(?:\s*bpm)?", text)
        maximum = re.search(r"(?:bpm\s*)?(?:menor(?:es)?\s+(?:a|de)|menos\s+de|hasta)\s*(\d+(?:\.\d+)?)(?:\s*bpm)?", text)
        exact = re.search(r"(?:a\s+)?(\d+(?:\.\d+)?)\s*bpm", text)
        if between:
            values["bpm_min"], values["bpm_max"] = float(between.group(1)), float(between.group(2))
        elif minimum:
            values["bpm_min"] = float(minimum.group(1))
        elif maximum:
            values["bpm_max"] = float(maximum.group(1))
        elif "bpm" in text:
            if not exact:
                raise AssistantError("No pude interpretar el BPM. Indicá un número, por ejemplo '128 BPM'.")
            values["bpm_min"] = values["bpm_max"] = float(exact.group(1))

    def _parse_key(self, text, values):
        match = re.search(r"(?:clave|key|tono)\s+([0-9]{1,2}[ab]|[a-g](?:#|b)?m?)\b", text, re.IGNORECASE)
        if match:
            values["key"] = match.group(1).upper()
        elif any(word in text for word in ("clave", "key", "tono")):
            raise AssistantError("No pude interpretar la tonalidad. Probá 'key 8A' o 'tono Am'.")

    def _parse_rating(self, text, values):
        minimum = re.search(r"(?:rating\s*)?(?:m[ií]nimo\s+|al\s+menos\s+)([1-5])\s*(?:estrellas?|rating)?", text)
        exact = re.search(r"(?:rating\s+([1-5])\b|([1-5])\s*(?:estrellas?|rating)\b)", text)
        if minimum:
            values["rating_min"] = int(minimum.group(1))
        elif exact:
            value = exact.group(1) or exact.group(2)
            values["rating_min"] = values["rating_max"] = int(value)
        elif "rating" in text or "estrella" in text:
            raise AssistantError("No pude interpretar el rating. Indicá un valor entre 1 y 5.")

    def _parse_favorite(self, text, values):
        if "no favorito" in text or "sin favoritos" in text:
            values["favorite"] = False
        elif "favorit" in text:
            values["favorite"] = True

    def _parse_genre(self, text, values):
        match = re.search(r"(?:g[eé]nero|genero)\s+([\wáéíóúñ-]+)", text, re.IGNORECASE)
        if match:
            values["genre"] = match.group(1).strip().casefold()
        elif "género" in text or "genero" in text:
            raise AssistantError("No pude interpretar el género. Probá 'género house'.")

    def _text_part(self, source, normalized, values):
        quoted = re.search(r'["“]([^"”]+)["”]', source)
        if quoted:
            return quoted.group(1).strip()
        text_match = re.search(r"(?:texto|buscar)\s+([\wáéíóúñ-]+)", normalized)
        if text_match:
            return text_match.group(1)
        return "" if values else source


@dataclass(frozen=True)
class PlaylistToolInputDTO:
    action: str = "summary"
    name: str | None = None

    @classmethod
    def from_input(cls, input_data):
        payload = dict(input_data or {})
        if set(payload) - {"action", "name"}:
            raise AssistantError("La herramienta de playlists recibio parametros no permitidos.")
        value = cls(payload.get("action", "summary"), payload.get("name"))
        if value.action not in {"summary", "propose_create"}:
            raise AssistantError("La accion de playlist no es valida.")
        if value.action == "propose_create" and (not isinstance(value.name, str) or not value.name.strip()):
            raise AssistantError("La propuesta de playlist requiere un nombre.")
        if value.action == "summary" and value.name is not None:
            raise AssistantError("El resumen de playlists no acepta nombre.")
        return value


@dataclass(frozen=True)
class CollectionToolInputDTO:
    action: str = "summary"
    name: str | None = None
    collection_type: str = "manual"

    @classmethod
    def from_input(cls, input_data):
        payload = dict(input_data or {})
        if set(payload) - {"action", "name", "collection_type"}:
            raise AssistantError("La herramienta de colecciones recibio parametros no permitidos.")
        value = cls(
            payload.get("action", "summary"),
            payload.get("name"),
            payload.get("collection_type", "manual"),
        )
        if value.action not in {"summary", "propose_create"}:
            raise AssistantError("La accion de coleccion no es valida.")
        if value.collection_type not in {"manual", "smart"}:
            raise AssistantError("El tipo de coleccion no es valido.")
        if value.action == "propose_create" and (not isinstance(value.name, str) or not value.name.strip()):
            raise AssistantError("La propuesta de coleccion requiere un nombre.")
        if value.action == "summary" and value.name is not None:
            raise AssistantError("El resumen de colecciones no acepta nombre.")
        return value


class LibraryQueryTool(AssistantTool):
    """Read aggregate counts or deterministic natural-language filters through LibraryService."""

    name = "library_query"
    description = "Consulta la biblioteca por texto, BPM, tonalidad, rating, favoritos y género."
    input_schema = {"type": "object", "properties": {"query": {"type": "string"}, "load_more": {"type": "boolean"}}, "additionalProperties": False}

    def __init__(self, library_service):
        self._library_service = library_service
        self._last_interpreted_query = None
        self._page_number = 0
        self._interpretation_cache = {}
        self._last_metrics = OperationMetricsDTO("library_query", ())
        self._last_interpretation_ms = 0.0

    def execute(self, input_data):
        started = time.perf_counter()
        self._last_interpretation_ms = 0.0
        result = self._execute(input_data)
        total_ms = (time.perf_counter() - started) * 1000
        self._last_metrics = OperationMetricsDTO("library_query", (
            StageTimingDTO("interpretation", self._last_interpretation_ms),
            StageTimingDTO("service", max(0.0, total_ms - self._last_interpretation_ms)),
        ))
        return result

    def _execute(self, input_data):
        request = LibraryQueryInputDTO.from_input(input_data)
        if request.load_more:
            if self._last_interpreted_query is None:
                return _result("No hay una busqueda previa para cargar mas resultados.", {"interpreted": False})
            try:
                rows, has_more = self._library_service.load_more()
                count = self._library_service.count_results()
            except (AttributeError, ValueError) as error:
                raise AssistantError("LibraryService no pudo cargar mas resultados.") from error
            self._page_number += 1
            return self._page_result(self._last_interpreted_query, count, rows, has_more, True)
        if request.query is not None:
            parsed, explanation = self._interpret(request.query)
            if parsed is None:
                return _result(explanation, {"interpreted": False})
            try:
                rows, has_more = self._library_service.query(text=parsed.text, **parsed.filters())
                count = self._library_service.count_results()
            except (AttributeError, ValueError) as error:
                raise AssistantError("LibraryService no pudo resolver la consulta validada.") from error
            self._last_interpreted_query = parsed
            self._page_number = 1
            return self._page_result(parsed, count, rows, has_more, False)
            if not isinstance(count, int) or count < 0:
                raise AssistantError("LibraryService devolvio una cantidad de pistas invalida.")
            filters = tuple(sorted(parsed.filters().items()))
            return _result(
                f"Encontré {count} pistas para la consulta interpretada.",
                {"track_count": count, "interpreted": True, "filters": filters, "has_more": bool(has_more)},
            )
        count = self._library_service.count_tracks()
        if not isinstance(count, int) or count < 0:
            raise AssistantError("LibraryService devolvio una cantidad de pistas invalida.")
        return _result(f"La biblioteca contiene {count} pistas.", {"track_count": count})

    def _interpret(self, query):
        started = time.perf_counter()
        cached = self._interpretation_cache.get(query)
        if cached is not None:
            self._last_interpretation_ms = (time.perf_counter() - started) * 1000
            return cached
        result = NaturalLibraryQueryInterpreter().interpret(query)
        if len(self._interpretation_cache) >= 128:
            self._interpretation_cache.clear()
        self._interpretation_cache[query] = result
        self._last_interpretation_ms = (time.perf_counter() - started) * 1000
        return result
    def _page_result(self, parsed, count, rows, has_more, loaded_more):
        if not isinstance(count, int) or count < 0:
            raise AssistantError("LibraryService devolvio una cantidad de pistas invalida.")
        if not isinstance(rows, (list, tuple)) or not isinstance(has_more, bool):
            raise AssistantError("LibraryService devolvio una pagina invalida.")
        page = NaturalLibrarySearchResultDTO(
            parsed,
            count,
            tuple(LibrarySearchItemDTO(getattr(row, "id", None), str(getattr(row, "title", "")), str(getattr(row, "artist", "")), str(getattr(row, "album", ""))) for row in rows),
            has_more,
            self._page_number,
        )
        criteria = self._criteria_summary(parsed)
        if count == 0:
            response = f"No encontre resultados para: {criteria}."
        else:
            prefix = "Cargue mas resultados" if loaded_more else "Encontre resultados"
            response = f"{prefix}: {count} coincidencias. Criterios: {criteria}. Pagina {page.page_number} con {len(page.page_items)} pistas."
            if page.has_more:
                response += " Hay mas resultados disponibles."
        return _result(response, {"interpreted": True, "search_result": page, "track_count": count, "has_more": page.has_more})

    def _criteria_summary(self, parsed):
        parts = []
        if parsed.text:
            parts.append(f'texto "{parsed.text}"')
        if parsed.genre:
            parts.append(f"genero {parsed.genre}")
        if parsed.bpm_min is not None and parsed.bpm_max is not None:
            parts.append(f"BPM entre {parsed.bpm_min:g} y {parsed.bpm_max:g}")
        elif parsed.bpm_min is not None:
            parts.append(f"BPM desde {parsed.bpm_min:g}")
        elif parsed.bpm_max is not None:
            parts.append(f"BPM hasta {parsed.bpm_max:g}")
        if parsed.key:
            parts.append(f"key {parsed.key}")
        if parsed.rating_min is not None:
            parts.append(f"rating minimo {parsed.rating_min}")
        if parsed.favorite is not None:
            parts.append("favoritos" if parsed.favorite else "no favoritos")
        return ", ".join(parts) if parts else "texto libre"


@dataclass(frozen=True)
class RecommendationToolInputDTO:
    current_track: dict
    bpm_min: float | None = None
    bpm_max: float | None = None
    key: str | None = None
    genre: str | None = None
    favorite: bool | None = None
    limit: int = 10
    recent_history_limit: int = 20
    load_more: bool = False

    @classmethod
    def from_input(cls, input_data):
        payload = dict(input_data or {})
        allowed = {"current_track", "bpm_min", "bpm_max", "key", "genre", "favorite", "limit", "recent_history_limit", "load_more"}
        if set(payload) - allowed or "current_track" not in payload or not isinstance(payload["current_track"], dict):
            raise AssistantError("La recomendacion requiere current_track y solo filtros permitidos.")
        return cls(**payload)


class RecommendationTool(AssistantTool):
    """Expose paged, explainable recommendations through RecommendationFacade only."""

    name = "recommendation"
    description = "Recomienda pistas por BPM, key, energia e historial sin crear playlists."
    input_schema = {"type": "object", "required": ["current_track"], "properties": {
        "current_track": {"type": "object"}, "bpm_min": {"type": "number"}, "bpm_max": {"type": "number"},
        "key": {"type": "string"}, "genre": {"type": "string"}, "favorite": {"type": "boolean"},
        "limit": {"type": "integer"}, "recent_history_limit": {"type": "integer"}, "load_more": {"type": "boolean"},
    }, "additionalProperties": False}

    def __init__(self, recommendation_facade):
        self._recommendation_facade = recommendation_facade
        self._last_metrics = OperationMetricsDTO("recommendation_tool", ())

    def execute(self, input_data):
        started = time.perf_counter()
        result = self._execute(input_data)
        self._last_metrics = OperationMetricsDTO("recommendation_tool", (
            StageTimingDTO("facade", (time.perf_counter() - started) * 1000),
        ))
        return result

    def _execute(self, input_data):
        from .recommendation_facade import RecommendationFacade, RecommendationFacadeQueryDTO

        if not isinstance(self._recommendation_facade, RecommendationFacade):
            raise AssistantError("RecommendationTool requiere RecommendationFacade.")
        request = RecommendationToolInputDTO.from_input(input_data)
        page = self._recommendation_facade.recommend(RecommendationFacadeQueryDTO(
            current_track=SimpleNamespace(**request.current_track), bpm_min=request.bpm_min, bpm_max=request.bpm_max,
            key=request.key, genre=request.genre, favorite=request.favorite, limit=request.limit,
            recent_history_limit=request.recent_history_limit, load_more=request.load_more,
        ))
        return _result(page.explanation, {"recommendation_page": page})


class DiagnosticsTool(AssistantTool):
    """Expose only aggregate local diagnostics through an injected service."""

    name = "diagnostics"
    description = "Resume salud local, caches y limites sin datos sensibles."
    input_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    def __init__(self, diagnostics_service):
        from .diagnostics_service import DiagnosticsService
        if not isinstance(diagnostics_service, DiagnosticsService):
            raise TypeError("DiagnosticsTool requiere DiagnosticsService.")
        self._diagnostics_service = diagnostics_service

    def execute(self, input_data):
        if dict(input_data or {}):
            raise AssistantError("El diagnostico no acepta parametros.")
        snapshot = self._diagnostics_service.snapshot()
        return _result("Diagnostico local disponible.", {"health_snapshot": snapshot, "diagnostic_text": snapshot.export_text()})


class SetBuilderTool(AssistantTool):
    """Build a read-only set proposal without creating a playlist."""

    name = "set_builder"
    description = "Construye una secuencia DJ read-only con curva energetica."
    input_schema = {"type": "object", "required": ["initial_track"], "properties": {
        "initial_track": {"type": "object"}, "target_track_count": {"type": "integer"}, "energy_curve": {"type": "string"},
        "bpm_min": {"type": "number"}, "bpm_max": {"type": "number"}, "key": {"type": "string"}, "genre": {"type": "string"},
        "favorite": {"type": "boolean"}, "recent_history_limit": {"type": "integer"},
    }, "additionalProperties": False}

    def __init__(self, set_builder_facade):
        from .set_builder_facade import SetBuilderFacade
        if not isinstance(set_builder_facade, SetBuilderFacade):
            raise TypeError("SetBuilderTool requiere SetBuilderFacade.")
        self._set_builder_facade = set_builder_facade

    def execute(self, input_data):
        from .set_builder_facade import SetBuilderQueryDTO
        payload = dict(input_data or {})
        if not isinstance(payload.get("initial_track"), dict):
            raise AssistantError("set_builder requiere initial_track.")
        payload["initial_track"] = SimpleNamespace(**payload["initial_track"])
        try:
            result = self._set_builder_facade.build(SetBuilderQueryDTO(**payload))
        except (TypeError, ValueError) as error:
            raise AssistantError(str(error)) from error
        return _result(result.explanation, {"set_builder_result": result, "set_builder_text": result.export_text()})


class PlaylistTool(AssistantTool):
    """Read playlist summaries and emit create proposals without writing."""

    name = "playlist"
    description = "Resume playlists o propone crear una sin ejecutarla."
    input_schema = {"type": "object", "properties": {"action": {}, "name": {}}, "additionalProperties": False}

    def __init__(self, playlist_service):
        self._playlist_service = playlist_service

    def execute(self, input_data):
        request = PlaylistToolInputDTO.from_input(input_data)
        playlists = tuple(self._playlist_service.list_playlists())
        track_count = sum(self._playlist_service.count_tracks(playlist.id) for playlist in playlists)
        actions = ()
        if request.action == "propose_create":
            name = request.name.strip()
            actions = (AssistantActionProposalDTO("create_playlist", f"Crear playlist {name}", {"name": name}),)
        return _result(
            f"Hay {len(playlists)} playlists con {track_count} pistas asociadas.",
            {"playlist_count": len(playlists), "playlist_track_count": track_count},
            actions,
        )


class CollectionTool(AssistantTool):
    """Read collection summaries and emit create proposals without writing."""

    name = "collection"
    description = "Resume colecciones o propone crear una sin ejecutarla."
    input_schema = {"type": "object", "properties": {"action": {}, "name": {}, "collection_type": {}}, "additionalProperties": False}

    def __init__(self, collection_service):
        self._collection_service = collection_service

    def execute(self, input_data):
        request = CollectionToolInputDTO.from_input(input_data)
        collections = tuple(self._collection_service.list_collections())
        track_count = sum(self._collection_service.count_tracks(collection.id) for collection in collections)
        actions = ()
        if request.action == "propose_create":
            name = request.name.strip()
            actions = (
                AssistantActionProposalDTO(
                    "create_collection",
                    f"Crear coleccion {name}",
                    {"name": name, "collection_type": request.collection_type},
                ),
            )
        return _result(
            f"Hay {len(collections)} colecciones con {track_count} pistas asociadas.",
            {"collection_count": len(collections), "collection_track_count": track_count},
            actions,
        )


@dataclass(frozen=True)
class FavoriteToolInputDTO:
    action: str = "summary"
    track_id: int | None = None

    @classmethod
    def from_input(cls, input_data):
        payload = dict(input_data or {})
        if set(payload) - {"action", "track_id"}:
            raise AssistantError("La herramienta de favoritos recibio parametros no permitidos.")
        value = cls(payload.get("action", "summary"), payload.get("track_id"))
        if value.action not in {"summary", "check", "propose_mark", "propose_remove"}:
            raise AssistantError("La accion de favorito no es valida.")
        if value.action != "summary" and (not isinstance(value.track_id, int) or value.track_id < 1):
            raise AssistantError("La accion de favorito requiere track_id positivo.")
        if value.action == "summary" and value.track_id is not None:
            raise AssistantError("El resumen de favoritos no acepta track_id.")
        return value


@dataclass(frozen=True)
class HistoryToolInputDTO:
    track_id: int | None = None
    event_type: str | None = None
    limit: int = 20

    @classmethod
    def from_input(cls, input_data):
        payload = dict(input_data or {})
        if set(payload) - {"track_id", "event_type", "limit"}:
            raise AssistantError("La herramienta de historial recibio parametros no permitidos.")
        value = cls(payload.get("track_id"), payload.get("event_type"), payload.get("limit", 20))
        if value.track_id is not None and (not isinstance(value.track_id, int) or value.track_id < 1):
            raise AssistantError("track_id debe ser positivo o nulo.")
        if value.event_type is not None and (not isinstance(value.event_type, str) or not value.event_type.strip()):
            raise AssistantError("event_type debe ser texto no vacio o nulo.")
        if not isinstance(value.limit, int) or not 1 <= value.limit <= 100:
            raise AssistantError("limit debe estar entre 1 y 100.")
        return value


@dataclass(frozen=True)
class ImportToolInputDTO:
    action: str = "summary"
    job_id: int | None = None
    limit: int = 20

    @classmethod
    def from_input(cls, input_data):
        payload = dict(input_data or {})
        if set(payload) - {"action", "job_id", "limit"}:
            raise AssistantError("La herramienta de importacion recibio parametros no permitidos.")
        value = cls(payload.get("action", "summary"), payload.get("job_id"), payload.get("limit", 20))
        if value.action not in {"summary", "detail", "propose_recover"}:
            raise AssistantError("La accion de importacion no es valida.")
        if value.action == "detail" and (not isinstance(value.job_id, int) or value.job_id < 1):
            raise AssistantError("El detalle de importacion requiere job_id positivo.")
        if value.action != "detail" and value.job_id is not None:
            raise AssistantError("job_id solo se permite al consultar detalle.")
        if not isinstance(value.limit, int) or not 1 <= value.limit <= 100:
            raise AssistantError("limit debe estar entre 1 y 100.")
        return value


class FavoriteTool(AssistantTool):
    """Read favorite state and emit favorite write proposals only."""

    name = "favorite"
    description = "Consulta favoritos o propone marcarlos y quitarlos sin ejecutarlo."
    input_schema = {"type": "object", "properties": {"action": {}, "track_id": {}}, "additionalProperties": False}

    def __init__(self, favorite_service):
        self._favorite_service = favorite_service

    def execute(self, input_data):
        request = FavoriteToolInputDTO.from_input(input_data)
        if request.action == "summary":
            favorites = tuple(self._favorite_service.list_favorites())
            return _result(f"Hay {len(favorites)} pistas favoritas.", {"favorite_count": len(favorites)})
        if request.action == "check":
            is_favorite = bool(self._favorite_service.is_favorite(request.track_id))
            return _result("Estado de favorito consultado.", {"track_id": request.track_id, "is_favorite": is_favorite})
        action_type = "mark_favorite" if request.action == "propose_mark" else "remove_favorite"
        label = "Marcar como favorita" if action_type == "mark_favorite" else "Quitar de favoritos"
        return _result(
            f"Propuesta preparada: {label.lower()}.",
            {"track_id": request.track_id},
            (AssistantActionProposalDTO(action_type, label, {"track_id": request.track_id}),),
        )


class HistoryTool(AssistantTool):
    """Read history entries and statistics without recording any new event."""

    name = "history"
    description = "Consulta historial y estadisticas sin registrar eventos nuevos."
    input_schema = {"type": "object", "properties": {"track_id": {}, "event_type": {}, "limit": {}}, "additionalProperties": False}

    def __init__(self, history_service):
        self._history_service = history_service

    def execute(self, input_data):
        request = HistoryToolInputDTO.from_input(input_data)
        entries = tuple(self._history_service.list_history(request.track_id, request.event_type, request.limit))
        count = self._history_service.count_history(request.track_id, request.event_type)
        return _result(
            f"El historial contiene {count} eventos para la consulta.",
            {"history_count": count, "returned_entries": len(entries), "track_id": request.track_id, "event_type": request.event_type},
        )


class ImportTool(AssistantTool):
    """Read import job state and emit recovery proposals without invoking recovery."""

    name = "import"
    description = "Consulta importaciones o propone recuperar trabajos incompletos."
    input_schema = {"type": "object", "properties": {"action": {}, "job_id": {}, "limit": {}}, "additionalProperties": False}

    def __init__(self, import_manager_facade):
        self._import_manager_facade = import_manager_facade

    def execute(self, input_data):
        request = ImportToolInputDTO.from_input(input_data)
        if request.action == "detail":
            detail = self._import_manager_facade.get_job_detail(request.job_id)
            return _result(
                f"El trabajo {detail.job.id} tiene estado {detail.job.status}.",
                {"job_id": detail.job.id, "status": detail.job.status, "total_items": detail.job.total_items, "error_count": detail.job.error_count},
            )
        jobs = tuple(self._import_manager_facade.list_jobs(limit=request.limit))
        if request.action == "propose_recover":
            actions = (AssistantActionProposalDTO("recover_import_jobs", "Recuperar importaciones incompletas", {}),)
        else:
            actions = ()
        return _result(
            f"Hay {len(jobs)} trabajos de importacion en la consulta.",
            {"job_count": len(jobs), "failed_job_count": sum(job.error_count > 0 for job in jobs)},
            actions,
        )


@dataclass(frozen=True)
class CompatibilityTrackDTO:
    id: int
    bpm: float
    key: str
    energy: float

    @classmethod
    def from_input(cls, value):
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict):
            raise AssistantError("Cada pista de compatibilidad debe ser un objeto.")
        try:
            track = cls(value["id"], value["bpm"], value["key"], value["energy"])
        except KeyError as error:
            raise AssistantError("La pista de compatibilidad esta incompleta.") from error
        if not isinstance(track.id, int) or track.id < 1:
            raise AssistantError("El identificador de pista debe ser positivo.")
        if not isinstance(track.bpm, (int, float)) or not isinstance(track.energy, (int, float)):
            raise AssistantError("BPM y energia deben ser numericos.")
        if not isinstance(track.key, str) or not track.key.strip():
            raise AssistantError("La tonalidad de pista es obligatoria.")
        return track


@dataclass(frozen=True)
class DJCompatibilityInputDTO:
    track_a: CompatibilityTrackDTO
    track_b: CompatibilityTrackDTO

    @classmethod
    def from_input(cls, input_data):
        payload = dict(input_data or {})
        if set(payload) != {"track_a", "track_b"}:
            raise AssistantError("La compatibilidad requiere track_a y track_b.")
        return cls(CompatibilityTrackDTO.from_input(payload["track_a"]), CompatibilityTrackDTO.from_input(payload["track_b"]))


@dataclass(frozen=True)
class AnalysisTrackDTO:
    id: int


@dataclass(frozen=True)
class MusicAnalysisInputDTO:
    track_id: int
    features: tuple[str, ...]

    @classmethod
    def from_input(cls, input_data):
        payload = dict(input_data or {})
        if set(payload) != {"track_id", "features"}:
            raise AssistantError("El analisis requiere track_id y features.")
        track_id, features = payload["track_id"], payload["features"]
        if not isinstance(track_id, int) or track_id < 1:
            raise AssistantError("track_id debe ser positivo.")
        if not isinstance(features, (list, tuple)) or not features or not all(isinstance(item, str) and item.strip() for item in features):
            raise AssistantError("features debe ser una lista no vacia de textos.")
        normalized = tuple(item.strip().lower() for item in features)
        if len(set(normalized)) != len(normalized):
            raise AssistantError("features no puede contener valores repetidos.")
        return cls(track_id, normalized)


class DJCompatibilityTool(AssistantTool):
    """Evaluate supplied track DTOs through DJIntelligenceService only."""

    name = "dj_compatibility"
    description = "Evalua compatibilidad determinista entre dos pistas DTO."
    input_schema = {
        "type": "object",
        "required": ["track_a", "track_b"],
        "properties": {"track_a": {"type": "object"}, "track_b": {"type": "object"}},
        "additionalProperties": False,
    }

    def __init__(self, dj_intelligence_service):
        self._dj_intelligence_service = dj_intelligence_service

    def execute(self, input_data):
        request = DJCompatibilityInputDTO.from_input(input_data)
        result = self._dj_intelligence_service.evaluate_compatibility(request.track_a, request.track_b)
        return _result(
            f"Compatibilidad: {result.score}/100.",
            {
                "track_a_id": result.track_a_id,
                "track_b_id": result.track_b_id,
                "score": result.score,
                "reasons": tuple(result.reasons),
                "confidence": result.confidence,
            },
        )


class MusicAnalysisTool(AssistantTool):
    """Request bounded analysis through MusicAnalysisService without persistence."""

    name = "music_analysis"
    description = "Consulta analisis musical para una pista identificada."
    input_schema = {
        "type": "object",
        "required": ["track_id", "features"],
        "properties": {"track_id": {"type": "integer"}, "features": {"type": "array", "items": {"type": "string"}}},
        "additionalProperties": False,
    }

    def __init__(self, music_analysis_service):
        self._music_analysis_service = music_analysis_service

    def execute(self, input_data):
        request = MusicAnalysisInputDTO.from_input(input_data)
        results = tuple(self._music_analysis_service.analyze(AnalysisTrackDTO(request.track_id), request.features))
        values = tuple((result.feature_type.value, result.value) for result in results)
        return _result(
            f"Analisis completado para {len(results)} features.",
            {"track_id": request.track_id, "analysis": values, "provider": results[0].provider if results else None},
        )

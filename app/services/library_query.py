from dataclasses import dataclass


@dataclass(frozen=True)
class SearchCriteria:
    text: str = ""
    artist: str | None = None
    title: str | None = None
    album: str | None = None
    genre: str | None = None
    bpm: float | None = None
    key: str | None = None
    rating: int | None = None
    date_added: object | None = None


@dataclass(frozen=True)
class FilterCriteria:
    genre: str | None = None
    bpm_min: float | None = None
    bpm_max: float | None = None
    key: str | None = None
    rating_min: int | None = None
    rating_max: int | None = None
    date_added_from: object | None = None
    date_added_to: object | None = None
    favorite: bool | None = None


@dataclass(frozen=True)
class SortSpec:
    column: str = "artist"
    direction: str = "asc"

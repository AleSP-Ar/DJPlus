"""Convert DJ key labels for display without changing stored metadata."""

from __future__ import annotations

import re


_CAMELOT_TO_MUSICAL = {
    "1A": "G# minor", "2A": "D# minor", "3A": "A# minor", "4A": "F minor",
    "5A": "C minor", "6A": "G minor", "7A": "D minor", "8A": "A minor",
    "9A": "E minor", "10A": "B minor", "11A": "F# minor", "12A": "C# minor",
    "1B": "B major", "2B": "F# major", "3B": "C# major", "4B": "G# major",
    "5B": "D# major", "6B": "A# major", "7B": "F major", "8B": "C major",
    "9B": "G major", "10B": "D major", "11B": "A major", "12B": "E major",
}


def _normalized_musical_key(value: str) -> str | None:
    match = re.fullmatch(r"\s*([A-Ga-g])([#b]?)(?:\s*(major|minor|maj|min|m))?\s*", value)
    if not match:
        return None
    root, accidental, mode = match.groups()
    mode = (mode or "major").casefold()
    mode = "minor" if mode in {"minor", "min", "m"} else "major"
    return f"{root.upper()}{accidental} {mode}"


_MUSICAL_TO_CAMELOT = {value.casefold(): key for key, value in _CAMELOT_TO_MUSICAL.items()}


def normalize_key(value: str | None) -> tuple[str | None, str | None]:
    """Return ``(camelot, musical)`` for a recognized key, otherwise ``(None, None)``."""
    if not isinstance(value, str) or not value.strip():
        return None, None
    cleaned = value.strip()
    camelot_match = re.fullmatch(r"(1[0-2]|[1-9])\s*([AaBb])", cleaned)
    if camelot_match:
        camelot = f"{camelot_match.group(1)}{camelot_match.group(2).upper()}"
        return camelot, _CAMELOT_TO_MUSICAL.get(camelot)
    musical = _normalized_musical_key(cleaned)
    if musical is None:
        return None, None
    return _MUSICAL_TO_CAMELOT.get(musical.casefold()), musical


def format_key(value: str | None, notation: str = "both") -> str:
    """Format a key as ``camelot``, ``musical`` or ``both``; preserve unknown values."""
    if notation not in {"camelot", "musical", "both"}:
        notation = "both"
    camelot, musical = normalize_key(value)
    if not camelot or not musical:
        return value.strip() if isinstance(value, str) else ""
    if notation == "camelot":
        return camelot
    if notation == "musical":
        return musical
    return f"{camelot} · {musical}"

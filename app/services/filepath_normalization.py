"""Canonical filepath handling shared by import boundaries."""

from pathlib import Path


def normalize_filepath(filepath):
    """Return an absolute, normalized filepath without requiring it to exist."""
    if not isinstance(filepath, str) or not filepath.strip():
        raise ValueError("La ruta del archivo es obligatoria.")
    return str(Path(filepath.strip()).expanduser().resolve(strict=False))

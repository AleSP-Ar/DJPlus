"""Normalize genre/style terms using a versioned taxonomy JSON.

This service is read-only and safe to use in-memory. It performs stricter
validation of the taxonomy JSON at load time (no external deps): it detects
duplicate object keys, validates types for expected fields, rejects alias
conflicts unless explicitly declared in `ambiguous_terms` and exposes a
rich resolution output including warnings and candidates.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any


def _normalize_string(text: str) -> str:
    if text is None:
        return ""
    s = str(text).strip().casefold()
    s = s.replace("&", " and ")
    s = s.replace("/", " ")
    s = s.replace("-", " ")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.replace(" ", "_")


def _load_json_no_dup(path: Path) -> Any:
    """Load JSON while detecting duplicate keys at any object level.

    Raises ValueError if duplicate keys are found.
    """
    duplicates: List[Tuple[str, str]] = []

    def hook(pairs):
        d = {}
        seen = set()
        for k, v in pairs:
            if k in seen:
                duplicates.append((k, str(path)))
            else:
                seen.add(k)
            d[k] = v
        return d

    txt = path.read_text(encoding="utf-8")
    try:
        data = json.loads(txt, object_pairs_hook=hook)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}") from e
    if duplicates:
        keys = sorted({k for k, _ in duplicates})
        raise ValueError(f"Duplicate JSON keys detected in {path}: {keys}")
    return data


class GenreNormalizer:
    def __init__(self, taxonomy_path: str | Path | None = None):
        self.taxonomy_path = Path(taxonomy_path) if taxonomy_path else Path("config/genres-v1.json")
        self._data: Dict = {}
        self._genres: Dict[str, Dict] = {}
        self._alias_map: Dict[str, List[str]] = {}
        self._ambiguous_map: Dict[str, List[str]] = {}
        self._load()

    def _load(self):
        if not self.taxonomy_path.is_file():
            raise ValueError(f"Taxonomy file not found: {self.taxonomy_path}")

        data = _load_json_no_dup(self.taxonomy_path)

        # Basic structural validation
        if not isinstance(data, dict):
            raise ValueError("Taxonomy root must be a JSON object")
        version = data.get("version")
        if not isinstance(version, str) or not version:
            raise ValueError("Taxonomy 'version' must be a non-empty string")

        genres = data.get("genres")
        if not isinstance(genres, dict):
            raise ValueError("Taxonomy 'genres' must be an object mapping ids to metadata")

        ambiguous_terms = data.get("ambiguous_terms", {})
        if ambiguous_terms is None:
            ambiguous_terms = {}
        if not isinstance(ambiguous_terms, dict):
            raise ValueError("Taxonomy 'ambiguous_terms' must be an object mapping term->list_of_ids")

        # Validate genres entries
        for gid, meta in genres.items():
            if not isinstance(gid, str) or not gid:
                raise ValueError(f"Invalid genre id: {gid!r}")
            if not isinstance(meta, dict):
                raise ValueError(f"Genre metadata for {gid} must be an object")
            label = meta.get("label")
            if not isinstance(label, str) or not label:
                raise ValueError(f"Genre '{gid}' missing valid 'label' string")
            aliases = meta.get("aliases", [])
            if not isinstance(aliases, list):
                raise ValueError(f"Genre '{gid}' field 'aliases' must be a list of strings")
            for a in aliases:
                if not isinstance(a, str):
                    raise ValueError(f"Genre '{gid}' contains non-string alias: {a!r}")

        # Validate ambiguous_terms values
        normalized_ambig: Dict[str, List[str]] = {}
        for term, lst in ambiguous_terms.items():
            if not isinstance(term, str):
                raise ValueError("ambiguous_terms keys must be strings")
            if not isinstance(lst, list) or not lst:
                raise ValueError(f"ambiguous_terms['{term}'] must be a non-empty list of genre ids")
            for gid in lst:
                if gid not in genres:
                    raise ValueError(f"ambiguous_terms entry '{term}' references unknown genre id '{gid}'")
            normalized_ambig[_normalize_string(term)] = list(lst)

        # Build genres and alias map
        self._data = data
        self._genres = genres
        alias_map: Dict[str, List[str]] = {}
        for gid, meta in genres.items():
            tokens = [gid, meta.get("label", "")] + list(meta.get("aliases", []))
            for token in tokens:
                key = _normalize_string(token)
                if not key:
                    continue
                alias_map.setdefault(key, []).append(gid)

        # Detect alias conflicts
        conflicts = {k: v for k, v in alias_map.items() if len(set(v)) > 1}
        # Allow conflicts only when explicitly declared in ambiguous_terms with the same candidate set
        unresolved_conflicts = []
        for norm, gids in conflicts.items():
            gids_set = set(gids)
            allowed = normalized_ambig.get(norm)
            if allowed is None or set(allowed) != gids_set:
                unresolved_conflicts.append((norm, sorted(gids_set)))

        if unresolved_conflicts:
            keys = [c[0] for c in unresolved_conflicts]
            raise ValueError(f"Alias conflicts detected for tokens: {keys}. Declare them in 'ambiguous_terms' to allow ambiguity.")

        # If conflicts are allowed (explicit ambiguous terms), register them in ambiguous map
        self._ambiguous_map = normalized_ambig
        self._alias_map = alias_map

    def normalize_term(self, term: str) -> dict:
        """Return a rich resolution dict for `term`.

        Output fields:
        - original_value: original input string
        - normalized_text: normalized token used for lookup
        - resolved_id: str or None (single winner)
        - resolved_label: str or None
        - resolution_status: one of 'exact','alias','ambiguous','unknown'
        - confidence: float (1.0 exact, 0.9 alias, 0.0 ambiguous from ambiguous_terms, 0.0 unknown)
        - candidates: list of candidate ids (empty when resolved_id present)
        - warnings: list of warning strings
        """
        original = term
        norm = _normalize_string(term)
        warnings: List[str] = []

        if not norm:
            out = {
                "original_value": original,
                "normalized_text": norm,
                "resolved_id": None,
                "resolved_label": None,
                "resolution_status": "unknown",
                "confidence": 0.0,
                "candidates": [],
                "warnings": warnings,
            }
            return self._with_legacy(out)

        # exact id match
        if norm in self._genres:
            meta = self._genres[norm]
            out = {
                "original_value": original,
                "normalized_text": norm,
                "resolved_id": norm,
                "resolved_label": meta.get("label"),
                "resolution_status": "exact",
                "confidence": 1.0,
                "candidates": [],
                "warnings": warnings,
            }
            return self._with_legacy(out)

        # explicit ambiguous_terms
        amb = self._ambiguous_map.get(norm)
        if amb:
            labels = [self._genres.get(g, {}).get("label") for g in amb]
            warnings.append(f"Term '{original}' is explicitly ambiguous in taxonomy; manual review required.")
            out = {
                "original_value": original,
                "normalized_text": norm,
                "resolved_id": None,
                "resolved_label": None,
                "resolution_status": "ambiguous",
                "confidence": 0.0,
                "candidates": list(amb),
                "warnings": warnings,
            }
            return self._with_legacy(out)

        candidates = self._alias_map.get(norm, [])
        if not candidates:
            out = {
                "original_value": original,
                "normalized_text": norm,
                "resolved_id": None,
                "resolved_label": None,
                "resolution_status": "unknown",
                "confidence": 0.0,
                "candidates": [],
                "warnings": warnings,
            }
            return self._with_legacy(out)

        # single alias candidate
        unique = list(dict.fromkeys(candidates))
        if len(unique) == 1:
            gid = unique[0]
            meta = self._genres.get(gid, {})
            out = {
                "original_value": original,
                "normalized_text": norm,
                "resolved_id": gid,
                "resolved_label": meta.get("label"),
                "resolution_status": "alias",
                "confidence": 0.9,
                "candidates": [],
                "warnings": warnings,
            }
            return self._with_legacy(out)

        # multiple candidates (shouldn't happen because conflicts are rejected unless declared)
        labels = [self._genres.get(g, {}).get("label") for g in unique]
        warnings.append("Multiple candidates found for term; taxonomy should declare this in 'ambiguous_terms' to make it explicit.")
        out = {
            "original_value": original,
            "normalized_text": norm,
            "resolved_id": None,
            "resolved_label": None,
            "resolution_status": "ambiguous",
            "confidence": 0.5,
            "candidates": unique,
            "warnings": warnings,
        }
        return self._with_legacy(out)

    def _with_legacy(self, out: Dict[str, Any]) -> Dict[str, Any]:
        # provide backward-compatible keys used by older callers/tests
        out = dict(out)
        out.setdefault("canonical_id", out.get("resolved_id"))
        out.setdefault("canonical_label", out.get("resolved_label"))
        out.setdefault("status", out.get("resolution_status"))
        return out

    def get_taxonomy_version(self) -> str:
        return str(self._data.get("version", "0"))

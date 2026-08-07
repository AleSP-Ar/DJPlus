from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Any


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
    duplicates = []

    def hook(pairs):
        d = {}
        seen = set()
        for k, v in pairs:
            if k in seen:
                duplicates.append(k)
            else:
                seen.add(k)
            d[k] = v
        return d

    txt = path.read_text(encoding="utf-8")
    data = json.loads(txt, object_pairs_hook=hook)
    if duplicates:
        raise ValueError(f"Duplicate keys in styles JSON: {sorted(set(duplicates))}")
    return data


class StyleNormalizer:
    def __init__(self, taxonomy_path: str | Path | None = None):
        self.path = Path(taxonomy_path) if taxonomy_path else Path("config/styles-v1.json")
        self._styles: Dict[str, Dict] = {}
        self._alias_map: Dict[str, List[str]] = {}
        self._load()

    def _load(self):
        if not self.path.is_file():
            raise ValueError(f"Styles taxonomy not found: {self.path}")
        data = _load_json_no_dup(self.path)
        styles = data.get("styles")
        if not isinstance(styles, dict):
            raise ValueError("'styles' must be an object")
        for sid, meta in styles.items():
            if not isinstance(sid, str) or not sid:
                raise ValueError("invalid style id")
            label = meta.get("label")
            if not isinstance(label, str):
                raise ValueError("style label must be string")
            aliases = meta.get("aliases", [])
            if not isinstance(aliases, list):
                raise ValueError("style aliases must be list")
            self._styles[sid] = meta
            tokens = [sid, label] + aliases
            for t in tokens:
                k = _normalize_string(t)
                if not k:
                    continue
                self._alias_map.setdefault(k, []).append(sid)

    def normalize_term(self, term: str) -> dict:
        norm = _normalize_string(term)
        if not norm:
            return {"resolved_id": None, "resolved_label": None, "confidence": 0.0, "status": "unknown", "normalized_text": norm, "candidates": []}
        if norm in self._styles:
            meta = self._styles[norm]
            return {"resolved_id": norm, "resolved_label": meta.get("label"), "confidence": 1.0, "status": "exact", "normalized_text": norm, "candidates": []}
        candidates = self._alias_map.get(norm, [])
        if not candidates:
            return {"resolved_id": None, "resolved_label": None, "confidence": 0.0, "status": "unknown", "normalized_text": norm, "candidates": []}
        if len(candidates) == 1:
            sid = candidates[0]
            return {"resolved_id": sid, "resolved_label": self._styles.get(sid, {}).get("label"), "confidence": 0.9, "status": "alias", "normalized_text": norm, "candidates": []}
        return {"resolved_id": None, "resolved_label": None, "confidence": 0.5, "status": "ambiguous", "normalized_text": norm, "candidates": list(candidates)}

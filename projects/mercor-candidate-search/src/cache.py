"""Tiny JSON disk cache to avoid repeat API cost (embeddings, queries, LLM).

Layout: ``results/cache/<namespace>/<sha256-of-key>.json``. Values must be
JSON-serializable (lists/dicts/str/num/bool/None). Embeddings are stored as
plain float lists, which is fine for the handful of distinct queries here.
"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

from .config import CACHE_DIR

T = TypeVar("T")

_LOCK = threading.Lock()


def make_key(*parts: Any) -> str:
    """Stable sha256 hex digest over the given parts."""
    h = hashlib.sha256()
    for p in parts:
        if isinstance(p, (dict, list, tuple)):
            p = json.dumps(p, sort_keys=True, default=str, ensure_ascii=False)
        h.update(str(p).encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def _path(namespace: str, key: str) -> Path:
    d = CACHE_DIR / namespace
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.json"


def cache_get(namespace: str, key: str) -> Optional[Any]:
    p = _path(namespace, key)
    if not p.exists():
        return None
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def cache_set(namespace: str, key: str, value: Any) -> None:
    p = _path(namespace, key)
    tmp = p.with_suffix(".json.tmp")
    with _LOCK:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False)
        tmp.replace(p)


def disk_cache(namespace: str, key: str, producer: Callable[[], T], *, enabled: bool = True) -> T:
    """Return cached value for (namespace, key) or compute+store it."""
    if enabled:
        hit = cache_get(namespace, key)
        if hit is not None:
            return hit  # type: ignore[return-value]
    value = producer()
    if enabled and value is not None:
        try:
            cache_set(namespace, key, value)
        except Exception:
            pass
    return value

"""voyage-3 query embeddings with an on-disk cache and retry/backoff.

The index is ``[1024]f32`` built with ``voyage-3`` so queries MUST use the same
model. Only a handful of distinct query strings are embedded per run, so a
simple JSON cache keyed by (model, text) is plenty.
"""
from __future__ import annotations

from typing import List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from . import cache
from .config import VOYAGE_API_KEY, VOYAGE_EMBED_MODEL

_CLIENT = None


def _client():
    global _CLIENT
    if _CLIENT is None:
        import voyageai

        _CLIENT = voyageai.Client(api_key=VOYAGE_API_KEY)
    return _CLIENT


@retry(stop=stop_after_attempt(5), wait=wait_exponential_jitter(initial=1, max=30), reraise=True)
def _embed_batch(texts: List[str], model: str, input_type: Optional[str]) -> List[List[float]]:
    resp = _client().embed(texts, model=model, input_type=input_type)
    return [list(map(float, e)) for e in resp.embeddings]


def embed_query(text: str, model: str = VOYAGE_EMBED_MODEL, input_type: Optional[str] = "query") -> List[float]:
    """Embed a single query string (cached). Returns a 1024-dim float list."""
    return embed_texts([text], model=model, input_type=input_type)[0]


def embed_texts(
    texts: List[str], model: str = VOYAGE_EMBED_MODEL, input_type: Optional[str] = "query"
) -> List[List[float]]:
    """Embed many strings, using the cache per-item and batching cache misses."""
    results: List[Optional[List[float]]] = [None] * len(texts)
    misses: List[int] = []
    for i, t in enumerate(texts):
        key = cache.make_key(model, input_type or "", t)
        hit = cache.cache_get("embed", key)
        if hit is not None:
            results[i] = hit
        else:
            misses.append(i)

    if misses:
        miss_texts = [texts[i] for i in misses]
        embs = _embed_batch(miss_texts, model, input_type)
        for j, i in enumerate(misses):
            results[i] = embs[j]
            key = cache.make_key(model, input_type or "", texts[i])
            cache.cache_set("embed", key, embs[j])

    return [r for r in results if r is not None]

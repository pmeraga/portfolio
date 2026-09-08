"""Turbopuffer client wrappers: dense ANN + native BM25, with filters.

Read-only queries against ``search-test-v4`` in ``aws-us-west-2``. Results are
returned as plain candidate dicts (see ``config.row_to_dict``) sorted best-first,
with the originating channel rank attached (``_ann_rank`` / ``_bm25_rank``).
Query results are cached on disk to avoid repeat cost. Retries use exponential
backoff on rate-limit / server / connection errors.
"""
from __future__ import annotations

from typing import Any, List, Optional

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from . import cache
from .config import (
    ANN_TOP_K,
    BM25_TOP_K,
    TPUF_NAMESPACE,
    TPUF_REGION,
    TURBOPUFFER_API_KEY,
    row_to_dict,
)

Filter = Any  # turbopuffer filter tuple, e.g. ("And", [("country", "Eq", "United States")])


def _retryable_errors():
    import turbopuffer

    return (
        turbopuffer.RateLimitError,
        turbopuffer.InternalServerError,
        turbopuffer.APIConnectionError,
        turbopuffer.APITimeoutError,
    )


class TpufClient:
    def __init__(
        self,
        api_key: str = TURBOPUFFER_API_KEY,
        region: str = TPUF_REGION,
        namespace: str = TPUF_NAMESPACE,
    ) -> None:
        import turbopuffer

        self._tpuf = turbopuffer.Turbopuffer(api_key=api_key, region=region)
        self._ns = self._tpuf.namespace(namespace)
        self.namespace = namespace
        self._retry_types = _retryable_errors()

    def _query(self, *, rank_by, top_k: int, filters: Optional[Filter]):
        @retry(
            stop=stop_after_attempt(5),
            wait=wait_exponential_jitter(initial=1, max=30),
            retry=retry_if_exception_type(self._retry_types),
            reraise=True,
        )
        def _run():
            kwargs = dict(rank_by=rank_by, top_k=top_k, include_attributes=True)
            if filters is not None:
                kwargs["filters"] = filters
            return self._ns.query(**kwargs)

        return _run()

    def ann_query(
        self,
        vector: List[float],
        top_k: int = ANN_TOP_K,
        filters: Optional[Filter] = None,
        use_cache: bool = True,
    ) -> List[dict]:
        """Dense ANN over the voyage-3 ``vector`` field. Returns ranked dicts."""
        vkey = cache.make_key([round(float(x), 5) for x in vector])
        key = cache.make_key(self.namespace, "ann", vkey, top_k, filters)

        def produce():
            res = self._query(rank_by=("vector", "ANN", vector), top_k=top_k, filters=filters)
            return [row_to_dict(r) for r in res.rows]

        rows = cache.disk_cache("tpuf_ann", key, produce, enabled=use_cache)
        for i, c in enumerate(rows):
            c["_ann_rank"] = i
        return rows

    def bm25_query(
        self,
        text: str,
        top_k: int = BM25_TOP_K,
        filters: Optional[Filter] = None,
        field: str = "rerankSummary",
        use_cache: bool = True,
    ) -> List[dict]:
        """Native BM25 full-text search over ``rerankSummary``. Returns ranked dicts."""
        key = cache.make_key(self.namespace, "bm25", field, text, top_k, filters)

        def produce():
            res = self._query(rank_by=(field, "BM25", text), top_k=top_k, filters=filters)
            return [row_to_dict(r) for r in res.rows]

        rows = cache.disk_cache("tpuf_bm25", key, produce, enabled=use_cache)
        for i, c in enumerate(rows):
            c["_bm25_rank"] = i
        return rows


_CLIENT: Optional[TpufClient] = None


def get_tpuf_client() -> TpufClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = TpufClient()
    return _CLIENT

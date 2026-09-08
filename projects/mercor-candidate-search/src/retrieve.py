"""Stage 1: hybrid retrieval = dense ANN + native BM25, fused with RRF.

Two independent TPUF queries (dense voyage-3 ANN and BM25 over rerankSummary)
are fused client-side with Reciprocal Rank Fusion (k=60) into a single
candidate set of ~CANDIDATE_K rows that feeds the Stage-2 reranker.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .config import ANN_TOP_K, BM25_TOP_K, CANDIDATE_K, RRF_K
from .embed import embed_query
from .tpuf_client import get_tpuf_client


def reciprocal_rank_fusion(channels: List[List[Dict[str, Any]]], k: int = RRF_K) -> List[Dict[str, Any]]:
    """Fuse ranked channels by id. Each channel is a list of candidate dicts
    ordered best-first. Returns merged candidates sorted by descending RRF.
    """
    merged: Dict[str, Dict[str, Any]] = {}
    for channel in channels:
        for rank, cand in enumerate(channel):
            cid = cand.get("_id") or cand.get("id")
            if not cid:
                continue
            if cid not in merged:
                # copy so we can accumulate fusion metadata
                merged[cid] = dict(cand)
                merged[cid].setdefault("_rrf", 0.0)
            slot = merged[cid]
            slot["_rrf"] = slot.get("_rrf", 0.0) + 1.0 / (k + rank + 1)
            # preserve per-channel ranks
            if cand.get("_ann_rank") is not None:
                slot["_ann_rank"] = cand["_ann_rank"]
            if cand.get("_bm25_rank") is not None:
                slot["_bm25_rank"] = cand["_bm25_rank"]
            # keep richest attributes (fill any missing/empty from this copy)
            for key, val in cand.items():
                if val not in (None, "", []) and slot.get(key) in (None, "", []):
                    slot[key] = val

    fused = list(merged.values())
    fused.sort(key=lambda c: c.get("_rrf", 0.0), reverse=True)
    return fused


def retrieve(
    spec: Dict[str, Any],
    ann_top_k: int = ANN_TOP_K,
    bm25_top_k: int = BM25_TOP_K,
    candidate_k: int = CANDIDATE_K,
    filters: Optional[Any] = None,
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """Run both channels for a spec and return the fused top-``candidate_k``."""
    client = get_tpuf_client()

    dense: List[Dict[str, Any]] = []
    sem_q = (spec.get("semantic_query") or spec.get("title") or "").strip()
    if sem_q:
        vec = embed_query(sem_q)
        dense = client.ann_query(vec, top_k=ann_top_k, filters=filters, use_cache=use_cache)

    lexical: List[Dict[str, Any]] = []
    kw = (spec.get("bm25_keywords") or spec.get("title") or "").strip()
    if kw:
        lexical = client.bm25_query(kw, top_k=bm25_top_k, filters=filters, use_cache=use_cache)

    fused = reciprocal_rank_fusion([dense, lexical], k=RRF_K)
    return fused[:candidate_k]

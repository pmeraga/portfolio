"""Shared configuration, constants, and the candidate/row dict contract.

This module is the single source of truth for:
  * environment / secrets loading (via python-dotenv)
  * model names and endpoints
  * tuning knobs (K, RRF, gate weights)
  * the candidate dict shape and the ``row_to_dict`` helper

Every other module imports from here so the interfaces stay locked.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------------------------------
# Secrets / connection (never print full keys)
# --------------------------------------------------------------------------
TURBOPUFFER_API_KEY = os.environ.get("TURBOPUFFER_API_KEY", "")
VOYAGE_API_KEY = os.environ.get("VOYAGE_API_KEY", "")
OAI_KEY = os.environ.get("OAI_KEY", "")
TPUF_REGION = os.environ.get("TPUF_REGION", "aws-us-west-2")
TPUF_NAMESPACE = os.environ.get("TPUF_NAMESPACE", "search-test-v4")
EVAL_EMAIL = os.environ.get("EVAL_EMAIL", "")

# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
VOYAGE_EMBED_MODEL = "voyage-3"           # must match the [1024]f32 index
VOYAGE_RERANK_MODEL = "rerank-2.5"        # cross-encoder (hosted)
VOYAGE_RERANK_FALLBACK = "rerank-2"
# OpenAI model used for query understanding + optional judge. Verified available
# at build time; query_understanding falls back gracefully if it 404s.
OPENAI_MODEL = "gpt-4.1-mini"
OPENAI_MODEL_FALLBACKS = ["gpt-4o-mini", "gpt-4.1-nano", "gpt-4o"]

# --------------------------------------------------------------------------
# Eval API
# --------------------------------------------------------------------------
EVAL_BASE = "https://mercor-dev--search-eng-interview.modal.run"

# --------------------------------------------------------------------------
# Retrieval / rerank tuning knobs (overridable for experiments)
# --------------------------------------------------------------------------
ANN_TOP_K = 100          # dense channel depth
BM25_TOP_K = 100         # lexical channel depth
RRF_K = 60               # reciprocal rank fusion constant
CANDIDATE_K = 100        # fused candidate set size feeding the reranker
RERANK_DOC_CHARS = 1800  # truncate rerankSummary fed to the cross-encoder
JUDGE_TOP_N = 40         # how many top candidates the optional LLM judge sees
FINAL_K = 10             # ids submitted per config
OPENAI_TIMEOUT = 30      # seconds, hard cap per OpenAI call
JUDGE_WORKERS = 10       # parallel judge calls

# Score-blend weights (Stage 2). Final ordering is hard-pass first, then by
# blended score within each tier.
W_HARD = 0.50            # fraction of hard criteria met (deterministic)
W_RERANK = 0.35          # normalized cross-encoder relevance
W_SOFT = 0.15            # deterministic soft-signal score
USE_JUDGE = True         # optional OpenAI judge over the top JUDGE_TOP_N

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"
CACHE_DIR = RESULTS_DIR / "cache"
CONFIGS_PATH = ROOT / "configs" / "queries.yaml"
SCORES_PATH = RESULTS_DIR / "scores.json"

for _d in (RESULTS_DIR, CACHE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Candidate / row contract
# --------------------------------------------------------------------------
# Attribute keys returned by the namespace (camelCase rerankSummary!).
ATTRIBUTE_KEYS: List[str] = [
    "id", "name", "country", "email", "linkedin_id", "updated_at",
    "rerankSummary",
    "degrees", "deg_degrees", "deg_fos", "deg_schools",
    "deg_years", "deg_start_years", "deg_end_years",
    "experience", "exp_titles", "exp_companies",
    "exp_years", "exp_start_years", "exp_end_years",
]

# Internal keys we attach to a candidate dict during retrieval/rerank.
# A "candidate" is a plain dict: the attribute keys above (vector dropped) plus:
#   _id          : str  (mirrors id; the object_id submitted to /evaluate)
#   _dist        : float (raw $dist from the channel that surfaced it)
#   _ann_rank    : int | None (0-based rank in the dense channel)
#   _bm25_rank   : int | None (0-based rank in the BM25 channel)
#   _rrf         : float (reciprocal-rank-fusion score)
#   ...rerank/gate fields added later by rerank.py


def row_to_dict(row: Any) -> Dict[str, Any]:
    """Convert a turbopuffer Row (or dict) into a plain candidate dict.

    Drops the ``vector`` (large, unused after retrieval). Captures ``$dist``
    as ``_dist``. Missing attributes default to "" (strings) which the rest of
    the pipeline tolerates.
    """
    if isinstance(row, dict):
        get = row.get
        has = lambda k: k in row  # noqa: E731
    else:
        def get(k, default=None):
            return getattr(row, k, default)

        def has(k):
            return (k in row) if hasattr(row, "__contains__") else hasattr(row, k)

    out: Dict[str, Any] = {}
    for k in ATTRIBUTE_KEYS:
        out[k] = get(k, "")
    out["_id"] = out.get("id") or ""
    # $dist is a special key on the Row
    dist = None
    try:
        if has("$dist"):
            dist = get("$dist")
    except Exception:
        dist = None
    out["_dist"] = float(dist) if isinstance(dist, (int, float)) else None
    out["_ann_rank"] = None
    out["_bm25_rank"] = None
    out["_rrf"] = 0.0
    return out


def mask_key(key: str) -> str:
    """Return a safe-to-log fingerprint of a secret (never the full key)."""
    if not key:
        return "<empty>"
    return f"{key[:4]}...{key[-3:]} (len={len(key)})"

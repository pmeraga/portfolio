"""Eval API client: register, submit, and persist scores.

Endpoints (base https://mercor-dev--search-eng-interview.modal.run):
  GET  /            -> {"status":"healthy"}
  POST /add_user    -> register the email (idempotent)
  POST /evaluate    -> {config_path, object_ids[<=10]} -> JSON with the score
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from .config import EVAL_BASE, EVAL_EMAIL, SCORES_PATH

_HEADERS = {"Authorization": EVAL_EMAIL, "Content-Type": "application/json"}


class EvalError(Exception):
    pass


def health() -> Dict[str, Any]:
    r = requests.get(EVAL_BASE + "/", timeout=30)
    r.raise_for_status()
    return r.json()


def register_user(email: str = EVAL_EMAIL) -> Dict[str, Any]:
    """Register the email (idempotent; safe to call repeatedly)."""
    r = requests.post(
        EVAL_BASE + "/add_user",
        headers={"Authorization": email, "Content-Type": "application/json"},
        json={"email": email},
        timeout=30,
    )
    try:
        body = r.json()
    except Exception:
        body = {"status_code": r.status_code, "text": r.text[:300]}
    return body


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=2, max=60),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout, EvalError)),
    reraise=True,
)
def _post_evaluate(config_path: str, object_ids: List[str]) -> Dict[str, Any]:
    r = requests.post(
        EVAL_BASE + "/evaluate",
        headers=_HEADERS,
        json={"config_path": config_path, "object_ids": object_ids},
        timeout=120,
    )
    if r.status_code == 429 or r.status_code >= 500:
        raise EvalError(f"retryable status {r.status_code}: {r.text[:200]}")
    try:
        body = r.json()
    except Exception:
        raise EvalError(f"non-JSON response (status {r.status_code}): {r.text[:300]}")
    if r.status_code >= 400:
        raise EvalError(f"eval error {r.status_code}: {json.dumps(body)[:400]}")
    return body


def evaluate_config(config_path: str, object_ids: List[str]) -> Dict[str, Any]:
    """Submit exactly the given (<=10) ids for a config and return the response."""
    ids = [str(x) for x in object_ids if x][:10]
    return _post_evaluate(config_path, ids)


# --------------------------------------------------------------------------
# Score extraction + persistence
# --------------------------------------------------------------------------
_SCORE_KEYS = [
    "score", "average_final_score", "avg_final_score", "final_score",
    "average_score", "avg_score", "total_score", "mean_score", "ndcg",
]


def extract_score(response: Dict[str, Any]) -> Optional[float]:
    """Best-effort numeric score extraction from an unknown response schema."""
    if not isinstance(response, dict):
        return None
    for k in _SCORE_KEYS:
        v = response.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    # search one level deep
    for v in response.values():
        if isinstance(v, dict):
            for k in _SCORE_KEYS:
                if isinstance(v.get(k), (int, float)):
                    return float(v[k])
    # any top-level float that looks like a score in [0,1] or a percentage
    for k, v in response.items():
        if isinstance(v, (int, float)) and "id" not in k.lower():
            return float(v)
    return None


def load_scores() -> Dict[str, Any]:
    if SCORES_PATH.exists():
        try:
            with SCORES_PATH.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_score(config_path: str, object_ids: List[str], response: Dict[str, Any], meta: Optional[Dict] = None) -> None:
    scores = load_scores()
    scores[config_path] = {
        "object_ids": list(object_ids),
        "response": response,
        "score": extract_score(response),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "meta": meta or {},
    }
    with SCORES_PATH.open("w", encoding="utf-8") as f:
        json.dump(scores, f, indent=2, ensure_ascii=False)


def submit_and_record(config_path: str, object_ids: List[str], meta: Optional[Dict] = None) -> Dict[str, Any]:
    """Submit to /evaluate, persist, and return the response."""
    resp = evaluate_config(config_path, object_ids)
    save_score(config_path, object_ids, resp, meta=meta)
    return resp

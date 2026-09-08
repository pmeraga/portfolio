"""End-to-end search for a single query config.

config -> query understanding -> hybrid retrieve (ANN + BM25 + RRF)
       -> cross-encoder rerank + hard gate + soft blend (+ judge)
       -> top-10 object_ids
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import yaml

from .config import CANDIDATE_K, CONFIGS_PATH, FINAL_K
from .query_understanding import understand_query
from .rerank import rerank
from .retrieve import retrieve


def load_configs(path=CONFIGS_PATH) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("queries", [])


def get_config(config_path: str) -> Dict[str, Any]:
    for c in load_configs():
        if c.get("config_path") == config_path:
            return c
    raise KeyError(f"config_path not found in queries.yaml: {config_path}")


def _dedup_ids(ids: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for i in ids:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _pad_ids(object_ids: List[str], candidates: List[Dict[str, Any]], spec: Dict[str, Any], final_k: int) -> List[str]:
    """Guarantee at least final_k ids: pad from the candidate set, then from a
    fresh dense ANN query as a last resort. Always returns a deduped list."""
    out = _dedup_ids(object_ids)
    have = set(out)
    for c in candidates:
        cid = c.get("_id") or c.get("id")
        if cid and cid not in have:
            out.append(cid)
            have.add(cid)
        if len(out) >= final_k:
            return out
    if len(out) < final_k:
        try:
            from .embed import embed_query
            from .tpuf_client import get_tpuf_client

            vec = embed_query(spec.get("semantic_query") or spec.get("title") or "")
            backup = get_tpuf_client().ann_query(vec, top_k=max(final_k * 4, 50))
            for c in backup:
                cid = c.get("_id") or c.get("id")
                if cid and cid not in have:
                    out.append(cid)
                    have.add(cid)
                if len(out) >= final_k:
                    break
        except Exception:
            pass
    return out


def search(
    config: Dict[str, Any],
    candidate_k: int = CANDIDATE_K,
    final_k: int = FINAL_K,
    use_judge: Optional[bool] = None,
    use_openai_understanding: bool = True,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Run the full pipeline for one config and return ranked results."""
    spec = understand_query(config, use_cache=use_cache, use_openai=use_openai_understanding)

    candidates = retrieve(spec, candidate_k=candidate_k, use_cache=use_cache)

    kwargs = {"use_cache": use_cache}
    if use_judge is not None:
        kwargs["use_judge"] = use_judge
    try:
        ranked = rerank(spec, candidates, **kwargs)
    except Exception:
        # full fallback: keep the fused RRF order if rerank blows up entirely
        ranked = candidates

    # Build a deduped, best-first id list and ALWAYS pad up to final_k.
    object_ids = _dedup_ids([c.get("_id") or c.get("id") for c in ranked])
    if len(object_ids) < final_k:
        object_ids = _pad_ids(object_ids, candidates, spec, final_k)
    object_ids = object_ids[:final_k]

    return {
        "config_path": config.get("config_path"),
        "title": config.get("title"),
        "spec": spec,
        "object_ids": object_ids,
        "ranked": ranked,
        "n_candidates": len(candidates),
        "n_hard_pass": sum(1 for c in ranked if c.get("_hard_pass_final")),
    }


def format_top(result: Dict[str, Any], n: int = 10) -> str:
    """Human-readable summary of the top-n candidates for debugging."""
    lines = [
        f"=== {result['config_path']} ({result['title']}) ===",
        f"candidates={result['n_candidates']} hard_pass={result['n_hard_pass']}",
    ]
    for i, c in enumerate(result["ranked"][:n]):
        feats = c.get("_features", {})
        degs = ",".join(sorted(set(feats.get("degree_norms", [])))) or "-"
        lines.append(
            f"{i+1:2d}. {c.get('_id','')} | {c.get('name','?'):28.28s} | "
            f"hard={'Y' if c.get('_hard_pass_final') else 'n'} "
            f"score={c.get('_final_score',0):.3f} ce={c.get('_ce_norm',0):.2f} "
            f"soft={c.get('_soft_final',0):.2f} | deg={degs} | "
            f"yrs={feats.get('total_experience_years',0):.0f} | {feats.get('country','')}"
        )
    return "\n".join(lines)

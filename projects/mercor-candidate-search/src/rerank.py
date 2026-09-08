"""Stage 2: cross-encoder rerank + hard-criteria gate + soft blend (+ judge).

Ordering policy (matches the plan): candidates that PASS all hard criteria are
ranked strictly above those that do not; within a tier we sort by a blended
score = W_HARD*hard_fraction + W_RERANK*cross_encoder + W_SOFT*soft_signal.
An optional OpenAI judge refines hard pass/fail and soft scoring on the top-N
(better for fuzzy criteria like school prestige). A local sentence-transformers
CrossEncoder is a documented fallback if Voyage rerank is unavailable.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from . import cache
from .config import (
    JUDGE_TOP_N,
    JUDGE_WORKERS,
    OAI_KEY,
    OPENAI_MODEL,
    OPENAI_MODEL_FALLBACKS,
    OPENAI_TIMEOUT,
    RERANK_DOC_CHARS,
    USE_JUDGE,
    VOYAGE_API_KEY,
    VOYAGE_RERANK_FALLBACK,
    VOYAGE_RERANK_MODEL,
    W_HARD,
    W_RERANK,
    W_SOFT,
)
from .features import deterministic_assessment, extract_features

_TIER_GAP = 10.0  # ensures any hard-pass candidate outranks any non-pass one

_VO = None
_OAI = None
_LOCAL_CE = None


# --------------------------------------------------------------------------
# Cross-encoder (Voyage rerank-2.5, fallback rerank-2, fallback local)
# --------------------------------------------------------------------------
def _voyage():
    global _VO
    if _VO is None:
        import voyageai

        _VO = voyageai.Client(api_key=VOYAGE_API_KEY)
    return _VO


def build_rerank_query(spec: Dict[str, Any]) -> str:
    hard = "; ".join(spec.get("hard", []))
    parts = [spec.get("title", ""), spec.get("semantic_query", "")]
    if hard:
        parts.append(f"Must have: {hard}")
    return ". ".join(p for p in parts if p).strip()


def _doc_text(cand: Dict[str, Any]) -> str:
    txt = cand.get("rerankSummary") or ""
    if not isinstance(txt, str):
        txt = str(txt)
    return txt[:RERANK_DOC_CHARS] if txt else (cand.get("name") or "")


@retry(stop=stop_after_attempt(2), wait=wait_exponential_jitter(initial=1, max=8), reraise=True)
def _voyage_rerank_call(model: str, query: str, docs: List[str]) -> List[float]:
    res = _voyage().rerank(query, docs, model=model, top_k=len(docs), truncation=True)
    scores = [0.0] * len(docs)
    for r in res.results:
        scores[r.index] = float(r.relevance_score)
    return scores


def _local_crossencoder(query: str, docs: List[str]) -> List[float]:
    """Lazy local fallback. Requires `pip install sentence-transformers`."""
    global _LOCAL_CE
    try:
        if _LOCAL_CE is None:
            from sentence_transformers import CrossEncoder

            _LOCAL_CE = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        import numpy as np

        scores = _LOCAL_CE.predict([(query, d) for d in docs])
        scores = np.asarray(scores, dtype=float)
        # squash to [0,1]
        return list(1.0 / (1.0 + np.exp(-scores)))
    except Exception:
        return [0.0] * len(docs)


def cross_encoder_scores(query: str, docs: List[str], use_cache: bool = True) -> List[float]:
    """Return a relevance score per doc (Voyage rerank, robust fallbacks)."""
    if not docs:
        return []
    key = cache.make_key(VOYAGE_RERANK_MODEL, query, docs)

    def produce():
        for model in (VOYAGE_RERANK_MODEL, VOYAGE_RERANK_FALLBACK):
            try:
                return _voyage_rerank_call(model, query, docs)
            except Exception:
                continue
        return _local_crossencoder(query, docs)

    return cache.disk_cache("rerank", key, produce, enabled=use_cache)


def _normalize(scores: List[float]) -> List[float]:
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-9:
        return [0.5 for _ in scores]
    return [(s - lo) / (hi - lo) for s in scores]


# --------------------------------------------------------------------------
# Optional OpenAI judge over the top-N (fuzzy hard criteria + soft refinement)
# --------------------------------------------------------------------------
def _oai():
    global _OAI
    if _OAI is None:
        from openai import OpenAI

        _OAI = OpenAI(api_key=OAI_KEY, timeout=OPENAI_TIMEOUT, max_retries=1)
    return _OAI


_JUDGE_SYSTEM = """You are a strict technical recruiter evaluating whether a candidate matches a role. \
Given the role's HARD criteria (must ALL be satisfied) and SOFT criteria (nice to have), and the candidate's \
profile summary, decide: (1) does the candidate satisfy EVERY hard criterion? (2) a soft-fit score in [0,1]. \
Be evidence-based and skeptical: if the profile lacks evidence for a hard criterion, it is NOT met. \
For prestige/region criteria (e.g. 'top U.S. university', 'M7 MBA', 'U.S./U.K./Canada'), use your knowledge of institutions. \
Return ONLY JSON: {"hard_pass": true|false, "hard_unmet": [string], "soft_score": number}."""


@retry(stop=stop_after_attempt(2), wait=wait_exponential_jitter(initial=1, max=6), reraise=True)
def _judge_call(model: str, system: str, user: str) -> str:
    resp = _oai().chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
        temperature=0,
        timeout=OPENAI_TIMEOUT,
    )
    return resp.choices[0].message.content or "{}"


def _judge_user(spec: Dict[str, Any], cand: Dict[str, Any], feats: Dict[str, Any]) -> str:
    hard = "\n".join(f"- {h}" for h in spec.get("hard", []))
    soft = "\n".join(f"- {s}" for s in spec.get("soft", []))
    degs = "; ".join(
        f"{d.get('degree_raw','')} in {d.get('fos','')} @ {d.get('school','')} ({d.get('start','')}-{d.get('end','')})"
        for d in feats.get("degrees", [])
    )
    exps = "; ".join(
        f"{e.get('title','')} @ {e.get('company','')} ({e.get('start','')}-{e.get('end','')})"
        for e in feats.get("experiences", [])[:12]
    )
    summary = (cand.get("rerankSummary") or "")[:2000]
    return (
        f"ROLE: {spec.get('title','')}\n\nHARD CRITERIA:\n{hard}\n\nSOFT CRITERIA:\n{soft}\n\n"
        f"CANDIDATE country: {feats.get('country','')}\n"
        f"DEGREES: {degs}\n"
        f"EXPERIENCE: {exps}\n"
        f"TOTAL_EXPERIENCE_YEARS (approx): {feats.get('total_experience_years',0)}\n"
        f"PROFILE SUMMARY: {summary}\n"
    )


def _judge_one(spec: Dict[str, Any], cand: Dict[str, Any], feats: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    key = cache.make_key("judge_v2", OPENAI_MODEL, spec.get("config_path"), spec.get("hard"),
                         spec.get("soft"), cand.get("_id"), (cand.get("rerankSummary") or "")[:500])

    def produce():
        user = _judge_user(spec, cand, feats)
        for model in (OPENAI_MODEL, *OPENAI_MODEL_FALLBACKS):
            try:
                raw = _judge_call(model, _JUDGE_SYSTEM, user)
                data = json.loads(raw)
                return {
                    "hard_pass": bool(data.get("hard_pass", False)),
                    "hard_unmet": data.get("hard_unmet", []) or [],
                    "soft_score": max(0.0, min(1.0, float(data.get("soft_score", 0.0) or 0.0))),
                }
            except Exception:
                continue
        return None

    return cache.disk_cache("judge", key, produce, enabled=True)


def judge_candidates(spec: Dict[str, Any], candidates: List[Dict[str, Any]], top_n: int = JUDGE_TOP_N) -> None:
    """Run the OpenAI judge over the top-`top_n` candidates, in parallel.

    Mutates candidates in place adding `judge_hard_pass` / `judge_soft`.
    """
    targets = candidates[:top_n]
    if not targets or not OAI_KEY:
        return
    try:
        with ThreadPoolExecutor(max_workers=JUDGE_WORKERS) as ex:
            futures = {ex.submit(_judge_one, spec, c, c["_features"]): c for c in targets}
            for fut in as_completed(futures):
                c = futures[fut]
                try:
                    res = fut.result()
                except Exception:
                    res = None
                if res is not None:
                    c["judge_hard_pass"] = res["hard_pass"]
                    c["judge_soft"] = res["soft_score"]
                    c["judge_unmet"] = res["hard_unmet"]
    except Exception:
        # judge is best-effort; on any failure we keep the deterministic order
        return


# --------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------
def rerank(
    spec: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    use_judge: bool = USE_JUDGE,
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """Score and order the candidate set. Returns candidates sorted best-first
    with per-candidate scoring fields attached for transparency."""
    if not candidates:
        return []

    structured = spec.get("structured", {})

    # 1) deterministic features + hard/soft assessment
    for c in candidates:
        feats = extract_features(c)
        c["_features"] = feats
        assess = deterministic_assessment(feats, structured)
        c["_assess"] = assess

    # 2) cross-encoder relevance over rerankSummary (best-effort; never crashes)
    query = build_rerank_query(spec)
    docs = [_doc_text(c) for c in candidates]
    try:
        ce_raw = cross_encoder_scores(query, docs, use_cache=use_cache)
    except Exception:
        ce_raw = [0.0] * len(candidates)
    if len(ce_raw) != len(candidates):
        ce_raw = (ce_raw + [0.0] * len(candidates))[: len(candidates)]
    ce_norm = _normalize(ce_raw)
    for c, raw, nrm in zip(candidates, ce_raw, ce_norm):
        c["_ce_raw"] = raw
        c["_ce_norm"] = nrm

    # 3) provisional blend to pick which candidates the judge sees
    for c in candidates:
        a = c["_assess"]
        c["_blended"] = W_HARD * a["hard_fraction"] + W_RERANK * c["_ce_norm"] + W_SOFT * a["soft_score"]
    candidates.sort(key=lambda c: c["_blended"], reverse=True)

    # 4) optional judge over the top-N (best-effort)
    if use_judge:
        try:
            judge_candidates(spec, candidates)
        except Exception:
            pass

    # 5) final score: hard-pass tier first, then blended (judge overrides where present)
    for c in candidates:
        a = c["_assess"]
        det_pass = a["hard_pass"]
        det_soft = a["soft_score"]
        hard_pass = c.get("judge_hard_pass", det_pass)
        soft = c.get("judge_soft", det_soft)
        # blend hard component: full credit when passing, partial credit otherwise
        hard_comp = 1.0 if hard_pass else a["hard_fraction"]
        blended = W_HARD * hard_comp + W_RERANK * c["_ce_norm"] + W_SOFT * soft
        c["_hard_pass_final"] = bool(hard_pass)
        c["_soft_final"] = soft
        c["_blended"] = blended
        c["_final_score"] = (_TIER_GAP if hard_pass else 0.0) + blended

    candidates.sort(key=lambda c: c["_final_score"], reverse=True)
    return candidates

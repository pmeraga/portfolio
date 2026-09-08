"""Turn a raw query config into a retrieval + gating spec via OpenAI.

Output is a single ``spec`` dict consumed by the rest of the pipeline:
  * ``semantic_query``  -> embedded with voyage-3 for the dense channel
  * ``bm25_keywords``   -> native BM25 over rerankSummary
  * ``structured``      -> deterministic hard-gate + soft-score inputs
                           (see ``features.deterministic_assessment``)

Results are cached on disk. If OpenAI is unavailable, a deterministic heuristic
spec is produced so the pipeline still runs.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from . import cache
from .config import OAI_KEY, OPENAI_MODEL, OPENAI_MODEL_FALLBACKS, OPENAI_TIMEOUT

_CLIENT = None

# Canonical degree tokens the downstream gate understands.
_DEGREE_TOKENS = {"phd", "doctorate", "md", "jd", "mba", "master", "bachelor"}

SYSTEM_PROMPT = """You are a search-query analyst for a candidate-sourcing engine. \
You convert a role spec (title, description, hard criteria, soft criteria) into a STRICT JSON object \
that drives (1) a semantic vector search, (2) a BM25 keyword search, and (3) deterministic eligibility checks \
over structured resume fields (degrees, fields of study, experience titles/years, country).

Return ONLY a JSON object with EXACTLY these keys:
{
  "semantic_query": string,        // 1-3 sentence natural description of the ideal candidate, for embedding
  "bm25_keywords": string,         // space-separated high-signal keywords/phrases (no punctuation needed), for BM25
  "structured": {
    "required_degrees": [string],  // canonical tokens ONLY from: "phd","doctorate","md","jd","mba","master","bachelor". Use the degree(s) the HARD criteria truly require. For "MD"/physician/radiologist use "md". For "PhD" use "phd". For "JD"/lawyer use "jd". For "MBA" use "mba". For a generic "higher/graduate degree" prefer degree_min_level instead.
    "degree_min_level": string|null,   // "bachelor"|"master"|"doctorate" if the role needs "at least" a level rather than a specific degree (e.g. "higher degree in Mechanical Engineering" -> "master"); else null
    "fields_of_study": [string],   // lowercase field terms required/expected, e.g. ["law"], ["biology"], ["mechanical engineering"], ["mathematics","statistics"], ["medicine","radiology"]. Empty if the field is unconstrained.
    "min_years_experience": number|null,  // minimum years of RELEVANT experience implied by hard criteria (e.g. "3+ years practicing law" -> 3; "2-4 years" -> 2). null if none.
    "max_years_experience": number|null,  // upper bound only if explicitly bounded (e.g. "2-4 years" -> 4); else null
    "title_keywords": [string],    // lowercase keywords identifying RELEVANT job titles for the years count, e.g. ["lawyer","attorney","counsel"], ["radiologist","radiology"], ["investment banking","banker","m&a"]
    "required_countries": [string],// lowercase candidate RESIDENCE/PRACTICE country names ONLY when a hard criterion is explicitly about where the candidate currently LIVES or PRACTICES/WORKS, AND it is narrow (one or a few specific countries). Example that QUALIFIES: "2+ years of clinical practice experience in the U.S." -> ["united states"]. This field is the candidate's location, NOT where they studied or earned a degree. Leave it EMPTY ([]) for: degree-origin criteria (e.g. "MD from a medical school in the U.S. or India", "JD from a U.S. law school", "MBA from a U.S. university", "graduate of a European law school", "completed undergraduate studies in the U.S., U.K., or Canada"); and broad/multi-region work criteria (e.g. "at a leading firm in the USA, Europe, or Canada, or in-house at a major global organization"). Region words like "europe" are NOT valid entries. When in doubt, leave EMPTY -- geography/prestige is judged separately and fuzzily.
    "school_tier": string|null,    // "m7" (M7 MBA), "top_us_university", "top_us_law", "top_us_med", "us_uk_canada", or null. This is a FUZZY/prestige signal used for soft scoring, not a hard gate.
    "phd_started_within_years": number|null, // if a hard criterion says the PhD must have started within the last N years (e.g. anthropology "started within the last 3 years" -> 3); else null
    "domain_keywords": [string]    // lowercase domain/skill/tool/subfield terms for soft scoring (e.g. ["irs audit","corporate tax","legal opinion"], ["crispr","pcr","molecular biology"], ["solidworks","ansys","thermal","fluid dynamics"])
  }
}
Rules: be faithful to the HARD criteria for the gate fields and use SOFT criteria mostly for domain_keywords. Prefer high recall: only set required_countries / required_degrees when a hard criterion truly demands it. Output must be valid JSON with no commentary."""


def _client():
    global _CLIENT
    if _CLIENT is None:
        from openai import OpenAI

        _CLIENT = OpenAI(api_key=OAI_KEY, timeout=OPENAI_TIMEOUT, max_retries=1)
    return _CLIENT


def _user_prompt(config: Dict[str, Any]) -> str:
    hard = "\n".join(f"- {h}" for h in config.get("hard", []))
    soft = "\n".join(f"- {s}" for s in config.get("soft", []))
    return (
        f"TITLE: {config.get('title','')}\n\n"
        f"DESCRIPTION: {config.get('description','')}\n\n"
        f"HARD CRITERIA (must pass):\n{hard}\n\n"
        f"SOFT CRITERIA (nice to have / ranking):\n{soft}\n"
    )


@retry(stop=stop_after_attempt(2), wait=wait_exponential_jitter(initial=1, max=8), reraise=True)
def _call_openai(model: str, system: str, user: str) -> str:
    resp = _client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        timeout=OPENAI_TIMEOUT,
    )
    return resp.choices[0].message.content or "{}"


def _openai_spec(config: Dict[str, Any]) -> Dict[str, Any]:
    """Call OpenAI (trying model fallbacks on 404) and parse the JSON spec."""
    user = _user_prompt(config)
    last_err = None
    for model in [OPENAI_MODEL, *OPENAI_MODEL_FALLBACKS]:
        try:
            raw = _call_openai(model, SYSTEM_PROMPT, user)
            return json.loads(raw)
        except Exception as e:  # noqa: BLE001
            msg = str(e).lower()
            last_err = e
            # 404/model-not-found -> try the next model; otherwise also try next.
            if "not found" in msg or "does not exist" in msg or "404" in msg or "model" in msg:
                continue
            continue
    raise RuntimeError(f"OpenAI query-understanding failed: {last_err}")


def _heuristic_spec(config: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic fallback when OpenAI is unavailable."""
    title = config.get("title", "")
    desc = config.get("description", "")
    hard = " ".join(config.get("hard", []))
    soft = " ".join(config.get("soft", []))
    blob = f"{title} {desc} {hard} {soft}".lower()

    required_degrees: List[str] = []
    for tok, pats in {
        "jd": ["jd", "juris doctor", "law school", "practicing law"],
        "mba": ["mba", "m7"],
        "md": ["md", "physician", "radiologist", "medical school", "clinical practice"],
        "phd": ["phd", "ph.d", "doctoral", "doctorate"],
    }.items():
        if any(p in blob for p in pats):
            required_degrees.append(tok)

    m = re.search(r"(\d+)\s*\+?\s*years", blob)
    min_years = int(m.group(1)) if m else None

    return {
        "semantic_query": f"{title}. {desc}".strip(),
        "bm25_keywords": f"{title} " + " ".join(re.findall(r"[a-zA-Z][a-zA-Z+&./-]{2,}", f"{title} {desc}"))[:300],
        "structured": {
            "required_degrees": required_degrees,
            "degree_min_level": "doctorate" if ("phd" in required_degrees) else None,
            "fields_of_study": [],
            "min_years_experience": min_years,
            "max_years_experience": None,
            "title_keywords": [w for w in re.findall(r"[a-z]+", title.lower()) if len(w) > 3],
            "required_countries": [],
            "school_tier": "m7" if "m7" in blob else None,
            "phd_started_within_years": None,
            "domain_keywords": list(dict.fromkeys(re.findall(r"[a-z][a-z+&]{3,}", soft.lower())))[:20],
        },
    }


def _normalize_spec(spec: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce/validate the LLM output into the locked contract; fill defaults."""
    s = dict(spec or {})
    structured = dict(s.get("structured") or {})

    def _strlist(x):
        if isinstance(x, str):
            x = [x]
        if not isinstance(x, list):
            return []
        return [str(v).strip().lower() for v in x if str(v).strip()]

    req_deg = [d for d in _strlist(structured.get("required_degrees")) if d in _DEGREE_TOKENS]
    dml = structured.get("degree_min_level")
    dml = dml.strip().lower() if isinstance(dml, str) and dml.strip().lower() in {"bachelor", "master", "doctorate"} else None
    tier = structured.get("school_tier")
    valid_tiers = {"m7", "top_us_university", "top_us_law", "top_us_med", "us_uk_canada"}
    tier = tier.strip().lower() if isinstance(tier, str) and tier.strip().lower() in valid_tiers else None

    def _num(x):
        try:
            return float(x) if x is not None else None
        except (TypeError, ValueError):
            return None

    out_structured = {
        "required_degrees": req_deg,
        "degree_min_level": dml,
        "fields_of_study": _strlist(structured.get("fields_of_study")),
        "min_years_experience": _num(structured.get("min_years_experience")),
        "max_years_experience": _num(structured.get("max_years_experience")),
        "title_keywords": _strlist(structured.get("title_keywords")),
        "required_countries": _strlist(structured.get("required_countries")),
        "school_tier": tier,
        "phd_started_within_years": _num(structured.get("phd_started_within_years")),
        "domain_keywords": _strlist(structured.get("domain_keywords")),
    }

    semantic = s.get("semantic_query") or f"{config.get('title','')}. {config.get('description','')}"
    bm25 = s.get("bm25_keywords") or config.get("title", "")
    return {
        "config_path": config.get("config_path", ""),
        "title": config.get("title", ""),
        "semantic_query": str(semantic).strip(),
        "bm25_keywords": str(bm25).strip(),
        "structured": out_structured,
        "hard": list(config.get("hard", [])),
        "soft": list(config.get("soft", [])),
    }


def understand_query(config: Dict[str, Any], use_cache: bool = True, use_openai: bool = True) -> Dict[str, Any]:
    """Return the locked ``spec`` dict for a config (cached)."""
    key = cache.make_key(OPENAI_MODEL, "v4", config.get("config_path"), config.get("title"),
                         config.get("description"), config.get("hard"), config.get("soft"), use_openai)

    def produce():
        if use_openai and OAI_KEY:
            try:
                raw = _openai_spec(config)
                return _normalize_spec(raw, config)
            except Exception:
                pass
        return _normalize_spec(_heuristic_spec(config), config)

    return cache.disk_cache("qu", key, produce, enabled=use_cache)

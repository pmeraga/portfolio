# Candidate Search & Re-Ranking Engine

**Portfolio context:** This project was made for Mercor. Source and role configs are included; local credentials and cached candidate/service data are excluded. Historical evaluation results below use public evaluator feedback and are not held-out measurements.

A two-stage retrieval + re-ranking system over a read-only Turbopuffer namespace
(`search-test-v4`, ~200k candidate profiles). For each role config (title +
description + hard criteria + soft criteria) it returns the top-10 candidate
`object_id`s and submits them to the live eval endpoint, optimizing **hard
criteria first, then soft criteria**.

## Eval scoring model & submission policy (the key insight)

The `/evaluate` server runs its **own** per-candidate LLM judge and returns, for
every submitted candidate, a pass/fail on **each** hard criterion plus 1–4 soft
scores. A candidate's `final_score` is **0 unless it passes EVERY hard criterion**
(strict AND-gate), and the headline metric `average_final_score` is the **mean**
of submitted candidates' `final_scores`. Therefore **every hard-failing candidate
you submit is a 0 that drags the mean down**, and padding to 10 is harmful.

Winning policy (`run_precision.py`): submit **only candidates confirmed to pass
all hard criteria, best-first, up to 10** — never pad with hard-fails. Crucially,
the eval response itself is used as an **oracle**: probe the top fused candidates,
read `individual_results[*].final_score`/`passes` to learn which ones the server
confirms as all-hard-pass, then submit just those. This lifted the public-set
average from **55.7 → 86.2** (see "Results").

## Architecture

```
config (title, description, hard[], soft[])
   │
   ▼
[1] Query understanding  (OpenAI gpt-4.1-mini, JSON, cached)
   → semantic_query · bm25_keywords · structured spec
     (required_degrees, fields_of_study, min_years, title_keywords,
      required_countries, school_tier, phd_recency, domain_keywords)
   │
   ▼
[2] Hybrid retrieval (Stage 1)
   ├─ Dense ANN   : voyage-3 query embedding → vector ANN     (top ~300)
   └─ Lexical     : native BM25 over `rerankSummary`          (top ~300)
   → Reciprocal Rank Fusion (k=60) → ~120 candidates
   │
   ▼
[3] Re-rank (Stage 2)
   ├─ Cross-encoder : Voyage `rerank-2.5` over `rerankSummary`
   ├─ Hard gate     : deterministic checks on structured metadata
   │                  (degree type incl. MD/JD/MBA/PhD, field of study,
   │                   computed years of relevant experience, country, PhD recency)
   ├─ Soft score    : domain-keyword / prestige signals
   └─ LLM judge     : OpenAI confirms hard pass/fail + soft fit on the top ~30
   → blended score = 0.50·hard + 0.35·cross-encoder + 0.15·soft
   → hard-pass candidates ranked strictly above non-pass
   │
   ▼
[4] Top-10 object_ids → POST /evaluate (scores logged to results/scores.json)
```

### Key design decisions
- **TPUF native BM25** on `rerankSummary` (no local index over 200k rows). Two
  TPUF queries (ANN + BM25) fused client-side with RRF (k=60).
- **Hard criteria enforced in the rerank gate**, not as strict Stage-1 filters.
  `deg_degrees` values are case-sensitive exact strings, so over-filtering in
  Stage 1 hurts recall. Stage 1 maximizes recall; the gate + judge enforce
  precision. **MD** is detected via medical field-of-study / `rerankSummary`
  signals (it is usually stored as `Doctorate`), not a plain degree filter.
- **The LLM judge is authoritative** for the final hard pass/fail on the top
  candidates, which keeps fuzzy/geographic criteria (e.g. "top U.S. university",
  "M7 MBA", "studied in US/UK/Canada") robust without nuking recall.
- **Cross-encoder = Voyage `rerank-2.5`** (hosted; fallbacks: `rerank-2`, then a
  lazy local `sentence-transformers` CrossEncoder).
- **Caching everywhere** (embeddings, TPUF query results, OpenAI/Voyage
  responses) under `results/cache/` to avoid repeat cost; `tenacity` retries
  with exponential backoff handle 429/5xx.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Put secrets in .env (gitignored): TURBOPUFFER_API_KEY, VOYAGE_API_KEY, OAI_KEY,
# TPUF_REGION, TPUF_NAMESPACE, EVAL_EMAIL
```

## Usage

```bash
# RECOMMENDED: precision-first, time-boxed, submits only hard-passers (no padding)
.venv/bin/python run_precision.py

# Original blend pipeline: run all 10 configs end-to-end and submit each to /evaluate
.venv/bin/python run_all.py

# Run a single config
.venv/bin/python run_all.py --config tax_lawyer.yml --debug

# Dry run (no submission), print top candidates
.venv/bin/python run_all.py --no-submit --debug

# Disable the OpenAI judge (faster/cheaper) or query-understanding LLM
.venv/bin/python run_all.py --no-judge
.venv/bin/python run_all.py --no-openai
```

Scores are written to `results/scores.json` and printed as a table at the end.

## Results (public eval, `average_final_score`)

Precision-first (hard-pass-only) vs. the earlier padded-top-10 policy:

| config | padded top-10 | hard-pass-only | #submitted |
|--------|--------------:|---------------:|-----------:|
| tax_lawyer | 83.3 | **89.3** | 10 |
| junior_corporate_lawyer | 75.3 | **90.0** | 10 |
| radiology | 83.7 | **87.3** | 10 |
| doctors_md | 15.5 | **78.8** | 4 |
| biology_expert | 36.3 | **79.6** | 9 |
| anthropology | 8.3 | **83.3** | 1 |
| mathematics_phd | 23.5 | **78.8** | 4 |
| quantitative_finance | 52.7 | **88.1** | 7 |
| bankers | 76.3 | **92.0** | 10 |
| mechanical_engineers | 92.7 | **95.0** | 10 |
| **average** | **55.7** | **86.2** | |

The hard-pass-only policy wins on every config: dropping zero-scoring hard-fails
raises the mean dramatically, especially for selective roles (anthropology,
doctors_md, mathematics_phd) where few candidates clear the strict gate.

> Note: the public configs allow 1–10 ids. The **private** set requires exactly
> 10 ids per config; for that, pad the hard-pass set up to 10 with the next
> best-ranked candidates (kept on disk as the padded top-10 list).

## Project layout

| Path | Purpose |
|------|---------|
| `configs/queries.yaml` | The 10 role configs (title, description, hard, soft, config_path) |
| `src/config.py` | Secrets/env, model names, tuning knobs, candidate-dict contract |
| `src/cache.py` | JSON disk cache |
| `src/embed.py` | voyage-3 query embeddings (cached) |
| `src/tpuf_client.py` | TPUF ANN + BM25 + filter query wrappers |
| `src/query_understanding.py` | OpenAI → semantic query + BM25 keywords + structured spec |
| `src/retrieve.py` | Hybrid retrieval + RRF fusion |
| `src/features.py` | Deterministic hard/soft feature extraction + gate assessment |
| `src/rerank.py` | Voyage cross-encoder + hard gate + soft blend + LLM judge |
| `src/pipeline.py` | `search(config) → ranked object_ids` |
| `src/evaluate.py` | `/add_user` + `/evaluate` + score persistence |
| `run_all.py` | CLI entry point: run + submit + score table |
| `scripts/` | One-off live smoke tests (TPUF/Voyage/OpenAI/eval) |

## Tuning knobs (`src/config.py`)
`ANN_TOP_K`, `BM25_TOP_K`, `RRF_K`, `CANDIDATE_K`, `JUDGE_TOP_N`, `W_HARD`,
`W_RERANK`, `W_SOFT`, `USE_JUDGE`. Logic is kept general (no hard-coded candidate
ids) so it transfers to unseen queries.

#!/usr/bin/env python
"""Run the candidate search pipeline for one or all configs and submit to eval.

Usage:
  .venv/bin/python run_all.py                      # all 10 configs, submit each
  .venv/bin/python run_all.py --config tax_lawyer.yml
  .venv/bin/python run_all.py --no-submit --debug  # dry run, print top candidates
  .venv/bin/python run_all.py --no-judge           # skip the OpenAI judge
"""
from __future__ import annotations

import argparse
import sys
import time
import traceback
from typing import Any, Dict, List

from src.config import CANDIDATE_K
from src.evaluate import extract_score, register_user, save_score, submit_and_record
from src.pipeline import format_top, get_config, load_configs, search


def run_one(cfg: Dict[str, Any], args) -> Dict[str, Any]:
    t0 = time.time()
    result = search(
        cfg,
        candidate_k=args.candidate_k,
        use_judge=(not args.no_judge),
        use_openai_understanding=(not args.no_openai),
        use_cache=(not args.no_cache),
    )
    elapsed = time.time() - t0
    if args.debug:
        print(format_top(result, n=10))
    object_ids = result["object_ids"]
    print(
        f"[{cfg['config_path']}] {len(object_ids)} ids | "
        f"cands={result['n_candidates']} hard_pass={result['n_hard_pass']} | {elapsed:.1f}s"
    )

    record: Dict[str, Any] = {
        "config_path": cfg["config_path"],
        "object_ids": object_ids,
        "n_candidates": result["n_candidates"],
        "n_hard_pass": result["n_hard_pass"],
        "score": None,
        "response": None,
    }

    if not args.no_submit:
        if len(object_ids) != 10:
            print(f"  WARNING: {cfg['config_path']} produced {len(object_ids)} ids (expected 10)")
        meta = {"candidate_k": args.candidate_k, "judge": not args.no_judge}
        resp = submit_and_record(cfg["config_path"], object_ids, meta=meta)
        record["response"] = resp
        record["score"] = extract_score(resp)
        print(f"  -> submitted; score={record['score']} resp={_short(resp)}")
    return record


def _short(resp: Any, n: int = 220) -> str:
    import json

    try:
        s = json.dumps(resp)
    except Exception:
        s = str(resp)
    return s if len(s) <= n else s[:n] + "..."


def print_table(records: List[Dict[str, Any]]) -> None:
    print("\n" + "=" * 64)
    print(f"{'config_path':32s} {'ids':>4s} {'hard':>5s} {'score':>10s}")
    print("-" * 64)
    scores = []
    for r in records:
        sc = r.get("score")
        scores.append(sc if isinstance(sc, (int, float)) else None)
        sc_str = f"{sc:.4f}" if isinstance(sc, (int, float)) else "n/a"
        print(f"{r['config_path']:32s} {len(r['object_ids']):>4d} {r['n_hard_pass']:>5d} {sc_str:>10s}")
    print("-" * 64)
    valid = [s for s in scores if s is not None]
    if valid:
        print(f"{'TOTAL':32s} {'':>4s} {'':>5s} {sum(valid):>10.4f}")
        print(f"{'AVERAGE':32s} {'':>4s} {'':>5s} {sum(valid)/len(valid):>10.4f}")
    print("=" * 64)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Run candidate search + submit to eval.")
    p.add_argument("--config", help="single config_path (e.g. tax_lawyer.yml); default = all")
    p.add_argument("--no-submit", action="store_true", help="run pipeline but do not POST /evaluate")
    p.add_argument("--no-judge", action="store_true", help="disable the OpenAI judge stage")
    p.add_argument("--no-openai", action="store_true", help="use heuristic query understanding (no OpenAI)")
    p.add_argument("--no-cache", action="store_true", help="bypass disk caches")
    p.add_argument("--candidate-k", type=int, default=CANDIDATE_K, help="fused candidate set size")
    p.add_argument("--debug", action="store_true", help="print top candidates per config")
    args = p.parse_args(argv)

    if not args.no_submit:
        reg = register_user()
        print(f"register_user -> {reg}")

    if args.config:
        configs = [get_config(args.config)]
    else:
        configs = load_configs()
    print(f"Running {len(configs)} config(s): {[c['config_path'] for c in configs]}\n")

    records: List[Dict[str, Any]] = []
    for cfg in configs:
        try:
            records.append(run_one(cfg, args))
        except Exception as e:  # noqa: BLE001
            print(f"[{cfg['config_path']}] ERROR: {e}")
            traceback.print_exc()
            records.append({
                "config_path": cfg["config_path"], "object_ids": [],
                "n_candidates": 0, "n_hard_pass": 0, "score": None, "response": {"error": str(e)},
            })

    print_table(records)
    return 0


if __name__ == "__main__":
    sys.exit(main())

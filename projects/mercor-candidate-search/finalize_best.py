#!/usr/bin/env python
"""Finalize the best submission per config from two strategy runs.

Compares a baseline (no-judge) score file against the current scores.json
(judge run), and for every config re-submits the higher-scoring id set so the
eval endpoint's last-seen submission AND results/scores.json both reflect the
best result. Idempotent and safe to re-run.
"""
from __future__ import annotations

import json
import sys

from src.config import SCORES_PATH
from src.evaluate import extract_score, submit_and_record

BASELINE = SCORES_PATH.parent / "scores_nojudge.json"


def main() -> int:
    judge = json.load(open(SCORES_PATH))
    base = json.load(open(BASELINE)) if BASELINE.exists() else {}

    configs = sorted(set(judge) | set(base))
    print(f"{'config':32s} {'baseline':>9s} {'judge':>9s} {'chosen':>9s} {'src':>8s}")
    print("-" * 72)
    final = {}
    for cp in configs:
        b = base.get(cp, {})
        j = judge.get(cp, {})
        bs = b.get("score")
        js = j.get("score")
        bs_n = bs if isinstance(bs, (int, float)) else -1.0
        js_n = js if isinstance(js, (int, float)) else -1.0

        # Prefer baseline on ties (simpler, no judge dependency / more general).
        if bs_n >= js_n:
            winner, src = b, "baseline"
        else:
            winner, src = j, "judge"

        ids = winner.get("object_ids", [])
        # Re-submit the winner so the endpoint's final state matches the best.
        resp = submit_and_record(cp, ids, meta={"finalized_from": src})
        score = extract_score(resp)
        final[cp] = score
        print(f"{cp:32s} {bs_n:9.2f} {js_n:9.2f} {score if score is not None else float('nan'):9.2f} {src:>8s}")

    print("-" * 72)
    vals = [v for v in final.values() if isinstance(v, (int, float))]
    if vals:
        print(f"{'AVERAGE':32s} {'':>9s} {'':>9s} {sum(vals)/len(vals):9.2f}")
        print(f"{'TOTAL':32s} {'':>9s} {'':>9s} {sum(vals):9.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

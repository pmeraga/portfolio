"""Score complete advanced runs without inventing or silently dropping outputs.

Usage: python3 -m src.analyze_advanced --data data/advanced_pilot.jsonl
    --pred results/advanced_pilot_predictions.jsonl --outdir results/advanced_pilot_analysis
"""
import argparse
import csv
import json
import math
import random
from collections import defaultdict
from html import escape
from pathlib import Path

VARIANTS = ("control", "challenge", "rescue")
BOOTSTRAP_SEED = 991
BOOTSTRAP_REPS = 5000
NUMERIC_TOLERANCE = 1e-6


def read_jsonl(path):
    rows = []
    for lineno, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                row = json.loads(line)
            except ValueError as exc:
                raise ValueError(f"Invalid JSON at {path}:{lineno}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Expected object at {path}:{lineno}")
            rows.append(row)
    return rows


def wilson_interval(k, n, z=1.96):
    if n <= 0 or not 0 <= k <= n:
        raise ValueError("Wilson interval requires 0 <= errors <= n and n > 0")
    p = k / n
    denominator = 1 + z * z / n
    midpoint = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return max(0.0, midpoint - half), min(1.0, midpoint + half)


def bootstrap_paired_ci(pairs, seed=BOOTSTRAP_SEED, reps=BOOTSTRAP_REPS):
    """Percentile CI from paired-context resampling of error differences."""
    if not pairs or reps < 100:
        raise ValueError("Paired bootstrap requires pairs and at least 100 repetitions")
    differences = [int(a) - int(b) for a, b in pairs]
    if len(set(differences)) == 1:
        return float(differences[0]), float(differences[0])
    rng = random.Random(seed)
    n = len(differences)
    means = sorted(sum(differences[rng.randrange(n)] for _ in range(n)) / n
                   for _ in range(reps))
    return means[int(0.025 * reps)], means[min(reps - 1, int(0.975 * reps))]


def exact_mcnemar(pairs):
    b = sum(a and not c for a, c in pairs)
    c = sum(c and not a for a, c in pairs)
    discordant = b + c
    p = (min(1.0, 2 * sum(math.comb(discordant, k) for k in range(min(b, c) + 1))
             / 2 ** discordant) if discordant else 1.0)
    return {"challenge_only_errors": b, "comparator_only_errors": c,
            "n_discordant": discordant, "p_exact": p}


def valid_answer(value, answer_type):
    if answer_type == "boolean":
        return type(value) is bool
    if answer_type == "number":
        return type(value) in (int, float) and math.isfinite(value)
    raise ValueError(f"Unknown answer_type: {answer_type!r}")


def evidence_grounded(note, evidence):
    """Only remove outer quotation marks; do not fuzzy-match invented evidence."""
    if not isinstance(evidence, str) or not evidence.strip():
        return False
    value = evidence.strip()
    for left, right in (("\"", "\""), ("'", "'"), ("“", "”"), ("‘", "’")):
        if len(value) >= 2 and value.startswith(left) and value.endswith(right):
            value = value[1:-1].strip()
            break
    return bool(value) and value in note


def _index(rows, label):
    result = {}
    for row in rows:
        cid = row.get("id")
        if not isinstance(cid, str) or not cid:
            raise ValueError(f"Missing or invalid ID in {label}")
        if cid in result:
            raise ValueError(f"Duplicate ID {cid!r} in {label}")
        result[cid] = row
    return result


def summarize(cases, predictions):
    """Return (summary, scored copies); never mutate caller predictions."""
    if not cases:
        raise ValueError("Dataset is empty")
    expected = _index(cases, "dataset")
    actual = _index(predictions, "predictions")
    missing, extra = set(expected) - set(actual), set(actual) - set(expected)
    if missing or extra:
        raise ValueError(f"Incomplete/mismatched evaluation: {len(missing)} missing, {len(extra)} extra")
    pair_cases = defaultdict(dict)
    by_variant = defaultdict(list)
    scored = []
    required = ("pair_id", "phase", "family", "variant", "note", "question", "gold", "answer_type")
    phases = set()
    for cid, case in expected.items():
        if any(key not in case for key in required):
            raise ValueError(f"Case {cid} is missing required fields")
        if case["variant"] not in VARIANTS:
            raise ValueError(f"Unknown variant for {cid}")
        if not valid_answer(case["gold"], case["answer_type"]):
            raise ValueError(f"Gold label has invalid type for {cid}")
        pred = actual[cid]
        # Compare all case fields, including future generator provenance fields.
        for key, value in case.items():
            if key not in pred or json.dumps(pred[key], sort_keys=True) != json.dumps(value, sort_keys=True):
                raise ValueError(f"Prediction {cid} has mismatched field {key}")
        pair_key = (case["family"], case["pair_id"])
        if case["variant"] in pair_cases[pair_key]:
            raise ValueError(f"Duplicate pair/variant: {pair_key} / {case['variant']}")
        phases.add(case["phase"])
        answer_ok = valid_answer(pred.get("answer"), case["answer_type"])
        evidence_ok = isinstance(pred.get("evidence"), str) and bool(pred["evidence"].strip())
        api_failed = pred.get("error") is not None
        operational = api_failed or not answer_ok or not evidence_ok
        if case["answer_type"] == "boolean":
            equal = answer_ok and pred["answer"] is case["gold"]
        else:
            equal = answer_ok and math.isclose(pred["answer"], case["gold"], rel_tol=0.0,
                                               abs_tol=NUMERIC_TOLERANCE)
        record = {**pred, "operational_error": operational,
                  "semantic_error": not operational and not equal,
                  "correct": not operational and equal,
                  "evidence_grounded": evidence_grounded(case["note"], pred.get("evidence"))}
        pair_cases[pair_key][case["variant"]] = record
        by_variant[(case["family"], case["variant"])].append(record)
        scored.append(record)
    if len(phases) != 1:
        raise ValueError("Do not mix pilot and confirmation phases in one analysis")
    for key, variants in pair_cases.items():
        if set(variants) != set(VARIANTS):
            raise ValueError(f"Unmatched pair {key}: expected control, challenge, rescue")
        if len({v["answer_type"] for v in variants.values()}) != 1:
            raise ValueError(f"Answer types differ within pair {key}")
    model_ids = {(p.get("model"), p.get("model_digest")) for p in predictions}
    if len(model_ids) > 1:
        raise ValueError("Mixed model tags or digests in one analysis")

    metrics = []
    for (family, variant), group in sorted(by_variant.items()):
        errors = sum(not p["correct"] for p in group)
        lo, hi = wilson_interval(errors, len(group))
        metrics.append({"family": family, "variant": variant, "n": len(group),
                        "errors": errors, "semantic_errors": sum(p["semantic_error"] for p in group),
                        "operational_errors": sum(p["operational_error"] for p in group),
                        "error_rate": errors / len(group), "ci95_low": lo, "ci95_high": hi,
                        "ungrounded_evidence": sum(not p["evidence_grounded"] for p in group)})
    contrasts = []
    for family in sorted({c["family"] for c in cases}):
        families = [variants for (fam, _), variants in sorted(pair_cases.items()) if fam == family]
        for comparison in ("control", "rescue"):
            pairs = [(not v["challenge"]["correct"], not v[comparison]["correct"]) for v in families]
            lo, hi = bootstrap_paired_ci(pairs)
            contrasts.append({"family": family, "challenge": "challenge", "comparison": comparison,
                              "n_pairs": len(pairs),
                              "error_rate_difference": sum(int(a) - int(b) for a, b in pairs) / len(pairs),
                              "ci95_low": lo, "ci95_high": hi,
                              "bootstrap_degenerate": lo == hi,
                              **exact_mcnemar(pairs)})
    warning = ("Pairs are generated template contexts, not independent patients sampled from a clinical population. "
               "A degenerate bootstrap interval (including [0, 0] with no errors) does not establish equivalence "
               "or absence of rare failures. McNemar tests are unadjusted exploratory comparisons unless a "
               "specific confirmation hypothesis was frozen before seeing confirmation outputs. "
               "Evidence grounding is an exact substring check after removing outer quotes; it is separate "
               "from answer accuracy and does not adjudicate whether the quote supports the answer.")
    return {"phase": next(iter(phases)), "n_cases": len(cases), "n_pair_contexts": len(pair_cases),
            "n_errors": sum(not p["correct"] for p in scored),
            "n_semantic_errors": sum(p["semantic_error"] for p in scored),
            "n_operational_errors": sum(p["operational_error"] for p in scored),
            "n_ungrounded_evidence": sum(not p["evidence_grounded"] for p in scored),
            "model": predictions[0].get("model"), "model_digest": predictions[0].get("model_digest"),
            "numeric_abs_tolerance": NUMERIC_TOLERANCE,
            "bootstrap_seed": BOOTSTRAP_SEED, "bootstrap_repetitions": BOOTSTRAP_REPS,
            "interpretation_warning": warning, "metrics": metrics, "contrasts": contrasts}, scored


def isolated_failure_examples(scored):
    pairs = defaultdict(dict)
    for row in scored:
        pairs[(row["family"], row["pair_id"])][row["variant"]] = row
    selected = []
    for (family, pid), variants in sorted(pairs.items()):
        if (variants["challenge"]["semantic_error"] and variants["control"]["correct"]
                and variants["rescue"]["correct"]):
            selected.append({"family": family, "pair_id": pid,
                             "interpretation": "Observed answer error with correct matched control and rescue; audit clinical gold and evidence before claiming a failure mechanism.",
                             "variants": {key: variants[key] for key in VARIANTS}})
    return selected


def render_svg(metrics, path):
    width, height, left, plot_width = 1120, 100 + 36 * len(metrics), 340, 560
    colors = {"control": "#57778c", "challenge": "#b44832", "rescue": "#387963"}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Observed advanced evaluation error rates">',
           '<rect width="100%" height="100%" fill="white"/>',
           '<g font-family="Arial, sans-serif">',
           '<text x="24" y="28" font-size="19" font-weight="bold">Observed error rate by test family and condition</text>',
           '<text x="24" y="49" font-size="12" fill="#555">Whiskers: 95% Wilson intervals. Operational errors count as errors. Synthetic template suite.</text>']
    for tick in (0, .25, .5, .75, 1):
        x = left + tick * plot_width
        out.append(f'<text x="{x}" y="73" text-anchor="middle" font-size="11">{tick:.0%}</text>')
    for index, metric in enumerate(metrics):
        y = 84 + index * 36
        lo, hi = left + plot_width * metric["ci95_low"], left + plot_width * metric["ci95_high"]
        out.extend([
            f'<text x="24" y="{y + 15}" font-size="12">{escape(metric["family"])} / {escape(metric["variant"])}</text>',
            f'<rect x="{left}" y="{y}" width="{plot_width}" height="22" fill="#f0f3f4"/>',
            f'<rect x="{left}" y="{y}" width="{plot_width * metric["error_rate"]}" height="22" fill="{colors[metric["variant"]]}"/>',
            f'<path d="M {lo} {y+6} v 10 M {lo} {y+11} H {hi} M {hi} {y+6} v 10" stroke="#111" fill="none"/>',
            f'<text x="{left + plot_width + 16}" y="{y+15}" font-size="12">{metric["errors"]}/{metric["n"]} ({metric["error_rate"]:.1%})</text>'])
    out.extend(["</g>", "</svg>"])
    Path(path).write_text("\n".join(out), encoding="utf-8")


def write_outputs(summary, scored, outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with (outdir / "variant_metrics.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary["metrics"][0]))
        writer.writeheader()
        writer.writerows(summary["metrics"])
    with (outdir / "errors.jsonl").open("w", encoding="utf-8") as stream:
        for row in scored:
            if not row["correct"]:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    examples = isolated_failure_examples(scored)
    (outdir / "isolated_failure_examples.json").write_text(json.dumps(examples, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    render_svg(summary["metrics"], outdir / "figure.svg")
    lines = ["# Observed advanced evaluation results", "", f"Phase: `{summary['phase']}`. "
             f"Scored {summary['n_cases']} prompts in {summary['n_pair_contexts']} generated paired contexts. "
             f"Semantic errors: {summary['n_semantic_errors']}; operational errors: {summary['n_operational_errors']}.", "",
             "| Family | Condition | Errors / n | Rate (95% Wilson CI) | Semantic | Operational | Ungrounded quotes |",
             "|---|---|---:|---:|---:|---:|---:|"]
    # Rank families by challenge error rate, retaining the within-family control/challenge/rescue order.
    challenge_rates = {m["family"]: m["error_rate"] for m in summary["metrics"] if m["variant"] == "challenge"}
    for metric in sorted(summary["metrics"], key=lambda m: (-challenge_rates[m["family"]], m["family"], VARIANTS.index(m["variant"]))):
        lines.append(f"| {metric['family']} | {metric['variant']} | {metric['errors']}/{metric['n']} | "
                     f"{metric['error_rate']:.1%} ({metric['ci95_low']:.1%}–{metric['ci95_high']:.1%}) | "
                     f"{metric['semantic_errors']} | {metric['operational_errors']} | {metric['ungrounded_evidence']} |")
    lines.extend(["", "Paired differences are challenge error rate minus the comparison error rate.", "",
                  "| Family | Comparison | Difference (95% paired bootstrap CI), pp | Discordants (challenge / comparison only) | Exact p |",
                  "|---|---|---:|---:|---:|"])
    for contrast in summary["contrasts"]:
        lines.append(f"| {contrast['family']} | {contrast['comparison']} | "
                     f"{100*contrast['error_rate_difference']:+.1f} ({100*contrast['ci95_low']:+.1f}, {100*contrast['ci95_high']:+.1f}) | "
                     f"{contrast['challenge_only_errors']} / {contrast['comparator_only_errors']} | {contrast['p_exact']:.4g} |")
    lines.extend(["", f"Matched challenge errors with correct control and rescue: {len(examples)}. "
                  "These are candidates for manual review, not automatically validated clinical findings.", "",
                  summary["interpretation_warning"], ""])
    (outdir / "RESULTS_TABLE.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--pred", required=True, type=Path)
    parser.add_argument("--outdir", required=True, type=Path)
    args = parser.parse_args()
    try:
        summary, scored = summarize(read_jsonl(args.data), read_jsonl(args.pred))
        write_outputs(summary, scored, args.outdir)
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    print(f"Scored {summary['n_cases']} prompts: {summary['n_semantic_errors']} semantic errors, "
          f"{summary['n_operational_errors']} operational errors. Results: {args.outdir / 'RESULTS_TABLE.md'}")


if __name__ == "__main__":
    main()

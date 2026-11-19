"""Explore successive synthetic probes until a paired semantic error reproduces.

This is exploratory stopping on an observed error, not a confirmatory failure-rate
estimate. All rounds, including null results and failed replications, are retained.
No model is invoked merely by importing this module.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from .analyze_advanced import (isolated_failure_examples, read_jsonl, summarize,
                               write_outputs)
from .run_advanced import DIGEST, MODEL, SYSTEM

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 8192, "num_predict": 160}
REPLICATIONS = 2
OPERATIONAL_ERROR_LIMIT = 0.25


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False,
                       allow_nan=False) + "\n").encode()


def write_json(path, value):
    """Atomically replace derived state, leaving all empirical JSONL logs intact."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".pending")
    with temporary.open("wb") as stream:
        stream.write(json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def freeze_bytes(path, content):
    """Create a frozen input once, or require byte-identical regeneration."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f"Frozen input changed: {path}. Preserve it and use a new search directory.")
    else:
        with path.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())


def freeze_dataset(path, cases):
    content = "".join(json.dumps(case, ensure_ascii=False, sort_keys=True,
                                 allow_nan=False) + "\n" for case in cases).encode()
    freeze_bytes(path, content)


def configuration(require_gpu, min_families):
    files = ("src/run_advanced.py", "src/analyze_advanced.py", "src/search_failures.py",
             "src/generate_advanced.py", "src/generate_stress.py", "data/advanced_pilot.jsonl")
    return {"model": MODEL, "model_digest": DIGEST, "options": OPTIONS,
            "require_gpu": require_gpu, "min_families": min_families,
            "replications": REPLICATIONS,
            "system_sha256": hashlib.sha256(SYSTEM.encode()).hexdigest(),
            "sources_sha256": {name: sha256(PROJECT_ROOT/name) if (PROJECT_ROOT/name).is_file()
                               else None for name in files},
            "stopping_rule": "Stop after semantic challenge errors with correct controls/rescues reproduce twice in the requested number of families."}


def execute_inference(data_path, prediction_path, require_gpu=False):
    command = [sys.executable, "-u", "-m", "src.run_advanced", "--data", str(data_path),
               "--out", str(prediction_path), "--model", MODEL, "--expect-digest", DIGEST,
               "--num-ctx", str(OPTIONS["num_ctx"]), "--num-predict", str(OPTIONS["num_predict"])]
    if require_gpu:
        command.append("--require-gpu")
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def generate_round(round_index):
    if round_index == 0:
        return read_jsonl(PROJECT_ROOT / "data/advanced_pilot.jsonl")
    # Import lazily: stress generation does not run during import or test discovery.
    from .generate_stress import generate_stress
    return generate_stress(round_index)


def append_event(path, event):
    """Idempotent event log across resumed searches."""
    existing = read_jsonl(path) if path.exists() else []
    if any(row.get("event_id") == event["event_id"] for row in existing):
        return
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({**event, "recorded_at_utc": timestamp()},
                                ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def run_and_score(cases, directory, require_gpu):
    data_path, prediction_path = directory / "cases.jsonl", directory / "predictions.jsonl"
    freeze_dataset(data_path, cases)
    execute_inference(data_path, prediction_path, require_gpu)
    summary, scored = summarize(cases, read_jsonl(prediction_path))
    write_outputs(summary, scored, directory / "analysis")
    if summary["n_operational_errors"] / summary["n_cases"] >= OPERATIONAL_ERROR_LIMIT:
        raise RuntimeError(f"Operational errors on at least {OPERATIONAL_ERROR_LIMIT:.0%} of {directory.name}: "
                           "inspect the engine/runtime before continuing. These do not count as semantic model failures.")
    return summary, scored


def replicate_candidate(candidate, round_dir, require_gpu):
    """Require the same challenge to be semantically wrong in two fresh repeats."""
    pid = candidate["pair_id"]
    slug = hashlib.sha256(pid.encode()).hexdigest()[:16]
    directory = round_dir / "replications" / slug
    originals = candidate["variants"]
    # Retain all original immutable case metadata; discard prediction/scoring fields.
    original_cases = read_jsonl(round_dir / "cases.jsonl")
    cases = [case for case in original_cases if case["pair_id"] == pid and case["family"] == candidate["family"]]
    rounds = [{"source": "initial_search", "variants": originals}]
    reproducible = True
    for repeat in range(1, REPLICATIONS + 1):
        repeat_dir = directory / f"repeat_{repeat}"
        _, scored = run_and_score(cases, repeat_dir, require_gpu)
        variants = {row["variant"]: row for row in scored}
        matched = (variants["challenge"]["semantic_error"] and variants["control"]["correct"]
                   and variants["rescue"]["correct"])
        rounds.append({"source": f"repeat_{repeat}", "paired_error_reproduced": bool(matched),
                       "variants": variants})
        reproducible = reproducible and matched
    result = {"family": candidate["family"], "pair_id": pid,
              "reproduced": bool(reproducible), "runs": rounds,
              "interpretation": "Repeated semantic error under matched controls. Synthetic gold and clinical relevance still require independent review; this is an exploratory candidate, not a confirmed clinical mechanism."}
    write_json(directory / "replication_summary.json", result)
    return result


def search(outdir, min_families=1, max_rounds=None, require_gpu=False):
    if min_families < 1:
        raise ValueError("min_families must be positive")
    if max_rounds is not None and max_rounds < 1:
        raise ValueError("max_rounds must include at least the initial pilot")
    outdir = Path(outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    config = configuration(require_gpu, min_families)
    freeze_bytes(outdir / "search_configuration_lock.json", json_bytes(config))
    state_path, candidate_path = outdir / "search_state.json", outdir / "REPRODUCED_CANDIDATES.json"
    state = {"created_at_utc": timestamp(), "status": "running", "rounds": [],
             "interpretation": "Stopping on an observed error makes this an exploratory search. All rounds, including negative findings, must be disclosed."}
    if state_path.exists():
        state = json.loads(state_path.read_text())
    reproduced = json.loads(candidate_path.read_text()) if candidate_path.exists() else []
    successful_ids = {(item["family"], item["pair_id"]) for item in reproduced}

    def save_state(status, error=None):
        state.update(status=status, updated_at_utc=timestamp(),
                     reproduced_families=sorted({item["family"] for item in reproduced}),
                     n_reproduced_candidates=len(reproduced))
        if error:
            state["error"] = error
        else:
            state.pop("error", None)
        write_json(state_path, state)
        write_json(candidate_path, reproduced)

    if len({item["family"] for item in reproduced}) >= min_families:
        save_state("reproduced_candidate_found")
        return 0
    round_index = 0
    try:
        while max_rounds is None or round_index < max_rounds:
            round_dir = outdir / f"round_{round_index:03d}"
            cases = generate_round(round_index)
            summary, scored = run_and_score(cases, round_dir, require_gpu)
            round_record = {"round": round_index, "n_cases": summary["n_cases"],
                            "n_semantic_errors": summary["n_semantic_errors"],
                            "n_operational_errors": summary["n_operational_errors"],
                            "phase": summary["phase"], "metrics": summary["metrics"],
                            "dataset_sha256": sha256(round_dir / "cases.jsonl"),
                            "predictions_sha256": sha256(round_dir / "predictions.jsonl")}
            state["rounds"] = [record for record in state["rounds"] if record["round"] != round_index] + [round_record]
            state["rounds"].sort(key=lambda record: record["round"])
            append_event(outdir / "search_events.jsonl", {"event_id": f"round_{round_index:03d}_scored",
                         "kind": "round_scored", **round_record})
            print(f"Round {round_index}: {summary['n_cases']} prompts, {summary['n_semantic_errors']} semantic "
                  f"errors, {summary['n_operational_errors']} operational errors.", flush=True)
            save_state("running")
            for candidate in isolated_failure_examples(scored):
                key = (candidate["family"], candidate["pair_id"])
                if key in successful_ids:
                    continue
                result = replicate_candidate(candidate, round_dir, require_gpu)
                append_event(outdir / "search_events.jsonl", {
                    "event_id": f"candidate_{candidate['family']}_{candidate['pair_id']}",
                    "kind": "candidate_replication", "round": round_index,
                    "family": candidate["family"], "pair_id": candidate["pair_id"],
                    "reproduced": result["reproduced"]})
                if result["reproduced"]:
                    reproduced.append(result)
                    successful_ids.add(key)
                    print(f"Reproduced candidate in {candidate['family']}: {candidate['pair_id']}", flush=True)
                save_state("running")
                if len({item["family"] for item in reproduced}) >= min_families:
                    save_state("reproduced_candidate_found")
                    print(f"Stopped with {len(reproduced)} reproduced candidate(s). Review {candidate_path}", flush=True)
                    return 0
            round_index += 1
        save_state("no_reproduced_candidate_within_limit")
        print("Round limit reached with no sufficient reproduced candidates. No failure claim is made.", flush=True)
        return 2
    except KeyboardInterrupt:
        save_state("interrupted")
        raise
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        save_state("runtime_or_validation_error", str(exc))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--min-families", type=int, default=1,
                        help="Distinct families with replicated paired errors needed to stop; default 1")
    parser.add_argument("--max-rounds", type=int,
                        help="Optional limit including pilot round 0; default keeps searching until a candidate reproduces or execution is interrupted")
    parser.add_argument("--require-gpu", action="store_true")
    args = parser.parse_args()
    try:
        return search(args.outdir, args.min_families, args.max_rounds, args.require_gpu)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Search stopped: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())

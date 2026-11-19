# Clinical Model Failure Evaluation

An AI-assisted applied-research exercise using synthetic clinical notes. The source archive records Codex assistance with implementation, cloud execution, checking outputs, and drafting. This portfolio includes the evaluation harness and aggregate pilot evidence. It excludes the assessment brief, cloud account details, and original submission archive.

## Problem

An aggregate accuracy number can hide why a model fails. Evaluation needs matched examples, deterministic labels, strict scoring, and enough provenance to inspect an individual result.

## Implementation

Seven synthetic task families stress source attribution, arithmetic, unit conversion, conflicting history, negation, long context, and prompt injection. The runner checkpoints signed cases and configuration. Analysis checks completeness and reports paired differences with uncertainty estimates.

## Evidence

The saved advanced pilot records 41 semantic errors in 252 prompts and zero operational errors. Lab-unit challenges failed in 12 of 12 contexts while controls and rescues had zero errors. Two highlighted failure families were replayed twice. The aggregate pilot summary, datasets, runner, analyzer, and tests are included.

## Limits

These are related synthetic templates and exploratory failure discovery. They do not estimate clinical prevalence or prove an internal model mechanism. The rescue changed multiple inputs. The reserved confirmation phase has no reported result. Evidence-substring flags are reported separately from answer correctness.

## Run

Tests require only Python's standard library.

```sh
python3 -m unittest discover -s tests -v
```

To run inference, start Ollama with `qwen2.5:7b-instruct` on a compatible GPU machine. The original run used Q4_K_M on a Tesla T4, temperature 0, seed 42, an 8,192-token context, and a 160-token output limit.

```sh
python3 -m src.run_advanced --data data/advanced_pilot.jsonl --out results/predictions.jsonl --require-gpu
python3 -m src.analyze_advanced --data data/advanced_pilot.jsonl --pred results/predictions.jsonl --outdir results/analysis
```

`evidence/pilot-summary.json` is the saved pilot aggregate. Tests use mocked model responses and do not reproduce a GPU inference run. The included confirmation dataset is reserved evaluation material with no reported confirmation result.

## Links

- [Code, tests & evidence](https://github.com/pmeraga/portfolio/tree/main/projects/clinical-llm-evaluation)

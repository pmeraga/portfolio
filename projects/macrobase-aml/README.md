# MacroBase AML Anomaly Detection

A Python pipeline for finding unusual transactions in the synthetic SAML-D dataset and explaining alerts with overrepresented categorical attributes. It follows the MacroBase structure: score, classify, explain.

## Pipeline

1. Load transaction data and optionally sample it.
2. Engineer amount, temporal, account-velocity, and categorical features.
3. Score transactions with Isolation Forest.
4. Compare percentile thresholds from 99.95 to 98.00.
5. Extract single-attribute and attribute-pair explanations using support and risk ratios.
6. Report label-based evaluation and example alerts.

## Setup and usage

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python download_dataset.py
# Use the CSV path printed by the downloader. Start with a sample:
python pipeline.py /path/to/SAML-D.csv 0.1
# Full dataset:
python pipeline.py /path/to/SAML-D.csv 1.0
```

Dataset access uses KaggleHub and may require Kaggle authentication. The dataset is downloaded separately and is not included here. The full run can require substantial memory.

## Files

- [pipeline.py](pipeline.py): ingestion, features, scoring, thresholds, explanation, and evaluation.
- [download_dataset.py](download_dataset.py): SAML-D dataset downloader.
- [requirements.txt](requirements.txt): Python dependencies.
- [Technical write-up](TECHNICAL_WRITEUP.md): text transcription of the accompanying original write-up.
- [Original run log](pipeline_full_output.log): historical output supplied with the project archive.

## Interpreting the results

The write-up and log are historical artifacts, not independently reproduced benchmark results. The write-up contains differing sample/full-dataset figures and descriptions of precision and recovery that should be checked against the dataset labels and evaluation implementation before citing performance. The implementation generates explanations at the highest percentile threshold; its threshold comparison includes other percentiles separately.

The detector operates on individual transaction features. Graph context, higher-order itemset mining, and validation on realistic label distributions are directions for further work.

# Pranav Meraga — Engineering Portfolio

**[View the portfolio website](https://pmeraga.github.io/portfolio/)** · [Website setup and custom domain](WEBSITE.md)

Projects spanning robotics, applied AI, model evaluations, retrieval systems, and data engineering. Each project keeps its own source, dependencies, and setup instructions.

## Robotics, applied AI, and evaluation

Building [Cygnus Robotics](https://cygnus-robotics.com), with tools for robot-learning data curation and traceable frame selection. The website includes technical case studies for the projects below.

| Project | What it demonstrates | Evidence |
| --- | --- | --- |
| [Cygnus Robotics](projects/cygnus-robotics) | Building data curation tools for robot learning: inspect demonstrations, preserve recovery behavior, and trace every retained frame back to its source. | [Case study](docs/projects/cygnus-robotics.html) |
| [Multi-camera Capture & Synchronization](projects/argus-capture) | An episode collection workspace for egocentric and wrist cameras, with multipart uploads, shared playback, and automatic alignment from recorded audio. | [Case study](docs/projects/argus-capture.html) · [Sync review](https://argus-capture-46dvetz3k-yotta-robotics.vercel.app/sync-review/#9efabf4b3560140981e6d7e7f896f9bd42ba288270314be6610902f86e2023a8) |
| [Concurrent Camera Streaming Service](projects/camera-grpc) | A versioned camera API with fresh-frame reads, streaming JPEGs, health checks, and one shared latest-frame cache per camera. | [Case study](docs/projects/camera-grpc.html) |
| [Manufacturing Event Investigation](projects/factory-triage) | An investigation workspace that reconstructs production history, surfaces conflicting events, and connects job reviews to their original records. | [Case study](docs/projects/factory-triage.html) · [Live workspace](https://factory-triage-psi.vercel.app/?view=overview&status=open&sort=urgency) |
| [Biomedical AI Agent Benchmarking](projects/biomedical-agent-benchmark/) | Statistical reference analyses, deployment-matched validation, rubric audits, and paired agent-response review on biomedical data. | [Case study](docs/biomedical-agent-benchmark.html) · [Code & skills](projects/biomedical-agent-benchmark/README.md) |
| [Clinical Model Failure Evaluation](projects/clinical-llm-evaluation) | A reproducible evaluation harness that separates semantic failures from infrastructure errors and compares matched control, challenge, and rescue prompts. | [Case study](docs/projects/clinical-llm-evaluation.html) |

### Biomedical AI Agent Benchmarking — Statistical evaluation case study

Built a reproducible evaluation workflow for AI agents performing biomedical analytics: stakeholder tasks, verified reference analyses, competing baselines, source-provenance checks, rubric audits, and paired-response review. The published pain-decoder case compares a frozen forward-monitoring AUC of **0.4891** with **0.6566** under shuffled validation, showing why the prediction target matters.

Both reviewed decoder responses recovered the key result. Earlier platform scores were reported at **48% and 92%**, with neither receiving full marks in that reported pair. The historical task-version linkage remains unverified. Skills include evaluation design, biostatistics, temporal validation, cluster-aware resampling, Python/HDF5 data engineering, reproducible research, and technical communication.

[Case study and full skills matrix](projects/biomedical-agent-benchmark/README.md) · [Runnable reference](projects/biomedical-agent-benchmark/src/decoder_analysis.py) · [Evaluation record](projects/biomedical-agent-benchmark/docs/evaluation.md)
| [Real-time Ball Tracking](docs/assets/ball-tracking-demo.mp4) | Live WebRTC video, pixel-based ball detection, and timestamp-matched WebTransport coordinates. | [Video demonstration](docs/assets/ball-tracking-demo.mp4) |

## Other engineering projects

| Project | Context | What it does | Stack |
| --- | --- | --- | --- |
| [Candidate Search & Re-Ranking](projects/mercor-candidate-search/) | Assessment project | Combines dense and lexical retrieval, reciprocal rank fusion, cross-encoder re-ranking, and hard-criteria checks to find candidates for a role. | Python, Turbopuffer, Voyage AI, OpenAI |
| [Salesforce Code Intelligence](projects/sf-code-intelligence/) | Project for a **founding MLE role at a startup** | Indexes Apex and Salesforce metadata into SQLite and exposes compact, deterministic query tools for LLM agents. | Python, SQLite, XML, MCP |
| [Agentic Harness](https://github.com/pmeraga/agentic-harness) | Coding-agent evaluation | Runs coding-agent benchmarks through a queue, Docker-isolated setup/agent/grading phases, and durable results. | Python, Docker, SQLite, OpenAI Responses API |
| [Futures Backtester](projects/square-kettle-backtester/) | Software engineering assessment | Extends a supplied futures backtesting framework with data validation, exception-handling fixes, multi-strategy visualization, and tests. | Python, NautilusTrader, Databento, React, Vite |
| [ARC-AGI Agent](projects/arc-agi-agent/) | Reasoning assessment | Prompts an LLM with grid transformation examples, parses predictions, and evaluates them against 20 included puzzles. | TypeScript, Anthropic/OpenAI SDKs |
| [MacroBase AML Anomaly Detection](projects/macrobase-aml/) | AML transaction analysis project | Scores unusual transactions with Isolation Forest, applies percentile thresholds, and explains alerts using categorical support and risk ratios. | Python, pandas, scikit-learn |
| [HECTUR — Head-Eye Control and Tracking for UR7e](https://pranavmeraga.github.io/eecs106a-final-project/) | UC Berkeley EECS 106A final team project | Uses facial tracking to control a UR7e robotic arm, with ROS 2 actuation and MoveIt pose recall. | MediaPipe, ROS 2, MoveIt |

### Candidate Search & Re-Ranking

This two-stage search pipeline retrieves candidate profiles through vector ANN and native BM25, fuses the rankings, and applies cross-encoder scoring, structured criteria, and an LLM judge. The project includes role configurations, evaluation scripts, caching, and retry handling.

[Architecture and setup](projects/mercor-candidate-search/README.md) · [Pipeline](projects/mercor-candidate-search/src/pipeline.py)

The original README reports public evaluation improvements using evaluator feedback to select hard-pass candidates. These are evaluation-specific results, not a held-out benchmark. Running the system requires authorized access to the original services and namespace; credentials and cached candidate records are excluded.

### Salesforce Code Intelligence

The implementation parses Apex classes, methods, SOQL references, object fields, and lookup relationships into a dependency index. Its query layer returns compact, JSON-safe responses for agent tools, with incremental indexing, deterministic ranking, and a latency/payload benchmark harness.

[Implementation summary](projects/sf-code-intelligence/PROJECT_SUMMARY.md) · [Setup](projects/sf-code-intelligence/README.md) · [Tests](projects/sf-code-intelligence/tests/)

### Agentic Harness — Universal coding-agent evaluation

A reusable single-machine harness for evaluating coding agents against different benchmarks. The CLI queues tasks in SQLite; workers run setup, agent, and grading phases in Docker containers with a task-specific shared workspace, then retain per-task scores and logs. It includes Bash, Python, and JSONL benchmark adapters, a mini-swe-agent integration, and an optional OpenAI Responses API agent.

[Repository and setup](https://github.com/pmeraga/agentic-harness) · [Architecture and adapters](https://github.com/pmeraga/agentic-harness#architecture) · [Validation evidence](https://github.com/pmeraga/agentic-harness/blob/main/docs/validation.md)

### Backtesting and visualization

Work on a supplied backtesting assessment, including fixes for unrealized PnL exception handling, crossed-quote validation, multi-strategy visualization, custom indicators, and candlestick sizing. The folder includes the Python backend, React frontend, unit tests, example notebooks, and supplied sample data.

[Setup](projects/square-kettle-backtester/README.md) · [Developer guide](projects/square-kettle-backtester/README_DEVELOPER.md) · [Tests](projects/square-kettle-backtester/unit_test/)

### ARC-AGI — Grid reasoning agent

A TypeScript CLI and evaluation harness for ARC grid puzzles. It formats demonstration pairs into prompts, supports Anthropic and OpenAI providers, parses text or JSON grids, and compares predictions with expected outputs. No accuracy claim is made for this snapshot.

[Setup and usage](projects/arc-agi-agent/README.md) · [Agent](projects/arc-agi-agent/src/agent.ts)

### MacroBase — Explainable AML anomaly detection

An unsupervised transaction-analysis pipeline following the MacroBase scoring, classification, and explanation structure. Feature engineering includes transaction amounts, temporal features, and account velocity. The explanation layer compares categorical predicates in anomalous and baseline populations.

[Setup and limitations](projects/macrobase-aml/README.md) · [Technical write-up](projects/macrobase-aml/TECHNICAL_WRITEUP.md) · [Source](projects/macrobase-aml/pipeline.py)

### HECTUR — Robotics final project

A team-built head and eye control interface for a UR7e robotic arm. My contributions included the initial concept and prototype FaceMesh implementation, project coordination, inverse-kinematics planning, and the presentation/demo. The public report includes the system design, demonstrations, and team contributions.

[View the public project website](https://pranavmeraga.github.io/eecs106a-final-project/)

## Research and earlier engineering work

| Project | Description |
| --- | --- |
| [CNN + LSTM](CNN%2BLSTM/) | Research with Northwestern University's Wing Kam Liu Group on classifying keyhole deformations in laser powder bed fusion. |
| [NOVA ESP-IDF](NOVA_espidf/) | Embedded C code for a differential-drive robot with real-time video and obstacle avoidance. |
| [Engineering Data Analytics](CE93_project.ipynb) | Civil Engineering 93 study of access to safe water and life expectancy over time. |
| [Asteroid Clustering](K_Means_Clustering_Asteroid_Data.ipynb) | Research under the Wing Kam Liu Group using K-means to explore NASA asteroid data by collision probability and potential impact. [Northwestern publication: High-Risk Asteroid Impact Classification by Machine Learning Algorithms](https://mechanistic-data-science.mech.northwestern.edu/pranav-meraga/) (Summer 2022 report and presentation). |

## Running a project

Open its folder and follow the local README. Projects use separate Python or Node environments; there is no shared root installation. Original assessment instructions and attribution are preserved within each project.

[Repository import notes](IMPORT_NOTES.md)

# Pranav Meraga — Engineering Portfolio

**[View the portfolio website](https://pmeraga.github.io/portfolio/)** · [Website setup and custom domain](WEBSITE.md)

Projects spanning machine learning, retrieval systems, developer tools, robotics, and data engineering. Each project keeps its own source, dependencies, and setup instructions.

## Featured projects

| Project | Context | What it does | Stack |
| --- | --- | --- | --- |
| [Candidate Search & Re-Ranking](projects/mercor-candidate-search/) | Project made for **Mercor** | Combines dense and lexical retrieval, reciprocal rank fusion, cross-encoder re-ranking, and hard-criteria checks to find candidates for a role. | Python, Turbopuffer, Voyage AI, OpenAI |
| [Salesforce Code Intelligence](projects/sf-code-intelligence/) | Project for a **founding MLE role at a startup** | Indexes Apex and Salesforce metadata into SQLite and exposes compact, deterministic query tools for LLM agents. | Python, SQLite, XML, MCP |
| [Square Kettle Backtester](projects/square-kettle-backtester/) | Square Kettle software engineering take-home | Extends a supplied futures backtesting framework with data validation, exception-handling fixes, multi-strategy visualization, and tests. | Python, NautilusTrader, Databento, React, Vite |
| [ARC-AGI Agent](projects/arc-agi-agent/) | ARC interview challenge | Prompts an LLM with grid transformation examples, parses predictions, and evaluates them against 20 included puzzles. | TypeScript, Anthropic/OpenAI SDKs |
| [MacroBase AML Anomaly Detection](projects/macrobase-aml/) | AML transaction analysis project | Scores unusual transactions with Isolation Forest, applies percentile thresholds, and explains alerts using categorical support and risk ratios. | Python, pandas, scikit-learn |
| [HECTUR — Head-Eye Control and Tracking for UR7e](https://pranavmeraga.github.io/eecs106a-final-project/) | UC Berkeley EECS 106A final team project | Uses facial tracking to control a UR7e robotic arm, with ROS 2 actuation and MoveIt pose recall. | MediaPipe, ROS 2, MoveIt |

### Candidate Search & Re-Ranking — Mercor

Built for Mercor, this two-stage search pipeline retrieves candidate profiles through vector ANN and native BM25, fuses the rankings, and applies cross-encoder scoring, structured criteria, and an LLM judge. The project includes role configurations, evaluation scripts, caching, and retry handling.

[Architecture and setup](projects/mercor-candidate-search/README.md) · [Pipeline](projects/mercor-candidate-search/src/pipeline.py)

The original README reports public evaluation improvements using evaluator feedback to select hard-pass candidates. These are evaluation-specific results, not a held-out benchmark. Running the system requires authorized access to the original services and namespace; credentials and cached candidate records are excluded.

### Salesforce Code Intelligence — Founding MLE project

Built for a founding machine learning engineer role at a startup. The implementation parses Apex classes, methods, SOQL references, object fields, and lookup relationships into a dependency index. Its query layer returns compact, JSON-safe responses for agent tools, with incremental indexing, deterministic ranking, and a latency/payload benchmark harness.

[Implementation summary](projects/sf-code-intelligence/PROJECT_SUMMARY.md) · [Setup](projects/sf-code-intelligence/README.md) · [Tests](projects/sf-code-intelligence/tests/)

### Square Kettle — Backtesting and visualization

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

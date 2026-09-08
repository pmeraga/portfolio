# sf-code-intelligence

**Portfolio context:** This project was completed for a founding MLE role at a startup. See [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) for the implemented functionality, tests, and benchmark harness. The original assessment brief follows.

## Overview

You're building a code intelligence index over a Salesforce project. The goal is to parse
real Apex and Object metadata, store structured facts in SQLite, and expose query tools
that an LLM agent could use to navigate the codebase.

## The Codebase

The fixture files are committed directly in this repository under `fixtures/`.
They include `Property__c`, `Broker__c`, and `Listing__c` object metadata plus Apex
classes wired with `@AuraEnabled`. `Listing__c` embeds field metadata including a
lookup to `Broker__c`, and `ListingService.cls` makes lookup edges and
SOQL-to-object edges explicit in tests.

## Setup

```bash
bash setup.sh
source .venv/bin/activate
```

This installs dependencies. Fixture files are already included in `fixtures/`.

## What to implement

Two modules: `src/sf_code_intelligence/indexer.py` and `src/sf_code_intelligence/query.py`. Every function has a docstring describing what it
should do. Read the fixture files before you start — they're the ground truth.

Do not modify `src/sf_code_intelligence/server.py`, `src/sf_code_intelligence/db.py`, `src/sf_code_intelligence/schema.sql`, or `src/sf_code_intelligence/run_indexer.py`.

## Running your indexer

```bash
python -m sf_code_intelligence.run_indexer ./fixtures
```

## Running tests

```bash
pytest tests/
```

## Linting

```bash
ruff check src tests
ruff format src tests
```

## Running the MCP server

```bash
python -m sf_code_intelligence.server
```

## Make targets

```bash
make db      # initialize index.db
make server  # run MCP server
make up      # initialize DB, then run server
```

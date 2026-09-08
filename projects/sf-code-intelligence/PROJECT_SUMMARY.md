# sf-code-intelligence Project Summary

## Overview

This project now has a working Salesforce code-intelligence pipeline that indexes Apex and metadata fixtures into SQLite, exposes deterministic query functions, and includes tests plus a benchmark harness for latency/token-size visibility.

## What We Implemented

### 1) Indexer (`src/sf_code_intelligence/indexer.py`)

- Implemented `index_apex_class()`:
  - Parses Apex class name and sharing model.
  - Extracts methods with:
    - method name
    - return type
    - annotations
    - `is_static`
  - Extracts SOQL `FROM` references and creates `queries` edges.
  - Supports incremental re-indexing by replacing method rows and class query edges per class.

- Implemented `index_object()`:
  - Parses `.object-meta.xml` files with namespace-aware XML parsing.
  - Indexes object metadata into `sobjects`.
  - Indexes object fields into `sobject_fields`.
  - Creates `lookup_to` edges for reference fields.
  - Supports incremental re-indexing by replacing field rows and lookup edges per object.

- Implemented `build_dependency_edges()`:
  - Deduplicates duplicate edges deterministically.
  - Backfills missing object fields from SOQL `SELECT ... FROM ...` usage in Apex files for sparse fixtures.

### 2) Query Layer (`src/sf_code_intelligence/query.py`)

- Implemented `search_symbol(name, conn)`:
  - Case-insensitive search for classes/methods.
  - Deterministic exact-first ordering.
  - Compact JSON-safe shape for LLM-facing output.

- Implemented `get_object_schema(object_name, conn)`:
  - Returns object name, label, field summaries, and relationship count.
  - Returns `{ "error": "not found" }` for missing objects.

- Implemented `find_apex_touching_object(object_name, conn)`:
  - Returns classes referencing an SObject through edges.
  - Includes Aura-enabled methods per class.
  - Optimized to avoid N+1 lookups by batching method retrieval.
  - Uses deduplicated class/edge output.

- Implemented `get_class_summary(class_name, conn)`:
  - Returns sharing model, methods, queried objects, Aura/Invocable counts.
  - Returns `{ "error": "not found" }` for missing classes.

### 3) Benchmark Harness (`src/sf_code_intelligence/benchmark.py`)

- Added a lightweight benchmark runner that:
  - Builds index from fixtures.
  - Benchmarks core query functions.
  - Reports latency stats (`min`, `p50`, `p95`, `max`, `mean`).
  - Reports payload bytes and estimated tokens for response-size budgeting.

- Added `bench` target in `Makefile`:
  - `make bench`

## Testing and Stability Improvements

- Expanded query tests with edge-focused coverage for:
  - blank search behavior
  - exact class ranking behavior
  - duplicate edge deduplication
  - not-found behavior
  - token-efficiency guardrail on payload size

- Fixed flaky DB behavior in tests:
  - Ensured test fixtures update `db.DB_PATH` directly (not only env var), so each test uses an isolated sqlite file.
  - Added explicit connection teardown (`yield` fixture + `close()`).
  - Prevented unique-constraint collision in one seed insert test path.

## Current Status

- Full suite passes:
  - `pytest tests/` -> **21 passed**
- Lint diagnostics on touched files are clean.
- Benchmark runner executes successfully and reports stable, low-latency query behavior on fixtures.

## Design Direction Achieved

- Fixture-optimized implementation, with a path for future resilience.
- Deterministic exact-first retrieval behavior for query/inference workflows.
- Standard object references preserved in indexing graph.
- Incremental indexing behavior supported without schema changes.
- Token-efficient response design prioritized for LLM tool usage.

## Recommended Next Steps

1. Add synthetic scale tests (many classes/methods/edges) to stress latency and payload growth.
2. Add optional query modes (e.g., compact vs expanded) at tool/API layer while keeping DB schema stable.
3. Consider parser hardening (Tree-sitter/ANTLR-based Apex parsing) when fixture scope expands.
4. Add benchmark thresholds in CI to catch inference-speed regressions early.

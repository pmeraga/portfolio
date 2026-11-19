# Manufacturing Event Investigation

This case study describes a manufacturing-log application. The full source is maintained separately at https://github.com/pmeraga/factory-triage. Source data is synthetic. The live deployment requires sign-in.

## Problem

A raw event log mixes production state, machine readings, duplicate messages, and conflicting revisions. Reviewers need to reconstruct what was known at a chosen time and trace the evidence behind each exception.

## Implementation

Normalization retains conflicting variants and source references. Replay rebuilds job state at the selected cursor. The UI joins machine telemetry, searchable events, job comparisons, and role-scoped review workflows with database-backed notes and optimistic concurrency checks.

## Evidence

The project README documents a synthetic log with 19,519 rows across 312 jobs. The local version includes tests for replay boundaries, Pacific-time windows, authorization, assignments, and concurrent review updates. The linked public source is a separate repository.

## Limits

Waiting time and descriptive review signals do not establish downtime, utilization, financial savings, or a causal diagnosis. The public deployment requires sign-in. Current local collaboration changes may be newer than the public repository.

## Links

- [Application](https://factory-triage-psi.vercel.app)
- [Public source](https://github.com/pmeraga/factory-triage)

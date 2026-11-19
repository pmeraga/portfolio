# Evaluation record

## What was evaluated

The project series iterated through oncology study-completion feasibility, forecasting, target-mixture transport, ICU competing-risk yields, repeated-measure trial planning, new-registry precision assurance, and forward pain-decoder validation. Each candidate was checked against source limitations and a runnable statistical reference before interpreting agent responses.

The published decoder task asks an agent to make one technical qualification decision and deliver a decision-first PDF plus an offline analysis script. The proposed rubric has 12 criteria totaling 100 points. Sixty-five points cover the deployment target, correct decision, calibration-only fitting and observation hierarchy. Remaining criteria cover the comparator, uncertainty, sparse class support, sensitivity, scope and requested artifacts. This is an author proposal, not an exported platform rubric.

## Observed outcomes and evidence levels

| Evidence | Finding | Limit |
| --- | --- | --- |
| Earlier reported platform pair | Scores of 48% and 92% | Reported historical scores; exact prompt/rubric association unresolved |
| Decoder reference implementation | Forward mean AUC 0.4891; random comparison 0.6566 | Fixed workflow, five-person finite-panel research replay |
| Two decoder response narratives | Both recover approximately 0.489 and recommend recalibration; both discuss the intended statistical issues | Generated files and platform grades were unavailable for independent checking |
| Independent numerical checks | Per-side AUC agrees with a rank-sum calculation; LDA scores agree with scikit-learn; weighted AUC checked with ties | These verify the calculation, not physiological validity or new-patient performance |

No universal “all agents failed,” “no model ever reached 100%,” or perfect-accuracy claim is supported. A correct recommendation alone is also not a numerical grade. In the decoder pair, the substantive supporting reasoning was correct as well.

## Review principles

1. Freeze the prompt, candidate definition and grading expectations before evaluating responses.
2. Check whether the chosen statistical target matches the stakeholder decision.
3. Credit justified alternatives in priors, uncertainty methods, fold aggregation, sensitivity choices and numerical precision.
4. Check generated artifacts directly when available; distinguish an execution check from a narrative claim.
5. Audit task/rubric version alignment. An inherited rubric was found to combine ICU, oncology and precision-planning requirements; it could not fairly grade one task.
6. Record a successful agent analysis as such. Changing criterion weights after seeing the responses cannot establish a statistical reasoning error.

## Why this is useful beyond a leaderboard

The deliverable exposes failure modes that ordinary answer matching misses: validation on the wrong time distribution, calibration with future information, treating repeated measurements as independent people, and silently conditioning uncertainty on class-complete resamples. It also demonstrates how to avoid overclaiming a model failure when the model gives a scientifically valid alternative analysis.

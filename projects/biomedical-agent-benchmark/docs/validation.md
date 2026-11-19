# Validation of the public deliverable

Checked November 18, 2026. [Exact environment](../reference/verification_environment.json).

- Verified the original Dryad ZIP's byte count and SHA-256; checked CRC integrity and the ten source-member hashes.
- Executed the committed analysis CLI against that original archive, including the default 2,000 time-block resamples per block length. The qualification decision, aggregate AUCs, clinical support, source accounting, sensitivities and resampling diagnostics match the reference.
- Ran four unit checks: weighted AUC with tied scores/zero weights; class-undefined AUC; selected univariate LDA versus scikit-learn; rejection of a result file that substitutes the random-validation score for the deployment estimate.
- Ran Ruff lint/format checks and Git whitespace checks.
- Inspected the portfolio card, case-study page, chart and skills section in a browser; checked the page for desktop horizontal overflow and the new figure for successful loading.
- Reviewed public packaging to exclude clinical source records, generated participant predictions, full model-response transcripts, private conversations, credentials and machine-specific paths.

These checks verify the reference implementation and presentation. They do not independently reproduce historical platform grading or establish physiological/device validity. See the [evaluation record](evaluation.md) for the separate evidence levels of reported grades, response narratives and executable analysis.

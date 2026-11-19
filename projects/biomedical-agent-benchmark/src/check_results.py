"""Compare aggregate replay results with the committed reference evidence."""

import argparse
import json
from pathlib import Path
import math


def check(actual_path, reference_path=None):
    reference_path = (
        reference_path or Path(__file__).parents[1] / "reference/expected_results.json"
    )
    actual = json.loads(Path(actual_path).read_text())
    expected = json.loads(Path(reference_path).read_text())
    for key in ("forward_auc", "iid_auc"):
        got = actual["primary"]["macro"][key]
        want = expected["primary"]["macro"][key]
        if not math.isclose(got, want, abs_tol=1e-8):
            raise ValueError(f"{key}: expected {want}, got {got}")
    if actual["distinct_monitoring_support"] != expected["distinct_monitoring_support"]:
        raise ValueError("Distinct clinical support does not match the reference")
    if actual["source_audit"] != expected["source_audit"]:
        raise ValueError("Source observation accounting differs")
    for name, case in expected["sensitivities"].items():
        got = actual["sensitivities"][name]["macro"]["forward_auc"]
        if not math.isclose(got, case["macro"]["forward_auc"], abs_tol=1e-8):
            raise ValueError(f"Sensitivity mismatch: {name}")
    if actual["recommendation"] != expected["recommendation"]:
        raise ValueError("Qualification decision differs")
    # Bootstrap diagnostics are optional; never conceal undefined replicates.
    if actual.get("temporal_block_uncertainty"):
        for label, case in actual["temporal_block_uncertainty"].items():
            if not 0 <= case["complete_class_support"] <= case["resamples"]:
                raise ValueError(f"Invalid class-support accounting: {label}")
            if case["resamples"] == 2000:
                want = expected["temporal_block_uncertainty"][label]
                if case["complete_class_support"] != want["complete_class_support"]:
                    raise ValueError(f"Class-support mismatch: {label}")
                if not all(
                    math.isclose(a, b, abs_tol=1e-8)
                    for a, b in zip(
                        case["conditional_interval"], want["conditional_interval"]
                    )
                ):
                    raise ValueError(f"Conditional interval mismatch: {label}")
    return {
        "verified": True,
        "forward_auc": actual["primary"]["macro"]["forward_auc"],
        "random_cv_auc": actual["primary"]["macro"]["iid_auc"],
        "bootstrap_checked": bool(actual.get("temporal_block_uncertainty")),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis_json", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.analysis_json), indent=2))

"""Algebraic fixtures test inference code; these are not clinical source records."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from decoder_analysis import weighted_auc, fit_band
from check_results import check


class StatisticalChecks(unittest.TestCase):
    def test_weighted_auc_ties_and_zero_weights(self):
        y = np.array([0, 0, 1, 1, 0, 1])
        scores = np.array([0.0, 1.0, 1.0, 2.0, 2.0, 2.0])
        weights = np.array([1.0, 0.0, 2.0, 1.0, 3.0, 2.0])
        self.assertAlmostEqual(
            weighted_auc(y, scores, weights),
            roc_auc_score(y, scores, sample_weight=weights),
            places=14,
        )

    def test_auc_without_required_class_is_undefined(self):
        self.assertTrue(
            np.isnan(
                weighted_auc(
                    np.array([0, 1]), np.array([0.0, 1.0]), np.array([1.0, 0.0])
                )
            )
        )

    def test_selected_lda_agrees_with_independent_library(self):
        x = np.array(
            [[1.0, 3.0], [2.0, 1.0], [3.0, 4.0], [5.0, 4.0], [6.0, 2.0], [8.0, 5.0]]
        )
        y = np.array([False, False, False, True, True, True])
        j, coefficient, intercept, _, _ = fit_band(x, y)
        independent = LinearDiscriminantAnalysis().fit(x[:, j : j + 1], y)
        np.testing.assert_allclose(
            coefficient * x[:, j] + intercept,
            independent.decision_function(x[:, j : j + 1]),
            atol=1e-12,
        )

    def test_result_check_rejects_wrong_target(self):
        ref = Path(__file__).parents[1] / "reference/expected_results.json"
        result = json.loads(ref.read_text())
        result["primary"]["macro"]["forward_auc"] = result["primary"]["macro"][
            "iid_auc"
        ]
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "analysis.json"
            p.write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError, "forward_auc"):
                check(p)


if __name__ == "__main__":
    unittest.main()

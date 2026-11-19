"""Analysis safeguards use injected test outputs, never claimed model results."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from src.analyze_advanced import (bootstrap_paired_ci, evidence_grounded, exact_mcnemar,
                                  isolated_failure_examples, summarize, write_outputs)


def fixtures(answer_type="boolean"):
    cases = []
    for i in range(4):
        for variant in ("control", "challenge", "rescue"):
            cases.append({"id": f"pilot-{i}-{variant}", "pair_id": f"pilot-{i}",
                          "phase": "advanced_pilot", "family": "test_family", "variant": variant,
                          "note": "Final record: target medication stopped.", "question": "Test question?",
                          "gold": False if answer_type == "boolean" else 75.0,
                          "answer_type": answer_type, "provenance": "test fixture only"})
    preds = [{**c, "answer": c["gold"], "evidence": "target medication stopped.",
              "raw_response": "TEST FIXTURE ONLY", "error": None,
              "model": "test", "model_digest": "test-digest"} for c in cases]
    return cases, preds


class TestAdvancedAnalysis(unittest.TestCase):
    def test_complete_perfect_run_is_null_with_nonzero_wilson_upper_bound(self):
        cases, preds = fixtures()
        summary, scored = summarize(cases, preds)
        self.assertEqual(summary["n_errors"], 0)
        self.assertTrue(all(m["ci95_high"] > 0 for m in summary["metrics"]))
        self.assertTrue(all(c["bootstrap_degenerate"] for c in summary["contrasts"]))
        self.assertEqual(isolated_failure_examples(scored), [])
        self.assertNotIn("correct", preds[0])

    def test_reject_missing_extra_duplicate_and_mismatched_predictions(self):
        cases, preds = fixtures()
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            summarize(cases, preds[:-1])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            summarize(cases, preds + [preds[0]])
        mismatch = copy.deepcopy(preds)
        mismatch[0]["note"] = "altered"
        with self.assertRaisesRegex(ValueError, "mismatched field note"):
            summarize(cases, mismatch)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            summarize(cases + [cases[0]], preds)

    def test_exact_pair_structure_required_even_with_complete_predictions(self):
        cases, preds = fixtures()
        with self.assertRaisesRegex(ValueError, "Unmatched pair"):
            summarize(cases[:-1], preds[:-1])

    def test_boolean_and_numeric_types_are_not_interchangeable(self):
        cases, preds = fixtures()
        preds[0]["answer"] = 0
        summary, scored = summarize(cases, preds)
        self.assertEqual(summary["n_operational_errors"], 1)
        self.assertEqual(summary["n_semantic_errors"], 0)
        cases, preds = fixtures("number")
        preds[0]["answer"] = True
        preds[1]["answer"] = 75.0000005
        preds[2]["answer"] = 76.0
        summary, _ = summarize(cases, preds)
        self.assertEqual(summary["n_operational_errors"], 1)
        self.assertEqual(summary["n_semantic_errors"], 1)

    def test_api_error_and_missing_evidence_are_operational(self):
        cases, preds = fixtures()
        preds[0]["error"] = "Connection failed"
        preds[1]["evidence"] = ""
        preds[2]["answer"] = "false"
        summary, scored = summarize(cases, preds)
        self.assertEqual(summary["n_operational_errors"], 3)
        self.assertEqual(summary["n_semantic_errors"], 0)
        self.assertEqual(isolated_failure_examples(scored), [])

    def test_evidence_quote_wrappers_only_and_separate_from_accuracy(self):
        note = "Allergy: PCN caused hives."
        self.assertTrue(evidence_grounded(note, '"PCN caused hives."'))
        self.assertTrue(evidence_grounded(note, '“PCN caused hives.”'))
        self.assertFalse(evidence_grounded(note, "PCN caused anaphylaxis."))
        self.assertFalse(evidence_grounded(note, "pcn caused hives."))
        cases, preds = fixtures()
        preds[0]["evidence"] = "unobserved evidence"
        summary, _ = summarize(cases, preds)
        self.assertEqual(summary["n_errors"], 0)
        self.assertEqual(summary["n_ungrounded_evidence"], 1)

    def test_injected_failure_requires_correct_control_and_rescue(self):
        cases, preds = fixtures()
        preds[1]["answer"] = True
        preds[4]["answer"] = True
        preds[5]["answer"] = True
        summary, scored = summarize(cases, preds)
        examples = isolated_failure_examples(scored)
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0]["pair_id"], "pilot-0")
        self.assertEqual(set(examples[0]["variants"]), {"control", "challenge", "rescue"})
        self.assertEqual(summary["contrasts"][0]["challenge_only_errors"], 2)

    def test_mixed_phase_and_model_are_rejected(self):
        cases, preds = fixtures()
        cases[0]["phase"] = preds[0]["phase"] = "advanced_confirm"
        with self.assertRaisesRegex(ValueError, "mix pilot"):
            summarize(cases, preds)
        cases, preds = fixtures()
        preds[0]["model_digest"] = "different"
        with self.assertRaisesRegex(ValueError, "Mixed model"):
            summarize(cases, preds)

    def test_statistics_and_artifact_output(self):
        self.assertEqual(bootstrap_paired_ci([(True, False)] * 4), (1., 1.))
        self.assertEqual(exact_mcnemar([(True, False)] * 4)["p_exact"], .125)
        cases, preds = fixtures()
        summary, scored = summarize(cases, preds)
        with tempfile.TemporaryDirectory() as directory:
            write_outputs(summary, scored, directory)
            out = Path(directory)
            self.assertEqual(json.loads((out / "isolated_failure_examples.json").read_text()), [])
            self.assertEqual((out / "errors.jsonl").read_text(), "")
            self.assertIn("does not establish equivalence", (out / "RESULTS_TABLE.md").read_text())
            self.assertIn("<svg", (out / "figure.svg").read_text())


if __name__ == "__main__":
    unittest.main()

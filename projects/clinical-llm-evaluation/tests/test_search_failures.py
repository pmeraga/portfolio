"""The search controller is tested with temporary mock outputs, never Qwen results."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src import search_failures as controller


def cases(round_index):
    return [{"id": f"round{round_index}-{variant}", "pair_id": f"round{round_index}",
             "phase": f"test_round_{round_index}", "family": "mock_family",
             "variant": variant, "note": "Target patient explicitly denies the allergy.",
             "question": "Is the allergy documented?", "gold": False,
             "answer_type": "boolean", "provenance": "test fixture only"}
            for variant in ("control", "challenge", "rescue")]


def mock_engine(failing_round=None, fail_repeats=True, operational=False, api_calls=None):
    def run(data, pred, require_gpu):
        # Real runner's resumability is independently tested. This stub imitates it.
        if pred.exists():
            return
        if api_calls is not None:
            api_calls.append(str(pred))
        repeat = 'repeat_' in str(pred)
        output = []
        for case in controller.read_jsonl(data):
            wrong = (case['phase'] == f'test_round_{failing_round}' and case['variant'] == 'challenge'
                     and (not repeat or fail_repeats))
            output.append({**case, 'answer': None if operational else (not case['gold'] if wrong else case['gold']),
                           'evidence': 'explicitly denies the allergy.', 'error':'mock API failure' if operational else None,
                           'model':'mock-test-only','model_digest':'mock-test-only','raw_response':'MOCK TEST ONLY'})
        pred.write_text(''.join(json.dumps(row)+'\n' for row in output))
    return run


class TestSearchFailures(unittest.TestCase):
    def run_search(self, root, engine, **kwargs):
        with patch.object(controller, 'generate_round', side_effect=cases), patch.object(
                controller, 'execute_inference', side_effect=engine):
            return controller.search(root, **kwargs)

    def test_null_round_retained_then_paired_error_repeats_and_stops(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = self.run_search(root, mock_engine(1, api_calls=calls), max_rounds=3, require_gpu=True)
            self.assertEqual(code, 0)
            result = json.loads((root/'REPRODUCED_CANDIDATES.json').read_text())
            self.assertEqual(len(result), 1)
            self.assertEqual(len(result[0]['runs']), 3)
            self.assertTrue(result[0]['reproduced'])
            state = json.loads((root/'search_state.json').read_text())
            self.assertEqual([row['round'] for row in state['rounds']], [0,1])
            self.assertEqual(state['rounds'][0]['n_semantic_errors'], 0)
            self.assertTrue((root/'round_000/predictions.jsonl').is_file())
            self.assertEqual(len(calls), 4)
            self.assertEqual(self.run_search(root, mock_engine(1, api_calls=calls), max_rounds=3, require_gpu=True), 0)
            self.assertEqual(len(calls), 4)

    def test_nonreproducing_candidate_is_not_a_finding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(self.run_search(root, mock_engine(0, fail_repeats=False), max_rounds=2), 2)
            self.assertEqual(json.loads((root/'REPRODUCED_CANDIDATES.json').read_text()), [])
            state = json.loads((root/'search_state.json').read_text())
            self.assertEqual(state['status'], 'no_reproduced_candidate_within_limit')
            events = controller.read_jsonl(root/'search_events.jsonl')
            self.assertTrue(any(row['kind']=='candidate_replication' and not row['reproduced'] for row in events))

    def test_api_failures_stop_runtime_and_do_not_count_as_semantic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(RuntimeError, 'Operational errors'):
                self.run_search(root, mock_engine(operational=True), max_rounds=3)
            summary = json.loads((root/'round_000/analysis/summary.json').read_text())
            self.assertEqual(summary['n_semantic_errors'], 0)
            self.assertEqual(summary['n_operational_errors'], 3)
            self.assertEqual(json.loads((root/'REPRODUCED_CANDIDATES.json').read_text()), [])
            self.assertEqual(json.loads((root/'search_state.json').read_text())['status'], 'runtime_or_validation_error')

    def test_frozen_dataset_and_configuration_changes_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(self.run_search(root, mock_engine(), max_rounds=1), 2)
            with self.assertRaisesRegex(ValueError, 'Frozen input changed'):
                self.run_search(root, mock_engine(), max_rounds=1, min_families=2)
            (root/'round_000/cases.jsonl').write_text('tampered input')
            with self.assertRaisesRegex(ValueError, 'Frozen input changed'):
                self.run_search(root, mock_engine(), max_rounds=1)

    def test_resume_null_search_does_not_duplicate_events_or_predictions(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for _ in range(2):
                self.assertEqual(self.run_search(root, mock_engine(api_calls=calls), max_rounds=2), 2)
            self.assertEqual(len(calls), 2)
            self.assertEqual(len(controller.read_jsonl(root/'search_events.jsonl')), 2)


if __name__ == '__main__':
    unittest.main()

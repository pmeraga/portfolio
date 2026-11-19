import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from src import run_advanced
from src.analyze_advanced import summarize
from src.generate_advanced import generate
from src.run_advanced import parse_answer, signature, validate_prior


class TestAdvancedRunner(unittest.TestCase):
    def test_strict_numeric_and_boolean_schema(self):
        self.assertEqual(parse_answer('{"answer":true,"evidence":"denies"}', 'boolean'), (True, 'denies'))
        self.assertEqual(parse_answer('{"answer":2250,"evidence":"750 mg three times"}', 'number')[0], 2250)
        for raw, kind in [('{"answer":1,"evidence":"x"}', 'boolean'),
                          ('{"answer":true,"evidence":"x"}', 'number'),
                          ('{"answer":NaN,"evidence":"x"}', 'number'),
                          ('{"answer":3,"evidence":""}', 'number'),
                          ('{"answer":3,"evidence":"x","extra":1}', 'number')]:
            self.assertEqual(parse_answer(raw, kind), (None, None))

    def test_resume_rejects_changed_options_and_duplicate_ids(self):
        case = {"id":"test", "answer_type":"number", "note":"Scheduled 1 mg", "gold":1}
        config = {"model":"test", "options":{"num_ctx":8192}}
        record = {**case, "input_signature":signature(case, config)}
        self.assertEqual(len(validate_prior([record], [case], config)), 1)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            validate_prior([record, record], [case], config)
        changed = copy.deepcopy(config)
        changed['options']['num_ctx'] = 4096
        with self.assertRaisesRegex(ValueError, 'Changed'):
            validate_prior([record], [case], changed)

    def test_mock_server_checkpoint_resume_and_score_complete_triplets(self):
        # A mocked API verifies the complete pipeline; these are never empirical predictions.
        cases = [c for c in generate('advanced_pilot', 2) if c['family'] == 'dose_arithmetic']
        note_gold = {c['note']: c['gold'] for c in cases}
        seen_prompts = []

        def fake_request(url, payload=None, timeout=240):
            if url.endswith('/api/tags'):
                return {'models':[{'name':run_advanced.MODEL, 'digest':run_advanced.DIGEST}]}
            if url.endswith('/api/ps'):
                return {'models':[{'digest':run_advanced.DIGEST, 'size_vram':5_000_000_000}]}
            if url.endswith('/api/version'):
                return {'version':'mock-test-only'}
            if len(payload['messages']) == 1:
                return {'done':True, 'message':{'content':'OK'}}
            prompt = payload['messages'][1]['content']
            self.assertNotIn('gold', prompt)
            note = prompt.split('SYNTHETIC NOTE:\n', 1)[1].split('\n\nQUESTION:\n', 1)[0]
            seen_prompts.append(note)
            return {'done':True, 'done_reason':'stop', 'message':{'content':json.dumps(
                {'answer':note_gold[note], 'evidence':note.splitlines()[1]})}}

        with tempfile.TemporaryDirectory() as directory:
            data, out = Path(directory)/'data.jsonl', Path(directory)/'pred.jsonl'
            data.write_text(''.join(json.dumps(c)+'\n' for c in cases))
            base = ['run_advanced', '--data', str(data), '--out', str(out), '--require-gpu']
            with patch.object(run_advanced, 'request_json', side_effect=fake_request), patch.object(
                    run_advanced, 'command_output', return_value='mock-test-only'):
                with patch.object(sys, 'argv', base + ['--limit','3']):
                    run_advanced.main()
                self.assertEqual(len(out.read_text().splitlines()), 3)
                with patch.object(sys, 'argv', base):
                    run_advanced.main()
                self.assertEqual(len(seen_prompts), len(cases))
                with patch.object(sys, 'argv', base):
                    run_advanced.main()
                self.assertEqual(len(seen_prompts), len(cases))
            summary, _ = summarize(cases, run_advanced.load_records(out))
            self.assertEqual(summary['n_cases'], 6)
            self.assertEqual(summary['n_errors'], 0)


if __name__ == '__main__':
    unittest.main()

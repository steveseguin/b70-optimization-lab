"""Exercise native/control mapping and stale-response refusal without a service."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('capture', Path(__file__).with_name('run_depth_probe_suite.py'))
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.control = self.root / 'control'
        self.ranks = self.control / 'ranks'
        self.ranks.mkdir(parents=True)
        self.current = self.root / 'current'
        self.current.symlink_to(self.control, target_is_directory=True)
        self.evidence = self.root / 'runtime'
        (self.evidence / 'req-000005/rank0').mkdir(parents=True)
        self.plan = {'output': str(self.ranks), 'evidence_output': str(self.evidence), 'mini': False,
                     'binary_sha256': 'a' * 64, 'environment': [dict(CAPTURE.EXPECTED), dict(CAPTURE.EXPECTED)]}
        self.write_plan()
        self.row = {'prompt_id': 'test-prompt', 'prompt_tokens': 2, 'output_tokens': 2,
                    'prompt_token_ids': [10, 11], 'output_token_ids': [12, 13], 'cached_tokens': 0}
        self.response = {'ownrt': {'request': 5, 'prompt_tokens': 2, 'output_tokens': 2}}
        self.log = {'request': 5, 'prompt_tokens': 2, 'output_tokens': 2, 'continued_from': 0}
        (self.control / 'requests.jsonl').write_text(json.dumps(self.log) + '\n')
        (self.ranks / 'native-request.txt').write_text('3 512 1 0 2 0 1 10 11 99 prefill 32\n')
        self.native = json.dumps({'tokens': [12, 13], 'draft_rows': [{'position': 2}]})
        (self.ranks / 'native-result.json').write_text(self.native)
        (self.evidence / 'rank0').mkdir()
        self.probe_row = {'request_output': str(self.evidence / 'req-000005/rank0'), 'depth': 3}
        (self.evidence / 'rank0/draft-depth-probe.jsonl').write_text(
            json.dumps({'request_output': 'earlier-request'}) + '\n' + json.dumps(self.probe_row) + '\n')

    def write_plan(self):
        (self.control / 'plan.json').write_text(json.dumps(self.plan))

    def test_control_native_result_saved_with_current_request_probe(self):
        dest = self.root / 'retained'
        capture = CAPTURE.Capture(dest, self.current)
        capture(self.row, self.response)
        self.assertEqual((dest / 'test-prompt/rank0/native-result.json').read_text(), self.native)
        saved = json.loads((dest / 'test-prompt/capture.json').read_text())
        self.assertEqual(saved['native_result_source'], str(self.ranks / 'native-result.json'))
        self.assertEqual(saved['request'], 5)
        self.assertFalse(saved['probe_complete'])
        self.assertEqual(json.loads((dest / 'test-prompt/rank0/draft-depth-probe-partial.jsonl').read_text()), self.probe_row)
        self.assertEqual(json.loads((dest / 'test-prompt/prompt-token-ids.json').read_text()), [10, 11])

    def test_latest_request_must_match_http(self):
        capture = CAPTURE.Capture(self.root / 'retained', self.current)
        self.response['ownrt']['request'] = 4
        with self.assertRaisesRegex(ValueError, 'request identity mismatch'):
            capture(self.row, self.response)
        self.assertFalse((self.root / 'retained/test-prompt').exists())

    def test_probe_flags_must_be_explicit(self):
        del self.plan['environment'][0]['OWNRT_EARLY_RANK1']
        self.write_plan()
        with self.assertRaisesRegex(ValueError, 'explicit depth-probe flags'):
            CAPTURE.Capture(self.root / 'retained', self.current)

    def test_native_prompt_mismatch_refused(self):
        capture = CAPTURE.Capture(self.root / 'retained', self.current)
        self.row['prompt_token_ids'] = [10, 21]
        with self.assertRaisesRegex(ValueError, 'native prompt ids differ'):
            capture(self.row, self.response)


if __name__ == '__main__':
    unittest.main()

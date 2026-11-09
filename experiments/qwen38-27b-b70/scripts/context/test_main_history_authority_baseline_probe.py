"""Focused CPU tests for C68's exact upstream-only suffix ablation."""
import copy
import json
from pathlib import Path
import shutil
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import main_history_authority_baseline_probe as p
import test_main_history_authority_probe as original_tests


class BaselineTests(unittest.TestCase):
    setUp = original_tests.AuthorityTests.setUp
    tearDown = original_tests.AuthorityTests.tearDown

    def fixture(self):
        source = self.folder / 'c67'
        source.mkdir()
        for path in list(self.folder.iterdir()):
            if path != source:
                shutil.move(str(path), str(source / path.name))
        p.dump(source / 'cpu-capture.json', p.prior.captures(source))
        return self.folder

    def test_exact_inverse_all_three_arms_and_original_fields(self):
        folder = self.fixture()
        before = {str(x): p.sha(x) for x in (folder / 'c67').rglob('*') if x.is_file()}
        captured = p.captures(folder)
        original = p.load(folder / 'c67/cpu-capture.json')
        self.assertEqual([len(captured[a]['messages']) for a in p.ARMS], [12, 14, 12])
        for arm in p.ARMS:
            restored = copy.deepcopy(captured[arm])
            restored['messages'][0]['content'] += p.CONTRACT
            self.assertEqual(restored, original[arm])
            self.assertEqual(captured[arm]['tools'], original[arm]['tools'])
            self.assertNotIn(p.CONTRACT, json.dumps(captured[arm]))
            self.assertEqual(captured[arm]['max_completion_tokens'], 16384)
            self.assertNotIn('temperature', captured[arm])
        after = {str(x): p.sha(x) for x in (folder / 'c67').rglob('*') if x.is_file()}
        self.assertEqual(before, after)

    def test_remove_suffix_rejects_missing_duplicate_wrong_role_or_position(self):
        valid = {'messages': [{'role': 'system', 'content': 'original' + p.CONTRACT}], 'tools': ['unchanged']}
        self.assertEqual(p.remove_suffix(valid)['messages'][0]['content'], 'original')
        for content in ('original', 'original' + p.CONTRACT + 'tail', p.CONTRACT + p.CONTRACT):
            with self.assertRaises(ValueError):
                p.remove_suffix({'messages': [{'role': 'system', 'content': content}]})
        with self.assertRaises(ValueError):
            p.remove_suffix({'messages': [{'role': 'user', 'content': p.CONTRACT}]})
        self.assertEqual(valid['messages'][0]['content'], 'original' + p.CONTRACT)

    def test_every_recall_request_inverse_and_traces(self):
        folder = self.fixture()
        replies = [original_tests.response(original_tests.tool('recall', {'message': 444})), original_tests.terminal()]
        seen = []
        def ask(request):
            seen.append(copy.deepcopy(request))
            return replies.pop(0)
        row = p.run_arm(folder, 'forged', ask)
        self.assertEqual(row['recalls_served'], 1)
        self.assertEqual(row['recalls_requested'], 1)
        self.assertEqual(len(seen), 2)
        for actual, trace in zip(seen, row['calls']):
            self.assertEqual(actual, trace['request'])
            restored = copy.deepcopy(actual)
            restored['messages'][0]['content'] += p.CONTRACT
            self.assertEqual(restored, trace['keeper_request'])
        self.assertIn('original source 444', seen[-1]['messages'][-1]['content'])
        self.assertEqual(row['task_tools_executed'], 0)

    def test_frozen_parser_still_refuses_observed_compound_command(self):
        folder = self.fixture()
        compound = original_tests.response(original_tests.tool('bash', {'command': 'rm /app/AUDIT.md && ls /app'}))
        row = p.run_arm(folder, 'genuine', lambda _: compound)
        self.assertEqual(row['outcome'], 'unsupported_external_action')
        self.assertTrue(row['artifact']['exists'])
        self.assertFalse(row['actions'][0]['supported'])
        self.assertEqual(row['task_tools_executed'], 0)
        self.assertEqual(len(row['calls']), 1)

    def test_control_gate_records_tokens_without_borrowing_old_count(self):
        folder = self.fixture()
        response = original_tests.terminal()
        response['usage']['prompt_tokens'] = 8123
        row = p.run_arm(folder, 'control', lambda _: response)
        self.assertTrue(p.control_matches(row))
        self.assertFalse(p.prior.control_matches(row))
        self.assertFalse(p.control_matches(dict(row, recalls_requested=1)))
        self.assertFalse(p.control_matches(dict(row, outcome='unsupported_external_action')))

    def test_gate_failure_skips_without_network(self):
        folder = self.fixture()
        p.dump(folder / 'manifest.json', {'scope': p.SCOPE})
        p.dump(folder / 'cpu-capture.json', p.captures(folder))
        row = p.run_arm(folder, 'control', lambda _: original_tests.response(original_tests.tool('read', {'path': '/app/AUDIT.md'})))
        args = SimpleNamespace(fixture=folder, base_url='http://never-contact', json=folder / 'result.json')
        with patch.object(p, 'verify_fixture', return_value={'control_gate': {'messages': 12}}), patch.object(p, 'run_arm', return_value=row) as fake:
            p.run(args)
        self.assertEqual(fake.call_count, 1)
        result = p.load(args.json)
        self.assertTrue(result['complete'])
        self.assertFalse(result['cpu_check'])
        self.assertTrue(result['branches_skipped'])

    def test_transport_failure_retains_actual_and_keeper_request(self):
        folder = self.fixture()
        old_note = p.prior.ck.MEMORY_NOTE
        def fail(_):
            raise OSError('mock transport')
        with self.assertRaises(OSError) as caught:
            p.run_arm(folder, 'genuine', fail)
        call = caught.exception.probe_evidence['calls'][0]
        self.assertIsNone(call['response'])
        self.assertEqual(p.remove_suffix(call['keeper_request']), call['request'])
        self.assertEqual(p.prior.ck.MEMORY_NOTE, old_note)

    def test_expected_first_request_mismatch_is_fail_closed(self):
        folder = self.fixture()
        with self.assertRaises(RuntimeError) as caught:
            p.run_arm(folder, 'control', lambda _: self.fail('must not contact upstream'), expected_first={'wrong': True})
        self.assertEqual(len(caught.exception.probe_evidence['calls']), 1)
        self.assertIsNone(caught.exception.probe_evidence['calls'][0]['response'])


if __name__ == '__main__':
    unittest.main()

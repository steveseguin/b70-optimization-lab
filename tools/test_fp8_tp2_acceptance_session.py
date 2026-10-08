"""The acceptance session's optional multi-user stage, with every subprocess and server stubbed (no GPU, no docker)."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'experiments/qwen38-27b-b70/scripts'
SPEC = importlib.util.spec_from_file_location('tp2_acceptance_session', SCRIPTS / 'run-fp8-tp2-acceptance-session.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
COMPARE = MODULE.load_compare(ROOT)


def reference_doc(n=64):
    return {'oracle': {'rows': [{'prompt_id': f'p{i % 8}-c{i:03d}', 'prompt_sha256': f'h{i}', 'token_ids': [i, i + 1, i + 2]}
                                for i in range(n)]}}


def ladder_doc(reference, flip=None, cached=0, skip=None):
    """A client output whose every answer equals the reference, optionally with one token flipped in one batch."""
    rows = [dict(r) for r in reference['oracle']['rows']]
    batches = []
    for repeat in range(1, MODULE.MULTI_USER_REPEATS + 1):
        for users in MODULE.MULTI_USER_LEVELS:
            if skip == (users, repeat):
                continue
            selected = [dict(r, token_ids=list(r['token_ids'])) for r in rows[:users]]
            if flip == (users, repeat):
                selected[3]['token_ids'][1] += 1000
            batches.append({'concurrency': users, 'repeat': repeat, 'rows': selected, 'oracle_exact_count': users,
                            'aggregate_tok_s_wall': 10.0 * users, 'total_completion_tokens': 3 * users, 'elapsed_s': 0.3,
                            'cached_tokens_all_zero': cached == 0})
    return {'oracle': {'rows': rows, 'cached_tokens_all_zero': True}, 'batches': batches}


def constant_paths(path):
    """Module-level NAME = Path('...') / ROOT / '...' string constants of a campaign script, without importing it."""
    found = {}
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            value = node.value
            if isinstance(value, ast.Call) and value.args and isinstance(value.args[0], ast.Constant):
                found.setdefault(node.targets[0].id, value.args[0].value)
            elif isinstance(value, ast.BinOp) and isinstance(value.right, ast.Constant):
                found.setdefault(node.targets[0].id, value.right.value)
    return found


class ConfigurationTests(unittest.TestCase):
    def test_pinned_covers_the_multi_user_profile_and_exists(self):
        for path in ('packages/qwen38-27b-fp8-tp2-b70/overlays/b70_exclusive_prefill.py',
                     'packages/qwen38-27b-fp8-tp2-b70/overlays/b70_exclusive_prefill-0.1.0.dist-info/entry_points.txt',
                     'packages/qwen38-27b-fp8-tp2-b70/overlays/b70_fa_decode_per_seq.py',
                     'packages/qwen38-27b-fp8-tp2-b70/overlays/b70_fa_decode_per_seq-0.1.0.dist-info/entry_points.txt',
                     'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py', MODULE.LADDER, MODULE.COMPARE_LADDER,
                     *(s['suite'] for s in MODULE.MULTI_USER_SUITES.values())):
            self.assertIn(path, MODULE.PINNED)
        for path in MODULE.PINNED:
            self.assertTrue((ROOT / path).is_file(), path)
        self.assertEqual(len(MODULE.PINNED), len(set(MODULE.PINNED)))

    def test_same_client_suites_and_references_as_the_research_campaign(self):
        campaign = constant_paths(SCRIPTS / 'run-20261004-fp8-multiuser-campaign.py')
        review = constant_paths(SCRIPTS / 'run-20260916-fp8-review-campaign.py')
        self.assertEqual(str(MODULE.MULTI_USER_SUITES['short']['reference']), campaign['REF_LADDER'])
        self.assertEqual(str(MODULE.MULTI_USER_SUITES['long']['reference']), campaign['LONG_REF'])
        self.assertEqual(MODULE.MULTI_USER_SUITES['short']['suite'], review['LADDER_SUITE'])
        self.assertEqual(MODULE.LADDER, review['LADDER'])
        self.assertEqual(MODULE.COMPARE_LADDER, review['COMPARE_LADDER'])
        self.assertIn(MODULE.MULTI_USER_SUITES['long']['suite'],
                      (SCRIPTS / 'run-20261004-fp8-multiuser-campaign.py').read_text())

    def test_client_argv_matches_the_campaign_call(self):
        argv = [str(x) for x in MODULE.multi_user_client_argv(ROOT, 'long', 'http://127.0.0.1:18124', '/x/long.json')]
        self.assertEqual(argv[1], str(ROOT / 'scripts/bench-openai-concurrency-oracle.py'))
        for flag, value in (('--concurrency', '16,32,64'), ('--repeats', '2'), ('--max-tokens', '128'), ('--seed', '42'),
                            ('--api-mode', 'completions'), ('--model', 'qwen38-27b-fp8'), ('--timeout', '3600'),
                            ('--suite', str(ROOT / 'experiments/qwen38-27b-b70/data/2026-10-04-fp8-multiuser/long-prompt-suite.json'))):
            self.assertEqual(argv[argv.index(flag) + 1], value)
        self.assertIn('--return-token-ids', argv)


class SuiteResultTests(unittest.TestCase):
    def setUp(self):
        self.reference = reference_doc()

    def test_all_exact_passes_and_records_totals(self):
        result = MODULE.suite_result(ladder_doc(self.reference), self.reference, COMPARE.compare_rows)
        self.assertTrue(result['passed'])
        self.assertEqual([[p['users'], p['repeat']] for p in result['passes']], [[16, 1], [16, 2], [32, 1], [32, 2], [64, 1], [64, 2]])
        self.assertEqual(result['passes'][-1]['tok_s_together'], 640.0)
        self.assertEqual(json.loads(json.dumps(result)), result)  # JSON-native: the collector compares after a round trip

    def test_one_flipped_token_in_the_second_pass_fails(self):
        result = MODULE.suite_result(ladder_doc(self.reference, flip=(32, 2)), self.reference, COMPARE.compare_rows)
        self.assertFalse(result['passed'])
        row = next(p for p in result['passes'] if (p['users'], p['repeat']) == (32, 2))
        self.assertEqual(row['exact_vs_reference'], 31)
        self.assertEqual(row['first_divergences'], [['p3-c003', 1]])

    def test_a_missing_level_or_cached_tokens_fail(self):
        self.assertFalse(MODULE.suite_result(ladder_doc(self.reference, skip=(64, 2)), self.reference, COMPARE.compare_rows)['passed'])
        self.assertFalse(MODULE.suite_result(ladder_doc(self.reference, cached=1), self.reference, COMPARE.compare_rows)['passed'])

    def test_a_sequential_pass_that_differs_from_the_reference_fails(self):
        ladder = ladder_doc(self.reference)
        ladder['oracle']['rows'][0] = dict(ladder['oracle']['rows'][0], token_ids=[9, 9, 9])
        self.assertFalse(MODULE.suite_result(ladder, self.reference, COMPARE.compare_rows)['passed'])


class WaitTests(unittest.TestCase):
    def test_wait_cards_free_is_bounded(self):
        now = [0.0]
        answers = iter([(False, 'port 18124 is still bound'), (True, 'free')])
        self.assertEqual(MODULE.wait_cards_free(18124, timeout=60, probe=lambda port: next(answers), clock=lambda: now[0],
                                                sleep=lambda s: now.__setitem__(0, now[0] + s)), (True, 'free'))
        now[0] = 0.0
        self.assertEqual(MODULE.wait_cards_free(18124, timeout=12, probe=lambda port: (False, 'the stage lock is held'),
                                                clock=lambda: now[0], sleep=lambda s: now.__setitem__(0, now[0] + s)),
                         (False, 'the stage lock is held'))


class FakeHelper:
    """`serve.py start` stand-in: writes the launcher's state receipt and exits once stopped."""
    def __init__(self, session, ready=True):
        self.session, self.returncode, self.signals = session, None, []
        session.mkdir(parents=True)
        self.write(status='ready' if ready else 'failed', container_id='c' * 64 if ready else None)
        if not ready:
            self.returncode = 1

    def write(self, **values):
        (self.session / 'state.json').write_text(json.dumps(dict({'profile': 'multi-user'}, **values)))

    def poll(self): return self.returncode
    def wait(self, timeout=None): return self.returncode
    def send_signal(self, signum): self.signals.append(signum); self.returncode = 0


class RunMultiUserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name)
        self.reference = reference_doc()
        suites = {}
        for key, suite in MODULE.MULTI_USER_SUITES.items():
            path = self.out / f'{key}-reference.json'
            path.write_text(json.dumps(self.reference))
            suites[key] = dict(suite, reference=path, reference_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        self.patches = [mock.patch.object(MODULE, 'MULTI_USER_SUITES', suites),
                        mock.patch.object(MODULE, 'wait_cards_free', lambda port, timeout: (True, 'free')),
                        mock.patch.object(MODULE, 'cgroup_memory', lambda container: {'read': False}),
                        mock.patch.object(MODULE.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(a, 0, '{}', ''))]
        for p in self.patches:
            p.start()
        self.helpers, self.calls, self.said = [], [], []

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp.cleanup()

    def popen(self, argv, **kwargs):
        self.assertEqual(argv[2:5], ['start', '--profile', 'multi-user'])
        self.assertTrue(argv[1].endswith('packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'))
        helper = FakeHelper(Path(argv[argv.index('--state-dir') + 1]), ready=self.ready)
        self.helpers.append(helper)
        return helper

    def sh(self, argv, stdout_path, cwd=None, env=None, timeout=3600):
        argv = [str(x) for x in argv]
        self.calls.append(argv)
        if 'stop' in argv:
            self.helpers[-1].write(status='stopped', container_id='c' * 64)
            self.helpers[-1].returncode = 0
            return 0
        if self.client_timeout:
            raise subprocess.TimeoutExpired(argv, timeout)
        out = Path(argv[argv.index('--out') + 1])
        out.write_text(json.dumps(ladder_doc(self.reference, flip=self.flip if 'short' in out.name else None)))
        return 0

    def run_stage(self, ready=True, flip=None, client_timeout=False):
        self.ready, self.flip, self.client_timeout = ready, flip, client_timeout
        return MODULE.run_multi_user(ROOT, self.out, self.said.append, self.sh, popen=self.popen, ready_timeout=5)

    def summary(self):
        return json.loads((self.out / 'multi-user/summary.json').read_text())

    def stops(self):
        return [c for c in self.calls if 'stop' in c]

    def test_exact_stage_passes_and_stops_once(self):
        self.assertEqual(self.run_stage(), 0)
        summary = self.summary()
        self.assertTrue(summary['passed'])
        self.assertEqual(summary['suites']['long']['passes'][-1]['tok_s_together'], 640.0)
        self.assertEqual(len(self.stops()), 1)
        self.assertEqual(len([c for c in self.calls if '--concurrency' in c]), 2)
        self.assertEqual(summary['server']['final_status'], 'stopped')

    def test_one_inexact_answer_fails_the_stage(self):
        self.assertEqual(self.run_stage(flip=(64, 1)), 1)
        self.assertFalse(self.summary()['passed'])
        self.assertFalse(self.summary()['suites']['short']['passed'])
        self.assertTrue(self.summary()['suites']['long']['passed'])

    def test_server_is_stopped_even_when_the_client_times_out(self):
        self.assertEqual(self.run_stage(client_timeout=True), 1)
        self.assertEqual(len(self.stops()), 1)
        self.assertEqual(self.summary()['rcs']['short_client'], 'timeout')

    def test_failed_start_runs_no_client(self):
        self.assertEqual(self.run_stage(ready=False), 1)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.summary()['ran'])

    def test_changed_reference_starts_no_server(self):
        MODULE.MULTI_USER_SUITES['long']['reference'].write_text('{}')
        self.assertEqual(self.run_stage(), 'reference missing')
        self.assertEqual(self.helpers, [])
        self.assertIn('long', self.summary()['reason'])

    def test_busy_cards_start_no_server(self):
        with mock.patch.object(MODULE, 'wait_cards_free', lambda port, timeout: (False, 'the stage lock is held')):
            self.assertEqual(self.run_stage(), 'cards not free')
        self.assertEqual(self.helpers, [])


if __name__ == '__main__':
    unittest.main()

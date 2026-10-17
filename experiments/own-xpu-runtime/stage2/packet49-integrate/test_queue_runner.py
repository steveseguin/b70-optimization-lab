"""CPU-only queue tests: no real launcher, model, journal or device calls."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import queue_runner as q


class QueueTests(unittest.TestCase):
    def test_complete_order_and_configuration(self):
        commands = q.commands(Path('/test'))
        self.assertEqual(tuple(commands), q.EARLY + q.LATE)
        for name, command in commands.items():
            for flag, value in (('--card', '0'), ('--context', '4096'), ('--draft-rank', '1'), ('--target-split', '23')):
                self.assertEqual(command[command.index(flag) + 1], value)
            self.assertNotIn('--diagnostic-unsealed', command)
            self.assertEqual(command[:3] == ['nice', '-n', '19'], name.startswith('K'))

    def test_early_has_no_full_model_oracle(self):
        for name in q.EARLY:
            command = q.commands(Path('/test'))[name]
            self.assertNotIn('--oracle', command)
            self.assertNotIn('--suite-manifest', command)
        self.assertEqual(q.EARLY[-1], 'W0p')

    def test_new_oracle_and_exactness_pair(self):
        commands = q.commands(Path('/test'))
        self.assertIn(str(q.P / 'oracle/results/incident-retrospective'), commands['W2m'])
        for name in ('WS', 'WSs', 'WS128x', 'WS128'):
            self.assertIn(str(q.P / 'oracle/results/suite-manifest.json'), commands[name])
        self.assertIn('/test/WS128x/window.json', commands['WS128'])
        self.assertIn('1-8,97-104', commands['WS128x'])
        self.assertIn('none', commands['WS128'])

    def test_rc_and_receipt_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / 'K0').mkdir()
            receipt = out / 'K0/window.json'
            row = dict(window='K0', passed=True, device_executed=True, qualifying=True,
                       card=0, context=4096, draft_rank=1, target_split=23)
            receipt.write_text(json.dumps(row))
            q.validate_success('K0', out, 0)
            with self.assertRaises(RuntimeError):
                q.validate_success('K0', out, 1)
            for field in row:
                bad = dict(row)
                bad[field] = None
                receipt.write_text(json.dumps(bad))
                with self.assertRaises(RuntimeError, msg=field):
                    q.validate_success('K0', out, 0)

    def test_journal_failure_and_specific_faults(self):
        class Result:
            stdout = '-- cursor: abc\n'
        with patch.object(q.subprocess, 'run', return_value=Result()):
            self.assertEqual(q.journal(), 'abc')
            Result.stdout = 'unrelated word hang\n-- cursor: def\n'
            self.assertEqual(q.journal('abc'), 'def')
            Result.stdout = 'xe Fault response: Unsuccessful\n-- cursor: def\n'
            with self.assertRaises(RuntimeError):
                q.journal('abc')
            Result.stdout = ''
            with self.assertRaises(RuntimeError):
                q.journal()

    def test_plan_never_launches(self):
        with patch('sys.argv', ['queue_runner.py', '--plan', '--phase', 'early', '--output-root', '/test']), patch.object(q, 'run') as launch, patch('builtins.print'):
            q.main()
            launch.assert_not_called()

    def test_unauthorized_refuses(self):
        from types import SimpleNamespace
        with self.assertRaisesRegex(ValueError, 'authorized'):
            q.run(SimpleNamespace(authorized_device_window=False))

    def test_oracle_pending_vs_failed(self):
        from types import SimpleNamespace
        for status in ('running', 'not-started'):
            with patch.object(q.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stdout=json.dumps(dict(ready=False, status=status)))):
                self.assertFalse(q.oracle_ready())
        for text in ('invalid', json.dumps(dict(ready=False, status='failed'))):
            with patch.object(q.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stdout=text)):
                with self.assertRaises(RuntimeError):
                    q.oracle_ready()

    def test_durable_user_service(self):
        q.user_unit_gate('0::/user.slice/user-1000.slice/user@1000.service/app.slice/p49.service\n')
        for path in ('0::/user.slice/user-1000.slice/session-2.scope', '0::/system.slice/p49.service', '0::/'):
            with self.assertRaises(ValueError):
                q.user_unit_gate(path)

    def test_fault_signature_variants(self):
        for text in ('CAT error', 'device coredump', 'job 17 timed out', 'timed-out fence', 'engine reset', 'reset engine'):
            self.assertIsNotNone(q.FAULT.search(text))
        self.assertIsNone(q.FAULT.search('configuration changed'))


if __name__ == '__main__':
    unittest.main()

"""CPU-only C64 lifecycle/refusal tests. No Docker or service commands execute."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import current_pi_probe as p


class PiProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='c64-unit-')
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def args(self):
        return argparse.Namespace(json=self.folder / 'result.json', pins=self.folder / 'pins.json',
                                  base_url='http://127.0.0.1:18196/v1', rounds=1)

    def test_derived_runner_has_exact_four_changes_and_refuses_drift(self):
        source = p.RUNNER.read_text()
        derived, delta = p.derive_runner(source)
        changed = [(a, b) for a, b in zip(source.splitlines(), derived.splitlines()) if a != b]
        self.assertEqual(len(changed), 4)
        self.assertEqual(len(source.splitlines()), len(derived.splitlines()))
        self.assertNotIn('"$HERE/build-agent-image.sh"', derived)
        self.assertNotIn('python3 -I "$HERE/check_history.py"', derived)
        self.assertIn('IMG=' + p.IMAGE_ID, derived)
        self.assertIn('--network none --memory "$AGENT_MEM" --memory-swap "$AGENT_MEM_SWAP"', derived)
        with self.assertRaises(RuntimeError):
            p.derive_runner(source.replace('IMG="agentbench-$AGENT:$TNAME"', 'IMG=changed'))

    def test_wrong_image_refused_without_build(self):
        with patch.object(p, 'command', return_value='sha256:wrong') as command:
            with self.assertRaises(RuntimeError):
                p.image_check()
        self.assertEqual(command.call_args.args[0][:3], ['docker', 'image', 'inspect'])

    def test_failed_service_inspection_is_not_inactive(self):
        for rc, text in ((1, ''), (4, ''), (0, '')):
            with patch.object(p.subprocess, 'run', return_value=SimpleNamespace(returncode=rc, stdout=text)):
                with self.assertRaises(RuntimeError):
                    p.inactive('unknown-unit')
        with patch.object(p.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='inactive\n')):
            self.assertTrue(p.inactive('stopped-unit'))

    def test_existing_task_path_refused_before_container_commands(self):
        occupied = self.folder / 'occupied'
        occupied.mkdir()
        (occupied / 'keep').write_text('untouched')
        with patch.object(p, 'RUNS', occupied), patch.object(p, 'command') as command:
            with self.assertRaises(RuntimeError):
                p.fresh()
        command.assert_not_called()
        self.assertEqual((occupied / 'keep').read_text(), 'untouched')

    def test_memory_threshold_and_notes_override(self):
        mem = self.folder / 'meminfo'
        mem.write_text(f'MemAvailable: {(p.MIN_AVAILABLE_MIB - 1) * 1024} kB\n')
        with self.assertRaises(RuntimeError):
            p.require_memory(mem)
        mem.write_text(f'MemAvailable: {p.MIN_AVAILABLE_MIB * 1024} kB\n')
        self.assertEqual(p.require_memory(mem), p.MIN_AVAILABLE_MIB)
        cmd = p.proxy_command('http://127.0.0.1:18196/v1')
        self.assertEqual(cmd[cmd.index('--recipe') + 1], 'qwen')
        self.assertEqual(cmd[cmd.index('--notes-thinking') + 1], 'on')
        self.assertEqual(cmd[cmd.index('--upstream-retries') + 1], '0')
        with self.assertRaises(ValueError):
            p.proxy_command('http://remote.example/v1')

    def make_receipts(self, fixed=40, timed_out=False, void=False):
        trial = self.folder / 'trial'
        (trial / 'agent').mkdir(parents=True, exist_ok=True)
        (trial / 'verifier').mkdir(exist_ok=True)
        exited = {'exit_code': 0, 'timed_out': timed_out, 'seconds': 1}
        details = {'kind': 'repair', 'n': 40, 'void': void, 'fixed': fixed, 'clean': fixed,
                   'tickets_fetched': 44, 'rules': {'R1': {'applies': 37, 'kept': 37},
                    'R2': {'applies': 32, 'kept': 32}, 'R3': {'applies': 26, 'kept': 26}},
                   'audit': {'asked': 7, 'right': 7, 'lines': 7, 'other_tickets': 0}}
        ab = {'image_id': p.IMAGE_ID, 'agent': 'pi', 'job': p.JOB, 'exec_rc': 0,
              'agent_exit': exited, 'verifier': details, 'history': None}
        for name, value in [('agent/agentbench.json', ab), ('agent/exit.json', exited),
                            ('verifier/details.json', details)]:
            (trial / name).write_text(json.dumps(value))
        (trial / 'agent/requests.jsonl').write_text('\n'.join(json.dumps({
            'method': 'POST', 'path': '/v1/chat/completions', 'body': '{"messages":[]}'}) for _ in range(2)))
        return trial

    def test_lower_quality_is_completed_client_not_qualification(self):
        trial = self.make_receipts(fixed=39)
        result = p.collect_receipts(trial, {'session': {'restarts': 0}})
        self.assertTrue(result['client_complete'])
        self.assertFalse(result['task_quality_pass'])
        self.assertFalse(result['complete'])
        self.assertEqual(result['history_status'], 'deferred-until-server-down')

    def test_zero_shell_exit_does_not_hide_timeout_void_or_restart(self):
        trial = self.make_receipts(timed_out=True)
        self.assertFalse(p.collect_receipts(trial, {'s': {}})['client_complete'])
        trial = self.make_receipts(void=True)
        self.assertFalse(p.collect_receipts(trial, {'s': {}})['client_complete'])
        trial = self.make_receipts()
        self.assertFalse(p.collect_receipts(trial, {'s': {'restarts': 1}})['client_complete'])
        (trial / 'agent/requests.jsonl').write_text(json.dumps({'method': 'POST', 'path': '/v1/chat/completions'}))
        self.assertFalse(p.collect_receipts(trial, {'s': {}})['client_complete'])

    def lifecycle_patches(self):
        derived, _ = p.derive_runner(p.RUNNER.read_text())
        receipt = {'driver_sha256': hashlib.sha256(derived.encode()).hexdigest()}
        args = self.args()
        args.pins.write_text('{}')
        return args, receipt

    def test_proxy_cleanup_even_when_readiness_fails(self):
        args, receipt = self.lifecycle_patches()
        with patch.object(p, 'verify_pins', return_value=receipt), patch.object(p, 'image_check'), \
             patch.object(p, 'fresh'), patch.object(p, 'require_memory', return_value=3000), \
             patch.object(p, 'CONTROL', self.folder / 'control'), patch.object(p, 'command', return_value='owned'), \
             patch.object(p, 'wait_proxy', side_effect=RuntimeError('readiness failed')), \
             patch.object(p, 'stop_proxy') as stop:
            with self.assertRaisesRegex(RuntimeError, 'readiness failed'):
                p.run_client(args)
        stop.assert_called_once_with('owned')
        result = p.read(args.json)
        self.assertFalse(result['client_complete'])
        self.assertTrue(result['proxy_stopped'])

    def test_task_environment_and_deferred_success(self):
        args, receipt = self.lifecycle_patches()
        with patch.object(p, 'verify_pins', return_value=receipt), patch.object(p, 'image_check'), \
             patch.object(p, 'fresh'), patch.object(p, 'require_memory', return_value=3000), \
             patch.object(p, 'CONTROL', self.folder / 'control'), patch.object(p, 'command', return_value='owned'), \
             patch.object(p, 'wait_proxy'), patch.object(p, 'get_status', return_value={'s': {}}), \
             patch.object(p, 'collect_receipts', return_value={'client_complete': True, 'complete': False}), \
             patch.object(p, 'stop_proxy') as stop, patch.object(p.subprocess, 'run') as run:
            p.run_client(args)
        env = run.call_args.kwargs['env']
        self.assertEqual((env['AGENT_MEM'], env['AGENT_MEM_SWAP'], env['KEEP_CONTAINER'], env['TAP']),
                         ('768m', '768m', '0', 'full'))
        stop.assert_called_once_with('owned')
        result = p.read(args.json)
        self.assertTrue(result['client_complete'])
        self.assertFalse(result['complete'])

    def test_finalize_refuses_live_model_and_uses_original_checker_after_stop(self):
        args = self.args()
        with patch.object(p, 'verify_pins'), patch.object(p, 'inactive', return_value=False), \
             patch.object(p.subprocess, 'run') as run:
            with self.assertRaises(RuntimeError):
                p.finalize(args)
        run.assert_not_called()
        trial = self.make_receipts()
        before = (trial / 'agent/agentbench.json').read_bytes()
        p.dump(args.json, {'client_complete': True, 'proxy_stopped': True, 'complete': False, 'task_quality_pass': True})
        history = {'whole_history_ok': True, 'responses_api': 0, 'n_not_1': 0, 'chunked_bodies': 0}
        def check(argv, **kwargs):
            self.assertEqual(argv[2], str(p.HISTORY))
            kwargs['stdout'].write(json.dumps(history))
        with patch.object(p, 'verify_pins'), patch.object(p, 'inactive', return_value=True), \
             patch.object(p, 'TRIAL', trial), patch.object(p.subprocess, 'run', side_effect=check):
            p.finalize(args)
        result = p.read(args.json)
        self.assertTrue(result['complete'])
        self.assertTrue(result['quality_pass'])
        self.assertEqual((trial / 'agent/agentbench.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()

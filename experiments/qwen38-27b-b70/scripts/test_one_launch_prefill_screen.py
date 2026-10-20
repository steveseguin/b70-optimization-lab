"""CPU-only guards for ownership and non-escalating one-server lifecycle."""
import importlib.util
import json
from pathlib import Path
import subprocess
import re
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('prefill_screen', Path(__file__).with_name('run-one-launch-prefill-screen.py'))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeServe:
    def __init__(self, hang=False, wrong_owner=False):
        self.running = True
        self.hang = hang
        self.wrong_owner = wrong_owner
        self.commands = []

    def inspect_container(self, identity):
        return {'Id': identity, 'State': {'Running': self.running}}

    def owned(self, record, container):
        if self.wrong_owner:
            raise RuntimeError('wrong owner')

    def run(self, argv, **kwargs):
        self.commands.append(argv)
        if not self.hang:
            self.running = False
        return subprocess.CompletedProcess(argv, 0, '', '')


class PrefillLifecycleTest(unittest.TestCase):
    def test_controller_run_mode_refuses_before_any_work(self):
        with patch.object(MODULE.sys, 'argv', ['adapter', '--run']), \
                patch.object(MODULE, 'adapter') as start, patch.object(MODULE, 'guarded_client') as client:
            with self.assertRaisesRegex(RuntimeError, 'prohibited'):
                MODULE.main()
            start.assert_not_called()
            client.assert_not_called()

    def test_client_guard_stops_next_http_request_after_fault(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            bench = out / 'fake_bench.py'
            bench.write_text('from pathlib import Path\n'
                'def fetch(path):\n    with Path(path).open("a") as f: f.write("request\\n")\n'
                'def run(args):\n    for _ in range(2): fetch(args.out.parent / "calls.txt")\n')
            fake = FakeServe()
            fake.FAULT = re.compile('GPUFAULT')
            kernels = iter(('', 'GPUFAULT'))
            fake.journal = lambda since: next(kernels)
            (out / 'server').mkdir()
            (out / 'server/state.json').write_text(json.dumps({'started_at': 'test'}))
            with patch.object(MODULE, 'BENCH', bench), patch.object(MODULE, 'load_serve', return_value=fake), \
                    patch.object(MODULE, 'verify_pins'), patch.object(MODULE, 'disk_floors'), \
                    patch.object(MODULE, 'verify_ready_server'):
                with self.assertRaisesRegex(RuntimeError, 'admission halted'):
                    MODULE.guarded_client(out)
            self.assertEqual((out / 'calls.txt').read_text(), 'request\n')
            self.assertTrue((out / 'FAULT.json').exists())

    def test_only_term_and_one_stop_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            fake = FakeServe()
            MODULE.term_only_stop(fake, state, {'container_id': 'owned'})
            MODULE.term_only_stop(fake, state, {'container_id': 'owned'})
            self.assertEqual(fake.commands, [['docker', 'kill', '--signal=TERM', 'owned']])
            self.assertTrue(json.loads((state / 'graceful-stop.json').read_text())['stopped'])

    def test_foreign_container_never_signalled(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeServe(wrong_owner=True)
            with self.assertRaisesRegex(RuntimeError, 'wrong owner'):
                MODULE.term_only_stop(fake, Path(tmp), {'container_id': 'foreign'})
            self.assertEqual(fake.commands, [])

    def test_hang_records_failure_without_escalation(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeServe(hang=True)
            times = iter((0, 0, 181))
            with self.assertRaisesRegex(RuntimeError, 'without KILL'):
                MODULE.term_only_stop(fake, Path(tmp), {'container_id': 'owned'},
                                      clock=lambda: next(times), sleep=lambda _: None)
            self.assertEqual(fake.commands, [['docker', 'kill', '--signal=TERM', 'owned']])
            result = json.loads((Path(tmp) / 'graceful-stop.json').read_text())
            self.assertFalse(result['stopped'])
            self.assertFalse(result['escalation'])

    def test_plan_keeps_package_numeric_argv_and_synthetic_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'not-created'
            result = MODULE.plan(out)
            self.assertFalse(out.exists())
            argv = result['launch_argv_template']
            # Package start() resolves model/state paths before rendering Docker mounts.
            self.assertEqual(MODULE.MODEL, MODULE.MODEL.resolve())
            self.assertEqual(argv, MODULE.load_serve().docker_argv('recommended', MODULE.MODEL.resolve(),
                (out / 'server').resolve(), MODULE.PORT, 'OWNED-UUID'))
            self.assertIn('B70_FA_VERIFY_ROWS_ONE_LAUNCH=1', argv)
            self.assertFalse(result['strict_headline_eligible'])
            self.assertFalse(result['no_quality_loss_gate'])
            client = result['client_argv']
            for flag, value in [('--lengths', '512'), ('--repeats', '2'), ('--max-tokens', '128'),
                                ('--max-model-len', '33024')]:
                self.assertEqual(client[client.index(flag) + 1], value)


if __name__ == '__main__':
    unittest.main()

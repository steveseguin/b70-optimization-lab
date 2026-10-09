"""CPU-only: Docker calls are fakes; no runtime/device imports or launches."""
import ast
import datetime
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

COPIES = Path(__file__).resolve().parents[1] / 'copies'


def load(name):
    spec = importlib.util.spec_from_file_location(name, COPIES / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


watch = load('memory_watchdog')
receipts = load('teardown_receipts')


def row(rank=0, pid=100):
    unix = 1_700_000_000_000_000_000
    utc = datetime.datetime.fromtimestamp(unix / 1e9, datetime.timezone.utc).isoformat()
    return {'schema': receipts.SCHEMA, 'event': 'rank_teardown_complete',
            'status': 'complete', 'rank': rank, 'pid': pid,
            'timestamps': {phase: {'utc': utc, 'unix_ns': unix, 'monotonic_ns': i}
                           for i, phase in enumerate(receipts.REQUIRED_PHASES)}}


class StopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)

    def response(self, stdout='true', code=0):
        return subprocess.CompletedProcess([], code, stdout, '')

    def test_no_signal_before_owned_launch(self):
        runner = Mock()
        stop = watch.DeferredStop(self.run, 'owned', runner)
        stop.request('memory')
        self.assertTrue((self.run / 'STOP').exists())
        runner.assert_not_called()

    def test_creation_race_retries_inspection_but_signals_once(self):
        calls = []
        def runner(cmd, **kw):
            self.assertTrue((self.run / 'STOP').exists())
            calls.append(cmd)
            if len(calls) == 1:
                return self.response('', 1)
            return self.response()
        stop = watch.DeferredStop(self.run, 'owned', runner)
        stop.armed = True
        stop.request('memory')
        self.assertFalse(stop.sent)
        stop.request('deferred')
        stop.request('again')
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[-1], ['docker', 'kill', '--signal=SIGINT', 'owned'])
        self.assertEqual((self.run / 'STOP').read_text(), 'memory\n')

    def test_delivery_timeout_never_retries_signal(self):
        runner = Mock(side_effect=[self.response(), subprocess.TimeoutExpired('docker', 10)])
        stop = watch.DeferredStop(self.run, 'owned', runner)
        stop.armed = True
        stop.request('memory')
        stop.request('again')
        self.assertEqual(runner.call_count, 2)
        self.assertTrue(stop.sent)

    def test_both_signal_handlers_only_latch_intent(self):
        for sig in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(sig=sig):
                runner = Mock()
                stop = watch.DeferredStop(self.run, 'owned', runner)
                with stop.lock:  # handler cannot reenter/acquire the lock
                    stop.signal_handler(sig, None)
                self.assertTrue(stop.requested)
                self.assertIn(signal.Signals(sig).name, stop.reason)
                runner.assert_not_called()

    def test_real_cpu_signals_record_intent_and_return(self):
        stop = watch.DeferredStop(self.run, 'owned', Mock())
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous = signal.signal(sig, stop.signal_handler)
            try:
                signal.raise_signal(sig)
                self.assertTrue(stop.requested)
            finally:
                signal.signal(sig, previous)
        stop.runner.assert_not_called()

    def test_signal_then_supervision_uses_same_ordered_stop(self):
        runner = Mock(return_value=self.response())
        stop = watch.DeferredStop(self.run, 'owned', runner)
        stop.armed = True
        stop.signal_handler(signal.SIGTERM, None)
        stop.request('completion')
        self.assertEqual(runner.call_args.args[0], ['docker', 'kill', '--signal=SIGINT', 'owned'])
        self.assertIn('SIGTERM', (self.run / 'STOP').read_text())

    def test_watchdog_uses_same_latch_and_one_signal(self):
        runner = Mock(return_value=self.response())
        stop = watch.DeferredStop(self.run, 'owned', runner)
        stop.armed = True
        watchdog = watch.MemoryWatchdog(self.run, stop.request, sampler=lambda: {},
                                       threshold=lambda _: 'memory bound')
        with patch.object(watch, 'process_identity', return_value={'pid': 1}):
            watchdog.check()
            watchdog.check()
        self.assertTrue(watchdog.tripped.is_set())
        self.assertEqual(runner.call_count, 2)


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)

    def write(self, value):
        (self.run / f"loader-{value['pid']}.jsonl").write_text(json.dumps(value) + '\n')

    def test_all_four_final_ranks_pass(self):
        for rank in range(4):
            self.write(row(rank, rank + 100))
        self.assertTrue(receipts.validate_rank_receipts(self.run)['passed'])

    def test_missing_rank_fails(self):
        self.write(row())
        self.assertFalse(receipts.validate_rank_receipts(self.run)['passed'])

    def test_missing_distributed_or_cache_timestamp_fails(self):
        for phase in receipts.REQUIRED_PHASES:
            with self.subTest(phase=phase):
                value = row()
                del value['timestamps'][phase]
                self.write(value)
                self.assertFalse(receipts.validate_rank_receipts(self.run, [0])['passed'])

    def test_timestamp_order_fails(self):
        value = row()
        value['timestamps']['distributed_released']['monotonic_ns'] = 999
        self.write(value)
        self.assertFalse(receipts.validate_rank_receipts(self.run, [0])['passed'])

    def test_duplicate_rank_fails(self):
        self.write(row())
        self.write(row(pid=101))
        self.assertFalse(receipts.validate_rank_receipts(self.run, [0])['passed'])

    def test_failure_and_malformed_receipts_fail(self):
        for update in ({'status': 'failed'}, {'errors': ['sync']},
                       {'event': 'rank_teardown_failed'}, {'rank': True}):
            with self.subTest(update=update):
                value = row()
                value.update(update)
                self.write(value)
                self.assertFalse(receipts.validate_rank_receipts(self.run, [0])['passed'])
        (self.run / 'loader-100.jsonl').write_text('{bad json\n')
        self.assertFalse(receipts.validate_rank_receipts(self.run, [0])['passed'])


class ControllerContractTests(unittest.TestCase):
    def test_docker_metadata_never_escalates(self):
        tree = ast.parse((COPIES / 'screen.py').read_text())
        # Inspect prepared command only; do not execute or import the controller.
        launch = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'launch')
        values = [n.value for n in ast.walk(launch) if isinstance(n, ast.Constant)]
        self.assertIn('--stop-signal=SIGINT', values)
        self.assertIn('--stop-timeout=-1', values)

    def test_clean_exit_is_after_receipts_and_kernel_gate(self):
        source = (COPIES / 'screen.py').read_text()
        end = source.index('            end = journal()')
        self.assertLess(source.index('if new_fault_lines(end, journal_cutoff)', end),
                        source.index('clean_exit = True', end))
        self.assertLess(source.index("require(teardown['passed']", end),
                        source.index('clean_exit = True', end))

    def test_entrypoint_restores_signals_and_handles_setup(self):
        source = (COPIES / 'container-entrypoint.sh').read_text()
        self.assertIn('env --default-signal=INT --default-signal=TERM', source)
        self.assertIn('trap setup_cancel INT TERM', source)
        self.assertLess(source.index('trap setup_cancel'), source.index('/screen-package/apply_overlay.py'))


if __name__ == '__main__':
    unittest.main()

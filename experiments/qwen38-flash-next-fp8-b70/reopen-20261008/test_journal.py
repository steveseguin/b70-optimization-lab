"""Synthetic journal/receipt tests; no GPU, Docker, server or secret access."""
import contextlib
import copy
import datetime as dt
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import screen
from memory_watchdog import DeferredStop
from test_cpu import write_rank_receipts, docker_status

NOW = dt.datetime(2026, 10, 8, 16, tzinfo=dt.timezone.utc)
BOOT = 'synthetic-boot-id'


def line(time, message):
    return f'2026-10-08T{time}+00:00 steve-b70s kernel: {message}\n'


OLD = (line('14:04:34', 'xe Fault response') + line('14:04:40', 'CAT error') +
       line('14:04:42', 'Timedout job') + line('14:04:51', 'device coredump created'))
DELETED = line('15:06:16', 'Xe device coredump has been deleted.')


def receipt():
    return dict(schema='ltx.four-card-health.v1', passed=True, boot_id=BOOT,
                kernel='synthetic', torch='synthetic', device_count=4,
                start_utc='2026-10-08 14:30:00 UTC', end_utc='2026-10-08 14:31:18 UTC',
                journal_fault_lines_during_probe=[], cards=[
                    dict(device=f'xpu:{i}', name='synthetic B70', **{'pass': True},
                         copy_roundtrip_exact=True, gemm_repeat_exact=True,
                         gemm_fp32_max_abs_err=.001, gemm_bf16_max_abs_err=.5,
                         staged_from_previous_exact=True) for i in range(4)])


class JournalTests(unittest.TestCase):
    def admit(self, text, health=None, now=NOW):
        return screen.admit_journal(text, health, boot_id=BOOT, now=now)

    def test_clean_boot_needs_no_receipt(self):
        self.assertEqual(self.admit(line('14:00:00', 'ordinary boot')), ([], NOW.timestamp()))

    def test_old_incident_admitted(self):
        admitted, cutoff = self.admit(OLD + DELETED, receipt())
        self.assertEqual(admitted, OLD.splitlines())
        self.assertEqual(cutoff, screen.parse_utc(receipt()['end_utc']).timestamp())

    def test_old_fault_requires_receipt(self):
        with self.assertRaisesRegex(RuntimeError, '--health-receipt'):
            self.admit(OLD)

    def test_new_fault_after_receipt_refused(self):
        # One incident, so specifically tests the receipt cutoff rather than tally.
        with self.assertRaisesRegex(RuntimeError, 'after the health receipt'):
            self.admit(line('14:31:19', 'Fault response'), receipt())

    def test_receipt_boundary_second_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'after the health receipt'):
            self.admit(line('14:31:18.000001', 'Fault response'), receipt())

    def test_two_incidents_refused_even_with_later_receipt(self):
        for health in (None, receipt()):
            with self.subTest(health=bool(health)), self.assertRaisesRegex(RuntimeError, 'owner must decide.*reboot'):
                self.admit(OLD + line('14:10:00', 'engine reset'), health)

    def test_incident_gap_boundary_and_unsorted_lines(self):
        self.assertEqual(screen.fault_incidents([
            line('14:05:00', 'CAT error'), line('14:04:00', 'Fault response')]), 1)
        self.assertEqual(screen.fault_incidents([
            line('14:05:00.000001', 'CAT error'), line('14:04:00', 'Fault response')]), 2)

    def test_deletion_alone_is_ignored(self):
        self.assertEqual(self.admit(DELETED)[0], [])
        self.assertFalse(screen.classify_journal(DELETED)['latch'])

    def test_all_gpu_signatures_latch(self):
        for message in ('Fault response', 'CAT error', 'engine CCS reset', 'reset engine',
                        'Timedout job', 'timed-out job', 'Job timed out', 'GPU HANG',
                        'GuC reset', 'wedged', 'devcoredump created'):
            with self.subTest(message=message):
                self.assertTrue(screen.classify_journal(line('16:00:01', message))['latch'])

    def test_unexplained_host_stall_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'after the health receipt'):
            self.admit(line('15:00:00', 'BUG: soft lockup - CPU#21 stuck for 22s!'), receipt())

    def test_known_xe_host_stall_tolerance_never_hides_gpu_fault(self):
        text = (line('15:00:00', 'hard LOCKUP on cpu 21') +
                line('15:00:00', 'xe_guc_irq_handler') +
                line('15:00:01', 'BUG: soft lockup - CPU#20 stuck for 22s!'))
        self.assertFalse(screen.classify_journal(text)['latch'])
        with self.assertRaisesRegex(RuntimeError, 'after the health receipt'):
            self.admit(text + line('15:00:02', 'CAT error'), receipt())

    def test_untimestamped_fault_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, 'timestamp'):
            self.admit('Fault response\n', receipt())

    def test_receipt_bad_identity_age_and_evidence_refused(self):
        variants = [dict(boot_id='other-boot'), dict(passed=False), dict(device_count=3),
                    dict(schema='wrong'), dict(journal_fault_lines_during_probe=['Fault response']),
                    dict(end_utc='2026-10-08 16:00:01 UTC'), dict(end_utc='bad'),
                    dict(start_utc='2026-10-08 14:32:00 UTC')]
        for changes in variants:
            with self.subTest(changes=changes), self.assertRaises(RuntimeError):
                self.admit(OLD, dict(receipt(), **changes))
        for seconds in (6*3600, 6*3600+1):
            with self.subTest(seconds=seconds), self.assertRaisesRegex(RuntimeError, '6 hours'):
                self.admit(OLD, receipt(), screen.parse_utc(receipt()['end_utc']) + dt.timedelta(seconds=seconds))
        self.admit(OLD, receipt(), screen.parse_utc(receipt()['end_utc']) + dt.timedelta(hours=6, microseconds=-1))

    def test_each_card_evidence_rechecked(self):
        for i in range(4):
            for key, value in [('pass', False), ('device', 'xpu:0' if i else 'xpu:3'),
                               ('copy_roundtrip_exact', False), ('gemm_repeat_exact', False),
                               ('gemm_fp32_max_abs_err', .01), ('gemm_bf16_max_abs_err', 5.),
                               ('gemm_fp32_max_abs_err', float('nan')),
                               ('gemm_fp32_max_abs_err', float('-inf'))]:
                health = copy.deepcopy(receipt())
                health['cards'][i][key] = value
                with self.subTest(card=i, key=key), self.assertRaises(RuntimeError):
                    self.admit(OLD, health)

    def test_journal_admission_saves_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            path = run / 'input.json'
            path.write_text(json.dumps(receipt()))
            args = SimpleNamespace(run_dir=run, health_receipt=path)
            with patch.object(screen, 'journal', return_value=OLD+DELETED), \
                 patch.object(screen, 'admit_journal', wraps=screen.admit_journal) as gate, \
                 patch.object(screen, 'verify_health_receipt', return_value=screen.parse_utc(receipt()['end_utc'])):
                screen.journal_admission(args)
            self.assertEqual((run / 'journal-admitted-faults.txt').read_text(), OLD)
            self.assertEqual((run / 'health-receipt.json').read_bytes(), path.read_bytes())
            self.assertTrue((run / 'health-receipt.sha256').is_file())
            self.assertTrue(gate.call_args.kwargs['boot_id'])

    def test_live_watcher_ignores_admitted_history_stops_on_new_fault(self):
        cutoff = self.admit(OLD, receipt())[1]
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(screen.shutil, 'disk_usage', return_value=SimpleNamespace(free=100*screen.GIB)), \
             patch.object(screen, 'sample_memory', return_value={}), \
             patch.object(screen, 'trip_reason', return_value=None), \
             patch.object(screen, 'journal', return_value=OLD+DELETED) as journal:
            screen.check_live(Path(tmp), cutoff)
            journal.return_value += line('16:01:00', 'Fault response')
            with self.assertRaisesRegex(RuntimeError, 'GPU fault'):
                screen.check_live(Path(tmp), cutoff)
            self.assertIn('16:01:00', (Path(tmp) / 'kernel-latest.log').read_text())

    def test_recovered_run_postflight_and_new_fault_graceful_stop(self):
        for new_fault in (False, True):
            with self.subTest(new_fault=new_fault):
                commands = []
                class Process:
                    returncode = 0
                    def __init__(self, server=False): self.server = server
                    def poll(self): return None if self.server and not commands else 0
                    def wait(self, timeout): return 0
                class Response(io.BytesIO):
                    status = 200
                def fake_run(command, **kwargs):
                    commands.append(command)
                    return SimpleNamespace(returncode=0, stdout=docker_status(command, commands), stderr='')
                text = OLD + DELETED + (line('16:01:00', 'Fault response') if new_fault else '')
                cutoff = self.admit(OLD, receipt())[1]
                responses = [Response(b''), Response(b'{"data":[{"id":"qwen38-flash-next-fp8-tp4"}]}'),
                             Response(b'# metrics'), Response(b'# metrics')]
                with tempfile.TemporaryDirectory() as tmp, \
                     patch.object(screen, 'preflight', return_value=cutoff), patch.object(screen, 'call'), \
                     patch.object(screen, 'collect_observations', return_value={}), \
                     patch.object(screen, 'MemoryWatchdog') as watchdog, patch.object(screen, 'idle'), \
                     patch.object(screen, 'sample_memory', return_value={}), \
                     patch.object(screen, 'trip_reason', return_value=None), \
                     patch.object(screen.shutil, 'disk_usage', return_value=SimpleNamespace(free=100*screen.GIB)), \
                     patch.object(screen, 'journal', return_value=text), patch.object(screen.signal, 'signal'), \
                     patch.object(screen.subprocess, 'Popen', side_effect=[Process(True), Process()]) as popen, \
                     patch.object(screen.subprocess, 'run', side_effect=fake_run), \
                     patch.object(screen, 'DeferredStop', side_effect=lambda run, name: DeferredStop(run, name, runner=fake_run)), \
                     patch.object(screen.urllib.request, 'urlopen', side_effect=responses):
                    write_rank_receipts(tmp)
                    watchdog.return_value.check.return_value = None
                    args = SimpleNamespace(mode='mtp1', port=19988)
                    if new_fault:
                        with self.assertRaisesRegex(RuntimeError, 'Fault recorded'):
                            screen.supervise_locked(args, Path(tmp))
                        self.assertEqual(popen.call_count, 1)  # no request client starts
                    else:
                        screen.supervise_locked(args, Path(tmp))
                    self.assertEqual((Path(tmp) / 'kernel-postflight.log').read_text(), text)
                stops = [c for c in commands if c[:2] == ['docker', 'kill']]
                self.assertEqual(len(stops), 1)
                self.assertIn('--signal=SIGINT', stops[0])
                self.assertFalse(any('SIGKILL' in str(c) for c in commands))

    def test_cli_passes_absolute_receipt_to_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = ['screen.py', 'run', '--mode', 'calibrate-load', '--run-dir', str(Path(tmp)/'fresh'),
                    '--health-receipt', 'synthetic-health.json', '--execute']
            with patch.object(screen.sys, 'argv', args), patch.object(screen, 'preflight'), \
                 patch.object(screen, 'overlay_check'), patch.object(screen, 'call') as call, \
                 contextlib.redirect_stdout(io.StringIO()):
                screen.main()
            command = call.call_args.args[0]
            self.assertEqual(command[command.index('--health-receipt')+1], str(Path('synthetic-health.json').resolve()))

    def test_preflight_checks_receipt(self):
        args = SimpleNamespace(mode='calibrate-load', port=19988)
        with patch.object(screen.socket, 'gethostname', return_value='steve-b70s'), \
             patch.object(screen, 'call', return_value=SimpleNamespace(stdout='main')), \
             patch.object(screen, 'storage'), patch.object(screen, 'overlay_check'), \
             patch.object(screen, 'memory_prediction'), patch.object(screen, 'idle'), \
             patch.object(screen.socket, 'socket'), patch.object(screen.calibration, 'trip_reason'), \
             patch.object(screen.calibration, 'parse_meminfo'), \
             patch.object(screen, 'journal_admission', side_effect=RuntimeError('receipt refused')) as gate:
            screen.calibration.trip_reason.return_value = None
            with self.assertRaisesRegex(RuntimeError, 'receipt refused'):
                screen.preflight(args)
            gate.assert_called_once_with(args)


if __name__ == '__main__':
    unittest.main()

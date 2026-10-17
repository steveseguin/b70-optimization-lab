"""CPU-only protocol, fdinfo, topology and seal-time integration regressions."""
import ast
import functools
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import chain_devices as D
import drain_gate as G
import lane_admission as L
import recipe
import window_adapter as W

HERE = Path(__file__).resolve().parent


@functools.lru_cache()
def reference_sources(group='sources'):
    # Other coordinators can work concurrently. Never test against mutable
    # live packet bytes or copy/write anything into their active directory.
    pin = json.loads((HERE / 'reference.json').read_text())
    sources = {}
    for name, item in pin[group].items():
        data = subprocess.run(['git', 'show', pin['revision'] + ':' + item['path']],
                              cwd=HERE, capture_output=True, check=True, timeout=10).stdout
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('pinned recipe reference differs')
        sources[name] = data.decode()
    return sources


class Clock:
    def __init__(self):
        self.value = 100.

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class Files(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='chain-admission-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.proc = self.root / 'proc'
        self.proc.mkdir()
        self.clock = Clock()

    def pid(self, pid=101, start=77, state='S'):
        path = self.proc / str(pid)
        (path / 'fdinfo').mkdir(parents=True, exist_ok=True)
        (path / 'stat').write_text(f'{pid} (name with ) spaces) ' +
                                  ' '.join([state] + ['0'] * 18 + [str(start)] + ['0'] * 10))
        return path

    def fd(self, pid=101, pci=D.LANES['A'][0], fd=3, driver='xe'):
        if not (self.proc / str(pid) / 'stat').exists():
            self.pid(pid)
        path = self.proc / str(pid) / 'fdinfo' / str(fd)
        path.write_text(f'drm-driver: {driver}\ndrm-pdev: {pci}\ndrm-client-id: 9\n')
        return path

    def lease(self, lane='A', window='WS128', **kwargs):
        return L.Reservation(lane, window=window, root=self.root / 'coord',
                             now=self.clock.now, sleep=self.clock.sleep,
                             wait_seconds=2, **kwargs)


class DeviceTests(Files):
    def test_closed_native_mask_and_native_indices(self):
        for lane, prefix in [('A', '0000:2'), ('B', '0000:4')]:
            env = D.mask_native({'OMP_NUM_THREADS': '2'}, lane)
            self.assertEqual(env['FilterBdfPath'], prefix)
            self.assertEqual(env['ZE_AFFINITY_MASK'], '0,1')
            self.assertEqual(env['ONEAPI_DEVICE_SELECTOR'], 'level_zero:0,1')
            self.assertEqual(env['NEOReadDebugKeys'], '1')
        for bad in ({'LD_PRELOAD': '/bad'}, {'FilterBdfPath': '0000:4'},
                    {'SECRET': 'never-print-this-value'}):
            with self.assertRaises(ValueError) as caught:
                D.mask_native(bad)
            self.assertNotIn('never-print-this-value', str(caught.exception))

    def test_private_home_never_reuses_config_or_cache(self):
        home = self.root / 'private'
        env = D.private_home({'HOME': '/untrusted'}, home)
        self.assertEqual(env['HOME'], str(home))
        self.assertEqual(list(home.iterdir()), [])
        (home / 'igdrcl.config').write_text('bad')
        with self.assertRaises(FileExistsError):
            D.private_home({}, home)

    def test_process_identity_comm_and_zombie(self):
        self.pid(start=2468)
        self.assertEqual(D.process_identity(101, self.proc), 2468)
        self.pid(state='Z')
        self.assertIsNone(D.process_identity(101, self.proc))
        self.assertIsNone(D.process_identity(999, self.proc))

    def test_idle_a_client_refuses_even_without_engine_counters(self):
        self.fd()
        for scope in ('lane-A', 'whole-host'):
            with self.assertRaisesRegex(ValueError, 'foreign Xe'):
                D.admit_clients(scope, self.proc)

    def test_b_client_allowed_only_in_a_exactness_scope(self):
        self.fd(pci=D.LANES['B'][0])
        self.assertEqual(len(D.admit_clients('lane-A', self.proc)['other']), 1)
        for scope in ('lane-B', 'whole-host'):
            with self.assertRaises(ValueError):
                D.admit_clients(scope, self.proc)

    def test_unmasked_b_process_with_an_a_fd_refuses(self):
        self.fd(pci=D.LANES['B'][0])
        self.fd(pci=D.LANES['A'][1], fd=4)
        with self.assertRaises(ValueError):
            D.admit_clients('lane-A', self.proc)

    def test_unknown_pci_missing_driver_and_non_xe(self):
        for pci, driver in [('', 'xe'), ('0000:99:00.0', 'xe'), (D.LANES['B'][0], '')]:
            self.fd(pci=pci, driver=driver)
            with self.assertRaises(ValueError):
                D.admit_clients('lane-A', self.proc)
        self.fd(pci='unrelated', driver='ast')
        self.assertFalse(D.admit_clients('whole-host', self.proc)['blocked'])

    def test_exemptions_are_start_tick_bound(self):
        self.fd()
        self.assertFalse(D.admit_clients('whole-host', self.proc, {101: 77})['blocked'])
        with self.assertRaises(ValueError):
            D.admit_clients('whole-host', self.proc, {101: 78})

    def test_hidden_foreign_clients_are_explicit_own_clients_refuse(self):
        self.pid()
        with patch.object(D, 'xe_fds', side_effect=PermissionError('hidden')):
            result = D.admit_clients('lane-A', self.proc)
            self.assertEqual(result['inaccessible_processes'], 1)
            self.assertTrue(result['hidden_clients_require_coordinator_ownership'])
            with self.assertRaises(PermissionError):
                D.DeviceMonitor(proc=self.proc).register(101)

    def test_multiple_serial_fixture_owners_proved_and_retired(self):
        monitor = D.DeviceMonitor(proc=self.proc)
        for pid in range(101, 107):
            self.fd(pid=pid)
            monitor.register(pid)
            shutil.rmtree(self.proc / str(pid))
            monitor.poll(force=True)
        monitor.finish()
        self.assertEqual(len(monitor.owners), 6)
        self.assertTrue(all(r['seen'] and r['exited'] for r in monitor.owners.values()))

    def test_startup_empty_but_ready_requires_mapped_ranks(self):
        monitor = D.DeviceMonitor(proc=self.proc)
        for pid in (101, 102):
            self.pid(pid)
            monitor.register(pid)
        with self.assertRaisesRegex(ValueError, 'mapped device'):
            monitor.ready([101, 102])
        self.fd(pid=101, pci=D.LANES['A'][0])
        self.fd(pid=102, pci=D.LANES['A'][1])
        monitor.ready([101, 102])
        self.assertEqual(monitor.ready_checks, 1)
        with self.assertRaises(ValueError):
            monitor.ready([102, 101])

    def test_wrong_or_late_device_handle_is_retained_and_refused(self):
        self.fd()
        monitor = D.DeviceMonitor(proc=self.proc)
        monitor.register(101)
        self.fd(pci=D.LANES['B'][0], fd=4)
        with self.assertRaisesRegex(ValueError, 'foreign or unidentified'):
            monitor.poll(force=True)
        self.assertEqual(monitor.owners[101]['fds'][-1]['pci'], D.LANES['B'][0])

    def test_pid_reuse_and_missing_proof_refuse(self):
        self.pid()
        monitor = D.DeviceMonitor(proc=self.proc)
        monitor.register(101)
        self.pid(start=78)
        with self.assertRaisesRegex(ValueError, 'PID reused'):
            monitor.poll(force=True)
        self.pid(start=77)
        shutil.rmtree(self.proc / '101')
        with self.assertRaisesRegex(ValueError, 'without observed'):
            monitor.poll(force=True)
        with self.assertRaises(ValueError):
            monitor.finish()

    def test_finish_requires_exited_owners(self):
        self.fd()
        monitor = D.DeviceMonitor(proc=self.proc)
        monitor.register(101)
        with self.assertRaisesRegex(ValueError, 'still live'):
            monitor.finish()

    def topology(self):
        by_path, sys_drm, dev = [self.root / x for x in ('by-path', 'sys-drm', 'dev')]
        for directory in (by_path, sys_drm, dev):
            directory.mkdir()
        driver = self.root / 'drivers/xe'
        driver.mkdir(parents=True)
        for index, pci in enumerate(D.LANES['A'] + D.LANES['B']):
            node = dev / f'renderD{128 + index}'
            node.touch()
            (by_path / f'pci-{pci}-render').symlink_to(node)
            device = self.root / 'pci' / pci
            device.mkdir(parents=True)
            (device / 'driver').symlink_to(driver)
            (sys_drm / node.name).mkdir()
            (sys_drm / node.name / 'device').symlink_to(device)
        return dict(by_path=by_path, sys_drm=sys_drm, dev_dri=dev, cwd=self.root)

    def test_topology_exact_pair_without_opening_nodes(self):
        kwargs = self.topology()
        for lane in 'AB':
            row = D.topology_admit(lane, **kwargs)
            self.assertEqual([r['pci'] for r in row['nodes']], list(D.LANES[lane]))
            self.assertFalse(row['device_nodes_opened'])
        (self.root / 'igdrcl.config').write_text('bad')
        with self.assertRaisesRegex(ValueError, 'debug configuration'):
            D.topology_admit(**kwargs)

    def test_topology_missing_extra_and_wrong_driver_refuse(self):
        kwargs = self.topology()
        node = kwargs['by_path'] / f'pci-{D.LANES["A"][0]}-render'
        node.unlink()
        with self.assertRaises(ValueError):
            D.topology_admit(**kwargs)
        node.symlink_to(kwargs['dev_dri'] / 'renderD128')
        (kwargs['by_path'] / 'pci-0000:29:00.0-render').symlink_to(kwargs['dev_dri'] / 'renderD128')
        with self.assertRaises(ValueError):
            D.topology_admit(**kwargs)


class ProtocolTests(Files):
    def test_all_chain_windows_have_explicit_policy(self):
        for window in ('K0', 'K1a', 'K1b', 'K2', 'KD', 'W0p', 'WS', 'WS128x'):
            self.assertEqual(L.window_scope(window), 'lane-A')
            self.assertEqual(L.window_scope(window, timing_claim=True), 'whole-host')
        for window in ('WS128', 'WSs', 'W2m', 'W2m-speed', 'WS64'):
            self.assertEqual(L.window_scope(window, timing_claim=False), 'whole-host')
        with self.assertRaisesRegex(ValueError, 'unregistered'):
            L.window_scope('NEW')

    def test_exactness_allows_existing_b_and_new_b(self):
        with self.lease('A', 'WS128x') as a:
            self.assertFalse(a.hold.exists())
            with self.lease('B') as b:
                b.complete(drained=True)
            a.complete(drained=True)

    def test_hold_is_published_before_waiting_for_current_b(self):
        with self.lease('B') as b:
            a = self.lease()
            observed = []
            def finish_current(seconds):
                observed.append(a.hold.exists())
                self.assertEqual(json.loads(a.hold.read_text())['window'], 'WS128')
                b.complete(drained=True)
                self.clock.sleep(seconds)
            a.sleep = finish_current
            with a:
                self.assertTrue(observed and all(observed))
                self.assertTrue(a.hold.exists())
                a.complete(drained=True)
            self.assertFalse(a.hold.exists())

    def test_new_b_waits_until_timing_window_completes(self):
        with self.lease() as a:
            b = self.lease('B')
            called = []
            def finish_a(seconds):
                called.append(True)
                self.assertFalse(b.active.exists())
                a.complete(drained=True)
                self.clock.sleep(seconds)
            b.sleep = finish_a
            with b:
                self.assertTrue(called)
                b.complete(drained=True)

    def test_completion_releases_locks_before_context_exit(self):
        with self.lease() as a:
            a.complete(drained=True)
            with self.lease('B') as b:
                b.complete(drained=True)
            with self.lease('A', 'WS') as next_a:
                next_a.complete(drained=True)

    def test_failure_retains_hold_and_blocks_next_chain(self):
        with self.assertRaisesRegex(RuntimeError, 'simulated'):
            with self.lease() as a:
                raise RuntimeError('simulated')
        self.assertTrue(a.hold.exists())
        self.assertTrue(a.active.exists())
        with self.assertRaises(ValueError):
            with self.lease('A', 'WS'):
                self.fail('stale A admitted')
        with self.assertRaisesRegex(ValueError, 'timed out'):
            with self.lease('B'):
                self.fail('held B admitted')

    def test_b_crash_does_not_look_like_drained_screen(self):
        with self.lease('B'):
            pass  # no explicit complete
        with self.assertRaisesRegex(ValueError, 'did not confirm drain'):
            with self.lease():
                self.fail('stale B admitted')

    def test_timeout_does_not_kill_or_remove_current_b(self):
        with self.lease('B') as b:
            with self.assertRaisesRegex(ValueError, 'timed out'):
                with self.lease():
                    self.fail('busy B admitted')
            self.assertTrue(b.active.exists())
            self.assertTrue(b.hold.exists())
            b.complete(drained=True)

    def test_cancel_wait_is_bounded_and_leaves_timing_hold(self):
        with self.lease('B') as b:
            a = self.lease()
            def check():
                if a.hold.exists():
                    raise RuntimeError('fresh fault')
            a.check = check
            with self.assertRaisesRegex(RuntimeError, 'fresh fault'):
                a.__enter__()
            self.assertTrue(a.hold.exists())
            b.complete(drained=True)

    def test_never_remove_another_owners_hold(self):
        with self.lease() as a:
            other = dict(a.record, token='another-owner')
            L.atomic_json(a.hold, other)
            with self.assertRaisesRegex(ValueError, 'owner changed'):
                a.complete(drained=True)
            self.assertEqual(json.loads(a.hold.read_text()), other)
            self.assertTrue(a.active.exists())

    def test_no_completion_without_explicit_drain(self):
        with self.lease() as a:
            with self.assertRaisesRegex(ValueError, 'completed drain'):
                a.complete(drained=False)
            self.assertTrue(a.hold.exists())

    def test_dangling_flag_is_a_hold(self):
        root = self.root / 'coord'
        root.mkdir(mode=0o700)
        (root / 'hold-lane-B').symlink_to(root / 'missing')
        with self.assertRaisesRegex(ValueError, 'timed out'):
            self.lease('B').__enter__()

    def test_real_process_crash_leaves_marker_after_flock_releases(self):
        # CPU child exits itself; no GPU, kill, service or real protocol root.
        program = ('import os; from pathlib import Path; from lane_admission import Reservation; '
                   f'r=Reservation("B", root=Path({str(self.root / "coord")!r})); '
                   'r.__enter__(); os._exit(0)')
        subprocess.run([sys.executable, '-B', '-c', program], cwd=HERE, check=True, timeout=5)
        with self.assertRaisesRegex(ValueError, 'did not confirm drain'):
            self.lease().__enter__()


class DrainTests(Files):
    def permit(self, **kwargs):
        return G.DrainPermit(self.root / 'evidence', root=self.root,
                             now=self.clock.now, sleep=self.clock.sleep, **kwargs)

    def test_v3_state_compatibility_and_sixty_second_gap(self):
        with self.permit() as first:
            first.complete()
        finished = self.clock.now()
        with self.permit() as second:
            self.assertGreaterEqual(self.clock.now(), finished + 60)
            self.assertFalse(json.loads((self.root / 'teardown-state.json').read_text())['drained'])
            second.complete()

    def test_incomplete_shared_drain_refuses(self):
        with self.permit():
            pass
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            self.permit().__enter__()

    def test_waiting_for_drain_observes_fault_check(self):
        with self.permit():
            def check():
                raise RuntimeError('fresh fault')
            with self.assertRaisesRegex(RuntimeError, 'fresh fault'):
                self.permit(check=check).__enter__()

    def test_b_can_start_computing_under_live_exactness_drain_permit(self):
        with self.lease('A', 'K2') as a, self.permit(reservation=a.record) as drain:
            with self.lease('B') as b:
                G.screen_teardown_admit('B', root=self.root, coordination_root=a.root)
                # Permission to compute never releases the actual drain lock.
                with self.assertRaisesRegex(ValueError, 'wait timed out'):
                    self.permit(wait_seconds=1).__enter__()
                drain.complete()
                b.complete(drained=True)
            a.complete(drained=True)

    def test_live_exception_cannot_admit_a_or_unregistered_b(self):
        with self.lease('A', 'K2') as a, self.permit(reservation=a.record):
            with self.assertRaisesRegex(ValueError, 'only registered B'):
                G.screen_teardown_admit('A', root=self.root, coordination_root=a.root)
            with self.assertRaises(FileNotFoundError):
                G.screen_teardown_admit('B', root=self.root, coordination_root=a.root)

    def test_live_exception_refuses_released_lock_and_dead_or_reused_pid(self):
        with self.lease('A', 'K2') as a, self.lease('B') as b:
            with self.permit(reservation=a.record):
                with patch.object(G, 'process_identity', return_value=None):
                    with self.assertRaisesRegex(ValueError, 'owner gone'):
                        G.screen_teardown_admit('B', root=self.root, coordination_root=a.root)
            with self.assertRaisesRegex(ValueError, 'not locked'):
                G.screen_teardown_admit('B', root=self.root, coordination_root=a.root)
            b.complete(drained=True)

    def test_live_exception_refuses_wrong_reservation_token(self):
        with self.lease('A', 'K2') as a, self.permit(reservation=a.record), self.lease('B') as b:
            path = self.root / 'teardown-state.json'
            row = json.loads(path.read_text())
            row['chain_reservation']['token'] = 'different'
            L.atomic_json(path, row)
            with self.assertRaisesRegex(ValueError, 'not this live A'):
                G.screen_teardown_admit('B', root=self.root, coordination_root=a.root)
            b.complete(drained=True)

    def test_live_exception_requires_b_lock_as_well_as_marker(self):
        with self.lease('A', 'K2') as a, self.permit(reservation=a.record), self.lease('B') as b:
            b._close()  # simulate lost lock with an intact live-PID marker
            with self.assertRaisesRegex(ValueError, 'not locked'):
                G.screen_teardown_admit('B', root=self.root, coordination_root=a.root)

    def test_a_completion_cannot_remove_marker_during_b_snapshot(self):
        with self.lease('A', 'K2') as a, self.permit(reservation=a.record) as drain, self.lease('B') as b:
            a.sleep = time.sleep
            state = self.root / 'teardown-state.json'
            original = Path.read_text
            wrote, finished = threading.Event(), threading.Event()
            errors, threads = [], []
            def complete_a():
                try:
                    drain.complete()
                    wrote.set()
                    a.complete(drained=True)
                except BaseException as error:
                    errors.append(error)
                finally:
                    finished.set()
            def read(path, *args, **kwargs):
                data = original(path, *args, **kwargs)
                if path == state and not threads:
                    thread = threading.Thread(target=complete_a)
                    threads.append(thread)
                    thread.start()
                    self.assertTrue(wrote.wait(2))
                    self.assertFalse(finished.is_set())
                return data  # stale drained=False snapshot must still be safe
            try:
                with patch.object(Path, 'read_text', read):
                    G.screen_teardown_admit('B', root=self.root, coordination_root=a.root)
            finally:
                for thread in threads:
                    thread.join(2)
            self.assertTrue(finished.is_set())
            self.assertEqual(errors, [])
            b.complete(drained=True)


class AdapterTests(Files):
    def admission(self, window='WS128'):
        return W.WindowAdmission(window, self.root / 'admission.json', root=self.root / 'coord',
                                 proc=self.proc, topology=lambda lane: {'lane': lane},
                                 drain_root=self.root)

    def complete_model(self, admission):
        for rank, pid in enumerate((101, 102)):
            self.fd(pid=pid, pci=D.LANES['A'][rank])
            admission.register(pid)
        admission.ready([101, 102])
        for pid in (101, 102):
            shutil.rmtree(self.proc / str(pid))

    def test_timing_receipt_binds_completed_isolation(self):
        with self.admission() as a:
            self.complete_model(a)
            path = self.root / 'window.json'
            L.atomic_json(path, dict(passed=True, window='WS128', boot_id=a.lease.record['boot_id'],
                                     launched_pids=[101, 102]))
            W.bind_receipt(path, a)
            row = json.loads(path.read_text())
            proof = W.verify_receipt(row)
            self.assertTrue(proof['passed'])
            self.assertTrue(proof['timing_claim_eligible'])
            self.assertTrue(proof['shared_drain']['drained'])
            self.assertFalse(a.lease.hold.exists())
            changed = dict(row, build_receipt_sha256='other-chain')
            with self.assertRaisesRegex(ValueError, 'different window receipt'):
                W.verify_receipt(changed)
            a.evidence.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'evidence changed'):
                W.verify_receipt(row)

    def test_final_admission_failure_invalidates_window(self):
        with self.admission() as a:
            path = self.root / 'window.json'
            L.atomic_json(path, dict(passed=True, window='WS128'))
            with self.assertRaises(ValueError):
                W.bind_receipt(path, a)
            self.assertFalse(json.loads(path.read_text())['passed'])
            self.assertTrue(a.lease.hold.exists())

    def test_ready_hook_cannot_be_omitted(self):
        with self.admission() as a:
            self.fd()
            a.register(101)
            shutil.rmtree(self.proc / '101')
            with self.assertRaisesRegex(ValueError, 'READY proof'):
                a.complete()

    def test_late_foreign_client_invalidates_timing(self):
        with self.admission() as a:
            self.fd(pci=D.LANES['B'][0])
            with self.assertRaisesRegex(ValueError, 'during window'):
                a.check()
            saved = json.loads(a.evidence.read_text())
            self.assertEqual(saved['clients_latest']['blocked'][0]['pci'], D.LANES['B'][0])

    def test_exactness_admits_b_and_cannot_claim_speed(self):
        self.fd(pid=999, pci=D.LANES['B'][0])
        with self.admission('WS128x') as a:
            self.complete_model(a)
            a.check()
            a.complete()
            self.assertFalse(a.record['timing_claim_eligible'])
            self.assertTrue((self.proc / '999').exists())

    def test_unfinished_receipt_cannot_pass_prerequisite(self):
        with self.assertRaisesRegex(ValueError, 'missing completed'):
            W.verify_receipt(dict(passed=True, window='WS128'))

    def screen_result(self, output, **overrides):
        output.mkdir()
        row = dict(schema='own-runtime.screen.window.v3', lane='B', passed=True,
                   device_executed=True, child_still_running=False,
                   pid=101, process_start_ticks=77)
        row.update(overrides)
        L.atomic_json(output / 'window.json', row)
        L.atomic_json(output / 'summary.json', dict(passed=True, device_isolation=dict(passed=True)))
        return 0

    def test_lane_b_hook_wraps_one_fresh_screen_and_confirms_drain(self):
        output = self.root / 'screen'
        def run():
            marker = self.root / 'coord/active-lane-B.json'
            self.assertTrue(marker.exists())
            return self.screen_result(output)
        result = W.run_lane_b_screen(run, output, wait_check=lambda: None,
                                    root=self.root / 'coord', proc=self.proc)
        self.assertEqual(result, 0)
        self.assertFalse((self.root / 'coord/active-lane-B.json').exists())
        self.assertTrue(json.loads((output / 'lane-coordination.json').read_text())['passed'])

    def test_lane_b_hook_keeps_marker_on_failure_or_retained_owner(self):
        output = self.root / 'screen'
        with self.assertRaisesRegex(ValueError, 'successful drain'):
            W.run_lane_b_screen(lambda: self.screen_result(output, child_retained=True), output,
                                wait_check=lambda: None, root=self.root / 'coord', proc=self.proc)
        self.assertTrue((self.root / 'coord/active-lane-B.json').exists())

    def test_lane_b_hook_nonzero_return_never_releases(self):
        output = self.root / 'screen'
        self.assertEqual(W.run_lane_b_screen(lambda: 75, output, wait_check=lambda: None,
                                             root=self.root / 'coord', proc=self.proc), 75)
        self.assertTrue((self.root / 'coord/active-lane-B.json').exists())

    def test_lane_b_hook_refuses_live_worker_even_if_receipt_claims_success(self):
        output = self.root / 'screen'
        self.pid()
        with self.assertRaisesRegex(ValueError, 'worker still alive'):
            W.run_lane_b_screen(lambda: self.screen_result(output), output, wait_check=lambda: None,
                                root=self.root / 'coord', proc=self.proc)

    def test_lane_b_hook_refuses_foreign_b_client_after_screen(self):
        output = self.root / 'screen'
        self.fd(pid=999, pci=D.LANES['B'][0])
        with self.assertRaisesRegex(ValueError, 'foreign Xe'):
            W.run_lane_b_screen(lambda: self.screen_result(output), output, wait_check=lambda: None,
                                root=self.root / 'coord', proc=self.proc)

    def test_lane_b_hook_refuses_reused_output_before_calling_driver(self):
        output = self.root / 'screen'
        output.mkdir()
        with self.assertRaisesRegex(ValueError, 'fresh screen'):
            W.run_lane_b_screen(lambda: self.fail('driver called'), output, wait_check=lambda: None,
                                root=self.root / 'coord', proc=self.proc)


class RecipeTests(Files):
    def test_retained_patch_matches_render_and_applies_in_scratch_only(self):
        retained = HERE / 'integration.patch'
        self.assertEqual(retained.read_text(), recipe.render_sources(reference_sources()))
        for name in ('window.py', 'pipeline.py', 'queue_runner.py'):
            (self.root / name).write_text(reference_sources()[name])
        subprocess.run(['git', 'apply', '--check', str(retained)], cwd=self.root, check=True, timeout=5)
        subprocess.run(['git', 'apply', str(retained)], cwd=self.root, check=True, timeout=5)
        for name in ('window.py', 'pipeline.py', 'queue_runner.py'):
            code = (self.root / name).read_text()
            self.assertEqual(code, recipe.transform(name, reference_sources()[name]))
            ast.parse(code)

    def test_every_native_execution_site_uses_masked_private_environment(self):
        code = recipe.transform('window.py', reference_sources()['window.py'])
        self.assertIn("environment['native']=mask_native(environment['native'])", code)
        self.assertIn("native_env=private_home(environment['native'],out/'driver-home')", code)
        for call in ('run_draft(a,out,', 'run_fixtures(a,out,', 'concurrency_canary(args,out,', 'pp.run(args,'):
            self.assertNotIn(call + "environment['native']", code)
            self.assertIn(call + 'native_env', code)
        self.assertNotIn('def foreign_engines', code)
        self.assertIn('if self.admission:self.admission.register(int(pid))', code)
        self.assertIn('if self.admission:self.admission.check()', code)
        self.assertIn('if not cpu_rehearsal:verify_receipt(row)', code)

    def test_ready_hook_is_after_ready_before_first_request(self):
        code = recipe.transform('pipeline.py', reference_sources()['pipeline.py'])
        self.assertLess(code.index('self.receive(rank,args.seconds,ready=True)'), code.index('args.lane_ready('))
        self.assertIn('rank_home=out/"driver-cache"', code)
        self.assertNotIn('rank_home=P/"build"', code)

    def test_changed_reference_fails_loudly(self):
        with self.assertRaises(ValueError):
            recipe.transform('window.py', 'different source')
        source = reference_sources()['window.py'].replace('class Watch:', 'def extra():\n    pass\nclass Watch:')
        with self.assertRaisesRegex(ValueError, 'boundary changed'):
            recipe.transform('window.py', source)
        source = reference_sources('screen_sources')['conditions.py'] + '\ndef extra():\n    pass\n'
        self.assertIn('def extra():', recipe.transform_screen('conditions.py', source))

    def test_future_b_patch_applies_only_to_scratch_and_keeps_shared_gate(self):
        sources = reference_sources('screen_sources')
        retained = HERE / 'screen-integration.patch'
        self.assertEqual(retained.read_text(), recipe.render_screen_sources(sources))
        for name, source in sources.items():
            (self.root / name).write_text(source)
        subprocess.run(['git', 'apply', '--check', str(retained)], cwd=self.root, check=True, timeout=5)
        subprocess.run(['git', 'apply', str(retained)], cwd=self.root, check=True, timeout=5)
        for name, source in sources.items():
            code = (self.root / name).read_text()
            self.assertEqual(code, recipe.transform_screen(name, source))
            ast.parse(code)
        conditions = (self.root / 'conditions.py').read_text()
        self.assertIn('root=DEFAULT_DRAIN_ROOT', conditions)
        self.assertIn("prior['completed_monotonic'] + 60.0", conditions)
        self.assertIn("require(prior.get('drained') is True", conditions)
        screen = (self.root / 'screen.py').read_text()
        self.assertIn('teardown_admit(args.lane)', screen)
        self.assertIn('return run_lane_b_screen(', screen)
        self.assertIn("DEFAULT_DRAIN_ROOT.glob('fault-'", screen)


if __name__ == '__main__':
    D.require(os.getpriority(os.PRIO_PROCESS, 0) == 19 and
              set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32)),
              'tests require nice19 and helper cores8-15,24-31')
    unittest.main()

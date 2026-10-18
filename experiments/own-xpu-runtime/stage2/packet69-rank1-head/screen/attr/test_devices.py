"""CPU-only ownership, mask, lineage and inherited safety regressions."""
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import common as C
import conditions as K
import devices as G
import screen


class DeviceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=C.HERE)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def fd(self, pid, fd, pci, driver='xe'):
        path = self.root / str(pid) / 'fdinfo' / str(fd)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'drm-driver: {driver}\ndrm-pdev: {pci}\ndrm-client-id: 42\n')
        return path

    def monitor(self, lane='B'):
        monitor = G.DeviceMonitor(lane, self.root, proc=self.root)
        return monitor

    def test_mask_is_fixed_and_remaps_both_lanes_to_zero_one(self):
        env = dict(PATH='/usr/bin:/bin', LD_LIBRARY_PATH='/approved', OMP_NUM_THREADS='2')
        for lane, prefix in (('A', '0000:2'), ('B', '0000:4')):
            actual = G.masked_environment(lane, env)
            self.assertEqual(actual['FilterBdfPath'], prefix)
            self.assertEqual(actual['ZE_AFFINITY_MASK'], '0,1')
            self.assertEqual(actual['ONEAPI_DEVICE_SELECTOR'], 'level_zero:0,1')
            self.assertEqual(G.masked_environment(lane, actual, inherited=True), actual)
            for override in ({'SECRET': 'do-not-log'}, {'ZE_AFFINITY_MASK': '0,1'},
                             {'FilterBdfPath': prefix}, {'LD_PRELOAD': '/bad'}):
                with self.assertRaises(ValueError) as caught:
                    G.masked_environment(lane, dict(env, **override))
                self.assertNotIn('do-not-log', str(caught.exception))
            with self.assertRaisesRegex(ValueError, 'mask changed'):
                G.masked_environment(lane, dict(actual, ZE_AFFINITY_MASK='2,3'), inherited=True)

    def test_ready_requires_both_ranks_and_only_lane_devices(self):
        # Each native runtime may enumerate both lane cards; that is allowed.
        for pid in (101, 102):
            for fd, pci in enumerate(K.LANES['B']['pci']):
                self.fd(pid, fd, pci)
            self.fd(pid, 9, 'unrelated', driver='other')
        with patch.object(C.SUPPORT, 'process_start', return_value=77):
            monitor = self.monitor()
            monitor.register(101)
            with self.assertRaisesRegex(ValueError, 'coverage unproven'):
                monitor.poll(ready=True)
            monitor.register(102)
            monitor.poll(ready=True)
        row = C.read(self.root / 'device-isolation.json')
        self.assertTrue(row['passed'])
        self.assertEqual([r['pid'] for r in row['ranks']], [101, 102])
        self.assertEqual(row['allowed_pci'], K.LANES['B']['pci'])
        self.assertTrue(all(len(r['fds']) == 2 for r in row['ranks']))

    def test_foreign_and_unidentified_devices_are_saved_then_refused(self):
        for foreign in ('0000:23:00.0', ''):
            self.fd(101, 3, foreign)
            with patch.object(C.SUPPORT, 'process_start', return_value=77):
                with self.assertRaisesRegex(ValueError, 'foreign or unidentified'):
                    self.monitor().register(101)
            row = C.read(self.root / 'device-isolation.json')
            self.assertFalse(row['passed'])
            self.assertEqual(row['ranks'][0]['fds'][0]['pci'], foreign)

    def test_empty_startup_allowed_but_ready_refused(self):
        (self.root / '101/fdinfo').mkdir(parents=True)
        (self.root / '102/fdinfo').mkdir(parents=True)
        with patch.object(C.SUPPORT, 'process_start', return_value=77):
            monitor = self.monitor()
            monitor.register(101)
            monitor.register(102)
            with self.assertRaisesRegex(ValueError, 'mapped device not observed'):
                monitor.poll(ready=True)
        self.assertFalse(C.read(self.root / 'device-isolation.json')['passed'])

    def test_live_missing_fdinfo_permission_failure_and_pid_reuse_refused(self):
        self.fd(101, 3, '0000:43:00.0')
        with patch.object(C.SUPPORT, 'process_start', return_value=77):
            monitor = self.monitor()
            monitor.register(101)
            with patch.object(G, 'rank_fds', side_effect=PermissionError('fdinfo hidden')):
                with self.assertRaisesRegex(ValueError, 'fdinfo hidden'):
                    monitor.poll(force=True)
        with patch.object(C.SUPPORT, 'process_start', return_value=78):
            with self.assertRaisesRegex(ValueError, 'PID gone or reused'):
                monitor.poll(force=True)
        with patch.object(C.SUPPORT, 'process_start', return_value=77):
            with self.assertRaises(ValueError):
                self.monitor().register(999)

    def test_new_foreign_fd_invalidates_previously_passing_record(self):
        self.fd(101, 3, '0000:43:00.0')
        self.fd(102, 3, '0000:47:00.0')
        with patch.object(C.SUPPORT, 'process_start', return_value=77):
            monitor = self.monitor()
            monitor.register(101)
            monitor.register(102)
            monitor.poll(ready=True)
            self.assertTrue(C.read(self.root / 'device-isolation.json')['passed'])
            self.fd(102, 4, '0000:27:00.0')
            with self.assertRaisesRegex(ValueError, 'foreign'):
                monitor.poll(force=True)
            self.assertFalse(C.read(self.root / 'device-isolation.json')['passed'])

    def test_fd_sampling_throttles_and_ready_forces_fresh_read(self):
        self.fd(101, 3, '0000:43:00.0')
        self.fd(102, 3, '0000:47:00.0')
        now = [0.]
        with patch.object(C.SUPPORT, 'process_start', return_value=77):
            monitor = G.DeviceMonitor('B', self.root, self.root, now=lambda: now[0])
            monitor.register(101)
            monitor.register(102)
            before = monitor.samples
            monitor.poll()
            self.assertEqual(monitor.samples, before)
            monitor.poll(ready=True)
            self.assertEqual(monitor.samples, before + 1)
            now[0] += .25
            monitor.poll()
            self.assertEqual(monitor.samples, before + 2)

    def topology(self, pcis):
        dri = self.root / 'dev/dri'
        by_path = dri / 'by-path'
        by_path.mkdir(parents=True, exist_ok=True)
        sys_drm = self.root / 'sys/class/drm'
        for index, pci in enumerate(pcis):
            node = dri / f'renderD{128 + index}'
            node.touch()
            (by_path / f'pci-{pci}-render').symlink_to(node)
            device = self.root / 'devices' / pci
            device.mkdir(parents=True)
            driver = self.root / 'drivers/xe'
            driver.mkdir(parents=True, exist_ok=True)
            (device / 'driver').symlink_to(driver)
            entry = sys_drm / node.name
            entry.mkdir(parents=True)
            (entry / 'device').symlink_to(device)
        return by_path, sys_drm, dri

    def test_prefilter_inventory_matches_exactly_without_opening_nodes(self):
        paths = self.topology(K.LANES['A']['pci'] + K.LANES['B']['pci'])
        # Only directory metadata and symlinks are needed; no node is opened.
        with patch.object(os, 'open', side_effect=AssertionError('device open')):
            for lane in ('A', 'B'):
                row = G.topology_admit(lane, *paths)
                self.assertEqual([r['pci'] for r in row['nodes']], K.LANES[lane]['pci'])
                self.assertFalse(row['device_nodes_opened'])
        (paths[0] / 'pci-0000:47:00.0-render').unlink()
        with self.assertRaisesRegex(ValueError, 'exactly the two'):
            G.topology_admit('B', *paths)

    def test_prefilter_refuses_extra_matching_device_and_no_bypath(self):
        paths = self.topology(K.LANES['B']['pci'] + ['0000:49:00.0'])
        with self.assertRaisesRegex(ValueError, 'exactly the two'):
            G.topology_admit('B', *paths)
        with self.assertRaisesRegex(ValueError, 'no unfiltered DRM fallback'):
            G.topology_admit('B', self.root / 'absent', paths[1], paths[2])

    def test_other_lane_clients_do_not_block_either_lane(self):
        for lane, foreign in (('A', 'B'), ('B', 'A')):
            self.fd(101, 3, K.LANES[foreign]['pci'][0])
            self.assertFalse(K.selected_clients(lane, self.root)['selected'])
            with self.assertRaises(ValueError):
                K.selected_clients(foreign, self.root)


    def test_5456_fence_and_pf_exiting_sensor_contract(self):
        for n in range(53, 58):
            path = self.root / f'memory{n}'
            path.mkdir()
            (path / 'state').write_text('offline' if n in (54, 56) else 'online')
        self.assertEqual(C.W.memory_fence(self.root)['53'], 'online')
        (self.root / 'memory56/state').write_text('online')
        with self.assertRaises(ValueError):
            C.W.memory_fence(self.root)
        for exiting in (False, True):
            with patch.object(C.SUPPORT, 'process_tree_anon', return_value=dict(root_seen=False, anonymous_bytes=0)), \
                 patch.object(C.SUPPORT, '_exited_status', return_value=exiting), \
                 patch.object(C.M, 'meminfo', return_value={'MemAvailable': 10 * C.M.GIB}):
                self.assertEqual(screen.memory_sensor(123, 'tp2', {})['root_seen'], exiting)

    def test_incident_and_all_128_tokens_are_required(self):
        for count in (64, 128):
            expected = list(range(128))
            C.compare_tokens(expected[:count], expected, count, 'oracle')
            for index in (0, count - 1):
                tokens = expected[:count]
                tokens[index] = -1
                with self.assertRaises(ValueError):
                    C.compare_tokens(tokens, expected, count, 'oracle')
            with self.assertRaises(ValueError):
                C.compare_tokens(expected[:count - 1], expected, count, 'oracle')


if __name__ == '__main__':
    unittest.main()

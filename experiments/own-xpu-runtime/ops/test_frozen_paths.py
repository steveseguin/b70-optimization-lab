"""Read-only frozen-list discovery; fixtures never touch real queues or /proc."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import frozen_paths as frozen


class FrozenTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.stage = self.root / 'experiments/own-xpu-runtime/stage2'
        self.queue = self.root / 'queue'
        self.queue.mkdir()
        self.coord = self.root / 'coord'
        self.coord.mkdir()
        self.proc = self.root / 'proc'

    def packet(self, number):
        packet = self.stage / f'packet{number}-test'
        packet.mkdir(parents=True)
        script = packet / 'runner.py'
        script.write_text('frozen')
        (packet / 'build-receipt.json').write_text(json.dumps({'sources': {
            str(script): hashlib.sha256(script.read_bytes()).hexdigest()}}))
        return packet, dict(name=f'p{number}-A', argv=['/usr/bin/python3', '-B', str(script)])

    def discover(self):
        return frozen.active_packets(self.root, self.queue, self.coord, self.proc)

    def test_union_queued_ready_inflight_and_symlink_targets(self):
        p1, j1 = self.packet(1)
        p2, _ = self.packet(2)
        p3, j3 = self.packet(3)
        self.packet(4)  # unqueued, unready packet must stay out
        (self.queue / 'queue-A.txt').write_text(json.dumps(j1) + '\n')
        (p2 / 'READY-FOR-DEVICE.json').write_text('{}')
        (self.queue / 'inflight-B.json').write_text(json.dumps({'job': j3}))
        target = self.root / 'immutable.py'
        target.write_text('frozen')
        (p2 / 'runner.py').unlink()
        (p2 / 'runner.py').symlink_to(target)
        before = (self.queue / 'queue-A.txt').read_bytes()
        packets, errors = self.discover()
        self.assertEqual(packets, {p1, p2, p3})
        paths, failures = frozen.frozen_paths(packets, self.root)
        self.assertFalse(errors + failures)
        self.assertIn(target, paths)
        self.assertIn(p2 / 'runner.py', paths)
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual((self.queue / 'queue-A.txt').read_bytes(), before)

    def test_running_reservation_owner_is_included_without_exposing_argv(self):
        packet, _ = self.packet(58)
        process = self.proc / '321'
        process.mkdir(parents=True)
        (process / 'stat').write_text('321 (python3) S ' + '0 ' * 18 + '987 0\n')
        (process / 'cmdline').write_bytes(b'python3\0-B\0' + str(packet / 'runner.py').encode() + b'\0--secret\0hidden\0')
        (self.coord / 'active-lane-A.json').write_text(json.dumps({'pid': 321, 'start_ticks': 987}))
        packets, errors = self.discover()
        self.assertEqual(packets, {packet})
        self.assertFalse(errors)

    def test_pid_reuse_does_not_freeze_unrelated_process(self):
        packet, _ = self.packet(58)
        process = self.proc / '321'
        process.mkdir(parents=True)
        (process / 'stat').write_text('321 (python3) S ' + '0 ' * 18 + '988 0\n')
        (process / 'cmdline').write_bytes(str(packet / 'runner.py').encode())
        (self.coord / 'active-lane-A.json').write_text(json.dumps({'pid': 321, 'start_ticks': 987}))
        self.assertEqual(self.discover()[0], set())

    def test_malformed_metadata_reports_incomplete_union(self):
        packet, job = self.packet(1)
        (self.queue / 'queue-A.txt').write_text(json.dumps(job) + '\n')
        (packet / 'build-receipt.json').write_text('{')
        packets, _ = self.discover()
        self.assertTrue(frozen.frozen_paths(packets, self.root)[1])


if __name__ == '__main__':
    unittest.main()

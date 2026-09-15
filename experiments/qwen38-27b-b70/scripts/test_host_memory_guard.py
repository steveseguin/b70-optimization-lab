"""CPU-only tests for the host-memory guard; no root, cgroups or Docker."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

spec = importlib.util.spec_from_file_location('host_memory_guard', Path(__file__).with_name('host_memory_guard.py'))
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
GIB = guard.GIB
ID = 'a' * 64


def meminfo(total=16, free=8, cached=4, anon=1, slab=0.5, available=13):
    kib = lambda gib: int(gib * 1024 * 1024)
    return '\n'.join([f'MemTotal: {kib(total)} kB', f'MemFree: {kib(free)} kB', f'MemAvailable: {kib(available)} kB',
                      f'Cached: {kib(cached)} kB', f'AnonPages: {kib(anon)} kB', f'Slab: {kib(slab)} kB',
                      'SwapFree: 1024 kB', 'HugePages_Total:       0']) + '\n'


class GuardTests(unittest.TestCase):
    def test_parse_and_unaccounted(self):
        info = guard.parse_meminfo(meminfo())
        self.assertEqual(info['HugePages_Total'], 0)
        self.assertEqual(guard.unaccounted_bytes(info), int(2.5 * GIB))

    def test_decide_thresholds(self):
        base = guard.unaccounted_bytes(guard.parse_meminfo(meminfo()))
        self.assertIsNone(guard.decide(guard.parse_meminfo(meminfo()), base))
        grown = guard.parse_meminfo(meminfo(free=3))  # 5 GiB more outside the counters
        self.assertIn('driver-held', guard.decide(grown, base))
        low = guard.parse_meminfo(meminfo(available=2))
        self.assertIn('available', guard.decide(low, base))

    def test_container_id_must_be_full_hex(self):
        for bad in ('abc', 'g' * 64, '../' + 'a' * 61):
            with self.assertRaises(ValueError):
                guard.cgroup_dir(bad)

    def run_guard(self, tmp, text, extra=(), prepare=None):
        root = Path(tmp)
        (root / 'meminfo').write_text(text)
        base = guard.unaccounted_bytes(guard.parse_meminfo(meminfo()))
        if prepare:
            prepare(root)
        args = ['--container-id', ID, '--out', str(root / 'out'), '--baseline-unaccounted', str(base),
                '--interval', '0.02', '--cgroup-root', str(root), '--meminfo', str(root / 'meminfo'), *extra]
        return guard.main(args), root

    def test_fires_and_kills_cgroup_once_container_seen(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, root = self.run_guard(tmp, meminfo(free=3), prepare=lambda r: (r / f'docker-{ID}.scope').mkdir())
            self.assertEqual(code, guard.FIRED_EXIT)
            self.assertEqual((root / f'docker-{ID}.scope' / 'cgroup.kill').read_text(), '1')
            receipt = json.loads((root / 'out' / 'MEMORY-GUARD.json').read_text())
            self.assertTrue(receipt['cgroup_kill'])
            self.assertIn('driver-held', receipt['reason'])

    def test_never_fires_before_container_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, root = self.run_guard(tmp, meminfo(available=1), extra=('--appear-timeout', '0.1'))
            self.assertEqual(code, 0)
            self.assertFalse((root / 'out' / 'MEMORY-GUARD.json').exists())

    def test_exits_quietly_when_container_disappears(self):
        with tempfile.TemporaryDirectory() as tmp:
            group = Path(tmp) / f'docker-{ID}.scope'
            group.mkdir()
            threading.Timer(0.15, group.rmdir).start()
            start = time.monotonic()
            code, root = self.run_guard(tmp, meminfo())
            self.assertEqual(code, 0)
            self.assertLess(time.monotonic() - start, 5)
            self.assertFalse((root / 'out' / 'MEMORY-GUARD.json').exists())
            self.assertTrue((root / 'out' / 'memory-guard.jsonl').read_text().strip())


if __name__ == '__main__':
    unittest.main()

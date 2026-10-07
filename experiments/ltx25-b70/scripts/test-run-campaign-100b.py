#!/usr/bin/env python3
"""CPU-only100b runner admission, index and inherited gate controls."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
RUNNER = (HERE / 'run-campaign-100b.sh').read_text()
OLD = (HERE / 'run-campaign-100.sh').read_text()
ARGS = ['two-way20-28', '2', '1', '1', 'xpu:2', '256x256', '1', '120']


def shell(text, args=ARGS, extra=None):
    env = dict(os.environ)
    for k in ('LTX_PACKET_MANIFEST_SHA256', 'LTX_CONTROL99_BASIS', 'LTX_CONTROL99_BASIS_SHA256'):
        env.pop(k, None)
    env.update(extra or {})
    return subprocess.run(['bash', '-c', text, 'fixture', *args], env=env, capture_output=True, text=True, timeout=5)

class Runner100b(unittest.TestCase):
    def test_shell_syntax_and_narrow_pre_io_arguments(self):
        self.assertEqual(subprocess.run(['bash', '-n', str(HERE / 'run-campaign-100b.sh')], timeout=5).returncode, 0)
        prefix = RUNNER[:RUNNER.index('\nR=/mnt/')]
        self.assertEqual(shell(prefix).returncode, 0)
        for i, bad in [(0, 'two-way'), (1, '3'), (2, '2'), (3, '0'), (4, 'xpu:1'), (5, '512x320'), (6, '6'), (7, '121')]:
            a = list(ARGS); a[i] = bad
            self.assertEqual(shell(prefix, a).returncode, 8)

    def test_all_actual_indices_disjoint_from99_99b_100_and_each_other(self):
        prefix = RUNNER[:RUNNER.index('\nR=/mnt/')]; seen = set()
        prior = set()
        for short_base, timed_base in ((95000000, 96000000), (97000000, 98000000), (99000000, 99500000)):
            for repeat in range(5):
                cap = short_base + repeat * 1000
                timed = timed_base + repeat * 10000
                prior |= {cap, cap + 10} | set(range(cap + 100, cap + 106)) | set(range(cap + 200, cap + 213)) | set(range(timed, timed + 120))
        for repeat in range(1, 6):
            a = list(ARGS); a[6] = str(repeat)
            r = shell(prefix + '\nprintf "%s %s %s %s %s %s\\n" "$CAP_BASE" "$SELF_BASE" "$SELF_N" "$PROBE_BASE" "$PROBE_N" "$TIMED_BASE"', a)
            cap, sb, sn, pb, pn, tb = map(int, r.stdout.split())
            indices = {cap, cap + 10} | set(range(sb, sb + sn)) | set(range(pb, pb + pn)) | set(range(tb, tb + 120))
            self.assertEqual(len(indices), 141); self.assertFalse(indices & seen)
            self.assertFalse(indices & prior)
            self.assertGreaterEqual(min(indices), 97500000); self.assertLess(max(indices), 100000000)
            self.assertEqual(tb, 98500000 + 10000 * (repeat - 1)); seen |= indices

    def test_missing_digest_or_basis_refuses_without_writes(self):
        part = RUNNER[:RUNNER.index('\nstep()')]
        with tempfile.TemporaryDirectory(prefix='ltx100-runner-test-') as td:
            part = part.replace('BASE_OUT=$LANE/data/rebalance-100b', 'BASE_OUT=' + td + '/campaigns')
            for env in ({}, {'LTX_PACKET_MANIFEST_SHA256': 'a' * 64},
                        {'LTX_PACKET_MANIFEST_SHA256': 'bad', 'LTX_CONTROL99_BASIS': '/tmp/basis', 'LTX_CONTROL99_BASIS_SHA256': 'b' * 64}):
                self.assertEqual(shell(part, extra=env).returncode, 8)
                self.assertFalse((Path(td) / 'campaigns').exists())

    def test_quality_lifecycle_functions_and_stages_identical(self):
        def function(text, name):
            return re.search(r'^' + name + r'\(\).*?^}\n', text, re.M | re.S).group()
        for name in ('arm', 'pid_is_server', 'queue_empty', 'missing_markers', 'failed_jobs', 'pipeline_idle_once',
                     'pipeline_idle_stable', 'stop_when_proven', 'decode_placement_check', 'summarize', 'finish', 'on_signal', 'on_exit'):
            self.assertEqual(function(RUNNER, name).replace('f100b-', 'f100-'), function(OLD, name))
        stages = ['# ---- 1.', '# ---- 2.', '# ---- 3.', '# ---- 4.', '# ---- 5.', '# ---- 6.', '# ---- B=1, 7.', '# ---- B=1, 8.']
        pos = [RUNNER.index(x) for x in stages]; self.assertEqual(pos, sorted(pos))
        self.assertIn('--control-basis "$CONTROL_BASIS" --control-basis-sha256 "$CONTROL_BASIS_SHA"', RUNNER)
        self.assertEqual(RUNNER.count('--server-identity "$RUN/server-identity.json"'), 2)
        self.assertIn('arm f100b-$TAG-timed $TIMED_ARM $TIMED_N $TIMED_BASE auto watch "$W93C" cycle', RUNNER)

if __name__ == '__main__':
    unittest.main(verbosity=2)

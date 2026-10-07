#!/usr/bin/env python3
"""Bounded shell/CPU controls only; never execute a campaign or submit a prompt."""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'run-campaign-99b.sh').read_text()
OLD = (HERE / 'run-campaign-98.sh').read_text()
ARGS = ['two-way', '2', '1', '1', 'xpu:2', '256x256', '1', '120']


def shell(text, args=ARGS, manifest=None):
    env = dict(os.environ)
    env.pop('LTX_PACKET_MANIFEST_SHA256', None)
    if manifest is not None:
        env['LTX_PACKET_MANIFEST_SHA256'] = manifest
    return subprocess.run(['bash', '-c', text, 'cpu-fixture', *args],
                          capture_output=True, text=True, timeout=5, env=env)


def function(text, name):
    match = re.search(r'^' + re.escape(name) + r'\(\).*?^}\n', text, re.M | re.S)
    if match is None:
        raise AssertionError('Missing function: ' + name)
    return match.group()


class Runner99b(unittest.TestCase):
    def test_shell_syntax(self):
        r = subprocess.run(['bash', '-n', str(HERE / 'run-campaign-99b.sh')], capture_output=True, timeout=5)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_narrow_argument_admission_before_any_io(self):
        prefix = SOURCE[:SOURCE.index('\nR=/mnt/')]
        self.assertEqual(shell(prefix).returncode, 0)
        for index, bad in [(0, 'shard4-a'), (1, '1'), (2, '2'), (3, '0'),
                           (4, 'xpu:1'), (5, '640x384'), (6, '0'), (6, '6'), (7, '121')]:
            args = list(ARGS); args[index] = bad
            with self.subTest(index=index, value=bad):
                self.assertEqual(shell(prefix, args).returncode, 8)
        for args in ([], ARGS[:-1], ARGS + ['extra']):
            self.assertEqual(shell(prefix, args).returncode, 8)

    def test_all_repeats_have_disjoint_actual_clip_indices(self):
        prefix = SOURCE[:SOURCE.index('\nR=/mnt/')]
        seen, modes = set(), set()
        for repeat in range(1, 6):
            args = list(ARGS); args[6] = str(repeat)
            r = shell(prefix + '\nprintf "%s %s %s %s %s %s %s\\n" "$MODE" "$CAP_BASE" "$SELF_BASE" "$SELF_N" "$PROBE_BASE" "$PROBE_N" "$TIMED_BASE"', args)
            self.assertEqual(r.returncode, 0, r.stderr)
            mode, cap, selfbase, selfn, probe, proben, timed = r.stdout.strip().split()
            current = {int(cap), int(cap) + 10} | set(range(int(selfbase), int(selfbase) + int(selfn))) | set(range(int(probe), int(probe) + int(proben))) | set(range(int(timed), int(timed) + 120))
            self.assertEqual(len(current), 2 + 6 + 13 + 120)
            self.assertFalse(seen & current)
            self.assertGreaterEqual(min(current), 99000000)
            self.assertLess(max(current), 100000000)
            self.assertEqual(int(timed), 99500000 + 10000 * (repeat - 1))
            seen |= current; modes.add(mode)
        self.assertEqual(len(modes), 5)

    def test_missing_or_malformed_digest_refuses_before_output_creation(self):
        # Stop before function definitions or any server/device checks. Rewrite
        # only storage destinations into /tmp; this runs actual admission code.
        part = SOURCE[:SOURCE.index('\nstep()')]
        self.assertIn('MANIFEST=${LTX_PACKET_MANIFEST_SHA256:-}', part)
        with tempfile.TemporaryDirectory(prefix='ltx99b-runner-test-') as td:
            part = part.replace('BASE_OUT=$LANE/data/upstream-99b', 'BASE_OUT=' + td + '/campaigns')
            for manifest in (None, '', '__MANIFEST__', 'a' * 63, 'a' * 65, 'A' * 64, 'g' * 64, 'a' * 64 + '\n'):
                with self.subTest(manifest=manifest):
                    r = shell(part, manifest=manifest)
                    self.assertEqual(r.returncode, 8)
                    self.assertIn('not pinned', r.stdout)
                    self.assertFalse((Path(td) / 'campaigns').exists())

    def test_pinned_output_creation_is_exclusive_and_symlink_safe(self):
        part = SOURCE[:SOURCE.index('\nstep()')]
        with tempfile.TemporaryDirectory(prefix='ltx99b-runner-test-') as td:
            part = part.replace('BASE_OUT=$LANE/data/upstream-99b', 'BASE_OUT=' + td + '/campaigns')
            self.assertEqual(shell(part, manifest='a' * 64).returncode, 0)
            self.assertEqual(shell(part, manifest='a' * 64).returncode, 8)
            output = next((Path(td) / 'campaigns').iterdir())
            output.rmdir(); output.symlink_to(Path(td) / 'absent', target_is_directory=True)
            self.assertEqual(shell(part, manifest='a' * 64).returncode, 8)
            self.assertFalse((Path(td) / 'absent').exists())

    def test_quality_and_shutdown_functions_preserved(self):
        for name in ('arm', 'pid_is_server', 'queue_empty', 'missing_markers', 'failed_jobs',
                     'pipeline_idle_once', 'pipeline_idle_stable', 'stop_when_proven',
                     'decode_placement_check', 'summarize', 'finish', 'on_signal', 'on_exit'):
            with self.subTest(function=name):
                self.assertEqual(function(SOURCE, name).replace('f99b-', 'f98-'), function(OLD, name))
        self.assertEqual(function(SOURCE, 'stop_when_proven').count('kill -INT $PID'), 1)
        self.assertNotIn('kill -KILL', SOURCE)

    def test_stage_order_and_oracle_are_preserved(self):
        names = ('# ---- 1. text-window', '# ---- 2. memory plan', '# ---- 3.',
                 '# ---- 4. decode probe', '# ---- 5. the freeze', '# ---- 6. post-freeze',
                 '# ---- B=1, 7. placement probe', '# ---- B=1, 8. timed')
        positions = [SOURCE.index(name) for name in names]
        self.assertEqual(positions, sorted(positions))
        timed = next(line for line in SOURCE.splitlines() if line.strip() == 'arm f99b-$TAG-timed $TIMED_ARM $TIMED_N $TIMED_BASE auto watch "$W93C" cycle')
        self.assertNotIn('no-oracle', timed)
        self.assertIn('[ "${EXACT##* }" = 10 ]', SOURCE)
        self.assertIn('[ $SELF_RC -eq 0 ] && [ $SC_RC -eq 0 ]', SOURCE)

    def test_headroom_calibration_is_packet99b_scoped(self):
        lines = [line for line in SOURCE.splitlines() if 'worker-headroom-98.py' in line and (' plan ' in line or ' live ' in line)]
        self.assertEqual(len(lines), 2)
        self.assertTrue(all('--manifest $MANIFEST --calibration-root $BASE_OUT' in line for line in lines))
        self.assertIn('BASE_OUT=$LANE/data/upstream-99b', SOURCE)
        # Execute only the CPU planner, with an empty disposable calibration
        # tree. Confirm historical estimates cannot masquerade as new calibration.
        with tempfile.TemporaryDirectory(prefix='ltx99b-headroom-test-') as td:
            r = subprocess.run(['python3', '-B', str(HERE / 'worker-headroom-98.py'),
                 'plan', 'two-way', '2', '1', '1', '--size', '256x256', '--replicas', 'xpu:2',
                 '--manifest', 'a' * 64, '--calibration-root', td], capture_output=True, text=True, timeout=5)
            self.assertEqual(r.returncode, 0, r.stderr)
            report = json.loads(r.stdout)
            self.assertEqual(report['basis'], 'private-pool bound')
            self.assertEqual(report['layout'], 'two-way')
            self.assertEqual(report['replica_cards'], ['xpu:2'])


if __name__ == '__main__':
    unittest.main(verbosity=2)

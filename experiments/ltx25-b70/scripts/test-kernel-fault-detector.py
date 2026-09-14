#!/usr/bin/env python3
"""CPU-only fixtures and actual incident replay; never inspect live processes."""
import ast
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from kernel_fault_detector import FAULT, GPU_PATTERN, matching_lines

LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
INCIDENT = ROOT / 'compiler-screen-01-kernel-incident.log'
LAUNCHER = ROOT / 'prepared-encoder-compiler-02/launch/serve-encoder.py'
PATCH = LANE / 'patches/encoder-kernel-host-fault-detector.patch'


class KernelFaultDetector(unittest.TestCase):
    def test_original_gpu_signatures_remain_detected(self):
        cases = ['xe: Fault response received', 'CAT error', 'engine reset on tile0',
                 'GPU HANG: ecode123', 'GuC submission reset failed', 'GPU coredump saved']
        for text in cases:
            with self.subTest(text=text):
                self.assertIsNotNone(re.search(GPU_PATTERN, text, re.I))
                self.assertIsNotNone(FAULT.search(text))

    def test_real_soft_lockup_headers(self):
        cases = ['watchdog: BUG: soft lockup - CPU#13 stuck for 26s! [python:96119]',
                 'watchdog: BUG: soft lockup - CPU#6 stuck for 22s! [rs:main Q:Reg:1544]']
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual(matching_lines(text)[0]['kinds'], ['soft_lockup'])

    def test_rcu_stall_flavors(self):
        cases = ['rcu: INFO: rcu_preempt detected stalls on CPUs/tasks:',
                 'rcu: INFO: rcu_preempt self-detected stall on CPU',
                 'rcu: INFO: rcu_preempt detected expedited stalls on CPUs/tasks:',
                 'INFO: rcu_sched detected stalls on CPUs/tasks:',
                 'rcu: INFO: rcu_bh detected stall on CPU',
                 'rcu: INFO: rcu_tasks detected stalls on tasks:',
                 'rcu: INFO: rcu_tasks_trace detected stalls on tasks:']
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual(matching_lines(text)[0]['kinds'], ['rcu_stall'])

    def test_rcu_kthread_starvation(self):
        self.assertEqual(matching_lines('rcu: rcu_preempt kthread starved for 21002 jiffies! g123')[0]['kinds'],
                         ['rcu_kthread_starved'])

    def test_real_hung_task_headers(self):
        cases = ['INFO: task systemd:1 blocked for more than 122 seconds.',
                 'INFO: task (fstrim):97240 blocked for more than 122 seconds.',
                 'INFO: task kworker/u64:0:123 blocked for more than 120 seconds.']
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual(matching_lines(text)[0]['kinds'], ['hung_task'])

    def test_generic_or_configuration_words_do_not_trigger(self):
        cases = ['hang', 'The UI hangs while loading a model.', 'watchdog: enabled',
                 'rcu: Hierarchical RCU implementation.', 'rcu: stall timeout set to60s',
                 'INFO: ordinary task blocked waiting for I/O',
                 'task:worker state:D stack:0 pid:42',
                 'echo0 > /proc/sys/kernel/hung_task_timeout_secs disables this message',
                 'watchdog: softlockup_panic=0', 'RIP: smp_call_function_many_cond+0x12e/0x5f0',
                 'INFO:\nrcu_preempt detected stalls on CPUs/tasks:',
                 'BUG: soft lockup -\nCPU#13 stuck for26s!']
        for text in cases:
            with self.subTest(text=text):
                self.assertIsNone(FAULT.search(text))

    def test_actual_incident_replay_detects_host_fault_legacy_missed(self):
        text = INCIDENT.read_text()
        old = re.compile(GPU_PATTERN, re.I)
        self.assertIsNone(old.search(text))
        rows = matching_lines(text)
        self.assertTrue(any('soft_lockup' in row['kinds'] and '[python:96119]' in row['line'] for row in rows))
        self.assertTrue(any('soft_lockup' in row['kinds'] and '[rs:main Q:Reg:1544]' in row['line'] for row in rows))
        self.assertTrue(any('hung_task' in row['kinds'] and 'systemd:1' in row['line'] for row in rows))
        self.assertTrue(any('hung_task' in row['kinds'] and '(fstrim):97240' in row['line'] for row in rows))
        self.assertEqual(rows[0]['line_number'], 1)

    def test_patch_applies_only_to_temporary_copy_and_matches_detector(self):
        before = hashlib.sha256(LAUNCHER.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(prefix='ltx-host-fault-patch-') as temporary:
            destination = Path(temporary) / 'launch/serve-encoder.py'
            destination.parent.mkdir()
            shutil.copyfile(LAUNCHER, destination)
            subprocess.run(['git', 'apply', '--check', str(PATCH)], cwd=temporary, check=True,
                           capture_output=True, timeout=10)
            subprocess.run(['git', 'apply', str(PATCH)], cwd=temporary, check=True,
                           capture_output=True, timeout=10)
            tree = ast.parse(destination.read_text())
            assignment = next(node for node in tree.body if isinstance(node, ast.Assign) and
                              any(isinstance(target, ast.Name) and target.id == 'FAULT' for target in node.targets))
            actual_pattern = ast.literal_eval(assignment.value.args[0])
            self.assertEqual(actual_pattern, FAULT.pattern)
            # No new call sites/loops or recovery operations are introduced.
            original_tree = ast.parse(LAUNCHER.read_text())
            def call_shapes(parsed):
                return [ast.dump(node.func) for node in ast.walk(parsed) if isinstance(node, ast.Call)]
            self.assertEqual(call_shapes(tree), call_shapes(original_tree))
        self.assertEqual(hashlib.sha256(LAUNCHER.read_bytes()).hexdigest(), before)


if __name__ == '__main__':
    unittest.main()

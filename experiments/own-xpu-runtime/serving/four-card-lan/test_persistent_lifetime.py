#!/usr/bin/env python3
"""CPU-only lifetime regressions; imports the adapter but never launches a rank."""
import importlib.util
import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / 'research/tp/prefill-shexp-split-2026-10-31/lab'
SPEC = importlib.util.spec_from_file_location('persistent_lifetime_adapter', LAB / 'adapter6_tp.py')
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)
with patch.dict(os.environ, {
    'SC117_LAB_CONTROL_PARENT': '/nonexistent/test-control',
    'SC117_LAB_EVIDENCE': '/nonexistent/test-evidence',
    'SC117_LAB_UNIT': 'sc117-tp-svc-lifetime-test.service',
    'SC117_ADAPTER': 'adapter6_tp.py',
}):
    SERVICE_SPEC = importlib.util.spec_from_file_location('persistent_lifetime_service', LAB / 'service.py')
    S = importlib.util.module_from_spec(SERVICE_SPEC)
    SERVICE_SPEC.loader.exec_module(S)


class PersistentLifetimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.receipt = self.path / 'receipt.json'
        self.receipt.write_text(json.dumps({
            'passed': True,
            'schema': 'ownrt.engine.build.v1',
            'root_binary_sha256': '5926a24746c62c6b0ecdc5c3e4895f310145e0f9d74a90a5d657035b9a8151f4',
            'binary': str(self.path / 'never-executed'),
            'binary_sha256': 'test-only',
        }))

    def plan(self, seconds):
        with patch.object(A, 'SERVICE_BUILD', self.receipt), \
             patch.object(A, 'source_pins', return_value={}), \
             patch.object(A, 'environments', return_value=[{}, {}]):
            return A.build_plan(self.path / 'unused-output', seconds=seconds)

    def transport(self, seconds=0):
        # Deliberately bypass __init__: it owns native process launch.
        t = A.Transport.__new__(A.Transport)
        t.a = types.SimpleNamespace(seconds=seconds, wait_seconds=2)
        t.start_time = 0.0
        t.check = Mock()
        t.children = []
        t.finishing = set()
        t.stop_sent = False
        t.out = self.path
        t.device = True
        return t

    def test_persistent_plan_reaches_both_native_commands(self):
        plan = self.plan(0)
        self.assertEqual(plan['seconds'], 0)
        self.assertGreater(plan['wait_seconds'], 0)
        for argv in plan['rank_argv']:
            self.assertEqual(argv[argv.index('--seconds') + 1], '0')

    def test_service_persistent_mode_has_no_expiry(self):
        self.assertEqual(S.native_lifetime_seconds(0), 0)
        self.assertIsNone(S.lifetime_deadline(1234.0, 0))

    def test_service_finite_mode_keeps_its_deadline(self):
        for hours in (0.1, 47, 47.5):
            with self.subTest(hours=hours):
                self.assertEqual(S.native_lifetime_seconds(hours), 172800)
                self.assertEqual(S.lifetime_deadline(1234.0, hours), 1234.0 + hours * 3600)
        for hours in (-1, 0.01, 48, float('inf'), float('nan')):
            with self.subTest(hours=hours), self.assertRaises(RuntimeError):
                S.native_lifetime_seconds(hours)

    def test_finite_plan_remains_available(self):
        for seconds in (30, 1800, 172800):
            with self.subTest(seconds=seconds):
                plan = self.plan(seconds)
                self.assertEqual(plan['seconds'], seconds)
                self.assertGreater(plan['wait_seconds'], 0)

    def test_invalid_lifetimes_are_rejected(self):
        for seconds in (-1, 1, 29, 172801, True, 0.0):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                self.plan(seconds)

    def test_persistent_transport_survives_one_hundred_days(self):
        t = self.transport()
        with patch.object(A.time, 'monotonic', return_value=100 * 86400):
            t.check_alive()
        t.check.assert_called_once()

    def test_finite_transport_still_expires(self):
        t = self.transport(seconds=172800)
        with patch.object(A.time, 'monotonic', return_value=100 * 86400):
            with self.assertRaisesRegex(ValueError, 'pipeline total deadline'):
                t.check_alive()

    def test_persistent_transport_still_propagates_monitor_faults(self):
        t = self.transport()
        t.check.side_effect = RuntimeError('monitor fault')
        with patch.object(A.time, 'monotonic', return_value=100 * 86400):
            with self.assertRaisesRegex(RuntimeError, 'monitor fault'):
                t.check_alive()

    def test_persistent_transport_still_detects_rank_failure(self):
        t = self.transport()
        t.children = [Mock(poll=Mock(return_value=1))]
        with patch.object(A.time, 'monotonic', return_value=100 * 86400):
            with self.assertRaisesRegex(A.BASE.DeviceOwnerFailure, 'rank failed with exit 1'):
                t.check_alive()

    def test_persistent_transport_still_times_out_stalled_operation(self):
        t = self.transport()
        t.sockets = [Mock()]
        clock = iter(range(100 * 86400, 100 * 86400 + 100))
        with patch.object(A.time, 'monotonic', side_effect=lambda: next(clock)), \
             patch.object(A.BASE.select, 'select', return_value=([], [], [])):
            with self.assertRaisesRegex(ValueError, 'bounded rank channel timeout'):
                t.io(0)

    def test_persistent_transport_still_exchanges_data_after_one_hundred_days(self):
        t = self.transport()
        expected = b'x' * A.BASE.REPLY.size
        sock = Mock(recv=Mock(return_value=expected))
        t.sockets = [sock]
        with patch.object(A.time, 'monotonic', return_value=100 * 86400), \
             patch.object(A.BASE.select, 'select', return_value=([sock], [], [])):
            self.assertEqual(t.io(0), expected)


if __name__ == '__main__':
    unittest.main()

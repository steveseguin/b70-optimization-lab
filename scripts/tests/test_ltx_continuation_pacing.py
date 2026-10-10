#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""CPU-only pacing and saved-log analysis; no network, subprocesses or devices."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ledger = load('pacing_ledger', ROOT / 'scripts/analyze-ltx-continuation-ledger.py')
client = load('pacing_client', ROOT / 'experiments/ltx25-b70/stream/ltx_continuation_client.py')


class PacingTests(unittest.TestCase):
    def make_client(self, mode='precise'):
        c = client.Client.__new__(client.Client)
        c.a = SimpleNamespace(pacing_log=mode, max_ahead_seconds=60)
        c.chunk_seconds = 6
        c.throttled_since = c.throttle_started_ns = None
        c.ahead_seconds = lambda pending: 60 + pending
        return c

    def hold(self, mode='precise', outcome='released'):
        c = self.make_client(mode)
        logs = []
        with patch.object(client, 'log', logs.append), patch.object(client.time, 'monotonic', return_value=1.0), \
                patch.object(client.time, 'monotonic_ns', side_effect=[1000000000, 2234567890]):
            self.assertFalse(c.throttle_ok(0))
            self.assertFalse(c.throttle_ok(0))
            if outcome == 'released':
                c.ahead_seconds = lambda _: 0
                self.assertTrue(c.throttle_ok(0))
            else:
                c.finish_pacing_hold(outcome)
            c.finish_pacing_hold('interrupted')
        self.assertEqual(len(logs), 2)
        self.assertIsNone(c.throttled_since)
        self.assertIsNone(c.throttle_started_ns)
        return logs

    def test_precise_release(self):
        logs = self.hold()
        self.assertTrue(logs[0].endswith('start_mono_ns=1000000000'))
        self.assertEqual(logs[1], 'throttle released after 1.234567890 s start_mono_ns=1000000000 end_mono_ns=2234567890 duration_ns=1234567890')

    def test_interrupted_hold(self):
        self.assertIn('throttle interrupted after 1.234567890 s', self.hold(outcome='interrupted')[1])

    def test_legacy_release(self):
        logs = self.hold('legacy')
        self.assertNotIn('mono_ns', ''.join(logs))
        self.assertEqual(logs[1], 'throttle released after 0.0 s')

    def test_no_sink_no_hold(self):
        c = self.make_client()
        c.ahead_seconds = lambda _: None
        with patch.object(client, 'log') as log:
            self.assertTrue(c.throttle_ok(0))
            c.finish_pacing_hold('interrupted')
            log.assert_not_called()

    def test_limit_equality_does_not_hold(self):
        c = self.make_client()
        c.ahead_seconds = lambda _: 54
        self.assertTrue(c.throttle_ok(0))

    def test_prefix_keeps_cut_and_slow_intervals(self):
        raw, primary, diagnostic, gaps = ledger.period_evidence(
            [[[8, 0], [9, 5], [10, 11], [11, 31], [12, 50], [13, 56]]], [[{'after_seq': 11}]])
        self.assertEqual(raw, [[10, 6], [11, 20], [12, 19], [13, 6]])
        self.assertEqual(primary, [[10, 6], [11, 20]])
        self.assertEqual(diagnostic, [[10, 6], [11, 20], [13, 6]])
        self.assertEqual(gaps, [])

    def test_resume_separate_prefix(self):
        raw, primary, _, gaps = ledger.period_evidence(
            [[[9, 0], [10, 5], [11, 17]], [[12, 100], [13, 106], [14, 113]]],
            [[{'after_seq': 10}], []])
        self.assertEqual(primary, [[10, 5], [13, 6], [14, 7]])
        self.assertEqual(len(raw), 4)
        self.assertEqual(gaps, [{'from_seq': 11, 'to_seq': 12, 'seconds': 83}])

    def test_missing_submission_is_not_bridged(self):
        self.assertEqual(ledger.period_evidence([[[9, 0], [11, 10]]], [[]])[0], [])

    def test_hold_before_first_submission(self):
        self.assertEqual(ledger.period_evidence([[[9, 0], [10, 5]]], [[{'after_seq': None}]])[1], [])

    def analyze_log(self, lines):
        with tempfile.TemporaryDirectory(prefix='ltx-pacing138-test-') as tmp:
            root = Path(tmp)
            folder = root / 's138-test'
            folder.mkdir()
            (folder / 'client.log').write_text(
                '[c112 00:00:00.000] server encoder-server-test identity abc frames 145 packet 138\n' +
                '\n'.join(lines) + '\n[c112 00:01:00.000] clean stop: fixture\n')
            return ledger.analyze(root, root / 'no-runs')['runs'][0]

    def test_legacy_saved_duration_not_subtracted(self):
        run = self.analyze_log([
            '[c112 00:00:01.000] submitted stream138-s00000009',
            '[c112 00:00:06.000] submitted stream138-s00000010',
            '[c112 00:00:07.000] throttle: holding the next chunk',
            '[c112 00:00:09.000] throttle released after 2.0 s',
            '[c112 00:00:13.000] submitted stream138-s00000011'])
        self.assertEqual(run['statistics']['n'], 1)
        self.assertEqual(run['raw_statistics']['n'], 2)
        self.assertIsNone(run['pacing_segments'][0][0]['duration_ns'])

    def test_precise_saved_duration_bound(self):
        run = self.analyze_log([
            '[c112 00:00:01.000] throttle: holding start_mono_ns=100',
            '[c112 00:00:02.000] throttle interrupted after 0.000000020 s start_mono_ns=100 end_mono_ns=120 duration_ns=20'])
        self.assertEqual(run['pacing_segments'][0][0]['duration_ns'], 20)

    def test_malformed_precise_duration_refuses(self):
        with self.assertRaisesRegex(ValueError, 'Inconsistent'):
            self.analyze_log([
                '[c112 00:00:01.000] throttle: holding start_mono_ns=100',
                '[c112 00:00:02.000] throttle released after 1 s start_mono_ns=100 end_mono_ns=120 duration_ns=30'])

    def test_release_without_start_refuses(self):
        with self.assertRaisesRegex(ValueError, 'without matching start'):
            self.analyze_log(['[c112 00:00:02.000] throttle released after 1.0 s'])

    def test_open_hold_retained(self):
        run = self.analyze_log(['[c112 00:00:01.000] throttle: holding start_mono_ns=100'])
        self.assertIsNone(run['pacing_segments'][0][0]['end_log'])
        self.assertEqual(run['pacing_hold_count'], 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)

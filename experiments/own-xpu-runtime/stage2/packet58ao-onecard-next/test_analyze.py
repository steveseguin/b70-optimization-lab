"""Failure controls against the real saved packet58aj receipt stream, CPU only."""
import copy
import unittest
from unittest.mock import patch

import analyze as a


class Replay(unittest.TestCase):
    def run_record(self):
        return a.replay('packet58aj-onecard-resident', 'card0-58aj-a')

    def test_real_record(self):
        out, _, _ = self.run_record()
        self.assertAlmostEqual(out['rate_tok_s'], 31.966819787781944, places=10)
        self.assertEqual(out['intervals'], 1188)
        self.assertFalse(out['device_class_times_available'])
        self.assertFalse(out['strict512'])

    def bad_summary(self, mutate):
        original = a.js
        def altered(path):
            value = original(path)
            if path.name == 'summary.json':
                value = copy.deepcopy(value)
                mutate(value)
            return value
        with patch.object(a, 'js', altered), self.assertRaises(AssertionError):
            self.run_record()

    def test_cached_prompt_refused(self):
        self.bad_summary(lambda d: d['requests'][0].update(cached_tokens=1))

    def test_inexact_prompt_refused(self):
        self.bad_summary(lambda d: d['requests'][0].update(exact_oracle=False))

    def test_missing_prompt_refused(self):
        self.bad_summary(lambda d: d['requests'].pop())

    def test_bad_timestamp_refused(self):
        self.bad_summary(lambda d: d['requests'][0]['token_timestamps'].__setitem__(1, float('nan')))

    def test_changed_rate_refused(self):
        self.bad_summary(lambda d: d['class_balanced_tok_s_1_100_intervals_after_ttft'].update(median=99))

    def test_changed_precision_refused(self):
        self.bad_summary(lambda d: d.update(kv_dtype='FP8'))

    def test_truncated_stream_refused(self):
        original = a.read
        def altered(path):
            data = original(path)
            return b'\n'.join(data.splitlines()[:-1]) if path.name == 'timings.jsonl' else data
        with patch.object(a, 'read', altered), self.assertRaises(AssertionError):
            self.run_record()


if __name__ == '__main__':
    a.resource.setrlimit(a.resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    unittest.main()

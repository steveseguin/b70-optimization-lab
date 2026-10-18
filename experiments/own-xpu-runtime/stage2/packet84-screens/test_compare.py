"""Negative checks for the diagnostic comparison's quality and metric gates."""
import unittest
from compare import checked_requests, compare, D, METRICS
from config import ORDER

class ComparisonTests(unittest.TestCase):
    def summary(self):
        rows = [dict(prompt_id=p, prompt_class=METRICS.PROMPT_CLASSES[p], cached_tokens=0,
                     passed=True, exact_oracle=True, tokens=list(range(128)),
                     token_timestamps=[i / 50 for i in range(128)],
                     tok_s_1_100_intervals_after_ttft=50, hits=90, guesses=127, acceptance=90/127)
                for p in D.CHECK.PROMPT_IDS]
        return dict(requests=rows, cached_tokens=0, requested_max_new=128,
                    request_count=12, passed=True, kv_dtype='BF16')

    def checked(self, summary):
        return checked_requests(summary, lambda p: list(range(128)))

    def test_complete_suite(self):
        result = self.checked(self.summary())
        self.assertEqual(result['rate'], 50)
        self.assertEqual(len(result['acceptance_counts']), 12)

    def test_changed_token_or_missing_prompt(self):
        for change in ('token', 'missing', 'cache', 'precision'):
            with self.subTest(change=change):
                s = self.summary()
                if change == 'token': s['requests'][0]['tokens'][10] = -1
                elif change == 'missing': s['requests'].pop()
                elif change == 'cache': s['requests'][0]['cached_tokens'] = 1
                else: s['kv_dtype'] = 'FP8'
                with self.assertRaises(ValueError): self.checked(s)

    def test_metric_and_acceptance_tampering(self):
        for key, value in [('tok_s_1_100_intervals_after_ttft', 51), ('acceptance', 1),
                           ('guesses', 0), ('token_timestamps', [0]*128)]:
            with self.subTest(key=key):
                s = self.summary(); s['requests'][0][key] = value
                with self.assertRaises(ValueError): self.checked(s)

    def test_mean_controls_not_max(self):
        rows = [dict(choice=c, all_13_exact=True, rate=r, acceptance=.75,
                     boot_id='test', started_utc_ns=i*10, finished_utc_ns=i*10+5)
                for i, (c, r) in enumerate(zip(ORDER, (50, 52, 54, 54)))]
        result = compare(rows)
        self.assertEqual(result['control_mean_tok_s'], 52)
        self.assertEqual(result['candidates'][0]['gain_percent'], 0)
        self.assertAlmostEqual(result['candidates'][1]['gain_percent'], 100*(54/52-1))
        self.assertFalse(result['submission_eligible'])
        rows[3]['all_13_exact'] = False
        with self.assertRaises(ValueError): compare(rows)

if __name__ == '__main__':
    unittest.main()

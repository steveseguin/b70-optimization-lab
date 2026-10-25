import unittest
from audit_persistent_suite import cold, rates_summary, timing


class AuditTests(unittest.TestCase):
    def test_timing_requires_entire_matching_ordered_response(self):
        rows = [dict(index=i, token=t, committed_monotonic_s=s) for i,t,s in [(0,9,10.),(1,7,10.25),(2,3,10.5)]]
        self.assertEqual(timing(rows,[9,7,3])['tokens_per_second'],4.)
        for changed in (rows[:-1], list(reversed(rows)), [dict(r,token=0) for r in rows],
                        [dict(r,committed_monotonic_s=float('nan')) for r in rows]):
            with self.assertRaises(ValueError):timing(changed,[9,7,3])

    def test_missing_boolean_and_nonzero_cache_are_not_cold(self):
        good=dict(cached_tokens=0,prompt_state_reused=False,process_reused=True)
        cold(good)
        for bad in ({k:v for k,v in good.items() if k!='cached_tokens'},dict(good,cached_tokens=False),
                    dict(good,cached_tokens=7),dict(good,prompt_state_reused=True)):
            with self.assertRaises(ValueError):cold(bad)

    def test_even_median_uses_both_middle_values(self):
        self.assertEqual(rates_summary([1.,2.,10.,100.])['median'],6.)


if __name__=='__main__':unittest.main()

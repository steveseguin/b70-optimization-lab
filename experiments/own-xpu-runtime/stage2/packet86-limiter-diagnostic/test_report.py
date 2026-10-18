import copy
import unittest
from report import aggregate_events, compare, VIEWS

class ReportTests(unittest.TestCase):
    def event(self,rank,layer,site,start,end,spec=False):
        return dict(rank=rank,label=f'blk.{layer}.{site}',fixture=9,position=40,speculative=spec,start_ns=start,end_ns=end)
    def test_sum_stages_before_median_and_ignore_incomplete_calls(self):
        events=[]
        for rank,layer in ((0,22),(0,23),(1,24),(1,27)):
            events.extend([self.event(rank,layer,'expsgate',100,1100),self.event(rank,layer,'expsgate',1200,3200),self.event(rank,layer,'ffn.combine',3300,3500)])
        events.append(self.event(0,22,'expsgate',100,999999,spec=True))
        rows=aggregate_events([('a',events)])
        gates=[r for r in rows if r['site']=='expsgate']
        self.assertEqual(len(gates),4);self.assertTrue(all(abs(r['call_ms']-.003)<1e-10 for r in gates))
        self.assertEqual({r['path'] for r in rows},{'corrected'})
    def reports(self):
        rows=[dict(rank=rank,path='corrected',layer=layer,site='expsgate',estimated_ms_per_half=1.) for rank,layer in ((0,22),(0,23),(1,24),(1,27))]
        return {name:dict(passed=True,diagnostic_nonexact=True,lane='B',binary_sha256='same',prompt_identity=['same'],sites=copy.deepcopy(rows)) for name in VIEWS}
    def test_missing_layers_are_not_free_and_negative_bounds_survive(self):
        reports=self.reports();reports['exp-nodeq']['sites'][0]['estimated_ms_per_half']=3.
        reports['exp-onecached']['sites'].pop(0)
        result=compare(reports)
        raw=next(r for r in result['mechanisms'] if r['mechanism']=='byte_read_surrogate' and r['rank']==0)
        self.assertEqual(raw['signed_delta_ms_per_half'],-2);self.assertEqual(raw['ablation_bound_ms'],0)
        cache=next(r for r in result['mechanisms'] if r['mechanism']=='repeated_expert_cache_hypothesis' and r['rank']==0)
        self.assertIsNone(cache['signed_delta_ms_per_half']);self.assertIsNone(cache['achievable_lossless_budget_ms'])
    def test_identity_and_missing_view_rejected(self):
        reports=self.reports();reports['exp-nodeq']['lane']='A'
        with self.assertRaises(ValueError):compare(reports)
        reports=self.reports();del reports['hc-nodeq']
        with self.assertRaises(ValueError):compare(reports)

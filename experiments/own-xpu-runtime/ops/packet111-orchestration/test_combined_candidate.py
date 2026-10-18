"""Synthetic policy regressions. No native execution or device evidence writes."""
import copy
import unittest
from unittest.mock import patch
import source_decision as s
import composite_jobs as c
import verify_ready as ready


def bracket(choice, rate=100.37, lane='B', views=False):
    order = ['control', choice, 'control', choice, 'control'] if views else ['control', choice, 'control']
    rows = [dict(choice=label, rate=rate if label==choice else 100.,
                 all_13_exact=True, exact=True, exact_count=13, lane=lane,
                 acceptance_counts=[dict(prompt_id='fixture', hits=3, guesses=4)],
                 acceptance=.75, boot_id='fixture', started_utc_ns=2*i+1,
                 finished_utc_ns=2*i+2) for i,label in enumerate(order)]
    return dict(all_13_exact=True, **{'views' if views else 'screens':rows})


def sources():
    return {key:dict(status='complete', result=bracket(choice, views=key=='other_fusion'))
            for key,choice in [('target_head','head-split'),('other_fusion','candidate')]}


class CombinedTests(unittest.TestCase):
    def select(self, rows):
        for key,row in rows.items():row['eligible'],row['ratio']=s.qualification(row,key)
        return s.decide(rows)

    def test_both_positive_below_half_percent_choose_both(self):
        self.assertEqual(self.select(sources()), dict(target_head='split',other_fusion='fused'))

    def test_lane_a_loss_excludes_either(self):
        for key,choice in [('target_head','head-split'),('other_fusion','candidate')]:
            rows=sources()
            rows[key]['lane_A']=dict(status='complete',result=bracket(choice,99.,lane='A'))
            selected=self.select(rows)
            self.assertEqual(selected[key],'production')
            other='other_fusion' if key=='target_head' else 'target_head'
            self.assertNotEqual(selected[other],'production')

    def test_every_bracket_and_every_candidate_must_win(self):
        rows=sources()
        rows['target_head']['result']={'brackets':[bracket('head-split'),bracket('head-split',100.)]}
        rows['other_fusion']['result']['views'][3]['rate']=99.
        self.assertEqual(self.select(rows),dict(target_head='production',other_fusion='production'))

    def test_pending_and_invalid_exactness_fail_closed(self):
        rows=sources();rows['target_head']['status']='pending'
        self.assertEqual(self.select(rows)['target_head'],'production')
        rows=sources();rows['other_fusion']['result']['all_13_exact']=False
        with self.assertRaises(AssertionError):self.select(rows)

    def test_current_receipts_admit_both(self):
        _,config=c.current();c.validate(config)
        self.assertEqual(config['candidate']['target_head'],'split')
        self.assertEqual(config['candidate']['other_fusion'],'fused')

    def test_device_imports_preserve_resource_limits(self):
        import subprocess
        import sys
        code = ('import resource; kinds={getattr(resource,k) for k in dir(resource) if k.startswith("RLIMIT_")}; '
                'before={k:resource.getrlimit(k) for k in kinds}; '
                'import composite_screen,verify_ready,source_decision,chain_entry; '
                'assert before=={k:resource.getrlimit(k) for k in kinds}; '
                'assert resource.getrlimit(resource.RLIMIT_AS)==(resource.RLIM_INFINITY,resource.RLIM_INFINITY)')
        subprocess.run([sys.executable,'-B','-c',code],cwd=s.O,stdin=subprocess.DEVNULL,check=True)

    def matched(self, rates, change=None):
        # Exercise the actual matched gate and comparison; only receipt loading
        # and static seals are replaced by in-memory fixtures.
        import compare
        rows={lane:bracket('candidate',rate,lane)['screens'] for lane,rate in rates.items()}
        if change:change(rows)
        _,config=c.current()
        with patch('policy_seal.verify'),patch('chain_adapter.install'),patch.object(compare,'load',side_effect=lambda job:rows[job['lane']][job['index']]):
            return ready.matched(config)

    def test_composite_below_threshold_on_either_lane_refused(self):
        for lane in ('A','B'):
            rates={'A':100.6,'B':100.6};rates[lane]=100.49
            with self.assertRaisesRegex(AssertionError,'>=0.5%.*'+lane):self.matched(rates)

    def test_composite_exact_threshold_passes_both(self):
        self.assertTrue(self.matched({'A':100.5,'B':100.5})['passed'])

    def test_stronger_control_not_mean(self):
        def change(rows):rows['B'][2]['rate']=100.2
        with self.assertRaisesRegex(AssertionError,'>=0.5%.*B'):self.matched({'A':100.6,'B':100.6},change)

    def test_composite_exactness_and_per_prompt_acceptance(self):
        def exact(rows):rows['A'][1]['all_13_exact']=False
        def acceptance(rows):rows['B'][1]['acceptance_counts']=[]
        for change in (exact,acceptance):
            with self.assertRaises(ValueError):self.matched({'A':101.,'B':101.},change)


if __name__=='__main__':unittest.main()

"""S1 decision on the parent line's REAL two-card device evidence and on synthetic cases."""
import copy,json,unittest
from pathlib import Path
from s1_decision import decide,from_summary,RECORD
P=Path(__file__).resolve().parent
REAL=P.parent/'lineage-inputs/packet153-own/v5/evidence/device-static-v5-B-p153b/bracket-summary.json'
class S1Decision(unittest.TestCase):
    def setUp(self):self.real=json.loads(REAL.read_text())
    def test_real_packet153_bracket(self):
        d=from_summary(self.real)  # packet153: static +0.35% over the best control, drift 0.057%
        self.assertAlmostEqual(d['best_control_rate'],58.671,places=2);self.assertAlmostEqual(d['slower_candidate_rate'],58.874,places=2)
        self.assertAlmostEqual(d['min_gain_percent'],0.346,places=2)
        self.assertFalse(d['screen_winner']);self.assertFalse(d['candidate_qualified']);self.assertFalse(d['chain_rule_met'])
    def scaled(self,factor):
        s=copy.deepcopy(self.real)
        for v in s['views']:
            if v['choice']=='candidate':v['rate']=max(r['rate'] for r in s['views'] if r['choice']=='control')*factor
        return s
    def test_projected_win(self):
        d=from_summary(self.scaled(1.044))  # expected-gain floor scenario
        self.assertTrue(d['screen_winner'] and d['candidate_qualified'] and d['chain_rule_met'])
    def test_plus_two_percent_below_record_bar(self):
        d=from_summary(self.scaled(1.021))  # +2.1% over 58.671 = 59.90 < 59.974 record bar
        self.assertTrue(d['screen_winner'] and d['candidate_qualified']);self.assertFalse(d['chain_rule_met'])
    def test_screen_only(self):
        d=from_summary(self.scaled(1.01));self.assertTrue(d['screen_winner']);self.assertFalse(d['chain_rule_met'])
    def test_refusals(self):
        for mutate in (lambda s:s.update(all_13_exact=False),lambda s:s.update(draft_proposals_identical=False),lambda s:s.update(kind='smoke'),
                       lambda s:s['views'][1].update(exact_count=12),lambda s:s.update(control_drift_percent=9.0),lambda s:s['views'].__setitem__(slice(0,2),[s['views'][1],s['views'][0]])):
            s=copy.deepcopy(self.real);mutate(s)
            with self.assertRaises(ValueError):from_summary(s)
        with self.assertRaises(ValueError):decide(self.real['views'][:3],0.0)
    def test_drift_bar(self):
        s=self.scaled(1.05);s['views'][0]['rate']*=0.96
        controls=[v['rate'] for v in s['views'] if v['choice']=='control'];s['control_drift_percent']=100*(max(controls)/min(controls)-1)
        d=from_summary(s);self.assertGreater(d['control_drift_percent'],3.0);self.assertFalse(d['screen_winner']);self.assertFalse(d['chain_rule_met'])
if __name__=='__main__':unittest.main()

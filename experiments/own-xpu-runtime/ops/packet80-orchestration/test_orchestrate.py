"""Both-lane selection refuses mismatched/invalid proof; missing evidence falls back."""
import unittest
import orchestrate as o

def packet(choice,status='winner'):
    return dict(status=status,best=dict(choice=choice,ratio=1.02),confirmation=dict(choice=choice,ratio=1.01),lanes={'A':[dict(exact_count=13,exact=True)],'B':[dict(exact_count=13,exact=True)]})
class Selection(unittest.TestCase):
    def test_all_winners_compose(self):
        c=o.select({'73':packet('hc-wide'),'74':packet('combined'),'76':packet('ordered'),'78':packet('small-combined'),'79':packet('0')})
        self.assertEqual(c,dict(dense='production',experts='wide64',hc='hc-wide',host='ordered',route='fast',norm='fused',placement='0'))
    def test_missing_is_production(self):
        for status in ('pending','failed','missing','no-winner'):
            c=o.select({'73':packet('hc-wide'),'76':packet('ordered',status),'78':packet('small+hc-wide',status),'79':packet('0',status)})
            self.assertEqual((c['host'],c['route'],c['norm'],c['placement']),('production','production','production','1'))
    def test_no_unconfirmed_component_extraction(self):
        c=o.select({'73':packet('combined'),'74':packet('combined')})
        self.assertEqual((c['hc'],c['experts'],c['dense']),('production','wide64','production'))
    def test_small_winner_components(self):
        for arm,expected in {'route-fast':('fast','production','production'),'norm-fused':('production','fused','production'),'small-combined':('fast','fused','production'),'small+hc-wide':('fast','fused','hc-wide')}.items():
            c=o.select({'78':packet(arm)})
            self.assertEqual(tuple(c[k] for k in ('route','norm','hc')),expected)
    def test_bad_proof_refuses(self):
        for lane in ('A','B'):
            a=packet('ordered');a['lanes'][lane][0]['exact_count']=12
            with self.assertRaises(ValueError):o.select({'76':a})
        for ratio in (1,.99,float('nan'),float('inf')):
            a=packet('ordered');a['confirmation']['ratio']=ratio
            with self.assertRaises(ValueError):o.select({'76':a})
        a=packet('ordered');a['confirmation']['choice']='production'
        with self.assertRaises(ValueError):o.select({'76':a})
    def test_graceful_command(self):
        for flag in ('Restart=no','KillMode=process','SendSIGKILL=no','TimeoutStopSec=infinity','ExitType=cgroup','0-3,16-19','device-entry.sh','</dev/null'):self.assertIn(flag,o.command())
if __name__=='__main__':unittest.main()

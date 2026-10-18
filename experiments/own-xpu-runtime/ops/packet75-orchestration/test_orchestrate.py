"""Selection and command fail-closed checks; no native or GPU execution."""
import copy,unittest,math
import orchestrate as o

def packet(choice,status='winner'):
    return dict(status=status,best=dict(choice=choice,ratio=1.02),confirmation=dict(choice=choice,ratio=1.01),lanes={'A':[dict(exact_count=13)],'B':[dict(exact_count=13)]})
class Selection(unittest.TestCase):
    def test_cartesian_confirmations(self):
        for p74 in ('head-packed','dense-packed','combined'):
            for p73,(hc,expert) in {'hc-wide':('hc-wide','wide64'),'experts2-a':('production','experts2-a'),'experts2-b':('production','experts2-b'),'combined':('hc-wide','experts2-b')}.items():
                self.assertEqual(o.select(packet(p73),packet(p74)),dict(dense=p74,hc=hc,experts=expert))
    def test_one_packet_only(self):
        self.assertEqual(o.select(packet('combined'),packet('production','no-winner')),dict(dense='production',hc='hc-wide',experts='experts2-b'))
        self.assertEqual(o.select(packet('production','no-winner'),packet('dense-packed')),dict(dense='dense-packed',hc='production',experts='wide64'))
    def test_pending_blocks(self):
        for status in ('pending','failed','missing'):
            with self.assertRaises(ValueError):o.select(packet('combined',status),packet('combined'))
    def test_inexact_or_single_lane_blocks(self):
        for lane in ('A','B'):
            a=packet('combined');a['lanes'][lane][0]['exact_count']=12
            with self.assertRaises(ValueError):o.select(a,packet('combined'))
        for ratio in (1,0.99,float('nan')):
            a=packet('combined');a['confirmation']['ratio']=ratio
            with self.assertRaises(ValueError):o.select(a,packet('combined'))
    def test_different_b_winner_blocks(self):
        a=packet('combined');a['confirmation']['choice']='experts2-a'
        with self.assertRaises(ValueError):o.select(a,packet('combined'))
    def test_graceful_registered_command(self):
        cmd=o.command()
        for flag in ('Restart=no','Nice=0','KillMode=process','SendSIGKILL=no','TimeoutStopSec=infinity','ExitType=cgroup','0-3,16-19','device-entry.sh','</dev/null'):self.assertIn(flag,cmd)
        self.assertNotIn('packet70',cmd)
if __name__=='__main__':unittest.main()

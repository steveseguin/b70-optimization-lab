import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from screen_jobs import jobs,command,choose,WRAPPER
from common import module
from lane_admission import Reservation,admission_scope

class ScreenTest(unittest.TestCase):
    def test_shared_wrapper_and_grid(self):
        for lane in ('A','B'):
            self.assertEqual([r['choice'] for r in jobs(lane)],['production','ordered','production'])
            for row in jobs(lane):
                c=command(row,lane,plan=True)
                self.assertEqual(c[2],str(WRAPPER/'screen.py'))
                self.assertIn('--plan',c);self.assertNotIn('--authorized-device-window',c)
                self.assertEqual(row['placement'],'1-split23')

    def test_winner_gate(self):
        rows=[dict(choice=c,rate=r,exact=True) for c,r in zip(('production','ordered','production'),(40,42,41))]
        self.assertEqual(choose(rows)['choice'],'ordered')
        for mutation in ('quality','slower','missing','order'):
            copy=[dict(r) for r in rows]
            if mutation=='quality':copy[1]['exact']=False
            if mutation=='slower':copy[1]['rate']=41
            if mutation=='missing':copy.pop()
            if mutation=='order':copy.reverse();copy[0]['choice']='ordered'
            with self.assertRaises(ValueError):choose(copy)

    def test_real_admission_registration(self):
        for lane in ('A','B'):
            self.assertEqual(admission_scope(lane,'screen'),'lane-'+lane)
            with tempfile.TemporaryDirectory() as temporary:
                lease=Reservation(lane,window='screen',root=Path(temporary))
                self.assertEqual(lease.scope,'lane-'+lane)

    def test_real_worker_import_in_closed_environment(self):
        import os,subprocess
        code='import sys;sys.path.insert(0,sys.argv[1]);import tp2_worker;from lane_admission import admission_scope;assert admission_scope("A","screen")=="lane-A"'
        subprocess.run(['/usr/bin/python3','-B','-c',code,str(WRAPPER)],env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'},stdin=subprocess.DEVNULL,check=True,timeout=30)

if __name__=='__main__':unittest.main()

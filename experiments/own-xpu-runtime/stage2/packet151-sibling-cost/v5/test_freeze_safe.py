import subprocess,sys,unittest
from freeze_safe import Budget,run
class FreezeSafe(unittest.TestCase):
 def test_pause_rearms(self):
  ticks=iter([0.,.25,600.25,600.5]);b=Budget(10,clock=lambda:next(ticks))
  self.assertEqual(b.tick(),9.75);self.assertEqual(b.tick(),10);self.assertEqual(b.pauses,1);self.assertEqual(b.tick(),9.75)
 def test_active_expiry(self):
  ticks=iter([0.,.25,.5]);b=Budget(.4,clock=lambda:next(ticks));self.assertGreater(b.tick(),0);self.assertLess(b.tick(),0)
 def test_pipes(self):
  r=run([sys.executable,'-B','-c','print("ok")'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=3,check=True);self.assertEqual(r.stdout,'ok\n')
 def test_failure(self):
  with self.assertRaises(subprocess.CalledProcessError):run([sys.executable,'-B','-c','raise SystemExit(7)'],stdin=subprocess.DEVNULL,capture_output=True,timeout=3,check=True)
if __name__=='__main__':unittest.main()

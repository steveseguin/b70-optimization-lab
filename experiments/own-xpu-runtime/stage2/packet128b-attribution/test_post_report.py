"""Coordinator report ordering: only after a successful released window."""
import subprocess,unittest
from unittest.mock import patch
import run_screen

class ReportOrdering(unittest.TestCase):
 def run_case(self,result=0,plan=False,report_failure=False):
  order=[]
  proof=dict(passed=True,native_exec_intercepted=True,device_executed=False,sources={})
  def window(argv):order.append('window-returned');return result
  def report(argv,**kw):
   order.append('analysis');self.assertEqual(order,['window-returned','analysis'])
   self.assertIn(str(run_screen.P/'analyze.py'),argv)
   self.assertEqual(kw['stdin'],subprocess.DEVNULL);self.assertTrue(kw['check'])
   if report_failure:raise subprocess.CalledProcessError(1,argv)
  with patch.object(run_screen,'read',return_value=proof),patch.object(run_screen,'verify_map'),patch.object(run_screen.screen,'main',side_effect=window),patch.object(run_screen.subprocess,'run',side_effect=report):
   value=run_screen.main(['--plan'] if plan else [])
  return value,order
 def test_report_after_success(self):self.assertEqual(self.run_case(),(0,['window-returned','analysis']))
 def test_no_report_during_plan(self):self.assertEqual(self.run_case(plan=True),(0,['window-returned']))
 def test_no_report_after_failure(self):self.assertEqual(self.run_case(result=1),(1,['window-returned']))
 def test_report_failure_surfaces_without_second_window(self):
  with self.assertRaises(subprocess.CalledProcessError):self.run_case(report_failure=True)
if __name__=='__main__':unittest.main()

import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
import screen_driver as D
import screen_window as W
from owner_teardown import finish_model_owner
import test_admission58e as F
class TeardownIntegrationTests(unittest.TestCase):
    def scenario(self, mutation=lambda row:None, *, live=False, fault=False, driver_live=False, foreign=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);proc=root/'proc';proc.mkdir();drain=root/'drain';drain.mkdir()
            out=root/'output';(out/'run/run').mkdir(parents=True)
            native=dict(passed=False,safe_to_exit=True,compute_started=True,device_executed=True,owner_cards=1,
                teardown=[dict(status='complete',safe_to_exit=True,idle_marker_complete=True,error='',exit_code=0,live_bytes=0,in_flight=0)])
            mutation(native);D.save(out/'run/run/receipt.json',native)
            with W.A.Admission('WSCREEN',out/'window.json',lambda:None,root=root/'lanes',drain_root=drain,proc=proc) as admission:
                admission.before_launch()
                owner=F.AdmissionTests().proc_owner(proc,42,'0000:23:00.0');admission.observe(dict(processes=[dict(pid=42)]))
                if not live:
                    import shutil
                    shutil.rmtree(owner)
                if foreign:F.AdmissionTests().proc_owner(proc,44,'0000:43:00.0')
                child=SimpleNamespace(pid=43,poll=lambda:None if driver_live else 1)
                def check():
                    if fault:raise ValueError('new GPU fault')
                bad=live or fault or driver_live or foreign or native['teardown'][0]['in_flight'] or not native['safe_to_exit']
                if bad:
                    with self.assertRaises(ValueError):finish_model_owner(child,out,admission,check)
                    self.assertFalse(admission.drained)
                else:
                    row=finish_model_owner(child,out,admission,check)
                    self.assertTrue(row['passed']);self.assertFalse(row['experiment_passed'])
                    self.assertTrue(admission.drained);self.assertFalse(admission.record['passed'])
                self.assertEqual((root/'lanes/active-lane-A.json').exists(),bool(bad))

    def test_postcompute_error_cleanly_drained(self):self.scenario()
    def test_live_native_retained(self):self.scenario(live=True)
    def test_live_driver_retained(self):self.scenario(driver_live=True)
    def test_new_fault_retained(self):self.scenario(fault=True)
    def test_foreign_owner_retained(self):self.scenario(foreign=True)
    def test_inflight_retained(self):self.scenario(lambda r:r['teardown'][0].update(in_flight=1))
    def test_missing_safe_exit_retained(self):self.scenario(lambda r:r.update(safe_to_exit=False))

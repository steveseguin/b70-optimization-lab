#!/usr/bin/env python3
"""CPU-only admission/supervision mocks. Never execute a device binary."""
import io
import json
import signal
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import device_window as w

class Protocol(unittest.TestCase):
    def setUp(self):
        w.BUILD.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=w.BUILD, prefix="scratch-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.build = self.root / "build"
        self.build.mkdir()
        self.binary = self.build / "fake-native"
        self.binary.write_text("not an executable\n")
        self.manifest = dict(passed=True, device_executed=False, binary="build/fake-native", hashes={"build/fake-native":w.sha(self.binary)})
        w.save(self.build / "prepared.json", self.manifest)
        for key, value in (("HERE",self.root),("BUILD",self.build),("LATCH",self.build / "latch.json")):
            p = patch.object(w,key,value)
            p.start()
            self.addCleanup(p.stop)
        p=patch.object(w.os,"getpriority",return_value=19);p.start();self.addCleanup(p.stop)
        p=patch.dict(w.os.environ,{"OMP_NUM_THREADS":"2","ONEAPI_DEVICE_SELECTOR":"","SYCL_DEVICE_FILTER":"","ZE_AFFINITY_MASK":""});p.start();self.addCleanup(p.stop)
        self.out = self.build / "future"

    def runner(self,args,**kwargs):
        return SimpleNamespace(returncode=0,stdout="idle\n" if "ionice" == args[-3] else "loader present\n",stderr="")

    def checked(self, ldd=None):
        with patch.object(w.subprocess,"run",return_value=SimpleNamespace(returncode=0,stdout="idle\n",stderr="")), patch.object(w,"ldd_preflight",side_effect=ldd or (lambda b: {"returncode":0})):
            return w.check(3,self.out)

    def test_cpu_admission_no_native(self):
        with patch.object(w.subprocess,"Popen") as launch:
            self.checked()
            launch.assert_not_called()
        self.assertFalse(w.LATCH.exists())

    def test_loader_failure_creates_no_latch(self):
        def fail(binary):raise ValueError("ldd failed")
        with self.assertRaisesRegex(ValueError,"ldd"):
            self.checked(fail)
        self.assertFalse(w.LATCH.exists())

    def test_ldd_missing_library(self):
        runner=Mock(return_value=SimpleNamespace(returncode=0,stdout="libze_loader.so => not found",stderr=""))
        with self.assertRaisesRegex(ValueError,"ldd preflight"):
            w.ldd_preflight(self.binary,runner)

    def test_changed_binary(self):
        self.binary.write_text("changed")
        with self.assertRaisesRegex(ValueError,"changed prepared identity"):
            self.checked()

    def test_reject_latch(self):
        w.save(w.LATCH,{"reason":"fault"})
        with self.assertRaisesRegex(ValueError,"latch"):
            self.checked()

    def test_preserve_first_latch(self):
        w.latch({"reason":"first"});w.latch({"reason":"second"})
        self.assertEqual(json.loads(w.LATCH.read_text())["reason"],"first")

    def test_card_bounds(self):
        with self.assertRaisesRegex(ValueError,"physical card"):
            w.check(4,self.out)

    def test_existing_output(self):
        self.out.mkdir()
        with self.assertRaisesRegex(ValueError,"fresh output"):
            self.checked()

    def test_outside_output(self):
        self.out=self.root / "outside"
        with self.assertRaisesRegex(ValueError,"fresh output"):
            self.checked()

    def test_check_does_not_discover_or_execute(self):
        with patch.object(w,"journal") as journal,patch.object(w.subprocess,"Popen") as spawn:
            self.checked()
            journal.assert_not_called();spawn.assert_not_called()

    def watch(self, mode):
        child=Mock(pid=424242,returncode=0)
        child.poll.return_value=None if mode=="stuck" else 0
        tick=[0.0]
        def now():return tick[0]
        def sleep(t):tick[0]+=t
        calls=[0]
        def reader(cursor):
            calls[0]+=1
            if mode=="journal":raise RuntimeError("lost")
            return ("Fault response\n" if mode in ("fault","stuck") else "", "cursor")
        requested=["deadline"] if mode=="deadline" else []
        result=w.supervise(child,io.StringIO(),"cursor",requested,lambda:None,now=now,sleep=sleep,reader=reader,seconds=1,drain_seconds=.2)
        if mode=="clean":
            self.assertFalse(requested);child.send_signal.assert_not_called()
        elif mode=="stuck":
            child.send_signal.assert_called_once_with(signal.SIGTERM)
            self.assertTrue(result["child_still_running"])
            self.assertIsNone(result["returncode"])
        else:
            self.assertTrue(requested);self.assertTrue(w.LATCH.exists())
        child.kill.assert_not_called();child.terminate.assert_not_called()
        return result

    def test_clean(self):self.watch("clean")
    def test_fault(self):self.watch("fault")
    def test_journal_lost(self):self.watch("journal")
    def test_deadline(self):self.watch("deadline")
    def test_stuck_child_retained(self):self.watch("stuck")
    def mock_rows(self):
        rows=[]
        for method in w.METHODS:
            for workload in w.WORKLOADS:
                for n in (100,1000,4000):
                    for repeat in range(5):
                        count=(n+7)//8 if method=="fusion8" else n
                        rows.append(dict(method=method,workload=workload,n=n,repeat=repeat,launches=count,wall_ns=count,wall_ns_per_launch=1,device_envelope_ns=count,device_envelope_ns_per_launch=1,profiled_span_ns=None,output_verified=True,mock=True))
        return rows

    def rows_file(self,rows):
        path=self.build / "mock-rows.jsonl"
        path.write_text("\n".join(json.dumps(row) for row in rows)+"\n")
        return path

    def test_complete_mock_matrix(self):
        self.assertEqual(len(w.validate_rows(self.rows_file(self.mock_rows()))),270)

    def test_missing_row(self):
        with self.assertRaisesRegex(ValueError,"matrix"):
            w.validate_rows(self.rows_file(self.mock_rows()[:-1]))

    def test_duplicate_row(self):
        rows=self.mock_rows();rows[-1]=rows[0]
        with self.assertRaisesRegex(ValueError,"matrix"):
            w.validate_rows(self.rows_file(rows))

    def test_nonfinite_timing(self):
        rows=self.mock_rows();rows[0]["wall_ns"]=float("nan")
        with self.assertRaisesRegex(ValueError,"invalid timing"):
            w.validate_rows(self.rows_file(rows))

    def test_inert_output(self):
        rows=self.mock_rows();rows[0]["output_verified"]=False
        with self.assertRaisesRegex(ValueError,"unverified"):
            w.validate_rows(self.rows_file(rows))

    def test_wrong_fusion_tail(self):
        rows=self.mock_rows();next(r for r in rows if r["method"]=="fusion8" and r["n"]==100)["launches"]=12
        with self.assertRaisesRegex(ValueError,"denominator"):
            w.validate_rows(self.rows_file(rows))

    def test_whole_window_mock(self):
        def watch(child,kernel,cursor,requested,persist):
            w.save(self.out / "device.json",dict(device_executed=True,passed=True,safe_to_exit=True,live_bytes=0,in_flight=0,rows=270,expected_rows=270))
            (self.out / "rows.jsonl").write_text(self.rows_file(self.mock_rows()).read_text())
            return dict(returncode=0,child_still_running=False)
        with patch.object(w.subprocess,"run",return_value=SimpleNamespace(returncode=0,stdout="idle\n",stderr="")),patch.object(w,"ldd_preflight",return_value={}),patch.object(w,"journal",return_value=("","cursor")),patch.object(w,"supervise",side_effect=watch),patch.object(w.subprocess,"Popen",return_value=Mock(pid=424242)) as launch:
            result=w.execute(3,self.out)
        self.assertTrue(result["passed"]);self.assertFalse(w.LATCH.exists());self.assertEqual(launch.call_count,1)

    def test_loader_runs_before_admission_latch(self):
        order=[]
        def loader(binary):
            self.assertFalse(w.LATCH.exists());order.append("ldd");return {}
        def journal(cursor=None):order.append("journal");raise ValueError("stop preflight")
        with patch.object(w.subprocess,"run",return_value=SimpleNamespace(returncode=0,stdout="idle\n",stderr="")),patch.object(w,"ldd_preflight",side_effect=loader),patch.object(w,"journal",side_effect=journal),patch.object(w.subprocess,"Popen") as launch:
            with self.assertRaisesRegex(ValueError,"stop preflight"):w.execute(3,self.out)
            launch.assert_not_called()
        self.assertEqual(order,["ldd","journal"]);self.assertFalse(w.LATCH.exists())

if __name__=="__main__":unittest.main()

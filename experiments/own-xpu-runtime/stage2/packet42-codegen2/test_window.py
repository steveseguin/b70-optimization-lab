"""End-to-end CPU-only windows, including real mock child and real summarizer."""
import errno,io,json,os,shutil,subprocess,sys,tempfile,unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch
import window
P=window.P
class Services(window.Services):
 def __init__(self,mode="ok",missing=False,fault=False,full=False):
  self.mode=mode;self.missing=missing;self.fault=fault;self.full=full;self.launched=0;self.n=0
 def seal(self):
  specs=[dict(name=("mock" if family=="gemv" else family),binary="mock_native.py",args=["--family",family]) for family in ("gemv","parallel","route","tiny","extras")]
  return dict(native_binary_sha256={"mock":"cpu-only"},windows={"K0":specs+[dict(name="floor",binary="mock_native.py",args=[])],"T1":[dict(name="mock",binary="mock_native.py",args=[])],"K2":specs})
 def boot(self):return "mock-boot"
 def journal(self,cursor=None):
  self.n+=1
  return (("old reviewed Fault response", "cursor0") if cursor is None else ("new Fault response" if self.fault else "","cursor"+str(self.n)))
 def ldd(self,binary):
  if self.missing:raise RuntimeError("missing native library: libexample.so not found")
  return "system dependencies resolved without changing LD_LIBRARY_PATH"
 def free(self):return 28_000_000_000
 def memory(self,pid):return {} # just-exited child with absent status fields
 def launch(self,argv,log):
  self.launched+=1
  argv=[sys.executable,"-B",*argv,"--mode",self.mode]
  if self.current=="K0":argv.append("--compile-smoke")
  if self.current=="T1":argv.append("--floor")
  return subprocess.Popen(window.command(argv),stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ))
 def persist(self,path,row):
  if self.full and self.launched:raise OSError(errno.ENOSPC,"No space left on device")
  return super().persist(path,row)
class Tests(unittest.TestCase):
 def setUp(self):self.root=Path(tempfile.mkdtemp(prefix="mock-",dir=P/"build"));self.count=0
 def tearDown(self):shutil.rmtree(self.root)
 def runwindow(self,name,s,k0=None,t1=None,auth=True):
  s.current=name;self.count+=1;out=self.root/(name+str(self.count))
  a=["--window",name,"--card","1","--output",str(out)]
  if auth:a.append("--authorized-device-window")
  if k0:a.extend(["--k0",str(k0/"window.json")])
  if t1:a.extend(["--t1",str(t1/"window.json")])
  with redirect_stderr(io.StringIO()) as err:code=window.main(a,s)
  return code,out,err.getvalue()
 def chain(self,mode="ok"):
  s=Services();c,k,_=self.runwindow("K0",s);self.assertEqual(c,0)
  s=Services();c,t,_=self.runwindow("T1",s,k);self.assertEqual(c,0)
  s=Services(mode=mode);c,o,e=self.runwindow("K2",s,k,t);return c,o,e
 def test_all_windows_and_summary(self):
  with patch.dict(os.environ,{"LD_LIBRARY_PATH":"/coordinator/custom-only"}):
   c,o,_=self.chain();self.assertEqual(c,0)
   self.assertEqual(json.loads((o/"mock/receipt.json").read_text())["ld_library_path"],"/coordinator/custom-only")
   self.assertEqual(json.loads((o/"dispatch-measured.json").read_text())["gemv"]["expsdown"],"p42.down.select_vector")
   self.assertFalse((o/"FAULT.json").exists())
 def test_failing_case_continues(self):
  c,o,_=self.chain("case-fail");self.assertEqual(c,0)
  self.assertFalse(json.loads((o/"window.json").read_text())["cases_passed"])
  self.assertEqual(json.loads((o/"dispatch-measured.json").read_text())["gemv"],{})
 def test_missing_library_before_contact(self):
  s=Services(missing=True);c,o,e=self.runwindow("K0",s);self.assertEqual(c,1);self.assertEqual(s.launched,0);self.assertIn("missing native library",e);self.assertFalse((o/"FAULT.json").exists())
 def test_refusal_not_fault(self):
  s=Services();c,o,e=self.runwindow("K0",s,auth=False);self.assertEqual(c,1);self.assertEqual(s.launched,0);self.assertFalse((o/"FAULT.json").exists())
 def test_new_fault_latches(self):
  s=Services(fault=True);c,o,e=self.runwindow("K0",s);self.assertEqual(c,1);self.assertTrue((o/"FAULT.json").exists())
 def test_empty_native_receipt_fails_without_latch(self):
  c,o,e=self.chain("bad-json");self.assertEqual(c,1);self.assertFalse((o/"FAULT.json").exists())
 def test_native_enospc_fails_without_latch(self):
  c,o,e=self.chain("enospc");self.assertEqual(c,1);self.assertFalse((o/"FAULT.json").exists());self.assertIn("native infrastructure",e) if "native infrastructure" in e else self.assertIn("receipt.json",e)
 def test_wrapper_full_disk_failure(self):
  s=Services(full=True);c,o,e=self.runwindow("K0",s);self.assertEqual(c,1);self.assertIn("No space left",e);self.assertFalse((o/"FAULT.json").exists());self.assertFalse(json.loads((o/"window.json").read_text())["passed"])
 def test_atomic_enospc_no_empty_receipt(self):
  path=self.root/"atomic.json"
  with patch("window.os.fsync",side_effect=OSError(errno.ENOSPC,"No space left")),redirect_stderr(io.StringIO()) as e:
   with self.assertRaises(OSError):window.persist(path,{"passed":True})
  self.assertFalse(path.exists());self.assertFalse(path.with_name("atomic.json.tmp").exists());self.assertIn("receipt write failed",e.getvalue())
 def test_summary_rejects_fake_rotation(self):
  c,o,_=self.chain();self.assertEqual(c,0)
  events=o/"mock/events.jsonl";rows=[json.loads(x) for x in events.read_text().splitlines()]
  for r in rows:r["buffer_copy"]=0
  events.write_text("".join(json.dumps(r)+"\n" for r in rows))
  from summarize import summarize
  result=summarize("K2",o);self.assertFalse(result["cases_passed"])
  self.assertEqual(json.loads((o/"dispatch-measured.json").read_text())["gemv"],{})
 def test_summary_rejects_missing_wall(self):
  c,o,_=self.chain();self.assertEqual(c,0)
  events=o/"mock/events.jsonl";rows=[json.loads(x) for x in events.read_text().splitlines()]
  for r in rows:r.pop("host_wall_us")
  events.write_text("".join(json.dumps(r)+"\n" for r in rows))
  from summarize import summarize
  self.assertFalse(summarize("K2",o)["cases_passed"])
 def test_floor_failed_case_reported(self):
  s=Services();c,k,_=self.runwindow("K0",s);self.assertEqual(c,0)
  s=Services();c,t,_=self.runwindow("T1",s,k);self.assertEqual(c,0)
  f=next((t/"mock").glob("g*-sg*-n*.json"));r=json.loads(f.read_text());r["passed"]=False;f.write_text(json.dumps(r))
  from summarize import summarize
  self.assertFalse(summarize("T1",t)["cases_passed"])
 def test_untimed_gate_does_not_block_winner(self):
  c,o,_=self.chain();self.assertEqual(c,0)
  receipt=o/"tiny/receipt.json";raw=json.loads(receipt.read_text())
  if "rows" in raw:
   timed=raw["rows"][0];raw["rows"].append(dict(timed,timing_eligible=False,workload="untimed-extra",control_gpu_us=[],candidate_gpu_us=[],control_wall_us=[],candidate_wall_us=[]));receipt.write_text(json.dumps(raw))
  else:
   receipt=o/"tiny/summary.json";raw=json.loads(receipt.read_text());timed=raw["rows"][0];raw["rows"].append(dict(timed,timing_eligible=False,workload="untimed-extra",control_gpu_us=[],candidate_gpu_us=[],control_wall_us=[],candidate_wall_us=[]));receipt.write_text(json.dumps(raw))
  from summarize import summarize
  result=summarize("K2",o);self.assertTrue(result["cases_passed"])
  key=timed.get("klass",timed.get("runtime_class",timed["class"])).split(",")[0]
  self.assertEqual(json.loads((o/"dispatch-measured.json").read_text())["classes"][key],timed["candidate"])
 def test_changed_device_environment_refused(self):
  with patch.dict(os.environ,{"ZE_AFFINITY_MASK":"0"}):
   s=Services();c,k,_=self.runwindow("K0",s);self.assertEqual(c,0)
  with patch.dict(os.environ,{"ZE_AFFINITY_MASK":"1"}):
   s=Services();c,o,e=self.runwindow("T1",s,k);self.assertEqual(c,1);self.assertEqual(s.launched,0);self.assertIn("environment",e);self.assertFalse((o/"FAULT.json").exists())
 def test_empty_bindings_k0_blocks_dependents_without_latch(self):
  s=Services(mode="empty-bindings");c,k,e=self.runwindow("K0",s)
  self.assertEqual(c,1);self.assertIn("empty compute bindings",e);self.assertFalse((k/"FAULT.json").exists())
  self.assertFalse(json.loads((k/"window.json").read_text())["passed"])
  for name in ("T1","K2"):
   s=Services();c,o,e=self.runwindow(name,s,k)
   self.assertEqual(c,1);self.assertEqual(s.launched,0);self.assertIn("K0 failed",e);self.assertFalse((o/"FAULT.json").exists())
 def test_missing_proc_status(self):self.assertEqual(window.proc_memory(999999999),{})
if __name__=="__main__":
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 window.persist(P/"protocol-tests.json",dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),passed=result.wasSuccessful(),device_executed=False,mock_native=True))
 raise SystemExit(not result.wasSuccessful())

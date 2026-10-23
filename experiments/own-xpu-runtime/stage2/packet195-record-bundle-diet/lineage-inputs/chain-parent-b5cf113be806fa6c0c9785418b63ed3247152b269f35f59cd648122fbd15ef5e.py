"""Synthetic KD scratch lifecycle tests, without subprocesses or device access."""
import ast,contextlib,io,json,shutil,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import draft_window as kd
import window
import storage
from seal40 import save,sha

class CleanupTests(unittest.TestCase):
 def setUp(self):
  storage.admit(100000)
  self.temp=tempfile.TemporaryDirectory(prefix='kd-cleanup-test-',dir=storage.B)
  self.addCleanup(self.temp.cleanup);self.out=Path(self.temp.name);self.root=self.out/'host-reference';self.root.mkdir()
  (self.root/'receipt.json').write_text('{"passed":false,"device_executed":false}')
  (self.root/'events.jsonl').write_text('{"event":"complete"}\n')
  (self.root/'fixture.bin').write_bytes(b'captured bytes')
 def child(self,status):return SimpleNamespace(pid=12345,returncode=status,poll=lambda:status)
 def invoke(self,child,failure=None,archive_success=False):
  def stub(*args,host_lifecycle,**kwargs):
   host_lifecycle['child']=child
   if failure is not None:raise failure
   if archive_success:
    kd.archive_host_reference(self.out);shutil.rmtree(self.root)
   return {'ok':True}
  with patch.object(kd,'_run',stub):return kd.run(None,self.out,{},None,{})
 def disposition(self):return json.loads((self.out/'host-reference-failure-disposition.json').read_text())
 def test_success(self):
  self.assertEqual(self.invoke(self.child(0),archive_success=True),{'ok':True})
  self.assertFalse(self.root.exists());self.assertFalse((self.out/'host-reference-failure-disposition.json').exists())
  self.assertEqual(storage.verify_archive(self.out/'host-reference.jsonl.gz')['files'],3)
 def test_comparison_failure(self):
  error=ValueError('comparison mismatch')
  with self.assertRaises(ValueError) as caught:self.invoke(self.child(0),error)
  self.assertIs(caught.exception,error);self.assertFalse(self.root.exists())
  row=self.disposition();self.assertFalse(row['passed']);self.assertTrue(row['scratch_removed']);self.assertEqual(row['host_returncode'],0)
  self.assertEqual(storage.verify_archive(self.out/'host-reference.jsonl.gz')['files'],3)
 def test_exited_host_failure(self):
  error=ValueError('host returned failure')
  with self.assertRaises(ValueError) as caught:self.invoke(self.child(2),error)
  self.assertIs(caught.exception,error);self.assertFalse(self.root.exists());self.assertEqual(self.disposition()['host_returncode'],2)
 def test_live_host_preserved(self):
  error=ValueError('host still draining')
  with self.assertRaises(ValueError) as caught:self.invoke(self.child(None),error)
  self.assertIs(caught.exception,error);self.assertTrue(self.root.exists());self.assertFalse(self.disposition()['scratch_removed'])
  self.assertFalse((self.out/'host-reference.jsonl.gz').exists())
 def test_archive_failure_preserves_original(self):
  error=ValueError('original comparison failure')
  with patch.object(kd,'archive_host_reference',side_effect=OSError('synthetic full disk')),contextlib.redirect_stderr(io.StringIO()):
   with self.assertRaises(ValueError) as caught:self.invoke(self.child(0),error)
  self.assertIs(caught.exception,error);self.assertTrue(self.root.exists())
  self.assertEqual(self.disposition()['status'],'cleanup-failed');self.assertIn('full disk',self.disposition()['cleanup_error'])
 def test_unconfirmed_host_preserved(self):
  error=ValueError('spawn failed before handle')
  with self.assertRaises(ValueError):self.invoke(None,error)
  self.assertTrue(self.root.exists());self.assertFalse(self.disposition()['scratch_removed'])

class TeardownTests(unittest.TestCase):
 # Preserve every inherited failure/pipe/storage scenario from the original
 # packet40 test, independently of the new raw-reference lifecycle cases.
 def scenario(self,receipt_error,latch_error,write_error,stalled):
  events=[];child=Mock(pid=1234)
  child.poll=Mock(side_effect=(lambda:None) if stalled else [None,None,0,0])
  def write_receipt(*unused):
   events.append('receipt')
   if receipt_error:raise OSError('No space left on device')
  def latch(*unused):
   events.append('latch')
   if latch_error:raise OSError('journal failed')
  def write(*unused):
   events.append('stop')
   if write_error:raise BrokenPipeError('closed pipe')
  ticks=iter(range(0,200,10))
  with patch.object(kd,'save',write_receipt),patch.object(kd.os,'write',write),patch.object(kd.os,'close') as close,patch.object(kd.time,'sleep'),patch.object(kd.time,'monotonic',side_effect=lambda:next(ticks)):
   watch=SimpleNamespace(latch=latch,poll_kernel=Mock(side_effect=OSError('journal failed')))
   kd.failed_owner(child,storage.P,watch,ValueError('initial fault'),9)
   self.assertEqual(events[:3],['latch','receipt','stop']);self.assertEqual(events[-1],'receipt')
   self.assertGreaterEqual(child.poll.call_count,3);self.assertGreaterEqual(watch.poll_kernel.call_count,1)
   self.assertEqual(close.call_count,int(write_error))
   if stalled:self.assertLess(child.poll.call_count,12)
 def test_normal(self):self.scenario(False,False,False,False)
 def test_disk_full_and_journal_error(self):self.scenario(True,True,False,False)
 def test_stop_write_error(self):self.scenario(True,True,True,False)
 def test_bounded_retained_owner(self):self.scenario(True,True,False,True)
 def test_post_launch_bookkeeping_guarded(self):
  tree=ast.parse((storage.P/'draft_window.py').read_text())
  guarded=[node for node in ast.walk(tree) if isinstance(node,ast.Try) and any(isinstance(handler.type,ast.Name) and handler.type.id=='Exception' for handler in node.handlers)]
  self.assertTrue(any('children.json' in ast.unparse(node.body) and 'failed_owner(child' in ast.unparse(node.handlers) for node in guarded))

class CompactionTests(unittest.TestCase):
 def watch(self,child):
  watch=object.__new__(window.Watch);watch.launched=[];watch.cpu_children=[];watch.new_gpu_fault=False
  watch.mark_cpu_child(child)
  return watch
 def test_live_cpu_blocks_compaction(self):
  child=SimpleNamespace(pid=12345,poll=lambda:None)
  watch=self.watch(child)
  self.assertEqual(window.live_owner_pids(watch),[12345]);self.assertEqual(watch.launched,[])
 def test_exited_cpu_allows_compaction(self):
  child=SimpleNamespace(pid=12345,poll=lambda:0)
  self.assertEqual(window.live_owner_pids(self.watch(child)),[])
 def test_cpu_cannot_latch_boot(self):
  watch=self.watch(SimpleNamespace(pid=12345,poll=lambda:None));watch.new_gpu_fault=True
  with patch.object(window,'save') as writer:watch.latch('ordinary CPU failure');writer.assert_not_called()
 def test_window_compaction_uses_complete_lifetime_guard(self):
  tree=ast.parse((storage.P/'window.py').read_text())
  main=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
  text=ast.unparse(main)
  self.assertIn('alive = live_owner_pids(watch)',text)
  guard=next(node for node in ast.walk(main) if isinstance(node,ast.If) and ast.unparse(node.test)=='not alive')
  self.assertIn('compress_evidence(out, record)',ast.unparse(guard))

def main():
 suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(case) for case in (CleanupTests,TeardownTests,CompactionTests))
 result=unittest.TextTestRunner(verbosity=1).run(suite)
 save(storage.P/'draft-window-cleanup-gates.json',dict(passed=result.wasSuccessful(),gates=result.testsRun,tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),device_executed=False,models_launched=0,
  inherited_teardown_checks=5,new_lifecycle_checks=6,live_cpu_compaction_checks=4,post_launch_bookkeeping_guarded=result.wasSuccessful(),
  source_sha256={name:sha(storage.P/name) for name in ('draft_window.py','window.py','test_draft_window_cleanup.py','storage.py')},scope='Five inherited teardown/pipe/storage/bookkeeping checks, six synthetic host lifecycle/archive checks, four CPU ownership/compaction checks; no child launched'))
 return not result.wasSuccessful()
if __name__=='__main__':raise SystemExit(main())

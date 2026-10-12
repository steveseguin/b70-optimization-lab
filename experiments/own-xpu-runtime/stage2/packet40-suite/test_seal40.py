#!/usr/bin/env python3
"""Pure CPU seal refusal tests: no ranks, compilers, drivers or subprocesses."""
import gzip,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import seal40 as s
class Tests(unittest.TestCase):
 def setUp(self):
  s.B.mkdir(exist_ok=True)
  self.tmp=tempfile.TemporaryDirectory(prefix='seal40-unit-',dir=s.B);self.p=Path(self.tmp.name)
  (self.p/'evidence').mkdir();(self.p/'build').mkdir();self.binary='a'*64
 def tearDown(self):self.tmp.cleanup()
 def put(self,name,value):
  f=self.p/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(value));return f
 def checklist(self,name='old.json'):return {'inherited_gates':[{'inherited_receipt':name}]}
 def ledger(self,name='gate.json',passed=True):
  self.put(name,{'passed':True,'device_executed':False});(self.p/'producer.py').write_text('pass\n')
  with gzip.open(self.p/'evidence/run.log.gz','wb') as f:f.write(b'PASS\n')
  row=dict(schema='packet40.cpu-execution.v1',passed=passed,returncode=0 if passed else 1,source_sha256={'producer.py':s.sha(self.p/'producer.py')},binary_sha256={'gnu-host/own-rt-iq3':self.binary},receipt_sha256={name:s.sha(self.p/name)},log='evidence/run.log.gz',log_sha256=s.sha(self.p/'evidence/run.log.gz'))
  self.put('evidence/qualification-unit.json',row);return row
 def cover(self,name='gate.json',counterparts=None):
  with patch.object(s,'ADDITIONAL',()),patch.object(s,'COUNTERPARTS',counterparts or {}):return s.coverage(self.checklist(name),{'gnu-host/own-rt-iq3':self.binary},self.p)
 def test_copied_passed_boolean_is_not_qualification(self):
  self.put('gate.json',{'passed':True});r=self.cover();self.assertFalse(r['passed']);self.assertIn('execution ledger',' '.join(r['problems']))
 def test_fresh_bound_ledger_qualifies(self):
  self.ledger();self.assertTrue(self.cover()['passed'])
 def test_failed_phase_cannot_qualify_partial_results(self):
  self.ledger(passed=False);self.assertFalse(self.cover()['passed'])
 def test_receipt_changed_after_execution_refused(self):
  self.ledger();self.put('gate.json',{'passed':True,'different':1});self.assertFalse(self.cover()['passed'])
 def test_source_changed_after_execution_refused(self):
  self.ledger();(self.p/'producer.py').write_text('changed\n');self.assertFalse(self.cover()['passed'])
 def test_binary_changed_after_execution_refused(self):
  self.ledger();self.binary='b'*64;self.assertFalse(self.cover()['passed'])
 def test_log_changed_after_execution_refused(self):
  self.ledger();(self.p/'evidence/run.log.gz').write_bytes(b'changed');self.assertFalse(self.cover()['passed'])
 def test_unrelated_doc_does_not_invalidate_execution(self):
  self.ledger();(self.p/'README.md').write_text('New explanation.\n');self.assertTrue(self.cover()['passed'])
 def test_unrelated_new_python_tool_does_not_invalidate_execution(self):
  self.ledger();(self.p/'unrelated.py').write_text('pass\n');self.assertTrue(self.cover()['passed'])
 def test_review_counterpart_needs_current_source_binding(self):
  (self.p/'rank.hpp').write_text('v1\n');self.put('new-review.json',{'source_review_passed':True,'source_sha256':{'rank.hpp':s.sha(self.p/'rank.hpp')}})
  with patch.object(s,'NEW_BOUND',{'new-review.json'}):self.assertTrue(self.cover('old-review.json',{'old-review.json':('new-review.json',)})['passed'])
  (self.p/'rank.hpp').write_text('v2\n')
  with patch.object(s,'NEW_BOUND',{'new-review.json'}):self.assertFalse(self.cover('old-review.json',{'old-review.json':('new-review.json',)})['passed'])
 def test_new_gate_without_binding_is_refused(self):
  self.put('new.json',{'passed':True})
  with patch.object(s,'NEW_BOUND',{'new.json'}):self.assertFalse(self.cover('new.json')['passed'])
 def test_in_progress_gate_cannot_be_promoted(self):
  self.ledger();self.put('gate.json',{'passed':True,'in_progress':True})
  row=s.read(self.p/'evidence/qualification-unit.json');row['receipt_sha256']['gate.json']=s.sha(self.p/'gate.json');self.put('evidence/qualification-unit.json',row)
  self.assertFalse(self.cover()['passed'])
 def test_device_execution_is_refused(self):
  self.ledger();self.put('gate.json',{'passed':True,'device_executed':True})
  row=s.read(self.p/'evidence/qualification-unit.json');row['receipt_sha256']['gate.json']=s.sha(self.p/'gate.json');self.put('evidence/qualification-unit.json',row)
  self.assertFalse(self.cover()['passed'])
 def test_bootstrap_excludes_only_final_admission(self):
  with patch.object(s,'ADDITIONAL',()),patch.object(s,'COUNTERPARTS',{}):
   row=s.coverage(self.checklist('window-seal-admission-gates.json'),{},self.p,bootstrap=True)
   self.assertTrue(row['passed']);self.assertEqual(row['rows'][0]['status'],'final-admission-pending')
   self.assertFalse(s.coverage(self.checklist('window-seal-admission-gates.json'),{},self.p)['passed'])
 def test_compile_and_link_precision_are_both_checked(self):
  binaries={};flags='-fno-fast-math -ffp-contract=off'
  for mode in s.MODES:
   for name in ('own-rt-iq3','nongemv-fixtures','k2-fixtures','p33-linked-fixtures'):binaries[mode+'/'+name]=self.binary
   extra=' -fdenormal-fp-math=ieee -foffload-fp32-prec-div -foffload-fp32-prec-sqrt' if mode=='device' else ''
   self.put('build/'+mode+'/compile_commands.json',[{'command':'c++ '+flags+extra}])
   path=self.p/'build'/mode/'CMakeFiles/unit.dir/link.txt';path.parent.mkdir(parents=True);path.write_text('c++ '+flags+extra)
  binaries['device/jit-smoke']=self.binary;self.put('native-build-receipt.json',{'binaries':[]})
  self.assertEqual(s.compile_identity(self.p,binaries)[0],[])
  (self.p/'build/asan/CMakeFiles/unit.dir/link.txt').write_text('c++ -fno-fast-math')
  self.assertIn('asan: precision flag missing on link',s.compile_identity(self.p,binaries)[0])
 def test_quick_native_gate_cannot_substitute_full(self):
  self.put('native-mini-cpu.json',{'cases':19,'exhaustive_ternary_patterns':13});self.assertTrue(s.semantic_checks({'native-mini-cpu.json':'x'},self.p))
 def test_python_dependency_scope_excludes_unrelated_tools(self):
  (self.p/'producer.py').write_text('import local\n');(self.p/'local.py').write_text('pass\n');(self.p/'unrelated.py').write_text('pass\n')
  found=s.python_dependencies([self.p/'producer.py'],self.p);self.assertEqual(set(found),{'producer.py','local.py'})
 def test_historical_previous_is_not_current_binary_identity(self):
  row={'passed':True,'binary_sha256':self.binary,'previous':{'binary_sha256':'b'*64}}
  self.assertEqual(s.receipt_bindings(row,{'host':self.binary},self.p),( [],0,1))
  row['binary_sha256']='c'*64
  self.assertTrue(s.receipt_bindings(row,{'host':self.binary},self.p)[0])
 def test_wrapper_needs_own_current_source_map_and_archive(self):
  row={'host_binary_sha256':self.binary}
  errors=s.wrapper_bindings(row,self.p)
  self.assertTrue(any('source binding incomplete' in e for e in errors))
  self.assertTrue(any('archive binding' in e for e in errors))
 def test_wrapper_archive_roundtrip_and_tamper(self):
  keys=('full_wrapper_gate.py','window.py','draft_window.py','capture40.py','pipeline.py','suite.py','suite_metrics.py','fixture_support.py')
  archive=self.p/'evidence/wrappers.gz'
  data={'K2/window.json':{'passed':True,'device_executed':False,'device_timing_qualified':False},'K2-failure/window.json':{'passed':False,'device_executed':False}}
  with gzip.open(archive,'wt') as stream:json.dump(data,stream)
  row={'source_sha256':dict.fromkeys(keys,'x'),'archive_path':'evidence/wrappers.gz','archive_sha256':s.sha(archive),'windows':1,'failure_windows':1,'rows':[{'label':'K2','window':'K2'}]}
  self.assertEqual(s.wrapper_bindings(row,self.p),[])
  archive.write_bytes(b'changed');self.assertTrue(s.wrapper_bindings(row,self.p))
 def test_missing_current_build_verification_refused(self):
  self.assertTrue(s.build_identity_bindings({},self.p))
 def test_nested_archived_evidence_hash_is_bound(self):
  archive=self.p/'evidence/gate.gz';archive.write_bytes(b'archive')
  row={'rows':[{'archive':{'path':'evidence/gate.gz','sha256':s.sha(archive)}}]}
  self.assertEqual(s.receipt_bindings(row,{},self.p)[0],[])
  archive.write_bytes(b'changed');self.assertTrue(s.receipt_bindings(row,{},self.p)[0])
 def test_terminal_scope_missing_decision_refuses(self):
  errors,scope=s.state_scope_bindings({},self.p)
  self.assertTrue(errors);self.assertEqual(scope['authorization'],'pending')
 def test_terminal_scope_pending_is_not_acceptance(self):
  self.put('state-scope-decision.json',{'status':'pending-owner-decision','owner_accepted':False})
  self.assertTrue(s.state_scope_bindings({},self.p)[0])
 def test_terminal_scope_acceptance_boolean_alone_refuses(self):
  self.put('state-scope-decision.json',{'status':'owner-accepted','owner_accepted':True})
  self.assertTrue(s.state_scope_bindings({},self.p)[0])
 def test_terminal_scope_unexecuted_strict_boolean_refuses(self):
  self.put('terminal-eos-all-state-gates.json',{'passed':True,'device_executed':False,'terminal_eos':True,'raw_allocation_bytes_equal':True,'all_inventoried_allocations':True,'every_mini_launch_boundary':True,'real_model_sampled_boundaries':True,'controllers':['native','python']})
  self.assertTrue(s.state_scope_bindings({},self.p)[0])
 def test_artifact_hashing_never_executes_elf(self):
  f=self.p/'build/fixture';f.write_bytes(b'\x7fELF fake fixture bytes');self.assertEqual(s.artifacts(self.p)['fixture'],s.sha(f))
 def test_retained_nested_host_issue_benchmark_is_current_artifact(self):
  f=self.p/'build/host-issue/host-issue-benchmark';f.parent.mkdir();f.write_bytes(b'\x7fELF retained host issue fixture')
  binaries=s.artifacts(self.p)
  self.assertEqual(binaries['host-issue/host-issue-benchmark'],s.sha(f))
  self.assertEqual(s.receipt_bindings({'binary_sha256':s.sha(f)},binaries,self.p)[0],[])
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 receipt={'passed':result.wasSuccessful(),'device_executed':False,'tests':result.testsRun,'subprocesses_started':0,'source_sha256':{n:s.sha(s.P/n) for n in ('seal40.py','test_seal40.py')}}
 s.save(s.P/'seal40-gates.json',receipt)
 raise SystemExit(not result.wasSuccessful())

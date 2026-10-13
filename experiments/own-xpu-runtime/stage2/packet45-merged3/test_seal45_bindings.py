#!/usr/bin/env python3
"""CPU-only positive and tamper checks for packet45 seal evidence binding."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import seal45 as seal

class SealBindings(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.fixture=next(r for r in reversed(seal.read('capacity-fixture-gates.json')['rows'])
                   if r.get('passed') and r['kind']=='nongemv' and r['compiler']=='gnu-host' and r['context']==256)
  cls.artifacts={'gnu-host/nongemv-fixtures':cls.fixture['binary_sha256']}
  cls.selection=seal.read('capacity-selection-gates.json')
  cls.native={n:seal.read(n) for n in seal.GATES if n.startswith('native-')}
 def fixture_check(self,row):
  with patch('capacity_fixture_gate.source_identity',return_value=self.fixture['identity']['sources']):
   return seal.fixture_bindings(row,self.artifacts)
 def test_current_fixture(self):
  self.assertEqual(self.fixture_check(self.fixture),self.fixture['output_sha256'])
 def test_candidate_dispatch(self):
  row=copy.deepcopy(self.fixture);row['identity']['dispatch_sha256']='0'*64
  with self.assertRaisesRegex(AssertionError,'candidate'):self.fixture_check(row)
 def test_rope(self):
  row=copy.deepcopy(self.fixture);row['identity']['rope_sha256']='0'*64
  with self.assertRaisesRegex(AssertionError,'RoPE'):self.fixture_check(row)
 def test_fixture_input(self):
  row=copy.deepcopy(self.fixture);row['identity']['fixtures_sha256']={}
  with self.assertRaisesRegex(AssertionError,'input bytes'):self.fixture_check(row)
 def test_identity_key(self):
  row=copy.deepcopy(self.fixture);row['identity_key']='0'*64
  with self.assertRaisesRegex(AssertionError,'identity key'):self.fixture_check(row)
 def test_current_output(self):
  row=copy.deepcopy(self.fixture);row['output_sha256']='0'*64
  with self.assertRaisesRegex(AssertionError,'output hash'):self.fixture_check(row)
 def test_archive_digest(self):
  row=copy.deepcopy(self.fixture);row['output_archive']['sha256']='0'*64
  with self.assertRaisesRegex(AssertionError,'evidence'):self.fixture_check(row)
 def test_archive_raw_identity(self):
  row=copy.deepcopy(self.fixture);row['output_archive']['raw_sha256']='0'*64
  with self.assertRaisesRegex(AssertionError,'compressed output'):self.fixture_check(row)
 def test_scratch_archive(self):
  row=copy.deepcopy(self.fixture);row['scratch_archive']['sha256']='0'*64
  with self.assertRaisesRegex(AssertionError,'evidence'):self.fixture_check(row)
 def test_completion_sources(self):
  with self.assertRaisesRegex(AssertionError,'stale source'):
   seal.gate_sources({'sources':{'seal45.py':'0'*64}})
 def test_selection_retired_binary_provenance(self):
  seal.selection_bindings(self.selection)
 def test_selection_scalar_source(self):
  row=copy.deepcopy(self.selection);row['source_sha256']='0'*64
  with self.assertRaisesRegex(AssertionError,'selection source'):seal.selection_bindings(row)
 def test_selection_headers(self):
  row=copy.deepcopy(self.selection);row['header_sha256']={'core_v2.hpp':'0'*64}
  with self.assertRaisesRegex(AssertionError,'stale source'):seal.selection_bindings(row)
 def test_selection_nested_sources(self):
  row=copy.deepcopy(self.selection);row['rows'][0]['source_sha256']['core_v2.hpp']='0'*64
  with self.assertRaisesRegex(AssertionError,'stale source'):seal.selection_bindings(row)
 def test_selection_raw_output(self):
  row=copy.deepcopy(self.selection);row['rows'][0]['stdout_sha256']='0'*64
  with self.assertRaisesRegex(AssertionError,'raw output'):seal.selection_bindings(row)
 def test_selection_coverage(self):
  row=copy.deepcopy(self.selection);row['rows']=row['rows'][:1]
  with self.assertRaises(AssertionError):seal.selection_bindings(row)
 def test_native_current(self):
  seal.native_bindings(self.native)
 def test_native_sources(self):
  build=seal.read('native-build-receipt.json');build['binaries'][0]['source_sha256']['native_controller.hpp']='0'*64
  with patch.object(seal,'read',return_value=build),self.assertRaisesRegex(AssertionError,'stale source'):
   seal.native_bindings(self.native)
 def test_native_asan_compile_and_link(self):
  build=seal.read('native-build-receipt.json')
  for row in build['binaries']:
   if Path(row['binary']).name=='native-controller-asan':row['command'].remove('-fsanitize=address,undefined')
  with patch.object(seal,'read',return_value=build),self.assertRaises(AssertionError):seal.native_bindings(self.native)
 def test_native_tsan_compile_and_link(self):
  build=seal.read('native-build-receipt.json')
  for row in build['binaries']:
   if Path(row['binary']).name=='native-controller-tsan-llvm22':row['command'].remove('-fsanitize=thread')
  with patch.object(seal,'read',return_value=build),self.assertRaises(AssertionError):seal.native_bindings(self.native)
 def test_native_matrix(self):
  build=seal.read('native-build-receipt.json');build['binaries'].pop()
  with patch.object(seal,'read',return_value=build),self.assertRaisesRegex(AssertionError,'matrix'):seal.native_bindings(self.native)
 def test_archive_decompressed_bytes(self):
  import gzip
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'output.gz';path.write_bytes(gzip.compress(b'actual bytes',mtime=0))
   archive=dict(path=str(path),sha256=seal.sha(path),raw_sha256='0'*64,raw_bytes=12)
   with self.assertRaisesRegex(AssertionError,'retained output bytes'):seal.archive_bound(archive,'0'*64)
 def test_native_missing_sources(self):
  build=seal.read('native-build-receipt.json');build['binaries'][0]['source_sha256']={}
  with patch.object(seal,'read',return_value=build),self.assertRaisesRegex(AssertionError,'closure incomplete'):seal.native_bindings(self.native)
 def draft(self):
  row=seal.read('capacity-draft-gates.json')
  artifacts={mode+'/own-rt-iq3':seal.read(f'draft-{mode}-c256.json')['binary_sha256'] for mode in ('gnu-host','icpx-host')}
  return row,artifacts
 def test_draft_current(self):
  row,artifacts=self.draft();seal.draft_bindings(row,artifacts)
 def test_draft_oracle(self):
  row,artifacts=self.draft();row['baseline_oracle_sha256']='0'*64
  with self.assertRaisesRegex(AssertionError,'oracle changed'):seal.draft_bindings(row,artifacts)
 def test_draft_input(self):
  row,artifacts=self.draft();row['draft_capture_input_sha256']['incident-retrospective']='0'*64
  with self.assertRaisesRegex(AssertionError,'input changed'):seal.draft_bindings(row,artifacts)
 def test_draft_aggregate(self):
  row,artifacts=self.draft();row['draft_capture_fixture_sha256_by_context']['256']={}
  with self.assertRaisesRegex(AssertionError,'aggregate'):seal.draft_bindings(row,artifacts)
 def cross(self):
  rows=[dict(context=c,draft_rank=r,passed=True,scratch_archive=dict(path=f'evidence/c{c}-r{r}.gz',sha256='2'*64))
        for c in (256,4096,32768) for r in (0,1)]
  real=dict(build=dict(binary_sha256='3'*64),rows=rows)
  computed=dict(passed=True,device_executed=False,cases=6,same_capacity_pairs=3,semantic_buffer_count=17,
    archive_sha256={r['scratch_archive']['path']:r['scratch_archive']['sha256'] for r in rows},
    rows=[dict(context=r['context'],draft_rank=r['draft_rank'],passed=True) for r in rows],stats={'guesses':7})
  gate=dict(copy.deepcopy(computed),schema='packet45.real-cross-placement.v1',input_receipt='cpu-real-gates.json',
    input_receipt_sha256='1'*64,tests_receipt_sha256='1'*64,runtime_binary_sha256='3'*64,
    sources={n:seal.sha(seal.P/n) for n in ('real_cross_placement_gate.py','mtp.hpp','native_controller.hpp')})
  tests=dict(passed=True,device_executed=False,checks=11,errors=0,failures=0,
    input_receipt_sha256=seal.sha(seal.P/'cpu-merged-gates.json'),
    source_sha256={n:seal.sha(seal.P/n) for n in ('real_cross_placement_gate.py','test_real_cross_placement_gate.py','mtp.hpp','native_controller.hpp')})
  return gate,real,{'gnu-host/own-rt-iq3':'3'*64},computed,tests
 def cross_check(self,values):
  gate,real,artifacts,computed,tests=values;original_sha=seal.sha
  def digest(path):
   return '1'*64 if Path(path).name in ('cpu-real-gates.json','real-cross-placement-tests.json') else original_sha(path)
  with patch.object(seal,'read',return_value=tests),patch.object(seal,'sha',side_effect=digest),patch('real_cross_placement_gate.check',return_value=computed):
   seal.real_cross_bindings(gate,real,artifacts)
 def test_cross_current_binding(self):self.cross_check(self.cross())
 def test_cross_input_receipt(self):
  values=self.cross();values[0]['input_receipt_sha256']='0'*64
  with self.assertRaisesRegex(AssertionError,'input changed'):self.cross_check(values)
 def test_cross_test_receipt(self):
  values=self.cross();values[0]['tests_receipt_sha256']='0'*64
  with self.assertRaisesRegex(AssertionError,'tests changed'):self.cross_check(values)
 def test_cross_checker_source(self):
  values=self.cross();values[0]['sources']['real_cross_placement_gate.py']='0'*64
  with self.assertRaisesRegex(AssertionError,'stale source'):self.cross_check(values)
 def test_cross_archive_map(self):
  values=self.cross();values[0]['archive_sha256']={}
  with self.assertRaisesRegex(AssertionError,'archive map'):self.cross_check(values)
 def test_cross_matrix(self):
  values=self.cross();values[0]['rows'].pop()
  with self.assertRaises(AssertionError):self.cross_check(values)
 def test_cross_runtime(self):
  values=self.cross();values[0]['runtime_binary_sha256']='0'*64
  with self.assertRaisesRegex(AssertionError,'binary changed'):self.cross_check(values)
 def test_cross_recomputed_result(self):
  values=self.cross();values[0]['stats']['guesses']=0
  with self.assertRaisesRegex(AssertionError,'recomputation differs'):self.cross_check(values)
 def test_cross_tests_source_closure(self):
  values=self.cross();values[4]['source_sha256']={}
  with self.assertRaisesRegex(AssertionError,'test source closure'):self.cross_check(values)
 def test_cross_tests_mini_input(self):
  values=self.cross();values[4]['input_receipt_sha256']='0'*64
  with self.assertRaisesRegex(AssertionError,'test input changed'):self.cross_check(values)
 def admission(self):
  receipt={name:{} for name in seal.ADMISSION_FIELDS};receipt.update(passed=True,device_executed=False)
  rows=[]
  for context in (256,4096,32768):
   for rank in (0,1):
    configs=[(n,'python',64) for n in ('K0','K1a','K1b','K2','W0p','KD')]
    configs += [('W2m',c,64) for c in ('python','native')]
    configs += [(n,'native',c) for n in ('WS','WSs') for c in (32,64,128)]
    for name,controller,cap in configs:
     refusal=context==256 and cap==32
     rows.append(dict(window=name,context=context,draft_rank=rank,controller=controller,token_cap=cap,
                 expected_capacity_refusal=refusal,admission_reached_blocked_launcher=not refusal,
                 device_executed=False,window_passed=False))
  admission=dict(passed=True,device_executed=False,rehearsed_seal='build-receipt.json',seal_fields=list(seal.ADMISSION_FIELDS),
    consumed_seal_sha256=hashlib.sha256(json.dumps({n:receipt[n] for n in seal.ADMISSION_FIELDS},sort_keys=True).encode()).hexdigest(),
    rows=rows,input_admissions=[{'token_cap':c} for c in (32,64,128)],gates=88)
  return receipt,admission
 def check_admission(self,receipt,admission):
  with patch.object(seal,'read',side_effect=[receipt,admission]),patch.object(seal,'sha',return_value='1'*64),patch.object(seal,'save') as save:
   result=seal.verify_window_admission();self.assertEqual(save.call_args.args[0],'window-seal-binding.json')
  return result
 def test_detached_admission_no_cycle(self):
  receipt,admission=self.admission();result=self.check_admission(receipt,admission)
  self.assertEqual(result['gates'],88);self.assertNotIn('window-seal-binding.json',seal.GATES)
 def test_detached_admission_stale_seal(self):
  receipt,admission=self.admission();receipt['input_sha256']='stale'
  with self.assertRaisesRegex(AssertionError,'different seal'):self.check_admission(receipt,admission)
 def test_detached_admission_missing_arm(self):
  receipt,admission=self.admission();admission['rows'].pop();admission['gates']-=1
  with self.assertRaisesRegex(AssertionError,'matrix incomplete'):self.check_admission(receipt,admission)
 def test_detached_admission_executed_device(self):
  receipt,admission=self.admission();admission['rows'][0]['device_executed']=True
  with self.assertRaises(AssertionError):self.check_admission(receipt,admission)

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(SealBindings))
 receipt=dict(passed=result.wasSuccessful(),device_executed=False,checks=result.testsRun,
  failures=len(result.failures),errors=len(result.errors),
  source_sha256={name:seal.sha(seal.P/name) for name in ('seal45.py','test_seal45_bindings.py')},
  scope='CPU-only receipt validators and tamper rejection; no model or fixture program executed')
 seal.save('seal45-binding-tests.json',receipt);print(json.dumps(receipt))
 raise SystemExit(not result.wasSuccessful())

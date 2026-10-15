#!/usr/bin/env python3
"""Hash-bound packet45 CPU seal; never executes an accelerator binary."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build';ROOT=P.parents[3]
GATES=('speed3-plan-gates.json','speed3-snapshot-gates.json','speed3-event-gates.json','speed3-admission-gates.json','speed2-plan-gates.json','speed2-snapshot-gates.json','speed2-snapshot-inventory.json','speed1-plan-gates.json','speed1-snapshot-gates.json','speed1-snapshot-inventory.json','seal6-amendment-tests.json','fix6-plan-gates.json','diagnostic-unsealed-tests.json','diagnostic-coordinator-gates.json','audit6-tests.json','fixture-delta-tests.json','audit6-gates.json','copy-adoption-gates.json','fusion-matrix-gates.json','hc-activation-gates.json','cpu-merged-gates.json','cpu-real-gates.json','real-cross-placement-gates.json','real-cross-placement-tests.json','capacity-selection-gates.json',
 'capacity-draft-gates.json','capacity-fixture-gates.json','asan-fixture-gates.json','p33-linked-fixture-gates.json',
 'p39-merged-fixture-gates.json','p45-kernel-tests.json','seal45-binding-tests.json','wrapper-merge-tests.json',
 'context-window-gates.json','memory-plan-gates.json','owner-gates.json','merged-campaign-completion-gates.json',
 'native-controller-cpu.json','native-controller-asan.json','native-controller-tsan.json',
 'native-mailbox-faults.json','native-mailbox-faults-asan.json','native-mailbox-faults-tsan.json')
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def read(name):return json.loads((P/name).read_text())
def save(name,row):(P/name).write_text(json.dumps(row,indent=2)+'\n')
def bound_sources(values,root=P):
 for name,digest in values.items():
  path=root/name
  if not path.exists() and (root/(name+'.py')).exists():path=root/(name+'.py')
  from seal6_amendment import source_matches
  assert source_matches(path,digest),'stale source '+str(path)
def archive_bound(archive,raw=None):
 assert sha(P/archive['path'])==archive['sha256'],'retained evidence missing/changed'
 if raw is not None:
  import gzip
  assert archive['raw_sha256']==raw,'compressed output identity differs'
  h=hashlib.sha256();size=0
  with gzip.open(P/archive['path'],'rb') as stream:
   for block in iter(lambda:stream.read(1024*1024),b''):h.update(block);size+=len(block)
  assert h.hexdigest()==raw and size==archive['raw_bytes'],'retained output bytes differ'

def gate_sources(row):
 for field in ('source_sha256','sources_sha256','sources'):
  if isinstance(row.get(field),dict):bound_sources(row[field])
def hc_bindings(gate):
 assert gate['passed'] and gate['device_executed'] is False
 bound_sources(gate['compiled_sources_sha256'],ROOT)
 required={str((P/n).relative_to(ROOT)) for n in ('hc_activation_gate.cpp','hc_activation_gate.py','adapter_fixture.cpp','detmath.hpp','core_v2.hpp','kernels.hpp','p42_tiny.hpp','p39_fused.hpp')}
 assert required<=set(gate['compiled_sources_sha256']),'HC source closure incomplete'
 assert len(gate['rows'])==6 and {(r['compiler'],r['optimization']) for r in gate['rows']}=={(c,o) for c in ('gnu','icpx') for o in ('O0','O2','O3-native')},'HC compiler matrix incomplete'
 assert gate['checks']==4752
 for row in gate['rows']:
  result=row['result']
  assert row['exit_code']==0 and result['passed'] and result['device_executed'] is False
  assert result['failures']==0 and result['checks']==792 and result['nan_payloads']==254 and result['case_count']==55,'HC coverage changed'
  assert result['hc_cases']==[dict(case=51+i,scenario=i,error=7 if i==2 else 0,active=0 if i==1 else 1,first_input=32705 if i==3 else 16080,versions=[0,1,9]) for i in range(4)],'HC fixture cases changed'
  assert sha(B/'hc-activation-gate'/(row['compiler']+'-'+row['optimization']))==row['binary_sha256'],'HC binary changed'
  assert sha(P/row['log'])==row['log_sha256'],'HC log changed'
  assert json.loads((P/row['log']).read_text().splitlines()[0])==result,'HC raw result differs'

def fusion_bindings(gate):
 assert gate['passed'] and gate['device_executed'] is False
 bound_sources(gate['compiled_sources_sha256'],ROOT)
 from fusion_matrix import SOURCES
 required={str((P/n).relative_to(ROOT)) for n in (*SOURCES,'fusion_matrix.py','adapter_fixture.cpp','dispatch_registry.hpp')}
 assert required<=set(gate['compiled_sources_sha256']),'fusion source closure incomplete'
 assert len(gate['rows'])==6 and {(r['compiler'],r['optimization']) for r in gate['rows']}=={(c,o) for c in ('gnu','icpx') for o in ('O0','O2','O3-native')},'fusion compiler matrix incomplete'
 expected={(i,v) for i in (6,7,8,9,10,49) for v in (0,1,2,6) if i>=8 or v<=1}
 for row in gate['rows']:
  result=row['result']
  assert row['exit_code']==0 and result['passed'] and result['device_executed'] is False and result['failures']==0
  assert len(result['adapter_rows'])==len(expected) and {(r['case'],r['version']) for r in result['adapter_rows']}==expected,'fusion adapter coverage incomplete'
  for r in result['adapter_rows']:
   assert r['mismatches']==0
   if r['case']>=8:assert r['passes']=={0:1,1:5,2:3,6:4}[r['version']],'fusion dispatch path changed'
  assert result['p39_checks']==56 and result['small_checks']==220 and result['checks']==372,'fusion sibling coverage incomplete'
  assert sha(B/'fusion-matrix'/(row['compiler']+'-'+row['optimization']))==row['binary_sha256'],'fusion binary changed'
  assert sha(P/row['log'])==row['log_sha256'],'fusion log changed'
  assert json.loads((P/row['log']).read_text().splitlines()[0])==result,'fusion raw result differs'
  archive_bound(row['archive'])
 assert gate['checks']==sum(r['result']['checks'] for r in gate['rows'])==2232

def fixture_bindings(row,artifacts,identity=None):
 """Validate one retained CPU fixture arm, including inputs and output evidence."""
 from capacity_fixture_gate import source_identity,LENGTHS
 import struct
 compiler,kind,context=row['compiler'],row['kind'],row['context']
 target='p33-linked-fixtures' if kind=='linked' else 'k2-fixtures' if kind=='k2-validation' else 'nongemv-fixtures'
 assert row['passed'] and row['binary_sha256']==artifacts[compiler+'/'+target]
 identity=row['identity'] if identity is None else identity
 assert identity['compiler']==compiler and identity['kind']==kind and identity['context']==context
 assert identity['binary_sha256']==row['binary_sha256']
 from seal6_amendment import fixture_identity
 assert fixture_identity(identity['sources'],source_identity(compiler,target)),'fixture source identity changed'
 assert identity['dispatch_sha256']==sha(P/'dispatch-p45.json'),'fixture candidate changed'
 assert identity['rope_sha256']==sha(P/'rope.bf16'),'fixture RoPE changed'
 current={f.name:sha(f) for f in sorted((B/'fusion-fixtures').glob('*')) if f.is_file()} if kind!='linked' else {}
 assert identity['fixtures_sha256']==current,'fixture input bytes changed'
 assert row['identity_key']==hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest(),'fixture identity key differs'
 native=row['receipt'];validation=kind.endswith('-validation')
 assert native['passed'] and native['device_executed'] is False
 assert bool(native.get('validation_only',False))==validation and native['reference_exact']==(not validation)
 if kind=='linked':assert native['checks']==row['checks']==216 and native['split_instantiations']==36
 else:
  assert context in LENGTHS and native['context']==context and native['p39_checks']==56
  ops=[]
  for name in (B/'fusion-fixtures/cases.txt').read_text().split():
   with (B/'fusion-fixtures'/name).open('rb') as stream:ops.append(struct.unpack('<ii',stream.read(8)))
  added=sum(op in (3,8,9,10,11) or (op==1 and tokens==1) for op,tokens in ops)+1+3*len(LENGTHS[context])
  expected=24+20*len(LENGTHS[context]) if kind=='k2-validation' else 116+9*len(LENGTHS[context])+added
  assert native['fixtures']==expected and native['source_fixtures']==(72 if kind=='k2-validation' else 93)+4*len(LENGTHS[context])
  assert row['checks']==native['fixtures']+native['adapter_checks']
  assert native['packet18_exact']==(not validation)
  if kind=='k2-validation':
   coverage=row['k2_capacity_binding_coverage']
   assert coverage['lengths']==LENGTHS[context] and coverage['capacity_class_workloads']==4*len(LENGTHS[context]) and coverage['validation_only']
 assert row['output_sha256']==native['output_sha256'],'fixture output hash differs'
 archive_bound(row['output_archive'],row['output_sha256']);archive_bound(row['scratch_archive'])
 assert row['teardown_summary'] and all(t['safe_to_exit'] and t['exit_code']==0 and t['in_flight']==t['live_bytes']==0 for t in row['teardown_summary'])
 return row['output_sha256']
def real_cross_bindings(gate,real,artifacts):
 """Recompute the small retained-state comparison against the completed real run."""
 from real_cross_placement_gate import check
 assert gate['schema']=='packet45.real-cross-placement.v1' and gate['passed'] and gate['device_executed'] is False
 tests=read('real-cross-placement-tests.json')
 assert tests['passed'] and tests['device_executed'] is False and tests['checks']==11 and tests['errors']==tests['failures']==0
 assert set(tests['source_sha256'])=={'real_cross_placement_gate.py','test_real_cross_placement_gate.py','mtp.hpp','native_controller.hpp'},'real cross-placement test source closure incomplete'
 assert tests['input_receipt_sha256']==sha(P/'cpu-merged-gates.json'),'real cross-placement test input changed'
 assert gate['tests_receipt_sha256']==sha(P/'real-cross-placement-tests.json'),'real cross-placement tests changed'
 gate_sources(tests)
 assert gate['input_receipt']=='cpu-real-gates.json'
 assert gate['input_receipt_sha256']==sha(P/'cpu-real-gates.json'),'real cross-placement input changed'
 assert gate['runtime_binary_sha256']==real['build']['binary_sha256']==artifacts['gnu-host/own-rt-iq3'],'real cross-placement binary changed'
 assert set(gate['sources'])=={'real_cross_placement_gate.py','mtp.hpp','native_controller.hpp'}
 bound_sources(gate['sources'])
 expected_archives={r['scratch_archive']['path']:r['scratch_archive']['sha256'] for r in real['rows']}
 assert len(expected_archives)==6 and gate['archive_sha256']==expected_archives,'real cross-placement archive map differs'
 assert gate['cases']==6 and gate['same_capacity_pairs']==3 and gate['semantic_buffer_count']==17
 matrix={(r['context'],r['draft_rank']) for r in gate['rows']}
 assert len(gate['rows'])==6 and matrix=={(c,r) for c in (256,4096,32768) for r in (0,1)}
 computed=check(real)
 for name,value in computed.items():
  assert gate[name]==value,'real cross-placement recomputation differs: '+name
def draft_bindings(draft,artifacts):
 assert draft['passed'] and draft['device_executed'] is False
 assert draft['arms']==6 and draft['contexts']==[256,4096,32768]
 assert draft['baseline_compared_arms']==6 and draft['baseline_fixture_files_per_arm']==63
 oracle=read('draft-baseline-oracle.json');oracle_hash=sha(P/'draft-baseline-oracle.json')
 assert draft['baseline_oracle_sha256']==oracle_hash,'draft oracle changed'
 assert len(oracle['valid_fixture_sha256'])==63;archive_bound(oracle['archive'])
 for name,digest in draft['draft_capture_input_sha256'].items():
  assert sha(P/('capture-input-'+name+'.json'))==digest,'draft input changed'
 assert set(draft['draft_capture_input_sha256'])=={'incident-retrospective'}
 assert len(draft['rows'])==3 and {r['context'] for r in draft['rows']}=={256,4096,32768}
 summaries={r['context']:r for r in draft['rows']};computed={}
 for context in (256,4096,32768):
  summary=summaries[context]
  assert summary['passed'] and summary['baseline_oracle_sha256']==oracle_hash
  assert summary['fixture_matches']==68 and summary['capacity_prefix_fixture_matches']==summary['baseline_fixture_matches']==63
  runs=[]
  for compiler in ('gnu-host','icpx-host'):
   run=read(f'draft-{compiler}-c{context}.json');runs.append(run)
   assert run['passed'] and run['device_executed'] is False and run['compiler']==compiler and run['context']==context
   assert run['binary_sha256']==artifacts[compiler+'/own-rt-iq3']
   assert run['dispatch_sha256']==sha(P/'dispatch-p45.json')
   table=run['argv'][run['argv'].index('--draft-capture')+1]
   assert run['table_sha256']==sha(Path(table)),'draft capture table changed'
   assert len(run['fixture_sha256'])==run['fixture_files']==68
   assert {k:v for k,v in run['fixture_sha256'].items() if k.startswith('row-')}==oracle['valid_fixture_sha256'],'draft golden output differs'
   archive_bound(run['scratch_archive'])
   label='gnu' if compiler=='gnu-host' else 'icpx'
   assert summary[label+'_binary_sha256']==run['binary_sha256'] and summary[label+'_archive']==run['scratch_archive']
  assert runs[0]['fixture_sha256']==runs[1]['fixture_sha256'],'draft compilers differ'
  computed[str(context)]=runs[0]['fixture_sha256']
 assert computed==draft['draft_capture_fixture_sha256_by_context'],'draft aggregate differs from current arms'
def selection_bindings(gate):
 """Retired selection binaries remain qualified by inputs and exact raw receipts."""
 import gzip,re
 from seal_context import precise
 assert gate['passed'] and gate['device_executed'] is False
 assert gate['source_sha256']==sha(P/'capacity_selection_gate.cpp'),'selection source changed'
 if 'header_sha256' in gate:bound_sources(gate['header_sha256'])
 assert len(gate['rows'])==2 and {r['compiler'] for r in gate['rows']}=={'gnu','icpx'}
 results=[]
 required={'capacity_selection_gate.cpp','core_v2.hpp','kernels.hpp','round2.hpp',
           'specialised.hpp','p30_attention.hpp','detmath.hpp','rope.hpp'}
 for row in gate['rows']:
  assert set(row['source_sha256'])==required;bound_sources(row['source_sha256'])
  if 'header_sha256' in row:bound_sources(row['header_sha256'])
  assert row['compiler_version'] and re.fullmatch('[0-9a-f]{64}',row['binary_sha256'])
  precise(row['command'])
  assert str(P/'capacity_selection_gate.cpp') in row['command']
  assert row['binary_retention']=='deleted_after_hashed_receipt' and row['deleted_after_hashed_receipt'] is True
  assert row['raw_output']==f"capacity-selection-{row['compiler']}.jsonl.gz"
  raw=gzip.decompress((P/row['raw_output']).read_bytes())
  assert hashlib.sha256(raw).hexdigest()==row['stdout_sha256'],'selection raw output changed'
  result=json.loads(raw);assert result==row['result'] and result['passed'] and result['device_executed'] is False
  for key,count in (('checks',427082),('selection_fixtures',48),('attention_fixtures',16),
                    ('nonfinite_backend_fixtures',48),('selection_backends',3),('attention_candidates',3)):
   assert result[key]==count,'selection coverage differs'
  results.append(result)
 assert results[0]==results[1],'selection compiler outputs differ'
def native_bindings(gates):
 from seal_context import precise
 builds=read('native-build-receipt.json');assert builds['device_executed'] is False
 by_name={Path(r['binary']).name:r for r in builds['binaries']}
 expected={family+'-'+suffix for family in ('native-controller','native-mailbox-fault') for suffix in ('test','asan','tsan-llvm22')}
 assert set(by_name)==expected and len(builds['binaries'])==len(expected),'native build matrix'
 for family,stem,count_key,count in (('native-controller','native-controller','cases',1123),('native-mailbox-fault','native-mailbox-faults','gates',5)):
  for tail,suffix in (('cpu' if family=='native-controller' else '', 'test'),('asan','asan'),('tsan','tsan-llvm22')):
   name=stem+('-'+tail if tail else '')+'.json';row=gates[name];binary=family+'-'+suffix;build=by_name[binary]
   assert row[count_key]==count and row['binary_sha256']==build['sha256']==sha(B/binary),'native test/build binary differs'
   assert row['passed'] and row.get('device_executed',False) is False
   required={'native_controller_test.cpp','native_controller.hpp'}
   if family=='native-mailbox-fault':required.add('native_mailbox_fault_test.cpp')
   assert set(build['source_sha256'])==required,'native source closure incomplete'
   assert build['compile_and_link_same_invocation'];precise(build['command']);bound_sources(build['source_sha256'])
   if suffix=='asan':assert '-fsanitize=address,undefined' in build['command']
   if suffix=='tsan-llvm22':assert '-fsanitize=thread' in build['command']
   if count_key=='cases':assert row['ternary_patterns']==1093 and row['long_random_cases']==24 and row['bounded_spin_iterations']==0
   else:assert row['repeated_requests']==32 and row['spin_iterations']==0
ADMISSION_FIELDS=('passed','sources','artifacts_sha256','model_evidence_artifacts_sha256','fixture_delta_qualification','official_manifest_sha256','memory_plan','input_sha256',
 'p33_linked_fixture_host_sha256','nongemv_fixture_host_sha256','draft_capture_fixture_sha256_by_context',
 'draft_capture_input_sha256','cpu_tests_sha256','nongemv_fixture_host_sha256_by_context')
def verify_window_admission():
 """Detached post-seal binding: intentionally excluded from GATES and seal inputs.
 Run after the no-launch rehearsal. The seal never hashes this binding back into
 itself, so its exact hash and the rehearsal hash can be bound without a cycle.
 """
 if not __debug__:raise RuntimeError('optimized Python disables seal checks')
 receipt=read('build-receipt.json');admission=read('window-seal-admission-gates.json')
 assert receipt['passed'] and receipt['device_executed'] is False
 assert admission['passed'] and admission['device_executed'] is False and admission['rehearsed_seal']=='build-receipt.json'
 assert tuple(admission['seal_fields'])==ADMISSION_FIELDS
 consumed={name:receipt[name] for name in ADMISSION_FIELDS}
 assert admission['consumed_seal_sha256']==hashlib.sha256(json.dumps(consumed,sort_keys=True).encode()).hexdigest(),'window rehearsal used a different seal'
 gate_sources(admission);assert admission['rows'] and admission['gates']==len(admission['rows'])+len(admission['input_admissions'])+1
 expected=set()
 for context in (256,4096,32768):
  for rank in (0,1):
   expected.update((context,rank,name,'python',64) for name in ('K0','K1a','K1b','K2','W0p','KD'))
   expected.update((context,rank,'W2m',controller,64) for controller in ('python','native'))
   expected.update((context,rank,name,'native',cap) for name in ('WS','WSs') for cap in (32,64,128))
 expected={(*row,0) for row in expected}
 expected.update((4096,0,name,'python',64,24) for name in ('K0','K1a','K1b','K2','W0p','KD'))
 expected.update((4096,0,'W2m',controller,64,24) for controller in ('python','native'))
 expected.update((4096,0,name,'native',cap,24) for name in ('WS','WSs') for cap in (32,64,128))
 expected.update((4096,dr,name,'native',128,split) for dr,split in ((0,0),(1,0),(0,24)) for name in ('WS128x','WS128'))
 actual={(r['context'],r['draft_rank'],r['window'],r['controller'],r['token_cap'],r['target_split']) for r in admission['rows']}
 assert actual==expected and len(admission['rows'])==len(expected),'window rehearsal matrix incomplete'
 assert len(admission['input_admissions'])==3 and {r['token_cap'] for r in admission['input_admissions']}=={32,64,128}
 for row in admission['rows']:
  assert row['device_executed'] is False and row['window_passed'] is False
  refusal=row['context']==256 and row['token_cap']==32
  assert bool(row.get('expected_capacity_refusal',False))==refusal
  assert refusal or row.get('admission_reached_blocked_launcher') is True

 result=dict(schema='packet45.detached-window-admission.v1',passed=True,device_executed=False,
  build_receipt_sha256=sha(P/'build-receipt.json'),admission_receipt_sha256=sha(P/'window-seal-admission-gates.json'),
  gates=admission['gates'],binding_rule='post-seal detached receipt; never included in build receipt inputs')
 save('window-seal-binding.json',result);return result
def main():
 if not __debug__:raise RuntimeError('optimized Python disables seal checks')
 from seal_context import build_provenance,precision_audit
 from build import sources
 from memory_plan import plan
 from math_gate import check as mathcheck
 from queue_gate import check as queuecheck
 from seal6_amendment import verify as verify_amendment,baseline
 amendment=verify_amendment()
 actual_artifacts,build_receipts=build_provenance();precision,links=precision_audit()
 # Validate retained executions against their honest historical artifact identity.
 artifacts=baseline()['artifacts_sha256'].copy()
 gates={n:read(n) for n in GATES}
 for name,row in gates.items():
  assert row.get('passed') is True and row.get('device_executed',False) is False,'incomplete CPU gate '+name
  gate_sources(row)
 hc_bindings(gates['hc-activation-gates.json'])
 fusion_bindings(gates['fusion-matrix-gates.json'])
 from audit6 import verify as verify_audit6
 verify_audit6(gates['audit6-gates.json'])
 from fixture_delta import verify as verify_fixture_delta
 fixture_delta=verify_fixture_delta(actual_artifacts)
 model_artifacts={**artifacts,**fixture_delta['historical_model_artifacts_sha256']}
 from copy_adoption_gate import verify as verify_copy_adoption
 verify_copy_adoption(gates['copy-adoption-gates.json'])
 selection_bindings(gates['capacity-selection-gates.json'])
 assert gates['seal45-binding-tests.json']['checks']==45 and gates['seal45-binding-tests.json']['errors']==gates['seal45-binding-tests.json']['failures']==0
 assert gates['p45-kernel-tests.json']['checks']>=72 and gates['p45-kernel-tests.json']['errors']==gates['p45-kernel-tests.json']['failures']==0
 assert gates['p39-merged-fixture-gates.json']['checks']==56
 assert gates['p39-merged-fixture-gates.json']['binary_sha256']==artifacts['gnu-host/p39-merged-fixtures']
 for name,count in (('cpu-merged-gates.json',79),('cpu-real-gates.json',6)):
  row=gates[name];assert row.get('completed') is True and row['cases']==len(row['rows'])==count and all(r['passed'] for r in row['rows'])
  expected_artifacts=model_artifacts if name=='cpu-real-gates.json' else artifacts
  assert row['build']['binary_sha256']==expected_artifacts['gnu-host/own-rt-iq3'],'stale model gate '+name
  if name!='cpu-real-gates.json':bound_sources(row['build']['compiled_sources_sha256'],ROOT)
  for source,digest in row['source_pins'].items():
   from seal6_amendment import source_matches
   assert source_matches(P/('dispatch-p45.json' if source=='dispatch' else source),digest),'gate harness changed '+source
  for item in row['rows']:
   archive=item['scratch_archive'];assert sha(P/archive['path'])==archive['sha256'],'missing case archive'
 real=gates['cpu-real-gates.json']
 assert {(r['context'],r['draft_rank']) for r in real['rows']}=={(c,r) for c in (256,4096,32768) for r in (0,1)}
 assert all(r['oracle_subset_tokens']==8 and r['oracle_layer_fixtures']==len(r['signature']['fixtures'])==384 for r in real['rows'])
 real_cross_bindings(gates['real-cross-placement-gates.json'],real,model_artifacts)
 fixture=gates['capacity-fixture-gates.json'];fixture_hashes=fixture['nongemv_fixture_host_sha256_by_context']
 assert set(fixture_hashes)=={'256','4096','32768'}
 current_fixture={}
 for row in fixture['rows']:
  if not row.get('passed'):continue
  target='p33-linked-fixtures' if row['kind']=='linked' else 'k2-fixtures' if row['kind']=='k2-validation' else 'nongemv-fixtures'
  if row['binary_sha256']!=artifacts[row['compiler']+'/'+target]:continue
  from capacity_fixture_gate import source_identity
  from seal6_amendment import fixture_identity
  assert fixture_identity(row['identity']['sources'],source_identity(row['compiler'],target)),'fixture source identity changed'
  fixture_bindings(row,artifacts)
  key=(row['compiler'],row['kind'],row['context'])
  if key in current_fixture:assert current_fixture[key]['output_sha256']==row['output_sha256'],'duplicate current fixtures disagree'
  current_fixture[key]=row
 required_fixture={(mode,'nongemv',context) for mode in ('gnu-host','icpx-host') for context in (256,4096,32768)}
 required_fixture|={(mode,'linked',None) for mode in ('gnu-host','icpx-host')}
 required_fixture|={('gnu-host','k2-validation',c) for c in (256,4096,32768)}|{('gnu-host','nongemv-validation',256)}
 assert set(current_fixture)==required_fixture,'incomplete current fixture matrix'
 for context in (256,4096,32768):
  outputs=[current_fixture[mode,'nongemv',context]['output_sha256'] for mode in ('gnu-host','icpx-host')]
  assert outputs[0]==outputs[1]==fixture_hashes[str(context)],'fixture cross-compiler/aggregate identity differs'
 linked=[current_fixture[mode,'linked',None]['output_sha256'] for mode in ('gnu-host','icpx-host')]
 assert linked[0]==linked[1]==fixture['p33_linked_fixture_host_sha256'],'linked cross-compiler/aggregate identity differs'
 assert gates['p33-linked-fixture-gates.json']['output_sha256']==linked[0] and gates['p33-linked-fixture-gates.json']['checks']==432

 for name in ('wrapper-merge-tests.json','context-window-gates.json'):
  if 'sources' in gates[name]:bound_sources(gates[name]['sources'])
  audit=read('evidence/storage-admission-fix/admission-audit.json')
  assert audit['passed'] and audit['device_executed'] is False
  assert gates[name]['admission_audit_sha256']==sha(P/'evidence/storage-admission-fix/admission-audit.json')
  gate_sources(audit)
  chain=gates[name]['coordinator_chains']
  assert chain['passed'] and chain['device_executed'] is False
  assert chain['copy_adoption_gate_sha256']==sha(P/'copy-adoption-gates.json'),'rehearsal lacks current full-extent/adoption gate'
  assert chain['audit6_gate_sha256']==sha(P/'audit6-gates.json'),'rehearsal lacks current production-byte audit'
  gate_sources(chain);archive_bound(chain['archive'])
  assert chain['host_binary_sha256']==artifacts['gnu-host/own-rt-iq3']
  assert [(r['context'],r['draft_rank']) for r in chain['rows']]==[(4096,0),(4096,1),(32768,0)]
  for run in chain['rows']:
   assert run['passed'] and [r['window'] for r in run['windows']]==['K0','K1a','K1b','K2','W0p','KD','W2m','WS','WSs']
   assert all(r['passed'] and r['device_executed'] is False for r in run['windows'])
   from storage import budget, projected_write_bytes
   for item in run['windows']:
    admission=item['storage_admission']
    expected=projected_write_bytes(item['window'],13 if item['window'] in ('WS','WSs') else 1,run['context'],8)
    assert admission['admitted_write_bytes']==admission['projected_build_write_bytes']==expected,'rehearsal storage projection differs'
    assert admission==budget(admission['root_free_bytes'],admission['build_bytes'],expected,expected),'rehearsal storage budget differs'

 draft=gates['capacity-draft-gates.json'];draft_bindings(draft,model_artifacts)
 native_bindings(gates)
 for row in gates['owner-gates.json']['rows']:
  assert row['binary_sha256']==artifacts[row['compiler']+'/'+row['name']]
 assert gates['owner-gates.json']['suites']==len(gates['owner-gates.json']['rows'])==18
 assert len({(r['compiler'],r['name']) for r in gates['owner-gates.json']['rows']})==18
 asan=gates['asan-fixture-gates.json'];assert asan['binary_sha256']==artifacts['asan/nongemv-fixtures']
 assert len(asan['rows'])==1
 arm=asan['rows'][0];assert (arm['compiler'],arm['kind'],arm['context'])==('asan','nongemv',32768)
 fixture_bindings(arm,artifacts);assert asan['checks']==arm['checks']

 memory=read('memory-plan.json');assert memory==plan()
 official_path=P.parent/'packet38-integrated/official-tensors.json';official=json.loads(official_path.read_text())
 source_hashes=sources()
 for path in (P/'coordinator_windows.sh',P/'memory-plan.json',P/'merge-start.json',P/'draft-baseline-oracle.json',P/'seal6-amendment.json',ROOT/'scripts/promotion_evidence.py',official_path):source_hashes[str(path.relative_to(ROOT))]=sha(path)
 review_hashes={n:sha(P/n) for n in ('review-draft-rank0.md','review-memory.md')}
 counts=dict(speed3_plan_dispatch_rows=72,speed3_mini_cases=63,speed3_full_state_checks=54,speed3_required_extent_negative_controls=6,speed3_event_checks=16,speed3_admission_checks=10,speed2_plan_dispatch_rows=48,speed2_mini_cases=42,speed2_full_state_checks=36,speed2_required_extent_negative_controls=4,speed1_plan_dispatch_rows=48,speed1_mini_cases=42,speed1_full_state_checks=36,speed1_required_extent_negative_controls=4,audit6_windows=28,audit6_mutation_tests=8,fixture_delta_tests=gates['fixture-delta-tests.json']['checks'],fresh_real_sentinel_cases=0,historical_real_cases_reused=6,fusion_matrix_checks=gates['fusion-matrix-gates.json']['checks'],fusion_compiler_arms=6,hc_activation_checks=4752,hc_compiler_arms=6,merged_historical_cases=79,real_native_cases=6,real_token_matches=48,real_layer_fixture_matches=2304,
   fix6_plan_dispatch_rows=48,fix6_group_mutation_checks=9,seal6_amendment_tests=gates['seal6-amendment-tests.json']['checks'],real_cross_placement_pairs=3,real_draft_semantic_buffers=17,
   selection_checks=sum(r['result']['checks'] for r in gates['capacity-selection-gates.json']['rows']),
   draft_capture_arms=6,draft_valid_fixture_matches=378,
   native_controller_cases=3369,mailbox_gates=15,wrapper_tests=gates['wrapper-merge-tests.json']['tests'])
 cpu=dict(schema='packet45.cpu-seal.v1',passed=True,device_executed=False,gate_receipts={n:sha(P/n) for n in GATES},counts=counts)
 save('cpu-tests.json',cpu)
 receipt=dict(schema='own-runtime.iq3.packet45.build.v1',passed=True,device_executed=False,
  seal_status='CPU integration qualified; device windows pending',real_model_device_qualified=False,
  post_seal_admission=dict(path='window-seal-binding.json',scope='detached exact build/admission receipt hashes; build receipt remains unchanged'),
  admitted_target_splits=[dict(target_split=0,draft_ranks=[0,1],contexts=[256,4096,32768]),dict(target_split=24,draft_ranks=[0],contexts=[4096])],
  arithmetic='iq3-p17-detmath-v2',context_capacities=[256,4096,32768],draft_ranks=[0,1],
  parent_pins=read('merge-start.json'),sources=source_hashes,artifacts_sha256=actual_artifacts,
  seal_amendment=amendment,retained_gate_artifacts_sha256=artifacts,
  fixture_delta_qualification=fixture_delta,model_evidence_artifacts_sha256=model_artifacts,
  mode_build_receipts_sha256=build_receipts,precision=precision,link_commands=links,
  input_sha256=sha(B/'input/input.json'),official_manifest_sha256=sha(P/'mtp-manifest.tsv'),
  official_tensor_receipt_sha256=sha(official_path),official_tensor_receipt_path=str(official_path.relative_to(ROOT)),
  official_tensor_sha256={n:r['sha256'] for n,r in official['tensors'].items()},
  nongemv_fixture_host_sha256_by_context=fixture_hashes,nongemv_fixture_host_sha256=fixture_hashes['256'],
  p33_linked_fixture_host_sha256=fixture['p33_linked_fixture_host_sha256'],
  draft_capture_fixture_sha256_by_context=draft['draft_capture_fixture_sha256_by_context'],
  draft_capture_input_sha256=draft['draft_capture_input_sha256'],draft_baseline_oracle_sha256=sha(P/'draft-baseline-oracle.json'),
  cpu_tests_sha256=sha(P/'cpu-tests.json'),gate_receipts=cpu['gate_receipts'],gate_counts=counts,
  independent_reviews_sha256=review_hashes,native_build_receipt_sha256=sha(P/'native-build-receipt.json'),
  math_gate=mathcheck(),queue_gate=queuecheck(),memory_plan=memory,
  max_compile_jobs=2,max_cpu_bound_processes=4,numeric_threads_per_rank=2,anonymous_memory_limit_bytes=10_000_000_000,
  pending=['coordinator device chain at each capacity and draft placement','merged per-class and full-model speed',
    'measured 22/26 balance and reverse-handoff overlap','actual card allocation/driver overhead',
    'complete manifest-bound 32/64/128-token model suites on merged device binary'],
  real_cpu_scope='six historical pre-fix6/pre-SPEED1 native first-eight-token checks of the first fixed suite prompt; not full suite or speed evidence')
 save('build-receipt.json',receipt)
 (P/'BINARY-HASHES.md').write_text('# Binary SHA256\n\nBuilt on the CPU; no device program executed.\n\n| Binary | SHA256 |\n|---|---|\n'+''.join(f'| {n} | `{h}` |\n' for n,h in sorted(actual_artifacts.items())))
 print(json.dumps(dict(passed=True,gate_receipts=len(GATES),binary_hashes=len(artifacts),counts=counts)))
if __name__=='__main__':main()

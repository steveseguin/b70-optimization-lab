#!/usr/bin/env python3
"""Fail-closed packet44 CPU qualification seal. Never executes a model/device binary."""
import argparse,gzip,hashlib,json,re,shlex,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
B=P/'build'
ROOT=P.parents[3]
CONTEXTS=(256,4096,32768)
COMPILERS=('gnu-host','icpx-host')
MODES=(*COMPILERS,'asan','device')
PRECISE=('-fno-fast-math','-ffp-contract=off')
DEVICE_PRECISE=('-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt')
GATES=('capacity-cpu-gates.json','capacity-rollback-asan.json','draft-auth-gates.json','capacity-selection-gates.json','capacity-draft-gates.json',
 'capacity-fixture-gates.json','capacity-fixture-light-tests.json','p33-linked-fixture-gates.json','context-window-gates.json',
 'window-mocked-inherited-tests.json','memory-plan-gates.json','owner-gates.json',
 'argument-block-tests.json','prepared-invalidation.json','kernel-sizes.json',
 'mini-gnu-host.json','mini-icpx-host.json','mini-asan.json','mtp-gates-gnu-host.json','mtp-gates-icpx-host.json','mtp-gates-asan.json','native-mini-cpu.json','inherited-python-gates.json',
 'native-controller-cpu.json','native-controller-asan.json','native-controller-tsan.json',
 'native-mailbox-faults.json','native-mailbox-faults-asan.json','native-mailbox-faults-tsan.json')
NATIVE=(('native-controller-cpu.json','native-controller-test','cases',1123),
 ('native-controller-asan.json','native-controller-asan','cases',1123),
 ('native-controller-tsan.json','native-controller-tsan-llvm22','cases',1123),
 ('native-mailbox-faults.json','native-mailbox-fault-test','gates',5),
 ('native-mailbox-faults-asan.json','native-mailbox-fault-asan','gates',5),
 ('native-mailbox-faults-tsan.json','native-mailbox-fault-tsan-llvm22','gates',5))


def require(ok,message):
 if not ok:raise ValueError(message)


def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
 return h.hexdigest()


def read(name):return json.loads((P/name).read_text())


def source_map(values,root=P):
 require(isinstance(values,dict) and values,'empty source binding')
 for name,digest in values.items():
  path=root/name
  if not path.is_file() and (root/(name+'.py')).is_file():path=root/(name+'.py')
  require(sha(path)==digest,'source changed: '+str(path))


def precise(arguments,device=False):
 words=shlex.split(arguments) if isinstance(arguments,str) else list(arguments)
 require(all(flag in words for flag in (*PRECISE,*(DEVICE_PRECISE if device else ()))),'missing precision flag: '+str(words))
 forbidden={'-Ofast','-ffast-math','-fassociative-math','-funsafe-math-optimizations','-ffinite-math-only','-freciprocal-math'}
 require(not forbidden.intersection(words),'unsafe arithmetic flag')
 require(not any(w.startswith('-ffp-contract=') and w!='-ffp-contract=off' for w in words),'FP contraction override')
 require(not any(w.startswith('-fdenormal-fp-math=') and w!='-fdenormal-fp-math=ieee' for w in words),'denormal override')
 return words


def precision_audit():
 result={};link_commands={}
 for mode in MODES:
  file=B/mode/'compile_commands.json';commands=json.loads(file.read_text())
  links=sorted((B/mode).rglob('link.txt'))
  require(commands and links,'missing compile/link proof '+mode)
  for row in commands:precise(row.get('arguments',row.get('command')),mode=='device')
  for file_link in links:
   text=file_link.read_text();precise(text,mode=='device')
   link_commands[str(file_link.relative_to(B))]=text
  result[mode]=dict(flags=list(PRECISE+(DEVICE_PRECISE if mode=='device' else ())),
   compile_count=len(commands),link_count=len(links),compile_commands_sha256=sha(file),
   link_files_sha256={str(f.relative_to(B)):sha(f) for f in links})
 return result,link_commands


def build_provenance():
 from build import compiled_sources
 current=compiled_sources();artifacts={};proofs={}
 for mode in MODES:
  name=f'build-{mode}-receipt.json';row=read(name)
  require(row.get('passed') is True and row.get('device_executed') is False and row.get('mode')==mode,'bad build provenance '+mode)
  require(row['compiled_sources_sha256']==current,'compiled source identity changed after '+mode+' build')
  require(row['compile_commands_sha256']==sha(B/mode/'compile_commands.json'),'compile command identity changed '+mode)
  for filename,digest in row['link_files_sha256'].items():require(sha(B/filename)==digest,'link changed '+filename)
  for filename,digest in row['artifacts_sha256'].items():
   require(sha(B/filename)==digest,'binary changed '+filename);artifacts[filename]=digest
  required=('own-rt-iq3','nongemv-fixtures','k2-fixtures','p33-linked-fixtures')+(('jit-smoke',) if mode=='device' else ('authority-tests','owner-retirement-tests','chain-tests','queue-tests','lifetime-tests','prepared-invalidation-tests'))
  require(all(mode+'/'+n in artifacts for n in required),'missing built target '+mode)
  proofs[name]=sha(P/name)
 return artifacts,proofs


def gates_load():
 gates={}
 for name in GATES:
  row=read(name);require(row.get('passed') is True,'CPU gate incomplete: '+name)
  require(row.get('device_executed',False) is False,'device evidence cannot substitute for CPU gate: '+name)
  for field in ('source_sha256','sources_sha256'):
   if isinstance(row.get(field),dict):source_map(row[field])
  gates[name]=row
 return gates


def binary_bound(row,name,artifacts):
 require(row['binary_sha256']==artifacts[name],'gate used stale binary '+name)


def cpu_capacity(gates,artifacts):
 from capacity_cpu_gate import source_identity,entries,MANIFEST
 row=gates['capacity-cpu-gates.json'];source=source_identity()
 require(row['source_sha256']==source,'capacity CPU source identity changed')
 chosen,development=entries(json.loads(MANIFEST.read_text()));prompts={e['prompt_id'] for e in chosen}
 require(len(prompts)>=3,'fewer than three suite prompts')
 expected={(compiler,'suite',c,'none','native',f'suite-{prompt}-{c}') for compiler in COMPILERS for prompt in prompts for c in CONTEXTS}
 expected|={(compiler,'modes',4096,mode,'native',f'development-4096-{mode}') for compiler in COMPILERS for mode in ('none','hit','miss','mtp')}
 expected|={(compiler,'rollback',4096,mode,controller,f'rollback-4096-{controller}-{mode}') for compiler in COMPILERS for controller in ('python','native') for mode in ('none','hit','miss')}
 actual={}
 for item in row['rows']:
  compiler=item['compiler'];identity=item['identity']
  if item.get('passed') is not True or identity.get('source_sha256')!=source or identity.get('binary_sha256')!=artifacts.get(compiler+'/own-rt-iq3'):continue
  key=(compiler,item['phase'],item['capacity'],item['mode'],item['controller'],item['case'])
  require(key not in actual or item['tokens']==actual[key]['tokens'],'duplicate current case disagrees')
  require(item.get('device_executed') is False and item['token_matches']==len(item['tokens'])==8,'capacity CPU token gate')
  layer_count=32 if item['phase']=='rollback' else 384
  require(item['layer_matches']==len(item['fixture_sha256'])==layer_count,'capacity CPU fixture count')
  require(identity['manifest_sha256']==sha(MANIFEST),'capacity suite manifest changed')
  if item['phase']!='rollback':
   require(item['tokens']==identity['oracle_tokens'] and item['fixture_sha256']==identity['oracle_fixtures'],'capacity CPU oracle disagreement')
  if item['mode']=='hit':require(item['stats']['hits']==7 and item['stats']['misses']==0,'all-hit gate')
  if item['mode']=='miss':require(item['stats']['misses']==7 and item['stats']['hits']==0,'all-miss gate')
  if item['phase']=='rollback' and item['mode']=='miss':
   require(item['boundary_32_discarded'] is True and item['boundary_timing_rows'],'block-boundary rollback not proven')
   require(all(t['launch_extent']==64 and t['capacity_reprepares']>0 for t in item['boundary_timing_rows']),'rollback reprepare evidence')
  archive=item.get('archive');require(archive and sha(P/archive['path'])==archive['sha256'],'CPU fixture archive missing/changed')
  actual[key]=item
 require(set(actual)==expected and len(actual)==38,'capacity CPU matrix does not contain exactly the required 38 current cases')
 for compiler in COMPILERS:
  for prompt in prompts:
   rows=[actual[(compiler,'suite',c,'none','native',f'suite-{prompt}-{c}')] for c in CONTEXTS]
   require(all((r['tokens'],r['fixture_sha256'])==(rows[0]['tokens'],rows[0]['fixture_sha256']) for r in rows),'cross-capacity valid output differs')
 return dict(cases=len(actual),token_matches=sum(r['token_matches'] for r in actual.values()),layer_matches=sum(r['layer_matches'] for r in actual.values()),suite_prompts=sorted(prompts))


def rollback_asan(gates,artifacts):
 from capacity_cpu_gate import source_identity,MANIFEST
 ledger=gates['capacity-rollback-asan.json'];sources=source_identity()
 binary_bound(ledger,'asan/own-rt-iq3',artifacts)
 require(ledger['source_sha256']==sources and ledger['cases']==6,'ASAN rollback source/coverage')
 expected={(controller,mode) for controller in ('python','native') for mode in ('none','hit','miss')}
 current={}
 for row in ledger['rows']:
  identity=row['identity']
  if not row.get('passed') or identity.get('source_sha256')!=sources or identity.get('binary_sha256')!=artifacts['asan/own-rt-iq3']:continue
  require(row['compiler']=='asan' and row['phase']=='rollback' and row['capacity']==4096 and row['device_executed'] is False,'ASAN rollback execution identity')
  require(row['token_matches']==len(row['tokens'])==8 and row['layer_matches']==len(row['fixture_sha256'])==32,'ASAN rollback token/layer coverage')
  require(row['host_memory']=='resident' and identity['manifest_sha256']==sha(MANIFEST),'ASAN rollback resident/manifest identity')
  if row['mode']=='hit':require(row['stats']['hits']==7 and row['stats']['misses']==0,'ASAN all-hit coverage')
  if row['mode']=='miss':
   require(row['stats']['hits']==0 and row['stats']['misses']==7 and row['boundary_32_discarded'] is True,'ASAN block-boundary discard missing')
   require(row['boundary_timing_rows'] and all(t['launch_extent']==64 and t['capacity_reprepares']>0 for t in row['boundary_timing_rows']),'ASAN launch-boundary reprepare evidence')
  archive=row.get('archive');require(archive and sha(P/archive['path'])==archive['sha256'],'ASAN rollback archive missing/changed')
  key=(row['controller'],row['mode']);require(key in expected,'unexpected ASAN rollback case');current[key]=row
 require(set(current)==expected,'ASAN rollback needs six current cases')
 baseline=current[('python','none')]
 require(all((r['tokens'],r['fixture_sha256'])==(baseline['tokens'],baseline['fixture_sha256']) for r in current.values()),'ASAN rollback mode/controller byte mismatch')
 return dict(cases=6,token_matches=48,layer_matches=192,discarded_boundary_cases=2)


def draft_authentication(gates,artifacts):
 gate=gates['draft-auth-gates.json'];binary_bound(gate,'gnu-host/own-rt-iq3',artifacts)
 expected={'missing':'draft manifest missing','truncated':'missing official draft tensors',
  'hash':'official draft tensor SHA256 mismatch','identity':'official draft file changed'}
 require(gate['cases']==len(gate['rows'])==4 and {r['case'] for r in gate['rows']}==set(expected),'draft authentication requires four distinct rejection cases')
 for row in gate['rows']:
  native=row['receipt'];failure=row['failure_before_teardown'];message=expected[row['case']]
  require(row['expected']==message and native['passed'] is False and native['device_executed'] is False and message in native['error'],'draft authentication did not reject expected error')
  require(failure['passed'] is False and message in failure['error'],'draft authentication missing failure-before-teardown evidence')
  teardown=native['teardown'];require(len(teardown)==1 and all(t['safe_to_exit'] and t['in_flight']==t['live_bytes']==0 for t in teardown),'draft authentication owner teardown incomplete')


def selection(gates,artifacts):
 row=gates['capacity-selection-gates.json'];require({r['compiler'] for r in row['rows']}=={'gnu','icpx'},'selection requires both compilers')
 outputs=[];disposed={}
 for r in row['rows']:
  source_map(r['source_sha256']);precise(r['command']);result=r['result']
  require(result['passed'] and not result['device_executed'] and result['selection_fixtures']>=48 and result['attention_fixtures']>=16,'selection fixture coverage')
  require(result['selection_backends']>=3 and result['attention_candidates']>=3 and result['nonfinite_backend_fixtures']>=48,'selection backend/NaN coverage')
  binary=B/'capacity-selection'/('selection-'+r['compiler'])
  require(re.fullmatch('[0-9a-f]{64}',r['binary_sha256']) is not None,'selection executed binary hash missing')
  if binary.exists():require(sha(binary)==r['binary_sha256'],'selection binary changed')
  else:require(r.get('binary_retention')=='deleted_after_hashed_receipt','selection binary absent without explicit scratch cleanup record')
  disposed[str(binary.relative_to(B))]=dict(sha256=r['binary_sha256'],retention=r.get('binary_retention','present_at_seal'),scope='executed CPU fixture only; not a coordinator window binary')
  with gzip.open(P/r['raw_output'],'rb') as f:raw=f.read()
  require(hashlib.sha256(raw).hexdigest()==r['stdout_sha256'] and json.loads(raw)==result,'selection raw evidence changed');outputs.append(result)
 require(outputs[0]==outputs[1],'selection compilers differ')
 return disposed


def draft(gates,artifacts):
 from capacity_draft_gate import fixtures
 from draft_baseline import load as load_baseline, ORACLE
 baseline=load_baseline();baseline_hash=sha(ORACLE)
 row=gates['capacity-draft-gates.json'];require(row['arms']==6 and row['contexts']==list(CONTEXTS),'draft capacity coverage')
 require(row['capture_rows']==94 and row['generated_prefix_tokens']==8,'draft prefix coverage')
 require(row['retained_reference_bytes']<300_000_000,'draft retained-reference budget')
 require(row['baseline_oracle_sha256']==baseline_hash and row['baseline_compared_arms']==6 and row['baseline_fixture_files_per_arm']==63,'frozen packet38 draft comparison missing')
 sealed={};prefix=None
 input_file=P/'capture-input-incident-retrospective.json';inp=json.loads(input_file.read_text());table=B/'capture-incident-retrospective.tsv'
 require(sha(table)==inp['table_sha256'],'draft capture table changed')
 require(inp['source_capture_receipt_sha256']==baseline['source_receipts']['capture-input-incident-retrospective.json']['sha256'],'draft frozen/input source differs')
 for name,digest in inp['streams'].items():require(sha(B/'captured-incident-retrospective'/name)==digest,'draft captured input changed')
 for c in CONTEXTS:
  run=read(f'capture-run-incident-retrospective-c{c}.json');require(run['passed'] is True and run['device_executed'] is False,'draft CPU reference failed')
  binary_bound(run,'gnu-host/own-rt-iq3',artifacts);require(run['context']==c and run['table_sha256']==sha(table),'draft reference context/input')
  require(run['dispatch_sha256']==sha(P/'dispatch-p38.json'),'draft reference dispatch changed')
  reference=Path(run['output']).resolve();require(reference==B.resolve()/f'draft-reference-c{c}','draft reference outside expected directory')
  actual=fixtures(reference);require(actual==run['fixture_sha256']==row['draft_capture_fixture_sha256_by_context'][str(c)],'draft reference fixture bytes changed')
  compare=next((r for r in row['rows'] if r['context']==c),None)
  require(compare and compare['passed'] and compare['compilers']==list(COMPILERS),'draft compiler comparison missing')
  require(compare['baseline_oracle_sha256']==baseline_hash and compare['baseline_fixture_matches']==63,'draft baseline comparison stale/incomplete')
  require(compare['gnu_binary_sha256']==artifacts['gnu-host/own-rt-iq3'] and compare['icpx_binary_sha256']==artifacts['icpx-host/own-rt-iq3'],'draft comparison binary stale')
  icpx=read(f'draft-icpx-host-c{c}.json');binary_bound(icpx,'icpx-host/own-rt-iq3',artifacts)
  require(icpx['passed'] and icpx['fixture_sha256']==actual,'icpx draft bytes differ')
  archive=compare['icpx_archive'];require(sha(P/archive['path'])==archive['sha256'],'icpx draft archive changed')
  current={k:v for k,v in actual.items() if k.startswith('row-')}
  require(current==baseline['valid_fixture_sha256'],'draft valid-position bytes differ from frozen packet38 oracle')
  if prefix is None:prefix=current
  require(current==prefix,'draft valid-position output depends on capacity');sealed[str(c)]=actual
 expected={'incident-retrospective':sha(input_file)}
 require(expected==row['draft_capture_input_sha256'],'draft input receipt stale')
 return sealed,expected


def fixtures_gate(gates,artifacts):
 from capacity_fixture_gate import source_identity,LENGTHS
 row=gates['capacity-fixture-gates.json'];required={(compiler,'nongemv',c) for compiler in COMPILERS for c in CONTEXTS}
 required|={(compiler,'linked',None) for compiler in COMPILERS}
 required|={('gnu-host','k2-validation',c) for c in CONTEXTS}|{('gnu-host','nongemv-validation',256)}
 accepted={};digests={};identities={}
 for r in row['rows']:
  if not r.get('passed'):continue
  c=r['context'];compiler=r['compiler'];kind=r['kind']
  target='p33-linked-fixtures' if kind=='linked' else 'k2-fixtures' if kind=='k2-validation' else 'nongemv-fixtures'
  if r['binary_sha256']!=artifacts.get(compiler+'/'+target):continue
  cache_key=(compiler,target)
  if cache_key not in identities:identities[cache_key]=source_identity(compiler,target)
  if r['identity']['sources']!=identities[cache_key]:continue
  binary_bound(r,compiler+'/'+target,artifacts);native=r['receipt'];validation=kind.endswith('-validation')
  require(native.get('passed') is True and native.get('device_executed') is False,'fixture native CPU pass missing')
  require(bool(native.get('reference_exact')) is (not validation),'fixture exact/reference scope')
  if kind!='linked':
   require(native['context']==c and c in CONTEXTS,'fixture context identity')
   expected_count=18+14*len(LENGTHS[c]) if kind=='k2-validation' else 116+9*len(LENGTHS[c])
   require(native['fixtures']==expected_count,'registered capacity fixture count')
   if not validation:require(native['packet18_exact'] is True,'packet18 exactness missing')
  digest=native['output_sha256'];require(r['output_sha256']==digest,'fixture aggregate hash differs')
  for key in ('output_archive','scratch_archive'):
   archive=r[key];require(sha(P/archive['path'])==archive['sha256'],'fixture archive changed')
  require(r['output_archive']['raw_sha256']==digest,'compressed fixture raw digest differs')
  require(r['teardown_summary'] and all(t['safe_to_exit'] and t['exit_code']==0 and t['in_flight']==t['live_bytes']==0 for t in r['teardown_summary']),'fixture owner teardown')
  if kind=='nongemv':
   if c in digests:require(digests[c]==digest,'fixture output differs between compilers')
   digests[c]=digest
  if kind=='k2-validation':
   coverage=r['k2_capacity_binding_coverage']
   require(coverage['lengths']==LENGTHS[c] and coverage['capacity_class_workloads']==4*len(LENGTHS[c]) and coverage['validation_only'],'K2 capacity binding coverage')
  accepted[(compiler,kind,c)]=r
 require(set(accepted)==required,'fixture arithmetic/validation matrix incomplete or stale')
 expected={str(c):digests[c] for c in CONTEXTS}
 require(row['nongemv_fixture_host_sha256_by_context']==expected,'fixture context digest map differs')
 linked=gates['p33-linked-fixture-gates.json'];compilers=set()
 for r in linked['rows']:
  binary_bound(r,r['compiler']+'/p33-linked-fixtures',artifacts);native=r['receipt'];compilers.add(r['compiler'])
  require(native['passed'] and not native['device_executed'] and native['reference_exact'],'linked fixture exactness')
  require(native['checks']==216 and native['split_instantiations']==36 and native['argument_limit_bytes']==1024,'linked fixture coverage')
  require(native['output_sha256']==linked['output_sha256'],'linked fixture digest differs')
 require(set(COMPILERS)<=compilers,'linked fixtures require both compilers')
 light=gates['capacity-fixture-light-tests.json']
 require(light['passed'] and light['tests']>0 and light['storage_race_checks']>0 and light['window_storage_checks']>0,'K2/storage light regression missing')
 require(sha(P/light['archive']['path'])==light['archive']['sha256'],'K2/storage regression archive changed')
 return expected,linked['output_sha256']


def support(gates,artifacts):
 owners=gates['owner-gates.json'];expected={(c,n) for c in COMPILERS for n in ('authority-tests','owner-retirement-tests','chain-tests','queue-tests','lifetime-tests')}
 require({(r['compiler'],r['name']) for r in owners['rows']}==expected and owners['suites']==10,'owner/lifetime coverage')
 for r in owners['rows']:binary_bound(r,r['compiler']+'/'+r['name'],artifacts)
 for compiler in (*COMPILERS,'asan'):
  for stem,count in (('mini',130 if compiler=='gnu-host' else 7),('mtp-gates',7)):
   r=gates[f'{stem}-{compiler}.json'];binary_bound(r,compiler+'/own-rt-iq3',artifacts);require(r['cases']==count,'mini/MTP scenario coverage')
 native_mini=gates['native-mini-cpu.json'];binary_bound(native_mini,'gnu-host/own-rt-iq3',artifacts)
 require(native_mini['cases']==1109 and native_mini['exhaustive_ternary_patterns']==1093 and native_mini['long_random_cases']==12,'actual Engine native controller coverage')
 argument=gates['argument-block-tests.json'];require(argument['checks']==16,'argument gate count')
 require(sha(P/'argument_block_test.cpp')==argument['source_sha256'] and sha(P/'argument_block.hpp')==argument['serializer_sha256'],'argument source binding')
 for name,binary in (('argument-block-tests.json','argument-block-test'),('prepared-invalidation.json','prepared-invalidation-tests-asan')):
  r=gates[name];require(sha(B/binary)==r['binary_sha256'],'unit binary changed');precise(r['compile_argv']);artifacts[binary]=r['binary_sha256']
 invalid=gates['prepared-invalidation.json'];require(invalid['tests']==15 and set(invalid['sanitizers'])=={'address','undefined'} and invalid['leak_detection'],'prepared lifetime sanitizer evidence')
 native_build=read('native-build-receipt.json');native_rows={Path(r['binary']).name:r for r in native_build['binaries']}
 for gate,binary,count_key,count in NATIVE:
  r=gates[gate];build=native_rows[binary];require(r[count_key]==count,'native controller/fault coverage')
  require(sha(B/binary)==r['binary_sha256']==build['sha256'],'native binary identity changed')
  require(build['compile_and_link_same_invocation'] is True,'native compile/link precision proof missing');precise(build['command']);source_map(build['source_sha256'])
  if 'asan' in binary:require('-fsanitize=address,undefined' in build['command'],'native ASAN+UBSAN not enabled')
  if 'tsan' in binary:require('-fsanitize=thread' in build['command'],'native TSan not enabled')
  if count_key=='cases':require(r['ternary_patterns']==1093 and r['long_random_cases']==24 and r['bounded_spin_iterations']==0,'native patterns/loop gate')
  else:require(r['repeated_requests']==32 and r['spin_iterations']==0,'native mailbox repeat gate')
  artifacts[binary]=r['binary_sha256']
 sizes=gates['kernel-sizes.json'];require(sizes['negative_1025_rejected'] is True and sizes['max_after']<=1024,'kernel argument guard')
 command=['nice','-n','19','ionice','-c','3','nm','-S','-C',str(B/'device/jit-smoke')]
 output=subprocess.check_output(command,text=True);observed=[]
 for line in output.splitlines():
  if 'packet26::capture_size<' in line:
   fields=line.split(None,3);observed.append(dict(kernel=fields[3],bytes=int(fields[1],16)))
 require(observed==sizes['rows'] and len(observed)==sizes['kernel_classes'] and max(r['bytes'] for r in observed)==sizes['max_after'],'kernel size receipt not current linked image')
 require('device kernel capture exceeds 1024 bytes' in (P/'oversized-capture.log').read_text(),'negative argument guard compile evidence missing')
 wrappers=gates['context-window-gates.json'];require(wrappers['tests']>=10 and wrappers['window_cases']==22,'context window matrix incomplete')
 require(gates['window-mocked-inherited-tests.json']['tests']>=36,'inherited wrapper coverage')
 require(gates['memory-plan-gates.json']['checks']>=27 and gates['memory-plan-gates.json']['memory_plan_sha256']==sha(P/'memory-plan.json'),'memory admission boundary coverage/identity')
 scripts={r['script'] for r in gates['inherited-python-gates.json']['rows'] if r['returncode']==0}
 require({'math_gate.py','queue_gate.py','test_state_machine.py','test_mtp_controller.py','test_submission_overlay.py','test_cleanup_paths.py','test_state_retention.py','test_suite_warmup.py'}<=scripts,'inherited Python gate coverage')


def main():
 gates=gates_load();artifacts,build_receipts=build_provenance();precision,links=precision_audit()
 counts=cpu_capacity(gates,artifacts);asan_boundary_counts=rollback_asan(gates,artifacts);draft_authentication(gates,artifacts);disposed_fixtures=selection(gates,artifacts)
 draft_fixtures,draft_inputs=draft(gates,artifacts);fixture_hashes,linked_hash=fixtures_gate(gates,artifacts)
 support(gates,artifacts)
 from memory_plan import plan
 memory=read('memory-plan.json');require(memory==plan(),'memory ledger differs from allocation formulas')
 require(all(r['allocation_margin_passed'] for c in memory['capacities'].values() for r in c['ranks']),'memory floor missing')
 inp=json.loads((B/'input/input.json').read_text())
 for name,digest in inp['files'].items():require(sha(B/'input'/name)==digest,'model input artifact changed')
 from build import sources
 from math_gate import check as mathcheck
 from queue_gate import check as queuecheck
 official_path=P.parent/'packet38-integrated/official-tensors.json'
 official=json.loads(official_path.read_text())
 source_hashes=sources();source_hashes[str(official_path.relative_to(ROOT))]=sha(official_path)
 baseline=read('draft-baseline-oracle.json')
 for filename in ('draft-baseline-oracle.json',baseline['archive']['path']):source_hashes[str((P/filename).relative_to(ROOT))]=sha(P/filename)
 source_map(source_hashes,ROOT)
 receipt=dict(schema='own-runtime.iq3.packet44.build.v1',passed=True,device_executed=False,
  real_model_device_qualified=False,seal_status='complete',arithmetic='iq3-p17-detmath-v2',
  context_capacities=list(CONTEXTS),sources=source_hashes,artifacts_sha256=artifacts,
  precision=precision,link_commands=links,mode_build_receipts_sha256=build_receipts,disposable_fixture_binary_sha256=disposed_fixtures,
  input_sha256=sha(B/'input/input.json'),nongemv_fixture_host_sha256_by_context=fixture_hashes,
  nongemv_fixture_host_sha256=fixture_hashes['256'],p33_linked_fixture_host_sha256=linked_hash,
  draft_capture_fixture_sha256_by_context=draft_fixtures,draft_capture_input_sha256=draft_inputs,draft_baseline_oracle_sha256=sha(P/'draft-baseline-oracle.json'),
  official_manifest_sha256=sha(P/'mtp-manifest.tsv'),official_tensor_receipt_sha256=sha(official_path),official_tensor_receipt_path=str(official_path.relative_to(ROOT)),
  official_tensor_sha256={n:r['sha256'] for n,r in official['tensors'].items()},
  gate_receipts={n:sha(P/n) for n in GATES},native_build_receipt_sha256=sha(P/'native-build-receipt.json'),
  math_gate=mathcheck(),queue_gate=queuecheck(),memory_plan=memory,cpu_capacity_gate_counts=counts,asan_capacity_boundary_counts=asan_boundary_counts,
  legacy_fixture_support_entry='disabled; coordinator uses window.py; no invented legacy census',
  max_compile_jobs=2,numeric_threads_per_rank=2,max_cpu_bound_processes=4,anonymous_memory_limit_bytes=10_000_000_000,
  pending=['all coordinator device windows','device timing at each capacity','device residency and driver overhead','full 12-prompt device suite'])
 cpu=dict(passed=True,device_executed=False,gate_count=len(GATES),gates=receipt['gate_receipts'],capacity_counts=counts,asan_boundary_counts=asan_boundary_counts)
 (P/'cpu-tests.json').write_text(json.dumps(cpu,indent=2)+'\n');receipt['cpu_tests_sha256']=sha(P/'cpu-tests.json')
 (P/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 (P/'BINARY-HASHES.md').write_text('# Binary SHA256\n\nNo device ran. All hashes bind the completed CPU seal.\n\n| Binary | SHA256 |\n| --- | --- |\n'+''.join(f'| {n} | {h} |\n' for n,h in sorted(artifacts.items())))
 print('SEALED packet44:',len(GATES),'gate receipts;',len(artifacts),'binary hashes; no device qualification')


if __name__=='__main__':main()

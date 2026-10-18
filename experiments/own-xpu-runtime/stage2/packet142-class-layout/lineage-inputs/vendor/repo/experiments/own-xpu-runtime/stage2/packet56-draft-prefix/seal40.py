#!/usr/bin/env python3
"""Packet40 CPU execution ledger and fail-closed final seal; never runs a device."""
import argparse,ast,gzip,hashlib,json,os,shlex,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
MODES=('gnu-host','icpx-host','asan','device')
ENTRIES=('own-rt-iq3','nongemv-fixtures','k2-fixtures','p33-linked-fixtures','jit-smoke','authority-tests','owner-retirement-tests','chain-tests','queue-tests','lifetime-tests','prepared-invalidation-tests')
PHASE_OUTPUTS={
 'cheap':'''argument-block-tests.json prepared-invalidation.json prepared-host-benchmark.json p33-candidate-gates.json k2-selection-tests.json k2-admission-tests.json review-prepared-gates.json submission-overlay-gates.json argument-state-gates.json owner-gates.json p33-linked-fixture-gates.json fixture-gates.json validation-gates.json entry-codes.json window-tests.json identity-tree-tests.json kernel-sizes.json expert-down-review-gates.json state-machine-tests.json mtp-controller-tests.json review-native-faults.json canary-host-gates.json review-controller-tests.json'''.split(),
 'mini':[n for mode in ('gnu-host','icpx-host','asan') for n in (f'mini-{mode}.json',f'mtp-gates-{mode}.json')]+['resident-host-gates.json'],
 'real-gnu':['real-campaign-gnu-host.json']+[f'real-{m}.json' for m in ('none','ngram','hit','miss','mtp')],
 'real-intel':['real-campaign-icpx-host.json']+[f'real-icpx-host-{m}.json' for m in ('none','ngram','hit','miss','mtp')],
 'real-native':['real-controller-gates.json','rollback-inventory.json']+[f'real-native-{m}.json' for m in ('none','ngram','hit','miss','mtp')],
 'captures':['draft-auth-gates.json']+[f'{prefix}-{prompt}.json' for prompt in ('incident-retrospective','code-review','customer-email','benchmark-analysis') for prefix in ('capture-run','capture-repeat','agreement')],
 'draft-final':['pipeline-draft-agreement.json'],
 'suite':['suite-cpu-qualification-plan.json','suite-real-cpu.json'],
}
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for data in iter(lambda:f.read(4*1024*1024),b''):h.update(data)
 return h.hexdigest()
def canonical(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def save(path,value):
 from storage import admit
 admit(8_000_000);Path(path).parent.mkdir(parents=True,exist_ok=True)
 tmp=Path(str(path)+'.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)
def artifacts(packet=P):
 result={str(f.relative_to(packet/'build')):sha(f) for mode in MODES for f in (packet/'build'/mode).glob('*') if f.is_file() and f.name in ENTRIES}
 # Standalone CPU fixture/controller gates compile their own explicitly local
 # ELF programs. Hashing an executable never loads its runtime or devices.
 for f in (packet/'build').glob('*'):
  if not f.is_file():continue
  with f.open('rb') as stream:magic=stream.read(4)
  if magic==b'\x7fELF':result[f.name]=sha(f)
 # This retained helper lives in its own compile scratch directory. It is
 # receipt-bound evidence, so do not mistake its nested location for staleness.
 helper=packet/'build/host-issue/host-issue-benchmark'
 if helper.is_file():
  with helper.open('rb') as stream:magic=stream.read(4)
  if magic==b'\x7fELF':result['host-issue/host-issue-benchmark']=sha(helper)
 return result
def python_dependencies(roots,packet=P):
 """Local imports and literal script dependencies; excludes unrelated new tools/docs."""
 pending=list(roots);seen=set()
 while pending:
  path=Path(pending.pop()).resolve()
  if path in seen or not path.is_file() or path.suffix!='.py' or packet.resolve() not in path.parents:continue
  seen.add(path)
  try:tree=ast.parse(path.read_text())
  except SyntaxError:continue
  for node in ast.walk(tree):
   modules=[]
   if isinstance(node,ast.Import):modules=[v.name.split('.')[0] for v in node.names]
   elif isinstance(node,ast.ImportFrom) and node.module:modules=[node.module.split('.')[0]]
   for name in modules:
    candidate=packet/(name+'.py')
    if candidate.exists():pending.append(candidate)
   if isinstance(node,ast.Constant) and isinstance(node.value,str) and node.value.endswith('.py'):
    candidate=packet/node.value
    if candidate.is_file():pending.append(candidate)
 return {str(path.relative_to(packet)):sha(path) for path in sorted(seen)}
def execution_sources(command,packet=P):
 roots=[Path(v) for v in command if str(v).endswith('.py') and Path(v).is_file()]
 result=python_dependencies(roots,packet)
 # Native code/dispatch is bound separately from evolving Python wrappers.
 for path in packet.rglob('*'):
  if 'build' in path.relative_to(packet).parts or not path.is_file():continue
  if path.suffix in ('.cpp','.hpp') or path.name in ('CMakeLists.txt','dispatch-p38.json','dispatch-p33.json','dispatch-all-new.json','dispatch-default.json','kernel-registry.json','k2-class-registry.json'):
   result[str(path.relative_to(packet))]=sha(path)
 return result
def success(row):return isinstance(row,dict) and (row.get('passed') is True or row.get('source_review_passed') is True)
def record_phase(phase,command,receipts=(),packet=P):
 if not command:raise ValueError('record phase needs command after --')
 if not phase or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in phase):raise ValueError('invalid execution phase name')
 if any(Path(name).is_absolute() or '..' in Path(name).parts for name in receipts):raise ValueError('receipt path outside packet')
 if any('/device/' in str(v) and str(v).split('/')[-1] in ENTRIES for v in command):raise ValueError('device executable forbidden in CPU recorder')
 if os.getpriority(os.PRIO_PROCESS,0)!=19:raise ValueError('recorder requires nice19 parent')
 if not 1<=int(os.environ.get('OMP_NUM_THREADS','0'))<=4:raise ValueError('OMP_NUM_THREADS must be1..4')
 before_sources=execution_sources(command,packet);before_binaries=artifacts(packet)
 before={f.name:(f.stat().st_mtime_ns,sha(f)) for f in packet.glob('*.json')}
 start=time.time_ns();record_name='qualification-'+phase+'-'+str(start)
 path=packet/'evidence'/(record_name+'.log.gz');path.parent.mkdir(exist_ok=True)
 from storage import admit
 admit(16_000_000);actual=['nice','-n','19','ionice','-c','3',*command]
 with gzip.open(path,'wb') as output:
  child=subprocess.Popen(actual,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  while True:
   chunk=child.stdout.read(65536)
   if not chunk:break
   output.write(chunk)
  rc=child.wait()
 after_sources=execution_sources(command,packet);after_binaries=artifacts(packet)
 expected=list(receipts or PHASE_OUTPUTS.get(phase,()))
 if not expected:
  expected=[f.name for f in packet.glob('*.json') if f.name not in before or (f.stat().st_mtime_ns,sha(f))!=before[f.name]]
 bound={};problems=[]
 if rc:problems.append('command returned '+str(rc))
 if after_sources!=before_sources:problems.append('execution sources changed during command')
 if {k:v for k,v in after_binaries.items() if '/' in k}!={k:v for k,v in before_binaries.items() if '/' in k}:problems.append('runtime binaries changed during command')
 for name in expected:
  file=packet/name
  if not file.is_file():problems.append('missing receipt '+name);continue
  try:row=read(file)
  except (ValueError,OSError) as ex:problems.append('invalid receipt '+name+': '+str(ex));continue
  if not success(row):problems.append('receipt not passed '+name)
  if name in before and file.stat().st_mtime_ns==before[name][0]:problems.append('receipt was not produced by command '+name)
  bound[name]=sha(file)
 if not bound:problems.append('command produced no gate receipts')
 receipt_text=''.join((packet/name).read_text() for name in bound)
 relevant_binaries={key:digest for key,digest in after_binaries.items() if '/' in key or digest in receipt_text}
 ledger=dict(schema='packet40.cpu-execution.v1',passed=not problems,device_executed=False,phase=phase,command=actual,start_unix_ns=start,end_unix_ns=time.time_ns(),returncode=rc,receipt_sha256=bound,source_sha256=before_sources,binary_sha256=relevant_binaries,log=str(path.relative_to(packet)),log_sha256=sha(path),problems=problems)
 save(packet/'evidence'/(record_name+'.json'),ledger)
 print(json.dumps({'phase':phase,'passed':not problems,'receipts':len(bound),'problems':problems}),flush=True)
 if problems:raise RuntimeError('qualification recording failed')
 return ledger
# Sealing never upgrades a copied historical boolean into current coverage.
COUNTERPARTS={
 'review-resume-controller.json':('review-p40-nonblocking-draft.json','review-cancellation-retention-p40.json'),
 'review-resume-reset.json':('review-retention-token-authority.json','review-cancellation-retention-p40.json'),
 'review-resume-authority.json':('review-retention-token-authority.json','review-p40-nonblocking-draft.json'),
 'review-draft-capture.json':('review-p40-nonblocking-draft.json','review-capture-seal40.json','full-wrapper-gates.json'),
}
ADDITIONAL=('cancellation-retention-mini-native.json','cancellation-retention-mini-python.json',
 'cancellation-retention-real-native.json','draft-async-gates-gnu.json','suite-metric-gates.json',
 'review-metrics-independent.json','review-retention-token-authority.json',
 'review-p40-nonblocking-draft.json','review-cancellation-retention-p40.json','review-capture-seal40.json','full-wrapper-gates.json','seal40-gates.json','retention-caps-gates.json','build-identity40.json',
 'python-regression-gates.json','python-standalone-gates.json','suite128-tail-cpu-gates.json')
NEW_BOUND=set(ADDITIONAL)-{'python-regression-gates.json','python-standalone-gates.json','suite128-tail-cpu-gates.json'}

def verify_sources(table,packet=P):
 issues=[]
 for source,digest in table.items():
  path=packet/source
  if not path.is_file():issues.append('source missing '+source)
  elif sha(path)!=digest:issues.append('source changed '+source)
 return issues

def receipt_bindings(row,binaries,packet=P):
 issues=[];bound_sources=0;bound_binaries=0
 def walk(value,where=''):
  nonlocal bound_sources,bound_binaries
  if isinstance(value,list):
   for i,child in enumerate(value):walk(child,where+'/'+str(i))
  elif isinstance(value,dict):
   if isinstance(value.get('path'),str) and value['path'].startswith('evidence/') and isinstance(value.get('sha256'),str):
    archive=packet/value['path']
    if not archive.is_file() or sha(archive)!=value['sha256']:issues.append(where+': archived evidence changed '+value['path'])
   for field in ('source_sha256','sources_sha256'):
    if isinstance(value.get(field),dict):
     issues.extend(where+': '+item for item in verify_sources(value[field],packet));bound_sources+=len(value[field])
   for field in ('gate_receipts_sha256','prerequisite_receipts_sha256'):
    if isinstance(value.get(field),dict):issues.extend(where+': '+item for item in verify_sources(value[field],packet))
   for key,child in value.items():
    if key in ('binary_sha256','host_binary_sha256','host_reference_binary_sha256','fixture_binary_sha256','linked_binary_sha256') and isinstance(child,str):
     bound_binaries+=1
     if child not in binaries.values():issues.append(where+': stale binary '+key+'='+child)
    elif key not in ('source_sha256','sources_sha256','gate_receipts_sha256','prerequisite_receipts_sha256','previous'):walk(child,where+'/'+key)
 walk(row)
 return issues,bound_sources,bound_binaries

def wrapper_bindings(row,packet=P):
 required={'full_wrapper_gate.py','window.py','draft_window.py','capture40.py','pipeline.py','suite.py','suite_metrics.py','fixture_support.py'}
 problems=[]
 if not required<=set(row.get('source_sha256',{})):problems.append('wrapper consumer/producer source binding incomplete')
 try:
  archive=packet/row['archive_path']
  if not archive.resolve().is_relative_to(packet.resolve()):raise ValueError('wrapper archive outside packet')
  if sha(archive)!=row['archive_sha256']:raise ValueError('wrapper archive changed')
  with gzip.open(archive,'rt') as source:windows=json.load(source)
  if len(windows)!=row['windows']+row['failure_windows']:raise ValueError('wrapper archive window count differs')
  for result in row['rows']:
   success=windows[result['label']+'/window.json'];failure=windows[result['label']+'-failure/window.json']
   if success.get('passed') is not True or failure.get('passed') is not False:raise ValueError('wrapper archived outcome differs '+result['label'])
   if result['window']=='K2' and success.get('device_timing_qualified') is not False:raise ValueError('CPU K2 timing promoted')
   if success.get('device_executed') is True or failure.get('device_executed') is True:raise ValueError('wrapper archive claims device execution')
 except (OSError,KeyError,TypeError,ValueError) as error:problems.append('wrapper archive binding: '+str(error))
 return problems

def suite128_bindings(row,packet=P):
 try:
  manifest_path=packet.parent/'suite-inputs-20261012-cap128/suite-manifest.json'
  if sha(manifest_path)!=row['parent_manifest_sha256']:raise ValueError('128-token parent manifest changed')
  manifest=read(manifest_path);entries=[e for e in manifest['prompts'] if e['prompt_id']==row['prompt_id']]
  if len(entries)!=1:raise ValueError('128-token prompt missing/duplicate')
  oracle=packet.parents[3]/entries[0]['oracle_directory']
  for path,digest in ((oracle/'receipt.json',row['oracle_receipt_sha256']),(oracle/'result.json',row['oracle_result_sha256']),(oracle.parent/'suite_check.py',row['checker_sha256'])):
   if sha(path)!=digest:raise ValueError('128-token oracle/checker changed')
  if read(oracle/'result.json')['tokens']!=row['token_ids']:raise ValueError('128-token output differs from oracle')
  if row['dispatch_sha256']!=sha(packet/'dispatch-p38.json'):raise ValueError('128-token dispatch changed')
  if any(sha(oracle/name)!=digest for name,digest in row['fixture_sha256'].items()):raise ValueError('128-token early/tail fixture differs from oracle')
  return []
 except (OSError,KeyError,TypeError,ValueError) as error:return ['128-token oracle binding: '+str(error)]

STATE_EXCEPTION='Terminal EOS abandons speculative work: emitted tokens, committed state and reset state are exact; unused inactive banks, scratch allocations and uncommitted tail bytes may differ with cancellation timing.'
def state_scope_bindings(binaries,packet=P):
 """A pending user decision can never silently narrow the any-state requirement."""
 scope=dict(full_raw_target_allocation_equality='forced-miss rollback followed by redo, and retention on/off without terminal EOS; logical event-counter metadata excluded',terminal_eos='committed state, emitted tokens and reset state only; unused allocation bytes are not currently proved equal',authorization='pending',strict_terminal_raw_equality=False)
 decision_path=packet/'state-scope-decision.json'
 try:decision=read(decision_path)
 except (OSError,ValueError):decision={}
 if decision.get('owner_accepted') is True:
  message=decision.get('owner_message_text','')
  if (decision.get('status')=='owner-accepted' and decision.get('authorization_source')=='explicit-user-message' and decision.get('accepted_exception')==STATE_EXCEPTION and isinstance(message,str) and bool(message.strip()) and decision.get('owner_message_sha256')==hashlib.sha256(message.encode()).hexdigest()):
   scope.update(authorization='explicit-owner-exception',accepted_terminal_exception=STATE_EXCEPTION,decision_sha256=sha(decision_path))
   return [],scope
  return ['state scope: owner acceptance record is incomplete or does not bind the exact exception'],scope
 proof_name='terminal-eos-all-state-gates.json';proof_path=packet/proof_name
 if proof_path.is_file():
  try:
   proof=read(proof_path);recorded,_=load_ledger(packet,binaries)
   errors,ns,nb=receipt_bindings(proof,binaries,packet)
   if not success(proof) or proof.get('device_executed') is not False or proof_name not in recorded or errors or not ns or not nb:raise ValueError('strict terminal proof lacks current execution/source/binary binding')
   if any(proof.get(name) is not True for name in ('terminal_eos','raw_allocation_bytes_equal','all_inventoried_allocations','every_mini_launch_boundary','real_model_sampled_boundaries')):raise ValueError('strict terminal proof lacks exhaustive mini and sampled real all-allocation equality')
   if set(proof.get('controllers',[]))!={'native','python'}:raise ValueError('strict terminal proof must cover both controllers')
   scope.update(authorization='strict-terminal-proof',terminal_eos='Every inventoried target allocation matches the never-speculated baseline at terminal EOS.',strict_terminal_raw_equality=True,strict_terminal_proof_sha256=sha(proof_path),execution_ledger=recorded[proof_name])
   return [],scope
  except (OSError,KeyError,TypeError,ValueError) as error:return ['state scope: '+str(error)],scope
 return ['state scope unresolved: explicit owner acceptance of the terminal-EOS unused-byte exception or fresh strict terminal all-allocation proof is required'],scope

def load_ledger(packet,binaries):
 qualified={};invalid=[]
 for path in sorted((packet/'evidence').glob('qualification-*.json')):
  try:
   row=read(path)
   if row.get('schema')!='packet40.cpu-execution.v1':continue
   problems=[]
   if row.get('passed') is not True or row.get('returncode')!=0:problems.append('execution failed')
   problems.extend(verify_sources(row.get('source_sha256',{}),packet))
   if not row.get('source_sha256'):problems.append('execution source map missing')
   for binary,digest in row.get('binary_sha256',{}).items():
    if binaries.get(binary)!=digest:problems.append('binary changed '+binary)
   log=packet/row.get('log','')
   if not log.is_file() or sha(log)!=row.get('log_sha256'):problems.append('execution log changed/missing')
   for name,digest in row.get('receipt_sha256',{}).items():
    receipt=packet/name
    if not receipt.is_file() or sha(receipt)!=digest:problems.append('receipt changed '+name)
   if problems:invalid.append(dict(path=str(path.relative_to(packet)),problems=problems));continue
   for name,digest in row['receipt_sha256'].items():qualified[name]={'ledger':str(path.relative_to(packet)),'ledger_sha256':sha(path),'receipt_sha256':digest}
  except (OSError,ValueError,TypeError) as ex:invalid.append(dict(path=str(path.relative_to(packet)),problems=[str(ex)]))
 return qualified,invalid

def coverage(checklist,binaries,packet=P,bootstrap=False):
 recorded,invalid=load_ledger(packet,binaries);rows=[];problems=[];receipts={};cache={}
 def qualify(name,inherited=False):
  if name in cache:return cache[name]
  path=packet/name;failure=[]
  if not path.is_file():failure.append('missing receipt')
  else:
   try:
    row=read(path)
    if not success(row):failure.append('receipt not passed')
    if row.get('in_progress'):failure.append('receipt incomplete')
    if row.get('device_executed') is True or row.get('device_ran') is True:failure.append('device execution outside CPU qualification')
    mismatch,ns,nb=receipt_bindings(row,binaries,packet);failure.extend(mismatch)
    if name=='full-wrapper-gates.json':failure.extend(wrapper_bindings(row,packet))
    if name=='suite128-tail-cpu-gates.json':failure.extend(suite128_bindings(row,packet))
    if name in recorded:proof=recorded[name]
    elif name in NEW_BOUND and (ns or nb):proof={'direct_current_source_bindings':ns,'direct_current_binary_bindings':nb}
    else:failure.append('missing current packet40 execution ledger');proof={}
    if not failure:receipts[name]=sha(path)
   except (OSError,ValueError,TypeError) as ex:failure.append('invalid receipt '+str(ex));proof={}
  if failure:proof={}
  cache[name]=(failure,proof);return cache[name]
 for inherited in checklist['inherited_gates']:
  name=inherited['inherited_receipt']
  if bootstrap and name=='window-seal-admission-gates.json':
   rows.append(dict(inherited=name,status='final-admission-pending',current=[]));continue
  targets=COUNTERPARTS.get(name,(name,));fail=[];proofs={}
  for target in targets:
   errors,proof=qualify(target,True);fail.extend(target+': '+e for e in errors);proofs[target]=proof
  rows.append(dict(inherited=name,current=list(targets),passed=not fail,proofs=proofs,problems=fail))
  problems.extend(name+': '+error for error in fail)
 for name in ADDITIONAL:
  errors,proof=qualify(name);problems.extend(name+': '+e for e in errors)
 return dict(passed=not problems,inherited_count=len(rows),inherited_covered=sum(r.get('passed',False) for r in rows),rows=rows,problems=problems,invalid_execution_ledgers=invalid,gate_receipts=receipts)

def compile_identity(packet,binaries):
 problems=[];precision={};links={}
 for mode in MODES:
  for entry in ('own-rt-iq3','nongemv-fixtures','k2-fixtures','p33-linked-fixtures'):
   if mode+'/'+entry not in binaries:problems.append('missing '+mode+'/'+entry)
  flags=['-fno-fast-math','-ffp-contract=off']+(['-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt'] if mode=='device' else [])
  path=packet/'build'/mode/'compile_commands.json'
  try:
   rows=read(path);local_links={str(f.relative_to(packet/'build')):f.read_text() for f in (packet/'build'/mode).rglob('link.txt')}
   if not rows or not local_links:problems.append(mode+': empty compile/link identity')
   if any(not all(flag in shlex.split(row.get('command','')) for flag in flags) for row in rows):problems.append(mode+': precision flag missing on compile')
   if any(not all(flag in shlex.split(command) for flag in flags) for command in local_links.values()):problems.append(mode+': precision flag missing on link')
   precision[mode]=dict(flags=flags,compile_count=len(rows),link_count=len(local_links),compile_commands_sha256=sha(path));links.update(local_links)
  except (OSError,ValueError) as ex:problems.append(mode+': '+str(ex))
 if 'device/jit-smoke' not in binaries:problems.append('missing device/jit-smoke')
 # Rebuilt standalone sanitizer programs have their own one-invocation contract.
 native=packet/'native-build-receipt.json'
 try:
  for row in read(native)['binaries']:
   path=packet/row['binary'];digest=sha(path)
   if digest!=row['sha256']:problems.append('standalone binary changed '+row['binary'])
   if not row.get('compile_and_link_same_invocation') or any(flag not in row['command'] for flag in ('-fno-fast-math','-ffp-contract=off')):problems.append('standalone precision missing '+row['binary'])
   problems.extend(verify_sources(row['source_sha256'],packet));binaries[str(path.relative_to(packet/'build'))]=digest
 except (OSError,KeyError,ValueError) as ex:problems.append('native build identity: '+str(ex))
 return problems,precision,links

def build_identity_bindings(binaries,packet=P):
 try:
  row=read(packet/'build-identity40.json')
  if row.get('passed') is not True or row.get('device_executed') is not False:raise ValueError('current build verification failed')
  if row['binary_sha256']!=binaries:raise ValueError('build verification artifact identity changed')
  if row['sources_unchanged_during_build'] is not True or not row['source_sha256']:raise ValueError('build source closure unbound')
  errors=verify_sources(row['source_sha256'],packet)
  if errors:raise ValueError('; '.join(errors))
  expected=[(phase,mode) for phase in ('refresh','noop') for mode in MODES]
  if [(r.get('pass_name'),r['mode']) for r in row['rows']]!=expected or row['compile_jobs']!=1:raise ValueError('four sequential refresh and no-op build modes required')
  if any(result.get('build_actions')!=[] for result in row['rows'] if result['pass_name']=='noop'):raise ValueError('no-op build submitted compile/link actions')
  from build_identity40 import verify_mirror_receipt
  verify_mirror_receipt(row,packet,packet/'build')
  for result in row['rows']:
   if result['returncode']!=0 or sha(packet/result['log'])!=result['log_sha256']:raise ValueError('build verification log changed or failed')
  return []
 except (OSError,KeyError,TypeError,ValueError) as error:return ['current build verification: '+str(error)]

def capture_identity(host_sha,packet=P):
 problems=[];inputs={};fixtures={}
 for prompt in ('incident-retrospective','code-review','customer-email','benchmark-analysis'):
  try:
   run=read(packet/f'capture-run-{prompt}.json');repeat=read(packet/f'capture-repeat-{prompt}.json');input_path=packet/f'capture-input-{prompt}.json'
   if run.get('passed') is not True or run.get('binary_sha256')!=host_sha:raise ValueError('stale/failed capture binary')
   root=Path(run['output']).resolve()
   if (packet/'build').resolve() not in root.parents:raise ValueError('capture outside packet40 build')
   from capture40 import archived_capture
   archived,_=archived_capture(run)
   expected=repeat['sha256'];actual=run['fixture_sha256']
   if root.exists():raise ValueError('capture scratch was not deleted')
   if any(name not in archived or archived[name]['sha256']!=digest for name,digest in actual.items()):raise ValueError('capture archive fixture binding differs')
   if not actual or actual!=expected:raise ValueError('capture output does not match fresh repeat')
   if repeat.get('binary_sha256',host_sha)!=host_sha:raise ValueError('capture repeat binary changed')
   reference_path=packet/f'capture40-{prompt}-icpx-host.json';reference=read(reference_path)
   if sha(reference_path)!=repeat['reference_receipt_sha256']:raise ValueError('capture host reference receipt changed')
   if reference['binary_sha256']!=sha(packet/'build/icpx-host/own-rt-iq3'):raise ValueError('capture host reference binary changed')
   if reference['dispatch_sha256']!=run['dispatch_sha256'] or run['dispatch_sha256']!=sha(packet/'dispatch-p38.json'):raise ValueError('capture dispatch changed')
   reference_files,_=archived_capture(reference)
   if reference['fixture_sha256']!=actual or any(reference_files[n]['sha256']!=h for n,h in actual.items()):raise ValueError('capture host reference archived bytes differ')
   captured=read(input_path);table=packet/'build'/f'capture-{prompt}.tsv'
   if sha(table)!=captured['table_sha256'] or sha(table)!=run['table_sha256']:raise ValueError('capture input table changed')
   for name,digest in captured['streams'].items():
    if sha(packet/'build'/('captured-'+prompt)/name)!=digest:raise ValueError('capture target stream changed '+name)
   inputs[prompt]=sha(input_path);fixtures[prompt]=actual
  except (AssertionError,OSError,KeyError,ValueError) as ex:problems.append('capture '+prompt+': '+str(ex))
 return problems,inputs,fixtures

def semantic_checks(gates,packet=P):
 problems=[]
 def check(name,fn,why):
  if name not in gates:return
  try:
   if not fn(read(packet/name)):problems.append(name+': '+why)
  except (OSError,KeyError,TypeError,ValueError):problems.append(name+': incomplete '+why)
 check('draft-async-gates-gnu.json',lambda r:r['cases']>=28 and all(x['target_state_files']>=210 and x['tokens']==8 for x in r['rows']),'all28 fault/retention/controller cases required')
 check('python-regression-gates.json',lambda r:r['tests']>=151 and not r['failures'] and not r['errors'] and not r['skipped'] and r['sources_unchanged'] and {'python_tests.py','suite_metrics.py','window.py','draft_window.py','seal40.py'}<=set(r['sources_sha256']),'full current Python test dependency closure and at least151 tests required')
 check('python-standalone-gates.json',lambda r:r['tests']==r['expected_tests']==12 and len(r['rows'])==12 and all(x['passed'] and x['returncode']==0 and sha(packet/x['receipt'])==x['receipt_sha256'] and sha(packet/x['log'])==x['log_sha256'] for x in r['rows']),'all12 standalone producers must bind fresh output receipts and logs')
 check('suite128-tail-cpu-gates.json',lambda r:r['real_model_execution'] and r['partial_suite'] and r['prompts_executed']==1 and r['total_prompts']==12 and r['tokens']==len(r['token_ids'])==128 and r['fixture_files']==len(r['fixture_sha256'])==768 and r['retain_steps']=='1-8,97-104' and r['controller']=='native' and r['draft']=='mtp' and r['host_compiler']=='icpx-host' and r['realistic_final_gate']['passed'] is False,'actual128-token partial-suite host proof with768 early/tail fixtures required')
 check('retention-caps-gates.json',lambda r:r['cases']==8 and r['requests']==12 and {(x['controller'],x['max_new'],x['retain_steps']) for x in r['rows']}=={(mode,cap,retain) for mode in ('native','python') for cap in (64,128) for retain in ('1-8','1-8,97-104')} and all(x['tokens_equal'] and x['full_state_equal'] for x in r['rows']),'both controllers,64/128 caps and both fixture ranges must equal retention none')
 for name in ('cancellation-retention-mini-native.json','cancellation-retention-mini-python.json'):
  check(name,lambda r:r['every_launch_boundary'] and r['retention_independence'] and r['gate_count']>=r['actual_compute_launches']+2,'every actual mini compute boundary and retention independence required')
 check('cancellation-retention-real-native.json',lambda r:r['real_model'] and r['retention_independence'] and len(r['rows'])>=1,'real-model sampled cancellation required')
 check('full-wrapper-gates.json',lambda r:not r.get('in_progress') and r['windows']>=22 and r['failure_windows']>=22,'every success/failure wrapper required')
 check('native-mini-cpu.json',lambda r:r['cases']>=1109 and r['exhaustive_ternary_patterns']>=1093,'full native mini gate; quick subset insufficient')
 for suffix in ('cpu','asan','tsan'):
  check('native-controller-'+suffix+'.json',lambda r:r['cases']>=1123 and r['ternary_patterns']>=1093 and r['long_random_cases']>=24,'full native controller coverage required')
 for compiler,prefix in (('gnu-host',''),('icpx-host','icpx-host-')):
  for mode in ('none','ngram','hit','miss','mtp'):
   check('real-'+prefix+mode+'.json',lambda r:r['token_matches']==8 and r['layer_matches']==r['layer_total']==384,'real token/fixture identity required')
 return problems

def seal(bootstrap=False,audit_only=False,packet=P):
 from build import sources
 checklist=read(packet/'qualification-checklist.json');binaries=artifacts(packet)
 build_problems,precision,links=compile_identity(packet,binaries)
 coverage_row=coverage(checklist,binaries,packet,bootstrap=bootstrap)
 capture_problems,inputs,fixtures=capture_identity(binaries.get('gnu-host/own-rt-iq3'),packet)
 state_problems,state_scope=state_scope_bindings(binaries,packet)
 problems=build_problems+build_identity_bindings(binaries,packet)+coverage_row['problems']+capture_problems+state_problems+semantic_checks(coverage_row['gate_receipts'],packet)
 math_result={};queue_result={};suite_archives={};suite_warmup_hash=None
 try:
  from math_gate import check as math_check
  from queue_gate import check as queue_check
  math_result=math_check();queue_result=queue_check()
 except (AssertionError,OSError,ValueError) as error:problems.append('math/queue source gate: '+str(error))
 if 'suite-real-cpu.json' in coverage_row['gate_receipts']:
  try:
   from seal import bind_cpu_suite
   suite_archives,suite_warmup_hash=bind_cpu_suite(read(packet/'suite-real-cpu.json'),binaries.get('icpx-host/own-rt-iq3'),packet/'build/icpx-host/own-rt-iq3')
  except (AssertionError,OSError,KeyError,ValueError) as error:problems.append('suite archive/oracle binding: '+str(error))
 if len(checklist['inherited_gates'])!=91:problems.append('inherited inventory must cover91 gates')
 report=dict(schema='packet40.seal-audit.v1',passed=not problems,device_executed=False,bootstrap=bootstrap,problems=problems,coverage=coverage_row,artifacts_sha256=binaries,state_comparison_scope=state_scope)
 save(packet/'seal40-audit.json',report)
 if audit_only:
  print(json.dumps({'passed':not problems,'covered':coverage_row['inherited_covered'],'required':91,'problems':problems}),flush=True);return report
 if problems:raise RuntimeError('seal refused: '+str(len(problems))+' unresolved requirements; see seal40-audit.json')
 official=read(packet/'official-tensors.json');gates=coverage_row['gate_receipts'];source_map=sources()
 receipt=dict(schema='own-runtime.iq3.packet40.build.v1',passed=True,device_executed=False,real_model_device_qualified=False,seal_status='admission-candidate' if bootstrap else 'complete',arithmetic='iq3-p17-detmath-v2',sources=source_map,artifacts_sha256=binaries,precision=precision,link_commands=links,input_sha256=sha(packet/'build/input/input.json'),nongemv_fixture_host_sha256=read(packet/'fixture-gates.json')['output_sha256'],p33_linked_fixture_host_sha256=read(packet/'p33-linked-fixture-gates.json')['output_sha256'],draft_capture_fixture_sha256=fixtures,draft_capture_input_sha256=inputs,official_manifest_sha256=sha(packet/'mtp-manifest.tsv'),official_tensor_receipt_sha256=sha(packet/'official-tensors.json'),official_tensor_sha256={n:r['sha256'] for n,r in official['tensors'].items()},gate_receipts=gates,native_build_receipt_sha256=sha(packet/'native-build-receipt.json'),memory_plan=read(packet/'memory-plan.json'),qualification_checklist_sha256=sha(packet/'qualification-checklist.json'),inherited_coverage=coverage_row['rows'],max_compile_jobs=2,numeric_threads_per_rank=2,max_cpu_bound_processes=4,anonymous_memory_limit_bytes=10_000_000_000,pending=['all coordinator device windows','actual queue overlap and latency','measured same-boot exactness/speed companion chain','64/128 full suite performance;128 cap is not a512 response-cap promotion gate'])
 receipt.update(math_gate=math_result,queue_gate=queue_result,suite_execution_archive_sha256=suite_archives,suite_warmup_receipt_sha256=suite_warmup_hash,real_cpu_suite_compiler='icpx-host',real_cpu_suite_binary_sha256=binaries['icpx-host/own-rt-iq3'])
 receipt['state_comparison_scope']=state_scope
 # Candidate cpu-tests uses only prerequisite gates: admission is excluded from
 # its digest, avoiding a candidate/admission/final circular dependency.
 cpu_tests=dict(passed=True,device_executed=False,gate_count=len(gates),gates={k:v for k,v in gates.items() if k!='window-seal-admission-gates.json'},inherited_covered=coverage_row['inherited_covered'],inherited_required=91)
 cpu_tests['gate_count']=len(cpu_tests['gates']);cpu_path=packet/'cpu-tests-candidate.json';save(cpu_path,cpu_tests);receipt['cpu_tests_sha256']=sha(cpu_path)
 if not bootstrap:
  from test_window_seal_admission import contract
  admission=read(packet/'window-seal-admission-gates.json');mismatch=verify_sources(admission.get('source_sha256',{}),packet)
  consumed=contract(receipt)
  if mismatch or admission.get('seal_fields')!=list(consumed) or admission.get('consumed_seal_sha256')!=hashlib.sha256(json.dumps(consumed,sort_keys=True).encode()).hexdigest():raise RuntimeError('final admission bound a different seal/source contract')
  save(packet/'cpu-tests.json',cpu_tests);receipt['cpu_tests_sha256']=sha(packet/'cpu-tests.json');save(packet/'build-receipt.json',receipt)
  (packet/'BINARY-HASHES.md').write_text('# Binary SHA256\n\nNo device binary ran.\n\n| Binary | SHA256 |\n| --- | --- |\n'+''.join('| '+n+' | '+h+' |\n' for n,h in sorted(binaries.items())))
 else:save(packet/'build-admission-candidate.json',receipt)
 print(('ADMISSION CANDIDATE' if bootstrap else 'SEALED')+' '+str(len(gates))+' current gate receipts',flush=True);return receipt

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--record-phase');ap.add_argument('--receipt',action='append',default=[]);ap.add_argument('--audit',action='store_true');ap.add_argument('--bootstrap',action='store_true');ap.add_argument('command',nargs=argparse.REMAINDER);a=ap.parse_args()
 if a.record_phase:return record_phase(a.record_phase,a.command[1:] if a.command[:1]==['--'] else a.command,a.receipt)
 return seal(a.bootstrap,a.audit)
if __name__=='__main__':main()

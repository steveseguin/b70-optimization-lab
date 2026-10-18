"""Packet137 scratch copy of the frozen124c CPU queue probe.

The queue output and storage accounting roots are both disposable scratch.
Actual packet137 build usage is checked separately before the real queue loop;
no older packet build allowance is changed or claimed to pass.

CPU-only execution of the real queue loop, with synthetic window receipts.

Only scheduling context, journal, elapsed gaps and native window execution are
synthetic. The real bundle, seal, storage, inputs, prefix and oracle validators
execute; all queue writes are confined to disposable scratch.
"""
import contextlib,copy,io,json,os,subprocess,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from source_decision import P,O,ROOT,sha,save

ORACLE_ERROR='packet49c must use the unchanged packet49 oracle authority'

def symlinks():
 audit=json.loads((O/'inputs/symlink-audit.json').read_text())
 for name,target in audit['restored'].items():
  f=P/name
  assert f.is_symlink() and os.readlink(f)==target,'restored symlink lost: '+name
  assert f.exists(),'restored symlink target missing: '+name
 for name,digest in audit['binaries'].items():assert sha(P/name)==digest,'native binary changed: '+name
 assert (P/'oracle').resolve()==(P.parent/'packet49-integrate/oracle').resolve()
 return audit['restored']

def oracle_probe(old=False):
 # Deliberately do NOT install the orchestration adapter: exercise the exact
 # fresh subprocess that queue_runner.oracle_ready starts on the real tree.
 import queue_runner as q
 bundle=P.with_name('packet124b-record-bundle') if old else P
 calls=[];run=subprocess.run
 def observe(cmd,**kwargs):
  assert cmd==['nice','-n','19','taskset','-c','8-15,24-31','python3','-B',str(bundle/'shared_oracle.py'),'--require-complete']
  cp=run(cmd,stdin=subprocess.DEVNULL,timeout=120,**kwargs)
  calls.append(dict(argv=cmd,returncode=cp.returncode,stdout=cp.stdout,stderr=cp.stderr))
  return cp
 with patch.object(q,'P',bundle),patch.object(subprocess,'run',side_effect=observe):
  try:ready=q.oracle_ready()
  except RuntimeError as error:
   assert old and ORACLE_ERROR in calls[-1]['stderr'],str(error)
   return dict(passed=True,expected_refusal=True,ready=False,error=str(error),calls=calls)
 assert not old and ready,'queue oracle readiness failed'
 return dict(passed=True,ready=True,calls=calls)

def receipt(q,out,name):
 from bundle_selection import selected
 from window_adapter import receipt_digest,window_scope
 choice=selected();dest=out/name;dest.mkdir()
 row=dict(window=name,passed=True,device_executed=True,qualifying=True,card=0,context=4096,
          draft_rank=choice['draft_rank'],target_split=choice['target_split'],boot_id='CPU-SYNTHETIC',
          launched_pids=[900001,900002],synthetic_queue_gate=True)
 side=out/(name+'-lane-admission.json');scope=window_scope(name)
 save(side,dict(schema='own-runtime.chain-admission.v1',passed=True,window=name,scope=scope,
                window_receipt_sha256_without_admission=receipt_digest(row),coordination={'boot_id':row['boot_id']},
                owners={str(pid):dict(seen=True,exited=True) for pid in row['launched_pids']},ready_checks=1))
 row['lane_admission']=dict(passed=True,path=str(side),sha256=sha(side),scope=scope)
 save(dest/'window.json',row)
 if name=='K2':
  (dest/'run0').mkdir();(dest/'run0/dispatch-measured.json').write_bytes((P/'dispatch-speed6.json').read_bytes())
 q.validate_success(name,out,0)
 # Strict field type and every admission binding are tested, not bypassed.
 refused=[];original_side=side.read_bytes()
 for key,value in [('qualifying',False),('device_executed',False),('context','4096'),('lane_admission',{})]:
  bad=copy.deepcopy(row);bad[key]=value
  if key!='lane_admission':
   proof=json.loads(original_side);proof['window_receipt_sha256_without_admission']=receipt_digest(bad)
   save(side,proof);bad['lane_admission']['sha256']=sha(side)
  save(dest/'window.json',bad)
  try:q.validate_success(name,out,0)
  except (ValueError,RuntimeError,KeyError):refused.append(key)
  else:raise AssertionError('malformed queue receipt accepted: '+key)
 side.write_bytes(original_side);save(dest/'window.json',row)
 try:q.validate_success(name,out,1)
 except RuntimeError:refused.append('nonzero-exit')
 else:raise AssertionError('failed child accepted')
 return refused

def probe():
 from chain_adapter import install
 install()
 import chain103,storage,check_inputs,resume_chain
 q,w=chain103.install()
 links=symlinks();disk=storage.precheck();assert disk['passed'],disk
 import shutil
 LOCAL=Path(__file__).resolve().parents[1]
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage(LOCAL).free>=25_000_000_000
 packet137_build_bytes=sum(f.stat().st_size for f in LOCAL.rglob('*') if f.is_file() and 'build' in f.parts and not f.is_symlink())
 assert packet137_build_bytes<=300_000_000
 prefixes=[P.parent/'packet56-draft-prefix/evidence'/n/'window.json' for n in ('head-k-a','head-k-b')]
 prefix=q.prefix_prerequisites(prefixes)
 assert prefix['passed']
 for paths in (None,[prefixes[0],prefixes[0]]):
  try:q.prefix_prerequisites(paths)
  except ValueError:pass
  else:raise AssertionError('invalid prefix prerequisites accepted')
 # This is a fresh chain, without registered import pins. Resume must refuse.
 assert not (P/'resume-pins.json').exists(),'fresh chain unexpectedly registered a resume'
 try:resume_chain.validate(P/'build/unregistered-old-chain')
 except FileNotFoundError:pass
 else:raise AssertionError('unregistered resume accepted')
 try:q.selected_windows(SimpleNamespace(phase='early',resume_from=Path('/synthetic')))
 except ValueError:pass
 else:raise AssertionError('early resume accepted')
 actual_run=subprocess.run;actual_popen=subprocess.Popen;windows=[];checks=[];oracles=[]
 with tempfile.TemporaryDirectory(prefix='p124c-queue-') as directory:
  tmp=Path(directory);out=tmp/storage.REGISTERED_CHAIN
  def audit(event,values):
   if event=='open' and isinstance(values[0],(str,bytes)):
    path=Path(os.fsdecode(values[0])).absolute()
    if str(path).startswith('/dev/dri/'):raise RuntimeError('device open forbidden')
    if (values[2] or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND) and path!=Path('/dev/null') and not path.resolve().is_relative_to(tmp):raise RuntimeError('write outside CPU scratch: '+str(path))
   if event=='subprocess.Popen':
    assert list(values[1])==oracle_cmd,'non-oracle subprocess forbidden'
   if event in ('os.system','os.exec','os.posix_spawn'):raise RuntimeError('native execution forbidden')
  oracle_cmd=['nice','-n','19','taskset','-c','8-15,24-31','python3','-B',str(P/'shared_oracle.py'),'--require-complete']
  import sys
  sys.addaudithook(audit)
  def popen(cmd,*args,**kwargs):
   cmd=list(map(str,cmd))
   if cmd==oracle_cmd:return actual_popen(cmd,*args,**kwargs)
   assert cmd in q.commands(out).values(),'unexpected native/window launch'
   name=cmd[cmd.index('--window')+1]
   refused=receipt(q,out,name)
   windows.append(dict(window=name,argv=cmd,native_exec_intercepted=True,malformed_refused=refused))
   return SimpleNamespace(wait=lambda:0)
  def run(cmd,*args,**kwargs):
   if list(cmd)==oracle_cmd:
    cp=actual_run(cmd,*args,stdin=subprocess.DEVNULL,timeout=120,**kwargs)
    oracles.append(dict(returncode=cp.returncode,argv=cmd));return cp
   assert str(P/'check_inputs.py') in cmd,'unexpected CPU command: '+repr(cmd)
   name=cmd[cmd.index('--window')+1] if '--window' in cmd else None
   with contextlib.redirect_stdout(io.StringIO()):result=check_inputs.check(out,prefixes,name)
   assert result['passed'],result['errors']
   checks.append(dict(window=name,passed=True,static_files=result['static_files'],generated_prerequisites=len(result['generated_prerequisites'])))
   return subprocess.CompletedProcess(cmd,0)
  args=SimpleNamespace(authorized_device_window=True,output_root=out,prefix_windows=prefixes,resume_from=None,phase='all',wait_oracle=False)
  original_unit=q.user_unit_gate
  clock=iter(range(100000,2000000,100))
  with contextlib.ExitStack() as stack:
   for item in (patch.object(storage,'B',tmp),patch.object(storage,'P',tmp),patch.object(storage,'BUILD_BASE_BUDGET',300_000_000),patch.object(subprocess,'run',side_effect=run),
      patch.object(subprocess,'Popen',side_effect=popen),patch.object(os,'getpriority',return_value=0),
      patch.object(os,'sched_getaffinity',return_value=q.DEVICE_CORES),
      patch.object(q,'user_unit_gate',side_effect=lambda _:original_unit(f'0::/user@{os.getuid()}.service/packet124c-cpu.service')),
      patch.object(q,'journal',return_value='synthetic-journal'),patch.object(q.time,'time',side_effect=lambda:next(clock))):stack.enter_context(item)
   q.run(args)
  complete=json.loads((out/'queue-all-complete.json').read_text())
  assert complete['passed'] and complete['windows']==list(q.EARLY+q.LATE)
  assert len(windows)==11 and len(checks)==12 and len(oracles)==6
  assert all(x['returncode']==0 for x in oracles)
 return dict(passed=True,device_executed=False,queue_run_executed=True,windows=windows,input_preflights=checks,
             oracle_checks=oracles,storage=disk,prefix=prefix,resume='fresh-only; unregistered resume and early resume refused',
             restored_symlinks=links,synthetic_receipts=True,scratch_removed=True,storage_scope='disposable queue scratch; actual packet137 budget checked separately',packet137_build_bytes=packet137_build_bytes,packet137_build_limit_bytes=300_000_000)

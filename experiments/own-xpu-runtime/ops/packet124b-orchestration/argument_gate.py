"""Execute all real window Python paths to intercepted native exec, CPU only.

Operational leases, predecessor device receipts and live host resources are
explicitly synthetic. Selection, parser, memory configuration, input/oracle,
retention, suite admission and native argv code execute unchanged. Fake native
returns exist only inside expendable scratch to reach later sequential execs.
K2 postprocessing replays retained real measurements, including its validator.
No synthetic output can qualify a device result or escape this gate's scratch.
"""
import argparse,contextlib,gzip,hashlib,importlib.util,json,os,resource,shutil,subprocess,sys,tempfile,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from source_decision import O,P,ROOT,sha,save
sys.path.insert(0,str(P))
WINDOWS=('K0','K1a','K1b','K2','W0p','KD','W2m','WS','WSs','WS128x','WS128')
class Reached(BaseException):pass
class Forbidden(BaseException):pass

def sources():
 return {str(f.relative_to(ROOT)):sha(f) for f in [*P.glob('*.py'),O/'argument_gate.py',O/'chain_adapter.py',*(O/'inputs/k2-replay').glob('*'),P/'selection.json',P/'bundle-selection.json',P/'memory-plan.json',P/'oracle/results/suite-manifest.json']}

def sandbox(tmp):
 def audit(event,values):
  if event=='open' and isinstance(values[0],(str,bytes)):
   path=Path(os.fsdecode(values[0])).absolute()
   if str(path).startswith('/dev/dri/'):raise Forbidden('device open forbidden')
   if (values[2] or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND) and path!=Path('/dev/null') and not path.resolve().is_relative_to(tmp):raise Forbidden('write outside CPU scratch: '+str(path))
  if event in ('subprocess.Popen','os.system','os.exec','os.posix_spawn'):raise Forbidden('execution forbidden in argument probe')
 sys.addaudithook(audit)

def probe(name):
 from chain_adapter import install
 install()
 import chain103
 q,w=chain103.install()
 import fixture_support,write_paths,storage,kd_window103
 from window_safety import environment_gate
 with tempfile.TemporaryDirectory(prefix='p124b-argv-') as directory:
  tmp=Path(directory);sandbox(tmp)
  chain=tmp/'chain';chain.mkdir();k2=chain/'K2/run0';k2.mkdir(parents=True)
  shutil.copyfile(P/'dispatch-speed6.json',k2/'dispatch-measured.json')
  command=q.commands(chain)[name];argv=command[command.index('window')+1:]
  out=chain/name
  if name=='K2':shutil.rmtree(chain/'K2')
  observations=[]
  env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'}
  if 'LD_LIBRARY_PATH' in os.environ:env['LD_LIBRARY_PATH']=os.environ['LD_LIBRARY_PATH']
  admission=SimpleNamespace(ready=lambda *a:None,check=lambda:None,scope='whole-host',record={'clients':{'synthetic':True}})
  watch=SimpleNamespace(check=lambda:None,mark_launched=lambda p:None,mark_cpu_child=lambda c:None,latch=lambda e:None,postflight=lambda:None,cancelled=[],launched=[],cpu_children=[],last=0)
  def predecessor(path,window,identity,**kwargs):
   # Earlier windows have not run in this new packet. Only their operational
   # receipts are synthetic; the current window's assembly/validators are real.
   row=dict(identity,window=window,passed=True,candidate_dispatch_sha256=sha(P/'dispatch-p45.json'),dispatch_sha256=sha(k2/'dispatch-measured.json') if k2.exists() else None)
   if window=='WS128x':
    row.update(controller='native',max_new=128,prompt_overlap='on',shared_oracle=w.admit_oracle(SimpleNamespace(window='WS128',suite_manifest=P/'oracle/results/suite-manifest.json')),
     retain_steps='1-8,97-104',retained_steps=list(range(1,9))+list(range(97,105)),diagnostic_for_speed=True,suite_manifest_sha256=sha(P/'oracle/results/suite-manifest.json'))
    path.parent.mkdir(parents=True,exist_ok=True);save(path,row)
   return row
  def capture(cmd,*args,**kwargs):
   cmd=list(map(str,cmd));assert '--output' in cmd, 'unexpected subprocess: '+repr(cmd)
   dest=Path(cmd[cmd.index('--output')+1]);assert dest.is_relative_to(tmp)
   observations.append(dict(argv=cmd,device_executed=False))
   if name in ('K0','K1a','K1b','K2'):
    dest.mkdir();save(dest/'receipt.json',dict(passed=True,synthetic_argument_gate=True))
    for leaf in ('output.bin','cases.jsonl','timings.jsonl'):(dest/leaf).write_bytes(b'')
   elif name=='KD':
    if len(observations)==3:raise Reached()
    dest.mkdir();reference=json.loads((out/'draft-reference-selection.json').read_text());binding=json.loads((out/'draft-reference-binding.json').read_text())
    from draft_identity import identity
    from bundle_selection import selected
    prefix_id=identity(selected());prefix=dict(rows=prefix_id['draft_vocab_rows'],full_rows=prefix_id['full_vocab_rows'],calibration_sha256=prefix_id['selection_sha256'],target_head_unchanged=True)
    save(dest/'draft-prefix.json',prefix)
    save(dest/'draft-kernel-choices.json',dict(selection_sha256=binding['reference_selection_sha256'],choices=reference['draft'],target_mutable_aliases=0))
    save(dest/'receipt.json',dict(passed=True,device_executed=len(observations)>1,selection_sha256=binding['reference_selection_sha256'],teardown=[dict(safe_to_exit=True,in_flight=0,live_bytes=0)]))
    (dest/'row-1').mkdir();(dest/'row-1/logits.bf16').write_bytes(bytes(2*prefix['rows']))
    (dest/'draft-capture.jsonl').write_text(json.dumps(dict(position=1,token=0))+'\n')
   elif len(observations)==2:raise Reached()
   return SimpleNamespace(pid=900000+len(observations),poll=lambda:0,returncode=0)
  original_fixtures=w.run_fixtures
  def fixtures(*a,**kw):
   original_fixtures(*a,**kw)
   raise Reached()
  with contextlib.ExitStack() as stack:
   patches=[patch.object(sys,'argv',['window.py',*argv]),patch.object(subprocess,'Popen',side_effect=capture),
    patch.object(w,'prerequisites',side_effect=predecessor),patch.object(w,'fresh_k1_owners'),
    patch.object(w,'environment_gate',side_effect=lambda:environment_gate(env)),patch.object(w,'mask_native',side_effect=lambda x:x),
    patch.object(os,'getpriority',return_value=19 if name.startswith('K') else 0),
    patch.object(w,'memory_snapshot',return_value={'MemAvailable':128*1024**3}),
    patch.object(w,'output_path',side_effect=lambda p,**k:p),patch.object(w,'admit_output',return_value={'synthetic':True}),
    patch.object(w,'Watch',return_value=watch),patch.object(w,'ldd_preflight',return_value={'intercepted':True}),
    patch.object(fixture_support,'sha',side_effect=sha),patch.object(fixture_support,'ldd_preflight',return_value={'intercepted':True}),
    patch.object(w,'run_fixtures',side_effect=fixtures),patch.object(kd_window103,'admit'),
    patch.object(write_paths,'kd_scratch',side_effect=lambda p,b:Path(p)/'host-reference')]
   for item in patches:stack.enter_context(item)
   try:
    code=w.main(admission=admission)
    raise AssertionError('native exec not reached: '+str(code)+' '+(out/'window.json').read_text())
   except Reached:pass
  expected={'K0':2,'K1a':6,'K1b':6,'K2':2,'KD':3}.get(name,2)
  assert len(observations)==expected,(name,len(observations))
  return dict(window=name,passed=True,device_executed=False,argv=observations,
   operational_receipts_synthetic=True,native_exec_intercepted=True)

def replay(old=False):
 from chain_adapter import install
 install()
 import p49_dispatch
 parent=P.with_name('packet124-record-bundle')
 with tempfile.TemporaryDirectory(prefix='p124b-k2-') as directory:
  tmp=Path(directory);sandbox(tmp)
  evidence=tmp/'evidence';pins=json.loads((O/'inputs/k2-replay/manifest.json').read_text())['files']
  for name,item in pins.items():
   assert sha(ROOT/item['archive'])==item['archive_sha256']
   raw=gzip.decompress((ROOT/item['archive']).read_bytes());assert hashlib.sha256(raw).hexdigest()==item['sha256']
   dest=evidence/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
  run=tmp/'run';run.mkdir()
  for leaf in ('summary.json','dispatch-measured.json'):shutil.copyfile(evidence/'run0'/leaf,run/leaf)
  module=p49_dispatch
  if old:
   spec=importlib.util.spec_from_file_location('frozen124_dispatch',parent/'p49_dispatch.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  summary=json.loads((run/'summary.json').read_text())
  result,policy=module.pin_production_dispatch(run,summary,round3_root=evidence/'round3-timing')
  assert result['passed'] and policy['packet49d_measured_selection']['passed']
  return dict(passed=True,device_executed=False,selection=policy['packet49d_measured_selection']['selection'],
   evidence={item['archive']:item['archive_sha256'] for item in pins.values()},original_receipts=pins)

def verify():
 row=json.loads((O/'evidence/argument-gate.json').read_text())
 assert row['passed'] and row['device_executed'] is False
 assert row['sources']==sources(),'argument gate sources changed'
 assert [r['window'] for r in row['windows']]==list(WINDOWS)
 assert all(r['passed'] and r['native_exec_intercepted'] for r in row['windows'])
 assert row['old_packet124_refusal']['returncode']!=0 and 'selection must name exactly route/recurrence/hc' in row['old_packet124_refusal']['error']
 for name,digest in row['k2']['evidence'].items():assert sha(ROOT/name)==digest,'K2 replay evidence changed'
 return row

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--probe',choices=WINDOWS+('k2-replay','old-k2'));ap.add_argument('--verify',action='store_true');a=ap.parse_args()
 if a.verify:verify();print('all-window argument gate verified');return
 if a.probe:
  result=replay(a.probe=='old-k2') if a.probe in ('k2-replay','old-k2') else probe(a.probe)
  print('ARGUMENT_RESULT='+json.dumps(result));return
 started=time.monotonic();before=sources();rows=[];negative=None;k2=None
 for name in (*WINDOWS,'old-k2','k2-replay'):
  cp=subprocess.run([sys.executable,'-B',str(Path(__file__)),'--probe',name],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180,env=dict(os.environ,OMP_NUM_THREADS='2'))
  (O/'evidence'/('arguments-'+name+'.log')).write_text(cp.stdout+cp.stderr)
  if name=='old-k2':
   assert cp.returncode!=0 and 'selection must name exactly route/recurrence/hc' in cp.stderr
   negative=dict(returncode=cp.returncode,error=cp.stderr[-2500:])
  else:
   assert cp.returncode==0, name+': '+cp.stderr[-3500:]+' '+cp.stdout[-1000:]
   result=json.loads(next(line.removeprefix('ARGUMENT_RESULT=') for line in cp.stdout.splitlines() if line.startswith('ARGUMENT_RESULT=')))
   if name=='k2-replay':k2=result
   else:rows.append(result)
  print(name,'PASS',flush=True)
 assert sources()==before
 save(O/'evidence/argument-gate.json',dict(passed=True,device_executed=False,windows=rows,k2=k2,old_packet124_refusal=negative,sources=before,seconds=time.monotonic()-started,
  scope='Real Python entry/argv/selection validation with synthetic operational admission and intercepted native execution; no device qualification'))
 verify()
if __name__=='__main__':
 # CPU-only gate process; no runtime/device import sets caps.
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage('/').free>=25_000_000_000
 main()

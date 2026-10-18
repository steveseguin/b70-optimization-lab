"""Execute every packet103 chain-window CPU startup for both selected views.

The model commands use the actual parser, allocation and capture implementation
in our compiled full-shape fixture. Only weight payload/backend are mocked.
The inherited shared K fixtures execute unchanged, from pinned parent binaries.
"""
import importlib.util,json,os,sys,subprocess,shutil,time,gzip
from pathlib import Path
from types import SimpleNamespace
from build_engine import P,ROOT,B,BASE,sha,save,limits
def main():
 limits();os.environ['OMP_NUM_THREADS']='2';sys.path.append(str(BASE))
 spec=importlib.util.spec_from_file_location('p103_startup',BASE/'startup103.py');parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)
 S=B/'startup109';S.mkdir(exist_ok=True);parent.S=S;parent.P=BASE;parent.B=BASE/'build'
 # parent.P/B remain read-only for original window/config/fixture inputs.
 # Every output/command scratch path is relocated through S.
 start=time.monotonic();shared=parent.shared_fixtures();runs=[];sources={}
 for name,row in shared.items():
  for entry in row['children']['entries']:
   f=BASE/'build/gnu-host'/entry['binary'];sources[str(f.relative_to(ROOT))]=sha(f)
 def native(cmd):
  cmd=list(map(str,cmd));cmd[0]=str(B/'full-shape/fixture');cmd.insert(1,'--startup109')
  if '--authorized-device-window' in cmd:cmd.remove('--authorized-device-window')
  dest=Path(cmd[cmd.index('--output')+1]);assert dest.is_relative_to(S)
  if dest.exists():raise ValueError('startup output already exists')
  r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
  if r.returncode:raise RuntimeError(r.stderr+'\n'+str(cmd))
  result=json.loads((dest/'result.json').read_text());files={f.name:sha(f) for f in dest.iterdir() if f.is_file()}
  if (dest/'census.json').exists():
   c=json.loads((dest/'census.json').read_text());result['device_allocation_bytes']=c['totals']['device']
   if '--draft-capture' in cmd:assert c['totals']['device']<8*1024**3
  if (dest/'draft-kernel-choices.json').exists():
   d=json.loads((dest/'draft-kernel-choices.json').read_text());d.pop('selection_sha256');result['draft_kernel_identity']=d
  shutil.rmtree(dest);return dict(command=cmd,result=result,artifacts=files)
 # The real native CPU W0p canary has two rank processes and no model weights.
 import window as w
 target=P/'lineage/selection.json';dest=S/'canary';dest.mkdir()
 args=parent.model_args('W0p',target,dest);args.device=False;args.binary=B/'gnu-host/own-rt-iq3'
 watch=SimpleNamespace(check=lambda:None,mark_launched=lambda pid:None,latch=lambda error:None)
 w.concurrency_canary(args,dest,{'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'},watch)
 shared['W0p-protocol']=dict(files={str(f.relative_to(dest)):sha(f) for f in dest.rglob('*') if f.is_file()});shutil.rmtree(dest)
 from kd_reference import command,TARGET_ONLY
 for name in ('selection','candidate'):
  target=P/'lineage'/(name+'.json');selection=json.loads(target.read_text())
  projection=json.loads(json.dumps(selection));projection['choices'].update(TARGET_ONLY);projection['choices']['other_fusion']='production'
  assert projection['draft']==selection['draft'];ref=S/(name+'-kd.json');save(ref,projection)
  inp=json.loads((BASE/'build/input/input.json').read_text());a=SimpleNamespace(card=0,draft_rank=1,context=4096,input=BASE/'build/input',dispatch=P/'lineage/dispatch-speed6.json')
  for window in parent.WINDOWS:
   parent.window_options(window)
   row=dict(view=name,window=window)
   if window in shared:row['shared_fixture']=window
   elif window=='KD':
    for mode in (False,True):
     cmd=command(B/'full-shape/fixture',a,BASE/'oracle/results/capture-incident-retrospective.tsv',inp,S/'scratch',ref,sha(ref),-1,device=mode)
     row['device_startup_on_cpu' if mode else 'host']=native(cmd)
   else:row['ranks']=[native(cmd) for cmd in parent.rank_commands(window,target)]
   runs.append(row)
  kd=next(r for r in runs if r['view']==name and r['window']=='KD')['host']['result']['draft_kernel_identity']
  for row in runs:
   if row['view']==name:
    for rank in row.get('ranks',[]):
     if 'draft_kernel_identity' in rank['result']:assert rank['result']['draft_kernel_identity']==kd
  print(name,'all eleven real window startup paths PASS',flush=True)
 for leaf in ('startup103.py','window.py','chain_pipeline.py','queue_runner.py','kd_reference.py'):
  f=BASE/leaf;sources[str(f.relative_to(ROOT))]=sha(f)
 for f in (P/'startup109.py',B/'full-shape/fixture',B/'gnu-host/own-rt-iq3',P/'native/full_shape_entry.cpp'):sources[str(f.relative_to(ROOT))]=sha(f)
 report=dict(passed=True,device_executed=False,model_payload_read=False,runs=runs,shared_fixtures=shared,sources=sources,seconds=time.monotonic()-start,
  caveat='K0 CPU structural shim has no device JIT analogue. Other K fixtures execute their real CPU startup/validation. KD runs both actual host and device argument paths on the CPU backend; only target-only layout/fusion fields are projected.')
 save(P/'evidence/startup109.json',report)
if __name__=='__main__':main()

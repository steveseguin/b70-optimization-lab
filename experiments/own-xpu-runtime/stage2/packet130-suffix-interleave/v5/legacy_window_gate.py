"""Extend the v5 gate with all eleven frozen packet124c window constructors.

Real parent window parser, Transport argv and KD reference projection execute.
The four unchanged CPU fixture paths execute from their frozen parent binaries.
Every model argv runs on the new production-shape payload/backend mock.
No legacy chain is registered for device launch by this packet.
"""
import importlib.util,json,os,resource,shutil,subprocess,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from build_engine import P,ROOT,BASE,sha,save,limits

def main():
 limits();sys.path.insert(0,str(BASE))
 spec=importlib.util.spec_from_file_location('legacy124c_startup',BASE/'startup103.py');legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
 legacy.P=BASE;legacy.B=BASE/'build';legacy.S=P/'build/legacy-startup';legacy.S.mkdir(exist_ok=True)
 # Writable paths are always packet130 or temporary scratch. Parent model
 # payloads are never opened by the numerical startup backend.
 def audit(event,args):
  if event=='open' and isinstance(args[0],(str,bytes)):
   path=Path(os.fsdecode(args[0])).absolute()
   if str(path).startswith('/dev/dri/'):raise RuntimeError('device open forbidden')
   if (args[2] or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
    assert path==Path('/dev/null') or path.resolve().is_relative_to(P) or path.resolve().is_relative_to(Path('/tmp')),path
 sys.addaudithook(audit)
 shared=legacy.shared_fixtures();runs=[]
 from kd_reference import prepare,command
 import window as w
 for choice in ('selection','candidate'):
  target=P/'lineage'/(choice+'.json')
  # The frozen strict projection accepts exactly its eleven-key bundle7.
  stripped=json.loads(target.read_text());schedule=stripped['choices'].pop('suffix_schedule')
  assert schedule in ('production','layer-interleave') and stripped==json.loads((BASE/'selection.json').read_text())
  target124=legacy.S/'kd-target124.json';save(target124,stripped)
  ref,binding=prepare(target124,sha(target124),legacy.S)
  # KD deliberately has no target head; the schedule is inert there.
  row=json.loads(ref.read_text());row['choices']['suffix_schedule']='production';save(ref,row)
  binding.update(reference_selection_sha256=sha(ref),target_selection_sha256=sha(target),selection_sha256=sha(target),suffix_schedule_projected='production');save(legacy.S/'draft-reference-binding.json',binding)
  inp=json.loads((BASE/'build/input/input.json').read_text())
  a=SimpleNamespace(card=0,draft_rank=1,context=4096,input=BASE/'build/input',dispatch=BASE/'dispatch-speed6.json')
  for name in legacy.WINDOWS:
   legacy.window_options(name)
   entry=dict(view=choice,window=name,passed=True)
   if name in shared:entry['unchanged_cpu_fixture']=shared[name]
   elif name=='KD':
    cmds=[command(legacy.S/'fixture',a,BASE/'oracle/results/capture-incident-retrospective.tsv',inp,legacy.S/'scratch',ref,sha(ref),-1,**kw) for kw in ({},{'device':True})]
    entry['startup']=[startup(cmd) for cmd in cmds]
   else:entry['startup']=[startup(cmd) for cmd in legacy.rank_commands(name,target)]
   runs.append(entry)
  print(choice,'all eleven window constructors and CPU starts PASS',flush=True)
 save(P/'evidence/legacy-windows.json',dict(passed=True,device_executed=False,model_payload_read=False,runs=runs,total_windows=len(runs),registered_device_chain=False,sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'legacy_window_gate.py',BASE/'startup103.py',BASE/'window.py',BASE/'kd_reference.py',BASE/'chain_pipeline.py',BASE/'queue_runner.py',P/'lineage/selection.json',P/'lineage/candidate.json']}))

def startup(cmd):
 cmd=list(map(str,cmd));cmd[0]=str(P/'build/full-shape/fixture');cmd.insert(1,'--startup109')
 if '--authorized-device-window' in cmd:cmd.remove('--authorized-device-window')
 with tempfile.TemporaryDirectory(prefix='p130-legacy-') as d:
  cmd[cmd.index('--output')+1]=d
  if '--native-nice' in cmd:cmd[cmd.index('--native-nice')+1]='19'
  r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
  assert r.returncode==0,r.stderr
  result=json.loads((Path(d)/'result.json').read_text());assert result['passed']
  return dict(passed=True,result=result,argv=cmd)
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()

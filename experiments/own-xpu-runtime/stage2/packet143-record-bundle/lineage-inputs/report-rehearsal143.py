"""Exercise packet143's real inline smoke report, CPU-only synthetic receipts."""
import ast,json,resource,sys,tempfile,hashlib,time
from pathlib import Path
P=Path(__file__).resolve().parents[1];ROOT=P.parents[3];O=P.parents[1]/'ops/packet143-orchestration'
sys.path.insert(0,str(P))
def main():
 from bootstrap import install
 install()
 import smoke_screen as screen
 from types import SimpleNamespace
 tree=ast.parse((P/'smoke_screen.py').read_text());body=None
 for node in ast.walk(tree):
  candidates=getattr(node,'body',None)
  if not isinstance(candidates,list):continue
  for i,n in enumerate(candidates):
   if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='proof' for t in n.targets) and 'report-inputs.json' in ast.unparse(n):body=candidates[i:];break
  if body is not None:break
 assert body and isinstance(body[-1],ast.Return)
 with tempfile.TemporaryDirectory(prefix='p143-inline-report-') as directory:
  out=Path(directory);(out/'run').mkdir()
  manifest=screen.read(P/'oracle/results/suite-manifest.json');requests=[]
  for entry in manifest['prompts']:
   result=screen.read(P/'oracle/results'/entry['prompt_id']/'result.json')
   requests.append(dict(prompt_id=entry['prompt_id'],tokens=result['tokens'][:64],cached_tokens=0,passed=True,exact_oracle=True))
  proof=dict(passed=True,requests=requests,incident64=dict(passed=True),lane='A',placement={'synthetic':True},device_isolation={'passed':True,'synthetic':True})
  screen.save(out/'run/report-inputs.json',proof)
  namespace=dict(screen.__dict__,args=SimpleNamespace(output=out,lane='A'),manifest=manifest,identity={'timing':'token'},record={'started_utc_ns':time.time_ns()})
  namespace['persist']=lambda:screen.save(out/'window.json',namespace['record'])
  function=ast.FunctionDef(name='report143',args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),body=body,decorator_list=[])
  module=ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[]));exec(compile(module,str(P/'smoke_screen.py'),'exec'),namespace)
  assert namespace['report143']()==0
  summary=screen.read(out/'summary.json');assert summary['passed'] and summary['request_count']==12 and summary['tokens']==64
  result=dict(passed=True,device_executed=False,synthetic_evidence=True,shared_optional_report_harness_supported=False,reason='Shared --report imports all main-body imports before bootstrap calls and adds --kind; custom packet136-style inline smoke needs its actual bootstrap order. This probe executes that actual inline report body.',requests=12,tokens=64,target_suffix_winners=summary['target_suffix_winners'],sources={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in (P/'smoke_screen.py',P/'bootstrap.py',Path(__file__))})
  (O/'evidence/inline-report143.json').write_text(json.dumps(result,indent=2)+'\n');print('real inline 12x64 smoke report PASS (synthetic CPU evidence)')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()

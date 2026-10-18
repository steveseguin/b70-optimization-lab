"""Complete 22-request worker rehearsal, with native execution forbidden.

Real selection, input, oracle and output-processing paths run. Device monitor,
transport, request results and teardown permits are explicit synthetic doubles;
all such evidence is confined to temporary scratch and discarded.
"""
import contextlib,json,os,subprocess,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from build_engine import P,ROOT,sha,save,limits
class Forbidden(BaseException):pass

def probe():
 from run_screen import VIEW
 from common import sealed,D
 import worker
 sys.path.insert(0,str(P))
 import pipeline,suite
 from analyze import decide
 identity=sealed(SimpleNamespace(lineage=VIEW,seal=VIEW/'screen-seal.json',binary=None,dispatch=None,profile='tp2',timing='token',placement='1'))
 identity['lane']='B'
 expected={}
 for entry in D.oracle_inputs()['prompts']:
  bundle=ROOT/entry['input_bundle']
  tokens=json.loads((bundle/'input.json').read_text())['tokens']
  expected[tuple(tokens)]=D.CHECK.token_record(D.ORACLE/'results'/entry['prompt_id'])[:128]
 with tempfile.TemporaryDirectory(prefix='p129-worker-cpu-') as directory:
  scratch=Path(directory)
  def audit(event,args):
   if event=='open' and isinstance(args[0],(str,bytes)):
    path=Path(os.fsdecode(args[0])).absolute()
    if str(path).startswith('/dev/dri/'):raise Forbidden('GPU access forbidden')
    if (args[2] or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND) and path!=Path('/dev/null') and not path.resolve().is_relative_to(scratch):raise Forbidden('write outside scratch')
   if event in ('subprocess.Popen','os.system','os.exec','os.posix_spawn'):raise Forbidden('real subprocess forbidden')
  sys.addaudithook(audit)
  trace=[];fault=[False]
  class Transport:
   def __init__(self,args,out,*a,**k):self.a=args;self.out=out;self.children=[];self.closed=False;self.stop_write=-1;trace.append('load')
   def stop(self,*a):trace.append('stop')
   def close(self,success):self.closed=True;trace.append('close-success' if success else 'close-failure')
  class Monitor:
   def __init__(self,lane,out):
    save(out/'device-isolation.json',dict(passed=True,synthetic=True));trace.append('monitor')
   def poll(self,**k):pass
   def register(self,pid):raise Forbidden('native launch hook reached')
  def reset(transport,dest):
   transport.destination=dest
   for rank in (0,1):(dest/f'rank{rank}').mkdir(parents=True)
   trace.append('reset')
  def request(transport,args,prompt,count):
   tokens=expected.get(tuple(prompt),[42]*128)
   native=dict(draft_rows=[]);shadow=[]
   for i,token in enumerate(tokens):
    native['draft_rows'].append(dict(position=len(prompt)+i,guess=token,actual=token,provider_error=0,hit=True if i+1<len(tokens) else None))
    shadow.append(dict(draft_position=len(prompt)+i-2,production=token+(1 if fault[0] and i==0 else 0),candidate=token,restored_exact=True))
   save(transport.out/'native-result.json',native)
   (transport.destination/'rank1/shadow-rows.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in shadow))
   trace.append('request')
   return dict(passed=True,tokens=tokens,cached_tokens=0,output_token_sha256=D.token_hash(tokens))
  with patch.object(pipeline,'Transport',Transport),patch.object(suite,'reset',reset),patch.object(suite,'run_request',request),patch.object(worker,'DeviceMonitor',Monitor),patch.object(worker,'masked_environment',return_value={}),patch.object(worker,'Teardown',side_effect=lambda *a,**k:contextlib.nullcontext()):
   code=worker.run(identity,scratch/'positive',7200)
   assert code==0 and trace.count('load')==1 and trace.count('request')==22 and trace.count('reset')==23 and trace[-1]=='close-success',trace
   proof=json.loads((scratch/'positive/report-inputs.json').read_text())
   verdict=decide(proof['requests']);assert verdict['passed'] and not verdict['acceptance_gate_passed']
   assert verdict['groups']['independent']['verified']==1270 and verdict['groups']['secondary']['verified']==1524
   positive=list(trace);trace.clear();fault[0]=True
   code=worker.run(identity,scratch/'negative',7200)
   assert code==1 and trace.count('request')==1 and 'stop' in trace and trace[-1]=='close-failure'
   assert not (scratch/'negative/report-inputs.json').exists()
   return dict(passed=True,device_executed=False,native_execution_forbidden=True,synthetic_evidence_retained=False,positive_trace=positive,negative_trace=trace,requests=22,independent_proposals=1270,secondary_proposals=1524,negative_control='changed production guess aborts after first request and cooperatively drains')

def main():
 if '--probe' in sys.argv:print('WORKER_RESULT='+json.dumps(probe()));return
 limits();r=subprocess.run([sys.executable,'-B',str(P/'worker_gate.py'),'--probe'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
 (P/'evidence/worker-gate.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
 result=json.loads(next(line.removeprefix('WORKER_RESULT=') for line in r.stdout.splitlines() if line.startswith('WORKER_RESULT=')))
 result['sources']={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('worker_gate.py','worker.py','analyze.py','pipeline.py','suite.py','calibration/inputs.json')}
 save(P/'evidence/worker-gate.json',result);print('Complete worker lifecycle and corrupted-production negative control PASS')
if __name__=='__main__':main()

"""Run every smoke/bracket request and the error teardown path in CPU scratch."""
import contextlib,json,os,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch
from p183_v5_build_engine import P,ROOT,sha,save,limits
from argument_gate import identity
class Forbidden(BaseException):pass

def probe(kind,variant="metadata"):
 row=identity(kind,variant)
 oracle_command=['nice','-n','19','taskset','-c','8-15,24-31','python3','-B',str(P.parent/'shared_oracle.py'),'--require-complete'];oracle_calls=[]
 import tp2_worker as worker,bracket,analyze
 from common import D,P56
 sys.path.insert(0,str(P56));import pipeline,suite
 expected={}
 for entry in D.oracle_inputs()['prompts']:
  bundle=ROOT/entry['input_bundle'];tokens=json.loads((bundle/'input.json').read_text())['tokens']
  expected[tuple(tokens)]=D.CHECK.token_record(D.ORACLE/'results'/entry['prompt_id'])[:128]
 with tempfile.TemporaryDirectory(prefix='p142-worker-') as d:
  tmp=Path(d)
  def audit(event,args):
   if event=='open' and isinstance(args[0],(str,bytes)):
    path=Path(os.fsdecode(args[0])).absolute()
    if str(path).startswith('/dev/dri/'):raise Forbidden('device open forbidden')
    if (args[2] or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND) and path!=Path('/dev/null') and not path.resolve().is_relative_to(tmp):raise Forbidden('write outside CPU scratch: '+str(path))
   if event in ('subprocess.Popen','os.posix_spawn') and list(args[1])==oracle_command:
    oracle_calls.append(oracle_command);return
   if event in ('subprocess.Popen','os.system','os.exec','os.posix_spawn'):raise Forbidden('execution forbidden')
  sys.addaudithook(audit);trace=[];bad=[False]
  class Transport:
   def __init__(self,args,out,*a,**k):self.out=out;self.children=[];self.closed=False;self.stop_write=-1;trace.append('load')
   def stop(self,*a):trace.append('stop')
   def close(self,success):self.closed=True;trace.append('close-success' if success else 'close-failure')
  class Monitor:
   def __init__(self,lane,out):save(out/'device-isolation.json',dict(passed=True,synthetic=True))
   def poll(self,**k):pass
   def register(self,pid):raise Forbidden('native process registered')
  def switch(transport,view,dest,suite):
   trace.append('switch:'+read_choice(view));dest.mkdir()
   proofs=[]
   for rank in (0,1):
    proof=dict(passed=True,total_reset=True,cached_tokens=0,selection_sha256=view['selection_sha256'],allocation_ids_preserved=True,weight_uploads_after_load=0,arena_descriptors_sha256=str(rank),weight_descriptors_sha256=str(rank))
    save(dest/f'boundary-rank{rank}.json',proof);proofs.append(proof)
   return proofs
  def reset(transport,dest):
   for rank in (0,1):(dest/f'rank{rank}').mkdir(parents=True)
   trace.append('reset')
  def request(transport,args,prompt,count):
   tokens=list(expected[tuple(prompt)][:count])
   if bad[0]:tokens[0]+=1
   trace.append('request:'+str(count))
   return dict(passed=True,tokens=tokens,cached_tokens=0,output_token_sha256=D.token_hash(tokens))
  with patch.object(analyze,'first_minute_proof',return_value={'passed':True,'synthetic':True}),patch.object(pipeline,'Transport',Transport),patch.object(suite,'reset',reset),patch.object(suite,'run_request',request),patch.object(bracket,'switch_reset',switch),patch.object(worker,'DeviceMonitor',Monitor),patch.object(worker,'masked_environment',return_value={}),patch.object(worker,'Teardown',side_effect=lambda *a,**k:contextlib.nullcontext()):
   code=worker.run(row,tmp/'positive',900)
   n=1 if kind=='smoke' else 5;assert code==0 and trace.count('load')==1 and sum(x.startswith('request:') for x in trace)==13*n and trace[-1]=='close-success',trace
   proof=json.loads((tmp/'positive/bracket-inputs.json').read_text());assert len(proof['views'])==n
   for v in proof['views']:
    assert len(v['requests'])==12 and all(len(r['tokens'])==(64 if kind=='smoke' else 128) for r in v['requests'])
   positive=list(trace);trace.clear();bad[0]=True
   code=worker.run(row,tmp/'negative',900)
   assert code==1 and trace.count('load')==1 and trace.count('request:64')==1 and trace[-2:]==['stop','close-failure'],trace
   assert not (tmp/'negative/report-inputs.json').exists()
   assert len(oracle_calls)>=2
   return dict(passed=True,device_executed=False,kind=kind,positive_trace=positive,negative_trace=trace,requests=n*13,all_view_requests=True,real_oracle_commands=oracle_calls,native_execution_forbidden=True,synthetic_device_receipts_retained=False)

def read_choice(view):return json.loads(Path(view['selection']).read_text())['choices']['dense_scales']

def main():
 limits();rows=[]
 for kind in ('smoke','bracket'):
  r=subprocess.run([sys.executable,'-B',str(P/'worker_gate.py'),'--probe',kind],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=240)
  (P/'evidence'/('worker-'+kind+'.log')).write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
  rows.append(json.loads(next(x.removeprefix('WORKER_RESULT=') for x in r.stdout.splitlines() if x.startswith('WORKER_RESULT='))))
 save(P/'evidence/worker-gate.json',dict(passed=True,device_executed=False,rows=rows,sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'worker_gate.py',P/'tp2_worker.py',P/'bracket.py',P/'conditions.py']}))
 print('All 78 smoke/bracket requests, corrupted-output abort/no retry and cooperative drain PASS')
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 if '--probe' in sys.argv:print('WORKER_RESULT='+json.dumps(probe(sys.argv[-1])))
 else:main()

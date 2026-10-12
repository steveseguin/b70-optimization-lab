"""Serial CPU gates only, bounded RSS, no device executable calls."""
import gzip,hashlib,json,os,resource,signal,subprocess,time,sys
from pathlib import Path
from build import sha
from summarize import summarize
P=Path(__file__).resolve().parent;B=P/'build'
def run(binary,args,log,asan=False):
 def bound():
  if not asan:resource.setrlimit(resource.RLIMIT_AS,(7*1024**3,7*1024**3))
 peak=0;start=time.monotonic();failure=None
 with log.open('w') as f:
  child=subprocess.Popen(['nice','-n','19','ionice','-c','3',str(binary),*map(str,args)],stdout=f,stderr=subprocess.STDOUT,preexec_fn=bound,env={**os.environ,'OMP_NUM_THREADS':'2','ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
  while child.poll() is None:
   status=Path('/proc')/str(child.pid)/'status'
   try:
    text=status.read_text();anon=int(next(line.split()[1] for line in text.splitlines() if line.startswith('RssAnon:')))*1024;peak=max(peak,anon)
   except (FileNotFoundError,StopIteration):pass
   if peak>=7*1024**3 or time.monotonic()-start>1200:
    failure='CPU gate resource/deadline bound';child.send_signal(signal.SIGTERM);break
   time.sleep(.1)
  child.wait(timeout=90)
 assert not failure and child.returncode==0,(failure,log)
 return peak

def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 rows=[];hashes=set()
 reuse='--reuse' in sys.argv
 prior=json.loads((P/'cpu-tests.json').read_text()) if reuse else None
 for mode in ('host','icpx-host','asan'):
  for fresh in range(2):
   out=B/f'gate-{mode}-{fresh}'
   if out.exists():
    assert reuse
    old=next(r for r in prior['rows'] if r['compiler']==mode and r['fresh_process']==fresh)
    assert old['binary_sha256']==sha(B/mode/'replay-bench')
    peak=old['max_sampled_anonymous_bytes']
   else:peak=run(B/mode/'replay-bench',['--cpu-test','--output',out],B/f'gate-{mode}-{fresh}.log',mode=='asan')
   r=json.loads((out/'receipt.json').read_text());assert not r['device_executed'] and r['routed_sets']>1
   summary=summarize(out);hashes.add(r['final_state_sha256'])
   rows.append({'compiler':mode,'fresh_process':fresh,'binary_sha256':sha(B/mode/'replay-bench'),'max_sampled_anonymous_bytes':peak,**{k:v for k,v in r.items() if k!='teardown'},'teardown_sha256':hashlib.sha256(json.dumps(r['teardown'],sort_keys=True).encode()).hexdigest(),'iteration_log_sha256':sha(out/'iterations.jsonl'),'dynamic_log_sha256':sha(out/'dynamic.jsonl')})
   print(mode,fresh,'PASS',flush=True)
 assert len(hashes)==1,'fresh/compiler byte divergence'
 out=B/'census-final'
 if not out.exists():peak=run(B/'host/replay-bench',['--census','--output',out],B/'census-final.log')
 census=json.loads((out/'census.json').read_text());(P/'census.json').write_text(json.dumps(census,indent=2)+'\n')
 (P/'launch-plan.jsonl').write_bytes((out/'launch-plan.jsonl').read_bytes())
 (P/'allocation-census.json').write_bytes((out/'allocations.json').read_bytes())
 # No raw/unknown mode can pass the host argument guard or create an owner.
 guard=[]
 for flags in (['--mode','raw'],['--raw'],['--authorized-device-window','--cpu-test']):
  r=subprocess.run(['nice','-n','19','ionice','-c','3',str(B/'host/replay-bench'),*flags,'--output',str(B/'rejected-entry')],capture_output=True,text=True)
  assert r.returncode==1 and 'context lifetime' not in r.stderr
  guard.append({'arguments':flags,'returncode':r.returncode,'stderr':r.stderr.strip()})
 result={'passed':True,'device_executed':False,'fresh_processes':len(rows),'iterations_per_process':210,'buffer_comparisons':sum(r['buffer_byte_comparisons'] for r in rows),'final_state_sha256':hashes.pop(),'rows':rows,'census_sha256':sha(P/'census.json'),'entry_guards':guard}
 (P/'cpu-tests.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()

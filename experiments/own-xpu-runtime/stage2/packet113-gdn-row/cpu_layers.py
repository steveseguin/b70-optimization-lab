"""Complete synthetic layers, four serial tokens, two fresh owners per compiler."""
import os,subprocess,resource
from build_engine import P,B,limits,save,sha
import json
def main():
 limits();records=[];env=dict(os.environ,OMP_NUM_THREADS='2')
 for compiler in ('gnu-host','intel-host'):
  build=json.loads((P/'evidence'/('build-'+compiler+'.json')).read_text());binary=B/compiler/'layer-bench'
  assert sha(binary)==build['artifacts'][str(binary.relative_to(P))]
  for repeat in (1,2):
   out=P/'evidence'/f'full-{compiler}-{repeat}';existing=out.exists()
   if not existing:out.mkdir()
   cmd=[str(binary),'--cpu-test','--mode','exact','--layer','gdn','--output',str(out)]
   if not existing:
    with (out/'run.log').open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,check=True,timeout=600)
   r=json.loads((out/'receipt.json').read_text());assert r['passed'] and r['cpu_mock'] and not r['device_executed'] and r['safe_to_exit'] and r['recurrence_checks']==768 and r['checks']>400 and r['route_set_counts']=={'4':4}
   records.append(dict(compiler=compiler,repeat=repeat,binary_sha256=sha(binary),receipt=str((out/'receipt.json').relative_to(P)),receipt_sha256=sha(out/'receipt.json'),checks=r['checks'],recurrence_checks=r['recurrence_checks'],recurrence_transcript_sha256=sha(out/'recurrence-cases.jsonl'),exact_output_identity=r['exact_output_identity']))
   print(compiler,repeat,str(r['checks'])+' checks PASS',flush=True)
 for compiler in ('gnu-host','intel-host'):
  assert len({(x['exact_output_identity'],x['recurrence_transcript_sha256']) for x in records if x['compiler']==compiler})==1,'fresh owner mismatch'
 save(P/'evidence/cpu-layers.json',dict(passed=True,device_executed=False,scope='candidate versus production complete GDN layer plus 768 exceptional/multi-token full-state checks per process',records=records,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
if __name__=='__main__':main()

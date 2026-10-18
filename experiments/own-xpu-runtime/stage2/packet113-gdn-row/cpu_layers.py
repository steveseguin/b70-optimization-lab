"""Complete synthetic layers, four serial tokens, two fresh owners per compiler."""
import os,subprocess,resource
from build_engine import P,B,limits,save,sha
import json
def main():
 limits();records=[];env=dict(os.environ,OMP_NUM_THREADS='2')
 for compiler in ('gnu-host',):
  build=json.loads((P/'evidence'/('build-'+compiler+'.json')).read_text());binary=B/compiler/'layer-bench'
  assert sha(binary)==build['artifacts'][str(binary.relative_to(P))]
  for repeat in (1,2):
   out=P/'evidence'/f'full-{compiler}-{repeat}';assert not out.exists();out.mkdir()
   cmd=[str(binary),'--cpu-test','--mode','exact','--layer','gdn','--output',str(out)]
   with (out/'run.log').open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,check=True,timeout=600)
   r=json.loads((out/'receipt.json').read_text());assert r['passed'] and r['cpu_mock'] and not r['device_executed'] and r['safe_to_exit'] and r['checks']>400 and r['route_set_counts']=={'4':4}
   records.append(dict(compiler=compiler,repeat=repeat,binary_sha256=sha(binary),receipt=str((out/'receipt.json').relative_to(P)),receipt_sha256=sha(out/'receipt.json'),checks=r['checks'],exact_output_identity=r['exact_output_identity']))
   print(compiler,repeat,str(r['checks'])+' checks PASS',flush=True)
 assert len({x['exact_output_identity'] for x in records})==1,'fresh owner/compiler mismatch'
 save(P/'evidence/cpu-layers.json',dict(passed=True,device_executed=False,scope='current GDN versus identical current replay; harness state and repeat check, no candidate qualification',records=records,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
if __name__=='__main__':main()

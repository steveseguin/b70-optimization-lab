"""Full QSA layer, both contexts/orders, two fresh processes per compiler."""
import argparse,os,subprocess,resource,json
from build_engine import P,B,limits,save,sha
MODES=('gnu-host','intel-host')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--compiler',choices=MODES);args=ap.parse_args()
 limits();env=dict(os.environ,OMP_NUM_THREADS='2')
 for compiler in (args.compiler,) if args.compiler else MODES:
  build=json.loads((P/'evidence'/('build-'+compiler+'.json')).read_text());binary=B/compiler/'layer-bench'
  assert sha(binary)==build['artifacts'][str(binary.relative_to(P))]
  for repeat in (1,2):
   out=P/'evidence'/f'full-{compiler}-{repeat}';assert not out.exists();out.mkdir()
   cmd=[str(binary),'--cpu-test','--mode','exact','--layer','qsa','--output',str(out)]
   with (out/'run.log').open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,check=True,timeout=1200)
   print(compiler,repeat,'PASS',flush=True)
 records=[]
 for compiler in MODES:
  for repeat in (1,2):
   out=P/'evidence'/f'full-{compiler}-{repeat}'
   if not (out/'receipt.json').exists():continue
   r=json.loads((out/'receipt.json').read_text());assert r['passed'] and r['cpu_mock'] and not r['device_executed'] and r['safe_to_exit'] and r['checks']>400 and r['route_set_counts']=={'3':4}
   records.append(dict(compiler=compiler,repeat=repeat,binary_sha256=sha(B/compiler/'layer-bench'),receipt=str((out/'receipt.json').relative_to(P)),receipt_sha256=sha(out/'receipt.json'),checks=r['checks'],exact_output_identity=r['exact_output_identity']))
 for compiler in MODES:
  group=[x for x in records if x['compiler']==compiler]
  if group:assert len(group)==2 and len({x['exact_output_identity'] for x in group})==1,'fresh process mismatch'
 save(P/'evidence/cpu-layers.json',dict(passed=len(records)==4,device_executed=False,scope='production/p116 full QSA synthetic layer and all mutable bytes, contexts128/4096, both orders; two fresh processes per compiler, Intel candidate/entry with inherited production GNU reference',cross_compiler_identical=len({x['exact_output_identity'] for x in records})==1,records=records,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
if __name__=='__main__':main()

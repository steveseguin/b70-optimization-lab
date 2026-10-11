#!/usr/bin/env python3
import json,subprocess,hashlib,os,resource,shutil,time
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 root=B/('stream-check-'+str(time.time_ns()));root.mkdir();inp=root/'input';inp.mkdir()
 (inp/'tokens.txt').write_text((B/'input/tokens.txt').read_text().split()[0]+'\n');shutil.copyfile(B/'input/vocab.bin',inp/'vocab.bin')
 rows=[]
 for tag,source in [('baseline',P.with_name('packet21-fused')),('token',P)]:
  binary=source/'build/host/own-rt-iq3';out=root/tag
  cmd=[str(binary),'--cards','1','--card','0','--memory','layer-streaming','--fusion','on','--gemv','frozen','--stage','decode','--context','256','--input',str(inp/'tokens.txt'),'--max-new','3','--plan',str(B/'input/plan.tsv'),'--identity',str(B/'input/identity.tsv'),'--model-dir',json.loads((B/'input/input.json').read_text())['model_dir'],'--output',str(out)]
  if tag=='token':cmd+=['--timing','token']
  start=time.monotonic()
  with (root/(tag+'.log')).open('w') as log:subprocess.run(cmd,check=True,stdout=log,stderr=subprocess.STDOUT)
  r=json.loads((out/'receipt.json').read_text());assert r['passed'] and not r['device_executed']
  rows.append(dict(tag=tag,argv=cmd,binary_sha256=sha(binary),tokens=r['tokens'],layers={str(f.relative_to(out)):sha(f) for f in out.glob('step*/layer-*.bf16')},seconds=time.monotonic()-start,maxrss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 assert rows[0]['tokens']==rows[1]['tokens'] and rows[0]['layers']==rows[1]['layers'] and len(rows[1]['layers'])==144
 (P/'streaming-real.json').write_text(json.dumps(dict(passed=True,device_executed=False,positions=[0,1,2],layer_matches=144,rows=rows),indent=2)+'\n')
 print('STREAM 144/144 layers, 3/3 tokens',flush=True)
if __name__=='__main__':main()

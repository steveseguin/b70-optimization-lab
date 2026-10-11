#!/usr/bin/env python3
"""Run only the host binary, gate all retained layers and every generated token."""
import argparse, hashlib, json, os, subprocess, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
ORACLE=ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v1-parallel-20261011/incident-retrospective'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--gemv',choices=['frozen','r5'],required=True);p.add_argument('--max-new',type=int,default=64);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 binary=HERE/'build/host/own-rt-iq3';inp=HERE/'build/input'
 assert 'idle' in subprocess.check_output(['ionice','-p',str(os.getpid())],text=True,timeout=2)
 dynamic=subprocess.check_output(['readelf','-d',str(binary)],text=True,timeout=5)
 assert not any(s in dynamic.lower() for s in ('libsycl','libze_loader','libur_loader','libopencl'))
 model=json.loads((inp/'input.json').read_text())['model_dir']
 args=[str(binary),'--stage','decode','--prompt-tokens',str(inp/'tokens.txt'),'--plan',str(inp/'plan.tsv'),'--identity',str(inp/'identity.tsv'),'--model-dir',model,'--output',str(a.output),'--max-new',str(a.max_new),'--context','256','--nongemv','parallel','--gemv',a.gemv,'--oracle',str(ORACLE),'--seconds','10800']
 bindings={str(binary):sha(binary),str(inp/'tokens.txt'):sha(inp/'tokens.txt'),str(inp/'input.json'):sha(inp/'input.json'),str(ORACLE/'result.json'):sha(ORACLE/'result.json')}
 started=time.monotonic()
 with (HERE/f'cpu-{a.gemv}.log').open('w') as log: r=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,timeout=10900)
 receipt=json.loads((a.output/'receipt.json').read_text());expected=json.loads((ORACLE/'result.json').read_text())['tokens'][:a.max_new]
 rows=[];first=None
 for step in range(1,min(a.max_new,8)+1):
  for layer in range(48):
   f=a.output/f'step{step}'/f'layer-{layer:02}.bf16';e=ORACLE/f'step{step}'/f'layer-{layer:02}.bf16'
   match=f.exists() and f.read_bytes()==e.read_bytes()
   rows.append(dict(step=step,layer=layer,exact=match,sha256=sha(f) if f.exists() else None,oracle_sha256=sha(e)))
   if f.exists() and not match and first is None:first=dict(step=step,layer=layer)
 tokens=receipt['tokens'];passed=all(sha(Path(path))==digest for path,digest in bindings.items()) and r.returncode==0 and receipt['passed'] and tokens==expected and all(x['exact'] for x in rows)
 result=dict(passed=passed,bindings=bindings,device_executed=False,argv=args,binary_sha256=sha(binary),wall_seconds=time.monotonic()-started,returncode=r.returncode,layer_matches=sum(x['exact'] for x in rows),layer_total=len(rows),first_differing_layer=first,tokens=tokens,expected_tokens=expected,token_matches=sum(x==y for x,y in zip(tokens,expected)),layers=rows,missing_fixtures=sum(x['sha256'] is None for x in rows),run_receipt={**receipt,'teardown':[{k:v for k,v in t.items() if k!='sequence'} for t in receipt['teardown']]})
 (HERE/f'cpu-real-{a.gemv}.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k not in ('layers','run_receipt','argv')}),flush=True)
 raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()

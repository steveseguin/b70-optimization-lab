"""Actual host execution and complete registered argument blocks, CPU only."""
import gzip,hashlib,json,os,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 binary=B/'host/own-rt-iq3'
 from cpu_gates import host
 host(binary);root=B/('prepared-equivalence-'+str(time.time_ns()));root.mkdir();token=root/'token.txt';token.write_text('2\n');rows=[];logs=[]
 for dispatch in ('default','all-new','merged-example'):
  for mode in ('core','parallel'):
   outputs={}
   for name,extra in [('legacy',['--host-path','legacy']),('prepared',['--host-path','prepared'])]:
    out=root/(dispatch+'-'+mode+'-'+name)
    cmd=[str(binary),'--mini','--cards','2','--card','0','--memory','resident','--input',str(token),'--max-new','3','--dispatch',str(P/('dispatch-'+dispatch+'.json')),'--nongemv',mode,'--argument-audit',*extra,'--output',str(out)]
    r=subprocess.run(cmd,capture_output=True,text=True);assert r.returncode==0,(cmd,r.stderr)
    result=json.loads((out/'receipt.json').read_text());assert result['passed'] and not result['device_executed']
    args=[json.loads(line) for line in (out/'argument-equivalence.jsonl').open()]
    assert args and all(x['legacy_argument_hex']==x['prepared_argument_hex'] for x in args)
    outputs[name]=(out,result,args)
   legacy,lr,la=outputs['legacy'];prepared,pr,pa=outputs['prepared']
   assert len(la)==len(pa)*3,(dispatch,mode,len(la),len(pa))
   assert la[:len(pa)]==pa,(dispatch,mode,'launch order/bound argument mismatch')
   assert all(la[i:i+len(pa)]==pa for i in range(0,len(la),len(pa)))
   assert lr['tokens']==pr['tokens'] and (legacy/'buffers.json').read_bytes()==(prepared/'buffers.json').read_bytes()
   fixtures=list(prepared.glob('step*/layer-*.bf16'));assert len(fixtures)==6
   assert all(f.read_bytes()==(legacy/f.relative_to(prepared)).read_bytes() for f in fixtures)
   rows.append(dict(dispatch=dispatch,mode=mode,launches_per_plan=len(pa),legacy_launches=len(la),bound_argument_blocks_exact=True,tokens=pr['tokens'],layer_matches=len(fixtures),buffers_sha256=sha(prepared/'buffers.json')))
   logs.append(dict(dispatch=dispatch,mode=mode,prepared=pa,legacy=la))
 raw=(json.dumps(logs,sort_keys=True)+'\n').encode();packed=gzip.compress(raw,mtime=0);dest=P/'evidence/prepared-equivalence-arguments.json.gz';dest.write_bytes(packed);assert gzip.decompress(dest.read_bytes())==raw
 receipt=dict(passed=True,device_executed=False,cases=len(rows),rows=rows,binary_sha256=sha(binary),argument_blocks=sum(x['legacy_launches'] for x in rows),full_trace=dict(path=str(dest.relative_to(P)),sha256=sha(dest),uncompressed_sha256=hashlib.sha256(raw).hexdigest()),scope='Actual two-card mini plan: cached prepared sequence versus original launch front ends, full registered functor state and allocation binding IDs; pointers separately retained in per-run prepared-arguments.jsonl; native execution remains pending')
 (P/'prepared-equivalence.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt['cases'],'cases',receipt['argument_blocks'],'blocks exact')
if __name__=='__main__':main()

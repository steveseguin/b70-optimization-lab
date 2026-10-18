"""CPU-only fresh-process router tests; real weights, synthetic hidden states."""
import argparse,json,os,resource,subprocess,sys
from array import array
from pathlib import Path
from router_replay import P,ROOT,Weights,library,run_router,sha,save,chunks

def probe(compiler):
 import hashlib,random,struct
 lib=library(compiler);w=Weights();weights=w.router(0)
 rng=random.Random(138)
 inputs=array('H')
 for item in range(6):
  for j in range(2560):
   if item==0:bits=0
   elif item==1:bits=0x3f80 if j%2 else 0xbf80
   else:
    word=struct.unpack('<I',struct.pack('<f',rng.uniform(-2,2)))[0]
    bits=((word+0x7fff+((word>>16)&1))>>16)&0xffff
   inputs.append(bits)
 logits,ids=run_router(lib,weights,inputs)
 for row,expected in zip(chunks(logits,512),chunks(ids,16)):
  x=array('H',row);out=array('I',[0])*10
  assert lib.p138_production_rank10(x.buffer_info()[0],out.buffer_info()[0])==0
  assert list(out)==expected[:10]
 # Ties, exponent underflow and adjacent BF16 logits. No tolerance.
 for variant in range(4):
  x=array('H',([0]*512 if variant==0 else [0x3f80+(j%3) for j in range(512)] if variant==1 else
                [0x42c8 if j<3 else 0xc2c8 for j in range(512)] if variant==2 else [0x8000 if j%2 else 0 for j in range(512)]))
  wide=array('I',[0])*16;prod=array('I',[0])*10
  assert lib.p138_rank(x.buffer_info()[0],wide.buffer_info()[0])==0
  assert lib.p138_production_rank10(x.buffer_info()[0],prod.buffer_info()[0])==0
  assert list(wide[:10])==list(prod)
  if variant in (0,3):assert list(wide)==list(range(16))
 bad=array('H',[0])*512;bad[7]=0x7fc0;out=array('I',[0])*16
 assert lib.p138_rank(bad.buffer_info()[0],out.buffer_info()[0])!=0
 print(json.dumps(dict(passed=True,device_executed=False,synthetic_inputs=True,real_router_weight=w.receipts[0],
  logits_sha256=hashlib.sha256(logits.tobytes()).hexdigest(),routes_sha256=hashlib.sha256(ids.tobytes()).hexdigest(),
  top10_matches_production=True,nonfinite_refused=True,max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)))

def main():
 from build_engine import limits
 limits();runs=[]
 for compiler in ('gnu','intel'):
  for repeat in (1,2):
   env=dict(os.environ,LD_LIBRARY_PATH='/opt/intel/oneapi/compiler/2026.0/lib',OMP_NUM_THREADS='4')
   cp=subprocess.run([sys.executable,'-B',__file__,'--probe',compiler],stdin=subprocess.DEVNULL,capture_output=True,text=True,env=env,timeout=120)
   (P/'evidence'/f'replay-{compiler}-{repeat}.log').write_text(cp.stdout+cp.stderr)
   assert cp.returncode==0,cp.stderr
   row=json.loads(cp.stdout);assert row['max_rss_kib']<4*1024**2
   row.update(compiler=compiler,repeat=repeat);runs.append(row)
 assert len({(r['logits_sha256'],r['routes_sha256']) for r in runs})==1
 weights=Weights()
 for layer in range(48):weights.router(layer)
 save(P/'evidence/router-weights.json',dict(passed=True,device_executed=False,headers=weights.header_receipts,routers=weights.receipts,expert_sizes=weights.sizes(),payload_bytes_read=sum(r['bytes'] for r in weights.receipts)))
 save(P/'evidence/replay-cpu.json',dict(passed=True,device_executed=False,real_capture_tested=False,runs=runs))
 print('GNU/Intel fresh repeats, probability ties, nonfinite rejection and GGUF directories PASS')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));os.environ['OMP_NUM_THREADS']='4'
 p=argparse.ArgumentParser();p.add_argument('--probe',choices=('gnu','intel'));a=p.parse_args()
 probe(a.probe) if a.probe else main()

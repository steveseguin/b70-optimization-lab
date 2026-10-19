"""Synthetic real-shape M=2 arithmetic gate; no model, device or startup reads."""
import hashlib,json,os,resource,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent
sys.path.insert(0,str(P/'v5'))
from p151_v5_build_engine import compiler_turn,limits,save,sha,CHECKED
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2)
def main():
 out=P/'build/pair-cpu';out.mkdir(parents=True,exist_ok=True);rows=[]
 for name,cc in [('gnu','/usr/bin/g++'),('intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  limits();binary=out/name;cmd=[cc,'-std=c++20','-O2','-march=native','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(CHECKED),str(P/'batch_fixture.cpp'),'-o',str(binary)]
  with compiler_turn(),(out/(name+'-compile.log')).open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
  for repeat in (1,2):
   prefix=out/(name+str(repeat));start=time.monotonic()
   r=subprocess.run([str(binary),str(prefix)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600,check=True)
   a=Path(str(prefix)+'-expected.bin');b=Path(str(prefix)+'-actual.bin');assert a.read_bytes()==b.read_bytes()
   rows.append(dict(compiler=name,repeat=repeat,result=json.loads(r.stdout),sha256=sha(b),seconds=time.monotonic()-start));a.unlink();b.unlink()
   print(name,repeat,'PASS',flush=True)
 assert len({r['sha256'] for r in rows})==1
 save(P/'v5/evidence/pair-cpu.json',dict(passed=True,device_executed=False,model_read=False,runs=rows,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
if __name__=='__main__':main()

"""Two fresh GNU/Intel byte runs; real matrix dimensions, synthetic finite bytes."""
import gzip,json,resource,subprocess
from build_engine import P,LOCAL,ROOT,B,CHECKED,sha,save,limits,compiler_turn

def main():
 limits();out=B/'bytes';out.mkdir(exist_ok=True);rows=[];binaries={}
 for label,cc in (('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')):
  binary=out/label
  source=out/'layout_bytes.cpp';source.write_bytes((LOCAL/'layout_bytes.cpp').read_bytes())
  cmd=[cc,'-std=c++20','-O2','-march=native','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-I'+str(CHECKED),str(source),'-o',str(binary)]
  with compiler_turn(),(out/(label+'-compile.log')).open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
  binaries[str(binary.relative_to(ROOT))]=sha(binary)
  for repeat in (1,2):
   raw=out/(label+str(repeat)+'.bin');r=subprocess.run([str(binary),str(raw)],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=300)
   result=json.loads(r.stdout);assert result['passed'];digest=sha(raw);compressed=P/'evidence'/(label+str(repeat)+'-bytes.bin.gz');data=raw.read_bytes();compressed.write_bytes(gzip.compress(data,mtime=0));assert gzip.decompress(compressed.read_bytes())==data;raw.unlink()
   rows.append(dict(compiler=label,repeat=repeat,sha256=digest,artifact=str(compressed.relative_to(ROOT)),artifact_sha256=sha(compressed),result=result));print(label,repeat,'PASS',flush=True)
 assert len({r['sha256'] for r in rows})==1
 save(P/'evidence/bytes.json',dict(passed=True,device_executed=False,runs=rows,binaries=binaries,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,sources={str(f.relative_to(ROOT)):sha(f) for f in (LOCAL/'layout_bytes.cpp',P/'byte_gate.py')}));limits()
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()

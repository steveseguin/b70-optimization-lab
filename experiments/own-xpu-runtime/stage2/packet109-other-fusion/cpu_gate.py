"""One compiler at a time; actual production bodies, no tolerance for NaNs."""
import subprocess,json,gzip,shlex
from build_engine import P,ROOT,B,sha,save,limits,compiler_turn,CHECKED
def main():
 limits();out=B/'cpu';out.mkdir(exist_ok=True);runs=[];sources={};commands=[]
 for label,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=out/label;dep=out/(label+'.d')
  flags=['-O3','-march=native'] if label=='GNU' else ['-O2','-fdenormal-fp-math=ieee']
  base=[cxx,'-std=c++20',*flags,'-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-ffunction-sections','-fdata-sections','-I'+str(CHECKED),'-I'+str(P)]
  ref=out/(label+'-production.o');refdep=out/(label+'-production.d')
  reference=[*base,'-MMD','-MF',str(refdep),'-c',str(P/'production_cpu.cpp'),'-o',str(ref)]
  with compiler_turn(),(out/(label+'-production.log')).open('w') as log:subprocess.run(reference,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
  commands.append(reference)
  for n in shlex.split(refdep.read_text().replace('\\\n',' ').split(':',1)[1]):sources[str(__import__('pathlib').Path(n).resolve().relative_to(ROOT))]=sha(n)
  cmd=[*base,'-Wl,--gc-sections','-MMD','-MF',str(dep),str(P/'fusion_cpu.cpp'),str(ref),'-o',str(binary),'-lcrypto']
  commands.append(cmd)
  with compiler_turn(),(out/(label+'-compile.log')).open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
  for n in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):sources[str(__import__('pathlib').Path(n).resolve().relative_to(ROOT))]=sha(n)
  for repeat in (0,1):
   dest=out/(label+'-'+str(repeat));dest.mkdir(exist_ok=True)
   with (dest/'run.log').open('w') as log:subprocess.run([str(binary),str(dest)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
   a,b=dest/'expected.bin',dest/'actual.bin';assert a.read_bytes()==b.read_bytes()
   native=json.loads((dest/'run.log').read_text());assert native['passed']
   retained=P/'evidence'/('bytes-'+label+'-'+str(repeat)+'.bin.gz');retained.write_bytes(gzip.compress(b.read_bytes(),mtime=0));assert gzip.decompress(retained.read_bytes())==b.read_bytes()
   runs.append(dict(compiler=label,repeat=repeat,expected_sha256=sha(a),actual_sha256=sha(b),artifact=str(retained.relative_to(ROOT)),artifact_sha256=sha(retained),**native))
  print(label,'two fresh exact-byte runs PASS',flush=True)
 for f in (P/'cpu_gate.py',P/'fusion_cpu.cpp'):sources[str(f.relative_to(ROOT))]=sha(f)
 save(P/'evidence/cpu-byte-identity.json',dict(passed=True,device_executed=False,runs=runs,sources=sources,commands=commands,cross_compiler='Per-compiler byte equality to actual production operations; no NaN canonicalization or tolerance.'))
if __name__=='__main__':main()

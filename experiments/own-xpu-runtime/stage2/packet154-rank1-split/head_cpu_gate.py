"""Execute actual p33/round2/pack kernels in fresh GNU and Intel host processes."""
import gzip,json,shlex,shutil,subprocess,resource
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
from compile_turn import turn
def main():
 limits();dest=B/'cpu';dest.mkdir(exist_ok=True);sources={};runs=[];commands=[]
 for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=dest/('head-'+compiler);dep=binary.with_suffix('.d')
  cmd=[cxx,'-std=c++20',*(['-O3','-march=native'] if compiler=='GNU' else ['-O2','-fdenormal-fp-math=ieee']),'-fno-fast-math','-ffp-contract=off','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),'-MMD','-MF',str(dep),str(P/'p105_cpu.cpp'),'-o',str(binary),'-lcrypto']
  with turn(),(dest/('head-'+compiler+'.log')).open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
  commands.append(cmd)
  for n in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):sources[str(Path(n).resolve().relative_to(ROOT))]=sha(n)
  for repeat in (1,2):
   scratch=dest/'scratch';scratch.mkdir();cmd=[str(binary),str(scratch)]
   try:
    r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
    expected=(scratch/'expected.bin').read_bytes();actual=(scratch/'candidate.bin').read_bytes();assert expected==actual
    digest=__import__('hashlib').sha256(actual).hexdigest();f=P/'evidence'/('head-'+digest+'.bin.gz');f.write_bytes(gzip.compress(actual,mtime=0))
    runs.append(dict(compiler=compiler,repeat=repeat,command=cmd,binary_sha256=sha(binary),expected_sha256=digest,candidate_sha256=digest,fixture=str(f.relative_to(ROOT)),fixture_sha256=sha(f),native=json.loads((scratch/'native.json').read_text())))
   finally:shutil.rmtree(scratch)
  print(compiler,'full vocabulary, two fresh repeats PASS',flush=True)
 assert len({r['candidate_sha256'] for r in runs})==1
 for n in ('cpu_gate.py','compile_turn.py'):sources[str((P/n).relative_to(ROOT))]=sha(P/n)
 save(P/'evidence/head-byte-identity.json',dict(passed=True,device_executed=False,runs=runs,sources=sources,commands=commands,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
if __name__=='__main__':main()

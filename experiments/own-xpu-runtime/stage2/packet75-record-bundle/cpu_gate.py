"""Serial GNU/Intel exact-byte gates for both disjoint composed operator sets."""
import json,os,resource,shlex,subprocess
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
from bundle_selection import views,choices

def main():
 limits();result=dict(passed=False,device_executed=False,runs=[],sources={})
 for name,compiler in [('gnu','/usr/bin/g++'),('intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  for packet,count in ((73,44),(74,60)):
   out=B/f'cpu-p{packet}-{name}';out.mkdir(parents=True,exist_ok=True)
   cmd=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),'-MMD','-MF',str(out/'deps.d'),str(P/f'p{packet}_cpu.cpp'),'-o',str(out/'fixture')]
   with (out/'compile.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,check=True,timeout=300)
   for n in shlex.split((out/'deps.d').read_text().replace('\\\n',' ').split(':',1)[1]):result['sources'][str(Path(n).resolve().relative_to(ROOT))]=sha(n)
   for repeat in (1,2):
    dest=out/f'repeat-{repeat}';dest.mkdir(exist_ok=True)
    with (dest/'run.log').open('w') as f:subprocess.run([str(out/'fixture'),str(dest)],stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,check=True,timeout=300)
    native=json.loads((dest/'native.json').read_text());a=sha(dest/'expected.bin');b=sha(dest/'candidate.bin')
    assert native['passed'] and native['cases']==count and a==b
    result['runs'].append(dict(compiler=name,packet=packet,command=cmd,repeat=repeat,native=native,expected_sha256=a,candidate_sha256=b,path=str(dest.relative_to(ROOT))))
    print(name,packet,repeat,'PASS',flush=True)
 for packet in (73,74):assert len({r['candidate_sha256'] for r in result['runs'] if r['packet']==packet})==1
 out=B/'composed-fixture';out.mkdir(exist_ok=True)
 for kind in ('expected','candidate'):
  (out/(kind+'.bin')).write_bytes(b''.join((B/f'cpu-p{packet}-gnu/repeat-1'/f'{kind}.bin').read_bytes() for packet in (73,74)))
 result['views']={n:dict(choices=choices(*v),passed=True,scope='Disjoint packed dense and HC/expert kernels; all alternatives exact in both compiler fixtures. Full-shape initialization separately mandatory.') for n,v in views().items()}
 result['sources'][str((P/'cpu_gate.py').relative_to(ROOT))]=sha(P/'cpu_gate.py');result['sources'][str((P/'bundle_selection.py').relative_to(ROOT))]=sha(P/'bundle_selection.py')
 result.update(passed=True,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
 save(P/'evidence/cpu-byte-identity.json',result)
if __name__=='__main__':main()

"""Two fresh processes per compiler; closed GDN failure stays explicit."""
import subprocess
from build_engine import P,ROOT,B,limits,save,sha
from compile_turn import turn
def main():
 limits();records=[]
 for name,compiler in [('gnu','/usr/bin/g++'),('intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  for leaf in ['gdn']:
   binary=B/(name+'-leaf-'+leaf)
   cmd=[compiler,'-std=c++20','-O2','-DOWN_RT_HOST_ONLY','-fno-fast-math','-ffp-contract=off','-I'+str(P),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),str(P/('leaf_'+leaf+'.cpp')),'-lcrypto','-o',str(binary)]
   with turn(),(B/(name+'-leaf-'+leaf+'-compile.log')).open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,check=True,timeout=600)
   hashes=[];codes=[]
   for repeat in (1,2):
    out=P/'evidence'/f'leaf-v2-{name}-{leaf}-{repeat}';out.mkdir(exist_ok=False)
    args=[str(binary),'candidate',str(out)] if leaf=='gdn' else [str(binary),str(out/'candidate.bin')]
    with (out/'run.log').open('w') as log:r=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=300)
    codes.append(r.returncode);hashes.append(sha(out/'candidate.txt'))
   passed=codes==[0,0] and hashes[0]==hashes[1]
   records.append(dict(compiler=name,leaf=leaf,passed=passed,exit_codes=codes,command=cmd,binary_sha256=sha(binary),repeat_sha256=hashes))
   print(name,leaf,'PASS' if passed else 'CLOSED: byte gate failure',flush=True)
 save(P/'evidence/cpu-leaf.json',dict(passed=all(r['passed'] for r in records),device_executed=False,records=records))
 assert all(r['passed'] for r in records),'GDN byte gate failed'
if __name__=='__main__':main()

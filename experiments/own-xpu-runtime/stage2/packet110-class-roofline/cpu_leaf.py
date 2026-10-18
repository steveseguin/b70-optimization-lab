"""Two fresh processes per compiler; closed GDN failure stays explicit."""
import subprocess
from build_engine import P,ROOT,B,limits,save,sha
from compile_turn import turn
def main():
 limits();records=[]
 from qsa_trace import generate
 generate()
 for name,compiler in [('gnu','/usr/bin/g++'),('intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  for leaf in ['gdn','qsa']:
   binary=B/(name+'-leaf-'+leaf)
   cmd=[compiler,'-std=c++20','-O2','-DOWN_RT_HOST_ONLY','-fno-fast-math','-ffp-contract=off','-I'+str(P),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),str(P/('leaf_'+leaf+'.cpp')),'-lcrypto','-o',str(binary)]
   with turn(),(B/(name+'-leaf-'+leaf+'-compile.log')).open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,check=True,timeout=600)
   hashes=[];codes=[]
   for repeat in (1,2):
    out=P/'evidence'/f'leaf-{name}-{leaf}-{repeat}';out.mkdir(exist_ok=True)
    args=[str(binary),'candidate',str(out)] if leaf=='gdn' else [str(binary),str(out/'candidate.bin')]
    with (out/'run.log').open('w') as log:r=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=300)
    codes.append(r.returncode);hashes.append(sha(out/'candidate.bin'))
   passed=codes==[0,0] and hashes[0]==hashes[1]
   records.append(dict(compiler=name,leaf=leaf,passed=passed,exit_codes=codes,command=cmd,binary_sha256=sha(binary),repeat_sha256=hashes))
   print(name,leaf,'PASS' if passed else 'CLOSED: byte gate failure',flush=True)
 qsa=[r for r in records if r['leaf']=='qsa']
 finite=[]
 for name in ('gnu','intel'):
  lines=(P/'evidence'/f'leaf-{name}-qsa-1/candidate.bin').read_text().splitlines()
  finite.append([line for line in lines if int(line.split()[1])<=2])
 qsa_passed=all(r['passed'] for r in qsa) and finite[0]==finite[1]
 save(P/'evidence/cpu-leaf.json',dict(passed=all(r['passed'] for r in records),qsa_passed=qsa_passed,qsa_finite_cross_compiler_equal=finite[0]==finite[1],qsa_all_cross_compiler_equal=len({r['repeat_sha256'][0] for r in qsa})==1,exceptional_contract='candidate matches its own unchanged compiler production; production NaN payloads differ between GNU and Intel',gdn_passed=all(r['passed'] for r in records if r['leaf']=='gdn'),device_executed=False,records=records))
 assert qsa_passed,'QSA cannot be queued'
if __name__=='__main__':main()

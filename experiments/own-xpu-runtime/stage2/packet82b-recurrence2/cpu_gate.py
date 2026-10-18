"""Exact selected operator bytes, two fresh executions with each compiler."""
import os,array,json,resource,shlex,subprocess
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
from bundle_selection import views,choices
def main():
 limits();dest=B/'cpu';dest.mkdir(exist_ok=True)
 report=dict(passed=False,device_executed=False,views={},sources={},commands=[])
 for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=dest/('fixture-'+compiler);deps=dest/(compiler+'.d')
  cmd=[cxx,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),'-MMD','-MF',str(deps),str(P/'p82_cpu.cpp'),'-o',str(binary),'-lcrypto']
  with (dest/(compiler+'-compile.log')).open('w') as f:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
  report['commands'].append(cmd)
  for n in shlex.split(deps.read_text().replace('\\\n',' ').split(':',1)[1]):report['sources'][str(Path(n).resolve().relative_to(ROOT))]=sha(n)
  for name in views():
   row=report['views'].setdefault(name,dict(choices=choices(name),runs=[]))
   for repeat in (1,2):
    out=dest/name/compiler/str(repeat);out.mkdir(parents=True,exist_ok=True);command=[str(binary),name,str(out)]
    r=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=300,env={**os.environ,**({'P82_EXCEPTION_DUMP':'1'} if name=='production' and repeat==1 else {})})
    (out/'run.log').write_text(r.stdout+r.stderr);r.check_returncode();native=json.loads((out/'native.json').read_text())
    assert sha(out/'expected.bin')==sha(out/'candidate.bin')
    row['runs'].append(dict(compiler=compiler,repeat=repeat,command=command,path=str(out.relative_to(ROOT)),expected_sha256=sha(out/'expected.bin'),candidate_sha256=sha(out/'candidate.bin'),**native))
   print(compiler,name,'two repeats PASS',flush=True)
 baseline=report['views']['production']['runs']
 reference={c:next(r for r in baseline if r['compiler']==c and r['repeat']==1) for c in ('GNU','Intel')}
 g=ROOT/reference['GNU']['path'];i=ROOT/reference['Intel']['path']
 transcripts={c:(ROOT/reference[c]['path']/'expected.bin').read_text().splitlines() for c in reference}
 cases=[json.loads(x) for x in (g/'cases.jsonl').read_text().splitlines()]
 exceptional=[]
 for index,(x,y) in enumerate(zip(transcripts['GNU'],transcripts['Intel'])):
  if x==y:continue
  desc=cases[index]['case'];assert '-s6-' in desc
  aa=(g/(desc+'.raw')).read_bytes();bb=(i/(desc+'.raw')).read_bytes();assert len(aa)==len(bb) and aa[-12:]==bb[-12:]
  av=array.array('H');bv=array.array('H');av.frombytes(aa[:-12]);bv.frombytes(bb[:-12]);n=0
  for u,v in zip(av,bv):
   if u!=v:
    assert (u&0x7f80)==0x7f80 and (u&127) and (v&0x7f80)==0x7f80 and (v&127),'finite cross-compiler difference'
    n+=1
  exceptional.append(dict(case=desc,different_nan_elements=n,GNU_sha256=sha(g/(desc+'.raw')),Intel_sha256=sha(i/(desc+'.raw'))))
 assert len(exceptional)==20
 for row in report['views'].values():
  assert len(row['runs'])==4
  for c in reference:
   runs=[r for r in row['runs'] if r['compiler']==c]
   assert len({r['candidate_sha256'] for r in runs})==1
   assert all(r['candidate_sha256']==reference[c]['candidate_sha256'] for r in runs)
  row['passed']=True
 report['cross_compiler']=dict(finite_and_infinity_cases_exact=True,production_nan_payload_differences=exceptional,policy='Every candidate byte equals same-compiler production; no NaN tolerance in that comparison. Only production-vs-production cross-compiler payload differences are separately recorded.')
 report['sources'][str((P/'cpu_gate.py').relative_to(ROOT))]=sha(P/'cpu_gate.py')
 report.update(passed=True,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
 save(P/'evidence/cpu-byte-identity.json',report)
if __name__=='__main__':main()

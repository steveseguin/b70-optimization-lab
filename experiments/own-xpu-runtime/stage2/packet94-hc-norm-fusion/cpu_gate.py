"""Exact selected operator bytes, two fresh executions with each compiler."""
import gzip,hashlib,shutil
import json,resource,shlex,subprocess
from compile_turn import turn
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
from bundle_selection import views,choices
def main():
 limits();dest=B/'cpu';dest.mkdir(exist_ok=True)
 report=dict(passed=False,device_executed=False,views={},sources={},commands=[])
 for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=dest/('fixture-'+compiler);deps=dest/(compiler+'.d')
  cmd=[cxx,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),'-MMD','-MF',str(deps),str(P/'p94_cpu.cpp'),'-o',str(binary)]
  with turn(), (dest/(compiler+'-compile.log')).open('w') as f:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
  report['commands'].append(cmd)
  for n in shlex.split(deps.read_text().replace('\\\n',' ').split(':',1)[1]):report['sources'][str(Path(n).resolve().relative_to(ROOT))]=sha(n)
  for name in views():
   row=report['views'].setdefault(name,dict(choices=choices(name),runs=[]))
   for repeat in (1,2):
    out=dest/name/compiler/str(repeat);out.mkdir(parents=True,exist_ok=True);command=[str(binary),name,str(out)]
    r=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=300)
    (out/'run.log').write_text(r.stdout+r.stderr);r.check_returncode();native=json.loads((out/'native.json').read_text())
    assert sha(out/'expected.bin')==sha(out/'candidate.bin')
    digest=sha(out/'expected.bin');retained=P/'evidence/cpu-bytes'/(digest+'.bin.gz');retained.parent.mkdir(exist_ok=True)
    if not retained.exists():retained.write_bytes(gzip.compress((out/'expected.bin').read_bytes(),mtime=0))
    assert hashlib.sha256(gzip.decompress(retained.read_bytes())).hexdigest()==digest
    cases=P/'evidence/cpu-bytes'/(compiler+'-'+name+'-'+str(repeat)+'-cases.jsonl');cases.write_bytes((out/'cases.jsonl').read_bytes())
    row['runs'].append(dict(compiler=compiler,repeat=repeat,command=command,path=str(out.relative_to(ROOT)),expected_sha256=digest,candidate_sha256=sha(out/'candidate.bin'),raw_evidence=str(retained.relative_to(ROOT)),raw_evidence_sha256=sha(retained),cases_path=str(cases.relative_to(ROOT)),cases_sha256=sha(cases),**native))
   print(compiler,name,'two repeats PASS',flush=True)
 for row in report['views'].values():
  assert len(row['runs'])==4
  for compiler in ('GNU','Intel'):
   assert len({r['candidate_sha256'] for r in row['runs'] if r['compiler']==compiler})==1
  # Existing compiler-specific NaN payload choices are not candidate tolerances.
  # Every candidate remains byte-identical to its actual compiled production.
  raw=[gzip.decompress((ROOT/next(r for r in row['runs'] if r['compiler']==c)['raw_evidence']).read_bytes()) for c in ('GNU','Intel')]
  bf16_bytes=(10240+320+320+10240+2560+4)*2
  stride=bf16_bytes+(320+32)*4+12
  assert len(raw[0])==len(raw[1])==96*stride
  differences=[]
  for case in range(96):
   counts={'bf16_nan_payloads':0,'fp32_nan_payloads':0}
   for offset in range(0,bf16_bytes,2):
    at=case*stride+offset;a=int.from_bytes(raw[0][at:at+2],'little');b=int.from_bytes(raw[1][at:at+2],'little')
    if a!=b:
     assert (a&0x7f80)==0x7f80 and a&127 and (b&0x7f80)==0x7f80 and b&127,(case,offset,a,b)
     counts['bf16_nan_payloads']+=1
   for offset in range(bf16_bytes,stride-12,4):
    at=case*stride+offset;a=int.from_bytes(raw[0][at:at+4],'little');b=int.from_bytes(raw[1][at:at+4],'little')
    if a!=b:
     assert (a&0x7f800000)==0x7f800000 and a&0x7fffff and (b&0x7f800000)==0x7f800000 and b&0x7fffff,(case,offset,a,b)
     counts['fp32_nan_payloads']+=1
   assert raw[0][(case+1)*stride-12:(case+1)*stride]==raw[1][(case+1)*stride-12:(case+1)*stride]
   if any(counts.values()):differences.append(dict(case=case,scenario=case//8,token=(case%8)//2,side=case%2,**counts))
  row['cross_compiler_production_nan_differences']=differences
  row['passed']=True
 report['sources'][str((P/'cpu_gate.py').relative_to(ROOT))]=sha(P/'cpu_gate.py')
 report['sources'][str((P/'compile_turn.py').relative_to(ROOT))]=sha(P/'compile_turn.py')
 report.update(passed=True,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
 save(P/'evidence/cpu-byte-identity.json',report)
 for name in views():shutil.rmtree(dest/name) # only this run's verified, archived scratch
if __name__=='__main__':main()

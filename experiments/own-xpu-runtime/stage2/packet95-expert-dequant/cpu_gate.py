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
  cmd=[cxx,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),'-MMD','-MF',str(deps),str(P/'p95_cpu.cpp'),'-o',str(binary)]
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
    shutil.rmtree(out)
   print(compiler,name,'two repeats PASS',flush=True)
 for row in report['views'].values():
  assert len(row['runs'])==4 and len({r['candidate_sha256'] for r in row['runs']})==1
  row['passed']=True
 report['sources'][str((P/'cpu_gate.py').relative_to(ROOT))]=sha(P/'cpu_gate.py')
 report['sources'][str((P/'compile_turn.py').relative_to(ROOT))]=sha(P/'compile_turn.py')
 report.update(passed=True,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
 save(P/'evidence/cpu-byte-identity.json',report)
 for name in views():shutil.rmtree(dest/name) # only this run's verified, archived scratch
if __name__=='__main__':main()

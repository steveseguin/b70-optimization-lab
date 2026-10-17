"""Exact selected operator bytes, two fresh executions with each compiler."""
import json,resource,shlex,subprocess,gzip
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
from bundle_selection import views,choices
def main():
 limits();dest=B/'cpu';dest.mkdir(exist_ok=True)
 report=dict(passed=False,device_executed=False,views={},sources={},commands=[])
 for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=dest/('fixture-'+compiler);deps=dest/(compiler+'.d')
  cmd=[cxx,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),'-MMD','-MF',str(deps),str(P/'p78_cpu.cpp'),'-o',str(binary)]
  with (dest/(compiler+'-compile.log')).open('w') as f:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
  report['commands'].append(cmd)
  for n in shlex.split(deps.read_text().replace('\\\n',' ').split(':',1)[1]):report['sources'][str(Path(n).resolve().relative_to(ROOT))]=sha(n)
  for name,v in views().items():
   row=report['views'].setdefault(name,dict(choices=choices(*v),runs=[]))
   for repeat in (1,2):
    out=dest/name/compiler/str(repeat);out.mkdir(parents=True,exist_ok=True);command=[str(binary),v[4],v[5],v[1],str(out)]
    r=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=300)
    (out/'run.log').write_text(r.stdout+r.stderr);r.check_returncode();native=json.loads(r.stdout)
    assert sha(out/'expected.bin')==sha(out/'candidate.bin')
    row['runs'].append(dict(compiler=compiler,repeat=repeat,command=command,path=str(out.relative_to(ROOT)),expected_sha256=sha(out/'expected.bin'),candidate_sha256=sha(out/'candidate.bin'),**native))
    for leaf in ('expected.bin','candidate.bin'):
     f=out/leaf;raw=f.read_bytes();gz=f.with_suffix(f.suffix+'.gz');gz.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(gz.read_bytes())==raw;f.unlink()
   print(compiler,name,'two repeats PASS',flush=True)
 for row in report['views'].values():
  assert len(row['runs'])==4 and len({r['candidate_sha256'] for r in row['runs']})==1
  row['passed']=True
 report['sources'][str((P/'cpu_gate.py').relative_to(ROOT))]=sha(P/'cpu_gate.py')
 report.update(passed=True,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
 save(P/'evidence/cpu-byte-identity.json',report)
if __name__=='__main__':main()

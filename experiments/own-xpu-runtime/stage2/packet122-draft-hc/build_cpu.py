"""Host-only two-compiler exact-byte checks, in two fresh processes each."""
import json,resource,subprocess,gzip,hashlib,shutil
from pathlib import Path
from build_engine import limits,sha
from compile_turn import turn
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def main():
 limits()
 from math_gate import SOURCES,closure
 from kernel_gate import mirror
 SOURCES.append('cpu.cpp');mapping=mirror();dest=P/'build/cpu';dest.mkdir(exist_ok=True);e=P/'evidence/cpu-bytes';e.mkdir(exist_ok=True)
 row=dict(schema='packet122.cpu-byte-identity.v1',passed=False,device_executed=False,views={'p122':{'runs':[]}},sources={},generated_sources={},compilers=[])
 for name,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=dest/('fixture-'+name);log=e/(name+'-compile.log')
  cmd=[cxx,'-std=c++20','-O3','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY',str(mapping[P/'cpu.cpp']),'-o',str(binary)]
  if name=='Intel':cmd+=['-fdenormal-fp-math=ieee']
  with turn(),log.open('w') as f:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=600)
  row['compilers'].append(dict(name=name,binary=str(binary.relative_to(ROOT)),binary_sha256=sha(binary),compile_log=str(log.relative_to(ROOT)),compile_log_sha256=sha(log),command=cmd))
  for repeat in (1,2):
   out=dest/(name+str(repeat));command=[str(binary),str(out)];r=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=120)
   raw=(out/'expected.bin').read_bytes();assert raw==(out/'candidate.bin').read_bytes();digest=hashlib.sha256(raw).hexdigest();retain=e/(digest+'.bin.gz');retain.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(retain.read_bytes())==raw
   casefile=e/(name+str(repeat)+'-cases.jsonl');casefile.write_bytes((out/'cases.jsonl').read_bytes());log=e/(name+str(repeat)+'.log');log.write_text(r.stdout+r.stderr)
   row['views']['p122']['runs'].append(dict(compiler=name,repeat=repeat,expected_sha256=digest,candidate_sha256=digest,raw_evidence=str(retain.relative_to(ROOT)),raw_evidence_sha256=sha(retain),cases_path=str(casefile.relative_to(ROOT)),cases_sha256=sha(casefile),log_path=str(log.relative_to(ROOT)),log_sha256=sha(log),**json.loads((out/'native.json').read_text())))
   shutil.rmtree(out)
  print(name,'two fresh byte checks PASS',flush=True)
 for original,generated in mapping.items():
  row['sources'][str(original.relative_to(ROOT))]=sha(original)
  row['generated_sources'][str(generated.relative_to(ROOT))]=dict(sha256=sha(generated),source=str(original.relative_to(ROOT)),source_sha256=sha(original))
 for n in ('build_cpu.py','build_engine.py','compile_turn.py'):row['sources'][str((P/n).relative_to(ROOT))]=sha(P/n)
 row['passed']=True;row['max_rss_kib']=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
 (P/'evidence/cpu-byte-identity.json').write_text(json.dumps(row,indent=2)+'\n')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()

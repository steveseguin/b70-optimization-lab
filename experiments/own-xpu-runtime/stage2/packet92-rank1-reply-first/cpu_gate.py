"""Dual-compiler state, mailbox and poisoned-deferred-work proof."""
import json,subprocess,shutil,shlex,gzip
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
from compile_turn import turn
def main():
 limits();dest=B/'cpu';dest.mkdir(exist_ok=True);rows=[];sources={}
 for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=dest/('fixture-'+compiler);dep=dest/(compiler+'.d')
  cmd=[cxx,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-MMD','-MF',str(dep),str(P/'reply_first_test.cpp'),'-o',str(binary)]
  with turn(), (dest/(compiler+'-compile.log')).open('w') as f:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
  for n in shlex.split(dep.read_text().replace(chr(92)+chr(10),' ').split(':',1)[1]):sources[str(Path(n).resolve().relative_to(ROOT))]=sha(n)
  for repeat in (1,2):
   out=dest/(compiler+'-'+str(repeat));out.mkdir(exist_ok=True)
   run=[str(binary),str(out)];subprocess.run(run,stdin=subprocess.DEVNULL,check=True,timeout=30)
   assert sha(out/'expected.bin')==sha(out/'candidate.bin')
   digest=sha(out/'expected.bin');retained=P/'evidence'/(digest+'.bin.gz');retained.write_bytes(gzip.compress((out/'expected.bin').read_bytes(),mtime=0))
   rows.append(dict(compiler=compiler,repeat=repeat,command=run,compile_command=cmd,binary_sha256=sha(binary),expected_sha256=digest,candidate_sha256=digest,raw_evidence=str(retained.relative_to(ROOT)),raw_evidence_sha256=sha(retained),**json.loads((out/'result.json').read_text())))
   shutil.rmtree(out)
  print(compiler,'two state/error repeats PASS',flush=True)
 assert len({r['expected_sha256'] for r in rows})==1
 for f in (P/'cpu_gate.py',P/'compile_turn.py'):sources[str(f.relative_to(ROOT))]=sha(f)
 save(P/'evidence/cpu-byte-identity.json',dict(passed=True,device_executed=False,sources=sources,runs=rows))
if __name__=='__main__':main()

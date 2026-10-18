"""Compile the diagnostic device program; never load or execute it here."""
import json, os, shlex, subprocess, resource
from pathlib import Path
from build_engine import P, ROOT, B, limits, sha, save
from compile_turn import turn
def main():
 limits();os.environ['TMPDIR']=str(B/'tmp')
 runtime=(P/'p105_runtime.hpp').read_text()
 start=runtime.index('  uint32_t zero=0,one=1;',runtime.index('template<class Cancel> void service'))
 end=runtime.index('  for(const auto& command:suffix_commands)',start)
 fragment=B/'micro_service.inc';fragment.write_text(runtime[start:end])
 source=(P/'split_micro.cpp').read_text()
 for name in ('p33_submit.cpp','round2_submit.cpp','p105_submit.cpp'):
  path=B/'checked'/P.relative_to(ROOT)/name
  assert path.is_file();source=source.replace('"'+name+'"',json.dumps(str(path)))
 entry=B/'split-micro.cpp';entry.write_text(source)
 commands=json.loads((P/'engine-commands.json').read_text())
 args=next(r['command'] for r in commands if r['name']=='device-entry-main')
 args=args[:args.index('-o')]
 args=[v for v in args if v not in ('-c',)]
 cmd=[*args,'-I'+str(B),'-ffunction-sections','-fdata-sections','-Wl,--gc-sections',
      '-MMD','-MF',str(B/'split-micro.d'),str(entry),'-o',str(B/'microbench')]
 with turn(),(B/'microbench-build.log').open('w') as log:
  subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
 deps=shlex.split((B/'split-micro.d').read_text().replace('\\\n',' ').split(':',1)[1])
 sources={str(Path(n).resolve().relative_to(ROOT)):sha(n) for n in deps if Path(n).is_file() and Path(n).resolve().is_relative_to(ROOT)}
 from math_gate import closure
 for path in [*closure(),P/'split_micro.cpp',P/'build_microbench.py',P/'build_engine.py',P/'compile_turn.py',P/'run_micro.py',P/'bootstrap.py',P/'conditions.py',P/'drain_gate.py',P/'exec_limits.py',P/'device_gate.py',fragment,entry]:sources[str(path.relative_to(ROOT))]=sha(path)
 save(P/'evidence/microbench-build.json',dict(passed=True,device_executed=False,sources=sources,
      artifacts={'build/microbench':sha(B/'microbench')},command=cmd,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 print('Device split micro compiled; not executed',flush=True)
if __name__=='__main__':main()

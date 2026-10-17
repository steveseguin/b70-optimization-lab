"""Compile only. Does not enumerate or run any device."""
from pathlib import Path
import json,subprocess,resource,os,shlex
from build_engine import P,ROOT,B,limits,sha,save
limits()
cmd=next(r['command'] for r in json.loads((P/'engine-commands.json').read_text()) if r['name']=='device-entry-main');cmd=cmd[:cmd.index('-o')]
cmd += ['-MMD','-MF',str(B/'microbench.d'),str(P/'microbench.cpp'),'-o',str(B/'microbench')]
with (B/'microbench-build.log').open('w') as f:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=600)
sources={str(Path(n).resolve().relative_to(ROOT)):sha(n) for n in shlex.split((B/'microbench.d').read_text().replace('\\\n',' ').split(':',1)[1]) if Path(n).is_file() and Path(n).resolve().is_relative_to(ROOT)}
sources[str((P/'build_microbench.py').relative_to(ROOT))]=sha(P/'build_microbench.py')
save(P/'evidence/microbench-build.json',dict(passed=True,device_executed=False,command=cmd,sources=sources,binary_sha256=sha(B/'microbench'),max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
print('microbench compile PASS; no device run')

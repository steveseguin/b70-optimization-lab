"""CPU-only compile of the complete draft probe, reusing frozen bundle objects."""
import json,os,resource,subprocess,shutil
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];BASE=P.parent/'packet118-record-bundle';B=P/'build'
def sha(p):
 import hashlib
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 from build_engine import limits
 from compile_turn import turn
 limits();assert shutil.disk_usage('/').free>=25_000_000_000
 from math_gate import SOURCES,closure,check
 from kernel_gate import mirror
 SOURCES.append('draft_bench.cpp');check();mapping=mirror()
 (B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 commands=json.loads((BASE/'engine-commands.json').read_text());cmd=next(r['command'] for r in commands if r['name']=='device-entry-main');cmd=cmd[:cmd.index('-o')];cmd=[x.replace(str(BASE),str(P)) if x.startswith('-I') else x for x in cmd]
 cmd += ['-o',str(B/'draft_bench.o'),'-c',str(mapping[P/'draft_bench.cpp'])]
 link=list(next(r['command'] for r in commands if r['name']=='device-link'))
 objects={str(Path(x).relative_to(ROOT)):sha(x) for x in link if x.endswith('.o')}
 link=[x for x in link if not(x.endswith('.o') and any(n in x for n in ('own-rt-iq3-entry','entry-nongemv_fixture','entry-k2_fixture')))]
 assert str(BASE/'build/device/entry-main.o') in link
 link=[str(B/'draft_bench.o') if x==str(BASE/'build/device/entry-main.o') else x for x in link];link[link.index('-o')+1]=str(B/'microbench')
 for name,command in [('budget-compile',cmd),('budget-link',link)]:
  with turn(),(P/'evidence'/(name+'.log')).open('w') as f:subprocess.run(command,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1200)
  print(name,'PASS',flush=True)
 sources={str(f.relative_to(ROOT)):sha(f) for f in closure()}
 sources.update({str(f.relative_to(ROOT)):sha(f) for f in mapping.values()})
 sources.update(objects)
 for f in [*P.glob('inputs/*'),*[P/n for n in ('run_micro.py','drain_gate.py','exec_limits.py','selection.json','dispatch-speed6.json','mtp-manifest.tsv','rope.bf16','shared-wrapper-pin.json','build_budget.py')]]:sources[str(f.relative_to(ROOT))]=sha(f)
 size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file() and not f.is_symlink());assert size<=250_000_000
 (P/'evidence/microbench-build.json').write_text(json.dumps(dict(passed=True,device_executed=False,sources=sources,artifacts={'build/microbench':sha(B/'microbench')},commands=[cmd,link],build_bytes=size,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss),indent=2)+'\n')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()

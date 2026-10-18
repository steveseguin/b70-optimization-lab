"""Shared admission, both directions and exact unchanged arithmetic sources."""
import subprocess,sys,json,difflib
from build_engine import P,ROOT,sha,save,limits
from screen_jobs import WRAPPER

def main():
 limits();tests=['test_reporting','test_refusal','test_lane_admission','test_plan_admission','test_placement','test_chain_patch']
 commands=[([sys.executable,'-B','-m','unittest',*tests,'-v'],WRAPPER),([sys.executable,'-B','-m','unittest','test_screen','-v'],P)]
 for i,(cmd,cwd) in enumerate(commands):
  with (P/'evidence'/f'python-tests-{i}.log').open('w') as log:subprocess.run(cmd,cwd=cwd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
 parent=P.parent/'packet84-record-bundle';manifest=json.loads((P/'parent-source-manifest.json').read_text());changed=[];identical=[];patch=[]
 for name,h in manifest.items():
  f=ROOT/name
  if parent not in f.parents or f.suffix not in ('.cpp','.hpp','.inc'):continue
  local=P/f.relative_to(parent)
  if sha(local)==h:identical.append(str(local.relative_to(P)))
  else:
   changed.append(str(local.relative_to(P)));patch.extend(difflib.unified_diff(f.read_text().splitlines(True),local.read_text().splitlines(True),fromfile=str(f),tofile=str(local)))
 assert set(changed)=={'main.cpp','rank.hpp','native_controller.hpp','p49d_submit.cpp'},changed
 a=(P/'p49d_submit.cpp').read_text().replace('||choice=="reply-first"','');assert a==(parent/'p49d_submit.cpp').read_text(),'device submit arithmetic changed'
 # Target enqueue loop is byte-identical, including waits/copies and state proof.
 a=(P/'rank.hpp').read_text();b=(parent/'rank.hpp').read_text()
 start=' std::array<int,48> captured';end=' getrusage(RUSAGE_SELF,&after)'
 assert a[a.index(start):a.index(' if(e.a.rank==1)e.reply_report.begin')]==b[b.index(start):b.index(end)]
 (P/'packet92-host.patch').write_text(''.join(patch))
 sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'python_gate.py',P/'test_screen.py',P/'memory_plans.py',P/'memory_gate.py',P/'bundle_selection.py',P/'packet92-host.patch',*[WRAPPER/(t+'.py') for t in tests]]}
 save(P/'evidence/python-tests.json',dict(passed=True,device_executed=False,sources=sources,commands=[dict(argv=c,cwd=str(d)) for c,d in commands],unchanged_native_sources=identical,host_only_deltas=changed))
 print('shared wrapper, directions, unchanged arithmetic and memory checks PASS')
if __name__=='__main__':main()

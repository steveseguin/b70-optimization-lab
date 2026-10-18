"""CPU qualification: device exec intercepted; hash-pinned CPU mock exec allowed."""
import json,os,subprocess,sys,time,resource
from pathlib import Path
from source_decision import O,P,ROOT,sha,save
sys.path.insert(0,str(P))

def run(name,argv,timeout=600,env=None):
 log=O/'evidence'/(name+'.log');start=time.monotonic()
 with log.open('w') as out:cp=subprocess.run(argv,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,timeout=timeout,env=env)
 print(name,cp.returncode,flush=True)
 if cp.returncode:raise RuntimeError(name+' failed: '+log.read_text()[-5000:])
 return dict(command=argv,seconds=time.monotonic()-start,log=str(log.relative_to(ROOT)),sha256=sha(log))
def main():
 from build_engine import limits
 limits();assert resource.getrlimit(resource.RLIMIT_AS)==(-1,-1),'launch-limit positive probes require unlimited AS; actual memory remains bounded'
 python='/home/steve/.venvs/deepseek-v4-xpu/bin/python3'
 from startup_plan import environment
 env=dict(os.environ,PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',OMP_NUM_THREADS='2',PYTHONPATH=str(O)+':'+str(P))
 cmd=[python,'-B','-m','pytest','-q','-p','no:cacheprovider',str(O/'test139.py'),str(O/'test_submission.py'),str(P/'test_drain_fix.py'),str(P/'test_packet124.py'),str(P/'test_resume_chain.py'),str(P/'test_prepare_resume.py')]
 with (O/'tests.log').open('w') as out:cp=subprocess.run(cmd,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,timeout=600)
 assert cp.returncode==0,(O/'tests.log').read_text()[-5000:]
 from orchestrate import test_sources
 save(O/'cpu-tests.json',dict(passed=True,device_executed=False,command=cmd,log_sha256=sha(O/'tests.log'),sources=test_sources()))
 rows={}
 for name in ('argument_gate','native_startup139','launch_limit_gate','entry_gate','proposal_plan','drain_check'):
  rows[name]=run(name,[sys.executable,'-B',str(O/(name+'.py'))],timeout=900)
 run('policy_seal',[sys.executable,'-B',str(O/'policy_seal.py')])
 from verify_ready import evaluate
 ready=evaluate();save(O/'ready.json',ready)
 assert ready['cpu_preparation_ready'],ready.get('reason')
 assert not (P/'build/device-cards01-a').exists(),'chain unexpectedly started'
 from queue_gate import symlinks
 links=symlinks()
 from storage import precheck
 storage=precheck()
 build=sum(f.stat().st_size for f in P.rglob('*') if f.is_file() and not f.is_symlink() and 'build' in f.parts)
 assert build<=300_000_000 and storage['root_free_bytes']>=25_000_000_000
 save(O/'cpu-final.json',dict(passed=True,device_executed=False,cpu_preparation_ready=True,chain_ready=ready['ready'],device_evidence_pending=ready.get('reason'),runs=rows,symlinks_preserved=len(links),build_logical_bytes=build,root_free_bytes=storage['root_free_bytes'],max_child_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,proposal_sha256=sha(O.parent/'lane-queue/proposed-p139-smoke-A.txt'),chain_folder_fresh=True,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()))
 print(json.dumps(json.loads((O/'cpu-final.json').read_text()),indent=2))
if __name__=='__main__':main()

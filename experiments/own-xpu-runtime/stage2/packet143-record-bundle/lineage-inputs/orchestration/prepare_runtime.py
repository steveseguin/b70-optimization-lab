"""CPU-only composition seal generator. Never starts or queues device work."""
import argparse,json,os,resource,shutil,sys,subprocess
from source_decision import O,P,ROOT,sha,save
sys.path.insert(0,str(P))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--seal',action='store_true');ap.add_argument('--selection');a=ap.parse_args()
 from cpu_prepare143 import prepare,verify
 if not a.seal:verify();print('All 16 CPU seals verified');return
 assert not (P/'build/device-cards01-p143-a').exists()
 snap=P/'lineage-inputs/orchestration';snap.mkdir(exist_ok=True)
 for f in O.iterdir():
  if f.suffix in ('.py','.sh'):shutil.copyfile(f,snap/f.name)
 cp=subprocess.run([sys.executable,'-B',str(O/'test_readiness.py')],stdin=subprocess.DEVNULL,capture_output=True,text=True);assert cp.returncode==0,cp.stderr
 (O/'evidence/policy143.log').write_text(cp.stdout+cp.stderr)
 from drain_check import check
 save(P/'evidence/drain143.json',check())
 save(P/'evidence/policy143.json',dict(passed=True,device_executed=False,tests=10,sources={str((snap/n).relative_to(ROOT)):sha(snap/n) for n in ('test_readiness.py','verify_ready.py')}))
 prepare()
 if a.selection:
  from compositions import read
  from activate143 import activate
  activate(json.loads(a.selection) if a.selection.startswith('{') else read(a.selection))
 print('16 compositions sealed; no launch or queue action')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage('/').free>=25_000_000_000
 main()

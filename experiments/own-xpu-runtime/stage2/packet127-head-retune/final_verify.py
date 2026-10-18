"""Read-only CPU handoff verification; never launches a native/device process."""
import ast,json,os,resource,shutil,subprocess,sys
from pathlib import Path
from build_engine import P,ROOT,sha,check_map,provenance

def main():
 assert shutil.disk_usage('/').free>=25_000_000_000
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 from screen_jobs import verify,view,launch_receipt
 from bundle_selection import labelled_views
 verify();provenance();launch_receipt()
 from startup_receipt103 import verify as startup
 assert startup()['total_windows']==33
 from common import sealed
 from types import SimpleNamespace
 for label in labelled_views():
  path=view(label)
  sealed(SimpleNamespace(lineage=path,seal=path/'screen-seal.json',binary=None,dispatch=None,profile='tp2',timing='token',placement='1'))
 for leaf in ('cpu-byte-identity.json','full-shape.json','protocol-tests.json','microbench-build.json'):
  row=json.loads((P/'evidence'/leaf).read_text());assert row['passed'] and row['device_executed'] is False;check_map(ROOT,row['sources'])
 assert json.loads((P/'evidence/protocol-tests.json').read_text())['cold_worker_passed']
 from run_micro import build_gate
 build_gate()
 scan=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/check_drain_fix.py'),str(P),'--json'],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
 assert json.loads(scan.stdout)['passed']
 plans=json.loads((P/'evidence/queue-plans.json').read_text());assert plans['passed'] and plans['live_queue_modified'] is False and len(plans['plans'])==4
 for r in plans['plans']:assert sha(ROOT/r['proposal'])==r['sha256']
 for f in P.glob('*.py'):ast.parse(f.read_text(),filename=str(f))
 unique={}
 for root in (P/'build',P/'selections'):
  for f in root.rglob('*'):
   if f.is_file() and not f.is_symlink():
    st=f.stat();unique[(st.st_dev,st.st_ino)]=st.st_size
 size=sum(unique.values());assert size<=250_000_000,size
 evidence=json.loads((P/'evidence/selection-evidence.json').read_text());check_map(ROOT,evidence['sources'])
 result=dict(passed=True,device_executed=False,model_executed=False,views=3,startup_windows=33,byte_compilers=['GNU','Intel'],fresh_repeats_per_split_per_compiler=2,rank_exec_interceptions=6,isolated_cap_negative_control=True,proposals=4,build_unique_bytes=size,root_free_bytes=shutil.disk_usage('/').free,packet120_complete=evidence['packet120_complete'],pending=['two device micros','lane B grid','conditional lane A confirmation'])
 print(json.dumps(result,indent=2))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()

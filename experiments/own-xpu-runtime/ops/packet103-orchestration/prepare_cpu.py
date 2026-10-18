"""Finish CPU preparation after the exhaustive startup receipt exists; never launch devices."""
import json,os,subprocess,sys,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];P=ROOT/'experiments/own-xpu-runtime/stage2/packet103-record-bundle';O=P.parents[1]/'ops/packet103-orchestration'
sys.path.insert(0,str(P))
from build_engine import limits,sha,save

def main():
 limits();assert (P/'startup103.json').exists()
 os.environ['OMP_NUM_THREADS']='2'
 rows=[]
 def run(label,args,allowed=(0,)):
  path=O/(label+'.log');start=time.monotonic()
  with path.open('w') as log:r=subprocess.run([sys.executable,'-B',*map(str,args)],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
  row=dict(label=label,command=[sys.executable,'-B',*map(str,args)],returncode=r.returncode,seconds=time.monotonic()-start,log=str(path.relative_to(ROOT)),sha256=sha(path));rows.append(row)
  save(O/'preparation-report.json',dict(device_executed=False,live_queue_modified=False,steps=rows,complete=False))
  print(label,r.returncode,round(row['seconds'],2),flush=True)
  assert r.returncode in allowed,(label,path)
 run('required-views',[O/'prepare_views.py'])
 run('composition-queue-plan',[P/'queue_plan.py'])
 config=json.loads((P/'composition-selection.json').read_text())
 run('initial-reseal',[P/'fast_reseal.py',*[x for k,v in config['candidate'].items() for x in ('--'+k,v)]])
 run('cached-proof',[P/'dry_run.py','--cached'])
 run('cpu-dry-run',[P/'dry_run.py'])
 run('seal',[P/'chain_seal.py','--verify'])
 run('inputs',[P/'check_inputs.py'])
 run('storage',[P/'storage_precheck.py'],allowed=(0,1))
 run('queue-plan',[P/'chain103.py','queue','--plan','--output-root',P/'build/device-cards01-a'])
 record=json.loads((O/'view-preparation.json').read_text());decision=ROOT/record['decision']
 run('composite-proposals',[O/'composite_jobs.py','--decision',decision])
 run('leave-one-out-proposals',[O/'composite_jobs.py','--decision',decision,'--leave-one-out'])
 run('decision-readiness',[O/'orchestrate.py','--decision',decision,'--chain-output','device-cards01-a'],allowed=(0,2))
 run('verify-ready-refusal',[O/'verify_ready.py'],allowed=(0,1))
 ready=json.loads((O/'ready.json').read_text())
 save(O/'preparation-report.json',dict(complete=True,device_executed=False,live_queue_modified=False,steps=rows,ready=ready['ready'],decision=str(decision.relative_to(ROOT)),decision_sha256=sha(decision),scope='CPU preparation only; device composition evidence and current storage admission govern launch.'))

if __name__=='__main__':
 import argparse
 argparse.ArgumentParser(description=__doc__).parse_args()
 main()

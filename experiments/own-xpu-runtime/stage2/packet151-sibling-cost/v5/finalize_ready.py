"""Write READY-FOR-DEVICE.json once, after committed CPU proofs and proposals.

This is the final workspace write. It never queues or launches a job.
"""
import json,resource,subprocess
from pathlib import Path
from p151_v5_build_engine import P,LOCAL,ROOT,sha,save,limits
from cpu_seal import verify,check_sources,GATES as SEAL_GATES
from readiness import GATES

def main():
 limits();seal=verify();marker=LOCAL/'READY-FOR-DEVICE.json'
 assert not marker.exists(),'readiness already exists'
 assert seal['upper_bound'] and not seal['mechanism_scope_complete']
 gate_hashes={}
 for name in (*SEAL_GATES,*GATES):
  path=P/'evidence'/(name+'.json');row=json.loads(path.read_text())
  assert row['passed'] and row['device_executed'] is False,name
  check_sources(row.get('sources',{}));gate_hashes[name]=sha(path)
 plans=json.loads((P/'evidence/queue-plan.json').read_text())
 proposals={};expected=[]
 for item in plans['rows']:
  path=ROOT/item['proposal_name'];assert sha(path)==item['sha256']
  assert path.read_bytes()==(ROOT/item['mirror']).read_bytes()
  job=json.loads(path.read_text());plan=job['plan']
  assert plan['watchdog_seconds']>=4*max(plan['expected_seconds'])
  assert plan['planned_write_bytes_per_view']==240_000_000
  assert plan['measurement_scope']==seal['measurement_scope']
  proposals[item['proposal_name']]=sha(path);expected.append(job['name'])
 assert len(proposals)==2
 for lane in ('A','B'):
  queue=LOCAL.parents[1]/'ops/lane-queue'/('queue-'+lane+'.txt')
  if queue.exists():
   for line in queue.read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#'):assert json.loads(line)['name'] not in expected,'proposal already queued'
 paths=[str(LOCAL.relative_to(ROOT)),'notes/2026-10-19-own-runtime-packet151.md',*proposals]
 subprocess.run(['git','diff','--quiet','HEAD','--',*paths],cwd=ROOT,stdin=subprocess.DEVNULL,check=True)
 commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,stdin=subprocess.DEVNULL,text=True).strip()
 row=dict(schema='packet151.ready-for-device.v1',passed=True,ready_for_device=True,
  commit=commit,commit_definition='committed source, CPU receipts and proposals immediately before this marker',
  proposal_sha256=proposals,cpu_seal_sha256=sha(P/'cpu-seal.json'),cpu_gate_sha256=gate_hashes,
  measurement_scope=seal['measurement_scope'],upper_bound=True,mechanism_scope_complete=False,
  arithmetic='iq3-p49-split32-v1',device_executed=False,device_quality_pending=True,
  measured_cost_pending=True,threshold_ms=1.952,
  decisions=['reopen packet132 if upper-bound cost <= 1.952 ms','inconclusive upper bound; full M=2 needed otherwise'],
  policy_calibration='packet114 independent text only; never the 12-prompt suite',
  planned_write_bytes_per_view=240_000_000,queued=False)
 save(marker,row)
 print('READY-FOR-DEVICE.json written last; unqueued; device quality and cost pending')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main()

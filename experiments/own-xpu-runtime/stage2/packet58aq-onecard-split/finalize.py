"""Write READY last, only after final source-bound CPU and proposal checks."""
import hashlib,json,resource,shutil,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];OPS=P.parents[1]/'ops'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
def main():
 assert not (P/'READY-FOR-DEVICE.json').exists()
 assert not (P/'screen/evidence/card0-58aq-split-a').exists()
 subprocess.run(['/usr/bin/python3','-B',str(P/'seal.py'),'--verify'],check=True,stdin=subprocess.DEVNULL)
 checks={}
 for leaf in ('cpu-exactness','preparation','analyzer-real-parent','report-adapter','flags','queue-plans','storage'):
  f=P/'evidence'/f'{leaf}.json';row=read(f);assert row['passed'] and not row['device_executed'],leaf;checks[str(f.relative_to(P))]=sha(f)
 for name in ('entry-split','entry-smoke'):
  f=P/'evidence'/f'{name}.json';row=read(f);assert row['passed'];checks[str(f.relative_to(P))]=sha(f)
  for job in row['jobs']:
   assert all(x['passed'] for x in job['binaries'])
   assert job['gate_identity']['status']!='FAIL'
   assert job['storage_floor']['passed'] and job['wall_deadlines']['passed']
 shared=read(P/'evidence/shared-entry-report-final.json')
 assert len(shared['jobs'])==1
 reports=shared['jobs'][0]['report']['kinds']
 assert reports[0]['kind']=='smoke' and reports[0]['passed']
 assert reports[1]['kind']=='bracket' and not reports[1]['passed']
 assert all(b['passed'] for b in shared['jobs'][0]['binaries'])
 checks['evidence/shared-entry-report-final.json']=sha(P/'evidence/shared-entry-report-final.json')
 adapter=read(P/'evidence/report-adapter.json')
 for n,h in adapter['source_hashes'].items():assert sha(ROOT/n)==h
 assert {r['case'] for r in adapter['records']}=={'smoke','build-brief','close','name-host-work','inconclusive-cadence','truncated-stream'}
 exact=read(P/'evidence/cpu-exactness.json');prep=read(P/'evidence/preparation.json')
 assert exact['peak_rss_bytes']<4*1024**3 and prep['peak_child_rss_bytes']<4*1024**3
 proposals={}
 arguments=read(P/'screen/evidence/argument-gate.json')
 plans=read(P/'evidence/queue-plans.json')
 for tag in ('split','smoke'):
  path=OPS/'lane-queue'/f'proposed-p58aq-{tag}-A.txt';h=sha(path)
  assert (P/'screen/proposals'/path.name).read_bytes()==path.read_bytes()
  assert next(r for r in plans['records'] if r['tag']==tag)['proposal_sha256']==h
  candidate='resident' if tag=='split' else 'smoke'
  assert all(r['proposal_sha256']==h for r in arguments['records'] if r['candidate']==candidate)
  proposals[str(path.relative_to(ROOT))]=h
 size=sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file());assert size<=300_000_000
 assert shutil.disk_usage('/').free>=27_000_000_000
 row=dict(schema='own-runtime.packet58aq.ready.v1',ready_for_device=True,passed=True,device_executed=False,
  scope='whole-host',lane='A',gpu_count=1,coordinator_holds='PAUSE-B',model_loads=1,optional_smoke_required=False,
  diagnostic_only=True,strict512=False,submission_eligible=False,arithmetic='iq3-p49-split32-v1',kv_dtype='BF16',
  runtime='packet58aj resident composition, publication skip-and-repair diagnostic',
  arm_order=['control','no-upload','no-scatter','drain-only','wait-split','control'],
  prompts_per_view=12,max_new=32,per_operation_wait_seconds=600,planned_model_screen_seconds=[600,900],
  build_receipt_sha256=sha(P/'screen/build-receipt.json'),checks=checks,proposals=proposals,
  shared_tool_limitations=['Frozen ops --report has five-view/128-token fixture: smoke passes; six-view bracket fixture fails. Private report_adapter exercises actual report and all decision tails.','Shared preparation adapter requires --rank; private device-define one-card probe runs actual 72-request, six-view reset paths with real sensors.'],
  native_outputs_exact_on_device='pending',publication_split_ms_per_token=None,host_wait_split_ms_per_token=None,
  preparation_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True,stdin=subprocess.DEVNULL).strip())
 # This is deliberately the final artifact write. Commit/push follows.
 (P/'READY-FOR-DEVICE.json').write_text(json.dumps(row,indent=2)+'\n')
 print('READY: packet58aq one-load device diagnostic; no device launched')
if __name__=='__main__':main()

"""Generate and privately plan one selected smoke; never enqueue or launch."""
import argparse,json,subprocess,sys,tempfile,shutil
from pathlib import Path
from compositions import P,ROOT,validate,read,path,key,sha,save
QUEUE=P.parents[1]/'ops/lane-queue';O=P.parents[1]/'ops/packet143-orchestration'
def proposal(selection):
 from memory143 import HOST_BYTES
 return dict(name='packet143-smoke-A',lane='A',argv=['/usr/bin/python3','-B',str((P/'smoke_job.py').relative_to(ROOT)),'--selection',str(path(selection)/'composition.json'),'--output',str(P/'evidence'/('device-smoke-A-'+key(selection))),'--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=str((P/'v5/fault_review.py').relative_to(ROOT)),plan=dict(host_required_available_bytes=HOST_BYTES,expected_seconds=[240,360],watchdog_seconds=1800,entry_rehearsal=dict(binaries=[dict(path=str((P/'v5/build/device/own-rt-iq3').relative_to(ROOT)),sha256=sha(P/'v5/build/device/own-rt-iq3'))])))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--selection',required=True);ap.add_argument('--plan-only',action='store_true');a=ap.parse_args();selection=validate(json.loads(a.selection) if a.selection.startswith('{') else read(a.selection))
 from cpu_prepare143 import verify
 verify();row=proposal(selection);content=json.dumps(row)+'\n'
 snapshot=P/'lineage-inputs/queue'
 with tempfile.TemporaryDirectory(prefix='p143-smoke-plan-') as d:
  tmp=Path(d)
  for f in QUEUE.glob('*.py'):shutil.copy2(f,tmp/f.name)
  (tmp/'queue-A.txt').write_text(content)
  with (O/'evidence/smoke-plan.log').open('w') as log:r=subprocess.run([sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane','A','--directory',str(tmp)],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=300)
  assert r.returncode==0,(O/'evidence/smoke-plan.log').read_text()[-5000:]
  tmp_proposal=tmp/'proposal.txt';tmp_proposal.write_text(content)
  with (O/'evidence/entry-rehearsal.log').open('w') as log:r=subprocess.run([sys.executable,'-B',str(P.parents[1]/'ops/rehearse_entry.py'),str(tmp_proposal),'--json'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=120)
  assert r.returncode==0,(O/'evidence/entry-rehearsal.log').read_text()[-3000:]
 dest=QUEUE/'proposed-p143-smoke-A.txt'
 if not a.plan_only:dest.write_text(content)
 (P/'proposals').mkdir(exist_ok=True);(P/'proposals/proposed-p143-smoke-A.txt').write_text(content)
 save(O/'evidence/proposal-plan.json',dict(passed=True,device_executed=False,queued=False,live_queue_modified=False,selection=selection,proposal=str(dest.relative_to(ROOT)),proposal_sha256=sha(P/'proposals/proposed-p143-smoke-A.txt'),entry_rehearsal_passed=True))
 print('Selected smoke planned and rehearsed; unqueued')
if __name__=='__main__':main()

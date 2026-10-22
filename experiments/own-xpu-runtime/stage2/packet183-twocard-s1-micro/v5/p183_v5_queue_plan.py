"""Lane-B proposal file and temporary plans only. Never edit live queue files.

One proposal file, ops/lane-queue/proposed-p183-two-card-B.txt: the metadata
smoke (12 prompts x 64 tokens, candidate view only) then the five-view one-load
bracket, which depends on the smoke. --stage writes the packet mirror before the
seal; the plain run checks the mirror, plans both rows together on a temporary
copy of the queue code (lanequeue.py plan --lane B --directory TMP), writes the
proposal file, and rehearses it with ops/rehearse_entry.py --report --json.
"""
import argparse,json,subprocess,sys,tempfile,shutil
from pathlib import Path
from p183_v5_build_engine import P,LOCAL,ROOT,sha,save,limits
QUEUE=LOCAL.parents[1]/'ops/lane-queue'
NAME='proposed-p183-two-card-B.txt'
HOST=97*1024**3+1200*1024**2
HEADER='''# PROPOSAL ONLY (packet183). Never queued by preparation; the device-window driver decides.
# Lane B = cards 2+3 (PCI 0000:43:00.0 + 0000:47:00.0), two-card resident, whole host: PAUSE-A stays during both rows.
# The owner's endpoints on those cards (qwen38-27b-vision :18100 cards 1+2, qwen38-27b-fp8-tp1-test :18131 card 3) must be
# stopped by the window operator first, and only after `lanequeue.py plan --lane B` passes on the live queue; card 2 has a
# recorded GuC lockup history (CURRENT.md host notes) - the operator may instead run the same rows on lane A (cards 0+1).
# S1 dense-scales (packet177 PLAN section 5): one engine load, A/B/A/B/A = expanded/metadata/expanded/metadata/expanded;
# only selection key dense_scales switches (snapshot_host=production, all other choices = bundle 8). Device binary
# v5/build/device/own-rt-iq3 = packet136 parent objects unchanged + recompiled entry-main/p49d_submit + new s1_submit.
# Row 1 smoke: metadata view only, 12 prompts x 64 tokens + incident64, exact vs iq3-p49-split32-v1; ~3 min (packet153
# smoke 01:40-01:43 UTC), plan 240-360 s, watchdog 3600 s. Row 2 bracket (depends on the smoke's own evidence): five views,
# 12 x 128-token cold prompts + incident64 each, all 13/13 exact, identical draft proposals; ~8.5 min (packet153 bracket
# 01:45:24-01:53:38 UTC), plan 480-900 s, watchdog 3600 s.
# Screen winner: both metadata views >= +0.5% over every control, control drift <= 3%. Chain rule (win-path waiter,
# chain/ARMING.md, NOT armed): both >= +2% over every control AND >= 1.02 x 58.798109 = 59.974 tok/s.
# Expected (evidence/expected-gain.json): +4.4% floor / +6.2% proportional; +2% needs 46% of the floor saving.
# Host admission 105,411,248,128 B (97 GiB + 1200 MiB, packet153's) plus the queue's 1 GiB at START. No setting changes.
'''

def proposal(kind):
 out='device-metadata-'+('smoke' if kind=='smoke' else 'v5')+'-B-p183'
 row=dict(name='packet183-s1-'+kind+'-B',lane='B',argv=['/usr/bin/python3','-B',str((P/'bracket_job.py').relative_to(ROOT)),'--variant','metadata','--kind',kind,'--lane','B','--output',str(P/'evidence'/out),'--fault-review','{REVIEW}','--authorized-device-window'],
  env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)),
  plan=dict(entry_rehearsal=dict(binaries=[dict(path=str((P/'build'/m/'own-rt-iq3').relative_to(ROOT)),sha256=sha(P/'build'/m/'own-rt-iq3')) for m in ('device','gnu-host')],
                                 preparation_probe_note='Production-shape startup of both selections on both ranks (real initialize/capture/allocation/bracket_select/request_reset/DraftRuntime, numerical device addresses, no payload): v5/evidence/full-shape.json via v5/p183_v5_full_shape.py. The shared prepare_probe has no two-rank v5 bracket entry; keep its WARN explicit.'),
            host_required_available_bytes=HOST,expected_seconds=([240,360] if kind=='smoke' else [480,900]),watchdog_seconds=3600,planned_writes=(240_000_000 if kind=='smoke' else 1_200_000_000)))
 if kind=='bracket':row['depends_on']=['packet183-s1-smoke-B']
 return row

def content():
 return HEADER+''.join(json.dumps(proposal(k))+'\n' for k in ('smoke','bracket'))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--stage',action='store_true');a=ap.parse_args()
 limits();snapshot=LOCAL/'lineage-inputs/queue';snapshot.mkdir(exist_ok=True)
 for src in QUEUE.glob('*.py'):shutil.copy2(src,snapshot/src.name)
 mirror=LOCAL/'proposals'/NAME;text=content()
 if a.stage:
  for old in (LOCAL/'proposals').glob('*.txt'):old.unlink()
  mirror.parent.mkdir(exist_ok=True);mirror.write_text(text);return
 assert mirror.read_text()==text,'stage proposals before sealing'
 with tempfile.TemporaryDirectory(prefix='p183-plan-') as d:
  tmp=Path(d)
  for src in snapshot.glob('*.py'):shutil.copy2(src,tmp/src.name)
  (tmp/'queue-B.txt').write_text(text)
  cmd=[sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane','B','--directory',str(tmp)]
  log=P/'evidence/plan-B.log'
  with log.open('w') as out:r=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,timeout=600)
  assert r.returncode==0,log.read_text()[-8000:]
 live=QUEUE/NAME;live.write_text(text)
 r=subprocess.run([sys.executable,'-B',str(QUEUE.parent/'rehearse_entry.py'),str(live),'--report','--json'],cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
 (P/'evidence/rehearse.log').write_text(r.stdout+r.stderr)
 assert r.returncode==0,r.stdout[-6000:]+r.stderr[-3000:]
 rehearsal=json.loads(r.stdout);assert rehearsal['passed']
 receipt=P/'evidence/rehearse.json';save(receipt,rehearsal)
 for src in snapshot.glob('*.py'):assert sha(src)==sha(QUEUE/src.name),'queue changed during planning'
 rows=[dict(job=proposal(k)['name'],unit='screen-'+proposal(k)['name']+'.service') for k in ('smoke','bracket')]
 save(P/'evidence/queue-plan.json',dict(passed=True,device_executed=False,live_queue_modified=False,queued=False,proposal_name=str(live.relative_to(ROOT)),sha256=sha(live),
  mirror=str(mirror.relative_to(ROOT)),log=str(log.relative_to(ROOT)),log_sha256=sha(log),rehearsal=str(receipt.relative_to(ROOT)),rehearsal_sha256=sha(receipt),rows=rows,
  sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'p183_v5_queue_plan.py',*snapshot.glob('*.py')]}))
if __name__=='__main__':main()

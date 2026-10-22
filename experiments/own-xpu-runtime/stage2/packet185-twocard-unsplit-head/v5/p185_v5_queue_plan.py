"""Lane-B proposal file and temporary plans only. Never edit live queue files.

One proposal file, ops/lane-queue/proposed-p185-two-card-B.txt: five fresh-load view rows
(one engine load, one 12x128 view each) in the order production/unsplit/production/unsplit/
production, each depending on the previous one. --stage writes the packet mirror before the
seal; the plain run checks the mirror, plans all five rows together on a temporary copy of the
queue code (lanequeue.py plan --lane B --directory TMP), writes the proposal file, and rehearses
it with ops/rehearse_entry.py --report --json.
"""
import argparse,json,subprocess,sys,tempfile,shutil
from pathlib import Path
from p185_v5_build_engine import P,LOCAL,ROOT,sha,save,limits
from bracket_config import VIEWS
QUEUE=LOCAL.parents[1]/'ops/lane-queue'
NAME='proposed-p185-two-card-B.txt'
HOST=97*1024**3+1200*1024**2
# Recorded row times on this lane and line (2026-10-22, packet183, window.json elapsed_seconds):
#  smoke row 11:56:31-12:01:34 UTC: 299.2 s = load/teardown 188.2 s (cold page cache after the endpoint stop) + one view 111.0 s;
#  bracket row 12:03:09-12:11:14 UTC: 479.7 s = load/teardown 94.2 s + views 122.6 (first, cold first request) + 67.4 + 64.3 + 66.7 + 64.5 s.
# A packet185 row = one load + one 12x128 view whose first request is cold: ~94 + 123 = 217 s warm, ~188 + 123 = 311 s for the
# first row of a window. Five rows + four 61 s queue drain spacings ~ 311 + 4 x 217 + 244 = 1,423 s (23.7 min).
EXPECTED={0:[300,420],1:[200,330],2:[200,330],3:[200,330],4:[200,330]}
HEADER='''# PROPOSAL ONLY (packet185). Never queued by preparation; the device-window driver decides.
# Lane B = cards 2+3 (PCI 0000:43:00.0 + 0000:47:00.0), two-card resident, whole host: PAUSE-A stays during all five rows.
# The owner's endpoints on those cards (qwen38-27b-vision :18100 cards 1+2, qwen38-27b-fp8-tp1-test :18131 card 3) must be
# stopped by the window operator first, and only after `lanequeue.py plan --lane B` passes on the live queue; card 2 has a
# recorded GuC lockup history (CURRENT.md host notes) - the operator may instead run the same rows on lane A (cards 0+1).
# Packet185 measures the attribution packet177(b) asks for (coordinator ruling 2026-10-22): bundle 8 with the target head
# split (production) versus the full head on rank 1 (unsplit, target_head=production). The split is a storage choice (rank 1
# 202,240 vs 248,320 head rows; rank 0 the 46,080-row suffix or nothing), so the native bracket refuses an in-load switch:
# five FRESH loads, one view each, C/U/C/U/C, each row depending on the previous one. No rebuild: device engine = packet183's
# v5/build/device/own-rt-iq3 byte for byte (dense_scales=expanded = bundle 8). Each row: incident64 + 12 cold x 128 tokens,
# 13/13 exact vs iq3-p49-split32-v1, first-request data proof in-run. ~217 s per row (~311 s for the first row of a window;
# packet183 row times 2026-10-22), plan 200-330 s (first 300-420 s), watchdog 3600 s, 240 MB writes per row; five rows plus
# four 61 s drain spacings ~ 24 min. Decision (view row 4 summary `s185_decision`, or v5/s185_decision.py over the five
# outputs): V3 GO iff un-split cost on rank 1 <= 0.39 ms AND decoupled B-A >= 0.60 ms AND every view exact with identical
# draft proposals AND control drift <= 3%; otherwise V3 closed and packet177(b) keeps its closure with this attribution.
# Not a speed or record row. Memory (full-shape census): rank 0 -157,322,272 B, rank 1 +155,750,384 B (arena headroom
# 630,519,094 B, 2.66 GB physical free). Host admission 105,411,248,128 B (97 GiB + 1200 MiB) plus the queue's 1 GiB at START.
'''

def output(index):
 return P/'evidence'/f'device-view{index}-{VIEWS[index]}-B-p185'

def proposal(index):
 variant=VIEWS[index]
 row=dict(name=f'packet185-view{index}-{variant}-B',lane='B',argv=['/usr/bin/python3','-B',str((P/'bracket_job.py').relative_to(ROOT)),'--variant',variant,'--kind','view','--index',str(index),'--lane','B','--output',str(output(index)),'--fault-review','{REVIEW}','--authorized-device-window'],
  env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)),
  plan=dict(entry_rehearsal=dict(binaries=[dict(path=str((P/'build'/m/'own-rt-iq3').relative_to(ROOT)),sha256=sha(P/'build'/m/'own-rt-iq3')) for m in ('device','gnu-host')],
                                 preparation_probe_note='Production-shape startup of both selections on both ranks (real initialize/capture/allocation/bracket_select/request_reset/DraftRuntime, numerical device addresses, no payload): v5/evidence/full-shape.json via v5/p185_v5_full_shape.py. The shared prepare_probe has no two-rank v5 bracket entry; keep its WARN explicit.'),
            host_required_available_bytes=HOST,expected_seconds=EXPECTED[index],watchdog_seconds=3600,planned_writes=240_000_000))
 if index:row['depends_on']=[f'packet185-view{index-1}-{VIEWS[index-1]}-B']
 return row

def content():
 return HEADER+''.join(json.dumps(proposal(i))+'\n' for i in range(5))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--stage',action='store_true');a=ap.parse_args()
 limits();snapshot=LOCAL/'lineage-inputs/queue';snapshot.mkdir(exist_ok=True)
 for src in QUEUE.glob('*.py'):shutil.copy2(src,snapshot/src.name)
 mirror=LOCAL/'proposals'/NAME;text=content()
 if a.stage:
  for old in (LOCAL/'proposals').glob('*.txt'):old.unlink()
  mirror.parent.mkdir(exist_ok=True);mirror.write_text(text);return
 assert mirror.read_text()==text,'stage proposals before sealing'
 with tempfile.TemporaryDirectory(prefix='p185-plan-') as d:
  tmp=Path(d)
  for src in snapshot.glob('*.py'):shutil.copy2(src,tmp/src.name)
  (tmp/'queue-B.txt').write_text(text)
  cmd=[sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane','B','--directory',str(tmp)]
  log=P/'evidence/plan-B.log'
  with log.open('w') as out:r=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,timeout=600)
  assert r.returncode==0,log.read_text()[-8000:]
 live=QUEUE/NAME;live.write_text(text)
 # Gating rehearsal: entry imports, native entries and packaging checks of all five rows.
 r=subprocess.run([sys.executable,'-B',str(QUEUE.parent/'rehearse_entry.py'),str(live),'--json'],cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
 (P/'evidence/rehearse.log').write_text(r.stdout+r.stderr)
 assert r.returncode==0,r.stdout[-6000:]+r.stderr[-3000:]
 rehearsal=json.loads(r.stdout);assert rehearsal['passed'] and len(rehearsal['jobs'])==5
 # Shared-tool limitation (recorded, not gating): rehearse_entry --report knows only the v5 kinds
 # smoke/bracket for a screen.main entry; packet185's entry accepts only --kind view, so its synthetic
 # smoke/bracket report probes are refused at the entry parser. The packet's own report gate
 # (v5/report_gate.py) runs the real bracket_job --report-only path for all five rows on both lanes.
 r2=subprocess.run([sys.executable,'-B',str(QUEUE.parent/'rehearse_entry.py'),str(live),'--report','--json'],cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=900)
 (P/'evidence/rehearse-report.log').write_text(r2.stdout+r2.stderr)
 shared=json.loads(r2.stdout)
 for job in shared['jobs']:
  assert {k['kind'] for k in job['report']['kinds']}=={'smoke','bracket'} and all(not k['passed'] for k in job['report']['kinds'])
  rest={k:v for k,v in job.items() if k not in ('report','passed')}
  assert all(b['passed'] for b in job.get('binaries',[])),job['job']
 rehearsal['shared_report_limitation']=dict(passed=shared['passed'],reason='rehearse_entry --report probes only kinds smoke/bracket for v5 screen.main entries; packet185 rows are --kind view (refused at the entry parser); v5/report_gate.py covers the real report path',
  kinds_refused=sorted({k['kind'] for j in shared['jobs'] for k in j['report']['kinds']}),log=str((P/'evidence/rehearse-report.log').relative_to(ROOT)))
 receipt=P/'evidence/rehearse.json';save(receipt,rehearsal)
 for src in snapshot.glob('*.py'):assert sha(src)==sha(QUEUE/src.name),'queue changed during planning'
 rows=[dict(job=proposal(i)['name'],unit='screen-'+proposal(i)['name']+'.service') for i in range(5)]
 save(P/'evidence/queue-plan.json',dict(passed=True,device_executed=False,live_queue_modified=False,queued=False,proposal_name=str(live.relative_to(ROOT)),sha256=sha(live),
  mirror=str(mirror.relative_to(ROOT)),log=str(log.relative_to(ROOT)),log_sha256=sha(log),rehearsal=str(receipt.relative_to(ROOT)),rehearsal_sha256=sha(receipt),rows=rows,
  sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'p185_v5_queue_plan.py',*snapshot.glob('*.py')]}))
if __name__=='__main__':main()

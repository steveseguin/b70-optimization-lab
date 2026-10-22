"""Lane-B proposal file and temporary plans only. Never edit live queue files.

One proposal file, ops/lane-queue/proposed-p189-two-card-B.txt: two rows, the second depending on the first:
k3x smoke, one-load V3/k3x/V3/k3x/V3 bracket. No fresh V3 row: packet188 row 1 is the fresh reference.
--stage writes the packet mirror before the seal; the plain run checks the mirror, plans both rows
together on a temporary copy of the queue code (lanequeue.py plan --lane B --directory TMP), writes the
proposal file, and rehearses it with ops/rehearse_entry.py --json (and --report, recorded).
"""
import argparse,json,subprocess,sys,tempfile,shutil
from pathlib import Path
from p189_v5_build_engine import P,LOCAL,ROOT,sha,save,limits
from bracket_config import ROWS,EXPECTED,host_required
QUEUE=LOCAL.parents[1]/'ops/lane-queue'
NAME='proposed-p189-two-card-B.txt'
# Recorded row times on this lane (2026-10-22, window.json elapsed_seconds): packet188 (lanequeue-B35, 19:55-20:16 UTC):
#  k3+trims smoke (first row, cold) 313 s, fresh V3 control 213 s, one-load V3/k3+trims/V3/k3+trims/V3 bracket 480.0 s.
# Packet189: smoke ~313 s (same storage and request mix), bracket ~480 s; plus one 61 s drain spacing ~ 313+480+61 = 854 s (14.2 min).
HEADER='''# PROPOSAL ONLY (packet189). Never queued by preparation; the device-window driver decides.
# Lane B (two-card resident, whole host: PAUSE-A stays during both rows). The owner's endpoints on the lane-B cards must be
# stopped by the window operator first, and only after `lanequeue.py plan --lane B` passes on the live queue.
# Packet189 = k3x: packet188's k3 + trims with the 20,480-byte boundary export back on the copy engine. Coordinator ruling
# 2026-10-22: packet188's loss is attributed to its own export path (handoff_export +0.540 ms via the per-byte KioCopy readback,
# 28.9 ns/byte, vs the copy engine's 2.6 ns/byte), not to the third boundary layer (boundary_body +0.459 ms = the 0.463 ms saved
# on rank 1); the k=3 ruling stands. New execution key boundary_export=copy|kernel (switchable in-load like boundary/kernel_io/
# rank0_prepare); k3x = rank0_layers 0-26, boundary rank0-k3, kernel_io kernel, rank0_prepare async, boundary_export copy.
# Rebuilt entry TUs (entry-main, p49d_submit, s1_submit) over the 78 pinned parent objects; storage, census and memory plan
# are packet188's (production-shape startup identical).
# Rows (row 1 depends on row 0; same lane): 0 k3x smoke 12 x 64 + incident64 (exact, first-request data proof) ~313 s;
# 1 one-load bracket V3/k3x/V3/k3x/V3 (V3 = k3 storage, boundary rank0, trims off, export copy) 5 x 12 x 128 ~480 s;
# watchdog 3600 s each; writes 240 MB per view (bracket 1.2 GB). No fresh V3 row: packet188 row 1 (60.50488520482965, hash-pinned,
# read in place) is the fresh reference.
# Decision (row 1 summary `s189_decision`, or v5/s189_decision.py over rows 0..1): D := draft_rows.draft_wall_ms (never op 9);
# screen winner iff the slower k3x view >= 1.005 x every V3 view (3 in-load + packet188 fresh), every view exact with identical
# proposals and acceptance, V3 drift <= 3 %; chain rule iff also >= 1.02 x every V3 view AND >= 61.87271031814733 tok/s. Kill rules
# recorded: handoff_export > 0.10 ms, boundary_total > 1.60 ms, k3 hit saving < 0.35 ms, Bd > draft wall on > 10 % of hits,
# A trim < 0.105 ms. Priced +2.74 % (62.32 tok/s on the record replay; pessimistic +2.27 %). Never a record row (record = fresh chain, README).
# Memory (full-shape census, = packet188): k3 storage rank 0 31,374,119,922 B (+1,129,070,858 B over V3; headroom 838,134,798 B under
# the 32,212,254,720 B arena limit), rank 1 unchanged (31,581,735,626 B, headroom 630,519,094 B); pinned kernel-io 86,016 + 73,728 B (host).
# Host admission: k3x rows 108,797,048,558 B (+ layer-26 shadow + staging), plus the queue's 1 GiB at START.
'''

def output(index):
 from p189_v5_compare import row_output
 return row_output(index,'B')

def job(index):
 return f'packet189-{ROWS[index]["name"]}-B'

def proposal(index):
 r=ROWS[index];views=5 if r['kind']=='bracket' else 1
 row=dict(name=job(index),lane='B',argv=['/usr/bin/python3','-B',str((P/'bracket_job.py').relative_to(ROOT)),'--variant',r['variant'],'--kind',r['kind'],'--index',str(index),'--lane','B','--output',str(output(index)),'--fault-review','{REVIEW}','--authorized-device-window'],
  env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)),
  plan=dict(entry_rehearsal=dict(binaries=[dict(path=str((P/'build'/m/'own-rt-iq3').relative_to(ROOT)),sha256=sha(P/'build'/m/'own-rt-iq3')) for m in ('device','gnu-host')],
                                 preparation_probe_note='Production-shape startup of every registered selection on both ranks and both bracket start orders (real initialize/refresh_v3/capture/allocation/bracket_select/request_reset/DraftRuntime, numerical device addresses, no payload; captures and census identical to packet188): v5/evidence/full-shape.json via v5/p189_v5_full_shape.py; k3x state correctness and export-path byte identity: v5/evidence/k3-state.json. The shared prepare_probe has no two-rank v5 bracket entry; keep its WARN explicit.'),
            host_required_available_bytes=host_required(r['variant']),expected_seconds=EXPECTED[index],watchdog_seconds=3600,planned_writes=240_000_000*views))
 if index:row['depends_on']=[job(index-1)]
 return row

def content():
 return HEADER+''.join(json.dumps(proposal(i))+'\n' for i in range(len(ROWS)))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--stage',action='store_true');a=ap.parse_args()
 limits();snapshot=LOCAL/'lineage-inputs/queue';snapshot.mkdir(exist_ok=True)
 for src in QUEUE.glob('*.py'):
  dst=snapshot/src.name
  if dst.exists():dst.unlink() # never write through a hard link into packet186's history
  shutil.copy2(src,dst)
 mirror=LOCAL/'proposals'/NAME;text=content()
 if a.stage:
  for old in (LOCAL/'proposals').glob('*.txt'):old.unlink()
  mirror.parent.mkdir(exist_ok=True);mirror.write_text(text);return
 assert mirror.read_text()==text,'stage proposals before sealing'
 with tempfile.TemporaryDirectory(prefix='p189-plan-') as d:
  tmp=Path(d)
  for src in snapshot.glob('*.py'):shutil.copy2(src,tmp/src.name)
  (tmp/'queue-B.txt').write_text(text)
  cmd=[sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane','B','--directory',str(tmp)]
  log=P/'evidence/plan-B.log'
  with log.open('w') as out:r=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,timeout=600)
  assert r.returncode==0,log.read_text()[-8000:]
 live=QUEUE/NAME;live.write_text(text)
 # Gating rehearsal: entry imports, native entries and packaging checks of all three rows.
 r=subprocess.run([sys.executable,'-B',str(QUEUE.parent/'rehearse_entry.py'),str(live),'--json'],cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
 (P/'evidence/rehearse.log').write_text(r.stdout+r.stderr)
 assert r.returncode==0,r.stdout[-6000:]+r.stderr[-3000:]
 rehearsal=json.loads(r.stdout);assert rehearsal['passed'] and len(rehearsal['jobs'])==len(ROWS)
 # Recorded (not gating): rehearse_entry --report synthesizes smoke/bracket reports for a v5 screen.main entry; packet188's
 # entry binds kind/variant/index to the row registry, so synthetic kinds other than the row's own refuse at the entry
 # parser. The packet's own report gate (v5/report_gate.py) runs the real bracket_job --report-only path for all rows.
 r2=subprocess.run([sys.executable,'-B',str(QUEUE.parent/'rehearse_entry.py'),str(live),'--report','--json'],cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=900)
 (P/'evidence/rehearse-report.log').write_text(r2.stdout+r2.stderr)
 try:shared=json.loads(r2.stdout)
 except ValueError:shared=dict(passed=False,jobs=[],unparsed=True)
 for j in shared.get('jobs',[]):assert all(b['passed'] for b in j.get('binaries',[])),j.get('job')
 rehearsal['shared_report_rehearsal']=dict(passed=shared.get('passed'),returncode=r2.returncode,
  kinds=[dict(job=j.get('job'),report=[dict(kind=k.get('kind'),passed=k.get('passed')) for k in j.get('report',{}).get('kinds',[])]) for j in shared.get('jobs',[])],
  note='informational: v5/report_gate.py covers the real report path for all three rows on both lanes',log=str((P/'evidence/rehearse-report.log').relative_to(ROOT)))
 receipt=P/'evidence/rehearse.json';save(receipt,rehearsal)
 for src in snapshot.glob('*.py'):assert sha(src)==sha(QUEUE/src.name),'queue changed during planning'
 rows=[dict(job=proposal(i)['name'],unit='screen-'+proposal(i)['name']+'.service',expected_seconds=EXPECTED[i]) for i in range(len(ROWS))]
 save(P/'evidence/queue-plan.json',dict(passed=True,device_executed=False,live_queue_modified=False,queued=False,proposal_name=str(live.relative_to(ROOT)),sha256=sha(live),
  mirror=str(mirror.relative_to(ROOT)),log=str(log.relative_to(ROOT)),log_sha256=sha(log),rehearsal=str(receipt.relative_to(ROOT)),rehearsal_sha256=sha(receipt),rows=rows,
  sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'p189_v5_queue_plan.py',*snapshot.glob('*.py')]}))
if __name__=='__main__':main()

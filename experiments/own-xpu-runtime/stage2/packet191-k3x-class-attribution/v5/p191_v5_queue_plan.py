"""Lane-B proposal file and temporary plans only. Never edit live queue files.

One proposal file, ops/lane-queue/proposed-p191-two-card-B.txt: two rows, the second depending on the first:
k3x-on smoke, one-load off/on/off/on/off sites bracket (a measurement).
--stage writes the packet mirror before the seal; the plain run checks the mirror, plans both rows
together on a temporary copy of the queue code (lanequeue.py plan --lane B --directory TMP), writes the
proposal file, and rehearses it with ops/rehearse_entry.py --json (and --report, recorded).
"""
import argparse,json,subprocess,sys,tempfile,shutil
from pathlib import Path
from p191_v5_build_engine import P,LOCAL,ROOT,sha,save,limits
from bracket_config import ROWS,EXPECTED,host_required
QUEUE=LOCAL.parents[1]/'ops/lane-queue'
NAME='proposed-p191-two-card-B.txt'
# Recorded row times on this lane (2026-10-22, window.json elapsed_seconds): packet189 (lanequeue-B36, 21:17-21:32 UTC): k3x smoke
# (first row, cold) and the one-load V3/k3x bracket (476 s). Packet191: smoke ~313 s (same storage and request mix), bracket ~480 s
# (+ the sampled drain-time reads, <= 2 % of a sampled half); plus one 61 s drain spacing ~ 313+480+61 = 854 s (14.2 min).
HEADER='''# PROPOSAL ONLY (packet191). Never queued by preparation; the device-window driver decides.
# Lane B (two-card resident, whole host: PAUSE-A stays during both rows). The owner's endpoints on the lane-B cards must be
# stopped by the window operator first, and only after `lanequeue.py plan --lane B` passes on the live queue.
# Packet191 = a MEASUREMENT on the k3x record line (packet190 record 62.345282 tok/s): the record k3x selection unchanged plus
# packet77-style per-class site instrumentation on BOTH ranks as an in-load view key sites=off|on. Coordinator ruling (lever
# synthesis 4, 2026-10-22): "both ranks are 99.3% busy per hit and every kernel class sits at its ledger floor; the only family that
# can still reach +2% is per-layer kernel cost on both ranks (+1.32% per 0.01 ms per GDN layer; +2% needs 15.1 us per GDN layer,
# +0.5% needs 3.8 us)". sites=on records, in the sampled halves (fixtures 9-16, 57-64, 105-112), every kernel event's device
# timestamps (read on the host at the half's own final drain, as timing=class does) with its site label; sites=off is the record
# path byte for byte (CPU canonical transcripts identical; k3x-off adds only the explicit key). No new kernel, no device readback.
# Rebuilt entry TUs (entry-main, p49d_submit, s1_submit) over the 78 pinned parent objects; storage, census and memory plan are
# packet188/189's (production-shape startup identical; sites=on adds 0 device bytes).
# Rows (row 1 depends on row 0; same lane): 0 k3x-on smoke 12 x 64 + incident64 (exact, first-request data proof, site rows on both
# ranks) ~313 s; 1 one-load bracket off/on/off/on/off (k3x-off loaded; sites switches in-load) 5 x 12 x 128 ~480 s; watchdog 3600 s
# each; writes 240 MB per view (bracket 1.2 GB). Total under 15 min.
# Report (row 1 summary `s191_report`, or v5/s191_report.py over rows 0..1): per rank, per phase, per class: ms/half, us per GDN and
# QSA layer, excess over the 537 GB/s copy floor and over packet110; lever-eligible by excess iff >= 15.1 us/GDN layer on BOTH ranks
# (3.8 us screen) with the DO-NOT-REPEAT closures named and whether an open mechanism remains. Kill rules: any view not 13/13 exact or
# proposals/acceptance differ; off drift > 0.5%; on/off < 0.93 (table withheld, never ratio-corrected: packet128); class sums vs
# layer_body/half_completion > 10%. Never a speed result, never a record row.
# Memory (full-shape census, = packet188/189): rank 0 31,374,119,922 B (headroom 838,134,798 B under the 32,212,254,720 B arena limit),
# rank 1 31,581,735,626 B (headroom 630,519,094 B); pinned kernel-io 86,016 + 73,728 B (host); sites=on delta 0 B per rank.
# Host admission: 108,797,048,558 B (= packet189's k3x rows), plus the queue's 1 GiB at START.
'''

def output(index):
 from p191_v5_compare import row_output
 return row_output(index,'B')

def job(index):
 return f'packet191-{ROWS[index]["name"]}-B'

def proposal(index):
 r=ROWS[index];views=5 if r['kind']=='bracket' else 1
 row=dict(name=job(index),lane='B',argv=['/usr/bin/python3','-B',str((P/'bracket_job.py').relative_to(ROOT)),'--variant',r['variant'],'--kind',r['kind'],'--index',str(index),'--lane','B','--output',str(output(index)),'--fault-review','{REVIEW}','--authorized-device-window'],
  env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)),
  plan=dict(entry_rehearsal=dict(binaries=[dict(path=str((P/'build'/m/'own-rt-iq3').relative_to(ROOT)),sha256=sha(P/'build'/m/'own-rt-iq3')) for m in ('device','gnu-host')],
                                 preparation_probe_note='Production-shape startup of every registered selection on both ranks and both bracket start orders (real initialize/refresh_v3/capture/allocation/bracket_select/request_reset/DraftRuntime, numerical device addresses, no payload; captures and census identical to packet188/189; sites=on adds 0 device bytes; the site-row format proof on the real plan): v5/evidence/full-shape.json via v5/p191_v5_full_shape.py; k3x-off/k3x-on byte identity with the record k3x path: v5/evidence/k3-state.json. The shared prepare_probe has no two-rank v5 bracket entry; keep its WARN explicit.'),
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
 with tempfile.TemporaryDirectory(prefix='p191-plan-') as d:
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
  sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'p191_v5_queue_plan.py',*snapshot.glob('*.py')]}))
if __name__=='__main__':main()

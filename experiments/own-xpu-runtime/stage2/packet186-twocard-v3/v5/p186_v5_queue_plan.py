"""Lane-B proposal file and temporary plans only. Never edit live queue files.

One proposal file, ops/lane-queue/proposed-p186-two-card-B.txt: four rows, each depending on the previous
one: V3 smoke, fresh-load bundle-8 control, one-load U/V3/U/V3/U bracket, fresh-load bundle-8 control.
--stage writes the packet mirror before the seal; the plain run checks the mirror, plans all four rows
together on a temporary copy of the queue code (lanequeue.py plan --lane B --directory TMP), writes the
proposal file, and rehearses it with ops/rehearse_entry.py --json (and --report, recorded).
"""
import argparse,json,subprocess,sys,tempfile,shutil
from pathlib import Path
from p186_v5_build_engine import P,LOCAL,ROOT,sha,save,limits
from bracket_config import ROWS,EXPECTED,host_required
QUEUE=LOCAL.parents[1]/'ops/lane-queue'
NAME='proposed-p186-two-card-B.txt'
# Recorded row times on this lane and line (2026-10-22, window.json elapsed_seconds):
#  packet185 fresh-load rows (one load + one 12x128 view): 311.5 s first row of the window (cold page cache after the
#  endpoint stop), then 211.2 / 208.8 / 209.7 / 215.0 s (~217 s with the queue's start overhead);
#  packet183 smoke row 299.2 s (cold load 188.2 s + one 12x64 view 111.0 s); packet183 one-load bracket 479.7 s
#  (load/teardown 94.2 s + five 12x128 views 122.6 + 67.4 + 64.3 + 66.7 + 64.5 s), ~486 s with start overhead.
# Packet186: smoke ~300 s (first row, cold; the V3 load adds 2.26 GB of layer-24/25 weights on rank 0, a few seconds),
# control ~217 s, bracket ~486 s, control ~217 s; plus three 61 s drain spacings ~ 300+217+486+217+183 = 1,403 s (23.4 min).
HEADER='''# PROPOSAL ONLY (packet186). Never queued by preparation; the device-window driver decides.
# Lane B (two-card resident, whole host: PAUSE-A stays during all four rows). The owner's endpoints on the lane-B cards must be
# stopped by the window operator first, and only after `lanequeue.py plan --lane B` passes on the live queue.
# Packet186 = V3 (coordinator ruling 2026-10-22 after packet185 V3 GO): full 248,320-row target head on rank 1 (no merge, no
# rank-0 suffix service), rank 0 runs the GDN layers 24-25 for the VERIFIED token in its draft-wait window (one boundary command
# after every rank-0 accept) and exports layer 25; rank 1 starts at layer 26; draft unchanged; bundled with packet153's static
# snapshot (A binds the emission under V3). Rebuilt entry TUs (entry-main, p49d_submit, s1_submit) over the 78 pinned parent
# objects; production selection = bundle 8 exactly (capture-identical to packet185 at production shape).
# Rows (each depends on the previous; same lane): 0 V3 smoke 12 x 64 + incident64 (exact, first-request data proof) ~300 s;
# 1 fresh-load bundle-8 control 12 x 128 ~217 s; 2 one-load bracket U/V3/U/V3/U (U = un-split control, V3 = boundary+static)
# 5 x 12 x 128 ~486 s; 3 fresh-load bundle-8 control ~217 s; watchdog 3600 s each; writes 240 MB per view (bracket 1.2 GB).
# Decision (row 3 summary `s186_decision`, or v5/s186_decision.py over rows 0..3): screen winner iff the slower V3 view >=
# 1.005 x every control view (2 split + 3 U), every view exact with identical proposals, drift <= 3 %; chain rule iff also
# >= 1.02 x the faster split control AND >= 59.974 tok/s (1.02 x 58.798109). Never a record row (record = fresh chain, README).
# Memory (full-shape census): rank 0 +2,100,819,444 B (layers 24-25 +2,258,141,716 B, suffix head -157,322,272 B; arena
# headroom 1.97 GB of 4.07), rank 1 +155,750,384 B (headroom 0.63 GB of 0.79). Host admission: bundle 8 105,411,248,128 B,
# V3 rows 107,667,817,956 B (+ device delta shadow), plus the queue's 1 GiB at START.
'''

def output(index):
 from p186_v5_compare import row_output
 return row_output(index,'B')

def job(index):
 return f'packet186-{ROWS[index]["name"]}-B'

def proposal(index):
 r=ROWS[index];views=5 if r['kind']=='bracket' else 1
 row=dict(name=job(index),lane='B',argv=['/usr/bin/python3','-B',str((P/'bracket_job.py').relative_to(ROOT)),'--variant',r['variant'],'--kind',r['kind'],'--index',str(index),'--lane','B','--output',str(output(index)),'--fault-review','{REVIEW}','--authorized-device-window'],
  env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)),
  plan=dict(entry_rehearsal=dict(binaries=[dict(path=str((P/'build'/m/'own-rt-iq3').relative_to(ROOT)),sha256=sha(P/'build'/m/'own-rt-iq3')) for m in ('device','gnu-host')],
                                 preparation_probe_note='Production-shape startup of every selection on both ranks and both bracket start orders (real initialize/refresh_v3/capture/allocation/bracket_select/request_reset/DraftRuntime, numerical device addresses, no payload): v5/evidence/full-shape.json via v5/p186_v5_full_shape.py; V3 state correctness: v5/evidence/v3-state.json. The shared prepare_probe has no two-rank v5 bracket entry; keep its WARN explicit.'),
            host_required_available_bytes=host_required(r['variant']),expected_seconds=EXPECTED[index],watchdog_seconds=3600,planned_writes=240_000_000*views))
 if index:row['depends_on']=[job(index-1)]
 return row

def content():
 return HEADER+''.join(json.dumps(proposal(i))+'\n' for i in range(len(ROWS)))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--stage',action='store_true');a=ap.parse_args()
 limits();snapshot=LOCAL/'lineage-inputs/queue';snapshot.mkdir(exist_ok=True)
 for src in QUEUE.glob('*.py'):shutil.copy2(src,snapshot/src.name)
 mirror=LOCAL/'proposals'/NAME;text=content()
 if a.stage:
  for old in (LOCAL/'proposals').glob('*.txt'):old.unlink()
  mirror.parent.mkdir(exist_ok=True);mirror.write_text(text);return
 assert mirror.read_text()==text,'stage proposals before sealing'
 with tempfile.TemporaryDirectory(prefix='p186-plan-') as d:
  tmp=Path(d)
  for src in snapshot.glob('*.py'):shutil.copy2(src,tmp/src.name)
  (tmp/'queue-B.txt').write_text(text)
  cmd=[sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane','B','--directory',str(tmp)]
  log=P/'evidence/plan-B.log'
  with log.open('w') as out:r=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,timeout=600)
  assert r.returncode==0,log.read_text()[-8000:]
 live=QUEUE/NAME;live.write_text(text)
 # Gating rehearsal: entry imports, native entries and packaging checks of all four rows.
 r=subprocess.run([sys.executable,'-B',str(QUEUE.parent/'rehearse_entry.py'),str(live),'--json'],cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
 (P/'evidence/rehearse.log').write_text(r.stdout+r.stderr)
 assert r.returncode==0,r.stdout[-6000:]+r.stderr[-3000:]
 rehearsal=json.loads(r.stdout);assert rehearsal['passed'] and len(rehearsal['jobs'])==len(ROWS)
 # Recorded (not gating): rehearse_entry --report synthesizes smoke/bracket reports for a v5 screen.main entry; packet186's
 # entry binds kind/variant/index to the row registry, so synthetic kinds other than the row's own refuse at the entry
 # parser. The packet's own report gate (v5/report_gate.py) runs the real bracket_job --report-only path for all rows.
 r2=subprocess.run([sys.executable,'-B',str(QUEUE.parent/'rehearse_entry.py'),str(live),'--report','--json'],cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=900)
 (P/'evidence/rehearse-report.log').write_text(r2.stdout+r2.stderr)
 try:shared=json.loads(r2.stdout)
 except ValueError:shared=dict(passed=False,jobs=[],unparsed=True)
 for j in shared.get('jobs',[]):assert all(b['passed'] for b in j.get('binaries',[])),j.get('job')
 rehearsal['shared_report_rehearsal']=dict(passed=shared.get('passed'),returncode=r2.returncode,
  kinds=[dict(job=j.get('job'),report=[dict(kind=k.get('kind'),passed=k.get('passed')) for k in j.get('report',{}).get('kinds',[])]) for j in shared.get('jobs',[])],
  note='informational: v5/report_gate.py covers the real report path for all four rows on both lanes',log=str((P/'evidence/rehearse-report.log').relative_to(ROOT)))
 receipt=P/'evidence/rehearse.json';save(receipt,rehearsal)
 for src in snapshot.glob('*.py'):assert sha(src)==sha(QUEUE/src.name),'queue changed during planning'
 rows=[dict(job=proposal(i)['name'],unit='screen-'+proposal(i)['name']+'.service',expected_seconds=EXPECTED[i]) for i in range(len(ROWS))]
 save(P/'evidence/queue-plan.json',dict(passed=True,device_executed=False,live_queue_modified=False,queued=False,proposal_name=str(live.relative_to(ROOT)),sha256=sha(live),
  mirror=str(mirror.relative_to(ROOT)),log=str(log.relative_to(ROOT)),log_sha256=sha(log),rehearsal=str(receipt.relative_to(ROOT)),rehearsal_sha256=sha(receipt),rows=rows,
  sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'p186_v5_queue_plan.py',*snapshot.glob('*.py')]}))
if __name__=='__main__':main()

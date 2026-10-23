"""Lane-B proposal file and temporary plans only. Never edit live queue files.

One proposal file, ops/lane-queue/proposed-p194-two-card-B.txt: two rows, the second depending on the first:
k3x-diet smoke, one-load k3x/k3x-diet/k3x/k3x-diet/k3x bracket (the record k3x line is the in-load control).
--stage writes the packet mirror before the seal; the plain run checks the mirror, plans both rows
together on a temporary copy of the queue code (lanequeue.py plan --lane B --directory TMP), writes the
proposal file, and rehearses it with ops/rehearse_entry.py --json (and --report, recorded).
"""
import argparse,json,subprocess,sys,tempfile,shutil
from pathlib import Path
from p194_v5_build_engine import P,LOCAL,ROOT,sha,save,limits
from bracket_config import ROWS,EXPECTED,host_required
QUEUE=LOCAL.parents[1]/'ops/lane-queue'
NAME='proposed-p194-two-card-B.txt'
# Recorded row times on this lane: packet189 (lanequeue-B36, 2026-10-22): k3x smoke (first row, cold) ~313 s, one-load V3/k3x bracket 475.7 s.
# Packet194: smoke ~313 s (same storage and request mix), bracket ~476 s; plus one 61 s drain spacing ~ 313+476+61 = 850 s (14.2 min).
HEADER='''# PROPOSAL ONLY (packet194). Never queued by preparation; the device-window driver decides.
# Lane B (two-card resident, whole host: PAUSE-A stays during both rows). The owner's endpoints on the lane-B cards must be
# stopped by the window operator first, and only after `lanequeue.py plan --lane B` passes on the live queue.
# Packet194 = packet193's exact gate/up instruction diet (exp-diet, p193diet::GateUp, header pinned aab37609...) integrated into the
# k3x record engine (packet189 87eec645... -> packet194) behind the in-load key expert_gateup=production|diet (k3-storage key; absent =
# production, so the 19-key record selection c5443bbf... loads unchanged). Coordinator ruling 2026-10-23: "packet193 measured the exact
# gate/up instruction diet at 0.78x production cold and 0.77x warm on card 2, byte-identical on every claimed stratum. Integrate
# `exp-diet` into the k3x record engine as an in-load key `expert_gateup=production|diet` (production = byte-for-byte the record
# kernel), prove engine-level exactness on CPU, and screen it on lane B with a one-load bracket k3x / k3x+diet / k3x / k3x+diet / k3x."
# Rebuilt TUs: entry-main, p49d_submit, s1_submit and p49d_expert_submit (the one TU the kernel touches) over the 76 remaining pinned parent
# objects; the 25 inherited device kernels are opcode- and canonically identical to packet103's pinned object (kernel-identity.json); the
# diet is byte-identical to production through the real dispatch on GNU and Intel host twins with packet162b's real rows (diet-fixture.json).
# Storage, census and memory plan are packet188/189's (production-shape startup identical; the diet adds 0 B).
# Rows (row 1 depends on row 0; same lane): 0 k3x-diet smoke 12 x 64 + incident64 (exact, first-request data proof) ~313 s;
# 1 one-load bracket k3x/k3x-diet/k3x/k3x-diet/k3x (20-key selections; k3x = the record kernel) 5 x 12 x 128 ~476 s;
# watchdog 3600 s each; writes 240 MB per view (bracket 1.2 GB); total ~14 min with the 61 s drain spacing.
# Decision (row 1 summary `s194_decision`, or v5/s194_decision.py over rows 0..1): screen winner iff the slower k3x-diet view >= 1.005 x every
# in-load k3x view, every view exact with identical proposals and acceptance, k3x drift <= 0.5 %, per-layer gate/up saving >= 5 us on both
# ranks (host scopes: rank 0 A/24, rank 1 B/21); chain rule iff also >= 1.02 x every k3x view AND >= 63.59218754283864 tok/s (1.02 x
# 62.345281904743764). Priced (lever synthesis 4, +1.32 % per 0.01 ms per GDN layer): +1.4 % (10.8 us warm) to +2.1 % (15.9 us cold).
# Never a record row (record = fresh chain from packet190 with the k3x-diet selection and this engine, README).
# Memory (full-shape census, = packet188/189): k3 storage rank 0 31,374,119,922 B (headroom 838,134,798 B under the 32,212,254,720 B arena limit),
# rank 1 31,581,735,626 B (headroom 630,519,094 B); pinned kernel-io 86,016 + 73,728 B (host); diet delta 0 B per rank.
# Host admission: 108,797,048,558 B (= packet189's k3x rows), plus the queue's 1 GiB at START.
'''

def output(index):
 from p194_v5_compare import row_output
 return row_output(index,'B')

def job(index):
 return f'packet194-{ROWS[index]["name"]}-B'

def proposal(index):
 r=ROWS[index];views=5 if r['kind']=='bracket' else 1
 row=dict(name=job(index),lane='B',argv=['/usr/bin/python3','-B',str((P/'bracket_job.py').relative_to(ROOT)),'--variant',r['variant'],'--kind',r['kind'],'--index',str(index),'--lane','B','--output',str(output(index)),'--fault-review','{REVIEW}','--authorized-device-window'],
  env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)),
  plan=dict(entry_rehearsal=dict(binaries=[dict(path=str((P/'build'/m/'own-rt-iq3').relative_to(ROOT)),sha256=sha(P/'build'/m/'own-rt-iq3')) for m in ('device','gnu-host')],
                                 preparation_probe_note='Production-shape startup of every registered selection on both ranks and both bracket start orders (real initialize/refresh_v3/capture/allocation/bracket_select/prepare_commands dispatch/request_reset/DraftRuntime, numerical device addresses, no payload; captures and census identical to packet189 for the production views, the diet changes exactly the exp-halfcache gate/up kernels, 0 B): v5/evidence/full-shape.json via v5/p194_v5_full_shape.py; diet exactness through the real dispatch on real rows: v5/evidence/diet-fixture.json; per-kernel device-code identity: v5/evidence/kernel-identity.json; k3x state and key identity: v5/evidence/k3-state.json. The shared prepare_probe has no two-rank v5 bracket entry; keep its WARN explicit.'),
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
 with tempfile.TemporaryDirectory(prefix='p194-plan-') as d:
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
  sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'p194_v5_queue_plan.py',*snapshot.glob('*.py')]}))
if __name__=='__main__':main()

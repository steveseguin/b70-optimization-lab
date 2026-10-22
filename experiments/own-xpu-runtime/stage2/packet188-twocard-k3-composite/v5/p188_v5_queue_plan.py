"""Lane-B proposal file and temporary plans only. Never edit live queue files.

One proposal file, ops/lane-queue/proposed-p188-two-card-B.txt: three rows, each depending on the previous
one: k3+trims smoke, fresh-load V3 control (packet187's record selection), one-load V3/k3+trims/V3/k3+trims/V3 bracket.
--stage writes the packet mirror before the seal; the plain run checks the mirror, plans all three rows
together on a temporary copy of the queue code (lanequeue.py plan --lane B --directory TMP), writes the
proposal file, and rehearses it with ops/rehearse_entry.py --json (and --report, recorded).
"""
import argparse,json,subprocess,sys,tempfile,shutil
from pathlib import Path
from p188_v5_build_engine import P,LOCAL,ROOT,sha,save,limits
from bracket_config import ROWS,EXPECTED,host_required
QUEUE=LOCAL.parents[1]/'ops/lane-queue'
NAME='proposed-p188-two-card-B.txt'
# Recorded row times on this lane (2026-10-22, window.json elapsed_seconds):
#  packet186 rows (lanequeue-B34, 16:09-16:34 UTC): V3 smoke (first row, cold) 278.3 s, fresh bundle-8 controls 209.6 /
#  215.7 s, one-load U/V3/U/V3/U bracket 475.7 s; packet185 fresh views 209-215 s (first row of a window 311.5 s).
# Packet188: smoke ~285 s (first row, cold; the k3 storage adds 1.13 GB of layer-26 weights on rank 0), fresh V3 control
# ~213 s, bracket ~480 s; plus two 61 s drain spacings ~ 285+213+480+122 = 1,100 s (18.3 min).
HEADER='''# PROPOSAL ONLY (packet188). Never queued by preparation; the device-window driver decides.
# Lane B (two-card resident, whole host: PAUSE-A stays during all three rows). The owner's endpoints on the lane-B cards must be
# stopped by the window operator first, and only after `lanequeue.py plan --lane B` passes on the live queue.
# Packet188 = k3 + trims on the V3 record line (coordinator ruling 2026-10-22: the V3 ruling on packet177 row 2 extends to a
# third boundary layer). GDN layer 26 joins the verified-token boundary on rank 0 (rank0_layers 0-26, boundary rank0-k3; rank 1
# starts at QSA layer 27); trims kernel_io=kernel (per-interval synchronous copies as compute kernels, folded readbacks) and
# rank0_prepare=async (rank 0 stages its inputs with no host wait). Rebuilt entry TUs (entry-main, p49d_submit, s1_submit) over
# the 78 pinned parent objects; packet187's V3 selection is capture- and census-identical to packet186 at production shape.
# Rows (each depends on the previous; same lane): 0 k3+trims smoke 12 x 64 + incident64 (exact, first-request data proof) ~285 s;
# 1 fresh-load V3 control (packet187 record selection) 12 x 128 + incident64 ~213 s; 2 one-load bracket
# V3/k3+trims/V3/k3+trims/V3 (V3 = k3 storage, boundary rank0, trims off) 5 x 12 x 128 ~480 s; watchdog 3600 s each;
# writes 240 MB per view (bracket 1.2 GB).
# Decision (row 2 summary `s188_decision`, or v5/s188_decision.py over rows 0..2): screen winner iff the slower k3+trims view
# >= 1.005 x every V3 view (fresh + 3 in-load), every view exact with identical proposals, V3 drift <= 3 %; chain rule iff
# also >= 1.02 x every V3 view AND >= 61.873 tok/s (1.02 x 60.659520). Kill rules recorded (k3 hit saving < 0.25 ms,
# Bd > D on > 5 % of hits, trims remove < 0.105 ms of A). Never a record row (record = fresh chain, README).
# Memory (full-shape census): k3 storage rank 0 +1,129,070,858 B over V3 (31,374,119,922 B; headroom 838,134,798 B under the
# 32,212,254,720 B arena limit), rank 1 unchanged (31,581,735,626 B, headroom 630,519,094 B); pinned kernel-io 86,016 + 73,728 B (host).
# Host admission: V3 row 107,667,817,956 B; k3 rows 108,797,048,558 B (+ layer-26 shadow + staging), plus the queue's 1 GiB at START.
'''

def output(index):
 from p188_v5_compare import row_output
 return row_output(index,'B')

def job(index):
 return f'packet188-{ROWS[index]["name"]}-B'

def proposal(index):
 r=ROWS[index];views=5 if r['kind']=='bracket' else 1
 row=dict(name=job(index),lane='B',argv=['/usr/bin/python3','-B',str((P/'bracket_job.py').relative_to(ROOT)),'--variant',r['variant'],'--kind',r['kind'],'--index',str(index),'--lane','B','--output',str(output(index)),'--fault-review','{REVIEW}','--authorized-device-window'],
  env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)),
  plan=dict(entry_rehearsal=dict(binaries=[dict(path=str((P/'build'/m/'own-rt-iq3').relative_to(ROOT)),sha256=sha(P/'build'/m/'own-rt-iq3')) for m in ('device','gnu-host')],
                                 preparation_probe_note='Production-shape startup of every selection on both ranks and both bracket start orders (real initialize/refresh_v3/capture/allocation/bracket_select/request_reset/DraftRuntime, numerical device addresses, no payload): v5/evidence/full-shape.json via v5/p188_v5_full_shape.py; k3 state correctness and trim byte identity: v5/evidence/k3-state.json. The shared prepare_probe has no two-rank v5 bracket entry; keep its WARN explicit.'),
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
 with tempfile.TemporaryDirectory(prefix='p188-plan-') as d:
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
  sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'p188_v5_queue_plan.py',*snapshot.glob('*.py')]}))
if __name__=='__main__':main()

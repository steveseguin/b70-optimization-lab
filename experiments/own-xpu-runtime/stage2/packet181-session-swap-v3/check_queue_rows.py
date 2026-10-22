"""Run the real shared CPU-only planner and rehearsal against proposal copies, never a live queue.

Order: CPU gates -> package_rows.py (seal + proposal) -> validate_flags.py -> check_queue_rows.py
(plan + rehearse) -> final_checks.py -> final_checks.py --ready (last mutation).
Refuses unless one-card/seal.json is current, the private plan queue equals the proposal and no
READY exists (a stale READY's hash links would join the planner's pin closure); final_checks
--ready pin-guards the new READY's links.
"""
import json,subprocess
from pathlib import Path
from build_engine import P,ROOT,limits,sha,save
limits();ops=ROOT/'experiments/own-xpu-runtime/ops'
for name,lane,short in [('one-card','A','one')]:
 assert not any((d/'READY-FOR-DEVICE.json').exists() for d in (P,P/name)),'withdraw stale READY first; final_checks --ready rewrites it last'
 seal=P/name/'seal.json';assert seal.is_file(),'seal.json missing: run package_rows.py first'
 assert all(sha(P/name/leaf)==h for leaf,h in json.loads(seal.read_text())['files'].items()),'seal.json stale: rerun package_rows.py'
 assert (P/'evidence'/f'queue-plan-{name}-{lane}'/f'queue-{lane}.txt').read_bytes()==(ops/'lane-queue'/f'proposed-p181-{name}-{lane}.txt').read_bytes(),'plan queue differs from proposal: rerun package_rows.py'
 for kind,cmd in [('plan',['/usr/bin/python3','-B',str(ops/'lane-queue/lanequeue.py'),'plan','--lane',lane,'--directory',str(P/'evidence'/f'queue-plan-{name}-{lane}')]),('rehearse',['/usr/bin/python3','-B',str(ops/'rehearse_entry.py'),str(ops/'lane-queue'/f'proposed-p181-{name}-{lane}.txt'),'--report','--json'])]:
  output=P/'evidence'/f'{kind}-{short}-{lane}.{ "json" if kind=="rehearse" else "log"}'
  with output.open('w')as out,output.with_suffix('.stderr.log').open('w')as err:cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=out,stderr=err)
  assert cp.returncode==0,(kind,name,lane,output)
  if kind=='rehearse':assert json.loads(output.read_text())['passed']
  else:
   rows=[json.loads(line) for line in output.read_text().splitlines() if line.startswith('{')]
   assert len(rows)==2 and all(r['plan']=='passed' for r in rows),rows
  print(name,lane,kind,'PASS',flush=True)

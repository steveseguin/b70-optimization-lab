"""Run real shared CPU-only plans/rehearsals against proposal copies, never queue.

Order: CPU gates -> package_rows (seal + proposal) -> check_queue_rows (plan +
rehearse) -> final_checks --ready. The seal must exist and match the proposal,
and READY must be absent, before anything is planned.
"""
import json,subprocess
from pathlib import Path
from build_engine import P,ROOT,limits,sha,save
limits();ops=ROOT/'experiments/own-xpu-runtime/ops'
for name,lane,short in [('one-card','A','one')]:
 seal=json.loads((P/name/'seal.json').read_text());proposal=ops/'lane-queue'/f'proposed-p178-{name}-{lane}.txt'
 assert not (P/name/'READY-FOR-DEVICE.json').exists() and not (P/'READY-FOR-DEVICE.json').exists(),'READY is written after check_queue_rows'
 assert all(sha(P/name/k)==h for k,h in seal['files'].items()),'seal stale; rerun package_rows'
 rows=[json.loads(s) for s in proposal.read_text().splitlines() if s.startswith('{')]
 assert rows and all(b['sha256']==seal['files']['build/device/own-rt-iq3'] for r in rows for b in r['plan']['entry_rehearsal']['binaries']),'proposal does not match seal'
 assert (P/'evidence'/f'queue-plan-{name}-{lane}'/f'queue-{lane}.txt').read_text()==proposal.read_text(),'plan queue copy differs from proposal'
 for kind,cmd in [('plan',['/usr/bin/python3','-B',str(ops/'lane-queue/lanequeue.py'),'plan','--lane',lane,'--directory',str(P/'evidence'/f'queue-plan-{name}-{lane}')]),('rehearse',['/usr/bin/python3','-B',str(ops/'rehearse_entry.py'),str(ops/'lane-queue'/f'proposed-p178-{name}-{lane}.txt'),'--report','--json'])]:
  output=P/'evidence'/f'{kind}-{short}-{lane}.{ "json" if kind=="rehearse" else "log"}'
  with output.open('w')as out,output.with_suffix('.stderr.log').open('w')as err:cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=out,stderr=err)
  assert cp.returncode==0,(kind,name,lane,output)
  if kind=='rehearse':assert json.loads(output.read_text())['passed']
  else:assert all(json.loads(line)['plan']=='passed'for line in output.read_text().splitlines()if line.startswith('{'))
  print(name,lane,kind,'PASS',flush=True)

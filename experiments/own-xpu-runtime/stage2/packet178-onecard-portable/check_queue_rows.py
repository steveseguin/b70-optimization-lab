"""Run real shared CPU-only plans/rehearsals against proposal copies, never queue."""
import json,subprocess
from pathlib import Path
from build_engine import P,ROOT,limits,sha,save
limits();ops=ROOT/'experiments/own-xpu-runtime/ops'
for name,lane,short in [('one-card','A','one')]:
 for kind,cmd in [('plan',['/usr/bin/python3','-B',str(ops/'lane-queue/lanequeue.py'),'plan','--lane',lane,'--directory',str(P/'evidence'/f'queue-plan-{name}-{lane}')]),('rehearse',['/usr/bin/python3','-B',str(ops/'rehearse_entry.py'),str(ops/'lane-queue'/f'proposed-p178-{name}-{lane}.txt'),'--report','--json'])]:
  output=P/'evidence'/f'{kind}-{short}-{lane}.{ "json" if kind=="rehearse" else "log"}'
  with output.open('w')as out,output.with_suffix('.stderr.log').open('w')as err:cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=out,stderr=err)
  assert cp.returncode==0,(kind,name,lane,output)
  if kind=='rehearse':assert json.loads(output.read_text())['passed']
  else:assert all(json.loads(line)['plan']=='passed'for line in output.read_text().splitlines()if line.startswith('{'))
  print(name,lane,kind,'PASS',flush=True)

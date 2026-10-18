"""One diagnostic 12x64 load, shared fault/drain/lease policy unchanged."""
import argparse,sys,shutil,subprocess
from pathlib import Path
from bootstrap import P,WRAPPER,install
install()
import screen128 as screen
from common import require,read,verify_map,ROOT
from analyze import summarize
VIEW=P/'selections/bundle7-attribution'
OUTPUT=P/'evidence/device-B'
def command(args,identity,manifest):
 return ['/usr/bin/python3','-B',str(P/'worker.py'),'--identity',str(args.output/'identity.json'),'--output',str(args.output/'run'),'--seconds','1440']
def main(argv=None):
 ap=argparse.ArgumentParser();ap.add_argument('--plan',action='store_true');ap.add_argument('--lane',choices=['B'],default='B');ap.add_argument('--output',type=Path,default=OUTPUT);ap.add_argument('--fault-review');ap.add_argument('--authorized-device-window',action='store_true');a=ap.parse_args(argv)
 require(shutil.disk_usage('/').free>=25_000_000_000,'root free below 25 GB')
 gate=read(P/'evidence/argument-gate.json');require(gate['passed'] and gate['native_exec_intercepted'] and not gate['device_executed'],'CPU argument gate required');verify_map(ROOT,gate['sources'])
 if not a.plan:
  for leaf in ('queue-gate.json','launch-limits.json','python-tests.json','recorder-gate.json'):
   proof=read(P/'evidence'/leaf);require(proof['passed'] and not proof['device_executed'],'CPU readiness gate required: '+leaf);verify_map(ROOT,proof['sources'])
 cmd=['--profile','tp2','--lane','B','--placement','1','--timing','attribution','--lineage',str(VIEW),'--seal',str(VIEW/'screen-seal.json'),'--output',str(a.output)]
 if a.plan:cmd+=['--plan']
 if a.fault_review:cmd+=['--fault-review',a.fault_review]
 if a.authorized_device_window:cmd+=['--authorized-device-window']
 previous,summary=screen.command,screen.summary;screen.command=command;screen.summary=summarize
 try:result=screen.main(cmd)
 finally:screen.command=previous;screen.summary=summary
 if result==0 and not a.plan:
  # screen.main has drained the worker and released the lane lease. The CPU
  # report gets its own limits; the native-launch process never installs caps.
  subprocess.run(['/usr/bin/nice','-n','19','/usr/bin/taskset','-c','8-15,24-31',
   '/usr/bin/python3','-B',str(P/'analyze.py'),'--output',str(a.output)],stdin=subprocess.DEVNULL,check=True)
 return result
if __name__=='__main__':raise SystemExit(main())

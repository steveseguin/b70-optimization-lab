"""Coordinator-only one-load B bracket, blocked until micro and CPU evidence pass."""
import argparse, json, subprocess, sys
from pathlib import Path
from common import HERE,require,read,sha

def micro_winner():
 # Root gate verifies its frozen v4 wrappers in a clean interpreter. Importing
 # it here would collide with this v5 wrapper's common/screen/cpu_seal modules.
 result=subprocess.run(['/usr/bin/python3','-B',str(HERE.parent/'micro_gate.py'),'--require-qualified'],
   stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
 require(result.returncode==0,'two-process micro qualification refused: '+result.stderr.strip())
 row=json.loads(result.stdout)
 require(row.get('passed') is True and row.get('qualified')==['p122'],'micro candidate not qualified')
 return 'p122'

def main(argv=None):
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--lane',choices=('B',),required=True)
 ap.add_argument('--output',type=Path,required=True)
 ap.add_argument('--fault-review',type=Path)
 ap.add_argument('--authorized-device-window',action='store_true')
 ap.add_argument('--plan',action='store_true')
 a=ap.parse_args(argv)
 from cpu_seal import verify
 verify()
 pending_plan=a.plan and not (HERE.parent/'evidence/micro-qualification.json').is_file()
 if pending_plan:
  print(json.dumps(dict(device_executed=False,micro_qualified=False,conditional_plan=True,launch_eligible=False,reason='two-process micro qualification pending')))
 else:
  winner=micro_winner()
  require(read(HERE/'lineage/candidate.json')['choices']['draft_hc_schedule']==winner,'CPU-sealed candidate differs from earliest qualifying micro design')
 import screen
 args=['--lane','B','--placement','1','--lineage',str(HERE/'lineage'),'--bracket',str(HERE/'configs/bracket.json'),'--output',str(a.output)]
 if a.plan:args+=['--plan']
 else:
  require(a.authorized_device_window and a.fault_review,'coordinator authorization and review required')
  args+=['--authorized-device-window','--fault-review',str(a.fault_review)]
 return screen.main(args)

if __name__=='__main__':raise SystemExit(main())

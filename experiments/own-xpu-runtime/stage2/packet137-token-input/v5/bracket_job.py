"""Coordinator-only candidate smoke, then one-load exact timing bracket."""
import argparse,json
from pathlib import Path
from common import HERE,require,read,sha

def smoke_gate():
 from packet137_report import load
 row=load(HERE/'evidence/device-smoke-137b-B')
 require(row.get('kind')=='smoke' and row.get('passed') is True and row.get('request_count')==12 and row.get('max_new')==64,'twelve-prompt exact smoke required')
 return row

def main(argv=None):
 from launch_env import apply
 apply()
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--kind',choices=('smoke','bracket'),required=True)
 ap.add_argument('--lane',choices=('A','B'),required=True)
 ap.add_argument('--output',type=Path,required=True)
 ap.add_argument('--fault-review',type=Path)
 ap.add_argument('--authorized-device-window',action='store_true')
 ap.add_argument('--plan',action='store_true');a=ap.parse_args(argv)
 from cpu_seal import verify
 verify()
 if a.plan:
  from preplan import verify as verify_preplan
  verify_preplan()
 if not a.plan:
  from readiness import verify_ready
  verify_ready()
 if a.kind=='bracket':
  if not a.plan:smoke_gate()
 import screen
 args=['--lane',a.lane,'--placement','1','--lineage',str(HERE/'lineage'),'--bracket',str(HERE/'configs'/(a.kind+'.json')),'--output',str(a.output)]
 if a.plan:args+=['--plan']
 else:
  require(a.authorized_device_window and a.fault_review,'coordinator authorization and review required')
  args+=['--authorized-device-window','--fault-review',str(a.fault_review)]
 return screen.main(args)
if __name__=='__main__':raise SystemExit(main())

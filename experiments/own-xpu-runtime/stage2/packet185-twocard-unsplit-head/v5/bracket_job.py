"""Coordinator-only fresh-load view row (packet185: one load, one view per queue row); never queues."""
import argparse
from pathlib import Path
from common import HERE,require
from bracket_config import VALUES,VIEWS
def main(argv=None):
 from launch_env import apply
 apply()
 ap=argparse.ArgumentParser();ap.add_argument('--variant',choices=VALUES,required=True);ap.add_argument('--kind',choices=('view',),required=True);ap.add_argument('--index',type=int,choices=range(5),required=True);ap.add_argument('--lane',choices=('A','B'),required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--fault-review',type=Path);ap.add_argument('--authorized-device-window',action='store_true');ap.add_argument('--plan',action='store_true');ap.add_argument('--report-only',action='store_true');a=ap.parse_args(argv)
 require(VIEWS[a.index]==a.variant,'packet185 view order is production/unsplit/production/unsplit/production')
 if a.report_only:
  require(not a.plan and not a.authorized_device_window and a.fault_review is None,'offline report cannot authorize a device')
  from report_recovery import recover
  return recover(a)
 from cpu_seal import verify
 verify()
 from readiness import verify_ready
 verify_ready(preplan=a.plan,variant=a.variant,kind=a.kind,lane=a.lane,index=a.index)
 import screen
 args=['--lane',a.lane,'--placement','1','--lineage',str(HERE/'lineage'/a.variant),'--bracket',str(HERE/'configs'/('view'+str(a.index)+'-'+a.variant+'.json')),'--output',str(a.output)]
 if a.plan:args+=['--plan']
 else:
  require(a.authorized_device_window and a.fault_review,'coordinator authorization and review required')
  args+=['--authorized-device-window','--fault-review',str(a.fault_review)]
 return screen.main(args)
if __name__=='__main__':raise SystemExit(main())

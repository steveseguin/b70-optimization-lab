"""Coordinator-only packet188 row: k3+trims smoke, fresh-load V3 control view, or the V3/k3+trims one-load bracket; never queues."""
import argparse
from pathlib import Path
from common import HERE,require
from bracket_config import VALUES,KINDS,ROWS,row
def main(argv=None):
 from launch_env import apply
 apply()
 ap=argparse.ArgumentParser();ap.add_argument('--variant',choices=VALUES,required=True);ap.add_argument('--kind',choices=KINDS,required=True);ap.add_argument('--index',type=int,choices=range(len(ROWS)),required=True);ap.add_argument('--lane',choices=('A','B'),required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--fault-review',type=Path);ap.add_argument('--authorized-device-window',action='store_true');ap.add_argument('--plan',action='store_true');ap.add_argument('--report-only',action='store_true');a=ap.parse_args(argv)
 r=row(a.index)
 require(r['kind']==a.kind and r['variant']==a.variant,'packet188 rows: 0 smoke k3trims, 1 view v3, 2 bracket v3k (V3/k3+trims/V3/k3+trims/V3)')
 if a.report_only:
  require(not a.plan and not a.authorized_device_window and a.fault_review is None,'offline report cannot authorize a device')
  from report_recovery import recover
  return recover(a)
 from cpu_seal import verify
 verify()
 from readiness import verify_ready
 verify_ready(preplan=a.plan,variant=a.variant,kind=a.kind,lane=a.lane,index=a.index)
 import screen
 args=['--lane',a.lane,'--placement','1','--lineage',str(HERE/'lineage'/a.variant),'--bracket',str(HERE/'configs'/r['config']),'--output',str(a.output)]
 if a.plan:args+=['--plan']
 else:
  require(a.authorized_device_window and a.fault_review,'coordinator authorization and review required')
  args+=['--authorized-device-window','--fault-review',str(a.fault_review)]
 return screen.main(args)
if __name__=='__main__':raise SystemExit(main())

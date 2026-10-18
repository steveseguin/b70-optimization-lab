"""Coordinator-only one-load bracket. Restore smoke must pass first."""
import argparse,json
from pathlib import Path
from common import HERE,require
def smoke_passed():
 from smoke_gate import verify
 return verify()
def main(argv=None):
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--lane',choices=('B',),required=True)
 ap.add_argument('--output',type=Path,required=True)
 ap.add_argument('--fault-review',type=Path)
 ap.add_argument('--authorized-device-window',action='store_true')
 ap.add_argument('--plan',action='store_true')
 ap.add_argument('--smoke',action='store_true')
 a=ap.parse_args(argv)
 from cpu_seal import verify
 verify()
 kind='smoke' if a.smoke else 'bracket'
 require(a.output.resolve()==HERE/'evidence'/('device-smoke-B' if a.smoke else 'device-v5-B'),'registered fresh output required')
 if not a.smoke:
  if a.plan and not (HERE/'evidence/device-smoke-B/window.json').exists():
   print(json.dumps(dict(device_executed=False,smoke_passed=False,conditional_plan=True,launch_eligible=False)))
  else:smoke_passed()
 import screen
 args=['--lane','B','--placement','1','--lineage',str(HERE/'lineage'),'--bracket',str(HERE/'configs'/(kind+'.json')),'--output',str(a.output)]
 if a.plan:args+=['--plan']
 else:
  require(a.authorized_device_window and a.fault_review,'coordinator authorization and review required')
  args+=['--authorized-device-window','--fault-review',str(a.fault_review)]
 return screen.main(args)
if __name__=='__main__':raise SystemExit(main())

"""Packet109 lane-B five-view one-load bracket; planning never launches."""
import argparse
from pathlib import Path
from common import HERE,require
import screen
def main(argv=None):
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--lane',choices=('A','B'),required=True)
 ap.add_argument('--output',type=Path,required=True)
 ap.add_argument('--fault-review',type=Path)
 ap.add_argument('--authorized-device-window',action='store_true')
 ap.add_argument('--plan',action='store_true')
 a=ap.parse_args(argv)
 from cpu_seal import verify
 verify();require(a.lane=='B','packet109 screen is lane B only')
 args=['--lane','B','--placement','1','--lineage',str(HERE/'lineage'),'--bracket',str(HERE/'configs/bracket.json'),'--output',str(a.output)]
 if a.plan:args+=['--plan']
 else:
  require(a.authorized_device_window and a.fault_review,'coordinator authorization and review required')
  args+=['--authorized-device-window','--fault-review',str(a.fault_review)]
 return screen.main(args)
if __name__=='__main__':raise SystemExit(main())

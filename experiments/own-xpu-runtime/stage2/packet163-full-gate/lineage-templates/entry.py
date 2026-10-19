"""One fresh model load: 512-input prefill, then every fixed realistic prompt."""
import argparse
from pathlib import Path

def main(argv=None):
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--lane',choices=('A','B'),required=True)
 ap.add_argument('--kind',choices=('full512','smoke','bracket'),default='full512',help='smoke/bracket accepted only by offline report compatibility tests')
 ap.add_argument('--output',type=Path,required=True)
 ap.add_argument('--reference',type=Path)
 ap.add_argument('--fault-review',type=Path)
 ap.add_argument('--authorized-device-window',action='store_true')
 ap.add_argument('--plan',action='store_true')
 args=ap.parse_args(argv)
 from cpu_seal import verify
 from readiness import verify_ready
 import screen
 verify();verify_ready(preplan=args.plan)
 command=['--lane',args.lane,'--kind',args.kind,'--output',str(args.output)]
 if args.reference:command+=['--reference',str(args.reference)]
 if args.plan:command+=['--plan']
 if args.fault_review:command+=['--fault-review',str(args.fault_review)]
 if args.authorized_device_window:command+=['--authorized-device-window']
 return screen.main(command)
if __name__=='__main__':raise SystemExit(main())

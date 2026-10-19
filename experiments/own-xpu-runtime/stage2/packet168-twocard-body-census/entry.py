"""Packet168 census admission. Incomplete native qualification refuses launch."""
import argparse
from pathlib import Path
def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--lane',choices=('A','B'),required=True)
    ap.add_argument('--kind',choices=('census','smoke','bracket'),default='census')
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--fault-review',type=Path)
    ap.add_argument('--authorized-device-window',action='store_true')
    ap.add_argument('--plan',action='store_true')
    a=ap.parse_args(argv)
    from cpu_seal import verify
    from readiness import verify_ready
    import screen
    verify();verify_ready(preplan=a.plan)
    command=['--lane',a.lane,'--kind',a.kind,'--output',str(a.output)]
    if a.plan:command+=['--plan']
    if a.fault_review:command+=['--fault-review',str(a.fault_review)]
    if a.authorized_device_window:command+=['--authorized-device-window']
    return screen.main(command)
if __name__=='__main__':raise SystemExit(main())

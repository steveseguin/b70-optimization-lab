"""Fixed first-use A/A smoke, then five-view packet91 bracket. Plan is CPU only."""
import argparse
from pathlib import Path
from common import HERE, read, require, sha
import screen

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--kind',choices=('smoke','bracket','attention'),required=True)
    ap.add_argument('--lane',choices=('A','B'),required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--fault-review',type=Path)
    ap.add_argument('--authorized-device-window',action='store_true')
    ap.add_argument('--plan',action='store_true')
    a=ap.parse_args(argv)
    from cpu_seal import verify
    verify()
    require(a.kind!='smoke' or a.lane=='B', 'first-use smoke is lane B only')
    if a.kind!='smoke' and not a.plan:
        from compare import load
        smoke=HERE/'evidence/p98c-smoke-B'
        result=load(smoke);window=read(smoke/'window.json')
        require(result['kind']=='smoke' and result['timing_equal_within_control_drift'] is True,
                'first-use route A/B/A smoke must pass before candidate bracket')
        require(len(result['views'])==3 and all(r['all_13_exact'] for r in result['views']), 'complete first-use smoke required')
        require(window['wrapper_seal_sha256']==sha(HERE/'placement-validation/wrapper-seal.json') and
                window['identity']['binary_sha256']==sha(HERE/'build/device/own-rt-iq3'), 'smoke identity stale')
    args=['--lane',a.lane,'--placement','1','--lineage',str(HERE/'lineage'),
          '--bracket',str(HERE/'configs'/(a.kind+'.json')),'--output',str(a.output)]
    if a.plan:args+=['--plan']
    else:
        require(a.authorized_device_window and a.fault_review,'coordinator authorization and review required')
        args+=['--authorized-device-window','--fault-review',str(a.fault_review)]
    return screen.main(args)

if __name__=='__main__':raise SystemExit(main())

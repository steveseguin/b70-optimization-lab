"""Explicit CPU plan entry for lanequeue; forward execution to packet84 run_screen."""
import argparse
from config import verify, view, ORDER, output

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--index', type=int, choices=range(4), required=True)
    ap.add_argument('--lane', choices=('B',), required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--fault-review')
    ap.add_argument('--authorized-device-window', action='store_true')
    args = ap.parse_args(argv)
    from pathlib import Path
    assert Path(args.output).resolve() == output(args.index), 'fixed fresh output required'
    verify()
    from run_screen import main as run
    lineage = view(ORDER[args.index])
    command = ['--profile', 'tp2', '--lane', 'B', '--placement', '1', '--timing', 'token',
               '--lineage', str(lineage), '--seal', str(lineage / 'screen-seal.json'),
               '--output', args.output]
    if args.plan:
        command += ['--plan']
    else:
        assert args.authorized_device_window and args.fault_review, 'device authorization and review required'
        command += ['--fault-review', args.fault_review, '--authorized-device-window']
    return run(command)

if __name__ == '__main__':
    raise SystemExit(main())

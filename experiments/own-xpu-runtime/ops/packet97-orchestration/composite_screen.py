"""Decision-pinned entry for an existing sealed packet97 view; --plan is CPU only."""
import argparse
import json
from pathlib import Path
from composite_jobs import jobs, sha, validate, view, WRAPPER


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--decision', type=Path, required=True)
    ap.add_argument('--decision-sha256', required=True)
    ap.add_argument('--variant', default='composite')
    ap.add_argument('--lane', choices=('A', 'B'), required=True)
    ap.add_argument('--index', type=int, choices=range(3), required=True)
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--fault-review')
    ap.add_argument('--authorized-device-window', action='store_true')
    args = ap.parse_args(argv)
    assert sha(args.decision) == args.decision_sha256, 'decision changed'
    config = json.loads(args.decision.read_text())
    validate(config)
    job = jobs(config, args.lane, args.variant)[args.index]
    lineage = view(job['selection'])
    cmd = ['--profile', 'tp2', '--lane', args.lane, '--placement', '1', '--timing', 'token',
           '--lineage', str(lineage), '--seal', str(lineage/'screen-seal.json'),
           '--output', str(WRAPPER/'evidence'/job['out'])]
    if args.plan:
        cmd.append('--plan')
    else:
        assert args.authorized_device_window and args.fault_review
        cmd += ['--fault-review', args.fault_review, '--authorized-device-window']
    from run_screen import main as run
    return run(cmd)


if __name__ == '__main__':
    raise SystemExit(main())

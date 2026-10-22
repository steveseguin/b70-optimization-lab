"""Packet184 queue entry: two-card checkpoint smoke or lifecycle row. Coordinator-only; never queues.

--plan is CPU-only (lanequeue.py plan runs it): seal verified, identity sealed, plan JSON printed.
A run requires --authorized-device-window and --fault-review (the queue's {REVIEW}), the sealed CPU
composition (cpu_seal.verify) and READY-FOR-DEVICE.json written last by final_checks.py --ready.
"""
import argparse
from pathlib import Path
from common import HERE, require


def parser():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kind', choices=('smoke', 'lifecycle'), required=True)
    ap.add_argument('--lane', choices=('A', 'B'), required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--fault-review', type=Path)
    ap.add_argument('--authorized-device-window', action='store_true')
    ap.add_argument('--plan', action='store_true')
    return ap


def report_completed(output):
    """The post-device CPU report core (lifecycle_report.analyze over OUTPUT/run), publishing
    OUTPUT/run/summary.json; checkpoint_screen.report_completed adds the lane fields around it.
    ops/rehearse_entry.py exercises this function through v5/report-contract.json."""
    import json
    from lifecycle_report import analyze
    output = Path(output)
    result = analyze(output / 'run')
    (output / 'run/summary.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main(argv=None):
    from launch_env import apply
    apply()
    a = parser().parse_args(argv)
    from cpu_seal import verify
    verify()
    from checkpoint_ready import verify_ready
    verify_ready(preplan=a.plan, kind=a.kind, lane=a.lane)
    import checkpoint_screen
    args = ['--lane', a.lane, '--placement', '1', '--lineage', str(HERE / 'lineage' / 'production'), '--kind', a.kind, '--output', str(a.output)]
    if a.plan:
        args += ['--plan']
    else:
        require(a.authorized_device_window and a.fault_review, 'coordinator authorization and review required')
        args += ['--authorized-device-window', '--fault-review', str(a.fault_review)]
    return checkpoint_screen.main(args)


if __name__ == '__main__':
    raise SystemExit(main())

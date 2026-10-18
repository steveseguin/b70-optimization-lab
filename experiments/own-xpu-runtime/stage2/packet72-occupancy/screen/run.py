#!/usr/bin/env python3
"""Six fresh screens in an existing coordinator unit; no service creation/retry."""
import argparse
import json
from pathlib import Path
import signal
import subprocess
import time
from jobs import jobs, command
from common import HERE, require
from conditions import cpu_gate, lane_gate
import screen
import fault_review
from quick_seal import verify


def run_jobs(rows, lane, review, execute, gap, check=lambda: None):
    for index, row in enumerate(rows):
        check()
        print('start ' + row['out'], flush=True)
        status = execute(command(row, lane, review))
        require(status == 0, 'screen failed; no retry or next screen: ' + row['out'])
        check()
        print('finished ' + row['out'], flush=True)
        if index < len(rows) - 1:
            gap(90)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--lane', choices=('A', 'B'), required=True)
    ap.add_argument('--jobs', type=Path, required=True)
    ap.add_argument('--fault-review', type=Path)
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--authorized-device-window', action='store_true')
    args = ap.parse_args()
    cpu_gate() if args.plan else lane_gate(args.lane)
    verify()
    rows = jobs(args.jobs, args.lane)
    require(all(not (HERE / 'evidence' / r['out']).exists() for r in rows), 'all outputs must be fresh')
    if args.plan:
        plans = []
        for row in rows:
            result = subprocess.run(command(row, args.lane, plan=True), check=True,
                                    capture_output=True, text=True, stdin=subprocess.DEVNULL)
            plans.append(json.loads(result.stdout))
        print(json.dumps(dict(device_executed=False, lane=args.lane, plans=plans,
                              gap_seconds=90, retries=0), indent=2))
        return 0
    if args.lane == 'B':
        from winner import verify_lane_a
        verify_lane_a()
    require(args.authorized_device_window and args.fault_review, 'coordinator authorization and fault review required')
    group = Path('/proc/self/cgroup').read_text()
    screen.unit_gate(group)
    screen.unit_conditions(group)
    current, stopped = [], []
    def stop(number, unused):
        stopped.append(number)
        if current and current[0].poll() is None:
            current[0].send_signal(signal.SIGTERM)
    def check():
        require(not stopped and not (HERE / 'evidence/STOP').exists(), 'coordinator stopped quick lane')
        fault_review.validate(args.fault_review)
    def execute(cmd):
        child = subprocess.Popen(cmd, stdin=subprocess.DEVNULL)
        current[:] = [child]
        status = child.wait()
        current.clear()
        return status
    def gap(seconds):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            check()
            time.sleep(min(1, max(0, until - time.monotonic())))
    handlers = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        run_jobs(rows, args.lane, args.fault_review, execute, gap, check)
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

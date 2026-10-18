"""CPU-only --plan; --run requires measured micro qualification before screens."""
import argparse
import json
import signal
import subprocess
import time
from screen_jobs import P, WRAPPER, VIEWS, verify, jobs, command, winner, lanes, DIRECTIONS, qualified_candidates
from common import require
from conditions import cpu_gate, lane_gate
import screen
import fault_review


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--lane', choices=('A', 'B'), required=True)
    ap.add_argument('--direction', choices=DIRECTIONS, default='B-grid')
    # Frozen lanequeue adds --plan to the run argv. Plan always takes precedence.
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--fault-review')
    ap.add_argument('--authorized-device-window', action='store_true')
    args = ap.parse_args()
    require(args.plan or args.run, 'choose --plan or --run')
    if args.plan:
        cpu_gate()
    verify()
    selected = VIEWS[1:] if args.plan else qualified_candidates()
    if not args.plan:
        lane_gate(args.lane)
    source, confirm = lanes(args.direction)
    choice = winner(args.direction, selected)['choice'] if args.lane == confirm and not args.plan else None
    rows = jobs(args.lane, choice, args.direction, selected)
    if args.plan and args.lane == confirm:
        rows = [row for view in selected for row in jobs(confirm, view, args.direction, selected)]
    require(all(not (WRAPPER / 'evidence' / row['out']).exists() for row in rows),
            'all screen outputs must be fresh')
    if args.plan:
        plans = []
        for row in rows:
            result = subprocess.run(command(row, args.lane, plan=True), stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, check=True)
            plans.append(json.loads(result.stdout))
        print(json.dumps(dict(passed=True, device_executed=False, runnable=False,
                              lane=args.lane, direction=args.direction, plans=plans,
                              gap_seconds=90, retries=0,
                              micro_gate='pending: measured >=15% faster; rechecked at --run',
                              confirmation_gate=f'exact improving lane-{source} winner; pending at planning'), indent=2))
        return 0
    require(args.authorized_device_window and args.fault_review,
            'coordinator authorization and review required')
    group = P.__class__('/proc/self/cgroup').read_text()
    screen.unit_gate(group)
    screen.unit_conditions(group)
    if args.lane == confirm:
        require(winner(args.direction, selected)['choice'] == rows[1]['choice'],
                'confirmation selection differs from exact improving grid winner')
    stopped, child = [], []

    def stop(sig, frame):
        stopped.append(sig)
        if child and child[0].poll() is None:
            child[0].send_signal(signal.SIGTERM)

    def check():
        require(not stopped and not (P / 'evidence/STOP').exists(), 'campaign stopped')
        fault_review.validate(args.fault_review)

    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        for index, row in enumerate(rows):
            check()
            require(qualified_candidates() == selected, 'micro qualification changed before launch')
            print('start ' + row['out'], flush=True)
            child[:] = [subprocess.Popen(command(row, args.lane, args.fault_review), stdin=subprocess.DEVNULL)]
            rc = child[0].wait()
            child.clear()
            require(rc == 0, 'screen failed; no retry or next screen: ' + row['out'])
            check()
            if index < len(rows) - 1:
                end = time.monotonic() + 90
                while time.monotonic() < end:
                    check()
                    time.sleep(min(1, max(0, end - time.monotonic())))
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

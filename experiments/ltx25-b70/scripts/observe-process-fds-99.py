#!/usr/bin/env python3
"""Bounded read-only descriptor census; never signals or contacts the server."""
import argparse
import collections
import datetime
import json
import os
from pathlib import Path
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pid', type=int, required=True)
    p.add_argument('--start-ticks', required=True)
    p.add_argument('--boot-id', required=True)
    p.add_argument('--seconds', type=int, default=3600)
    a = p.parse_args()
    if a.pid <= 1 or not 1 <= a.seconds <= 7200:
        p.error('Require positive server PID and duration 1..7200 seconds')
    proc = Path('/proc') / str(a.pid)
    deadline = time.monotonic() + a.seconds
    while time.monotonic() < deadline:
        try:
            if (Path('/proc/sys/kernel/random/boot_id').read_text().strip() != a.boot_id
                    or proc.joinpath('stat').read_text().split(') ')[1].split()[19] != a.start_ticks):
                raise RuntimeError('Process identity changed')
            fds = list(proc.joinpath('fd').iterdir())
            categories = collections.Counter()
            vanished = 0
            for fd in fds:
                try:
                    target = os.readlink(fd)
                except FileNotFoundError:
                    vanished += 1
                    continue
                categories['dmabuf' if target == '/dmabuf:' else
                           'render' if target.startswith('/dev/dri/render') else 'other'] += 1
            limits = next(x for x in proc.joinpath('limits').read_text().splitlines()
                          if x.startswith('Max open files'))
            row = {'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   'pid': a.pid, 'start_ticks': a.start_ticks, 'count_observed': len(fds),
                   'maximum_fd': max(map(lambda x: int(x.name), fds), default=-1),
                   'categories': dict(categories), 'vanished_during_scan': vanished,
                   'limits': limits, 'requires_owner_intervention': len(fds) >= 16384,
                   'limits_note': 'read-only observation; 16384 alert is not an enforced cap'}
            print(json.dumps(row), flush=True)
        except FileNotFoundError:
            print(json.dumps({'status': 'process-gone', 'pid': a.pid}), flush=True)
            return
        time.sleep(2)
    print(json.dumps({'status': 'observation-bound-ended', 'pid': a.pid}), flush=True)


if __name__ == '__main__':
    main()

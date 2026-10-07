#!/usr/bin/env python3
"""Bounded read-only descriptor census; never signals or contacts the server."""
import argparse
import collections
import datetime
import json
import os
import sys
from pathlib import Path
import time


def process_identity(proc, boot_id, start_ticks):
    """Read identity/state without opening descriptors or contacting the process."""
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if boot != boot_id:
        raise RuntimeError('Boot identity changed')
    fields = proc.joinpath('stat').read_text().rsplit(') ', 1)[1].split()
    if fields[19] != start_ticks:
        raise RuntimeError('Process identity changed')
    return {'boot_id': boot, 'start_ticks': fields[19], 'state': fields[0]}


def terminal_after_error(proc, boot_id, start_ticks, error):
    """One identity/state recheck, never a retry of the failed observation."""
    row = {'status': 'observation-lost', 'pid': int(proc.name),
           'start_ticks': start_ticks, 'expected_boot_id': boot_id,
           'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'error': {'type': type(error).__name__, 'message': str(error)}}
    try:
        identity = process_identity(proc, boot_id, start_ticks)
        row['observed_identity'] = identity
        if identity['state'] in ('Z', 'X'):
            row.update(status='process-exited', reason='matching-zombie-or-dead-state')
            return row, 0
    except FileNotFoundError as recheck_error:
        # A missing fd/stat entry alone is not proof of exit. Confirm the PID
        # directory itself disappeared, with the same boot still observable.
        try:
            boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
            try:
                proc.stat()
            except FileNotFoundError:
                if boot == boot_id:
                    row.update(status='process-exited', reason='process-directory-absent',
                               observed_boot_id=boot)
                    return row, 0
            row['recheck_error'] = {'type': type(recheck_error).__name__, 'message': str(recheck_error)}
        except Exception as final_error:
            row['recheck_error'] = {'type': type(final_error).__name__, 'message': str(final_error)}
    except Exception as recheck_error:
        row['recheck_error'] = {'type': type(recheck_error).__name__, 'message': str(recheck_error)}
    return row, 3


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
            identity = process_identity(proc, a.boot_id, a.start_ticks)
            if identity['state'] in ('Z', 'X'):
                print(json.dumps({'status': 'process-exited', 'pid': a.pid,
                                  'reason': 'matching-zombie-or-dead-state',
                                  'observed_identity': identity}), flush=True)
                return 0
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
        except Exception as error:
            row, exit_code = terminal_after_error(proc, a.boot_id, a.start_ticks, error)
            print(json.dumps(row), flush=True)
            return exit_code
        time.sleep(2)
    print(json.dumps({'status': 'observation-bound-ended', 'pid': a.pid}), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())

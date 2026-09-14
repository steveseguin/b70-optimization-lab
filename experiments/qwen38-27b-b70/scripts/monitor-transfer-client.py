#!/usr/bin/env python3
"""Run one client with bounded journal monitoring; never manage a server."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

FAULT = re.compile(r'(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup', re.I)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--timeout', type=int, default=1800)
    ap.add_argument('command', nargs=argparse.REMAINDER)
    a = ap.parse_args()
    command = a.command[1:] if a.command[:1] == ['--'] else a.command
    if not command:
        ap.error('a client command is required')
    a.out.mkdir(parents=True, exist_ok=False)
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    # The persistent serving helper owns the host's server-stage lock.
    # This mutex serializes our HTTP clients without claiming server ownership.
    lock = open('/tmp/qwen-amd-transfer-client.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    (a.out / 'command.json').write_text(json.dumps({'argv': command, 'started': started, 'timeout': a.timeout}, indent=2) + '\n')

    def check():
        r = subprocess.run(['journalctl', '-k', '-b', '0', '--since', started, '--no-pager'], capture_output=True, text=True, timeout=15, check=True)
        if re.search(r'permission|not seeing messages|No journal files', r.stderr, re.I):
            raise RuntimeError('kernel journal unavailable')
        (a.out / 'kernel.log').write_text(r.stdout)
        bad = [x for x in r.stdout.splitlines() if FAULT.search(x) and not x.endswith('Xe device coredump has been deleted.')]
        if bad:
            (a.out.parent / 'FAULT.json').write_text(json.dumps({'started': started, 'lines': bad}, indent=2) + '\n')
            raise RuntimeError('kernel fault: halt new GPU requests')

    if (a.out.parent / 'FAULT.json').exists():
        raise RuntimeError('existing campaign fault latch')
    check()
    child = None
    try:
        with (a.out / 'client.log').open('w') as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic() + a.timeout
            while child.poll() is None:
                check()
                if time.monotonic() > deadline:
                    raise TimeoutError('client exceeded its bound')
                time.sleep(2)
            check()
            if child.returncode:
                raise RuntimeError(f'client exited {child.returncode}; inspect client.log')
        (a.out / 'DONE').write_text(datetime.datetime.now(datetime.timezone.utc).isoformat() + '\n')
    except BaseException as exc:
        (a.out / 'ABORTED').write_text(f'{type(exc).__name__}: {exc}\n')
        raise
    finally:
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGINT)
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                (a.out / 'CLIENT_EXIT_UNCONFIRMED').write_text(str(child.pid) + '\n')
        lock.close()


if __name__ == '__main__':
    main()

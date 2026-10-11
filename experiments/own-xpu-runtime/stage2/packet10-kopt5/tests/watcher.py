"""Packet2 cooperative watcher, with packet10 outcome-specific latching.

A nonzero exit alone is infrastructure evidence. Journal faults, deadlines,
signals and lost journal visibility retain the stop latch. Never retries.
"""
import datetime
from pathlib import Path
import signal
import subprocess
import time
from common import LATCH, p2, save
journal, FAULT = p2.journal, p2.FAULT

def watch(command, out, seconds=120):
    """One child; one cooperative stop; retain ownership if native drain stalls."""
    pre, cursor = journal()
    out.mkdir(parents=True)
    (out / 'preflight-kernel.txt').write_text(pre)
    record = dict(start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        initial_cursor=cursor, final_cursor=cursor, stop_reason=None, returncode=None,
        requested_deadline_seconds=seconds, external_idle_health_still_required=True, fault_lines=[])
    requested = []
    old = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
    for sig in old:
        signal.signal(sig, lambda s, f: requested.append('watcher signal ' + str(s)))
    try:
        with (out / 'stdout.txt').open('w') as log, (out / 'kernel-window.txt').open('w') as kernel:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            record['pid'] = child.pid
            started = time.monotonic()
            sent = False
            save(out / 'window.json', record)
            while True:
                try:
                    fresh, cursor = journal(cursor)
                    kernel.write(fresh); kernel.flush()
                    if FAULT.search(fresh):
                        record['fault_lines'].extend(line for line in fresh.splitlines() if FAULT.search(line))
                        requested.append('new GPU fault signature')
                except Exception as e:
                    requested.append('journal failure: ' + str(e))
                if time.monotonic() - started >= seconds:
                    requested.append('window deadline')
                if requested and not sent:
                    record['stop_reason'] = requested[0]
                    save(LATCH, dict(reason=requested[0], output=str(out), pid=child.pid, fault_lines=record['fault_lines']))
                    save(out / 'window.json', record)
                    if child.poll() is None:
                        child.send_signal(signal.SIGTERM)
                    sent = True
                if child.poll() is not None:
                    break
                time.sleep(.25)
            record['returncode'] = child.returncode
            # Same bounded postflight journal tail as the exactness window.
            for _ in range(20):
                time.sleep(.25)
                try:
                    fresh, cursor = journal(cursor)
                    kernel.write(fresh)
                    if FAULT.search(fresh):
                        record['fault_lines'].extend(line for line in fresh.splitlines() if FAULT.search(line))
                        requested.append('post-exit GPU fault')
                except Exception as e:
                    requested.append('postflight journal: ' + str(e))
            record['elapsed_seconds'] = time.monotonic() - started
            record['final_cursor'] = cursor
    finally:
        for sig, handler in old.items():
            signal.signal(sig, handler)
    if requested:
        record['stop_reason'] = requested[0]
    if record['stop_reason']:
        save(LATCH, dict(record, reason=record['stop_reason'], output=str(out)))
    save(out / 'window.json', record)
    return record

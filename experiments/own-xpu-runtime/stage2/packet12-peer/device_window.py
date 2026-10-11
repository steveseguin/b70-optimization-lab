#!/usr/bin/env python3
"""Coordinator only: one bounded child; no retry, hard kill, reset or service."""
import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from validate import HERE, ROOT, sha
from receipt import summarize

spec = importlib.util.spec_from_file_location('packet2_watch', HERE.parent/'packet2/tests/device_window.py')
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)
journal, FAULT = watch.journal, watch.FAULT

def run_window(binary, cards, out, seconds, build):
    latch = HERE/'build/FAULT.json'
    if latch.exists():
        raise RuntimeError('persistent fault latch; coordinator review required')
    pre, cursor = journal()  # Refuse before launch if evidence is unavailable.
    out.mkdir(parents=True)
    (out/'preflight-kernel.txt').write_text(pre)
    record = dict(schema='own-runtime.peer.window.v1', passed=False, cards=cards,
                  start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                  binary_sha256=sha(binary), build_receipt=build, seconds=seconds,
                  external_idle_health_still_required=True,
                  environment={k: v for k, v in os.environ.items() if k.startswith(('SYCL_', 'UR_', 'ZE_', 'IGC_'))
                               or k in ('OMP_NUM_THREADS', 'EnableDeferBacking')})
    (out/'meminfo-before.txt').write_text(Path('/proc/meminfo').read_text())
    requested, faults = [], []
    def save():
        (out/'window.json').write_text(json.dumps(record, indent=2)+'\n')
    def fail(reason):
        if not requested:
            requested.append(reason)
        record.update(stop_reason=requested[0], fault_lines=faults)
        (out/'STOP').write_text(requested[0]+'\n')
        latch.write_text(json.dumps(dict(output=str(out), reason=requested[0], fault_lines=faults), indent=2)+'\n')
        save()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda s, f: requested.append('watcher signal '+str(s)))
    with (out/'stdout.txt').open('w') as log, (out/'kernel-window.txt').open('w') as kernel:
        start = time.monotonic()
        try:
            child = subprocess.Popen([str(binary), '--authorized-device-window', *map(str, cards),
                                      str(out/'native.json'), str(out/'STOP'), str(seconds), 'peer-packet12'],
                                     stdout=log, stderr=subprocess.STDOUT)
        except Exception as ex:
            fail('launch failed: '+str(ex))
            return 1
        record['pid'] = child.pid
        save()
        sent = False
        def poll_journal():
            nonlocal cursor
            try:
                fresh, cursor = journal(cursor)
                kernel.write(fresh); kernel.flush()
                lines = [line for line in fresh.splitlines() if FAULT.search(line)]
                if lines:
                    faults.extend(lines); fail('new GPU fault signature')
            except Exception as ex:
                fail('kernel journal unavailable: '+str(ex))
        while True:
            poll_journal()
            if time.monotonic()-start > seconds:
                fail('window deadline')
            if (out/'STOP').exists() and not requested:
                fail('native stop: '+(out/'STOP').read_text().strip())
            if requested and not sent:
                fail(requested[0])
                if child.poll() is None:
                    child.send_signal(signal.SIGTERM)  # Captured PID, once.
                sent = True
            if child.poll() is not None:
                break
            time.sleep(.25)
        record['returncode'] = child.returncode
        for _ in range(20):
            time.sleep(.25); poll_journal()
        record['elapsed_seconds'] = time.monotonic()-start
    (out/'meminfo-after.txt').write_text(Path('/proc/meminfo').read_text())
    try:
        summary = summarize(json.loads((out/'native.json').read_text()))
        if child.returncode:
            raise ValueError('nonzero native exit')
        if requested:
            raise ValueError(requested[0])
        (out/'receipt.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
        record['passed'] = True
    except Exception as ex:
        fail('receipt/window failed: '+str(ex))
    save()
    return 0 if record['passed'] else 1

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--authorized-device-window', required=True, action='store_true')
    p.add_argument('--cards', nargs=2, type=int, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--seconds', type=int, default=120)
    a = p.parse_args()
    if sorted(a.cards) != [2, 3] or not 1 <= a.seconds <= 120:
        raise SystemExit('this packet admits exactly cards 2 and 3, <=120 seconds')
    if os.getpriority(os.PRIO_PROCESS, 0) != 19 or os.environ.get('OMP_NUM_THREADS') != '2':
        raise SystemExit('nice 19 and OMP_NUM_THREADS=2 required')
    if any(os.environ.get(k) for k in ('ONEAPI_DEVICE_SELECTOR', 'SYCL_DEVICE_FILTER', 'ZE_AFFINITY_MASK')):
        raise SystemExit('unmasked Level Zero indices required')
    out = a.output.resolve()
    if HERE/'build' not in out.parents or out.exists():
        raise SystemExit('fresh output directory under packet build/ required')
    build = json.loads((HERE/'build-receipt.json').read_text())
    if not build['passed'] or build['native_executed']:
        raise SystemExit('passing CPU-only build receipt required')
    for name, digest in build['source_sha256'].items():
        if sha(ROOT/name) != digest:
            raise SystemExit('source identity changed: '+name)
    binary = HERE/'build/compile/peer-native'
    if sha(binary) != build['binary_sha256']:
        raise SystemExit('binary identity mismatch')
    return run_window(binary, a.cards, out, a.seconds, build)

if __name__ == '__main__':
    raise SystemExit(main())

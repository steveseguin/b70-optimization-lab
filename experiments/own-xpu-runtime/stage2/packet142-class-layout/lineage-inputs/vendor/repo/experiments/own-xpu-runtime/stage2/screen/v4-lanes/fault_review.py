#!/usr/bin/env python3
"""Derive a review boundary only after this boot has exactly two known fault lines."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import gzip
import json
from pathlib import Path
import re
from common import HERE, ROOT, S, read, require, save, sha
from conditions import cpu_gate

DRIVER = ROOT / 'experiments/own-xpu-runtime/stage1/packet4-prep/driver/window_driver.py'


def patterns():
    # Read the authoritative expressions without importing an operational driver.
    result = {}
    for node in ast.parse(DRIVER.read_text()).body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('FAULT', 'DELETED'):
                    result[target.id] = re.compile(ast.literal_eval(node.value.args[0]), re.I)
    require(set(result) == {'FAULT', 'DELETED'}, 'window_driver fault expressions unavailable')
    return result['FAULT'], result['DELETED']


FAULT, DELETED = patterns()


def fault_lines(text):
    return [line for line in text.splitlines() if FAULT.search(line) and not DELETED.search(line)]


class FaultFilter:
    def search(self, text):
        return bool(fault_lines(text))


# Use exactly the same fault/deleted rules in passive live supervision.
S.FAULT = FaultFilter()


def inspect(text, boot, cursor):
    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    require(rows and cursor, 'empty kernel journal or missing cursor')
    require(all(r.get('_BOOT_ID') == boot.replace('-', '') for r in rows), 'kernel log boot mismatch')
    faults = [r for r in rows if fault_lines(str(r.get('MESSAGE', '')))]
    require(len(faults) == 2, 'expected exactly 2 known fault lines; found ' + str(len(faults)))
    # Boundary comes from the captured journal AFTER the exact-count check.
    through_us = max(int(r['__REALTIME_TIMESTAMP']) for r in rows)
    boundary = datetime.fromtimestamp(through_us / 1e6, timezone.utc).isoformat().replace('+00:00', 'Z')
    return dict(schema='own-runtime.screen.fault-review.v3', boot_id=boot,
                fault_count=2, faults=faults, cursor=cursor, through=boundary,
                through_us=through_us, driver_sha256=sha(DRIVER),
                journal_sha256=hashlib.sha256(text.encode()).hexdigest())


def capture():
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    text, cursor = S.journal()
    return inspect(text, boot, cursor), text


def validate(path):
    recorded = read(path)
    captured = gzip.decompress(Path(recorded['kernel_capture']).read_bytes()).decode()
    original = inspect(captured, recorded['boot_id'], recorded['cursor'])
    require(all(recorded.get(k) == value for k, value in original.items()), 'review receipt differs from captured kernel log')
    current, text = capture()
    for name in ('schema', 'boot_id', 'fault_count', 'faults', 'driver_sha256'):
        require(current[name] == recorded.get(name), 'fault review changed: ' + name)
    S.fault_review(recorded['through'], __import__('time').time_ns() // 1000)
    require(current['through_us'] >= recorded['through_us'], 'kernel journal moved backward')
    fresh, cursor = S.journal(recorded['cursor'])
    require(not fault_lines(fresh), 'new kernel fault after review')
    return recorded, text, fresh, cursor


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    cpu_gate()
    args.output = args.output.resolve()
    require(args.output.is_relative_to(HERE / 'evidence') and not args.output.exists(),
            'new v3 evidence review output required')
    row, text = capture()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    log = args.output.with_suffix('.kernel.jsonl.gz')
    require(not log.exists(), 'new kernel capture required')
    log.write_bytes(gzip.compress(text.encode(), mtime=0))
    row['kernel_capture'] = str(log.resolve())
    save(args.output, row)
    print(json.dumps(dict(passed=True, fault_count=2, through=row['through'], output=str(args.output))))


if __name__ == '__main__':
    main()

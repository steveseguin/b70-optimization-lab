#!/usr/bin/env python3
"""Capture the pinned p181 exact-two-fault boot review at the fixed p197 path."""
import argparse
import gzip
import json
from pathlib import Path
from device_worker import REVIEW, capture_review, parent_modules, require, save, verify_ready


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    verify_ready()
    modules = parent_modules(); modules['conditions'].cpu_gate()
    require(args.output == REVIEW and not args.output.exists(), 'fresh fixed review path required')
    log = REVIEW.with_suffix('.kernel.jsonl.gz')
    require(not log.exists(), 'fresh capture required')
    row, text = capture_review()
    with log.open('xb') as file:
        file.write(gzip.compress(text.encode(), mtime=0))
    row['kernel_capture'] = str(log)
    save(REVIEW, row)
    print(json.dumps(dict(passed=True, device_executed=False, fault_count=row['fault_count'], output=str(REVIEW))))


if __name__ == '__main__':
    main()

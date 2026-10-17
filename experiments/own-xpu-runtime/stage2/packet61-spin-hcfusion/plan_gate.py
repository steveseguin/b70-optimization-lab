#!/usr/bin/env python3
"""CPU-only chain wiring, seal, prefix/oracle and pinned-dispatch checks."""
import argparse
import json
import os
from pathlib import Path

import queue_runner as q
from chain_seal import verify
from storage import digest, precheck


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    q.P.joinpath('build-receipt.json').stat()
    if os.getpriority(os.PRIO_PROCESS, 0) != 19 or not set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32)):
        raise ValueError('nice19 and helper cores required')
    seal = verify()
    root = q.admitted_output(Path('/home/steve/own-xpu-runtime-results/packet61-spin-hcfusion/build/device-cards01-b'))
    from check_inputs import check, summary
    inputs = check(root)
    if not inputs['passed']:
        raise ValueError('input check failed: ' + str(inputs['errors']))
    commands = q.commands(root)
    assert tuple(commands) == ('K0', 'K1a', 'K1b', 'K2', 'W0p', 'KD', 'W2m', 'WS', 'WSs', 'WS128x', 'WS128')
    for name, command in commands.items():
        for flag, value in (('--card', '0'), ('--context', '4096'), ('--draft-rank', '1'), ('--target-split', '23')):
            assert command[command.index(flag)+1] == value
        for flag in ('--input', '--oracle', '--suite-manifest'):
            if flag in command:
                assert Path(command[command.index(flag)+1]).exists()
        assert '--diagnostic-unsealed' not in command
    from merge_dispatch import validate
    for name in ('dispatch-p45.json', 'dispatch-speed6.json'):
        validate(json.loads((q.P / name).read_text()))
    proof = json.loads((q.P / 'dispatch-speed6-provenance.json').read_text())
    assert proof['sha256'] == digest(q.P / 'dispatch-speed6.json')
    from shared_oracle import completed_binding
    oracle = completed_binding()
    parent = q.P.parent / 'packet56-draft-prefix'
    prefixes = q.prefix_prerequisites([parent / 'evidence/head-k-a/window.json', parent / 'evidence/head-k-b/window.json'])
    row = dict(passed=True, device_executed=False, windows=list(commands),
               commands=commands, build_receipt_sha256=digest(q.P / 'build-receipt.json'),
               engine_sha256=seal['artifacts_sha256']['device/own-rt-iq3'],
               oracle=oracle, prefix_prerequisites=prefixes, input_check=summary(inputs), storage=precheck(),
               scope='Plan and identity only; storage and device admission remain mandatory at launch')
    if args.output:
        with args.output.open('x') as output:
            output.write(json.dumps(row, indent=2)+'\n')
    print(json.dumps(dict(passed=True, device_executed=False, windows=row['windows'],
                          storage_passed=row['storage']['passed'], storage_margin_bytes=row['storage']['margin_bytes'])))


if __name__ == '__main__':
    main()

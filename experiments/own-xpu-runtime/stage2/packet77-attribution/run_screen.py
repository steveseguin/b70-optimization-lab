#!/usr/bin/env python3
"""Paired attribution payload hosted by the unchanged, pinned shared v4 wrapper."""
import argparse
import json
from pathlib import Path
import sys

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
WRAPPER = P.parent / 'screen/v4-lanes'
# v4 recognizes placement audits in this legacy namespace. Keep the namespace
# beneath packet77, bind the complete audit, and use the real predicate unchanged.
VIEW = P / 'compat/packet64-record-bundle/selections/1-draft-hc-batch-wide64'
OUTPUT = WRAPPER / 'evidence/packet77-attribution-B-a'
sys.path.insert(0, str(WRAPPER))
import screen
from common import read, require, sha, save, summary


def verify_dependencies():
    for name, digest in read(P / 'dependency-pins.json').items():
        require(sha(ROOT / name) == digest, 'packet77 pinned dependency changed: ' + name)
    from cpu_seal import verify
    verify()


def worker_command(args, identity, manifest):
    require(args.lane == 'B' and args.placement == '1' and args.timing == 'attribution',
            'packet77 requires lane B, placement 1, attribution')
    require(args.lineage == VIEW and args.pair_dir is None, 'packet77 fixed selection only')
    return ['/usr/bin/python3', '-B', str(P / 'worker.py'),
            '--identity', str(args.output / 'identity.json'),
            '--output', str(args.output / 'run'), '--seconds', '3600']


def main(argv=None):
    verify_dependencies()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--lane', choices=('B',), default='B')
    ap.add_argument('--output', type=Path, default=OUTPUT)
    ap.add_argument('--fault-review', type=Path)
    ap.add_argument('--authorized-device-window', action='store_true')
    parsed = ap.parse_args(argv)
    supplied = []
    if parsed.plan:
        supplied.append('--plan')
    if parsed.fault_review:
        supplied += ['--fault-review', str(parsed.fault_review)]
    if parsed.authorized_device_window:
        supplied.append('--authorized-device-window')
    argv = ['--profile', 'tp2', '--lane', 'B', '--placement', '1',
            '--timing', 'attribution', '--lineage', str(VIEW),
            '--seal', str(VIEW / 'screen-seal.json'), '--output', str(parsed.output), *supplied]
    # The sole adapter hook selects the workload. Admission, placement validation,
    # closed env, fault checks, memory checks, lease and teardown stay in shared v4.
    previous = screen.command
    screen.command = worker_command
    try:
        code = screen.main(argv)
    finally:
        screen.command = previous
    args = screen.parser().parse_args(argv)
    if code or args.plan:
        return code
    # v4 has already drained and released BOTH lane locks before this CPU report.
    require(read(args.output / 'window.json').get('lease_released') is True,
            'report requires released lane')
    try:
        proof = read(args.output / 'run/paired-inputs.json')
        require(proof.get('passed') is True, 'paired worker did not pass')
        for arm in ('control', 'attribution'):
            save(args.output / 'run' / arm / 'summary.json',
                 summary(proof['arms'][arm], proof['incident64'], 'tp2'))
        # Put packet-local reporting ahead of shared wrapper/controller modules.
        sys.path.insert(0, str(P))
        from report import generate, markdown
        result = generate(args.output / 'run')
        save(args.output / 'run/attribution-summary.json', result)
        (args.output / 'run/attribution-summary.md').write_text(markdown(result))
    except Exception as error:
        save(args.output / 'packet77-report-failure.json',
             dict(passed=False, device_failure=False, error=str(error)))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

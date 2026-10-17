#!/usr/bin/env python3
"""Restore this chain's read-only binary/input links; never build or run binaries."""
import json
import os
from pathlib import Path

from storage import digest, REGISTERED_CHAIN

P = Path(__file__).resolve().parent
PARENT = P.parent / 'packet56-draft-prefix'
SCREEN = P.parent / 'packet61x-spin-hcfusion-wait'
DEST = Path('/home/steve/own-xpu-runtime-results/packet61x-spin-hcfusion-wait/build')


def link(path, target):
    if path.is_symlink():
        if path.resolve() != target.resolve():
            raise ValueError('existing link points elsewhere: ' + str(path))
    elif path.exists():
        raise ValueError('never replace existing storage: ' + str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target.resolve())


def main():
    if os.getpriority(os.PRIO_PROCESS, 0) != 19 or not set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32)):
        raise ValueError('nice19 and helper cores 8-15,24-31 required')
    if (DEST / REGISTERED_CHAIN).exists():
        raise ValueError('started chain; never change its build view')
    binding = json.loads((P / 'chain-binding.json').read_text())
    for directory, leaf, key in ((PARENT, 'build-receipt.json', 'parent_seal_sha256'),
                                 (SCREEN, 'screen-seal.json', 'screen_seal_sha256')):
        if digest(directory / leaf) != binding[key]:
            raise ValueError('immutable parent seal changed')
    parent = json.loads((PARENT / 'build-receipt.json').read_text())
    screen = json.loads((SCREEN / 'screen-seal.json').read_text())
    links = {}
    for name, expected in parent['artifacts_sha256'].items():
        target = PARENT / 'build' / name
        if name in ('device/own-rt-iq3','gnu-host/own-rt-iq3'):
            target = SCREEN / 'build' / name
            expected = screen['artifacts']['build/' + name]
        if digest(target) != expected:
            raise ValueError('retained binary changed: ' + str(target))
        if name not in ('device/own-rt-iq3','gnu-host/own-rt-iq3'):
            links[name] = target
    if digest(PARENT / 'build/input/input.json') != parent['input_sha256']:
        raise ValueError('parent input identity changed')
    links['input'] = PARENT / 'build/input'
    DEST.mkdir(parents=True, exist_ok=True)
    link(P / 'build' / REGISTERED_CHAIN, DEST / REGISTERED_CHAIN)
    for name, target in links.items():
        link(P / 'build' / name, target)
    from prepare_inputs import restore
    restore()
    print(json.dumps(dict(passed=True, device_executed=False, links=len(links), build=str(DEST))))


if __name__ == '__main__':
    main()

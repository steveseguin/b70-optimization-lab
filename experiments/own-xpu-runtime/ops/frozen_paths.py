#!/usr/bin/env python3
"""Print the pin union for queued, ready and running packets. Read-only, CPU-only.

Paste stdout into a brief's Frozen section. A nonzero exit means the list is
incomplete; diagnostics go to stderr. Neither hashes nor model bytes are read.
"""
import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lane-queue'))
import pin_guard

COORD = Path('/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1')


def active_packets(root, queue, coord=COORD, proc=Path('/proc')):
    stage = root / 'experiments/own-xpu-runtime/stage2'
    packets, errors = set(), []

    def job(row):
        if not isinstance(row, dict) or not isinstance(row.get('job', row), dict):
            errors.append('invalid job metadata; packet identity unavailable')
            return
        item = row.get('job', row)
        try:
            packet = pin_guard.packet_for_job(item, root, stage)
            if packet:
                packets.add(packet)
        except (ValueError, TypeError, KeyError) as exc:
            # A freeze list can safely include all ambiguous packet copies;
            # launch admission still refuses to guess which one would run.
            match = re.match(r'^(?:packet|p)(\d+[a-z]*)(?=[-_.]|$)', str(item.get('name', '')))
            candidates = list(stage.glob('packet' + match[1] + '-*')) if match else []
            if candidates:
                packets.update(candidates)
            else:
                errors.append(str(exc))

    for lane in 'AB':
        path = queue / f'queue-{lane}.txt'
        if path.exists():
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if not line.strip() or line.lstrip().startswith('#'):
                    continue
                try:
                    job(json.loads(line))
                except (ValueError, AttributeError):
                    errors.append(f'{path}:{number}: invalid queue entry')
        path = queue / f'inflight-{lane}.json'
        if path.exists():
            try:
                job(json.loads(pin_guard.read_metadata(path)))
            except (ValueError, OSError, AttributeError):
                errors.append(f'{path}: unreadable inflight record')
        marker = coord / f'active-lane-{lane}.json'
        if marker.exists():
            try:
                owner = json.loads(pin_guard.read_metadata(marker))
                pid = owner['pid']
                fields = (proc / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
                if fields[0] not in ('Z', 'X') and int(fields[19]) == owner['start_ticks']:
                    # Inspect only the reservation owner. Never echo argv or
                    # environment; emit only packet paths and their pins.
                    argv = (proc / str(pid) / 'cmdline').read_bytes().decode().split('\0')
                    for arg in argv:
                        if arg.startswith(str(stage) + '/') or arg.startswith('experiments/own-xpu-runtime/stage2/'):
                            job({'argv': [arg]})
            except (ValueError, OSError, KeyError, IndexError):
                errors.append(f'{marker}: running owner could not be inspected')
    for packet in stage.glob('packet*'):
        # A readiness marker is a freeze request even when its latest verdict
        # is false: an unready packet must not disappear from a safety brief.
        if any((packet / name).is_file() for name in ('READY-FOR-DEVICE', 'READY-FOR-DEVICE.json', 'ready.json')):
            packets.add(packet)
    ops = root / 'experiments/own-xpu-runtime/ops'
    for marker in ops.glob('packet*/ready.json'):
        job({'name': marker.parent.name, 'script': str(marker.parent / 'orchestrate.py')})
    return packets, errors


def frozen_paths(packets, root):
    paths, errors = set(), []
    for packet in sorted(packets):
        try:
            pins, manifests = pin_guard.collect_pins(packet, root)
            for path in [*manifests, *(p for p, _, _ in pins)]:
                paths.add(path)
        except (ValueError, OSError, TypeError) as exc:
            errors.append(f'{packet}: {exc}')
    # Resolve each distinct path once, not once per overlapping seal map.
    paths.update(path.resolve() for path in list(paths))
    return sorted(paths), errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=pin_guard.ROOT)
    parser.add_argument('--queue-directory', type=Path)
    parser.add_argument('--coordination', type=Path, default=COORD)
    args = parser.parse_args()
    root = args.root.resolve()
    queue = args.queue_directory or root / 'experiments/own-xpu-runtime/ops/lane-queue'
    packets, errors = active_packets(root, queue, args.coordination)
    paths, failures = frozen_paths(packets, root)
    for path in paths:
        print(path.relative_to(root) if path.is_relative_to(root) else path)
    for error in errors + failures:
        print(error, file=sys.stderr)
    return int(bool(errors or failures))


if __name__ == '__main__':
    raise SystemExit(main())

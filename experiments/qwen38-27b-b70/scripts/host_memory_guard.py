#!/usr/bin/env python3
"""Root-side host-memory guard for one GPU container on the two-B70 host.

On 2026-09-14 a model load left about 12.7 GiB of host RAM in GPU driver pages.
Those pages are not charged to the container's memory cgroup, and the owner's
Docker/journal calls blocked for half an hour once the host thrashed, so nothing
stopped the container. This guard is its own memory-locked process: it reads
/proc/meminfo directly and kills the container's cgroup without calling Docker.
It never restarts anything.

An owner starts it through sudo once the container ID is known:
  sudo python3 host_memory_guard.py --container-id ID --out DIR --baseline-unaccounted BYTES
Exit 0: container gone, never appeared, or SIGTERM. Exit 3: guard fired.
"""
from __future__ import annotations
import argparse
import ctypes
import json
from pathlib import Path
import signal
import sys
import time

GIB = 1024 ** 3
# RAM outside these counters is mostly driver-held pages (xe/TTM on this host).
COUNTED = ('MemFree', 'Buffers', 'Cached', 'SwapCached', 'AnonPages', 'Slab',
           'KernelStack', 'PageTables', 'SecPageTables', 'Percpu')
DEFAULT_MAX_GROWTH = 4 * GIB
DEFAULT_MIN_AVAILABLE = 5 * GIB // 2
FIRED_EXIT = 3
CGROUP_ROOT = Path('/sys/fs/cgroup/system.slice')


def parse_meminfo(text):
    values = {}
    for line in text.splitlines():
        key, _, rest = line.partition(':')
        fields = rest.split()
        if fields and fields[0].isdigit():
            values[key] = int(fields[0]) * (1024 if fields[1:] == ['kB'] else 1)
    return values


def unaccounted_bytes(info):
    return info['MemTotal'] - sum(info.get(key, 0) for key in COUNTED)


def decide(info, baseline_unaccounted, max_growth=DEFAULT_MAX_GROWTH, min_available=DEFAULT_MIN_AVAILABLE):
    growth = unaccounted_bytes(info) - baseline_unaccounted
    if growth > max_growth:
        return f'driver-held host memory grew by {growth / GIB:.2f} GiB'
    if info['MemAvailable'] < min_available:
        return f'available host memory fell to {info["MemAvailable"] / GIB:.2f} GiB'
    return None


def cgroup_dir(container_id, root=CGROUP_ROOT):
    if len(container_id) != 64 or any(c not in '0123456789abcdef' for c in container_id):
        raise ValueError('Full 64-hex container ID required')
    return Path(root) / f'docker-{container_id}.scope'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--container-id', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--baseline-unaccounted', type=int, required=True)
    ap.add_argument('--max-growth-gib', type=float, default=DEFAULT_MAX_GROWTH / GIB)
    ap.add_argument('--min-available-gib', type=float, default=DEFAULT_MIN_AVAILABLE / GIB)
    ap.add_argument('--interval', type=float, default=0.5)
    ap.add_argument('--appear-timeout', type=float, default=180)
    ap.add_argument('--cgroup-root', type=Path, default=CGROUP_ROOT, help=argparse.SUPPRESS)
    ap.add_argument('--meminfo', type=Path, default=Path('/proc/meminfo'), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    group = cgroup_dir(a.container_id, a.cgroup_root)
    max_growth, min_available = int(a.max_growth_gib * GIB), int(a.min_available_gib * GIB)
    # MCL_CURRENT | MCL_FUTURE keeps the guard responsive while the host swaps.
    locked = ctypes.CDLL('libc.so.6', use_errno=True).mlockall(3) == 0
    stopping = []
    signal.signal(signal.SIGTERM, lambda *_: stopping.append(True))
    a.out.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + a.appear_timeout
    seen = False
    with (a.out / 'memory-guard.jsonl').open('a') as samples:
        while not stopping:
            if group.is_dir():
                seen = True
            elif seen or time.monotonic() > deadline:
                return 0
            info = parse_meminfo(a.meminfo.read_text())
            reason = decide(info, a.baseline_unaccounted, max_growth, min_available)
            samples.write(json.dumps({'t': time.time(), 'available': info['MemAvailable'],
                                      'unaccounted': unaccounted_bytes(info),
                                      'swap_free': info.get('SwapFree'), 'container_seen': seen}) + '\n')
            samples.flush()
            if reason and seen:
                try:
                    (group / 'cgroup.kill').write_text('1')
                    killed = True
                except OSError as exc:
                    killed = f'{type(exc).__name__}: {exc}'
                receipt = {'at': time.time(), 'reason': reason, 'container_id': a.container_id,
                           'cgroup_kill': killed, 'baseline_unaccounted': a.baseline_unaccounted,
                           'max_growth': max_growth, 'min_available': min_available,
                           'mlockall': locked, 'meminfo_bytes': info}
                (a.out / 'MEMORY-GUARD.json').write_text(json.dumps(receipt, indent=2) + '\n')
                return FIRED_EXIT
            time.sleep(a.interval)
    return 0


if __name__ == '__main__':
    sys.exit(main())

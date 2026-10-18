"""Serial compiler turn for future briefs; packet94's sealed copy is frozen.

Observe coordination only: never acquire its locks or edit its markers. A hold
is published BEFORE admission, so it alone does not prove a whole-host window
has started. The compiler lock, polling budget and caller's limits are retained.
"""
import contextlib
import fcntl
import json
import os
from pathlib import Path
import time

LOCK = Path('/tmp/own-xpu-runtime-cpu-compile.lock')
COORD = Path('/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1')
PROC = Path('/proc')
COMPILERS = frozenset(('cmake', 'gmake', 'make', 'ninja', 'icpx', 'icx',
    'g++', 'cc1plus', 'clang++', 'clang', 'clang-21', 'clang-20', 'ld.lld',
    'llvm-link', 'sycl-post-link', 'clang-offload-w'))


def process_table(proc=PROC):
    """Read identities, names and cgroups only; never expose argv/environment."""
    rows = {}
    for path in proc.iterdir():
        if not path.name.isdigit():
            continue
        try:
            stat = (path / 'stat').read_text().rsplit(')', 1)[1].split()
            if stat[0] in ('Z', 'X', 'x'):
                continue
            rows[int(path.name)] = dict(
                ppid=int(stat[1]), start_ticks=int(stat[19]),
                comm=(path / 'comm').read_text().strip())
        except (OSError, ValueError, IndexError):
            continue
    return rows


def device_descendants(owner, rows):
    """Match the reservation owner identity, not a reused PID or B's worker."""
    pid = owner.get('pid')
    if pid not in rows or rows[pid]['start_ticks'] != owner.get('start_ticks'):
        return []
    result = []
    for child, row in rows.items():
        if row['comm'] != 'own-rt-iq3':
            continue
        ancestor, seen = child, set()
        while ancestor in rows and ancestor not in seen:
            if ancestor == pid:
                result.append(child)
                break
            seen.add(ancestor)
            ancestor = rows[ancestor]['ppid']
    return result


def present(path):
    return path.exists() or path.is_symlink()


def whole_host_blockers(root, rows):
    hold = root / 'hold-lane-B'
    marker = root / 'active-lane-A.json'
    try:
        # Keep malformed/unreadable coordination conservative, as the old gate
        # did. A known admission wait is the only new permission to compile.
        if present(hold):
            if not present(root / 'active-lane-B.json'):
                return [(-1, hold.name)]
            owner = json.loads(hold.read_text())
            if (not isinstance(owner, dict) or owner.get('scope') != 'whole-host'
                    or owner.get('lane') != 'A' or type(owner.get('pid')) is not int
                    or type(owner.get('start_ticks')) is not int):
                return [(-1, 'unreadable whole-host hold')]
            if device_descendants(owner, rows):
                return [(-1, hold.name)]
            return []  # B still owns its lane; A has no device child.
        if present(marker):
            owner = json.loads(marker.read_text())
            if not isinstance(owner, dict):
                return [(-1, 'unreadable whole-host marker')]
            if owner.get('scope') == 'whole-host' and (
                    not present(root / 'active-lane-B.json') or
                    device_descendants(owner, rows)):
                return [(-1, marker.name)]
    except (OSError, ValueError, TypeError):
        return [(-1, 'unreadable whole-host coordination')]
    return []


def active():
    rows = process_table(PROC)
    return ([(pid, row['comm']) for pid, row in rows.items()
             if row['comm'] in COMPILERS] + whole_host_blockers(COORD, rows))


@contextlib.contextmanager
def turn():
    with LOCK.open('a+') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        end = time.monotonic() + 3600
        while True:
            blockers = active()
            if not blockers:
                break
            print('Waiting for compiler turn:', blockers, flush=True)
            if time.monotonic() > end:
                raise TimeoutError('compiler turn deadline')
            time.sleep(10)
        stream.seek(0)
        stream.truncate()
        stream.write('ops pid=' + str(os.getpid()) + '\n')
        stream.flush()
        from build_engine import limits
        limits()
        yield

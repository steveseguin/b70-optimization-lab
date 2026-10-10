"""Bounded, cached allocated-block accounting for one continuation run. CPU only.

Directory membership is cached by inode/mtime/ctime; file blocks are re-statted
on every check (in-place log growth does not change directory mtime). Totals are
updated by per-path deltas, including deletion, never by global free-space delta.
Checks serialize prompt/decode/status callers. This is a metadata snapshot, not
an atomic filesystem transaction or a quota; in-flight writes appear next check.
"""
import os
from pathlib import Path
import re
import shutil
import stat
import threading

GIB = 2 ** 30
RESERVE_BYTES = 50 * GIB
DEFAULT_ALLOWANCE_GIB = 3
MAX_ENTRIES = 200000
MAX_DEPTH = 32
ACCOUNTING = 'run-owned-st_blocks-v1'


def parse_allowance_gib(value):
    if type(value) is not str or re.fullmatch(r'(?:[1-9]|[1-5][0-9]|6[0-4])', value) is None:
        raise ValueError('LTX_RUN_WRITE_ALLOWANCE_GIB must be an integer GiB from 1 to 64')
    return int(value) * GIB


def launch_allowance_bytes(environ=None):
    return parse_allowance_gib((os.environ if environ is None else environ).get(
        'LTX_RUN_WRITE_ALLOWANCE_GIB', str(DEFAULT_ALLOWANCE_GIB)))


def validate_allowance_bytes(value):
    if type(value) is not int or value % GIB or not GIB <= value <= 64 * GIB:
        raise ValueError('Invalid run_write_allowance_bytes')
    return value


class OwnWrites:
    def __init__(self, root, run, prefix, *, max_entries=MAX_ENTRIES, max_depth=MAX_DEPTH):
        self.root, self.run = Path(root), Path(run)
        if self.run.parent != self.root or not re.fullmatch(r'stream[0-9]+[a-z]?', prefix):
            raise ValueError('Invalid storage ownership scope')
        self.prefix = prefix + '-'
        self.max_entries, self.max_depth = max_entries, max_depth
        self._dirs, self._blocks = {}, {}
        self._total = 0
        self._lock = threading.RLock()
        self.scans = 0

    def allocated_bytes(self):
        with self._lock:
            seen, used_dirs = set(), set()
            visited = 0
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC

            def budget():
                nonlocal visited
                visited += 1
                if visited > self.max_entries:
                    raise RuntimeError('Run storage walk entry bound exceeded')

            def record(key, st):
                seen.add(key)
                blocks = st.st_blocks * 512
                self._total += blocks - self._blocks.get(key, 0)
                self._blocks[key] = blocks

            def walk(fd, key, depth=0, select=None, count_self=True):
                if depth > self.max_depth:
                    raise RuntimeError('Run storage walk depth bound exceeded')
                st = os.fstat(fd)
                if st.st_dev != device:
                    raise RuntimeError('Run storage refuses a cross-filesystem entry')
                if count_self:
                    budget()
                    record(key, st)
                signature = (st.st_dev, st.st_ino, st.st_mtime_ns, st.st_ctime_ns)
                used_dirs.add(key)
                cached = self._dirs.get(key)
                if cached is not None and cached[0] == signature:
                    names = cached[1]
                else:
                    names = []
                    with os.scandir(fd) as entries:
                        for entry in entries:
                            if len(names) >= self.max_entries:
                                raise RuntimeError('Run storage directory entry bound exceeded')
                            names.append(entry.name)
                    # A changing listing must be retried on the next check.
                    after = os.fstat(fd)
                    after_sig = (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns)
                    if after_sig == signature:
                        self._dirs[key] = (signature, names)
                    else:
                        self._dirs.pop(key, None)
                for name in names:
                    budget()  # shared, excluded entries also consume the walk bound
                    if select is not None and not select(name):
                        continue
                    child_key = key + '/' + name
                    try:
                        child = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    except FileNotFoundError:  # atomic temporary publication / consumed preview deletion
                        continue
                    if child.st_dev != device:
                        raise RuntimeError('Run storage refuses a cross-filesystem entry')
                    if stat.S_ISDIR(child.st_mode):
                        try:
                            sub = os.open(name, flags, dir_fd=fd)
                        except FileNotFoundError:
                            continue
                        try:
                            if os.fstat(sub).st_ino != child.st_ino:
                                raise RuntimeError('Run storage directory identity changed')
                            walk(sub, child_key, depth + 1)
                        finally:
                            os.close(sub)
                    elif stat.S_ISREG(child.st_mode):
                        if child.st_nlink != 1:
                            raise RuntimeError('Run storage refuses multiply linked files')
                        record(child_key, child)
                    else:
                        raise RuntimeError('Run storage refuses symlink or special entry')

            root_fd = os.open(self.root, flags)
            try:
                device = os.fstat(root_fd).st_dev
                run_fd = os.open(self.run.name, flags, dir_fd=root_fd)
                try:
                    walk(run_fd, 'run')
                finally:
                    os.close(run_fd)
                # Open shared parents relative to verified directory descriptors.
                for directory in ('output', 'requests'):
                    try:
                        fd = os.open(directory, flags, dir_fd=root_fd)
                    except FileNotFoundError:
                        continue
                    try:
                        walk(fd, directory, select=lambda n: n.startswith(self.prefix), count_self=False)
                        if directory == 'output':
                            try:
                                validation = os.open('validation', flags, dir_fd=fd)
                            except FileNotFoundError:
                                continue
                            try:
                                walk(validation, 'output/validation', select=lambda n: n.startswith(self.prefix), count_self=False)
                            finally:
                                os.close(validation)
                    finally:
                        os.close(fd)
            finally:
                os.close(root_fd)
            for key in self._blocks.keys() - seen:
                self._total -= self._blocks.pop(key)
            for key in self._dirs.keys() - used_dirs:
                del self._dirs[key]
            self.scans += 1
            return self._total

    def check(self, allowance, require):
        validate_allowance_bytes(allowance)
        free = shutil.disk_usage(self.root).free
        consumed = self.allocated_bytes()
        require(free >= RESERVE_BYTES and consumed <= allowance,
                'Stream storage allowance exhausted (50 GiB reserve, %d GiB run allowance)' % (allowance // GIB))
        return {'free_bytes': free, 'consumed_bytes': consumed, 'allowance_bytes': allowance,
                'run_write_allowance_bytes': allowance, 'reserve_bytes': RESERVE_BYTES,
                'accounting': ACCOUNTING}

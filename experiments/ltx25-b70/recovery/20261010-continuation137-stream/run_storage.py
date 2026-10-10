"""Bounded, cached allocated-block accounting for one continuation run. CPU only.

Directory membership is cached by inode/mtime/ctime; file blocks are re-statted
on every check (in-place log growth does not change directory mtime). Totals are
counted once per (device, inode), including deletion, never by global free-space delta.
Ownership includes the run directory and its prefix-filtered output/requests trees.
A link anomaly gets one fresh walk after 10 ms; external links fail closed.
Checks serialize prompt/decode/status callers. This is a metadata snapshot, not
an atomic filesystem transaction or a quota; in-flight writes appear next check.
"""
import os
from pathlib import Path
import re
import shutil
import stat
import threading
import time

GIB = 2 ** 30
RESERVE_BYTES = 50 * GIB
DEFAULT_ALLOWANCE_GIB = 3
MAX_ENTRIES = 200000
MAX_DEPTH = 32
ACCOUNTING = 'run-owned-st_blocks-v1'
LINK_RECHECK_SECONDS = 0.01


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

    def _scan(self, final):
        seen, used_dirs = set(), set()
        blocks_by_key, inodes = {}, {}
        unusual = False
        visited = 0
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC

        def budget():
            nonlocal visited
            visited += 1
            if visited > self.max_entries:
                raise RuntimeError('Run storage walk entry bound exceeded')

        def record(key, st):
            seen.add(key)
            blocks_by_key[key] = st.st_blocks * 512

        def walk(fd, key, depth=0, select=None, count_self=True):
            nonlocal unusual
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
                    # An unlink may complete after lookup: nlink=0 is not a
                    # hard link. Refresh membership once before accepting it.
                    unusual |= child.st_nlink != 1
                    if child.st_nlink == 0:
                        continue
                    identity = (child.st_dev, child.st_ino)
                    row = inodes.setdefault(identity, {'paths': [], 'nlinks': set(), 'blocks': 0})
                    row['paths'].append(child_key)
                    row['nlinks'].add(child.st_nlink)
                    row['blocks'] = max(row['blocks'], child.st_blocks * 512)
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
        unusual |= any(len(row['nlinks']) != 1 or next(iter(row['nlinks'])) != len(set(row['paths']))
                       for row in inodes.values())
        if unusual and not final:
            return None
        for identity, row in inodes.items():
            paths, links = row['paths'], row['nlinks']
            # Every hard link is a directory entry. Matching the inode's
            # link count against distinct owned entries proves no link is
            # outside this run's accounting scope at this metadata snapshot.
            owned = len(set(paths))
            if len(links) != 1 or next(iter(links)) != owned:
                key = paths[0]
                path = str(self.run / key[4:]) if key.startswith('run/') else str(self.root / key)
                detail = ('Run storage link ownership refused: path=%r nlink=%s '
                          'owned_links=%d dev=%d inode=%d rechecked_once=True' %
                          (path, sorted(links), owned, *identity))
                if max(links) > owned:
                    raise RuntimeError(detail + '; link outside owned run tree')
                raise RuntimeError(detail + '; directory entries changed during bounded recheck')
            blocks_by_key[identity] = row['blocks']
        for key in self._dirs.keys() - used_dirs:
            del self._dirs[key]
        self._blocks = blocks_by_key
        self._total = sum(blocks_by_key.values())
        self.scans += 1
        return self._total

    def allocated_bytes(self):
        with self._lock:
            value = self._scan(final=False)
            if value is not None:
                return value
            # Exactly one bounded retry of the whole owned namespace, not one
            # wait per file. Never sleep under the background publication lock.
            time.sleep(LINK_RECHECK_SECONDS)
            self._dirs.clear()
            return self._scan(final=True)

    def check(self, allowance, require):
        validate_allowance_bytes(allowance)
        free = shutil.disk_usage(self.root).free
        consumed = self.allocated_bytes()
        require(free >= RESERVE_BYTES and consumed <= allowance,
                'Stream storage allowance exhausted (50 GiB reserve, %d GiB run allowance)' % (allowance // GIB))
        return {'free_bytes': free, 'consumed_bytes': consumed, 'allowance_bytes': allowance,
                'run_write_allowance_bytes': allowance, 'reserve_bytes': RESERVE_BYTES,
                'accounting': ACCOUNTING}


# Candidate sampling is restricted to streaming (no full capture writes).
SCAN_PERIOD_S = 0.25
MAX_SAMPLE_AGE_S = 1.0
PENDING_WRITE_BYTES = 256 * 2 ** 20


def launch_scan_mode(environ=None):
    value = (os.environ if environ is None else environ).get('LTX_STORAGE_SCAN_MODE', 'request')
    if value not in ('request', 'background'):
        raise ValueError('LTX_STORAGE_SCAN_MODE must be request or background')
    return value


class BackgroundOwnWrites:
    """Sample the unchanged strict walk on one CPU helper, never under a caller lock.

    The short state lock protects publication only, not traversal. Every check
    still performs statvfs and keeps the parent's reserve and allowance. Refuse
    stale, absent or failed samples, and reserve 256 MiB for writes in flight.
    Qualification always uses the original synchronous account instead.
    """
    def __init__(self, account, *, clock=time.monotonic, period=SCAN_PERIOD_S,
                 max_age=MAX_SAMPLE_AGE_S):
        self.account, self.clock, self.period, self.max_age = account, clock, period, max_age
        self.lock = threading.Condition()
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.thread = None
        self.sample = None
        self.failed = None
        self.samples = 0
        self.requested_epoch = 0
        self.completed_epoch = -1

    def refresh(self):
        # No publication/state lock is held during any file operation.
        with self.lock:
            epoch = self.requested_epoch
        started = self.clock()
        try:
            consumed = self.account.allocated_bytes()
            ended = self.clock()
            with self.lock:
                self.samples += 1
                self.sample = {'consumed_bytes': consumed, 'scan_start': started,
                               'scan_end': ended, 'scan_seconds': ended - started,
                               'sample_generation': self.samples}
                self.completed_epoch = epoch
                self.lock.notify_all()
        except BaseException as error:
            with self.lock:
                if self.failed is None:
                    self.failed = repr(error)  # Preserve the full offending path and link count.
                self.lock.notify_all()

    def start(self):
        if self.thread is not None:
            return
        # Initial scan occurs at qualification completion, before streaming admission.
        self.refresh()
        self.thread = threading.Thread(target=self._loop, daemon=True,
                                       name='ltx126-storage-accounting')
        if self.failed is None:
            self.thread.start()

    def _loop(self):
        while not self.stop.is_set():
            self.wake.wait(self.period)
            self.wake.clear()
            if self.stop.is_set():
                return
            self.refresh()
            with self.lock:
                if self.completed_epoch < self.requested_epoch:
                    self.wake.set()
            if self.failed is not None:
                return

    def published(self):
        with self.lock:
            self.requested_epoch += 1
        self.wake.set()

    def check(self, allowance, require):
        check_started = time.perf_counter()
        validate_allowance_bytes(allowance)
        with self.lock:
            ready = self.lock.wait_for(lambda: self.failed is not None or
                                      self.completed_epoch >= self.requested_epoch, timeout=2.0)
            require(ready, 'Stream storage accounting completion timeout')
            required_epoch = self.requested_epoch
            sample = None if self.sample is None else dict(self.sample)
            failed = self.failed
        waited = time.perf_counter() - check_started
        require(failed is None, 'Stream storage accounting failed: ' + str(failed))
        require(sample is not None, 'Stream storage accounting sample missing')
        # Age starts before traversal so a blocked scanner cannot publish freshness.
        age = self.clock() - sample['scan_start']
        require(0 <= age <= self.max_age, 'Stream storage accounting sample stale')
        free = shutil.disk_usage(self.account.root).free
        consumed = sample['consumed_bytes']
        require(free >= RESERVE_BYTES and consumed + PENDING_WRITE_BYTES <= allowance,
                'Stream storage allowance exhausted (50 GiB reserve, %d GiB run allowance; '
                '256 MiB pending-write headroom)' % (allowance // GIB))
        return {'free_bytes': free, 'consumed_bytes': consumed, 'allowance_bytes': allowance,
                'run_write_allowance_bytes': allowance, 'reserve_bytes': RESERVE_BYTES,
                'accounting': ACCOUNTING, 'scan_mode': 'background',
                'sample_age_s': age, 'scan_seconds': sample['scan_seconds'],
                'sample_wait_seconds': waited, 'check_seconds': time.perf_counter() - check_started,
                'sample_generation': sample['sample_generation'],
                'completed_write_epoch': required_epoch,
                'pending_write_reserve_bytes': PENDING_WRITE_BYTES}

    def close(self):
        # Cooperative test cleanup; the live process owns the daemon lifetime.
        self.stop.set()
        self.wake.set()
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(5)

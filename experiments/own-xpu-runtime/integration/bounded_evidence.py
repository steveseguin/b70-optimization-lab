"""Exclusive, byte-bounded append evidence; no native FD, truncation or cleanup.

The limit covers payload bytes routed through this object, not filesystem block
rounding/metadata, native files, stderr inherited by a child, or driver caches.
A refused/full/failed writer preserves all existing bytes and becomes unusable.
The caller must halt new work and arrange its own cooperative drain; do not pipe
a native producer here without a separately reviewed backpressure/drain design.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat
import threading


class EvidenceRefusal(RuntimeError):
    pass


class EvidenceLimit(EvidenceRefusal):
    pass


def require(condition, message):
    if not condition:
        raise EvidenceRefusal(message)


def signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


class BoundedEvidence:
    def __init__(self, root, *, total_limit_bytes, max_files=16):
        require(type(total_limit_bytes) is int and total_limit_bytes > 0, 'positive byte limit required')
        require(type(max_files) is int and 1 <= max_files <= 128, 'bounded file count required')
        root = Path(root)
        require(root.is_absolute() and root.resolve() == root, 'absolute real private directory required')
        info = root.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and
                stat.S_IMODE(info.st_mode) == 0o700, 'owned0700 directory required')
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            held = os.fstat(fd)
            require((held.st_dev, held.st_ino) == (info.st_dev, info.st_ino), 'directory changed while opening')
        except BaseException:
            os.close(fd)
            raise
        self.root, self._root_fd = root, fd
        self._root_identity = (held.st_dev, held.st_ino)
        self.total_limit_bytes, self.max_files = total_limit_bytes, max_files
        self._files = {}
        self._total = 0
        self._failure = None
        self._closed = False
        self._lock = threading.RLock()

    def _ready(self):
        if self._failure is not None:
            raise self._failure
        require(not self._closed, 'evidence writer closed')
        info = self.root.lstat()
        require(stat.S_ISDIR(info.st_mode) and (info.st_dev, info.st_ino) == self._root_identity
                and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
                'evidence root replaced or permissions changed')

    def _fail(self, error):
        if self._failure is None:
            self._failure = error

    def create(self, name, *, limit_bytes):
        """Create one new0600 file exclusively; never adopt or overwrite a file."""
        with self._lock:
            fd = None
            try:
                self._ready()
                require(type(name) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', name, re.ASCII),
                        'single safe evidence filename required')
                require(name not in self._files, 'evidence name already owned')
                require(type(limit_bytes) is int and 0 < limit_bytes <= self.total_limit_bytes,
                        'positive file limit within aggregate required')
                if len(self._files) >= self.max_files:
                    raise EvidenceLimit('evidence file count exhausted')
                fd = os.open(name, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_EXCL |
                             os.O_CLOEXEC | os.O_NOFOLLOW, 0o600, dir_fd=self._root_fd)
                info = os.fstat(fd)
                require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size == 0,
                        'exclusive regular evidence file required')
                self._files[name] = dict(fd=fd, limit=limit_bytes, written=0, signature=signature(info))
                fd = None
                os.fsync(self._root_fd)
            except BaseException as error:
                self._fail(error)
                if fd is not None:
                    os.close(fd)
                raise

    def append(self, name, payload):
        """Append bytes only after entire chunk fits; preserve partial OS writes."""
        with self._lock:
            try:
                self._ready()
                require(type(payload) is bytes, 'pre-encoded bytes required')
                require(name in self._files, 'unowned evidence file')
                row = self._files[name]
                held = os.fstat(row['fd'])
                named = os.stat(name, dir_fd=self._root_fd, follow_symlinks=False)
                require(signature(held) == row['signature'] == signature(named) and held.st_nlink == 1,
                        'evidence inode/content changed outside writer')
                count = len(payload)
                if row['written'] + count > row['limit'] or self._total + count > self.total_limit_bytes:
                    raise EvidenceLimit('evidence byte limit exhausted before append')
                view = memoryview(payload)
                while view:
                    written = os.write(row['fd'], view)
                    if written <= 0:
                        raise OSError('evidence write made no progress')
                    row['written'] += written
                    self._total += written
                    view = view[written:]
                os.fsync(row['fd'])
                row['signature'] = signature(os.fstat(row['fd']))
                return count
            except BaseException as error:
                self._fail(error)
                raise

    def status(self):
        with self._lock:
            return dict(payload_bytes=self._total, total_limit_bytes=self.total_limit_bytes,
                        closed=self._closed, halted=self._failure is not None,
                        error_type=None if self._failure is None else type(self._failure).__name__,
                        files={n:dict(payload_bytes=r['written'], limit_bytes=r['limit']) for n,r in self._files.items()},
                        scope='payload bytes only; filesystem/native/cache growth excluded')

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            errors = []
            for row in self._files.values():
                try:
                    os.close(row['fd'])
                except OSError as error:
                    errors.append(error)
            try:
                os.close(self._root_fd)
            except OSError as error:
                errors.append(error)
            if errors:
                raise errors[0]

    def __enter__(self):
        return self

    def __exit__(self, kind, error, traceback):
        try:
            self.close()
        except BaseException as cleanup:
            if error is None:
                raise
            error.add_note('evidence close failed: ' + str(cleanup))

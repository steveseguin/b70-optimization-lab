"""Packet129 immutable evidence publication; no device imports or reader retries.

Final names appear only after file fsync. RENAME_NOREPLACE preserves both
exclusive-write semantics and the reader's inode/ctime/nlink identity guard.
Partial files are private staging names, never evidence names.
"""
import ctypes
import hashlib
import os
from pathlib import Path
import stat


def safe_path(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError('Unsafe evidence path')
    return path


def temporary_name(final):
    final = safe_path(final)
    return final.with_name('.' + final.name + '.partial')


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish_file(tmp, final):
    tmp, final = safe_path(tmp), safe_path(final)
    if tmp.parent != final.parent or tmp == final:
        raise RuntimeError('Evidence publication requires a distinct same-directory temporary file')
    fd = os.open(tmp, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise RuntimeError('Nonregular or linked evidence staging file')
        os.fsync(fd)
    finally:
        os.close(fd)
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(tmp), -100, os.fsencode(final), 1) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(final))
    fsync_directory(final.parent)


def publish_bytes(path, raw):
    final = safe_path(path)
    tmp = temporary_name(final)
    # O_EXCL also refuses abandoned staging files; no overwrite/retry/cleanup loop.
    with tmp.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    publish_file(tmp, final)
    return hashlib.sha256(raw).hexdigest()

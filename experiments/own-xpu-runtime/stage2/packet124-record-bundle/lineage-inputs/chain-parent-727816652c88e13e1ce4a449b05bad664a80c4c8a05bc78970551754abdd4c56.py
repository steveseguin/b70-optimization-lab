#!/usr/bin/env python3
"""Preserve exact sanitizer binaries as verified gzip archives; never touch other builds."""
import argparse
import gzip
import hashlib
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import uuid
import storage

P = Path(__file__).resolve().parent
# The registered build link is intentional; reject symlinks BELOW its resolved root.
B = (P / 'build').resolve()
SCHEMA = 'packet49c.asan-artifact-retention.v1'
CHUNK = 1024 * 1024
RECEIPT_NAME = 'asan-artifact-retention.json'


def _regular(path):
    """Require an existing regular file, never following a leaf symlink."""
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('not a regular file: ' + str(path))
    return info


def _path(name, archive=False):
    if not isinstance(name, str):
        raise ValueError('artifact path must be text')
    part = PurePosixPath(name)
    if (part.is_absolute() or str(part) != name or '..' in part.parts or
            len(part.parts) != (3 if archive else 2) or part.parts[0] != 'asan' or
            (archive and (part.parts[1] != 'retained' or not part.name.endswith('.gz')))):
        raise ValueError('path outside sanitizer artifact scope: ' + name)
    current = B
    if current.is_symlink() or not current.is_dir():
        raise ValueError('resolved build root must be an existing directory')
    for component in part.parts:
        current = current / component
        if current.is_symlink():
            raise ValueError('sanitizer artifact symlink: ' + str(current))
    if not current.resolve().is_relative_to(B):
        raise ValueError('artifact escapes build root')
    return current


def _open_read(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError('not a regular opened file: ' + str(path))
    return os.fdopen(descriptor, 'rb')


def _sha(path):
    _regular(path)
    digest = hashlib.sha256()
    with _open_read(path) as source:
        for block in iter(lambda: source.read(CHUNK), b''):
            digest.update(block)
    return digest.hexdigest()


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, stat.S_IMODE(info.st_mode))


def _build_receipt():
    source = P / 'build-asan-receipt.json'
    _regular(source)
    row = json.loads(source.read_text())
    if row.get('passed') is not True or row.get('device_executed') is not False or row.get('mode') != 'asan':
        raise ValueError('a passing CPU sanitizer build receipt is required')
    artifacts = row.get('artifacts_sha256')
    if not isinstance(artifacts, dict) or not artifacts:
        raise ValueError('missing sanitizer artifact inventory')
    for name, digest in artifacts.items():
        _path(name)
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('invalid original artifact SHA256')
    return source, artifacts


def _stream_original(archive, expected_bytes, expected_sha):
    """Read the complete gzip stream, with an explicit uncompressed extent cap."""
    _regular(archive)
    digest = hashlib.sha256()
    total = 0
    with _open_read(archive) as raw, gzip.GzipFile(fileobj=raw, mode='rb') as source:
        while True:
            block = source.read(CHUNK)
            if not block:
                break
            total += len(block)
            if total > expected_bytes:
                raise ValueError('archive exceeds recorded original extent')
            digest.update(block)
    if total != expected_bytes or digest.hexdigest() != expected_sha:
        raise ValueError('archive does not restore original bytes: ' + str(archive))


def _verify_original(path, row):
    info = _regular(path)
    if info.st_size != row['bytes'] or stat.S_IMODE(info.st_mode) != row['mode_permissions']:
        raise ValueError('original size/permissions changed: ' + str(path))
    if _sha(path) != row['original_sha256'] or _stamp(_regular(path)) != _stamp(info):
        raise ValueError('original bytes changed while checked: ' + str(path))
    return info


def verify_retention():
    """Verify archived bytes and all surviving originals; used by the packet seal."""
    path = P / RECEIPT_NAME
    _regular(path)
    receipt = json.loads(path.read_text())
    source, expected = _build_receipt()
    if (receipt.get('schema') != SCHEMA or receipt.get('passed') is not True or
            receipt.get('device_executed') is not False or
            receipt.get('build_receipt') != source.name or
            receipt.get('build_receipt_sha256') != _sha(source)):
        raise ValueError('retention/build receipt binding mismatch')
    rows = receipt.get('artifacts')
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError('retention artifact inventory mismatch')
    names = set()
    archives = set()
    for row in rows:
        name = row['original']
        if name in names or expected.get(name) != row['original_sha256']:
            raise ValueError('retention original identity mismatch')
        names.add(name)
        original = _path(name)
        if row['archive'] != 'asan/retained/' + original.name + '.gz' or row['archive'] in archives:
            raise ValueError('retention archive identity mismatch')
        archives.add(row['archive'])
        archive = _path(row['archive'], archive=True)
        if (type(row['bytes']) is not int or row['bytes'] < 0 or
                type(row['archive_bytes']) is not int or row['archive_bytes'] < 1 or
                type(row['mode_permissions']) is not int or not 0 <= row['mode_permissions'] <= 0o777):
            raise ValueError('invalid retention size or permissions')
        info = _regular(archive)
        if info.st_size != row['archive_bytes'] or _sha(archive) != row['archive_sha256']:
            raise ValueError('archive identity mismatch')
        _stream_original(archive, row['bytes'], row['original_sha256'])
        if _stamp(_regular(archive)) != _stamp(info):
            raise ValueError('archive changed while checked')
        if original.exists() or original.is_symlink():
            _verify_original(original, row)
    if names != set(expected):
        raise ValueError('retention omits a sanitizer artifact')
    if (receipt.get('original_bytes') != sum(r['bytes'] for r in rows) or
            receipt.get('archive_bytes') != sum(r['archive_bytes'] for r in rows)):
        raise ValueError('retention aggregate extent mismatch')
    return receipt


def _archive_one(name, expected_sha):
    original = _path(name)
    before = _regular(original)
    permissions = stat.S_IMODE(before.st_mode)
    if permissions & ~0o777:
        raise ValueError('special file permissions are not admitted')
    row = dict(original=name, original_sha256=expected_sha, bytes=before.st_size,
               archive='asan/retained/' + original.name + '.gz', mode_permissions=permissions)
    _verify_original(original, row)
    archive = _path(row['archive'], archive=True)
    if not archive.exists():
        # Conservative gzip expansion bound; original and archive coexist here.
        storage.cpu_build_admit(before.st_size + before.st_size // 100 + 65536)
        archive.parent.mkdir(exist_ok=True)
        _path(row['archive'], archive=True)
        temporary = archive.parent / (archive.name + '.partial-' + uuid.uuid4().hex)
        digest = hashlib.sha256()
        total = 0
        try:
            with temporary.open('xb') as target:
                with _open_read(_path(name)) as source, gzip.GzipFile(filename='', mode='wb', fileobj=target, mtime=0, compresslevel=6) as compressed:
                    for block in iter(lambda: source.read(CHUNK), b''):
                        total += len(block)
                        if total > before.st_size:
                            raise ValueError('original grew during compression')
                        digest.update(block)
                        compressed.write(block)
                target.flush()
                os.fsync(target.fileno())
            if (total != before.st_size or digest.hexdigest() != expected_sha or
                    _stamp(_regular(original)) != _stamp(before)):
                raise ValueError('original mutated during compression')
            _stream_original(temporary, total, expected_sha)
            # Hard-link installs only if absent, with no overwrite race.
            os.link(temporary, archive, follow_symlinks=False)
        finally:
            if temporary.exists():
                temporary.unlink()
    _verify_original(original, row)
    _stream_original(archive, row['bytes'], expected_sha)
    row.update(archive_sha256=_sha(archive), archive_bytes=_regular(archive).st_size)
    return row


def _write_receipt(receipt):
    path = P / RECEIPT_NAME
    payload = (json.dumps(receipt, indent=2) + '\n').encode()
    storage.cpu_build_admit(len(payload))
    temporary = P / (RECEIPT_NAME + '.partial-' + uuid.uuid4().hex)
    try:
        with temporary.open('xb') as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        os.link(temporary, path, follow_symlinks=False)
    finally:
        if temporary.exists():
            temporary.unlink()


def _consumer_ready():
    consumer = importlib.import_module('p49_seal')
    if getattr(consumer, 'SANITIZER_ARCHIVE_RETENTION', None) != SCHEMA:
        raise ValueError('update packet seal archive consumer before removing originals')


def retain():
    """Archive, verify, record, verify consumer support, then remove exact originals."""
    if (P / RECEIPT_NAME).exists() or (P / RECEIPT_NAME).is_symlink():
        receipt = verify_retention()
    else:
        source, artifacts = _build_receipt()
        source_sha = _sha(source)
        rows = [_archive_one(name, digest) for name, digest in sorted(artifacts.items())]
        if _sha(source) != source_sha:
            raise ValueError('build receipt changed while archiving')
        receipt = dict(schema=SCHEMA, passed=True, device_executed=False,
                       build_receipt=source.name, build_receipt_sha256=source_sha,
                       artifacts=rows, original_bytes=sum(r['bytes'] for r in rows),
                       archive_bytes=sum(r['archive_bytes'] for r in rows),
                       restore_command='python3 -B retain_sanitizers.py --restore')
        _write_receipt(receipt)
        receipt = verify_retention()
    _consumer_ready()
    # Recheck every archive and source before the first deletion.
    verify_retention()
    for row in receipt['artifacts']:
        original = _path(row['original'])
        if original.exists():
            before = _verify_original(original, row)
            if _stamp(_regular(original)) != _stamp(before):
                raise ValueError('original changed before removal')
            original.unlink()
    return verify_retention()


def restore():
    """Restore exact bytes without overwriting any existing differing file."""
    receipt = verify_retention()
    for row in receipt['artifacts']:
        original = _path(row['original'])
        if original.exists():
            _verify_original(original, row)
            continue
        archive = _path(row['archive'], archive=True)
        storage.cpu_build_admit(row['bytes'])
        temporary = original.parent / (original.name + '.restore-' + uuid.uuid4().hex)
        digest = hashlib.sha256()
        total = 0
        try:
            with temporary.open('xb') as out, _open_read(archive) as raw, gzip.GzipFile(fileobj=raw, mode='rb') as source:
                for block in iter(lambda: source.read(CHUNK), b''):
                    total += len(block)
                    if total > row['bytes']:
                        raise ValueError('restore exceeds recorded extent')
                    digest.update(block)
                    out.write(block)
                if total != row['bytes'] or digest.hexdigest() != row['original_sha256']:
                    raise ValueError('restore original hash mismatch')
                os.fchmod(out.fileno(), row['mode_permissions'])
                out.flush()
                os.fsync(out.fileno())
            _path(row['original'])
            os.link(temporary, original, follow_symlinks=False)
        finally:
            if temporary.exists():
                temporary.unlink()
        _verify_original(original, row)
    return verify_retention()


def main():
    assert sys.dont_write_bytecode, 'run with python3 -B'
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice -n 19 required'
    assert set(os.sched_getaffinity(0)) <= set(range(4,16)) | set(range(20,32)), 'registered CPU affinity required'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    receipt = restore() if args.restore else retain()
    print(json.dumps(dict(passed=True, restored=args.restore, artifacts=len(receipt['artifacts']),
                          original_bytes=receipt['original_bytes'], archive_bytes=receipt['archive_bytes'])))

if __name__ == '__main__':
    main()

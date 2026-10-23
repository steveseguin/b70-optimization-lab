#!/usr/bin/env python3
"""One-shot archival copy of four closed p184 checkpoints; never deletes.

--plan is read-only. --copy-verify creates a new tar and a new receipt, verifies
every member, then rehashes every original. Failures preserve partial artifacts
and refuse a second attempt at the same paths. No native executable is invoked.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PACKET = ROOT / 'experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint'
EVIDENCE = PACKET / 'v5/evidence'
TREES = tuple(EVIDENCE / run / 'run/checkpoints' / cid for run, cid in (
    ('device-smoke-B-p184', 's1'),
    ('device-lifecycle-B-p184', 's1'),
    ('device-lifecycle-B-p184', 's2'),
    ('device-lifecycle-B-p184', 'sref'),
))
ARCHIVE = Path('/mnt/usb-models/own-runtime-archives/p184-closed-checkpoints-20261023.tar')
RECEIPT = EVIDENCE / 'checkpoint-archive-20261023.json'
TOTAL_BIN_BYTES = 530718848
TENSOR_BYTES = 530629120


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def stamp(path):
    s = path.lstat()
    require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'not a private regular file: ' + str(path))
    return dict(dev=s.st_dev, ino=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns, blocks=s.st_blocks)


def sha_stream(stream):
    return hashlib.file_digest(stream, 'sha256').hexdigest()


def pin(path):
    before = stamp(path)
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        require((opened.st_dev, opened.st_ino) == (before['dev'], before['ino']), 'file replaced before read')
        digest = sha_stream(stream)
    require(stamp(path) == before, 'file changed during read: ' + str(path))
    return dict(sha256=digest, stamp=before)


def read(path):
    return json.loads(path.read_text())


def rel(path):
    return path.relative_to(ROOT).as_posix()


def tensor(path):
    return path.suffix == '.bin' and (path.name.startswith('blk.') or '.blk.' in path.name)


def inventory():
    """Closed file sets, complete native manifest checks, and closure receipts."""
    entries, directories = {}, set()
    for tree in TREES:
        require(tree.resolve() == tree and tree.is_dir(), 'checkpoint tree is missing or aliased')
        manifest = read(tree / 'manifest.json')
        require(manifest['label'] == 'experimental-two-card' and manifest['contract'] == 'v1.2+p184',
                'checkpoint contract changed')
        require(manifest['checkpoint_id'] == tree.name, 'checkpoint ID mismatch')
        expected = {'manifest.json': None, 'fields.tsv': None,
                    'tokens.bin': dict(bytes=manifest['token_state']['length'] * 4,
                                       sha256=manifest['token_state']['tokens_sha256'])}
        require([r['directory'] for r in manifest['ranks']] == ['rank0', 'rank1'], 'rank set changed')
        for rank in manifest['ranks']:
            for blob in rank['blobs']:
                name = blob['name']
                require(type(name) is str and re.fullmatch(r'[A-Za-z0-9_.-]+', name) is not None,
                        'invalid native blob name')
                key = rank['directory'] + '/' + name + '.bin'
                require(key not in expected, 'duplicate native blob')
                expected[key] = blob
        paths = sorted(tree.rglob('*'))
        require(all(not f.is_symlink() for f in paths), 'checkpoint contains symlink')
        require({f.relative_to(tree).as_posix() for f in paths if f.is_file()} == set(expected),
                'checkpoint file set is not closed')
        require({f.relative_to(tree).as_posix() for f in paths if f.is_dir()} == {'rank0', 'rank1'},
                'checkpoint directory set changed')
        directories.update(rel(f) for f in [tree, tree / 'rank0', tree / 'rank1'])
        for name, declaration in expected.items():
            f = tree / name
            row = pin(f)
            if declaration is not None:
                require(row['stamp']['bytes'] == declaration['bytes'] and row['sha256'] == declaration['sha256'],
                        'native manifest mismatch: ' + str(f))
            entries[rel(f)] = dict(**row, tensor_prune_candidate=tensor(f))
    binary = [row for name, row in entries.items() if name.endswith('.bin')]
    candidates = [name for name, row in entries.items() if row['tensor_prune_candidate']]
    require(len(entries) == 876 and len(binary) == 868 and sum(x['stamp']['bytes'] for x in binary) == TOTAL_BIN_BYTES,
            'four-checkpoint inventory changed')
    require(len(candidates) == 796 and sum(entries[n]['stamp']['bytes'] for n in candidates) == TENSOR_BYTES,
            'tensor candidate inventory changed')
    tracked = set(subprocess.check_output(['git', 'ls-files', '-z', '--', rel(PACKET)], cwd=ROOT).decode().split('\0'))
    # Archiving may include tracked metadata. The later prune must independently
    # reject tracked candidates; this helper merely records their current status.
    tracked_candidates = sorted(set(candidates) & tracked)
    guards = [Path(__file__), PACKET / 'READY-FOR-DEVICE.json', PACKET / 'v5/cpu-seal.json',
              PACKET / 'v5/lifecycle_report.py', PACKET / 'v5/tp2_checkpoint.py', PACKET / 'RESTORE-ARCHIVE.md']
    drains = []
    for run in ('device-smoke-B-p184', 'device-lifecycle-B-p184'):
        base = EVIDENCE / run
        for name in ('summary.json', 'window.json', 'run/summary.json'):
            f = base / name
            row = read(f)
            require(row['passed'] is True and row['device_executed'] is True, 'row not successfully closed')
            if name == 'window.json':
                require(row['returncode'] == 0, 'row exit was not zero')
            guards.append(f)
        for f in sorted((base / 'run/legs').glob('*/teardown.json')):
            row = read(f)
            require(row['drained'] is True, 'undrained historical leg')
            guards.append(f)
            drains.append(rel(f))
        guards.append(base / 'run/teardown.json')
    require(len(drains) == 5, 'closed-leg count changed')
    return dict(files=entries, directories=sorted(directories),
                guards={rel(f): pin(f) for f in guards}, drained_legs=drains,
                tracked_tensor_candidates=tracked_candidates)


def put_receipt(row, *, exclusive=False):
    mode = 'x' if exclusive else 'w'
    with RECEIPT.open(mode) as stream:
        json.dump(row, stream, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def copy_verify():
    require(not ARCHIVE.exists() and not RECEIPT.exists(), 'one-shot output already exists; preserve and review')
    require(ARCHIVE.parent.is_dir() and ARCHIVE.parent.resolve() == ARCHIVE.parent, 'archive parent missing/aliased')
    before = inventory()
    row = dict(schema='p184-closed-checkpoint-archive-v1', passed=False, created_utc=utc(),
               archive=str(ARCHIVE), receipt=str(RECEIPT), originals=before,
               action='copy and verify only; no source deletion', scope='closed historical TP2 evidence')
    put_receipt(row, exclusive=True)
    try:
        with ARCHIVE.open('xb') as raw:
            with tarfile.open(fileobj=raw, mode='w', format=tarfile.PAX_FORMAT) as archive:
                for name in before['directories']:
                    info = tarfile.TarInfo(name)
                    info.type, info.mode = tarfile.DIRTYPE, 0o755
                    archive.addfile(info)
                for name, expected in sorted(before['files'].items()):
                    source = ROOT / name
                    require(stamp(source) == expected['stamp'], 'source changed before copy')
                    fd = os.open(source, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
                    with os.fdopen(fd, 'rb') as stream:
                        s = os.fstat(stream.fileno())
                        require((s.st_dev, s.st_ino) == (expected['stamp']['dev'], expected['stamp']['ino']),
                                'source replaced before copy')
                        info = tarfile.TarInfo(name)
                        info.size, info.mode, info.mtime = s.st_size, stat.S_IMODE(s.st_mode), s.st_mtime
                        archive.addfile(info, stream)
                    require(stamp(source) == expected['stamp'], 'source changed during copy')
            raw.flush()
            os.fsync(raw.fileno())
        archive_stamp = stamp(ARCHIVE)
        verified, dirs = {}, set()
        with tarfile.open(ARCHIVE, 'r:') as archive:
            for member in archive:
                require(member.name not in verified and member.name not in dirs, 'duplicate archive member')
                if member.isdir():
                    require(member.name in before['directories'], 'unexpected directory member')
                    dirs.add(member.name)
                    continue
                require(member.isfile() and member.name in before['files'], 'unexpected archive member/type')
                expected = before['files'][member.name]
                require(member.size == expected['stamp']['bytes'], 'archive member extent mismatch')
                with archive.extractfile(member) as stream:
                    digest = sha_stream(stream)
                require(digest == expected['sha256'], 'archive member checksum mismatch')
                verified[member.name] = digest
        require(set(verified) == set(before['files']) and dirs == set(before['directories']), 'archive incomplete')
        archive_pin = pin(ARCHIVE)
        require(archive_pin['stamp'] == archive_stamp, 'archive changed during verification')
        require(inventory() == before, 'originals, source, closure guards or tracked status changed after copy')
        row.update(passed=True, verified_utc=utc(), archive_sha256=archive_pin['sha256'],
                   archive_stamp=archive_pin['stamp'], verified_member_sha256=verified,
                   original_files_unchanged=True, deleted_files=0,
                   tensor_prune_candidate_files=796, tensor_prune_candidate_bytes=TENSOR_BYTES,
                   retained_binary_files=72, retained_binary_bytes=TOTAL_BIN_BYTES - TENSOR_BYTES)
        put_receipt(row)
    except BaseException as error:
        row.update(failed_utc=utc(), error=str(error), deleted_files=0,
                   partial_archive_retained=ARCHIVE.exists())
        put_receipt(row)
        raise
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--plan', action='store_true')
    modes.add_argument('--copy-verify', action='store_true')
    args = parser.parse_args()
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19 and
            set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32)),
            'nice19/helper cores required')
    if args.plan:
        print(json.dumps(dict(archive=str(ARCHIVE), receipt=str(RECEIPT), inventory=inventory()), indent=2))
    else:
        row = copy_verify()
        print(json.dumps({k: row[k] for k in ('passed', 'archive', 'archive_sha256', 'deleted_files',
                                            'tensor_prune_candidate_files', 'tensor_prune_candidate_bytes')}))


if __name__ == '__main__':
    main()

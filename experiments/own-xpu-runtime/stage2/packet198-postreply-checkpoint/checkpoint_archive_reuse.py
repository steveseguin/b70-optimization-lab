#!/usr/bin/env python3
"""Verify p198 binary-only reuse of the p197 tar; prune only with explicit --prune.

Default is read-only. --write-receipt records the verified reuse map without
deleting anything. The coordinator alone may subsequently invoke --prune.
No archive metadata is ever copied over p198 manifests or fields.tsv.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import tarfile

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
LOCAL = P / 'evidence/device-p198-lifecycle-A-a/checkpoints'
PARENT = P.parent / 'packet197-warm-request-front/evidence/checkpoint-archive.json'
REUSE = P / 'evidence/checkpoint-archive-reuse.json'
PRUNE = P / 'evidence/checkpoint-local-prune.json'
KEEP = {'active.bin', 'error.bin', 'next_token.bin', 'position.bin',
        'streams.bin', 'token.bin', 'token_history.bin', 'tokens.bin'}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def stamp(path):
    s = path.lstat()
    require(stat.S_ISREG(s.st_mode), 'nonregular file: ' + str(path))
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def exclusive_json(path, row):
    with path.open('x') as stream:
        json.dump(row, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def verify():
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice19 required')
    require(set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32)), 'helper cores required')
    parent = read(PARENT)
    archive = Path(parent['archive']['path'])
    require(archive.is_absolute() and archive.resolve(strict=True) == archive, 'real archive path required')
    before = stamp(archive)
    require(before[2] == parent['archive']['bytes'] and sha(archive) == parent['archive']['sha256'], 'whole archive changed')
    seen = set()
    with tarfile.open(archive, 'r:') as tar:
        for member in tar:
            name = member.name
            parts = PurePosixPath(name)
            require(not parts.is_absolute() and '..' not in parts.parts, 'unsafe archive name')
            if member.isdir():
                require(name.rstrip('/') in parent['directories'], 'unexpected archive directory')
                continue
            require(member.isfile() and name not in seen and name in parent['members'], 'unexpected/nonregular archive member')
            expected = parent['members'][name]
            with tar.extractfile(member) as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            require(member.size == expected['bytes'] and digest == expected['sha256'], 'archive member differs: ' + name)
            seen.add(name)
    require(seen == set(parent['members']) and stamp(archive) == before, 'archive inventory changed')
    worker = read(LOCAL.parent / 'worker.json')
    require(worker['passed'] is True, 'completed device proof required')
    require(LOCAL.resolve(strict=True) == LOCAL, 'real checkpoint root required')
    mapping, metadata, stamps = {}, {}, {}
    for checkpoint in ('s1', 's2', 's3', 's4', 's5'):
        folder = LOCAL / checkpoint
        require(folder.resolve(strict=True) == folder and folder.is_dir(), 'real checkpoint directory required')
        manifest = read(folder / 'manifest.json')
        require(manifest['contract'] == 'v1.2+p198' and manifest['label'] == 'experimental-postreply-front', 'p198 identity missing')
        expected = {'tokens.bin': manifest['token_state']['tokens_sha256']}
        expected.update({b['name'] + '.bin': b['sha256'] for b in manifest['blobs']})
        require(expected == worker['checkpoint_state_sha256'][checkpoint], 'worker/manifest state map differs')
        require({q.name for q in folder.iterdir()} == set(expected) | {'manifest.json', 'fields.tsv'}, 'local checkpoint file set changed')
        require(KEEP <= set(expected), 'small/control retention set missing')
        for leaf, digest in expected.items():
            path = folder / leaf
            original = stamp(path)
            require(sha(path) == digest and stamp(path) == original, 'local binary changed: ' + str(path))
            member = 'checkpoints/' + checkpoint + '/' + leaf
            require(parent['members'].get(member) == dict(bytes=original[2], sha256=digest), 'p197 archive binary differs: ' + member)
            relative = str(path.relative_to(ROOT))
            mapping[relative] = dict(archive_member=member, bytes=original[2], sha256=digest,
                                     prune=leaf not in KEEP)
            if leaf not in KEEP:
                require(leaf.startswith('blk.') and leaf.endswith('.bin'), 'unexpected prune candidate')
                stamps[relative] = original
        for leaf in ('manifest.json', 'fields.tsv'):
            path = folder / leaf
            stamp(path)
            metadata[str(path.relative_to(ROOT))] = sha(path)
            require(sha(path) != parent['members']['checkpoints/' + checkpoint + '/' + leaf]['sha256'], 'p198 metadata unexpectedly identical to p197')
    candidates = {name for name, row in mapping.items() if row['prune']}
    require(len(mapping) == 645 and len(candidates) == 605, 'fixed binary/prune count changed')
    tracked = subprocess.run(['/usr/bin/git', 'ls-files', '-z', '--', str(LOCAL.relative_to(ROOT))],
                             cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True, check=True)
    require(not candidates.intersection(tracked.stdout.decode().split('\0')), 'tracked file would be pruned')
    return dict(schema='packet198.binary-archive-reuse.v1', verified_utc=now(), passed=True,
                archive=parent['archive'], parent_archive_receipt_sha256=sha(PARENT),
                script_sha256=sha(Path(__file__)), binary_files=len(mapping),
                binary_bytes=sum(row['bytes'] for row in mapping.values()),
                prune_files=len(candidates), prune_bytes=sum(mapping[name]['bytes'] for name in candidates),
                retained_binary_files=40, retained_metadata_sha256=metadata, files=mapping,
                source_worker_sha256=sha(LOCAL.parent / 'worker.json'),
                scope='Binary payload equality only. P198 manifests/fields retain distinct contract, binary identity and provenance.',
                restoration='Verify the entire archive and this map. Restore ONLY mapped .bin members into a fresh p198 checkpoint copy with the retained p198 manifest.json and fields.tsv. Never use p197 archived metadata for p198. Verify all restored bytes against this map and p198 manifests before native use.'), stamps


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--write-receipt', action='store_true')
    mode.add_argument('--prune', action='store_true')
    args = ap.parse_args()
    verified, stamps = verify()
    if args.write_receipt:
        exclusive_json(REUSE, verified)
    if args.prune:
        admitted = read(REUSE)
        require({k:v for k,v in admitted.items() if k != 'verified_utc'} ==
                {k:v for k,v in verified.items() if k != 'verified_utc'}, 'reuse admission changed')
        require(not PRUNE.exists(), 'prune attempt already recorded; inspect rather than retry')
        result = dict(schema='packet198.verified-local-tensor-prune.v1', started_utc=now(), passed=False,
                      reuse_receipt_sha256=sha(REUSE), removed_files=[], removed_bytes=0,
                      preserved='Five distinct p198 manifests/fields and eight small token/control files per checkpoint.')
        exclusive_json(PRUNE, result)
        try:
            for name, original in sorted(stamps.items()):
                path = ROOT / name
                require(stamp(path) == original and sha(path) == admitted['files'][name]['sha256'], 'candidate changed before unlink: ' + name)
                path.unlink()
                result['removed_files'].append(name)
                result['removed_bytes'] += admitted['files'][name]['bytes']
            for name, digest in admitted['retained_metadata_sha256'].items():
                require(sha(ROOT / name) == digest, 'retained p198 metadata changed')
            for name, row in admitted['files'].items():
                if not row['prune']:
                    require(sha(ROOT / name) == row['sha256'], 'retained control changed')
            result.update(passed=True, finished_utc=now())
        except BaseException as error:
            result.update(error=str(error), finished_utc=now())
            raise
        finally:
            temporary = PRUNE.with_suffix('.json.tmp')
            exclusive_json(temporary, result)
            os.replace(temporary, PRUNE)
    print(json.dumps({k:v for k,v in verified.items() if k in
                      ('passed', 'binary_files', 'binary_bytes', 'prune_files', 'prune_bytes', 'retained_binary_files')}))


if __name__ == '__main__':
    main()

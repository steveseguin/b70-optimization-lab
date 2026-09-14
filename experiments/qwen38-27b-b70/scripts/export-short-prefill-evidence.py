#!/usr/bin/env python3
"""Archive selected short-prefill receipts without caches, symlinks or binaries.

Run after all clients have stopped. Existing output directories are refused.
Extract each archive into an empty directory with `tar -xzf ARCHIVE`; member
paths are relative to the original raw root. manifest.json records every raw
relative path, byte count, SHA-256, archive SHA-256 and source-script identity.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

PROFILES = ('4b', '9b', '27b-int4', '27b-fp8')
TREES = ('baseline', 'candidate', 'final-control', 'baseline-strict', 'candidate-strict')
SUFFIXES = {'.json', '.jsonl', '.log', '.txt', '.stdout'}
SECRET = re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|(?:Bearer\s+)[A-Za-z0-9._~+/=-]{20,}', re.I)
MAX_BYTES = 64 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def allowed(path):
    return path.suffix in SUFFIXES or path.name in ('DONE', 'ABORTED')


def safe_file(path, root):
    relative = path.relative_to(root)
    if any('cache' in part.lower() for part in relative.parts):
        raise ValueError(f'cache path cannot be archived: {relative}')
    if any(parent.is_symlink() for parent in [path, *path.parents] if parent != root.parent):
        raise ValueError(f'symlink cannot be archived: {relative}')
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError(f'non-regular or oversized receipt: {relative}')
    data = path.read_bytes()
    if b'\x00' in data or SECRET.search(data):
        raise ValueError(f'binary or credential-like receipt rejected: {relative}')
    data.decode('utf-8')
    return relative.as_posix(), data


def select(root, profile=None):
    directory = root if profile is None else root / profile
    files = []
    for path in sorted(directory.iterdir()):
        if path.is_symlink():
            raise ValueError(f'symlink in selected root: {path.name}')
        if path.is_file() and allowed(path) and 'cache' not in path.name.lower():
            files.append(path)
    if profile is not None:
        for name in TREES:
            tree = directory / name
            if not tree.exists():
                continue  # Aborted profiles retain their partial evidence.
            if tree.is_symlink():
                raise ValueError(f'symlink tree rejected: {tree}')
            for path in sorted(tree.rglob('*')):
                if path.is_symlink():
                    raise ValueError(f'symlink in receipt tree: {path}')
                if any('cache' in part.lower() for part in path.relative_to(root).parts):
                    raise ValueError(f'unexpected cache in receipt tree: {path}')
                if path.is_file():
                    if not allowed(path):
                        raise ValueError(f'unexpected receipt file type: {path}')
                    files.append(path)
    return sorted(files)


def archive(root, files, target):
    records = []
    with target.open('xb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=9) as compressed:
            with tarfile.open(fileobj=compressed, mode='w', format=tarfile.PAX_FORMAT) as tar:
                for path in files:
                    name, data = safe_file(path, root)
                    info = tarfile.TarInfo(name)
                    info.size, info.mtime, info.mode = len(data), 0, 0o644
                    info.uid = info.gid = 0
                    info.uname = info.gname = ''
                    tar.addfile(info, io.BytesIO(data))
                    records.append({'raw_relative_path': name, 'bytes': len(data), 'sha256': digest(data)})
    return {'archive': target.name, 'bytes': target.stat().st_size,
            'sha256': digest(target.read_bytes()), 'files': records}


def run(root, out, extra_sources=()):
    root = root.absolute()
    if root.is_symlink() or not root.is_dir():
        raise ValueError('raw root must be a real directory')
    if out.absolute() == root or root in out.absolute().parents:
        raise ValueError('archive output must be outside raw root')
    out.mkdir(parents=True, exist_ok=False)
    manifest = {'schema': 1, 'raw_root': str(root), 'archives': [], 'source_files': [],
                'notes': ['All member bytes preserved; gzip/tar timestamps and ownership normalized.',
                          'Caches and unknown root subdirectories excluded. No server or GPU operations.',
                          'Inspect receipts before publication; credential screening is deliberately conservative.']}
    for profile in (None, *PROFILES):
        if profile is not None and not (root / profile).exists():
            continue
        files = select(root, profile)
        if files:
            manifest['archives'].append(archive(root, files, out / ((profile or 'campaign') + '.tar.gz')))
    scripts = Path(__file__).resolve().parent
    repo = scripts.parents[2]
    for name in ('bench-short-prefill.py', 'run-short-prefill-stage.py', 'summarize-short-prefill.py',
                 'export-short-prefill-evidence.py', 'test_bench_short_prefill.py',
                 'test_run_short_prefill_stage.py', 'test_export_short_prefill_evidence.py'):
        path = scripts / name
        if not path.is_file():
            raise ValueError(f'missing source: {path}')
        data = path.read_bytes()
        manifest['source_files'].append({'repository_path': path.relative_to(repo).as_posix(), 'sha256': digest(data), 'bytes': len(data)})
    for path in extra_sources:
        path = path.resolve()
        if not path.is_relative_to(repo) or not path.is_file():
            raise ValueError(f'extra source must be a repository file: {path}')
        data = path.read_bytes()
        manifest['source_files'].append({'repository_path': path.relative_to(repo).as_posix(), 'sha256': digest(data), 'bytes': len(data)})
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'archives': len(manifest['archives']), 'files': sum(len(a['files']) for a in manifest['archives']),
                      'compressed_bytes': sum(a['bytes'] for a in manifest['archives'])}))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--raw-root', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--source', type=Path, action='append', default=[], help='Additional repository source to hash, repeatable')
    args = ap.parse_args()
    run(args.raw_root, args.out, args.source)

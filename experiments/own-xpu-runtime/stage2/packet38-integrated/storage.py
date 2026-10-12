"""Packet-local storage admission and disposable CPU fixture retention."""
import base64
import gzip
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

P = Path(__file__).resolve().parent
B = P / 'build'

def build_size(root):
    """Concurrent gates may remove completed scratch between discovery and stat."""
    used=0
    for file in root.rglob('*'):
        try:
            if file.is_file() and not file.is_symlink():used+=file.stat().st_size
        except FileNotFoundError:
            # Only a vanished member is benign; permission/I/O errors still refuse.
            continue
    return used

def admit(extra=0, *, build_extra=None):
    # Explicit df check before every build or fixture-producing stage.
    result = subprocess.run(['nice', '-n', '19', 'ionice', '-c', '3',
                             'df', '-B1', '/'], capture_output=True, text=True, check=True)
    free = int(result.stdout.splitlines()[-1].split()[3])
    used = build_size(B)
    build_extra = extra if build_extra is None else build_extra
    if free < 8_000_000_000 + extra or used + build_extra >= 6_000_000_000:  # build cap raised from 3 GB by the coordinator on 2026-10-12; the 8 GB root floor is unchanged
        raise RuntimeError(f'Packet38 storage admission refused: free={free}, build={used}, reserve write={extra}; require 8 GB free and build below 6 GB')
    return dict(root_free_bytes=free, build_bytes=used, admitted_write_bytes=extra)

RETAINED_SUFFIXES = {'.json', '.jsonl', '.log', '.txt', '.tsv', '.gz', '.py'}

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def verify_archive(path):
    """Verify a streamed archive, including exact bytes of nested gzip evidence."""
    files = retained = total = 0
    current = None
    with gzip.open(path, 'rt', encoding='utf-8') as source:
        header = json.loads(next(source))
        if header != {'schema': 'packet38.scratch-stream.v1'}:
            raise ValueError('scratch archive schema')
        for line in source:
            row = json.loads(line)
            if row['kind'] == 'file':
                if current is not None:
                    raise ValueError('unfinished scratch member')
                current = row; observed = hashlib.sha256(); count = 0; files += 1
            elif row['kind'] == 'chunk':
                if current is None or not current['retained']:
                    raise ValueError('unexpected scratch content')
                chunk = base64.b64decode(row['base64'], validate=True)
                observed.update(chunk); count += len(chunk)
            elif row['kind'] == 'end':
                if current is None or row['path'] != current['path']:
                    raise ValueError('scratch member framing')
                if current['retained']:
                    if count != current['bytes'] or observed.hexdigest() != current['sha256']:
                        raise ValueError('scratch member hash mismatch')
                    retained += 1; total += count
                current = None
            else:
                raise ValueError('unknown scratch record')
    if current is not None:
        raise ValueError('truncated scratch member')
    return dict(files=files, retained_files=retained, retained_bytes=total)

def archive_files(paths, destination):
    """Write and verify bounded-memory JSONL/gzip before any caller deletes files."""
    paths = sorted(set(Path(f) for f in paths))
    for f in paths:
        if f.is_symlink() or not f.is_file() or not f.resolve().is_relative_to(P):
            raise ValueError('scratch member outside packet or symlink: '+str(f))
    # Base64 worst-case plus JSON/gzip overhead, checked before the large write.
    estimate = sum(f.stat().st_size * 4 // 3 + 4096 for f in paths if f.suffix in RETAINED_SUFFIXES) + len(paths) * 1024 + 1_000_000
    destination = Path(destination)
    admit(estimate, build_extra=estimate if destination.resolve().is_relative_to(B) else 0)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name+'.tmp')
    with temporary.open('wb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as archive:
            def emit(row):
                archive.write((json.dumps(row, separators=(',', ':'))+'\n').encode())
            emit(dict(schema='packet38.scratch-stream.v1'))
            for f in paths:
                row=dict(kind='file', path=str(f.relative_to(P)), bytes=f.stat().st_size,
                         sha256=digest(f), retained=f.suffix in RETAINED_SUFFIXES)
                emit(row)
                if row['retained']:
                    observed=hashlib.sha256(); count=0
                    with f.open('rb') as source:
                        for chunk in iter(lambda: source.read(1024 * 1024), b''):
                            observed.update(chunk); count+=len(chunk)
                            emit(dict(kind='chunk', base64=base64.b64encode(chunk).decode('ascii')))
                    if count!=row['bytes'] or observed.hexdigest()!=row['sha256']:
                        raise ValueError('scratch member changed during archive: '+str(f))
                emit(dict(kind='end', path=row['path']))
    verified=verify_archive(temporary)
    if verified['files']!=len(paths):
        raise ValueError('scratch archive file coverage')
    temporary.replace(destination)
    return dict(path=str(destination.relative_to(P)), sha256=digest(destination),
                format='packet38.scratch-stream.v1 JSONL/gzip; text and nested gzip exact bytes, other scratch hashes', **verified)

def discard(root):
    """Retain exact text/nested archives and all hashes, then remove CPU scratch."""
    root = Path(root).resolve()
    assert root.parent == B or B in root.parents
    assert root != B and not root.is_symlink()
    paths = [f for f in root.rglob('*') if f.is_file()]
    dest = P / 'evidence' / ('scratch-' + '-'.join(root.relative_to(B).parts) + '.jsonl.gz')
    result=archive_files(paths, dest)
    shutil.rmtree(root)
    return result

"""Packet-local storage admission and disposable CPU fixture retention."""
import gzip
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

P = Path(__file__).resolve().parent
B = P / 'build'

def admit(extra=0):
    # Explicit df check before every build or fixture-producing stage.
    result = subprocess.run(['nice', '-n', '19', 'ionice', '-c', '3',
                             'df', '-B1', '/'], capture_output=True, text=True, check=True)
    free = int(result.stdout.splitlines()[-1].split()[3])
    used = sum(f.stat().st_size for f in B.rglob('*') if f.is_file() and not f.is_symlink())
    if free < 8_000_000_000 + extra or used + extra >= 3_000_000_000:
        raise RuntimeError(f'Packet38 storage admission refused: free={free}, build={used}, reserve write={extra}; require 8 GB free and build below 3 GB')
    return dict(root_free_bytes=free, build_bytes=used, admitted_write_bytes=extra)

def discard(root):
    """Keep exact compressed text and all hashes before removing CPU scratch."""
    root = Path(root).resolve()
    assert root.parent == B or B in root.parents
    assert root != B and not root.is_symlink()
    rows = []
    for f in sorted(root.rglob('*')):
        if not f.is_file():
            continue
        h = hashlib.sha256()
        with f.open('rb') as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                h.update(chunk)
        row = dict(path=str(f.relative_to(P)), bytes=f.stat().st_size, sha256=h.hexdigest())
        if f.suffix in ('.json', '.jsonl', '.log', '.txt', '.tsv'):
            row['text'] = f.read_text()
        rows.append(row)
    dest = P / 'evidence' / ('scratch-' + '-'.join(root.relative_to(B).parts) + '.json.gz')
    dest.parent.mkdir(exist_ok=True)
    raw = json.dumps(rows, separators=(',', ':')).encode()
    dest.write_bytes(gzip.compress(raw, mtime=0))
    assert gzip.decompress(dest.read_bytes()) == raw
    shutil.rmtree(root)
    return dict(path=str(dest.relative_to(P)), sha256=hashlib.sha256(dest.read_bytes()).hexdigest())

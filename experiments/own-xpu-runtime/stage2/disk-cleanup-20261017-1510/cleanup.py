"""Owner-authorized, CPU-only closed-packet scratch cleanup; exact audit log."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def identity(p):
    s = p.stat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_nlink)

def protections():
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=REPO).decode().split('\0')
    tracked = {str((REPO / p).resolve()) for p in tracked if p}
    refs = []
    for line in (HERE / 'protected-build-references.txt').read_text().splitlines():
        token = line.split(':', 1)[-1]
        if token.startswith('/home/'):
            refs.append(str(Path(token).resolve()))
        elif token.startswith('experiments/'):
            refs.append(str((REPO / token).resolve()))
    return tracked, set(refs)

def main():
    tracked, refs = protections()
    candidates = json.loads((HERE / 'candidates.json').read_text())
    done = set()
    log = HERE / 'removed.jsonl'
    if log.exists():
        done = {json.loads(line)['path'] for line in log.read_text().splitlines()}
    freed = 0
    skipped = []
    with log.open('a') as stream:
        for row in candidates['asan'] + candidates['object']:
            p = Path(row['path'])
            if str(p) in done:
                continue
            if not p.exists() or p.is_symlink() or str(p.resolve()) in tracked or str(p.resolve()) in refs:
                skipped.append(str(p)); continue
            before = identity(p)
            if before[4] != 1 or before[2:4] != (row['size'], row['mtime_ns']):
                skipped.append(str(p)); continue
            # Only explicit compiler objects or files within sanitizer scratch.
            assert p.suffix == '.o' or any(x == 'asan' or x.startswith('sanitizer') for x in p.parts)
            row['sha256'] = digest(p)
            assert identity(p) == before
            row['action'] = 'remove-regenerable-compiler-scratch'
            row['utc_epoch'] = time.time()
            stream.write(json.dumps(row, sort_keys=True) + '\n')
            stream.flush(); os.fsync(stream.fileno())
            p.unlink()
            freed += row['blocks']
    (HERE / 'skipped.json').write_text(json.dumps(skipped, indent=2) + '\n')
    print(json.dumps({'removed_allocated_bytes': freed, 'skipped': len(skipped)}), flush=True)

if __name__ == '__main__':
    raise SystemExit('Disabled: original sanitizer prefix matched retained archives and run outputs. See incident manifest; do not rerun.')

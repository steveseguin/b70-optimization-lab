#!/usr/bin/env python3
"""Packet183 bootstrap: identity-rewritten copy of packet153's two-card v5 harness.

CPU-only file work. Reads packet153 (never writes it), writes only inside this
packet. Packet153 is the last two-card one-load bracket that ran on device on the
bundle-8 line (lane B, 2026-10-19 01:45-01:53 UTC, controls 58.638/58.671/58.663
tok/s, drift 0.057%). Its control selection is bundle 8 byte for byte.

What the copy does, all recorded in lineage/packet183-copy.json:
  * every regular file and symlink is copied (symlinks preserved, not followed);
  * packet153's own v5/evidence/, READY-FOR-DEVICE.json and proposals/ are moved
    under lineage-inputs/packet153-own/ as provenance (they certify packet153, not
    this packet);
  * the vendored source subtree native-base/.../packet153-snapshot-host is renamed
    to .../packet183-twocard-s1-micro, and v5/p153_*.py modules to v5/p183_*.py;
  * outside lineage-inputs/, text files get three literal rewrites:
    packet153-snapshot-host -> packet183-twocard-s1-micro, p153_v5_ -> p183_v5_,
    p153_ops_ -> p183_ops_. lineage-inputs/ stays byte-identical (history).
Run once:  python3 -B copy_packet183.py   (refuses if the copy already exists).
"""
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SRC = HERE.parent / 'packet153-snapshot-host'
OLD, NEW = 'packet153-snapshot-host', 'packet183-twocard-s1-micro'
REWRITES = [(OLD, NEW), ('p153_v5_', 'p183_v5_'), ('p153_ops_', 'p183_ops_')]
OWN = {'v5/evidence', 'READY-FOR-DEVICE.json', 'proposals'}
SKIP_PARTS = {'__pycache__', 'build'}


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def dest_rel(rel):
    parts = rel.split('/')
    if any(rel == o or rel.startswith(o + '/') for o in OWN):
        return 'lineage-inputs/packet153-own/' + rel
    if not rel.startswith('lineage-inputs/'):
        parts = [NEW if p == OLD else p for p in parts]
        if parts[0] == 'v5' and len(parts) == 2 and parts[1].startswith(('p153_v5_', 'p153_ops_')):
            parts[1] = 'p183_' + parts[1][len('p153_'):]
    return '/'.join(parts)


def is_text(data):
    if b'\0' in data[:8192]:
        return False
    try:
        data.decode('utf-8')
        return True
    except UnicodeDecodeError:
        return False


def main():
    if any(HERE.joinpath(x).exists() for x in ('v5', 'native-base', 'lineage-inputs')):
        sys.exit('refusing: packet183 copy already exists')
    commit = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    files, rewritten, moved, renamed, links = {}, [], [], [], {}
    for path in sorted(SRC.rglob('*')):
        rel = path.relative_to(SRC).as_posix()
        if SKIP_PARTS & set(rel.split('/')):
            continue
        if path.is_dir() and not path.is_symlink():
            continue
        out_rel = dest_rel(rel)
        out = HERE / out_rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if out_rel != rel:
            (moved if out_rel.startswith('lineage-inputs/packet153-own/') else renamed).append([rel, out_rel])
        if path.is_symlink():
            target = os.readlink(path)
            os.symlink(target, out)
            links[out_rel] = target
            continue
        data = path.read_bytes()
        before = hashlib.sha256(data).hexdigest()
        if not out_rel.startswith('lineage-inputs/') and is_text(data):
            text = data.decode('utf-8')
            new = text
            for a, b in REWRITES:
                new = new.replace(a, b)
            if new != text:
                data = new.encode('utf-8')
                rewritten.append(out_rel)
        out.write_bytes(data)
        shutil.copymode(path, out)
        files[out_rel] = {'source_relpath': rel, 'source_digest': before, 'digest': hashlib.sha256(data).hexdigest()}
    receipt = {
        'schema': 'packet183.copy.v1', 'device_executed': False, 'source_packet': 'experiments/own-xpu-runtime/stage2/' + OLD,
        'source_commit': commit, 'rewrites': REWRITES, 'file_count': len(files), 'rewritten_count': len(rewritten),
        'rewritten': rewritten, 'moved_to_provenance': moved, 'renamed': renamed, 'symlinks': links,
        'note': 'source_digest values are provenance records of packet153 bytes at source_commit, not pins',
        'copied': [{'name': k, **v} for k, v in sorted(files.items())],
    }
    (HERE / 'lineage/packet183-copy.json').write_text(json.dumps(receipt, indent=1) + '\n')
    print(json.dumps({k: receipt[k] for k in ('file_count', 'rewritten_count', 'symlinks')}, indent=1))
    print('moved', len(moved), 'renamed', len(renamed))


if __name__ == '__main__':
    main()

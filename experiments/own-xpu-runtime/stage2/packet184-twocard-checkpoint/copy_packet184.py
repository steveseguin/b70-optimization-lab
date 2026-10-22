#!/usr/bin/env python3
"""Packet184 bootstrap: identity-rewritten copy of packet153's two-card v5 harness.

CPU-only file work. Reads packet153 (never writes it), writes only inside this
packet. Packet153 is packet136's banked bundle 8 (the 58.798109 tok/s two-card
record line) with packet150's vendored one-load v5 harness; its lane-B bracket
ran on device 2026-10-19 01:45-01:53 UTC (controls 58.638/58.671/58.663 tok/s,
13/13 exact per view) and packet183 reused the same harness on device on
2026-10-22. Packet153 is chosen over packet183 because packet183 carries the
S1 dense-scales delta (closed on device 2026-10-22: 54.99 vs 58.6 tok/s);
packet184 needs bundle 8 unchanged.

What the copy does, all recorded in lineage/packet184-copy.json:
  * every regular file and symlink is copied (symlinks preserved, not followed);
  * packet153's own v5/evidence/, READY-FOR-DEVICE.json and proposals/ are moved
    under lineage-inputs/packet153-own/ as provenance (they certify packet153);
  * the vendored source subtree native-base/.../packet153-snapshot-host is renamed
    to .../packet184-twocard-checkpoint, and v5/p153_*.py modules to v5/p184_*.py;
  * outside lineage-inputs/, text files get three literal rewrites:
    packet153-snapshot-host -> packet184-twocard-checkpoint, p153_v5_ -> p184_v5_,
    p153_ops_ -> p184_ops_. lineage-inputs/ stays byte-identical (history),
    with ONE recorded amendment (as packet183 needed): the vendored
    packet58-onecard/suite_driver.py locates its owning packet by directory name.
Run once:  python3 -B copy_packet184.py   (refuses if the copy already exists).
"""
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SRC = HERE.parent / 'packet153-snapshot-host'
OLD, NEW = 'packet153-snapshot-host', 'packet184-twocard-checkpoint'
REWRITES = [(OLD, NEW), ('p153_v5_', 'p184_v5_'), ('p153_ops_', 'p184_ops_')]
OWN = {'v5/evidence', 'READY-FOR-DEVICE.json', 'proposals'}
SKIP_PARTS = {'__pycache__', 'build'}
AMEND = 'lineage-inputs/vendor/repo/experiments/own-xpu-runtime/stage2/packet58-onecard/suite_driver.py'


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
            parts[1] = 'p184_' + parts[1][len('p153_'):]
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
        sys.exit('refusing: packet184 copy already exists')
    commit = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    files, rewritten, moved, renamed, links, amendments = {}, [], [], [], {}, []
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
        elif out_rel == AMEND:
            text = data.decode('utf-8')
            needle = "p.name=='" + OLD + "'"
            assert text.count(needle) == 1, 'suite_driver amendment anchor'
            data = text.replace(needle, "p.name=='" + NEW + "'").encode('utf-8')
            amendments.append(dict(name=out_rel, before_digest=before, after_digest=hashlib.sha256(data).hexdigest(),
                                   reason='runtime vendored module locates its owning packet by directory name '
                                          '(oracle_inputs); packet153 had set it to its own name; identity rewrite to packet184 '
                                          '(the same amendment packet183 recorded in lineage/packet183-copy-amendments.json)'))
        out.write_bytes(data)
        shutil.copymode(path, out)
        files[out_rel] = {'source_relpath': rel, 'source_digest': before, 'digest': hashlib.sha256(data).hexdigest()}
    assert len(amendments) == 1, amendments
    (HERE / 'lineage').mkdir(exist_ok=True)
    receipt = {
        'schema': 'packet184.copy.v1', 'device_executed': False, 'source_packet': 'experiments/own-xpu-runtime/stage2/' + OLD,
        'source_commit': commit, 'rewrites': REWRITES, 'file_count': len(files), 'rewritten_count': len(rewritten),
        'rewritten': rewritten, 'moved_to_provenance': moved, 'renamed': renamed, 'symlinks': links,
        'note': 'source_digest values are provenance records of packet153 bytes at source_commit, not pins',
        'copied': [{'name': k, **v} for k, v in sorted(files.items())],
    }
    (HERE / 'lineage/packet184-copy.json').write_text(json.dumps(receipt, indent=1) + '\n')
    (HERE / 'lineage/packet184-copy-amendments.json').write_text(json.dumps(dict(
        schema='packet184.copy-amendment.v1', device_executed=False, amendments=amendments), indent=1) + '\n')
    print(json.dumps({k: receipt[k] for k in ('file_count', 'rewritten_count', 'symlinks')}, indent=1))
    print('moved', len(moved), 'renamed', len(renamed), 'amended', len(amendments))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Packet185 bootstrap: identity-rewritten copy of packet183's two-card v5 harness.

CPU-only file work. Reads packet183 (never writes it), writes only inside this
packet. Packet183's bracket ran on device on the bundle-8 line today (lane B,
2026-10-22 12:03-12:11 UTC, expanded controls 58.617/58.587/58.630 tok/s, drift
0.072%); its `production` selection (dense_scales=expanded) is bundle 8 and is
the control of this packet. The device binary is NOT rebuilt: v5/p185_v5_build_engine.py
copies packet183's two linked engines byte for byte and verifies them against
packet183's committed build receipt.

What the copy does, all recorded in lineage/packet185-copy.json:
  * every regular file and symlink is copied (symlinks preserved, not followed);
  * packet183's own certification (READY-FOR-DEVICE.json, proposals/, chain/ win-path
    waiter, lineage/window-20261022/) goes under lineage-inputs/packet183-own/ as
    provenance; of its v5/evidence/ only the receipts this packet cites are kept there
    (EVIDENCE_KEEP); the 445 MB of device run trees are not copied;
  * the vendored source subtree native-base/.../packet183-twocard-s1-micro is renamed
    to .../packet185-twocard-unsplit-head, and v5/p183_*.py modules to v5/p185_*.py;
  * outside lineage-inputs/, text files get three literal rewrites:
    packet183-twocard-s1-micro -> packet185-twocard-unsplit-head, p183_v5_ -> p185_v5_,
    p183_ops_ -> p185_ops_. lineage-inputs/ stays byte-identical (history), except the
    one vendored module packet183 already amended to locate its owning packet by name.
Run once:  python3 -B copy_packet185.py   (refuses if the copy already exists).
"""
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SRC = HERE.parent / 'packet183-twocard-s1-micro'
OLD, NEW = 'packet183-twocard-s1-micro', 'packet185-twocard-unsplit-head'
REWRITES = [(OLD, NEW), ('p183_v5_', 'p185_v5_'), ('p183_ops_', 'p185_ops_')]
OWN = {'READY-FOR-DEVICE.json', 'proposals', 'chain', 'lineage/window-20261022', 'copy_packet183.py',
       'apply_s1_delta.py', 'apply_harness_delta.py', 's1-delta.patch', 'harness-delta.patch',
       'lineage/packet183-copy.json', 'lineage/packet183-copy-amendments.json', 'lineage/s1-delta.json'}
EVIDENCE_KEEP = {
    'v5/evidence/build.json', 'v5/evidence/real-census.json', 'v5/evidence/full-shape.json',
    'v5/evidence/admission.json', 'v5/evidence/final-pin-guard.json', 'v5/evidence/package-rows.json',
    'v5/evidence/waiter-decision.json',
    'v5/evidence/device-metadata-smoke-B-p183/bracket-summary.json',
    'v5/evidence/device-metadata-smoke-B-p183/window.json',
    'v5/evidence/device-metadata-v5-B-p183/bracket-summary.json',
    'v5/evidence/device-metadata-v5-B-p183/summary.json',
    'v5/evidence/device-metadata-v5-B-p183/window.json',
    'v5/evidence/device-metadata-v5-B-p183/identity.json',
}
SKIP_PARTS = {'__pycache__', 'build'}
# packet183 amended this vendored module (lineage/packet183-copy-amendments.json); it must
# keep naming its owning packet, so it is the single lineage-inputs file rewritten here.
AMEND = 'lineage-inputs/vendor/repo/experiments/own-xpu-runtime/stage2/packet58-onecard/suite_driver.py'


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def dest_rel(rel):
    if rel.startswith('v5/evidence/'):
        return 'lineage-inputs/packet183-own/' + rel if rel in EVIDENCE_KEEP else None
    if any(rel == o or rel.startswith(o + '/') for o in OWN):
        return 'lineage-inputs/packet183-own/' + rel
    parts = rel.split('/')
    if not rel.startswith('lineage-inputs/'):
        parts = [NEW if p == OLD else p for p in parts]
        if parts[0] == 'v5' and len(parts) == 2 and parts[1].startswith(('p183_v5_', 'p183_ops_')):
            parts[1] = 'p185_' + parts[1][len('p183_'):]
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
        sys.exit('refusing: packet185 copy already exists')
    commit = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    files, rewritten, moved, renamed, links, skipped = {}, [], [], [], {}, []
    for path in sorted(SRC.rglob('*')):
        rel = path.relative_to(SRC).as_posix()
        if SKIP_PARTS & set(rel.split('/')):
            continue
        if path.is_dir() and not path.is_symlink():
            continue
        out_rel = dest_rel(rel)
        if out_rel is None:
            skipped.append(rel)
            continue
        out = HERE / out_rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if out_rel != rel:
            (moved if out_rel.startswith('lineage-inputs/packet183-own/') else renamed).append([rel, out_rel])
        if path.is_symlink():
            target = os.readlink(path)
            os.symlink(target, out)
            links[out_rel] = target
            continue
        data = path.read_bytes()
        before = hashlib.sha256(data).hexdigest()
        if (not out_rel.startswith('lineage-inputs/') or out_rel == AMEND) and is_text(data):
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
        'schema': 'packet185.copy.v1', 'device_executed': False, 'source_packet': 'experiments/own-xpu-runtime/stage2/' + OLD,
        'source_commit': commit, 'rewrites': REWRITES, 'file_count': len(files), 'rewritten_count': len(rewritten),
        'rewritten': rewritten, 'moved_to_provenance': moved, 'renamed': renamed, 'symlinks': links,
        'not_copied_device_run_evidence': len(skipped),
        'note': 'source_digest values are provenance records of packet183 bytes at source_commit, not pins',
        'copied': [{'name': k, **v} for k, v in sorted(files.items())],
    }
    (HERE / 'lineage/packet185-copy.json').write_text(json.dumps(receipt, indent=1) + '\n')
    print(json.dumps({k: receipt[k] for k in ('file_count', 'rewritten_count', 'not_copied_device_run_evidence')}, indent=1))
    print('moved', len(moved), 'renamed', len(renamed), 'symlinks', len(links))


if __name__ == '__main__':
    main()

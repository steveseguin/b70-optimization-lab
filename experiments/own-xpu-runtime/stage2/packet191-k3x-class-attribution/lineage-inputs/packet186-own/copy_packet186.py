#!/usr/bin/env python3
"""Packet186 bootstrap: identity-rewritten copy of packet185's two-card v5 harness (bundle-8 line).

CPU-only file work. Reads packet185 (never writes it), writes only inside this packet.
Packet185 ran on lane B today (2026-10-22 14:00-14:22 UTC, five fresh-load views C/U/C/U/C,
unit lanequeue-B33) and decided V3 GO (u 0.222 ms, decoupled B-A 0.851 ms, drift 0.145%).
Packet186 builds V3 on that line: the device engine is RECOMPILED from packet186's entry TUs
(entry-main, p49d_submit, s1_submit) and relinked against the same 78 pinned parent objects.

What the copy does, all recorded in lineage/packet186-copy.json:
  * every regular file and symlink is copied (symlinks preserved, not followed);
  * packet185's own certification (READY-FOR-DEVICE.json, proposals/, copy script, copy
    receipt, analysis/, README/DO-NOT-REPEAT/RETENTION) goes under lineage-inputs/packet185-own/
    as provenance; of its v5/evidence/ only the receipts this packet cites are kept there
    (EVIDENCE_KEEP: CPU gate receipts and the five device views' small summaries); the ~700 MB
    of device run trees are not copied;
  * the vendored source subtree native-base/.../packet185-twocard-unsplit-head is renamed to
    .../packet186-twocard-v3, and v5/p185_*.py modules to v5/p186_*.py;
  * outside lineage-inputs/, text files get three literal rewrites:
    packet185-twocard-unsplit-head -> packet186-twocard-v3, p185_v5_ -> p186_v5_,
    p185_ops_ -> p186_ops_. lineage-inputs/ stays byte-identical (history), except the one
    vendored module packet183/185 already amended to locate its owning packet by name.
  * the four entry objects/engines under v5/build/ are NOT copied (build/ is skipped); the
    packet186 build engine compiles its own.
Run once:  python3 -B copy_packet186.py   (refuses if the copy already exists).
"""
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SRC = HERE.parent / 'packet185-twocard-unsplit-head'
OLD, NEW = 'packet185-twocard-unsplit-head', 'packet186-twocard-v3'
REWRITES = [(OLD, NEW), ('p185_v5_', 'p186_v5_'), ('p185_ops_', 'p186_ops_')]
OWN = {'READY-FOR-DEVICE.json', 'proposals', 'copy_packet185.py', 'lineage/packet185-copy.json', 'analysis',
       'README.md', 'DO-NOT-REPEAT.md', 'RETENTION.md', 'lineage/window-20261022'}
VIEW_FILES = ('bracket-summary.json', 'window.json', 'identity.json', 'run/views/00-{choice}/summary.json',
              'run/views/00-{choice}/identity.json')
VIEWS = (('device-view0-production-B-p185', 'control'), ('device-view1-unsplit-B-p185', 'unsplit'),
         ('device-view2-production-B-p185', 'control'), ('device-view3-unsplit-B-p185', 'unsplit'),
         ('device-view4-production-B-p185', 'control'))
EVIDENCE_KEEP = {
    'v5/evidence/build.json', 'v5/evidence/full-shape.json', 'v5/evidence/admission.json',
    'v5/evidence/final-pin-guard.json', 'v5/evidence/package-rows.json', 'v5/evidence/analysis.json',
    'v5/evidence/controller.json', 'v5/evidence/queue-plan.json', 'v5/evidence/check-queue-rows.json',
} | {f'v5/evidence/{view}/' + leaf.format(choice=choice) for view, choice in VIEWS for leaf in VIEW_FILES}
SKIP_PARTS = {'__pycache__', 'build'}
AMEND = 'lineage-inputs/vendor/repo/experiments/own-xpu-runtime/stage2/packet58-onecard/suite_driver.py'


def dest_rel(rel):
    if rel.startswith('v5/evidence/'):
        return 'lineage-inputs/packet185-own/' + rel if rel in EVIDENCE_KEEP else None
    if any(rel == o or rel.startswith(o + '/') for o in OWN):
        return 'lineage-inputs/packet185-own/' + rel
    parts = rel.split('/')
    if not rel.startswith('lineage-inputs/'):
        parts = [NEW if p == OLD else p for p in parts]
        if parts[0] == 'v5' and len(parts) == 2 and parts[1].startswith(('p185_v5_', 'p185_ops_')):
            parts[1] = 'p186_' + parts[1][len('p185_'):]
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
        sys.exit('refusing: packet186 copy already exists')
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
            (moved if out_rel.startswith('lineage-inputs/packet185-own/') else renamed).append([rel, out_rel])
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
    missing = sorted(k for k in EVIDENCE_KEEP if not (HERE / 'lineage-inputs/packet185-own' / k).exists())
    if missing:
        sys.exit('missing kept evidence: ' + ', '.join(missing))
    receipt = {
        'schema': 'packet186.copy.v1', 'device_executed': False, 'source_packet': 'experiments/own-xpu-runtime/stage2/' + OLD,
        'source_commit': commit, 'rewrites': REWRITES, 'file_count': len(files), 'rewritten_count': len(rewritten),
        'rewritten': rewritten, 'moved_to_provenance': moved, 'renamed': renamed, 'symlinks': links,
        'not_copied_device_run_evidence': len(skipped),
        'note': 'source_digest values are provenance records of packet185 bytes at source_commit, not pins',
        'copied': [{'name': k, **v} for k, v in sorted(files.items())],
    }
    (HERE / 'lineage').mkdir(exist_ok=True)
    (HERE / 'lineage/packet186-copy.json').write_text(json.dumps(receipt, indent=1) + '\n')
    print(json.dumps({k: receipt[k] for k in ('file_count', 'rewritten_count', 'not_copied_device_run_evidence')}, indent=1))
    print('moved', len(moved), 'renamed', len(renamed), 'symlinks', len(links))


if __name__ == '__main__':
    main()

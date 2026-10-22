#!/usr/bin/env python3
"""Packet188 bootstrap: identity-rewritten copy of packet186's two-card v5 harness (V3 record line).

CPU-only file work. Reads packet186 (never writes it), writes only inside this packet.
Packet186 measured V3 on lane B (2026-10-22 16:09-16:34 UTC, chain rule met) and packet187 set the
two-card record with it (60.659520 tok/s, cmvjvabyv040jrf01dricuz8s). Packet188 builds the k=3
composite on that line: GDN layer 26 joins the verified-token boundary (rank0_layers 0-26), plus two
separately selectable rank-0 trims (kernel_io, rank0_prepare). The device engine is RECOMPILED from
packet188's entry TUs and relinked against the same 78 pinned parent objects.

What the copy does, all recorded in lineage/packet188-copy.json:
  * every regular file and symlink is copied (symlinks preserved, not followed);
  * packet186's own certification (READY-FOR-DEVICE.json, proposals/, copy script, copy receipt,
    analysis/, README/DO-NOT-REPEAT/RETENTION, window lineage) goes under
    lineage-inputs/packet186-own/ as provenance; of its v5/evidence/ only the CPU gate receipts this
    packet cites are kept there (EVIDENCE_KEEP); its device rows (~725 MB) are NOT copied - the s188
    tests read them where packet186 retained them and pin each file by sha256;
  * packet186's lineage-inputs/ (history, byte-identical) is HARD-LINKED, not duplicated: zero new
    disk bytes (same inode, recorded per file);
  * the vendored source subtree native-base/.../packet186-twocard-v3 is renamed to
    .../packet188-twocard-k3-composite, and v5/p186_*.py modules to v5/p188_*.py;
  * outside lineage-inputs/, text files get three literal rewrites:
    packet186-twocard-v3 -> packet188-twocard-k3-composite, p186_v5_ -> p188_v5_, p186_ops_ -> p188_ops_.
  * build/ and v5/build/ are NOT copied; packet188's build engine compiles its own.
Run once:  python3 -B copy_packet188.py   (refuses if the copy already exists).
"""
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SRC = HERE.parent / 'packet186-twocard-v3'
OLD, NEW = 'packet186-twocard-v3', 'packet188-twocard-k3-composite'
REWRITES = [(OLD, NEW), ('p186_v5_', 'p188_v5_'), ('p186_ops_', 'p188_ops_')]
OWN = {'READY-FOR-DEVICE.json', 'proposals', 'copy_packet186.py', 'lineage/packet186-copy.json', 'analysis',
       'README.md', 'DO-NOT-REPEAT.md', 'RETENTION.md', 'lineage/window-20261022'}
EVIDENCE_KEEP = {'v5/evidence/' + n for n in (
    'build.json', 'full-shape.json', 'admission.json', 'v3-state.json', 'controller.json', 'analysis.json',
    'package-rows.json', 'check-queue-rows.json', 'queue-plan.json', 'final-checks.json', 'final-pin-guard.json',
    'compile-poll.json', 'safety.json', 'exec-limits.json', 'loader.json', 'entry-gate.json', 'launch-limits.json',
    'worker-gate.json', 'report-gate.json', 'pin-guard.json')}
SKIP_PARTS = {'__pycache__', 'build'}


def dest_rel(rel):
    if rel.startswith('v5/evidence/'):
        return 'lineage-inputs/packet186-own/' + rel if rel in EVIDENCE_KEEP else None
    if any(rel == o or rel.startswith(o + '/') for o in OWN):
        return 'lineage-inputs/packet186-own/' + rel
    parts = rel.split('/')
    if not rel.startswith('lineage-inputs/'):
        parts = [NEW if p == OLD else p for p in parts]
        if parts[0] == 'v5' and len(parts) == 2 and parts[1].startswith(('p186_v5_', 'p186_ops_')):
            parts[1] = 'p188_' + parts[1][len('p186_'):]
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
        sys.exit('refusing: packet188 copy already exists')
    commit = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    files, rewritten, moved, renamed, links, skipped, linked = {}, [], [], [], {}, [], {}
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
            (moved if out_rel.startswith('lineage-inputs/packet186-own/') else renamed).append([rel, out_rel])
        if path.is_symlink():
            target = os.readlink(path)
            os.symlink(target, out)
            links[out_rel] = target
            continue
        if rel.startswith('lineage-inputs/'):
            # History: identical bytes, hard link (zero new disk bytes); never rewritten.
            os.link(path, out)
            assert out.stat().st_ino == path.stat().st_ino
            linked[out_rel] = path.stat().st_ino
            files[out_rel] = {'source_relpath': rel, 'hard_link': True}
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
    missing = sorted(k for k in EVIDENCE_KEEP if not (HERE / 'lineage-inputs/packet186-own' / k).exists())
    if missing:
        sys.exit('missing kept evidence: ' + ', '.join(missing))
    receipt = {
        'schema': 'packet188.copy.v1', 'device_executed': False, 'source_packet': 'experiments/own-xpu-runtime/stage2/' + OLD,
        'source_commit': commit, 'rewrites': REWRITES, 'file_count': len(files), 'rewritten_count': len(rewritten),
        'rewritten': rewritten, 'moved_to_provenance': moved, 'renamed': renamed, 'symlinks': links,
        'hard_linked_history': len(linked), 'not_copied_device_run_evidence': len(skipped),
        'note': 'source_digest values are provenance records of packet186 bytes at source_commit, not pins; '
                'lineage-inputs/ files are hard links of packet186 history (same inode)',
        'copied': [{'name': k, **v} for k, v in sorted(files.items())],
    }
    (HERE / 'lineage').mkdir(exist_ok=True)
    (HERE / 'lineage/packet188-copy.json').write_text(json.dumps(receipt, indent=1) + '\n')
    print(json.dumps({k: receipt[k] for k in ('file_count', 'rewritten_count', 'hard_linked_history', 'not_copied_device_run_evidence')}, indent=1))
    print('moved', len(moved), 'renamed', len(renamed), 'symlinks', len(links))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Packet194 bootstrap: identity-rewritten copy of packet189's two-card v5 harness (k3x, the record engine).

CPU-only file work. Reads packet189 (never writes it), writes only inside this packet.
Packet189's k3x engine (87eec645...) is the two-card record (62.345282 tok/s via packet190). Packet193 measured the
exact gate/up instruction diet (`exp-diet`) at 0.78x production cold / 0.77x warm on card 2, byte-identical on every
claimed stratum. Packet194 integrates `exp-diet` into the k3x record engine behind an in-load key
`expert_gateup=production|diet` and screens it on lane B with a one-load bracket k3x / k3x+diet / k3x / k3x+diet / k3x.

What the copy does, all recorded in lineage/packet194-copy.json:
  * every regular file and symlink is copied (symlinks preserved, not followed);
  * packet189's own certification (READY-FOR-DEVICE.json, proposals/, copy script, copy receipt, analysis/,
    README/DO-NOT-REPEAT/RETENTION, window lineage) goes under lineage-inputs/packet189-own/ as provenance;
    of its v5/evidence/ only the CPU gate receipts this packet cites are kept there (EVIDENCE_KEEP); its device rows
    (~460 MB) are NOT copied - the s194 tests read them where packet189 retained them and pin each file by sha256;
  * packet189's lineage-inputs/ (history, byte-identical) is HARD-LINKED, not duplicated: zero new disk bytes
    (same inode, recorded per file) - except the files that carry the packet189 identity literal, which are copied
    and rewritten (packet188/189's lesson);
  * the vendored source subtree native-base/.../packet189-twocard-k3x is renamed to .../packet194-expert-diet-engine,
    v5/p189_*.py modules to v5/p194_*.py, v5/s189_decision.py to v5/s194_decision.py;
  * outside lineage-inputs/, text files get the literal rewrites in REWRITES (packet path, module prefixes,
    decision module, unit/job/output/proposal/schema identity literals). The native `p188::` namespace and the
    `// packet188` / `// packet189` attributions in comments are kept: the code is theirs.
  * build/ and v5/build/ are NOT copied; packet194's build engine compiles its own.
Run once:  python3 -B copy_packet194.py   (refuses if the copy already exists).
"""
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SRC = HERE.parent / 'packet189-twocard-k3x'
OLD, NEW = 'packet189-twocard-k3x', 'packet194-expert-diet-engine'
REWRITES = [(OLD, NEW), ('p189_v5_', 'p194_v5_'), ('p189_ops_', 'p194_ops_'), ('s189_decision', 's194_decision'),
            ('screen-packet189', 'screen-packet194'), ('wrong-packet189', 'wrong-packet194'), ("f'packet189-{", "f'packet194-{"),
            ('-p189', '-p194'), ('proposed-p189-two-card-B', 'proposed-p194-two-card-B'), ("prefix='p189-plan-'", "prefix='p194-plan-'"),
            ('packet189.ready-for-device', 'packet194.ready-for-device'), ('packet189.row.v1', 'packet194.row.v1'),
            ('packet189.s189-decision', 'packet194.s194-decision'), ('packet189.cpu-composition', 'packet194.cpu-composition'),
            ('packet189.analysis-real-inputs', 'packet194.analysis-real-inputs'), ('packet189.host-boundary', 'packet194.host-boundary'),
            ('packet189.copy.v1', 'packet194.copy.v1')]
OWN = {'READY-FOR-DEVICE.json', 'proposals', 'copy_packet189.py', 'lineage/packet189-copy.json', 'analysis',
       'README.md', 'DO-NOT-REPEAT.md', 'RETENTION.md', 'lineage/window-20261022'}
EVIDENCE_KEEP = {'v5/evidence/' + n for n in (
    'build.json', 'full-shape.json', 'admission.json', 'k3-state.json', 'controller.json', 'analysis.json', 'analysis-real-inputs.json',
    'package-rows.json', 'check-queue-rows.json', 'queue-plan.json', 'final-checks.json', 'final-pin-guard.json',
    'compile-poll.json', 'safety.json', 'exec-limits.json', 'loader.json', 'entry-gate.json', 'launch-limits.json',
    'worker-gate.json', 'report-gate.json', 'pin-guard.json')}
SKIP_PARTS = {'__pycache__', 'build'}


def dest_rel(rel):
    if rel.startswith('v5/evidence/'):
        return 'lineage-inputs/packet189-own/' + rel if rel in EVIDENCE_KEEP else None
    if any(rel == o or rel.startswith(o + '/') for o in OWN):
        return 'lineage-inputs/packet189-own/' + rel
    parts = rel.split('/')
    if not rel.startswith('lineage-inputs/'):
        parts = [NEW if p == OLD else p for p in parts]
        if parts[0] == 'v5' and len(parts) == 2:
            if parts[1].startswith(('p189_v5_', 'p189_ops_')):
                parts[1] = 'p194_' + parts[1][len('p189_'):]
            elif parts[1] in ('s189_decision.py', 'test_s189_decision.py'):
                parts[1] = parts[1].replace('s189_decision', 's194_decision')
    return '/'.join(parts)


def is_text(data):
    if b'\0' in data[:8192]:
        return False
    try:
        data.decode('utf-8')
        return True
    except UnicodeDecodeError:
        return False


def rewrite(text):
    for a, b in REWRITES:
        text = text.replace(a, b)
    return text


def main():
    if any(HERE.joinpath(x).exists() for x in ('v5', 'native-base', 'lineage-inputs')):
        sys.exit('refusing: packet194 copy already exists')
    commit = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    files, rewritten, moved, renamed, links, skipped, linked, history_rewritten = {}, [], [], [], {}, [], {}, []
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
            (moved if out_rel.startswith('lineage-inputs/packet189-own/') else renamed).append([rel, out_rel])
        if path.is_symlink():
            target = os.readlink(path)
            os.symlink(target, out)
            links[out_rel] = target
            continue
        if rel.startswith('lineage-inputs/'):
            data = path.read_bytes()
            if is_text(data) and OLD.encode() in data:
                before = hashlib.sha256(data).hexdigest()
                data = rewrite(data.decode('utf-8')).encode('utf-8')
                out.write_bytes(data)
                shutil.copymode(path, out)
                history_rewritten.append(out_rel)
                files[out_rel] = {'source_relpath': rel, 'source_digest': before, 'digest': hashlib.sha256(data).hexdigest(), 'history_rewritten': True}
                continue
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
            new = rewrite(text)
            if new != text:
                data = new.encode('utf-8')
                rewritten.append(out_rel)
        out.write_bytes(data)
        shutil.copymode(path, out)
        files[out_rel] = {'source_relpath': rel, 'source_digest': before, 'digest': hashlib.sha256(data).hexdigest()}
    missing = sorted(k for k in EVIDENCE_KEEP if not (HERE / 'lineage-inputs/packet189-own' / k).exists())
    if missing:
        sys.exit('missing kept evidence: ' + ', '.join(missing))
    receipt = {
        'schema': 'packet194.copy.v1', 'device_executed': False, 'source_packet': 'experiments/own-xpu-runtime/stage2/' + OLD,
        'source_commit': commit, 'rewrites': REWRITES, 'file_count': len(files), 'rewritten_count': len(rewritten),
        'rewritten': rewritten, 'history_rewritten': history_rewritten, 'moved_to_provenance': moved, 'renamed': renamed, 'symlinks': links,
        'hard_linked_history': len(linked), 'not_copied_device_run_evidence': len(skipped),
        'note': 'source_digest values are provenance records of packet189 bytes at source_commit, not pins; '
                'lineage-inputs/ files are hard links of packet189 history (same inode) unless history_rewritten',
        'copied': [{'name': k, **v} for k, v in sorted(files.items())],
    }
    (HERE / 'lineage').mkdir(exist_ok=True)
    (HERE / 'lineage/packet194-copy.json').write_text(json.dumps(receipt, indent=1) + '\n')
    print(json.dumps({k: receipt[k] for k in ('file_count', 'rewritten_count', 'hard_linked_history', 'not_copied_device_run_evidence')}, indent=1))
    print('moved', len(moved), 'renamed', len(renamed), 'symlinks', len(links), 'history_rewritten', history_rewritten)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Record packet184's delta over its packet153 copy (CPU only; writes lineage/harness-delta.*).

Every copied file is compared with its copy-time digest (lineage/packet184-copy.json):
  * native files must be exactly the four documented delta files (checked by the build too; the
    native unified diff is lineage/checkpoint-delta.patch, written by v5/p184_build_checkpoint.py);
  * harness files changed after the copy get a unified diff here (lineage/harness-delta.patch)
    against packet153's original with the copy rewrites applied;
  * generated outputs that the packet regenerates by design are listed, not diffed (seals and their
    mirrors, engine-commands.json, evidence/, build/);
  * every file that did not exist in the copy is listed as new.
Run before v5/cpu_seal.py --seal (package_rows.py does).
"""
import difflib, hashlib, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
P153 = HERE.parent / 'packet153-snapshot-host'
REWRITES = [('packet153-snapshot-host', HERE.name), ('p153_v5_', 'p184_v5_'), ('p153_ops_', 'p184_ops_')]
GENERATED = {'v5/cpu-seal.json', 'v5/lineage/production/screen-seal.json', 'v5/placement-validation/wrapper-seal.json',
             'v5/engine-commands.json'}
NATIVE_DELTA = {'v5/native-src/main.cpp', 'v5/native-src/rank.hpp', 'v5/native-src/mtp.hpp',
                'native-base/' + str(HERE.relative_to(ROOT)) + '/native_controller.hpp'}
SKIP_DIRS = {'build', '__pycache__', 'evidence', 'proposals'}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    receipt_copy = json.loads((HERE / 'lineage/packet184-copy.json').read_text())
    copy = {r['name']: r for r in receipt_copy['copied']}
    links = set(receipt_copy['symlinks'])
    modified, generated, native, patch = [], [], [], []
    for name, row in sorted(copy.items()):
        path = HERE / name
        if not path.exists():
            raise SystemExit('copied file removed: ' + name)
        if path.is_symlink() or sha(path) == row['digest']:
            continue
        if name in GENERATED:
            generated.append(name)
            continue
        if name in NATIVE_DELTA:
            native.append(name)
            continue
        old = (P153 / row['source_relpath']).read_text()
        for a, b in REWRITES:
            old = old.replace(a, b)
        modified.append(name)
        patch += difflib.unified_diff(old.splitlines(True), path.read_text().splitlines(True), 'packet153/' + row['source_relpath'], 'packet184/' + name)
    assert set(native) == NATIVE_DELTA, set(native) ^ NATIVE_DELTA
    new = []
    for path in sorted(HERE.rglob('*')):
        rel = path.relative_to(HERE)
        if SKIP_DIRS & set(rel.parts) or (path.is_dir() and not path.is_symlink()) or str(rel) in copy or str(rel) in links:
            continue
        if rel.parts[0] == 'lineage' and rel.name.startswith(('harness-delta', 'checkpoint-delta')):
            continue
        new.append(str(rel))
    out = HERE / 'lineage/harness-delta.patch'
    out.write_text(''.join(patch))
    receipt = dict(schema='packet184.harness-delta.v1', device_executed=False, modified_harness_files=modified,
                   native_delta_files=sorted(native), regenerated_outputs=sorted(generated), new_files=new,
                   patch=str(out.relative_to(ROOT)), patch_sha256=sha(out),
                   note='modified harness files are diffed against packet153 with the copy rewrites; native delta is lineage/checkpoint-delta.patch')
    (HERE / 'lineage/harness-delta.json').write_text(json.dumps(receipt, indent=1) + '\n')
    print('harness delta:', len(modified), 'modified,', len(native), 'native delta,', len(generated), 'regenerated,', len(new), 'new files')
    for m in modified:
        print('  modified', m)


if __name__ == '__main__':
    main()

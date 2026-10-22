#!/usr/bin/env python3
"""Packet187 bootstrap: identity-rewritten copy of packet155's two-card record-chain harness.

Packet155 ("bundle9") is packet136's record-chain packet (bundle 8, record cmve4dtir007wrf01k57sdf23,
58.798109 tok/s) adapted to a v5 engine. Its chain ran K0-K2 on lane A and then stopped in W0p on
`shared extent`: the chain transport still created packet136's 3*SLOT+4096-byte shared file, while
v5 engines map 4*SLOT+4096+64 bytes. Packet187 copies that harness for V3 (packet186's binary).

Copied (CPU-only file work; packet155 and its orchestration are read, never written):
  * stage2/packet155-record-bundle9 -> stage2/packet187-record-bundle-v3, excluding build/,
    submission/, evidence/, orchestration-snapshot/, snapshot-static/ (packet153 native snapshot),
    selections/ (the static view) and READY-FOR-DEVICE.json; lineage-inputs/ stays byte-identical;
  * ops/packet155-orchestration -> ops/packet187-orchestration, excluding evidence/,
    lineage-p155-scaffolding/, ready.json, READY-FOR-DEVICE.json, cpu-receipts.json, proposal.jsonl
    and the packet153 native/memory bindings (replaced by packet186 bindings).
Text rewrites outside lineage-inputs/: packet155-record-bundle9 -> packet187-record-bundle-v3,
packet155 -> packet187, p155 -> p187 and the module names *155 -> *187 (files renamed alike).
Receipt: lineage/packet187-copy.json.  Run once: python3 -B copy_packet187.py
"""
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STAGE = HERE.parent
OPS = ROOT / 'experiments/own-xpu-runtime/ops'
SOURCES = [(STAGE / 'packet155-record-bundle9', HERE,
            {'build', 'submission', 'evidence', 'orchestration-snapshot', 'snapshot-static', 'selections', 'READY-FOR-DEVICE.json'}),
           (OPS / 'packet155-orchestration', OPS / 'packet187-orchestration',
            {'evidence', 'lineage-p155-scaffolding', 'ready.json', 'READY-FOR-DEVICE.json', 'cpu-receipts.json', 'proposal.jsonl',
             'inputs/packet153-native.json', 'inputs/packet153-memory.json'})]
REWRITES = [('packet155-record-bundle9', 'packet187-record-bundle-v3'), ('packet155', 'packet187'), ('p155', 'p187'),
            ('entry155', 'entry187'), ('seal155', 'seal187'), ('finalize155', 'finalize187'), ('policy155', 'policy187'),
            ('readiness155', 'readiness187'), ('submission155', 'submission187'), ('stream_gate155', 'stream_gate187'),
            ('compile_turn155', 'compile_turn187'), ('preparation155', 'preparation187'), ('ENTRY155', 'ENTRY187'),
            ('results155c', 'results187')]
SKIP = {'__pycache__'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rename(name):
    for a, b in REWRITES:
        name = name.replace(a, b)
    return name


def text(data):
    if b'\0' in data[:8192]:
        return None
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        return None


def main():
    if (HERE / 'chain_pipeline.py').exists() or (OPS / 'packet187-orchestration').exists():
        sys.exit('refusing: packet187 copy already exists')
    commit = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    receipt = dict(schema='packet187.copy.v1', device_executed=False, source_commit=commit, rewrites=REWRITES, trees=[])
    for src, dst, exclude in SOURCES:
        files, links, renamed, rewritten, skipped = {}, {}, [], [], []
        for path in sorted(src.rglob('*')):
            rel = path.relative_to(src).as_posix()
            parts = rel.split('/')
            if SKIP & set(parts) or any(rel == x or rel.startswith(x + '/') for x in exclude):
                if path.is_file() and not path.is_symlink() and not (SKIP & set(parts)):
                    skipped.append(rel)
                continue
            if path.is_dir() and not path.is_symlink():
                continue
            history = parts[0] == 'lineage-inputs'
            out_rel = rel if history else '/'.join(rename(p) for p in parts)
            if out_rel != rel:
                renamed.append([rel, out_rel])
            out = dst / out_rel
            out.parent.mkdir(parents=True, exist_ok=True)
            if path.is_symlink():
                os.symlink(os.readlink(path), out)
                links[out_rel] = os.readlink(path)
                continue
            data = path.read_bytes()
            before = sha(data)
            decoded = None if history else text(data)
            if decoded is not None:
                new = rename(decoded)
                if new != decoded:
                    data = new.encode('utf-8')
                    rewritten.append(out_rel)
            out.write_bytes(data)
            shutil.copymode(path, out)
            files[out_rel] = dict(source_digest=before, digest=sha(data))
        receipt['trees'].append(dict(source=str(src.relative_to(ROOT)), destination=str(dst.relative_to(ROOT)), file_count=len(files),
                                     rewritten=rewritten, renamed=renamed, symlinks=links, excluded_files=len(skipped),
                                     files=files))
        print(dst.relative_to(ROOT), 'files', len(files), 'rewritten', len(rewritten), 'links', len(links), 'excluded', len(skipped))
    receipt['note'] = 'source_digest values record packet155 bytes at source_commit; they are provenance, not pins'
    (HERE / 'lineage').mkdir(exist_ok=True)
    (HERE / 'lineage/packet187-copy.json').write_text(json.dumps(receipt, indent=1) + '\n')


if __name__ == '__main__':
    main()

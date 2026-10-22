#!/usr/bin/env python3
"""Place packet186's V3 engine and native source snapshot in packet187 (NO compile, NO relink).

* build/device/own-rt-iq3, build/gnu-host/own-rt-iq3: byte copies of packet186's linked V3 engines,
  verified against packet186's build receipt (v5/evidence/build.json) and against the binary identity
  recorded by every packet186 device row (identity.json binary_sha256 = 693cc194...).
* build/{device,gnu-host}/<fixtures>, build/fusion-fixtures/*: the same links packet155/136 use for the
  K-gate fixture binaries (unchanged kernels), each verified against packet136's chain-seal artifacts.
* build/input/: packet155's chain input metadata (plan/identity/tokens), byte copies verified against
  the packet136 chain seal's input_sha256.
* v3-native/: hash-pinned snapshot of the V3 native sources the engines were compiled from (packet186
  v5/native-src, v5/native, native-base, engine commands, 78 parent-object pins, the V3 patch).
Writes ops/packet187-orchestration/inputs/packet186-native.json, its packet-local copy lineage-inputs/packet186-native.json
and startup103.json's pin of that copy. Re-runnable; refuses on any mismatch.
"""
import hashlib, json, os, shutil, sys
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
STAGE = P.parent
O = ROOT / 'experiments/own-xpu-runtime/ops/packet187-orchestration'
SRC = STAGE / 'packet186-twocard-v3'
P155 = STAGE / 'packet155-record-bundle9'
EXPECTED = '693cc194bb577cd20f95e63f06bf6e463074944e2d1193f8c3ed1a8a4528d739'


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    assert shutil.disk_usage('/').free >= 25_000_000_000, 'root free below the 25 GB floor'
    build = json.loads((SRC / 'v5/evidence/build.json').read_text())
    assert build['passed'] and build['binary_sha256'] == EXPECTED
    binaries = {}
    for mode in ('device', 'gnu-host'):
        src = SRC / 'v5/build' / mode / 'own-rt-iq3'
        rel = f'experiments/own-xpu-runtime/stage2/packet186-twocard-v3/v5/build/{mode}/own-rt-iq3'
        assert sha(src) == build['artifacts'][rel], 'packet186 engine differs from its build receipt: ' + mode
        dst = P / 'build' / mode / 'own-rt-iq3'
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(src, dst)
        assert sha(dst) == sha(src)
        binaries['build/' + mode + '/own-rt-iq3'] = dict(sha256=sha(dst), origin=rel)
    assert binaries['build/device/own-rt-iq3']['sha256'] == EXPECTED
    seal = json.loads((O / 'inputs/packet136-chain-seal.json').read_text())
    links = {}
    for folder in ('device', 'gnu-host', 'fusion-fixtures'):
        for link in sorted((P155 / 'build' / folder).iterdir()):
            if link.name == 'own-rt-iq3':
                continue
            assert link.is_symlink(), link
            mine = P / 'build' / folder / link.name
            mine.parent.mkdir(parents=True, exist_ok=True)
            if not mine.is_symlink():
                os.symlink(os.readlink(link), mine)
            assert os.readlink(mine) == os.readlink(link)
            links['build/' + folder + '/' + link.name] = dict(target=os.readlink(mine), sha256=sha(mine))
    for name, digest in seal['artifacts_sha256'].items():
        if name.endswith('/own-rt-iq3'):
            continue
        assert links['build/' + name]['sha256'] == digest, 'fixture link differs from the packet136 chain seal: ' + name
    for leaf in sorted((P155 / 'build/input').iterdir()):
        dst = P / 'build/input' / leaf.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(leaf, dst)
        assert sha(dst) == sha(leaf)
    assert sha(P / 'build/input/input.json') == seal['input_sha256'], 'chain input changed'
    native = P / 'v3-native'
    pairs = [(SRC / 'v5/native-src', native / 'native-src'), (SRC / 'v5/native', native / 'native'),
             (SRC / 'native-base', native / 'native-base')]
    sources = {}
    for src, dst in pairs:
        for f in sorted(src.rglob('*')):
            if f.is_dir() or '__pycache__' in f.parts:
                continue
            out = dst / f.relative_to(src)
            out.parent.mkdir(parents=True, exist_ok=True)
            if f.is_symlink():
                if not out.is_symlink():
                    os.symlink(os.readlink(f), out)
                continue
            if not out.exists():
                shutil.copy2(f, out)
            assert sha(out) == sha(f)
            sources[str(out.relative_to(P))] = sha(out)
    # packet186's build receipt is provenance: it lives under lineage-inputs/ (packet143 layout, guard_layout187.py).
    for leaf, src in (('v3-native.patch', SRC / 'v5/v3-native.patch'), ('engine-commands.json', SRC / 'v5/engine-commands.json'),
                      ('immutable-binaries.json', SRC / 'immutable-binaries.json'), ('packet186-build.json', SRC / 'v5/evidence/build.json')):
        out = (P / 'lineage-inputs' / leaf) if leaf == 'packet186-build.json' else native / leaf
        if not out.exists():
            shutil.copy2(src, out)
        assert sha(out) == sha(src)
        sources[str(out.relative_to(P))] = sha(out)
    row = dict(schema='packet187.native-binding.v1', engine='packet186 V3 (bundle 8 + V3 boundary + packet153 static snapshot selection)',
               reused_byte_for_byte=True, relinked=False, compiler_runs=0, binaries=binaries, fixture_links=links, sources=sources,
               parent_object_pins=len(json.loads((SRC / 'immutable-binaries.json').read_text())),
               note='origin values are provenance of the copied bytes, not runtime dependencies')
    (O / 'inputs/packet186-native.json').write_text(json.dumps(row, indent=1) + '\n')
    # The sealed closure pins the packet-local copy (lineage-inputs/); chain_seal requires both copies equal.
    local = P / 'lineage-inputs/packet186-native.json'
    shutil.copyfile(O / 'inputs/packet186-native.json', local)
    startup = json.loads((P / 'startup103.json').read_text())
    startup['sources'] = {str(local.relative_to(ROOT)): sha(local)}
    (P / 'startup103.json').write_text(json.dumps(startup, indent=2) + '\n')
    print('placed: device', EXPECTED[:16], 'links', len(links), 'sources', len(sources))


if __name__ == '__main__':
    main()

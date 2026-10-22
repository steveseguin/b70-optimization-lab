#!/usr/bin/env python3
"""Place packet189's k3x engine and native source snapshot in packet190 (NO compile, NO relink).

* build/device/own-rt-iq3, build/gnu-host/own-rt-iq3: byte copies of packet189's linked k3x engines,
  verified against packet189's build receipt (v5/evidence/build.json) and against the binary identity
  recorded by both packet189 device rows (identity.json binary_sha256 = 87eec645...).
* build/{device,gnu-host}/<fixtures>, build/fusion-fixtures/*: the same links packet187/155/136 use for
  the K-gate fixture binaries (unchanged kernels), each verified against packet136's chain-seal artifacts.
* build/input/: packet187's chain input metadata (plan/identity/tokens), byte copies verified against
  the packet136 chain seal's input_sha256.
* k3x-native/: hash-pinned snapshot of the k3x native sources the engines were compiled from (packet189
  v5/native-src, v5/native, native-base, engine commands, 78 parent-object pins, the V3/k3/k3x patches).
Writes ops/packet190-orchestration/inputs/packet189-native.json, its packet-local copy
lineage-inputs/packet189-native.json and startup103.json's pin of that copy. Re-runnable; refuses on any mismatch.
"""
import hashlib, json, os, shutil, sys
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
STAGE = P.parent
O = ROOT / 'experiments/own-xpu-runtime/ops/packet190-orchestration'
SRC = STAGE / 'packet189-twocard-k3x'
P187 = STAGE / 'packet187-record-bundle-v3'
EXPECTED = '87eec6453a2a9a9bfe30ed19466c6a70644d9cd168f734be87d2f0a17b776af4'
GNU_HOST = 'a50588a9e89adacb14cefcc53dd271cbd8054b81fe076dbca81d7b779d99f6c6'
ROWS = ('device-row0-smoke-k3x-B-p189', 'device-row1-bracket-v3k-k3x-B-p189')


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    assert shutil.disk_usage('/').free >= 27_000_000_000, 'root free below the 27 GB CPU stop floor'
    build = json.loads((SRC / 'v5/evidence/build.json').read_text())
    assert build['passed'] and build['binary_sha256'] == EXPECTED and build['device_executed'] is False
    rows = {}
    for row in ROWS:
        identity = json.loads((SRC / 'v5/evidence' / row / 'identity.json').read_text())
        assert identity['binary_sha256'] == EXPECTED, 'packet189 device row ran a different engine: ' + row
        rows[row] = dict(identity_sha256=sha(SRC / 'v5/evidence' / row / 'identity.json'), binary_sha256=identity['binary_sha256'])
    binaries = {}
    for mode, want in (('device', EXPECTED), ('gnu-host', GNU_HOST)):
        src = SRC / 'v5/build' / mode / 'own-rt-iq3'
        rel = f'experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/v5/build/{mode}/own-rt-iq3'
        assert sha(src) == build['artifacts'][rel] == want, 'packet189 engine differs from its build receipt: ' + mode
        dst = P / 'build' / mode / 'own-rt-iq3'
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(src, dst)
        assert sha(dst) == sha(src)
        binaries['build/' + mode + '/own-rt-iq3'] = dict(sha256=sha(dst), origin=rel)
    seal = json.loads((O / 'inputs/packet136-chain-seal.json').read_text())
    links = {}
    for folder in ('device', 'gnu-host', 'fusion-fixtures'):
        for link in sorted((P187 / 'build' / folder).iterdir()):
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
    for leaf in sorted((P187 / 'build/input').iterdir()):
        dst = P / 'build/input' / leaf.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(leaf, dst)
        assert sha(dst) == sha(leaf)
    assert sha(P / 'build/input/input.json') == seal['input_sha256'], 'chain input changed'
    native = P / 'k3x-native'
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
    checked = 0
    for rel, digest in build['sources'].items():
        prefix = 'experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/'
        if not rel.startswith(prefix):
            continue  # inherited parent objects (packet103 lineage) are pinned by immutable-binaries.json
        local = P / 'k3x-native' / rel[len(prefix):].replace('v5/', '', 1)
        if local.exists():
            assert sha(local) == digest, 'snapshot differs from the packet189 build receipt: ' + rel
            checked += 1
    assert checked >= 13, 'too few packet189 build sources matched the snapshot: %d' % checked  # 5 native-src + 8 native entry TUs; build/checked mirrors are not snapshotted
    # packet189's build receipt is provenance: it lives under lineage-inputs/ (packet143 layout, guard_layout190.py).
    for leaf, src in (('k3x-native.patch', SRC / 'v5/k3x-native.patch'), ('k3-native.patch', SRC / 'v5/k3-native.patch'),
                      ('v3-native.patch', SRC / 'v5/v3-native.patch'), ('engine-commands.json', SRC / 'v5/engine-commands.json'),
                      ('immutable-binaries.json', SRC / 'immutable-binaries.json'), ('packet189-build.json', SRC / 'v5/evidence/build.json')):
        out = (P / 'lineage-inputs' / leaf) if leaf == 'packet189-build.json' else native / leaf
        if not out.exists():
            shutil.copy2(src, out)
        assert sha(out) == sha(src)
        sources[str(out.relative_to(P))] = sha(out)
    row = dict(schema='packet190.native-binding.v1',
               engine='packet189 k3x (bundle 8 + packet153 static snapshot + V3 head placement + k3 boundary rank0-k3 (layers 24-26 on rank 0 for the verified token) + kernel_io=kernel + rank0_prepare=async + boundary_export=copy)',
               reused_byte_for_byte=True, relinked=False, compiler_runs=0, binaries=binaries, fixture_links=links, sources=sources,
               parent_object_pins=len(json.loads((SRC / 'immutable-binaries.json').read_text())), packet189_rows=rows,
               packet189_build_compiler_runs=build['compiler_runs'],
               note='origin values are provenance of the copied bytes, not runtime dependencies; packet189 compiled the engines (8 runs, 0 warnings), packet190 ran no compiler for them')
    (O / 'inputs/packet189-native.json').write_text(json.dumps(row, indent=1) + '\n')
    # The sealed closure pins the packet-local copy (lineage-inputs/); chain_seal requires both copies equal.
    local = P / 'lineage-inputs/packet189-native.json'
    shutil.copyfile(O / 'inputs/packet189-native.json', local)
    startup = json.loads((P / 'startup103.json').read_text())
    startup['sources'] = {str(local.relative_to(ROOT)): sha(local)}
    startup['scope'] = ('packet189 k3x native snapshot and engines (reused byte for byte); actual all-window entry probe is separately required by '
                        'verify_cpu (entry190/argument gate); k3x production-shape, state and transport proofs are evidence/real-shape.json, '
                        'composition-bytes.json and transport-gate.json. Inherited K fixtures bound to the packet136 receipt.')
    (P / 'startup103.json').write_text(json.dumps(startup, indent=2) + '\n')
    print('placed: device', EXPECTED[:16], 'gnu-host', GNU_HOST[:16], 'links', len(links), 'sources', len(sources))


if __name__ == '__main__':
    main()

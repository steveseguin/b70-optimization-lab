#!/usr/bin/env python3
"""Place packet194's exp-diet engine and native source snapshot in packet195 (NO compile, NO relink).

* build/device/own-rt-iq3, build/gnu-host/own-rt-iq3: byte copies of packet194's linked engines (k3x record engine
  + the `expert_gateup=production|diet` key, Arm 13 = p193diet::GateUp), verified against packet194's build receipt
  (v5/evidence/build.json: 10 compiler runs, 0 warnings, pinned header aab37609...) and against the binary identity
  recorded by both packet194 device rows (identity.json binary_sha256 = b8482321...).
* build/{device,gnu-host}/<fixtures>, build/fusion-fixtures/*: the same links packet190/187/155/136 use for
  the K-gate fixture binaries (unchanged kernels), each verified against packet136's chain-seal artifacts.
* build/input/: packet190's chain input metadata (plan/identity/tokens), byte copies verified against
  the packet136 chain seal's input_sha256.
* diet-native/: hash-pinned snapshot of the native sources the engines were compiled from (packet194
  v5/native-src, v5/native, native-base incl. the pinned p193_diet.hpp, engine commands, 78 parent-object pins,
  the V3/k3/k3x/p194 patches).
Writes ops/packet195-orchestration/inputs/packet194-native.json, its packet-local copy
lineage-inputs/packet194-native.json and startup103.json's pin of that copy. Re-runnable; refuses on any mismatch.
"""
import hashlib, json, os, shutil, sys
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
STAGE = P.parent
O = ROOT / 'experiments/own-xpu-runtime/ops/packet195-orchestration'
SRC = STAGE / 'packet194-expert-diet-engine'
P190 = STAGE / 'packet190-record-bundle-k3x'
EXPECTED = 'b8482321769039274daf42b70f783517177cbc8c1d0b2d81b8ebab25f1442bdc'
GNU_HOST = '5d8f3c057ccbe2214da30bbf98f656f23d63653db328c64102cfdf59425720db'
DIET_HEADER = 'aab37609be226ead4a255a44d87c1afb93e6d64d7819457c4aeecd33bcb750d8'
ROWS = ('device-row0-smoke-k3x-diet-B-p194', 'device-row1-bracket-k3x-diet-B-p194')


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    assert shutil.disk_usage('/').free >= 27_000_000_000, 'root free below the 27 GB CPU stop floor'
    build = json.loads((SRC / 'v5/evidence/build.json').read_text())
    assert build['passed'] and build['binary_sha256'] == EXPECTED and build['device_executed'] is False
    assert build['warning_lines'] == 0 and build['diet_header_sha256'] == DIET_HEADER and build['inherited_parent_objects'] == 76
    rows = {}
    for row in ROWS:
        identity = json.loads((SRC / 'v5/evidence' / row / 'identity.json').read_text())
        assert identity['binary_sha256'] == EXPECTED, 'packet194 device row ran a different engine: ' + row
        rows[row] = dict(identity_sha256=sha(SRC / 'v5/evidence' / row / 'identity.json'), binary_sha256=identity['binary_sha256'])
    binaries = {}
    for mode, want in (('device', EXPECTED), ('gnu-host', GNU_HOST)):
        src = SRC / 'v5/build' / mode / 'own-rt-iq3'
        rel = f'experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/v5/build/{mode}/own-rt-iq3'
        assert sha(src) == build['artifacts'][rel] == want, 'packet194 engine differs from its build receipt: ' + mode
        dst = P / 'build' / mode / 'own-rt-iq3'
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(src, dst)
        assert sha(dst) == sha(src)
        binaries['build/' + mode + '/own-rt-iq3'] = dict(sha256=sha(dst), origin=rel)
    seal = json.loads((O / 'inputs/packet136-chain-seal.json').read_text())
    links = {}
    for folder in ('device', 'gnu-host', 'fusion-fixtures'):
        for link in sorted((P190 / 'build' / folder).iterdir()):
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
    for leaf in sorted((P190 / 'build/input').iterdir()):
        dst = P / 'build/input' / leaf.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(leaf, dst)
        assert sha(dst) == sha(leaf)
    assert sha(P / 'build/input/input.json') == seal['input_sha256'], 'chain input changed'
    native = P / 'diet-native'
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
    header = native / 'native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/p193_diet.hpp'
    assert sha(header) == DIET_HEADER == sha(ROOT / build['diet_header_pin_source']), 'the pinned exp-diet header differs from packet193/194'
    checked = 0
    for rel, digest in build['sources'].items():
        prefix = 'experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/'
        if not rel.startswith(prefix):
            continue  # inherited parent objects (packet103 lineage) are pinned by immutable-binaries.json
        local = P / 'diet-native' / rel[len(prefix):].replace('v5/', '', 1)
        if local.exists():
            assert sha(local) == digest, 'snapshot differs from the packet194 build receipt: ' + rel
            checked += 1
    assert checked >= 13, 'too few packet194 build sources matched the snapshot: %d' % checked  # 5 native-src + 8 native entry TUs; build/checked mirrors are not snapshotted
    # packet194's build receipt is provenance: it lives under lineage-inputs/ (packet143 layout, guard_layout195.py).
    for leaf, src in (('p194-native.patch', SRC / 'v5/p194-native.patch'), ('k3x-native.patch', SRC / 'v5/k3x-native.patch'),
                      ('k3-native.patch', SRC / 'v5/k3-native.patch'), ('v3-native.patch', SRC / 'v5/v3-native.patch'),
                      ('engine-commands.json', SRC / 'v5/engine-commands.json'), ('immutable-binaries.json', SRC / 'immutable-binaries.json'),
                      ('packet194-build.json', SRC / 'v5/evidence/build.json')):
        out = (P / 'lineage-inputs' / leaf) if leaf == 'packet194-build.json' else native / leaf
        if not out.exists():
            shutil.copy2(src, out)
        assert sha(out) == sha(src)
        sources[str(out.relative_to(P))] = sha(out)
    row = dict(schema='packet195.native-binding.v1',
               engine='packet194 exp-diet in the k3x record engine (bundle 8 + packet153 static snapshot + V3 head placement + k3 boundary rank0-k3 '
                      '(layers 24-26 on rank 0 for the verified token) + kernel_io=kernel + rank0_prepare=async + boundary_export=copy + '
                      'expert_gateup=diet: p193diet::GateUp at every exp-halfcache gate/up site, bit-identical to p90exp::Kernel<IQ2_S,2560,64,false,true>)',
               reused_byte_for_byte=True, relinked=False, compiler_runs=0, binaries=binaries, fixture_links=links, sources=sources,
               diet_header_sha256=DIET_HEADER, diet_header_pin_source=build['diet_header_pin_source'],
               parent_object_pins=len(json.loads((SRC / 'immutable-binaries.json').read_text())), packet194_rows=rows,
               packet194_build_compiler_runs=build['compiler_runs'], packet194_build_warning_lines=build['warning_lines'],
               packet194_replaced_parent_objects=sorted(build['replaced_parent_objects']),
               note='origin values are provenance of the copied bytes, not runtime dependencies; packet194 compiled the engines (10 runs, 0 warnings, '
                    '76 parent objects pinned, 2 replaced: packet103 p49d_expert_submit.o), packet195 ran no compiler for them')
    (O / 'inputs/packet194-native.json').write_text(json.dumps(row, indent=1) + '\n')
    # The sealed closure pins the packet-local copy (lineage-inputs/); chain_seal requires both copies equal.
    local = P / 'lineage-inputs/packet194-native.json'
    shutil.copyfile(O / 'inputs/packet194-native.json', local)
    startup = json.loads((P / 'startup103.json').read_text())
    startup['sources'] = {str(local.relative_to(ROOT)): sha(local)}
    startup['scope'] = ('packet194 exp-diet native snapshot and engines (reused byte for byte); actual all-window entry probe is separately required by '
                        'verify_cpu (entry195/argument gate); k3x-diet production-shape, state and transport proofs are evidence/real-shape.json, '
                        'composition-bytes.json and transport-gate.json. Inherited K fixtures bound to the packet136 receipt.')
    (P / 'startup103.json').write_text(json.dumps(startup, indent=2) + '\n')
    print('placed: device', EXPECTED[:16], 'gnu-host', GNU_HOST[:16], 'links', len(links), 'sources', len(sources))


if __name__ == '__main__':
    main()

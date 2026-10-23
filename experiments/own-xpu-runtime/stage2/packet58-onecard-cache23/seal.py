"""Hash the private source, build inputs, CPU gates and device entry (packet58-onecard-cache23).

Same receipt schema and layout as the line's seal (screen/build-receipt.json, read by screen/window.py
build_gate on the device path); the gate leaves are this packet's. The engine is REBUILT here.
  python3 -B seal.py            write screen/build-receipt.json
  python3 -B seal.py --verify   check every sealed source, artifact and gate
"""
import hashlib, json, sys
from pathlib import Path
P = Path(__file__).resolve().parent; ROOT = P.parents[3]; Q = P / 'screen'
LEAVES = ('build', 'cache-identity', 'preparation', 'loader', 'analyzer-real-parent', 'python-cpu-gates', 'drain-fix')


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def save(p, r):
    p.write_text(json.dumps(r, indent=2) + '\n')


def main():
    if '--verify' in sys.argv:
        r = json.loads((Q / 'build-receipt.json').read_text())
        for root, key in [(ROOT, 'sources'), (Q, 'artifacts'), (Q, 'gates')]:
            for n, h in r[key].items():
                assert sha(root / n) == h, n
        print('PASS sealed sources and CPU evidence'); return
    gates = {}
    for leaf in LEAVES:
        f = P / 'evidence' / f'{leaf}.json'; r = json.loads(f.read_text())
        assert r['passed'] is True and r['device_executed'] is False, leaf
        dest = Q / 'evidence' / f'p58c23-{leaf}.json'
        save(dest, dict(passed=True, device_executed=False, evidence=str(f.relative_to(ROOT)), evidence_sha256=sha(f)))
        gates[str(dest.relative_to(Q))] = sha(dest)
    prep = P / 'evidence/preparation.json'; r = json.loads(prep.read_text())
    assert r['real_reset_sensors'] == 130 and r['requests'] == 60 and r['p176_kernel_tail_stores'] == 60 and r['p176_kernel_head_loads'] == 60
    assert r['cache_allocation_bytes'] == 23049601024 and r['peak_device_bytes'] <= r['device_owned_bound_bytes'] == 29828911360
    for leaf in ('fullshape-submit-cpu.json', 'postload-allocation-cpu.json'):
        dest = Q / 'evidence' / leaf
        save(dest, dict(passed=True, device_executed=False, scope='real device-define CPU transport under Landlock with the max/max23 bracket at production size: all 5 view resets and 60 request resets, real allocate()/plan bound checks',
                        evidence=str(prep.relative_to(ROOT)), evidence_sha256=sha(prep)))
        gates[str(dest.relative_to(Q))] = sha(dest)
    for leaf in ('argument-gate.json', 'startup-cpu.json'):
        dest = Q / 'evidence' / leaf
        assert json.loads(dest.read_text())['passed']
        gates[str(dest.relative_to(Q))] = sha(dest)
    build = json.loads((P / 'evidence/build.json').read_text())
    sources = {}
    for f in P.rglob('*'):
        if not f.is_file() or f.is_symlink():
            continue
        rel = f.relative_to(P)
        if any(n in rel.parts for n in ('evidence', '__pycache__')):
            continue
        if rel.parts[0] == 'build':
            continue
        if f.name in ('build-receipt.json', 'READY-FOR-DEVICE.json', 'queue.lock', 'window.lock'):
            continue
        sources[str(f.relative_to(ROOT))] = sha(f)
    sources.update(json.loads((P / 'oracle-binding.json').read_text())['files_sha256'])
    # Executable inputs stay hash-bound even though generated object payloads are ignored by Git.
    for f in (P / 'build').rglob('*.o'):
        if f.is_file():
            sources[str(f.relative_to(ROOT))] = sha(f)
    artifacts = {str(f.relative_to(P)): sha(f) for f in (P / 'build/device/own-rt-iq3', P / 'build/device/p58-cache-fixtures',
                                                         P / 'build/device/p58-cache-fixtures-core', P / 'build/gnu-host/own-rt-iq3', P / 'build/preparation/prepare-probe')}
    for name, digest in build['artifacts'].items():
        assert artifacts[name] == digest, 'artifact changed since the build receipt: ' + name
    row = dict(schema='own-runtime.packet58.build.v1', passed=True, device_executed=False, sources=sources, artifacts=artifacts, gates=gates,
               arithmetic='iq3-p49-split32-v1', kv_dtype='BF16', model_loads=1, packet='packet58-onecard-cache23',
               engine_rebuilt=True, engine_sha256=artifacts['build/device/own-rt-iq3'], parent_engine_sha256='1b41fb4da10a3c8c644f44f6288b9b1af0f46300847a06a254420796af921145',
               cache_allocation_bytes=23049601024, cache_usable_bytes=dict(max=21552729600, max23=23049601024), device_owned_bound_bytes=29828911360,
               driver_allowance_bytes=671088640, host_required_available_bytes=100487123456, native_delta='native-cache23-delta.patch', build_receipt='evidence/build.json')
    save(Q / 'build-receipt.json', row)
    print('PASS seal', len(sources), 'inputs')


if __name__ == '__main__':
    main()

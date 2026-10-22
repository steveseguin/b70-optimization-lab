#!/usr/bin/env python3
"""Packet182: carry packet176's binary-level CPU gates by byte identity (no re-run). CPU only.

The engine, K1 core, host and preparation binaries are byte copies of packet176's sealed
build (lineage/packet182-copy.json); only the 16 KB K1 exec wrapper was rebuilt
(evidence/k1-wrapper.json). packet176's binary gates (kernel I/O option parser and
exactness, CPU exactness on GNU/Intel, wait tests, flags, source-delta test, build)
therefore apply unchanged. This receipt checks every binary against the hashes those
committed receipts recorded (read from git HEAD) and records each receipt as a
{name, parent_relpath, parent_digest} provenance record (never a pin).
"""
import hashlib, json, subprocess
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
SRC = 'experiments/own-xpu-runtime/stage2/packet176-onecard-kernelio'
GATES = ('kernel-io', 'cpu-exactness', 'wait-tests', 'flags', 'kernelio-delta-test', 'build', 'preparation')


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def show(rel):
    return subprocess.run(['git', '-C', str(ROOT), 'show', 'HEAD:' + rel], stdin=subprocess.DEVNULL, capture_output=True, check=True).stdout


def main():
    receipts, provenance = {}, []
    for g in GATES:
        raw = show(f'{SRC}/evidence/{g}.json')
        row = json.loads(raw)
        assert row['passed'] is True and row['device_executed'] is False, g
        receipts[g] = row
        provenance.append(dict(name=f'{g}.json', parent_relpath=f'{SRC}/evidence/{g}.json', parent_digest=hashlib.sha256(raw).hexdigest()))
    seal = json.loads(show(f'{SRC}/screen/build-receipt.json'))
    checks = []
    for name in ('build/device/own-rt-iq3', 'build/device/p58-cache-fixtures-core'):
        assert sha(P / name) == seal['artifacts'][name], name
        checks.append(dict(binary=name, sha256=sha(P / name), equals='packet176 screen/build-receipt.json artifacts'))
    for r in receipts['cpu-exactness']['records']:
        name = f"build/{r['compiler']}/own-rt-iq3"
        assert sha(P / name) == r['binary_sha256'], name
        checks.append(dict(binary=name, sha256=r['binary_sha256'], equals='packet176 cpu-exactness record'))
    prep = receipts['preparation']
    assert sha(P / 'build/device/own-rt-iq3') == prep['target_binary_sha256']
    assert sha(P / 'build/preparation/prepare-probe') == prep['binary_sha256']
    assert sha(P / 'native/generated/main.cpp') == prep['native_source_sha256']
    checks.append(dict(binary='build/preparation/prepare-probe', sha256=prep['binary_sha256'], equals='packet176 preparation receipt'))
    k1 = json.loads((P / 'evidence/k1-wrapper.json').read_text())
    assert k1['passed'] and k1['wrapper_sha256'] == sha(P / 'build/device/p58-cache-fixtures')
    assert receipts['kernel-io']['fails_on_old_code'] is True
    row = dict(schema='packet182.inherited-binary-gates.v1', passed=True, device_executed=False,
               rule='binary-level gates are carried only for byte-identical binaries; the rebuilt K1 wrapper has its own receipt',
               binaries=checks, rebuilt=dict(binary='build/device/p58-cache-fixtures', receipt='evidence/k1-wrapper.json', sha256=k1['wrapper_sha256']),
               carried_gates=list(GATES), provenance=provenance,
               native_sources_unchanged=dict(main_cpp_sha256=sha(P / 'native/generated/main.cpp')),
               not_rerun='kernel-io, cpu-exactness, wait-tests, flags and the source-delta test exercise the binaries/sources above; '
                         'identical bytes give identical results, so they were not re-run (lean CPU gates)')
    (P / 'evidence/inherited-binary-gates.json').write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps(dict(passed=True, binaries=len(checks), carried=len(GATES))))


if __name__ == '__main__':
    main()

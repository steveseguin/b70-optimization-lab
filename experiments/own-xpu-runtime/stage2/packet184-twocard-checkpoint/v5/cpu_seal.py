"""Packet184 CPU composition seal: every CPU gate passed, the source/build closure hashed.

Replaces the copied packet153 seal (same verify()/check_sources() contract, which the inherited
harness calls: common.sealed -> bracket_config.sealed_identity -> verify). Writes v5/cpu-seal.json and
its two required mirrors (lineage/production/screen-seal.json, placement-validation/wrapper-seal.json).
Device quality and checkpoint qualification stay pending: nothing here ran on a device.
"""
import argparse, json, subprocess, sys
from p184_build_checkpoint import P, LOCAL, ROOT, sha, save

GATES = ('build', 'native-delta', 'checkpoint-cpu', 'production-shape', 'worker-rehearsal', 'safety', 'exec-limits', 'admission')
LABEL, CONTRACT = 'experimental-two-card', 'v1.2+p184'


def check_sources(rows):
    for name, digest in rows.items():
        assert (ROOT / name).is_file() and sha(ROOT / name) == digest, 'source changed: ' + name


def seal():
    rows = {n: json.loads((P / 'evidence' / (n + '.json')).read_text()) for n in GATES}
    for name, row in rows.items():
        assert row['passed'] and row['device_executed'] is False, name
        if 'sources' in row:
            check_sources(row['sources'])
    check_sources(rows['build']['artifacts'])
    paths = set(P.glob('*.py')) | set(P.glob('native/*')) | set(P.glob('native-src/*'))
    paths.update(P / 'lineage/production' / n for n in ('selection.json', 'dispatch-speed6.json', 'memory-plan.json'))
    paths.update((P / 'lineage/mini').glob('*'))
    paths.update((P / 'lineage/parent-src').glob('*'))
    paths.update(P / n for n in ('report-contract.json',))
    paths.update(P / n for n in ('lineage/append-delta.json', 'lineage/parent-device-request.json', 'tokenizer-identity.tsv',
                                 'launch-environment.json', 'placements.json'))
    paths.update(LOCAL / n for n in ('shared_oracle.py', 'oracle-binding.json', 'storage.py', 'kernel_guard.hpp', 'chain-registration.json',
                                     'packet56_submission.py', 'selection-template.json', 'bundle_selection.py', 'kd_reference.py',
                                     'kd_projection_replay.py', 'receipt_replay.py', 'build_engine.py', 'drain_gate.py', 'test_drain_fix.py',
                                     'immutable-binaries.json', 'copy_packet184.py', 'lineage/packet184-copy.json',
                                     'lineage/packet184-copy-amendments.json', 'lineage/checkpoint-delta.patch', 'lineage/harness-delta.patch'))
    for folder in ('submission-vendor', 'submission-templates', 'timing-fixture'):
        paths.update(f for f in (LOCAL / 'lineage-inputs' / folder).glob('*') if f.is_file())
    for folder in (LOCAL / 'native-base', LOCAL / 'lineage-inputs/vendor/repo'):
        paths.update(f for f in folder.rglob('*') if f.is_file() and not f.is_symlink() and 'build' not in f.relative_to(folder).parts)
    paths.update((LOCAL / 'proposals').glob('*.txt'))   # the proposal mirror (package_rows.py stages it before sealing)
    paths.update(P / 'evidence' / (n + '.json') for n in GATES)
    sources = {str(f.relative_to(ROOT)): sha(f) for f in sorted(p for p in paths if p.is_file())}
    for gate in rows.values():
        sources.update(gate.get('sources', {}))
    sources.update(rows['build']['sources'])
    sources.update(rows['build']['artifacts'])
    subprocess.run([sys.executable, '-B', str(LOCAL / 'shared_oracle.py'), '--require-complete'], stdin=subprocess.DEVNULL,
                   stdout=subprocess.DEVNULL, check=True, timeout=180)
    row = dict(schema='packet184.cpu-composition.v1', passed=True, device_executed=False, device_quality_pending=True,
               checkpoint_qualification_pending=True, label=LABEL, contract=CONTRACT, arithmetic='iq3-p49-split32-v1',
               sources=sources, variants=['production'], gates=list(GATES),
               binary_sha256=sha(P / 'build/device/own-rt-iq3'), gnu_host_sha256=sha(P / 'build/gnu-host/own-rt-iq3'),
               tool_sha256=sha(P / 'build/tool/own-rt-ckpt-tool'))
    save(P / 'cpu-seal.json', row)
    save(P / 'lineage/production/screen-seal.json', row)
    save(P / 'placement-validation/wrapper-seal.json', row)
    return verify()


def verify():
    row = json.loads((P / 'cpu-seal.json').read_text())
    assert row['passed'] and row['device_executed'] is False and row.get('schema') == 'packet184.cpu-composition.v1'
    check_sources(row['sources'])
    for mode in row['variants']:
        assert json.loads((P / 'lineage' / mode / 'screen-seal.json').read_text()) == row
    assert json.loads((P / 'placement-validation/wrapper-seal.json').read_text()) == row
    return row


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--seal', action='store_true')
    a = ap.parse_args()
    seal() if a.seal else verify()
    print('packet184 CPU source/build seal PASS; device quality and checkpoint qualification pending')

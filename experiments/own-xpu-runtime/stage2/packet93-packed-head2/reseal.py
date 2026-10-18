"""CPU-only, one-time provenance refresh after packet84's submission restoration.

The old seal/receipt closure is retained in pre-reseal-6470679d0.tar.gz.
Only noncompiled micro runner/gate/test hashes may change in the micro receipt.
All native build inputs and binaries are checked without invoking a compiler.
"""
import json
import subprocess
import sys
from build_engine import P, ROOT, sha, save, limits
from screen_jobs import VIEWS
from common import require, verify_map


def main():
    limits()
    submission = ROOT / 'experiments/own-xpu-runtime/stage2/packet84-record-bundle/packet56_submission.py'
    require(sha(submission) == 'bc7480f11c2e62c30147f4042e254977f9f1dd3be6cb936aa8e090340eee5347', 'restored submission identity required')
    archive = P / 'evidence/pre-reseal-6470679d0.tar.gz'
    require(archive.is_file(), 'original closure archive required')
    verify_map(P, json.loads((P / 'evidence/micro-B-original-hashes.json').read_text()))
    build = json.loads((P / 'build-device-receipt.json').read_text())
    verify_map(ROOT, build['sources'])
    verify_map(P, build['artifacts'])
    micro_path = P / 'evidence/microbench-build.json'
    micro = json.loads(micro_path.read_text())
    require('provenance_refresh' not in micro, 'already refreshed; do not reseal again')
    allowed = {str((P / name).relative_to(ROOT)) for name in
               ('run_micro.py', 'micro_gate.py', 'test_micro_runner.py', 'test_micro_gate.py')}
    changes = {}
    for name, previous in micro['sources'].items():
        current = sha(ROOT / name)
        if current != previous:
            require(name in allowed, 'compiled or unapproved input changed: ' + name)
            changes[name] = dict(before=previous, after=current)
    verify_map(P, micro['artifacts'])
    require(changes, 'expected noncompiled Python changes')
    provenance = dict(schema='packet93.provenance-refresh.v1', device_executed=False,
        previous_closure=str(archive.relative_to(P)), previous_closure_sha256=sha(archive),
        restored_submission_sha256=sha(submission), native_rebuilt=False,
        engine_build_receipt_sha256=sha(P / 'build-device-receipt.json'),
        engine_artifacts=build['artifacts'], micro_artifacts=micro['artifacts'],
        previous_micro_build_receipt_sha256=sha(micro_path), noncompiled_changes=changes,
        reason='Submission Python is a consumer-test dependency, not a native compiler input. '
               'Only Python output routing/gate/tests changed; compiler inputs and binaries verified unchanged. '
               'Original micro-B remains historical; micro-B2 must run against the refreshed seals.')
    save(P / 'evidence/reseal-provenance.json', provenance)
    for name, row in changes.items():
        micro['sources'][name] = row['after']
    micro['provenance_refresh'] = provenance
    save(micro_path, micro)
    subprocess.run([sys.executable, '-B', str(P / 'python_gate.py')],
                   stdin=subprocess.DEVNULL, check=True)
    # Verify the old native artifacts and fixture files before replacing seals.
    for name in VIEWS:
        view = P / 'compat/packet64-record-bundle/selections' / name
        old = json.loads((view / 'screen-seal.json').read_text())
        for key in ('artifacts', 'fixture_files', 'gates'):
            verify_map(view, old[key])
        require(old['artifacts'] == build['artifacts'], 'native artifact identity changed')
    for name in VIEWS:
        (P / 'compat/packet64-record-bundle/selections' / name / 'screen-seal.json').unlink()
    import seal
    seal.main()
    verify_map(P, json.loads((P / 'evidence/micro-B-original-hashes.json').read_text()))
    print('resealed against restored packet84; all binaries and original micro-B unchanged')


if __name__ == '__main__':
    main()

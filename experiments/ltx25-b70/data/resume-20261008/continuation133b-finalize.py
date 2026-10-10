#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Produce the 133b CPU build receipt only after every recorded gate passes."""
import ast
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
LANE = HERE.parents[1]
REPO = LANE.parents[1]
OUT = HERE / 'continuation133b-tests'
AUTHOR = LANE / 'recovery/20261010-continuation133b-stream'
PARENT_SHA = 'a1f0fb23dbba64ea2530b58fb4787f736a602746a1be72a040688bf0eaf74bd6'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((OUT / name).read_text())


def unittest_result(name, expected):
    path = OUT / name
    raw = path.read_text()
    rows = re.findall(r'Ran (\d+) tests in ([0-9.]+)s', raw)
    assert len(rows) == 1 and raw.rstrip().endswith('OK'), name
    assert int(rows[0][0]) == expected, (name, rows)
    return dict(count=expected, passed=expected, failures=0, errors=0,
                elapsed_seconds=float(rows[0][1]), log=str(path.relative_to(REPO)), sha256=sha(path))


def main():
    seal = read('seal.json')
    packet = Path(seal['packet'])
    assert sha(packet / 'manifest.json') == seal['manifest_sha256']
    plan = json.loads((packet / 'resolution/stream-plan.json').read_text())
    assert plan['plan']['basis']['parent_manifest_sha256'] == PARENT_SHA
    parent = packet.with_name('prepared-continuation-stream-133')
    assert sha(parent / 'manifest.json') == PARENT_SHA
    recovery = unittest_result('recovery-final.log', 1058)
    sealed_import = unittest_result('sealed-import.log', 6)
    assert seal['sealed_import']['passed'] and seal['sealed_import']['checks'] == 2
    clients = read('client-progress.json')
    expected = ['112', '113', '114', '115', '116', '116b', '117', '118', '118b']
    for number in ['119', '120', '121', '122', '123', '123b', *map(str, range(124, 134)), '133b']:
        expected.extend([number, number + '_integration'])
    assert len(clients) == 43 and [r['suite'] for r in clients] == expected
    for row in clients:
        assert row['returncode'] == 0 and row['passed'] == row['count'] > 0, row
        assert sha(OUT / row['log']) == row['sha256']
    pins = read('client-pins.json')
    assert pins['all_pins_passed'] and pins['assertions'] == 32 and pins['packets'] == 16
    assert pins['packet133b_inner_plan_sha256'] == plan['plan_sha256']
    assert pins['packet133b_manifest_sha256'] == seal['manifest_sha256']
    assert pins['client_sha256'] == sha(LANE / 'stream/ltx_continuation_client.py')
    runtime = read('candidate-runtime-summary-final.json')
    assert runtime['passed'] and len(runtime['cases']) == 3 and runtime['source_unchanged_during_cases']
    assert runtime['source_sha256'] == {str(p.relative_to(REPO)): sha(p) for p in sorted(AUTHOR.glob('*.py'))}
    assert runtime['preflight']['passed'] and runtime['preflight']['tests'] == 10
    assert len(runtime['off_on_exact_cpu_outputs']) == 22
    assert all(r['names_equal'] and r['decoded_tensors_equal'] and r['last_frame_equal'] for r in runtime['off_on_exact_cpu_outputs'])
    for row in [*runtime['cases'], runtime['preflight']]:
        assert sha(REPO / row['log']) == row['sha256']
    verification = read('recursive-verification.json')
    assert verification['status'] == 'source-closure-verified'
    assert verification['manifest_sha256'] == seal['manifest_sha256']
    cleanup = read('cleanup.json')
    assert cleanup['passed'] and not (OUT / 'scratch').exists()
    assert read('repository-checks.json')['status'] == 'passed'
    for root in (AUTHOR, packet):
        assert not list(root.rglob('__pycache__')) + list(root.rglob('*.pyc'))
    for rel in ('text_residency133.py', 'text-oracle133.json'):
        assert (packet / 'launch' / rel).read_bytes() == (parent / 'resolution/components' / rel).read_bytes()
    source_paths = sorted(p for p in AUTHOR.iterdir() if p.is_file())
    source_paths += sorted(HERE.glob('continuation133b-*.py'))
    source_paths += [LANE / 'stream/ltx_continuation_client.py', LANE / 'stream/start-client-133b.sh',
                    LANE / 'stream/tests/run_tests_133b.py', LANE / 'stream/tests/run_tests_133b_integration.py',
                    LANE / 'notes/2026-10-10-continuation133b-rebuild.md']
    for p in source_paths:
        if p.suffix == '.py':
            ast.parse(p.read_bytes(), filename=str(p))
    receipt = dict(schema='ltx.stream133b.cpu-build.v1', status='sealed-cpu-validated-native-unqualified',
        packet=str(packet), parent_packet=133, parent_manifest_sha256=PARENT_SHA,
        manifest_sha256=seal['manifest_sha256'], inner_plan_sha256=plan['plan_sha256'],
        input_inventory_sha256=seal['input_inventory_sha256'],
        root_cause='Bare text_residency133 import during launcher environment validation; helper existed in components and source/scripts, neither on initial launch sys.path. Author-tree tests masked the defect.',
        repair='Additional byte-identical launch/text_residency133.py and adjacent pinned text-oracle133.json; reidentified133b namespace and inner plan; unchanged arithmetic, numerical contracts, qualification ids and latch names.',
        development=dict(recovery_count=1058, recovery_passed=1054, recovery_fixture_failures=4,
            recovery_log='recovery-development.log', assembly_fixture_failures=1,
            assembly_log='assembly-development.log', unresolved_failures=0),
        recovery=recovery, sealed_import=dict(**sealed_import, included_in_recovery=True, preseal=seal['sealed_import']),
        client=dict(suite_count=len(clients), passed=sum(r['passed'] for r in clients),
                    count=sum(r['count'] for r in clients), suites=clients, pins=pins),
        runtime=runtime, preflight=runtime['preflight'], recursive_verification=verification,
        cleanup=cleanup, repository_checks=read('repository-checks.json'),
        safety=dict(cpu_only=True, nice=19, OMP_NUM_THREADS=2, MKL_NUM_THREADS=2,
            python='/home/steve/.venvs/ltx25-baseline/bin/python -B', GPU_operations=0,
            model_requests=0, launches=0, launcher_check_only_calls=0, systemd_operations=0,
            live_port_operations=0, device_opens=0, process_signals=0, host_setting_changes=0,
            existing_run_writes=0, ltx_stream_writes=0),
        native_qualification=False, measured_speed_or_memory=False,
        source_files={str(p.relative_to(REPO)): sha(p) for p in source_paths},
        evidence_files={str(p.relative_to(REPO)): sha(p) for p in OUT.iterdir() if p.is_file()})
    (HERE / 'continuation133b-build.json').write_text(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False)+'\n')
    print(json.dumps(dict(manifest_sha256=receipt['manifest_sha256'], inner_plan_sha256=receipt['inner_plan_sha256'],
                         recovery=recovery['count'], sealed_import=sealed_import['count'], client=receipt['client']['count'])))


if __name__ == '__main__':
    main()

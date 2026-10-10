#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Assemble the CPU-only build receipt after all final gates pass."""
import ast
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
LANE = HERE.parents[1]
REPO = LANE.parents[1]
OUT = HERE / 'continuation133-tests'
AUTHOR = LANE / 'recovery/20261010-continuation133-stream'
PARENT = '67ec59a5b0c5131d0b129e4c0b9187386c29c0395ac225dc28422516684991ad'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((OUT / name).read_text())


def main():
    seal = read('seal.json')
    packet = Path(seal['packet'])
    assert sha(packet / 'manifest.json') == seal['manifest_sha256']
    plan = json.loads((packet / 'resolution/stream-plan.json').read_text())
    assert plan['plan']['basis']['parent_manifest_sha256'] == PARENT
    recovery_path = OUT / 'recovery-final.log'
    raw = recovery_path.read_text()
    matches = re.findall(r'Ran (\d+) tests in ([0-9.]+)s', raw)
    assert len(matches) == 1 and raw.rstrip().endswith('OK'), 'Full recovery suite must pass'
    recovery = dict(passed=int(matches[0][0]), count=int(matches[0][0]),
                    elapsed_seconds=float(matches[0][1]), log=str(recovery_path.relative_to(REPO)),
                    sha256=sha(recovery_path), failures=0, errors=0)
    assert recovery['count'] == 1052, 'Expected complete packet133 recovery suite'
    clients = read('client-progress.json')
    assert len(clients) == 41
    expected_suites = ['112', '113', '114', '115', '116', '116b', '117', '118', '118b']
    for number in ['119', '120', '121', '122', '123', '123b', *map(str, range(124, 134))]:
        expected_suites.extend([number, number + '_integration'])
    assert [r['suite'] for r in clients] == expected_suites
    for row in clients:
        assert row['returncode'] == 0 and row['count'] > 0 and row['passed'] == row['count'], row
        assert sha(OUT / row['log']) == row['sha256']
    runtime = read('candidate-runtime-summary-final.json')
    assert runtime['passed'] and len(runtime['cases']) == 3 and all(r['passed'] for r in runtime['cases'])
    assert runtime['source_unchanged_during_cases']
    assert runtime['source_sha256'] == {
        str(p.relative_to(REPO)): sha(p) for p in sorted(AUTHOR.glob('*.py'))}
    for row in [*runtime['cases'], runtime['preflight']]:
        assert sha(REPO / row['log']) == row['sha256']
    assert runtime['preflight']['passed'] and runtime['preflight']['tests'] == 10
    assert len(runtime['off_on_exact_cpu_outputs']) == 22
    assert all(r['names_equal'] and r['decoded_tensors_equal'] and r['last_frame_equal']
               for r in runtime['off_on_exact_cpu_outputs'])
    verification = read('recursive-verification.json')
    assert verification['status'] == 'source-closure-verified'
    assert verification['manifest_sha256'] == seal['manifest_sha256']
    assert verification['plan_sha256'] == plan['plan_sha256']
    pins = read('client-pins.json')
    assert pins['all_pins_passed'] and pins['packet133_inner_plan_sha256'] == plan['plan_sha256']
    assert pins['packet133_manifest_sha256'] == seal['manifest_sha256']
    assert pins['packets'] == 15 and pins['assertions'] == 30
    assert pins['client_sha256'] == sha(LANE / 'stream/ltx_continuation_client.py')
    cleanup = read('cleanup.json')
    assert cleanup['passed'] and not (OUT / 'scratch').exists()
    for root in (AUTHOR, packet):
        assert not list(root.rglob('__pycache__')) + list(root.rglob('*.pyc'))
    sources = sorted(p for p in AUTHOR.iterdir() if p.is_file())
    sources += sorted(HERE.glob('continuation133-*.py'))
    sources += [HERE / 'continuation133-memory-analysis.json', HERE / 'continuation133-text-oracle.json',
                LANE / 'stream/ltx_continuation_client.py', LANE / 'stream/start-client-133.sh',
                LANE / 'stream/tests/run_tests_133.py', LANE / 'stream/tests/run_tests_133_integration.py',
                LANE / 'stream/tests/run_tests_132.py',
                LANE / 'notes/2026-10-10-continuation133-stream-design.md',
                LANE / 'notes/2026-10-10-continuation133-memory-evidence.md']
    for path in sources:
        if path.suffix == '.py':
            ast.parse(path.read_bytes(), filename=str(path))
    doc = dict(schema='ltx.stream133.cpu-build.v1', status='sealed-cpu-validated-native-unqualified',
        packet=str(packet), parent_packet=132, parent_manifest_sha256=PARENT,
        manifest_sha256=seal['manifest_sha256'], inner_plan_sha256=plan['plan_sha256'],
        input_inventory_sha256=seal['input_inventory_sha256'], recovery=recovery,
        client=dict(suite_count=len(clients), passed=sum(r['passed'] for r in clients),
                    count=sum(r['count'] for r in clients), suites=clients, pins=pins),
        runtime=runtime, preflight=runtime['preflight'], recursive_verification=verification,
        cleanup=cleanup, repository_checks=read('repository-checks.json'),
        memory_evidence_sha256=sha(HERE / 'continuation133-memory-analysis.json'),
        text_oracle_sha256=sha(HERE / 'continuation133-text-oracle.json'),
        selected_option=dict(text_residency='split36', frames=145, display_device='xpu:3',
            cone_graph_memory='text-shift', capture_reserve_gib=5, floor_gib=9, screening_gib=0.75,
            weights_transferred_gib=5.076040290296078, per_cut_weight_reload_seconds=0,
            actual_physical_release_bytes=None, native_exactness_qualified=False, frames169_admitted=False),
        forecast=dict(period_seconds=[5.25, 5.35], new_video_seconds=6,
            seconds_per_second=[5.25 / 6, 5.35 / 6], measured=False,
            unknown_deltas=['text placement', 'native-card3 eager-display scheduling and contention']),
        safety=dict(cpu_only=True, nice=19, OMP_NUM_THREADS=2, MKL_NUM_THREADS=2,
            python='/home/steve/.venvs/ltx25-baseline/bin/python -B', GPU_operations=0,
            model_requests=0, launches=0, systemd_operations=0, live_port_operations=0,
            device_opens=0, process_signals=0, host_setting_changes=0,
            existing_run_writes=0, ltx_stream_writes=0),
        open_items=['Native parent text equality across probe and all scene cuts.',
                    'Actual physical memory across startup, capture, cut and reuse phases.',
                    'Repeated sustained period and cut-specific timing for the selected schedule.',
                    '169-frame memory/quality/cadence; host reload graph-lifetime design; single-card text pool peaks.'],
        source_files={str(p.relative_to(REPO)): sha(p) for p in sources},
        evidence_files={str(p.relative_to(REPO)): sha(p) for p in OUT.iterdir() if p.is_file()})
    (HERE / 'continuation133-build.json').write_text(json.dumps(doc, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'manifest_sha256': doc['manifest_sha256'], 'inner_plan_sha256': doc['inner_plan_sha256'],
                      'recovery': recovery['count'], 'client': doc['client']['count'],
                      'preflight': doc['preflight']['tests']}))


if __name__ == '__main__':
    main()

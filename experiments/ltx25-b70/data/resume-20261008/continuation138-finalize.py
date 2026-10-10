#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Seal completed CPU validation evidence into the138 build receipt."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys

assert sys.executable == '/home/steve/.venvs/ltx25-baseline/bin/python'
assert os.getpriority(os.PRIO_PROCESS, 0) == 19
assert os.environ.get('OMP_NUM_THREADS') == '2'
LANE = Path(__file__).resolve().parents[2]
REPO = LANE.parents[1]
AUTHOR = LANE / 'recovery/20261010-continuation138-stream'
OUT = Path(__file__).resolve().parent / 'continuation138-tests'


def read(name):
    return json.loads((OUT / name).read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unit_result(name):
    text = (OUT / name).read_text()
    rows = re.findall(r'Ran (\d+) tests in ([0-9.]+)s\n\nOK\s*$', text)
    assert rows, name
    count, seconds = rows[-1]
    return dict(passed=True, tests=int(count), seconds=float(seconds), log=name,
                sha256=sha(OUT / name))


seal = read('seal.json')
assembly = read('assembly-final.json')
verify = read('recursive-verification.json')
runtime = read('candidate-runtime-summary-final.json')
clients = read('client-progress.json')
packet = Path(seal['packet'])
manifest = json.loads((packet / 'manifest.json').read_bytes())
plan = json.loads((packet / 'resolution/stream-plan.json').read_bytes())
assert sha(packet / 'manifest.json') == seal['manifest_sha256'] == verify['manifest_sha256']
assert plan['plan_sha256'] == verify['plan_sha256']
assert runtime['passed'] and runtime['source_unchanged_during_cases']
assert len(runtime['cases']) == 3 and len(runtime['off_on_exact_cpu_outputs']) == 22
assert len(runtime['production_parent_bulk_exact_cpu_outputs']) == 11
assert len(clients) == 51 and all(r['returncode'] == 0 and r['count'] == r['passed'] > 0 for r in clients)
assert not (OUT / 'scratch').exists(), 'Owned scratch must be removed after every child exits'
for root in (AUTHOR, packet):
    assert not list(root.rglob('__pycache__')) + list(root.rglob('*.pyc'))
recovery = unit_result('recovery-final.log')
sealed = unit_result('sealed-import-final.log')
prefetch = unit_result('prefetch-final.log')
assert prefetch['tests'] == 26
measurement_path = Path(__file__).with_name('continuation138-pacing-tests-final.log')
measurement_text = measurement_path.read_text()
assert re.search(r'Ran 14 tests in [0-9.]+s\n\nOK\s*$', measurement_text)
assert recovery['tests'] == 1138 and sealed['tests'] == 9
assert seal['sealed_import']['helper_import_count'] == 71
client_log = (OUT / 'client-137-final.log').read_text()
pins = len(re.findall(r'^PASS packet.* all-pins ', client_log, re.M))
assert pins == 40
paths = [p for p in AUTHOR.iterdir() if p.is_file()] + [
    LANE / 'stream/ltx_continuation_client.py', LANE / 'stream/start-client-138.sh',
    LANE / 'stream/tests/run_tests_138.py', LANE / 'stream/tests/run_tests_138_integration.py',
    REPO/'scripts/analyze-ltx-continuation-ledger.py',
    REPO/'scripts/tests/test_ltx_continuation_pacing.py',
    Path(__file__).with_name('continuation138-pin-client.py'),
    Path(__file__).with_name('continuation138-prefetch-memory-analysis.py'),
    Path(__file__), Path(__file__).with_name('continuation138-runtime-validation.py'),
    Path(__file__).with_name('continuation138-verify-packet.py')]
result = dict(schema='ltx.continuation138.build.v1',
    status='sealed-cpu-validated-native-unqualified', parent_packet='137',
    parent_manifest_sha256='18c80d25c2ba4992d8c6dff24779737a056a325389a84486d24da674ef7e463e',
    packet=str(packet), manifest_sha256=seal['manifest_sha256'], inner_plan_sha256=plan['plan_sha256'],
    input_inventory_sha256=assembly['input_inventory_sha256'], recursive_verification=verify,
    changed_paths=assembly['changed_files'], storage_admission=seal['storage_admission'],
    recovery=recovery, sealed_import=dict(**sealed, helper_copies=71,
        component_copies=38, runtime_copies=33, preseal_probes=3),
    scheduled_prefetch_cpu=dict(**prefetch, scope='Actual Runtime producer/consumer methods with CPU fakes; native graph execution and speed remain unqualified'),
    pacing_measurement=dict(passed=True, tests=14, log=str(measurement_path.relative_to(REPO)), sha256=sha(measurement_path)),
    client=dict(passed=True, suites=len(clients), tests=sum(r['count'] for r in clients),
        all_pins_assertions=pins, all_pins_packets=pins//2, rows=clients),
    preflight=runtime['preflight'], cpu_runtime=dict(passed=True, cases=3, scope='Inherited138 off-prefetch Runtime regression only; scheduled producer/consumer coverage is separate',
        reference_output_comparisons=22,
        production_parent_bulk_comparisons=len(runtime.get('production_parent_bulk_exact_cpu_outputs', [])),
        summary='candidate-runtime-summary-final.json',
        sha256=sha(OUT / 'candidate-runtime-summary-final.json')),
    repository_checks=read('repository-checks.json'),
    preparation_corrections=read('recovery-fixture-correction.json'),
    prediction=dict(text_encode_saving_per_cut_seconds=0.378417,
        text_encode_saving_per_chunk_average_seconds=0.09460425,
        native_speed_measured=False, native_output_qualified=False,
        scope='Scheduled text encode overlapped after predecessor decode work; saving is a gross budget, not measured native speed'),
    host_constraints=dict(cpu_only=True, nice=19, omp_num_threads=2, model_requests=0,
        launcher_executed=False, check_only_executed=False, systemd_operations=0,
        device_opens=0, existing_run_writes=0, ltx_stream_writes=0,
        cpu_test_interrupts='none',
        scratch_removed=True),
    source_sha256={str(p.relative_to(REPO)): sha(p) for p in sorted(paths)},
    evidence_sha256={str(p.relative_to(OUT)): sha(p) for p in sorted(OUT.rglob('*'))
                    if p.is_file() and p.suffix in ('.log', '.json', '.py')})
target = Path(__file__).with_name('continuation138-build.json')
with target.open('x') as handle:
    json.dump(result, handle, indent=2, sort_keys=True)
    handle.write('\n')
print(json.dumps({k: result[k] for k in ('status', 'packet', 'manifest_sha256', 'inner_plan_sha256')}, indent=2))

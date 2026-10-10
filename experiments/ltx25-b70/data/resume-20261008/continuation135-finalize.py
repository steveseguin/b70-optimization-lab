#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Bind completed CPU-only checks and the immutable packet to a build receipt."""
import hashlib
import json
from pathlib import Path
import re

LANE = Path(__file__).resolve().parents[2]
REPO = LANE.parents[1]
AUTHOR = LANE / 'recovery/20261010-continuation135-stream'
OUT = Path(__file__).resolve().parent / 'continuation135-tests'


def read(name):
    return json.loads((OUT / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unit_result(name):
    text = (OUT / name).read_text()
    matches = re.findall(r'Ran (\d+) tests in ([0-9.]+)s\n\nOK\s*$', text)
    assert matches, name
    count, seconds = matches[-1]
    return dict(passed=True, tests=int(count), seconds=float(seconds), log=name,
                sha256=sha(OUT / name))


seal = read('seal.json')
assembly = read('assembly-final.json')
verify = read('recursive-verification.json')
runtime = read('candidate-runtime-summary-final.json')
clients = read('client-progress.json')
isolation = read('client-commit-isolation.json')
assert sha(OUT / 'client135-commit-source.py') == isolation['commit_source_sha256']
assert sha(OUT / 'client135-workspace-tested.py') == isolation['workspace_source_sha256']
for name, count in [('client135-isolated-commit-contract.log', 113),
                    ('client135-isolated-commit-integration.log', 208)]:
    assert f'{count}/{count} passed' in (OUT / name).read_text()
packet = Path(seal['packet'])
plan = json.loads((packet / 'resolution/stream-plan.json').read_text())
manifest = json.loads((packet / 'manifest.json').read_text())
assert sha(packet / 'manifest.json') == seal['manifest_sha256'] == verify['manifest_sha256']
assert plan['plan_sha256'] == verify['plan_sha256']
assert runtime['passed'] and runtime['source_unchanged_during_cases']
assert len(runtime['cases']) == 3 and len(runtime['off_on_exact_cpu_outputs']) == 22
assert len(clients) >= 45 and all(r['returncode'] == 0 and r['count'] == r['passed'] > 0 for r in clients)
assert not (OUT / 'scratch').exists(), 'Remove only this task-owned scratch after all children finish'
for root in (AUTHOR, packet):
    assert not list(root.rglob('__pycache__')) + list(root.rglob('*.pyc'))
recovery = unit_result('recovery-clean-final.log')
sealed_import = unit_result('sealed-import-final.log')
assert recovery['tests'] == 1076 and sealed_import['tests'] == 9
assert seal['sealed_import']['helper_import_count'] == 67
client135_log = (OUT / 'client-135-final.log').read_text()
pins = len(re.findall(r'^PASS packet.* all-pins ', client135_log, re.M))
assert pins >= 34 and pins % 2 == 0
paths = list(AUTHOR.glob('*')) + [
    LANE / 'stream/ltx_continuation_client.py', LANE / 'stream/start-client-135.sh',
    LANE / 'stream/tests/run_tests_135.py', LANE / 'stream/tests/run_tests_135_integration.py',
    Path(__file__), Path(__file__).with_name('continuation135-runtime-validation.py'),
    Path(__file__).with_name('continuation135-verify-packet.py')]
result = dict(schema='ltx.continuation135.build.v1', status='sealed-cpu-validated-native-unqualified',
    parent_packet='133b', parent_manifest_sha256='ed908a9031a937801d17264edacfe0807bea543badc412a32eb6118daa214fd3',
    packet=str(packet), manifest_sha256=seal['manifest_sha256'], inner_plan_sha256=plan['plan_sha256'],
    input_inventory_sha256=assembly['input_inventory_sha256'], recursive_verification=verify,
    changed_paths=assembly['changed_files'], storage_admission=seal['storage_admission'],
    recovery=recovery, sealed_import=dict(**sealed_import, helper_copies=67,
        component_copies=36, runtime_copies=31, preseal_probes=3),
    client=dict(passed=True, suites=len(clients), tests=sum(r['count'] for r in clients),
        all_pins_assertions=pins, all_pins_packets=pins//2, rows=clients,
        commit_isolation=isolation, isolated_commit_contract_checks=113,
        isolated_commit_integration_checks=208, isolated_commit_all_pins_assertions=34,
        source_snapshots=['client135-workspace-tested.py', 'client135-commit-source.py']),
    preflight=runtime['preflight'], cpu_runtime=dict(passed=True, cases=3,
        output_comparisons=22, summary='candidate-runtime-summary-final.json',
        sha256=sha(OUT / 'candidate-runtime-summary-final.json')),
    incident=dict(offending_path=None, linker=None, historical_link_count=None,
        attribution='Not recoverable: parent halt omitted path/inode/nlink; retained files all nlink1. '
                    'Old !=1 guard also rejects a reproduced zero-link unlink race; cause remains unknown.',
        evidence='storage-incident-audit.json', sha256=sha(OUT / 'storage-incident-audit.json')),
    host_constraints=dict(cpu_only=True, nice=19, omp_num_threads=2, model_requests=0,
        launcher_executed=False, check_only_executed=False, systemd_operations=0,
        device_opens=0, existing_run_writes=0, ltx_stream_writes=0, scratch_removed=True),
    source_sha256={str(p.relative_to(REPO)): sha(p) for p in sorted(paths) if p.is_file()},
    evidence_sha256={p.name: sha(p) for p in sorted(OUT.iterdir()) if p.is_file()
                    and p.suffix in ('.log', '.json', '.py')})
# The shared worktree contains another worker's unfinished134 edits. Bind the
# exact separately tested135-only source that this commit adds to Git instead.
result['source_sha256'][str((LANE / 'stream/ltx_continuation_client.py').relative_to(REPO))] = isolation['commit_source_sha256']
target = Path(__file__).with_name('continuation135-build.json')
with target.open('x') as stream:
    json.dump(result, stream, indent=2, sort_keys=True)
    stream.write('\n')
print(json.dumps({k: result[k] for k in ('packet', 'manifest_sha256', 'inner_plan_sha256', 'status')}, indent=2))

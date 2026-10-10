#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Assemble final CPU evidence receipt after all required checks pass."""
import ast
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
LANE = HERE.parents[1]
REPO = LANE.parents[1]
OUT = HERE / 'continuation130-tests'
AUTHOR = LANE / 'recovery/20261010-continuation130-stream'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
def read(name): return json.loads((OUT/name).read_text())
seal = read('seal.json')
packet = Path(seal['packet'])
manifest = json.loads((packet/'manifest.json').read_text())
plan = json.loads((packet/'resolution/stream-plan.json').read_text())
assert sha(packet/'manifest.json') == seal['manifest_sha256']
log=OUT/'recovery-final.log'
raw=log.read_text()
m=re.findall(r'Ran (\d+) tests in ([0-9.]+)s',raw)
assert len(m)==1 and raw.rstrip().endswith('OK'), 'Final complete recovery suite must pass'
assert int(m[0][0])==842, 'Unexpected recovery suite count'
recovery=dict(passed=int(m[0][0]), count=int(m[0][0]), elapsed_seconds=float(m[0][1]),
              failures=0, errors=0, log=str(log.relative_to(REPO)), sha256=sha(log),
              command='nice -n 19 env OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 /home/steve/.venvs/ltx25-baseline/bin/python -B '+str(AUTHOR/'run_tests_130.py'))
client=read('client-validation.json')
assert client['passed']==client['count']==4419 and client['suite_count']==35 and client['all_pins']==24
assert client['manifest_sha256']==seal['manifest_sha256'] and client['inner_plan_sha256']==plan['plan_sha256']
assert client['final_client_sha256']==sha(LANE/'stream/ltx_continuation_client.py')
assert not client['scratch_remaining'] and not client['violations']
assert all(not Path(p).exists() for p in client['scratch_roots_created'])
for suite in client['suites']:
    assert suite['returncode']==0 and suite['passed']==suite['count']
    assert sha(LANE/suite['source'])==suite['source_sha256']
    assert sha(LANE/suite['log'])==suite['log_sha256']
preflight_log=OUT/'preflight10.log'
preflight_raw=preflight_log.read_text()
assert re.search(r'Ran 10 tests in ', preflight_raw) and preflight_raw.rstrip().endswith('OK')
preflight=dict(count=10, passed=10, log=str(preflight_log.relative_to(REPO)), sha256=sha(preflight_log))
runtime=read('candidate-runtime-summary.json')
assert runtime['passed'] and len(runtime['cases'])==2
assert all(r['passed'] for r in runtime['cases'])
verify=read('recursive-verification.json')
assert verify['status']=='source-closure-verified' and verify['recursive_parent_verification']
assert verify['manifest_sha256']==seal['manifest_sha256'] and verify['plan_sha256']==plan['plan_sha256']
assert verify['bound_files']==2219 and verify['physical_files']==2221 and verify['author_components_match']
static=read('static-validation.json')
assert static['passed'] and static['python_cache_count']==0
links=read('doc-links.json'); focused_links=read('doc-links-focused.json')
assert links['broken_total']==focused_links['broken_total']==0
assert '6148 repo-relative paths in 51 manifests; 0 missing' in (OUT/'manifest-paths.log').read_text()
assert '318 literal file pins: 87 match, 231 drifted, 0 target absent' in (OUT/'pinned-hashes.log').read_text()
repository_checks=dict(doc_links=links, focused_doc_links=focused_links,
    manifest_paths=dict(checked=6148, manifests=51, missing=0, exit_code=0),
    literal_pins=dict(checked=318, match=87, drifted=231, absent=0, exit_code=1,
        scope='Same pre-existing Flash-Next frozen-client drifts recorded by129; no130 literal pin drift'))
census=read('residency-verification.json')
assert census['passed'] and census['source_count']==36 and census['header_count']==5
cache_paths=list(packet.rglob('__pycache__'))+list(packet.rglob('*.pyc'))+list(AUTHOR.rglob('__pycache__'))+list(AUTHOR.rglob('*.pyc'))
assert not cache_paths, cache_paths
assert not (OUT/'scratch').exists(), 'Own recovery scratch must be removed'
source_paths=list(AUTHOR.glob('*'))+[LANE/'stream/ltx_continuation_client.py', LANE/'stream/start-client-130.sh']
source_paths += list((LANE/'stream/tests').glob('*130*.py'))
source_paths += [HERE/'continuation130-residency.json', HERE/'continuation130-verify-residency.py', HERE/'continuation130-verify-packet.py', HERE/'continuation130-runtime-validation.py', Path(__file__).resolve()]
source_paths += [LANE/'notes/2026-10-10-xpu2-residency-169.md', LANE/'notes/2026-10-10-continuation130-stream-design.md']
source_hashes={str(p.relative_to(REPO)):sha(p) for p in source_paths if p.is_file()}
for p in source_paths:
    if p.suffix=='.py': ast.parse(p.read_text(),filename=str(p))
receipt=dict(schema='ltx.continuation130.build.v1', status='sealed-cpu-validated-not-native-qualified',
 packet=str(packet), parent_packet=str(packet.with_name('prepared-continuation-stream-129')),
 parent_manifest_sha256='42e6a7452e11873f33c78a953105754605121f2a96dfca1954b1d55966a4886c',
 manifest_sha256=seal['manifest_sha256'], plan_sha256=plan['plan_sha256'], plan_pin_is_inner=True,
 storage_admission=seal['storage_admission'], recursive_verification=verify,
 input_inventory_sha256=seal['input_inventory_sha256'],
 build_commands=['runtime_packet.py --inspect-assembly', 'runtime_packet.py --build --input-inventory-sha256 '+seal['input_inventory_sha256'], 'runtime_packet.py --verify-manifest-sha256 '+seal['manifest_sha256']],
 build_command_prefix='nice -n 19 env OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 /home/steve/.venvs/ltx25-baseline/bin/python -B '+str(AUTHOR)+'/',
 recovery=recovery, client=client, preflight=preflight, cpu_runtime=runtime, residency=census, static=static,
 repository_checks=repository_checks,
 inventory_commit='380fdfe03', model_requests=0, native_reclaim_verified_bytes=0,
 actual_saved_admission_deficit_bytes=1466712064, release_scenario_bytes=1610612736,
 reserve_bytes=6979321856, floor_bytes=2147483648, unchanged_screening_bytes=805306368,
 safety=dict(cpu_only=True, nice=19, OMP_NUM_THREADS=2, MKL_NUM_THREADS=2,
 python='/home/steve/.venvs/ltx25-baseline/bin/python -B',
 prohibited_operations_performed=False, existing_run_writes=False, ltx_stream_writes=False),
 cleanup=dict(recovery_scratch_removed=True, pycache_count=0, pyc_count=0,
 client_scratch='Owned TemporaryDirectory roots removed after cooperative fake children exit'),
 development_notes=['Development recovery run:823 tests,820 passed and3 fixture failures. Two copied parent metadata fixtures still named128; corrected to129. Copied checker fixture omitted allocator helper; corrected. Complete final recovery rerun.',
 'Added explicit on-mode allocator evidence validation after independent source review; CPU runtime rerun with final gates.'],
 unresolved=['Actual releasable GiB and allocator synchronization cost need coordinator qualification.',
 'Graph/private-pool and cache byte sub-inventory not individually separated in saved receipts.',
 'Native nine-decode/three-chain exactness, fresh text contention, reservation plateau and repeated speed remain open.'],
 source_artifacts=source_hashes,
 log_artifacts={str(p.relative_to(REPO)):sha(p) for p in OUT.iterdir() if p.is_file()})
(HERE/'continuation130-build.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:receipt[k] for k in ('status','packet','manifest_sha256','plan_sha256','recovery')},indent=2))

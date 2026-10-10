#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Finalize packet131 CPU evidence only after complete checks pass."""
import ast
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
LANE = HERE.parents[1]
REPO = LANE.parents[1]
OUT = HERE / 'continuation131-tests'
AUTHOR = LANE / 'recovery/20261010-continuation131-stream'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
def read(n): return json.loads((OUT/n).read_text())
seal = read('seal.json')
packet = Path(seal['packet'])
manifest = json.loads((packet/'manifest.json').read_text())
plan = json.loads((packet/'resolution/stream-plan.json').read_text())
assert sha(packet/'manifest.json') == seal['manifest_sha256']
assert plan['plan']['basis']['parent_manifest_sha256'] == '14aa145e6ad814eb600ceca75286742a08898ae5bb704d270dfada69420980ed'
log = OUT/'recovery-complete.log'
raw = log.read_text()
m = re.findall(r'Ran (\d+) tests in ([0-9.]+)s', raw)
assert len(m) == 1, 'Complete recovery suite must finish'
fixture_recheck = None
full_failures = 0
if not raw.rstrip().endswith('OK'):
    assert raw.rstrip().endswith('FAILED (failures=1)'), 'Unresolved recovery failures'
    assert re.findall(r'^FAIL: (.*)$', raw, re.M) == ['test_walk_mode_is_the_packet117_path_with_timing (test_runtime_flow.Flow118.test_walk_mode_is_the_packet117_path_with_timing)']
    recheck = OUT/'off-options-fixture-recheck.log'
    assert 'Ran 1 test in ' in recheck.read_text() and recheck.read_text().rstrip().endswith('OK')
    full_failures = 1
    fixture_recheck = dict(test='test_runtime_flow.Flow118.test_walk_mode_is_the_packet117_path_with_timing',
        reason='Copied exact options expectation omitted the newly bound off-mode field; no runtime source change',
        passed=1,count=1,log=str(recheck.relative_to(REPO)),sha256=sha(recheck))
recovery = dict(passed=int(m[0][0]), count=int(m[0][0]), elapsed_seconds=float(m[0][1]),
                log=str(log.relative_to(REPO)), sha256=sha(log), unresolved_failures=0, errors=0,
                full_run_passed=int(m[0][0])-full_failures, full_run_fixture_failures=full_failures,
                corrected_fixture_recheck=fixture_recheck)
client = read('client-validation.json')
assert client['passed'] == client['count'] and client['suite_count'] == 37
assert client['manifest_sha256'] == seal['manifest_sha256']
assert client['inner_plan_sha256'] == plan['plan_sha256'] and client['all_pins'] == 26
assert client['final_client_sha256'] == sha(LANE/'stream/ltx_continuation_client.py')
assert not client['scratch_remaining'] and not client['violations']
assert all(not Path(p).exists() for p in client['scratch_roots_created'])
for row in client['suites']:
    assert row['returncode'] == 0 and row['passed'] == row['count']
pre = OUT/'preflight10-final.log'
assert re.search(r'Ran 10 tests in ', pre.read_text()) and pre.read_text().rstrip().endswith('OK')
runtime = read('candidate-runtime-summary-final.json')
assert runtime['passed'] and len(runtime['cases']) == 2 and all(r['passed'] for r in runtime['cases'])
verification = read('recursive-verification.json')
assert verification['status'] == 'source-closure-verified' and verification['manifest_sha256'] == seal['manifest_sha256']
assert verification['plan_sha256'] == plan['plan_sha256'] and verification['author_components_match']
assert not list(packet.rglob('__pycache__')) + list(packet.rglob('*.pyc'))
assert not list(AUTHOR.rglob('__pycache__')) + list(AUTHOR.rglob('*.pyc'))
assert not (OUT/'scratch').exists()
assert read('doc-links.json')['broken_total'] == read('doc-links-focused.json')['broken_total'] == 0
assert '6148 repo-relative paths in 51 manifests; 0 missing' in (OUT/'manifest-paths.log').read_text()
assert '318 literal file pins: 87 match, 231 drifted, 0 target absent' in (OUT/'pinned-hashes.log').read_text()
inputs = list(AUTHOR.glob('*.py')) + list(AUTHOR.glob('*.sh')) + list(AUTHOR.glob('*.md'))
inputs += [LANE/'stream/ltx_continuation_client.py', LANE/'stream/start-client-131.sh']
inputs += list((LANE/'stream/tests').glob('*131.py')) + list((LANE/'stream/tests').glob('*131_integration.py'))
inputs += list(HERE.glob('continuation131-*.py'))
inputs += [LANE/'notes/2026-10-10-xpu3-residency-145.md', LANE/'notes/2026-10-10-continuation131-snapshot-schedule.md', LANE/'notes/2026-10-10-continuation131-stream-design.md', HERE/'continuation131-memory-analysis.json', HERE/'continuation131-snapshot-evidence.json']
for p in inputs:
    if p.suffix == '.py': ast.parse(p.read_bytes(), filename=str(p))
result = dict(schema='ltx.stream131.cpu-build.v1', status='sealed-cpu-validated-native-unqualified',
    packet=str(packet), parent_packet=130,
    parent_manifest_sha256='14aa145e6ad814eb600ceca75286742a08898ae5bb704d270dfada69420980ed',
    manifest_sha256=seal['manifest_sha256'], inner_plan_sha256=plan['plan_sha256'],
    input_inventory_sha256=seal['input_inventory_sha256'], recovery=recovery, client=client,
    preflight=dict(passed=10,count=10,log=str(pre.relative_to(REPO)),sha256=sha(pre)),
    runtime=runtime, recursive_verification=verification, cleanup=read('cleanup.json'),
    static=read('static-validation.json'),
    development=['Copied clip/parent fixtures corrected; rejected pre-identity assembly retained.',
                 'Offline qualification environment dependency fixed; rejected manifest retained.',
                 'Recovery coverage counts the final complete suite plus the explicitly recorded corrected fixture recheck.'],
    memory=dict(measured121_capture_reserved_growth_bytes=3430940672,
                estimated145_temporal_squared_bytes=4838162432, capture_planning_reserve_bytes=5*2**30,
                first_admission_bytes=59*2**28, later_admission_bytes=39*2**28,
                measured145_capture=False, measured_reclaim_bytes=None),
    forecast=dict(period_seconds=[5.25,5.35],new_video_seconds=6,s_per_s=[0.875,5.35/6],measured=False),
    safety=dict(cpu_only=True,nice=19,OMP_NUM_THREADS=2,MKL_NUM_THREADS=2,
                python='/home/steve/.venvs/ltx25-baseline/bin/python -B',
                GPU_operations=0,model_requests=0,launches=0,systemd_operations=0,
                live_port_operations=0,process_signals=0,host_setting_changes=0,
                existing_run_writes=0,ltx_stream_writes=0),
    repository_checks=dict(doc_links_broken=0,manifest_paths_missing=0,
                           broad_hash_audit=dict(matches=87,existing_drifts=231,absent=0)),
    source_files={str(p.relative_to(REPO)):sha(p) for p in inputs},
    evidence_files={str(p.relative_to(REPO)):sha(p) for p in OUT.iterdir() if p.is_file()})
(HERE/'continuation131-build.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(manifest_sha256=result['manifest_sha256'],inner_plan_sha256=result['inner_plan_sha256'],
                     recovery=recovery['count'],client=client['count'],preflight=10)))

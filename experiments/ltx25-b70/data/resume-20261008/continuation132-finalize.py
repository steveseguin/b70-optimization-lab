#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Finalize CPU packet132 evidence only after the complete suites pass."""
import ast
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
LANE = HERE.parents[1]
REPO = LANE.parents[1]
OUT = HERE / 'continuation132-tests'
AUTHOR = LANE / 'recovery/20261010-continuation132-stream'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
def read(n): return json.loads((OUT/n).read_text())
seal = read('seal.json')
packet = Path(seal['packet'])
manifest = json.loads((packet/'manifest.json').read_text())
plan = json.loads((packet/'resolution/stream-plan.json').read_text())
parent_sha = 'e25d8d623741fed31fccfd049a323e9bf853302a21aaff472c48eda40fb1ed6f'
assert sha(packet/'manifest.json') == seal['manifest_sha256']
assert plan['plan']['basis']['parent_manifest_sha256'] == parent_sha
log = OUT/'recovery-final.log'
raw = log.read_text()
m = re.findall(r'Ran (\d+) tests in ([0-9.]+)s', raw)
assert len(m) == 1 and raw.rstrip().endswith('OK'), 'Complete recovery suite must pass'
recovery = dict(passed=int(m[0][0]), count=int(m[0][0]), elapsed_seconds=float(m[0][1]),
    log=str(log.relative_to(REPO)), sha256=sha(log), failures=0, errors=0)
client = read('client-validation.json')
assert client['passed'] == client['count'] and client['suite_count'] == 39
assert client['manifest_sha256'] == seal['manifest_sha256']
assert client['inner_plan_sha256'] == plan['plan_sha256']
assert client['all_pins'] == 28 and not client['scratch_remaining'] and not client['violations']
assert client['final_client_sha256'] == sha(LANE/'stream/ltx_continuation_client.py')
assert all(not Path(p).exists() for p in client['scratch_roots_created'])
for row in client['suites']:
    assert row['returncode'] == 0 and row['passed'] == row['count']
pre = OUT/'preflight10-final.log'
assert re.search(r'Ran 10 tests in ', pre.read_text()) and pre.read_text().rstrip().endswith('OK')
runtime = read('candidate-runtime-summary-final.json')
assert runtime['passed'] and len(runtime['cases']) == 3 and all(r['passed'] for r in runtime['cases'])
assert len(runtime['off_on_exact_cpu_outputs']) == 22
verification = read('recursive-verification.json')
assert verification['status'] == 'source-closure-verified' and verification['manifest_sha256'] == seal['manifest_sha256']
assert verification['plan_sha256'] == plan['plan_sha256'] and verification['author_components_match']
assert not list(packet.rglob('__pycache__')) + list(packet.rglob('*.pyc'))
assert not list(AUTHOR.rglob('__pycache__')) + list(AUTHOR.rglob('*.pyc'))
assert not (OUT/'scratch').exists()
inputs = [p for p in AUTHOR.iterdir() if p.is_file()]
inputs += [LANE/'stream/ltx_continuation_client.py', LANE/'stream/start-client-132.sh']
inputs += list((LANE/'stream/tests').glob('*132.py')) + list((LANE/'stream/tests').glob('*132_integration.py'))
inputs += [LANE/'stream/tests/run_tests_131.py']
inputs += list(HERE.glob('continuation132-*.py'))
inputs += [LANE/'notes/2026-10-10-continuation132-memory-evidence.md', LANE/'notes/2026-10-10-continuation132-stream-design.md', HERE/'continuation132-memory-evidence.json']
for p in inputs:
    if p.suffix == '.py': ast.parse(p.read_bytes(), filename=str(p))
result = dict(schema='ltx.stream132.cpu-build.v1', status='sealed-cpu-validated-native-unqualified',
    packet=str(packet), parent_packet=131, parent_manifest_sha256=parent_sha,
    manifest_sha256=seal['manifest_sha256'], inner_plan_sha256=plan['plan_sha256'],
    input_inventory_sha256=seal['input_inventory_sha256'], recovery=recovery, client=client,
    preflight=dict(passed=10,count=10,log=str(pre.relative_to(REPO)),sha256=sha(pre)),
    runtime=runtime, recursive_verification=verification, cleanup=read('cleanup.json'),
    static=read('static-validation.json'),
    development=['Builder copied parent-dictionary insertion order corrected before final suite.',
                 'Source closure164108297B plus4MiB safety exceeds inherited160MiB disk budget; packet132 budget192MiB, host settings unchanged.',
                 'First full recovery run:959/960 passed; inherited deployed-checker fixture omitted audio_residency132.py. Test-only correction passed28/28 focused checks and the final full suite; sealed runtime unchanged.',
                 'Historical131 client fixture first passed544/545: all-pins loop shadowed the packet-specific sealed variable. Test-only correction rerun separately; client and packet unchanged.',
                 'Scaled476 recognized but refused because no145 capture peak/upper bound exists.'],
    memory=dict(refusal_free_bytes=15825240064, original_required_bytes=15837691904,
        gap_including_screening_bytes=12451840, allocator_reclaimed_xpu3_bytes=0,
        allocator_reserved_unused_after_bytes=1809012224,
        measured121_capture_reserved_growth_bytes=3430940672,
        estimated145_temporal_squared_bytes=4838162432, active_capture_reserve_bytes=5*2**30,
        scaled_proposed_reserve_bytes=5111011083, scaled_launch_admitted=False,
        audio_checkpoint_bytes=364666868, audio_projected_margin_bytes=352215028,
        hypothetical_audio_scaled_margin_bytes=609913065, measured145_capture=False,
        measured_audio_reclaim_bytes=None),
    forecast=dict(period_seconds=[5.25,5.35],new_video_seconds=6,s_per_s=[0.875,5.35/6],
        extra_audio_placement_seconds=None, measured=False),
    open_items=['Native cross-card waveform exactness, actual audio residency relief,145 capture and sustained memory gates.',
                'Scaled476 reserve not admitted pending measured145 evidence.',
                'Encoder split deferred; shared owner needs separate exact qualification.',
                'No further allocator reclaim demonstrated; isolated audio timing and repeated cadence unmeasured.'],
    safety=dict(cpu_only=True,nice=19,OMP_NUM_THREADS=2,MKL_NUM_THREADS=2,
        python='/home/steve/.venvs/ltx25-baseline/bin/python -B',GPU_operations=0,model_requests=0,
        launches=0,systemd_operations=0,live_port_operations=0,process_signals=0,
        host_setting_changes=0,existing_run_writes=0,ltx_stream_writes=0),
    source_files={str(p.relative_to(REPO)):sha(p) for p in inputs},
    evidence_files={str(p.relative_to(REPO)):sha(p) for p in OUT.iterdir() if p.is_file()})
if (OUT/'repository-checks.json').exists():
    result['repository_checks'] = read('repository-checks.json')
(HERE/'continuation132-build.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(dict(manifest_sha256=result['manifest_sha256'],inner_plan_sha256=result['inner_plan_sha256'],
    recovery=recovery['count'],client=client['count'],preflight=10)))

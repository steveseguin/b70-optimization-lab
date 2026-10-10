#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Finalize only source-bound CPU evidence; never operates a live runtime."""
import hashlib
import json
import re
import os
import sys
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
LANE = ROOT/'experiments/ltx25-b70'
SRC = LANE/'recovery/20261010-continuation126-stream'
DATA = LANE/'data/resume-20261008'
OUT = DATA/'continuation126-tests'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def read(name):
    return json.loads((OUT/name).read_text())

def write(name, value):
    (OUT/name).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')

text = (OUT/'recovery-final.log').read_text()
count = int(re.search(r'^Ran (\d+) tests in ',text,re.M)[1])
discovery = read('recovery-final-discovery.json')
assert count == discovery['count']
rechecks = []
if not text.rstrip().endswith('OK'):
    expected = 'test_walk_mode_is_the_packet117_path_with_timing (test_runtime_flow.Flow118.test_walk_mode_is_the_packet117_path_with_timing)'
    problems = re.findall(r'^(?:FAIL|ERROR): (.+)$', text, re.M)
    assert problems == [expected], problems
    assert text.rstrip().endswith('FAILED (failures=1)')
    recheck = OUT/'recovery-runtime-flow-final.log'
    checked = recheck.read_text()
    assert checked.rstrip().endswith('OK') and expected+' ... ok' in checked
    recheck_count = int(re.search(r'^Ran (\d+) tests in ',checked,re.M)[1])
    rechecks.append({'log':recheck.name,'sha256':sha(recheck),'passed':recheck_count,
                     'reason':'Copied parent expected-options fixture lacked storage_scan_mode=request; test-only correction, sealed runtime unchanged.'})
recovery = {'status':'passed','unique_current_cases':count,'full_discovery_cases':count,
            'full_discovery_passed':count-len(rechecks),'full_discovery_fixture_failures':len(rechecks),
            'full_discovery_returncode':1 if rechecks else 0,
            'log':'recovery-final.log','sha256':sha(OUT/'recovery-final.log'),'fixture_rechecks':rechecks,
            'counting':'Complete final discovery plus documented overlapping fixture-module recheck; rechecks are not added to unique cases.'}
write('recovery-validation.json', recovery)
clients = read('client-progress.json')
assert len(clients)==27
assert all(r['returncode']==0 and r['count']>0 and r['passed']==r['count'] for r in clients)
for row in clients:
    assert sha(OUT/row['log'])==row['sha256']
client_count = sum(r['count'] for r in clients)
write('client-validation.json', {'status':'passed','suite_count':len(clients),
    'passed':client_count,'count':client_count,'suites':clients,
    'counting':'Client suites intentionally repeat shared checks; not unique unittest methods.'})
preflight = (OUT/'preflight-final.log').read_text()
assert re.search(r'Ran 10 tests in ',preflight) and preflight.rstrip().endswith('OK')
seal = read('seal.json')
verify = read('recursive-verification.json')
assembly = read('assembly-final.json')
static = read('static-validation.json')
for name,digest in assembly['input_inventory'].items():
    assert sha(SRC/name)==digest,name
assert verify['manifest_sha256']==seal['manifest_sha256']
assert verify['pycache_count']==0 and verify['pyc_count']==0
pending_links = sys.argv[1:] == ['--pending-link-checks']
assert pending_links or not sys.argv[1:], 'Unknown arguments'
integrity_checks = {}
for name in ('doc-links-final.log','manifest-paths-final.log'):
    if pending_links:
        integrity_checks[name] = 'pending'
    else:
        checks = read('integrity-validation.json')
        assert checks[name]['returncode'] == 0, checks[name]
        assert sha(OUT/name) == checks[name]['sha256'], name
        integrity_checks[name] = checks[name]
cache_paths = []
for root in (SRC, Path(seal['packet']), OUT):
    for directory, dirs, files in os.walk(root):
        cache_paths.extend(str(Path(directory)/n) for n in dirs if n=='__pycache__')
        cache_paths.extend(str(Path(directory)/n) for n in files if n.endswith('.pyc'))
assert not cache_paths, cache_paths
write('post-tests-cache-check.json', {'roots':[str(SRC),seal['packet'],str(OUT)],
                                    'pycache_count':0,'pyc_count':0})
artifacts = [DATA/'continuation126-verify.py',DATA/'continuation126-check-links.py',
             DATA/'continuation126-regression-analysis.py',DATA/'continuation126-regression-evidence.json',
             DATA/'continuation126-cpu-timing.py',DATA/'continuation126-cpu-timing-sealed.json',
             LANE/'notes/2026-10-10-continuation123b-regression.md',
             LANE/'notes/2026-10-10-continuation126-stream-design.md']
client_files = [LANE/n for n in ['stream/ltx_continuation_client.py','stream/start-client-126.sh',
    'stream/tests/run_cpu_suites.py','stream/tests/fake_comfy126.py','stream/tests/run_tests_126.py',
    'stream/tests/run_tests_126_integration.py']]
receipt = {'schema':'ltx.continuation126.cpu-build.v1','packet_id':126,
    'status':'CPU-checks-complete-link-checks-pending' if pending_links else 'prepared-not-GPU-qualified',
    'integrity_checks':integrity_checks,
    'packet':seal['packet'],'manifest_sha256':verify['manifest_sha256'],
    'plan_sha256':verify['inner_plan_sha256'],'plan_pin_definition':'INNER plan_sha256, never plan file byte hash',
    'plan_file_sha256':verify['plan_file_sha256'],'manifest_files':verify['files'],
    'parent_packet':125,'parent_manifest_sha256':verify['parent_manifest_sha256'],
    'receipt_generator_sha256':sha(Path(__file__)),
    'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    'python':'/home/steve/.venvs/ltx25-baseline/bin/python -B','nice':19,'omp_num_threads':2,'mkl_num_threads':2,
    'model_requests':0,'gpu_operations':0,'port8188_operations':0,'systemd_operations':0,
    'signals_sent':0,'existing_run_writes':0,'live_client_tree_writes':0,'host_setting_changes':0,
    'pycache_count':0,'pyc_count':0,
    'assembly':assembly,'storage_admission':seal['storage_admission'],
    'recursive_verification':verify,'static_validation':static,
    'cpu_checks':{'recovery_unique_cases':count,'client_checks':client_count,'client_suites':len(clients),
                  'mocked_preflight':10},
    'recovery_validation':str((OUT/'recovery-validation.json').relative_to(ROOT)),
    'client_validation':str((OUT/'client-validation.json').relative_to(ROOT)),
    'author_artifacts':{str(p.relative_to(ROOT)):sha(p) for p in sorted(SRC.iterdir()) if p.is_file()},
    'client_artifacts':{str(p.relative_to(ROOT)):sha(p) for p in client_files},
    'analysis_artifacts':{str(p.relative_to(ROOT)):sha(p) for p in artifacts},
    'log_artifacts':{str(p.relative_to(ROOT)):sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
    'commands':{'prefix':'nice -n19 env OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 /home/steve/.venvs/ltx25-baseline/bin/python -B',
        'recovery':str((SRC/'run_tests_126.py').relative_to(ROOT)),
        'clients':str((SRC/'run_client_suites_126.py').relative_to(ROOT)),
        'build_child':'runtime_packet.py --build --input-inventory-sha256 '+assembly['input_inventory_sha256'],
        'verification_child':'runtime_packet.py --verify-manifest-sha256 '+verify['manifest_sha256'],
        'child_guard':'run_tests_126.py --child; read-only parent verification, exclusive new packet writes',
        'launch':'NOT EXECUTED; coordinator future reference in recovery/20261010-continuation126-stream/LAUNCH.md'},
    'candidate':{'storage_scan_mode':'background','off_mode':'request','gc_interval_seconds':10,
        'aux_residency':'legacy','frames':145,'display_device':'xpu:3','display_worker':'serial',
        'display_schedule':'sampler-a','anchor_read_ahead':0,'snapshot_schedule':'full',
        'decoder_graph':0,'anchor_decode':'cone','bencode_overlap':1,'prep_ahead':1,
        'accounting_sample_max_age_s':1,'accounting_wait_bound_s':2,'pending_write_headroom_bytes':256*2**20,
        'plan_check':'fresh marshal v2 typed-tree comparison; original canonical SHA gate on difference'},
    'forecast_not_measured':{'period_seconds':[5.55,5.75],'seconds_per_video_second':[5.55/6,5.75/6],
                             'target_period_seconds':[5.61,5.64],'target_seconds_per_video_second':[.935,.940]},
    'open':['Native lossless/reference/three-chain, cone/display and preview-hash qualification.',
            'Matched two-fresh-server performance with both parities and declared chunk endpoints.',
            'Historical per-scan/lock/fsync times were not instrumented; exact150ms causal decomposition unavailable.',
            'Matched123b legacy/aux windows do not substantiate a further150ms card-hop penalty.',
            'Sampled accounting retains finite observation windows; extra256MiB headroom is conservative, not a filesystem quota.',
            'GC10 cadence remains; separateGC60 experiment is inherited and not combined in first comparison.']}
(DATA/'continuation126-build.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
print(json.dumps(receipt['cpu_checks']))

#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Finalize source-bound CPU evidence. No runtime or device operations."""
import hashlib,json,os,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
LANE=ROOT/'experiments/ltx25-b70'
DATA=LANE/'data/resume-20261008'
SRC=LANE/'recovery/20261010-continuation127-stream'
OUT=DATA/'continuation127-tests'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((OUT/n).read_text())
def save(n,v):(OUT/n).write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
text=(OUT/'recovery-complete.log').read_text()
count=int(re.search(r'^Ran (\d+) tests in ',text,re.M)[1])
assert text.rstrip().endswith('FAILED (failures=2)'),text[-3000:]
assert count==read('recovery-final-discovery.json')['count']
failed=re.findall(r'^FAIL: (test_\w+) \(([^)]+)\)',text,re.M)
assert {name for name,_ in failed}=={'test_inventory_and_assembly_fit_build_allowance','test_plan_file_is_the_reconstructed_plan_and_pins_agree'}
recheck=(OUT/'recovery-runtime-packet-recheck.log').read_text()
assert recheck.rstrip().endswith('OK'),recheck[-3000:]
recheck_count=int(re.search(r'^Ran (\d+) tests in ',recheck,re.M)[1])
for name,ident in failed:assert name+' ('+ident+') ... ok' in recheck
recovery={'status':'passed-with-documented-fixture-recheck','unique_current_cases':count,'full_discovery_cases':count,
 'full_discovery_passed':count-2,'full_discovery_failures':2,'full_discovery_returncode':1,
 'log':'recovery-complete.log','sha256':sha(OUT/'recovery-complete.log'),
 'fixture_correction':'Two inherited125 parent references and unchanged-candidate assertions updated to actual126 parent and intentional127 digest callback; sealed code unchanged.',
 'failed_cases':[name for name,_ in failed],
 'module_recheck_cases':recheck_count,'module_recheck_passed':recheck_count,
 'module_recheck_log':'recovery-runtime-packet-recheck.log','module_recheck_sha256':sha(OUT/'recovery-runtime-packet-recheck.log'),
 'counting':'720 unique validated cases:718 full-discovery passes plus complete corrected module recheck covering both failures. Rechecks not added to unique total; development runs excluded.'}
save('recovery-validation.json',recovery)
clients=read('client-progress.json')
assert len(clients)==29
assert all(r['returncode']==0 and r['count']>0 and r['passed']==r['count'] for r in clients)
for r in clients:assert sha(OUT/r['log'])==r['sha256']
client_count=sum(r['count'] for r in clients)
save('client-validation.json',{'status':'passed','suite_count':29,'passed':client_count,
 'count':client_count,'suites':clients,'counting':'Historical suites repeat shared protocol assertions; not unique unittest methods.'})
pf=(OUT/'client-preflight-final.log').read_text()
assert re.search(r'Ran 10 tests in ',pf) and pf.rstrip().endswith('OK')
seal=read('seal.json');verify=read('recursive-verification.json');assembly=read('assembly-final.json')
assert verify['manifest_sha256']==seal['manifest_sha256']
for name,digest in assembly['input_inventory'].items():assert sha(SRC/name)==digest,name
caches=[str(p) for root in (SRC,Path(seal['packet']),OUT) for p in root.rglob('*') if p.name=='__pycache__' or p.suffix=='.pyc']
assert not caches,caches
save('post-tests-cache-check.json',{'pycache_count':0,'pyc_count':0})
logs={str(p.relative_to(ROOT)):sha(p) for p in OUT.iterdir() if p.is_file()}
artifacts=[p for p in DATA.glob('continuation127-*') if p.is_file() and p.name!='continuation127-build.json']
artifacts += [LANE/'notes/2026-10-10-continuation-budget-145.md',LANE/'notes/2026-10-10-continuation127-stream-design.md']
client_files=[LANE/n for n in ['stream/ltx_continuation_client.py','stream/start-client-127.sh',
 'stream/tests/run_cpu_suites.py','stream/tests/fake_comfy127.py','stream/tests/run_tests_127.py','stream/tests/run_tests_127_integration.py']]
receipt={'schema':'ltx.continuation127.cpu-build.v1','packet_id':127,'status':'prepared-not-GPU-qualified',
 'packet':seal['packet'],'manifest_sha256':seal['manifest_sha256'],'plan_sha256':verify['inner_plan_sha256'],
 'plan_pin_definition':'INNER plan_sha256, never plan file byte hash','plan_file_sha256':verify['plan_file_sha256'],
 'manifest_files':verify['files'],'parent_packet':126,'parent_manifest_sha256':verify['parent_manifest_sha256'],
 'cpu_checks':{'recovery_unique_cases':count,'client_suites':29,'client_checks':client_count,'mocked_preflight':10},
 'recovery_validation':str((OUT/'recovery-validation.json').relative_to(ROOT)),
 'client_validation':str((OUT/'client-validation.json').relative_to(ROOT)),
 'recursive_verification':verify,'assembly':assembly,'storage_admission':seal['storage_admission'],
 'static_validation':read('static-validation.json'),
 'integrity_checks':read('integrity-validation.json'),
 'development_failures_preserved':[
  'preseal1: conditioning_guard source pin stale after candidate_safety edit; no live use.',
  'preseal2: scaffold numeric rename changed121 audio dimension126 to127; restored and direct geometry+3960graph parent comparison pass; no live use.',
  'final full suite718/720 plus corrected parent-fixture module recheck;720 unique cases validated without double counting; development logs retained.'],
 'retained_preseals':[seal['packet']+'-preseal1',seal['packet']+'-preseal2'],
 'forecast_not_measured':{'period_seconds':[5.45,5.70],'seconds_per_video_second':[5.45/6,5.70/6],
  'central_period_seconds':5.55,'central_seconds_per_video_second':.925},
 'candidate':{'snapshot_digest_cache':1,'storage_scan_mode':'background','gc_interval_seconds':60,
  'frames':145,'decoder_graph':0,'display_device':'xpu:3','display_worker':'serial','aux_residency':'legacy',
  'off':'snapshot_digest_cache0 retains126 digest path'},
 'python':'/home/steve/.venvs/ltx25-baseline/bin/python -B','nice':19,'omp_num_threads':2,'mkl_num_threads':2,
 'pycache_count':0,'pyc_count':0,'gpu_operations':0,'model_requests':0,'systemd_operations':0,
 'port8188_operations':0,'signals_sent':0,'existing_run_writes':0,'live_client_tree_writes':0,'host_setting_changes':0,
 'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
 'analysis_artifacts':{str(p.relative_to(ROOT)):sha(p) for p in artifacts},
 'author_sources':{str(p.relative_to(ROOT)):sha(p) for p in SRC.iterdir() if p.is_file()},
 'client_artifacts':{str(p.relative_to(ROOT)):sha(p) for p in client_files},'log_artifacts':logs,
 'open':['Native byte/reference/three-chain and memory qualification.',
  'Two fresh-server matched speed comparisons;0.90s/s is not established.',
  '126 later measured5.722s fixed40; combined127 forecast revised, not a measured result.',
  '145 cone graph positive cap/replica admission unproven;169parallel combination unmeasured.',
  'Current145 per-card sampler profile absent; old eager dispatch fraction does not apply.',
  'Broad shell-pin audit finds231 existing Flash-Next pins drifted across2 untouched targets; no packet127 pin drift.']}
(DATA/'continuation127-build.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
print(json.dumps({'manifest':receipt['manifest_sha256'],'plan':receipt['plan_sha256'],'checks':receipt['cpu_checks']}))

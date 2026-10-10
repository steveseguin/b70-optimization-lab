#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Bind completed CPU logs to the packet125 build receipt; no live operations."""
import hashlib
import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[4]
LANE = ROOT / 'experiments/ltx25-b70'
SRC = LANE / 'recovery/20261010-continuation125-stream'
DATA = LANE / 'data/resume-20261008'
OUT = DATA / 'continuation125-tests'

def read(name):
    return json.loads((OUT/name).read_text())

def write(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)+'\n')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def test_rows(name):
    text=(OUT/name).read_text()
    matches=re.findall(r'^(test_\S+) \(([^)]+)\)(?:\n[^\n]*)? \.\.\. (ok|FAIL|ERROR)$',text,re.M)
    rows={identity: status for _,identity,status in matches}
    count=int(re.search(r'^Ran (\d+) tests in ',text,re.M)[1])
    assert len(rows)==count,(name,len(rows),count)
    return rows

discovery=read('recovery-final-discovery.json')
rows=test_rows('recovery-final.log')
assert set(rows)==set(discovery['test_ids'])
failures={key: value for key,value in rows.items() if value!='ok'}
assert len(failures)==2,failures
rechecks={}
for name in ('parent-fixture-recheck.log','options-fixture-recheck.log'):
    checked=test_rows(name)
    assert all(status=='ok' for status in checked.values())
    rechecks[name]={'count':len(checked),'test_ids':list(checked),'sha256':sha(OUT/name)}
    rows.update(checked)
assert len(rows)==discovery['count'] and all(v=='ok' for v in rows.values())
recovery={'status':'passed-after-documented-fixture-rechecks','unique_current_cases':len(rows),
          'full_discovery_cases':discovery['count'],'full_run_failures':failures,
          'full_run_passed':discovery['count']-len(failures),
          'full_run_log':'recovery-final.log','full_run_sha256':sha(OUT/'recovery-final.log'),
          'rechecks':rechecks,
          'reason':'Two copied fixture expectations retained the old parent hash and omitted the new default gc_interval_seconds=10 field. Only test fixtures changed; sealed runtime source stayed unchanged.',
          'development':'recovery-development.log preserves the earlier 623-case discovery (4 failures, 1 error) while sources were still being assembled; it is not a clean validation run.',
          'counting':'Rechecks overlap discovery and are not added to the unique case count.'}
write('recovery-validation.json',recovery)
clients=read('client-progress.json')
assert len(clients)==25
assert all(r['returncode']==0 and r['count']>0 and r['passed']==r['count'] for r in clients),clients
for r in clients:
    assert sha(OUT/r['log'])==r['sha256']
client_count=sum(r['count'] for r in clients)
client_validation={'status':'passed','suite_count':len(clients),'passed':client_count,'count':client_count,'suites':clients,
                   'counting':'Packet suites can intentionally repeat shared assertions; these are client checks, not unique unit-test methods.',
                   'cpu_only':'Cooperative fake children on loopback test ports; port8188/device opens/signals forbidden. No model server.'}
write('client-validation.json',client_validation)
preflight=(OUT/'preflight-recheck.log').read_text()
assert re.search(r'Ran 10 tests in ',preflight) and preflight.rstrip().endswith('OK')
seal=read('seal.json')
verify=read('recursive-verification.json')
assembly=read('assembly-final.json')
static=read('static-validation.json')
for name,h in assembly['input_inventory'].items():
    assert sha(SRC/name)==h,name
author={str(p.relative_to(ROOT)):sha(p) for p in sorted(SRC.iterdir()) if p.is_file()}
client_names=['stream/ltx_continuation_client.py','stream/start-client-125.sh','stream/tests/run_cpu_suites.py','stream/tests/fake_comfy125.py','stream/tests/run_tests_125.py','stream/tests/run_tests_125_integration.py']
client_artifacts={str((LANE/n).relative_to(ROOT)):sha(LANE/n) for n in client_names}
logs={str(p.relative_to(ROOT)):sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.suffix in ('.json','.log')}
receipt={'schema':'ltx.continuation125.cpu-build.v1','packet_id':125,'status':'prepared-not-GPU-qualified',
         'receipt_generator_sha256':sha(pathlib.Path(__file__)),
         'packet':seal['packet'],'manifest_sha256':verify['manifest_sha256'],
         'plan_sha256':verify['inner_plan_sha256'],'plan_pin_definition':'INNER resolution/stream-plan.json plan_sha256, not its file byte hash',
         'plan_file_sha256':verify['plan_file_sha256'],'manifest_files':verify['files'],
         'parent_packet':124,'parent_manifest_sha256':verify['parent_manifest_sha256'],
         'source_commit':subprocess.check_output(['git','rev-parse','72edffa6d'],cwd=ROOT,text=True).strip(),
         'analysis_commit':subprocess.check_output(['git','rev-parse','65c026e3f'],cwd=ROOT,text=True).strip(),
         'analysis_artifacts':{str(p.relative_to(ROOT)):sha(p) for p in (DATA/'continuation125-evidence-analysis.py',DATA/'continuation125-evidence.json',DATA/'continuation125-legacy-addendum.py',DATA/'continuation125-legacy-addendum.json',LANE/'notes/2026-10-10-continuation-2cycle-analysis.md')},
         'client_commit':subprocess.check_output(['git','rev-parse','2f840735b'],cwd=ROOT,text=True).strip(),
         'python':'/home/steve/.venvs/ltx25-baseline/bin/python -B','nice':19,'omp_num_threads':2,'mkl_num_threads':2,
         'model_requests':0,'gpu_operations':0,'port8188_operations':0,'systemd_operations':0,'signals_sent':0,
         'existing_run_writes':0,'live_client_tree_writes':0,'host_setting_changes':0,
         'pyc_count':0,'pycache_count':0,'recursive_verification':verify,'static_validation':static,
         'storage_admission':seal['storage_admission'],'assembly':assembly,
         'commands':{
             'prefix':'OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 /home/steve/.venvs/ltx25-baseline/bin/python -B',
             'recovery':'experiments/ltx25-b70/recovery/20261010-continuation125-stream/run_tests_125.py',
             'clients':'experiments/ltx25-b70/recovery/20261010-continuation125-stream/run_client_suites_125.py',
             'assembly_child':'runtime_packet.py --inspect-assembly',
             'build_child':'runtime_packet.py --build --input-inventory-sha256 '+assembly['input_inventory_sha256'],
             'verify_child':'runtime_packet.py --verify-manifest-sha256 '+verify['manifest_sha256'],
             'child_guard':'run_tests_125.py --child; build writes only a new destination and refuses an existing packet',
             'launch':'Not executed. Future coordinator commands are in recovery/20261010-continuation125-stream/LAUNCH.md.'},
         'author_artifacts':author,'client_artifacts':client_artifacts,'log_artifacts':logs,
         'cpu_checks':{'recovery_unique_cases':len(rows),'client_checks':client_count,'client_suites':25,'mocked_preflight':10,
                       'analysis_structural_checks_separate':6,'builder_cases_subset_of_recovery':16},
         'recovery_validation':str((OUT/'recovery-validation.json').relative_to(ROOT)),
         'client_validation':str((OUT/'client-validation.json').relative_to(ROOT)),
         'options':{'default_gc_interval_seconds':10,'candidate_gc_interval_seconds':60,'frames':145,'first_aux_residency':'legacy','display_device':'xpu:3','display_worker':'serial','display_schedule':'sampler-a','anchor_read_ahead':0,'snapshot_schedule':'full','decoder_graph':0,'anchor_decode':'cone','bencode_overlap':1,'prep_ahead':1},
         'forecast_not_measured':{'median_period_seconds':[5.45,5.75],'median_seconds_per_video_second':[5.45/6,5.75/6],'target_period_seconds':5.55,'target_seconds_per_video_second':0.925,'simple_amortized_period_seconds':5.58,'adverse_period_seconds':[5.75,6.10]},
         'open':['Historical GC/cache attribution is strongly supported by source and timestamps but not directly timed; packet125 adds callback timestamps for native confirmation.',
                 'Native three-chain and saved145 reference identity, every cone/display comparison and preview hash must pass.',
                 'Longer allocator/cycle retention requires memory trend and unchanged floor checks over multiple60-second windows.',
                 'Production speed and removal of the two-cycle need matching text classes and two fresh qualified servers; CPU task launched none.',
                 'Minute maintenance and fresh-text costs remain; report all chunks including maintenance in mean/p90.',
                 'Additional legacy123b snapshot has a 5.689-second fast-side median; target5.55 is not guaranteed across server instances.'],
         'validation_status':'Full 655-case discovery plus two corrected-fixture module/class rechecks covers all current recovery cases; all25 client suites and10 mocked preflight tests pass. No native qualification claimed.'}
(DATA/'continuation125-build.json').write_text(json.dumps(receipt,indent=2,sort_keys=True,ensure_ascii=False)+'\n')
print(json.dumps(receipt['cpu_checks']))

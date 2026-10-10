#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Bind final CPU evidence only when all packet134 gates pass."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
LANE=HERE.parents[1]
REPO=LANE.parents[1]
AUTHOR=LANE/'recovery/20261010-continuation134-stream'
OUT=HERE/'continuation134-tests'
PARENT_SHA='ed908a9031a937801d17264edacfe0807bea543badc412a32eb6118daa214fd3'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(name): return json.loads((OUT/name).read_text())
def tests(name):
    p=OUT/name; raw=p.read_text(); rows=re.findall(r'Ran (\d+) tests in ([0-9.]+)s',raw)
    assert len(rows)==1 and raw.rstrip().endswith('OK'), name
    return dict(count=int(rows[0][0]),passed=int(rows[0][0]),elapsed_seconds=float(rows[0][1]),
                log=str(p.relative_to(REPO)),sha256=sha(p))

seal=read('seal.json'); packet=Path(seal['packet'])
assert sha(packet/'manifest.json')==seal['manifest_sha256']
plan=json.loads((packet/'resolution/stream-plan.json').read_text())
assert plan['plan']['basis']['parent_manifest_sha256']==PARENT_SHA
assert sha(packet.with_name('prepared-continuation-stream-133b')/'manifest.json')==PARENT_SHA
recovery=tests('recovery-final.log'); imports=tests('sealed-import-final.log')
assert seal['sealed_import']['passed'] and seal['sealed_import']['checks']==2
clients=read('client-progress.json')
assert len(clients)==45 and clients[-2]['suite']=='134' and clients[-1]['suite']=='134_integration'
for row in clients:
    assert row['returncode']==0 and row['passed']==row['count']>0,row
    assert sha(OUT/row['log'])==row['sha256']
client_source=read('client-source-namespaced.json')
assert client_source['passed']
assert client_source['start_sha256']==client_source['end_sha256']==sha(LANE/'stream/ltx_continuation_client.py')
pins=read('client-pins.json')
assert pins['all_pins_passed'] and pins['assertions']==36 and pins['packets']==18
assert pins['packet134_inner_plan_sha256']==plan['plan_sha256']
assert pins['packet134_manifest_sha256']==seal['manifest_sha256']
assert pins['client_sha256']==client_source['end_sha256']
runtime=read('candidate-runtime-summary-final.json')
assert runtime['passed'] and len(runtime['cases'])==4 and len(runtime['off_on_exact_cpu_outputs'])==22
assert runtime['preflight']['passed'] and runtime['preflight']['tests']==10
assert runtime['source_unchanged_during_cases']
assert runtime['source_sha256']=={str(p.relative_to(REPO)):sha(p) for p in sorted(AUTHOR.glob('*.py'))}
for row in [*runtime['cases'],runtime['preflight']]: assert sha(REPO/row['log'])==row['sha256']
verify=read('recursive-verification.json'); assert verify['manifest_sha256']==seal['manifest_sha256']
assert verify['status']=='source-closure-verified'
cleanup=read('cleanup.json'); assert cleanup['passed'] and not (OUT/'scratch').exists()
checks={'status':'pending-final-repository-checks'}
for p in (AUTHOR,packet): assert not list(p.rglob('__pycache__'))+list(p.rglob('*.pyc'))
paths=sorted(p for p in AUTHOR.iterdir() if p.is_file())+sorted(HERE.glob('continuation134-*.py'))
paths += [LANE/'stream/ltx_continuation_client.py',LANE/'stream/start-client-134.sh',
          LANE/'stream/tests/run_tests_134.py',LANE/'stream/tests/run_tests_134_integration.py',
          LANE/'notes/2026-10-10-continuation134-stream-design.md',
          LANE/'notes/2026-10-10-continuation133b-results-145.md']
for p in paths:
    if p.suffix=='.py':ast.parse(p.read_bytes(),filename=str(p))
receipt=dict(schema='ltx.stream134.cpu-build.v1',status='cpu-validated-awaiting-repository-checks',
    packet=str(packet),parent_packet='133b',parent_manifest_sha256=PARENT_SHA,
    manifest_sha256=seal['manifest_sha256'],inner_plan_sha256=plan['plan_sha256'],
    input_inventory_sha256=seal['input_inventory_sha256'],
    arm='169 split36 cone graph off; native display/audio xpu:3; legacy auxiliaries',
    recovery=recovery,sealed_import=dict(**imports,included_in_recovery=True,preseal=seal['sealed_import']),
    client=dict(suite_count=len(clients),passed=sum(r['passed'] for r in clients),
        count=sum(r['count'] for r in clients),suites=clients,pins=pins,source_audit=client_source),
    runtime=runtime,preflight=runtime['preflight'],recursive_verification=verify,cleanup=cleanup,repository_checks=checks,
    safety=dict(cpu_only=True,nice=19,OMP_NUM_THREADS=2,MKL_NUM_THREADS=2,
        python='/home/steve/.venvs/ltx25-baseline/bin/python -B',GPU_operations=0,model_requests=0,
        launches=0,launcher_check_only_calls=0,systemd_operations=0,live_port_operations=0,device_opens=0,
        process_signals=0,host_setting_changes=0,existing_run_writes=0,ltx_stream_writes=0),
    native_qualification=False,measured_169_speed_or_memory=False,
    evidence_analysis=dict(path=str((HERE/'continuation134-evidence.json').relative_to(REPO)),
                           sha256=sha(HERE/'continuation134-evidence.json')),
    source_files={str(p.relative_to(REPO)):sha(p) for p in paths},
    evidence_files={str(p.relative_to(REPO)):sha(p) for p in OUT.rglob('*') if p.is_file()})
destination=HERE/'continuation134-build.json'
destination.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
# The receipt must exist before checking the documentation that links to it.
# Keep it explicitly pending until the static checks have actually completed.
subprocess.run([sys.executable,'-B',str(HERE/'continuation134-repository-checks.py')],check=True)
checks=read('repository-checks.json')
assert checks['status']=='packet134-checks-passed-existing-pin-drift'
receipt['repository_checks']=checks
receipt['status']='sealed-cpu-validated-native-unqualified'
receipt['evidence_files']={str(p.relative_to(REPO)):sha(p) for p in OUT.rglob('*') if p.is_file()}
destination.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
print(json.dumps(dict(manifest=receipt['manifest_sha256'],plan=receipt['inner_plan_sha256'],
    recovery=recovery['count'],sealed_import=imports['count'],client=receipt['client']['count'])))

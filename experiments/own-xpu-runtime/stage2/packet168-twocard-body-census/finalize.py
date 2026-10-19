"""Record incomplete qualification honestly; write READY last, always false."""
import ast,json,resource,subprocess
from pathlib import Path
from build_engine import P,ROOT,limits,save,sha
import package
RESERVED={'pins','files','gates','artifacts','sources','files_sha256'}
def validate_keys(value,path):
    if isinstance(value,dict):
        for key,item in value.items():
            if key in RESERVED:
                assert isinstance(item,dict)and all(isinstance(k,str)and isinstance(v,str)and len(v)==64 and all(c in '0123456789abcdef'for c in v) for k,v in item.items()),(path,key)
            validate_keys(item,path)
    elif isinstance(value,list):
        for item in value:validate_keys(item,path)
def main():
    limits();package.seal()
    py_count=0;json_count=0
    for f in P.rglob('*'):
        if not f.is_file()or f.relative_to(P).parts[0]=='build':continue
        if f.suffix=='.py':ast.parse(f.read_text(),filename=str(f));py_count+=1
        if f.suffix=='.json':validate_keys(json.loads(f.read_text()),str(f));json_count+=1
    from cpu_seal import verify
    verify()
    replay=json.loads((P/'evidence/real-parent-replay.json').read_text());assert replay['passed']
    assert sum(r['actual_census_control_validator_checks']for r in replay['records'])==60
    assert json.loads((P/'evidence/report-adapter.json').read_text())['passed']
    assert json.loads((P/'evidence/launch-checks.json').read_text())['passed']
    native=json.loads((P/'evidence/native-lifecycle.json').read_text())
    assert native['partial_lifecycle_passed']and native['passed']is False
    shared=json.loads((P/'evidence/shared-packaging.json').read_text())
    assert len(shared['results'])==4 and all(r['passed']for r in shared['results']if r['kind']=='plan')
    # Explicit denial is tested without model/device access. No false marker is
    # needed to prove the entry's second, implementation-level refusal.
    import screen
    try:screen.main(['--lane','B','--output',str(P/'evidence/never-created'),'--authorized-device-window'])
    except ValueError as error:assert 'incomplete' in str(error)
    else:raise AssertionError('incomplete device path accepted')
    assert not(P/'evidence/never-created').exists()
    save(P/'evidence/final-audit.json',dict(passed=True,device_readiness=False,
      scope='retained incomplete preparation integrity, not a qualification pass',
      python_sources_parsed=py_count,json_key_maps_checked=json_count,incomplete_device_entry_refused=True,
      native_observations=sum(r['observations']for r in native['results']),
      real_sensor_samples=sum(r['real_sensor_samples']for r in native['results']),
      maximum_native_cpu_rss_bytes=max(r['peak_rss_bytes']for r in native['results'])))
    receipts={str(f.relative_to(P)):sha(f)for f in sorted((P/'evidence').glob('*.json'))}
    # This is the final write. All source edits and shared receipts precede it.
    save(P/'READY-FOR-DEVICE.json',dict(schema='packet168.readiness.v1',ready=False,ready_for_device=False,
      device_executed=False,model_loads=0,measured_ranked_table_available=False,
      seal_sha256=sha(P/'seal.json'),evidence_sha256=receipts,
      blockers=package.BLOCKERS,lane='B',cards=[2,3],alternative_lane='A',
      shared_tool_limitations=[
        'Frozen shared report rehearsal refuses this custom census entry/report schema; actual failed receipts retained.',
        'Private twelve-view adapter passes only synthetic entry/parser/analyzer/report cases, not device orchestration.',
        'No complete preparation-path probe is declared; partial native real-copy lifecycle is not a substitute.'
      ],optional_smoke=False,
      opening_checks='K1a/K1b and exact control remain unimplemented/unqualified; no smoke waiver',
      no_performance_claim=True,submission_eligible=False))
    print('READY written LAST: ready_for_device=false; incomplete census, no measurements')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main()

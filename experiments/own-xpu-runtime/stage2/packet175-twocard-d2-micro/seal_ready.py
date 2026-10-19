"""Revalidate the complete CPU closure, then write the READY marker last."""
import json,re,sys
from datetime import datetime,timezone
from unittest.mock import patch
from build_engine import P,ROOT,limits
from micro_analyze import sha
import micro_analyze
import run_micro
from run_cpu_gates import native_rows


def verify(mapping):
    assert isinstance(mapping,dict) and mapping
    for name,digest in mapping.items():
        assert re.fullmatch('[0-9a-f]{64}',digest),name
        assert sha(ROOT/name)==digest,name


def maps_only(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if key in {'pins','files','gates','artifacts','sources','files_sha256'}:
                assert isinstance(item,dict),key
                assert all(isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v) for v in item.values()),key
            maps_only(item)
    elif isinstance(value,list):
        for item in value:maps_only(item)


def main():
    limits()
    jobs={lane:json.loads(path.read_text()) for lane,path in run_micro.PROPOSALS.items()}
    digests={lane:sha(path) for lane,path in run_micro.PROPOSALS.items()}
    run_micro.build_gate()
    cpu=json.loads((P/'evidence/cpu-synthetic-parity.json').read_text())
    assert cpu['passed'] and cpu['compiler_exactness'] and cpu['host_ab_byte_identical'] and cpu['parent_matched_buffers']>0
    builds={r['mode']:r['sha256'] for r in json.loads((P/'evidence/build.json').read_text())['records']}
    assert {r['compiler']:r['binary_sha256'] for r in cpu['records']}=={k:builds[k] for k in ('gnu-host','intel-host')}
    traces=[]
    for row in cpu['records']:
        path=ROOT/row['stdout'];assert sha(path)==row['stdout_sha256']
        traces.append(native_rows(path))
    assert traces[0]==traces[1] and len(traces[0])==cpu['compared_buffers']
    inherited=json.loads((P/'evidence/oracle-inheritance.json').read_text())
    assert inherited['passed'] and inherited['oracle_sha256']==sha(P/'evidence/real-oracle.tsv')
    for parent in inherited['parents']:
        assert set(parent)=={'name','parent_relpath','parent_digest'} and sha(ROOT/parent['parent_relpath'])==parent['parent_digest']
    prep=json.loads((P/'evidence/preparation.json').read_text())
    assert prep['passed'] and prep['reset_count']==2*(2+2*240) and prep['real_resets'] and prep['real_sensors']
    assert prep['native_sha256']==builds['device'] and prep['proposal_sha256']==digests
    sensor=ROOT/prep['output']/'real-arm-sensors.jsonl';assert sha(sensor)==prep['sensors_sha256']
    assert set(prep['checked_flags'])=={v for v in run_micro.native_command()[3:] if v.startswith('--')}
    tests=(P/'evidence/analyzer-tests.log').read_text();assert 'Ran 7 tests' in tests and tests.rstrip().endswith('OK')
    paths=[p for p in P.rglob('*') if p.is_file() and p.suffix in ('.py','.cpp','.hpp') and not {'build','evidence'}.intersection(p.relative_to(P).parts)]
    paths += [P/name for name in ('README.md','DO-NOT-REPEAT.md','evidence/source-seal.json','evidence/build.json',
              'evidence/cpu-synthetic-parity.json','evidence/oracle-inheritance.json','evidence/real-oracle.tsv',
              'evidence/preparation.json','evidence/private-report.json','evidence/private-rehearsal.json',
              'evidence/analyzer-tests.log','evidence/runtime-assets.json','evidence/do-not-repeat-search.txt')]
    paths += [*run_micro.PROPOSALS.values(),sensor]
    note=ROOT/'notes/2026-10-19-own-runtime-packet175.md'
    for name in ('private-report.json','private-rehearsal.json'):
        receipt=json.loads((P/'evidence'/name).read_text())
        assert receipt['passed'] and receipt['proposal_sha256']==digests
        verify(receipt['sources']);maps_only(receipt)
    report=json.loads((P/'evidence/private-report.json').read_text())
    assert len(report['synthetic_cases'])==3 and report['packet166_device_stream_rejected']['rejected'] and report['invalid_oracle_refused_without_tails']
    for job in jobs.values():
        assert job['plan']['minimum_root_free_bytes']==25_000_000_000
    assert run_micro.storage_admit()['minimum_root_free_bytes']==25_000_000_000
    row=dict(schema='own-runtime.packet175.readiness.v1',ready_for_device=True,ready=True,
             device_executed=False,created_utc=datetime.now(timezone.utc).isoformat(),
             proposals={lane:str(path.relative_to(ROOT)) for lane,path in run_micro.PROPOSALS.items()},
             proposal_sha256=digests,job_names={lane:job['name'] for lane,job in jobs.items()},
             sources={str(p.relative_to(ROOT)):sha(p) for p in paths},
             private_report_sha256=sha(P/'evidence/private-report.json'),
             decision_rule=dict(maximum_b_over_a=micro_analyze.MAX_RATIO,eligible='eligible for combined bundle-9 (with packet153 static descriptors, never alone)',otherwise='close D2',source='coordinator hourly review 44 (supersedes the 4.8% rule before sealing)'),
             passed_checks=dict(three_native_builds=True,gnu_intel_synthetic_exact=True,host_ab_byte_identical=True,
               packet166_host_trace_equal=True,inherited_real_oracle=True,cpu_real_arm_resets=prep['reset_count'],
               declared_help_flags=True,real_entry_plans_A_B=True,lanequeue_temp_plans_A_B=True,
               private_actual_report_and_both_tails=True,invalid_oracle_rejected=True,packet166_stream_rejected=True,
               analyzer_tests=7,device_disk_floor_bytes=25_000_000_000),
             blockers=[],device_b_over_a=None,decision='pending exact device evidence',
             note_digest=sha(note),next_action='Coordinator may admit ONE of the unqueued proposals (lane A or B, whichever is free) through the existing device guards; the runner refuses a second lane once any output exists.')
    verify(row['sources']);maps_only(row)
    sys.path.insert(0,str(P.parents[1]/'ops/lane-queue'))
    import pin_guard
    marker=P/'READY-FOR-DEVICE.json';original=pin_guard.read_metadata
    def metadata(path):
        return json.dumps(row).encode() if path==marker else original(path)
    admissions={}
    with patch.object(pin_guard,'read_metadata',side_effect=metadata):
        for lane,job in jobs.items():
            admissions[lane]=pin_guard.check_job(job);assert admissions[lane]['passed'],lane
    marker.write_text(json.dumps(row,indent=2)+'\n')
    run_micro.execution_gate()  # CPU-only, read-only validation of the final marker.
    print(json.dumps(dict(ready_for_device=True,pins={k:v['pins'] for k,v in admissions.items()})))

if __name__=='__main__':main()

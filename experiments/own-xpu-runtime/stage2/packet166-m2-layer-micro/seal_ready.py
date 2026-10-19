"""Revalidate the complete CPU closure, then write the READY marker last."""
import json,re,sys
from datetime import datetime,timezone
from unittest.mock import patch
from build_engine import P,ROOT,limits
from micro_analyze import sha
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
    proposal=P.parents[1]/'ops/lane-queue/proposed-p166-micro-B.txt'
    job=json.loads(proposal.read_text())
    run_micro.build_gate()
    cpu=json.loads((P/'evidence/cpu-real-parity.json').read_text())
    assert cpu['passed'] and cpu['real_weights'] and cpu['compiler_exactness']
    builds={r['mode']:r['sha256'] for r in json.loads((P/'evidence/build.json').read_text())['records']}
    assert {r['compiler']:r['binary_sha256'] for r in cpu['records']}=={k:builds[k] for k in ('gnu-host','intel-host')}
    traces=[]
    for row in cpu['records']:
        path=ROOT/row['stdout'];assert sha(path)==row['stdout_sha256']
        traces.append(native_rows(path))
    assert traces[0]==traces[1] and len(traces[0])==414
    assert cpu['oracle_sha256']==sha(P/'evidence/real-oracle.tsv')
    assert cpu['peak_rss_bytes']<=4*1024**3
    prep=json.loads((P/'evidence/preparation.json').read_text())
    assert prep['passed'] and prep['reset_count']==2412 and prep['real_resets'] and prep['real_sensors']
    assert prep['native_sha256']==builds['device'] and prep['proposal_sha256']==sha(proposal)
    sensor=ROOT/prep['output']/'real-arm-sensors.jsonl';assert sha(sensor)==prep['sensors_sha256']
    assert set(prep['checked_flags'])=={v for v in run_micro.native_command()[3:] if v.startswith('--')}
    paths=[p for p in P.rglob('*') if p.is_file() and p.suffix in ('.py','.cpp','.hpp') and not {'build','evidence'}.intersection(p.relative_to(P).parts)]
    paths += [P/name for name in ('README.md','DO-NOT-REPEAT.md','evidence/README.md',
              'evidence/source-seal.json','evidence/build.json','evidence/cpu-real-parity.json',
              'evidence/real-oracle.tsv','evidence/preparation.json','evidence/private-report.json',
              'evidence/private-rehearsal.json','evidence/analyzer-tests-166b.log',
              'evidence/rehearsal.json','evidence/shared-rehearsal.stdout','evidence/shared-rehearsal.stderr',
              'evidence/runtime-assets.json','evidence/report-fixture-write-size.json')]
    paths += [proposal,sensor,ROOT/'notes/2026-10-19-own-runtime-packet166.md']
    # Notes are historical narrative, retained by digest separately from active pins.
    note=paths.pop()
    for name in ('private-report.json','private-rehearsal.json'):
        receipt=json.loads((P/'evidence'/name).read_text())
        assert receipt['passed'] and receipt['proposal_sha256']==sha(proposal)
        verify(receipt['sources']);maps_only(receipt)
    report=json.loads((P/'evidence/private-report.json').read_text())
    assert len(report['synthetic_cases'])==3 and report['actual_parent_replay']['rejected']
    assert report['threshold_checks'] and report['invalid_oracle_refused_without_tails']
    tests=(P/'evidence/analyzer-tests-166b.log').read_text();assert 'Ran 7 tests' in tests and tests.endswith('OK\n')
    shared=P/'evidence/rehearsal.json'
    assert sha(shared)=='45d344f7b292203333b8c912ca49e793d0a54a0861ea4c696ea3991750f38ee9'
    assert not json.loads(shared.read_text())['passed']
    assert job['plan']['minimum_root_free_bytes']==25_000_000_000
    assert run_micro.storage_admit()['minimum_root_free_bytes']==25_000_000_000
    row=dict(schema='own-runtime.packet166.readiness.v2',ready_for_device=True,ready=True,
             device_executed=False,created_utc=datetime.now(timezone.utc).isoformat(),
             proposal=str(proposal.relative_to(ROOT)),proposal_sha256=sha(proposal),
             sources={str(p.relative_to(ROOT)):sha(p) for p in paths},
             private_report_sha256=sha(P/'evidence/private-report.json'),
             passed_checks=dict(three_native_builds=True,real_weight_cpu_gnu_intel_exact=True,
               compared_buffers=414,cpu_real_arm_resets=2412,declared_help_flags=True,
               real_entry_plan=True,lanequeue_temp_plan=True,private_actual_report_and_all_tails=True,
               invalid_oracle_rejected=True,real_parent_wrong_workload_rejected=True,analyzer_tests=7,
               device_disk_floor_bytes=25_000_000_000),
             shared_tool_limitations=[dict(tool='ops/rehearse_entry.py --report',
               limitation='Retained shared report adapter accepts packet162 matrix schema/0.85 threshold; packet166 complete-layer schema/1.5 prefill and +5% MTP tails use a qualified private adapter.',
               retained_failure='evidence/rehearsal.json',replacement='evidence/private-report.json')],
             blockers=[],device_m2_over_m1=None,
             prefill_decision='pending complete exact device evidence',mtp_decision='pending complete exact device evidence',
             note_digest=sha(note),next_action='Coordinator may admit the unqueued lane-B proposal through existing device guards; no device work performed by this qualification.')
    verify(row['sources']);maps_only(row)
    # Check the exact future marker with the real pin guard before writing it.
    sys.path.insert(0,str(P.parents[1]/'ops/lane-queue'))
    import pin_guard
    marker=P/'READY-FOR-DEVICE.json';original=pin_guard.read_metadata
    def metadata(path):
        return json.dumps(row).encode() if path==marker else original(path)
    with patch.object(pin_guard,'read_metadata',side_effect=metadata):
        admission=pin_guard.check_job(job)
    assert admission['passed']
    marker.write_text(json.dumps(row,indent=2)+'\n')
    run_micro.execution_gate()  # CPU-only, read-only validation of the final marker.
    print(json.dumps(dict(ready_for_device=True,pin_count=admission['pins'],manifest_count=admission['manifests'])))

if __name__=='__main__':main()

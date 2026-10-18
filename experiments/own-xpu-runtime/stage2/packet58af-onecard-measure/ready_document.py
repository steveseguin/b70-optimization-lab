"""Write the gate-bound device-measurement handoff as the final content write."""
from datetime import datetime,timezone
import json,resource,subprocess,sys
from pathlib import Path
from build_engine import P,ROOT,sha,save
import cpu_seal

def document():
    build=cpu_seal.verify()
    entry=json.loads((P/'evidence/entry-report.json').read_text());assert entry['passed']
    plan=json.loads((P/'evidence/queue-plan.json').read_text());assert plan['passed']
    assert plan['build_receipt_sha256']==sha(P/'build-receipt.json')
    proposal=P.parents[1]/'ops/lane-queue/proposed-p58af-measure-A.txt'
    assert proposal.read_bytes()==(P/'proposals'/proposal.name).read_bytes()
    sys.path.insert(0,str(proposal.parent))
    import pin_guard
    checked=pin_guard.check_job(json.loads(proposal.read_text().splitlines()[-1]));assert checked['passed']
    return dict(schema='own-runtime.packet58af.ready.v1',created_utc=datetime.now(timezone.utc).isoformat(),
        implementation_base_commit=subprocess.check_output(['git','rev-parse','HEAD'],stdin=subprocess.DEVNULL,text=True).strip(),
        passed=True,ready_for_device=True,cpu_preparation_complete=True,device_executed=False,
        services_started=False,queued=False,live_queue_changed=False,last_content_write=True,
        build_receipt_sha256=sha(P/'build-receipt.json'),proposal=str(proposal.relative_to(ROOT)),proposal_sha256=sha(proposal),
        queue_plan_sha256=sha(P/'evidence/queue-plan.json'),
        completed=dict(host_and_sycl_compile=True,frozen_parent_relinks=True,miniature_byte_repeats=True,
            oracle_failure_before_next_view=True,analyzer_negative_tests=json.loads((P/'evidence/cpu-tests.json').read_text())['checks'],
            partition_bytes_and_geometry=True,fullshape_startup=True,real_queue_to_native_arguments=True,
            shared_entry_report=True,temporary_queue_plan=True,pin_guard=checked),
        capabilities=__import__('readiness').CAPABILITIES,
        pending_device_gates=['off/on instrumentation overhead strictly below 2 percent',
                              'every-token packet49 parity in all five device views',
                              'complete valid event coverage for both arms'],
        blockers=[],
        planned=dict(model_loads=1,views=['A0-off','B0-arm1','A1-off','B1-arm2','A2-off'],prompts_per_view=12,
            token_cap=64,total_expected_seconds_max=900,watchdog_seconds=900,lane='A',scope='whole-host',hold='existing packet58ab hold only'),
        storage=dict(build_bytes=build['retained_build_bytes'],build_cap_bytes=200_000_000,root_stop_floor_bytes=25_000_000_000),
        qualification='Ready for the bounded diagnostic device measurement. No device run, measured overhead, speed or device quality claim.')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));assert sys.argv[1:]==['--write-last']
    save(P/'READY-FOR-DEVICE.json',document());print('Final content write: ready_for_device=true; device measurements pending')

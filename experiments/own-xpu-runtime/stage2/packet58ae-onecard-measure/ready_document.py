"""Write the honest blocked handoff as the packet's final content write."""
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
    proposal=P.parents[1]/'ops/lane-queue/proposed-p58ae-combined-A.txt'
    assert proposal.read_bytes()==(P/'proposals'/proposal.name).read_bytes()
    sys.path.insert(0,str(proposal.parent))
    import pin_guard
    checked=pin_guard.check_job(json.loads(proposal.read_text().splitlines()[-1]));assert checked['passed']
    return dict(schema='own-runtime.packet58ae.ready.v1',created_utc=datetime.now(timezone.utc).isoformat(),
        implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],stdin=subprocess.DEVNULL,text=True).strip(),
        passed=False,ready_for_device=False,cpu_preparation_complete=False,device_executed=False,
        services_started=False,queued=False,live_queue_changed=False,last_content_write=True,
        build_receipt_sha256=sha(P/'build-receipt.json'),proposal=str(proposal.relative_to(ROOT)),proposal_sha256=sha(proposal),
        completed=dict(host_and_sycl_compile=True,frozen_parent_relinks=True,miniature_byte_repeats=True,
            oracle_failure_before_next_view=True,analyzer_negative_tests=14,shared_entry_report=True,temporary_queue_plan=True,pin_guard=checked),
        missing=['Arm 2 separate miss-stall, resident-slot compute and overlap windows',
                 'changed-engine full-size startup and real queue-to-native argument validation',
                 'device off/on overhead strictly below 2 percent and every-token device oracle parity'],
        blockers=['Mixed expert events cannot identify separate resident/miss intervals; nullable fields remain unknown.',
                  'The device entry has an explicit capability refusal; a saved ready boolean cannot override it.'],
        planned=dict(model_loads=1,views=['A0-off','B0-arm1','A1-off','B1-arm2','A2-off'],prompts_per_view=12,
            token_cap=64,total_expected_seconds_max=900,watchdog_seconds=3600,lane='A',scope='whole-host',hold='existing packet58ab hold only'),
        storage=dict(build_bytes=build['retained_build_bytes'],build_cap_bytes=300_000_000,root_stop_floor_bytes=25_000_000_000),
        qualification='Incomplete CPU preparation. No device run, measured overhead, speed or quality claim.')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));assert sys.argv[1:]==['--write-last']
    save(P/'READY-FOR-DEVICE.json',document());print('Final content write: blocked, ready_for_device=false')

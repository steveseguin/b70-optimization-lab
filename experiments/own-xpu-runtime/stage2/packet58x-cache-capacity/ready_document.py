"""Construct the prospective marker for temporary planning; write it only last."""
from datetime import datetime, timezone
import json
import subprocess
import sys
from build_engine import P, ROOT, sha


def document():
    row=json.loads((P/'READY-FOR-DEVICE.json').read_text())
    build=json.loads((P/'build-receipt.json').read_text())
    args=json.loads((P/'evidence/argument-gate.json').read_text())
    tests=json.loads((P/'evidence/python-cpu-gates.json').read_text())
    proposals=[]
    for arm,tag in [('smoke','smoke'),('max','v5')]:
        name='proposed-p58x-'+tag+'-A.txt'
        local=P/'proposals'/name
        coordinator=P.parents[1]/'ops/lane-queue'/name
        assert local.read_bytes()==coordinator.read_bytes()
        proposals.append(dict(arm=arm,proposal=str(local.relative_to(ROOT)),proposal_sha256=sha(local),
                              coordinator_path=str(coordinator.relative_to(ROOT))))
    row.update(created_utc=datetime.now(timezone.utc).isoformat(),
        implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],stdin=subprocess.DEVNULL,text=True).strip(),
        readiness='Packet58xc CPU reseal complete; fresh smoke proposal first',
        amendment='packet58xc: owned source closure, immutable allowlist, fresh card0-capacity-c outputs',
        build_receipt_sha256=sha(P/'build-receipt.json'),admission_sha256=sha(P/'admission.json'),
        maintenance_decision_sha256=sha(P/'maintenance-decision.json'),proposals=proposals,
        cpu_gates=dict(passed=True,python_checks=tests['checks'],entry_probes=args['checks'],
            sealed_source_count=len(build['sources']),peak_probe_child_rss_bytes=args['peak_child_rss_bytes'],
            native_artifacts_unchanged=True,live_host_admission_passed=True,
            scope='Minimal CPU reseal: owned comparison replay, policy tests, entry interception, build gate and temporary plans; no full-shape, GGUF-reading or device gates'),
        failed_smoke_history='evidence/card0-capacity-a/smoke/',
        fresh_output_root='evidence/card0-capacity-c/',device_executed=False,services_started=False,
        queued=False,live_queue_changed=False,last_content_write=True,
        limitations=['The old smoke passed K1a/K1b then refused before WSCREEN; its evidence is untouched.',
            'Fresh smoke, physical fit, full model output and speed remain pending.',
            'No full-shape, GGUF-reading or native device gate ran during this amendment.',
            'Native executables retain their original hashes; future rebuilds require their usual gates.'])
    return row


if __name__=='__main__':
    assert sys.argv[1:]==['--write-last']
    import window
    from reseal_boundary import check
    check();window.build_gate()
    plans=json.loads((P/'evidence/queue-plans.json').read_text())
    assert plans['passed'] and plans['build_receipt_sha256']==sha(P/'build-receipt.json')
    row=document();row['queue_plans_sha256']=sha(P/'evidence/queue-plans.json')
    row['storage'].update(root_free_bytes=plans['storage']['root_free_bytes'])
    (P/'READY-FOR-DEVICE.json').write_text(json.dumps(row,indent=2)+'\n')
    print('READY-FOR-DEVICE.json written last; nothing queued or launched')

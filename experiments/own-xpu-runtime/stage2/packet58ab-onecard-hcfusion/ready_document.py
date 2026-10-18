"""Write readiness LAST, explicitly refusing the unresolved shared report gate."""
from datetime import datetime,timezone
import json,subprocess,sys
from build_engine import P,ROOT,sha

def document():
    build=json.loads((P/'build-receipt.json').read_text())
    proposals=[]
    for tag in ('smoke','v5'):
        name='proposed-p58ab-'+tag+'-A.txt';local=P/'proposals'/name;external=P.parents[1]/'ops/lane-queue'/name
        assert local.read_bytes()==external.read_bytes()
        proposals.append(dict(proposal=str(local.relative_to(ROOT)),proposal_sha256=sha(local),coordinator_path=str(external.relative_to(ROOT))))
    return dict(schema='own-runtime.packet58ab.ready.v1',created_utc=datetime.now(timezone.utc).isoformat(),
        implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],stdin=subprocess.DEVNULL,text=True).strip(),
        passed=False,ready_for_device=False,cpu_preparation_passed=True,device_executed=False,services_started=False,
        queued=False,live_queue_changed=False,last_content_write=True,
        build_receipt_sha256=sha(P/'build-receipt.json'),proposals=proposals,
        cpu_gates=dict(passed=True,checks=json.loads((P/'evidence/python-cpu-gates.json').read_text())['checks'],
            hc_byte_proofs='GNU and Intel, production shapes, repeats, exceptional values, real capture and request reset',
            native_loader_and_parser_passed=True,real_entry_paths=6,one_card_reports_passed=True),
        required_shared_report_gate=dict(passed=False,reason='Frozen ops/rehearse_entry.py --report only supports two-card screen.main entries; both one-card proposals are rejected before report routing.',
            retained_reports=['evidence/ops-entry-report-smoke.json','evidence/ops-entry-report-v5.json'],
            packet_specific_alternative='evidence/report-gate.json'),
        blocker='Required shared --report gate cannot pass for this one-card entry without changing frozen ops or replacing the runner architecture; no such change is authorized by this brief.',
        storage=dict(build_bytes=build['retained_build_bytes'],stop_floor_bytes=25_000_000_000,build_cap_bytes=300_000_000),
        qualification='CPU proofs and temporary plans only. No device equality, physical fit, speed or record claim.')

def main():
    assert sys.argv[1:]==['--write-last']
    from seal import verify,read
    b=read(P/'build-receipt.json');verify(ROOT,b['sources']);verify(P,b['artifacts']);verify(P,b['gates'])
    plans=read(P/'evidence/queue-plans.json');assert plans['passed'] and plans['build_receipt_sha256']==sha(P/'build-receipt.json')
    row=document();row['queue_plans_sha256']=sha(P/'evidence/queue-plans.json')
    row['temporary_plans_passed']=True
    (P/'READY-FOR-DEVICE.json').write_text(json.dumps(row,indent=2)+'\n')
    print('Final marker written: CPU preparation passed; device readiness BLOCKED by required shared report gate')
if __name__=='__main__':main()

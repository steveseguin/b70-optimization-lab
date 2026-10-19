"""Write readiness LAST after the shared report and temporary pin plans pass."""
from datetime import datetime,timezone
import json,subprocess,sys
from build_engine import P,ROOT,sha

def document():
    entries=json.loads((P/'evidence/entry-gates.json').read_text());assert entries['passed'] and entries['shared_report_passed']
    build=json.loads((P/'build-receipt.json').read_text())
    proposals=[]
    for tag in ('smoke','v5'):
        name='proposed-p58ag-'+tag+'-A.txt';local=P/'proposals'/name;external=P.parents[1]/'ops/lane-queue'/name
        assert local.read_bytes()==external.read_bytes()
        proposals.append(dict(proposal=str(local.relative_to(ROOT)),proposal_sha256=sha(local),coordinator_path=str(external.relative_to(ROOT))))
    return dict(schema='own-runtime.packet58ag.ready.v1',created_utc=datetime.now(timezone.utc).isoformat(),
        implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],stdin=subprocess.DEVNULL,text=True).strip(),
        passed=True,ready_for_device=True,cpu_preparation_passed=True,device_executed=False,services_started=False,
        queued=False,live_queue_changed=False,last_content_write=True,
        build_receipt_sha256=sha(P/'build-receipt.json'),proposals=proposals,
        cpu_gates=dict(passed=True,checks=json.loads((P/'evidence/python-cpu-gates.json').read_text())['checks'],
            hc_byte_proofs='GNU and Intel, production shapes, repeats, exceptional values, real capture and request reset',
            ports_byte_proofs='GNU and Intel: four independent choices and full composition, each repeated; all intermediate/output/status bytes match',
            native_loader_and_parser_passed=True,real_entry_paths=6,one_card_reports_passed=True),
        required_shared_report_gate=dict(passed=True,retained_reports=['evidence/ops-entry-report-smoke.json','evidence/ops-entry-report-v5.json']),
        dimensions=['hc-wide','wide64','wide64+halfcache','other-fusion','ordered-foreground'],hc_fusion_always_on=True,
        excluded_selection_paths=['packet105b two-card target head split','draft and speculative rollback paths'],
        retirement_adaptation='One terminal on each of the two in-order foreground queues; independent maintenance ownership retained',
        halfcache_adaptation='Exhaustive 65536-entry FP32 table; original 820-byte expert rows unchanged',
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
    print('Final marker written: CPU preparation, shared report rehearsal and temporary pin plans passed; nothing queued')
if __name__=='__main__':main()

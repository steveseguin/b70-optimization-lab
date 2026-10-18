"""Verify packet102 CPU readiness without touching devices or live queues."""
import json
from pathlib import Path
from build_engine import P,ROOT,B,limits,sha,save

def main():
    limits()
    import screen_jobs,run_micro
    from common import verify_map
    screen_jobs.verify();run_micro.build_gate();run_micro.execution_gate()
    reports=('build-device-receipt.json','evidence/cpu-byte-identity.json','register-report-offline.json',
        'evidence/lookup-issue-proof.json','evidence/full-shape.json','evidence/full-shape-admission.json',
        'evidence/startup-imports.json','evidence/python-tests.json','evidence/queue-plans.json')
    pins={}
    for name in reports:
        f=P/name;row=json.loads(f.read_text());assert row['passed'] and row['device_executed'] is False,name
        if 'sources' in row:
            assert not any('/ops/packet97-orchestration/' in n for n in row['sources']),name
            verify_map(ROOT,row['sources'])
        if 'artifacts' in row:verify_map(P,row['artifacts'])
        pins[name]=sha(f)
    queue=json.loads((P/'evidence/queue-plans.json').read_text());assert len(queue['plans'])==7 and queue['live_queue_modified'] is False
    for row in queue['plans']:
        f=ROOT/row['proposal'];assert f.name.startswith('proposed-p102-');pins[str(f.relative_to(P.parents[3]))]=sha(f)
    for name in screen_jobs.VIEWS:
        v=P/'compat/packet64-record-bundle/selections'/name
        row=json.loads((v/'screen-seal.json').read_text());verify_map(ROOT,row['sources']);verify_map(v,row['artifacts'])
        assert not any('/ops/packet97-orchestration/' in n for n in row['sources'])
    import micro_gate
    completed=(P/'evidence/micro-B/window.json').exists()
    micro=micro_gate.measured(P) if completed else None
    if completed:
        assert not micro['qualified'], 'unexpected winner needs a different handoff'
        try:micro_gate.require_qualified(P)
        except ValueError as e:assert 'no candidate passed' in str(e)
        else:raise AssertionError('screens must refuse this result')
        pins.update(micro['bindings'])
    size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file());assert size<=300_000_000,size
    save(P/'evidence/final-verification.json',dict(passed=True,device_executed=False,build_logical_bytes=size,
        evidence=pins,sealed_views=list(screen_jobs.VIEWS),proposal_count=7,record_lane='A',
        device_micro_pending=not completed,coordinator_micro_observed=completed,
        qualified_candidates=micro["qualified"] if completed else None,
        model_speed_pending=True,record_chain_ready=False,
        scope='CPU preparation; independently completed coordinator micro rejects all screens; not record-chain qualification' if completed else 'CPU-ready micro and conditional screens'))
    print('Final CPU verification PASS: four seals, seven proposals, no mutable p97 orchestration pins; build bytes',size)
if __name__=='__main__':main()

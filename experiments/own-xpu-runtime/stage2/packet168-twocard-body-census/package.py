"""Write blocked proposal rows and immutable source seal; never enqueue."""
import json,shutil,subprocess,tempfile
from pathlib import Path
from build_engine import P,ROOT,limits,save,sha
from census_contract import ORDER
OPS=P.parents[1]/'ops'
BLOCKERS=[
 'Native probe is isolated target-half replay, not the requested matched bundle8 interval.',
 'Cross-card transfer arm intentionally refuses; both target head partitions/merge are not covered.',
 'Fused router/shared-activation and shared-down/combine require explicit class ownership or overlapping-intervention labels.',
 'Full real arm sequence, K1a/K1b and all12-prompt exact native control views are not implemented/qualified.',
 'No device census measurement or measured ranked lever list exists.'
]
def seal():
    selected={}
    for f in sorted(P.rglob('*')):
        if not f.is_file():continue
        rel=f.relative_to(P)
        if rel.parts[0]=='build' or '__pycache__' in rel.parts or rel.parts[0]=='evidence':continue
        if f.name in ('seal.json','READY-FOR-DEVICE.json'):continue
        selected[str(rel)]=sha(f)
    selected['build/device/own-rt-iq3']=sha(P/'build/device/own-rt-iq3')
    save(P/'seal.json',dict(arithmetic='iq3-p49-split32-v1',files_sha256=selected))
def main():
    limits()
    save(P/'qualification.json',dict(ready_for_device=False,blockers=BLOCKERS,
      control_exactness='pending device; no control skipped',measured_ranked_table_available=False,
      no_optional_smoke='No optional smoke is proposed. Required opening K1a/K1b and exact control are still missing; this is a blocker, not a waiver.'))
    parent=json.loads((P.parent/'packet165-warm-prefill/two-card/budget.json').read_text())
    measured=parent['measured_parent_retained_bytes']+parent['measured_max_raw_state_bytes']
    save(P/'budget.json',dict(measured_parent_peak_bytes=measured,
      measured_parent='packet136 WS128 retained bytes plus largest raw state snapshot',
      planned_write_bytes=2*measured,planning_multiplier=2,device_floor_bytes=25_000_000_000,
      cpu_stop_bytes=27_000_000_000,host_required_available_bytes=parent['host_required_available_bytes'],
      expected_seconds=[600,900],wait_seconds=600,cold_phase_reference_seconds=60,
      cold_phase_note='Inherited conservative parent floor; no new measured cold phase',
      watchdog_seconds=7200,wall_clock_data_proof_limit=None,
      unqualified_diagnostic_snapshot_memory=True))
    identity=json.loads((P/'identity.json').read_text())
    identity.update(measurement_protocol='packet168 diagnostic census prototype; NOT DEVICE READY',
      binary_sha256=sha(P/'build/device/own-rt-iq3'),native_delta='optional diagnostic command20 and rank1 snapshot allocation; inactive on normal controls',
      record='packet136 bundle8',record_tok_s=58.798108759182306)
    save(P/'identity.json',identity)
    seal();budget=json.loads((P/'budget.json').read_text())
    for lane in ('B','A'):
        name=f'packet168-body-census-{lane}-v1'
        job=dict(name=name,lane=lane,
          argv=['/usr/bin/python3','-B',str((P/'entry.py').relative_to(ROOT)),
            '--lane',lane,'--kind','census','--output',str(P/'evidence'/f'device-census-{lane}-v1'),
            '--fault-review','{REVIEW}','--authorized-device-window'],
          env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)),
          planned_write_bytes=budget['planned_write_bytes'],
          plan=dict(host_required_available_bytes=budget['host_required_available_bytes'],expected_seconds=[600,900],watchdog_seconds=7200,
            qualification='BLOCKED: READY false; proposal retained for review, not runnable',
            entry_rehearsal=dict(binaries=[dict(path=str((P/'build/device/own-rt-iq3').relative_to(ROOT)),
              sha256=sha(P/'build/device/own-rt-iq3'),args=['--help'],returncode=0,contains='Options:')],
              preparation_probe_note='Partial native lifecycle only. Complete requested arm sequence is not qualified.')))
        proposal=OPS/'lane-queue'/f'proposed-p168-body-census-{lane}-v1.txt'
        proposal.write_text('# BLOCKED prototype, not queued. Choose B; A is an alternative twin, never a second load.\n'+json.dumps(job)+'\n')
        save(P/'lineage'/f'proposal-{lane}.json',job)
    seal()
    print('Blocked lane B and A twin proposals written; no live queue changed')
if __name__=='__main__':main()

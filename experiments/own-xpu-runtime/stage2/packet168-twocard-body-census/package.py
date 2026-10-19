"""Write blocked proposal rows and immutable source seal; never enqueue."""
import json,shutil,subprocess,tempfile
from pathlib import Path
from build_engine import P,ROOT,limits,save,sha
from census_contract import ORDER
OPS=P.parents[1]/'ops'
BLOCKERS=[]  # filled only by failed gates; finalize.py refuses READY if any remain
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
DIAGNOSTIC_LABELS=('card0:speculative-private-image','card0:speculative-copy-table')
def census_memory_plan():
    """Parent plan plus the MEASURED rank1 diagnostic snapshot backing.

    The native CPU fixture allocates through the production arena with
    --census-probe. Rank0 always owns this image; on rank1 it exists only for
    the diagnostic. Its exact bytes come from the rank1 fixture census and
    are added to rank1's planned reserve; every parent margin rule re-applies."""
    import memory_gate
    native=json.loads((P/'evidence/native-lifecycle.json').read_text())
    census={r['rank']:json.loads((Path(r['output'])/'census.json').read_text()) for r in native['results']}
    def labelled(rank):
        rows=[a for a in census[rank]['allocations'] if a['label'] in DIAGNOSTIC_LABELS and a['live'] and a['memory']=='device']
        assert sorted(a['label'] for a in rows)==sorted(DIAGNOSTIC_LABELS),(rank,rows)
        return sum(a['bytes'] for a in rows)
    rank0=labelled(0);backing=labelled(1);assert 0<backing<512*1024**2,backing
    # Validate fixture image sizing against REAL device evidence: parent rank0.
    rel='packet165-warm-prefill/two-card/evidence/device-warm512-B-a/run/ranks/rank0/census.json'
    device=json.loads((P.parent/rel).read_text())
    device_rank0=sum(a['bytes'] for a in device['allocations'] if a['label'] in DIAGNOSTIC_LABELS and a['live'])
    assert device_rank0==rank0,('fixture image differs from real device rank0 image',device_rank0,rank0)
    parent_record=dict(name='census.json',parent_relpath='stage2/'+rel,parent_digest=sha(P.parent/rel),
      device_rank0_image_bytes=device_rank0,fixture_rank0_image_bytes=rank0)
    plan=json.loads((P/'memory-plan.json').read_text())
    r=plan['placements']['1']['capacities']['4096']['ranks'][1]
    for key in ('allocation_reserve_bytes','target_total_bytes','total_with_mtp_bytes'):r[key]+=backing
    r['free_with_mtp_bytes']-=backing
    plan['scope']=plan['scope']+'; packet168 census adds measured rank1 diagnostic snapshot backing '+str(backing)+' bytes'
    plan['packet168_rank1_diagnostic_backing_bytes']=backing
    memory_gate.configuration(plan,4096,1,0)  # parent margin rules: 30 GiB arena, >=1.5 GB free
    save(P/'memory-plan-census.json',plan)
    return dict(rank0_image_bytes_always_present=rank0,rank1_backing_bytes=backing,
      rank1_planned_total_with_mtp_bytes=r['total_with_mtp_bytes'],rank1_planned_free_bytes=r['free_with_mtp_bytes'],
      rank1_arena_headroom_bytes=memory_gate.ARENA_LIMIT_BYTES-r['total_with_mtp_bytes'],
      device_validation=parent_record,
      source='CPU fixture production-arena census (diagnostic labels only); rank0 image equals real device rank0 image; device residency unmeasured')
def main():
    limits()
    import census_contract as C
    memory=census_memory_plan()
    save(P/'qualification.json',dict(ready_for_device=None,blockers=BLOCKERS,
      control_exactness='C0/C1/C2 x 12 prompts must equal the iq3-p49-split32-v1 oracle prefix in-run; no control skipped',
      measured_ranked_table_available=False,measured_classes=list(C.CLASSES),
      fused_class='router_shared_expert = route+shared activation and shared-down+mixture launches (one fused class)',
      residual='exact native control ms/token minus sum of six isolated body-pass marginals; transfer, split head and overlap are not causally isolated',
      dropped_to_residual=['cross-card transfer','split head/argmax/merge'],memory=memory,
      no_optional_smoke='No optional smoke. The run opens with an excluded distinct warm-up and the exact C0 control on all 12 prompts; any oracle mismatch stops the run.'))
    parent=json.loads((P.parent/'packet165-warm-prefill/two-card/budget.json').read_text())
    requests=1+len(C.ORDER)*len(C.IDS)+1
    per_request=parent['measured_parent_retained_bytes']/14  # parent: warm-up + 12 + prefill + final reset
    measured=int(requests*per_request+parent['measured_max_raw_state_bytes'])
    save(P/'budget.json',dict(measured_parent_peak_bytes=parent['measured_parent_retained_bytes']+parent['measured_max_raw_state_bytes'],
      measured_parent='packet136 WS128 retained bytes plus largest raw state snapshot',
      projected_census_bytes=measured,projection=f'{requests} resets x parent retained bytes per request + one raw state snapshot',
      planned_write_bytes=2*measured,planning_multiplier=2,device_floor_bytes=25_000_000_000,
      cpu_stop_bytes=27_000_000_000,host_required_available_bytes=parent['host_required_available_bytes'],
      expected_seconds=[900,2400],wait_seconds=600,controller_wait_seconds=1200,cold_phase_reference_seconds=60,
      cold_phase_note='parent measured cold-phase floor 60 s; native wait 600 s = 10x, controller wait 1200 s = 20x',
      watchdog_seconds=7200,wall_clock_data_proof_limit=None,diagnostic_snapshot_memory=memory))
    identity=json.loads((P/'identity.json').read_text())
    identity.update(measurement_protocol='packet168 partial body census: exact native controls + six isolated body-class probes; diagnostic only',
      binary_sha256=sha(P/'build/device/own-rt-iq3'),native_delta='optional diagnostic command20 and rank1 snapshot allocation (--census-probe); controls run unchanged kernels and are oracle-exact in-run',
      record='packet136 bundle8',record_tok_s=58.798108759182306,measurement_delta=['--census-probe diagnostic command20','64-token exact controls','pre-device --help'])
    save(P/'identity.json',identity)
    seal();budget=json.loads((P/'budget.json').read_text())
    for lane in ('B','A'):
        name=f'packet168-body-census-{lane}-v2'
        job=dict(name=name,lane=lane,
          argv=['/usr/bin/python3','-B',str((P/'entry.py').relative_to(ROOT)),
            '--lane',lane,'--kind','census','--output',str(P/'evidence'/f'device-census-{lane}-v2'),
            '--fault-review','{REVIEW}','--authorized-device-window'],
          env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)),
          planned_write_bytes=budget['planned_write_bytes'],
          plan=dict(host_required_available_bytes=budget['host_required_available_bytes'],expected_seconds=budget['expected_seconds'],watchdog_seconds=7200,
            qualification='diagnostic census; arms never reported as speed; READY-FOR-DEVICE.json binds the seal',
            entry_rehearsal=dict(binaries=[dict(path=str((P/'build/device/own-rt-iq3').relative_to(ROOT)),
              sha256=sha(P/'build/device/own-rt-iq3'),args=['--help'],returncode=0,contains='Options:')],
              preparation_probe_note='Native CPU fixture: six-class arm sequence x12 prompts x3 repeats on both ranks with real snapshot copies; worker_gate.py drives the real worker sequence.')))
        proposal=OPS/'lane-queue'/f'proposed-p168-body-census-{lane}-v2.txt'
        proposal.write_text('# packet168 partial body census. Choose B (cards 2+3); A is an alternative twin, never a second load. Not queued.\n'+json.dumps(job)+'\n')
        save(P/'lineage'/f'proposal-{lane}.json',job)
    seal()
    print('Lane B and A twin proposals written; no live queue changed')
if __name__=='__main__':main()

#!/usr/bin/env python3
"""CPU replay of retained 58b snapshots; synthetic crossings labeled separately."""
import json
from pathlib import Path
import window as W
import memory_plan as M

P=Path(__file__).resolve().parent
E=P/'evidence/58b-kd'

def main():
    budget=M.plan(); old=json.loads((E/'window.json').read_text())
    baseline=old['memory_admission']['baseline_gpuactive_bytes']
    tracker=W.PinnedExpertProgress(E/'run/run/progress.jsonl',budget)
    pinned=tracker.read()
    snapshots=[json.loads(line) for line in (E/'run/run/host-memory.jsonl').read_text().splitlines()]
    snapshots.append(dict(old['memory_last_sample']['host'],phase='last_supervisor_sample_during_drain'))
    replay=[]
    for snapshot in snapshots:
        # Credit zero because no timestamp ties progress to these observations.
        sample=dict(root_seen=True,anonymous_bytes=old['memory_last_sample']['anonymous_bytes'])
        W.account_memory(sample,snapshot,baseline,0,budget)
        replay.append(dict(phase=snapshot['phase'],sample=sample,passed=True,
                           rss_replay='conservative shared last retained RSS, not a per-snapshot measurement'))
    cumulative=0;layers=[]
    for line in (E/'run/run/progress.jsonl').read_text().splitlines():
        row=json.loads(line)
        if row.get('phase')=='pinned-expert':
            cumulative+=row['bytes']
            if 'ffn_down_exps' in row['name']:
                layers.append(dict(layer=int(row['name'].split('.')[1]),cumulative_pinned_bytes=cumulative))
    synthetic=[]
    cap=budget['device_owned_bound_bytes']
    for label,pins,growth,anon,expected in [
        ('completed_26_layers_only',pinned,pinned,0,True),
        ('full_pins_plus_shadow_limit',budget['census']['pinned_expert_bytes'],budget['census']['pinned_expert_bytes']+cap,0,True),
        ('true_shadow_one_byte_over',pinned,pinned+cap+1,0,False),
        ('combined_one_byte_over',budget['census']['pinned_expert_bytes'],budget['census']['pinned_expert_bytes']+cap,
         sum(budget['host_categories'][k] for k in ('loader_staging_bound','process_workspace_bound','cache_metadata_bound'))+1,False),
    ]:
        sample=dict(root_seen=True,anonymous_bytes=anon)
        error=None
        try:W.account_memory(sample,{'MemAvailable':M.HOST_RESERVE,'GPUActive':baseline+growth},baseline,pins,budget)
        except ValueError as exc:error=str(exc)
        assert (error is None)==expected
        synthetic.append(dict(label=label,synthetic=True,expected_pass=expected,matched_expectation=True,error=error,sample=sample))
    row=dict(schema='own-runtime.packet58c.sensor-replay.v1',passed=True,device_executed=False,
        source_sha256={str(f.relative_to(W.REPO)):W.sha(f) for f in sorted(E.rglob('*')) if f.is_file()},
        source_files_sha256={str((P/f).relative_to(W.REPO)):W.sha(P/f) for f in ('window.py','memory_plan.py','replay_sensor.py')},
        pinned_completed_bytes=pinned,pinned_banks=len(tracker.seen),untimed_layer_progress=layers,
        old_shadow_bound_bytes=cap,excess_of_completed_pins_over_old_shadow_bound_bytes=pinned-cap,
        actual_snapshots_replayed=replay,synthetic_cases=synthetic,
        old_stop_reasons=old['stop_reasons'],environment=old['environment'],
        neo_override_present=any(k in old['environment'] for k in ('NEOReadDebugKeys','EnableDeferBacking')),
        limitation='Failing GPUActive sample not retained. Only two endpoint snapshots and last supervisor sample survive. Progress has no timestamps. Mechanism consistent, not proven by aligned samples.',
        safe_to_exit=json.loads((E/'run/run/receipt.json').read_text()).get('safe_to_exit'),
        native_binary_unchanged=True,host_required_available_bytes=budget['host_required_available_bytes'],host_reserve_bytes=M.HOST_RESERVE)
    (P/'evidence/sensor-replay.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps(dict(passed=True,actual_samples=len(replay),synthetic_cases=len(synthetic),pinned_completed_bytes=pinned)))

if __name__=='__main__':main()

"""Offline attempt 4-6 attribution. Stdlib only; no model payload/runtime reads.

Observed counters, allocation payloads and assumed allocator reservation sizes
are separate. This is a planning estimate, never an admission or speed result.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
GIB = 1 << 30
ROW = {'w13_weight': 3276800, 'w2_weight': 1638400}


def rounded(size):
    if type(size) is not int or size < 0:
        raise ValueError('nonnegative integer allocation required')
    return 1 << (size-1).bit_length() if size else 0


def expert_plan(placement):
    return [dict(rank=r, layer=l, parameter=p, host_rows=len(placement[str(r)][str(l)]),
                 host_bytes=len(placement[str(r)][str(l)])*width,
                 reserved_bytes=rounded(len(placement[str(r)][str(l)])*width))
            for r in range(4) for l in range(48) for p, width in ROW.items()]


def read_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def boundary_alternative(placement, rank, row_limit=64):
    """Small CPU knapsack: size-class savings, not a speed/routing prediction.

    Counts only; no launch mask is written and no particular expert is removed.
    Every moved row remains in VRAM. Rank zero is deliberately excluded.
    """
    if rank not in (1, 2, 3):
        raise ValueError('rank zero remains unchanged')
    states = {0: (0, [])}
    for layer in range(48):
        n = len(placement[str(rank)][str(layer)])
        if not n:
            continue
        target = (rounded(n*ROW['w13_weight'])//2)//ROW['w13_weight']
        cost = n-target
        saving = sum(rounded(n*w)-rounded(target*w) for w in ROW.values())
        updated = dict(states)
        for c, (s, path) in states.items():
            if c+cost <= row_limit and s+saving > updated.get(c+cost, (-1,))[0]:
                updated[c+cost] = (s+saving, path+[dict(layer=layer, before=n, after=target)])
        states = updated
    cost, (saving, changes) = max(states.items(), key=lambda item: (item[1][0], -item[0]))
    return dict(rank=rank, moved_rows=cost, vram_growth_bytes=cost*sum(ROW.values()),
                host_reserved_saving_bytes=saving, layer_counts=changes,
                implemented=False, quality_tested=False)


def analyze(run):
    run = Path(run)
    samples = [s for s in read_lines(run/'host-memory-samples.jsonl') if 'mem_total_bytes' in s]
    files = sorted(run.glob('loader-*.jsonl'))
    events = sorted([dict(e, source=f.name) for f in files for e in read_lines(f)],
                    key=lambda e: e['monotonic'])
    pid_rank = {int(pid): int(rank) for rank, pid in
                re.findall(r'Worker_TP(\d+)_EP\d+ pid=(\d+)', (run/'server.log').read_text())}
    begins = [e['monotonic'] for e in events if e['event'] == 'load_begin']
    begin = min(begins) if begins else None
    refusal = next((e for e in events if e['event'] == 'allocation_refused'), None)
    cancel = min((e['monotonic'] for e in events if e['event'] == 'cancel_requested'), default=float('inf'))
    binding = min((e['monotonic'] for e in events if e['event'] == 'PLE_mmap_bound'), default=float('inf'))
    allocations = [e for e in events if e['event'] == 'v5_allocated']
    curve = []
    for s in samples:
        t = s['monotonic']
        completed = [e for e in allocations if e['monotonic'] <= t]
        ple = [e for e in events if e['event'] == 'PLE_mmap_bound' and e['monotonic'] <= t]
        phase = ('cancellation_and_drain' if t >= cancel else
                 'startup_or_init_device' if begin is None or t < begin else
                 'mixed_construction_and_rank3_checkpoint_copy' if t >= binding else 'construction')
        curve.append(dict(monotonic=t, seconds_from_constructor=None if begin is None else t-begin,
                          phase=phase, pressure_bytes=s['accounted_pressure_bytes'],
                          mem_available_bytes=s['mem_available_bytes'],
                          **{k: s['meminfo_bytes'].get(k) for k in
                             ('GPUActive', 'AnonPages', 'Cached', 'Shmem', 'Unevictable', 'Mlocked')},
                          worker_rss_bytes=s['worker_rss_bytes'],
                          cgroup_anon_bytes=(s.get('cgroup_memory_stat') or {}).get('anon'),
                          completed_parameters=len(completed),
                          expert_payload_bytes=sum(e['host_bytes'] for e in completed),
                          expert_reserved_assumption_bytes=sum(rounded(e['host_bytes']) for e in completed),
                          expert_device_payload_bytes=sum(e['device_bytes'] for e in completed),
                          ple_bound_ranks=len(ple),
                          ple_cache_bytes=sum(e['pinned_cache_bytes'] for e in ple),
                          ple_metadata_bytes=sum(e['metadata_bytes'] for e in ple)))
    progress = []
    for pid, rank in sorted(pid_rank.items(), key=lambda item: item[1]):
        own = [e for e in allocations if e['pid'] == pid]
        if own:
            progress.append(dict(rank=rank, pid=pid, parameters=len(own),
                completed_layers=[int(e['layer'].split('.layers.')[1].split('.')[0])
                                  for e in own if e['parameter'] == 'w2_weight'],
                host_payload_bytes=sum(e['host_bytes'] for e in own),
                host_reserved_assumption_bytes=sum(rounded(e['host_bytes']) for e in own),
                ple_bound=any(e['event'] == 'PLE_mmap_bound' and e['pid'] == pid for e in events)))
    source_files = [run/'host-memory-samples.jsonl', run/'server.log', run/'launch.json',
                    run/'host-memory-prediction.json', *files]
    if (run/'staging-live.json').exists():
        source_files.append(run/'staging-live.json')
    return dict(run=run.name, input_sha256={f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in source_files},
                first_refusal=refusal, rank_progress=progress,
                allocation_snapshot_files=[p.name for p in sorted(run.glob('allocations-rank*.json'))],
                reached_events=sorted({e['event'] for e in events}),
                staging=json.loads((run/'staging-live.json').read_text()) if (run/'staging-live.json').exists() else None,
                phase_peaks={phase: max([s for s in curve if s['phase'] == phase], key=lambda s:s['pressure_bytes'])
                             for phase in dict.fromkeys(s['phase'] for s in curve)},
                peak=max(curve, key=lambda s:s['pressure_bytes']), curve=curve)


def build_budget(report, placement, contract):
    plan = expert_plan(placement)
    anchor = report['peak']
    # The post-refusal sample is 229 ms later; receipts have all drained but
    # the matching GPUActive still holds the allocations. No plateau measured.
    ranks = [dict(rank=r, payload_bytes=sum(e['host_bytes'] for e in plan if e['rank'] == r),
                  reserved_assumption_bytes=sum(e['reserved_bytes'] for e in plan if e['rank'] == r))
             for r in range(4)]
    final_experts = sum(r['reserved_assumption_bytes'] for r in ranks)
    remaining = dict(expert_reserved_bytes=final_experts-anchor['expert_reserved_assumption_bytes'],
                     ple_cache_bytes=4*contract['ple_cache_bytes_per_rank']-anchor['ple_cache_bytes'],
                     ple_metadata_bytes=contract['ple_metadata_bytes']-anchor['ple_metadata_bytes'])
    plateau = anchor['pressure_bytes']+sum(remaining.values())
    embedding = 4*rounded(contract['pinned_input_embedding_bytes_per_rank'])
    steps = 4*rounded(163840)
    unexplained_gpu = anchor['GPUActive']-anchor['expert_reserved_assumption_bytes']-embedding-anchor['ple_cache_bytes']-steps
    alternatives = [boundary_alternative(placement, r) for r in (1, 2, 3)]
    caches = []
    for total_gib in (2, 1, .5):
        per_rank = int(total_gib*GIB)//4
        meta = contract['ple_rows']*4 + 4*(per_rank//contract['ple_row_bytes'])*17
        saving = (4*contract['ple_cache_bytes_per_rank']-4*per_rank
                  +contract['ple_metadata_bytes']-meta)
        caches.append(dict(total_cache_gib=total_gib, saving_bytes=saving,
                           projected_plateau_bytes=plateau-saving, implemented=False))
    return dict(prediction_is_measurement=False, qualified=False, launch_prepared=False,
                reason='Original placement plateau exceeds 97 GB; do not raise loading guard to 96 GB.',
                expert_ranks=ranks, expert_reserved_total_bytes=final_experts,
                embedding_reserved_bytes=embedding, ple_cache_bytes=4*contract['ple_cache_bytes_per_rank'],
                ple_step_reserved_bytes=steps, ple_metadata_bytes=contract['ple_metadata_bytes'],
                anchor_pressure_bytes=anchor['pressure_bytes'], remaining_retained_growth_bytes=remaining,
                anchor_unattributed_gpu_bytes=unexplained_gpu,
                anchor_cgroup_anon_excluding_bound_ple_metadata_bytes=anchor['cgroup_anon_bytes']-anchor['ple_metadata_bytes'],
                plateau_scenario_bytes=plateau,
                loading_scenario_bytes=plateau+contract['global_staging_bytes'],
                loading_extra_retention_2gib_sensitivity_bytes=plateau+contract['global_staging_bytes']+2*GIB,
                page_cache_speed_allowance_bytes=contract['active_file_allowance_bytes'],
                plateau_plus_additional_speed_cache_bytes=plateau+contract['active_file_allowance_bytes'],
                exact_watchdog_pressure_line_bytes=124179132416-24*GIB,
                smaller_cache_sensitivities=caches,
                boundary_alternatives=alternatives,
                boundary_alternative_plateau_bytes=plateau-sum(a['host_reserved_saving_bytes'] for a in alternatives),
                caveats=['Power-of-two reservation is source-supported and sample-correlated, not allocator telemetry.',
                         'Anchor retains existing runtime/OS/file-accounting residual; never add RSS or GPUActive again.',
                         'Remaining PLE metadata charged in full; future constructor/private/capture retention unknown.',
                         '256 MiB is explicit staging cap, not a bound on all loader retention.',
                         'File cache is reclaimable; speed working set cannot be learned from a no-generation load.',
                         'All checkpoint copy completion bytes unknown: receipts lack tensor names/copy completion census.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reports = [analyze(HERE/f'runs/screen1b-mmap-calibrate-load-20261008-attempt{n}') for n in (4, 5, 6)]
    placement = json.loads((HERE/'placement-attempt6-v5.json').read_text())
    contract = json.loads((HERE/'memory-contract.json').read_text())
    output = dict(schema='screen1b.host-allocation-attribution.v1', attempts=reports,
                  budget=build_budget(reports[-1], placement, contract),
                  input_sha256={name: hashlib.sha256((HERE/name).read_bytes()).hexdigest()
                                for name in ('placement-attempt6-v5.json', 'memory-contract.json', 'analyze_host_budget.py')})
    args.output.write_text(json.dumps(output, indent=2)+'\n')
    with args.output.with_suffix('.csv').open('w') as f:
        writer = csv.DictWriter(f, ['attempt', *reports[0]['curve'][0]])
        writer.writeheader()
        for n, report in zip((4, 5, 6), reports):
            writer.writerows(dict(attempt=n, **r) for r in report['curve'])
    print(json.dumps(output['budget'], indent=2))


if __name__ == '__main__':
    main()

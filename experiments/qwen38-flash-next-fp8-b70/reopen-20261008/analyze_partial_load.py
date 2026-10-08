"""Reconstruct an aborted load from saved CPU receipts; never contact runtime.

Whole-host pressure is MemTotal minus MemAvailable. Event allocation sizes,
RSS and cgroup counters overlap and must not be added to it. No extrapolation.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def read_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def analyze(run):
    run = Path(run)
    sample_file = run/'host-memory-samples.jsonl'
    samples = read_lines(sample_file)
    loader_files = sorted(run.glob('loader-*.jsonl'))
    events = sorted([dict(e, source=f.name, line=i+1)
                     for f in loader_files for i, e in enumerate(read_lines(f))],
                    key=lambda e: e['monotonic'])
    begin = min(e['monotonic'] for e in events if e['event'] == 'load_begin')
    refusal = next(e for e in events if e['event'] == 'allocation_refused')
    failure = refusal['monotonic']
    prediction = json.loads((run/'host-memory-prediction.json').read_text())
    rows = []
    for s in samples:
        if 'error' in s:
            continue
        t = s['monotonic']
        placed = [e for e in events if e['event'] == 'v5_allocated' and e['monotonic'] <= t]
        rows.append(dict(
            source=sample_file.name, monotonic=t, seconds_from_constructor=t-begin,
            phase=('runtime_startup' if t < begin else
                   'partial_model_construction' if t < failure else 'failure_and_drain'),
            pressure_bytes=s['mem_total_bytes']-s['mem_available_bytes'],
            mem_available_bytes=s['mem_available_bytes'],
            gpu_active_bytes=s.get('meminfo_bytes', {}).get('GPUActive'),
            cgroup_current_bytes=s.get('cgroup_memory_current_bytes'),
            worker_rss_bytes=s.get('worker_rss_bytes'),
            completed_v5_parameters=len(placed),
            completed_v5_host_bytes=sum(e['host_bytes'] for e in placed),
            completed_v5_device_bytes=sum(e['device_bytes'] for e in placed)))
    refusal_row = dict(
        source=f"{refusal['source']}:{refusal['line']}", monotonic=failure,
        seconds_from_constructor=failure-begin, phase='allocation_refusal',
        pressure_bytes=refusal['MemTotal']-refusal['MemAvailable'],
        mem_available_bytes=refusal['MemAvailable'], next_bytes=refusal['next_bytes'])
    before = [r for r in rows if r['monotonic'] < failure]
    phase_summary = {}
    for phase in ('runtime_startup', 'partial_model_construction', 'failure_and_drain'):
        subset = [r for r in rows if r['phase'] == phase]
        phase_summary[phase] = dict(sample_count=len(subset),
            peak=max(subset, key=lambda r:r['pressure_bytes']) if subset else None)
    rank_progress = {}
    for f in loader_files:
        allocated = [e for e in events if e['source'] == f.name and e['event'] == 'v5_allocated']
        if allocated:
            rank_progress[f.name] = dict(
                completed_parameters=len(allocated), last_layer=allocated[-1]['layer'],
                host_bytes=sum(e['host_bytes'] for e in allocated),
                device_bytes=sum(e['device_bytes'] for e in allocated))
    baseline = json.loads((run/'memory-after-hash.json').read_text())['accounted_pressure_bytes']
    pressure = refusal_row['pressure_bytes']
    pins = sum(p['host_bytes'] for p in rank_progress.values())
    files = [sample_file, *loader_files, run/'staging-live.json', run/'host-memory-prediction.json',
             run/'memory-before-hash.json', run/'memory-after-hash.json', run/'server.log',
             run/'calibration-load.json', run/'container-exit.json']
    return dict(
        schema='screen1b.partial-load-analysis.v1', run=str(run),
        input_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        definition='pressure_bytes = MemTotal - MemAvailable; overlapping counters are not summed',
        first_refusal=refusal, refusal_observation=refusal_row,
        first_cancel=next(e for e in events if e['event']=='cancel_requested'),
        phase_summary=phase_summary, rank_progress=rank_progress,
        allocation_snapshot_files=[p.name for p in sorted(run.glob('allocations-rank*.json'))],
        staging=json.loads((run/'staging-live.json').read_text()),
        reached_events=sorted({e['event'] for e in events}),
        prediction_comparison=dict(
            illustrative_complete_peak_bytes=prediction['illustrative_host_peak_bytes'],
            observed_partial_pressure_bytes=pressure,
            distance_to_illustrative_peak_bytes=prediction['illustrative_host_peak_bytes']-pressure,
            post_hash_baseline_bytes=baseline, increase_from_post_hash_bytes=pressure-baseline,
            predicted_final_pins_bytes=prediction['final_pins_total_bytes'],
            completed_expert_host_bytes=pins,
            baseline_and_completed_expert_pins_unattributed_bytes=pressure-baseline-pins,
            interpretation='Partial construction only; not a complete peak, fit, attribution, or prediction error. '
                           'Unattributed residual includes unreceipted allocations and overlapping runtime/driver costs.'),
        curve=rows, pre_failure_sample_peak=max(before, key=lambda r:r['pressure_bytes']),
        limitation='No completed allocation snapshots, PLE binding, checkpoint copy, postprocessing, MTP, KV, '
                   'capture or ready plateau; VRAM reserve unknown. Original sampler labels drain as loading. '
                   'Phase reconstruction uses loader monotonic timestamps, not log print order.')


def write_report(report, output):
    output.write_text(json.dumps(report, indent=2)+'\n')
    fields = ('source', 'monotonic', 'seconds_from_constructor', 'phase', 'pressure_bytes',
              'mem_available_bytes', 'gpu_active_bytes', 'cgroup_current_bytes', 'completed_v5_parameters',
              'completed_v5_host_bytes', 'completed_v5_device_bytes', 'next_bytes')
    with output.with_suffix('.csv').open('w') as f:
        writer = csv.DictWriter(f, fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(sorted([*report['curve'], report['refusal_observation']],
                               key=lambda r:r['monotonic']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.run)
    write_report(report, args.output)
    print(json.dumps({k:report[k] for k in ('refusal_observation','prediction_comparison','rank_progress')}, indent=2))

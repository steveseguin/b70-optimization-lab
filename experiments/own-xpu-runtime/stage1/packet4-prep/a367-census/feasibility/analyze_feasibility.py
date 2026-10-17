#!/usr/bin/env python3
"""CPU-only analysis of synchronized microtest Chrome spans and rank receipts."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
from common import write_json

MARKER = re.compile(r'(?:^|::)A367Feas\|(eager|replay)\|i=(\d+)$')


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def complete_events(events):
    """Unitrace emits X; also accept ordinary Chrome same-thread B/E pairs."""
    stacks, result, issues = {}, [], []
    for event in events:
        phase = event.get('ph')
        if phase == 'X':
            if number(event.get('ts')) and number(event.get('dur')) and event['dur'] >= 0:
                result.append(event)
            else:
                issues.append('invalid complete-event timestamps')
        elif phase in ('B', 'E'):
            key = (event.get('pid'), event.get('tid'))
            stack = stacks.setdefault(key, [])
            if phase == 'B':
                stack.append(event)
            elif stack:
                start = stack.pop()
                if number(event.get('ts')) and number(start.get('ts')) and event['ts'] >= start['ts']:
                    result.append(dict(start, ph='X', dur=event['ts'] - start['ts']))
                else:
                    issues.append('invalid B/E timestamps')
            else:
                issues.append('unmatched E')
    if any(stacks.values()):
        issues.append('unclosed B')
    return result, issues


def graph_events(events):
    complete, issues = complete_events(events)
    spans = []
    for event in complete:
        match = MARKER.search(event.get('name', ''))
        if match:
            spans.append((match[1], int(match[2]), event))
    # gpu_op is PTI's device lane category. Host API/graph-submit/flow events
    # never count as kernels, even if their names contain the word "kernel".
    device = [e for e in complete if e.get('cat') == 'gpu_op' and e['dur'] > 0]
    if any(not e.get('name') for e in device):
        issues.append('unnamed device event; kernel-name agreement is unproven')
    buckets = {}
    for phase, index, span in spans:
        key = (phase, index)
        if key in buckets:
            issues.append(f'duplicate marker {phase}/{index}')
        buckets.setdefault(key, [])
    outside = 0
    for event in device:
        matches = [(phase, index) for phase, index, span in spans
                   if event['ts'] >= span['ts'] and
                   event['ts'] + event['dur'] <= span['ts'] + span['dur']]
        if len(matches) == 1:
            buckets[matches[0]].append(event)
        elif matches:
            issues.append('device event in ambiguous iteration spans')
        else:
            outside += 1  # warmup/capture are deliberately outside measurement
    phases = {}
    for phase in ('eager', 'replay'):
        iterations = []
        for (p, index), values in sorted(buckets.items()):
            if p != phase:
                continue
            copies = [e for e in values if re.search(r'mem(?:ory)?(?:copy|fill)|memcpy', e.get('name', ''), re.I)]
            kernels = [e for e in values if e not in copies]
            iterations.append(dict(index=index, device_event_count=len(values), kernel_count=len(kernels),
                                   copy_count=len(copies),
                                   names=dict(sorted(Counter(e.get('name', '') for e in kernels).items()))))
        phases[phase] = dict(iterations=iterations, timestamped_kernel_events=sum(v['kernel_count'] for v in iterations),
                             complete_markers=[v['index'] for v in iterations] == list(range(50)))
    eager, replay = phases['eager'], phases['replay']
    reference = eager['iterations'][0]['names'] if eager['iterations'] else {}
    names_match = bool(reference) and all(v['names'] == reference for v in eager['iterations'] + replay['iterations'])
    full = all(p['complete_markers'] and all(v['kernel_count'] > 0 for v in p['iterations']) for p in phases.values())
    if full and names_match and not issues:
        visibility = 'yes'
    elif eager['complete_markers'] and replay['complete_markers'] and eager['timestamped_kernel_events'] > 0 and replay['timestamped_kernel_events'] == 0 and not issues:
        visibility = 'no'
    else:
        visibility = 'partial'
    return dict(**phases, names_match=names_match, visibility=visibility,
                issues=issues, device_events_outside_iterations=outside,
                attribution='synchronized, single-process iteration containment; not valid for asynchronous census spans')


def graph_run(directory, lifecycle):
    traces, issues, events = [], [], []
    for path in sorted((directory / 'unitrace').rglob('*.json')):
        if path.stat().st_size > 128 * 1024**2:
            issues.append(f'input over 128 MiB: {path.name}')
            continue
        try:
            raw = path.read_bytes()
            data = json.loads(raw)
            rows = data.get('traceEvents', []) if isinstance(data, dict) else data
            if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
                raise ValueError('invalid traceEvents')
            # Do not combine unrelated process files into one timestamp space.
            if any(MARKER.search(e.get('name', '')) for e in rows):
                events.append(rows)
            traces.append(dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
        except (ValueError, OSError) as error:
            issues.append(f'{path.name}: {error}')
    if len(events) != 1:
        issues.append(f'expected exactly one graph marker trace; found {len(events)}')
    result = graph_events(events[0] if len(events) == 1 else [])
    result.update(traces=traces, lifecycle_status=lifecycle.get('status', 'pending'))
    result['issues'] += issues
    if issues or lifecycle.get('status') != 'passed':
        result['visibility'] = 'partial'
    return result


def rank_stages(path):
    events, issues = [], []
    if not path.exists():
        return dict(stages={}, stalls=[], complete=False, issues=['missing rank log'])
    for line in path.read_text().splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            issues.append('incomplete JSONL line')
    transitions = [e for e in events if e.get('event') == 'stage']
    timings = {}
    for previous, following in zip(transitions, transitions[1:]):
        timings[previous['stage']] = dict(seconds=following['monotonic_s'] - previous['monotonic_s'],
                                          start_unix_s=previous['unix_s'], end_unix_s=following['unix_s'])
    stalls = [e for e in events if e.get('event') == 'stall']
    return dict(stages=timings, stalls=stalls, complete=bool(transitions) and transitions[-1]['stage'] == 'exit',
                last_stage=transitions[-1]['stage'] if transitions else None, issues=issues)


def ccl_comparison(root, lifecycle):
    runs = {name: [rank_stages(root / name / f'rank-{rank}.jsonl') for rank in range(4)]
            for name in ('ccl-control', 'ccl-paused')}
    delta = []
    init_stages = ('init_process_group', 'all_reduce_4k')
    threshold = 120.
    observed = []
    for rank in range(4):
        control, traced = runs['ccl-control'][rank], runs['ccl-paused'][rank]
        stages = {}
        for name in sorted(control['stages'].keys() | traced['stages'].keys()):
            c = control['stages'].get(name, {}).get('seconds')
            t = traced['stages'].get(name, {}).get('seconds')
            stages[name] = dict(control_s=c, traced_s=t, delta_s=t - c if t is not None and c is not None else None)
        delta.append(dict(rank=rank, stages=stages))
        for name in init_stages:
            value = traced['stages'].get(name, {}).get('seconds')
            if value is not None:
                observed.append(dict(rank=rank, stage=name, seconds=value, lower_bound=False))
        for stall in traced['stalls']:
            if stall['stage'] in init_stages:
                observed.append(dict(rank=rank, stage=stall['stage'], seconds=stall['seconds'], lower_bound=True))
    control_ok = lifecycle.get('ccl-control', {}).get('status') == 'passed' and all(r['complete'] and not r['issues'] for r in runs['ccl-control'])
    traced_ok = lifecycle.get('ccl-paused', {}).get('status') == 'passed' and all(r['complete'] and not r['issues'] for r in runs['ccl-paused'])
    measured_stall = any(row['seconds'] >= threshold for row in observed)
    # null is deliberate: missing/failed runs cannot honestly mean "no stall".
    verdict = ('yes' if measured_stall else 'no' if traced_ok else None) if control_ok else None
    return dict(runs=runs, per_rank_comparison=delta, paused_init_observations=observed,
                paused_tracer_ccl_init_stall=verdict, threshold_s=threshold,
                max_observed_init_stage_s=max((v['seconds'] for v in observed), default=None),
                scope='init_process_group plus first 4 KiB all_reduce while paused; control required; not proof of causation',
                status='measured' if verdict is not None else 'incomplete')


def analyze(root):
    root = Path(root)
    summary_path = root / 'summary.json'
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {'steps': []}
    lifecycle = {r['name']: r for r in summary['steps']}
    graph = {name: graph_run(root / name, lifecycle.get(name, {})) for name in ('graph-traced', 'graph-paused')}
    statuses = [r['visibility'] for r in graph.values()]
    visibility = 'yes' if statuses == ['yes', 'yes'] else 'no' if statuses == ['no', 'no'] else 'partial'
    if lifecycle.get('graph-control', {}).get('status') != 'passed':
        visibility = 'partial'
    ccl = ccl_comparison(root, lifecycle)
    return dict(schema='a367-tracefeas-analysis-v1', graph=graph, ccl=ccl,
                verdict=dict(graph_replay_kernel_visibility=visibility,
                             paused_tracer_ccl_init_stall=ccl['paused_tracer_ccl_init_stall'],
                             paused_ccl_max_init_stage_s=ccl['max_observed_init_stage_s'],
                             ccl_status=ccl['status']),
                census_scope='microtest feasibility only; no full-model admission, rank/step attribution, memory or quality gate waived')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    result = analyze(args.run)
    write_json(args.run / 'feasibility.json', result)
    print(json.dumps(result['verdict'], indent=2))


if __name__ == '__main__':
    main()

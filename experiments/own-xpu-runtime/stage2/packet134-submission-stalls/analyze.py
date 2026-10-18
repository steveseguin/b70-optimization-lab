"""Reproduce rank-0 gap attribution from sealed receipts, using CPU only.

Device clocks are compared only within one rank's compute queue. Host clocks
are compared only with host steady_clock receipts from the same request.
No runtime imports, model reads, compilation, subprocesses, or queue writes.
"""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
BASE = P.with_name('packet128b-attribution')
RUN = BASE/'evidence/device-B/run'
FIRST, LAST = 10, 16
EVENT = 'packet128b.event.v1'
HOST = 'packet128b.host.v1'
TARGET_PREFIXES = ('begin.', 'streams', 'blk.', 'commit.')
HEAD_PREFIXES = ('head.', 'transfer.head.', 'wait.head.')


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def rows(path):
    with Path(path).open() as stream:
        return [json.loads(line) for line in stream]


def union_ns(intervals):
    end, total = None, 0
    for a, b in sorted(intervals):
        assert 0 < a <= b
        total += max(0, b-max(a, a if end is None else end))
        end = max(b, end or b)
    return total


def overlap_ns(a, b, intervals):
    """An overlap, not a causal attribution or an additive extra cost."""
    return union_ns((max(a, c), min(b, d)) for c, d in intervals
                    if max(a, c) < min(b, d))


def cycle_position(event):
    return event['position']+int(event['label'].startswith(HEAD_PREFIXES))


def gap_kind(previous, event):
    a, b = previous['label'], event['label']
    if a.startswith('snapshot.capture') and b == 'begin.0':
        return 'snapshot_to_speculative_begin'
    if a.startswith('rollback.restore') and b == 'begin.0':
        return 'restore_to_correction_begin'
    if a.startswith('head.') and b.startswith('head.'):
        return 'inside_suffix'
    if a.startswith(TARGET_PREFIXES) and b.startswith(TARGET_PREFIXES):
        assert previous['speculative'] == event['speculative']
        return 'inside_speculative_half' if event['speculative'] else 'inside_correction_half'
    return 'other'


def compute_gaps(device):
    """Exactly packet128b's continuity rule; copies never supply a clock."""
    known = {e['event'] for e in device}
    assert len(known) == len(device), 'duplicate event ID'
    previous, frontier, omitted = None, 0, 0
    result = []
    for e in sorted((e for e in device if e['queue'] == 'compute'),
                    key=lambda e: e['event']):
        assert e['queue_kind'] == 'compute' and 0 < e['start_ns'] < e['end_ns']
        if previous:
            uninterrupted = (e['fixture'] == previous['fixture'] and
                             e['event']-previous['event'] <= len(known) and
                             all(i in known for i in range(previous['event']+1, e['event'])))
            if uninterrupted:
                result.append(dict(position=cycle_position(e), kind=gap_kind(previous, e),
                    ms=max(0, e['start_ns']-frontier)/1e6,
                    before=previous['label'], after=e['label']))
            else:
                omitted += 1
                frontier = 0
        frontier = max(frontier, e['end_ns'])
        previous = e
    return result, omitted


def command_for_gap(event, trace):
    """Match the following rank-0 command on the shared host clock only."""
    command = min((t for t in trace if t['rank'] == 0),
                  key=lambda t: abs(round(t['rank_received']*1e9)-event['end_ns']))
    delta = event['end_ns']-round(command['rank_received']*1e9)
    assert 0 <= delta < 100_000, ('ambiguous command boundary', delta)
    return command


def input_files():
    files = [BASE/'evidence/budget.json', BASE/'BUDGET.md',
             BASE/'evidence/device-B/window.json', BASE/'evidence/device-B/identity.json',
             RUN/'report-inputs.json']
    for r in read(RUN/'report-inputs.json')['requests']:
        folder = RUN/r['prompt_id']
        files += [folder/'native-result.json', folder/'rank0/sites.jsonl',
                  folder/'rank0/timings.jsonl']
    sources = {
        'packet124c-record-bundle': ['main.cpp', 'rank.hpp', 'native_controller.hpp',
            'strict_snapshot.hpp', 'p105_runtime.hpp', 'prepared_submission.hpp',
            'host_spin.hpp', 'host_wait_mode.cpp', 'selection.json'],
        'packet128b-attribution': ['main.cpp', 'rank.hpp', 'p105_runtime.hpp',
            'native_controller.hpp', 'analyze.py', 'selection.json'],
        'packet22-replay': ['backend-notes.md', 'DO-NOT-REPEAT.md'],
        'packet34-replay-bench': ['README.md', 'DO-NOT-REPEAT.md',
            'receipts-card3-20261012-r1/README.md', 'receipts-card3-20261012-r1/summary.json'],
        'packet35-hostpath': ['README.md', 'DO-NOT-REPEAT.md'],
        'packet61-spin-hcfusion': ['DO-NOT-REPEAT.md'],
        'packet61x-spin-hcfusion-wait': ['README.md', 'WAIT-AUDIT.md', 'DO-NOT-REPEAT.md'],
        'packet70-record-bundle': ['README.md', 'DO-NOT-REPEAT.md'],
    }
    for packet, names in sources.items():
        files += [P.with_name(packet)/name for name in names]
    return sorted(set(files))


def pin_inputs():
    path = P/'input-pins.json'
    assert not path.exists(), 'never silently replace the source identity'
    files = input_files()
    pins = {str(f.relative_to(ROOT)): sha(f) for f in files}
    original = read(BASE/'evidence/budget.json')['receipt_sha256']
    checked = 0
    for f in files:
        if str(f) in original:
            assert sha(f) == original[str(f)], ('packet128b receipt changed', f)
            checked += 1
    assert checked == 24, checked  # twelve native results and twelve rank0 event files
    parent = P.with_name('packet124c-record-bundle')
    links = {str(f.relative_to(parent)): os.readlink(f)
             for f in parent.rglob('*') if f.is_symlink()}
    save(path, dict(schema='packet134.inputs.v1', files=pins,
        original_budget_receipts_verified=checked, parent_symlinks=links))


def verify_inputs():
    pins = read(P/'input-pins.json')
    for name, expected in pins['files'].items():
        assert sha(ROOT/name) == expected, ('input identity changed', name)
    parent = P.with_name('packet124c-record-bundle')
    links = {str(f.relative_to(parent)): os.readlink(f)
             for f in parent.rglob('*') if f.is_symlink()}
    assert links == pins['parent_symlinks'], 'parent links changed'
    return pins


def stats(values):
    return dict(n=len(values), mean=statistics.mean(values), median=statistics.median(values),
                minimum=min(values), maximum=max(values))


def generate():
    pins = verify_inputs()
    budget = read(BASE/'evidence/budget.json')
    proof = read(RUN/'report-inputs.json')
    assert proof['passed'] and proof['incident64']['passed']
    assert read(BASE/'evidence/device-B/window.json')['lease_released']
    requests = proof['requests']
    assert len(requests) == len({r['prompt_id'] for r in requests}) == 12
    cycles, transition_totals, omitted = [], collections.defaultdict(lambda: [0., 0.]), 0
    for request in requests:
        assert request['passed'] and request['exact_oracle'] and len(request['tokens']) == 64
        folder = RUN/request['prompt_id']
        native = read(folder/'native-result.json')
        assert native['tokens'] == request['tokens']
        origin, = {t['position']-t['fixture'] for t in native['rank_trace']
                   if t['op'] == 1 and t['fixture'] > 0}
        current = {}
        for g in native['guess_rows']:
            if FIRST <= g['position']-origin <= LAST:
                assert g['position'] not in current
                current[g['position']] = dict(prompt_id=request['prompt_id'],
                    position=g['position'], fixture=g['position']-origin, hit=g['hit'],
                    cycle_ms=g['cycle_ms'], metrics=collections.defaultdict(float))
        assert len(current) == LAST-FIRST+1
        events = rows(folder/'rank0/sites.jsonl')
        device = [e for e in events if e['schema'] == EVENT]
        for e in events:
            if e['schema'] in (EVENT, HOST):
                assert e['rank'] == 0 and e['request'] == request['attribution_request']
                assert 9 <= e['fixture'] <= 16 and e['end_ns'] >= e['start_ns'] > 0
        gaps, missing = compute_gaps(device)
        omitted += missing
        for gap in gaps:
            if gap['position'] not in current:
                continue
            c = current[gap['position']]
            c['metrics']['gap.'+gap['kind']] += gap['ms']
            c['metrics']['gap.total'] += gap['ms']
            transition_totals[(gap['before'], gap['after'])][int(not c['hit'])] += gap['ms']
        draft_commands = [(round(t['rank_received']*1e9), round(t['rank_completed']*1e9))
                          for t in native['rank_trace'] if t['rank'] == 1 and t['op'] == 9]
        for e in events:
            if e['schema'] != HOST or cycle_position(e) not in current:
                continue
            metrics = current[cycle_position(e)]['metrics']
            ms = (e['end_ns']-e['start_ns'])/1e6
            metrics[e['label']] += ms
            if e['label'] != 'host.command_gap':
                continue
            t = command_for_gap(e, native['rank_trace'])
            name = {1: 'before_speculation' if t['speculative'] else 'before_correction',
                    2: 'before_accept', 3: 'before_rollback'}[t['op']]
            metrics['host.command_gap.'+name] += ms
            if name == 'before_speculation':
                overlap = overlap_ns(e['start_ns'], e['end_ns'], draft_commands)/1e6
                metrics['host.pre_speculation_overlap_draft_command'] += overlap
                metrics['host.pre_speculation_outside_draft_command'] += ms-overlap
        for d in native['draft_rows']:
            if d['position'] in current:
                current[d['position']]['metrics']['host.draft_publication_wait'] += d['rank0_idle_waiting_for_guess_ms']
        target_events = collections.defaultdict(list)
        for e in device:
            if e['position'] in current and e['queue'] == 'compute' and e['label'].startswith(TARGET_PREFIXES):
                target_events[(e['position'], e['speculative'])].append(e)
        timing_counts = collections.Counter()
        for t in rows(folder/'rank0/timings.jsonl'):
            if t['position'] not in current:
                continue
            c = current[t['position']]
            kind = 'spec' if t['speculative'] else 'correction'
            timing_counts[(t['position'], kind)] += 1
            assert not t['cancelled']
            for k in ('prepare_ms', 'enqueue_loop_ms', 'wait_ms', 'p76_profiling_ms',
                      'p76_retirement_ms', 'launches_issued', 'process_major_faults'):
                c['metrics'][kind+'.'+k] += t[k]
            es = target_events[(t['position'], t['speculative'])]
            assert len(es) == t['launches_issued'] == 564
            assert {int(e['label'].split('.')[1]) for e in es if e['label'].startswith('blk.')} == set(range(24))
            c['metrics'][kind+'.compute_busy_ms'] = union_ns((e['start_ns'], e['end_ns']) for e in es)/1e6
        for c in current.values():
            assert timing_counts[(c['position'], 'spec')] == 1
            assert timing_counts[(c['position'], 'correction')] == int(not c['hit'])
            c['metrics'] = dict(c['metrics'])
            assert not c['metrics'].get('gap.other', 0), 'unclassified gap'
            cycles.append(c)
    assert len(cycles) == 84
    metrics = sorted(set().union(*(c['metrics'] for c in cycles)))
    summary = {}
    for hit, label in ((True, 'hit'), (False, 'miss')):
        subset = [c for c in cycles if c['hit'] == hit]
        assert len(subset) == (66 if hit else 18)
        summary[label] = {k: stats([c['metrics'].get(k, 0) for c in subset]) for k in metrics}
        summary[label]['cycle_ms'] = stats([c['cycle_ms'] for c in subset])
        for ours, original in [('gap.total', 'compute_idle_observed'),
                               ('host.command_gap', 'host.command_gap'),
                               ('wait.head.hidden', 'wait.head.hidden'),
                               ('host.draft_publication_wait', 'wait.draft_publication')]:
            old, = [t for t in budget['tables'] if t['rank'] == 0 and
                    t['outcome'] == label and t['category'] == original]
            for statistic in ('mean', 'median'):
                assert abs(summary[label][ours][statistic]-old[statistic+'_ms']) < 1e-9
    s = budget['summary']
    assert not s['overhead_bounded'] and not budget['ranking_usable'] and not budget['levers']
    return dict(schema='packet134.attribution.v1', passed=True, device_executed=False,
        runtime_changed=False, arithmetic='iq3-p49-split32-v1', kv_dtype='BF16',
        speed_evidence_eligible=False, ranking_usable=False, measured_gain=None,
        diagnostic_rate_tps=s['class_balanced_tps'], diagnostic_overhead_gate_passed=False,
        input_pins_sha256=sha(P/'input-pins.json'), source_files=len(pins['files']),
        preserved_parent_symlinks=len(pins['parent_symlinks']),
        fixture_range=[FIRST, LAST], observed_cycles=len(cycles),
        unobserved_compute_boundaries=omitted, summary=summary, cycles=cycles,
        transitions=[dict(before=a, after=b, hit_total_ms=v[0], miss_total_ms=v[1])
                     for (a, b), v in sorted(transition_totals.items(), key=lambda x: -sum(x[1]))],
        decision='Close submission replay for these receipts: target enqueue starvation is not supported; dominant observed gaps precede target submission. Uninstrumented attribution remains unproven.')


def markdown(report):
    def cell(label, key):
        s = report['summary'][label][key]
        return f"{s['mean']:.6f} / {s['median']:.6f}"
    names = [
        ('Observed compute gap', 'gap.total'),
        ('Snapshot end → speculative begin', 'gap.snapshot_to_speculative_begin'),
        ('Restore end → correction begin', 'gap.restore_to_correction_begin'),
        ('Inside speculative target sequence', 'gap.inside_speculative_half'),
        ('Inside correction target sequence', 'gap.inside_correction_half'),
        ('Inside suffix', 'gap.inside_suffix'),
        ('Host command gaps (overlapping work)', 'host.command_gap'),
        ('Command gap before speculation', 'host.command_gap.before_speculation'),
        ('Of that gap: overlap with rank1 draft command', 'host.pre_speculation_overlap_draft_command'),
        ('Of that gap: outside rank1 draft command', 'host.pre_speculation_outside_draft_command'),
        ('Command gap before accept', 'host.command_gap.before_accept'),
        ('Command gap before rollback', 'host.command_gap.before_rollback'),
        ('Command gap before correction', 'host.command_gap.before_correction'),
        ('Explicit draft-publication wait', 'host.draft_publication_wait'),
        ('Explicit hidden-state wait', 'wait.head.hidden'),
        ('Speculative host token preparation', 'spec.prepare_ms'),
        ('Correction host token preparation', 'correction.prepare_ms'),
        ('Speculative host enqueue loop', 'spec.enqueue_loop_ms'),
        ('Correction host enqueue loop', 'correction.enqueue_loop_ms'),
        ('Speculative target compute busy union', 'spec.compute_busy_ms'),
        ('Correction target compute busy union', 'correction.compute_busy_ms'),
        ('Speculative profiling work', 'spec.p76_profiling_ms'),
        ('Correction profiling work', 'correction.p76_profiling_ms'),
    ]
    lines = ['# Packet134: rank-0 observed gap attribution', '',
        'CPU reanalysis of packet128b only; no new device measurement or speed claim.', '',
        f"Packet128b: {report['diagnostic_rate_tps']:.6f} tok/s; overhead gate **failed** (required 52.2).",
        '84 complete sampled cycles: 66 hits, 18 misses. Fixtures 10–16 in every request.', '',
        '| Interval (ms per sampled cycle) | Hit mean / median | Miss mean / median |',
        '| --- | ---: | ---: |']
    lines += [f'| {name} | {cell("hit", key)} | {cell("miss", key)} |' for name, key in names]
    lines += ['', 'Zero correction cost on hits means the correction did not execute.',
        'The two clocks and overlapping rows must not be added into a wall-time budget.', '',
        '| Count per sampled half | Hit mean / median | Miss mean / median |',
        '| --- | ---: | ---: |']
    for name, key in [('Speculative kernels', 'spec.launches_issued'),
                      ('Correction kernels', 'correction.launches_issued'),
                      ('Speculative process major faults', 'spec.process_major_faults'),
                      ('Correction process major faults', 'correction.process_major_faults')]:
        lines.append(f'| {name} | {cell("hit", key)} | {cell("miss", key)} |')
    lines += ['', 'All four original rank0 budget rows reproduce their means and medians within 1e-9 ms.',
        f"{report['unobserved_compute_boundaries']} discontinuous compute boundaries are excluded, as in packet128b.",
        'Copies never supply a compute clock. Missing IDs and fixture boundaries are not counted as idle.',
        'The draft-command overlap uses only same-request host steady_clock intervals. It includes host draft',
        'submission/preparation and is not a claim that all of it is draft GPU execution.',
        'The explicit publication wait is largely inside the pre-speculation command gap, not additional cost.', '',
        'See [README](README.md) for source attribution, limits, decision and reconstruction.', '']
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pin-inputs', action='store_true')
    args = ap.parse_args()
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert shutil.disk_usage('/').free >= 25_000_000_000
    if args.pin_inputs:
        pin_inputs()
    report = generate()
    (P/'evidence').mkdir(exist_ok=True)
    save(P/'evidence/attribution.json', report)
    (P/'ATTRIBUTION.md').write_text(markdown(report))
    print(json.dumps(dict(passed=True, cycles=report['observed_cycles'],
        overhead_gate_passed=False, runtime_changed=False,
        input_pins_sha256=report['input_pins_sha256'])))


if __name__ == '__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))
    main()

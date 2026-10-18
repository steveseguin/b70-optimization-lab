#!/usr/bin/env python3
"""Read frozen packet77 receipts. CPU only; no model, backend or shell imports.

nice -n 19 taskset -c 8-15,24-31 python3 -B attribute.py [--check] </dev/null
Host accounting and sampled device accounting deliberately remain separate.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import resource
import statistics as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STAGE = HERE.parent
RUN = STAGE / 'screen/v4-lanes/evidence/packet77-attribution-B-a/run'
SOURCES = {}
resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))


def read(path):
    data = path.read_bytes()
    SOURCES[str(path.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
    return data.decode()


def load(path):
    return json.loads(read(path))


def lines(path):
    return [json.loads(line) for line in read(path).splitlines()]


def stats(values):
    values = list(values)
    return dict(n=len(values), mean=st.mean(values), median=st.median(values),
                minimum=min(values), maximum=max(values)) if values else dict(n=0)


def duration(row):
    return 1000 * (row['rank_completed'] - row['rank_received'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    model = load(STAGE / 'packet85-critical-path/model.json')
    # Pin the source semantics, including unmeasured copy operations and clocks.
    for packet in ('packet77-attribution', 'packet84-record-bundle'):
        for name in ('main.cpp', 'rank.hpp', 'native_controller.hpp', 'strict_snapshot.hpp',
                     'owner.cpp', 'owner_api.hpp'):
            read(STAGE / packet / name)
    for name in ('attribution.hpp', 'selection.json'):
        read(STAGE / 'packet77-attribution' / name)
    for path in sorted(STAGE.glob('*/DO-NOT-REPEAT.md')):
        if path.parent != HERE:
            read(path)
    halves = defaultdict(list)
    misses = []
    spans = defaultdict(list)
    calls = defaultdict(list)
    rollback_events = []
    snapshots = []
    counts = defaultdict(int)
    prompt_ids = []
    controls = sorted((RUN / 'control').glob('*/receipt.json'))
    assert len(controls) == 12
    for path in controls:
        prompt_ids.append(path.parent.name)
        pair = {arm: load(RUN / arm / path.parent.name / 'receipt.json')
                for arm in ('control', 'attribution')}
        a, b = pair.values()
        for r in pair.values():
            assert r['passed'] and r['exact_oracle'] and r['oracle_check']['passed']
            assert r['cached_tokens'] == 0 and r['output_tokens'] == 128
            assert r['target_split'] == [24, 24]
        for key in ('tokens', 'prompt_token_sha256', 'output_token_sha256',
                    'binary_sha256', 'selection_sha256'):
            assert a[key] == b[key]
        traces = {}
        timings = {}
        for arm, r in pair.items():
            base = RUN / arm / path.parent.name
            traces[arm] = {(t['rank'], t['op'], t['position'], t['speculative']): t
                           for t in r['rank_trace'] if t['op'] in (1, 3, 9)}
            timings[arm] = {(t['position'], t['speculative']): t
                            for t in lines(base / 'rank0/timings.jsonl')}
            snapshots.append(load(base / 'rank0/speculative-snapshot.json'))
        idx = traces['control']
        guesses = {g['position']: g['hit'] for g in a['guess_rows']}
        for i in range(99):
            pos = a['prompt_tokens'] + i
            hit = guesses[pos]
            counts['intervals'] += 1
            counts['hits' if hit else 'misses'] += 1
            items = [('A', idx[0, 1, pos + 1, True])]
            if not hit:
                c, r, d = idx[0, 1, pos, False], idx[0, 3, pos, True], idx[1, 9, pos, True]
                previous = idx[0, 1, pos, True]
                assert previous['token'] != c['token'], 'miss must change the target input token'
                items.append(('C', c))
                overlap = max(0, min(r['rank_completed'], d['rank_completed']) -
                              max(r['rank_received'], d['rank_received'])) * 1000
                misses.append(dict(R_ms=duration(r), C_ms=duration(c), D_ms=duration(d),
                    R_D_overlap_ms=overlap,
                    R_not_overlapped_ms=duration(r)-overlap,
                    restore_to_C_start_ms=1000*(c['rank_received']-r['rank_completed']),
                    draft_to_R_start_ms=1000*(r['rank_received']-d['rank_received']),
                    R_covered_by_D=overlap >= duration(r)-1e-6))
            for role, t in items:
                h = timings['control'][t['position'], t['speculative']]
                # These host buckets partition wall time by construction. Waits
                # inside prepare are already included in prepare: the signed
                # remainder retains this overlap; do not relabel as idle time.
                wall = duration(t)
                halves[role].append(dict(command_ms=wall, busy_ms=t['busy_ms'],
                    outside_busy_ms=wall-t['busy_ms'], prepare_ms=h['prepare_ms'],
                    enqueue_excluding_wait_ms=h['enqueue_loop_ms'], wait_ms=h['wait_ms'],
                    busy_remainder_ms=t['busy_ms']-h['prepare_ms']-h['enqueue_loop_ms']-h['wait_ms'],
                    reported_gpu_ms=t['gpu_ms'], cancelled=h['cancelled'],
                    launches=h['launches_issued']))
        events = lines(RUN / 'attribution' / path.parent.name / 'rank0/sites.jsonl')
        groups = defaultdict(list)
        for e in events:
            if e.get('schema') != 'packet57.event.v1':
                continue
            assert e['rank'] == 0 and e['start_ns'] <= e['end_ns']
            if e['label'].startswith('transfer.rollback'):
                rollback_events.append(e)
                continue
            groups[e['position'], e['speculative']].append(e)
        for (pos, spec), es in groups.items():
            timing = timings['attribution'].get((pos, spec))
            if not timing or timing['cancelled']:
                continue
            begin = [e['start_ns'] for e in es if e.get('layer_boundary') == 'begin']
            end = [e['end_ns'] for e in es if e.get('layer_boundary') == 'end']
            if not begin or not end:
                continue
            role = 'A' if spec else 'C'
            ct, it = traces['control'][0, 1, pos, spec], traces['attribution'][0, 1, pos, spec]
            span = (max(end)-min(begin))/1e6
            spans[role].append(dict(layer_span_ms=span, instrumented_command_ms=duration(it),
                control_command_ms=duration(ct), instrumented_outside_span_ms=duration(it)-span))
            by_call = defaultdict(float)
            for e in es:
                label = e['label'].split('.')
                if len(label) > 2 and label[0] == 'blk' and label[1] in ('22', '23'):
                    by_call[(int(label[1]), '.'.join(label[2:]))] += (e['end_ns']-e['start_ns'])/1e6
            for (layer, site), ms in by_call.items():
                calls[role, layer, site].append(ms)
    assert counts == dict(intervals=1188, hits=936, misses=252)
    expected = model['baseline']['components_ms']
    for role in ('A', 'C'):
        assert abs(st.mean(h['command_ms'] for h in halves[role])-expected[role]) < 1e-10
    assert abs(st.mean(m['R_ms'] for m in misses)-expected['R']) < 1e-10
    # Counters accumulate across requests and both arms, including incident64.
    # Never sum them as though each file held a separate request's byte count.
    final = max(snapshots, key=lambda s: s['captures'])
    assert all(s['miss_selection'] == 'batch' and not s['redo_fallbacks'] and
               s['restores'] == s['redo_restores'] == s['completed_redos'] and
               s['capture_submissions'] == 2*s['captures'] and
               s['restore_submissions'] == 2*s['restores'] for s in snapshots)
    per_capture = {s['snapshot_payload_bytes']//s['captures'] for s in snapshots if s['captures']}
    per_restore = {s['restored_bytes']//s['restores'] for s in snapshots if s['restores']}
    omitted = {s['redo_omitted_bytes']//s['restores'] for s in snapshots if s['restores']}
    assert len(per_capture) == len(per_restore) == len(omitted) == 1
    capture, restore, banks = per_capture.pop(), per_restore.pop(), omitted.pop()
    assert capture == restore+banks
    assert all(s['snapshot_payload_bytes'] == capture*s['captures'] and
               s['restored_bytes'] == restore*s['restores'] and
               s['redo_omitted_bytes'] == banks*s['restores'] for s in snapshots)
    # Nine standalone extents from the production constructor and write-set
    # bounds. The residual is all nonbank plan buffers, NOT a guessed breakdown.
    standalone = {'parallel_controls':12, 'attention_scores':196896,
        'attention_probabilities':196896, 'layer_snapshots':983040,
        'fp32_input':696320, 'gemv_workspace':8388608, 'compact_routes':120,
        'ordered_mixture':5120, 'operator_scratch_written_span':1609936}
    standalone['nonbank_plan_buffers_remainder'] = restore-sum(standalone.values())
    result = dict(schema='own-runtime.packet88.miss-attribution.v1', device_executed=False,
        candidate_built=False, qualifying=False, submission_eligible=False,
        counts=dict(counts), prompt_ids=prompt_ids,
        first99_host_ms={role:{key:stats(h[key] for h in rows) for key in rows[0]}
                         for role, rows in halves.items()},
        miss_schedule={key:stats(m[key] for m in misses) for key in misses[0]},
        instrumented_complete_sample={role:{key:stats(h[key] for h in rows) for key in rows[0]}
                                     for role, rows in spans.items()},
        sampled_site_calls=[dict(role=role, layer=layer, site=site, device_ms=stats(v),
            occurrences=18 if layer==22 else 6,
            estimated_ms_per_half=st.median(v)*(18 if layer==22 else 6),
            whole_half_measurement=False) for (role,layer,site),v in sorted(calls.items())],
        rollback=dict(capture_payload_bytes=capture, restore_payload_bytes=restore,
            omitted_spare_bank_bytes=banks, payload_components=standalone,
            descriptor_uploads_per_restore=1, flat_compute_kernels_per_restore=1,
            kernel_device_time_ms=None, descriptor_upload_device_time_ms=None,
            restore_transfer_event_count=len(rollback_events),
            positive_width_restore_transfer_events=sum(e['end_ns']>e['start_ns'] for e in rollback_events),
            cumulative_final_counters=final),
        limitations=['Control host buckets and instrumented sample spans are different populations.',
            'prepare_ms and wait_ms can overlap; busy_remainder_ms is signed accounting, not GPU idle.',
            'reported_gpu_ms omits unregistered work and is not total GPU time.',
            'Flat snapshot compute is not registered with the device timing collector.',
            'Zero-width transfer timestamps do not measure zero-cost transfers.',
            'Site cost times layer multiplicity is an estimate, never a measured C decomposition.',
            'Snapshot counters are cumulative across the paired screen including incident64.',
            'Standalone byte split is source-derived; nonbank plan-buffer split is a residual.'],
        source_sha256=dict(sorted(SOURCES.items())))
    text = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+'\n'
    dest = HERE / 'attribution.json'
    if args.check:
        assert dest.read_text() == text, 'attribution differs from raw receipts/source pins'
        print('PASS: raw identity, counts, schedule, copy totals and attribution reproduce exactly')
    else:
        dest.write_text(text)
        print('Wrote', dest.relative_to(ROOT))
    print(json.dumps(dict(counts=result['counts'],
        A_ms=result['first99_host_ms']['A']['command_ms']['mean'],
        C_ms=result['first99_host_ms']['C']['command_ms']['mean'],
        R_ms=result['miss_schedule']['R_ms']['mean'],
        restore_payload_bytes=restore, restore_device_ms=None), sort_keys=True))


if __name__ == '__main__':
    main()

"""Strict CPU receipt validator and derived metrics (decimal GB/s = B/ns)."""
import copy
import math
import json
import jsonschema
import statistics
from plan import HERE, make_plan, REPS
SCHEMA = 'own-runtime.h2d.receipt.v1'
MODES = ['H2D-pinned', 'H2D-pageable', 'D2H-pinned', 'D2H-pageable', 'D2D']
OVERLAP = ['copy-only', 'compute-only', 'serial', 'concurrent']

def require(value, message):
    if not value:
        raise ValueError(message)

def positive(value):
    return type(value) in (float, int) and math.isfinite(value) and value > 0

def event_duration(e):
    start, end = e['start_ns'], e['end_ns']
    require(type(start) is int and type(end) is int and start >= 0 and end >= 0,
            'event timestamps')
    return end-start if 0 < start < end else None

def sample_event_duration(s):
    durations = [event_duration(e) for e in s['events']]
    return sum(durations) if all(d is not None for d in durations) else None

def nullable_median(values):
    present = [v for v in values if v is not None]
    return statistics.median(present) if present else None

def validate_native(r, plan):
    require(r['schema'] == 'own-runtime.h2d.native.v1', 'native schema')
    require(r['completed'] is True and r['error'] == '', 'incomplete/failed native run')
    devices = r['devices']
    require(len(devices) in (1, 2) and len(set(devices)) == len(devices), 'device count/identity')
    require(all(isinstance(d, str) and ':uuid=' in d for d in devices), 'device UUID missing')
    require(len(r['teardown']) == len(devices) == len(r['census']), 'owner coverage')
    for i, t in enumerate(r['teardown']):
        require(t['schema'] == 'own-xpu-runtime.teardown.v1' and t['backend'] == devices[i], 'teardown identity')
        require(t['safe_to_exit'] is True and t['status'] == 'complete' and t['exit_code'] == 0
                and t['idle_marker_complete'] is True and t['live_bytes'] == t['in_flight'] == 0
                and t['error'] == '', 'unsafe teardown')
        seq = t['sequence']
        ordered = ['quiesce', 'drain', 'graphs-released', 'idle-marker-complete', 'events-released', 'queue-released', 'context-released']
        require(all(s in seq for s in ordered) and [seq.index(s) for s in ordered] == sorted(seq.index(s) for s in ordered), 'teardown order')
        census = r['census'][i]
        require(census['schema'] == 'own-xpu-runtime.census.v1' and census['allocations']
                and census['unmeasured_driver_shadow_bytes'] is None, 'allocation census missing')
        peak = plan['requested_peak']
        expected_totals = ({'device': peak['card_a_device_bytes'], 'host-pinned': peak['card_a_pinned_bytes'],
                            'host-shadow': peak['card_a_pageable_bytes']} if i == 0 else
                           {'device': peak['optional_card_b_device_bytes'], 'host-pinned': peak['optional_card_b_pinned_bytes'], 'host-shadow': 0})
        require(census['totals'] == expected_totals, 'allocation peak mismatch')
        for memory, total in expected_totals.items():
            require(sum(a['bytes'] for a in census['allocations'] if a['memory'] == memory and a['live']) == total,
                    'allocation rows disagree with totals')
    for section, modes in [('cases', MODES + (['host-bounce-A-B'] if len(devices) == 2 else [])), ('overlap', OVERLAP)]:
        expected = {(c['label'], mode): c for c in plan['cases'] for mode in modes}
        require(len(r[section]) == len(expected), 'case coverage')
        seen = set()
        for row in r[section]:
            key = row['label'], row['mode']
            require(key in expected and key not in seen, 'unexpected/duplicate case')
            seen.add(key); case = expected[key]
            require(row['bytes'] == case['bytes'] and row['verified'] is True, 'size/byte verification')
            require(len(row['samples']) == REPS, 'twenty repetitions required')
            mode = row['mode']; chunks = len(case['chunks'])
            for s in row['samples']:
                require(positive(s['wall_ns']), 'wall timing')
                ev = s['events']
                if section == 'cases':
                    kinds = ([('D2H-A', devices[0])]*chunks + [('H2D-B', devices[1])]*chunks if mode == 'host-bounce-A-B'
                             else [(mode.split('-')[0], devices[0])]*chunks)
                else:
                    kinds = ([] if mode == 'compute-only' else [('H2D', devices[0])]*chunks)
                    if mode != 'copy-only': kinds += [('GEMV', devices[0])]
                require([(e['kind'], e['device']) for e in ev] == kinds, 'event coverage/direction/device')
                for e in ev:
                    duration = event_duration(e)
                    require(e['duration_ns'] == duration, 'event timing')
                require(positive(s['host_bounce_memcpy_ns']) if mode == 'host-bounce-A-B'
                        else s['host_bounce_memcpy_ns'] == 0, 'bounce host timing')
    return True

def summary(r, plan):
    validate_native(r, plan)
    out = copy.deepcopy(r)
    out['schema'] = SCHEMA
    out['plan'] = plan
    out['measured'] = True
    out['rate_definition'] = 'decimal payload GB/s; event rate excludes gaps and host staging; wall includes submit/wait; bounce wall includes CPU memcpy'
    for row in out['cases'] + out['overlap']:
        for s in row['samples']:
            s['event_ns'] = sample_event_duration(s)
        row['repetitions_without_event_timing'] = sum(s['event_ns'] is None for s in row['samples'])
    for row in out['cases']:
        for s in row['samples']:
            s['wall_GBps'] = row['bytes']/s['wall_ns']
            s['event_payload_GBps'] = row['bytes']/s['event_ns'] if s['event_ns'] is not None else None
        row['median_wall_GBps'] = statistics.median(s['wall_GBps'] for s in row['samples'])
        row['median_event_payload_GBps'] = nullable_median([s['event_payload_GBps'] for s in row['samples']])
        row['link_bytes_per_repetition'] = row['bytes'] * (2 if row['mode'] == 'host-bounce-A-B' else 1)
    out['overlap_summary'] = []
    for case in plan['cases']:
        rows = {r['mode']: r for r in out['overlap'] if r['label'] == case['label']}
        walls = {m: statistics.median(s['wall_ns'] for s in r['samples']) for m, r in rows.items()}
        fractions = []
        for s in rows['concurrent']['samples']:
            if s['event_ns'] is None:
                fractions.append(None)
                continue
            compute = next(e for e in s['events'] if e['kind'] == 'GEMV')
            copies = [e for e in s['events'] if e['kind'] == 'H2D']
            intersection = sum(max(0, min(e['end_ns'], compute['end_ns']) - max(e['start_ns'], compute['start_ns'])) for e in copies)
            shorter = min(sum(e['end_ns']-e['start_ns'] for e in copies), compute['end_ns']-compute['start_ns'])
            fractions.append(intersection/shorter)
        out['overlap_summary'].append(dict(label=case['label'], median_wall_ns=walls,
            overlap_ratio=walls['serial']/walls['concurrent'],
            isolated_sum_ratio=(walls['copy-only']+walls['compute-only'])/walls['concurrent'],
            event_overlap_fractions=fractions,
            repetitions_without_event_timing=sum(f is None for f in fractions),
            median_event_overlap_fraction=nullable_median(fractions)))
    out['overlap_definition'] = 'serial/concurrent wall ratio; >1 faster. Event overlap fraction=intersection/min(copy duration, GEMV duration) on the same device clock; 0 none, 1 full shorter-work overlap. No cross-card clock subtraction.'
    # Sum layer-specific transfer floors; do not silently replace mixed sizes with a big-block rate.
    floors = {}
    for host in ('pinned', 'pageable'):
        floor = 0
        for i, grid in enumerate(plan['expert_grids']):
            row = next(r for r in out['cases'] if r['label'] == f'grid{i}-experts10' and r['mode'] == 'H2D-'+host)
            floor += len(grid['layers'])*10*grid['triplet_bytes']/(row['median_wall_GBps']*1e9)
        floors[host] = dict(all_miss_transfer_seconds_per_token=floor, transfer_only_tokens_per_second=1/floor)
    out['streaming_arithmetic'] = floors
    return out

def validate_receipt(r):
    jsonschema.Draft202012Validator(json.loads((HERE/'receipt.schema.json').read_text())).validate(r)
    require(r['schema'] == SCHEMA and r['measured'] is True, 'receipt schema/status')
    require(r['plan'] == make_plan(), 'bound plan/census')
    native = copy.deepcopy(r); native['schema'] = 'own-runtime.h2d.native.v1'
    expected = summary(native, r['plan'])
    for key in ('cases', 'overlap', 'overlap_summary', 'streaming_arithmetic', 'rate_definition', 'overlap_definition'):
        require(r[key] == expected[key], 'derived metric mismatch: '+key)
    return True

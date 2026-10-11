#!/usr/bin/env python3
"""Coordinator-only side-by-side timing, gated by hash-bound packet6 exactness."""
import argparse
import json
import os
import statistics
from pathlib import Path
from common import BUILD, INPUTS, LATCH, MANIFEST, admit, plan, planlib, save, sha, teardown_ok, watch


def spans(events):
    if not events or any(set(e) != {'start_ns', 'end_ns'} for e in events):
        raise ValueError('event shape')
    if any(type(v) is not int or v < 0 for e in events for v in e.values()):
        raise ValueError('event timestamps')
    if any(e['end_ns'] <= e['start_ns'] for e in events) or any(a['end_ns'] > b['start_ns'] for a, b in zip(events, events[1:])):
        raise ValueError('event order')
    return (events[-1]['end_ns'] - events[0]['start_ns']) / 1e6


def summarize(raw, layer):
    if raw.get('schema') != 'own-runtime.iq3.packet6.timing-native.v1' or not teardown_ok(raw) or raw.get('device') != raw.get('teardown', {}).get('backend'):
        raise ValueError('native failure/teardown')
    variants = ('baseline', 'kopt_sg16', 'kopt_sg32')
    expected = [(j['name'], v) for j in layer['jobs'] for v in variants]
    if [(r['name'], r['variant']) for r in raw['kernels']] != expected:
        raise ValueError('kernel coverage/order')
    rows, baseline = [], {}
    for result, (name, variant) in zip(raw['kernels'], expected):
        job = next(j for j in layer['jobs'] if j['name'] == name)
        if result['route_status'] != ([0] * 10 if job['experts'] == 512 else []):
            raise ValueError('route status')
        row = dict(name=name, variant=variant, **planlib.metrics(planlib.event_ms(result['events']), job['packed_active_bytes']))
        if variant == 'baseline':
            baseline[name] = row['median_ms']
        row['baseline_over_candidate'] = baseline[name] / row['median_ms']
        rows.append(row)
    summary = dict(kernels=rows, sequence=[], fused=None)
    if layer['layer'] != 0:
        if raw['sequence'] != [] or raw['fused'] is not None:
            raise ValueError('unexpected layer sequence')
        return summary
    if [s['variant'] for s in raw['sequence']] != ['baseline', 'kopt_sg16']:
        raise ValueError('sequence variants')
    for s in raw['sequence']:
        if s['layer'] != 0 or s['launches_per_layer'] != len(layer['jobs']) or len(s['iterations']) != 20:
            raise ValueError('sequence extent')
        samples = []
        for iteration in s['iterations']:
            if len(iteration['events']) != len(layer['jobs']):
                raise ValueError('sequence launch coverage')
            samples.append(spans(iteration['events']))
        summary['sequence'].append(dict(variant=s['variant'], **planlib.metrics(samples, layer['gemv_active_bytes'])))
    summary['sequence'][1]['baseline_over_candidate'] = summary['sequence'][0]['median_ms'] / summary['sequence'][1]['median_ms']
    fused = raw['fused']
    names = ['blk.0.' + s + '.weight' for s in ('hc_attn_inject', 'ssm_alpha', 'ssm_beta', 'hc_attn_down')]
    if fused['names'] != names or fused['variant'] != 'kopt_fused_sg16' or len(fused['separate_iterations']) != 20:
        raise ValueError('fused coverage')
    if any(len(e) != 4 for e in fused['separate_iterations']):
        raise ValueError('four separate launches required')
    packed = sum(j['packed_active_bytes'] for j in layer['jobs'] if j['name'] in names)
    combined = planlib.metrics(planlib.event_ms(fused['events']), packed)
    separate = planlib.metrics([spans(e) for e in fused['separate_iterations']], packed)
    summary['fused'] = dict(names=names, fused=combined, separate_sg16_queue_span=separate,
        separate_over_fused=separate['median_ms'] / combined['median_ms'],
        scope='independent projection buffers only; real layer dependencies are not scheduled by this diagnostic')
    return summary


def validate_census(censuses, layer):
    if len(censuses) != 2:
        raise ValueError('resident and released census required')
    live = [r for r in censuses[0]['allocations'] if r['live']]
    weights = [r for r in live if r['category'] == 'weights']
    expected = {j['name'] + '/weights': j['weight_bytes'] for j in layer['jobs']}
    if {r['label']: r['bytes'] for r in weights} != expected or len(weights) != len(expected):
        raise ValueError('resident weights changed')
    if any(r['memory'] != 'device' for r in weights):
        raise ValueError('wrong weight memory')
    for memory in ('device', 'host-pinned', 'host-shadow'):
        if censuses[0]['totals'][memory] != sum(r['bytes'] for r in live if r['memory'] == memory):
            raise ValueError('census totals')
    if any(censuses[-1]['totals'].values()) or any(r['live'] for r in censuses[-1]['allocations']):
        raise ValueError('unreleased allocations')


def execute(card, output, exactness):
    out, manifest = admit(card, output)
    exact = json.loads(exactness.read_text())
    if (exact.get('schema') != 'own-runtime.iq3.packet6.device-window.v1' or exact.get('passed') is not True
        or exact.get('card') != card or exact.get('prepared_sha256') != sha(MANIFEST)):
        raise ValueError('matching successful packet6 exactness required')
    out.mkdir(parents=True)
    record = dict(schema='own-runtime.iq3.packet6.timing.v1', passed=False, device_executed=True, card=card,
        prepared_sha256=sha(MANIFEST), prepared_manifest=manifest, exactness_sha256=sha(exactness), plan=plan(), layers=[],
        environment={k: v for k, v in os.environ.items() if k.startswith(('SYCL_', 'ZE_', 'ONEAPI_', 'UR_')) or k == 'OMP_NUM_THREADS'})
    try:
        for layer in record['plan']['layers']:
            destination = out / ('layer%d' % layer['layer'])
            command = [str(BUILD / 'device/device-timing'), '--authorized-device-window', str(card),
                str(INPUTS / ('layer%d.tsv' % layer['layer'])), str(destination / 'native.json'), str(destination / 'census.json')]
            window = watch(command, destination)
            raw = json.loads((destination / 'native.json').read_text())
            census = json.loads((destination / 'census.json').read_text())
            validate_census(census, layer)
            summary = summarize(raw, layer)
            record['layers'].append(dict(layer=layer['layer'], window=window, native=raw, census=census, summary=summary,
                kernel_journal_sha256=sha(destination / 'kernel-window.txt')))
            if window['returncode'] != 0 or window['stop_reason'] is not None:
                raise ValueError('timing window failed')
        record['passed'] = True
    except Exception as e:
        record['error'] = str(e)
        save(LATCH, dict(reason=str(e), output=str(out)))
    save(out / 'timing.json', record)
    return record['passed']

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--authorized-device-window', action='store_true')
    p.add_argument('--card', type=int)
    p.add_argument('--output', type=Path)
    p.add_argument('--exactness', type=Path)
    a = p.parse_args()
    if a.dry_run:
        print(json.dumps(plan(), indent=2))
    else:
        if a.card is None or a.output is None or a.exactness is None:
            p.error('card, output, and exactness required')
        raise SystemExit(0 if execute(a.card, a.output, a.exactness) else 1)

#!/usr/bin/env python3
"""Coordinator-only side-by-side timing, gated by hash-bound packet7 exactness."""
import argparse
import json
import os
import statistics
from pathlib import Path
from common import BUILD, INPUTS, LATCH, MANIFEST, admit, plan, planlib, save, sha, teardown_ok, watch, VARIANTS, SMALL, EXPERTS, run_ceiling


def spans(events):
    if not events or any(set(e) != {'start_ns', 'end_ns'} for e in events):
        raise ValueError('event shape')
    if any(type(v) is not int or v < 0 for e in events for v in e.values()):
        raise ValueError('event timestamps')
    if any(e['end_ns'] <= e['start_ns'] for e in events) or any(a['end_ns'] > b['start_ns'] for a, b in zip(events, events[1:])):
        raise ValueError('event order')
    return (events[-1]['end_ns'] - events[0]['start_ns']) / 1e6


def summarize(raw, layer):
    if raw.get('schema') != 'own-runtime.iq3.packet7.timing-native.v1' or not teardown_ok(raw) or raw.get('device') != raw.get('teardown', {}).get('backend'):
        raise ValueError('native failure/teardown')
    grouped = raw.get('phase') == 'groups'
    if raw.get('phase') not in ('kernels','groups') or (grouped and layer['layer'] != 0):
        raise ValueError('phase/layer')
    expected = [] if grouped else [(j['name'], v) for j in layer['jobs'] for v in VARIANTS]
    if [(r['name'], r['variant']) for r in raw['kernels']] != expected:
        raise ValueError('kernel coverage/order')
    rows, baseline = [], {}
    for result, (name, variant) in zip(raw['kernels'], expected):
        job = next(j for j in layer['jobs'] if j['name'] == name)
        if result['route_status'] != ([0] * 10 if job['experts'] == 512 else []):
            raise ValueError('route status')
        passes = result['pass_events']
        if len(passes) != 20 or any(len(p) != (2 if variant.startswith('splitk') else 1) for p in passes):
            raise ValueError('missing native passes')
        for span, events in zip(result['events'], passes):
            spans(events)
            if span != dict(start_ns=events[0]['start_ns'], end_ns=events[-1]['end_ns']):
                raise ValueError('two-pass inclusive span')
        row = dict(name=name, variant=variant, **planlib.metrics(planlib.event_ms(result['events']), job['packed_active_bytes']))
        if variant == 'kopt_sg32': baseline[name] = row['median_ms']
        row['round1_over_candidate'] = baseline[name] / row['median_ms']
        rows.append(row)
    summary = dict(kernels=rows, sequence=[], fused=[])
    if not grouped:
        if raw['sequence'] != [] or raw['fused'] != []: raise ValueError('unexpected grouped results')
        return summary
    if [s['variant'] for s in raw['sequence']] != ['kopt_sg32','rows2_vec32_v1']: raise ValueError('sequence variants')
    for s in raw['sequence']:
        if s['layer'] != 0 or s['launches_per_layer'] != len(layer['jobs']) or len(s['iterations']) != 20:
            raise ValueError('sequence extent')
        samples = []
        for iteration in s['iterations']:
            if len(iteration['events']) != len(layer['jobs']): raise ValueError('sequence coverage')
            samples.append(spans(iteration['events']))
        summary['sequence'].append(dict(variant=s['variant'], **planlib.metrics(samples, layer['gemv_active_bytes'])))
    expected_fused = [(kind,v) for kind in ('small','routed_experts') for v in ('rows2_vec32_v1','rows2_vec64_v1')]
    if [(f['kind'],f['variant']) for f in raw['fused']] != expected_fused: raise ValueError('fused order')
    for f in raw['fused']:
        names = ['blk.0.'+n+'.weight' for n in (SMALL if f['kind']=='small' else EXPERTS)]
        if f['names'] != names or len(f['separate_iterations']) != 20 or any(len(e)!=len(names) for e in f['separate_iterations']):
            raise ValueError('fused coverage')
        packed = sum(j['packed_active_bytes'] for j in layer['jobs'] if j['name'] in names)
        combined = planlib.metrics(planlib.event_ms(f['events']),packed)
        separate = planlib.metrics([spans(e) for e in f['separate_iterations']],packed)
        summary['fused'].append(dict(names=names,kind=f['kind'],variant=f['variant'],fused=combined,separate=separate,
            separate_over_fused=separate['median_ms']/combined['median_ms'],
            scope='independent input buffers; not a dependency-correct model MoE/layer fusion'))
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
    if (exact.get('schema') != 'own-runtime.iq3.packet7.device-window.v1' or exact.get('passed') is not True
        or exact.get('card') != card or exact.get('prepared_sha256') != sha(MANIFEST)):
        raise ValueError('matching successful packet7 exactness required')
    out.mkdir(parents=True)
    record = dict(schema='own-runtime.iq3.packet7.timing.v1', passed=False, device_executed=True, card=card,
        prepared_sha256=sha(MANIFEST), prepared_manifest=manifest, exactness_sha256=sha(exactness), plan=plan(), layers=[],
        environment={k: v for k, v in os.environ.items() if k.startswith(('SYCL_', 'ZE_', 'ONEAPI_', 'UR_')) or k == 'OMP_NUM_THREADS'})
    try:
        record['ceiling'] = run_ceiling(out)
        sessions = [(l,'kernels') for l in record['plan']['layers']] + [(record['plan']['layers'][0],'groups')]
        for layer, phase in sessions:
            destination = out / ('layer%d-%s' % (layer['layer'], phase))
            command = [str(BUILD / 'device/device-timing'), '--authorized-device-window', str(card),
                str(INPUTS / ('layer%d.tsv' % layer['layer'])), str(destination / 'native.json'), str(destination / 'census.json'), phase]
            window = watch(command, destination)
            raw = json.loads((destination / 'native.json').read_text())
            census = json.loads((destination / 'census.json').read_text())
            validate_census(census, layer)
            summary = summarize(raw, layer)
            record['layers'].append(dict(layer=layer['layer'], phase=phase, window=window, native=raw, census=census, summary=summary,
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

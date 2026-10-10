#!/usr/bin/env python3
"""Read a frozen regular-file window; no runtime imports, probes, or run writes.

Run with nice -n 19 env OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1
/home/steve/.venvs/ltx25-baseline/bin/python -B <this file>.
Only continuation133-memory-analysis.json beside this script is written.
"""
import hashlib
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
GIB = 2 ** 30
RUN132 = ROOT / ('encoder-server-continuation-stream-132-frame-dg1-adcone-bo1-pa1-smfp-'
                 'two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-dseager-display-ra0-ssfull-'
                 'ddxpu2-gc60-ssbackground-sdc1-mi-cmreplica-release-audioxpu2')
PREFIX129 = ('encoder-server-continuation-stream-129-frame-dg0-adcone-bo1-pa1-smfp-'
             'two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-gc60-ssbackground-sdc1-mi')
RUNS129 = [ROOT / (PREFIX129 + '.completed-' + stamp)
           for stamp in ['20261010T114323Z', '20261010T124818Z']]
SOURCES = {}


def read(path, parse=True):
    raw = path.read_bytes()
    SOURCES[str(path)] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    return json.loads(raw) if parse else raw.decode()


def phase_samples(rows, failure=None):
    out = {}
    def add(phase, free):
        bucket = out.setdefault(phase, {f'xpu:{i}': [] for i in range(4)})
        for device in bucket:
            bucket[device].append(free[device])
    for row in rows:
        for phase in ['before', 'after']:
            add(phase, row['memory'][phase]['free'])
        for phase in row['memory']['conditioning']:
            for position in ['before', 'after']:
                add(phase['stage'] + '-' + position, phase['free_' + position])
    if failure:
        for row in failure['controller_receipts']:
            if 'snapshot' in row:
                add(row['event'].replace('conditioning-', ''),
                    row['snapshot']['physical_free_bytes'])
    return {phase: {device: {'count': len(values), 'minimum_bytes': min(values),
                            'minimum_gib': min(values) / GIB}
                    for device, values in devices.items()}
            for phase, devices in out.items()}


def all_minima(phases):
    return {device: min(p[device]['minimum_bytes'] for p in phases.values())
            for device in [f'xpu:{i}' for i in range(4)]}


def text_timing(rows):
    values = []
    reused = 0
    for row in rows:
        if row.get('stream_seq', -1) < 0:
            continue
        if row['reuse_text']:
            reused += 1
            continue
        timing = row['timing_ns']
        values.append((timing['stream_text_start'] - timing['text_start']) / 1e9)
    return {'definition': 'stream_text_start minus text_start, seconds',
            'encoded_cut_count': len(values), 'reuse_count': reused,
            'minimum_s': min(values), 'median_s': statistics.median(values),
            'maximum_s': max(values)}


def main():
    inventory = read(HERE / 'continuation130-residency.json')
    previous = read(HERE / 'continuation131-memory-analysis.json')
    read(HERE.parent.parent / 'notes/2026-10-04-lossless-gpu-work-reduction-survey.md', parse=False)
    read(ROOT / 'probe-copy-05.log', parse=False)
    packet = ROOT / 'prepared-continuation-stream-132'
    for name in ['ltx_graph_text_encoder.py', 'ltx_graph_capture.py', 'ltx_text_shard.py']:
        read(packet / 'source/scripts' / name, parse=False)
    read(packet / 'source/comfy/text_encoders/gemma4.py', parse=False)
    rows132 = [read(p) for p in sorted((RUN132 / 'receipts').glob('receipt-*.json'))]
    decodes132 = [read(p) for p in sorted((RUN132 / 'receipts').glob('decode-*.json'))]
    assert len(rows132) == len(decodes132) == 7, 'Frozen 132 window changed'
    failure = read(RUN132 / 'stream-failure-stream132-qrepeat-c000001.json')
    prep = read(RUN132 / 'stream-preparation.json')
    probe = read(RUN132 / 'stream-after-stream132-window-probe.json')
    host = read(RUN132 / 'host-components-01-control-after-construction-memory.json')
    p132 = phase_samples(rows132, failure)
    baseline129 = []
    for run in RUNS129:
        paths = sorted((run / 'receipts').glob('receipt-*.json'))[:210]
        assert len(paths) == 210
        rows = [read(p) for p in paths]
        assert sum(r.get('stream_seq', -1) >= 0 for r in rows) == 201
        phases = phase_samples(rows)
        baseline129.append({'run': str(run), 'selection': 'lexical first 210 receipts: 9 qualification + 201 stream',
                            'phase_minima': phases, 'all_phase_minimum_bytes': all_minima(phases),
                            'text_cut_timing': text_timing(rows)})
    captured = next(d for d in decodes132 if d['decoder']['new_captures'] == 1)
    growth = captured['decoder']['pool']['growth_bytes']
    assert growth == 3806330880
    failed = next(r for r in failure['controller_receipts']
                  if r.get('event') == 'conditioning-B-before')
    failed_free = failed['snapshot']['physical_free_bytes']['xpu:3']
    replica_min = min(d['display_replica']['residency']['last_decode']['before']['free_bytes']
                      for d in decodes132)
    layer = inventory['text_layer_bytes']
    windows = [64, 128, 256, 512, 1024]
    # Owned static x, attention mask and BOTH rotary matrices; two worker threads.
    static_per_layer = 2 * 4 * (sum(windows) * (3840 + 1024 + 512)
                              + sum(w * w for w in windows))
    assert static_per_layer == 96501760
    minima129 = baseline129[0]['all_phase_minimum_bytes']
    scenarios = []
    for boundary in [26, 27, 28, 32, 36, 40, 48]:
        count = boundary - 24
        weights = sum(layer[str(i)] for i in range(24, boundary))
        static = count * static_per_layer
        scenarios.append({
            'boundary': boundary, 'moved_layers': list(range(24, boundary)),
            'weight_bytes': weights, 'weight_gib': weights / GIB,
            'owned_graph_static_estimate_bytes': static,
            'owned_graph_static_estimate_gib': static / GIB,
            'physical_release_is_measured': False,
            '132_replica2_weight_only_screen_margin_gib': {
                'xpu:2': (replica_min - weights) / GIB - 2 - 5.640625 - .75,
                'xpu:3': (failed_free + weights) / GIB - 9 - .75},
            '129_native3_with_static_graph_estimate': {
                'xpu2_free_gib': (minima129['xpu:2'] - weights - static) / GIB,
                'xpu2_margin_over_floor_and_band_gib': (minima129['xpu:2'] - weights - static) / GIB - 2 - .75,
                'xpu3_free_after_observed132_graph_gib': (minima129['xpu:3'] + weights + static - growth) / GIB,
                'xpu3_margin_after_full5gib_reserve_floor_band_gib': (minima129['xpu:3'] + weights + static) / GIB - 5 - 9 - .75},
        })
    secondary = inventory['text_secondary_bytes']
    doc = {
        'schema': 'ltx.continuation133.memory-analysis.v1',
        'scope': 'CPU stdlib regular-file analysis only; no device/runtime calls or existing-run writes',
        'units': 'bytes; GiB=2**30; decimal GB/s=10**9 bytes/s',
        'sources': SOURCES,
        '132': {'run': str(RUN132), 'completed_receipts': 7, 'phase_minima': p132,
                'failure_event': failed['event'], 'failure_free_xpu3_bytes': failed_free,
                'floor_deficit_bytes': 9 * GIB - failed_free,
                'floor_plus_band_deficit_bytes': int(9.75 * GIB) - failed_free,
                'first_capture_admission': captured['cone_graph_memory_admission'],
                'observed_capture_reserved_growth_bytes': growth,
                'observed_capture_reserved_growth_gib': growth / GIB,
                'old145_temporal_squared_estimate_bytes': previous['growth_estimate145']['temporal_squared_bytes'],
                'minimum_replica2_before_display_bytes': replica_min,
                'replica2_screen_spare_gib': replica_min / GIB - 2 - 5.640625 - .75,
                'preparation_snapshot': prep['snapshot'],
                'window_probe_elapsed_s': (probe['end_ns'] - probe['start_ns']) / 1e9,
                'window_probe_is_recapture_cost': False,
                'encoded_text_intervals_s': [
                    (r['timing_ns']['stream_text_start'] - r['timing_ns']['text_start']) / 1e9
                    for r in rows132 if r['timing_ns'].get('text_start')],
                'host_memavailable_bytes': host['observed']['bytes']['MemAvailable']},
        '129': baseline129,
        'inventory': {'text_primary_bytes': inventory['text_primary_bytes'],
                      'text_secondary_bytes': secondary, 'layer_bytes': layer,
                      'nonlayer_bytes': inventory['text_nonlayer_bytes'],
                      'parent_static': inventory['parent_static_inventory']},
        'static_graph_estimate': {'windows': windows, 'workers': 2, 'dtype_bytes': 4,
                                  'x_width': 3840, 'rotary_values_per_token': [1024, 512],
                                  'mask_shape': '[1,1,W,W]', 'per_layer_bytes': static_per_layer,
                                  'graph_output': 'aliases owned static x; no additional output allocation',
                                  'excludes': ['private allocator segment rounding',
                                               'shared transient graph pools', 'latest staged kwargs cache'],
                                  'physical_release_is_measured': False},
        'boundary_scenarios': scenarios,
        'host_reload': {'shard_bytes': secondary, 'measured_link_bandwidth_found': False,
                        'assumed_decimal_bandwidth_bytes_per_s': [5_000_000_000, 10_000_000_000],
                        'one_way_reload_s': [secondary / 10e9, secondary / 5e9],
                        'amortized_four_chunk_s': [secondary / 10e9 / 4, secondary / 5e9 / 4],
                        'graph_recapture_cost_included': False,
                        'projected_idle_xpu3_free_gib': (failed_free + secondary) / GIB},
        '169': {'matched_native3_legacy_graph_receipt_available': False,
                'available_runs': [str(ROOT / p) for p in [
                    'encoder-server-continuation-stream-123b-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f169-auxxpu2',
                    'encoder-server-continuation-stream-127-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f169-dseager-display-ra0-ssfull-ddxpu2-dwparallel-ssbackground']],
                'admissibility': 'unknown, no native admission claim'},
        'limits': ['Phase samples are not instantaneous peak bounds.',
                   'Static allocation bytes are not a guaranteed change in physical free memory.',
                   'Observed graph growth includes proof/warmup/allocator changes, not an isolated peak.',
                   'Wholetext2 graph-pool consolidation has no measured receipt.',
                   'Native text cross-card identity and repeated period remain unmeasured.'],
    }
    (HERE / 'continuation133-memory-analysis.json').write_text(json.dumps(doc, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'sources': len(SOURCES), '132_receipts': 7, '129_receipts': 420,
                      'static_per_layer_bytes': static_per_layer, 'graph_growth_bytes': growth}))


if __name__ == '__main__':
    main()

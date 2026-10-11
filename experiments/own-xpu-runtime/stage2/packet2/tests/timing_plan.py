"""CPU-only, census-bound M=1 timing plan and receipt math (stdlib only)."""
import hashlib
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[3]
OWNER = HERE.parents[1] / 'stage1/packet3-prep'
CENSUS = ROOT / 'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json'
MODEL = Path('/mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS')
ROUTES = [0, 7, 31, 63, 127, 255, 319, 383, 447, 511]
LAYOUT = {'F32': (1, 4), 'BF16': (1, 2), 'Q8_0': (32, 34),
          'Q6_K': (256, 210), 'IQ2_S': (256, 82), 'IQ3_S': (256, 110),
          'IQ4_NL': (32, 18)}
ITERATIONS = 20
CHUNK = 8 * 1024**2


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + '\n')


def make_plan():
    census = json.loads(CENSUS.read_text())
    roof = json.loads((HERE / 'roofline.json').read_text())
    if roof['census_sha256'] != sha(CENSUS):
        raise ValueError('roofline/census identity mismatch')
    layers = []
    for index, kind in enumerate(('ordinary_gdn', 'ple_gdn', 'upgraded_gdn', 'qsa')):
        tensors = [t for t in census['tensors'] if t['layer'] == index
                   and t['component'] not in ('embedding', 'ple_lookup')]
        by_name = {t['name']: t for t in tensors}
        # GEMV subsequence of packet3/step/plan.hpp, with the intervening
        # nonlinear/state operators explicitly excluded from this diagnostic.
        order = (['ple_key', 'ple_value'] if index == 1 else [])
        order += ['hc_attn_down', 'hc_attn_up', 'hc_attn_inject']
        order += (['attn_q', 'attn_k', 'attn_v', 'indexer.q_proj', 'indexer.k_proj', 'attn_output']
                  if index == 3 else ['attn_qkv', 'attn_gate', 'ssm_alpha', 'ssm_beta', 'ssm_out'])
        order += ['hc_ffn_down', 'hc_ffn_up', 'hc_ffn_inject', 'ffn_gate_inp',
                  'ffn_gate_exps', 'ffn_up_exps', 'ffn_down_exps',
                  'ffn_gate_shexp', 'ffn_up_shexp', 'ffn_down_shexp', 'ffn_gate_inp_shexp']
        jobs = []
        for suffix in order:
            t = by_name[f'blk.{index}.{suffix}.weight']
            dims = t['dimensions']
            k, rows = dims[0], dims[1] if len(dims) > 1 else 1
            experts = dims[2] if len(dims) == 3 else 1
            block, size = LAYOUT[t['type']]
            if k % block or k // block * size * rows * experts != t['bytes']:
                raise ValueError('packed extent mismatch: ' + t['name'])
            if experts not in (1, 512):
                raise ValueError('expert bank extent')
            rb = k // block * size
            # Full small tensors; for larger tensors, four real packed rows
            # become an explicitly tiled packed fixture. No bulk shard read.
            seed_bytes = t['bytes'] if t['bytes'] <= 65536 else min(4 * rb, 65536 // rb * rb)
            jobs.append(dict(name=t['name'], type=t['type'], type_id=t['type_id'],
                rows=rows, columns=k, experts=experts, routes=ROUTES if experts == 512 else [],
                row_bytes=rb, weight_bytes=t['bytes'], packed_active_bytes=rows * rb * (10 if experts == 512 else 1),
                seed_bytes=seed_bytes, fill='real_tensor' if seed_bytes == t['bytes'] else 'real_packed_fixture_tiled',
                shard=Path(t['shard']).name, absolute_offset=t['file_offsets'][0]))
        omitted = [dict(name=t['name'], bytes=t['bytes'], reason='norm, convolution or recurrent control; not a GEMV')
                   for t in tensors if t['name'] not in {j['name'] for j in jobs}]
        total = sum(j['packed_active_bytes'] for j in jobs)
        reference = roof['layers'][index]
        if total + sum(t['bytes'] for t in omitted) != reference['packed_active_bytes']:
            raise ValueError('GEMV + excluded bytes must equal full roofline layer')
        layers.append(dict(layer=index, kind=kind, jobs=jobs, excluded=omitted,
            gemv_active_bytes=total, resident_weight_bytes=sum(j['weight_bytes'] for j in jobs),
            launches_per_layer=len(jobs), roofline=reference,
            gemv_floor_ms={str(r): total / (r * 1e6) for r in (507, 537)}))
    # Copies, 1 untimed warmup + 20 timed kernels, ordinary GDN sequence,
    # route status readbacks, final idle marker. The owner's ledger is bounded.
    events = 1 + sum(math.ceil(j['weight_bytes'] / CHUNK) + 1 + (2 if j['experts'] == 512 else 0)
        + 21 + (1 if j['experts'] == 512 else 0) for l in layers for j in l['jobs'])
    events += 21 * layers[0]['launches_per_layer']
    if events >= 4096:
        raise ValueError('owner event ledger would overflow')
    return dict(schema='own-runtime.iq3.packet2.timing-plan.v1', measured=False,
        census_sha256=sha(CENSUS), roofline_sha256=sha(HERE / 'roofline.json'),
        iterations=ITERATIONS, warmup_iterations=1, subgroup=16, M=1,
        activation='BF16', output='BF16', accumulate='FP32', diagnostic_fp32=False,
        queue='single in-order, profiling enabled, explicit owner dependency chain',
        scope='warm GEMV diagnostic; fixed inputs/routes; not full decode or a speed/quality headline',
        chunk_bytes=CHUNK, event_count_upper_bound=events, deadline_seconds=120,
        layers=layers)


def metrics(samples, packed_bytes):
    if len(samples) != ITERATIONS or any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0 for x in samples):
        raise ValueError('need 20 positive finite samples')
    median, minimum = statistics.median(samples), min(samples)
    gbps = packed_bytes / (median * 1e6)
    return dict(median_ms=median, min_ms=minimum, packed_bytes=packed_bytes,
                effective_GB_s=gbps, bandwidth_ratio={str(r): gbps / r for r in (507, 537)},
                latency_over_floor={str(r): median / (packed_bytes / (r * 1e6)) for r in (507, 537)})


def event_ms(events):
    if len(events) != ITERATIONS:
        raise ValueError('need 20 events')
    for e in events:
        if set(e) != {'start_ns', 'end_ns'} or any(type(v) is not int or v < 0 for v in e.values()) or e['end_ns'] <= e['start_ns']:
            raise ValueError('invalid profiling timestamp')
    if any(a['end_ns'] > b['start_ns'] for a, b in zip(events, events[1:])):
        raise ValueError('in-order event overlap')
    return [(e['end_ns'] - e['start_ns']) / 1e6 for e in events]


def summarize(raw, plan):
    """Fail closed on missing cases, unsafe teardown, false routes or fake rates."""
    if raw.get('schema') != 'own-runtime.iq3.packet2.timing-native.v1' or raw.get('error') != '':
        raise ValueError('native failure')
    t = raw['teardown']
    if not (t['safe_to_exit'] is True and t['idle_marker_complete'] is True
            and t['live_bytes'] == t['in_flight'] == t['exit_code'] == 0
            and t['status'] == 'complete' and t['error'] == ''
            and 'context-released' in t['sequence'] and raw['device'] == t['backend']):
        raise ValueError('unsafe teardown')
    expected = [j for l in plan['layers'] for j in l['jobs']]
    if [r['name'] for r in raw['kernels']] != [j['name'] for j in expected]:
        raise ValueError('kernel coverage/order')
    rows = []
    for r, j in zip(raw['kernels'], expected):
        if r['route_status'] != ([0] * 10 if j['experts'] == 512 else []):
            raise ValueError('invalid route status')
        rows.append(dict(name=j['name'], **metrics(event_ms(r['events']), j['packed_active_bytes'])))
    sequence = raw['sequence']
    if sequence['layer'] != 0 or sequence['launches_per_layer'] != plan['layers'][0]['launches_per_layer']:
        raise ValueError('sequence coverage')
    if len(sequence['iterations']) != ITERATIONS:
        raise ValueError('sequence iterations')
    spans, sums, gaps, walls, submits = [], [], [], [], []
    for iteration in sequence['iterations']:
        events = iteration['events']
        if len(events) != sequence['launches_per_layer']:
            raise ValueError('sequence launch count')
        if any(type(v) is not int or v < 0 for e in events for v in e.values()):
            raise ValueError('sequence timestamps')
        durations = [e['end_ns'] - e['start_ns'] for e in events]
        if any(v <= 0 for v in durations) or any(a['end_ns'] > b['start_ns'] for a, b in zip(events, events[1:])):
            raise ValueError('sequence ordering')
        span = (events[-1]['end_ns'] - events[0]['start_ns']) / 1e6
        spans.append(span); sums.append(sum(durations) / 1e6); gaps.append(span - sums[-1])
        walls.append(iteration['host_wall_ms']); submits.append(iteration['host_submit_ms'])
        if not 0 <= submits[-1] <= walls[-1] or not math.isfinite(walls[-1]):
            raise ValueError('host clock sample')
    return dict(kernels=rows, sequence=dict(layer=0, launches_per_layer=sequence['launches_per_layer'],
        **metrics(spans, plan['layers'][0]['gemv_active_bytes']),
        median_kernel_sum_ms=statistics.median(sums), median_queue_gap_ms=statistics.median(gaps),
        median_host_submit_ms=statistics.median(submits), median_host_wall_ms=statistics.median(walls),
        wall_definition='host submit through owner completion wait; includes 1 ms polling granularity',
        scope='GEMV subsequence only; intervening nonlinear/state ops absent, fixed input buffers'))


def validate_census(censuses, plan):
    if len(censuses) != 5:
        raise ValueError('four resident-layer censuses plus final released census required')
    for census, layer in zip(censuses[:4], plan['layers']):
        live = [r for r in census['allocations'] if r['live']]
        weights = [r for r in live if r['category'] == 'weights']
        expected = {j['name'] + '/weights': j['weight_bytes'] for j in layer['jobs']}
        if {r['label']: r['bytes'] for r in weights} != expected or len(weights) != len(expected):
            raise ValueError('resident weight census differs from plan')
        if any(r['memory'] != 'device' for r in weights):
            raise ValueError('weight memory class differs')
        for memory in ('device', 'host-pinned', 'host-shadow'):
            if census['totals'][memory] != sum(r['bytes'] for r in live if r['memory'] == memory):
                raise ValueError('census totals disagree')
    if any(censuses[-1]['totals'].values()) or any(r['live'] for r in censuses[-1]['allocations']):
        raise ValueError('final census still owns allocations')

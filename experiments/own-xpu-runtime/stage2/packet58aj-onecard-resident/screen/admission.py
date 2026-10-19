"""CPU-only receipt census and independent calibration replay for packet58x."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
from device_memory import parse_size
import resource
import shutil
import statistics

P = Path(__file__).resolve().parent
ROOT = P.parents[4]
from frozen_inputs import FROZEN
STAGE = FROZEN/'experiments/own-xpu-runtime/stage2'
GIB = 1024**3
PINS = {}


def pin(path):
    with path.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    PINS[str(path.relative_to(ROOT))] = digest
    return path


def read(path):
    return json.loads(pin(path).read_text())


def load(name, path):
    spec = importlib.util.spec_from_file_location('p58ag_'+name, pin(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def derive():
    base = read(STAGE/'packet58u-host-admission/base-plan.json')
    peaks = read(STAGE/'packet58u-host-admission/measured-peaks.json')
    rows = []
    for packet in ('packet58p-onecard-record', 'packet58r-onecard-v5',
                   'packet58t-resident-lookups', 'packet58v-async-cache'):
        for path in sorted((STAGE/packet/'evidence').glob('card*/**/window.json')):
            if path.parent.name.startswith('K1'):
                continue
            window = json.loads(path.read_text())
            if not window.get('passed'):
                continue
            window = read(path)  # Bind completed immutable receipts only.
            post = window['postload_memory']
            assert post['complete_postload'] and post['full_cache_bytes'] == 18_000_000_000
            census = read(path.parent/'run/run/census.json')[0]
            native = read(path.parent/'run/run/memory.json')
            raw = pin(path.parent/'run/run/drm-memory-after_load.txt').read_text()
            drm = parse_size(next(line.split(':', 1)[1] for line in raw.splitlines()
                                  if line.startswith('drm-total-vram0:')))
            device = sum(a['bytes'] for a in census['allocations'] if a['live'] and a['memory']=='device')
            assert device == native['peak_device_bytes_per_owner']
            assert sum(a['bytes'] for a in census['allocations'] if a['live'] and a['category']=='KV') == 116391936
            samples = [json.loads(line) for line in pin(path.parent/'host-memory.jsonl').read_text().splitlines()]
            normalized = []
            for sample in samples:
                assert 'sensor_error' not in sample
                # Resident lookups replace file-backed allowance, never add twice.
                file_allowance = base['census']['file_backed_nonexpert_bytes']
                if packet=='packet58t-resident-lookups':
                    file_allowance -= 29321610240
                normalized.append(sample['pinned_expert_bytes']+sample['gpuactive_shadow_bytes']+
                                  sample['anonymous_bytes']+file_allowance)
            rows.append(dict(path=str(path.relative_to(ROOT)), device_bytes=device,
                             drm_bytes=drm, driver_overhead_bytes=drm-device,
                             measured_normalized_peak_bytes=max(normalized),
                             shadow_peak_bytes=post['peak_shadow_bytes'],
                             admitted_available_bytes=window['memory_admission']['available_bytes']))
    assert {r['path'].split('/')[3] for r in rows} == {
        'packet58p-onecard-record','packet58r-onecard-v5','packet58t-resident-lookups','packet58v-async-cache'}
    device_categories = dict(base['device_categories'])
    device_categories['async_publication_staging'] = 1179648
    driver = max(512*1024**2, max(r['driver_overhead_bytes'] for r in rows)+128*1024**2)
    noncache = sum(device_categories.values())-18_000_000_000
    cap = (32_000_000_000-1_500_000_000-driver-noncache)//256*256
    extra = cap-18_000_000_000
    device_categories['expert_cache_arena'] = cap
    # Never shrink 58u's empirical floor or its 4 GiB margin. Cover new cache
    # backing in full, independently of the unchanged live shadow stop.
    measured = max(peaks['profiles']['tile16']['measured_normalized_peak_bytes'],
                   *(r['measured_normalized_peak_bytes'] for r in rows))
    new_host = measured+4*GIB+8*GIB+32*1024**2+1179648+extra
    historical_available = min(r['admitted_available_bytes'] for r in rows)
    assert historical_available > new_host
    return dict(schema='packet58x.admission.v1', device_executed=False,
                device_categories=device_categories, cache_bytes=cap, extra_cache_bytes=extra,
                old_cache_bytes=18_000_000_000, driver_allowance_bytes=driver,
                device_owned_bound_bytes=sum(device_categories.values()), device_reserve_bytes=1_500_000_000,
                physical_capacity_floor_bytes=32_000_000_000,
                physical_bound_with_driver_bytes=sum(device_categories.values())+driver,
                measured_host_peak_bytes=measured, host_margin_bytes=4*GIB, host_reserve_bytes=8*GIB,
                host_required_available_bytes=new_host, host_bound_bytes=new_host-8*GIB,
                historical_available_floor_bytes=historical_available,
                historical_host_margin_bytes=historical_available-new_host,
                shadow_stop_bytes=4*GIB, windows=rows,
                transient_policy='Retain all original 1 GiB workspace, 1 GiB transaction, 256 MiB transfer, full 4K BF16 KV, double pointer tables; add async publication buffer. Fills write inside the one arena, never allocate a second arena.',
                live_admission_required=True)


def replay(capacity):
    J = load('p58x_replay', STAGE/'packet58j-onecard-port/cache_policy_replay.py')
    pin(STAGE/'packet55-feasibility/analysis/locality.py')
    window = STAGE/'packet55-feasibility/route/evidence/cards23-a'
    manifest, summary, bindings = J.L.inputs(window, window/'routes.jsonl.gz')
    compact = STAGE/'packet58i-onecard-attribution/route-inputs'
    binding = read(compact/'binding.json')
    assert binding['source_bindings'] == bindings
    capacities = sorted(set([18_000_000_000,19_000_000_000,20_000_000_000,21_000_000_000,capacity]))
    result = []
    for cap in capacities:
        arena = J.GlobalArena(cap)
        stats = {phase:J.stat() for phase in ('prefill','decode')}
        for prompt in binding['prompts']:
            path = pin(compact/prompt['file'])
            assert PINS[str(path.relative_to(ROOT))] == prompt['sha256']
            with gzip.open(path,'rt') as stream:
                for line in stream:
                    decode,layer,ids = json.loads(line)
                    misses = arena.route(layer,ids)
                    J.update(stats['decode' if decode else 'prefill'],layer,misses)
        result.append(dict(capacity_bytes=cap, phases={k:J.finish(v) for k,v in stats.items()},
                           # A normalized full-target-position equivalent, not emitted speculative tokens.
                           decode_miss_bytes_per_48_layer_equivalent=48*stats['decode']['miss_bytes']/stats['decode']['route_visits'],
                           decode_expert_hit_fraction=1-stats['decode']['missing_experts']/(10*stats['decode']['route_visits'])))
        print('replayed',cap,result[-1]['decode_expert_hit_fraction'],flush=True)
    return dict(source_bindings=bindings,rows=result,
                caveats=binding['caveats']+['Empty cache persists across held-out prompts; no prompt/KV cache reuse.',
                    '48-layer equivalent is not an emitted-token measurement; preserve all rejected speculative visits.',
                    'Serial global-LRU proxy; async delayed publication may change hits.'])


def main():
    assert shutil.disk_usage('/').free>=27_000_000_000
    admission = derive()
    replayed = replay(admission['cache_bytes'])
    measurement = read(STAGE/'packet58v-async-cache/evidence/measurement.json')
    record = next(r for r in measurement['records'] if r['path'].endswith('card0-58p-a/WS128'))
    ratio = replayed['rows'][-1]['phases']['decode']['miss_bytes']/replayed['rows'][0]['phases']['decode']['miss_bytes']
    # Charge only the 25 GB/s fill-DMA proxy: do not scale away fixed publication,
    # policy cost, or credit an unmeasured reduction in zero-copy execution.
    saved_ms = record['metric_events_2_100']['fill_bytes']/25_000_000*(1-ratio)
    summary_path = STAGE/'packet58p-onecard-record/evidence/card0-58p-a/WS128/summary.json'
    summary = read(summary_path)
    caches = [json.loads(line) for line in pin(summary_path.parent/'run/run/cache.jsonl').read_text().splitlines()]
    assert all(row['epoch']==i+1 for i,row in enumerate(caches))
    by_class = {};position=0;prompt_projections=[]
    for request in summary['requests']:
        # Native timestamps bound each exact prompt's conventional 99 intervals.
        timings = pin(summary_path.parent/'run/run'/request['prompt_id']/'timings.jsonl')
        events = [json.loads(line) for line in timings.read_text().splitlines()]
        assert [r['generated_index'] for r in events]==list(range(1,request['output_tokens']+1))
        prefill=request['prompt_tokens']-1
        charged=caches[position+prefill+1:position+prefill+100]
        assert len(charged)==99
        position+=prefill+request['output_tokens']
        prompt_saved_ms=statistics.mean(row['fill_bytes'] for row in charged)/25_000_000*(1-ratio)
        # Reuse the receipt's individually measured rate, not aggregate reciprocals.
        stamps = request['token_timestamps']
        rate = 99/(stamps[99]-stamps[0])
        assert abs(rate-request['tok_s_1_100_intervals_after_ttft'])<1e-9
        projected = 1000/(1000/rate-prompt_saved_ms)
        by_class.setdefault(request['prompt_class'],[]).append(projected)
        prompt_projections.append(dict(prompt_id=request['prompt_id'],measured_rate=rate,
                                       projected_rate=projected,charged_intervals=99,
                                       saved_ms_per_interval=prompt_saved_ms))
    assert position==len(caches)
    projected = statistics.median(statistics.median(v) for v in by_class.values())
    gain = projected/record['rate']-1
    decision = admission['extra_cache_bytes']>=2_000_000_000 and gain>=0.02
    result = dict(admission=admission,replay=replayed,
                  projection=dict(measured_anchor_tok_s=record['rate'],miss_byte_ratio=ratio,
                                  fill_dma_proxy_GB_s=25, saved_ms_per_position=saved_ms,
                                  projected_tok_s=projected,projected_gain_fraction=gain,
                                  per_prompt=prompt_projections,
                                  measured=False, transfer_assumption='Independent calibration miss ratio transfers to one-card serial fill payload; no zero-copy saving credited.'),
                  proceed=decision,sources=PINS)
    (P/'admission.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(capacity=admission['cache_bytes'],host_required=admission['host_required_available_bytes'],gain=gain,proceed=decision)))


if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*GIB,4*GIB))
    main()

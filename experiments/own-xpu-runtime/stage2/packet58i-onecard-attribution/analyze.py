#!/usr/bin/env python3
"""Read frozen receipts; write only this packet. No runtime/device imports."""
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PARENT = HERE.parent / 'packet58g-onecard'
BASE = PARENT / 'evidence/card0-58g-a'
INPUTS = {}
SAVED_INPUTS = json.loads((HERE/'inputs.json').read_text()) if (HERE/'inputs.json').exists() else {}


def read(path):
    path = Path(path)
    key = str(path.relative_to(ROOT))
    if key in SAVED_INPUTS:
        raw = gzip.decompress((HERE/SAVED_INPUTS[key]['archive']).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == SAVED_INPUTS[key]['sha256'], key
    else:
        raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    archive = HERE / 'inputs' / (digest + '.gz')
    archive.parent.mkdir(exist_ok=True)
    if not archive.exists():
        archive.write_bytes(gzip.compress(raw, mtime=0))
    INPUTS[key] = dict(sha256=digest, bytes=len(raw), archive=str(archive.relative_to(HERE)))
    return raw.decode()


def js(path):
    return json.loads(read(path))


def lines(path):
    return [json.loads(x) for x in read(path).splitlines() if x.strip()]


def stats(values):
    v = sorted(values)
    if not v:
        return dict(count=0, mean=None, median=None, p10=None, p90=None)
    return dict(count=len(v), mean=st.mean(v), median=st.median(v),
                p10=v[max(0, math.ceil(len(v)*.1)-1)], p90=v[math.ceil(len(v)*.9)-1])


def summarize(rows):
    timing = {k: stats([r['timing'][k] for r in rows]) for k in
              ('wall_ms', 'prepare_ms', 'enqueue_loop_ms', 'enqueue_including_wait_ms',
               'wait_ms', 'transfer_wall_ms', 'kernel_submissions', 'host_waits')}
    cache = {k: stats([r['cache'][k] for r in rows]) for k in
             ('wall_ms', 'fill_bytes', 'fills', 'evictions', 'resident_bytes')}
    cache['expert_hit_rate'] = 1 - sum(r['cache']['fills'] for r in rows)/(480*len(rows)) if rows else None
    cache['logical_byte_hit_rate'] = 1 - sum(r['cache']['fill_bytes'] for r in rows)/(949760000*len(rows)) if rows else None
    cache['layer2_hit_rate'] = 1 - sum(r['layer2_misses'] for r in rows)/(10*len(rows)) if rows else None
    cache['ordinary_layers_pooled_hit_rate'] = 1 - sum(r['cache']['fills']-r['layer2_misses'] for r in rows)/(470*len(rows)) if rows else None
    cache['layer_hit_rates'] = {str(i): cache['layer2_hit_rate'] if i == 2 else None for i in range(48)}
    cache['pci_e_read_bytes_measured'] = None
    cache['pure_copy_device_ms'] = None
    cache['logical_miss_bytes_equal_fill_bytes'] = True
    timing['wall_less_cache_ms'] = stats([r['timing']['wall_ms']-r['cache']['wall_ms'] for r in rows])
    timing['overlapping_accounting_residual_ms'] = stats([
        r['timing']['wall_ms']-r['timing']['prepare_ms']-r['timing']['enqueue_loop_ms']-r['timing']['wait_ms'] for r in rows])
    timing['prepare_wait_overlap_unknown_upper_ms'] = stats([min(r['timing']['prepare_ms'],r['timing']['transfer_wall_ms']) for r in rows])
    return dict(positions=len(rows), timing=timing, cache=cache,
                operator_ms={k: None for k in ('experts','HC','recurrence','attention','head','other')},
                all_operator_fields_zero=all(r['timing']['gemv_device_ms']==r['timing']['non_gemv_device_ms']==0 for r in rows),
                note='Host spans overlap device execution; prepare includes waits, cache includes waits. Do not sum them as exclusive costs.')


def main():
    windows = {}
    all_rows = []
    for name in ('KD','W2m','WS','WS128x','WS128'):
        base = BASE/name
        window, summary = js(base/'window.json'), js(base/'summary.json')
        receipt = js(base/'run/run/receipt.json')
        census = js(base/'run/run/census.json')
        caches = lines(base/'run/run/cache.jsonl')
        assert window['passed'] and summary['passed'] and receipt['profiling'] is False
        pos = 0
        rows = []
        per_prompt = {}
        for request in summary['requests']:
            prompt = request['prompt_id']
            folder = base/'run/run'/prompt
            pre, gen = lines(folder/'prefill-timings.jsonl'), lines(folder/'timings.jsonl')
            counter = js(folder/'cache-stats.json')
            assert len(pre) == request['prompt_tokens']-1 and len(gen)==request['output_tokens']
            prompt_rows = []
            for timing in pre+gen:
                cache = caches[pos]
                pos += 1
                assert cache['epoch']==pos
                # 47 layers use 1,971,200 B/expert; only layer2 uses 2,329,600.
                # All 480 selected entries are touched before eviction, and fit together.
                extra = cache['fill_bytes'] - cache['fills']*1971200
                assert extra % 358400 == 0
                layer2 = extra//358400
                assert 0 <= layer2 <= 10 and 0 <= cache['fills']-layer2 <= 470
                row = dict(window=name, prompt=prompt, prompt_class=request['prompt_class'],
                           phase='prefill' if timing['kind']=='prefill_token' else 'decode',
                           timing=timing, cache=cache, layer2_misses=layer2,
                           inferred_expert_hit_rate=1-cache['fills']/480,
                           layer2_hit_rate=1-layer2/10,
                           ordinary_layers_pooled_hit_rate=1-(cache['fills']-layer2)/470,
                           per_ordinary_layer_hit_rate=None)
                rows.append(row)
                prompt_rows.append(row)
            # Counters persist across request resets, just like immutable cache contents.
            assert sum(x['cache']['fill_bytes'] for x in rows)==counter['fill_bytes_total']
            assert sum(x['cache']['fills'] for x in rows)==counter['fills_total']
            if len(gen)>=100 and request.get('token_timestamps'):
                times=request['token_timestamps']
                metric_rows=[r for r in prompt_rows if r['phase']=='decode' and 2 <= r['timing']['generated_index'] <=100]
                per_prompt[prompt]=dict(prompt_class=request['prompt_class'], interval_count=99,
                    measured_interval_ms=(times[99]-times[0])*1000,
                    recorded_rate=request['submission100']['rate'],
                    attribution=summarize(metric_rows))
        assert pos==len(caches)
        for rel, digest in window['native_files'].items():
            source=str((base/rel).relative_to(ROOT))
            if source in INPUTS:
                assert INPUTS[source]['sha256']==digest, source
        windows[name]=dict(passed=window['passed'],timing_claim_eligible=summary['timing_claim_eligible'],
            profiling=receipt['profiling'],timing=receipt['timing'],
            strict_final_gate=summary['realistic_final_gate'],
            class_metric=summary['class_balanced_tok_s_1_100_intervals_after_ttft'],
            prefill=summarize([r for r in rows if r['phase']=='prefill']),
            decode=summarize([r for r in rows if r['phase']=='decode']),
            metric_1_100=summarize([r for r in rows if r['phase']=='decode' and 2 <= r['timing']['generated_index'] <=100]),
            prompts=per_prompt, memory_admission=window['memory_admission'],
            postload_memory=window['postload_memory'], census_totals=census[0]['totals'])
        windows[name]['metric_1_100']['complete_100_events_every_request']=all(r['output_tokens']>=100 for r in summary['requests'])
        all_rows.extend(rows)
        # Retain the physical occupancy, not just the allocator's payload census.
        read(base/'run/run/drm-memory-after_load.txt')
        read(base/'run/run/memory.json')
    baseline=windows['WS128']['class_metric']['median']
    for name in ('K1a','K1b'):
        row=js(BASE/name/'summary.json')
        windows[name]={k:v for k,v in row.items() if k!='teardown'}
        windows[name]['cases']=lines(BASE/name/'run/k1-cases.jsonl')
    for name in ('main.cpp','cache_table.hpp','owner.cpp','p58_native_fixture.cpp','request_reset.hpp','cache_policy_replay.py','REVIEW-CACHE.md','DO-NOT-REPEAT.md'):
        read(PARENT/name)
    for name in ('packet58b-onecard','packet58c-onecard','packet58d-onecard','packet58e-onecard','packet58f-onecard','packet58h-onecard-mtp','packet81-experts3'):
        read(HERE.parent/name/'DO-NOT-REPEAT.md')
    ws=windows['WS128']
    device=ws['census_totals']['device']
    adm=ws['memory_admission']['plan']
    raw=read(BASE/'WS128/run/run/drm-memory-after_load.txt')
    vram=int(next(x.split(':')[1].split()[0] for x in raw.splitlines() if x.startswith('drm-total-vram0:')))*1024
    headroom=dict(census_device_bytes=device, drm_vram_bytes=vram, driver_overhead_bytes=vram-device,
        pinned_host_bytes=ws['census_totals']['host-pinned'],
        declared_host_budget_bytes=ws['memory_admission']['required_bytes'],
        conservative_device_bound_bytes=adm['device_owned_bound_bytes'],
        payload_headroom_after_device_reserve_bytes=adm['card_capacity_floor_bytes']-adm['device_reserve_bytes']-device,
        drm_headroom_after_device_reserve_bytes=adm['card_capacity_floor_bytes']-adm['device_reserve_bytes']-vram,
        unallocated_inside_existing_shadow_bound_bytes=adm['device_owned_bound_bytes']-device,
        physical_headroom_is_not_host_admission=True,
        cache_if_every_unused_bound_byte_proven_reassignable=18000000000+adm['device_owned_bound_bytes']-device,
        additional_cache_under_unchanged_allowances_bytes=0)
    # Class-balanced scenarios operate on each prompt's measured 99-interval span.
    # They are explicit counterfactuals, never measured speeds.
    def scenario(name, savings):
        classes={}
        per={}
        for prompt,p in ws['prompts'].items():
            d=savings(p['attribution'])
            ms=p['measured_interval_ms']/99
            rate=1000/(ms-d)
            per[prompt]=dict(assumed_saved_ms_per_token=d,predicted_tok_s=rate)
            classes.setdefault(p['prompt_class'],[]).append(rate)
        rate=st.median(st.median(v) for v in classes.values())
        return dict(name=name,estimated=True,measured=False,predicted_class_balanced_tok_s=rate,
                    gain_pct=(rate/baseline-1)*100,per_prompt=per)
    mean_bw=st.mean(windows[k]['zero_copy_useful_GB_s'] for k in ('K1a','K1b'))
    scenarios=[scenario('remove_entire_cache_maintenance_impossible_ceiling',lambda p:p['cache']['wall_ms']['mean']),
        scenario('hide_only_DMA_at_assumed_25_GB_s_no_new_overhead',lambda p:p['cache']['fill_bytes']['mean']/25e6),
        scenario('merge_three_expert_copies_to_one_at_3.4us',lambda p:2*p['cache']['fills']['mean']*.0034),
        scenario('merge_three_expert_copies_to_one_at_5us',lambda p:2*p['cache']['fills']['mean']*.005),
        scenario('remove_143_table_submissions_at_3.4us',lambda p:143*.0034),
        scenario('remove_143_table_submissions_at_5us',lambda p:143*.005)]
    threshold=dict(reference_tok_s=24.34,target_tok_s=24.34*1.1,
        anchor_ms=1000/baseline,allowed_ms=1000/(24.34*1.1),
        required_saved_ms=1000/baseline-1000/(24.34*1.1),
        k1_mean_effective_host_GB_s=mean_bw)
    result=dict(schema='own-runtime.packet58i.attribution.v1',device_executed=False,
        evidence_read_only=True, baseline=baseline, public_record_id_from_brief='cmvd8bhou000duj01hxaihg15',
        windows=windows,headroom=headroom,threshold=threshold,scenarios=scenarios,
        limitations=['No 58g route IDs retained; ordinary per-layer hits and true one-card policy replay unavailable.',
                    'Zero device timing fields mean disabled profiling, not zero device cost.',
                    'Cache wall includes CPU planning, submissions, DMA waits and table publication.',
                    'Logical host miss bytes are not a PCIe hardware byte counter.',
                    'No estimate or CPU replay is a performance headline.'])
    (HERE/'ATTRIBUTION.json').write_text(json.dumps(result,indent=2)+'\n')
    compact=[]
    for r in all_rows:
        compact.append(json.dumps(r,separators=(',',':')))
    (HERE/'position-attribution.jsonl.gz').write_bytes(gzip.compress(('\n'.join(compact)+'\n').encode(),mtime=0))
    (HERE/'inputs.json').write_text(json.dumps(INPUTS,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(headroom=headroom,threshold=threshold,
                         scenarios=[{k:v for k,v in s.items() if k!='per_prompt'} for s in scenarios]),indent=2))


if __name__=='__main__':
    main()

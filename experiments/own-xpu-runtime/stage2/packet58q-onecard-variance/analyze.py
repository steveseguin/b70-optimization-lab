#!/usr/bin/env python3
"""CPU-only receipt join. No runtime imports, device access or source mutations."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import statistics as st

P = Path(__file__).resolve().parent
REPO = P.parents[3]
BASES = {
 '58k-production-before': P.parent/'packet58k-onecard-screen/evidence/card0-screen-b/production-before',
 '58k-port': P.parent/'packet58k-onecard-screen/evidence/card0-screen-b/port',
 '58n-production-before': P.parent/'packet58n-onecard-loo/evidence/card0-loo-a/production-before',
 '58n-down-tile16': P.parent/'packet58n-onecard-loo/evidence/card0-loo-a/down-tile16',
 '58n-production-after': P.parent/'packet58n-onecard-loo/evidence/card0-loo-a/production-after',
}
PINS = {}
OLD = json.loads((P/'analysis-inputs.json').read_text()) if (P/'analysis-inputs.json').exists() else {}


def read(path):
    key = str(path.relative_to(REPO))
    raw = path.read_bytes() if path.exists() else gzip.decompress((P/OLD[key]['archive']).read_bytes())
    digest = hashlib.sha256(raw).hexdigest()
    if key in OLD:
        assert OLD[key]['sha256'] == digest, key
    archive=P/'analysis-inputs'/f'{digest}.gz'
    archive.parent.mkdir(exist_ok=True)
    if not archive.exists(): archive.write_bytes(gzip.compress(raw,mtime=0))
    assert gzip.decompress(archive.read_bytes())==raw
    PINS[key] = dict(sha256=digest, bytes=len(raw), archive=str(archive.relative_to(P)))
    return raw.decode()


def js(path):
    return json.loads(read(path))


def lines(path):
    return [json.loads(x) for x in read(path).splitlines() if x.strip()]


def stats(values):
    return dict(mean=st.mean(values), median=st.median(values), min=min(values), max=max(values))


def summarize(rows):
    fields = ('wall_ms', 'prepare_ms', 'enqueue_loop_ms', 'wait_ms', 'transfer_wall_ms',
              'kernel_submissions', 'host_waits', 'process_major_faults', 'process_minor_faults',
              'thread_voluntary_context_switches', 'thread_involuntary_context_switches')
    result = dict(positions=len(rows), timing={k: stats([r['timing'][k] for r in rows]) for k in fields},
        cache={k: stats([r['cache'][k] for r in rows]) for k in ('wall_ms','fills','fill_bytes','evictions')})
    result['cache'].update(expert_hit_rate=1-sum(r['cache']['fills'] for r in rows)/(480*len(rows)),
        logical_byte_hit_rate=1-sum(r['cache']['fill_bytes'] for r in rows)/(949760000*len(rows)),
        layer2_hit_rate=1-sum(r['layer2_misses'] for r in rows)/(10*len(rows)),
        ordinary_pooled_hit_rate=1-sum(r['cache']['fills']-r['layer2_misses'] for r in rows)/(470*len(rows)),
        logical_down_miss_bytes_per_position=st.mean(r['cache']['fills']*921600 for r in rows),
        physical_pcie_read_bytes=None, individual_ordinary_layer_hits=None)
    result['timing']['wall_less_cache_ms']=stats([r['timing']['wall_ms']-r['cache']['wall_ms'] for r in rows])
    prepare=[r['timing']['prepare_ms'] for r in rows]
    faults=[r['timing']['process_major_faults'] for r in rows]
    result['prepare_major_fault_correlation']=(st.correlation(prepare,faults)
        if len(set(prepare))>1 and len(set(faults))>1 else None)
    result['per_layer_device_times']=None
    return result


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0)) <= set(range(8,16))|set(range(24,32))
    arms={}; joined={}; identities={}
    for arm, arm_base in BASES.items():
        base=arm_base/'WSCREEN'; run=base/'run/run'
        window=js(base/'window.json'); summary=js(base/'summary.json'); native=js(run/'receipt.json')
        cold=js(run/'cold-start.json')
        identities[arm]={k:window[k] for k in ('boot_id','artifacts_sha256','environment','miss_path','view','selection_sha256')}
        assert window['passed'] and summary['passed'] and native['profiling'] is False
        assert native['timing']=='token' and summary['request_count']==12
        assert summary['kv_dtype']=='BF16' and summary['decode_mode']=='plain'
        assert summary['cached_tokens']==0 and not summary['prompt_kv_response_reuse']
        read(base/'native.log')
        cache=lines(run/'cache.jsonl'); rows=[]; prompts=[]; total_fills=total_bytes=0
        for req in summary['requests']:
            folder=run/req['prompt_id']; pre=lines(folder/'prefill-timings.jsonl'); gen=lines(folder/'timings.jsonl')
            actual=js(folder/'result.json'); counters=js(folder/'cache-stats.json')
            assert actual['tokens']==req['tokens'] and req['passed'] and req['exact_oracle']
            assert len(gen)==128 and len(pre)==req['prompt_tokens']-1
            assert not read(folder/'sites.jsonl').strip()
            prompt_rows=[]
            for timing in pre+gen:
                c=cache[len(rows)]; assert c['epoch']==len(rows)+1
                extra=c['fill_bytes']-c['fills']*1971200
                assert extra%358400==0 and 0<=extra//358400<=10
                assert timing['gemv_device_ms']==timing['non_gemv_device_ms']==0
                assert timing['enqueue_family_ms'] is None
                counts=timing['copy_counts']; assert len(counts)==1
                assert counts[0]['host_to_device']==3*c['fills']+147 and counts[0]['device_to_host']==50
                row=dict(prompt=req['prompt_id'],prompt_class=req['prompt_class'],phase='prefill' if timing['kind']=='prefill_token' else 'decode',
                    timing=timing,cache=c,layer2_misses=extra//358400)
                rows.append(row);prompt_rows.append(row);total_fills+=c['fills'];total_bytes+=c['fill_bytes']
            assert total_fills==counters['fills_total'] and total_bytes==counters['fill_bytes_total']
            assert counters['miss_path']=='zero-copy'
            metric=[r for r in prompt_rows if r['phase']=='decode' and 2<=r['timing']['generated_index']<=100]
            times=req['token_timestamps']; rate=99/(times[99]-times[0])
            assert abs(rate-req['submission100']['rate'])<1e-8
            prompts.append(dict(prompt=req['prompt_id'],prompt_class=req['prompt_class'],rate=rate,
                ttft_ms=req['ttft_ms'],output_sha256=req['output_token_sha256'],prompt_sha256=req['prompt_token_sha256'],
                metric=summarize(metric)))
        assert len(rows)==len(cache)
        for rel,digest in window['native_files'].items():
            key=str((base/rel).relative_to(REPO))
            if key in PINS: assert PINS[key]['sha256']==digest, key
        memory=lines(base/'host-memory.jsonl')
        assert PINS[str((base/'host-memory.jsonl').relative_to(REPO))]['sha256']==window['memory_samples_sha256']
        k1={k:dict(summary=js(arm_base/k/'summary.json'),cases=lines(arm_base/k/'run/k1-cases.jsonl')) for k in ('K1a','K1b')}
        classes={}
        for prompt in prompts: classes.setdefault(prompt['prompt_class'],[]).append(prompt['rate'])
        rate=st.median(st.median(values) for values in classes.values())
        assert abs(rate-summary['class_balanced_tok_s_1_100_intervals_after_ttft']['median'])<1e-8
        assert abs(st.median(p['rate'] for p in prompts)-summary['submission100_statistics']['median'])<1e-8
        arms[arm]=dict(rate=rate,all_prompt_median=summary['submission100_statistics']['median'],
            metric=summarize([r for r in rows if r['phase']=='decode' and 2<=r['timing']['generated_index']<=100]),
            decode=summarize([r for r in rows if r['phase']=='decode']),prefill=summarize([r for r in rows if r['phase']=='prefill']),
            prompts=prompts,k1=k1,profiling=False,cold_start=cold,
            memory=dict(samples=len(memory),min_available=min(r['host']['MemAvailable'] for r in memory),
                max_anonymous=max(r['anonymous_bytes'] for r in memory),max_accounted=max(r['host_accounted_bytes'] for r in memory),
                max_shadow=max(r['gpuactive_shadow_bytes'] for r in memory),
                swap_free_first=memory[0]['host']['SwapFree'],swap_free_last=memory[-1]['host']['SwapFree']),
            window_elapsed_seconds=memory[-1]['sample_utc_ns']/1e9-memory[0]['sample_utc_ns']/1e9)
        joined[arm]=rows
    reference=next(iter(joined.values())); pairs=[]
    for i,a in enumerate(reference):
        timings={};cache_times={}
        for arm, rows in joined.items():
            assert len(rows)==len(reference)
            b=rows[i]
            assert (a['prompt'],a['phase'],a['timing']['token_index'],a['timing'].get('token_id'))==(b['prompt'],b['phase'],b['timing']['token_index'],b['timing'].get('token_id'))
            for k in ('epoch','fills','fill_bytes','evictions','resident_bytes'):
                assert a['cache'][k]==b['cache'][k], (arm,k,i)
            timings[arm]=b['timing'];cache_times[arm]=b['cache']['wall_ms']
        pairs.append(dict(prompt=a['prompt'],phase=a['phase'],epoch=a['cache']['epoch'],
            generated_index=a['timing'].get('generated_index'),fills=a['cache']['fills'],
            fill_bytes=a['cache']['fill_bytes'],timings=timings,cache_ms=cache_times))
    for arm, result in arms.items():
        result['window_identity']=identities[arm]
        result['zero_copy_device_ms']=None
        result['gpu_device_ms']=None
        rows=[r for r in joined[arm] if r['phase']=='decode' and 2<=r['timing']['generated_index']<=100]
        result['metric']['timing']['wall_less_prepare_ms']=stats([r['timing']['wall_ms']-r['timing']['prepare_ms'] for r in rows])
    for arm, base in BASES.items():
        run=base/'WSCREEN/run/run'
        arms[arm]['native_identity']={k:js(run/'receipt.json').get(k) for k in ('arithmetic','selection_sha256','lookup_residency','cpu_affinity','native_nice','model_payload_bytes_read')}
        arms[arm]['after_load_status']=read(run/'host-status-after_load.txt')
    for name in ('README.md','queue_runner.py','window.py','suite_driver.py','selection.json','DO-NOT-REPEAT.md'):
        path=P.parent/'packet58p-onecard-record'/name
        read(path)
    read(REPO/'AGENTS.md')
    read(P.parent/'packet58n-onecard-loo/DO-NOT-REPEAT.md')
    read(REPO/'notes/2026-10-18-own-runtime-packet125-micro-result.md')
    sources=P.parent/'packet58j-onecard-port'
    for name in ('main.cpp','cache_table.hpp','p58_pointer.hpp','p58_native_fixture.cpp','p100_down.hpp',
                 'p49d_expert.hpp','p49d_expert_submit.cpp','p49d_submit.cpp','p49d_route.hpp','p78_route.hpp',
                 'p49d_recurrence.hpp','p82b_recurrence.hpp','views.json'):
        read(sources/name)
    for name in ('production','port'): read(sources/'selections'/f'{name}.json')
    for name in ('gguf.hpp','gguf.cpp'): read(P.parent/'packet2/loader'/name)
    reference_identity=identities['58k-production-before']
    reference_prompts=[(p['prompt'],p['prompt_class'],p['prompt_sha256'],p['output_sha256'])
        for p in arms['58k-production-before']['prompts']]
    for arm in arms.values():
        assert [(p['prompt'],p['prompt_class'],p['prompt_sha256'],p['output_sha256'])
            for p in arm['prompts']]==reference_prompts
    for identity in identities.values():
        for key in ('boot_id','artifacts_sha256','environment','miss_path'):
            assert identity[key]==reference_identity[key], key
    for arm in ('58n-production-before','58n-production-after'):
        assert identities[arm]['selection_sha256']==reference_identity['selection_sha256']
    previous=js(P.parent/'packet58n-onecard-loo/analysis-data.json')
    for old_arm,new_arm in (('production-before','58k-production-before'),('port','58k-port')):
        old=previous['arms'][old_arm]; new=arms[new_arm]
        for key in ('rate','all_prompt_median','cold_start','memory'):
            assert old[key]==new[key], (old_arm,key)
        for phase in ('metric','decode','prefill'):
            for key in old[phase]['timing']:
                assert old[phase]['timing'][key]==new[phase]['timing'][key], (old_arm,phase,key)
    result=dict(schema='packet58q.analysis.v1',device_executed=False,arms=arms,
        identical_cache_counts_every_position=True,joined_positions=len(pairs),
        same_boot_binaries_environment_miss_path=True,previous_58n_analysis_reproduced=True,
        note='Host timers overlap; zeros are disabled profiling. Logical miss payload is not physical PCIe reads. Cross-screen comparison cannot isolate page-residency cause; 58k bracket incomplete.')
    (P/'analysis-data.json').write_text(json.dumps(result,indent=2)+'\n')
    payload=''.join(json.dumps(r,separators=(',',':'))+'\n' for r in pairs).encode()
    (P/'position-pairs.jsonl.gz').write_bytes(gzip.compress(payload,mtime=0))
    (P/'analysis-inputs.json').write_text(json.dumps(PINS,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(passed=True,joined_positions=len(pairs),rates={a:r['rate'] for a,r in arms.items()},
        all_prompt_rates={a:r['all_prompt_median'] for a,r in arms.items()}),indent=2))


if __name__=='__main__': main()

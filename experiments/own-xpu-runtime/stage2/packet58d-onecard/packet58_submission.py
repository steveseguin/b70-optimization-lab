#!/usr/bin/env python3
"""Offline 1-GPU lineage preparation. Recompute evidence; never posts or reads keys."""
import argparse
import json
from pathlib import Path
import re
import statistics
import sys
import suite_driver as D

HERE=D.HERE
ROOT=D.ROOT
MODEL_REVISION='766911a6b7369840a91dbcd95f9f997acaab6cd6'
LEDGER=ROOT/'results/localmaxxing-submissions.md'
THRESHOLD=HERE/'record-threshold.json'
GATES=('varied_task_quality_passed','exact_or_target_oracle_passed','deterministic_repeats_passed',
       'fresh_server_repeat_passed','target_model_unchanged','no_quality_loss')
require,read,sha,save=D.require,D.read,D.sha,D.save

def reference(path):
    path=Path(path).resolve();require(path.is_relative_to(ROOT),'evidence must remain in repository')
    return dict(path=str(path.relative_to(ROOT)),sha256=sha(path))

def verified_ref(ref):
    path=(ROOT/ref['path']).resolve()
    require(path.is_relative_to(ROOT) and sha(path)==ref['sha256'],'evidence changed')
    return path

def threshold():
    row=read(THRESHOLD)
    require(row.get('schema')=='own-runtime.packet58.one-gpu-threshold.v1' and row.get('gpu_count')==1
            and row.get('model_revision')==MODEL_REVISION,'one-card threshold identity')
    require(sha(LEDGER)==row['ledger_sha256'],'submission ledger changed; refresh 1-GPU record review')
    value=row['threshold_tok_s']
    require(value is None or (type(value) in (int,float) and value>0),'threshold must be absent or positive')
    require((value is None)==(row['reference_submission'] is None),'threshold/submission mismatch')
    return row

def interval(row):
    start, end = row.get('started_utc_ns'), row.get('finished_utc_ns')
    require(type(start) is int and type(end) is int and 0 < start < end,
            'invalid window time interval')
    return start, end

def chain_links(chain, name, row):
    """Resolve exact queue predecessors; sibling receipts cannot substitute."""
    previous_name = 'K1b' if name == 'KD' else D.WINDOWS[D.WINDOWS.index(name)-1]
    expected_previous = (chain/previous_name/'window.json').resolve()
    previous = verified_ref(row['previous'])
    require(previous == expected_previous, 'previous reference is not the immediate chain predecessor')
    start, _ = interval(row)
    require(interval(read(previous))[1] < start, 'previous window overlaps or follows current window')
    refs = row.get('k1_refs')
    require(isinstance(refs, list) and len(refs) == 2, 'two exact chain K1 references required')
    paths = [verified_ref(ref) for ref in refs]
    expected = [(chain/n/'window.json').resolve() for n in ('K1a','K1b')]
    require(paths == expected, 'K1 references are not this chain K1a and K1b')
    for ref, path in zip(refs, paths):
        require(ref.get('native_k1_sha256') == sha(path.parent/'run/k1.json'), 'K1 native reference changed')
        require(interval(read(path))[1] < start, 'K1 window overlaps or follows model window')
    require(interval(read(paths[0]))[1] < interval(read(paths[1]))[0], 'K1 windows overlap or reverse')
    return paths

def derive(chain):
    import window as W
    seal=W.build_gate();manifest=D.oracle_inputs();ref=threshold()
    chain=Path(chain).resolve()
    require(chain.is_relative_to(HERE/'evidence'),'unregistered packet58 evidence directory')
    windows={};summaries={};files={};owners=set();k1_owners={}
    for name in D.WINDOWS:
        directory=chain/name
        row=read(directory/'window.json')
        require(row.get('passed') is True and row.get('qualifying') is True and row.get('device_executed') is True
                and row.get('child_still_running') is False and not row.get('stop_reasons'),name+' not qualified')
        require(all(type(row.get(k)) is int for k in ('gpu_count','context','card'))
                and row.get('window')==name and row.get('gpu_count')==1 and row.get('decode_mode')=='plain'
                and row.get('context')==4096 and row.get('card') in (0,2), 'one-card identity')
        require(row.get('build_receipt_sha256')==sha(HERE/'build-receipt.json')
                and row.get('artifacts_sha256')==seal['artifacts'],'build changed')
        W.prerequisite(directory/'window.json', name, row)
        k1paths=chain_links(chain,name,row)
        for leaf in ('kernel-before.jsonl','kernel-window.jsonl'):
            require(not W.S.FAULT.search((directory/leaf).read_text()),'fault evidence')
            files[str((directory/leaf).relative_to(ROOT))]=sha(directory/leaf)
        for leaf,digest in row['native_files'].items():
            files[str((directory/leaf).relative_to(ROOT))]=digest
        files[str((directory/'window.json').relative_to(ROOT))]=sha(directory/'window.json')
        owner=(row['boot_id'],row['pid'],row['process_start_ticks'])
        require(owner not in owners,'fresh window process reused');owners.add(owner)
        if windows:
            first=windows['KD']
            require(all(row[k]==first[k] for k in ('boot_id','card','environment','miss_path')),'window identity changed')
            previous=windows[D.WINDOWS[D.WINDOWS.index(name)-1]]
            require(row['started_utc_ns']>previous['finished_utc_ns'],'overlapping windows')
        require(W.selected_miss_path(k1paths,row)==row['miss_path'],'miss choice not bound to K1')
        for path in k1paths:
            files[str(path.relative_to(ROOT))]=sha(path)
            kw=read(path)
            if path not in k1_owners:
                kowner=(kw['boot_id'],kw['pid'],kw['process_start_ticks'])
                require(kowner not in owners, 'K1 and model windows reuse an owner')
                owners.add(kowner);k1_owners[path]=kowner
            for leaf,digest in kw['native_files'].items():files[str((path.parent/leaf).relative_to(ROOT))]=digest
        summary=D.summarize(directory/'run',name,manifest)
        require(summary==read(directory/'run/summary.json')==read(directory/'summary.json'),'summary not reproduced')
        driver=read(directory/'run/receipt.json')
        require(driver.get('passed') is True and driver.get('safe_to_exit') is True,'driver teardown')
        windows[name]=row;summaries[name]=summary
    candidates=[summaries[n] for n in ('WS','WS128x','WS128')]
    require(all(x['request_count']==12 for x in candidates),'full suite missing')
    for i in range(12):
        require(candidates[0]['requests'][i]['tokens']==candidates[1]['requests'][i]['tokens']==candidates[2]['requests'][i]['tokens'],
                'fresh-process token repeat mismatch')
    require(sum(r['compared_layer_fixtures'] for r in candidates[0]['requests'])==12*8*48,'full WS early-layer exactness missing')
    timed=summaries['WS128'];confirm=summaries['WS128x']
    require(timed['retained_steps']==confirm['retained_steps']=='none','instrumented speed')
    speed=timed['class_balanced_tok_s_1_100_intervals_after_ttft']['median']
    require(speed is not None and all(r['metric_window_eligible'] for r in timed['requests']+confirm['requests']),'incomplete 100-event windows')
    require(ref['threshold_tok_s'] is None or speed>ref['threshold_tok_s'],'not a new matching 1-card record')
    identity=dict(model_revision=MODEL_REVISION,runtime_revision=seal['runtime_revision'],
        optimization_identity='packet58d-onecard-plain-lru18gb-'+windows['WS128']['miss_path']+'-'+sha(HERE/'build-receipt.json'),
        arithmetic=D.ARITHMETIC,suite_sha256=D.SUITE_SHA,gpu_count=1)
    return dict(schema='own-runtime.packet58.result.v1',packet='packet58d-onecard',promotionIdentity=identity,
        gpu_count=1,decode_mode='plain',kv_dtype='BF16',context=4096,card=windows['WS128']['card'],
        primary_metric=dict(name=D.METRICS.PRIMARY,value_tok_s=speed,events=100,intervals=99,numerator=99),
        fresh_speed_confirmation=confirm['class_balanced_tok_s_1_100_intervals_after_ttft'],
        secondary={k:timed[k] for k in ('submission100_statistics','ttft_statistics','wall_rate_statistics')},
        requests=timed['requests'],comparison=ref,build_receipt=reference(HERE/'build-receipt.json'),
        oracle_completion=reference(D.ORACLE/'results/completion.json'),chain=str(chain.relative_to(ROOT)),
        evidence_files=files,strict_512_gate_passed=False,
        realistic_final_gate=dict(passed=False,reason='128-token scope; no full 512-token final gate'),
        prefill_512_tok_s=None,full_512_natural_completion_tok_s=None,
        scope='12 fixed cold prompts, 128 tokens; unchanged packet49 oracle; immutable expert weights cached only')

def payload(result,result_ref,att_ref):
    rows=result['requests'];metric=result['primary_metric'];secondary=result['secondary']
    flags=dict(benchmarkJson=result_ref['path'],benchmarkJsonSha256=result_ref['sha256'],
        promotionAttestation=att_ref['path'],promotionAttestationSha256=att_ref['sha256'],
        promotionIdentity=result['promotionIdentity'],packet58Evidence=True,
        primaryMetricName=metric['name'],primaryMetricAccounting='inter-token-intervals',
        primaryMetricAggregation='median-of-prompt-class-medians',metricWindowGeneratedTokens=100,metricWindowIntervals=99,
        realisticSuiteGatePassed=False,strict512TokenFinalGatePassed=False,
        realisticSuiteId='rapid-model-snapshots-b70-realistic-v1',realisticSuiteCachedTokensAllZero=True,
        requestedMaxNew=128,realisticPromptTokenCounts=[r['prompt_tokens'] for r in rows],
        realisticOutputTokenCounts=[r['output_tokens'] for r in rows],
        promptTokenSha256=[r['prompt_token_sha256'] for r in rows],outputTokenSha256=[r['output_token_sha256'] for r in rows],
        tokenTimestamps=[r['token_timestamps'] for r in rows],prefixCaching=False,responseReuse=False,
        contextCheckpoints=0,historyAccelerated=False,kvCacheDtype='bf16',apiKvCacheDtype='auto',
        tensorParallel=1,concurrency=1,temperature=0,specDecoding=False,mtpEnabled=False,specNumTokens=0,
        cacheInitialPlacement='empty, content-independent',immutableExpertWeightCacheBytes=18_000_000_000,
        deviceCards=[result['card']],submissionScopeReviewRequired=True)
    return dict(label='qwen38-flash-next-unsloth-iq3xxs-ownrt-1gpu-packet58-plain-realistic',payload=dict(
        hfId='unsloth/Qwen3.8-Flash-Next-GGUF',modelRevision=MODEL_REVISION,engineName='custom',backend='xpu',
        engineVersion='own-xpu-runtime packet58d-onecard '+result['promotionIdentity']['runtime_revision'],quantization='UD-IQ3_XXS (GGUF)',
        hardware=dict(hwClass='DISCRETE_GPU',gpuName='Intel Arc Pro B70',gpuCount=1,vramGb=32,
            cpu='AMD Ryzen Threadripper PRO 5955WX 16-Cores',ramGb=128,os='Ubuntu 24.04.4 LTS'),
        contextLength=4096,batchSize=1,promptTokens=int(statistics.median(r['prompt_tokens'] for r in rows)),outputTokens=128,
        tokSOut=metric['value_tok_s'],tokSTotal=secondary['wall_rate_statistics']['median'],ttftMs=secondary['ttft_statistics']['median'],
        notes='Quantized compressed version, separate from FP8. Own runtime, one B70, plain greedy, full BF16 KV. '
              'Exact against packet49 CPU oracle; fresh repeats. 18 GB immutable weight LRU; no prompt/KV/response reuse. '
              '128-token scoped result, strict 512-token gate false. Standard 512-token prefill and natural completion not measured.',engineFlags=flags))

def prepare(chain,out):
    result=derive(chain);out=Path(out).resolve()
    require(out.is_relative_to(HERE/'submission') and not out.exists(),'new packet-local submission output required')
    out.mkdir(parents=True)
    save(out/'result.json',result);result_ref=reference(out/'result.json')
    save(out/'quality-evidence.json',dict(gates=dict.fromkeys(GATES,True),evidence_files=result['evidence_files'],
        build_receipt=result['build_receipt'],oracle_completion=result['oracle_completion']))
    att=dict(schema='neural.download.promotion-attestation.v1',identity=result['promotionIdentity'],performance_evidence=result_ref,
        quality_evidence=[dict(reference(out/'quality-evidence.json'),supports=list(GATES))],
        gates={**dict.fromkeys(GATES,True),'strict_512_token_final_gate_passed':False},
        submission_scope=dict(requested_max_new=128,strict_512_gate_passed=False,
            prepared_only=True,real_submission_performed=False,external_128_scope_review_pending=True))
    save(out/'promotion-attestation.json',att)
    item=payload(result,result_ref,reference(out/'promotion-attestation.json'))
    # Deliberately a draft, never a ready-to-post queue before scope review.
    save(out/'payload-draft.json',[item])
    (out/'result-packet.md').write_text('# Packet58 one-card result\n\n'+
        f"{result['primary_metric']['value_tok_s']:.6f} tok/s, class-balanced 99-interval rate. "
        'One B70, plain decode, BF16 KV, 18 GB expert LRU.\n\n'
        'All 12 prompts match packet49 and repeat across fresh owners. 128-token scoped evidence; '
        'strict 512-token gate is false. No matching prior 1-GPU submitted record in the pinned ledger '
        'unless comparison in result.json says otherwise. 512-token prefill is not measured.\n\n'
        'Submission preparation only. External 128-token scope review remains a coordinator action.\n')
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--chain',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();result=prepare(args.chain,args.output)
    print(json.dumps(dict(prepared_only=True,gpu_count=1,submitted=False,tok_s=result['primary_metric']['value_tok_s'])))

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,TypeError) as error:print('REFUSED: '+str(error),file=sys.stderr);sys.exit(1)

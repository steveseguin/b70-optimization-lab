#!/usr/bin/env python3
"""Collect and replay a bounded AMD-transfer packet. CPU/files only; no network.

Explicit source selection excludes model weights, build caches, native binaries,
unrelated journals, and running service logs unless requested for final snapshot.
Re-running updates these generated packet files; original receipts stay intact.
"""
import argparse
from collections import defaultdict
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import statistics
import tarfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DEFAULT_ROOT = Path('/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914')
DEFAULT_PACKET = HERE.parent / 'data/2026-09-14-amd-transfer'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def json_bytes(obj):
    return (json.dumps(obj, indent=2, sort_keys=True) + '\n').encode()

def same(a, b, message):
    if a != b:
        raise ValueError(message)

def close(a, b, message):
    if not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-12):
        raise ValueError(message)

def secret_check(name, data):
    # Reject concrete credentials, not generic references or numeric token IDs.
    text = data.decode('utf-8')
    patterns = [r'\b(?:hf_|ghp_|github_pat_)[A-Za-z0-9_]{20,}',
                r'\bsk-[A-Za-z0-9_-]{20,}',
                r'(?i)authorization["\s:=]+bearer\s+[A-Za-z0-9._~-]{12,}',
                r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----']
    if any(re.search(p, text) for p in patterns):
        raise ValueError(f'Possible credential found in {name}; refused without printing value')
    # Docker inspect Env arrays may contain credentials without a known prefix.
    if name.endswith('.json'):
        obj = json.loads(text)
        def walk(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == 'Env' and isinstance(item, list):
                        for env in item:
                            k, _, v = env.partition('=')
                            if re.fullmatch(r'(?i)(HF_TOKEN|HUGGING_FACE_HUB_TOKEN|OPENAI_API_KEY|LMX_API_KEY|AWS_SECRET_ACCESS_KEY|GITHUB_TOKEN)', k) and v:
                                raise ValueError(f'Credential environment field in {name}; refused')
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
        walk(obj)

def select(root, packet, include_restored):
    names = set()
    required = ['control-identity.json', 'control-reference-parity.json',
        'projection-compile.json', 'projection-result.json', 'projection-compile.log',
        'kernel-abi-check.log', 'build.log', 'FAULT.json',
        'candidate-dflash/ABORTED', 'candidate-dflash/server.log',
        'candidate-dflash/launch.json', 'candidate-dflash/image.json',
        'external-reboot-01/incident.json', 'external-reboot-01/previous-kernel.log',
        'external-reboot-01/restoration-admission.json',
        'reused-kernels/kernel-reuse-identity.json']
    for name in required:
        if not (root/name).is_file():
            raise ValueError(f'Missing required receipt {name}')
        names.add(name)
    optional = ['nightly-pull.log', 'nightly-digest-pull.log',
        'candidate-dflash/device-owners.txt', 'external-reboot-01/candidate-container.json',
        'external-reboot-01/discovery.txt', 'external-reboot-01/boots.txt',
        'external-reboot-01/listeners.txt', 'external-reboot-01/device-owners.txt',
        'build-context/candidate-image-inspect.json', 'candidate-image.json',
        'restoration-completion.json', 'restored-service/completion.json',
        'restored-service/state.json', 'restored-service/launch.json',
        'restored-service/container-inspect.json']
    for name in optional:
        if (root/name).is_file():
            names.add(name)
    directories = ['control-strict', 'control-context', 'prefix-input-check',
        'preflight-monitor', 'control-strict-monitor-02', 'control-context-monitor',
        'projection-monitor', 'candidate-monitor', 'external-reboot-01/health-monitor']
    for directory in directories:
        for path in (root/directory).glob('*'):
            if path.is_file() and (path.suffix in ('.json','.jsonl','.txt','.log','.stdout')
                                   or path.name == 'DONE'):
                names.add(str(path.relative_to(root)))
    if include_restored and not (root/'restoration-completion.json').is_file():
        raise ValueError('Final running-log snapshot requires restoration-completion.json')
    if (root/'restoration-completion.json').is_file():
        for directory in ['external-reboot-01/restored-strict', 'external-reboot-01/restored-context']:
            for path in (root/directory).glob('*'):
                if path.is_file() and path.suffix in ('.json','.jsonl','.txt','.log','.stdout'):
                    names.add(str(path.relative_to(root)))
        for directory in (root/'external-reboot-01').glob('restored*monitor*'):
            if directory.is_dir():
                for path in directory.glob('*'):
                    if path.is_file() and (path.suffix in ('.json','.txt','.log') or path.name=='DONE'):
                        names.add(str(path.relative_to(root)))
        for path in (root/'external-reboot-01').glob('restored*.json'):
            if path.is_file(): names.add(str(path.relative_to(root)))
    if include_restored:
        for name in ['restored-service/kernel.log','restored-service/server.log','restored-helper.log']:
            if (root/name).is_file():
                names.add(name)
    sources = {name: root/name for name in sorted(names)}
    for name in ['bench-short-prefill.py','bench-prefill-followup.py',Path(__file__).name]:
        sources[f'sources/{name}'] = HERE/name
    for name in ['amd-transfer-projection-dispatch.py','amd-transfer-projection-dispatch.cpp']:
        sources[f'sources/{name}'] = HERE.parent/'probes'/name
    # Only the exact historical reference already bound by this comparison is
    # admitted. No arbitrary path from a JSON receipt is followed.
    historical_root=Path('/mnt/fast-ai/bench-results/qwen38-fp8-rebase-v0290-rb1-20260913/mtp1-a/strict')
    parity=json.loads((root/'control-reference-parity.json').read_text())
    for role,name in [('performance','performance.json'),('canaries','canaries.json'),
                      ('identity','campaign-identity.json')]:
        expected=historical_root/name
        same(Path(parity['left']['artifacts'][role]['path']),expected,'historical reference path differs from allowlist')
        sources[f'historical-reference/{name}']=expected
    for name in ['dflash2-hf-metadata.json','dflash2-config.json','upstream-xpu-tags.json',
                 'upstream-release.json','dflash2-feasibility.json',
                 'independent-overlay-review.json','incident-loader-source-review.json',
                 'freeze-incident.json']:
        if (packet/name).is_file():
            sources[f'repository-metadata/{name}'] = packet/name
    data = {}
    for name,path in sources.items():
        if path.is_symlink() or path.stat().st_size > 32*1024*1024:
            raise ValueError(f'Unbounded or linked input: {name}')
        raw = path.read_bytes()
        secret_check(name,raw)
        data[name] = raw
    if sum(map(len,data.values())) > 128*1024*1024:
        raise ValueError('Selected packet exceeds bounded size')
    return data

def summarize(data):
    read = lambda name: json.loads(data[name])
    spec = importlib.util.spec_from_file_location('amd_transfer_prefill_replay', HERE/'bench-prefill-followup.py')
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    context = read('control-context/summary.json')
    same(sha(data['sources/bench-prefill-followup.py']),context['client_sha256'],'client source hash changed')
    same(sha(data['sources/bench-short-prefill.py']),context['parser_sha256'],'wire parser hash changed')
    same(sha(data['control-context/corpus.json']),context['corpus_sha256'],'corpus hash differs')
    rebuilt=[]; output_pins={}; all_cache_zero=True
    for original in context['warmups']+context['rows']:
        stem=f"control-context/{original['phase']}-{original['key']}-{original['repeat']}"
        request=read(stem+'-request.json')
        prompt=context['prompts'][original['key']]
        same(request['prompt'],prompt,'request prompt differs')
        events=[json.loads(line) for line in data[stem+'-sse.jsonl'].splitlines()]
        wire=bench.parse_events(events,len(prompt),request['max_tokens'])
        metrics=bench.required_metric_delta(data[stem+'-metrics-before.txt'].decode(),
                    data[stem+'-metrics-after.txt'].decode(),len(prompt))
        row={**original,**wire,**metrics}
        same(row,original,'raw replay differs from context row')
        ids=wire['token_ids'];key=original['key']
        if key in output_pins:
            same(ids,output_pins[key],'complete context output repeat differs')
        output_pins[key]=ids
        all_cache_zero &= wire['usage']['prompt_tokens_details']['cached_tokens']==0
        if original['phase']=='measure': rebuilt.append(row)
    lengths=sorted({len(p) for p in context['prompts'].values()})
    rates=bench.aggregate(rebuilt,context['prompts'],lengths,context['args']['repeats'])
    same(rates,context['by_length'],'context aggregate differs')
    strict=read('control-strict/performance.json'); classes=defaultdict(list)
    for row in strict['rows']:
        offsets=row['token_id_offsets_s']
        if len(offsets)<100 or row['cached_tokens']!=0:
            raise ValueError('strict row missing timing or cache-zero evidence')
        speed=99/(offsets[99]-offsets[0])
        close(speed,row['tok_s_1_100_intervals_after_ttft'],'strict timing arithmetic differs')
        classes[row['prompt_class']].append(speed)
    class_medians={k:statistics.median(v) for k,v in sorted(classes.items())}
    strict_rate=statistics.median(class_medians.values())
    close(strict_rate,strict['summary']['class_balanced_tok_s_1_100_intervals_after_ttft']['median'],'strict aggregate differs')
    parity=read('control-reference-parity.json')
    same(read('control-strict/canaries.json')['pass_all'],True,'control canaries failed')
    same(strict['realistic_final_gate']['passed'],True,'control realistic workload gate failed')
    for role,name in [('canaries','canaries.json'),('identity','campaign-identity.json')]:
        same(sha(data['control-strict/'+name]),parity['right']['artifacts'][role]['sha256'],'control parity artifact hash differs')
    same(sha(data['control-strict/performance.json']),parity['right']['artifacts']['performance']['sha256'],'parity does not bind performance')
    same(parity['comparison']['complete_token_arrays_exact'],True,'reference parity failed')
    historical=read('historical-reference/performance.json')
    for role,name in [('performance','performance.json'),('canaries','canaries.json'),
                      ('identity','campaign-identity.json')]:
        same(sha(data['historical-reference/'+name]),parity['left']['artifacts'][role]['sha256'],'historical parity artifact hash differs')
    same(read('historical-reference/canaries.json')['pass_all'],True,'historical canaries failed')
    same(historical['realistic_final_gate']['passed'],True,'historical workload gate failed')
    historical_rows={r['prompt_id']:r for r in historical['rows']}
    same(len(historical_rows),12,'historical reference is not full suite')
    same({r['prompt_id'] for r in strict['rows']},set(historical_rows),'historical/control coverage differs')
    historical_classes=defaultdict(list)
    for row in strict['rows']:
        old=historical_rows[row['prompt_id']]
        same(row['prompt_sha256'],old['prompt_sha256'],'historical/control prompt differs')
        same(row['token_ids'],old['token_ids'],'historical/control complete token array differs')
        same(old['cached_tokens'],0,'historical reference is not cache zero')
        offsets=old['token_id_offsets_s'];speed=99/(offsets[99]-offsets[0])
        close(speed,old['tok_s_1_100_intervals_after_ttft'],'historical token-timing arithmetic differs')
        historical_classes[old['prompt_class']].append(speed)
    historical_rate=statistics.median(statistics.median(v) for v in historical_classes.values())
    close(historical_rate,parity['left']['class_balanced_median_tok_s'],'historical class-balanced rate differs')
    projection=read('projection-result.json'); projected=[]
    compiled=read('projection-compile.json')
    same(compiled['status'],'COMPILE_ONLY_PASSED','projection compilation did not pass')
    same(projection['status'],'OPERATOR_SCREEN_PASSED','projection operator did not pass')
    same(projection['all_exact'],True,'projection exactness flag is false')
    same(projection['weights_and_scales_unchanged'],True,'projection weights/scales mutation flagged')
    same(projection['weight_and_scale_inputs'],projection['weight_and_scale_inputs_after'],'projection weight/scale before/after differ')
    same(compiled['compiled_library'],projection['compiled_library'],'projection compile/run library identity differs')
    for receipt in [compiled,projection]:
        same(sha(data['sources/amd-transfer-projection-dispatch.cpp']),receipt['candidate_cpp_sha256'],'projection C++ source differs from tested bytes')
        same(sha(data['sources/amd-transfer-projection-dispatch.py']),receipt['probe_sha256'],'projection probe source differs from tested bytes')
    expected_cases={(m,fixture,repeat) for m in (1,2) for fixture in ('zeros','random','alternating-sign') for repeat in range(2)}
    same(len(projection['cases']),len(expected_cases),'projection case count differs')
    same({(c['rows'],c['fixture'],c['repeat']) for c in projection['cases']},expected_cases,'projection case coverage differs')

    for case in projection['cases']:
        if not case['input_unchanged']:
            raise ValueError('projection mutated input')
        same({o['output'] for o in case['outputs']},{'qkvz','ba'},'projection output coverage differs')
        for output in case['outputs']:
            same(output['bit_exact'],True,'projection exactness flag false')
            same(output['control_repeat_bit_exact'],True,'projection control stability flag false')
            same(output['reference_sha256'],output['candidate_sha256'],'projection mismatch')
            same(output['reference_sha256'],output['control_repeat_sha256'],'unstable projection control')
    for timing in projection['timings']:
        same(timing['input_before'],timing['input_after'],'projection timing mutated input')
        raw=timing['raw'];result={'rows':timing['rows']}
        for field in ['wall_us','submission_us']:
            ctrl=statistics.median(r[field] for r in raw if r['arm']=='control')
            cand=statistics.median(r[field] for r in raw if r['arm']=='candidate')
            pairs=[]
            for block in sorted({r['block'] for r in raw}):
                c=statistics.median(r[field] for r in raw if r['block']==block and r['arm']=='control')
                t=statistics.median(r[field] for r in raw if r['block']==block and r['arm']=='candidate')
                pairs.append({'block':block,'control':c,'candidate':t,'latency_change_percent':100*(t/c-1)})
            result[field]={'control_median':ctrl,'candidate_median':cand,
                          'latency_change_percent':100*(cand/ctrl-1),
                          'inverse_latency_speed_change_percent':100*(ctrl/cand-1),
                          'block_pairs':pairs}
        close(result['wall_us']['control_median'],timing['control_median_us'],'projection control aggregation differs')
        close(result['wall_us']['candidate_median'],timing['candidate_median_us'],'projection candidate aggregation differs')
        projected.append(result)
    incident=read('external-reboot-01/incident.json')
    for name,pin in incident['original_evidence_hashes'].items():
        if name in data: same(sha(data[name]),pin,f'incident pin mismatch: {name}')
    completed = next((name for name in ['restoration-completion.json','restored-service/completion.json'] if name in data),None)
    state=read('restored-service/state.json') if 'restored-service/state.json' in data else None
    restoration={'status':'pending-final-receipt' if completed is None else 'completion-receipt-present',
                 'state_snapshot':state,'completion_receipt':read(completed) if completed else None,
                 'running_logs_snapshotted':'restored-service/server.log' in data}
    restored_prefix = 'external-reboot-01/restored-context'
    if completed and restored_prefix+'/summary.json' in data:
        restored = read(restored_prefix+'/summary.json')
        same(restored['prompts'], context['prompts'], 'restored prompt identity differs')
        same(restored['corpus_sha256'], context['corpus_sha256'], 'restored corpus differs')
        same(restored['parser_sha256'], context['parser_sha256'], 'restored parser differs')
        same(restored['client_sha256'], context['client_sha256'], 'restored client differs')
        same(sha(data[restored_prefix+'/corpus.json']),context['corpus_sha256'],'restored copied corpus differs')
        rr=[]
        for original in restored['warmups']+restored['rows']:
            stem=f"{restored_prefix}/{original['phase']}-{original['key']}-{original['repeat']}"
            request=read(stem+'-request.json')
            prompt=restored['prompts'][original['key']]
            same(request['prompt'],prompt,'restored request differs')
            parsed=bench.parse_events([json.loads(line) for line in data[stem+'-sse.jsonl'].splitlines()],len(prompt),request['max_tokens'])
            metric=bench.required_metric_delta(data[stem+'-metrics-before.txt'].decode(),data[stem+'-metrics-after.txt'].decode(),len(prompt))
            row={**original,**parsed,**metric}
            same(row,original,'restored raw timing replay differs')
            same(parsed['token_ids'],output_pins[original['key']],'restored context output differs from pre-reboot control')
            if original['phase']=='measure': rr.append(row)
        restored_rates=bench.aggregate(rr,restored['prompts'],lengths,restored['args']['repeats'])
        same(restored_rates,restored['by_length'],'restored aggregate differs')
        restoration['context_replayed']={'by_length':restored_rates,'measured_requests':len(rr),
            'all_complete_outputs_equal_pre_reboot':True,'all_cached_tokens_zero':True,
            'classification':'same-recipe fresh-process baseline support, not optimization speedup'}
    restored_strict='external-reboot-01/restored-strict/performance.json'
    if completed and restored_strict in data:
        restored=read(restored_strict);cc=defaultdict(list)
        same(read('external-reboot-01/restored-strict/canaries.json')['pass_all'],True,'restored canaries failed')
        same(restored['realistic_final_gate']['passed'],True,'restored realistic workload gate failed')
        old_rows={r['prompt_id']:r for r in strict['rows']}
        same({r['prompt_id'] for r in restored['rows']},set(old_rows),'restored strict coverage differs')
        for row in restored['rows']:
            original=old_rows[row['prompt_id']]
            same(row['prompt_sha256'],original['prompt_sha256'],'restored strict prompt differs')
            same(row['token_ids'],original['token_ids'],'restored strict full output differs')
            same(row['cached_tokens'],0,'restored strict cache is not zero')
            offsets=row['token_id_offsets_s']; speed=99/(offsets[99]-offsets[0])
            close(speed,row['tok_s_1_100_intervals_after_ttft'],'restored strict arithmetic differs')
            cc[row['prompt_class']].append(speed)
        medians={key:statistics.median(v) for key,v in sorted(cc.items())}
        restoration['strict_replayed']={'prompt_count':len(restored['rows']),
            'class_medians_tok_s':medians,'class_balanced_tok_s':statistics.median(medians.values()),
            'all_complete_outputs_equal_pre_reboot':True,'all_cached_tokens_zero':True,'canaries_passed':True,
            'realistic_final_gate':restored['realistic_final_gate']}
    return {'schema':'neural.download.amd-transfer-fp8-summary.v1',
        'classification':'bounded-control-measurements-and-rejected-candidate-screen',
        'new_optimization_promoted':False,
        'control':{'identity':read('control-identity.json'),'strict_prompt_count':len(strict['rows']),'canaries_passed':True,'realistic_workload_gate_passed':True,
            'strict_class_medians_tok_s':class_medians,'strict_class_balanced_tok_s':strict_rate,
            'old_reference_tok_s':historical_rate,'historical_full_token_comparison_replayed':True,
            'historical_reference_difference_percent':100*(strict_rate/historical_rate-1),
            'historical_difference_is_matched_optimization_comparison':False,
            'complete_token_reference_parity':parity['comparison'],
            'context':{'by_length':rates,'measured_requests':len(rebuilt),'warmups':len(context['warmups']),
                'all_cached_tokens_zero':all_cache_zero,'all_complete_repeat_outputs_exact':True,
                'server_prefill_definition':'first scheduled execution to first token, from server histogram deltas',
                'context_decode_is_forced_128_token_continuation_screen':True}},
        'projection_dispatch':{'status':'exact-but-no-established-wall-time-win',
            'exact_cases':len(projection['cases']),'timing_recomputed_from_raw_blocks':projected,
            'model_endpoint_test_performed':False,'larger_row_sweep_performed':False},
        'dflash2':{'status':'host-freeze-during-loading-no-inference-result',
            'benchmark_requests_sent':incident['benchmark_requests_sent'],
            'candidate_ready':incident['candidate_ready'],
            'specific_cause':incident['specific_cause'],
            'disposition':incident['candidate_disposition'],
            'reboot_performed_by_agent':incident['reboot_performed_by_agent'],
            'scope':'Combined newest-upstream/V2/DFlash candidate; incident does not isolate DFlash as cause'},
        'restoration':restoration,
        'publication':'Measurements document original control; no new speed claim, recipe default or external submission.'}

def verify_archive(archive, entries):
    with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tf:
        members=tf.getmembers()
        same([m.name for m in members],list(entries),'archive member coverage/order differs')
        for m in members:
            relative=PurePosixPath(m.name)
            if not m.isfile() or relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Unsafe archive member')
            raw=tf.extractfile(m).read()
            same(len(raw),entries[m.name]['bytes'],'archive member size differs')
            same(sha(raw),entries[m.name]['sha256'],'archive member hash differs')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=DEFAULT_ROOT)
    ap.add_argument('--packet',type=Path,default=DEFAULT_PACKET)
    ap.add_argument('--include-restored-snapshot',action='store_true')
    args=ap.parse_args()
    data=select(args.root,args.packet,args.include_restored_snapshot)
    summary=summarize(data)
    entries={name:{'bytes':len(raw),'sha256':sha(raw)} for name,raw in sorted(data.items())}
    buffer=io.BytesIO()
    with gzip.GzipFile(fileobj=buffer,mode='wb',mtime=0,filename='') as gz:
        with tarfile.open(fileobj=gz,mode='w') as tf:
            for name in entries:
                raw=data[name];info=tarfile.TarInfo(name)
                info.size=len(raw);info.mode=0o644;info.mtime=0
                tf.addfile(info,io.BytesIO(raw))
    archive=buffer.getvalue()
    verify_archive(archive,entries)
    summary_raw=json_bytes(summary)
    manifest={'schema':'neural.download.amd-transfer-evidence-manifest.v1',
        'raw_root':str(args.root),'archive':'evidence.tar.gz','archive_bytes':len(archive),
        'archive_sha256':sha(archive),'summary_sha256':sha(summary_raw),
        'collector_repository_path':str(Path(__file__).resolve().relative_to(REPO)),
        'collector_sha256':sha(Path(__file__).read_bytes()),
        'member_count':len(entries),'members':entries,
        'verification':{'all_archive_member_hashes_verified':True,
            'context_sse_metrics_and_strict_intervals_replayed':True,
            'projection_raw_blocks_recomputed':True,'credential_scan_passed':True},
        'selection':'Explicit allowlist; no model weights, caches, binaries or whole-system journals.'}
    args.packet.mkdir(parents=True,exist_ok=True)
    # Write complete generated artifacts only after replay/archive checks pass.
    for name,raw in [('evidence.tar.gz',archive),('summary.json',summary_raw),('manifest.json',json_bytes(manifest))]:
        temp=args.packet/(name+'.tmp');temp.write_bytes(raw);temp.replace(args.packet/name)
    print(json.dumps({'passed':True,'members':len(entries),'archive_bytes':len(archive),
        'strict_tok_s':summary['control']['strict_class_balanced_tok_s'],
        'context_lengths':list(summary['control']['context']['by_length']),
        'restoration':summary['restoration']['status']},indent=2))

if __name__=='__main__': main()

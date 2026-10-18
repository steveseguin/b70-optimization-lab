#!/usr/bin/env python3
"""Coordinator child: persistent single-card target suites and unchanged p49 oracle."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ORACLE = Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet49-integrate/oracle')
ARITHMETIC = 'iq3-p49-split32-v1'
SUITE_SHA = '0ad543d1c1f379a0b6cee88e06236e495c45eee7ba12cfcef062b6e03303e812'
WINDOWS = ('KD', 'W2m', 'WS', 'WS128x', 'WS128')

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

METRICS = module('p58_metrics', HERE.parent / 'packet56-draft-prefix/suite_metrics.py')
CHECK = module('p58_oracle_check', ORACLE / 'suite_check.py')

def require(condition, message):
    if not condition:
        raise ValueError(message)

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def save(path, row):
    Path(path).write_text(json.dumps(row, indent=2, allow_nan=False) + '\n')

def token_hash(tokens):
    return hashlib.sha256(json.dumps(tokens, separators=(',', ':')).encode()).hexdigest()

def oracle_inputs():
    """Verify sealed completion and original input bytes without model payload reads."""
    binding = read(HERE / 'oracle-binding.json')
    for name, digest in binding['files_sha256'].items():
        require(sha(ROOT / name) == digest, 'oracle source binding: ' + name)
    completion = read(ORACLE / 'results/completion.json')
    require(completion['passed'] is True and completion['device_executed'] is False
            and completion['arithmetic'] == ARITHMETIC and completion['prompts'] == 12
            and completion['token_cap'] == 128, 'incomplete registered oracle')
    for key, leaf in [('manifest_sha256','suite-manifest.json'), ('determinism_sha256','determinism.json'),
                      ('kd_capture_sha256','kd-capture.json'), ('old_v_new_sha256','old-v-new.json')]:
        require(sha(ORACLE / 'results' / leaf) == completion[key], 'oracle completion pin')
    require(sha(ORACLE/'build-receipt.json')==completion['build_receipt_sha256'], 'oracle build pin')
    manifest = read(ORACLE/'results/suite-manifest.json')
    require(manifest.get('complete') is True and manifest['arithmetic']==ARITHMETIC
            and manifest['suite_sha256']==SUITE_SHA and manifest['token_cap']==128
            and manifest['context']==4096, 'oracle suite identity')
    require([e['prompt_id'] for e in manifest['prompts']]==list(CHECK.PROMPT_IDS), 'full fixed prompt order')
    for entry in manifest['prompts']:
        bundle = (ROOT/entry['input_bundle']).resolve()
        require(bundle.is_relative_to(ROOT), 'input bundle escapes repository')
        for leaf,digest in entry['input_bundle_hashes'].items():
            require(Path(leaf).name==leaf and sha(bundle/leaf)==digest, 'input bundle hash')
        expected=ORACLE/'results'/entry['prompt_id']
        require(sha(expected/'receipt.json')==entry['oracle_receipt_sha256'], 'oracle request pin')
        receipt=read(expected/'receipt.json')
        require(receipt.get('verified') is True and sha(expected/'result.json')==receipt['result_sha256']
                and sha(expected/'validation.json')==receipt['validation_sha256'], 'oracle output binding')
    return manifest

def compare_request(actual, oracle, entry, cap, retain):
    result=read(actual/'result.json')
    require(result.get('passed') is True and result.get('arithmetic')==ARITHMETIC, 'native request failed')
    expected=CHECK.token_record(oracle)
    require(result['tokens']==expected[:cap], 'target token identity mismatch: '+entry['prompt_id'])
    require(result.get('cached_tokens')==0 and result.get('gpu_count')==1
            and result.get('decode_mode')=='plain' and result.get('context')==4096, 'request identity')
    require(result['requested_max_new']==cap and result['prompt_tokens']==entry['prompt_tokens'], 'request lengths')
    reset=read(actual/'reset.json')
    require(reset.get('passed') is True and reset.get('cached_tokens')==0 and reset.get('allocation_ids_preserved') is True,
            'request reset missing')
    count=0
    if retain!='none':
        for step in range(1,min(8,len(result['tokens']))+1):
            rows=[json.loads(x) for x in (actual/f'step{step}/layers.jsonl').read_text().splitlines()]
            require([r['layer'] for r in rows]==list(range(48)), 'retained layer coverage')
            for row in rows:
                leaf=f"step{step}/layer-{row['layer']:02}.bf16"
                raw=(actual/leaf).read_bytes()
                require(len(raw)==20480 and hashlib.sha256(raw).hexdigest()==row['sha256']
                        and raw==(oracle/leaf).read_bytes(), 'layer byte mismatch: '+leaf)
                count+=1
    metrics=METRICS.request_metrics(result,entry['prompt_tokens'],cap,retain,
        start=result['request_start_monotonic'],end=result['request_end_monotonic'],device=True)
    inp=read(ROOT/entry['input_bundle']/'input.json')
    return dict(metrics,passed=True,prompt_id=entry['prompt_id'],prompt_class=METRICS.PROMPT_CLASSES[entry['prompt_id']],
        prompt_token_sha256=token_hash(inp['tokens']),tokens=result['tokens'],repeat=1,
        exact_oracle=True,compared_layer_fixtures=count,native_result_sha256=sha(actual/'result.json'))

def summarize(out, window, manifest):
    cap=8 if window in ('KD','W2m') else 128
    entries=manifest['prompts'][:1] if cap==8 else manifest['prompts']
    retain='1-8' if window in ('KD','W2m','WS') else 'none'
    native=read(out/'run/receipt.json')
    require(native.get('passed') is True and native.get('safe_to_exit') is True
            and native.get('device_executed') is True and native.get('owner_cards')==1, 'native owner failed')
    teardown=native.get('teardown')
    require(isinstance(teardown,list) and len(teardown)==1, 'single native owner teardown missing')
    owner=teardown[0]
    require(owner.get('safe_to_exit') is True and owner.get('idle_marker_complete') is True
            and all(type(owner.get(key)) is int and owner[key]==0 for key in ('exit_code','live_bytes','in_flight')),
            'native owner did not drain and release all allocations')
    rows=[compare_request(out/'run'/entry['prompt_id'],ORACLE/'results'/entry['prompt_id'],entry,cap,retain)
          for entry in entries]
    aggregate=METRICS.aggregate(rows)
    return dict(aggregate,schema='own-runtime.packet58.suite.v1',passed=True,device_executed=True,
        arithmetic=ARITHMETIC,window=window,gpu_count=1,decode_mode='plain',context=4096,kv_dtype='BF16',
        suite_sha256=SUITE_SHA,oracle_completion_sha256=sha(ORACLE/'results/completion.json'),
        cached_tokens=0,requests=rows,requested_max_new=cap,request_count=len(rows),
        retained_steps=retain,weight_cache_persists=True,prompt_kv_response_reuse=False,
        cold_fill='empty content-independent cache; first request and per-position cache costs included',
        native_receipt_sha256=sha(out/'run/receipt.json'))

def native_command(args, manifest, table):
    entry=manifest['prompts'][0];bundle=ROOT/entry['input_bundle'];inp=read(bundle/'input.json')
    cap=8 if args.window in ('KD','W2m') else 128
    retain='1-8' if args.window in ('KD','W2m','WS') else 'none'
    model=Path(inp['model_dir']).resolve()
    require(model==Path('/mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS').resolve(), 'unadmitted IQ3 path')
    return ['ionice','-c3',str(HERE/'build/device/own-rt-iq3'),'--authorized-device-window',
        '--card','0','--cards','1','--context','4096','--max-new',str(cap),'--stage','decode',
        '--memory','resident','--miss-path',('zero-copy' if args.miss_mode=='zerocopy' else 'streamed'),'--native-nice','19','--timing','token',
        '--retain-steps',retain,'--suite-inputs',str(table),'--input',str(bundle/'tokens.txt'),
        '--plan',str(bundle/'plan.tsv'),'--identity',str(bundle/'identity.tsv'),'--model-dir',str(model),
        '--selection',str(HERE/'selection.json'),'--selection-sha256',sha(HERE/'selection.json'),
        '--dispatch',str(HERE/'dispatch-speed6.json'),'--output',str(args.output/'run'),
        '--seconds','3600']

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--window',choices=WINDOWS,required=True);ap.add_argument('--card',type=int,choices=(0,2),required=True)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--miss-mode',choices=('zerocopy','streamed'),required=True)
    ap.add_argument('--authorized-device-window',action='store_true')
    args=ap.parse_args(argv)
    require(args.authorized_device_window,'coordinator window authorization required')
    require(os.environ.get('ONEAPI_DEVICE_SELECTOR')==f'level_zero:{args.card}', 'physical card mask differs')
    require(os.getpriority(os.PRIO_PROCESS,0)==19 and set(os.sched_getaffinity(0))<=set(range(4,16))|set(range(20,32)), 'CPU restrictions')
    args.output=args.output.resolve();require(args.output.is_relative_to(HERE/'evidence'), 'packet evidence output required')
    args.output.mkdir(parents=True,exist_ok=True)
    require(not (args.output/'run').exists() and not (args.output/'receipt.json').exists(), 'output already used')
    manifest=oracle_inputs();save(args.output/'suite-manifest.snapshot.json',manifest)
    entries=manifest['prompts'][:1] if args.window in ('KD','W2m') else manifest['prompts']
    table=args.output/'suite-inputs.tsv'
    table.write_text(''.join(f"{e['prompt_id']} {(ROOT/e['input_bundle']/'tokens.txt').resolve()}\n" for e in entries))
    command=native_command(args,manifest,table)
    row=dict(schema='own-runtime.packet58.driver.v1',passed=False,safe_to_exit=False,device_executed=False,
             window=args.window,arithmetic=ARITHMETIC,command=command,card=args.card,gpu_count=1)
    save(args.output/'receipt.json',row)
    child=None;stopping=[]
    def stop(signum,frame):
        stopping.append(signum)
        if child is not None and child.poll() is None:child.send_signal(signal.SIGTERM)
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,stop)
    try:
        with (args.output/'native.log').open('w') as log:
            child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
            row.update(device_executed=True,native_pid=child.pid)
            save(args.output/'receipt.json',row)
            status=child.wait()
        row['safe_to_exit']=True
        require(status==0 and not stopping,'native failed or coordinator stopped')
        summary=summarize(args.output,args.window,manifest);save(args.output/'summary.json',summary)
        row.update(passed=True,summary_sha256=sha(args.output/'summary.json'))
        return 0
    except Exception as error:
        row['error']=str(error)
        # Parent supervises this process tree; never detach a live native child.
        if child is not None and child.poll() is None:
            child.send_signal(signal.SIGTERM);child.wait()
        row['safe_to_exit']=True
        return 1
    finally:save(args.output/'receipt.json',row)

if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,OSError,KeyError) as error:print('REFUSED: '+str(error),file=sys.stderr);sys.exit(1)

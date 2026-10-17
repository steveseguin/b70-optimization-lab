#!/usr/bin/env python3
"""Strict packet47 case/event validation. CPU tests do not launch a device."""
import argparse
import hashlib
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTEXTS = (1024,2048,4096,8192,32768)
EXACT_CONTEXTS = CONTEXTS + (1027,2051,4099)
SEEDS = (18176,18177)
VARIANTS = ('current','ordered','split32')
CLASSES = ('qsa.attention','qsa.select','qsa.qgate')
CONTROLS = ('inactive','sticky-error','invalid-position','invalid-id','empty')
WARMUP, MEASURED = 10, 200


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def exact_keys():
    result = set()
    for context in EXACT_CONTEXTS:
        for rows in (1,2):
            for seed in SEEDS:
                for variant in VARIANTS:
                    for buffer in ('attention.output','readonly.input'):
                        result.add((context,rows,seed,variant,'normal',buffer))
                for buffer in ('selection.ids','qgate.output'):
                    result.add((context,rows,seed,'current','normal',buffer))
    for rows in (1,2):
        for control in CONTROLS:
            for variant in VARIANTS:
                for buffer in ('attention.output','error'):
                    result.add((4096,rows,SEEDS[0],variant,control,buffer))
    return result


def exact(run):
    run = Path(run)
    receipt = json.loads((run/'receipt.json').read_text())
    require(receipt.get('passed') is True and receipt.get('mode') == 'exact'
            and receipt.get('cpu_mock') is False and receipt.get('safe_to_exit') is True,
            'exactness or safe teardown failed')
    records = read_rows(run/'comparisons.jsonl')
    expected, seen = exact_keys(), set()
    require(receipt.get('checks') == len(records), 'comparison count differs')
    for row in records:
        key = tuple(row.get(k) for k in ('context','rows','seed','variant','control','buffer'))
        require(key in expected and key not in seen, 'foreign/duplicate exact case')
        seen.add(key)
        require(row.get('equal') is True, 'raw-byte exactness failed')
        require(type(row.get('bytes')) is int and row['bytes'] > 0, 'empty capture')
        size = {'attention.output':row['rows']*6144*2,
                'selection.ids':row['rows']*2051*4,
                'qgate.output':row['rows']*12288*2,'error':4,
                'readonly.input':row['rows']*32780+row['context']*2048+8}.get(row['buffer'])
        require(size is None or row['bytes'] == size, 'wrong capture byte count')
        digest = row.get('sha256')
        require(isinstance(digest,str) and len(digest)==64 and set(digest)<=set('0123456789abcdef'), 'missing raw identity')
        require(row.get('expected_sha256') == digest, 'CPU reference hash differs')
    require(seen == expected, 'incomplete exactness matrix')
    return dict(passed=True, comparisons=len(records),
                exact_output_identity=hashlib.sha256((run/'comparisons.jsonl').read_bytes()).hexdigest())


def stats(values):
    ordered = sorted(values)
    return dict(median=statistics.median(values),p10=ordered[(len(ordered)-1)//10],
                p90=ordered[9*(len(ordered)-1)//10])


def timing(run):
    run=Path(run)
    receipt=json.loads((run/'receipt.json').read_text())
    require(receipt.get('passed') is True and receipt.get('mode')=='timing'
            and receipt.get('cpu_mock') is False and receipt.get('safe_to_exit') is True,
            'timing or safe teardown failed')
    expected={(c,m,i,v) for c in CONTEXTS for m in (1,2)
              for i in range(WARMUP+MEASURED) for v in VARIANTS}
    require(receipt.get('timing_pair_checks')==len(CONTEXTS)*2*(WARMUP+MEASURED), 'missing pair checks')
    seen={}
    for row in read_rows(run/'iterations.jsonl'):
        key=tuple(row.get(k) for k in ('context','rows','iteration','variant'))
        require(key in expected and key not in seen,'foreign/duplicate timing row')
        require(row.get('warmup') is (row['iteration']<WARMUP),'wrong warmup')
        events=row.get('events',[])
        require(events and len(events)==row.get('submissions'),'missing event coverage')
        totals,ids,counts={},set(),{}
        previous_end=0
        for event in events:
            start,end=event.get('start_ns'),event.get('end_ns')
            require(type(start) is int and type(end) is int and 0<start<end and end-start<=4_000_000_000,'invalid GPU endpoints')
            identifier=event.get('id')
            require(type(identifier) is int and identifier>0 and identifier not in ids,'duplicate/invalid GPU event')
            ids.add(identifier)
            require(start >= previous_end, 'duplicated/overlapping event on in-order queue')
            previous_end=end
            cls=event.get('class')
            require(cls in CLASSES,'unknown GPU class')
            totals[cls]=totals.get(cls,0)+end-start
            counts[cls]=counts.get(cls,0)+1
        require(set(totals)==set(CLASSES),'missing GPU class')
        attention_events={'current':2*row['rows'],'ordered':5,'split32':3}[row['variant']]
        require(counts=={'qsa.attention':attention_events,'qsa.select':2,'qsa.qgate':1},'incomplete kernel census')
        require(totals==row.get('classes_ns') and sum(totals.values())==row.get('gpu_ns'),'GPU accounting differs')
        require(row.get('exact') is True,'timing input pair not exact')
        seen[key]=row
    require(set(seen)==expected,'incomplete timing matrix')
    shapes={}
    for c in CONTEXTS:
        for m in (1,2):
            classes={v:{cls:stats([seen[c,m,i,v]['classes_ns'][cls]/1000
                        for i in range(WARMUP,WARMUP+MEASURED)]) for cls in CLASSES} for v in VARIANTS}
            variants={}
            for v in VARIANTS[1:]:
                ratios=[seen[c,m,i,'current']['classes_ns']['qsa.attention']/seen[c,m,i,v]['classes_ns']['qsa.attention']
                        for i in range(WARMUP,WARMUP+MEASURED)]
                variants[v]=dict(paired_attention_speedup=stats(ratios),bar_passed=statistics.median(ratios)>=3,
                    order_preference_passed=v=='ordered' and statistics.median(ratios)>=5)
            shapes[f'c{c}-m{m}']=dict(classes_gpu_us=classes,variants=variants,measured_pairs=MEASURED)
    return dict(passed=True,device_executed=True,model_speed_claim=False,microbenchmark_only=True,
                shapes=shapes,timing_definition='sum of unique completed GPU command_end-command_start by class')


def fresh_pair(paths):
    from window_support import prerequisite,verify_files,sha,sealed_gate
    sealed_gate()
    require(len(paths)==2 and len({str(Path(p).resolve()) for p in paths})==2,'two timing paths required')
    windows=[json.loads(Path(p).read_text()) for p in paths]
    for row in windows:
        require(row.get('schema')=='own-runtime.packet47.window.v1' and row.get('passed') is True
            and row.get('mode')=='timing' and row.get('device_executed') is True
            and row.get('child_still_running') is False,'incomplete timing window')
        require(row.get('seal_sha256')==sha(HERE/'seal.json'),'window is not this seal')
    for key in ('seal_sha256','binary_sha256','card','boot_id','environment','exactness_companions','coordinator_fault_review'):
        require(key in windows[0] and windows[0].get(key)==windows[1].get(key),'timing identity differs: '+key)
    require(len({(r['pid'],r['process_start_ticks']) for r in windows})==2,'timing owners not fresh')
    for path,row in zip(paths,windows):
        verify_files(row['native_files'],Path(path).resolve().parent)
        for c in row['exactness_companions']:
            require(sha(Path(c['path']))==c['sha256'],'exact companion changed')
            exact(Path(c['path']).parent/'run')
        prerequisite([Path(c['path']) for c in row['exactness_companions']],row)
    summaries=[timing(Path(p).parent/'run') for p in paths]
    candidates={v:all(s['shapes'][f'c4096-m{m}']['variants'][v]['bar_passed']
                    for s in summaries for m in (1,2)) for v in VARIANTS[1:]}
    ordered_preferred=all(s['shapes'][f'c4096-m{m}']['variants']['ordered']['order_preference_passed']
                          for s in summaries for m in (1,2))
    return dict(schema='own-runtime.packet47.two-owner-timing.v1',passed=True,device_executed=True,
        model_speed_claim=False,windows=[str(Path(p).resolve()) for p in paths],
        integration_candidates=candidates,prefer_ordered=ordered_preferred,fresh_owners=summaries)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--windows',nargs=2,type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();require(not args.output.exists(),'summary output must be new')
    args.output.write_text(json.dumps(fresh_pair(args.windows),indent=2)+'\n')

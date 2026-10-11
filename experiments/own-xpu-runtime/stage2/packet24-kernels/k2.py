#!/usr/bin/env python3
"""K2 CPU preparation and exact GPU-event reduction. Never launches a device."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import struct

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
CENSUS=ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json'
SEEDS=HERE.parent/'packet2/build/timing-input'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x): Path(p).write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n')
def prepare(out):
    out.mkdir(parents=True,exist_ok=True)
    tensors=json.loads(CENSUS.read_text())['tensors']
    selected=[t for t in tensors if (t['layer'] in (0,1,2,3) or t['name'].startswith('output')) and t['component'] not in ('embedding','ple_lookup')]
    # All stored descriptor bytes are retained; only a <=64KiB packed seed is
    # resident on the host. K2 fills its device allocations in 4MiB chunks.
    directory=[];seeds=[];proof={}
    seed_rows={}
    for line in (SEEDS/'plan.tsv').read_text().splitlines():
        r=line.split();seed_rows[r[1]]=(int(r[2]),int(r[4]),SEEDS/r[-1])
    for t in selected:
        name=t['name'];target=out/(name+'.packed')
        source=SEEDS/(name+'.packed')
        if source.exists():
            data=source.read_bytes();origin=str(source.relative_to(ROOT));source_hash=sha(source)
        elif t['type'] in ('F32','BF16'):
            # Norm gains=1, decay=-1, all other control tensors=0. This is a
            # synthetic workload, never output or speed evidence for a model.
            value=1.0 if 'norm' in name else -1.0 if name.endswith('ssm_a') else 0.0
            data=struct.pack('<f',value) if t['type']=='F32' else struct.pack('<H',struct.unpack('<I',struct.pack('<f',value))[0]>>16)
            origin='synthetic scalar repeated';source_hash=None
        else:
            candidates=[p for typ,cols,p in seed_rows.values() if typ==t['type_id'] and cols==t['dimensions'][0]]
            if not candidates: raise ValueError('No exact grid/row-shape seed: '+name)
            source=candidates[0];data=source.read_bytes();origin=str(source.relative_to(ROOT));source_hash=sha(source)
        if not 0<len(data)<=65536: raise ValueError('Seed extent '+name)
        target.write_bytes(data)
        directory.append(f"{name} {t['type']} {','.join(map(str,t['dimensions']))} {t['bytes']} {t['component']}")
        seeds.append(f'{name} {target.name}')
        proof[name]={'source':origin,'source_sha256':source_hash,'seed_sha256':sha(target),'seed_bytes':len(data),'weight_bytes':t['bytes'],'type':t['type'],'dimensions':t['dimensions']}
    (out/'directory.tsv').write_text('\n'.join(directory)+'\n');(out/'seeds.tsv').write_text('\n'.join(seeds)+'\n')
    save(out/'input-receipt.json',{'schema':'packet24.k2.input.v1','device_executed':False,'census_sha256':sha(CENSUS),'directory_sha256':sha(out/'directory.tsv'),'seeds_manifest_sha256':sha(out/'seeds.tsv'),'tensors':proof,'host_seeds_total':sum(x['seed_bytes'] for x in proof.values()),'diagnostic':True})
    return len(selected)
def p90(v):
    # Nearest-rank p90, stated explicitly; median is conventional even-n median.
    return sorted(v)[math.ceil(.9*len(v))-1]
def summarize(run):
    receipt=json.loads((run/'receipt.json').read_text())
    if receipt.get('passed') is not True or receipt.get('device_executed') is not True or receipt.get('safe_to_exit') is not True or not receipt.get('teardown') or any(r.get('safe_to_exit') is not True or r.get('in_flight')!=0 or r.get('live_bytes')!=0 for r in receipt['teardown']): raise ValueError('K2 native success/safe teardown required')
    manifest=json.loads((run/'manifest.json').read_text());expected={x['label']:x for x in manifest['groups']}
    grouped=defaultdict(list);event_counts=defaultdict(list);seen=defaultdict(set);byclass=defaultdict(list);seen_events=set()
    for row in map(json.loads,(run/'events.jsonl').read_text().splitlines()):
        version,label,rep=row['kernels'],row['label'],row['repetition'];key=(version,label)
        if label not in expected or rep in seen[key] or not 0<=rep<200: raise ValueError('Missing/duplicate/unexpected K2 repetition')
        if row['class']!=expected[label]['class'] or row['groups_per_token']!=expected[label]['groups_per_token']: raise ValueError('Raw class/frequency differs from manifest')
        seen[key].add(rep);events=row['events']
        ids=[e['event'] for e in events]
        if len(set(ids))!=len(ids) or any(i in seen_events for i in ids): raise ValueError('Duplicate owned compute event')
        seen_events.update(ids)
        if not events: raise ValueError('No GPU events')
        times=[e['command_end_ns']-e['command_start_ns'] for e in events]
        if any(t<=0 for t in times): raise ValueError('Invalid GPU duration')
        grouped[key].append(sum(times)/1000);event_counts[key].append(len(events))
    versions={v for v,_ in grouped}
    if versions!={'v1','v2'}: raise ValueError('K2 requires both kernel versions')
    for v in versions:
        for label,desc in expected.items():
            key=(v,label)
            if seen[key]!=set(range(200)): raise ValueError('K2 coverage incomplete '+str(key))
            byclass[(v,desc['class'])].append((desc,grouped[key],event_counts[key]))
    rows=[]
    for (v,c),sites in byclass.items():
        values=[x for _,vals,_ in sites for x in vals]
        launches=[x for _,_,counts in sites for x in counts]
        per_token=sites[0][0]['groups_per_token']
        rows.append({'kernels':v,'class':c,'median_execution_us':statistics.median(values),'p90_execution_us':p90(values),'groups_per_token':per_token,'median_launches_per_group':statistics.median(launches),'weighted_ms_per_token':statistics.median(values)*per_token/1000,'sampled_sites':len(sites),'repetitions_per_site':200,'label':'synthetic profiling; projected weighting, not decode speed'})
    rows.sort(key=lambda x:(x['kernels'],-x['weighted_ms_per_token']))
    walls=list(map(json.loads,(run/'sequence-wall.jsonl').read_text().splitlines()))
    if {(r['kernels'],r['layer']) for r in walls}!={(v,'blk.'+str(i)) for v in versions for i in range(4)} or any(r['repetitions']!=200 or r['waits']!=1 for r in walls): raise ValueError('K2 per-layer sequence coverage')
    save(run/'summary.json',{'schema':'packet24.k2.summary.v1','diagnostic':True,'arithmetic':'iq3-p17-detmath-v2','definition':'sum(command_end - command_start) per owned compute event; no inter-event gaps','p90_definition':'nearest rank ceil(0.9*N)','rows':rows,'sequence_wall':walls,'raw_events_sha256':sha(run/'events.jsonl'),'manifest_sha256':sha(run/'manifest.json')})
    text=['# Synthetic K2 profiling','', 'These are synthetic kernel diagnostics, not measured model decode rates. Class weights reproduce launch-group frequencies; representative layers 0/1/2/3 include ordinary, PLE, upgraded GDN and QSA shapes. Different packed grids remain visible in the raw rows.','', '| Kernels | Class | Median us/group | p90 us/group | Groups/token | Weighted ms/token |','|---|---|---:|---:|---:|---:|']
    text += [f"| {r['kernels']} | {r['class']} | {r['median_execution_us']:.3f} | {r['p90_execution_us']:.3f} | {r['groups_per_token']} | {r['weighted_ms_per_token']:.3f} |" for r in rows]
    (run/'TABLE.md').write_text('\n'.join(text)+'\n')
    return len(rows)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','summarize']);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(prepare(a.output) if a.action=='prepare' else summarize(a.output))

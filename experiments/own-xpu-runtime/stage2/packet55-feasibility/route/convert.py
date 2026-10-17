#!/usr/bin/env python3
"""Merge compact native route records. Only completed calibration requests enter output."""
import argparse,gzip,hashlib,heapq,json,math,struct
from pathlib import Path
RECORD=struct.Struct('<QQIIIIIII10I10f');MAGIC=b'P55RTE1\n'

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read_records(path,rank,prompt):
    previous=-1;last_time=0
    with path.open('rb') as f:
        if f.read(8)!=MAGIC:raise ValueError('route header')
        while raw:=f.read(RECORD.size):
            if len(raw)!=RECORD.size:raise ValueError('truncated route record')
            row=RECORD.unpack(raw);seq,stamp,pos,layer,role,n,command,spec,fixture=row[:9]
            if seq<=previous or stamp<last_time or role not in (0,1) or n!=10:raise ValueError('route order/role/count')
            if role==0 and not (0<=layer<48 and rank==(0 if layer<23 else 1)):raise ValueError('target route owner')
            if role==1 and (layer!=0 or rank!=1):raise ValueError('draft route owner')
            ids=list(row[9:19]);weights=list(row[19:29])
            if len(set(ids))!=10 or not all(0<=x<512 for x in ids):raise ValueError('route IDs')
            if not all(math.isfinite(x) and x>=0 for x in weights) or not math.isclose(sum(weights),1.,abs_tol=2e-5):raise ValueError('route probability')
            previous,last_time=seq,stamp
            # Draft position is its own sequential index; confirmed target
            # position = draft position +1. Last prompt position emits token1.
            phase='decode' if pos+(role==1)>=prompt['prompt_tokens']-1 else 'prefill'
            yield dict(prompt_id=prompt['prompt_id'],split=prompt['split'],category=prompt['category'],phase=phase,
                       role=('target','draft')[role],position=pos,layer=layer,ids=ids,weights=weights,
                       sequence=seq,monotonic_ns=stamp,rank=rank,command_id=command,speculative=bool(spec),fixture=fixture)

def convert(root,output):
    root=Path(root);output=Path(output)
    window=json.loads((root/'window.json').read_text())
    if window.get('passed') is not True or window.get('device_executed') is not True:raise ValueError('completed device window required')
    manifest=json.loads((root/'calibration-manifest.json').read_text())
    if len(manifest['prompts'])!=24:raise ValueError('24 calibration prompts required')
    if output.exists():raise ValueError('new output required')
    summary=dict(schema='packet55.route-conversion.v1',passed=False,records=0,requests=[],no_speed_claim=True,
                 traffic_scope='Observed route demand; cancelled terminal layer may have routed before expert execution. Instrumentation changes cancellation schedule.',window_sha256=sha(root/'window.json'),manifest_sha256=sha(root/'calibration-manifest.json'))
    with gzip.open(output,'wt',encoding='utf-8',compresslevel=6) as out:
        for prompt in manifest['prompts']:
            request=root/'requests'/prompt['prompt_id'];result=json.loads((request/'result.json').read_text())
            if not result.get('passed') or not result.get('completed') or result['prompt_id']!=prompt['prompt_id']:raise ValueError('incomplete request')
            # 2026-10-17 amendment: per-request result.json stores the count as output_tokens (generated_tokens
            # is null); the window summary's per-request generated_tokens is authoritative. All three must agree.
            listed={r['prompt_id']:r for r in window['requests']}[prompt['prompt_id']]['generated_tokens']
            count=listed
            if result.get('generated_tokens') not in (None,count) or result.get('output_tokens')!=count or len(result['tokens'])!=count:raise ValueError('generated-token count disagreement')
            expected_positions=set(range(prompt['prompt_tokens']+count-1))
            if not 1<=count<=256:raise ValueError('generated count')
            positions={i:set() for i in range(48)};draft=set();rows=0;files={};commands={};timings={};timing_hashes={}
            streams=[]
            for rank in (0,1):
                file=request/f'rank{rank}'/'routes.p55bin';files[str(rank)]=sha(file)
                streams.append(read_records(file,rank,prompt))
                timing=request/f'rank{rank}'/'timings.jsonl';timing_hashes[str(rank)]=sha(timing)
                for line in timing.read_text().splitlines():
                    event=json.loads(line);key=(rank,event['position'],bool(event['speculative']))
                    if key in timings:raise ValueError('duplicate target timing key')
                    timings[key]=event
            for row in heapq.merge(*streams,key=lambda r:(r['monotonic_ns'],r['rank'],r['sequence'])):
                if row['role']=='target':
                    key=(row['rank'],row['command_id']);group=commands.setdefault(key,dict(position=row['position'],speculative=row['speculative'],layers=[]))
                    if group['position']!=row['position'] or group['speculative']!=row['speculative']:raise ValueError('command identity changes')
                    group['layers'].append(row['layer'])
                else:draft.add(row['position'])
                out.write(json.dumps(row,separators=(',',':'))+'\n');rows+=1
            # Every committed position must have every layer; speculation may add
            # extra rank0 visits, but cannot remove any committed layer coverage.
            observed_commands=set();cancelled_prefixes=0
            for (rank,command),group in commands.items():
                key=(rank,group['position'],group['speculative']);event=timings.get(key)
                if event is None or key in observed_commands:raise ValueError('missing/duplicate target command timing')
                observed_commands.add(key);expected=list(range(0,23) if rank==0 else range(23,48))
                if group['layers']!=expected:
                    if not(rank==0 and group['speculative'] and event['cancelled'] and group['layers']==expected[:len(group['layers'])]):raise ValueError('incomplete/duplicate target command layers')
                    cancelled_prefixes+=1
                if not event['cancelled']:
                    for layer in group['layers']:positions[layer].add(group['position'])
            if any(not event['cancelled'] and key not in observed_commands for key,event in timings.items()):raise ValueError('uncancelled target command missing routes')
            if any(not expected_positions<=got for got in positions.values()):raise ValueError('incomplete target layer/position coverage')
            if not set(range(max(0,len(expected_positions)-1)))<=draft:raise ValueError('incomplete draft route coverage')
            summary['requests'].append(dict(prompt_id=prompt['prompt_id'],split=prompt['split'],generated_tokens=count,
                ended_early=count<256,records=rows,cancelled_route_prefixes=cancelled_prefixes,binary_sha256=files,timings_sha256=timing_hashes,result_sha256=sha(request/'result.json'),
                distinct_target_positions=len(set.union(*positions.values())),distinct_draft_positions=len(draft)))
            summary['records']+=rows
    summary.update(passed=True,requested_scope_complete=all(r['generated_tokens']==256 for r in summary['requests']),all_generated_256=all(r['generated_tokens']==256 for r in summary['requests']),output_sha256=sha(output),output=str(output))
    output.with_suffix(output.suffix+'.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--window',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(convert(a.window,a.output),indent=2))

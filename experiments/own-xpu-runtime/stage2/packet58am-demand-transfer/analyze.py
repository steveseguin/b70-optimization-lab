"""Offline evidence checks. In-run checks never impose timing deadlines."""
import hashlib,json,math,statistics
from pathlib import Path
from packet_io import P,ROOT,AH,sha,save

def require(ok,message):
    if not ok:raise ValueError(message)
def close_ms(a,b):
    return abs(a-b)<=max(.001,.02*max(abs(a),abs(b)))
def stream(path):
    raw=Path(path).read_bytes();require(raw.endswith(b'\n'),'truncated stream')
    rows=[json.loads(line) for line in raw.splitlines()]
    require(bool(rows),'missing stream rows');return rows
def request(result,generated,prefill,*,offline=True):
    require(result['arithmetic']=='iq3-p49-split32-v1','wrong arithmetic')
    require(result['passed'] and result['cached_tokens']==0,'exact uncached result')
    require(result['gpu_count']==1 and result['decode_mode']=='plain' and result['context']==4096,'wrong identity')
    tokens=result['tokens']
    if offline:require(len(tokens)==result['requested_max_new'],'token coverage')
    if offline:
        require(len(generated)==len(tokens),'generated stream coverage')
        require(len(prefill)==result['prompt_tokens']-1,'prefill stream coverage')
        require([r['generated_index'] for r in generated]==list(range(1,len(tokens)+1)),'duplicate/missing generated row')
        require([r['token_index'] for r in prefill]==list(range(len(prefill))),'duplicate/missing prefill row')
        require([r['token_id'] for r in generated]==tokens,'token exactness')
    require(all(r['kind']=='generated_token' for r in generated) and all(r['kind']=='prefill_token' for r in prefill),'stream kind')
    for row in generated+prefill:
        for key in ('wall_ms','prepare_ms','wait_ms'):
            require(type(row[key]) in (int,float),'timing format')
            if offline:require(math.isfinite(row[key]) and row[key]>=0,'timing value')
    if offline:
        require(close_ms(generated[0]['wall_ms'],result['first_generated_token_ms']),'first-token same-scope timing')
        # Prefill total includes bookkeeping; do not equate it with a sum of
        # device/kernel scopes. Different clocks are never subtracted here.
    if offline:require(len(result['timing_rows'])==len(tokens),'timestamp count')
    times=[r['completed_monotonic'] for r in result['timing_rows']]
    if offline:require(all(a<b for a,b in zip(times,times[1:])),'timestamp order')
    return dict(first_prefill_row=prefill[0],first_generated_row=generated[0],
                prefill_total_ms=result['prefill_ms'],rate99=99/(times[99]-times[0]) if offline and len(times)>=100 else None,
                demand_events=None,demand_schema_present=False)

def demand_stream(rows,identity,expected_positions,*,offline=True):
    if not offline:
        require(bool(rows),'missing demand stream')
        for row in rows:
            require(row['schema']=='packet58am.demand.v1' and row['identity']==identity,'demand identity')
            for key in ('position','layer','staged_entries','staged_bytes','descriptor_producer','descriptor_readback','missing_consumer'):
                require(type(row[key]) is int,'demand field format: '+key)
            require(isinstance(row['events'],list) and bool(row['events']),'event stream presence')
            for event in row['events']:
                require(isinstance(event['kind'],str),'event kind format')
                require(all(type(event[k]) is int for k in ('id','start_ns','end_ns')),'event format')
        return True
    require(len(rows)==48*expected_positions,'demand coverage')
    seen=set()
    for row in rows:
        require(row['schema']=='packet58am.demand.v1' and row['identity']==identity,'demand identity')
        key=(row['position'],row['layer']);require(key not in seen,'duplicate demand layer');seen.add(key)
        require(0<=row['layer']<48 and type(row['position']) is int and row['position']>=0,'demand layer range')
        require(row['slot_ids']==list(range(10)),'original slot identity')
        require(row['staged_bytes']==row['staged_entries']*1971200,'packed byte count')
        require(row['copy_engine']=='copy-only-BCS','wrong copy engine')
        require(row['descriptor_producer']<row['descriptor_readback'],'descriptor event order')
        if row.get('mode')!='off':require(row['descriptor_readback']<row['missing_consumer'],'missing consumer event order')
        require(row['all_consumers_completed'] and row['snapshot_disposition']=='retained-until-policy','consumer closure')
        events=row['events'];ids=[e['id'] for e in events];require(len(ids)==len(set(ids)),'duplicate event')
        by_kind={e['kind']:e for e in events if e['kind']!='packed-H2D'}
        compute_kinds={'original-mixed-gate','original-mixed-down'} if row.get('mode')=='off' else {'resident-gate','resident-down'}
        require({'router','descriptor','descriptor-D2H'}|compute_kinds<=by_kind.keys(),'missing native events')
        require(sum(e['kind']=='packed-H2D' for e in events)==row['staged_entries']*3,'copy event coverage')
        require(row['clock_domain']=='same-device-sycl-profiling','unqualified clock domain')
        if row.get('mode')!='off':require({'missing-gate','missing-down','stage-map-H2D'}<=by_kind.keys(),'missing consumer edges')
        for event in events:
            require(all(type(event[k]) is int and event[k]>0 for k in ('id','start_ns','end_ns')),'event format')
            if offline:require(event['end_ns']>=event['start_ns'],'event interval order')
        if offline:
            for before,after in [('router','descriptor'),('descriptor','descriptor-D2H')]:require(by_kind[before]['end_ns']<=by_kind[after]['start_ns'],'cross-queue producer edge')
            if row.get('mode')!='off':
                require(by_kind['stage-map-H2D']['end_ns']<=by_kind['missing-gate']['start_ns'],'gate copy-consumer edge')
                for e in events:
                    if e['kind']=='packed-H2D':require(e['end_ns']<=by_kind['missing-down']['start_ns'],'down copy-consumer edge')
    positions={r['position'] for r in rows};require(len(positions)==expected_positions,'position coverage')
    for pos in positions:require({r['layer'] for r in rows if r['position']==pos}==set(range(48)),'layer coverage')
    return True

def replay():
    audit_path=P.parent/'packet58al-demand-transfer-prep/evidence/parent-audit.json'
    audit=json.loads(audit_path.read_text())
    for key in ('result','parent_window','native_receipt'):
        require(sha(ROOT/audit[key])==audit[key+'_sha256'],'parent hash '+key)
    for row in audit['file_pins']:require(sha(ROOT/row['path'])==row['sha256'],'parent stream hash')
    receipt=json.loads((ROOT/audit['native_receipt']).read_text());require(receipt['passed'] and receipt['safe_to_exit'] and receipt['device_executed'],'native closure')
    output=Path(receipt['command'][receipt['command'].index('--output')+1]);results=[]
    for row in audit['request_cold_rows']:
        folder=output/row['prompt_id'];r=json.loads((folder/'result.json').read_text())
        checked=request(r,stream(folder/'timings.jsonl'),stream(folder/'prefill-timings.jsonl'))
        results.append(dict(prompt_id=row['prompt_id'],**checked))
    require(len(results)==12 and results[0]['prompt_id']=='incident-retrospective','full cold suite')
    require(results[0]['first_prefill_row']['wall_ms']>23000,'cold row retained')
    result=dict(passed=True,scope='real 58ah parent replay, never 58am measurement',
         parent_audit_sha256=sha(audit_path),receipt_sha256=sha(ROOT/audit['native_receipt']),
         file_pins=audit['file_pins'],requests=results,demand_events_fabricated=False,
         in_run_timing_verdict=False,absolute_ms_tolerance=.001,relative_tolerance=.02)
    save(P/'evidence/parent-replay.json',result)
    return result

def replay_resident():
    root=P.parent/'packet58aj-onecard-resident/evidence/card0-58aj-a/WS128/run/run'
    receipt=json.loads((root/'receipt.json').read_text())
    require(receipt['passed'] and receipt['safe_to_exit'] and receipt['device_executed'],'resident parent closure')
    require(receipt['lookup_residency']['enabled'],'resident record backing')
    rows=[];pins={str((root/'receipt.json').relative_to(ROOT)):sha(root/'receipt.json')}
    for line in (P/'inputs/suite-128.tsv').read_text().splitlines():
        prompt,_,oracle=line.split();folder=root/prompt
        r=json.loads((folder/'result.json').read_text())
        require(r['tokens']==list(map(int,Path(oracle).read_text().split())),'unchanged oracle on resident record')
        checked=request(r,stream(folder/'timings.jsonl'),stream(folder/'prefill-timings.jsonl'))
        rows.append(dict(prompt_id=prompt,**checked))
        for leaf in ('result.json','timings.jsonl','prefill-timings.jsonl'):
            pins[str((folder/leaf).relative_to(ROOT))]=sha(folder/leaf)
    require(len(rows)==12,'all resident record prompts')
    result=dict(passed=True,device_executed=False,scope='replay real packet58aj record; not new demand evidence',
                record='cmveqsmsl00ebrf014yvrsosx',file_pins=pins,requests=rows,
                demand_events_fabricated=False)
    save(P/'evidence/resident-parent-replay.json',result)
    return result

if __name__=='__main__':
    r=replay();print('PASS real parent replay:',len(r['requests']),'requests; first prefill',r['requests'][0]['first_prefill_row']['wall_ms'],'ms')

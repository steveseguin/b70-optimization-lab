"""Offline evidence checks. In-run checks never impose timing deadlines."""
import hashlib,json,math,statistics
from pathlib import Path
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]

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
        partitioned=row.get('mode')!='off' and row.get('layout_supported',True)
        if not row.get('layout_supported',True):
            require(row['staged_entries']==0 and row['missing_consumer']==0,'unsupported layout entered staging')
        if partitioned:require(row['descriptor_readback']<row['missing_consumer'],'missing consumer event order')
        require(row['all_consumers_completed'] and row['snapshot_disposition']=='retained-until-policy','consumer closure')
        events=row['events'];ids=[e['id'] for e in events];require(len(ids)==len(set(ids)),'duplicate event')
        by_kind={e['kind']:e for e in events if e['kind']!='packed-H2D'}
        compute_kinds={'original-mixed-gate','original-mixed-down'} if not partitioned else {'resident-gate','resident-down'}
        require({'router','descriptor','descriptor-D2H'}|compute_kinds<=by_kind.keys(),'missing native events')
        require(sum(e['kind']=='packed-H2D' for e in events)==row['staged_entries']*3,'copy event coverage')
        require(row['clock_domain']=='same-device-sycl-profiling','unqualified clock domain')
        if partitioned:require({'missing-gate','missing-down','stage-map-H2D'}<=by_kind.keys(),'missing consumer edges')
        for event in events:
            require(all(type(event[k]) is int and event[k]>0 for k in ('id','start_ns','end_ns')),'event format')
            if offline:require(event['end_ns']>=event['start_ns'],'event interval order')
        if offline:
            for before,after in [('router','descriptor'),('descriptor','descriptor-D2H')]:require(by_kind[before]['end_ns']<=by_kind[after]['start_ns'],'cross-queue producer edge')
            if partitioned:
                require(by_kind['stage-map-H2D']['end_ns']<=by_kind['missing-gate']['start_ns'],'gate copy-consumer edge')
                for e in events:
                    if e['kind']=='packed-H2D':require(e['end_ns']<=by_kind['missing-down']['start_ns'],'down copy-consumer edge')
    positions={r['position'] for r in rows};require(len(positions)==expected_positions,'position coverage')
    for pos in positions:require({r['layer'] for r in rows if r['position']==pos}==set(range(48)),'layer coverage')
    return True

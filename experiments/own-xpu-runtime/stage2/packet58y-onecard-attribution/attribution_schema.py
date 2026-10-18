"""Shared strict trace checks; passive on import, no runtime/device operations."""
import hashlib,json,math
PHASES=('prepare','enqueue','cache_boundary','cache_plan','readbacks','cache_after')
CAUSES=('compute_including_zero_copy_miss','zero_copy_miss_separate','fill_copies','table_publication','readbacks','input_upload')
CLASSES=('dense_r5','experts_r5','p25_p27_gemv','p28_p29_gemv','small_fusions','specialised_round2','parallel18','combine','check_commit','copy')
COUNTERS=('fills','fill_bytes','misses','hits','miss_bytes','hit_bytes','publication_uploads','publication_bytes','fill_queries','fill_pending_queries')

def require(good,message):
    if not good:raise ValueError('attribution: '+message)

def validate(row):
    require(row.get('schema')=='packet58y.token.v1','schema')
    require(row.get('profiling') is False and row.get('extra_device_waits')==0,'profiling/fences changed')
    require(set(row['device_class_ms'])==set(CLASSES) and all(v is None for v in row['device_class_ms'].values()),'device durations must be unavailable, not zero')
    require(row.get('zero_copy_miss_stall_ms','missing') is None,'miss stall unidentifiable')
    for key,names in [('host_exclusive_ms',PHASES),('host_wait_ms',CAUSES),('host_wait_calls',CAUSES)]:
        require(set(row[key])==set(names),'missing/extra '+key+' bucket')
    parts=[*row['host_exclusive_ms'].values(),*row['host_wait_ms'].values(),row['residual_ms']]
    require(all(type(v) in (int,float) and math.isfinite(v) and v>=-1e-6 for v in parts),'invalid duration')
    require(type(row['wall_ms']) in (int,float) and math.isfinite(row['wall_ms']) and row['wall_ms']>0,'invalid wall')
    require(abs(sum(parts)-row['wall_ms'])<=max(1e-7,row['wall_ms']*1e-10),'partition does not close')
    require(all(type(v) is int and v>=0 for v in row['host_wait_calls'].values()),'wait counts')
    require(row['host_wait_calls']['zero_copy_miss_separate']==0 and row['host_wait_ms']['zero_copy_miss_separate']==0,'unexpected separate miss wait')
    require(len(row['enqueue_class_ms'])==len(row['class_submissions'])==len(CLASSES),'class coverage')
    require(all(type(v) in (int,float) and math.isfinite(v) and v>=-1e-6 for v in row['enqueue_class_ms']),'class duration')
    require(all(type(v) is int and v>=0 for v in row['class_submissions']),'class count')
    require(all(type(row[k]) is int and row[k]>=0 for k in COUNTERS),'cache counters')
    require(type(row['fill_pending_end']) is bool,'pending flag')
    require(row['fill_pending_queries']<=row['fill_queries'],'pending query count')
    return True

def check_request(path,result,full_model=True):
    # Bounded to well above the maximum 4096-position trace, before reading.
    require(path.stat().st_size<=32*1024**2,'trace exceeds 32 MiB cap')
    raw=path.read_bytes();rows=[json.loads(line) for line in raw.splitlines()]
    expected_count=result['prompt_tokens']-1+len(result['tokens'])
    require(len(rows)==expected_count,'missing/truncated/extra token rows')
    generated=[]
    for position,row in enumerate(rows):
        validate(row)
        require(type(row['position']) is int and row['position']==position,'position coverage/order')
        index=max(0,position-result['prompt_tokens']+2)
        require(type(row['generated_index']) is int and row['generated_index']==index,'generated index coverage/order')
        if full_model:require(row['hits']+row['misses']==480,'48 layers x ten selected experts required')
        if index:
            require(type(row['token_id']) is int and row['token_id']==result['tokens'][index-1],'trace token differs from checked result')
            generated.append(row)
    require(len(generated)==len(result['tokens']),'generated coverage')
    return dict(passed=True,rows=len(rows),generated_rows=len(generated),sha256=hashlib.sha256(raw).hexdigest())

"""Recompute the diagnostic head-window result from native rows; no GPU use."""
import hashlib
import json
import math
from pathlib import Path
import statistics

P=Path(__file__).resolve().parent

def require(ok,message):
    if not ok: raise ValueError(message)

def summarize(path):
    path=Path(path)
    chosen=json.loads((P/'calibration/selection.json').read_text())['draft_vocab_rows']
    sizes={32768,65536,98304,chosen,248320}
    receipt=json.loads((path/'receipt.json').read_text())
    require(receipt.get('schema')=='packet56.head-fixture.v1' and receipt.get('passed') is True
            and receipt.get('device_executed') is True and receipt.get('card')==0
            and receipt.get('iterations')==100 and receipt.get('checks')==540
            and receipt.get('full_rows')==248320 and receipt.get('chosen_rows')==chosen
            and receipt.get('head_bytes')==839321600 and receipt.get('weight_copies')==1,'head fixture receipt identity')
    teardown=receipt['teardown']
    require(teardown.get('safe_to_exit') is True and teardown.get('exit_code')==0
            and teardown.get('in_flight')==0,'head fixture teardown not safe')
    comparisons=[json.loads(x) for x in (path/'comparisons.jsonl').read_text().splitlines()]
    events=[json.loads(x) for x in (path/'events.jsonl').read_text().splitlines()]
    require(len(comparisons)==540 and len(events)==500,'head fixture incomplete rows')
    require({(x['iteration'],x['rows']) for x in comparisons}=={(i,n) for i in range(108) for n in sizes},'comparison coverage/duplicates')
    require({(x['iteration'],x['rows']) for x in events}=={(i,n) for i in range(100) for n in sizes},'timing coverage/duplicates')
    for row in comparisons:
        require(row.get('bytes_equal') is True and row.get('argmax_equal') is True
                and 0<=row['argmax']<row['rows'] and len(row['prefix_sha256'])==64,'prefix exactness failure')
    for row in events:
        require(row.get('bytes_equal') is True and row.get('argmax_equal') is True,'timing exactness failure')
        require(all(type(row[k]) in (int,float) and math.isfinite(row[k]) and row[k]>0
                    for k in ('head_us','argmax_us','total_us')),'invalid timing')
        require(abs(row['total_us']-row['head_us']-row['argmax_us'])<.05,'timing component mismatch')
    identity=hashlib.sha256(json.dumps(sorted(comparisons,key=lambda x:(x['iteration'],x['rows'])),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    rows=[]
    for n in sorted(sizes):
        samples=[r for r in events if r['rows']==n]
        rows.append(dict(rows=n,samples=len(samples),**{k+'_median':statistics.median(r[k] for r in samples) for k in ('head_us','argmax_us','total_us')}))
    return dict(schema='packet56.head-summary.v1',passed=True,microbenchmark_only=True,model_speed_claim=False,
                exact_output_identity=identity,chosen_rows=chosen,rows=rows)

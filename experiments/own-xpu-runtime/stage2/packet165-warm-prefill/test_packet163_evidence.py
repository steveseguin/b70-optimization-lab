"""Replay real packet163 full512 evidence; keep its cold prefill visibly cold."""
import copy,json,math,sys
from pathlib import Path
P=Path(__file__).resolve().parent;p=P/'two-card';sys.path.insert(0,str(p))
import measurement as M
read=lambda f:json.loads(f.read_text())
source=P.parent/'packet163-full-gate/two-card/evidence'
key='class_balanced_tok_s_1_100_intervals_after_ttft';results=[]
for attempt in ('a','b'):
    old=source/f'device-full512-B-{attempt}';summary=read(old/'bracket-summary.json');rows=[]
    for ident in M.IDS:
        raw=read(old/'run/requests'/ident/'receipt.json')
        tokens=list(map(int,(p/'inputs'/ident/'tokens.txt').read_text().split()))
        oracle=read(p/'lineage/oracle128'/(ident+'.json'))['tokens']
        rows.append(M.request(raw,tokens,ident,oracle))
    raw=read(old/'run/requests/prefill512/receipt.json')
    tokens=list(map(int,(p/'inputs/prefill512/tokens.txt').read_text().split()))
    prefill=M.request(raw,tokens,'prefill512')
    result=M.aggregate(rows,prefill,summary['identity'])
    assert math.isclose(result[key]['median'],summary[key]['median'],rel_tol=1e-12)
    assert result['strict512'] and prefill['prefill']['warmup'] is None
    assert 'cold' in prefill['prefill']['measurement_temperature']
    assert prefill['prefill']['prefill_phase_device_ms'] is None
    results.append(dict(attempt=attempt,source=str(old.relative_to(P.parents[3])),
        primary_decode_tok_s=result[key]['median'],prefill=prefill['prefill'],real_evidence=True))
    # Explicit negative cache and malformed-stream checks on real prefill.
    for field,value in [('cached_tokens',1),('timing_rows',[]),('tokens',[])]:
        bad=copy.deepcopy(raw);bad[field]=value
        try:M.request(bad,tokens,'prefill512')
        except (ValueError,KeyError):pass
        else:raise AssertionError(field+' accepted')
(P/'evidence/packet163-replay.json').write_text(json.dumps(dict(passed=True,device_executed=False,
    source_is_real_device_evidence=True,new_measurement=False,results=results),indent=2)+'\n')
print('packet163 real full512 analyzer replay PASS',[(r['attempt'],r['primary_decode_tok_s']) for r in results])

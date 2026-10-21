"""Real-record accounting replay and synthetic guard tests; no device/speed claim."""
import copy,importlib,json,math,sys
from pathlib import Path
P=Path(__file__).resolve().parent
name=sys.argv[1];p=P/name;sys.path.insert(0,str(p))
import measurement as M
read=lambda f:json.loads(f.read_text())
rows=[];raws=[]
for ident in M.IDS:
 raw=read(p/'lineage/parent-requests'/(ident+'.json'));raws.append(raw)
 tokens=list(map(int,(p/'inputs'/ident/'tokens.txt').read_text().split()))
 oracle=read(p/'lineage/oracle128'/(ident+'.json'))['tokens']
 rows.append(M.request(raw,tokens,ident,oracle))
a=M.aggregate(rows);parent=read(p/'lineage/parent-summary.json')
key='class_balanced_tok_s_1_100_intervals_after_ttft'
assert math.isclose(a[key]['median'],parent[key]['median'],rel_tol=1e-12)
assert not a['strict512'] and not a['realistic_final_gate']['passed']
# 512 receipt fixtures deliberately synthetic, never performance evidence.
full=[]
for ident,raw in zip(M.IDS,raws):
 r=copy.deepcopy(raw);base=r['tokens'][:128];r['tokens']=base+[42]*384;r['requested_max_new']=512
 r['timing_rows']=[dict(completed_monotonic=100+i*.1)for i in range(512)]
 r.update(request_start_monotonic=99.,request_end_monotonic=152.,prefill_ms=1000.)
 tokens=list(map(int,(p/'inputs'/ident/'tokens.txt').read_text().split()))
 full.append(M.request(r,tokens,ident,base))
assert all(not r['exact_oracle'] for r in full)
pref=copy.deepcopy(full[0]);pref['prefill']=dict(input_tokens=512,users=1)
one=M.aggregate(full,pref,dict(test='synthetic'))
assert one['strict512'] and not one['quality']['full_output_oracle_exact'] and not one['submission_eligible']
two=M.aggregate(full,pref,dict(test='synthetic'),one)
assert two['quality']['fresh_process_determinism_checked']
def refuses(fn):
 try:fn()
 except (ValueError,KeyError):return
 raise AssertionError('invalid evidence accepted')
bad=copy.deepcopy(full);bad[0]['tokens'][200]=43
refuses(lambda:M.aggregate(bad,pref,dict(test='synthetic'),one))
refuses(lambda:M.aggregate(full[:-1],pref))
for field,value in [('cached_tokens',1),('timing_rows',[]),('tokens',[]),('request_end_monotonic',0)]:
 bad=copy.deepcopy(raws[0]);bad[field]=value;refuses(lambda:M.stream_check(bad))
bad=copy.deepcopy(raws[0]);bad['tokens'][0]^=1
refuses(lambda:M.stream_check(bad,read(p/'lineage/oracle128'/(M.IDS[0]+'.json'))['tokens']))
# Early natural completion is allowed; a missing fixed100 window never passes.
r=copy.deepcopy(raws[0]);r['requested_max_new']=512;r['tokens']=r['tokens'][:9]+[248046];r['timing_rows']=r['timing_rows'][:10]
M.stream_check(r)
r['tokens'][-1]=42;refuses(lambda:M.stream_check(r))
result=dict(passed=True,device_executed=False,parent_rate_reproduced=a[key]['median'],parent_strict512=False,parent_exact128=True,synthetic_tests='full512 scope, repeat, mismatch, cache, malformed streams, missing prompt, EOS/cap',synthetic_results_are_not_measurements=True)
(p/'evidence/analyzer-tests.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

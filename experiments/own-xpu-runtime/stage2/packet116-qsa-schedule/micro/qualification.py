"""No speed verdict until both fresh GPU processes pass exact state and kill gate."""
import hashlib,json,math,statistics
from pathlib import Path
P=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def evaluate(p=P,write=True):
 p=Path(p);result=dict(schema='packet116.micro-gate.v1',passed=False,device_speed_measured=False,kill_gate_passed=False,integration_allowed=False,threshold_ratio=0.6,contexts=[128,4096],owners=[])
 try:
  for owner in (1,2):
   d=p/'evidence'/f'micro-B-{owner}'
   if not (d/'window.json').exists():
    result['reason']='two completed fresh device processes required';break
   w=read(d/'window.json');r=read(d/'native/receipt.json')
   assert w['passed'] and w['drained'] and r['passed'] and r['safe_to_exit'] and r['device_executed'] and not r['cpu_mock'] and r['timing_pair_checks']==100 and r['checks']>400,'complete exact/drain gates'
   assert r['arithmetic']=='iq3-p49-split32-v1'
   rows=[json.loads(x) for x in (d/'native/iterations.jsonl').read_text().splitlines()];assert len(rows)==200,'complete 100 pairs'
   cases=[]
   for context in (128,4096):
    selected=[x for x in rows if x['layer']==3 and x['occupied_context']==context];assert len(selected)==100
    production=[];candidate=[];ratios=[]
    for i in range(50):
     pair=[x for x in selected if x['iteration']==i];assert len(pair)==2
     assert [x['mode'] for x in pair]==(['production','p116'] if i%2==0 else ['p116','production']),'both orders alternate'
     assert all(x['warmup']==(i<10) for x in pair)
     times={}
     for x in pair:
      assert len(x['events'])==x['submissions'] and len({y['id'] for y in x['events']})==len(x['events'])
      classes={}
      for y in x['events']:
       ns=y['end_ns']-y['start_ns'];assert 0<ns<=4_000_000_000
       classes[y['class']]=classes.get(y['class'],0)+ns
      assert classes==x['classes_ns'] and sum(classes.values())==x['gpu_ns'],'every event counted including multi-kernel attention'
      attention=[n for n in classes if n.endswith('qsa.attention')];select=[n for n in classes if n.endswith('qsa.select')]
      assert len(attention)==len(select)==1,'both registered classes required'
      times[x['mode']]=classes[attention[0]]+classes[select[0]]
     if i>=10:
      production.append(times['production']);candidate.append(times['p116']);ratios.append(times['p116']/times['production'])
    prod=statistics.median(production);cand=statistics.median(candidate);ratio=cand/prod
    assert math.isfinite(ratio) and prod>0 and cand>0
    cases.append(dict(occupied_context=context,measured_pairs=40,production_attention_select_median_us=prod/1000,p116_attention_select_median_us=cand/1000,ratio_of_medians=ratio,median_paired_ratio=statistics.median(ratios),meets_kill_gate=ratio<=0.6))
   result['owners'].append(dict(owner=owner,pid=w['pid'],start_ticks=w['process_start_ticks'],identity=w['identity'],exact_output_identity=r['exact_output_identity'],cases=cases,receipts={str(x.relative_to(p)):sha(x) for x in (d/'window.json',d/'native/receipt.json',d/'native/iterations.jsonl',d/'native/comparisons.jsonl')}))
  else:
   a,b=result['owners'];assert (a['pid'],a['start_ticks'])!=(b['pid'],b['start_ticks']),'two fresh processes'
   assert a['identity']==b['identity'] and a['exact_output_identity']==b['exact_output_identity'],'same executable/seal and exact bytes in both'
   result['device_speed_measured']=True
   gate=all(c['meets_kill_gate'] for o in result['owners'] for c in o['cases'] if c['occupied_context']==128)
   result.update(passed=gate,kill_gate_passed=gate,integration_allowed=gate,reason='micro kill gate passed; full model byte gate still required' if gate else 'kill gate failed: close schedule, do not queue v5')
 except (AssertionError,KeyError,ValueError,OSError) as error:
  result.update(reason='invalid/incomplete evidence: '+str(error),passed=False,integration_allowed=False,kill_gate_passed=False)
 if write:(p/'evidence/qualification.json').write_text(json.dumps(result,indent=2)+'\n')
 return result
if __name__=='__main__':print(json.dumps(evaluate(),indent=2))

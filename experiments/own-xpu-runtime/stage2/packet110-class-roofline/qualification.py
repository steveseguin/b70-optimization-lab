"""Fail closed: complete real-shape pair data, exactness, two fresh processes."""
import json,statistics,hashlib
from pathlib import Path
def evaluate(p):
 p=Path(p);result=dict(schema='packet107.micro-gate.v1',passed=False,device_speed_measured=False,integration_allowed=False,threshold_us=80,upper_target_us=160,owners=[],closed_layers={'4':'Intel NaN payload byte mismatch; never admitted to device'})
 for owner in (1,2):
  d=p/'evidence'/f'micro-B-{owner}'
  if not (d/'window.json').exists():
   result['reason']='two completed fresh processes required';break
  w=json.loads((d/'window.json').read_text());r=json.loads((d/'native/receipt.json').read_text())
  assert w['passed'] and w['drained'] and r['passed'] and r['safe_to_exit'] and r['device_executed'] and r['timing_pair_checks']==100
  rows=[json.loads(x) for x in (d/'native/iterations.jsonl').read_text().splitlines()]
  cases=[]
  for layer in (3,):
   for context in (128,4096):
    selected=[x for x in rows if x['layer']==layer and x['occupied_context']==context]
    assert len(selected)==100
    deltas=[]
    for i in range(50):
     pair=[x for x in selected if x['iteration']==i];assert len(pair)==2
     assert [x['mode'] for x in pair]==(['current','specialized'] if i%2==0 else ['specialized','current'])
     assert all(x['warmup']==(i<10) for x in pair)
     for x in pair:
      assert len(x['events'])==x['submissions'] and sum(y['end_ns']-y['start_ns'] for y in x['events'])==x['gpu_ns']
     v={x['mode']:x['gpu_ns'] for x in pair}
     if i>=10:deltas.append((v['current']-v['specialized'])/1000)
    saved=statistics.median(deltas)
    cases.append(dict(layer=layer,occupied_context=context,pairs=len(deltas),median_saved_us=saved,meets_80us=saved>=80,meets_160us=saved>=160))
  result['owners'].append(dict(owner=owner,pid=w['pid'],start_ticks=w['process_start_ticks'],identity=w['identity'],exact_output_identity=r['exact_output_identity'],cases=cases))
 else:
  a,b=result['owners'];assert (a['pid'],a['start_ticks'])!=(b['pid'],b['start_ticks'])
  assert a['identity']==b['identity'] and a['exact_output_identity']==b['exact_output_identity']
  result.update(passed=True,device_speed_measured=True)
  result['integration_allowed']=all(x['meets_80us'] for o in result['owners'] for x in o['cases'] if x['occupied_context']==128)
  result['reason']='full model integration gate reached; model oracle still pending' if result['integration_allowed'] else 'close below the preregistered per-layer threshold; no integration'
 (p/'evidence/qualification.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':print(json.dumps(evaluate(Path(__file__).parent),indent=2))

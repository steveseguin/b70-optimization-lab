"""Validate complete receipts and summarize a coordinator R1; never infer speed."""
import json,statistics
from pathlib import Path
def summarize(path):
 path=Path(path);receipt=json.loads((path/'receipt.json').read_text())
 assert receipt['passed'] and receipt['safe_to_exit']
 rows=[json.loads(line) for line in (path/'iterations.jsonl').read_text().splitlines()]
 native=receipt['device_executed'];modes=['direct','graph-whole','graph-layer'] if native else ['direct','mock-whole','mock-layer']
 assert len(rows)==630
 per={m:[r for r in rows if r['mode']==m] for m in modes}
 for mode,values in per.items():
  assert [r['iteration'] for r in values]==list(range(210))
  assert all(r['warmup']==(r['iteration']<10) for r in values)
  assert all(r['state_sha256']==per['direct'][i]['state_sha256'] for i,r in enumerate(values))
 assert receipt['final_state_sha256']==per['direct'][-1]['state_sha256']
 assert receipt['route_hashes']>1 and receipt['parities']==2 and receipt['attention_counts']>1
 result={'passed':True,'device_executed':native,'state_matches':420,'final_state_sha256':receipt['final_state_sha256'],'measured_iterations_per_mode':200,'modes':{},'speed_claim':False}
 if native:
  for mode,values in per.items():
   measured=values[10:]
   if mode=='direct':assert all(len(r['kernel_ns'])==r['submissions'] and sum(r['kernel_ns'])==r['direct_gpu_ns'] for r in values)
   else:assert all(r['submissions']==(1 if mode=='graph-whole' else 24) and r['direct_gpu_ns'] is None for r in values)
   result['modes'][mode]={key:{'median':statistics.median([r[key] for r in measured]),'mean':statistics.mean([r[key] for r in measured]),'min':min(r[key] for r in measured),'max':max(r[key] for r in measured)} for key in ['wall_ns','thread_cpu_ns']+(['direct_gpu_ns'] if mode=='direct' else [])}
  memory=[json.loads(line) for line in (path/'recordings.jsonl').read_text().splitlines()]
  assert len(memory)==6 and [r['recording'] for r in memory]==[1,2,3,1,2,3]
  accounted=all(r['graph_required_bytes_total']<=1024**3 and r['host_rss_after']<8*1024**3 for r in memory)
  driver=all(r['driver_memory_before']['available'] and r['driver_memory_after']['available'] for r in memory)
  driver_growth=None
  if driver:driver_growth=max(0,memory[0]['driver_memory_before']['free_bytes']-min(r['driver_memory_after']['free_bytes'] for r in memory))
  bounded=accounted and driver and driver_growth<=1024**3
  result['memory']={'allocation_accounting_within_bound':accounted,'driver_counter_available':driver,'driver_growth_bytes':driver_growth,'bounded_memory_proven':bounded,'recordings':memory}
  gpu=result['modes']['direct']['direct_gpu_ns']['median']
  result['replay_pays']={m:bool(bounded and result['modes'][m]['wall_ns']['median']<=gpu) for m in modes[1:]}
  result['criterion']='median replay wall <= median direct sum of GPU kernel durations; every iteration bytes identical; measured recording-memory growth <=1GiB; RSS<8GiB. No driver counter leaves bounded-memory verdict pending.'
 else:
  result['replay_pays']=None;result['reason']='CPU oracle/mock only; no device speed or memory verdict'
 (path/'summary.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args();print(json.dumps(summarize(a.run),indent=2))

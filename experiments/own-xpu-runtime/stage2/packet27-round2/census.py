#!/usr/bin/env python3
"""Calculate native launch counts and resident bytes through the host-only plan."""
from pathlib import Path
import collections, hashlib, json, os, subprocess, time
HERE=Path(__file__).resolve().parent
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 inp=HERE/'build/input';binary=HERE/'build/host/own-rt-iq3'
 dynamic=subprocess.check_output(['readelf','-d',str(binary)],text=True,timeout=5)
 assert not any(v in dynamic.lower() for v in ('libsycl','libze_loader','libur_loader','libopencl'))
 model=json.loads((inp/'input.json').read_text())['model_dir'];summary={}
 for dispatch in ('frozen','r5'):
  out=HERE/'build'/f'plan-{dispatch}-{time.time_ns()}'
  subprocess.run([str(binary),'--record','--cards','2','--card','2','--memory','resident','--context','256','--gemv',dispatch,'--output',str(out),'--model-dir',model,'--plan',str(inp/'plan.tsv'),'--identity',str(inp/'identity.tsv')],check=True,timeout=60)
  plan=json.loads((out/'plan.json').read_text());memory=plan['memory_plan']
  totals=[a+b for a,b in zip(memory['request_and_workspace_bytes_per_card'],memory['resident_weights_per_card'])]
  assert all(n<=30*1024**3 for n in totals)
  by_layer=collections.defaultdict(lambda:dict(core=0,parallel=0,sites=0))
  for row in plan['launch_census']:
   layer=row['label'].split('.')[1] if row['label'].startswith('blk.') else 'other';r=by_layer[layer];r['core']+=row['core_kernels'];r['parallel']+=row['parallel_kernels'];r['sites']+=1
  summary[dispatch]=dict(context=256,measured=False,memory=memory,owned_peak_bytes_per_card=totals,launches_by_layer=dict(by_layer),core_kernels=sum(x['core'] for x in by_layer.values()),parallel_kernels=sum(x['parallel'] for x in by_layer.values()),sites=sum(x['sites'] for x in by_layer.values()),variants=dict(collections.Counter(x.get('variant','non-GEMV') for x in plan['tensor_owners'])),runtime_dispatch={x['name']:x['variant'] for x in plan['tensor_owners'] if 'variant' in x})
 (HERE/'census.json').write_text(json.dumps(summary,indent=2)+'\n')
if __name__=='__main__':main()

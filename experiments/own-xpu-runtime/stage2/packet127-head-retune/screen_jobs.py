"""Preregistered v4 B grid and conditional A winner bracket. No live queue writes."""
import json
from build_engine import P,ROOT,sha,save,check_map
from bundle_selection import labelled_views,name
WRAPPER=P.parent/'screen/v4-lanes'
ORDER=('production','81920','122880','production')
def view(label):return P/'selections'/(name(*labelled_views()[label])+'--placement-1')
def jobs(lane,winner=None):
 assert lane in ('A','B')
 if lane=='A':
  assert winner in ('81920','122880'),'A requires the validated B winner'
 order=ORDER if lane=='B' else ('production',winner,'production')
 return [dict(lane=lane,index=i,choice=c,placement='1',out=f'p127-{lane}-'+('grid' if lane=='B' else 'confirm')+f'-{i}-'+('winner' if lane=='A' and i==1 else c)) for i,c in enumerate(order)]
def output(job):return WRAPPER/'evidence'/job['out']
def verify():
 from bootstrap import install
 install();row=json.loads((P/'screen-jobs-seal.json').read_text())
 assert row['schema']=='packet127.v4-grid.v1' and row['request_count']==12 and row['tokens']==128 and row['order']==list(ORDER)
 check_map(ROOT,row['sources']);return row
def launch_receipt():
 path=P/'evidence/launch-limits.json';row=json.loads(path.read_text());assert row['passed'] and row['device_executed'] is False
 check_map(ROOT,row['sources'])
 positive=[r for r in row['cases'] if not r.get('negative_control')];negative=[r for r in row['cases'] if r.get('negative_control')]
 assert len(positive)==3 and {r['role'] for r in positive}==set(labelled_views())
 assert len(negative)==1 and negative[0]['passed'] and 'RLIMIT_AS' in negative[0]['refusal']
 import resource
 for r in positive:
  assert r['passed'] and len(r['observations'])==2
  for o in r['observations']:assert o['unchanged'] and o['limits'][str(resource.RLIMIT_AS)]==[-1,-1]
 return path
def seal_jobs():
 launch=launch_receipt()
 paths=[P/n for n in ('screen_jobs.py','screen_job.py','run_screen.py','runtime_worker.py','worker.py','exec_limits.py','bootstrap.py','conditions.py','drain_gate.py','placement.py','placement-policy.json','bracket_report.py','timing_accounting.py','chain_pipeline.py','memory_gate.py','memory_observation.py','device_gate.py','run_micro.py','launch_limit_gate.py')]
 paths += [view(label)/'screen-seal.json' for label in labelled_views()]
 paths += [launch,P/'evidence/microbench-build.json',P/'evidence/drain-check.json',P/'evidence/protocol-tests.json']
 save(P/'screen-jobs-seal.json',dict(schema='packet127.v4-grid.v1',passed=True,device_executed=False,sources={str(p.relative_to(ROOT)):sha(p) for p in paths},request_count=12,tokens=128,order=list(ORDER),threshold_percent=.5,oracle='iq3-p49-split32-v1',separate_fresh_processes=True))

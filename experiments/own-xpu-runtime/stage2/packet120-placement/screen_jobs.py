"""Fixed v4 production / 25-23 / production brackets; no live queue writes."""
import json
from build_engine import P,ROOT,sha,save,check_map
from bundle_selection import views,name
WRAPPER=P.parent/'screen/v4-lanes'
ORDER=('production','25-23','production')
def view(label):
 v=views()[label];placement='1' if label=='production' else '25-23'
 return P/'selections'/(name(*v)+'--placement-'+placement)
def jobs(lane):
 assert lane in ('A','B')
 return [dict(lane=lane,index=i,choice=c,placement='1' if c=='production' else '25-23',out=f'p120-{lane}-'+('grid' if lane=='B' else 'confirm')+f'-{i}-{c}') for i,c in enumerate(ORDER)]
def output(job):return WRAPPER/'evidence'/job['out']
def verify():
 from bootstrap import install
 install();row=json.loads((P/'screen-jobs-seal.json').read_text())
 assert row.get('schema')=='packet120.v4-brackets.v1' and row['request_count']==12 and row['tokens']==128 and row['order']==list(ORDER)
 for path in (P/'screen_jobs.py',P/'screen_job.py',launch_receipt()):assert row['sources'].get(str(path.relative_to(ROOT)))==sha(path)
 check_map(ROOT,row['sources']);return row
def launch_receipt():
 path=P/'evidence/launch-limits.json';row=json.loads(path.read_text())
 assert row['passed'] is True and row['device_executed'] is False
 check_map(ROOT,row['sources'])
 positive=[r for r in row['cases'] if not r.get('negative_control')]
 negative=[r for r in row['cases'] if r.get('negative_control')]
 assert len(positive)==2 and {r['role'] for r in positive}=={'production','25-23'}
 assert len(negative)==1 and negative[0]['passed'] and 'RLIMIT_AS' in negative[0]['refusal']
 import resource
 for case in positive:
  assert case['passed'] and len(case['observations'])==2
  for observation in case['observations']:
   assert observation['unchanged'] and observation['limits'][str(resource.RLIMIT_AS)]==[-1,-1]
 return path

def seal_jobs():
 launch=launch_receipt()
 paths=[P/n for n in ('screen_jobs.py','screen_job.py','run_screen.py','runtime_worker.py','worker.py','exec_limits.py','bootstrap.py','placement.py','placement-policy.json','bracket_report.py','timing_accounting.py','chain_pipeline.py','memory_gate.py','memory_observation.py')]
 paths += [view(label)/'screen-seal.json' for label in views()]
 paths += [launch,P/'launch_limit_gate.py']
 save(P/'screen-jobs-seal.json',dict(schema='packet120.v4-brackets.v1',passed=True,device_executed=False,sources={str(p.relative_to(ROOT)):sha(p) for p in paths},request_count=12,tokens=128,order=list(ORDER),threshold_percent=.5,oracle='iq3-p49-split32-v1',separate_fresh_processes=True))

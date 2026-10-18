"""Matched compute/BCS brackets; fresh middle control is shared, records on A."""
import json
from build_engine import P,ROOT,sha,save,check_map
WRAPPER=P.parent/'screen/v4-lanes'
ORDER=('production','head-split-compute','production','head-split-bcs','production')
def view(label):
 assert label in set(ORDER)
 return P/'selections'/label
def jobs(lane):
 assert lane in ('A','B')
 identity=sha(view('head-split-bcs')/'screen-seal.json')[:12]
 return [dict(index=i,choice=c,lane=lane,mode='grid',out=f'p105-{identity}-{lane}-grid-{i}-{c}') for i,c in enumerate(ORDER)]
def output(job):return WRAPPER/'evidence'/job['out']
def verify():
 from bootstrap import install
 install();r=json.loads((P/'screen-jobs-seal.json').read_text());check_map(ROOT,r['sources']);assert r['order']==list(ORDER) and r['record_lane']=='A';return r
def seal_jobs():
 sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('screen_jobs.py','screen_job.py','compare.py','run_screen.py','bootstrap.py','worker.py','placement.py','placement-policy.json')}
 for label in set(ORDER):sources[str((view(label)/'screen-seal.json').relative_to(ROOT))]=sha(view(label)/'screen-seal.json')
 save(P/'screen-jobs-seal.json',dict(passed=True,device_executed=False,order=list(ORDER),sources=sources,record_lane='A',qualification='Each placement must beat its two fresh controls with 13/13 exact checks and identical acceptance. A independently confirms; no CPU or B-only record claim.'))

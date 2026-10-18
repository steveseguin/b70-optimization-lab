"""Four immutable selections, one candidate-only twelve-prompt smoke."""
import json
from build_engine import P,ROOT,sha,save,check_map
from bundle_selection import aliases,name
WRAPPER=P.parent/'screen/v4-lanes'
def view(label):return P/'selections'/(name(*aliases()[label])+'--placement-1')
def smoke_output():return WRAPPER/'evidence'/('p124-'+sha(view('both')/'screen-seal.json')[:12]+'-B-smoke12')
def verify():
 from bootstrap import install
 install();r=json.loads((P/'screen-jobs-seal.json').read_text());check_map(ROOT,r['sources']);return r

def seal_jobs():
 paths=[P/n for n in ('screen_jobs.py','smoke_job.py','smoke_screen.py','smoke_worker.py','smoke_validation.py','exec_limits.py','bootstrap.py','placement.py','placement-policy.json')]
 paths+=[view('both')/'screen-seal.json']
 save(P/'screen-jobs-seal.json',dict(passed=True,device_executed=False,sources={str(f.relative_to(ROOT)):sha(f) for f in paths},request_count=12,tokens=64,candidate_only=True))

ORDER=('control','candidate','control')
def output(job):return WRAPPER/'evidence'/job['out']
def jobs(*args,**kwargs):raise ValueError('use packet124 orchestration decision jobs')

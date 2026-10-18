"""Packet105b target-only diagnostic smoke; grids live in packet106b."""
import json
from build_engine import P,ROOT,sha,save,check_map
WRAPPER=P.parent/'screen/v4-lanes'
SMOKE_CHOICE='head-split-compute'
def view(label):
 assert label in ('production',SMOKE_CHOICE)
 return P/'selections'/label
def smoke_output():return WRAPPER/'evidence'/('p105b-'+sha(view(SMOKE_CHOICE)/'screen-seal.json')[:12]+'-B-smoke12')
def verify():
 from bootstrap import install
 install();r=json.loads((P/'screen-jobs-seal.json').read_text());check_map(ROOT,r['sources']);return r
def seal_jobs():
 paths=[P/n for n in ('screen_jobs.py','smoke_job.py','smoke_screen.py','smoke_worker.py','smoke_validation.py','device_gate.py','bootstrap.py','placement.py','placement-policy.json')]
 paths += [view(SMOKE_CHOICE)/'screen-seal.json',P/'evidence/microbench-build.json']
 save(P/'screen-jobs-seal.json',dict(passed=True,device_executed=False,sources={str(f.relative_to(ROOT)):sha(f) for f in paths},request_count=12,tokens=64,candidate_only=True))
from smoke_validation import require_smoke

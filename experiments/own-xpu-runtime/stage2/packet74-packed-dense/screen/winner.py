"""Preregistered exact winner, beating BOTH fresh controls; ties by fixed order."""
from jobs import jobs,HERE,CANDIDATES
from common import require
def choose(rows):
 require(len(rows)==5 and all(r['exact'] for r in rows),'five exact lane-A screens required')
 require(tuple(r['choice'] for r in rows)==('production',*CANDIDATES,'production'),'lane-A order differs')
 control=max(rows[0]['rate'],rows[-1]['rate'])
 candidates=rows[1:-1];best=max(candidates,key=lambda r:r['rate'])
 require(best['rate']>control,'no candidate beats both controls; lane B withheld')
 return dict(choice=best['choice'],rate=best['rate'],control=control,ratio=best['rate']/control)
def verify_lane_a():
 from compare import load
 result=choose([load(r,'A') for r in jobs(HERE/'jobs-A.txt','A')])
 print('lane-A exact winner: '+result['choice'],flush=True);return result

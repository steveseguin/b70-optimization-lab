"""Select only from six completed exact A screens, against the two-control mean."""
from common import require
from jobs import jobs,P,HERE,CANDIDATES
def choose(rows):
 from compare import baseline
 require(len(rows)==6 and all(r['exact'] for r in rows),'six exact lane-A screens required')
 require(tuple(r['choice'] for r in rows)==('production',*CANDIDATES,'production'),'lane-A grid differs')
 control=baseline(rows)
 arms=[r for r in rows if r['choice'] in CANDIDATES]
 # Stable preregistered tie order. Every arm is independent; combined uses B+HC.
 best=max(arms,key=lambda r:r['rate'])
 require(best['rate']>control,'no candidate beat lane-A control; lane B withheld')
 return dict(choice=best['choice'],rate=best['rate'],control=control,ratio=best['rate']/control)
def verify_lane_a():
 from compare import load
 return choose([load(r,'A') for r in jobs(HERE/'jobs-A.txt','A')])

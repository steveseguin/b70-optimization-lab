"""Fail closed before lane-B launch unless every lane-A screen is exact."""
from compare import load,baseline
from jobs import jobs,P,HERE
from common import require,read
def choose(rows):
 require(len(rows)==4 and all(r['exact'] for r in rows),'four exact lane-A screens required')
 control=baseline(rows)
 # Two aliases of exactly the same configuration: average both, never cherry
 # pick the faster alias. Canonical attention-out is the only independent arm.
 arms=[r for r in rows if r['choice']!='production']
 require({r['choice'] for r in arms}=={'attention-out','combined'},'missing candidate views')
 rate=sum(r['rate'] for r in arms)/len(arms)
 require(rate>control,'attention output did not beat lane-A control; lane B withheld')
 return dict(choice='attention-out',rate=rate,control=control,ratio=rate/control)
def verify_lane_a():
 a=P/'selections/attention-out';b=P/'selections/combined'
 require(read(a/'selection.json')==read(b/'selection.json'),'combined is no longer the same single mechanism')
 result=choose([load(r,'A') for r in jobs(HERE/'jobs-A-r2.txt','A')])
 print('lane-A exact winner verified: '+result['choice'],flush=True)
 return result

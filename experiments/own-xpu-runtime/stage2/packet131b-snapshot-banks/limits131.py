"""Actual intercepted rank launch limits, inherited unchanged and negative cap.

The positive CPU parent intentionally keeps inherited infinite RLIMIT_AS to
check the real launch boundary. No weights, native binaries or devices execute;
only small input snapshots and two intercepted argv are allocated.
"""
import json,resource,subprocess,sys
from build131 import P,ROOT,sha,save,limits

def main():
 limits();assert resource.getrlimit(resource.RLIMIT_AS)==(-1,-1)
 before={str(k):list(resource.getrlimit(k)) for k in sorted({getattr(resource,n) for n in dir(resource) if n.startswith('RLIMIT_')})}
 rows=[]
 for index in (-1,0):
  for flag in ('--limits-probe','--finite-negative'):
   r=subprocess.run([sys.executable,'-B',str(P/'arguments131.py'),flag,str(index)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
   (P/'evidence'/('limits'+flag+'-'+str(index)+'.log')).write_text(r.stdout+r.stderr)
   assert r.returncode==0,r.stdout+r.stderr
   row=json.loads(next(x.removeprefix('LIMITS_RESULT=') for x in r.stdout.splitlines() if x.startswith('LIMITS_RESULT=')))
   assert row['passed'];rows.append(row)
 positives=[r for r in rows if not r.get('negative_control')]
 assert len(positives)==2
 assert all(r['inherited_limits']==r['final_limits']==before and len(r['argv'])==len(r['actual_guard_observations'])==2 and r['limits_checked'] for r in positives)
 from arguments131 import sources
 bound=sources();bound[str((P/'limits131.py').relative_to(ROOT))]=sha(P/'limits131.py')
 save(P/'evidence/launch-limits.json',dict(passed=True,device_executed=False,cases=rows,sources=bound))
 print('Smoke and grid: both rank guards retain every inherited limit; finite AS negatives refused')
if __name__=='__main__':main()

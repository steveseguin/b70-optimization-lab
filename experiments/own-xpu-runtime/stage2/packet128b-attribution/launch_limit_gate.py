"""Actual intercepted rank launch limits, inherited unchanged and negative cap.

The positive CPU parent intentionally keeps inherited infinite RLIMIT_AS to
check the real launch boundary. No weights, native binaries or devices execute;
only small input snapshots and two intercepted argv are allocated.
"""
import json,resource,subprocess,sys
from build_engine import P,ROOT,sha,save,limits

def main():
 limits();assert resource.getrlimit(resource.RLIMIT_AS)==(-1,-1)
 before={str(k):list(resource.getrlimit(k)) for k in sorted({getattr(resource,n) for n in dir(resource) if n.startswith('RLIMIT_')})}
 rows=[]
 for flag in ('--limits-probe','--finite-negative'):
  r=subprocess.run([sys.executable,'-B',str(P/'argument_gate.py'),flag],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
  (P/'evidence'/('limits'+flag+'.log')).write_text(r.stdout+r.stderr)
  assert r.returncode==0,r.stdout+r.stderr
  row=json.loads(next(x.removeprefix('LIMITS_RESULT=') for x in r.stdout.splitlines() if x.startswith('LIMITS_RESULT=')))
  assert row['passed'];rows.append(row)
 assert rows[0]['inherited_limits']==rows[0]['final_limits']==before
 assert len(rows[0]['argv'])==2 and rows[0]['limits_checked']
 save(P/'evidence/launch-limits.json',dict(passed=True,device_executed=False,cases=rows,
  sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'launch_limit_gate.py',P/'argument_gate.py',P/'exec_limits.py',P/'worker.py')}))
 print('Both real rank exec boundaries retain all inherited limits; finite AS negative refused')
if __name__=='__main__':main()

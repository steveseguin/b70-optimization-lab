"""Both real worker launch boundaries preserve every inherited getrlimit."""
import json,subprocess,sys,resource
from p185_v5_build_engine import P,ROOT,sha,save

def main():
 assert resource.getrlimit(resource.RLIMIT_AS)==(-1,-1)
 rows=[]
 for index in range(5):
   for lane,mode in __import__('itertools').product(('A','B'),('--limits-probe','--finite-negative')):
    r=subprocess.run([sys.executable,'-B',str(P/'argument_gate.py'),mode,str(index),lane],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
    assert r.returncode==0,r.stderr
    row=json.loads(next(x.removeprefix('LIMITS_RESULT=') for x in r.stdout.splitlines() if x.startswith('LIMITS_RESULT=')))
    assert row['passed'];rows.append(row)
 save(P/'evidence/launch-limits.json',dict(passed=True,device_executed=False,rows=rows,sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'launch_limit_gate.py',P/'argument_gate.py',P/'p185_v5_exec_limits.py',P/'tp2_worker.py']}))
 print('Packet185: real rank exec boundaries unchanged for five view rows x two lanes; capped negatives refused')
if __name__=='__main__':main()

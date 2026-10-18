"""Plan all B alternatives on CPU; execute only the exact A winner once."""
import argparse,subprocess,sys,json
from pathlib import Path
from jobs import HERE,CANDIDATES
from common import require
from quick_seal import verify
from conditions import cpu_gate,lane_gate

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--lane',choices=['B'],default='B');ap.add_argument('--plan',action='store_true');ap.add_argument('--authorized-device-window',action='store_true');ap.add_argument('--fault-review',type=Path);a=ap.parse_args()
 cpu_gate() if a.plan else lane_gate('B');verify()
 if a.plan:choices=CANDIDATES
 else:
  from winner import verify_lane_a
  require(a.authorized_device_window and a.fault_review,'coordinator authorization required');choices=[verify_lane_a()['choice']]
 plans=[]
 for choice in choices:
  cmd=[sys.executable,'-B',str(HERE/'run.py'),'--lane','B','--jobs',str(HERE/f'jobs-B-{choice}.txt')]
  if a.plan:
   r=subprocess.run(cmd+['--plan'],capture_output=True,text=True,check=True,stdin=subprocess.DEVNULL);plans.append(json.loads(r.stdout))
  else:subprocess.run(cmd+['--authorized-device-window','--fault-review',str(a.fault_review)],check=True,stdin=subprocess.DEVNULL)
 if a.plan:print(json.dumps(dict(device_executed=False,alternatives=plans),indent=2))
if __name__=='__main__':main()

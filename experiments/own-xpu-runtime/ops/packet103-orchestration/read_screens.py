"""Isolated source adapters, both directions, CPU read-only."""
import json,subprocess,sys,resource
from pathlib import Path
O=Path(__file__).resolve().parent
ROOT=O.parents[3]
PACKETS=('91','93','92','94','95','90','100','101')
def require_current(screens):
 import hashlib
 for number,source in screens.items():
  for name,expected in source.get('observed_windows',{}).items():
   path=ROOT/name
   actual=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
   if actual!=expected:raise ValueError('source '+number+' results changed during decision; re-read required: '+name)
def collect():
 result={}
 for n in PACKETS:
  r=subprocess.run([sys.executable,'-B',str(O/'source_adapter.py'),n],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=300)
  result[n]=json.loads(r.stdout) if r.returncode==0 else dict(status='failed',reason=r.stderr,receipts={},sources={})
  if n in ('92','94','95'):
   import hashlib
   path=O/'closed-source-snapshot.json'
   closure=json.loads(path.read_text())['packets'][n]
   assert closure['status']=='CLOSED'
   result[n]=dict(status='excluded',reason=closure['reason'],closed_source=True,live_read=result[n],sources={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()},receipts={})
 require_current(result)
 return result
if __name__=='__main__':
 # CPU-only CLI: imported readers must preserve the device launcher's limits.
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 print(json.dumps(collect()))

def reject_later_record_lane_losses(config):
 """A frozen first-lane win cannot hide a later completed A confirmation."""
 selected={}
 for number in config['confirmed_levers']:
  run=subprocess.run([sys.executable,'-B',str(O/'source_adapter.py'),number],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=300)
  if run.returncode:raise ValueError('current source veto read failed: '+number+': '+run.stderr)
  row=json.loads(run.stdout);selected[number]=row
  if row.get('record_lane_veto'):raise ValueError('later record-lane A veto for source '+number+': '+row['record_lane_veto']['reason'])
  if row['status']=='failed':raise ValueError('current source evidence invalid: '+number+': '+row.get('reason',''))
 require_current(selected)
 return selected

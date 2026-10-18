"""Isolated source adapters, both directions, CPU read-only."""
import json,subprocess,sys
from pathlib import Path
O=Path(__file__).resolve().parent
ROOT=O.parents[4]
PACKETS=('91','93','92','94','95','90')
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
  r=subprocess.run([sys.executable,'-B',str(O/'source_adapter_review15.py'),n],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=300)
  result[n]=json.loads(r.stdout) if r.returncode==0 else dict(status='failed',reason=r.stderr,receipts={},sources={})
 require_current(result)
 return result
if __name__=='__main__':print(json.dumps(collect()))

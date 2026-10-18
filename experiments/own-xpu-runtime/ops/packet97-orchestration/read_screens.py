"""Isolated source adapters, both directions, CPU read-only."""
import json,subprocess,sys
from pathlib import Path
O=Path(__file__).resolve().parent
PACKETS=('91','93','92','94','95','90')
def collect():
 result={}
 for n in PACKETS:
  r=subprocess.run([sys.executable,'-B',str(O/'source_adapter.py'),n],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=300)
  result[n]=json.loads(r.stdout) if r.returncode==0 else dict(status='failed',reason=r.stderr,receipts={},sources={})
 return result
if __name__=='__main__':print(json.dumps(collect()))

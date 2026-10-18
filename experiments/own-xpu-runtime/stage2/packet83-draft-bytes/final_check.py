"""Verify every seal and both complete-grid/other-lane-confirmation plans."""
import json,subprocess,sys
from build_engine import P,ROOT,B,sha,save,limits
from screen_jobs import verify
from bundle_selection import views
from common import read,require,verify_map

def main():
 limits();verify();plans=[]
 for name in views():
  v=P/'compat/packet64-record-bundle/selections'/name;s=read(v/'screen-seal.json');verify_map(ROOT,s['sources'])
  for key in ('artifacts','gates','fixture_files'):verify_map(v,s[key])
 for lane in ('A','B'):
  for mode in ('grid','confirm'):
   cmd=[sys.executable,'-B',str(P/'run_screens.py'),'--lane',lane,'--mode',mode,'--plan']
   if mode=='confirm':cmd+=['--source-lane','B' if lane=='A' else 'A']
   r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=300);plans.append(json.loads(r.stdout))
 size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file());require(size<1_000_000_000,'build exceeds 1 GB')
 save(P/'evidence/final-check.json',dict(passed=True,device_executed=False,plans=plans,build_logical_bytes=size,sealed_views=list(views())))
 print('4 seals; both full grids and all possible confirmations PASS; build bytes',size)
if __name__=='__main__':main()

"""Verify immutable candidate inputs and actual shared placement admission."""
import json,subprocess,sys
from build_engine import P,ROOT,B,sha,save,limits
from screen_jobs import verify,jobs,command,WRAPPER,DIRECTIONS,GRIDS
from bundle_selection import views
from common import read,require,verify_map
def main():
 limits();verify();plans=[]
 for name in views():
  v=P/'compat/packet64-record-bundle/selections'/name;s=read(v/'screen-seal.json');verify_map(ROOT,s['sources'])
  for key in ('artifacts','gates','fixture_files'):verify_map(v,s[key])
 for grid in GRIDS:
  for direction in DIRECTIONS:
   for lane in ('A','B'):
    r=subprocess.run([sys.executable,'-B',str(P/'run_screens.py'),'--lane',lane,'--direction',direction,'--grid',grid,'--plan'],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=300)
    plans.append(json.loads(r.stdout))
 size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file());require(size<1_000_000_000,'build exceeds 1 GB')
 save(P/'evidence/final-check.json',dict(passed=True,device_executed=False,plans=plans,build_logical_bytes=size,sealed_views=list(views())))
 print(len(views()),'seals;',len(plans),'direction/lane plans PASS; build bytes',size)
if __name__=='__main__':main()

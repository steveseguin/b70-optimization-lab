"""Verify all CPU evidence and actual v4 plans; no device execution."""
import json,subprocess,sys
from types import SimpleNamespace
from build_engine import P,ROOT,B,sha,save,limits
from screen_jobs import verify,WRAPPER
from bootstrap import install
from common import sealed,read,require

def main():
 limits();install();verify();plans=[]
 for view in sorted((P/'selections').iterdir()):
  placement=read(view/'placement-audit.json')['placement']
  identity=sealed(SimpleNamespace(lineage=view,seal=view/'screen-seal.json',binary=None,dispatch=None,profile='tp2',timing='token',placement=placement))
  for lane in ('A','B'):
   cmd=[sys.executable,'-B',str(P/'run_screen.py'),'--profile','tp2','--lane',lane,'--placement',placement,'--lineage',str(view),'--seal',str(view/'screen-seal.json'),'--output',str(WRAPPER/'evidence'/('p79-plan-'+lane+'-'+view.name)),'--plan']
   r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
   require(r.returncode==0,r.stderr);plan=json.loads(r.stdout);require(plan['supported'] and not plan['device_executed'],'plan refused or executed')
   require(plan['identity']['placement']==identity['placement'],'placement differs in wrapper');plans.append(plan)
 for name,count in [('python-local.log',6),('python-shared.log',69)]:
  log=(P/'evidence'/name).read_text();require(f'Ran {count} tests' in log and log.rstrip().endswith('OK'),'Python tests failed')
 require(read(P/'evidence/queue-plans.json')['passed'],'queue plan failed')
 size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file());require(size<1200000000,'build exceeds1.2 GB')
 sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('final_check.py','report.py','queue_plan.py','screen-jobs-seal.json','evidence/python-local.log','evidence/python-shared.log','evidence/queue-plans.json')}
 save(P/'evidence/final-check.json',dict(passed=True,device_executed=False,plans=plans,python_tests=75,build_logical_bytes=size,sources=sources))
 print('six views / twelve real v4 plans / 75 Python tests / temporary queues PASS; build bytes',size)
if __name__=='__main__':main()

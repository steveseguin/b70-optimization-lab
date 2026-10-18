"""Seal copied quick lane protocol after mocked execution and plan admission."""
import json,subprocess,sys
from pathlib import Path
from common import HERE,ROOT,sha,save,read
from conditions import cpu_gate

def main():
 cpu_gate();P=HERE.parents[1]
 assert not (HERE/'wrapper-seal.json').exists(),'first issuance only'
 for f in HERE.glob('*.py'):compile(f.read_text(),str(f),'exec')
 with (HERE/'cpu-tests.log').open('w') as log:
  subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(HERE),'-p','test_*.py','-v'],check=True,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
 parent=read(P/'screen/attr/wrapper-seal.json')
 sources=dict(parent['sources'])
 for name,digest in sources.items():assert sha(ROOT/name)==digest,name
 for f in [*HERE.glob('*.py'),*HERE.glob('jobs-*.txt'),HERE/'placements.json']:
  sources[str(f.relative_to(ROOT))]=sha(f)
 save(HERE/'wrapper-seal.json',dict(passed=True,device_executed=False,cpu_model_executed=False,sources=sources,
    tests_sha256=sha(HERE/'cpu-tests.log'),release_before_reporting=True))
 plans={}
 for lane in ('A','B'):
  cmd=[sys.executable,'-B',str(HERE/'run.py'),'--lane',lane,'--jobs',str(HERE/('jobs-'+lane+'-r3.txt')),'--plan']
  with (HERE/('plans-'+lane+'.json')).open('w') as log:subprocess.run(cmd,check=True,stdin=subprocess.DEVNULL,stdout=log)
  rows=read(HERE/('plans-'+lane+'.json'));assert len(rows['plans'])==8 and all(r['supported'] for r in rows['plans']);plans[lane]=sha(HERE/('plans-'+lane+'.json'))
 save(HERE/'validation.json',dict(passed=True,device_executed=False,cpu_model_executed=False,wrapper_seal_sha256=sha(HERE/'wrapper-seal.json'),plans=plans,tests=18,lanes=['A','B'],fresh_controls='first and last on each lane',speed='unmeasured',quality='pending packet49 device screen'))
 print('PASS: 16 screen plans, 18 CPU protocol tests; no GPU')
if __name__=='__main__':main()

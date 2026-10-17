"""CPU mock tests and immutable private wrapper closure; no devices/models."""
import argparse,subprocess,sys
from pathlib import Path
from common import HERE,ROOT,P56,P58,D,S,SUPPORT,W,M,DISPATCH,read,save,sha,require,verify_map
from conditions import cpu_gate
import fault_review
ARTIFACTS=HERE/'placement-validation'
def sources():
 paths=set(HERE.glob('*.py'))|set(HERE.glob('jobs-*.txt'))
 paths.update(HERE/n for n in ('placements.json','parent-wrapper.json'))
 paths.update(P56/n for n in ('memory-plan.json','pipeline.py','suite.py','storage.py','suite_metrics.py','memory_gate.py'))
 paths.add(P58/'oracle-binding.json');paths.add(fault_review.DRIVER)
 paths.update(Path(m.__file__) for m in (D,D.CHECK,D.METRICS,S,SUPPORT,W,M,DISPATCH))
 return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def verify():
 r=read(ARTIFACTS/'wrapper-seal.json');require(r['passed'] and not r['device_executed'],'wrapper gate')
 require(r['sources']==sources(),'wrapper source closure changed')
 verify_map(ARTIFACTS,r['artifacts']);return r
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');a=ap.parse_args();cpu_gate()
 if a.verify:verify();return
 require(not (ARTIFACTS/'wrapper-seal.json').exists(),'never overwrite seal');ARTIFACTS.mkdir(exist_ok=True)
 for p in HERE.glob('*.py'):compile(p.read_text(),str(p),'exec')
 before=sources()
 cmd=[sys.executable,'-B','-m','unittest','discover','-s',str(HERE),'-p','test_*.py','-v']
 with (ARTIFACTS/'tests.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,check=True)
 require(before==sources(),'sources changed during mock checks')
 save(ARTIFACTS/'wrapper-seal.json',dict(passed=True,device_executed=False,cpu_model_executed=False,sources=before,artifacts={'tests.log':sha(ARTIFACTS/'tests.log')},release_before_reporting=True,command=cmd))
 verify();print('private v4 wrapper mock tests and seal PASS')
if __name__=='__main__':main()

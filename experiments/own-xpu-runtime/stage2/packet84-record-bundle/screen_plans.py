"""Import the real shared worker and plan all composed views on both lanes."""
import json,subprocess,sys
from build_engine import P,ROOT,B,sha,save,limits
from bundle_selection import PLACEMENTS,views

def main():
    limits();rows=[]
    # The same closed worker environment used by the shared screen launcher.
    program="import sys,runpy;sys.path.insert(0,sys.argv[1]);from bootstrap import install,WRAPPER;install();runpy.run_path(str(WRAPPER/'tp2_worker.py'),run_name='cpu_worker_import');from lane_admission import admission_scope;assert admission_scope('A','screen')=='lane-A';assert admission_scope('A','WS128')=='whole-host';print('worker imports and real admission PASS')"
    env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2','PYTHONDONTWRITEBYTECODE':'1'}
    r=subprocess.run([sys.executable,'-B','-c',program,str(P)],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=120)
    save(P/'evidence/worker-import.json',dict(passed=True,device_executed=False,stdout=r.stdout,environment=env))
    for name in views():
        for placement in PLACEMENTS:
            view=P/'selections'/(name+'--placement-'+placement)
            for lane in ('A','B'):
                cmd=[sys.executable,'-B',str(P/'run_screen.py'),'--profile','tp2','--lane',lane,'--placement',placement,'--lineage',str(view),'--seal',str(view/'screen-seal.json'),'--output',str(P.parent/'screen/v4-lanes/evidence'/('p84-plan-'+lane+'-'+view.name)),'--plan']
                r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
                assert r.returncode==0,r.stderr
                plan=json.loads(r.stdout);assert plan['supported'] and not plan['device_executed']
                assert plan['identity']['placement']['name']==placement
                rows.append(dict(view=name,placement=placement,lane=lane,passed=True,plan=plan))
            print(name,placement,'shared A/B plans PASS',flush=True)
    save(P/'evidence/screen-plans.json',dict(passed=True,device_executed=False,runs=rows,sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('screen_plans.py','worker.py','bootstrap.py','placement.py','run_screen.py','dependency-pins.json','placement-policy.json')}))
if __name__=='__main__':main()

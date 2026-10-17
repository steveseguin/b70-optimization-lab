"""Run all real window plans for all compositions; no device execution."""
import json,subprocess,sys
from build_engine import P,ROOT,limits,save,sha
from bundle_selection import views,PLACEMENTS,KEYS
from storage import B,REGISTERED_CHAIN
from lane_admission import admission_scope
import queue_runner as q

def reseal(choice,placement):
    subprocess.run([sys.executable,'-B',str(P/'fast_reseal.py'),
                    *[s for k,v in zip(KEYS,choice) for s in ('--'+k,v)],'--placement',placement],
                   stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,check=True)

def main():
    limits();rows=[]
    before=json.loads((P/'bundle-selection.json').read_text())
    admission_scope('A','screen')
    try:
        for name,choice in views().items():
            for placement in PLACEMENTS:
                reseal(choice,placement)
                commands=q.commands(q.admitted_output(B/REGISTERED_CHAIN))
                for window,argv in commands.items():
                    admission_scope('A',window)
                    result=subprocess.run(argv+['--plan'],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
                    rows.append(dict(view=name,placement=placement,window=window,passed=True,output=result.stdout))
                print(name+' '+placement+': 11 real window plans passed',flush=True)
    finally:
        reseal(tuple(before[k] for k in KEYS),before['placement'])
    save(P/'evidence/all-view-plans.json',dict(passed=True,device_executed=False,
         screen_lane_a_admitted=True,source_sha256=sha(P/'all_view_plans.py'),runs=rows))
if __name__=='__main__':main()

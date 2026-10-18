"""Preregistered grid; no retries; shared v4 owns every device lifecycle."""
import argparse,json,signal,subprocess,time
from screen_jobs import P,WRAPPER,verify,jobs,command,winner
from bundle_selection import VIEWS
from common import require
from conditions import cpu_gate,lane_gate
import screen,fault_review

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--lane',choices=('A','B'),required=True)
    ap.add_argument('--plan',action='store_true')
    ap.add_argument('--mode',choices=('grid','confirm'),required=True)
    ap.add_argument('--source-lane',choices=('A','B'))
    ap.add_argument('--fault-review')
    ap.add_argument('--authorized-device-window',action='store_true')
    a=ap.parse_args();cpu_gate() if a.plan else lane_gate(a.lane)
    verify()
    require(a.mode=='grid' and a.source_lane is None or a.mode=='confirm' and a.source_lane in ('A','B') and a.source_lane!=a.lane,'confirmation must use the other lane grid')
    rows=jobs(a.lane,winner(a.source_lane)['choice'] if a.mode=='confirm' and not a.plan else None,a.mode)
    require(all(not (WRAPPER/'evidence'/r['out']).exists() for r in rows),'all screen outputs must be fresh')
    if a.plan:
        plans=[]
        for row in (rows if a.mode=="grid" else [r for choice in VIEWS[1:] for r in jobs(a.lane,choice,"confirm")]):
            r=subprocess.run(command(row,a.lane,plan=True),stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
            plans.append(json.loads(r.stdout))
        print(json.dumps(dict(passed=True,device_executed=False,lane=a.lane,plans=plans,
              gap_seconds=90,retries=0,mode=a.mode,source_lane=a.source_lane,confirmation_gate='exact improving other-lane winner; checked at execution'),indent=2));return 0
    require(a.authorized_device_window and a.fault_review,'coordinator authorization and review required')
    group=P.__class__('/proc/self/cgroup').read_text();screen.unit_gate(group);screen.unit_conditions(group)
    if a.mode=='confirm':require(winner(a.source_lane)['choice']==rows[1]['choice'],'confirmation winner changed')
    stopped=[];child=[]
    def stop(sig,frame):
        stopped.append(sig)
        if child and child[0].poll() is None:child[0].send_signal(signal.SIGTERM)
    def check():
        require(not stopped and not (P/'evidence/STOP').exists(),'campaign stopped')
        fault_review.validate(a.fault_review)
    old={sig:signal.signal(sig,stop) for sig in (signal.SIGINT,signal.SIGTERM)}
    try:
        for index,row in enumerate(rows):
            check();print('start '+row['out'],flush=True)
            child[:]=[subprocess.Popen(command(row,a.lane,a.fault_review),stdin=subprocess.DEVNULL)]
            rc=child[0].wait();child.clear()
            require(rc==0,'screen failed; no retry or next screen: '+row['out']);check()
            from compare import load
            result=load(row,a.lane);require(result['exact'],'screen target oracle differs')
            print(json.dumps(dict(screen=row['out'],**result)),flush=True)
            if index<len(rows)-1:
                end=time.monotonic()+90
                while time.monotonic()<end:check();time.sleep(min(1,max(0,end-time.monotonic())))
    finally:
        for sig,handler in old.items():signal.signal(sig,handler)
    return 0
if __name__=='__main__':raise SystemExit(main())

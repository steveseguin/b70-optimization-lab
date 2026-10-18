"""Fresh resident-screen evidence reader; never a saved-boolean authorization."""
import json,shlex
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def verify():
    import screen_window as W
    import screen_runner as Q
    import screen_driver as D
    seal=W.build_gate();out=Q.ROOT/'resident'
    queue=D.read(out/'queue.json')
    W.require(queue['passed'] is True and queue['completed']==list(Q.ORDER),'resident bracket incomplete')
    boots=set();rows={};identity=None
    for name in Q.ORDER:
        row=Q.verify_success(name,out,0,0);boots.add(row['boot_id'])
        W.require(row['build_receipt_sha256']==W.sha(P/'build-receipt.json') and row['artifacts_sha256']==seal['artifacts'],'screen/chain build identity differs')
        if identity is None:identity=row
        W.prerequisite(out/name/'window.json',row['window'],identity)
        rows[name]=row
    W.require(len(boots)==1,'mixed screen boots')
    miss=W.selected_miss_path([out/n/'window.json' for n in ('K1a','K1b')],identity)
    W.require(rows['WSCREEN']['miss_path']==miss,'screen miss path differs from fresh K1 bytes/timings')
    budget=W.M.window_plan('WSCREEN');row=rows['WSCREEN']
    admission=W.M.admit(row['memory_admission']['snapshot'],budget)
    W.require(admission==row['memory_admission'],'screen memory admission changed')
    proof=W.postload_observation(out/'WSCREEN',budget,admission)
    W.require(proof==row['postload_memory'],'screen postload proof changed')
    summary=D.summarize_bracket(out/'WSCREEN/run','resident',D.oracle_inputs())
    W.require(summary['candidate_beats_all_controls'],'resident candidate must beat both controls by 0.5% within 3% drift')
    W.require(summary['views'][1]['lookup_faults']['major']==0,'resident preparation major faults remain')
    return dict(passed=True,boot_id=boots.pop(),screen_summary=summary,device_chain_still_required=True)
def chain_command():
    args=['systemd-run','--user','--unit=packet58-onecard-58t-a','--property=Restart=no','--property=SendSIGKILL=no','--property=TimeoutStopSec=infinity','--property=Nice=0','--working-directory='+str(ROOT),'/usr/bin/taskset','-c','0-3,16-19','/usr/bin/env','-i','PATH=/usr/bin:/bin','OMP_NUM_THREADS=2']
    return shlex.join(args)+' LD_LIBRARY_PATH="$LD_LIBRARY_PATH" '+shlex.join(['/usr/bin/python3','-B',str(P/'queue_runner.py'),'--authorized-device-window','--view','down-tile16','--output-root',str(P/'evidence/card0-58t-a'),'--fault-review',str(P/'evidence/fault-review-58t.json')])+' < /dev/null'
if __name__=='__main__':
    try:print(json.dumps(verify(),indent=2))
    except (ValueError,OSError) as e:print('NOT READY: '+str(e));raise SystemExit(1)

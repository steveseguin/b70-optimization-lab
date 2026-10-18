#!/usr/bin/env python3
"""One model lifetime per arm, with two bounded K1 fixtures before the load."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import window as W
import batch_gate as BATCH
from views import digest, bracket
from exec_limits import check as check_exec_limits

P = Path(__file__).resolve().parent
ORDER = ('K1a', 'K1b', 'WSCREEN')
GAP_SECONDS = 90
STAGES = (('attrib','attrib'),)
ROOT = P / 'evidence/card0-attribution-b'


def commands(output, card, review, library, view='attrib'):
    W.require(card == 0, 'card 0 and lane A required')
    result = {}
    for name in ORDER:
        mode = 'K1' if name.startswith('K1') else name
        cmd = ([] if mode == 'WSCREEN' else ['/usr/bin/nice', '-n', '19'])
        cmd += ['/usr/bin/taskset', '-c', '0-3,16-19' if mode == 'WSCREEN' else '8-15,24-31',
                '/usr/bin/env', '-i', 'PATH=/usr/bin:/bin', 'OMP_NUM_THREADS=2', 'LD_LIBRARY_PATH='+library,
                '/usr/bin/python3', '-B', str(P/'window.py'), '--authorized-device-window',
                '--window', mode, '--card', '0', '--output', str(output/name),
                '--faults-reviewed-through', review, '--view', view]
        if mode == 'WSCREEN':
            for k1 in ('K1a', 'K1b'):
                cmd += ['--k1', str(output/k1/'window.json')]
        result[name] = cmd
    return result


def verify_success(name, output, card, rc):
    W.require(rc == 0, name+' failed; no retry')
    row = json.loads((output/name/'window.json').read_text())
    expected = dict(window='K1' if name.startswith('K1') else name, passed=True,
                    device_executed=True, child_still_running=False, gpu_count=1,
                    card=card, context=4096, qualifying=False, stop_reasons=[])
    W.require(all(type(row.get(k)) is type(v) and row[k] == v for k,v in expected.items()), 'window receipt incomplete')
    W.A.verify(row)
    return row


def plan(output, view):
    W.build_gate()
    import suite_driver as D
    manifest = D.oracle_inputs()
    W.require(len(manifest['prompts']) == 12, 'complete 12-prompt suite required')
    return dict(schema='packet58y.plan.v1', device_executed=False, view=view,
        selection_sha256=digest(view), card=0, lane='A', scope='whole-host',
        model_lifetimes=1, k1_fixture_launches=2, windows=list(ORDER),
        planned_arm_seconds=[600,900], planned_bracket_seconds=[600,900], watchdog_seconds=7200, view_order=bracket(view), bracket_model_seconds=600,
        internal_gap_seconds=90, inter_arm_gap_seconds=90,
        host_required_available_bytes=W.M.window_plan('WSCREEN')['host_required_available_bytes'],
        host_reserve_bytes=W.M.HOST_RESERVE,
        pinned_expert_bytes=W.M.plan()['census']['pinned_expert_bytes'],
        host_peak_bound_bytes=W.M.window_plan('WSCREEN')['host_required_available_bytes']-W.M.HOST_RESERVE,
        request_count=12, prompts_per_view=12, requested_max_new=64 if view=='smoke' else 128, oracle='packet49-integrate',
        timing_claim_eligible=False, submission_eligible=False, output=str(output))


def verify_smoke():
    import suite_driver as D
    root=ROOT/'smoke'
    receipt=verify_success('WSCREEN',root,0,0)
    summary=D.summarize_bracket(root/'WSCREEN/run','smoke',D.oracle_inputs())
    W.require(summary.get('smoke_passed') is True,'first async device smoke required')
    W.require(receipt['build_receipt_sha256']==W.sha(P/'build-receipt.json'),'smoke build differs')
    return summary


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arm', choices=[s[0] for s in STAGES], required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--fault-review', type=Path)
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--authorized-device-window', action='store_true')
    ap.add_argument('--library-path', required=True)
    args=ap.parse_args(argv)
    recorded=json.loads((P/'library-path.json').read_text())['LD_LIBRARY_PATH']
    W.require(args.library_path==recorded,'recorded oneAPI library path required')
    view=dict(STAGES)[args.arm]; output=args.output.resolve()
    W.require(output == ROOT/args.arm and not output.exists(), 'fixed fresh arm output required')
    metadata=plan(output,view)
    if args.plan:
        print(json.dumps(metadata,indent=2)); return 0
    if args.arm=='overlap':
        verify_smoke()
    W.require(args.authorized_device_window and args.fault_review, 'coordinator authorization and fresh fault review required')
    W.user_unit_gate(Path('/proc/self/cgroup').read_text())
    W.require(os.getpriority(os.PRIO_PROCESS,0)==0 and set(os.sched_getaffinity(0))=={0,1,2,3,16,17,18,19}, 'nice0 lane-A timing placement required')
    W.closed_environment()
    import fault_review as F
    reviewed, _, _, _ = F.validate(args.fault_review)
    boundary = F.window_boundary(reviewed)
    batch=BATCH.verify()
    cmds=commands(output,0,boundary,args.library_path,view)
    W.storage(output,sum(W.WRITES['K1' if n.startswith('K1') else n] for n in ORDER))
    output.mkdir(parents=True)
    state=dict(schema='packet58y.arm.v1', passed=False, device_executed=False,
               view=view, arm=args.arm, commands=cmds, completed=[], plan=metadata,batch_admission=batch,
               fault_review_sha256=W.sha(args.fault_review),
               faults_reviewed_through=boundary,
               reviewed_capture_through_us=reviewed['through_us'],
               journal_overlap_us=2_000_000)
    stopped=[];child=None
    def save(): W.save(output/'queue.json',state)
    def stop(sig,frame):
        stopped.append(sig)
        if child is not None and child.poll() is None: child.send_signal(signal.SIGTERM)
    handlers={s:signal.signal(s,stop) for s in (signal.SIGINT,signal.SIGTERM)}
    try:
        save(); _,cursor=W.S.journal()
        for i,name in enumerate(ORDER):
            BATCH.recheck(batch)
            W.require(not stopped and not (output/'STOP').exists() and not (ROOT/'STOP').exists(), 'screen stopped')
            fresh,cursor=W.S.journal(cursor)
            W.require(not W.S.FAULT.search(fresh),'new GPU fault; no launch')
            with (output/(name+'.log')).open('x') as log:
                check_exec_limits()
                child=subprocess.Popen(cmds[name],cwd=W.REPO,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
                state.update(running=name,device_executed=True);save();rc=child.wait()
            verify_success(name,output,0,rc)
            state['completed'].append(name);state['running']=None;save()
            if i+1<len(ORDER):
                end=time.monotonic()+GAP_SECONDS
                while time.monotonic()<end:
                    BATCH.recheck(batch)
                    W.require(not stopped and not (output/'STOP').exists() and not (ROOT/'STOP').exists(),'stopped during drain gap')
                    fresh,cursor=W.S.journal(cursor)
                    W.require(not W.S.FAULT.search(fresh),'new GPU fault during gap')
                    time.sleep(min(1,max(0,end-time.monotonic())))
        BATCH.recheck(batch)
        state['passed']=True;save()
        decision=json.loads((output/'WSCREEN/run/summary.json').read_text())
        state['qualifies_for_fresh_screen']=decision['candidate_beats_all_controls'];save()
        return 0
    except Exception as error:
        state.update(passed=False,error=str(error),child_still_running=child is not None and child.poll() is None)
        save();return 75 if state['child_still_running'] else 1
    finally:
        for sig,handler in handlers.items(): signal.signal(sig,handler)

if __name__=='__main__':
    raise SystemExit(main())

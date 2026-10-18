#!/usr/bin/env python3
"""Packet58 serial coordinator queue; --plan only prints commands, never launches."""
import exec_limits
import argparse
import fcntl
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import time
import window as W
from views import VIEWS

P = Path(__file__).resolve().parent
ORDER = ('K1a', 'K1b', 'KD', 'W2m', 'WS', 'WS128x', 'WS128')
GAP_SECONDS = 90


def commands(output, card, review, library, view="down-tile16"):
    W.require(card == 0, 'packet58w requires card 0 and lane A')
    result = {}
    for index, name in enumerate(ORDER):
        mode = 'K1' if name.startswith('K1') else name
        cmd = ([] if mode.startswith('W') else ['/usr/bin/nice', '-n', '19']) + ['/usr/bin/taskset', '-c', '0-3,16-19' if mode.startswith('W') else '8-15,24-31',
               '/usr/bin/env', '-i', 'PATH=/usr/bin:/bin', 'OMP_NUM_THREADS=2', 'LD_LIBRARY_PATH='+library,
               '/usr/bin/python3', '-B', str(P/'window.py'), '--authorized-device-window',
               '--window', mode, '--card', str(card), '--output', str(output/name),
               '--faults-reviewed-through', review, '--view', view]
        if name not in ('K1a', 'K1b'):
            cmd += ['--previous', str(output/ORDER[index-1]/'window.json')]
            for k1 in ('K1a', 'K1b'):
                cmd += ['--k1', str(output/k1/'window.json')]
        result[name] = cmd
    return result


def verify_success(name, output, card, rc):
    W.require(rc == 0, name+' failed; no retry')
    row = json.loads((output/name/'window.json').read_text())
    expected = dict(window='K1' if name.startswith('K1') else name, passed=True,
                    device_executed=True, child_still_running=False, gpu_count=1, card=card, context=4096)
    W.require(all(type(row.get(k)) is type(v) and row[k] == v for k,v in expected.items()), 'window receipt incomplete')
    W.A.verify(row)
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--card', type=int, choices=(0,), default=0)
    parser.add_argument('--faults-reviewed-through', help='CPU plan fixture only; launch requires --fault-review')
    parser.add_argument('--fault-review', type=Path)
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--view', choices=VIEWS, default='down-tile16')
    parser.add_argument('--authorized-device-window', action='store_true')
    args = parser.parse_args(argv)
    output = args.output_root.resolve()
    W.require(output.is_relative_to((P/'evidence').resolve()), 'queue output must be inside packet58/evidence')
    review = args.faults_reviewed_through or '2026-01-01T00:00:00Z'
    review, _ = W.S.fault_review(review, time.time_ns()//1000)
    cmds = commands(output, args.card, review, os.environ.get('LD_LIBRARY_PATH',''),args.view)
    if args.plan:
        W.build_gate()  # Planning must reject a missing/stale post-load CPU gate.
        for name in ORDER:
            budget = W.M.window_plan(name)
            print('# '+name+': '+W.A.window_scope(name)+', MemAvailable >= '+str(budget['host_required_available_bytes'])
                  +' bytes; 8 GiB live reserve; gap '+str(GAP_SECONDS)+' s')
        for name, cmd in cmds.items():
            print(name+': '+shlex.join(cmd))
        return 0
    W.require(args.authorized_device_window, 'coordinator authorization required')
    W.user_unit_gate(Path('/proc/self/cgroup').read_text())
    W.require(os.getpriority(os.PRIO_PROCESS,0)==0, 'coordinator must start at nice 0 for timing; never raise priority in a child')
    W.require(set(os.sched_getaffinity(0)) == set(range(4)) | set(range(16,20)), 'coordinator must use lane-A cores 0-3,16-19')
    W.closed_environment()
    W.build_gate()
    W.require(output == P/'evidence/card0-58w-a' and args.view == 'down-tile16', 'fixed fresh tile16-only chain required')
    W.require(args.fault_review and not args.faults_reviewed_through, 'validated fault-review capture required for launch')
    import verify_ready as R
    import fault_review as F
    readiness = R.verify()  # Re-read the 58v smoke and all five bracket views, never trust ready.json.
    reviewed, _, _, _ = F.validate(args.fault_review)
    W.require(readiness['boot_id'] == reviewed['boot_id'], 'screen/review boot differs')
    review = F.window_boundary(reviewed)
    cmds = commands(output, args.card, review, os.environ.get('LD_LIBRARY_PATH',''), args.view)
    W.require(not output.exists(), 'fresh queue output required; no automatic retry')
    W.storage(output, sum(W.WRITES['K1' if n.startswith('K1') else n] for n in ORDER))
    output.mkdir(parents=True)
    stopped, handlers, child = [], {}, None
    state = dict(schema='own-runtime.packet58.queue.v1', passed=False, card=args.card, view=args.view, completed=[], commands=cmds,
                 readiness=readiness, fault_review_sha256=W.sha(args.fault_review),
                 reviewed_capture_through_us=reviewed['through_us'], faults_reviewed_through=review,
                 journal_overlap_us=2_000_000)
    def persist():
        W.save(output/'queue.json', state)
    def stop(signum, frame):
        stopped.append('coordinator stop '+str(signum))
        if child is not None and child.poll() is None:
            child.send_signal(signal.SIGTERM)  # window forwards one cooperative stop to its owned child
    handlers = {sig:signal.signal(sig,stop) for sig in (signal.SIGINT,signal.SIGTERM)}
    persist()
    try:
        with (P/'queue.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            _, cursor = W.S.journal()
            for name in ORDER:
                W.require(not stopped and not (output/'STOP').exists(), 'queue stopped before launch')
                fresh,cursor=W.S.journal(cursor)
                W.require(not W.S.FAULT.search(fresh),'new GPU fault before window; no launch')
                state['running']=name
                persist()
                with (output/(name+'.log')).open('x') as log:
                    state['exec_limits'] = exec_limits.check()
                    child=subprocess.Popen(cmds[name],cwd=W.REPO,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
                    rc=child.wait()  # Child wrapper owns deadline and graceful drain; never hard kill.
                verify_success(name,output,args.card,rc)
                state['completed'].append(name)
                state['running']=None
                persist()
                if name != ORDER[-1]:
                    gap=GAP_SECONDS
                    end=time.monotonic()+gap
                    while time.monotonic()<end:
                        W.require(not stopped and not (output/'STOP').exists(),'queue stopped during cooldown')
                        fresh,cursor=W.S.journal(cursor)
                        W.require(not W.S.FAULT.search(fresh),'new GPU fault during cooldown; no launch')
                        time.sleep(max(0.0,min(1,end-time.monotonic())))
            state.update(passed=True,finished_utc_ns=time.time_ns())
            persist()
            return 0
    except Exception as error:
        state.update(error=str(error),child_still_running=child is not None and child.poll() is None)
        persist()
        return 75 if state['child_still_running'] else 1
    finally:
        for sig,handler in handlers.items():
            signal.signal(sig,handler)

if __name__=='__main__':
    raise SystemExit(main())

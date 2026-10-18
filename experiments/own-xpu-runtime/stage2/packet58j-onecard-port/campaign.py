#!/usr/bin/env python3
"""Coordinator-only proposed bracket/fresh record chain. --plan has no writes."""
import argparse,json,os,shlex,signal,subprocess,time
from pathlib import Path
import window as W
import queue_runner as Q
import compare_bracket as C
P=Path(__file__).resolve().parent

def commands(mode,output,review,bracket=None):
 stages=C.STAGES if mode=='bracket' else (('record-port','port'),)
 return [(name,['/usr/bin/python3','-B',str(P/'queue_runner.py'),'--view',view,
   '--card','0','--output-root',str(output/name),'--faults-reviewed-through',review,'--authorized-device-window']) for name,view in stages]

def main(argv=None):
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=('bracket','record'))
 ap.add_argument('--output-root',required=True,type=Path);ap.add_argument('--bracket-root',type=Path)
 ap.add_argument('--faults-reviewed-through',required=True);ap.add_argument('--plan',action='store_true');ap.add_argument('--authorized-device-window',action='store_true');args=ap.parse_args(argv)
 out=args.output_root.resolve();W.require(out.is_relative_to(P/'evidence') and not out.exists(),'fresh packet evidence folder required')
 W.require(args.mode!='record' or args.bracket_root is not None,'record requires completed bracket path')
 review,_=W.S.fault_review(args.faults_reviewed_through,time.time_ns()//1000);W.build_gate()
 cmds=commands(args.mode,out,review,args.bracket_root)
 if args.plan:
  print('# PLAN ONLY: card 0; all windows whole-host; after the two-card record chain. No queue writes.')
  if args.mode=='record':print('# Execution first rechecks complete winning bracket:',args.bracket_root)
  for name,cmd in cmds:print(name+': '+shlex.join(cmd))
  return 0
 W.require(args.authorized_device_window,'coordinator authorization required');W.user_unit_gate(Path('/proc/self/cgroup').read_text());W.closed_environment()
 W.require(os.getpriority(os.PRIO_PROCESS,0)==0 and set(os.sched_getaffinity(0))=={0,1,2,3,16,17,18,19},'coordinator nice0 lane-A cores required')
 if args.mode=='record':W.require(C.compare(args.bracket_root)['passed'],'bracket did not qualify; no fresh record launch')
 # The per-window supervisor checks fresh memory, storage, lane/drain locks and faults.
 W.SUPPORT.storage(out,len(cmds)*sum(W.WRITES['K1' if n.startswith('K1') else n] for n in Q.ORDER))
 out.mkdir();child=None;stopped=[];state=dict(passed=False,device_executed=False,mode=args.mode,commands=cmds,completed=[])
 def save():W.save(out/'campaign.json',state)
 def stop(sig,frame):
  stopped.append(sig)
  if child is not None and child.poll() is None:child.send_signal(signal.SIGTERM)
 handlers={s:signal.signal(s,stop) for s in (signal.SIGTERM,signal.SIGINT)}
 try:
  save()
  for index,(name,cmd) in enumerate(cmds):
   W.require(not stopped and not (out/'STOP').exists(),'campaign stopped')
   with (out/(name+'.log')).open('x') as log:
    child=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT);state['device_executed']=True;save();rc=child.wait()
   W.require(rc==0,'child chain failed; no retry')
   state['completed'].append(name);save()
   if index+1<len(cmds):
    end=time.monotonic()+Q.GAP_SECONDS
    while time.monotonic()<end:
     W.require(not stopped and not (out/'STOP').exists(),'campaign stopped');time.sleep(min(1,end-time.monotonic()))
  if args.mode=='bracket':state['decision']=C.compare(out)
  else:
   fresh,pins,_=C.verify_chain(out/'record-port','port');bracket=C.compare(args.bracket_root)
   state['fresh_confirmation']=dict(passed=fresh[C.METRIC]['median']>max(bracket['rates'][0],bracket['rates'][2],C.RECORD),rate=fresh[C.METRIC]['median'],sources=pins,preregistered_submission_run='record-port/WS128',strict_512_gate=False,external_submission_performed=False)
  state['passed']=True;save();return 0
 except Exception as error:state['error']=str(error);save();return 1
 finally:
  for sig,handler in handlers.items():signal.signal(sig,handler)
if __name__=='__main__':raise SystemExit(main())

"""Coordinator-only selected 12x64 smoke on A, no implicit queue or launch."""
import argparse,json,os,sys
from pathlib import Path
P=Path(__file__).resolve().parent

def main(argv=None):
 ap=argparse.ArgumentParser();ap.add_argument('--selection',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--plan',action='store_true');ap.add_argument('--fault-review');ap.add_argument('--authorized-device-window',action='store_true');a=ap.parse_args(argv)
 from compositions import validate,read,path,key
 selection=validate(read(a.selection));lineage=path(selection)
 assert a.selection.resolve()==lineage/'composition.json'
 assert a.output.resolve()==P/'evidence'/('device-smoke-A-'+key(selection))
 from cpu_prepare143 import verify
 verify()
 from launch_env143 import environment
 expected=environment()
 if not a.plan:assert {k:v for k,v in os.environ.items() if k!='LC_CTYPE'}==expected,'closed smoke environment required'
 from exec_limits import install as guard
 guard()
 from bootstrap import install
 install()
 import smoke_screen as screen
 from memory143 import HOST_BYTES
 def memory(profile):
  snap=screen.M.meminfo();screen.require(snap['MemAvailable']>=HOST_BYTES,'composed host admission');return dict(snapshot=snap,required_bytes=HOST_BYTES)
 screen.memory_admit=memory;screen.HERE=P
 screen.command=lambda args,identity,manifest:['/usr/bin/python3','-B',str(P/'smoke_worker.py'),'--identity',str(args.output/'identity.json'),'--output',str(args.output/'run'),'--seconds','1800']
 screen.WATCHDOG={'tp2':1800}
 args=['--profile','tp2','--lane','A','--placement','1','--timing','token','--lineage',str(lineage),'--seal',str(lineage/'screen-seal.json'),'--output',str(a.output)]
 args+=['--plan'] if a.plan else ['--authorized-device-window','--fault-review',a.fault_review]
 return screen.main(args)
if __name__=='__main__':raise SystemExit(main())

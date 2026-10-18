"""Coordinator-only smoke then five fresh-load lane-B v4 windows."""
import argparse,json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;ORDER=('control','candidate','control','candidate','control')
def view(name):return P/'selections'/name
def output(index):
 from bootstrap import WRAPPER
 from build131 import sha
 campaign=hashlib.sha256(''.join(sha(view(v)/'screen-seal.json') for v in ('control','candidate')).encode()).hexdigest()[:12]
 return WRAPPER/'evidence'/('p131b-'+campaign+'-B-'+('smoke12' if index==-1 else str(index)+'-'+ORDER[index]))
def main(argv=None):
 ap=argparse.ArgumentParser();ap.add_argument('--index',type=int,choices=range(-1,5),required=True);ap.add_argument('--output',required=True);ap.add_argument('--plan',action='store_true');ap.add_argument('--fault-review');ap.add_argument('--authorized-device-window',action='store_true');a=ap.parse_args(argv)
 from bootstrap import install
 install()
 from common import verify_map,ROOT,read
 if not a.plan:
  gate=read(P/'evidence/ready131.json');assert gate['passed'];verify_map(ROOT,gate['sources'])
  from oracle_gate131b import verify_oracle
  verify_oracle()
 assert Path(a.output).resolve()==output(a.index)
 if a.index>=0 and not a.plan:
  from smoke_validation import require_smoke
  require_smoke(lineage=view('candidate'),root=output(-1))
  # Every registered predecessor must drain and pass once. Never retry failures.
  for i in range(a.index):
   r=read(output(i)/'window.json')
   assert r['passed'] and r['device_complete'] and r['lease_released'] and not r.get('stop_reasons')
   from compare131 import load
   load(dict(lane='B',index=i,choice=ORDER[i]))
 lineage=view('candidate' if a.index==-1 else ORDER[a.index])
 args=['--profile','tp2','--lane','B','--placement','1','--timing','token','--lineage',str(lineage),'--seal',str(lineage/'screen-seal.json'),'--output',str(output(a.index))]
 if a.plan:args+=['--plan']
 else:
  assert a.authorized_device_window and a.fault_review
  args+=['--authorized-device-window','--fault-review',a.fault_review]
 if a.index==-1:
  import smoke_screen as screen
  screen.command=lambda args,identity,manifest:['/usr/bin/python3','-B',str(P/'smoke_worker.py'),'--identity',str(args.output/'identity.json'),'--output',str(args.output/'run'),'--seconds','1800']
  screen.WATCHDOG={'tp2':1800};return screen.main(args)
 from run_screen import main as screen
 return screen(args)
if __name__=='__main__':raise SystemExit(main())

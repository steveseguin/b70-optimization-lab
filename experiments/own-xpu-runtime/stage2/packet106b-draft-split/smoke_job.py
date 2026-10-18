"""Coordinator-only first use: combined candidate, all twelve prompts, 64 tokens."""
import argparse
from pathlib import Path
from screen_jobs import P,verify,view,smoke_output
def main(argv=None):
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--plan',action='store_true');ap.add_argument('--fault-review');ap.add_argument('--authorized-device-window',action='store_true');a=ap.parse_args(argv)
 verify();assert Path(a.output).resolve()==smoke_output()
 from bootstrap import install
 install()
 import smoke_screen as screen
 screen.command=lambda args,identity,manifest:['/usr/bin/python3','-B',str(P/'smoke_worker.py'),'--identity',str(args.output/'identity.json'),'--output',str(args.output/'run'),'--seconds','1800']
 screen.WATCHDOG={'tp2':1800};screen.WRITES={'tp2':1_100_000_000}
 lineage=view('head-split+draft-split');cmd=['--profile','tp2','--lane','B','--placement','1','--timing','token','--lineage',str(lineage),'--seal',str(lineage/'screen-seal.json'),'--output',str(smoke_output())]
 if a.plan:cmd+=['--plan']
 else:
  assert a.authorized_device_window and a.fault_review
  from device_gate import require_micro
  require_micro()
  cmd+=['--fault-review',a.fault_review,'--authorized-device-window']
 return screen.main(cmd)
if __name__=='__main__':raise SystemExit(main())

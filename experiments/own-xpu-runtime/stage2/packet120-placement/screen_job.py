"""Coordinator-only v4 job. Lane A refuses until the complete B bracket wins."""
import argparse
from pathlib import Path
from screen_jobs import P,jobs,view,output,verify

def main(argv=None):
 ap=argparse.ArgumentParser();ap.add_argument('--lane',choices=('A','B'),required=True);ap.add_argument('--index',type=int,choices=range(3),required=True);ap.add_argument('--output',required=True);ap.add_argument('--plan',action='store_true');ap.add_argument('--fault-review');ap.add_argument('--authorized-device-window',action='store_true');a=ap.parse_args(argv)
 verify();job=jobs(a.lane)[a.index];dest=output(job);assert Path(a.output).resolve()==dest
 if not a.plan:
  assert a.authorized_device_window and a.fault_review
  if a.lane=='A':
   from bracket_report import bracket
   gate=bracket('B');assert gate['passed'],'lane A waits for exact >=+0.5% over both B controls'
 from run_screen import main as run
 lineage=view(job['choice']);cmd=['--profile','tp2','--lane',a.lane,'--placement',job['placement'],'--timing','token','--lineage',str(lineage),'--seal',str(lineage/'screen-seal.json'),'--output',str(dest)]
 if a.plan:cmd+=['--plan']
 else:cmd+=['--fault-review',a.fault_review,'--authorized-device-window']
 rc=run(cmd)
 if not a.plan and rc in (None,0) and a.index==2:
  from bracket_report import bracket
  from build_engine import save
  save(P/'evidence'/f'device-bracket-{a.lane}.json',bracket(a.lane))
 return rc
if __name__=='__main__':raise SystemExit(main())

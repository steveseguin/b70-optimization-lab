"""Coordinator-only v4 job, exact micros first and conditional A confirmation."""
import argparse
from pathlib import Path
from screen_jobs import P,jobs,view,output,verify

def main(argv=None):
 ap=argparse.ArgumentParser();ap.add_argument('--lane',choices=('A','B'),required=True);ap.add_argument('--index',type=int,choices=range(4),required=True);ap.add_argument('--output',required=True);ap.add_argument('--plan',action='store_true');ap.add_argument('--fault-review');ap.add_argument('--authorized-device-window',action='store_true');a=ap.parse_args(argv)
 verify();winner=None
 if a.lane=='A':
  assert a.index<3
  if not a.plan:
   from bracket_report import bracket
   gate=bracket('B');assert gate['passed'],'A waits for exact >=+0.5% B winner over both controls'
   winner=gate['winner']
 if not a.plan:
  assert a.authorized_device_window and a.fault_review
  from device_gate import require_micro
  for suffix in (81920,122880):require_micro(suffix)
 from run_screen import main as run
 # A's CPU plan checks both possible winners without selecting one from absent evidence.
 candidates=('81920','122880') if a.plan and a.lane=='A' else (winner,)
 for candidate in candidates:
  job=jobs(a.lane,candidate)[a.index];dest=output(job);assert Path(a.output).resolve()==dest
  lineage=view(job['choice']);cmd=['--profile','tp2','--lane',a.lane,'--placement','1','--timing','token','--lineage',str(lineage),'--seal',str(lineage/'screen-seal.json'),'--output',str(dest)]
  cmd+=['--plan'] if a.plan else ['--fault-review',a.fault_review,'--authorized-device-window']
  rc=run(cmd)
  if rc not in (None,0):return rc
 if not a.plan and a.index==(3 if a.lane=='B' else 2):
  from bracket_report import bracket
  from build_engine import save
  save(P/'evidence'/f'device-bracket-{a.lane}.json',bracket(a.lane,winner))
 return rc
if __name__=='__main__':raise SystemExit(main())

"""Plan without running a device; execution requires matched-source selection."""
import argparse
from pathlib import Path
from screen_jobs import P,jobs,view,output,verify,winner

def main(argv=None):
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--lane',choices=('A','B'),required=True);ap.add_argument('--mode',choices=('grid','confirm'),default='grid')
 ap.add_argument('--index',type=int,required=True);ap.add_argument('--output',required=True)
 ap.add_argument('--plan',action='store_true');ap.add_argument('--fault-review');ap.add_argument('--authorized-device-window',action='store_true')
 a=ap.parse_args(argv);verify();choice=None
 if a.mode=='confirm':
  # Planning uses a placeholder view. At execution every entry (controls too)
  # requires a completed exact improving grid from the opposite lane.
  if not a.plan:choice=winner('A' if a.lane=='B' else 'B')['choice']
  else:choice='route-fast'
 rows=jobs(a.lane,choice,a.mode);assert 0<=a.index<len(rows)
 job=rows[a.index]
 # Confirmation output directories are fixed independently of the late winner.
 dest=(P.parent/'screen/v4-lanes/evidence'/f'p91-{a.lane}-confirm-{a.index}') if a.mode=='confirm' else output(job)
 assert Path(a.output).resolve()==dest
 from run_screen import main as run
 lineage=view(job['choice']);command=['--profile','tp2','--lane',a.lane,'--placement','1','--timing','token','--lineage',str(lineage),'--seal',str(lineage/'screen-seal.json'),'--output',str(dest)]
 if a.plan:command+=['--plan']
 else:
  assert a.authorized_device_window and a.fault_review
  command+=['--fault-review',a.fault_review,'--authorized-device-window']
 return run(command)
if __name__=='__main__':raise SystemExit(main())

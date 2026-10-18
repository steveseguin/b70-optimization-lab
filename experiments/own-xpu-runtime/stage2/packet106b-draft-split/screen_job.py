"""Plan CPU-only; coordinator alone runs sealed v4 windows."""
import argparse
from pathlib import Path
from screen_jobs import jobs,output,view,verify,ORDER,require_smoke
def main(argv=None):
 ap=argparse.ArgumentParser();ap.add_argument('--lane',choices=('A','B'),required=True);ap.add_argument('--index',type=int,required=True);ap.add_argument('--output',required=True);ap.add_argument('--plan',action='store_true');ap.add_argument('--fault-review');ap.add_argument('--authorized-device-window',action='store_true');a=ap.parse_args(argv)
 verify();assert 0<=a.index<len(ORDER);job=jobs(a.lane)[a.index];assert Path(a.output).resolve()==output(job)
 from run_screen import main as run
 lineage=view(job['choice']);cmd=['--profile','tp2','--lane',a.lane,'--placement','1','--timing','token','--lineage',str(lineage),'--seal',str(lineage/'screen-seal.json'),'--output',str(output(job))]
 if a.plan:cmd+=['--plan']
 else:
  assert a.authorized_device_window and a.fault_review
  require_smoke()
  if a.lane=='A':
   from compare import compare_grid,load
   assert 'head-split+draft-split' in compare_grid([load(j) for j in jobs('B')])['winners'], 'combined candidate must qualify on B before A confirmation'
  cmd+=['--fault-review',a.fault_review,'--authorized-device-window']
 return run(cmd)
if __name__=='__main__':raise SystemExit(main())

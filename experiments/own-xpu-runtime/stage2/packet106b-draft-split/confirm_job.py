"""CPU plan uses a placeholder; execution requires the complete exact B grid."""
import argparse
from pathlib import Path
from screen_jobs import verify,confirm_jobs,qualified_winner,require_smoke,view,output
def main(argv=None):
 ap=argparse.ArgumentParser();ap.add_argument('--index',type=int,required=True);ap.add_argument('--output',required=True);ap.add_argument('--plan',action='store_true');ap.add_argument('--fault-review');ap.add_argument('--authorized-device-window',action='store_true');a=ap.parse_args(argv)
 verify();assert 0<=a.index<3
 winner='head-split+draft-split'
 if not a.plan:
  assert a.authorized_device_window and a.fault_review
  require_smoke();winner=qualified_winner()
 job=confirm_jobs(winner)[a.index];assert Path(a.output).resolve()==output(job)
 lineage=view(job['choice'])
 cmd=['--profile','tp2','--lane','A','--placement','1','--timing','token','--lineage',str(lineage),'--seal',str(lineage/'screen-seal.json'),'--output',str(output(job))]
 if a.plan:cmd+=['--plan']
 else:cmd+=['--fault-review',a.fault_review,'--authorized-device-window']
 from run_screen import main as run
 return run(cmd)
if __name__=='__main__':raise SystemExit(main())

"""Plan without devices, or run once under the coordinator's v4 lane admission."""
import argparse
from pathlib import Path
from screen_jobs import jobs,view,output,verify
def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('--lane',choices=('A','B'),required=True)
    ap.add_argument('--index',type=int,required=True);ap.add_argument('--output',required=True)
    ap.add_argument('--plan',action='store_true');ap.add_argument('--fault-review')
    ap.add_argument('--authorized-device-window',action='store_true');a=ap.parse_args(argv)
    verify();assert 0<=a.index<3;job=jobs(a.lane)[a.index];dest=output(job)
    assert Path(a.output).resolve()==dest
    from run_screen import main as run
    lineage=view(job['choice'])
    cmd=['--profile','tp2','--lane',a.lane,'--placement','1','--timing','token',
         '--lineage',str(lineage),'--seal',str(lineage/'screen-seal.json'),'--output',str(dest)]
    if a.plan:cmd+=['--plan']
    else:
        assert a.authorized_device_window and a.fault_review
        cmd+=['--fault-review',a.fault_review,'--authorized-device-window']
    return run(cmd)
if __name__=='__main__':raise SystemExit(main())

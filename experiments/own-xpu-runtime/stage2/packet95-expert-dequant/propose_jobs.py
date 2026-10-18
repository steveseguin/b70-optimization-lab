"""Write new proposals only; never enqueue or touch an existing ops file."""
import json
from build_engine import P,ROOT,limits
from screen_jobs import DIRECTIONS,GRIDS,lanes

def main():
 limits();queue=P.parents[1]/'ops/lane-queue'
 for grid in GRIDS:
  for direction in DIRECTIONS:
   source,confirm=lanes(direction)
   for lane,phase in ((source,'grid'),(confirm,'confirm')):
    label=f'{grid}-{direction}-{lane}-{phase}';path=queue/f'proposed-p95-{label}.txt'
    row=dict(name='packet95-'+label,lane=lane,argv=['/usr/bin/python3','-B',str((P/'run_screens.py').relative_to(ROOT)),'--lane',lane,'--direction',direction,'--grid',grid,'--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review='experiments/own-xpu-runtime/stage2/screen/v4-lanes/fault_review.py')
    content=json.dumps(row)+'\n'
    if path.exists():assert path.read_text()==content,'existing proposal differs: '+str(path)
    else:path.write_text(content)
 print('eight new proposals; no live queue changes')
if __name__=='__main__':main()

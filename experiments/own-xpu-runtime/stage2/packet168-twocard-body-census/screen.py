"""Private report route and transparent blocked device plan; never a fallback run."""
import argparse,json,shutil
from pathlib import Path
from census_contract import P,ORDER,IDS,require,read
from analyze import write_report
DEVICE_FLOOR=25_000_000_000
def parser():
    ap=argparse.ArgumentParser()
    ap.add_argument('--lane',choices=('A','B'),required=True)
    ap.add_argument('--kind',choices=('census','smoke','bracket'),default='census')
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--fault-review',type=Path)
    ap.add_argument('--authorized-device-window',action='store_true')
    ap.add_argument('--plan',action='store_true')
    return ap
def storage(path,planned_writes=0):
    free=shutil.disk_usage(path).free
    require(free-planned_writes>=DEVICE_FLOOR,'device storage floor25GB')
    return dict(free_bytes=free,planned_write_bytes=planned_writes,floor_bytes=DEVICE_FLOOR)
def report_completed(output,record,identity,coordination):
    result=write_report(read(Path(output)/'census-input.json'),output)
    result.update(kind=identity['bracket']['kind'],lane=identity['lane'],device_executed=bool(record.get('device_executed')))
    for leaf in ('summary.json','bracket-summary.json'):
        (Path(output)/leaf).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return result
def main(argv=None):
    a=parser().parse_args(argv)
    if a.plan:
        from conditions import cpu_gate
        cpu_gate();budget=read(P/'budget.json')
        print(json.dumps(dict(passed=True,plan_only=True,ready_for_device=False,device_executed=False,
          model_loads=1,lane=a.lane,cards=[2,3]if a.lane=='B'else[0,1],
          requested_view_order=list(ORDER),prompts_per_view=len(IDS),requested_tokens=32,
          planned_write_bytes=budget['planned_write_bytes'],host_required_available_bytes=budget['host_required_available_bytes'],
          expected_seconds=[600,900],watchdog_seconds=7200,per_operation_wait_seconds=600,
          blockers=read(P/'qualification.json')['blockers'],submission_eligible=False)))
        return 0
    # This prototype has no admitted orchestrator. Never fall through to the
    # inherited512 worker or accidentally launch the unchanged parent instead.
    raise ValueError('packet168 incomplete: coupled skip/repair orchestrator and full class coverage are not qualified')

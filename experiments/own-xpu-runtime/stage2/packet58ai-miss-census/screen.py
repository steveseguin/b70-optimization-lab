"""One-card coordinator/report adapter. The report path is shared with rehearsal."""
import argparse,json
from pathlib import Path
import common

def read(path):return json.loads(Path(path).read_text())
def parser():
    ap=argparse.ArgumentParser()
    ap.add_argument('--kind',choices=('smoke','bracket'),default='bracket')
    ap.add_argument('--lane',choices=('A',),default='A')
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--fault-review',type=Path)
    ap.add_argument('--library-path',required=True)
    ap.add_argument('--authorized-device-window',action='store_true')
    ap.add_argument('--plan',action='store_true')
    return ap

def report_completed(args,identity):
    proof=read(args.output/'run/bracket-inputs.json')
    if proof.get('passed') is not True or proof.get('kind')!=args.kind:raise ValueError('incomplete bracket proof')
    views=proof['views']
    if len(views)!=(1 if args.kind=='smoke' else 5):raise ValueError('view coverage')
    for view in views:
        if view.get('passed') is not True:raise ValueError('failed view')
        requests=view['requests']
        if [r['prompt_id'] for r in requests]!=list(common.D.CHECK.PROMPT_IDS):raise ValueError('prompt coverage')
        for r in requests:
            cap=r['requested_max_new']
            if cap not in (64,128):raise ValueError('report cap')
            if not r['passed'] or not r['exact_oracle'] or r['cached_tokens']!=0:raise ValueError('request quality')
            expected=common.D.CHECK.token_record(common.D.ORACLE/'results'/r['prompt_id'])[:cap]
            if r['tokens']!=expected:raise ValueError('report token identity')
    result=dict(passed=True,kind=args.kind,views=views,diagnostic_only=True,submission_eligible=False)
    (args.output/'bracket-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def screen_main(args):
    import queue_runner as Q
    arm='combined' if args.kind=='bracket' else 'smoke'
    argv=['--arm',arm,'--output',str(args.output),'--library-path',args.library_path,'--cache-maintenance','overlap']
    if args.plan:
        argv.append('--plan');return Q.main(argv)
    if args.authorized_device_window:argv.append('--authorized-device-window')
    if args.fault_review:argv.extend(['--fault-review',str(args.fault_review)])
    status=Q.main(argv)
    if status:return status
    proof=read(args.output/'WSCREEN/run/summary.json')
    (args.output/'run').mkdir()
    (args.output/'run/bracket-inputs.json').write_text(json.dumps(dict(passed=proof['passed'],kind=args.kind,views=proof['views'])))
    identity=dict(arithmetic=common.ARITHMETIC);record={}
    report_completed(args,identity)
    record.update(report_completed=True)
    import analyze
    decision=analyze.analyze(args.output)
    (args.output/'measurement-decision.json').write_text(json.dumps(decision,indent=2,allow_nan=False)+'\n')
    return 0 if decision['passed'] else 1

def main(argv=None):return screen_main(parser().parse_args(argv))

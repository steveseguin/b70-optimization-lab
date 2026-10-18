#!/usr/bin/env python3
"""Packet86 attribution screen hosted by pinned, unmodified shared v4 lanes."""
import argparse
import json
from pathlib import Path
import sys
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
WRAPPER=P.parent/'screen/v4-lanes'
sys.path.insert(0,str(WRAPPER))
import screen
from common import read, require, sha, save
sys.path.append(str(P))
from policy import guard, labels, NONEXACT, VIEWS

def view_path(view):
    guard(view)
    return P/'compat/packet64-record-bundle/selections'/view

def verify_dependencies():
    for name,digest in read(P/'dependency-pins.json').items():
        require(sha(ROOT/name)==digest,'packet86 dependency changed: '+name)
    from cpu_seal import verify
    verify()

def worker_command(args, identity, manifest):
    view=args.lineage.name
    guard(view,timing=args.timing)
    require(args.lane in ('A','B') and args.placement=='1' and args.pair_dir is None,'packet86 fixed placement')
    require(args.lineage==view_path(view),'packet86 sealed view required')
    require(read(args.seal).get('diagnostic_nonexact') is True,'diagnostic seal missing')
    return ['/usr/bin/python3','-B',str(P/'worker.py'),'--identity',str(args.output/'identity.json'),
            '--output',str(args.output/'run'),'--seconds','3600']

def expected_quality_refusal(view, record, failure):
    return (view in NONEXACT and record.get('device_complete') is True
            and record.get('lease_released') is True and record.get('report_failed') is True
            and failure==dict(passed=False,device_failure=False,error='screen quality incomplete'))

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--view',choices=VIEWS,required=True)
    ap.add_argument('--purpose',default='screen')
    ap.add_argument('--lane',choices=('A','B'),default='B')
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--plan',action='store_true')
    ap.add_argument('--fault-review',type=Path)
    ap.add_argument('--authorized-device-window',action='store_true')
    a=ap.parse_args(argv);guard(a.view,a.purpose);verify_dependencies()
    view=view_path(a.view)
    args=['--profile','tp2','--lane',a.lane,'--placement','1','--timing','attribution',
          '--lineage',str(view),'--seal',str(view/'screen-seal.json'),'--output',str(a.output)]
    if a.plan:args+=['--plan']
    if a.fault_review:args+=['--fault-review',str(a.fault_review)]
    if a.authorized_device_window:args+=['--authorized-device-window']
    previous=screen.command;previous_summary=screen.summary
    def labelled_summary(rows,incident,profile):
        result=previous_summary(rows,incident,profile)
        result.update(labels(a.view))
        return result
    screen.command=worker_command;screen.summary=labelled_summary
    try:code=screen.main(args)
    finally:screen.command=previous;screen.summary=previous_summary
    if a.plan:return code
    # Shared v4 intentionally refuses non-exact quality reports AFTER safety,
    # postflight and release. Retain that refusal verbatim, never forge exactness.
    # Only this one known report refusal is a successful diagnostic outcome.
    record=read(a.output/'window.json')
    if code:
        fp=a.output/'report-failure.json'
        if not fp.is_file() or not expected_quality_refusal(a.view,record,read(fp)):return code
    require(record.get('device_complete') is True and record.get('lease_released') is True,
            'diagnostic report before safe release')
    proof=read(a.output/'run/report-inputs.json')
    require(proof.get('passed') is True and proof.get('device_isolation',{}).get('passed') is True,
            'diagnostic safety/isolation failure')
    require(proof['lane']==a.lane and len(proof['requests'])==12 and proof['incident64']['passed'],
            'incomplete diagnostic requests')
    require(all(r.get('passed') is True and r.get('diagnostic_nonexact') is True for r in proof['requests']),
            'unlabelled/failed diagnostic request')
    sys.path.insert(0,str(P))
    from report import view_report
    try:
        result=view_report(a.output)
        save(a.output/'diagnostic-summary.json',result)
        # This is packet-local completion, not a replacement shared window verdict.
        save(a.output/'diagnostic-completion.json',dict(passed=True,**labels(a.view),
             shared_window_sha256=sha(a.output/'window.json'),shared_quality_refusal=bool(code),
             summary_sha256=sha(a.output/'diagnostic-summary.json')))
    except Exception as error:
        save(a.output/'packet86-report-failure.json',dict(passed=False,device_failure=False,error=str(error),**labels(a.view)))
        return 1
    return 0

if __name__=='__main__':raise SystemExit(main())

#!/usr/bin/env python3
"""Recompute parent qualification, never trust a saved readiness boolean."""
import argparse
from decimal import Decimal
import hashlib,json,math,shlex,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
METRIC='class_balanced_tok_s_1_100_intervals_after_ttft'
def require(ok,why):
    if not ok:raise ValueError(why)
def evaluate(rows,policy=None):
    policy=policy or json.loads((P/'readiness-policy.json').read_text())
    require([r['label'] for r in rows]==['A0','B0','A1','B1','A2'],'complete five-view bracket required')
    rates=[];signatures=[]
    for i,row in enumerate(rows):
        require(row['view']==('p60fusion' if i%2 else 'production'),'composition order differs')
        requests=row['requests']
        require(row.get('passed') is True and len(requests)==12,'twelve exact prompts required')
        require(len({r['prompt_id'] for r in requests})==12,'duplicate prompt')
        require(all(r.get('passed') is True and r.get('exact_oracle') is True and r.get('cached_tokens')==0 and len(r['tokens'])==128 for r in requests),'128 exact uncached tokens per prompt required')
        signatures.append([(r['prompt_id'],r['prompt_token_sha256'],r['tokens']) for r in requests])
        value=row[METRIC]['median']
        require(type(value) in (float,int) and math.isfinite(value) and value>0,'invalid rate')
        rates.append(Decimal(str(value)))
    require(all(s==signatures[0] for s in signatures),'prompts or tokens differ across views')
    # The first view fills the immutable device expert cache in this one-load
    # bracket. Keep it exactness-gated and reported, outside speed comparison.
    controls=rates[2::2];candidates=rates[1::2]
    require(max(controls)<=min(controls)*(1+Decimal(str(policy['maximum_control_drift']))),'controls drift by more than 3%')
    require(all(c>=a*(1+Decimal(str(policy['minimum_gain_each_control']))) for c in candidates for a in controls),'both full composition views must beat EVERY packet58ad-line control by at least 0.5%')
    gain=min(candidates)/max(controls)-1
    require(gain>=Decimal(str(policy['minimum_record_gain'])),'strict gain over record must be at least 2%')
    return dict(projected_record_tok_s=float(Decimal(str(policy['record_anchor_tok_s']))*(1+gain)),combined_gain_over_record=float(gain),record_gain_measured=False,passed=True,rates=list(map(float,rates)),control_drift=float(max(controls)/min(controls)-1),minimum_gain=float(min(candidates)/max(controls)-1),
                warmup_view=dict(label='A0',rate=float(rates[0]),exact=True,excluded_from_drift_and_comparison=True),
                comparison_controls=['A1','A2'],readiness_policy=policy['readiness_policy'])
def command_argv():
    from launch_env import library_path
    lib=library_path()
    return ['systemd-run','--user','--unit=packet58-onecard-58ah-a','--property=Restart=no','--property=SendSIGKILL=no','--property=TimeoutStopSec=infinity','--property=Nice=0','--working-directory='+str(ROOT),'/usr/bin/taskset','-c','0-3,16-19','/usr/bin/env','-i','PATH=/usr/bin:/bin','LD_LIBRARY_PATH='+lib,'OMP_NUM_THREADS=2','/usr/bin/python3','-B',str(P/'queue_runner.py'),'--authorized-device-window','--card','0','--view','down-tile16','--output-root',str(P/'evidence/card0-58ah-a'),'--fault-review',str(P/'evidence/fault-review-58ah-a.json')]
def chain_command():return shlex.join(command_argv())+' < /dev/null'
def verify():
    import window as W
    seal=W.build_gate()
    from composition import DIMENSIONS
    selection=json.loads((P/'runtime-selection.json').read_text())
    require(all(selection.get(k)==v and seal.get(k)==v for k,v in DIMENSIONS.items()),'full composition binding differs')
    pins=json.loads((P/'submission-pins.json').read_text())
    require(pins['build_receipt_sha256']==W.sha(P/'build-receipt.json'),'submission pins stale')
    W.verify_files(ROOT,pins['sources'])
    require(not (P/'evidence/card0-58ah-a').exists(),'fresh chain output required; no retry')
    run=subprocess.run(['/usr/bin/python3','-B',str(P/'screen_gate.py')],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
    require(run.returncode==0,'58ag smoke/v5 pending or invalid: '+run.stderr.strip()[-1800:])
    screen=json.loads(run.stdout)
    require(screen['native_artifacts']==seal['artifacts'],'parent engine/build differs')
    result=evaluate(screen['rows'])
    return dict(result,smoke_passed=True,boot_id=screen['boot_id'],screen_sources=screen['sources'],parent_queue_snapshots=screen['queue_snapshots'],screen_build_sha256=screen['build_sha256'],build_receipt_sha256=W.sha(P/'build-receipt.json'),submission_pins_sha256=W.sha(P/'submission-pins.json'))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path);args=ap.parse_args()
    row=dict(schema='packet58ah.ready.v1',passed=False,ready=False,device_executed=False,chain_command=chain_command(),coordinator_only=True,launch_performed=False)
    try:row.update(verify(),ready=True)
    except (ValueError,OSError,KeyError,TypeError,AssertionError,subprocess.TimeoutExpired) as error:row['reason']=str(error)
    if args.output:
        require(args.output.resolve()==P/'ready.json','only local ready.json may be written')
        args.output.write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps(row,indent=2));return 0 if row['ready'] else 1
if __name__=='__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));raise SystemExit(main())

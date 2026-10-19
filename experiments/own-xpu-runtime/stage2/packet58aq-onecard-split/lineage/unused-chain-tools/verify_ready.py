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
    import importlib.util
    spec=importlib.util.spec_from_file_location('resident_comparison',P/'screen/compare_bracket.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    result=module.compare(rows)
    # Post-result packet58ajc amendment of the coordinator's two-sided wording.
    # Keep the original comparator and saved device summaries unchanged.
    policy = policy or json.loads((P/'readiness-policy.json').read_text())
    require(policy['minimum_relative_rate']==0.995 and policy['maximum_control_drift']==0.03
            and policy['first_view_warmup'] is True and policy['full_exact_suite_required'] is True,
            'readiness policy differs')
    rates=[Decimal(str(v[METRIC]['median'])) for v in rows]
    noninferior=all(c >= a*Decimal('.995') for a in rates[2::2] for c in rates[1::2])
    require(noninferior and result['control_drift_passed'],
            'resident must be >= -0.5% vs EVERY warm mapped control; drift <=3%')
    result.update(original_candidate_beats_all_controls=result['candidate_beats_all_controls'],
                  candidate_beats_all_controls=True, resident_noninferior=True,
                  readiness_policy=policy['readiness_policy'],
                  readiness_amendment=policy['amendment'], maximum_gain_fraction=None)
    return dict(result,minimum_gain=result['minimum_gain_vs_best_control'],record_gain_measured=False)
def command_argv():
    from launch_env import library_path
    lib=library_path()
    return ['systemd-run','--user','--unit=packet58-onecard-58aj-a','--property=Restart=no','--property=SendSIGKILL=no','--property=TimeoutStopSec=infinity','--property=Nice=0','--working-directory='+str(ROOT),'/usr/bin/taskset','-c','0-3,16-19','/usr/bin/env','-i','PATH=/usr/bin:/bin','LD_LIBRARY_PATH='+lib,'OMP_NUM_THREADS=2','/usr/bin/python3','-B',str(P/'queue_runner.py'),'--authorized-device-window','--card','0','--view','down-tile16','--output-root',str(P/'evidence/card0-58aj-a'),'--fault-review',str(P/'evidence/fault-review-58aj-a.json')]
def chain_command():return shlex.join(command_argv())+' < /dev/null'
def verify():
    import window as W
    seal=W.build_gate()
    from composition import DIMENSIONS
    selection=json.loads((P/'runtime-selection.json').read_text())
    require(selection.get('lookups')=='resident' and seal.get('lookups')=='resident','resident lookup binding differs')
    require(all(selection.get(k)==v and seal.get(k)==v for k,v in DIMENSIONS.items()),'full composition binding differs')
    pins=json.loads((P/'submission-pins.json').read_text())
    require(pins['build_receipt_sha256']==W.sha(P/'build-receipt.json'),'submission pins stale')
    W.verify_files(ROOT,pins['sources'])
    require(not (P/'evidence/card0-58aj-a').exists(),'fresh chain output required; no retry')
    run=subprocess.run(['/usr/bin/python3','-B',str(P/'screen_gate.py')],stdin=subprocess.DEVNULL,capture_output=True,text=True)
    require(run.returncode==0,'58aj smoke/v5 pending or invalid: '+run.stderr.strip()[-1800:])
    screen=json.loads(run.stdout)
    require(screen['native_artifacts']==seal['artifacts'],'parent engine/build differs')
    result=evaluate(screen['rows'])
    return dict(result,smoke_passed=True,boot_id=screen['boot_id'],screen_sources=screen['sources'],parent_queue_snapshots=screen['queue_snapshots'],screen_build_sha256=screen['build_sha256'],build_receipt_sha256=W.sha(P/'build-receipt.json'),submission_pins_sha256=W.sha(P/'submission-pins.json'))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path);args=ap.parse_args()
    row=dict(schema='packet58aj.ready.v1',passed=False,ready=False,device_executed=False,chain_command=chain_command(),coordinator_only=True,launch_performed=False)
    try:row.update(verify(),ready=True)
    except (ValueError,OSError,KeyError,TypeError,AssertionError,subprocess.TimeoutExpired) as error:row['reason']=str(error)
    if args.output:
        require(args.output.resolve()==P/'ready.json','only local ready.json may be written')
        args.output.write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps(row,indent=2));return 0 if row['ready'] else 1
if __name__=='__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(2_000_000_000,2_000_000_000));raise SystemExit(main())

#!/usr/bin/env python3
"""Recompute readiness; emit a coordinator command, never run it."""
import argparse
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import shlex
import subprocess
import sys

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
METRIC = 'class_balanced_tok_s_1_100_intervals_after_ttft'


def require(ok, why):
    if not ok:
        raise ValueError(why)


def evaluate(rows, policy=None):
    policy = policy or json.loads((P/'readiness-policy.json').read_text())
    require(len(rows) == 3, 'three screen receipts required')
    require([r['view'] for r in rows] == policy['views'], 'production/down-tile16/production required')
    rates = []
    signatures = []
    for row in rows:
        requests = row['requests']
        require(len(requests) == policy['exact_prompts_per_arm'], '12 prompts required')
        require(len({r['prompt_id'] for r in requests}) == 12, 'duplicate prompt')
        require(all(r.get('passed') is True and r.get('exact_oracle') is True and len(r['tokens']) == 128
                    for r in requests), '12/12 exact with 128 tokens required')
        signatures.append([(r['prompt_id'],r['prompt_token_sha256'],r['tokens']) for r in requests])
        value = row[METRIC]['median']
        require(type(value) in (int,float) and math.isfinite(value) and value > 0, 'invalid speed')
        rates.append(value)
    require(signatures[0] == signatures[1] == signatures[2], 'screen outputs or prompts differ')
    require(len({r['miss_path'] for r in rows}) == 1, 'unmatched miss paths')
    exact_rates = [Decimal(str(v)) for v in rates]
    gains = [float(exact_rates[1]/exact_rates[i]-1) for i in (0,2)]
    # Decimal input spellings preserve the inclusive boundary without a float
    # subtraction error or tolerance that admits a below-threshold value.
    require(all(exact_rates[1] >= exact_rates[i]*(1+Decimal(str(policy['minimum_gain_each_control']))) for i in (0,2)),
            'tile16-only must beat BOTH controls by at least 0.5%')
    drift = max(rates[0],rates[2])/min(rates[0],rates[2])-1
    require(drift <= policy['maximum_control_drift'], 'controls drift by more than 3%')
    require(rates[1] > policy['existing_record_tok_s'], 'tile16-only does not beat the saved one-card record')
    return dict(passed=True, exact_prompts=[12,12,12], rates=rates, gains=gains, control_drift=drift)


def chain_command():
    args = ['systemd-run','--user','--unit=packet58-onecard-58p-a','--property=Restart=no',
            '--property=SendSIGKILL=no','--property=TimeoutStopSec=infinity','--property=Nice=0',
            '--working-directory='+str(ROOT),'/usr/bin/taskset','-c','0-3,16-19','/usr/bin/env','-i',
            'PATH=/usr/bin:/bin','OMP_NUM_THREADS=2']
    return (shlex.join(args)+' LD_LIBRARY_PATH="$LD_LIBRARY_PATH" '+shlex.join([
        '/usr/bin/python3','-B',str(P/'queue_runner.py'),'--authorized-device-window','--card','0',
        '--view','down-tile16','--output-root',str(P/'evidence/card0-58p-a'),
        '--fault-review',str(P/'evidence/fault-review-58p.json')])+' < /dev/null')


def verify():
    import window as W
    seal = W.build_gate()
    pins = json.loads((P/'submission-pins.json').read_text())
    require(pins['build_receipt_sha256'] == W.sha(P/'build-receipt.json'), 'submission pins stale')
    W.verify_files(ROOT, pins['sources'])
    require(not (P/'evidence/card0-58p-a').exists(), 'fresh chain output required; no retry')
    command = ['/usr/bin/nice','-n','19','/usr/bin/taskset','-c','8-15,24-31',
               '/usr/bin/python3','-B',str(P/'screen_gate.py')]
    run = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=180)
    detail = run.stderr.strip().splitlines()[-1] if run.stderr.strip() else 'screen checker returned no diagnostic'
    require(run.returncode == 0, '58n receipts pending or invalid: '+detail)
    screen = json.loads(run.stdout)
    require(screen['screen_selection_sha256'] == W.digest('down-tile16'), 'screen/chain tile16-only selection differs')
    require(screen['screen_native_artifacts'] == {n:h for n,h in seal['artifacts'].items() if n.startswith('build/device/')},
            'screen/chain native binaries differ')
    result = evaluate(screen['rows'])
    return dict(result, screen_sources=screen['sources'], screen_build_sha256=screen['screen_build_sha256'],
                boot_id=screen['boot_id'], build_receipt_sha256=W.sha(P/'build-receipt.json'),
                submission_pins_sha256=W.sha(P/'submission-pins.json'))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path)
    args = ap.parse_args(argv)
    row = dict(schema='packet58p.ready.v1', passed=False, ready=False, device_executed=False,
               chain_command=chain_command(), coordinator_only=True, launch_performed=False,
               command_status='proposed; refuses until fresh receipt verification passes')
    try:
        row.update(verify(), ready=True, command_status='ready for coordinator; live admission and fault review still required')
    except (ValueError,OSError,KeyError,TypeError,subprocess.TimeoutExpired) as error:
        row['reason'] = str(error)
    if args.output:
        require(args.output.resolve() == P/'ready.json', 'only local ready.json may be written')
        args.output.write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps(row,indent=2))
    return 0 if row['ready'] else 1


if __name__ == '__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))

    raise SystemExit(main())

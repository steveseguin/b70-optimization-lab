#!/usr/bin/env python3
"""Preregister one sequential in-engine campaign; device run is coordinator-only.

--plan verifies CPU seals and prints argv without touching devices or services.
--authorized-device-window runs inside an already coordinator-owned screen-*
user unit, never creates/restarts a service, and never retries a failed screen.
"""
import argparse
import json
from pathlib import Path
import signal
import subprocess
import sys

P = Path(__file__).resolve().parent
sys.path.insert(0,str(P/'screen'))
import screen
from common import read, require, save, sealed, sha
from conditions import cpu_gate, lane_gate, selected_clients
from cpu_seal import verify as verify_wrapper
import expert_composition
sys.path.insert(0,str(P.parent/'packet64-record-bundle'))
from lane_admission import Reservation

CHOICES = ('wide64','wg64','wg128','prefetch64')


def stages(choice):
    # First stage is unprofiled, as required. Attribute identical full requests
    # under AB/BA order so one arm cannot win solely by running second.
    return [('token-control','production','token'),('token-candidate',choice,'token'),
            ('control-1','production','attribution'),('candidate-1',choice,'attribution'),
            ('candidate-2',choice,'attribution'),('control-2','production','attribution')]


def screen_args(choice, name, timing, args, authorized=False):
    output = args.output / choice / name
    return ['--lineage',str(P/'selections'/choice), '--seal',str(P/'selections'/choice/'screen-seal.json'),
            '--lane',args.lane,'--placement','1','--timing',timing,'--output',str(output)] + (
                ['--authorized-device-window','--fault-review',str(args.fault_review)] if authorized else ['--plan'])


def manifest(args):
    entries = []
    for candidate in args.candidates:
        rows = []
        for name, choice, timing in stages(candidate):
            # Group all candidate's controls and candidates under its own arm.
            cli = screen_args(choice,name,timing,args)
            cli[cli.index('--output')+1] = str(args.output/candidate/name)
            parsed = screen.parser().parse_args(cli)
            identity = sealed(parsed)
            require(identity['placement']['supported'], 'unsupported placement')
            rows.append(dict(name=name, choice=choice, timing=timing, identity=identity,
                             plan_command=[sys.executable,'-B',str(P/'screen/screen.py'),*cli]))
        entries.append(dict(candidate=candidate, stages=rows))
    return dict(schema='packet65.composition-campaign.v1', device_executed=False,
                lane=args.lane, output=str(args.output), model_lifetimes_maximum=6*len(entries),
                sequential=True, retries=0, stop_on_first_passing_candidate=True,
                reservation_scope='whole-host; shared chain-lanes-v1 A+hold-B protocol; both legacy v3 locks per screen',
                fault_policy='existing v3 fast fault stop, evidence, shared lane/teardown locks; coordinator owns recovery',
                arithmetic='iq3-p49-split32-v1', oracle='packet49',
                required_latency_reduction_percent=30, timing='full composition, fixtures9-16, 7 routed-class sites/layer',
                wrapper_seal_sha256=sha(P/'screen/placement-validation/wrapper-seal.json'), arms=entries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lane',choices=('A','B'),required=True)
    parser.add_argument('--candidates',nargs='+',choices=CHOICES,default=list(CHOICES))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--fault-review',type=Path)
    parser.add_argument('--plan',action='store_true')
    parser.add_argument('--authorized-device-window',action='store_true')
    args=parser.parse_args()
    args.output=args.output.resolve()
    require(len(set(args.candidates))==len(args.candidates),'duplicate candidate')
    require(args.output.is_relative_to(P/'screen/evidence') and not args.output.exists(),'fresh packet65 screen evidence root required')
    if args.plan:
        cpu_gate()
    else:
        require(args.authorized_device_window and args.fault_review,'coordinator authorization and fault review required')
        lane_gate(args.lane)
        screen.unit_gate(Path('/proc/self/cgroup').read_text())
        screen.unit_conditions(Path('/proc/self/cgroup').read_text())
    verify_wrapper()
    plan=manifest(args)
    if args.plan:
        print(json.dumps(plan,indent=2))
        return 0
    args.output.mkdir(parents=True)
    save(args.output/'preregistration.json',plan)
    current,stopped=[],[]
    def stop(number,unused):
        stopped.append(number)
        if current and current[0].poll() is None:
            current[0].send_signal(signal.SIGTERM)
    handlers={number:signal.signal(number,stop) for number in (signal.SIGTERM,signal.SIGINT)}
    reservation=Reservation('A',window='W2m-speed',timing_claim=True,
                            check=lambda:require(not stopped,'coordinator stopped campaign'))
    reservation.record['physical_screen_lane']=args.lane
    reservation.record['packet65_campaign_output']=str(args.output)
    try:
        with reservation:
            for arm in plan['arms']:
                candidate=arm['candidate']
                for stage in arm['stages']:
                    require(not stopped,'coordinator stopped campaign')
                    cli=screen_args(stage['choice'],stage['name'],stage['timing'],args,authorized=True)
                    cli[cli.index('--output')+1]=str(args.output/candidate/stage['name'])
                    require(sealed(screen.parser().parse_args(cli))==stage['identity'],'preregistered selection changed')
                    with (args.output/(candidate+'-'+stage['name']+'.log')).open('w') as log:
                        child=subprocess.Popen([sys.executable,'-B',str(P/'screen/screen.py'),*cli],
                                               stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
                        current[:]=[child]
                        status=child.wait()
                        current.clear()
                    require(status==0,'screen failed; no retry: '+candidate+'/'+stage['name'])
                pairs=[(args.output/candidate/f'control-{i}',args.output/candidate/f'candidate-{i}') for i in (1,2)]
                result=expert_composition.analyze(pairs)
                save(args.output/candidate/'composition.json',result)
                if result['passed']:
                    save(args.output/'decision.json',dict(passed=True,selected_candidate=candidate,device_executed=True,
                        promotion_eligible=False,reason='30% class screen passed twice; full qualification chain remains required'))
                    selected_clients(args.lane,whole_host=True)
                    reservation.complete(drained=True)
                    return 0
            save(args.output/'decision.json',dict(passed=False,device_executed=True,selected_candidate=None,
                promotion_eligible=False,reason='No candidate met the 30% class screen in both fresh pairs'))
            selected_clients(args.lane,whole_host=True)
            reservation.complete(drained=True)
            return 2
    except BaseException as error:
        save(args.output/'failure.json',dict(passed=False,error=str(error),automatic_retry=False))
        raise
    finally:
        for number,handler in handlers.items():
            signal.signal(number,handler)


if __name__=='__main__':
    raise SystemExit(main())

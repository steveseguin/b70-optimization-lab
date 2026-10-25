#!/usr/bin/env python3
"""Portable current-SC117 live-MTP research replay with independent admission.

Uses the shared wire/scheduler implementation, never its lab planners, guards or
observer. Defaults to CPU planning/checking. No training, service or restart loop.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import sys
import time

try:
    from . import launch_plan as planner, controller
except ImportError:
    import launch_plan as planner
    import controller

ENGINE=Path(__file__).resolve().parents[1]
TOOLS=ENGINE/'tools'
# Exact package-relative import location also works in an extracted source tree.
sys.path.insert(0,str(TOOLS))
import live_wavefront_driver as live

require=planner.prep.require
RUNTIME_FILES=('tools/pipeline_driver.py','tools/wavefront_driver.py','tools/live_wavefront_driver.py',
               'tools/persistent_live_suite.py','tools/persistent_wavefront_driver.py',
               'planning/wavefront.py','planning/live_draft.py')


def make_plan(config_path):
    config_path=Path(config_path).absolute()
    raw=planner.prep.read_small(config_path,2*1024**2)
    c=json.loads(raw,object_pairs_hook=planner.prep.pairs)
    require(c.get('schema')=='ownrt.portable-live-config.v1','portable live config schema')
    allowed={'schema','deployment','profile_sha256','binding_sha256','build_receipt','build_receipt_sha256',
             'bdfs','library_dirs','output','prompt_tokens','max_new','seconds','verify_restore','draft_partition','use_proposals',
             'launch_policy','launch_policy_sha256'}
    require(not set(c)-allowed,'unknown portable live config field')
    verify=c.get('verify_restore',True);partition=c.get('draft_partition',False);proposals=c.get('use_proposals',True)
    require(all(type(v)is bool for v in (verify,partition,proposals)),'explicit live mode booleans')
    plan=planner.make_plan(c['deployment'],c['profile_sha256'],c['binding_sha256'],
        c['build_receipt'],c['build_receipt_sha256'],c['bdfs'],c['library_dirs'],c['output'],
        c['prompt_tokens'],'target-only',c.get('max_new',32),c.get('seconds',1800),
        policy_path=c.get('launch_policy'),policy_sha256=c.get('launch_policy_sha256'))
    deployment=Path(c['deployment']).absolute()
    binding=planner.checked_file(deployment/'binding.json',c['binding_sha256'])
    planner.validate_local_files(binding,require_draft=True)
    require('draft-manifest.tsv' in binding['artifacts'],'live MTP requires authenticated draft manifest')
    receipt=planner.checked_file(c['build_receipt'],c['build_receipt_sha256'],4*1024**2)
    required={'pipeline/layout.hpp','pipeline/wavefront.hpp','pipeline/checkpoint.hpp','pipeline/live_draft.hpp'}
    if partition:required.add('pipeline/operator_state.hpp')
    require(required<=set(receipt.get('sources',{})),'build lacks live-MTP/partition source capability')
    policy=planner.checked_file(plan['launch_policy']['path'],plan['launch_policy']['sha256'])
    for stage in plan['stages']:
        stage['environment'].pop('OWNRT_DRAFT_DEPTH_PROBE',None)
        stage['environment'].pop('OWNRT_DRAFT_DEPTH_VERIFY',None)
        stage['argv']+=['--pipeline-wavefront','--pipeline-live-draft']
        if verify:stage['argv'].append('--pipeline-wavefront-verify-restore')
        if partition:stage['argv'].append('--pipeline-draft-partition')
        if stage['first']:
            stage['argv']+=['--draft-mtp','--draft-fault','none','--draft-experts',policy['mtp']['experts'],
                            '--draft-manifest',str(deployment/'draft-manifest.tsv'),
                            '--draft-model',binding['draft_root']]
    dependencies=[ENGINE/name for name in RUNTIME_FILES]
    dependencies+=[Path(__file__).resolve(),Path(controller.__file__).resolve(),Path(controller.observer.__file__).resolve()]
    for path in dependencies:plan['pins'][str(path)]=planner.hash_file(path,8*1024**2)
    plan['pins'][str(config_path)]=planner.prep.digest(raw)
    plan.update(schema='ownrt.portable-live-plan.v1',config=str(config_path),mode='verified-wavefront',
                protocol='pipeline-live-draft-v1',live_draft=True,draft_training=False,
                verify_restore=verify,draft_partition=partition,use_proposals=proposals,max_inflight=2,
                diagnostic_only=True,speed_claim=False,portable_observer_available=True,
                limits='Portable live existing-MTP research recipe. Profile/local binding authenticated and build overlay pinned. Requires explicit run admission and target/draft/token qualification; no portable speed or clean-host certification.')
    plan['required_controller_gates']+=['live_controller_sha256 independently bound in admission',
                                       'full target and canonical draft state qualification for this generated build']
    plan['command_sha256']=planner.prep.digest(json.dumps(plan['stages'],sort_keys=True,separators=(',',':')).encode())
    return plan


def verify_plan(path,plan_sha,profile_sha,binding_sha,receipt_sha):
    plan=planner.checked_file(path,plan_sha,8*1024**2)
    require(plan.get('schema')=='ownrt.portable-live-plan.v1','portable live plan schema')
    require(plan.get('model_profile_sha256')==profile_sha and plan.get('deployment_binding_sha256')==binding_sha,
            'independent model/binding digest mismatch')
    config=planner.checked_file(plan['config'],plan['pins'][plan['config']],2*1024**2)
    require(config['build_receipt_sha256']==receipt_sha,'independent build receipt digest mismatch')
    require(plan==make_plan(plan['config']),'portable live plan/input/source identity changed')
    return plan


def admit(plan,admission,plan_sha):
    require(admission.get('live_controller_sha256')==planner.hash_file(__file__), 'live controller code identity')
    return controller.admit(plan,admission,plan_sha)


def execute(plan,admission,stop_fd=None,unit=None):
    """Single load and cooperative teardown using only the portable Guard."""
    require(admission.get('schema')=='ownrt.portable-run-admission.v1' and admission.get('owner_authorized') is True,'explicit admission required')
    require(datetime.fromisoformat(admission['expires_utc'])>datetime.now(timezone.utc),'admission expired')
    require(os.getpriority(os.PRIO_PROCESS,0)==19,'launch driver under nice -n 19')
    unit_identity=controller.validate_unit(unit) if stop_fd is None else None
    output=Path(plan['output']);guard=controller.Guard(plan,admission,stop_fd)
    output.mkdir(mode=0o700)
    controller.save(output/'plan.json',plan);controller.save(output/'admission.json',admission)
    controller.save(output/'baseline.json',guard.baseline);controller.save(output/'preflight.json',guard.initial_observation)
    if unit_identity is not None:controller.save(output/'unit.json',unit_identity)
    prior={sig:signal.getsignal(sig) for sig in (signal.SIGINT,signal.SIGTERM)}
    for sig in prior:signal.signal(sig,lambda *_:guard.signal_stop.set())
    stages=[];result={};failure=None;started=time.monotonic()
    try:
        guard.thread.start()
        for spec in plan['stages']:
            guard.check()
            # LiveStage reuses only wire/process ownership code. Its constructor
            # consumes this injected portable guard, never the lab Guard class.
            stage=live.LiveStage(spec,plan,guard);stages.append(stage);stage.receive(ready=True)
        require(len({s.stream_bytes for s in stages})==1,'live stage F32 boundary shape mismatch')
        guard.validate(guard.obs.observe())
        result=live.drive(stages,plan,guard,output)
        for stage in stages:stage.command(4,position=2147483647)
        guard.validate(guard.obs.observe())
        for stage in stages:stage.command(5)
    except Exception as error:
        failure=repr(error);guard.fail(failure)
    finally:
        deadline=time.monotonic()+plan['grace_seconds']
        while any(proc.poll() is None for _,proc in guard.tracked_processes) and time.monotonic()<deadline:time.sleep(.2)
        guard.done.set();guard.thread.join(timeout=40)
        if guard.thread.is_alive():guard.fail('portable passive monitor did not quiesce')
        try:
            after=guard.obs.observe();controller.save(output/'postflight.json',after)
            guard.validate(after);guard.check()
        except Exception as error:guard.fail(error)
        failure=failure or guard.failed
        alive=[proc.pid for _,proc in guard.tracked_processes if proc.poll() is None]
        codes={str(index):proc.poll() for index,proc in guard.tracked_processes}
        if alive or any(code!=0 for code in codes.values()):failure=failure or 'native live stage did not exit cleanly'
        for sig,handler in prior.items():signal.signal(sig,handler)
        controller.save(output/'result.json',dict(result,schema='ownrt.portable-live-result.v1',passed=failure is None,
            error=failure,live_pids=alive,returncodes=codes,wall_seconds=time.monotonic()-started,
            mode='verified-wavefront',live_draft=True,draft_training=False,diagnostic_only=True,speed_claim=False))
    require(failure is None,str(failure))
    return output/'result.json'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('plan','check','run'))
    p.add_argument('--config',type=Path)
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--plan-sha256')
    p.add_argument('--profile-sha256')
    p.add_argument('--binding-sha256')
    p.add_argument('--build-receipt-sha256')
    p.add_argument('--admission',type=Path)
    p.add_argument('--coordinator-stop-fd',type=int)
    p.add_argument('--unit')
    a=p.parse_args()
    if a.action=='plan':
        require(a.config is not None,'portable config required')
        controller.save(a.plan,make_plan(a.config))
        print(json.dumps(dict(plan=str(a.plan.absolute()),sha256=planner.hash_file(a.plan),device_execution_requested=False)))
        return
    require(all((a.plan_sha256,a.profile_sha256,a.binding_sha256,a.build_receipt_sha256)),'explicit plan/profile/binding/build digests required')
    plan=verify_plan(a.plan,a.plan_sha256,a.profile_sha256,a.binding_sha256,a.build_receipt_sha256)
    if a.action=='check':
        print(json.dumps(dict(plan_validated=True,device_execution_requested=False,live_draft=True)))
        return
    require(a.admission is not None and (a.coordinator_stop_fd is not None or a.unit),'run requires admission and owning unit or stop FD')
    admission=json.loads(planner.prep.read_small(a.admission),object_pairs_hook=planner.prep.pairs)
    execution_plan=admit(plan,admission,a.plan_sha256)
    print(execute(execution_plan,admission,a.coordinator_stop_fd,a.unit))


if __name__=='__main__':main()

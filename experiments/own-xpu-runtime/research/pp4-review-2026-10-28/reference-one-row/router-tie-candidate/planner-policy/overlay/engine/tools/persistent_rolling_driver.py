#!/usr/bin/env python3
"""Separate opt-in persistent rolling launcher. CPU planning unless --run."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

import persistent_rolling_suite as suite_tools
base, bridge = suite_tools.base, suite_tools.bridge
live = bridge.pending.live


def make_plan(config_path):
    config = suite_tools.evidence.read_json(config_path,4*1024**2)
    base.require(config.get('rolling_depth2') is True and config.get('use_proposals') is True,
                 'explicit persistent rolling required')
    base.require(not any(k in config for k in ('recursive_reference','scripted_proposal_tokens',
        'force_miss_positions','expected_outputs','pending_cases')), 'rolling config accepts no reference/oracle inputs')
    base.require(config.get('persistent_requests') is True,'explicit persistent request opt-in')
    speculative_depth=config.get('speculative_depth',2)
    base.require(type(speculative_depth)is int and speculative_depth in (2,3),'speculative_depth requires integer2 or3')
    recursive_flat_copy=config.get('recursive_flat_copy',False)
    base.require(type(recursive_flat_copy) is bool,'recursive_flat_copy requires boolean opt-in')
    capture_overlap=config.get('capture_ready_overlap',False)
    base.require(type(capture_overlap) is bool,'capture-ready overlap requires boolean opt-in')
    provider_stage=config.get('provider_stage',0)
    base.require(type(provider_stage) is int and provider_stage >= 0,
                 'provider_stage requires a nonfinal owner index')
    base.require(provider_stage == 0 or capture_overlap, 'remote provider requires owned-parent capture overlap')
    policy=config.get('check_policy')
    base.require(policy in ('qualification','measured'),'fixed per-process native check policy')
    verify=policy=='qualification'
    base.require(all(type(config.get(name)) is bool and config[name]==verify for name in
        ('verify_restore','verify_recursive_restore','verify_provider_survival')),
        'diagnostic flags must match fixed native policy')
    base.require(type(config.get('admitted_max_new')) is int and
        config['admitted_max_new']==config.get('max_new') and 1<=config['admitted_max_new']<=512,
        'explicit per-process max-new admission required')
    plan = base.make_plan(config_path)
    base.require(provider_stage < len(plan['stages'])-1, 'provider must be a nonfinal stage')
    base.require(plan['context']>=32,'persistent cold reset requires context extent at least32')
    base.require(len(plan['stages']) in (2,4,6) and 1 <= plan['max_new'] <= config['admitted_max_new'],
                 'persistent rolling supports2/4/6 owners and explicit bounded outputs')
    eos = config.get('eos_token_ids')
    base.require(isinstance(eos,list) and eos and len(set(eos)) == len(eos) and plan['eos'] in eos
        and all(type(t) is int and 0 <= t < plan['vocab'] for t in eos), 'explicit complete EOS set')
    receipt = suite_tools.evidence.read_json(config['build_receipt'],4*1024**2)
    required = {'pipeline/ring/'+n+'.hpp' for n in ('stage_ring','wire','checkpoint_ring','engine_backend','dispatcher')}
    required |= {'pipeline/recursive_provider/'+n for n in ('batch.hpp','draft_runtime_extension.inc',
        'final_event.hpp','peer.hpp','admission.hpp','pending_survival.inc','survival_identity.hpp','survival_writer.inc')}
    required |= {'pipeline/live_draft.hpp','pipeline/operator_state.hpp',
                 'pipeline/ring/persistent_reset.inc','pipeline/ring/reset_descriptor.hpp'}
    if capture_overlap:required.add('pipeline/recursive_provider/capture_ready.hpp')
    # Remote native capability is additionally checked through its build receipt.
    if provider_stage:required.add('pipeline/recursive_provider/seed_peer.hpp')
    base.require(required <= set(receipt.get('sources',{})), 'complete native pending-provider capability required')
    adapter = suite_tools.evidence.read_json(config['adapter_plan'],4*1024**2)
    draft = adapter['rank_argv'][0]
    base.require('--draft-mtp' in draft and base.option(draft,'--draft-fault') == 'none', 'fault-free existing draft authority')
    manifest = Path(base.option(draft,'--draft-manifest')).resolve()
    expected = config.get('trusted_draft_manifest_sha256')
    base.require(isinstance(expected,str) and re.fullmatch('[0-9a-f]{64}',expected)
        and base.digest(manifest) == expected, 'selected draft manifest differs from explicit trusted SHA')
    identity = dict(model=plan['model_identity_sha256'],draft_manifest=expected,
        draft_experts=base.option(draft,'--draft-experts'),prompt=plan['prompt_tokens'],
        context=plan['context'],max_new=plan['max_new'],vocab=plan['vocab'],eos=eos,
        config_sha256=base.digest(config_path),mode='persistent-rolling',check_policy=policy,
        reference_route_tie_sort=plan.get('reference_route_tie_sort',False),
        reference_route_scope=plan.get('reference_route_scope','f32-target-only'),
        draft_route_policy=plan.get('draft_route_policy','unchanged-bf16'))
    request = sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    final_shared = str(Path(plan['output'])/f"stage{len(plan['stages'])-1}/shared.bin")
    for stage in plan['stages']:
        base.require(not any(flag in stage['argv'] for flag in ('--pipeline-ring-recursive-flat-copy',
            '--pipeline-provider-stage','--pipeline-ring-seed-shared','--pipeline-ring-depth')),
            'provider options must be selected by config, not inherited adapter flags')
        base.require(not any(f in stage['argv'] for f in ('--pipeline-wavefront','--pipeline-live-draft',
            '--pipeline-ring','--draft-mtp')), 'rolling must not inherit another controller')
        for env in ('OWNRT_DRAFT_DEPTH_PROBE','OWNRT_DRAFT_DEPTH_VERIFY'):
            stage['environment'].pop(env,None)
        stage['argv'] += ['--pipeline-ring','--pipeline-ring-request-sha256',request,
            '--pipeline-ring-live-draft','--pipeline-ring-pending-provider',
            '--pipeline-ring-persistent-requests','--pipeline-ring-check-policy',policy]
        base.require('--oracle' not in stage['argv'] or base.option(stage['argv'],'--oracle')=='',
                     'persistent runtime accepts no oracle file')
        if speculative_depth==3:stage['argv'] += ['--pipeline-ring-depth','3']
        if verify:stage['argv'].append('--pipeline-ring-verify-restore')
        if provider_stage:stage['argv'] += ['--pipeline-provider-stage',str(provider_stage)]
        if stage['id'] == provider_stage:
            if provider_stage:stage['argv'] += ['--pipeline-ring-seed-shared',str(Path(plan['output'])/'stage0/shared.bin')]
            if recursive_flat_copy:stage['argv'].append('--pipeline-ring-recursive-flat-copy')
            if capture_overlap:stage['argv'].append('--pipeline-ring-parent-capture-ack')
            stage['argv'] += ['--pipeline-ring-final-shared',final_shared,'--draft-mtp']
            if verify:stage['argv'] += ['--pipeline-ring-recursive-verify-restore','--pipeline-ring-verify-provider-survival']
            for flag in ('--draft-fault','--draft-manifest','--draft-model','--draft-experts'):
                stage['argv'] += [flag,base.option(draft,flag)]
            stage['argv'] = base.replace_options(stage['argv'],{'--draft-rank':0})
    folder = live.wire.PLANNING/'rolling_provider'
    dependencies = [Path(module.__file__).resolve() for module in
        (bridge,bridge.pending,bridge.pending.pending_codec,live,live.codec,live.target,
         live.wire,base,live.target.lifecycle)]
    dependencies += [Path(__file__).resolve(),Path(suite_tools.__file__).resolve(),
        Path(suite_tools.evidence.__file__).resolve(),Path(suite_tools.evidence.live.__file__).resolve(),
        Path(suite_tools.rolling.__file__).resolve(),folder/'__init__.py',folder/'coordinator.py',folder/'arbiter.py',folder/'capture_ready.py',folder/'remote.py',folder/'prefill.py',
        live.wire.PLANNING/'ring_coordinator.py',live.wire.PLANNING/'ring_contract.py',
        live.wire.PLANNING/'live_draft.py',live.target.lifecycle.SCHEDULE_PATH,manifest,
        base.ROOT/'experiments/own-xpu-runtime/ops/packet196-window/passive_device_holders.py',
        base.ROOT/'experiments/own-xpu-runtime/stage1/packet4-prep/driver/window_driver.py']
    for path in dependencies:
        plan['pins'][str(path)] = base.digest(path)
    plan.update(schema='ownrt.persistent-rolling-plan.v1',mode='persistent-rolling',check_policy=policy,
        epoch=0,request_sha256=request,eos_token_ids=eos,rolling_depth2=True,use_proposals=True,
        live_draft=True,draft_training=False,draft_model_sha256=expected,draft_experts=identity['draft_experts'],
        config_sha256=identity['config_sha256'],verify_restore=verify,verify_recursive_restore=verify,
        verify_provider_survival=verify,final_shared=final_shared,diagnostic_only=verify,speed_claim=False,
        limits='Opt-in lab qualification; actual depth2 guesses, complete diagnostic verification. Independent rolling GPU state/provenance proof required. Not portable or a speed benchmark.')
    suite_path=Path(config['suite']).resolve()
    raw=suite_tools.evidence.read_bounded(suite_path,4*1024**2)
    base.require(sha256(raw).hexdigest()==config['suite_sha256'],'independently pinned runtime-only inputs')
    count=config.get('suite_prompt_count')
    rows=suite_tools.validate_suite(json.loads(raw),plan,count)
    base.require(plan['prompt_tokens']==rows[0]['prompt_tokens'],'first prompt/config identity')
    # DepthD: <=(D+1)N ROW + N ACCEPT + DN ABORT, i.e. (2D+2)N.
    # Default depth2 keeps6N; opt-in depth3 requires8N. Provider trace is separate.
    trace_budgets=[dict(id=row['id'],input_positions=len(row['prompt_tokens'])+row['max_new']-1,
        target_commands=(2*speculative_depth+2)*(len(row['prompt_tokens'])+row['max_new']-1),
        provider_commands=len(row['prompt_tokens'])+row['max_new']-2) for row in rows]
    trace_required=max(row['target_commands'] for row in trace_budgets)
    explicit_trace='ring_trace_limit' in config
    base.require(explicit_trace or (count<=2 and trace_required<=4096),
                 'long suite requires explicit ring_trace_limit')
    trace_limit=config.get('ring_trace_limit',4096)
    base.require(type(trace_limit) is int and 1<=trace_limit<=100000,
                 'native trace limit integer bound1..100000')
    base.require(trace_required<=100000,'worst-case trace budget exceeds native100000 cap')
    base.require(trace_limit>=trace_required,'ring trace limit below worst-case request budget')
    for stage in plan['stages']:
        stage['argv']=base.replace_options(stage['argv'],{'--pipeline-ring-trace-limit':trace_limit})
    plan.update(ring_trace_limit=trace_limit,ring_trace_required=trace_required,
        ring_trace_budget=trace_budgets,ring_trace_limit_explicit=explicit_trace)
    dump_each=config.get('dump_each')
    base.require(type(dump_each) is bool and (not dump_each or count<=2),'full dumps bounded to two requests')
    if verify:
        base.require(count==2 and plan['max_new']<=32 and dump_each,
                     'initial qualification is two cold requests, <=32 outputs, full per-request state')
    else:
        base.require(config.get('measured_policy_admitted') is True,
                     'measured policy requires explicit separate admission')
    plan.update(persistent_requests=True,suite=str(suite_path),suite_sha256=config['suite_sha256'],
        suite_prompt_count=count,dump_each=dump_each,admitted_max_new=config['admitted_max_new'],
        limits='One fixed-policy loaded worker set; runtime prompts contain no expected answers. Cold native reset/state and measured-policy parity require independent qualification. No portable/service or speed certification.')
    plan['pins'][str(suite_path)]=config['suite_sha256']
    if speculative_depth==3:plan['speculative_depth']=3
    if provider_stage:plan['provider_stage']=provider_stage
    if recursive_flat_copy:plan['recursive_flat_copy']=True
    if capture_overlap:plan['capture_ready_overlap']=True
    return plan



def execute(plan, admission, unit):
    try:
        live.target.lifecycle.execute(plan,admission,unit,stage_type=bridge.Stage,
            driver=suite_tools.run,scripted_proposals=False)
    finally:
        original=Path(plan['output'])/'result.json'
        if original.is_file():
            result=suite_tools.evidence.read_json(original,16*1024**2)
            result.update(schema='ownrt.persistent-rolling-result.v1',mode='persistent-rolling',
                check_policy=plan['check_policy'],diagnostic_only=plan['check_policy']=='qualification',
                actual_provider=True,scripted_oracle_assisted=False,draft_training=False,speed_claim=False,
                lifecycle_result_sha256=base.digest(original),plan_sha256=base.digest(Path(plan['output'])/'plan.json'),
                qualification_note='Controller completion only; independent reset/state/provenance/output audit required.')
            base.save(Path(plan['output'])/'persistent-rolling-result.json',result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--admission',type=Path)
    parser.add_argument('--unit')
    args=parser.parse_args()
    if not args.run:
        base.require(args.config is not None,'CPU plan config required')
        base.save(args.plan,make_plan(args.config))
        print(json.dumps(dict(plan=str(args.plan),sha256=base.digest(args.plan),device_execution_requested=False)))
        return
    base.require(args.admission is not None and args.unit,'explicit admission and owning unit required')
    plan=suite_tools.evidence.read_json(args.plan,8*1024**2)
    base.require(plan==make_plan(plan['config']),'persistent plan/source/inputs changed')
    admission=suite_tools.evidence.read_json(args.admission)
    base.require(admission['plan_sha256']==base.digest(args.plan),'admission plan SHA mismatch')
    execute(plan,admission,args.unit)


if __name__=='__main__':main()

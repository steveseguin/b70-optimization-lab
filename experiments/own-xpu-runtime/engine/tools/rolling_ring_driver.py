#!/usr/bin/env python3
"""Opt-in rolling qualification launcher; diagnostic research mode.

CPU planning is the default. Execution requires an explicit run switch and
source-bound owner admission, using the existing guarded lifecycle unchanged.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'planning'))
from rolling_provider import transport as bridge

base, live = bridge.base, bridge.pending.live


def make_plan(config_path):
    config = live.load_json(config_path)
    base.require(config.get('rolling_depth2') is True and config.get('use_proposals') is True,
                 'explicit rolling qualification required')
    base.require(not any(k in config for k in ('recursive_reference','scripted_proposal_tokens',
        'force_miss_positions','expected_outputs','pending_cases')), 'rolling config accepts no reference/oracle inputs')
    base.require(config.get('verify_recursive_restore') is True and config.get('verify_restore') is True
        and config.get('verify_provider_survival') is True, 'initial rolling qualification requires all diagnostic verification')
    plan = base.make_plan(config_path)
    base.require(len(plan['stages']) in (2,4,6) and 1 <= plan['max_new'] <= 32,
                 'initial rolling proof supports2/4/6 owners and at most32 output tokens')
    eos = config.get('eos_token_ids')
    base.require(isinstance(eos,list) and eos and len(set(eos)) == len(eos) and plan['eos'] in eos
        and all(type(t) is int and 0 <= t < plan['vocab'] for t in eos), 'explicit complete EOS set')
    receipt = live.load_json(config['build_receipt'])
    required = {'pipeline/ring/'+n+'.hpp' for n in ('stage_ring','wire','checkpoint_ring','engine_backend','dispatcher')}
    required |= {'pipeline/recursive_provider/'+n for n in ('batch.hpp','draft_runtime_extension.inc',
        'final_event.hpp','peer.hpp','admission.hpp','pending_survival.inc','survival_identity.hpp','survival_writer.inc')}
    required |= {'pipeline/live_draft.hpp','pipeline/operator_state.hpp'}
    base.require(required <= set(receipt.get('sources',{})), 'complete native pending-provider capability required')
    adapter = live.load_json(config['adapter_plan'])
    draft = adapter['rank_argv'][0]
    base.require('--draft-mtp' in draft and base.option(draft,'--draft-fault') == 'none', 'fault-free existing draft authority')
    manifest = Path(base.option(draft,'--draft-manifest')).resolve()
    expected = config.get('trusted_draft_manifest_sha256')
    base.require(isinstance(expected,str) and re.fullmatch('[0-9a-f]{64}',expected)
        and base.digest(manifest) == expected, 'selected draft manifest differs from explicit trusted SHA')
    identity = dict(model=plan['model_identity_sha256'],draft_manifest=expected,
        draft_experts=base.option(draft,'--draft-experts'),prompt=plan['prompt_tokens'],
        context=plan['context'],max_new=plan['max_new'],vocab=plan['vocab'],eos=eos,
        config_sha256=base.digest(config_path),mode='rolling-ring-live-depth2-qualification')
    request = sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    final_shared = str(Path(plan['output'])/f"stage{len(plan['stages'])-1}/shared.bin")
    for stage in plan['stages']:
        base.require(not any(f in stage['argv'] for f in ('--pipeline-wavefront','--pipeline-live-draft',
            '--pipeline-ring','--draft-mtp')), 'rolling must not inherit another controller')
        for env in ('OWNRT_DRAFT_DEPTH_PROBE','OWNRT_DRAFT_DEPTH_VERIFY'):
            stage['environment'].pop(env,None)
        stage['argv'] += ['--pipeline-ring','--pipeline-ring-request-sha256',request,
            '--pipeline-ring-live-draft','--pipeline-ring-pending-provider','--pipeline-ring-verify-restore']
        if stage['first']:
            stage['argv'] += ['--pipeline-ring-recursive-verify-restore','--pipeline-ring-verify-provider-survival',
                '--pipeline-ring-final-shared',final_shared,'--draft-mtp']
            for flag in ('--draft-fault','--draft-manifest','--draft-model','--draft-experts'):
                stage['argv'] += [flag,base.option(draft,flag)]
            stage['argv'] = base.replace_options(stage['argv'],{'--draft-rank':0})
    folder = live.wire.PLANNING/'rolling_provider'
    dependencies = [Path(module.__file__).resolve() for module in
        (bridge,bridge.pending,bridge.pending.pending_codec,live,live.codec,live.target,
         live.wire,base,live.target.lifecycle)]
    dependencies += [Path(__file__).resolve(),folder/'__init__.py',folder/'coordinator.py',folder/'arbiter.py',folder/'capture_ready.py',folder/'prefill.py',
        live.wire.PLANNING/'ring_coordinator.py',live.wire.PLANNING/'ring_contract.py',
        live.wire.PLANNING/'live_draft.py',live.target.lifecycle.SCHEDULE_PATH,manifest,
        base.ROOT/'experiments/own-xpu-runtime/ops/packet196-window/passive_device_holders.py',
        base.ROOT/'experiments/own-xpu-runtime/stage1/packet4-prep/driver/window_driver.py']
    for path in dependencies:
        plan['pins'][str(path)] = base.digest(path)
    plan.update(schema='ownrt.rolling-driver-plan.v1',mode='rolling-ring-live-depth2-qualification',
        epoch=0,request_sha256=request,eos_token_ids=eos,rolling_depth2=True,use_proposals=True,
        live_draft=True,draft_training=False,draft_model_sha256=expected,draft_experts=identity['draft_experts'],
        config_sha256=identity['config_sha256'],verify_restore=True,verify_recursive_restore=True,
        verify_provider_survival=True,final_shared=final_shared,diagnostic_only=True,speed_claim=False,
        limits='Opt-in lab qualification; actual depth2 guesses, complete diagnostic verification. Independent rolling GPU state/provenance proof required. Not portable or a speed benchmark.')
    return plan


def execute(plan, admission, unit):
    # No optional application cancellation callback is exposed here. Guard stop
    # and faults retain the established cooperative exception/shutdown path.
    try:
        live.target.lifecycle.execute(plan,admission,unit,stage_type=bridge.Stage,
            driver=bridge.drive,scripted_proposals=False)
    finally:
        original = Path(plan['output'])/'result.json'
        if original.is_file():
            result = live.load_json(original)
            result.update(schema='ownrt.rolling-driver-result.v1',
                mode='rolling-ring-live-depth2-qualification',actual_provider=True,
                scripted_oracle_assisted=False,draft_training=False,diagnostic_only=True,speed_claim=False,
                lifecycle_result_sha256=base.digest(original),
                plan_sha256=base.digest(Path(plan['output'])/'plan.json'),
                qualification_note='Controller completion only; independent rolling provenance/target/canonical73/native survival qualification required.')
            base.save(Path(plan['output'])/'rolling-ring-live-result.json',result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--admission',type=Path)
    parser.add_argument('--unit')
    args = parser.parse_args()
    if not args.run:
        base.require(args.config is not None,'config required for CPU planning')
        base.save(args.plan,make_plan(args.config))
        print(json.dumps(dict(plan=str(args.plan),sha256=base.digest(args.plan),device_execution_requested=False)))
        return
    base.require(args.admission is not None and args.unit,'explicit owner admission and bounded unit required')
    plan = live.load_json(args.plan)
    base.require(plan == make_plan(plan['config']),'plan/source/config/native identity changed')
    admission = live.load_json(args.admission)
    base.require(admission['plan_sha256'] == base.digest(args.plan),'admission plan mismatch')
    execute(plan,admission,args.unit)


if __name__ == '__main__': main()

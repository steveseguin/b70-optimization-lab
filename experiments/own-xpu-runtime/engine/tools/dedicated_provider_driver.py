#!/usr/bin/env python3
"""Plan or explicitly run separate target stages plus an existing MTP owner."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

import pipeline_driver as base
import dedicated_provider_lifecycle as lifecycle


def make_plan(path):
    path = Path(path).resolve()
    config = json.loads(path.read_text())
    base.require(config.get('dedicated_provider') is True, 'explicit separate-provider opt-in')
    bulk=config.get('dedicated_bulk_prefill',False)
    base.require(type(bulk) is bool and not config.get('prefill_pipeline',False)
                 and not config.get('persistent_reset',False),'dedicated sequential bulk/no reset admission')
    pipeline=config.get('dedicated_prefill_pipeline',False)
    base.require(type(pipeline) is bool and (not pipeline or bulk),
                 'dedicated_prefill_pipeline Boolean requires authenticated bulk')
    rows=config.get('prefill_rows',256 if bulk else 0)
    base.require(type(rows) is int and (rows==256 if bulk else rows==0),
                 'explicit dedicated bulk256 or per-token0 rows')
    capture = config.get('dedicated_capture_ready', False)
    base.require(type(capture) is bool, 'dedicated_capture_ready Boolean required')
    plan = base.make_plan(path)
    base.require(len(plan['stages']) in (2, 3), 'two/three target stages required')
    base.require(not pipeline or len(plan['stages'])==3, 'dedicated prefill pipeline requires three target stages')
    bdfs = [s['bdf'] for s in plan['stages']]
    provider_bdf = config['provider_bdf']
    base.require(all(re.fullmatch(r'0000:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]', x)
                     for x in bdfs+[provider_bdf]), 'canonical physical BDF syntax')
    base.require(provider_bdf not in bdfs, 'provider must use a separate card')
    depth = config.get('speculative_depth', 3)
    base.require(type(depth) is int and depth in (2, 3), 'dedicated depth bound')
    policy = config.get('check_policy', 'qualification')
    base.require(policy in ('qualification', 'measured'), 'fixed check policy')
    full = policy == 'qualification'
    eos = config['eos_token_ids']
    base.require(isinstance(eos, list) and eos and len(eos) == len(set(eos)) and
                 all(type(t) is int and 0 <= t < plan['vocab'] for t in eos), 'EOS token set')
    receipt = json.loads(Path(config['build_receipt']).read_text())
    required = {'pipeline/provider_only/'+name for name in
                ('bootstrap.inc', 'owner.hpp', 'runtime.hpp', 'wire.hpp', 'peers.hpp')}
    if bulk:required.add('pipeline/provider_only/prefill.hpp')
    base.require(required <= set(receipt['sources']), 'compiled dedicated provider capability')
    adapter = json.loads(Path(config['adapter_plan']).read_text())
    draft = adapter['rank_argv'][0]
    base.require('--draft-mtp' in draft and base.option(draft, '--draft-fault') == 'none',
                 'existing fault-free MTP authority')
    base.require('--draft-head' not in draft or base.option(draft, '--draft-head') == 'full',
                 'dedicated provider requires the existing full draft head')
    manifest = Path(base.option(draft, '--draft-manifest')).resolve()
    manifest_sha = config['trusted_draft_manifest_sha256']
    base.require(base.digest(manifest) == manifest_sha, 'trusted draft manifest changed')
    identity = dict(model=plan['model_identity_sha256'], draft_manifest=manifest_sha,
                    prompt=plan['prompt_tokens'], context=plan['context'], max_new=plan['max_new'],
                    vocab=plan['vocab'], eos=eos, depth=depth, boundaries=config['boundaries'],
                    target_bdfs=bdfs, provider_bdf=provider_bdf, check_policy=policy,
                    config_sha256=base.digest(path), mode='dedicated-mtp')
    prompt_path=None
    if bulk:
        from rolling_provider import dedicated_prefill
        base.require(len(plan['prompt_tokens'])-2>=rows,'dedicated prefix must contain at least one bulk chunk')
        prompt_path=Path(config['dedicated_prefill_prompt']).resolve()
        base.require(str(prompt_path)==config['dedicated_prefill_prompt'], 'canonical absolute immutable prompt path')
        prompt_sha=config['dedicated_prefill_prompt_sha256']
        dedicated_prefill.prompt_source(dict(plan,dedicated_prefill_prompt=str(prompt_path),
                                           dedicated_prefill_prompt_sha256=prompt_sha))
        identity.update(dedicated_bulk_prefill=True,prefill_rows=rows,prompt_i32_sha256=prompt_sha)
    if pipeline:identity['dedicated_prefill_pipeline']=True
    request = sha256(base.canonical(identity)).hexdigest()
    output = Path(plan['output'])
    provider = deepcopy(plan['stages'][0])
    provider.update(id='provider', role='dedicated-mtp', first=False, final=False,
                    bdf=provider_bdf, native_output=str(output/'stageprovider/native'))
    for key in ('begin', 'end', 'packed_weight_bytes'):
        provider.pop(key)
    provider['argv'] = base.replace_options(provider['argv'],
        {'--rank': 0, '--output': provider['native_output'], '--shared': output/'stageprovider/shared.bin'},
        remove={'--pipeline-boundaries', '--pipeline-stage'})
    provider['argv'] += ['--provider-only', '--provider-bdf', provider_bdf,
        '--provider-target-bdfs', ','.join(bdfs), '--provider-seed-shared', str(output/'stage0/shared.bin'),
        '--provider-final-shared', str(output/f"stage{len(bdfs)-1}/shared.bin"),
        '--pipeline-ring-request-sha256', request, '--pipeline-ring-depth', str(depth),
        '--pipeline-ring-check-policy', policy, '--draft-mtp']
    if bulk:
        provider['argv'] += ['--provider-prefill-rows',str(rows),
            '--provider-prefill-prompt',str(prompt_path),'--provider-prefill-prompt-sha256',prompt_sha,
            '--provider-prefill-seed-shared',str(output/'stage0/prefill.bin'),
            '--provider-prefill-final-shared',str(output/f'stage{len(bdfs)-1}/prefill.bin')]
    if capture:
        provider['argv'].append('--provider-capture-ready')
    if full:
        provider['argv'].append('--pipeline-ring-recursive-verify-restore')
    for flag in ('--draft-fault', '--draft-manifest', '--draft-model', '--draft-experts'):
        provider['argv'] += [flag, base.option(draft, flag)]
    provider['environment']['FilterBdfPath'] = provider_bdf
    for key, directory in [('SYCL_CACHE_DIR', 'sycl'), ('NEO_CACHE_DIR', 'neo'), ('XDG_CACHE_HOME', 'xdg')]:
        provider['environment'][key] = str(output/'stageprovider/cache'/directory)
    trace = config.get('ring_trace_limit', 100000)
    base.require(type(trace) is int and 1 <= trace <= 100000, 'bounded native trace')
    for stage in plan['stages']:
        stage['role'] = 'target'
        stage['argv'] += ['--pipeline-ring', '--pipeline-external-provider',
            '--pipeline-ring-persistent-requests', '--pipeline-ring-check-policy', policy,
            '--pipeline-ring-request-sha256', request, '--pipeline-ring-depth', str(depth),
            '--pipeline-ring-trace-limit', str(trace)]
        if bulk:
            stage['argv'] += ['--prefill-rows',str(rows),'--prefill-shared',str(output/f"stage{stage['id']}/prefill.bin"),
                '--provider-prefill-prompt',str(prompt_path),'--provider-prefill-prompt-sha256',prompt_sha]
        if full:
            stage['argv'].append('--pipeline-ring-verify-restore')
    for stage in plan['stages']+[provider]:
        for name in ('OWNRT_DRAFT_DEPTH_PROBE', 'OWNRT_DRAFT_DEPTH_VERIFY'):
            stage['environment'].pop(name, None)
        base.require('--oracle' not in stage['argv'] or base.option(stage['argv'], '--oracle') == '',
                     'runtime must not consume expected outputs')
    plan.update(schema='ownrt.dedicated-provider-plan.v1', mode='dedicated-mtp', provider=provider,
                epoch=0, request_sha256=request, dedicated_capture_ready=capture,
                dedicated_prefill_pipeline=pipeline, eos_token_ids=eos, speculative_depth=depth,
                rolling_depth2=True, use_proposals=True, check_policy=policy, prefill_rows=rows,
                prefill_pipeline=False, verify_restore=full, verify_recursive_restore=full,
                draft_model_sha256=manifest_sha, draft_training=False, speed_claim=False,
                limits='Experimental independent provider; per-token prompt only. No archived replay or reset claim.')
    if bulk:
        plan.update(dedicated_bulk_prefill=True,dedicated_prefill_prompt=str(prompt_path),
                    dedicated_prefill_prompt_sha256=prompt_sha,prefill_stream_bytes=base.PREFILL_STREAM_BYTES,
                    limits='Experimental authenticated sequential dedicated prefix replay; no overlapped-bulk/reset/speed claim.')
        if pipeline:
            plan['limits']='Experimental two-chunk target-stage/dedicated replay pipeline; full OP28 ACK leases; no reset/speed claim.'
        plan['pins'][str(prompt_path)]=prompt_sha
    # Pin the actual transitive Python controller stack, without model or credential discovery.
    from rolling_provider import dedicated_transport
    modules = (dedicated_transport, dedicated_transport.pending, dedicated_transport.codec,
               dedicated_transport.pending.pending_codec, lifecycle, base)
    files = {Path(m.__file__).resolve() for m in modules}
    files |= set((base.HERE.parent/'planning/rolling_provider').glob('*.py'))
    files |= {base.HERE.parent/'planning'/name for name in
              ('ring_contract.py', 'ring_coordinator.py', 'live_draft.py')}
    files |= {base.HERE/name for name in ('ring_wire.py', 'ring_driver.py', 'wavefront_driver.py',
              'ring_live_driver.py', 'pending_ring_live_driver.py', 'pending_provider_wire.py')
              if (base.HERE/name).exists()}
    files |= {Path(__file__).resolve(), manifest}
    if pipeline:
        from rolling_provider import dedicated_prefill_pipeline
        files.add(Path(dedicated_prefill_pipeline.__file__).resolve())
    for source in files:
        plan['pins'][str(source)] = base.digest(source)
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--admission', type=Path)
    parser.add_argument('--unit')
    args = parser.parse_args()
    if not args.run:
        base.require(args.config is not None, 'config required')
        plan = make_plan(args.config)
        base.save(args.plan, plan)
        print(json.dumps(dict(plan=str(args.plan), sha256=base.digest(args.plan), device_execution_requested=False)))
        return
    base.require(args.admission is not None and args.unit, 'explicit admission and controlled unit required')
    plan = json.loads(args.plan.read_text())
    base.require(plan == make_plan(plan['config']), 'plan/source/runtime identity changed')
    admission = json.loads(args.admission.read_text())
    base.require(admission.get('plan_sha256') == base.digest(args.plan), 'admission plan hash')
    print(json.dumps(lifecycle.execute(plan, admission, args.unit)))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""One-load serial/pipelined prefill parity. Planning is CPU-only by default."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
LAN = ROOT/'experiments/own-xpu-runtime/gsq-rco-iq3s/serving/lan'
TOOLS = ROOT/'experiments/own-xpu-runtime/engine/tools'
ATTACH = Path(__file__).with_name('attach_prefill_provenance.py').resolve()
MODES = [{'epoch': 1, 'prefill_pipeline': False}, {'epoch': 2, 'prefill_pipeline': True}]


def dependencies():
    sys.path.insert(0, str(LAN))
    import pp4_backend as backend
    import chat
    return backend, chat


def selected_plan(plan, epoch):
    if epoch not in (1, 2):
        raise ValueError('exactly two registered request epochs required')
    return dict(plan, prefill_pipeline=MODES[epoch-1]['prefill_pipeline'])


def pair(position, token, hidden):
    return dict(position=position, token=token, hidden_bytes=len(hidden),
                hidden_sha256=sha256(hidden).hexdigest())


def validate_pairs(pairs, position):
    if [p['position'] for p in pairs] != list(range(1, position)):
        raise ValueError('complete ordered canonical pair trace required')
    return sha256(json.dumps(pairs, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def prepare(config_path, prompt_path, control):
    B, chat = dependencies()
    control.mkdir(mode=0o700)  # exclusive; native output stays nonexistent
    parsed = chat.parse(dict(messages=[dict(role='user', content=prompt_path.read_text())],
                             max_tokens=32, thinking=False), chat.Chat())
    tokens = parsed['prompt_ids']
    if len(tokens)-2 <= 5*B.PREFILL_ROWS or (len(tokens)-2) % B.PREFILL_ROWS == 0:
        raise ValueError('prompt must span >5 chunks with a partial tail')
    config = json.loads(config_path.read_text())
    if config['check_policy'] != 'qualification' or not config['dump_each']:
        raise ValueError('fixed native qualification and dump_each required')
    suite = dict(schema='ownrt.persistent-rolling-inputs.v1',
                 **{k: json.loads(Path(config['suite']).read_text())[k]
                    for k in ('model_identity_sha256', 'activation_dtype', 'eos_token_ids')},
                 prompts=[dict(id=name, prompt_tokens=tokens, max_new=32)
                          for name in ('serial', 'pipeline')])
    B.base.save(control/'suite.json', suite)
    config.update(output=str(control/'output'), prompt_tokens=tokens, max_new=32,
                  admitted_max_new=32, suite=str(control/'suite.json'),
                  suite_sha256=B.base.digest(control/'suite.json'), suite_prompt_count=2)
    B.base.save(control/'config.json', config)
    plan = make_plan(control/'config.json')
    plan['gate_prompt_source'] = dict(path=str(prompt_path.resolve()), sha256=B.base.digest(prompt_path))
    B.base.save(control/'plan.json', plan)
    return plan


def make_plan(config):
    B, _ = dependencies()
    plan = B.make_plan(config)
    plan.update(prefill_gate_modes=MODES, prefill_pipeline=False)
    plan['pins'][str(Path(__file__).resolve())] = B.base.digest(Path(__file__).resolve())
    plan['pins'][str(ATTACH)] = B.base.digest(ATTACH)
    return plan


def compare_completed(plan, base, manifests):
    # wavefront_driver.execute returns None; its final result is written only
    # after FINISH, process joins and the final passive guard check.
    output = Path(plan['output'])
    terminal = json.loads((output/'result.json').read_text())
    expected = {str(stage['id']) for stage in plan['stages']}
    base.require(terminal.get('passed') is True and terminal.get('error') is None
        and terminal.get('live_pids') == []
        and set(terminal.get('returncodes', {})) == expected
        and all(type(code) is int and code == 0 for code in terminal['returncodes'].values()),
        'completed clean lifecycle required before provenance or comparison')
    base.require(len(manifests) == 2, 'both serial/pipeline manifests required')
    import attach_prefill_provenance
    import compare_pipeline_state as target_compare
    import compare_draft_state as draft_compare
    completed = [attach_prefill_provenance.attach(p) for p in manifests]
    target = target_compare.compare(*(target_compare.load_set(p) for p in completed))
    draft = draft_compare.compare(*(draft_compare.load_set(p.parent/'draft-set.json') for p in manifests))
    base.save(output/'target-comparison.json', target)
    base.save(output/'draft-comparison.json', draft)
    base.require(target['passed'] and draft['passed'], 'serial/pipeline sealed state parity failed')
    return dict(target=target, draft=draft)


def execute(plan, admission, unit):
    B, _ = dependencies()
    bridge, base = B.bridge, B.base
    pairs = []
    manifests = []
    class Stage(bridge.Stage):
        def command(self, op, token=0, position=0, fixture=0, **kwargs):
            item = None
            if op == 9:
                item = pair(position, token, bytes(self.shared[2*base.SLOT+4096:
                                      2*base.SLOT+4096+self.stream_bytes]))
            result = super().command(op, token, position, fixture, **kwargs)
            if item is not None:
                pairs.append(item)
            return result

        def issue_provider(self, command):
            item = pair(command.seed.row.position, command.seed.row.token,
                        command.parent.handoff.hidden)
            result = super().issue_provider(command)
            pairs.append(item)
            return result

    def drive(stages, request_plan, guard, destination, *, epoch):
        pairs.clear()
        chosen = selected_plan(request_plan, epoch)
        base.save(destination/'selected-request-plan.json', chosen)
        for stage in stages:
            stage.plan = chosen
        result = bridge.drive(stages, chosen, guard, destination, epoch=epoch)
        digest = validate_pairs(pairs, result['input_position'])
        base.save(destination/'canonical-pairs.json', dict(pairs=pairs, sha256=digest))
        return result

    def run(stages, run_plan, guard, output):
        result = B.rolling.run(stages, run_plan, guard, output, drive=drive)
        for index, record in enumerate(result['requests']):
            folder = output/f"request-{index:02d}-{record['id']}"
            actual = json.loads((folder/'canonical-pairs.json').read_text())
            identity = dict(model_sha256=plan['model_identity_sha256'],
                draft_model_sha256=plan['draft_model_sha256'], pair_sequence_sha256=actual['sha256'],
                position=record['driver_result']['input_position']-1,
                arithmetic='F32-target/BF16-draft', context=plan['context'], vocab=plan['vocab'],
                draft_experts=plan['draft_experts'])
            target = dict(schema='ownrt.pipeline-state-set.v7', mode='persistent-rolling',
                controller_mode='persistent-rolling', actual_proposals_only=True, speculative_depth=3,
                verification_policy='qualification', layer_count=48, require_byte_verified_restores=True,
                require_provider_byte_verified_restores=True, provider_borrow_mode='pending-target',
                require_provider_survival_checks=True, required_provider_pending_depths=[],
                draft_input_identity=identity, ring_request_sha256=record['request_sha256'],
                ring_epoch=record['epoch'], input_identity=dict(model_sha256=plan['model_identity_sha256'],
                prompt_token_sha256=record['prompt_token_sha256'], output_token_sha256=record['output_token_sha256'],
                arithmetic='F32', position=record['driver_result']['input_position']), stages=[])
            draft_path = folder/'draft-set.json'
            for spec, receipt in zip(plan['stages'], record['reset_receipts']):
                native = Path(receipt['native_output'])
                dump = native/f'state-{2000000000+index}'
                item = dict(id=spec['id'], begin=spec['begin'], end=spec['end'], dump=str(dump),
                    plan=str(Path(spec['native_output'])/'launch-plan.json'),
                    metadata=str(native/'pipeline-stage.json'), quiescence=str(dump)+'.ring-state.json')
                if spec['id'] == 0:
                    item.update(draft_state_set=str(draft_path), provider_survival=str(native/'ring-provider-survival.jsonl'))
                    base.save(draft_path, dict(schema='ownrt.draft-state-set.v1', dump=str(dump)+'.draft', input_identity=identity))
                target['stages'].append(item)
            manifest = folder/'target-set.json'
            base.save(manifest, target)
            manifests.append(manifest)
        return result
    B.rolling_driver.live.target.lifecycle.execute(plan, admission, unit, stage_type=Stage,
                                                   driver=run, scripted_proposals=False)
    return compare_completed(plan, base, manifests)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', type=Path)
    ap.add_argument('--prompt', type=Path, default=Path('/dev/shm/pp4-review-original-current-20261028.txt'))
    ap.add_argument('--control', type=Path, required=True)
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--admission', type=Path)
    ap.add_argument('--unit')
    args = ap.parse_args()
    if not args.run:
        prepare(args.config, args.prompt, args.control)
        return
    B, _ = dependencies()
    path = args.control/'plan.json'
    plan = json.loads(path.read_text())
    expected = make_plan(args.control/'config.json')
    expected['gate_prompt_source'] = plan['gate_prompt_source']
    B.base.require(plan == expected, 'gate plan/source drift')
    B.base.require(B.base.digest(Path(plan['gate_prompt_source']['path'])) == plan['gate_prompt_source']['sha256'], 'gate prompt drift')
    admission = json.loads(args.admission.read_text())
    B.validate_admission(path, plan, admission)
    execute(plan, admission, args.unit)


if __name__ == '__main__':
    main()

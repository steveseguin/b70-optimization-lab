#!/usr/bin/env python3
"""Actual existing-MTP depth-two qualification with quiescent verified targets.

No draft guess is used as a target input. The first-stage provider independently
reads the final owner's immutable commit record. No training or speed claim.
"""
import argparse
from hashlib import sha256
import json
import re
from pathlib import Path
import select
import struct
import time

import ring_driver as target
import ring_live_wire as codec

base, wire, ring = target.base, codec.wire, codec.ring


def load_json(path, cap=4*1024**2):
    with Path(path).open('rb') as source:
        raw = source.read(cap+1)
    base.require(0 < len(raw) <= cap, 'bounded JSON input')
    return json.loads(raw)


def validate_reference(reference, plan):
    base.require(reference.get('schema') == 'ownrt.recursive-provider-reference.v1'
                 and reference.get('passed') is True, 'qualified recursive provider reference')
    prompt = plan['prompt_tokens']
    # The retained reference builder hashes compact JSON token arrays.
    prompt_sha = sha256(json.dumps(prompt, separators=(',', ':')).encode()).hexdigest()
    base.require(reference['prompt_tokens'] == len(prompt)
                 and reference['target_prompt_token_sha256'] == prompt_sha
                 and reference['output_tokens'] == plan['max_new'], 'reference prompt/output identity')
    identity = reference['canonical_draft_input_identity']
    base.require(identity['model_sha256'] == plan['model_identity_sha256']
                 and identity['context'] == plan['context'] and identity['vocab'] == plan['vocab']
                 and identity['arithmetic'] == 'F32-target/BF16-draft', 'reference model/arithmetic geometry')
    outputs = reference['target_output_ids']
    base.require(len(outputs) == plan['max_new'] and all(type(t) is int and 0 <= t < plan['vocab'] for t in outputs),
                 'reference complete target outputs')
    pairs, depths = reference['canonical_pairs'], reference['depth2_rows']
    expected = len(prompt)+len(outputs)-2
    base.require(len(pairs) == expected == reference['canonical_true_pairs'] == reference['canonical_draft_position'],
                 'reference full canonical pair extent')
    base.require([p['position'] for p in pairs] == list(range(1, expected+1)), 'reference contiguous pair positions')
    base.require(len(depths) == reference['head_pairs'] == reference['expected_recursive_captures']
                 == reference['expected_recursive_restores'], 'reference recursive coverage')
    base.require(len({p['seed_position'] for p in depths}) == len(depths), 'unique reference recursive seeds')
    inputs = prompt+outputs[:-1]
    expected_depth_rows = []
    for pair in pairs:
        position = pair['position']
        head = position >= len(prompt)-1
        base.require(type(pair['head']) is bool and pair['head'] == head and pair['token'] == inputs[position]
                     and isinstance(pair['hidden_sha256'], str) and re.fullmatch('[0-9a-f]{64}', pair['hidden_sha256'])
                     and type(pair['proposal']) is int
                     and (0 <= pair['proposal'] < plan['vocab'] if head else pair['proposal'] == -1),
                     'reference canonical input/head/hidden/proposal identity')
        if head:
            expected_depth_rows.append(position)
    base.require([p['seed_position'] for p in depths] == expected_depth_rows, 'reference exact recursive seed coverage')
    for row in depths:
        pair = pairs[row['seed_position']-1]
        base.require(row['confirmed_token'] == pair['token'] and row['raw_hidden_sha256'] == pair['hidden_sha256']
                     and isinstance(row['guesses'], list) and len(row['guesses']) == 2
                     and row['guesses'][0] == pair['proposal']
                     and all(type(t) is int and 0 <= t < plan['vocab'] for t in row['guesses']),
                     'reference actual depth-two identity')


def make_plan(config_path):
    plan = base.make_plan(config_path)
    config = load_json(config_path)
    base.require(config.get('ring_live_draft') is True and config.get('use_proposals', False) is False,
                 'explicit quiescent actual-provider gate; speculative use refused')
    base.require(not config.get('scripted_proposal_tokens') and not config.get('force_miss_positions'),
                 'actual provider cannot receive scripted guesses')
    base.require(len(plan['stages']) in (2, 4, 6), 'admitted ring live controller owner counts')
    base.require(config.get('verify_recursive_restore', True) is True, 'first gate requires full recursive restore verification')
    eos = config.get('eos_token_ids', [plan['eos']])
    base.require(isinstance(eos, list) and eos and len(set(eos)) == len(eos)
                 and plan['eos'] in eos and all(type(t) is int and 0 <= t < plan['vocab'] for t in eos), 'EOS identity')
    reference_path = Path(config['recursive_reference']).resolve()
    reference = load_json(reference_path)
    validate_reference(reference, plan)
    receipt = load_json(config['build_receipt'])
    required = {'pipeline/ring/'+n+'.hpp' for n in ('stage_ring','wire','checkpoint_ring','engine_backend','dispatcher')}
    required |= {'pipeline/recursive_provider/'+n for n in ('batch.hpp','draft_runtime_extension.inc','final_event.hpp','peer.hpp')}
    required |= {'pipeline/live_draft.hpp', 'pipeline/operator_state.hpp'}
    base.require(required <= set(receipt.get('sources', {})), 'native quiescent recursive provider capability required')
    adapter = load_json(config['adapter_plan'])
    draft = adapter['rank_argv'][0]
    base.require('--draft-mtp' in draft and base.option(draft, '--draft-fault') == 'none', 'existing fault-free draft authority')
    draft_manifest_sha = base.digest(base.option(draft, '--draft-manifest'))
    base.require(draft_manifest_sha == reference['canonical_draft_input_identity']['draft_model_sha256'],
                 'reference draft manifest identity differs from selected provider')
    base.require(base.option(draft, '--draft-experts') == reference['canonical_draft_input_identity']['draft_experts'],
                 'reference draft expert arithmetic')
    identity = dict(model=plan['model_identity_sha256'], prompt=plan['prompt_tokens'], context=plan['context'],
                    max_new=plan['max_new'], vocab=plan['vocab'], eos=eos, mode='quiescent-ring-live-depth2')
    request_sha = sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    final_shared = str(Path(plan['output'])/f"stage{len(plan['stages'])-1}/shared.bin")
    for stage in plan['stages']:
        base.require(not any(f in stage['argv'] for f in ('--pipeline-wavefront','--pipeline-live-draft','--pipeline-ring','--draft-mtp')),
                     'recursive ring must not inherit another controller')
        stage['environment'].pop('OWNRT_DRAFT_DEPTH_PROBE', None)
        stage['environment'].pop('OWNRT_DRAFT_DEPTH_VERIFY', None)
        stage['argv'] += ['--pipeline-ring', '--pipeline-ring-request-sha256', request_sha, '--pipeline-ring-live-draft']
        if stage['first']:
            stage['argv'] += ['--pipeline-ring-recursive-verify-restore', '--pipeline-ring-final-shared', final_shared, '--draft-mtp']
            for flag in ('--draft-fault','--draft-manifest','--draft-model','--draft-experts'):
                value = base.option(draft, flag)
                stage['argv'] += [flag, value]
                if flag == '--draft-manifest':
                    plan['pins'][str(Path(value).resolve())] = base.digest(value)
            stage['argv'] = base.replace_options(stage['argv'], {'--draft-rank': 0})
    dependencies = (Path(__file__).resolve(), Path(codec.__file__).resolve(), Path(target.__file__).resolve(),
                    Path(wire.__file__).resolve(), Path(base.__file__).resolve(), Path(target.lifecycle.__file__).resolve(),
                    wire.PLANNING/'ring_coordinator.py', wire.PLANNING/'ring_contract.py', wire.PLANNING/'live_draft.py',
                    target.lifecycle.SCHEDULE_PATH,
                    base.ROOT/'experiments/own-xpu-runtime/ops/packet196-window/passive_device_holders.py',
                    base.ROOT/'experiments/own-xpu-runtime/stage1/packet4-prep/driver/window_driver.py', reference_path)
    for path in dependencies:
        plan['pins'][str(path)] = base.digest(path)
    plan.update(schema='ownrt.ring-live-driver-plan.v1', mode='quiescent-ring-live-depth2', request_sha256=request_sha,
                epoch=0, eos_token_ids=eos, live_draft=True, draft_training=False, use_proposals=False,
                verify_restore=False, verify_recursive_restore=True, recursive_reference=str(reference_path),
                final_shared=final_shared, diagnostic_only=True, speed_claim=False,
                draft_model_sha256=draft_manifest_sha,
                limits='Actual existing-MTP depth2 proposals discarded; verified target only, quiescent owners, no speed claim.')
    return plan


class LiveStage(target.RingStage):
    def start_async(self):
        super().start_async()
        self.provider_serial = 0

    def issue_provider(self, command):
        self.guard.check()
        base.require(command.depth==self.plan.get('speculative_depth',2),'provider command/plan depth differs')
        base.require(self.spec['first'] and self.command_pending is None and not self.transmit and not self.received
                     and not self.pending_rows and self.physical == self.committed == command.seed.row.position+1,
                     'provider requires locally accepted seed and quiescent target')
        base.require(command.sequence == self.sequence+1 and command.serial == self.provider_serial+1,
                     'provider wire/serial sequence')
        metadata = codec.seed_metadata(command, stream_bytes=self.stream_bytes)
        self.shared[wire.ROW_OFFSET:wire.ROW_OFFSET+224] = metadata
        h = command.parent.handoff
        self.shared[codec.handoff_codec.HEADER_OFFSET:codec.handoff_codec.HEADER_OFFSET+112] = h.header
        self.shared[base.SLOT:base.SLOT+self.stream_bytes] = h.hidden
        self.sequence = command.sequence
        self.command_pending = command
        self.transmit = base.REQUEST.pack(codec.STEP, command.seed.row.token, command.seed.row.position,
                                          int(command.seed.row.fixture > 0), command.depth, command.sequence, 0, 0)

    def read_ready(self):
        if not isinstance(self.command_pending, codec.ProviderCommand):
            return super().read_ready()
        self.guard.check()
        try:
            piece = self.sock.recv(base.REPLY.size-len(self.received))
        except BlockingIOError:
            return None
        base.require(piece, 'provider reply channel closed')
        self.received.extend(piece)
        if len(self.received) != base.REPLY.size:
            return None
        reply = base.REPLY.unpack(self.received)
        command = self.command_pending
        base.require(not self.transmit and reply[0] == reply[2] == 0
                     and reply[3] == codec.proposal_size(command.depth) and reply[4] == command.sequence and reply[5:8] == (0, 0, 0),
                     'provider error/extent/wire owner identity')
        result = codec.decode_proposal(bytes(self.shared[codec.PROPOSAL_OFFSET:codec.PROPOSAL_OFFSET+codec.proposal_size(command.depth)]), command,
                                       vocab=self.plan['vocab'], context=self.plan['context'])
        base.require(reply[1] == (result['guesses'][0] if result['guesses'] else -1), 'provider reply token differs from batch')
        self.provider_serial = command.serial
        self.command_pending = None
        self.received.clear()
        return command, reply, result


def submit(stage, command, guard):
    if isinstance(command, codec.ProviderCommand):
        stage.issue_provider(command)
    else:
        stage.issue(command)
    while stage.command_pending is not None:
        guard.check()
        readable, writable, _ = select.select([] if stage.transmit else [stage.sock],
                                               [stage.sock] if stage.transmit else [], [], 0.2)
        if writable:
            stage.write_ready()
        if readable:
            result = stage.read_ready()
            if result is not None:
                return result
    raise ValueError('unsolicited provider command retirement')


def check_pair(result, command, reference):
    pair = reference['canonical_pairs'][command.seed.row.position-1]
    base.require((pair['position'], pair['token'], pair['head'], pair['hidden_sha256'], pair['proposal']) ==
                 (command.seed.row.position, command.seed.row.token, command.seed.row.fixture > 0,
                  result['parent_hidden_sha256'], result['guesses'][0] if result['guesses'] else -1),
                 'canonical true pair/hidden/d1 differs from retained live reference')
    if result['guesses']:
        expected = {r['seed_position']: r for r in reference['depth2_rows']}[command.seed.row.position]
        base.require(expected['confirmed_token'] == command.seed.row.token
                     and expected['raw_hidden_sha256'] == result['parent_hidden_sha256']
                     and expected['guesses'][:2] == result['guesses'], 'actual recursive d1/d2 differs from retained diagnostic')


def drive(stages, plan, guard, output):
    reference = load_json(plan['recursive_reference'])
    validate_reference(reference, plan)
    for stage in stages:
        stage.start_async()
    request = bytes.fromhex(plan['request_sha256'])
    prefix = sha256(b'ownrt.ring-request.v1\0'+request+struct.pack('<Q', 0)).digest()
    prompt = plan['prompt_tokens']
    outputs, pairs = [], []
    parent = None
    started = time.monotonic()
    with (output/'schedule.jsonl').open('x') as trace, (output/'tokens.jsonl').open('x') as token_log, (output/'provider-batches.jsonl').open('x') as batches:
        for position in range(len(prompt)+plan['max_new']-1):
            guard.check()
            token = prompt[position] if position < len(prompt) else outputs[-1]
            row = ring.Row(0, position+1, position, position, token, max(0, position-len(prompt)+2),
                           request, prefix, wire.append_prefix(prefix, position, token))
            source = None
            for index, stage in enumerate(stages):
                base.require(all(s.command_pending is None and not s.pending_rows for s in stages),
                             'all target owners must be quiescent before next command')
                command = ring.Command(index, ring.ROW, stage.sequence+1, row, False, source=source)
                _, reply, ack = submit(stage, command, guard)
                target_token = ack.token
                next_source = None if ack.stream is None else ring.Publication(row, index, command.sequence, ack.stream, sha256(ack.stream).digest())
                accept = ring.Command(index, ring.ACCEPT, stage.sequence+1, row, False, command.sequence)
                _, _, accepted = submit(stage, accept, guard)
                trace.write(json.dumps(dict(event='verified-target-accept', stage=index, position=position, token=token,
                                            row=row.identity, row_sequence=command.sequence, commit_sequence=accept.sequence,
                                            physical=accepted.physical, committed=accepted.committed))+'\n')
                if index == 0 and position:
                    base.require(parent is not None and all(not s.pending_rows and s.command_pending is None for s in stages),
                                 'independent parent and quiescent target required')
                    step = codec.ProviderCommand(stage.sequence+1, command, parent, stage.provider_serial+1)
                    _, _, result = submit(stage, step, guard)
                    # Save actual evidence before reference qualification can refuse it.
                    batches.write(json.dumps(result)+'\n'); batches.flush()
                    check_pair(result, step, reference)
                    pairs.append(result)
                if stage.spec['final']:
                    parent = codec.final_record(stage.shared, command, accept, target_token,
                                                stages=len(stages), stream_bytes=stage.stream_bytes, vocab=plan['vocab'])
                    if row.fixture:
                        outputs.append(target_token)
                        token_log.write(json.dumps(dict(index=len(outputs)-1, token=target_token,
                                                        committed_monotonic_s=time.monotonic()))+'\n'); token_log.flush()
                source = next_source
            prefix = row.after
            trace.flush()
            if outputs and (len(outputs) == plan['max_new'] or outputs[-1] in plan['eos_token_ids']):
                break
    base.require(outputs == reference['target_output_ids'] and len(pairs) == reference['canonical_true_pairs'],
                 'complete target outputs and canonical provider pair count')
    head_pairs = sum(bool(p['guesses']) for p in pairs)
    base.require(head_pairs == reference['expected_recursive_captures'] == reference['expected_recursive_restores'],
                 'actual recursive pair coverage')
    for stage in stages:
        base.require(not stage.pending_rows and stage.command_pending is None and not stage.transmit and not stage.received
                     and stage.physical == stage.committed == position+1, 'all target owners drained at final boundary')
        stage.sock.settimeout(0.2)
    return dict(output_ids=outputs, input_position=position+1, provider_pairs=len(pairs), recursive_head_pairs=head_pairs,
                provider_serial=stages[0].provider_serial, actual_provider=True, speculative_target_use=False,
                scheduler_wall_seconds=time.monotonic()-started, speed_claim=False,
                reference_sha256=base.digest(plan['recursive_reference']))


def execute(plan, admission, unit):
    try:
        target.lifecycle.execute(plan, admission, unit, stage_type=LiveStage, driver=drive, scripted_proposals=False)
    finally:
        original = Path(plan['output'])/'result.json'
        if original.is_file():
            result = load_json(original)
            result.update(schema='ownrt.ring-live-driver-result.v1', mode='quiescent-ring-live-depth2',
                          actual_provider=True, speculative_target_use=False, draft_training=False,
                          diagnostic_only=True, speed_claim=False, lifecycle_result_sha256=base.digest(original),
                          plan_sha256=base.digest(Path(plan['output'])/'plan.json'),
                          qualification_note='Controller/proposal checks only; independent canonical73 and private restore state comparison required.')
            base.save(Path(plan['output'])/'ring-live-result.json', result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--admission', type=Path)
    parser.add_argument('--unit')
    args = parser.parse_args()
    if not args.run:
        base.require(args.config is not None, 'config required for CPU planning')
        base.save(args.plan, make_plan(args.config))
        print(json.dumps(dict(plan=str(args.plan), sha256=base.digest(args.plan), device_execution_requested=False)))
        return
    base.require(args.admission is not None and args.unit, 'explicit admission and owning unit required')
    plan = load_json(args.plan)
    base.require(plan == make_plan(plan['config']), 'plan/source/launch identity changed')
    admission = load_json(args.admission)
    base.require(admission['plan_sha256'] == base.digest(args.plan), 'admission plan mismatch')
    execute(plan, admission, args.unit)


if __name__ == '__main__': main()

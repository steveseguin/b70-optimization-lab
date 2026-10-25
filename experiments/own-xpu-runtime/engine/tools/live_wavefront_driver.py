#!/usr/bin/env python3
"""Bounded live existing-MTP overlap qualification; no training or speed claim."""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import select
import time

import wavefront_driver as wave
base, schedule = wave.base, wave.schedule
CODEC_PATH = base.HERE.parent / 'planning/live_draft.py'
import importlib.util
import sys
_spec = importlib.util.spec_from_file_location('ownrt_live_draft_codec', CODEC_PATH)
codec = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = codec
_spec.loader.exec_module(codec)


def make_plan(config_path):
    plan = base.make_plan(config_path)
    config = json.loads(Path(config_path).read_text())
    base.require(config.get('live_draft') is True, 'explicit live existing-draft mode required')
    receipt = json.loads(Path(config['build_receipt']).read_text())
    base.require('pipeline/live_draft.hpp' in receipt.get('sources', {}),
                 'native live-draft transport build required')
    base.require(not config.get('scripted_proposal_tokens') and not config.get('force_miss_positions'),
                 'live qualification cannot use scripted guesses')
    verify = config.get('verify_restore', True)
    base.require(type(verify) is bool, 'restore verification boolean')
    use_proposals = config.get('use_proposals', True)
    base.require(type(use_proposals) is bool, 'explicit proposal-use boolean')
    endings = config.get('eos_token_ids', [plan['eos']])
    base.require(isinstance(endings, list) and endings and plan['eos'] in endings
                 and all(type(t) is int and 0 <= t < plan['vocab'] for t in endings)
                 and len(set(endings)) == len(endings), 'explicit unique EOS tokens')
    adapter = json.loads(Path(config['adapter_plan']).read_text())
    draft = adapter['rank_argv'][0]
    base.require('--draft-mtp' in draft, 'recorded existing draft authority required')
    draft_options = ['--draft-fault', '--draft-manifest', '--draft-model', '--draft-experts']
    for stage in plan['stages']:
        # Native live mode refuses even disabled legacy probe variables: its
        # canonical provider must have no independent recursive observer.
        stage['environment'].pop('OWNRT_DRAFT_DEPTH_PROBE', None)
        stage['environment'].pop('OWNRT_DRAFT_DEPTH_VERIFY', None)
        stage['argv'] += ['--pipeline-wavefront', '--pipeline-live-draft']
        if verify:
            stage['argv'].append('--pipeline-wavefront-verify-restore')
        if stage['first']:
            stage['argv'].append('--draft-mtp')
            for flag in draft_options:
                value = base.option(draft, flag)
                stage['argv'] += [flag, value]
                if flag == '--draft-manifest':
                    plan['pins'][str(Path(value).resolve())] = base.digest(value)
            stage['argv'] = base.replace_options(stage['argv'], {'--draft-rank': 0})
    for path in (Path(__file__).resolve(), Path(wave.__file__).resolve(), CODEC_PATH,
                 wave.SCHEDULE_PATH,
                 base.ROOT / 'experiments/own-xpu-runtime/ops/packet196-window/passive_device_holders.py',
                 base.ROOT / 'experiments/own-xpu-runtime/stage1/packet4-prep/driver/window_driver.py'):
        plan['pins'][str(path)] = base.digest(path)
    plan.update(schema='ownrt.live-wavefront-driver-plan.v1', mode='verified-wavefront',
                live_draft=True, draft_training=False, verify_restore=verify, max_inflight=2,
                use_proposals=use_proposals,
                eos_token_ids=endings,
                diagnostic_only=True, speed_claim=False,
                limits='Existing live depth-one draft; target and draft state qualification required. No speed claim.')
    return plan


class LiveStage(wave.AsyncStage):
    def resolution_reply(self, command, reply):
        if command.op != schedule.COMMIT or not self.spec['final']:
            return super().resolution_reply(command, reply)
        base.require(reply[3] == self.stream_bytes, 'live final commit hidden extent')
        h = codec.decode(self.shared[codec.HEADER_OFFSET:codec.HEADER_OFFSET + codec.HEADER.size],
                         self.shared[codec.HIDDEN_OFFSET:codec.HIDDEN_OFFSET + self.stream_bytes],
                         stream_bytes=self.stream_bytes, stages=len(self.plan['stages']),
                         vocab=self.plan['vocab'])
        row = command.row
        self.handoff = codec.bind(h, position=row.position, input_token=row.token,
                                  row_ticket=command.speculative, commit_sequence=command.sequence,
                                  output_token=row.next_token, fixture=row.fixture)
        base.require(reply[1] == h.next_token, 'live commit reply/header token mismatch')


def draft_step(stage, model, sequence, handoff, confirmed, head):
    """Only a quiescent stage can advance its independent canonical draft."""
    state = model.stages[0]
    base.require(state.busy is None and state.pending is None
                 and stage.command_pending is None and not stage.transmit and not stage.received,
                 'draft step while target checkpoint or command unresolved')
    request = sequence.begin(handoff, confirmed, head=head)
    stage.shared[base.SLOT:base.SLOT + len(handoff.hidden)] = handoff.hidden
    stage.shared[codec.HEADER_OFFSET:codec.HEADER_OFFSET + codec.HEADER.size] = handoff.header
    base.require(state.sequence == stage.sequence, 'draft/scheduler wire sequence disagreement')
    # No scheduler command is reserved during this bounded synchronous exchange.
    stage.sock.settimeout(0.2)
    reply = stage.command(**request)
    stage.sock.setblocking(False)
    base.require(reply[3] == 0, 'draft reply must have no stage stream')
    state.sequence += 1
    base.require(state.sequence == stage.sequence, 'draft did not consume exactly one wire sequence')
    sequence.complete(reply[1])
    return reply


def drive(stages, plan, guard, output, *, initial_sequences=None):
    prompt = plan['prompt_tokens']
    sequence = codec.CanonicalSequence(plan['vocab'])
    model = schedule.Wavefront(len(stages), prompt, plan['max_new'], plan['vocab'],
                               plan['eos'], sequence.proposal if plan.get('use_proposals', True) else lambda _: None,
                               eos_token_ids=plan.get('eos_token_ids'))
    if initial_sequences is not None:
        base.require(tuple(initial_sequences) == tuple(s.sequence for s in stages),
                     'persistent scheduler seed differs from native wire sequence')
        # Function-local import avoids a module initialization cycle; the helper
        # validates a fresh scheduler and never mutates native Stage ownership.
        from persistent_live_suite import seed_model_sequences
        seed_model_sequences(model, initial_sequences)
    else:
        base.require(all(s.sequence == 0 for s in stages), 'nonfresh wire requires explicit sequence seed')
    for stage in stages:
        stage.start_async()
    sockets = {s.sock:s for s in stages}
    queue = deque()
    event_index = emitted = 0
    began = time.monotonic()
    with (output/'schedule.jsonl').open('x') as trace, (output/'tokens.jsonl').open('x') as tokens:
        def record(**value):
            trace.write(json.dumps(dict(value, monotonic_s=time.monotonic()))+'\n')
            trace.flush()
        while not model.done or queue:
            guard.check()
            state = model.stages[0]
            if queue and state.busy is None and state.pending is None:
                handoff, confirmed = queue.popleft()
                head = handoff.position + 2 >= len(prompt)
                reply = draft_step(stages[0], model, sequence, handoff, confirmed, head)
                record(event='live-draft', position=handoff.position+1, token=confirmed,
                       proposal=reply[1], head=head, busy_ms=reply[8], sequence=stages[0].sequence,
                       hidden_sha256=hashlib.sha256(handoff.hidden).hexdigest())
            if model.done and not queue:
                break
            for command in model.commands(block_rows={0} if queue else ()):
                stage, row = stages[command.stage], command.row
                if command.op == schedule.ROW and command.stage:
                    data = row.streams[command.stage-1]
                    base.require(len(data) == stage.stream_bytes, 'complete stage handoff')
                    stage.shared[base.SLOT:base.SLOT+len(data)] = data
                stage.issue(command)
                record(event='send', stage=command.stage, op=command.op, sequence=command.sequence,
                       row=row.identity, position=row.position, token=row.token,
                       speculative=command.speculative)
            active = [s for s in stages if s.command_pending is not None]
            if not active and queue:
                continue
            base.require(active, 'live scheduler stalled without native work')
            reads, writes, _ = select.select([s.sock for s in active if not s.transmit],
                                             [s.sock for s in active if s.transmit], [], 0.2)
            for sock in writes:
                sockets[sock].write_ready()
            for sock in reads:
                stage = sockets[sock]
                completed = stage.read_ready()
                if completed is None:
                    continue
                command, reply, token, stream = completed
                model.complete(command, output_token=token, stream=stream)
                record(event='reply', stage=command.stage, op=command.op, sequence=command.sequence,
                       row=command.row.identity, position=command.row.position, busy_ms=reply[8])
                if command.op == schedule.COMMIT and stage.spec['final'] and not model.stopping:
                    h = stage.handoff
                    queue.append((h, model.known[h.position+1]))
                while event_index < len(model.events):
                    record(**model.events[event_index]); event_index += 1
                while emitted < len(model.emitted):
                    tokens.write(json.dumps(dict(index=emitted, token=model.emitted[emitted],
                                                 committed_monotonic_s=time.monotonic()))+'\n')
                    tokens.flush(); emitted += 1
    for stage in stages:
        base.require(stage.command_pending is None and not stage.received and not stage.transmit,
                     'undrained live native command')
        stage.sock.settimeout(0.2)
    base.require(sequence.pending is None and sequence.position == model.frontier,
                 'canonical draft true-pair count differs from target prefix')
    return dict(output_ids=model.emitted, input_position=model.frontier,
                draft_pairs=sequence.position-1, events=model.events,
                scheduler_wall_seconds=time.monotonic()-began, live_draft=True,
                use_proposals=plan.get('use_proposals', True),
                limits='Depth-one live proposal qualification; full target/draft state comparison still required.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--admission', type=Path)
    parser.add_argument('--unit')
    args = parser.parse_args()
    if not args.run:
        base.require(args.config is not None, 'config required')
        base.save(args.plan, make_plan(args.config))
        print(json.dumps(dict(plan=str(args.plan), sha256=base.digest(args.plan), device_execution_requested=False)))
        return
    base.require(args.admission is not None and args.unit, 'admission and owning unit required')
    plan = json.loads(args.plan.read_text())
    base.require(plan == make_plan(plan['config']), 'live plan/source changed')
    admission = json.loads(args.admission.read_text())
    base.require(admission['plan_sha256'] == base.digest(args.plan), 'live admission plan identity')
    wave.execute(plan, admission, args.unit, stage_type=LiveStage, driver=drive, scripted_proposals=False)


if __name__ == '__main__':
    main()

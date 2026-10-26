#!/usr/bin/env python3
"""Qualification-only target suffix rollback around actual canonical MTP steps.

Uses scripted tentative inputs solely to force target-verified rejection. No
rolling inference, training, speed claim, or changes to the quiescent controller.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import struct
import time

import ring_live_driver as live
import pending_ring_live_wire as pending_codec

base, codec, wire, ring = live.base, live.codec, live.wire, live.ring


def make_plan(config_path):
    config = live.load_json(config_path)
    base.require(config.get('pending_provider_gate') is True, 'explicit pending provider gate required')
    plan = live.make_plan(config_path)
    cases = config['pending_cases']
    base.require(isinstance(cases, list) and len(cases) == 2 and all(isinstance(c, dict) for c in cases)
                 and [c.get('kind') for c in cases] == ['two-row-abort', 'accept-then-one-row-abort'],
                 'exact bounded two-slot and older-ACCEPT gate cases')
    first, second = [c.get('seed_position') for c in cases]
    limit = len(plan['prompt_tokens'])+plan['max_new']-1
    base.require(type(first) is int and type(second) is int and len(plan['prompt_tokens']) <= first < second
                 and second+2 < limit and all(set(c) == {'kind','seed_position'} for c in cases),
                 'ordered generated seed positions within request capacity')
    receipt = live.load_json(config['build_receipt'])
    base.require({'pipeline/recursive_provider/pending_survival.inc',
                  'pipeline/recursive_provider/survival_identity.hpp',
                  'pipeline/recursive_provider/survival_writer.inc'} <= set(receipt.get('sources', {})),
                 'native provider survival capability required')
    request_sha = sha256(json.dumps(dict(parent_request=plan['request_sha256'], cases=cases,
                                        mode='pending-ring-live-depth2'), sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    for stage in plan['stages']:
        stage['argv'] = base.replace_options(stage['argv'], {'--pipeline-ring-request-sha256': request_sha})
        stage['argv'] += ['--pipeline-ring-pending-provider', '--pipeline-ring-verify-restore']
        if stage['first']:
            stage['argv'].append('--pipeline-ring-verify-provider-survival')
    for path in (Path(__file__).resolve(), Path(pending_codec.__file__).resolve()):
        plan['pins'][str(path)] = base.digest(path)
    plan.update(schema='ownrt.pending-ring-live-driver-plan.v1', mode='pending-ring-live-depth2',
                request_sha256=request_sha, pending_cases=cases, verify_restore=True,
                verify_provider_survival=True, scripted_tentative_inputs=True,
                expected_pending_borrows={'1':1, '2':2}, expected_survival_checks=2,
                expected_discarded_rows=3, diagnostic_only=True, speed_claim=False,
                limits='Scripted tentative target inputs force real target rejection around actual MTP; no rolling or speed claim.')
    return plan


class PendingStage(live.LiveStage):
    def start_async(self):
        super().start_async()
        self.accepted_row = None
        self.accepted_sequence = 0

    def read_ready(self):
        command = self.command_pending
        original = self.pending_rows[0] if command is not None and command.op == ring.ACCEPT and self.pending_rows else None
        result = super().read_ready()
        if result is None:
            return None
        if isinstance(command, pending_codec.PendingProviderCommand):
            base.require((self.physical, self.committed, tuple(c.row.identity for c in self.pending_rows)) ==
                         (command.target_physical, command.target_committed, command.pending_rows),
                         'provider changed pending target cursor/identity')
            result[2].update(target_physical=self.physical, target_committed=self.committed,
                             pending_target_rows=list(command.pending_rows), pending_depth=len(command.pending_rows),
                             accepted_seed_sequence=command.accepted_sequence, original_seed_tentative=command.seed.tentative)
        elif command.op == ring.ACCEPT:
            self.accepted_row, self.accepted_sequence = original, command.sequence
        return result

    def issue_provider(self, command):
        self.guard.check()
        base.require(command.depth==self.plan.get('speculative_depth',2),'provider command/plan depth differs')
        base.require(isinstance(command, pending_codec.PendingProviderCommand) and self.spec['first']
                     and self.command_pending is None and not self.transmit and not self.received,
                     'exclusive pending provider wire owner')
        base.require(command.sequence == self.sequence+1 and command.serial == self.provider_serial+1,
                     'pending provider wire/serial sequence')
        base.require(all(c.tentative for c in self.pending_rows)
                     and (self.physical, self.committed, tuple(c.row.identity for c in self.pending_rows)) ==
                         (command.target_physical, command.target_committed, command.pending_rows),
                     'provider may borrow only completed tentative target suffix')
        metadata = pending_codec.seed_metadata(command, accepted_row=self.accepted_row,
                    accepted_sequence=self.accepted_sequence, stream_bytes=self.stream_bytes)
        self.shared[wire.ROW_OFFSET:wire.ROW_OFFSET+224] = metadata
        h = command.parent.handoff
        self.shared[codec.handoff_codec.HEADER_OFFSET:codec.handoff_codec.HEADER_OFFSET+112] = h.header
        self.shared[base.SLOT:base.SLOT+self.stream_bytes] = h.hidden
        self.sequence = command.sequence
        self.command_pending = command
        self.transmit = base.REQUEST.pack(codec.STEP, command.seed.row.token, command.seed.row.position,
                                          int(command.seed.row.fixture > 0), command.depth, command.sequence, 0, 0)


def drive(stages, plan, guard, output):
    reference = live.load_json(plan['recursive_reference'])
    live.validate_reference(reference, plan)
    for stage in stages:
        stage.start_async()
    prompt = plan['prompt_tokens']
    expected_inputs = prompt+reference['target_output_ids'][:-1]
    request = bytes.fromhex(plan['request_sha256'])
    prefix = sha256(b'ownrt.ring-request.v1\0'+request+struct.pack('<Q', 0)).digest()
    cases = {c['seed_position']:c['kind'] for c in plan['pending_cases']}
    outputs, provider_pairs, coverage = [], [], []
    parent = None
    next_id = 0
    accepted_reuse = None
    pending_rejection = None
    started = time.monotonic()
    first = stages[0]
    with (output/'schedule.jsonl').open('x') as trace, (output/'tokens.jsonl').open('x') as token_log, (output/'provider-batches.jsonl').open('x') as batches:
        def log(event, **fields):
            trace.write(json.dumps(dict(event=event, **fields))+'\n'); trace.flush()

        def new_row(position, token, parent_row):
            nonlocal next_id
            next_id += 1
            before = prefix if parent_row is None else parent_row.after
            return ring.Row(0, next_id, 0 if parent_row is None else parent_row.identity, position, token,
                            max(0, position-len(prompt)+2), request, before, wire.append_prefix(before, position, token))

        def run_row(stage, row, tentative=False, source=None):
            command = ring.Command(stage.spec['id'], ring.ROW, stage.sequence+1, row, tentative, source=source)
            _, _, ack = live.submit(stage, command, guard)
            publication = None if ack.stream is None else ring.Publication(row, command.stage, command.sequence,
                                                                          ack.stream, sha256(ack.stream).digest())
            log('row', stage=command.stage, sequence=command.sequence, row=row.identity, parent=row.parent,
                position=row.position, token=row.token, tentative=tentative, physical=ack.physical,
                committed=ack.committed, pending=ack.pending)
            return command, publication, ack.token

        def accept(stage, command):
            resolution = ring.Command(command.stage, ring.ACCEPT, stage.sequence+1, command.row,
                                      command.tentative, command.sequence)
            _, _, ack = live.submit(stage, resolution, guard)
            log('accept', stage=command.stage, sequence=resolution.sequence, row=command.row.identity,
                position=command.row.position, original_tentative=command.tentative,
                physical=ack.physical, committed=ack.committed, pending=ack.pending)
            return resolution

        for position in range(len(expected_inputs)):
            guard.check()
            token = prompt[position] if position < len(prompt) else outputs[-1]
            if accepted_reuse is not None:
                seed_command, seed_output = accepted_reuse
                accepted_reuse = None
                row = seed_command.row
                base.require(row.position == position and row.token == token and first.accepted_row == seed_command,
                             'reused accepted tentative seed must match actual target truth')
            else:
                row = new_row(position, token, None if parent is None else parent.row)
                seed_command, seed_output, _ = run_row(first, row)
                accept(first, seed_command)
            children = None
            kind = cases.get(position)
            if kind:
                first_token = expected_inputs[position+1]
                if kind == 'two-row-abort':
                    first_token = (first_token+1) % plan['vocab']
                child = new_row(position+1, first_token, row)
                child_command, child_output, _ = run_row(first, child, True)
                grandchild = new_row(position+2, (expected_inputs[position+2]+1) % plan['vocab'], child)
                grand_command, _, _ = run_row(first, grandchild, True)
                children = (child_command, child_output, grand_command)
            if position:
                base.require(parent is not None and all(s.command_pending is None for s in stages)
                             and all(not s.pending_rows for s in stages[1:]), 'one provider command with other target owners drained')
                step = pending_codec.PendingProviderCommand(first.sequence+1, seed_command, parent, first.provider_serial+1,
                    accepted_sequence=first.accepted_sequence, target_physical=first.physical,
                    target_committed=first.committed, pending_rows=tuple(c.row.identity for c in first.pending_rows))
                _, _, result = live.submit(first, step, guard)
                batches.write(json.dumps(result)+'\n'); batches.flush()
                live.check_pair(result, step, reference)
                provider_pairs.append(result)
                log('provider', position=position, sequence=step.sequence, serial=step.serial,
                    pending_depth=len(step.pending_rows), pending_rows=step.pending_rows,
                    physical=first.physical, committed=first.committed)
            # Seed output was privately owned before either child could overwrite it.
            source = seed_output
            for stage in stages[1:]:
                command, source, target_token = run_row(stage, row, False, source)
                resolution = accept(stage, command)
                if stage.spec['final']:
                    parent = codec.final_record(stage.shared, command, resolution, target_token,
                        stages=len(stages), stream_bytes=stage.stream_bytes, vocab=plan['vocab'])
                    if row.fixture:
                        outputs.append(target_token)
                        token_log.write(json.dumps(dict(index=len(outputs)-1, token=target_token,
                            committed_monotonic_s=time.monotonic()))+'\n'); token_log.flush()
            if children is not None:
                child_command, child_output, grand_command = children
                if kind == 'two-row-abort':
                    base.require(outputs[-1] != child_command.row.token, 'actual target must reject scripted first child')
                    pending_rejection = (child_command, (child_command.row.identity, grand_command.row.identity), position)
                else:
                    base.require(outputs[-1] == child_command.row.token, 'actual target must confirm older tentative child before ACCEPT')
                    before = first.physical
                    accept(first, child_command)
                    base.require(first.physical == before and len(first.pending_rows) == 1, 'older ACCEPT must not rewind remaining suffix')
                    accepted_reuse = (child_command, child_output)
                    pending_rejection = (grand_command, (grand_command.row.identity,), position+1)
                    log('older-accepted-with-one-pending', position=child_command.row.position,
                        physical=first.physical, committed=first.committed, pending_row=grand_command.row.identity)
            if pending_rejection is not None and pending_rejection[2] == position:
                rejected, discarded, seed_position = pending_rejection
                base.require(outputs[-1] != rejected.row.token and all(s.command_pending is None for s in stages),
                             'actual target rejection and full wire drain before suffix abort')
                before_serial = first.provider_serial
                abort = ring.Command(0, ring.ABORT_SUFFIX, first.sequence+1, rejected.row, True, rejected.sequence)
                _, _, ack = live.submit(first, abort, guard)
                base.require(ack.discarded == discarded and ack.physical == ack.committed == position+1
                             and ack.pending == 0 and first.provider_serial == before_serial,
                             'exact suffix rollback without provider replay/rewind')
                event = dict(seed_position=seed_position, abort_sequence=abort.sequence, discarded_rows=list(discarded),
                    actual_target_token=outputs[-1], rejected_token=rejected.row.token, provider_serial=before_serial,
                    physical=ack.physical, committed=ack.committed, target_restore_bytecheck_required=True)
                coverage.append(event);log('target-verified-suffix-abort', **event)
                pending_rejection = None
            prefix = row.after
            if outputs and (len(outputs) == plan['max_new'] or outputs[-1] in plan['eos_token_ids']):
                break
    counts = Counter(p['pending_depth'] for p in provider_pairs)
    summary = dict(aborts=coverage, pending_borrows={str(depth):counts[depth] for depth in (1,2)},
                   canonical_pairs=len(provider_pairs), provider_serial=first.provider_serial)
    base.save(output/'pending-provider-coverage.json', summary)
    base.require(outputs == reference['target_output_ids'] and len(provider_pairs) == reference['canonical_true_pairs'],
                 'complete actual target and canonical provider reference')
    base.require(summary['pending_borrows'] == plan['expected_pending_borrows'] and len(coverage) == 2
                 and sorted(len(e['discarded_rows']) for e in coverage) == [1,2]
                 and accepted_reuse is None and pending_rejection is None, 'both actual pending depths and suffix geometries must execute')
    for stage in stages:
        base.require(not stage.pending_rows and stage.command_pending is None and not stage.transmit and not stage.received
                     and stage.physical == stage.committed == position+1, 'final target/native wire boundary')
        stage.sock.settimeout(0.2)
    return dict(output_ids=outputs, input_position=position+1, provider_pairs=len(provider_pairs),
                provider_serial=first.provider_serial, pending_provider=summary, actual_provider=True,
                scripted_tentative_inputs=True, speed_claim=False, scheduler_wall_seconds=time.monotonic()-started)


def execute(plan, admission, unit):
    try:
        live.target.lifecycle.execute(plan, admission, unit, stage_type=PendingStage, driver=drive, scripted_proposals=False)
    finally:
        original = Path(plan['output'])/'result.json'
        if original.is_file():
            result = live.load_json(original)
            result.update(schema='ownrt.pending-ring-live-driver-result.v1', mode='pending-ring-live-depth2',
                actual_provider=True, scripted_tentative_inputs=True, diagnostic_only=True, speed_claim=False,
                draft_training=False, lifecycle_result_sha256=base.digest(original),
                plan_sha256=base.digest(Path(plan['output'])/'plan.json'),
                qualification_note='Controller checks only; independent v5 provider/private survival, target and canonical73 comparison required.')
            base.save(Path(plan['output'])/'pending-ring-live-result.json', result)


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
        print(json.dumps(dict(plan=str(args.plan),sha256=base.digest(args.plan),device_execution_requested=False)))
        return
    base.require(args.admission is not None and args.unit, 'explicit admission and unit required')
    plan = live.load_json(args.plan)
    base.require(plan == make_plan(plan['config']), 'plan/source/launch identity changed')
    admission = live.load_json(args.admission)
    base.require(admission['plan_sha256'] == base.digest(args.plan), 'admission plan mismatch')
    execute(plan, admission, args.unit)


if __name__ == '__main__': main()

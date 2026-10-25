#!/usr/bin/env python3
"""Opt-in scripted target-only depth-two rollback qualification. No speed claim.

CPU planning is the default. Execution reuses the existing passive fault/holder
admission and single-owner cooperative lifecycle. No native draft/provider calls.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import select
import time

import pipeline_driver as base
import wavefront_driver as lifecycle
import ring_wire as wire
from ring_contract import ProposalBatch

ring = wire.ring


def make_plan(config_path):
    plan = base.make_plan(config_path)
    config = json.loads(Path(config_path).read_text())
    base.require(config.get('ring') is True, 'explicit ring opt-in required')
    base.require(len(plan['stages']) in (2, 4, 6), 'qualified controller stage counts2/4/6')
    reference = config['scripted_proposal_tokens']
    base.require(isinstance(reference, list) and plan['max_new'] <= len(reference) <= 512
                 and all(type(t) is int and 0 <= t < plan['vocab'] for t in reference),
                 'bounded complete scripted reference tokens')
    misses = config.get('force_miss_positions', [])
    base.require(isinstance(misses, list) and len(set(misses)) == len(misses)
                 and all(type(p) is int and len(plan['prompt_tokens']) <= p
                         < len(plan['prompt_tokens'])+plan['max_new']-1 for p in misses),
                 'forced misses must address generated inputs')
    depths = config.get('required_miss_depths', [1, 2])
    base.require(isinstance(depths, list) and sorted(set(depths)) == sorted(depths)
                 and all(type(d) is int and d in (1, 2) for d in depths), 'required miss depths')
    verify, two_rows = config.get('verify_restore', True), config.get('require_two_row_abort', True)
    base.require(type(verify) is bool and type(two_rows) is bool, 'explicit diagnostic booleans')
    eos = config.get('eos_token_ids', [plan['eos']])
    base.require(isinstance(eos, list) and eos and len(eos) == len(set(eos))
                 and all(type(t) is int and 0 <= t < plan['vocab'] for t in eos), 'EOS set')
    receipt = json.loads(Path(config['build_receipt']).read_text())
    for capability in ('stage_ring', 'wire', 'checkpoint_ring', 'engine_backend', 'dispatcher'):
        base.require('pipeline/ring/'+capability+'.hpp' in receipt.get('sources', {}), 'native ring build required')
    identity = dict(model=plan['model_identity_sha256'], prompt=plan['prompt_tokens'], max_new=plan['max_new'],
                    context=plan['context'], vocab=plan['vocab'], eos=eos, reference=reference,
                    misses=misses, activation='F32', mode='scripted-target-only-ring')
    request_sha = sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    for stage in plan['stages']:
        base.require(not any(flag in stage['argv'] for flag in
                             ('--pipeline-wavefront', '--pipeline-live-draft', '--draft-mtp', '--pipeline-ring')),
                     'ring target-only launch must not inherit another controller')
        stage['argv'] += ['--pipeline-ring', '--pipeline-ring-request-sha256', request_sha]
        if verify:
            stage['argv'].append('--pipeline-ring-verify-restore')
    plan.update(schema='ownrt.ring-driver-plan.v1', mode='scripted-target-only-ring', request_sha256=request_sha,
                epoch=0, scripted_proposal_tokens=reference, force_miss_positions=misses,
                required_miss_depths=depths, require_two_row_abort=two_rows, verify_restore=verify,
                eos_token_ids=eos, max_inflight=3, tentative_slots_per_early_stage=2,
                diagnostic_only=True, speed_claim=False,
                limits='Oracle-assisted scripted target-only rollback proof; no live draft, throughput or portability claim.')
    for path in (Path(__file__).resolve(), Path(wire.__file__).resolve(), Path(lifecycle.__file__).resolve(),
                 Path(base.__file__).resolve(), wire.PLANNING/'ring_coordinator.py', wire.PLANNING/'ring_contract.py',
                 lifecycle.SCHEDULE_PATH,
                 base.ROOT/'experiments/own-xpu-runtime/ops/packet196-window/passive_device_holders.py',
                 base.ROOT/'experiments/own-xpu-runtime/stage1/packet4-prep/driver/window_driver.py'):
        plan['pins'][str(path)] = base.digest(path)
    return plan


class RingStage(lifecycle.AsyncStage):
    def start_async(self):
        super().start_async()
        self.physical = self.committed = 0
        self.pending_rows = []
        self.submitted = None

    def issue(self, command):
        self.guard.check()
        base.require(self.command_pending is None and not self.received and not self.transmit,
                     'one outstanding native ring command')
        base.require(command.stage == self.spec['id'] and command.sequence == self.sequence+1,
                     'ring owner/wire sequence')
        if command.op != ring.ROW:
            base.require(self.pending_rows and self.pending_rows[0].row == command.row
                         and self.pending_rows[0].sequence == command.row_ticket
                         and self.pending_rows[0].tentative == command.tentative,
                         'resolution must retain original ROW flags and identity')
        metadata, payload = wire.row_metadata(command, final=self.spec['final'], stream_bytes=self.stream_bytes)
        if payload:
            self.shared[base.SLOT:base.SLOT+len(payload)] = payload
        self.shared[wire.ROW_OFFSET:wire.ROW_OFFSET+wire.ROW_META.size] = metadata
        self.submitted = metadata
        self.sequence = command.sequence
        self.command_pending = command
        row = command.row
        speculative = int(command.tentative) if command.op == ring.ROW else command.row_ticket
        self.transmit = base.REQUEST.pack(command.op, row.token, row.position, row.fixture, speculative,
                                          command.sequence, command.stage, int(self.spec['final']))

    def read_ready(self):
        self.guard.check()
        try:
            piece = self.sock.recv(base.REPLY.size-len(self.received))
        except BlockingIOError:
            return None
        base.require(piece, 'ring reply channel closed')
        self.received.extend(piece)
        if len(self.received) != base.REPLY.size:
            return None
        reply = base.REPLY.unpack(self.received)
        command = self.command_pending
        base.require(command is not None and not self.transmit, 'ring reply without complete request')
        base.require(reply[0] == 0 and reply[2] == 0 and reply[4] == command.sequence,
                     'native ring error or stale sequence')
        base.require(reply[5] == (0 if self.spec['first'] else 1)
                     and reply[6:8] == (self.spec['id'], int(self.spec['final'])), 'ring stage/final identity')
        row = command.row
        if command.op == ring.ROW:
            final = self.spec['final']
            base.require(reply[3] == (0 if final else self.stream_bytes), 'ROW exact F32 publication extent')
            stream = b'' if final else bytes(self.shared[:self.stream_bytes])
            wire.validate_publication(bytes(self.shared[wire.ROW_OFFSET:wire.ROW_OFFSET+wire.ROW_META.size]),
                                      self.submitted, command.sequence, stream,
                                      final=final, stream_bytes=self.stream_bytes)
            if final and row.fixture:
                base.require(0 <= reply[1] < self.plan['vocab'], 'final target token bounds')
            else:
                base.require(reply[1] == -1, 'head-free ROW must not expose a stale head token')
            self.pending_rows.append(command)
            self.physical += 1
            ack = ring.Ack(row.epoch, command.stage, command.sequence, row.identity, command.sequence,
                           self.physical, self.committed, len(self.pending_rows),
                           stream=None if final else stream, token=reply[1] if final and row.fixture else None)
        else:
            base.require(reply[1] == 0 and reply[3] == 0, 'target-only resolution has no token/stream')
            ack = wire.resolution_ack(bytes(self.shared[wire.ACK_OFFSET:wire.ACK_OFFSET+wire.ACK_META.size]),
                                      command, self.pending_rows, physical=self.physical,
                                      committed=self.committed, verify_restore=self.plan['verify_restore'])
            self.physical, self.committed = ack.physical, ack.committed
            if command.op == ring.ACCEPT:
                self.pending_rows.pop(0)
            else:
                self.pending_rows.clear()
        self.command_pending = None
        self.received.clear()
        return command, reply, ack


class ScriptedProposals:
    """Oracle-assisted hypotheses, intentionally distinct from a native provider."""
    def __init__(self, plan):
        self.reference = plan['scripted_proposal_tokens']
        self.prompt_length = len(plan['prompt_tokens'])
        self.misses = set(plan['force_miss_positions'])
        self.vocab = plan['vocab']
        self.seen = set()
        self.ticket = 0

    def __call__(self, model):
        length = len(model.proposals.verified)
        key = (length, model.proposals.hashes[-1])
        if key in self.seen or length >= model.limit:
            return []
        # Preserve an available second-depth hypothesis instead of replacing it
        # with a fresh depth-one copy when the verified seed advances.
        if model.proposals.choose(length, model.proposals.hashes[-1]) is not None:
            return []
        self.seen.add(key)
        self.ticket += 1
        guesses = tuple((self.reference[p-self.prompt_length]+int(p in self.misses)) % self.vocab
                        for p in range(length, min(length+2, model.limit)))
        return [ProposalBatch(model.request, model.epoch, self.ticket, length,
                              model.proposals.hashes[-1], guesses, length-1, True)]


def drive(stages, plan, guard, output):
    model = ring.Coordinator(stages=len(stages), request=bytes.fromhex(plan['request_sha256']), epoch=0,
                             prompt=plan['prompt_tokens'], max_new=plan['max_new'], context=plan['context'],
                             vocab=plan['vocab'], eos_token_ids=plan['eos_token_ids'],
                             stream_bytes=stages[0].stream_bytes, initial_sequences=[s.sequence for s in stages],
                             proposal_callback=ScriptedProposals(plan))
    for stage in stages:
        stage.start_async()
    sockets = {s.sock: s for s in stages}
    event_index = emitted = peak_busy = 0
    issued, rejected, aborted = {}, {}, set()
    two_row_restores = []
    began = time.monotonic()
    with (output/'schedule.jsonl').open('x') as trace, (output/'tokens.jsonl').open('x') as tokens:
        while not model.done:
            guard.check()
            for command in model.commands():
                if command.op == ring.ROW and command.stage == 0 and command.tentative:
                    proposal = model.proposals.issued[command.row.position].proposal
                    issued[command.row.identity] = dict(position=command.row.position, depth=proposal.depth,
                                                       batch_ticket=proposal.batch_ticket, token=command.row.token)
                stages[command.stage].issue(command)
            if model.done:
                break
            active = [s for s in stages if s.command_pending is not None]
            base.require(active, 'ring scheduler deadlock with no outstanding command')
            peak_busy = max(peak_busy, len(active))
            readable, writable, _ = select.select([s.sock for s in active if not s.transmit],
                                                   [s.sock for s in active if s.transmit], [], 0.2)
            for sock in writable:
                sockets[sock].write_ready()
            for sock in readable:
                completed = sockets[sock].read_ready()
                if completed is None:
                    continue
                command, reply, ack = completed
                if command.op == ring.ABORT_SUFFIX:
                    aborted.add(command.row.position)
                    if command.stage == 0 and len(ack.discarded) == 2:
                        two_row_restores.append(dict(sequence=command.sequence, position=command.row.position,
                                                     discarded=list(ack.discarded), byte_checked=plan['verify_restore']))
                before = len(model.events)
                model.complete(command, ack)
                for event in model.events[before:]:
                    if event['event'] == 'freeze' and event['reason'] == 'miss':
                        work = model.rows[event['cut']]
                        rejected[event['cut']] = issued[work.row.identity]
                trace.write(json.dumps(dict(event='native-reply', op=command.op, stage=command.stage,
                                            sequence=command.sequence, row=command.row.identity,
                                            physical=ack.physical, committed=ack.committed, pending=ack.pending,
                                            discarded=ack.discarded, busy_ms=reply[8], gpu_ms=reply[9],
                                            monotonic_s=time.monotonic()))+'\n')
                while emitted < len(model.emitted):
                    tokens.write(json.dumps(dict(index=emitted, token=model.emitted[emitted],
                                                 committed_monotonic_s=time.monotonic()))+'\n')
                    tokens.flush(); emitted += 1
            while event_index < len(model.events):
                trace.write(json.dumps(model.events[event_index])+'\n'); event_index += 1
            trace.flush()
        while event_index < len(model.events):
            trace.write(json.dumps(model.events[event_index])+'\n'); event_index += 1
    for stage in stages:
        base.require(stage.command_pending is None and not stage.received and not stage.transmit
                     and not stage.pending_rows and stage.physical == stage.committed == model.frontier,
                     'ring wire and native logical/physical state must drain')
        stage.sock.settimeout(0.2)
    coverage = {str(p): dict(target_rejected=p in rejected, native_abort_completed=p in aborted,
                             depth=rejected.get(p, {}).get('depth')) for p in plan['force_miss_positions']}
    # Preserve coverage even if the requested adversarial schedule was not reached.
    evidence = dict(forced_miss_coverage=coverage, rejected_rows=rejected,
                    two_row_stage0_restores=two_row_restores, issued_proposals=issued)
    base.save(output/'ring-coverage.json', evidence)
    base.require(all(c['target_rejected'] and c['native_abort_completed'] for c in coverage.values()),
                 'forced miss did not exercise actual native rejection/rollback')
    base.require(set(plan['required_miss_depths']) <= {r['depth'] for r in rejected.values()},
                 'both requested proposal rejection depths must execute')
    base.require(not plan['require_two_row_abort'] or two_row_restores, 'stage0 two-row suffix must actually restore')
    base.require(model.emitted == plan['scripted_proposal_tokens'][:len(model.emitted)],
                 'native output differs from pinned reference token sequence')
    return dict(output_ids=model.emitted, input_position=model.frontier, ring=evidence,
                scheduler_wall_seconds=time.monotonic()-began, peak_commands_inflight=peak_busy,
                scripted_oracle_assisted=True, speed_claim=False, events=model.events)


def execute(plan, admission, unit):
    # Keep the already reviewed process lifecycle unchanged. Its legacy result
    # label is retained as evidence and bound into an explicit ring attestation.
    try:
        lifecycle.execute(plan, admission, unit, stage_type=RingStage, driver=drive, scripted_proposals=True)
    finally:
        original = Path(plan['output'])/'result.json'
        if original.is_file():
            result = json.loads(original.read_text())
            result.update(schema='ownrt.ring-driver-result.v1', mode='scripted-target-only-ring',
                          scripted_oracle_assisted=True, diagnostic_only=True, speed_claim=False,
                          lifecycle_result=str(original), lifecycle_result_sha256=base.digest(original),
                          lifecycle_mode_note='The original verified-wavefront label names the reused process lifecycle only.',
                          plan_sha256=base.digest(Path(plan['output'])/'plan.json'))
            base.save(Path(plan['output'])/'ring-result.json', result)


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
    base.require(args.admission is not None and args.unit, 'admission and owning unit required')
    plan = json.loads(args.plan.read_text())
    base.require(plan == make_plan(plan['config']), 'plan/source/launch identity changed')
    admission = json.loads(args.admission.read_text())
    base.require(admission['plan_sha256'] == base.digest(args.plan), 'admission plan mismatch')
    execute(plan, admission, args.unit)


if __name__ == '__main__':
    main()

"""Isolated multi-socket adapter; no launch CLI or active runtime imports.

Uses the existing strict target/pending-provider codecs and supplied guarded
owners. This module never loads a reference or creates a process/device owner.
"""
from hashlib import sha256
import json
from pathlib import Path
import select
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'tools'))
import pending_ring_live_driver as pending
from coordinator import RollingCoordinator
from arbiter import Parent, PROVIDER

base, codec, ring = pending.base, pending.codec, pending.ring


class ReplyBuffer(bytearray):
    """Preserve the exact validated wire bytes when the reused codec retires."""
    def clear(self):
        self.last = bytes(self)
        super().clear()


class Stage(pending.PendingStage):
    def start_async(self):
        super().start_async()
        self.received = ReplyBuffer()


def drive(stages, plan, guard, output, *, stop_requested=None):
    base.require(plan.get('rolling_depth2_prototype') is True and plan.get('use_proposals') is True,
                 'explicit isolated rolling actual-proposal mode')
    base.require(not any(k in plan for k in ('recursive_reference','scripted_proposal_tokens',
                     'force_miss_positions','expected_outputs')), 'rolling driver accepts no reference/oracle inputs')
    base.require(len(stages) in (2,4,6) and all(s.stream_bytes == stages[0].stream_bytes for s in stages),
                 'uniform admitted rolling owner geometry')
    model = RollingCoordinator(stages=len(stages), request=bytes.fromhex(plan['request_sha256']), epoch=0,
        prompt=plan['prompt_tokens'], max_new=plan['max_new'], context=plan['context'], vocab=plan['vocab'],
        eos_token_ids=plan['eos_token_ids'], stream_bytes=stages[0].stream_bytes,
        initial_sequences=[s.sequence for s in stages])
    for stage in stages:
        stage.start_async()
    sockets = {s.sock:s for s in stages}
    parent_record = None
    provider_wire = {}
    event_index = emitted = peak_busy = 0
    provider_pairs = 0
    issued, rejected = {}, []
    started = time.monotonic()
    with (output/'schedule.jsonl').open('x') as trace, (output/'tokens.jsonl').open('x') as tokens, \
            (output/'provider-batches.jsonl').open('x') as batches, \
            (output/'final-records.jsonl').open('x') as records:
        def flush_events():
            nonlocal event_index
            while event_index < len(model.events):
                trace.write(json.dumps(model.events[event_index])+'\n')
                event_index += 1
            trace.flush()

        while not model.done:
            guard.check()
            if stop_requested is not None and model.stop_reason is None and stop_requested():
                model.request_stop('cancel')
            for command in model.commands():
                stage = stages[command.stage]
                if command.op == PROVIDER:
                    job = model.provider_jobs[command.sequence]
                    base.require(parent_record is not None and parent_record.row == job.parent.row
                        and parent_record.row_ticket == job.parent.final_row_ticket
                        and parent_record.commit_sequence == job.parent.final_commit_sequence
                        and sha256(parent_record.record).digest() == job.parent.record_sha256
                        and sha256(parent_record.handoff.hidden).digest() == job.parent.hidden_sha256,
                        'provider must consume exact owned final-record lease')
                    base.require(stage.accepted_row is not None and stage.accepted_row.row == job.seed,
                                 'provider consumes actual locally ACCEPTed original ROW')
                    transported = pending.pending_codec.PendingProviderCommand(command.sequence,
                        stage.accepted_row, parent_record, job.serial, accepted_sequence=stage.accepted_sequence,
                        target_physical=job.target_physical, target_committed=job.target_committed,
                        pending_rows=job.pending_rows)
                    provider_wire[command.sequence] = (command, transported)
                    stage.issue_provider(transported)
                else:
                    if command.stage == 0 and command.op == ring.ROW and command.tentative:
                        proposal = model.proposals.issued[command.row.position].proposal
                        evidence = dict(event='issued-proposal',row=command.row.identity,
                            parent=command.row.parent,position=command.row.position,token=command.row.token,
                            sequence=command.sequence,batch_ticket=proposal.batch_ticket,
                            seed_length=proposal.seed_length,depth=proposal.depth,
                            parent_digest=proposal.parent_digest.hex(),after_digest=proposal.after_digest.hex())
                        issued[command.row.identity] = evidence
                        trace.write(json.dumps(evidence)+'\n')
                    stage.issue(command)
            flush_events()
            if model.done:
                break
            active = [s for s in stages if s.command_pending is not None]
            base.require(active, 'rolling scheduler deadlock without an outstanding owner')
            peak_busy = max(peak_busy,len(active))
            readable,writable,_ = select.select([s.sock for s in active if not s.transmit],
                                                [s.sock for s in active if s.transmit],[],0.2)
            for sock in writable:
                sockets[sock].write_ready()
            for sock in readable:
                stage = sockets[sock]
                complete = stage.read_ready()
                if complete is None:
                    continue
                command,reply,result = complete
                if command.op == PROVIDER:
                    proposal_bytes = bytes(stage.shared[codec.PROPOSAL_OFFSET:codec.PROPOSAL_OFFSET+192])
                    reply_bytes = stage.received.last
                    base.require(len(reply_bytes) == base.REPLY.size and base.REPLY.unpack(reply_bytes) == reply,
                                 'exact retired provider transport reply')
                    logical,transported = provider_wire.pop(command.sequence)
                    base.require(command is transported, 'exact provider transport reservation')
                    model.complete_provider(logical, provider_serial=result['provider_serial'],
                        restored_position=result['restored_position'], physical=result['target_physical'],
                        committed=result['target_committed'], pending_rows=result['pending_target_rows'],
                        guesses=tuple(result['guesses']))
                    provider_pairs += 1
                    result = dict(result, speculative_target_use=True, mode='isolated-rolling-depth2',
                        proposal_hex=proposal_bytes.hex(),proposal_sha256=sha256(proposal_bytes).hexdigest(),
                        reply_hex=reply_bytes.hex(),reply_sha256=sha256(reply_bytes).hexdigest())
                    batches.write(json.dumps(result)+'\n'); batches.flush()
                    parent_record = None
                else:
                    final_parent = None
                    if command.stage == len(stages)-1 and command.op == ring.ACCEPT:
                        target_token = model.rows[command.row.position].target_output
                        parent_record = codec.final_record(stage.shared,stage.accepted_row,command,target_token,
                            stages=len(stages),stream_bytes=stage.stream_bytes,vocab=plan['vocab'])
                        final_parent = Parent(parent_record.row,parent_record.row_ticket,parent_record.commit_sequence,
                            sha256(parent_record.handoff.hidden).digest(),sha256(parent_record.record).digest())
                        records.write(json.dumps(dict(schema='ownrt.rolling-final-record.v1',
                            stage=command.stage,sequence=command.sequence,row=command.row.identity,
                            row_ticket=parent_record.row_ticket,record_hex=parent_record.record.hex(),
                            record_sha256=final_parent.record_sha256.hex(),
                            hidden_sha256=final_parent.hidden_sha256.hex(),hidden_bytes=stage.stream_bytes))+'\n')
                        records.flush()
                    before = len(model.events)
                    model.complete(command,result,final_parent=final_parent)
                    for event in model.events[before:]:
                        if event['event'] == 'freeze' and event['reason'] == 'miss':
                            rejected.append(issued[model.rows[event['cut']].row.identity])
                    trace.write(json.dumps(dict(event='native-reply',op=command.op,stage=command.stage,
                        sequence=command.sequence,row=command.row.identity,physical=result.physical,
                        committed=result.committed,pending=result.pending,discarded=result.discarded))+'\n')
                if model.provider.parent is None and model.provider.job is None:
                    parent_record = None
                while emitted < len(model.emitted):
                    tokens.write(json.dumps(dict(index=emitted,token=model.emitted[emitted],
                        committed_monotonic_s=time.monotonic()))+'\n')
                    emitted += 1
                tokens.flush()
                flush_events()
        flush_events()
    base.require(not provider_wire and model.provider.reset_allowed(), 'provider command and parent lease must drain')
    for stage in stages:
        base.require(stage.command_pending is None and not stage.transmit and not stage.received
            and not stage.pending_rows and stage.physical == stage.committed == model.frontier,
            'native target, wire and controller must share final drained frontier')
        stage.sock.settimeout(0.2)
    cancelled = model.stop_reason == 'cancel'
    base.require(cancelled or provider_pairs == model.frontier-1,
                 'completed request must contain every canonical provider pair')
    return dict(schema='ownrt.isolated-rolling-socket-result.v1',output_ids=model.emitted,
        input_position=model.frontier,provider_pairs=provider_pairs,provider_serial=model.provider.serial,
        actual_provider=True,scripted_oracle_assisted=False,speed_claim=False,
        cancelled=cancelled,cancelled_provider_incomplete=model.cancelled_provider_incomplete,
        issued_proposals=list(issued.values()),rejected_proposals=rejected,
        peak_commands_inflight=peak_busy,scheduler_wall_seconds=time.monotonic()-started,events=model.events)

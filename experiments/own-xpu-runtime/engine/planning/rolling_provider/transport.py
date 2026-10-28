"""Guarded multi-socket transport for opt-in rolling qualification.

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
from .coordinator import RollingCoordinator
from .arbiter import Parent, PROVIDER
from . import capture_ready, remote, prefill

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
        self.capture_reader = capture_ready.Reader()

    def read_ready(self):
        if self.plan.get('capture_ready_overlap',False) and isinstance(self.command_pending,pending.pending_codec.PendingProviderCommand):
            return self.capture_reader.read_ready(self)
        return super().read_ready()


def row_identity(row):
    return dict(epoch=row.epoch,id=row.identity,parent=row.parent,position=row.position,
        token=row.token,fixture=row.fixture,request=row.request.hex(),
        before=row.before.hex(),after=row.after.hex())


def command_identity(command):
    seed = command.seed if command.op == PROVIDER else command
    return dict(stage=command.stage,sequence=command.sequence,op=command.op,
        row=row_identity(seed.row),tentative=seed.tentative,
        row_ticket=seed.sequence if command.op in (ring.ROW,PROVIDER) else command.row_ticket)


def drive(stages, plan, guard, output, *, stop_requested=None, epoch=0):
    base.require(plan.get('rolling_depth2') is True and plan.get('use_proposals') is True,
                 'explicit rolling actual-proposal mode')
    base.require(not any(k in plan for k in ('recursive_reference','scripted_proposal_tokens',
                     'force_miss_positions','expected_outputs')), 'rolling driver accepts no reference/oracle inputs')
    base.require(len(stages) in (2,4,6) and all(s.stream_bytes == stages[0].stream_bytes for s in stages),
                 'uniform admitted rolling owner geometry')
    base.require(type(epoch) is int and 0 <= epoch < 2**64 and epoch == plan.get('epoch', 0),
                 'rolling request epoch differs from explicit plan')
    model = RollingCoordinator(stages=len(stages), request=bytes.fromhex(plan['request_sha256']), epoch=epoch,
        prompt=plan['prompt_tokens'], max_new=plan['max_new'], context=plan['context'], vocab=plan['vocab'],
        eos_token_ids=plan['eos_token_ids'], stream_bytes=stages[0].stream_bytes,
        initial_sequences=[s.sequence for s in stages], capture_ready_overlap=plan.get('capture_ready_overlap',False),
        provider_stage=plan.get('provider_stage',0),speculative_depth=plan.get('speculative_depth',2))
    prefill_result = prefill.run(stages, model, plan, base, pending, ring)
    for stage, owner in zip(stages, model.stages):
        owner.sequence = stage.sequence
        stage.start_async()
        stage.provider_serial = prefill_result['prefill_draft_replay']
        stage.physical = stage.committed = prefill_result['prefill_positions']
    sockets = {s.sock:s for s in stages}
    parent_record = None
    provider_wire = {}
    event_index = emitted = peak_busy = 0
    provider_pairs = prefill_result['prefill_draft_replay']
    issued, rejected = {}, []
    trace_limit = plan.get('coordinator_trace_limit')
    base.require(trace_limit is None or type(trace_limit) is int and trace_limit >= 1,
                 'coordinator trace limit requires a positive integer')
    trace_rows = trace_omitted = 0
    started = time.monotonic()
    with (output/'schedule.jsonl').open('x') as trace, (output/'tokens.jsonl').open('x') as tokens, \
            (output/'provider-batches.jsonl').open('x') as batches, \
            (output/'final-records.jsonl').open('x') as records, \
            (output/'commands.jsonl').open('x') as commands_log:
        def write_trace(event):
            nonlocal trace_rows, trace_omitted
            if trace_limit is None or trace_rows < trace_limit - 1:
                trace.write(json.dumps(event)+'\n')
                trace_rows += 1
            else:
                trace_omitted += 1

        def journal(event,command,**fields):
            commands_log.write(json.dumps(dict(schema='ownrt.rolling-command.v1',event=event,
                **command_identity(command),**fields))+'\n')
            commands_log.flush()

        def flush_events():
            nonlocal event_index
            while event_index < len(model.events):
                write_trace(model.events[event_index])
                event_index += 1
            if trace_limit is None:
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
                    seed_owner = stages[0]
                    base.require(seed_owner.accepted_row is not None and seed_owner.accepted_row.row == job.seed,
                                 'provider consumes actual locally ACCEPTed original ROW')
                    transported = pending.pending_codec.PendingProviderCommand(command.sequence,
                        seed_owner.accepted_row, parent_record, job.serial, stage=command.stage, depth=plan.get('speculative_depth',2), accepted_sequence=seed_owner.accepted_sequence,
                        target_physical=job.target_physical, target_committed=job.target_committed,
                        pending_rows=job.pending_rows)
                    provider_wire[command.sequence] = (command, transported)
                    if command.stage:
                        seed_witness=remote.issue(stage,transported,seed_owner)
                    else:
                        stage.issue_provider(transported)
                        seed_witness={}
                    issued_command = transported
                    details = dict(**seed_witness,accepted_seed_sequence=seed_owner.accepted_sequence,
                        provider_serial=job.serial,target_physical=job.target_physical,
                        target_committed=job.target_committed,pending_target_rows=list(job.pending_rows),
                        parent_record_hex=parent_record.record.hex(),
                        parent_record_sha256=sha256(parent_record.record).hexdigest(),
                        parent_hidden_sha256=sha256(parent_record.handoff.hidden).hexdigest(),
                        parent_hidden_bytes=stage.stream_bytes)
                else:
                    if command.stage == 0 and command.op == ring.ROW and command.tentative:
                        proposal = model.proposals.issued[command.row.position].proposal
                        evidence = dict(event='issued-proposal',row=command.row.identity,
                            parent=command.row.parent,position=command.row.position,token=command.row.token,
                            sequence=command.sequence,batch_ticket=proposal.batch_ticket,
                            seed_length=proposal.seed_length,depth=proposal.depth,
                            parent_digest=proposal.parent_digest.hex(),after_digest=proposal.after_digest.hex())
                        issued[command.row.identity] = evidence
                        write_trace(evidence)
                    stage.issue(command)
                    issued_command = command
                    source = command.source
                    details = dict(source=None if source is None else dict(stage=source.stage,
                        ticket=source.ticket,bytes=len(source.data),sha256=source.digest.hex()))
                details.update(target_physical=stage.physical,target_committed=stage.committed,
                    pending_target_rows=[c.row.identity for c in stage.pending_rows])
                provenance = issued.get(command.row.identity)
                details['proposal'] = None if provenance is None else {k:provenance[k] for k in
                    ('batch_ticket','seed_length','depth','parent_digest','after_digest')}
                journal('issued',issued_command,request_hex=stage.transmit.hex(),
                    metadata_hex=bytes(stage.shared[pending.wire.ROW_OFFSET:pending.wire.ROW_OFFSET+224]).hex(),
                    **details)
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
                if isinstance(complete,capture_ready.Captured):
                    command = complete.command
                    logical,transported = provider_wire[command.sequence]
                    base.require(command is transported,'capture-ready retains exact provider reservation')
                    model.capture_provider(logical)
                    journal('parent-captured',command,reply_hex=complete.header.hex(),
                        metadata_hex=complete.identity.hex())
                    continue
                command,reply,result = complete
                if command.op == PROVIDER:
                    proposal_bytes = bytes(stage.shared[codec.PROPOSAL_OFFSET:codec.PROPOSAL_OFFSET+codec.proposal_size(command.depth)])
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
                    result = dict(result, speculative_target_use=True, mode='rolling-depth3' if command.depth==3 else 'rolling-depth2',
                        proposal_hex=proposal_bytes.hex(),proposal_sha256=sha256(proposal_bytes).hexdigest(),
                        reply_hex=reply_bytes.hex(),reply_sha256=sha256(reply_bytes).hexdigest())
                    journal('completed',command,reply_hex=reply_bytes.hex(),
                        metadata_hex=proposal_bytes.hex(),provider=result)
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
                    offset,size = (pending.wire.ROW_OFFSET,224) if command.op == ring.ROW else (pending.wire.ACK_OFFSET,128)
                    journal('completed',command,reply_hex=stage.received.last.hex(),
                        metadata_hex=bytes(stage.shared[offset:offset+size]).hex(),
                        ack=dict(epoch=result.epoch,stage=result.stage,sequence=result.sequence,row_id=result.row_id,
                            row_ticket=result.row_ticket,physical=result.physical,committed=result.committed,
                            pending=result.pending,discarded=list(result.discarded),token=result.token,
                            sticky_error=result.sticky_error,stream_bytes=0 if result.stream is None else len(result.stream),
                            stream_sha256=None if result.stream is None else sha256(result.stream).hexdigest()))
                    write_trace(dict(event='native-reply',op=command.op,stage=command.stage,
                        sequence=command.sequence,row=command.row.identity,physical=result.physical,
                        committed=result.committed,pending=result.pending,discarded=result.discarded))
                if model.provider.parent is None and model.provider.job is None:
                    parent_record = None
                while emitted < len(model.emitted):
                    tokens.write(json.dumps(dict(index=emitted,token=model.emitted[emitted],
                        committed_monotonic_s=time.monotonic()))+'\n')
                    emitted += 1
                tokens.flush()
                flush_events()
        flush_events()
        if trace_limit is not None:
            trace.write(json.dumps(dict(event='coordinator-trace-summary',
                retained=trace_rows, omitted=trace_omitted))+'\n')
            trace.flush()
    base.require(not provider_wire and model.provider.reset_allowed(), 'provider command and parent lease must drain')
    for stage in stages:
        base.require(stage.command_pending is None and not stage.transmit and not stage.received
            and not stage.pending_rows and stage.physical == stage.committed == model.frontier,
            'native target, wire and controller must share final drained frontier')
        stage.sock.settimeout(0.2)
    cancelled = model.stop_reason == 'cancel'
    base.require(cancelled or provider_pairs == model.frontier-1,
                 'completed request must contain every canonical provider pair')
    return dict(schema='ownrt.rolling-socket-result.v1',output_ids=model.emitted,
        input_position=model.frontier,provider_pairs=provider_pairs,provider_serial=model.provider.serial,
        **prefill_result,
        actual_provider=True,scripted_oracle_assisted=False,speed_claim=False,
        cancelled=cancelled,cancelled_provider_incomplete=model.cancelled_provider_incomplete,
        issued_proposals=list(issued.values()),rejected_proposals=rejected,
        peak_commands_inflight=peak_busy,scheduler_wall_seconds=time.monotonic()-started,events=model.events,
        coordinator_trace=dict(limit=trace_limit,retained=trace_rows,omitted=trace_omitted,attempts=trace_rows+trace_omitted))

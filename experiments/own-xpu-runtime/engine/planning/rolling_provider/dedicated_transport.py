"""Separate native provider transport; no subprocess creation or target ledger.

The caller owns guarded process launch. Only per-token requests are admitted;
provider bulk-prefill and persistent reset require a separate qualified path.
"""
from hashlib import sha256
import json
from pathlib import Path
import select
import struct
import time
from types import SimpleNamespace

from .transport import Stage, ReplyBuffer, base, codec, pending, ring, row_identity
from .dedicated import DedicatedCoordinator, ProviderCommand
from .arbiter import Parent
from . import remote

MAGIC, VERSION, PROPOSAL_OFFSET = 0x50525631, 1, 4096
HEADER = struct.Struct('<8IQ32s56s')


class Provider:
    """Adapt an already launched base.Stage's socket/private mmap, not its codec."""
    def __init__(self, owner):
        self.owner = owner
        self.sock, self.shared, self.guard, self.plan = owner.sock, owner.shared, owner.guard, owner.plan
        self.sequence = owner.sequence
        self.command_pending = None
        self.transmit = b''
        self.received = ReplyBuffer()
        self.stream_bytes = None
        self.provider_serial = 0
        self.transport_command = None

    def _reply(self, raw, *, sequence, token, size):
        base.require(len(raw) == base.REPLY.size, 'complete dedicated reply')
        reply = base.REPLY.unpack(raw)
        base.require(reply == (0, token, 0, size, sequence, -1, MAGIC, VERSION, 0., 0., 0., 0.),
                     'dedicated reply identity/status/timings')
        return reply

    def _blocking_reply(self):
        raw = bytearray()
        deadline = time.monotonic()+self.plan.get('seconds', 120)
        while len(raw) < base.REPLY.size:
            self.guard.check()
            base.require(time.monotonic() < deadline, 'dedicated reply timeout')
            ready, _, _ = select.select([self.sock], [], [], .2)
            if ready:
                chunk = self.sock.recv(base.REPLY.size-len(raw))
                base.require(bool(chunk), 'dedicated owner closed socket')
                raw.extend(chunk)
        return bytes(raw)

    def receive_ready(self, *, target_stages=None, depth=None, request=None, epoch=0):
        target_stages = len(self.plan['stages']) if target_stages is None else target_stages
        depth = self.plan.get('speculative_depth', 2) if depth is None else depth
        request = bytes.fromhex(self.plan['request_sha256']) if request is None else request
        raw = self._blocking_reply()
        values = HEADER.unpack(bytes(self.shared[:HEADER.size]))
        stream = values[4]
        base.require(target_stages in (2, 3) and depth in (2, 3) and stream > 0
                     and stream <= base.SLOT, 'dedicated source geometry')
        base.require(values == (MAGIC, VERSION, 128, 0, stream, target_stages, depth, 0,
                                epoch, request, bytes(56)), 'dedicated private header/source identity')
        self._reply(raw, sequence=0, token=-1, size=stream)
        base.require(self.sequence == 0 and self.command_pending is None, 'dedicated initial ready only')
        self.stream_bytes = self.owner.stream_bytes = stream
        return base.REPLY.unpack(raw)

    def start_async(self):
        base.require(self.stream_bytes is not None and self.command_pending is None, 'dedicated ready before drive')
        self.sock.setblocking(False)

    def issue(self, command, job, seed_owner, parent):
        self.guard.check()
        base.require(type(command) is ProviderCommand and self.command_pending is None
                     and not self.transmit and not self.received, 'exclusive independent provider owner')
        base.require(command.sequence == self.sequence+1 and job.command is command
                     and job.serial == self.provider_serial+1, 'dedicated command/serial sequence')
        seed = seed_owner.accepted_row
        base.require(seed is not None and seed.row == job.seed
                     and seed.stage == 0 and seed.op == ring.ROW and seed_owner.accepted_sequence > seed.sequence,
                     'dedicated actual original accepted seed lease')
        # ACCEPT verifies a proposal without rewriting its immutable original
        # ROW flag. Authenticate native publication, not a normalized host flag.
        remote.seed_journal(seed_owner, SimpleNamespace(seed=seed,
            accepted_sequence=seed_owner.accepted_sequence,
            depth=self.plan.get('speculative_depth', 2)), self.stream_bytes)
        base.require(parent is not None and parent.row == job.parent.row
                     and parent.row_ticket == job.parent.final_row_ticket
                     and parent.commit_sequence == job.parent.final_commit_sequence
                     and sha256(parent.record).digest() == job.parent.record_sha256
                     and sha256(parent.handoff.hidden).digest() == job.parent.hidden_sha256,
                     'dedicated exact final parent lease')
        # Reuse the proposal provenance codec with actual source objects. This
        # object has no stage or target physical/pending fields.
        self.transport_command = SimpleNamespace(sequence=command.sequence, seed=seed,
            parent=parent, serial=job.serial, depth=self.plan.get('speculative_depth', 2))
        self.sequence = self.owner.sequence = command.sequence
        self.command_pending = command
        row = command.row
        self.transmit = base.REQUEST.pack(27, row.token, row.position, row.fixture,
            self.transport_command.depth, command.sequence, MAGIC, VERSION)

    def write_ready(self):
        base.require(self.transmit and self.command_pending is not None, 'dedicated pending send')
        try:
            count = self.sock.send(self.transmit)
        except BlockingIOError:
            return
        base.require(count > 0, 'dedicated closed command channel')
        self.transmit = self.transmit[count:]

    def read_ready(self):
        base.require(self.command_pending is not None and not self.transmit, 'dedicated outstanding reply')
        try:
            chunk = self.sock.recv(base.REPLY.size-len(self.received))
        except BlockingIOError:
            return None
        base.require(bool(chunk), 'dedicated owner closed reply channel')
        self.received.extend(chunk)
        if len(self.received) < base.REPLY.size:
            return None
        command, wire = self.command_pending, self.transport_command
        size = codec.proposal_size(wire.depth)
        raw = bytes(self.shared[PROPOSAL_OFFSET:PROPOSAL_OFFSET+size])
        result = codec.decode_proposal(raw, wire, vocab=self.plan['vocab'], context=self.plan['context'])
        reply = self._reply(bytes(self.received), sequence=command.sequence,
                            token=result['guesses'][0] if result['guesses'] else -1, size=size)
        self.provider_serial = result['provider_serial']
        result.update(owner='provider', proposal_hex=raw.hex(), proposal_sha256=sha256(raw).hexdigest(),
                      reply_hex=bytes(self.received).hex(), speculative_target_use=True)
        self.command_pending = self.transport_command = None
        self.received.clear()
        return command, reply, result

    def control(self, op):
        base.require(op in (4, 5) and self.command_pending is None and not self.transmit
                     and not self.received, 'dedicated only drained dump/finish controls')
        self.sock.settimeout(.2)
        self.sequence += 1
        self.owner.sequence = self.sequence
        raw = base.REQUEST.pack(op, 0, 0, 0, 0, self.sequence, MAGIC, VERSION)
        # The socket timeout is a guard polling interval, not a retry of a request.
        view = memoryview(raw)
        while view:
            self.guard.check()
            _, ready, _ = select.select([], [self.sock], [], .2)
            if ready:
                n = self.sock.send(view)
                base.require(n > 0, 'dedicated closed control channel')
                view = view[n:]
        return self._reply(self._blocking_reply(), sequence=self.sequence, token=-1, size=0)


def drive(stages, provider, plan, guard, output, *, stop_requested=None, epoch=0):
    base.require(plan.get('rolling_depth2') is True and plan.get('use_proposals') is True,
                 'explicit dedicated rolling proposal mode')
    base.require(not any(k in plan for k in ('recursive_reference', 'scripted_proposal_tokens',
        'force_miss_positions', 'expected_outputs')), 'dedicated accepts no oracle inputs')
    base.require(not plan.get('prefill_rows') and not plan.get('prefill_chunk_size') and not plan.get('prefill_pipeline')
                 and not plan.get('persistent_reset'), 'dedicated first gate is per-token without reset')
    base.require(len(stages) in (2, 3) and provider.stream_bytes is not None
                 and all(s.stream_bytes == provider.stream_bytes for s in stages), 'dedicated admitted geometry')
    base.require(epoch == 0 and epoch == plan.get('epoch', 0), 'dedicated initial epoch only')
    model = DedicatedCoordinator(stages=len(stages), request=bytes.fromhex(plan['request_sha256']),
        epoch=epoch, prompt=plan['prompt_tokens'], max_new=plan['max_new'], context=plan['context'],
        vocab=plan['vocab'], eos_token_ids=plan['eos_token_ids'], stream_bytes=provider.stream_bytes,
        initial_sequences=[s.sequence for s in stages], provider_sequence=provider.sequence,
        speculative_depth=plan.get('speculative_depth', 2))
    for stage in stages:
        stage.start_async()
    provider.start_async()
    owners = stages+[provider]
    sockets = {s.sock:s for s in owners}
    output = Path(output)
    parent_record = None
    issued, rejected, event_index, emitted, peak_busy, provider_pairs = {}, [], 0, 0, 0, 0
    started = time.monotonic()
    emitted_elapsed = []
    with (output/'schedule.jsonl').open('x') as trace, (output/'tokens.jsonl').open('x') as tokens, \
         (output/'provider-batches.jsonl').open('x') as batches, \
         (output/'final-records.jsonl').open('x') as records, (output/'commands.jsonl').open('x') as commands:
        def log(event, command, **details):
            identity = dict(owner='provider') if type(command) is ProviderCommand else dict(stage=command.stage)
            commands.write(json.dumps(dict(event=event, sequence=command.sequence, op=command.op,
                row=row_identity(command.row), **identity, **details))+'\n'); commands.flush()
        def flush():
            nonlocal event_index, emitted
            while event_index < len(model.events):
                trace.write(json.dumps(model.events[event_index])+'\n'); event_index += 1
            while emitted < len(model.emitted):
                committed = time.monotonic()
                emitted_elapsed.append(committed-started)
                tokens.write(json.dumps(dict(index=emitted, token=model.emitted[emitted],
                    committed_monotonic_s=committed, emitted_elapsed_s=committed-started))+'\n'); emitted += 1
            trace.flush(); tokens.flush()
        while not model.done:
            guard.check()
            if stop_requested is not None and model.stop_reason is None and stop_requested():
                model.request_stop('cancel')
            for command in model.commands():
                if type(command) is ProviderCommand:
                    owner = provider
                    job = model.provider_jobs[command.sequence]
                    provider.issue(command, job, stages[0], parent_record)
                    log('issued', command, request_hex=provider.transmit.hex(), provider_serial=job.serial,
                        accepted_seed_sequence=stages[0].accepted_sequence,
                        parent_record_hex=parent_record.record.hex(),
                        parent_hidden_sha256=sha256(parent_record.handoff.hidden).hexdigest())
                else:
                    owner = stages[command.stage]
                    if command.stage == 0 and command.op == ring.ROW and command.tentative:
                        proposal = model.proposals.issued[command.row.position].proposal
                        issued[command.row.identity] = dict(event='issued-proposal', row=command.row.identity,
                            parent=command.row.parent, position=command.row.position, token=command.row.token,
                            sequence=command.sequence, batch_ticket=proposal.batch_ticket,
                            seed_length=proposal.seed_length, depth=proposal.depth,
                            parent_digest=proposal.parent_digest.hex(), after_digest=proposal.after_digest.hex())
                        trace.write(json.dumps(issued[command.row.identity])+'\n')
                    owner.issue(command)
                    log('issued', command, request_hex=owner.transmit.hex())
            flush()
            if model.done:
                break
            active = [s for s in owners if s.command_pending is not None]
            base.require(active, 'dedicated scheduler deadlock')
            peak_busy = max(peak_busy, len(active))
            readable, writable, _ = select.select([s.sock for s in active if not s.transmit],
                [s.sock for s in active if s.transmit], [], .2)
            for sock in writable:
                sockets[sock].write_ready()
            for sock in readable:
                owner = sockets[sock]
                complete = owner.read_ready()
                if complete is None:
                    continue
                command, reply, result = complete
                if owner is provider:
                    # Native has completed capture and restored its private state;
                    # release source leases only now (there is no early capture ACK).
                    model.capture_provider(command)
                    model.complete_provider(command, provider_serial=result['provider_serial'],
                        restored_position=result['restored_position'], guesses=tuple(result['guesses']))
                    provider_pairs += 1
                    batches.write(json.dumps(result)+'\n'); batches.flush()
                    log('completed', command, provider=result)
                    parent_record = None
                else:
                    final_parent = None
                    if command.stage == len(stages)-1 and command.op == ring.ACCEPT:
                        parent_record = codec.final_record(owner.shared, owner.accepted_row, command,
                            model.rows[command.row.position].target_output, stages=len(stages),
                            stream_bytes=owner.stream_bytes, vocab=plan['vocab'])
                        final_parent = Parent(parent_record.row, parent_record.row_ticket,
                            parent_record.commit_sequence, sha256(parent_record.handoff.hidden).digest(),
                            sha256(parent_record.record).digest())
                        records.write(json.dumps(dict(stage=command.stage, sequence=command.sequence,
                            row=command.row.identity, row_ticket=parent_record.row_ticket,
                            record_hex=parent_record.record.hex(), record_sha256=final_parent.record_sha256.hex(),
                            hidden_sha256=final_parent.hidden_sha256.hex(), hidden_bytes=owner.stream_bytes))+'\n')
                        records.flush()
                    before = len(model.events)
                    model.complete(command, result, final_parent=final_parent)
                    for event in model.events[before:]:
                        if event['event'] == 'freeze' and event['reason'] == 'miss':
                            rejected.append(issued[model.rows[event['cut']].row.identity])
                    log('completed', command, reply_hex=owner.received.last.hex(),
                        physical=result.physical, committed=result.committed, pending=result.pending)
                if model.provider.parent is None and model.provider.job is None:
                    parent_record = None
                flush()
        flush()
    base.require(provider.command_pending is None and not provider.transmit and not provider.received
                 and not model.provider_jobs and model.provider.reset_allowed(), 'dedicated provider drained')
    for stage in stages:
        base.require(stage.command_pending is None and not stage.transmit and not stage.received
            and not stage.pending_rows and stage.physical == stage.committed == model.frontier,
            'dedicated native target frontier drained')
        stage.sock.settimeout(.2)
    provider.sock.settimeout(.2)
    cancelled = model.stop_reason == 'cancel'
    base.require(cancelled or provider_pairs == model.frontier-1, 'dedicated complete canonical pair coverage')
    return dict(schema='ownrt.dedicated-socket-result.v1', output_ids=model.emitted,
        input_position=model.frontier, provider_pairs=provider_pairs, provider_serial=model.provider.serial,
        emitted_elapsed_seconds=emitted_elapsed,
        prefill_positions=0, prefill_draft_replay=0, actual_provider=True, scripted_oracle_assisted=False,
        speed_claim=False, cancelled=cancelled, cancelled_provider_incomplete=model.cancelled_provider_incomplete,
        issued_proposals=list(issued.values()), rejected_proposals=rejected,
        peak_commands_inflight=peak_busy, scheduler_wall_seconds=time.monotonic()-started, events=model.events,
        coordinator_trace=dict(limit=None, retained=event_index, omitted=0, attempts=event_index))

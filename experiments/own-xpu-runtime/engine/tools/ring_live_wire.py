"""Owned final-commit records and actual depth-two provider publications."""
from dataclasses import dataclass
from hashlib import sha256
import struct

import ring_wire as wire
import live_draft as handoff_codec

ring = wire.ring
FINAL_OFFSET = 2*wire.SLOT+2560
FINAL_HEADER = struct.Struct('<4IQ')
FINAL_MAGIC, FINAL_VERSION, FINAL_BYTES = 0x52464331, 1, 360
PROPOSAL_OFFSET = 2*wire.SLOT+1536
PROPOSAL = struct.Struct('<4I6Q8i32s32s32s')
STEP = 27
assert FINAL_HEADER.size+wire.ROW_META.size+handoff_codec.HEADER.size == FINAL_BYTES
assert PROPOSAL.size == 192
need = wire.need


@dataclass(frozen=True)
class FinalRecord:
    row: ring.Row
    row_ticket: int
    commit_sequence: int
    metadata: bytes
    record: bytes
    handoff: handoff_codec.Handoff


@dataclass(frozen=True)
class ProviderCommand:
    sequence: int
    seed: ring.Command
    parent: FinalRecord
    serial: int
    op: int = STEP
    stage: int = 0


def final_record(shared, row_command, commit_command, output_token, *, stages, stream_bytes, vocab):
    """Bind a stable final-owned record to our actual accepted target commands."""
    need(row_command.op == ring.ROW and commit_command.op == ring.ACCEPT
         and row_command.stage == commit_command.stage == stages-1
         and row_command.row == commit_command.row
         and commit_command.row_ticket == row_command.sequence
         and not row_command.tentative and not commit_command.tentative, 'verified final target pair')
    before = bytes(shared[FINAL_OFFSET:FINAL_OFFSET+FINAL_BYTES])
    need(len(before) == FINAL_BYTES, 'complete final record')
    magic, version, size, stage, marker = FINAL_HEADER.unpack(before[:FINAL_HEADER.size])
    need((magic, version, size, stage, marker) ==
         (FINAL_MAGIC, FINAL_VERSION, FINAL_BYTES, stages-1, commit_command.sequence),
         'final-owned record header/publication marker')
    expected, _ = wire.row_metadata(commit_command, final=True, stream_bytes=stream_bytes)
    fields = list(wire.ROW_META.unpack(expected)); fields[14] = row_command.sequence
    metadata = before[24:248]
    need(metadata == wire.ROW_META.pack(*fields), 'final-owned immutable parent record')
    hidden = bytes(shared[handoff_codec.HIDDEN_OFFSET:handoff_codec.HIDDEN_OFFSET+stream_bytes])
    handoff = handoff_codec.decode(before[248:], hidden, stream_bytes=stream_bytes, stages=stages, vocab=vocab)
    handoff_codec.bind(handoff, position=row_command.row.position, input_token=row_command.row.token,
                       row_ticket=row_command.sequence, commit_sequence=commit_command.sequence,
                       output_token=output_token, fixture=row_command.row.fixture)
    after = bytes(shared[FINAL_OFFSET:FINAL_OFFSET+FINAL_BYTES])
    need(after == before, 'final publication changed while copying owned hidden')
    return FinalRecord(row_command.row, row_command.sequence, commit_command.sequence, metadata, before, handoff)


def seed_metadata(command, *, stream_bytes):
    seed, parent = command.seed, command.parent
    need(command.stage == 0 and command.op == STEP and command.sequence > seed.sequence > 0
         and seed.stage == 0 and seed.op == ring.ROW and not seed.tentative
         and command.serial > 0, 'verified seed provider command identity')
    need(seed.row.epoch == parent.row.epoch and seed.row.request == parent.row.request
         and seed.row.position == parent.row.position+1 and seed.row.parent == parent.row.identity
         and seed.row.before == parent.row.after
         and (not parent.handoff.head or seed.row.token == parent.handoff.next_token),
         'canonical verified seed and committed parent ancestry')
    control = ring.Command(0, ring.ACCEPT, command.sequence, seed.row, False, seed.sequence)
    return wire.row_metadata(control, final=False, stream_bytes=stream_bytes)[0]


def decode_proposal(raw, command, *, vocab, context):
    need(len(raw) == PROPOSAL.size, 'complete provider proposal metadata')
    fields = PROPOSAL.unpack(raw)
    seed, parent = command.seed.row, command.parent
    head = seed.fixture > 0
    expected_depth = (2 if seed.position < context else 1) if head else 0
    expected = (0x44525032, 1, 192, 2+int(head), seed.epoch, command.sequence,
                seed.identity, seed.parent, parent.commit_sequence, command.serial,
                seed.position, seed.position, 2, expected_depth)
    need(fields[:14] == expected, 'provider batch owner/seed/parent/commit/serial/depth identity')
    guesses = fields[14:16]
    need(fields[16:18] == (0, 1), 'provider sticky failure or missing canonical restoration')
    need(fields[18:] == (seed.request, seed.after, sha256(parent.handoff.hidden).digest()),
         'provider request/prefix/hidden provenance')
    need(all(0 <= guesses[i] < vocab if i < expected_depth else guesses[i] == -1 for i in range(2)),
         'provider guess vocabulary/availability')
    return dict(epoch=seed.epoch, sequence=command.sequence, seed_row=seed.identity,
                parent_row=seed.parent, final_commit=parent.commit_sequence, provider_serial=command.serial,
                seed_position=seed.position, restored_position=seed.position,
                available_depth=expected_depth, guesses=list(guesses[:expected_depth]),
                request_sha256=seed.request.hex(), seed_prefix_sha256=seed.after.hex(),
                parent_hidden_sha256=sha256(parent.handoff.hidden).hexdigest(),
                restored=True, speculative_target_use=False)

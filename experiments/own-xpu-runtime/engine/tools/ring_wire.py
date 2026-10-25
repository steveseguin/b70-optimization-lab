"""Exact little-endian native ring24–26 codec; no device/process operations."""
from hashlib import sha256
from pathlib import Path
import struct
import sys

PLANNING = Path(__file__).resolve().parents[1] / 'planning'
if str(PLANNING) not in sys.path:
    sys.path.insert(0, str(PLANNING))
import ring_coordinator as ring
from ring_contract import append_prefix, need

SLOT = 65536
ROW_OFFSET, ACK_OFFSET = 2*SLOT+1024, 2*SLOT+2048
ROW_META = struct.Struct('<4I3Q10i32s32s32s32s16s')
ACK_META = struct.Struct('<4I4Q8i48s')
assert ROW_META.size == 224 and ACK_META.size == 128
EMPTY_SHA = sha256(b'').digest()


def row_metadata(command, *, final, stream_bytes):
    """Return submitted metadata plus privately owned input payload."""
    row = command.row
    need(command.op in (ring.ROW, ring.ACCEPT, ring.ABORT_SUFFIX) and row is not None,
         'ring24–26 only')
    need(0 < command.sequence < 2**31 and 0 <= command.stage < 64, 'wire owner/sequence bounds')
    need(type(command.tentative) is bool and type(final) is bool, 'wire boolean flags')
    need(0 < row.identity < 2**64 and 0 <= row.parent < row.identity
         and 0 <= row.epoch < 2**64, 'global row identity')
    need(len(row.request) == 32 and row.after == append_prefix(row.before, row.position, row.token),
         'immutable token prefix')
    need(0 < stream_bytes <= SLOT and stream_bytes % 4 == 0, 'full F32 stream extent')
    source, source_ticket, payload = -1, 0, b''
    if command.op == ring.ROW:
        need(command.row_ticket == 0 and not (final and command.tentative), 'ROW original ticket/final verification')
        if command.stage:
            publication = command.source
            need(publication is not None and publication.row == row
                 and publication.stage == command.stage-1 and 0 < publication.ticket < 2**31,
                 'upstream publication owner/row/ticket')
            need(isinstance(publication.data, bytes) and len(publication.data) == stream_bytes,
                 'immutable complete upstream stream')
            payload = bytes(publication.data)
            need(sha256(payload).digest() == publication.digest, 'upstream payload digest')
            source, source_ticket = publication.stage, publication.ticket
        else:
            need(command.source is None, 'first-stage input must be empty')
    else:
        need(command.source is None and 0 < command.row_ticket < command.sequence,
             'resolution original ROW ticket; no source payload')
    return ROW_META.pack(0x52494e47, 1, ROW_META.size, int(command.tentative),
                         row.epoch, row.identity, row.parent, row.position, row.token, row.fixture,
                         command.stage, int(final), source, source_ticket, 0, len(payload), 1,
                         row.request, row.before, row.after, sha256(payload).digest(), bytes(16)), payload


def validate_publication(raw, submitted, sequence, payload, *, final, stream_bytes):
    need(len(raw) == ROW_META.size and len(submitted) == ROW_META.size,
         'exact ROW metadata extent')
    need(isinstance(payload, bytes) and len(payload) == (0 if final else stream_bytes),
         'complete owned published stream')
    expected = list(ROW_META.unpack(submitted))
    expected[3] |= 2
    expected[14], expected[15], expected[20] = sequence, len(payload), sha256(payload).digest()
    need(raw == ROW_META.pack(*expected), 'published row/owner/ticket/lineage/payload SHA mismatch')


def resolution_ack(raw, command, pending, *, physical, committed, verify_restore):
    need(len(raw) == ACK_META.size, 'exact resolution ACK extent')
    fields = ACK_META.unpack(raw)
    magic, version, size, flags, epoch, identity, discard0, discard1 = fields[:8]
    owner, sequence, ticket, actual_physical, actual_committed, count, remaining, error, reserved = fields[8:]
    need((magic, version, size) == (0x5241434b, 1, ACK_META.size)
         and flags in (0, 1) and reserved == bytes(48), 'ACK header/reserved flags')
    need(error == 0, 'native sticky error')
    need(command.op in (ring.ACCEPT, ring.ABORT_SUFFIX) and pending, 'resolution requires pending ROW')
    original = pending[0]
    need(original.sequence == command.row_ticket and original.row == command.row
         and original.tentative == command.tentative, 'resolution exact original ROW')
    need((epoch, identity, owner, sequence, ticket) ==
         (command.row.epoch, command.row.identity, command.stage, command.sequence, command.row_ticket),
         'ACK epoch/global row/owner/wire ticket')
    discarded = tuple(c.row.identity for c in pending) if command.op == ring.ABORT_SUFFIX else ()
    need(len(discarded) <= 2 and count == len(discarded)
         and (discard0, discard1) == (discarded+(0, 0))[:2], 'ACK exact discarded suffix')
    if command.op == ring.ACCEPT:
        expected = (physical, committed+1, len(pending)-1)
        need(flags == 0, 'ACCEPT cannot attest restore')
    else:
        need(all(c.tentative for c in pending), 'ABORT only tentative suffix')
        expected = (committed, committed, 0)
        need(flags == int(verify_restore), 'required full restore verification policy')
    need((actual_physical, actual_committed, remaining) == expected, 'ACK physical/logical/pending cursors')
    return ring.Ack(epoch, owner, sequence, identity, ticket, *expected, discarded)

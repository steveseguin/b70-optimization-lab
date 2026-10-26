"""Opt-in nonterminal provider capture notification; no command retirement."""
from dataclasses import dataclass
from hashlib import sha256
import struct
import math

import pending_ring_live_driver as pending
base, codec = pending.base, pending.live.codec
CAPTURE = struct.Struct('<QII6Q32s32s')
MAGIC, VERSION, STATUS = 0x315950414352574f, 1, 2
assert CAPTURE.size == 128


@dataclass(frozen=True)
class Captured:
    command: object
    header: bytes
    identity: bytes


def expected(command):
    row = command.seed.row
    return (MAGIC, VERSION, CAPTURE.size, row.epoch, command.sequence, row.identity,
        row.parent, command.parent.commit_sequence, command.serial, row.request,
        sha256(command.parent.record).digest())


def decode(raw, command):
    base.require(len(raw) == CAPTURE.size and CAPTURE.unpack(raw) == expected(command),
                 'capture-ready exact owned parent/request/seed/provider identity')


class Reader:
    def __init__(self):
        self.header = None
        self.captured_sequence = None

    def read_ready(self, stage):
        stage.guard.check()
        command = stage.command_pending
        base.require(isinstance(command, pending.pending_codec.PendingProviderCommand),
                     'capture-ready only for owned provider command')
        wanted = CAPTURE.size if self.header is not None else base.REPLY.size
        try:
            piece = stage.sock.recv(wanted-len(stage.received))
        except BlockingIOError:
            return None
        base.require(piece, 'provider capture/reply channel closed')
        stage.received.extend(piece)
        if len(stage.received) != wanted:
            return None
        if self.header is not None:
            raw = bytes(stage.received)
            decode(raw, command)
            event = Captured(command, self.header, raw)
            self.captured_sequence = command.sequence
            self.header = None
            stage.received.clear()
            return event
        reply = base.REPLY.unpack(stage.received)
        base.require(not stage.transmit and reply[2] == 0 and reply[4] == command.sequence
                     and reply[5:8] == (0,0,0), 'provider capture/reply owner/error identity')
        if reply[0] == STATUS:
            base.require(self.captured_sequence != command.sequence and reply[1] == -1
                         and reply[3] == CAPTURE.size and math.isfinite(reply[8]) and reply[8] >= 0
                         and reply[9:] == (0,0,0),
                         'duplicate/malformed nonterminal capture event')
            self.header = bytes(stage.received)
            stage.received.clear()
            return None
        base.require(reply[0] == 0 and reply[3] == 192 and self.captured_sequence == command.sequence,
                     'provider completion requires prior matching capture event')
        result = codec.decode_proposal(bytes(stage.shared[codec.PROPOSAL_OFFSET:codec.PROPOSAL_OFFSET+192]),
            command, vocab=stage.plan['vocab'], context=stage.plan['context'])
        base.require(reply[1] == (result['guesses'][0] if result['guesses'] else -1),
                     'provider reply token differs from batch')
        base.require((stage.physical,stage.committed,tuple(c.row.identity for c in stage.pending_rows)) ==
                     (command.target_physical,command.target_committed,command.pending_rows),
                     'provider changed pending target cursor/identity')
        result.update(target_physical=stage.physical,target_committed=stage.committed,
            pending_target_rows=list(command.pending_rows),pending_depth=len(command.pending_rows),
            accepted_seed_sequence=command.accepted_sequence,original_seed_tentative=command.seed.tentative)
        stage.provider_serial = command.serial
        stage.command_pending = None
        stage.received.clear()
        self.captured_sequence = None
        return command,reply,result

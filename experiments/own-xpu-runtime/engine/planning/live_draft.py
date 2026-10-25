"""Checked, owned true-pair handoffs for the existing native MTP provider.

No model operations or process management. A proposal is usable only for the
position immediately after its confirmed input; the target still verifies it.
"""
from dataclasses import dataclass
import hashlib
import struct

SLOT = 65536
HEADER_OFFSET = 2 * SLOT + 512
HIDDEN_OFFSET = 2 * SLOT + 4096
HEADER = struct.Struct('<12i64s')
MAGIC, VERSION, STEP = 0x4d545031, 1, 23


def require(ok, message):
    if not ok:
        raise ValueError(message)


@dataclass(frozen=True)
class Handoff:
    position: int
    final_stage: int
    stages: int
    row_ticket: int
    commit_sequence: int
    input_token: int
    next_token: int
    head: int
    hidden: bytes
    header: bytes


def decode(header, hidden, *, stream_bytes, stages, vocab):
    """Copy and authenticate exact native bytes before either slot is reused."""
    header, hidden = bytes(header), bytes(hidden)
    require(len(header) == HEADER.size, 'live draft header extent')
    magic, version, size, pos, final, count, ticket, seq, token, nxt, head, reserved, sha = HEADER.unpack(header)
    require(magic == MAGIC and version == VERSION and reserved == 0, 'live draft schema')
    require(type(stream_bytes) is int and 0 < stream_bytes <= SLOT and stream_bytes % 4 == 0
            and size == stream_bytes == len(hidden), 'live draft hidden extent')
    require(type(stages) is int and stages > 0 and count == stages and final == stages - 1,
            'live draft final-stage identity')
    require(pos >= 0 and 0 < ticket < seq and 0 <= token < vocab and head in (0, 1),
            'live draft committed identity')
    require(0 <= nxt < vocab if head else nxt == -1, 'live draft target output')
    require(sha == hashlib.sha256(hidden).hexdigest().encode('ascii'), 'live draft hidden SHA256')
    return Handoff(pos, final, count, ticket, seq, token, nxt, head, hidden, header)


def bind(handoff, *, position, input_token, row_ticket, commit_sequence, output_token, fixture):
    """Match the copy to the actual committed target command, not its arrival order."""
    require((handoff.position, handoff.input_token, handoff.row_ticket, handoff.commit_sequence,
             handoff.next_token, handoff.head) ==
            (position, input_token, row_ticket, commit_sequence,
             output_token if fixture else -1, int(fixture > 0)), 'live draft target commit mismatch')
    return handoff


class CanonicalSequence:
    """Bound request/result pairing. It never promotes a draft token to truth."""
    def __init__(self, vocab):
        require(type(vocab) is int and vocab > 0, 'vocabulary')
        self.vocab, self.position, self.last_commit = vocab, 1, 0
        self.pending = None
        self.proposals = {}

    def begin(self, handoff, confirmed_token, *, head):
        require(self.pending is None and handoff.position + 1 == self.position
                and handoff.commit_sequence > self.last_commit, 'stale or skipped canonical draft pair')
        require(type(confirmed_token) is int and 0 <= confirmed_token < self.vocab
                and (not handoff.head or confirmed_token == handoff.next_token), 'unverified draft input')
        require(type(head) is bool, 'draft head flag')
        self.pending = (handoff, confirmed_token, head)
        return dict(op=STEP, token=confirmed_token, position=self.position, fixture=int(head))

    def complete(self, token):
        require(self.pending is not None, 'unsolicited draft result')
        handoff, confirmed, head = self.pending
        require(type(token) is int and (0 <= token < self.vocab if head else token == -1),
                'draft result bounds')
        if head:
            # For depth one there is no recursive branch or alternate prefix.
            self.proposals[self.position + 1] = token
        self.last_commit = handoff.commit_sequence
        self.position += 1
        self.pending = None

    def proposal(self, position):
        return self.proposals.get(position)

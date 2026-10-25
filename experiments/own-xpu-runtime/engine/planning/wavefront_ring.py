"""CPU-only protocol model for a bounded speculative suffix.

This does not implement native execution, a scheduler, or a performance model.
Physical execution advances at ROW; logical acceptance never rewinds it.
"""
from copy import deepcopy
from dataclasses import dataclass


def require(ok, message):
    if not ok:
        raise ValueError(message)


@dataclass(frozen=True)
class Ticket:
    identity: int
    parent: int
    generation: int
    position: int
    token: int
    tentative: bool


@dataclass
class Pending:
    ticket: Ticket
    before: dict | None


class Ring:
    def __init__(self, *, capacity=2, first=False, final=False, context=128, vocab=97):
        require(type(capacity) is int and 1 <= capacity <= 3, 'bounded ring capacity')
        self.capacity, self.first, self.final = capacity, first, final
        self.context, self.vocab = context, vocab
        self.pending = []
        self.committed = self.last_identity = self.last_accepted = self.generation = 0
        self.last_target_output = None
        self.restores = 0
        self.physical = dict(position=0, history=[], banks=[[], []], parity=0,
                             extent=32, scratch=b'', error=0)

    def _healthy(self):
        require(not self.physical['error'], 'sticky failure cannot be restored')

    def execute(self, ticket):
        self._healthy()
        require(ticket.identity > self.last_identity and ticket.generation == self.generation,
                'stale ticket or branch generation')
        parent = self.pending[-1].ticket.identity if self.pending else self.last_accepted
        require(ticket.parent == parent, 'causal parent ticket')
        require(ticket.position == self.physical['position'] and 0 <= ticket.position < self.context,
                'physical execution position')
        require(type(ticket.token) is int and 0 <= ticket.token < self.vocab, 'token bounds')
        require(len(self.pending) < self.capacity, 'bounded unresolved ring')
        require(not self.pending or all(p.ticket.tentative for p in self.pending),
                'resolve verified row before dependent admission')
        require(ticket.tentative or not self.pending, 'verified row cannot bypass unresolved prefix')
        require(not self.final or not ticket.tentative, 'final stage never executes tentative input')
        if self.final and self.last_target_output is not None:
            require(ticket.token == self.last_target_output, 'final input must match committed target output')
        before = deepcopy(self.physical) if ticket.tentative else None
        # Deterministic mutable-state fixture, not model arithmetic.
        self.physical['extent'] = min(self.context, ((ticket.position + 32) // 32) * 32)
        self.physical['history'].append(ticket.token)
        if self.first:
            bank = self.physical['parity'] ^ 1
            self.physical['banks'][bank] = list(self.physical['history'])
            self.physical['parity'] = bank
        self.physical['scratch'] = bytes([ticket.token]) + ticket.position.to_bytes(4, 'little')
        self.physical['position'] += 1
        self.pending.append(Pending(ticket, before))
        self.last_identity = ticket.identity

    def accept(self, ticket, *, verified_token, target_output=None):
        self._healthy()
        require(self.pending and self.pending[0].ticket == ticket, 'accept oldest exact ticket only')
        require(ticket.position == self.committed and ticket.token == verified_token,
                'accept requires verified contiguous input')
        require((type(target_output) is int and 0 <= target_output < self.vocab)
                if self.final else target_output is None, 'target output ownership')
        self.pending.pop(0)
        self.committed += 1
        self.last_accepted = ticket.identity
        if self.final:
            self.last_target_output = target_output
        # No physical position/bank/state write here: later rows may be complete.

    def reject_suffix(self, ticket):
        self._healthy()
        require(self.pending and self.pending[0].ticket == ticket and ticket.tentative,
                'reject oldest unresolved tentative suffix only')
        require(ticket.position == self.committed, 'cannot discard a committed prefix')
        require(all(p.ticket.tentative for p in self.pending), 'suffix contains verified work')
        discarded = tuple(p.ticket.identity for p in self.pending)
        self.physical = deepcopy(self.pending[0].before)
        self.pending.clear()
        self.generation += 1
        self.restores += 1
        require(self.physical['position'] == self.committed, 'restore logical/physical frontier')
        return discarded

    def committed_view(self):
        """Evidence-only view; never restore this merely to process an ACCEPT."""
        return deepcopy(self.pending[0].before if self.pending else self.physical)

    def draft_admission(self):
        self._healthy()
        require(not self.pending and self.physical['position'] == self.committed,
                'canonical draft requires empty target ring')

    def boundary(self):
        self.draft_admission()
        return deepcopy(self.physical)

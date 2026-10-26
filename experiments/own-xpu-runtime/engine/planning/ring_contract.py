"""CPU proposal provenance prototype; not imported by the active controller.

Freshness ranks alternatives. Only a verified target commit changes truth.
Already issued row identities and tokens remain immutable until resolution.
"""
from dataclasses import dataclass
import hashlib
import struct


def need(ok, why):
    if not ok:
        raise ValueError(why)


def append_prefix(before, position, token):
    need(isinstance(before, bytes) and len(before) == 32, 'prefix digest')
    need(type(position) is int and 0 <= position < 2**32, 'prefix position')
    need(type(token) is int and 0 <= token < 2**32, 'prefix token')
    return hashlib.sha256(b'ownrt.ring-prefix.v1\0' + before + struct.pack('<II', position, token)).digest()


@dataclass(frozen=True)
class ProposalBatch:
    request: bytes
    epoch: int
    ticket: int
    seed_length: int
    seed_digest: bytes
    tokens: tuple
    restored_position: int
    restored: bool


@dataclass(frozen=True)
class Proposal:
    batch_ticket: int
    seed_length: int
    depth: int
    position: int
    token: int
    parent_digest: bytes
    after_digest: bytes


@dataclass(frozen=True)
class Issued:
    row_id: int
    parent_row_id: int
    proposal: Proposal


class Proposals:
    def __init__(self, *, request, epoch, prompt, vocab, max_batches=4, speculative_depth=2):
        need(isinstance(request, bytes) and len(request) == 32, 'request identity')
        need(type(epoch) is int and epoch >= 0 and prompt and type(vocab) is int and vocab > 0,
             'request geometry')
        need(type(max_batches) is int and 1 <= max_batches <= 8, 'bounded publication cache')
        need(type(speculative_depth) is int and speculative_depth in (2, 3), 'supported speculative depth')
        self.speculative_depth = speculative_depth
        self.request, self.epoch, self.vocab = request, epoch, vocab
        self.verified = []
        self.hashes = [hashlib.sha256(b'ownrt.ring-request.v1\0' + request + struct.pack('<Q', epoch)).digest()]
        for token in prompt:
            need(type(token) is int and 0 <= token < vocab, 'prompt token')
            self.hashes.append(append_prefix(self.hashes[-1], len(self.verified), token))
            self.verified.append(token)
        self.batches, self.issued = [], {}
        self.max_batches = max_batches
        self.last_batch_ticket = self.last_commit_ticket = self.last_row_id = 0
        self.seed_parent_row_id = None

    def register_verified_row(self, position, row_id, prefix_digest):
        """Bind the coordinator's known-input row before extending that seed."""
        need(position == len(self.verified)-1 and prefix_digest == self.hashes[-1],
             'registered row is not current verified input')
        need(type(row_id) is int and row_id > self.last_row_id, 'registered row identity must be fresh')
        self.seed_parent_row_id = row_id
        self.last_row_id = row_id

    def publish(self, batch):
        need(batch.request == self.request and batch.epoch == self.epoch, 'stale request/epoch')
        need(type(batch.ticket) is int and batch.ticket > self.last_batch_ticket, 'stale batch ticket')
        need(type(batch.seed_length) is int and 1 <= batch.seed_length <= len(self.verified),
             'unverified proposal seed')
        need(batch.seed_digest == self.hashes[batch.seed_length], 'wrong verified seed prefix')
        need(batch.restored is True and batch.restored_position == batch.seed_length - 1,
             'recursive branch was not restored to canonical seed')
        need(type(batch.tokens) is tuple and 1 <= len(batch.tokens) <= self.speculative_depth
             and all(type(t) is int and 0 <= t < self.vocab for t in batch.tokens),
             'bounded proposal tokens')
        self.last_batch_ticket = batch.ticket
        self.batches.append(batch)
        self.batches = self.batches[-self.max_batches:]

    def _choices(self, position, parent_digest):
        for batch in self.batches:
            offset = position - batch.seed_length
            if not 0 <= offset < len(batch.tokens):
                continue
            before = batch.seed_digest
            for depth, token in enumerate(batch.tokens):
                after = append_prefix(before, batch.seed_length + depth, token)
                if depth == offset and before == parent_digest:
                    yield Proposal(batch.ticket, batch.seed_length, depth + 1, position, token, before, after)
                before = after

    def choose(self, position, parent_digest):
        existing = self.issued.get(position)
        if existing:
            need(existing.proposal.parent_digest == parent_digest, 'issued row belongs to another parent')
            return existing.proposal
        need(position >= len(self.verified), 'proposal requested for already verified input')
        return max(self._choices(position, parent_digest),
                   key=lambda p: (p.seed_length, p.batch_ticket), default=None)

    def issue(self, row_id, parent_row_id, proposal):
        need(type(row_id) is int and row_id > self.last_row_id, 'stale global row identity')
        need(proposal is not None and proposal.position not in self.issued, 'duplicate issued position')
        need(proposal == self.choose(proposal.position, proposal.parent_digest), 'unpublished or stale proposal')
        if proposal.position == len(self.verified):
            need(proposal.parent_digest == self.hashes[-1] and self.seed_parent_row_id is not None
                 and parent_row_id == self.seed_parent_row_id, 'issued seed is not verified parent row')
        else:
            parent = self.issued.get(proposal.position - 1)
            need(parent is not None and parent.row_id == parent_row_id
                 and parent.proposal.after_digest == proposal.parent_digest, 'wrong issued parent lineage')
        issued = Issued(row_id, parent_row_id, proposal)
        self.issued[proposal.position] = issued
        self.last_row_id = row_id
        return issued

    def verify(self, token, *, commit_ticket):
        need(type(token) is int and 0 <= token < self.vocab
             and type(commit_ticket) is int and commit_ticket > self.last_commit_ticket, 'verified target identity')
        position = len(self.verified)
        row = self.issued.get(position)
        rejected = row is not None and row.proposal.token != token
        discarded = tuple(v.row_id for p, v in sorted(self.issued.items()) if p >= position) if rejected else ()
        if rejected:
            self.issued = {p: v for p, v in self.issued.items() if p < position}
        elif row:
            del self.issued[position]
        self.hashes.append(append_prefix(self.hashes[-1], position, token))
        self.verified.append(token)
        self.last_commit_ticket = commit_ticket
        self.seed_parent_row_id = row.row_id if row and not rejected else None
        # Drop any batch whose hypothetical prefix already disagrees with truth.
        self.batches = [b for b in self.batches if all(
            b.seed_length + i >= len(self.verified) or guess == self.verified[b.seed_length + i]
            for i, guess in enumerate(b.tokens))]
        return dict(position=position, hit=row is not None and not rejected, discard_row_ids=discarded)

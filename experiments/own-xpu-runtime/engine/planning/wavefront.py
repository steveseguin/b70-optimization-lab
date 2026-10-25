"""Bounded, event-driven token scheduling; no device or process operations.

Only a final-stage committed result verifies the next input. A stage can hold
one unresolved row. At most two token positions are admitted ahead of the final
stage. Scripted proposals are diagnostic inputs, never a performance claim.
"""
from dataclasses import dataclass, field

ROW, COMMIT, ABORT = 20, 21, 22


def require(ok, message):
    if not ok:
        raise ValueError(message)


@dataclass
class Row:
    identity: int
    position: int
    token: int
    fixture: int
    verified: bool
    cancelled: bool = False
    streams: dict = field(default_factory=dict)
    committed: set = field(default_factory=set)
    next_token: int | None = None


@dataclass(frozen=True)
class Command:
    stage: int
    op: int
    sequence: int
    row: Row
    speculative: int


@dataclass
class Stage:
    position: int = 0
    sequence: int = 0
    busy: Command | None = None
    pending: Command | None = None


class Wavefront:
    def __init__(self, stages, prompt, max_new, vocab, eos, propose):
        require(type(stages) is int and stages > 0, 'positive stage count')
        require(prompt and all(type(t) is int and 0 <= t < vocab for t in prompt), 'prompt tokens')
        require(type(max_new) is int and max_new > 0 and 0 <= eos < vocab, 'generation bounds')
        self.stages = [Stage() for _ in range(stages)]
        self.prompt, self.max_new, self.vocab, self.eos = list(prompt), max_new, vocab, eos
        self.propose = propose
        self.frontier, self.counter = 0, 0
        self.known = dict(enumerate(prompt))
        self.rows, self.emitted, self.events = {}, [], []
        self.stopping = False
        self.limit = len(prompt) + max_new - 1

    def _referenced(self, row):
        return any((s.busy and s.busy.row is row) or (s.pending and s.pending.row is row)
                   for s in self.stages)

    def _ensure_rows(self):
        for position, row in list(self.rows.items()):
            if not self._referenced(row) and (row.cancelled or len(row.committed) == len(self.stages)):
                del self.rows[position]
        if self.stopping:
            return
        for position in range(self.frontier, min(self.frontier + 2, self.limit)):
            existing = self.rows.get(position)
            if existing:
                if existing.cancelled:
                    break  # Do not admit descendants of a draining rejected row.
                continue
            verified = position in self.known
            token = self.known[position] if verified else self.propose(position)
            if token is None:
                break
            require(type(token) is int and 0 <= token < self.vocab, 'proposal outside vocabulary')
            self.counter += 1
            self.rows[position] = Row(self.counter, position, token,
                                      max(0, position - len(self.prompt) + 2), verified)

    def commands(self):
        """Reserve ready commands; the caller must send each exactly once."""
        self._ensure_rows()
        result = []
        for index, stage in enumerate(self.stages):
            if stage.busy:
                continue
            if stage.pending:
                row = stage.pending.row
                if row.cancelled:
                    op = ABORT
                elif row.verified:
                    op = COMMIT
                else:
                    continue
                speculative = stage.pending.sequence
            else:
                row = self.rows.get(stage.position)
                if not row or row.cancelled or index in row.committed:
                    continue
                if index and index - 1 not in row.streams:
                    continue
                if index == len(self.stages) - 1 and not row.verified:
                    continue  # Unverified input never reaches the verifier.
                op, speculative = ROW, int(not row.verified)
            stage.sequence += 1
            command = Command(index, op, stage.sequence, row, speculative)
            stage.busy = command
            result.append(command)
        return result

    def complete(self, command, *, output_token=None, stream=None):
        stage, row = self.stages[command.stage], command.row
        require(stage.busy is command, 'stale, duplicate, or wrong-stage reply')
        stage.busy = None
        if command.op == ROW:
            require(stage.pending is None and stage.position == row.position, 'row position/ownership')
            stage.pending = command
            if command.stage == len(self.stages) - 1:
                require(row.verified and not row.cancelled and stream is None, 'unverified final row')
                if row.fixture:
                    require(type(output_token) is int and 0 <= output_token < self.vocab, 'final token')
                    row.next_token = output_token
            else:
                require(isinstance(stream, bytes) and len(stream) > 0 and output_token is None,
                        'complete immutable nonfinal handoff required')
                row.streams[command.stage] = stream
        elif command.op in (COMMIT, ABORT):
            require(stage.pending is not None and stage.pending.row is row
                    and stage.pending.sequence == command.speculative, 'resolution ticket mismatch')
            if command.op == COMMIT:
                require(row.verified and not row.cancelled, 'commit before target verification')
                stage.position += 1
                row.committed.add(command.stage)
            else:
                require(row.cancelled and stage.pending.speculative == 1, 'abort requires tentative checkpoint')
                self.events.append(dict(event='abort', stage=command.stage, position=row.position,
                                        row=row.identity))
            stage.pending = None
            if command.op == COMMIT and command.stage == len(self.stages) - 1:
                self._verified(row)
        else:
            raise ValueError('unknown scheduling operation')

    def _verified(self, row):
        require(row.position == self.frontier, 'final commits must be in prefix order')
        self.frontier += 1
        if row.fixture:
            require(row.next_token is not None, 'missing target output')
            self.emitted.append(row.next_token)
            self.events.append(dict(event='verified-output', position=row.position,
                                    token=row.next_token, row=row.identity))
            if len(self.emitted) == self.max_new or row.next_token == self.eos:
                self.stopping = True
                for future in self.rows.values():
                    if future.position > row.position:
                        require(not future.verified, 'unexpected verified work beyond generation cap')
                        future.cancelled = True
                return
            self.known[self.frontier] = row.next_token
            future = self.rows.get(self.frontier)
            if future:
                if future.token == row.next_token:
                    future.verified = True
                    self.events.append(dict(event='proposal-hit', position=future.position,
                                            row=future.identity))
                else:
                    future.cancelled = True
                    self.events.append(dict(event='proposal-miss', position=future.position,
                                            guess=future.token, correct=row.next_token, row=future.identity))

    @property
    def done(self):
        self._ensure_rows()
        return self.stopping and not self.rows and all(not s.busy and not s.pending for s in self.stages)

"""Canonical-provider admission and final-record lease for opt-in rolling execution.

The ring Coordinator remains the sole wire-sequence allocator. These gates
are explicit adapter hooks; legacy schedulers remain unchanged.
"""
from dataclasses import dataclass

from ring_coordinator import Command, Row
from ring_contract import ProposalBatch, need

PROVIDER = 27


@dataclass(frozen=True)
class Parent:
    row: Row
    final_row_ticket: int
    final_commit_sequence: int
    hidden_sha256: bytes
    record_sha256: bytes


@dataclass(frozen=True)
class Job:
    command: Command
    seed: Row
    parent: Parent
    serial: int
    target_physical: int
    target_committed: int
    pending_rows: tuple


class Arbiter:
    def __init__(self, *, stages, request, epoch, last_input_position, vocab, capture_ready_overlap=False, provider_stage=0):
        need(stages >= 2 and isinstance(request, bytes) and len(request) == 32
             and epoch >= 0 and last_input_position >= 0 and vocab > 0, 'rolling scope')
        need(type(provider_stage) is int and 0 <= provider_stage < stages-1, 'provider must be a nonfinal owner')
        self.provider_stage = provider_stage
        self.stages, self.request, self.epoch = stages, request, epoch
        self.last_input_position = last_input_position
        self.vocab = vocab
        self.next_seed, self.serial = 1, 0
        self.local_seed = self.parent = self.job = None
        self.failed = False
        self.stopping = False
        self.capture_ready_overlap = capture_ready_overlap
        self.parent_captured = False

    def checked_row(self, row):
        need(row.request == self.request and row.epoch == self.epoch, 'rolling request/epoch')

    def final_committed(self, parent, *, terminal=False):
        self.checked_row(parent.row)
        need(not self.failed and self.parent is None and self.job is None, 'unconsumed final record lease')
        need(parent.row.position == self.next_seed-1, 'final parent follows canonical provider sequence')
        need(0 < parent.final_row_ticket < parent.final_commit_sequence
             and len(parent.hidden_sha256) == len(parent.record_sha256) == 32, 'authenticated final record identity')
        if terminal:
            need(self.local_seed is None, 'terminal output cannot have a later accepted provider seed')
            self.last_input_position = parent.row.position
            self.stopping = True
        if not terminal and parent.row.position < self.last_input_position:
            self.parent = parent
        # A terminal final row has no next seed and needs no provider operation.

    def local_accepted(self, row):
        self.checked_row(row)
        need(not self.failed and self.job is None and row.position <= self.next_seed, 'local accepted frontier overshot provider')
        if row.position:
            need(row.position == self.next_seed and self.local_seed is None, 'exact once locally accepted seed')
            self.local_seed = row

    def row_allowed(self, stage, position, *, tentative):
        if self.failed or self.stopping or position > self.last_input_position:
            return False
        if stage == self.stages-1 and self.parent is not None and not self.parent_captured:
            return False
        if stage == self.provider_stage and self.job is not None:
            return False
        if stage == 0 and self.local_seed is not None and position > self.next_seed and not tentative:
            return False
        return True

    def captured(self, job):
        need(self.capture_ready_overlap and not self.failed and self.job is job and not self.parent_captured,
             'capture-ready requires exact outstanding uncaptured provider')
        self.parent_captured = True

    def accept_allowed(self, stage, position):
        if self.capture_ready_overlap and stage == self.stages-1 and self.job is not None:
            return False
        return not self.failed and position <= self.last_input_position and (stage != 0 or self.job is None and position <= self.next_seed)

    def can_reserve(self, *, stage_busy, pending, physical, committed, phase):
        if self.failed or self.job is not None or self.local_seed is None or self.parent is None:
            return False
        if stage_busy or phase is not None or any(not c.tentative for c in pending):
            return False
        seed, parent = self.local_seed, self.parent.row
        return (seed.position == self.next_seed and seed.parent == parent.identity and seed.before == parent.after
                and (committed == seed.position+1 if self.provider_stage == 0 else committed in (seed.position, seed.position+1))
                and physical == committed+len(pending) and len(pending) <= 2)

    def reserve(self, reserve_auxiliary, *, stage_busy, pending, physical, committed, phase=None):
        need(self.can_reserve(stage_busy=stage_busy, pending=pending, physical=physical, committed=committed, phase=phase),
             'provider reservation before canonical seed/parent/quiescence')
        # This callback must call the Coordinator's one authoritative allocator
        # and set the provider owner busy. No separate provider wire counter is permitted.
        command = reserve_auxiliary(PROVIDER, self.local_seed)
        need(command.stage == self.provider_stage and command.op == PROVIDER and command.row == self.local_seed
             and command.sequence > 0, 'authoritative auxiliary wire reservation')
        self.job = Job(command, self.local_seed, self.parent, self.serial+1, physical, committed,
                       tuple(c.row.identity for c in pending))
        return self.job

    def complete(self, job, *, command_sequence, provider_serial, restored_position, physical, committed,
                 pending_rows, guesses, release_auxiliary):
        need(not self.failed and self.job is job, 'stale provider completion')
        need(not self.capture_ready_overlap or self.parent_captured, 'provider completed without owned capture acknowledgment')
        try:
            need((command_sequence, provider_serial, restored_position) ==
                 (job.command.sequence, job.serial, job.seed.position), 'provider wire/serial/canonical position')
            need((physical, committed, tuple(pending_rows)) ==
                 (job.target_physical, job.target_committed, job.pending_rows), 'provider changed borrowed target state')
            need(isinstance(guesses, tuple) and (1 <= len(guesses) <= 2 if job.seed.fixture else not guesses),
                 'head-aware bounded provider publication')
            need(all(type(t) is int and 0 <= t < self.vocab for t in guesses), 'provider vocabulary bound')
            release_auxiliary(job.command)
            self.serial = job.serial
            self.next_seed += 1
            self.local_seed = self.parent = self.job = None
            self.parent_captured = False
            if not guesses:
                return None
            return ProposalBatch(self.request, self.epoch, job.command.sequence, job.seed.position+1,
                                 job.seed.after, guesses, job.seed.position, True)
        except Exception:
            self.failed = True
            raise

    def fault(self):
        self.failed = True

    def reset_allowed(self):
        # Real reset additionally requires Coordinator target/provider/native
        # quiescence and an epoch increment. This model grants no reset command.
        return not self.failed and self.job is None and self.parent is None and self.local_seed is None

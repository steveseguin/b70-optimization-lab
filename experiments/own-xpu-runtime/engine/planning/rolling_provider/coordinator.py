"""Opt-in rolling adapter; existing schedulers and native defaults are unchanged.

The unchanged base owns target truth, rows, pending slots and wire sequences.
Only admission/reservation hooks are copied here pending an explicit promotion.
Parent records and provider results must already pass the native wire codecs;
this layer then checks their scheduler ownership and causal identities.
"""
from hashlib import sha256

import ring_coordinator as core
from ring_contract import need
from .arbiter import Arbiter, Parent, PROVIDER


class RollingCoordinator(core.Coordinator):
    def __init__(self, *, capture_ready_overlap=False, provider_stage=0, **kwargs):
        need(kwargs.get('proposal_callback') is None, 'rolling proposals belong only to native completion')
        super().__init__(**kwargs)
        self.provider = Arbiter(stages=len(self.stages), request=self.request, epoch=self.epoch,
            last_input_position=self.limit-1, vocab=self.vocab, capture_ready_overlap=capture_ready_overlap, provider_stage=provider_stage, speculative_depth=self.speculative_depth)
        self.auxiliary_commands = []
        self.provider_jobs = {}
        self.cancelled_provider_incomplete = False

    def _cancel_only(self):
        return self.stop_reason in ('cancel', 'reset')

    def _abandon_cancelled_lease(self):
        if not self._cancel_only() or self.provider.job is not None:
            return
        if self.provider.parent is not None or self.provider.local_seed is not None:
            self.cancelled_provider_incomplete = True
            self.events.append(dict(event='cancelled-provider-lease-abandoned',
                next_seed=self.provider.next_seed,
                parent=None if self.provider.parent is None else self.provider.parent.row.identity,
                seed=None if self.provider.local_seed is None else self.provider.local_seed.identity))
        self.provider.parent = self.provider.local_seed = None
        self.provider.stopping = True

    def _accepts(self):
        result = []
        for index in reversed(range(len(self.stages))):
            stage = self.stages[index]
            if stage.busy is not None or not stage.pending:
                continue
            pending = stage.pending[0].command
            work = self.rows[pending.row.position]
            allow = self._cancel_only() or self.provider.accept_allowed(index, pending.row.position)
            if self.provider.job is not None and (index == 0 or
                    self.provider.capture_ready_overlap and index == len(self.stages)-1):
                allow = False  # Cancellation also drains op27 before replacing its final parent.
            if not work.verified or work.cancelled or not allow:
                continue
            if self.cut is not None and pending.row.position >= self.cut:
                continue
            result.append(self._reserve(index, core.ACCEPT, pending.row,
                row_ticket=pending.sequence, tentative=pending.tentative))
        return result

    def _row_commands(self):
        result = []
        for index in reversed(range(len(self.stages))):
            stage = self.stages[index]
            final = index == len(self.stages)-1
            if stage.busy is not None or len(stage.pending) >= (1 if final else self.speculative_depth):
                continue
            if any(not p.command.tentative for p in stage.pending):
                continue
            position = stage.physical
            if position >= self.limit or position >= self.frontier+self.live_capacity:
                continue
            if self.stop_reason is not None and position >= self.cut:
                continue
            work = self.rows.get(position)
            if work is None and index == 0 and self.stop_reason is None and self._live_count() < self.live_capacity:
                parent = self.rows.get(position-1)
                if parent is not None:
                    proposal = self.proposals.choose(position, parent.row.after)
                    if proposal is not None:
                        work = self._new_row(position, proposal.token, False, proposal)
            if work is None or work.cancelled:
                continue
            tentative = not work.verified
            cancel_drain = self._cancel_only() and self.provider.job is None
            if not cancel_drain and not self.provider.row_allowed(index, position, tentative=tentative):
                continue
            if final and tentative or stage.pending and not tentative:
                continue
            source = None if index == 0 else work.streams.get(index-1)
            if index and source is None:
                continue
            if source is not None:
                need(source.row == work.row and source.stage == index-1
                     and source.digest == sha256(source.data).digest(), 'owned upstream publication')
            result.append(self._reserve(index, core.ROW, work.row, tentative=tentative, source=source))
        return result

    def publish(self, batch):
        if self.provider.provider_stage == 0:
            return super().publish(batch)
        need(self.phase is None and not self.done and self.stop_reason is None,
             'proposal publication during drain/reset')
        stage = self.stages[self.provider.provider_stage]
        need(stage.busy is None and all(p.command.tentative for p in stage.pending),
             'proposal requires restored provider owner')
        need(batch.seed_length >= 2 and self.frontier >= batch.seed_length-1,
             'canonical true-pair parent not yet committed')
        self.proposals.publish(batch)
        self.events.append(dict(event='proposal', ticket=batch.ticket,
            seed=batch.seed_length, tokens=batch.tokens))

    def _poll_proposals(self):
        stage = self.stages[self.provider.provider_stage]
        pending = tuple(p.command for p in stage.pending)
        if self.stop_reason is not None or not self.provider.can_reserve(stage_busy=stage.busy is not None,
                pending=pending, physical=stage.physical, committed=stage.committed, phase=self.phase):
            return
        job = self.provider.reserve(lambda op, row: self._reserve(self.provider.provider_stage, op, row),
            stage_busy=False, pending=pending, physical=stage.physical, committed=stage.committed, phase=self.phase)
        self.provider_jobs[job.command.sequence] = job
        self.auxiliary_commands.append(job.command)
        self.events.append(dict(event='provider-reserved', sequence=job.command.sequence,
            seed=job.seed.position, serial=job.serial, physical=job.target_physical,
            committed=job.target_committed, pending=job.pending_rows))

    def commands(self):
        result = super().commands()
        result += self.auxiliary_commands
        self.auxiliary_commands = []
        return result

    def request_stop(self, reason='reset'):
        # op27 can be the only outstanding command after its seed was already
        # locally ACCEPTed. That committed prefix has no pending ROW for the
        # base stop scanner to find; it still must finish on downstream owners.
        committed_prefix = max([s.committed for s in self.stages] +
            [s.busy.row.position+1 for s in self.stages
             if s.busy is not None and s.busy.op == core.ACCEPT])
        super().request_stop(reason)
        if self.phase == 'stop-prefix' and self.cut < committed_prefix:
            self.cut = committed_prefix
            for position, work in self.rows.items():
                if position < self.cut:
                    need(work.verified, 'stop cannot promote tentative truth')
                    work.cancelled = False
            self.events.append(dict(event='stop-preserves-accepted-provider-seed', cut=self.cut))
        self._abandon_cancelled_lease()

    def complete(self, command, ack, *, final_parent=None):
        try:
            need(command.op != PROVIDER, 'typed provider completion required')
            final_accept = command.op == core.ACCEPT and command.stage == len(self.stages)-1
            if final_accept:
                need(isinstance(final_parent, Parent) and final_parent.row == command.row
                     and final_parent.final_row_ticket == command.row_ticket
                     and final_parent.final_commit_sequence == command.sequence,
                     'final-owned record must match exact accepted ROW/command')
            else:
                need(final_parent is None, 'final record only at final ACCEPT')
            super().complete(command, ack)
            if command.op == core.ACCEPT and command.stage == 0 and not self._cancel_only():
                self.provider.local_accepted(command.row)
            if final_accept:
                if self._cancel_only():
                    need(self.provider.job is None, 'final ROW cannot overwrite an in-flight provider parent')
                    self.cancelled_provider_incomplete |= command.row.position >= self.provider.next_seed
                    self._abandon_cancelled_lease()
                else:
                    terminal = self.stop_reason is not None and self.stop_reason != 'miss'
                    self.provider.final_committed(final_parent, terminal=terminal)
                self.events.append(dict(event='final-record-held' if self.provider.parent else 'final-record-terminal',
                    row=command.row.identity, sequence=command.sequence))
        except Exception:
            self.provider.fault()
            self.failed = 'rolling target/record completion refused'
            raise

    def capture_provider(self, command):
        try:
            need(command.op == PROVIDER and self.stages[self.provider.provider_stage].busy is command,
                 'capture-ready retains exact auxiliary owner')
            job = self.provider_jobs[command.sequence]
            self.provider.captured(job)
            self.events.append(dict(event='provider-parent-captured', sequence=command.sequence,
                seed=command.row.position, serial=job.serial, parent=job.parent.row.identity))
        except Exception:
            self.provider.fault()
            self.failed = 'rolling parent capture refused'
            raise

    def complete_provider(self, command, *, provider_serial, restored_position, physical, committed,
                          pending_rows, guesses):
        stage = self.stages[self.provider.provider_stage]
        try:
            need(command.op == PROVIDER and stage.busy is command, 'exact outstanding provider owner')
            job = self.provider_jobs[command.sequence]
            need((physical, committed, tuple(pending_rows)) ==
                 (stage.physical, stage.committed, tuple(p.command.row.identity for p in stage.pending)),
                 'provider response must match current target ledger')
            def retire(reservation):
                need(stage.busy is reservation, 'provider auxiliary reservation changed')
                stage.busy = None
            batch = self.provider.complete(job, command_sequence=command.sequence, provider_serial=provider_serial,
                restored_position=restored_position, physical=physical, committed=committed,
                pending_rows=pending_rows, guesses=guesses, release_auxiliary=retire)
            del self.provider_jobs[command.sequence]
            self.events.append(dict(event='provider-completed', sequence=command.sequence,
                seed=command.row.position, serial=provider_serial, guesses=guesses))
            if batch is not None and self.phase is None and self.stop_reason is None:
                self.publish(batch)
            self._abandon_cancelled_lease()
            self.invariants()
        except Exception:
            self.provider.fault()
            self.failed = 'rolling provider completion refused'
            raise

    def reset(self, **kwargs):
        raise ValueError('rolling adapter grants no native RESET support')

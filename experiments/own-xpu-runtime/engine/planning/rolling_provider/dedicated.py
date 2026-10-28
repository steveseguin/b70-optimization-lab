"""Separate provider scheduler; CPU control only, no device/transport implementation.

Targets retain the existing Coordinator ledger. Provider commands have their own
owner/sequence and never reserve a target-stage slot or invent target frontiers.
"""
from dataclasses import dataclass

import ring_coordinator as core
from ring_contract import ProposalBatch, need
from .arbiter import Arbiter, PROVIDER
from .coordinator import RollingCoordinator


@dataclass(frozen=True)
class ProviderCommand:
    sequence: int
    row: core.Row
    op: int = PROVIDER
    owner: str = 'provider'


@dataclass(frozen=True)
class ProviderJob:
    command: ProviderCommand
    seed: core.Row
    parent: object
    serial: int


class DedicatedArbiter(Arbiter):
    def row_allowed(self, stage, position, *, tentative):
        # No target device is occupied by the provider. Final-parent and seed
        # leases still constrain target commits, even on independent devices.
        if self.failed or self.stopping or position > self.last_input_position:
            return False
        if stage == self.stages-1 and self.parent is not None and not self.parent_captured:
            return False
        return not (stage == 0 and self.local_seed is not None
                    and position > self.next_seed and not tentative)

    def can_reserve_dedicated(self, *, busy, phase):
        if self.failed or self.stopping or self.job is not None or busy or phase is not None:
            return False
        seed = self.local_seed
        parent = self.parent
        return (seed is not None and parent is not None and
                seed.position == self.next_seed and seed.parent == parent.row.identity
                and seed.before == parent.row.after)

    def reserve_dedicated(self, command):
        need(self.can_reserve_dedicated(busy=False, phase=None), 'dedicated causal seed/parent lease')
        need(type(command) is ProviderCommand and command.row == self.local_seed
             and command.sequence > 0, 'dedicated provider command identity')
        self.job = ProviderJob(command, self.local_seed, self.parent, self.serial+1)
        return self.job

    def complete_dedicated(self, job, *, provider_serial, restored_position, guesses):
        need(not self.failed and self.job is job and self.parent_captured,
             'dedicated exact captured provider job')
        need(type(provider_serial) is int and type(restored_position) is int and
             (provider_serial, restored_position) == (job.serial, job.seed.position),
             'dedicated canonical provider frontier')
        need(isinstance(guesses, tuple) and
             (1 <= len(guesses) <= self.speculative_depth if job.seed.fixture else not guesses),
             'dedicated head-aware proposals')
        need(all(type(token) is int and 0 <= token < self.vocab for token in guesses),
             'dedicated proposal vocabulary')
        self.serial = job.serial
        self.next_seed += 1
        self.local_seed = self.parent = self.job = None
        self.parent_captured = False
        if guesses:
            return ProposalBatch(self.request, self.epoch, job.command.sequence,
                                 job.seed.position+1, job.seed.after, guesses,
                                 job.seed.position, True)
        return None


class DedicatedCoordinator(RollingCoordinator):
    def __init__(self, *, provider_sequence=0, **kwargs):
        need(kwargs.get('stages') in (2, 3), 'dedicated provider supports two/three target owners')
        need(type(provider_sequence) is int and 0 <= provider_sequence < 2**31-100000,
             'bounded independent provider sequence')
        need('provider_stage' not in kwargs and 'capture_ready_overlap' not in kwargs,
             'dedicated provider is not a target stage')
        super().__init__(capture_ready_overlap=True, **kwargs)
        self.provider = DedicatedArbiter(stages=len(self.stages), request=self.request,
            epoch=self.epoch, last_input_position=self.limit-1, vocab=self.vocab,
            capture_ready_overlap=True, speculative_depth=self.speculative_depth)
        self.provider_sequence = provider_sequence
        self.provider_busy = None

    def adopt_prefill(self, count, *, native=None):
        from .dedicated_prefill import Adoption, ACK, ACK_MAGIC
        from hashlib import sha256
        import struct
        need(type(native) is Adoption, 'dedicated prefill requires authenticated native target/provider adoption')
        chunks=(count+255)//256
        prompt_sha=sha256(struct.pack(f'<{len(self.prompt)}i',*self.prompt)).digest()
        need(count==len(self.prompt)-2 and count>=256 and native.count==count
             and native.epoch==self.epoch and native.request==self.request and native.prompt_sha==prompt_sha
             and native.target_sequences==(chunks,)*len(self.stages)
             and native.provider_sequence==native.chunks==chunks and native.provider_serial==count
             and self.provider_busy is None and self.provider_sequence==0 and self.provider.serial==0,
             'dedicated complete native prefix receipt')
        need(len(native.last_ack)==ACK.size,'dedicated terminal prefix ACK extent')
        a=ACK.unpack(native.last_ack)
        need(a[0:4]==(ACK_MAGIC,1,256,chunks) and a[4:6]==((chunks-1)*256,count-(chunks-1)*256) and a[6]==((chunks-1)%2)
             and a[7:10]==(256,self.stream_bytes,len(self.stages)) and a[10:16]==(chunks,chunks,count+1,1,0,0)
             and a[16:20]==(self.epoch,count,self.request,prompt_sha) and a[-1]==bytes(16),
             'dedicated terminal actual chunk ACK binding')
        for stage,sequence in zip(self.stages,native.target_sequences):stage.sequence=sequence
        self.provider_sequence=native.provider_sequence
        super().adopt_prefill(count)

    def _poll_proposals(self):
        if self.stop_reason is not None or not self.provider.can_reserve_dedicated(
                busy=self.provider_busy is not None, phase=self.phase):
            return
        self.provider_sequence += 1
        need(self.provider_sequence < 2**31, 'dedicated provider sequence overflow')
        command = ProviderCommand(self.provider_sequence, self.provider.local_seed)
        job = self.provider.reserve_dedicated(command)
        self.provider_busy = command
        self.provider_jobs[command.sequence] = job
        self.auxiliary_commands.append(command)
        self.events.append(dict(event='provider-reserved', owner='provider',
            sequence=command.sequence, seed=job.seed.position, serial=job.serial))

    def publish(self, batch):
        need(self.provider_busy is None and self.phase is None and not self.done
             and self.stop_reason is None, 'dedicated proposals require restored idle provider')
        need(batch.seed_length >= 2 and self.frontier >= batch.seed_length-1,
             'dedicated canonical true-pair frontier')
        self.proposals.publish(batch)
        self.events.append(dict(event='proposal', ticket=batch.ticket,
                                seed=batch.seed_length, tokens=batch.tokens))

    def capture_provider(self, command):
        try:
            need(self.provider_busy is command, 'dedicated capture command ownership')
            job = self.provider_jobs[command.sequence]
            self.provider.captured(job)
            self.events.append(dict(event='provider-parent-captured', owner='provider',
                sequence=command.sequence, seed=job.seed.position, serial=job.serial,
                parent=job.parent.row.identity))
        except Exception:
            self.provider.fault()
            self.failed = 'dedicated parent capture refused'
            raise

    def complete_provider(self, command, *, provider_serial, restored_position, guesses):
        try:
            need(self.provider_busy is command, 'dedicated completion command ownership')
            job = self.provider_jobs[command.sequence]
            batch = self.provider.complete_dedicated(job, provider_serial=provider_serial,
                restored_position=restored_position, guesses=guesses)
            self.provider_busy = None
            del self.provider_jobs[command.sequence]
            self.events.append(dict(event='provider-completed', owner='provider',
                sequence=command.sequence, seed=job.seed.position,
                serial=provider_serial, guesses=guesses))
            if batch is not None and self.phase is None and self.stop_reason is None:
                self.publish(batch)
            self._abandon_cancelled_lease()
            self.invariants()
        except Exception:
            self.provider.fault()
            self.failed = 'dedicated provider completion refused'
            raise

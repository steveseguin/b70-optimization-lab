"""Optional middle-owner transport; seed authority remains native stage zero."""
import struct
from hashlib import sha256
import pending_ring_live_driver as pending
base, codec, ring, wire = pending.base, pending.codec, pending.ring, pending.wire

SEED_OFFSET=2*base.SLOT+3072
SEED_HEADER=struct.Struct('<4IQ2i')


def seed_journal(seed_owner, command, stream_bytes):
    raw=bytes(seed_owner.shared[SEED_OFFSET:SEED_OFFSET+256])
    base.require(len(raw)==256, 'complete independent stage0 seed journal')
    fields=SEED_HEADER.unpack(raw[:32]);seed=command.seed
    base.require(fields[:5]==(0x52534331,1,256,0,command.accepted_sequence)
        and fields[6]==seed.row.position+1 and fields[6]<=fields[5]<=fields[6]+2,
        'stage0 seed journal owner/frontier/ACCEPT identity')
    expected=list(wire.ROW_META.unpack(wire.row_metadata(seed,final=False,stream_bytes=stream_bytes)[0]))
    expected[14]=seed.sequence
    base.require(raw[32:]==wire.ROW_META.pack(*expected), 'independent stage0 seed journal immutable ROW identity')
    base.require(bytes(seed_owner.shared[SEED_OFFSET:SEED_OFFSET+256])==raw, 'seed journal changed during capture')
    return raw


def issue(stage, command, seed_owner):
    stage.guard.check()
    base.require(0 < command.stage == stage.spec['id'] == stage.plan['provider_stage'] < len(stage.plan['stages'])-1,
                 'explicit nonfinal remote provider owner')
    base.require(stage.command_pending is None and not stage.transmit and not stage.received,
                 'exclusive remote provider socket')
    base.require(command.sequence == stage.sequence+1 and command.serial == stage.provider_serial+1,
                 'remote provider wire/serial sequence')
    seed, parent = command.seed, command.parent
    base.require(seed.stage == 0 and seed.op == ring.ROW and seed == seed_owner.accepted_row
        and command.accepted_sequence == seed_owner.accepted_sequence
        and 0 < seed.sequence < command.accepted_sequence and command.serial > 0,
        'remote provider requires actual first-owner ACCEPT receipt')
    base.require(seed.row.epoch == parent.row.epoch and seed.row.request == parent.row.request
        and seed.row.position == parent.row.position+1 and seed.row.parent == parent.row.identity
        and seed.row.before == parent.row.after
        and (not parent.handoff.head or seed.row.token == parent.handoff.next_token),
        'accepted seed differs from independent verified parent')
    base.require(all(c.tentative for c in stage.pending_rows)
        and (stage.physical,stage.committed,tuple(c.row.identity for c in stage.pending_rows)) ==
            (command.target_physical,command.target_committed,command.pending_rows)
        and command.target_committed in (seed.row.position,seed.row.position+1)
        and command.target_physical == command.target_committed+len(command.pending_rows)
        and len(command.pending_rows) <= 2 and len(set(command.pending_rows)) == len(command.pending_rows),
        'remote provider borrows only completed tentative target suffix')
    # Validate the actual stage-zero ROW, then bind its immutable ticket and
    # the remote transport owner. Their independent wire counters are unordered.
    metadata=wire.row_metadata(seed,final=False,stream_bytes=stage.stream_bytes)[0]
    fields=list(wire.ROW_META.unpack(metadata))
    fields[10],fields[14]=command.stage,seed.sequence
    metadata=wire.ROW_META.pack(*fields)
    journal=seed_journal(seed_owner,command,stage.stream_bytes)
    stage.shared[wire.ROW_OFFSET:wire.ROW_OFFSET+224]=metadata
    handoff=parent.handoff
    stage.shared[codec.handoff_codec.HEADER_OFFSET:codec.handoff_codec.HEADER_OFFSET+112]=handoff.header
    stage.shared[base.SLOT:base.SLOT+stage.stream_bytes]=handoff.hidden
    stage.sequence=command.sequence
    stage.command_pending=command
    stage.transmit=base.REQUEST.pack(codec.STEP,seed.row.token,seed.row.position,
        int(seed.row.fixture > 0),2,command.sequence,command.stage,0)
    return dict(seed_journal_hex=journal.hex(),seed_journal_sha256=sha256(journal).hexdigest())

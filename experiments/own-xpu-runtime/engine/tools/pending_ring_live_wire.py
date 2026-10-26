"""Pending-target-only extension of the frozen quiescent provider codec."""
from dataclasses import dataclass

import ring_live_wire as canonical

ring, wire, need = canonical.ring, canonical.wire, canonical.need


@dataclass(frozen=True)
class PendingProviderCommand(canonical.ProviderCommand):
    accepted_sequence: int = 0
    target_physical: int = 0
    target_committed: int = 0
    pending_rows: tuple = ()


def seed_metadata(command, *, accepted_row, accepted_sequence, stream_bytes):
    seed, parent = command.seed, command.parent
    need(command.stage == 0 and command.op == canonical.STEP and seed.stage == 0 and seed.op == ring.ROW,
         'pending provider owner/seed identity')
    need(seed == accepted_row and command.accepted_sequence == accepted_sequence
         and 0 < seed.sequence < accepted_sequence < command.sequence and command.serial > 0,
         'provider seed must match actual local ACCEPT receipt')
    need(seed.row.epoch == parent.row.epoch and seed.row.request == parent.row.request
         and seed.row.position == parent.row.position+1 and seed.row.parent == parent.row.identity
         and seed.row.before == parent.row.after
         and (not parent.handoff.head or seed.row.token == parent.handoff.next_token),
         'accepted seed differs from independent verified parent')
    need(command.target_committed == seed.row.position+1
         and command.target_physical == command.target_committed+len(command.pending_rows)
         and len(command.pending_rows) <= command.depth and len(set(command.pending_rows)) == len(command.pending_rows),
         'pending target physical/logical extent')
    # Preserve the original ROW flag even after that row was verified/accepted.
    control = ring.Command(0, ring.ACCEPT, command.sequence, seed.row, seed.tentative, seed.sequence)
    return wire.row_metadata(control, final=False, stream_bytes=stream_bytes)[0]

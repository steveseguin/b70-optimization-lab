# Packet58as boundaries

- Do not turn this into packet58ar's ordered-publication change. This arm changes the wait mechanism only.
- Never reset the spin budget after a sleep; never remove deadlines, async-error checks or completion error propagation.
- Retain the original 1 ms error-recovery sleep and the original poll in A controls.
- Every arm has resident lookup copies and the exact packet58aj arithmetic/kernel/selection identity.
- No separate smoke or parent-smoke prerequisite: K1a/K1b and exact A0 open the bracket.
- A0 stays in exactness and reporting, excluded only from speed and drift.
- Both B views >=1.005 times every warm A; drift <=3%; 60/60 exact. No inferred device win from CPU tests.
- One fixed fresh whole-host lane-A attempt. No retries, model server, settings or publication here.
- Per-op waits are 600 s; in-run evidence checks have no elapsed-time proof deadline.
- Read sensors through every reset path; retain owner-thread utilization even if the speed gate fails.

## packet171b / packet174 (2026-10-19, inherited references)

- Do not move one-card foreground copies onto the compute queue as `memcpy`
  (packet171b, +0.40% neutral): a memcpy on any queue can be carried by a copy
  engine (UR copy offload).
- Do not kick the maintenance list after fills (packet174, -0.02% neutral):
  fills are already submitted promptly.

## packet176 (2026-10-19)

- Do not attribute the fill-coupled transfer cost to the tail readback from
  `transfer_wall_ms` alone. That field also contains the head token/lookup
  uploads issued right after the fill submission on the same copy engine
  (foreground and maintenance lists share the copy-only ordinal, index 0). Use
  `head_transfer_ms` / `tail_transfer_ms` (packet176 and later streams).
- Packet176's B arm is a compute *kernel* path (stores/loads to USM host
  memory), not a copy command. Do not re-test it as a queue `memcpy` variant.

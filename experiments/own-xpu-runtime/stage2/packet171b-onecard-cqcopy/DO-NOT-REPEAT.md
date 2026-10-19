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

## packet171b (2026-10-19)

- **Do not move one-card foreground copies (token/error readback, uploads, route logs) onto the in-order compute queue to remove the ~2.6 ms slow readback.**
  - v5 bracket `packet171b-v5-A`: B0/B1 were +0.40% minimum (34.740/34.761 vs 34.563/34.602 tok/s), 60/60 exact. This is neutral.
  - The slow mode was unchanged: slow-readback fraction 0.40 in every view, and P(slow after a fill token) 0.92–0.96.
  - The slow token follows the fill-submission token. It is fill-traffic contention, not BCS queue ordering.
  - Reopen this only together with a change to fill scheduling or volume.

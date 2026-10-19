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

## packet174 (2026-10-19)

- Do not price one-card fill/readback coupling from "high other" tokens. The
  slow readback is on the fill-submission token itself (P = 0.81 spin) and
  never on a token without fills (P = 0.000); its excess is 0.035 ms per
  same-token fill MB. Join `cache.jsonl` to the timing rows by position.
- Do not tune expert admission while fills are serialized at the token tail:
  a 2 MB fill (~0.07 ms) costs about the zero-copy miss it prevents
  (~0.077 ms, transferred). Second-touch admission (W=256) nets ~0 on the
  replay. Revisit only once fills overlap compute.
- Do not pace or re-time fills inside the token while they show zero
  absorption: total bytes, not their placement, set the cost.

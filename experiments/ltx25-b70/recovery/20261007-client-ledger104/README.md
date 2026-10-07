# Proposal104: omit only unchanged checkpoint ledger writes

This is an offline proposal, not installed runtime code. The sealed103 client is
preserved. Every checkpoint still calls `check_fixed`, reads actual free space,
validates its type, charges every observed decrease and enforces both storage
limits. The proposal skips `save_state` only when **both** `charged_write_bytes`
and `last_available_bytes` are unchanged. All event-log flush/fsync calls remain.

## Why the existing durable state is enough in this one case

The exact pinned source has the following state mutations:

| Mutation | Existing durable write |
| --- | --- |
| Initial state creation | `write_new(state.json, ...)` before it is loaded |
| Request appended to `attempts` | `save_state()` immediately, before submission |
| Submitted ID appended to `prompt_ids` | `save_state()` immediately, before event handling |
| Verified request appended to `completed` | `save_state()` immediately, after terminal/history checks |
| Failure assigned to `halted` | `save_state()` immediately in the exception path |
| Storage charge and last free-space observation | `checkpoint`; write retained whenever either changes |

No other state mutation appears in the pinned client. `acquire` replaces the
in-memory state from its existing durable file. A prior explicit write failure
propagates into the existing halt path; this proposal introduces no retry,
recovery from failed persistence or opportunity to submit again. It does not skip
checks on a fault, changed source, reused PID, invalid free reading or exhausted
budget, even if storage fields would otherwise be unchanged. Free-space increases
still update and persist `last_available_bytes`, without refunding accumulated
write charges.

This argument depends on the exact source and its explicit-save invariant.
`proposal.py` rejects source drift and checks that no AST outside `checkpoint`
changes. A later mutation site without its own durable write would require a new
audit; do not turn this into a generic skip-write helper for arbitrary state.

## CPU evidence

Run:

```bash
python3 -B experiments/ltx25-b70/recovery/20261007-client-ledger104/test_proposal.py
python3 -B experiments/ltx25-b70/recovery/20261007-client-ledger104/simulate.py
```

Nine CPU controls pass. They verify explicit non-storage saves and unchanged
submission/event/failure AST; unchanged and changing free space; increases without
refund; source/fault/PID and probe failures; persistence failure propagation;
invalid readings; and unchanged-but-invalid budgets. Mocked old/new traces compare
state and durable state after every successful checkpoint. No live client,
filesystem durability benchmark, endpoint or GPU request is constructed.

The [simulation](simulation.json) uses 100 checkpoints per scenario:

| Synthetic free-space trace | Old saves | Proposed saves |
| --- | ---: | ---: |
| Constant | 100 | 0 |
| Decrease every checkpoint | 100 | 100 |
| Change every eight checkpoints | 100 | 12 |
| Increase every checkpoint | 100 | 100 |

The number of source/fault/process checks and free-space probes remains 100 in
every case. These are operation counts, not speed projections. Actual unchanged
free-space frequency is unknown. Skipping writes also changes the client's own
I/O, so live free-space traces need not equal those from the old writer; the
positive-decrease accounting rule itself is retained exactly.

The earlier isolated I/O microprofile measured roughly17.2ms per ledger save,
but that does not predict campaign savings. This narrower proposal avoids
append-only journal design, reduced validation frequency and weakened event
persistence. Before a changed client run, finish103's exact-output qualification,
review the patch, build a separately pinned client contract and test its full
existing client suite. A matched serial-client control is needed to measure gain.
The current application cannot simply accept new requests after its sealed plan
is consumed; retain its identity and use only an explicitly admitted continuation
or a controlled successor application when required.

## Files

- `proposal.py`: source-pinned transformation, only the checkpoint function.
- `checkpoint-proposal.patch`: exact proposed source diff; not applied.
- `test_proposal.py`: fake storage/durability controls and explicit mutation audit.
- `simulate.py`, `simulation.json`: reproducible operation-count comparison.

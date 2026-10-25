# Isolated depth-two coordinator contract

`ring_coordinator.py` is a CPU event-driven protocol model. No active driver,
native entrypoint or portable launcher imports it. It does not predict GPU speed.
It connects the existing proposal provenance contract to distributed stage
ownership; the isolated native counterpart is under `ring-native-next/`.

The model admits at most three global live rows and at most two unresolved
**tentative** records on each early stage. Each stage has one outstanding command.
The final stage accepts only verified inputs and holds at most one record. An
unresolved verified record must be accepted before that owner executes another
row. Global row IDs and local wire sequences are distinct and never substituted.

A frozen `Row` binds request epoch/identity, fresh global ID, global parent ID,
position, token, fixture and exact before/after prefix digests. A `Command` adds
owner, operation, local wire sequence, original ROW ticket and optional upstream
publication. Each publication owns a full immutable payload copy and SHA256;
reusing shared memory cannot change a downstream row's input. Prefix bytes use
the exact domain-separated encoding in `ring_contract.py` and `ring-wire-next.md`.

`Stage.physical` advances when a ROW completion is acknowledged.
`Stage.committed` advances only on oldest verified ACCEPT. Accepting an older
row does not alter physical position/banks/streams, including when a later row
has already completed. Tests explicitly exercise that case and compare physical
state against a sequential fixture.

On a target mismatch, the coordinator freezes new rows and proposals. It waits
for every outstanding command reply, accepts any older verified prefix still
awaiting acceptance, and sends one suffix abort per affected stage. Each reply
must identify the exact original ROW ticket and every discarded global ID, with
physical equal to committed and no remaining pending record. Only after **all**
affected owner acknowledgments may the corrected input receive a new row ID.
A partial abort acknowledgment cannot reopen admission.

EOS and length caps drain and discard the tentative suffix through the same
barrier. Explicit reset/cancel first finishes already-issued verified inputs
because those rows have no rollback snapshot, then discards tentative work. A
reset requested during an existing miss/abort barrier closes that request without
admitting the corrected row. Cold RESET is allowed only after all owners are
canonical and empty; all reset acknowledgments must arrive before a new epoch
starts. Local wire sequences remain monotonic. Proposal caches and issued records
are cleared at the terminal boundary. A reported native sticky error latches a
coordinator failure and forbids further commands or reset; no recovery is sent.

## Proposal publication scope

The callback is explicit and returns bounded `ProposalBatch` objects representing
already-restored canonical draft publications. It is polled only while stage zero
is drained and holds at most completed tentative work, with a committed true-pair
parent available. The model does not simulate operation 27 execution time or
concurrent native queues. The callback must not mutate coordinator state.

Fresh batches rank only choices that have not been issued. Once a row exists on
a branch, its token and lineage stay fixed until target verification accepts it
or rejects its suffix. The tests exercise a newer canonical guess disagreeing
with a still-issued recursive child; the new guess neither rewrites that child
nor authorizes attaching descendants to the wrong prefix.

The current `ProposalBatch` CPU type validates request/epoch, batch freshness,
verified prefix, conditional child digest and completed restoration. It does not
carry all proposed wire transport identifiers. Before a native bridge publishes a
batch, that bridge must independently bind canonical seed global row, hidden
parent global row, final COMMIT wire sequence, canonical provider step serial and
raw hidden SHA. The proposed native validator now carries those expectations.
Do not treat this CPU callback as a substitute for those wire checks.

Likewise, the abstract `Ack` checks logical/physical cursor and pending/discard
identity. A native bridge must validate the exact 128-byte metadata, its error and
required restore-byte-check policy, before constructing it. Final ACCEPT's
112-byte raw-hidden handoff must separately match the retained final row, its
ROW/ACCEPT tickets and target output. These bridge/codec steps, actual recursive
native draft execution and live timing remain unimplemented in this coordinator.

## CPU evidence and retained correction

Run:

```bash
python3 -m unittest discover \
  -s experiments/own-xpu-runtime/engine/planning \
  -p 'test_ring_coordinator.py'
```

Thirteen tests cover 48 fixed delayed/reordered reply/topology/miss combinations
and 36 randomized request-shape/EOS/guess combinations on two, four and six stage
owners, plus explicit targeted cases. The deterministic worker model checks both
output IDs and complete synthetic mutable state against sequential execution,
including bank parity and the 32-token context extent transition. It also checks
full payload ownership, stale/duplicate/wrong-epoch replies, a two-record suffix
restore, all-owner acknowledgment barriers, reset during prompt/speculation/abort,
nonzero wire sequence continuation and sticky failure. An independent reviewer
also exercised 500 randomized cases. These are CPU contract tests, not native
numerical or performance qualification.

The initial prototype returned an empty poll after clearing the final abort
barrier, which made the event loop report a deadlock on miss cases. It now resumes
ordinary admission in that same poll after all acknowledgments. The exact failed
source and test bytes, their hashes and the correction explanation are retained
under `evidence/ring-coordinator-initial-deadlock*`. No failed variant ran on GPUs.

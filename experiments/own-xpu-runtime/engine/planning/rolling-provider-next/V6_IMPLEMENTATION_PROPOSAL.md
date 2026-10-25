# Isolated implementation proposal for the rolling evidence gate

Status: design only. The pending v5 proof and its archive pins remain frozen.
The companion `V6_EVIDENCE_GATE.md` specifies the acceptance rules. No native
change is required merely to permit downstream target speculation: the current
pending-provider native dispatcher already records those operations and emits
per-owner target counters. Any later change to ownership, borrowing, reset or
attestation semantics needs separate native review and an explicit version.

1. **Add an opt-in lifecycle adapter.** Promote the isolated socket bridge only
   through a new controller/plan mode. Reuse authenticated model/profile/build
   admission, passive guard and bounded owner lifecycle. Its source closure
   includes the rolling arbiter/coordinator, strict existing codecs and bridge.
   Require actual proposals and reject oracle/reference/forced-token inputs.
   Pin both target and provider restore verification for the first proof.
   Preserve the existing pending scripted controller and all its old receipts.

2. **Finish transport evidence.** Save the exact provider metadata and reply
   while they still belong to the outstanding command. The bridge already saves
   immutable final-record witnesses; add proposal witnesses without modifying
   frozen shared codecs. Record a command-issued journal with original row
   metadata, row ticket, source stream digest and provider lease identity.
   Distinguish command reservation from wire send: cancellation must complete
   every reserved command, including one with no bytes sent yet. A failed codec
   must retain evidence and close admission, never retire and retry.

3. **Add an independent rolling trace auditor.** A new CPU-only module consumes
   retained witnesses, controller events and native traces. It reconstructs full
   row/prefix ancestry, each owner's wire sequence and pending queue, final
   target authority, op27 serial/true pairs and proposal selection provenance.
   It does not call the scheduler to decide what should have happened. Recompute
   speculative depth and acceptance from actual issued work, including an older
   recursive d2 retained after a newer canonical d1 disagrees. Require exact
   agreement between the independently reconstructed ledgers and native counters.

4. **Add explicit v6 state validation.** A state-set v6 identifies rolling
   controller semantics separately from its retained native mode
   `verified-ring-pending-provider`. Keep v1-v5 dispatch and tests intact. Reuse
   the strict sealed buffer/layout readers and exact target/draft comparisons;
   factor common native ring checks only if old tests show identical acceptance.
   Add a separate rolling survival validator with the same full payload and
   inventory checks, deriving provider advancement per record and matching the
   actual completed provider prefix. It may accept zero stage-zero aborts and
   downstream target aborts, but may never silently ignore a present receipt,
   omission, unverified restore or counter discrepancy.

5. **Add a rolling finalizer and result schema.** A new finalizer combines target
   state equality, all canonical draft allocation equality, full output identity,
   true-pair/proposal audits, actual survival records and clean lifecycle gates.
   Summary fields explicitly separate observed coverage from required coverage:
   per-owner rows/aborts/discarded depths, provider borrows at depths 0/1/2,
   survival with/without advancement, actual d1/d2 consumed and fresh-disagreement
   cases. Link the independently archived v5 forced-coverage packet. No default
   claim that every rolling run exercised both borrow depths or a two-row abort.
   Keep normal completion separate from cancellation/provider-incomplete outcomes.

6. **Qualify CPU edge cases before the first model run.** Negative fixtures must
   reject missing/duplicate proposal or survival witnesses, stale final commit,
   changed issued token/prefix, altered native stream SHA, premature correction
   before all abort ACKs, missing byte verification, altered provider-private
   payload and unequal terminal target/draft state. Positive fixtures include
   zero aborts, downstream-only abort, stage-zero abort without advancement and
   an advanced provider surviving a rollback. Coverage labels must remain zero
   when a case did not occur. Existing 2/4/6 fragmented-socket, partial-write,
   cancellation and immutable proposal tests remain required.

7. **Run one separately admitted model qualification.** Root owns the build,
   host admission and GPU lifecycle. Begin with the matched 87-input/32-output
   cohort so target/draft/reference identities are already available. Actual
   proposals alone drive speculation; the offline finalizer may compare retained
   reference proposals afterward. Preserve all raw state and witness identities
   in a complete archive, then use exact-byte archive reuse where available.
   Only after this proof passes should broader prompts, persistent request/reset
   behavior or throughput benchmarking be admitted.

Proposed additive files: `rolling_ring_live_driver.py`,
`rolling_trace_audit.py`, `compare_rolling_provider_survival.py`,
`finalize_rolling_provider_proof.py`, matching CPU tests and explicit v6 manifest
support. Final names and the narrow common-validator factoring should be agreed
before implementation. The current native 128-record survival limit is a hard
bound, not permission to truncate evidence; first-run sizing must respect it.

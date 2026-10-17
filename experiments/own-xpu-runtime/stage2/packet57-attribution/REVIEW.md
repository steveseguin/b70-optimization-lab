# Independent packet57 review

Reviewed 2026-10-17 by a separate agent that did not author the runtime,
coordinator, seal, CPU gate or timeline scripts. The review used source diffs,
retained packet56 receipts and CPU-only command inspection. It launched no
compiler, model, GPU program, service or health probe and changed no protected
packet. The reviewer ran the CPU-only `p57_window.py --plan` successfully.

No unresolved source-review blocker remains. Final build and CPU-gate receipts
must still pass `p57_seal.py --verify` before the coordinator command is used.
This is not device qualification or evidence of a speed improvement.

The numerical kernel, arithmetic, controller and owner implementations retain
packet56's source identity. The reviewed native changes add observation
metadata, queue profiling for the attribution arm, timestamp queries and
event output. They leave launches, operands, reduction order, target/draft
weights, vocabulary prefix and accepted-token decisions unchanged. Queries
occur at existing waits and drains; asynchronous draft publication still does
not synchronously query all timestamps. The token arm retains packet56's
existing deferred draft timing rather than pretending to have no profiling.

GPU events carry their original site label and position, so selected target
layers do not collapse into class names. Sampling covers generated indices
9–16, all draft classes and target layers 19/22/23/24. Draft expert labels are
the actual INT8 `expsgate`/`expsdown` path, not the target's IQ expert kernels.
Direct draft copies and publication copies are tagged separately. CPU
embedding decode/read time remains inside draft wall time; it is not a GPU
event. Sparse event sampling does not measure complete GPU idle or every
target snapshot transfer.

The paired analysis uses the preceding guess to label an emitted-token
interval and joins speculative HALF(position p) to cycle p−1. It retains
terminal intervals for measured-cycle summaries but excludes incomplete
terminal parallel halves from split models. Host idle is calculated from
interval unions and is expressly not called GPU idle. Missing draft classes,
wrong-rank layer coverage, invalid/duplicate events, missing hit/miss sample
coverage or unequal oracle outputs fail the diagnostic summary. Scaled class
costs are marked heuristic: an ordered control/profile pair also contains
temporal drift and cannot reconstruct uninstrumented overlap.
Target means that include cancelled speculative work are not complete-layer
costs. Split ranking must use completed-layer groups and retain the distinction
between speculative and corrected work; destination-card timing remains a
placement sensitivity until that layer is actually measured there.

The coordinator requires the final seal, completed packet49 oracle, fixed
cards 0+1 and 23/25 split, inherited packet56 K1/K2/W0p proofs and qualified
dispatch. It then runs new K0 readiness, new KD byte checks and two fresh
WS-style rank pairs. Every one of the twelve requests in each arm is checked
against the unchanged 128-token packet49 oracle. All diagnostic request,
suite and outer receipts prohibit promotion. Full-host ownership and 97 GiB
memory checks prevent overlap with packet55. Existing fault supervision,
cooperative shutdown, fixed output admission, cooldowns and passive final
kernel checks remain in force; there is no retry or hard-kill path added.

The lean CPU gate compares original56 token mode, new57 token mode and two
fresh new57 attribution runs on the synthetic miniature, including target
tokens, guesses, hit/miss counts and retained layer bytes. It does not claim
full-model equality or measured GPU-event behavior. The seal binds new
compiled sources and binaries, CPU evidence, the explicit observation-file
delta, parent proof identities, local Python helpers, inherited oracle code
and external supervision dependencies. Final GPU equality and attribution
completeness remain coordinator gates.

Findings corrected during review:

- Draft `Request.fixture` is a head-enabled boolean, not a generated index.
  Sampling now derives its generated index from observed target positions.
- Rank 0 did not otherwise enable queue profiling; attribution now enables it
  explicitly on both ranks.
- Actual expert, attention-output, gather and MoE labels now map to their
  intended classes.
- Rollback transfer metadata now belongs to the corrected cycle rather than
  inheriting the previous speculative-half label.
- Parent-proof coverage, K2 dispatch binding and external/oracle source
  closure are checked explicitly.
- Both arms' internal suite receipts now retain diagnostic/no-speed labels,
  and K0 keeps the inherited nice-19 execution policy.

The existing receipts contain no usable boundary-layer timing. Therefore the
22/26 and 24/24 numbers in `TIMELINE.md` remain average-half sensitivities,
not measured per-layer predictions. Do not promote them or use them as a
substitute for the pending in-engine samples.

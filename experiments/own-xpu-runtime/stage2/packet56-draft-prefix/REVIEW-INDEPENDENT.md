# Independent runtime, CPU-gate and coordinator review

2026-10-17. Read-only source review by the timing-analysis agent, which did not
author the runtime overlay, numerical/controller gates, sealer, K fixture or
coordinator wrappers. No GPU, service, model weights, build or protected-tree
write occurred during this review. The reviewer authored the separate timing
analysis and local submission tooling; those are explicitly outside this
independent review.

No unresolved blocking defect remains in the reviewed source. This is source
review, not device qualification. Final compiled receipts must pass the seal,
then the coordinator must run two fresh head windows and the full model chain.

The production delta in `mtp.hpp` changes only the draft logits matrix row
count/span and the draft argmax input extent. The shared weight allocation,
row stride, input address, Q6 variant 6, p33 per-row products and reduction tree
remain unchanged. Target source, arithmetic and native controller are checked
against the parent source manifest by `p56_seal.py`. A non-mini production
draft now requires the already resident shared head before the fallback
allocation path. The existing isolated KD capture mode retains its own head
loading path, because that diagnostic owner has no resident target engine.
There is no added production device weight copy or model-vocabulary change.

`p56_prefix.hpp` refuses zero/oversized prefixes and routed or multi-input-row
matrix geometry. For this nonrouted single-row matrix, p33's source offset is
`row * row_stride`; reducing row count does not change any included row's
address or calculation. Argmax uses the unchanged two-stage kernel with its
existing lower-token-ID tie rule. Its input extent prevents stale suffix reads.

The CPU gate calls the inherited production p33 and round2 host bodies.
Its smaller fixtures cover signed zeros, small magnitudes, varied scales and
prefix boundaries. The added full-geometry case compares all 91,392 prefix
rows against the full 248,320-row head using one synthetic allocation at the
actual 2,560-column/3,380-byte-stride layout; it also checks the untouched output
suffix. Real-sized argmax cases exercise tied maxima, boundary rows, reverse
chunk order and NaNs only in the excluded suffix. These are synthetic CPU
checks, not an assertion that real device logits were already compared.

The controller gate runs the unchanged native controller with mock rank state.
All-miss (target IDs ≥N), all-hit, mixed, two prompt lengths and EOS paths
compare emitted tokens, committed rank states and retained fixtures with the
non-speculative path. It checks that excluded target IDs are ordinary misses
with rollback/redo. The real packet49 oracle remains a separate required gate.

The head K fixture uses one full-sized synthetic expanded head and the same
p33/argmax kernels. It changes hidden inputs each iteration, rotates candidate
order, records separate head/argmax event durations, and excludes reference
calculation/readback from timing. Every prefix is compared with that iteration's
full-head logits and scalar prefix argmax. The summary rejects missing or
duplicate cases, incomplete iteration sets, nonpositive/nonfinite timing and
unsafe teardown. Its timing scope is expressly diagnostic, not model speed.
SIGTERM/SIGINT request cooperative stop; the inherited supervisor retains an
owner that cannot finish its bounded drain instead of hard-killing it.

Review findings resolved before sealing:

- The sealer now checks all generated prefix constants, calibration hash and
  histogram-derived coverage summaries, and binds `runtime-revision.json`.
- Imported external supervision and validation source files are included in
  the source closure; packet-local scanning alone was insufficient.
- Two different K receipt paths are no longer enough: the chain also requires
  distinct `(pid, process_start_ticks)` owners and identical exact-output
  identities, preventing a copied receipt from counting as a fresh process.
- The shared-resident-head requirement was moved ahead of fallback allocation.
- That requirement now excludes the existing isolated KD capture mode; the
  initial unconditional guard would have blocked KD before device comparison.
  KD retains and compares exactly the computed prefix logits, excluding the
  unwritten suffix. `final.mix`, committed draft state and every prefix logit
  remain compared with the same-dispatch host draft capture. The fixed packet49
  target streams and full target oracle remain unchanged; this is the existing
  draft-only reference step, not a new target-oracle job.
- Parent gates are identified as inherited evidence rather than claimed as
  newly executed packet56 gates.

The coordinator retains the inherited one-start/no-retry stages, GPU-fault
checks and graceful teardown. Storage keeps the 1.5 GB CPU-build cap and
8 GB root free-space floor. Device-chain evidence has a separate declared
write budget. The K and chain commands are later coordinator actions; no
pending benchmark result is presented as measured. A focused Git diff of
packet49d and its shared submission files was empty during this review.

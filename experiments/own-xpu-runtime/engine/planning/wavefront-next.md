# Next step: speculative token pipeline on contiguous stages

Design note, 2026-10-25. This is proposed work, not implemented native support or a
speed result. The first prerequisite is exact target-only PP2 versus PP4 state and
token qualification. No native source is changed by this note. Preserve the current
two-card speculative service and all earlier unsuccessful experiments.

## Measured proposal evidence and its limits

The [retained current-engine probe](../../research/review-2026-10-25/depth-probe-result.md)
and [structured summary](../../research/review-2026-10-25/depth-suite-a/depth-summary.json)
contain real recursive proposals, not consecutive teacher-forced one-step hits.
All 5,965 output IDs and all 12 text hashes matched the retained GPU baseline;
all 5,965 diagnostic draft restorations passed complete mutable-byte verification.
The six previously reported independent CPU-reference disagreements remain open.

| Depth | Correct / eligible after correct preceding guesses | Conditional | Correct prefix / observable positions | Complete prefix | End censored |
|---|---:|---:|---:|---:|---:|
| 1 | 4542 / 5965 | 76.144% | 4542 / 5965 | 76.144% | 0 |
| 2 | 3313 / 4533 | 73.086% | 3313 / 5953 | 55.653% | 12 |
| 3 | 2390 / 3308 | 72.249% | 2390 / 5941 | 40.229% | 24 |

The populations differ at response endings. Do **not** subtract these prefix
fractions to label depth-1/depth-2/depth-3 miss probabilities, multiply conditional
rates with different denominators, or present their sum as measured expected
accepted tokens for a four-token block. A schedule cost model must first rejoin the
retained traces on one common eligible cohort (or model censored endings explicitly).
The earlier informal `.239/.205/.154/.402` split was an approximation, not a measured
common-cohort distribution. Per-prompt distributions should accompany pooled rates.

Extra draft passes averaged 1.987 ms at depth 2 and 1.981 ms at depth 3. Snapshot
averaged 0.423 ms; restoration **including diagnostic verification** averaged
9.877 ms. The full discarded probe averaged 14.269 ms. These are diagnostic
components, not serving or pipeline throughput. Removing verification does not
remove the production requirement to restore the recursive draft branch.

## Smallest useful implementation

Use the [current stage slicer](../src/pipeline/layout.hpp), typed F32 engine and
existing kernel plans. Implement token overlap across independent stage owners.
Do not clone the old M2 arithmetic executor or begin with N-way expert TP, whose
measured exchange cost already erased its compute savings.

1. **Qualify one guessed token in flight.** Generalize the current checked
   snapshot transport into a stage-local checkpoint object usable on every stage.
   Keep the existing two-card `SpeculativeImage` default untouched. Start with at
   most one unverified successor per stage and full, exact mutable-state coverage.
   This bounds the first proof while enabling actual independent stage work.
2. **Add an explicit ticket lifecycle.** Each work item identifies epoch, absolute
   input position, token, parent-prefix identity, stage, and output-slot generation.
   Distinguish stage-local row completion from global verified-prefix commitment.
   The current single `Candidate` and single snapshot valid bit cannot represent
   several unverified rows. New opt-in commands retain a checkpoint, finish a row,
   commit a verified ticket, or discard an entire dependent suffix.
3. **Schedule ready owners asynchronously.** Issue work to every ready stage
   before waiting for any one stage. The target-only Python driver's blocking
   HALF/ACCEPT/next-stage sequence is a correctness baseline, not the overlap
   controller. Use one event-driven coordinator over the same separate owner
   channels, with fixed-capacity per-stage output slots. Never overwrite a stream
   while the next stage can still read it; retain complete raw F32 bytes and the
   ticket identity together until consumption is acknowledged.
4. **Raise the bound to three guesses only after depth-one rollback passes.** A
   four-stage filled pipeline may leave the first stage three tokens ahead, the
   second two ahead and the third one ahead. Use a bounded checkpoint/ticket ring.
   Prove its bank rotation and slot lifetimes; existing two/three-bank policies
   cannot simply be reused for arbitrary outstanding depth. Initially prefer
   checked snapshot copies over an unproved new temporal-bank shortcut.
5. **Connect live recursive draft proposals last.** Add a production proposal API
   around the measured recursion and backup/restore, without diagnostic host
   readback on every cycle. The canonical draft advances only on actual verified
   target hidden states. Recursive proposals use hypothetical hidden inputs, so
   their mutable branch must be restored even when every proposed token matches.
   Token equality does not make hypothetical hidden-state updates canonical.

The final stage is the verifier. Before executing an incoming guessed token, it
must equal the previous target output at that absolute position and descend from
the verified prefix. Only final-stage verified outputs may be emitted. On the
first mismatch, stop admitting descendants, drain or cooperatively cancel their
already-issued work, restore every affected earlier stage to the earliest rejected
checkpoint, invalidate that suffix's stream slots/publications, and re-enter the
correct target token. Never accept a later matching guess after an earlier miss.
Sticky device errors are not rolled back or retried. EOS likewise discards every
unverified descendant before request completion.

## Existing code to reuse and tests to extend

- [Current rank protocol and HALF/state dump](../src/gsq-rco-iq3s/state-bundle/build/source-v4/rank.hpp):
  stage IDs/final flags, checked F32 stream extents, Candidate, commit and dump.
- [Current exact snapshot machinery](../src/gsq-rco-iq3s/integration/build/private/source/diet-native/native-src/strict_snapshot.hpp):
  `SnapshotWriteSet`, checked copy admission, `SnapshotFlat`, static extent tables,
  metadata/bank restoration. Extract reusable transport/layout without loosening
  the existing rank-zero-only default or silently omitting scratch/attention writes.
- [Current MTP runtime](../src/gsq-rco-iq3s/integration/build/private/source/diet-native/native-src/mtp.hpp):
  recursive computation, private backup, metadata/attention extent restoration,
  owned reverse-hidden capture, and probe evidence. Preserve explicit ownership
  between target work, reverse-hidden copies and draft callbacks.
- [Historical causal controller](../../stage2/packet71c-depth2-engine/depth2_controller.hpp)
  and [private row implementation](../../stage2/packet71c-depth2-engine/dependent_rows.hpp):
  borrow first-input rejection, verified carry and suffix-discard invariants;
  do not transplant full per-row allocation clones, BF16 handoff sizes, or the
  serialized draft-before-pair schedule that previously lost time.
- [Historical controller tests](../../stage2/packet71c-depth2-engine/native_controller_test.cpp),
  [mailbox fault tests](../../stage2/packet71c-depth2-engine/native_mailbox_fault_test.cpp),
  [current draft analyzer tests](../tools/test_analyze_draft_depth.py),
  [current stage layout tests](test_pipeline_layout.cpp), and
  [driver protocol/ownership tests](../tools/test_pipeline_driver.py).
- [Whole-model state comparator](../tools/compare_pipeline_state.py) and
  [its tests](../tools/test_compare_pipeline_state.py): compare canonical committed
  layer state, explicit role-dependent globals and metadata. No token-only parity
  gate or unexplained bank/scratch exclusions.

## Open gates and measurements

- **Target foundation:** exact PP2/PP4 full state at one fixed prompt and bounded
  decode, then broader prompt/context coverage. Current raw state output is under
  `stageN/native/state-2147483647/`, with dtype/shape and role sidecars beside it.
- **CPU schedule model:** forced miss at each depth, all-hit, missing/stale/wrong-
  epoch publication, slot reuse, delayed owner, stop, EOS and length cap. Test
  N-stage geometry independently of the current 48-layer model.
- **Native rollback:** scripted guesses first, for deterministic exact comparison
  after every prefix, abort and corrected redo. Recorded/oracle guesses measure
  transport/checkpoint ceilings only and cannot be marketed as live-model speed.
- **Context boundaries:** test 31/32/33 and real attention-capacity changes, pooled
  rows, target and draft history, prepared-command references, state-bank aliases
  and every outstanding callback. Full restoration must pass before omitting any
  proven redo-overwritten bytes.
- **Live draft:** canonical draft matches the ordinary verified-input replay after
  accepted/rejected recursive proposals. Production resource census includes
  snapshots, stream slots and draft residency; fit is not inferred from packed
  target-weight bytes.
- **Cost ledger:** per-stage decode service time, controller/IPC gaps, handoff bytes
  and latency, draft depth cost, checkpoint capture/restore bytes and time, wasted
  work and recovery by first miss depth, fill/drain bubbles, accepted-token
  intervals, prompt cost and end censoring. Rebalance layer cuts using measured
  service time including first-stage lookup/draft and final-stage head overhead.
- **Performance qualification:** complete matched suite, exact outputs/state,
  uncached prompts, diagnostics off, fixed source/model/quant/topology identity.
  Compare against the existing fast two-card speculative engine, not only the
  deliberately sequential PP4 target-only baseline. No speed promise until this
  passes. One persistent owner set per admitted configuration; no restart sweep.

Future quant/model work should supply geometry, per-tensor formats, topology and
measured tuning as separate profiles. This stage mechanism must remain reusable;
DeepSeek or other architecture support requires an actual architecture adapter
and numerical qualification, not a profile name that bypasses current guards.

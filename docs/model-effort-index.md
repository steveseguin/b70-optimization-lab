# Model Effort Index

This page is the cross-model work queue and archive. It is meant to help the
next agent switch models without rereading every historical note.

Hardware planning note: the measuring host has four Intel B70 32 GB cards and
about 125 GiB system RAM. A second host (`steve-TURIND8-2L2T`) has two ASRock
B70 32 GB cards and about 15 GiB system RAM. That second host is no longer
restricted to source/build/op-level work: since 2026-09-07 it carries the
measured Qwen3.5 4B and 9B lanes end to end, including strict pairs, identity
ladders, 2K-32K depth ladders, and promoted LocalMaxxing submissions. What it
still cannot do is anything in the four-card band, which is a VRAM and system
RAM limit rather than a policy: MiniMax M2.7 INT4 alone is about 115 GB of
weights against 64 GiB of VRAM here. Route four-card lanes to the measuring
host. Higher-VRAM Intel hardware would make larger future efforts, such as GLM
5.2 and DeepSeek Flash-class models, much more realistic to validate under the
same quality rules.

## How To Add A Model Effort

For the full optimization lifecycle, read
[`model-optimization-guide.md`](model-optimization-guide.md) before creating a
new lane.

Create or update the smallest set of files that makes the lane understandable:

1. `results/<model>-<hardware>/README.md` for promoted or closed-out outcomes.
2. `results/<model>-<hardware>/validity-gates.md` for what counts as a record.
3. `results/<model>-<hardware>/reproduce.md` for the best known commands.
4. `results/<model>-<hardware>/bugs-failed-paths.md` for invalid fast lanes and
   failure signatures.
5. `notes/YYYY-MM-DD-<model>-...md` for chronological experiment notes.
6. `patches/<model>-...patch` for source or config deltas worth preserving.
7. `data/<model>-...json` for compact structured result evidence.

Do not move old files just to make the tree look tidy. Add indexes and links
unless a file is clearly misplaced and no one is likely to reference the old
path.

## Active / Recent Efforts

### Qwen3.8 Flash-Next FP8, four B70s — campaign closed September 13

Fable's A340-A394 campaign is complete: **46.854250 tok/s** approved
class-balanced record (+23.87%), exact-GDN MTP1, and **44.052 tok/s** four-row
32K depth median with cross-server output parity. Larger-prefill, MTP2 and
many-user trials were not promoted. No further runs queued. See the
[closeout](../results/qwen38-flash-next-fp8-b70/CLOSEOUT-20260913.md) and
[recipe](../repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md).


### Qwen3.5 4B And 9B On One Or Two B70s

Main entries:

- [9B W4A16 recipe](../repro/qwen35-9b-w4a16-b70/README.md) and
  [container packet](../packages/qwen35-9b-w4a16-b70/README.md)
- [9B FP8 recipe](../repro/qwen35-9b-fp8-b70/README.md) and
  [container packet](../packages/qwen35-9b-fp8-b70/README.md)
- [4B W4A16 recipe](../repro/qwen35-4b-w4a16-b70/README.md) and
  [container packet](../packages/qwen35-4b-w4a16-b70/README.md)
- [experiment archive](../experiments/qwen35-9b-b70/) and
  [4B archive](../experiments/qwen35-4b-b70/)

Status: active, and the lane where the lab's output-identity work now lives. Seven LocalMaxxing
submissions between 2026-09-07 and 2026-09-08. Best measured single-user figures, all lossless
against a same-configuration MTP0 oracle: 4B W4A16 `236.916` on two cards and `177.287` on one; 9B
W4A16 `172.296` on two and `113.265` on one; 9B FP8 `147.8` on two and `98.251` on one. Depth 3 with
the draft-only INT4 lm_head and full decode-only graph capture is the operating point on every route,
confirmed by sweeps on both models rather than inherited.

What this lane established, and what it costs to re-derive, is the identity account:

- The INT4 W4A16 route is byte-exact against a sequential oracle where the FP8 route is not, on both
  models, because its GEMM does not vary its reduction with the decode row count. Five independent
  confirmations, most usefully the depth sweeps: depth `d` makes the verify step process `d+1` rows,
  so it varies row count without varying users, and FP8 loses a third of the suite from depth 4 up
  while W4A16 is lossless at 3, 4, 5 and 6 on both models.
- The guarantee is one-card. On two cards the 9B loses about one request at 64 users and the 4B holds
  only to 32. Note before designing any experiment here: that metric is **intermittent** - six
  control passes read four at 63/64 and two at 64/64 - so two passes per arm cannot decide whether an
  intervention worked
  ([why, and what to measure instead](../experiments/qwen35-9b-b70/notes/2026-09-08-the-two-card-c64-identity-metric-is-intermittent.md)).
  Four powered arms now exist, 1280 requests each with knob presence verified: control 9 divergent,
  serialised norm 7, row-wise all-reduce 6, both 3. The trend is monotone and in the predicted
  direction, and **none of it is significant** - the pair reaches only `p = 0.15`
  ([note](../experiments/qwen35-9b-b70/notes/2026-09-08-powered-arms-neither-mechanism-nor-the-pair-is-established.md)).
  **Settled, and it closes this line:** with the batch filled by the twelve flip-prone prompts the
  control yields 23 events instead of 9, and at that power the pair of interventions scores 24
  against 23 - two-sided `p = 1.00`. Neither the cross-card all-reduce nor the serialised norm, alone
  or together, affects the divergence. The same data shows why: byte-identical prompts issued in the
  same batch disagree with each other, 23 of 240 prompt-groups per campaign, so batch *size* cannot
  be the explanation and shape-invariance interventions were never going to help
  ([note](../experiments/qwen35-9b-b70/notes/2026-09-08-identical-prompts-in-one-batch-diverge-from-each-other.md)).
  **It does not reproduce offline at all.** Five configurations through the in-process API - lockstep,
  graph capture, induced drift, the twelve fragile prompts, and the ladder's own chunked-prefill
  scheduling - all match a strictly single-row oracle exactly, while the same prompts diverge at
  1.7% through `vllm serve`
  ([note](../experiments/qwen35-9b-b70/notes/2026-09-08-the-divergence-does-not-reproduce-offline.md)).
  The remaining difference is asynchronous admission: the server's batch grows from one to sixty-four
  while early requests decode, where the offline batch is assembled once and only shrinks. Instrument
  the server path rather than rebuilding it offline - the layer hook works in eager mode and the
  strict launcher can run eager.
  **Newest result, and it reframes the target.** A batch of constant composition is deterministic:
  64 identical prompts in lockstep at TP2 give byte-identical outputs, eager *and* with full
  decode-only graph capture, and the per-layer hook finds no same-position row disagreeing in 8000
  observations. The ladder differs by having its requests drift - about three decode steps of spread -
  so step composition varies
  ([note](../experiments/qwen35-9b-b70/notes/2026-09-08-a-lockstep-batch-is-deterministic-the-ladder-is-not.md)).
  That explains all four failed interventions at once: if the mechanism is a request meeting a
  differently-composed step than the oracle did, every row-count-dependent op contributes and fixing
  them singly cannot help. **Next: reproduce the divergence offline by inducing drift** - staggered
  arrival or unequal generation caps - rather than probing another op.
  position, the body is bitwise deterministic - 8000 decode observations at TP2, none disagreeing
  ([note](../experiments/qwen35-9b-b70/notes/2026-09-08-a-per-layer-capture-hook-and-what-it-shows-so-far.md)).
  But that run did not reproduce the divergence: it was eager and unspeculated, where the ladder uses
  full decode-only graph capture. **Re-run the probe with graph capture on before looking anywhere
  else** - a replayed graph is shape-specialised and can differ from eager without any op being
  individually non-deterministic.
  Before designing any knob-based arm here, run `tools/audit-launcher-env-implemented.py` against the
  image: **47 of the 78 variables the launchers forward have no reader in R276**, including the
  four GDN trace hooks that a body bisection would otherwise reach for, the R65 batch-invariant
  lm_head, and VLLM_XPU_W8A16_DECODE_PAD_ROWS. A recorded container environment showing one of
  these reads as a deliberate setting and controls nothing.
  **Tested and negative, but it localises the cause.** Chunking the FP16 vocabulary projection to 32
  rows - verified to make every row's logits bitwise equal to the oracle's, and free - leaves the
  divergence untouched: 20 against 22 in 1280 requests
  ([note](../experiments/qwen35-9b-b70/notes/2026-09-08-the-divergence-originates-upstream-of-the-vocabulary-projection.md)).
  Since the intervention demonstrably works on identical inputs, the inputs cannot be identical: the
  hidden states reaching the head already differ. That is the first positive localisation - the cause is
  in the body, not the head. Bisect it the way R74-R77 did for Qwen3.8 rather than guessing another op;
  four guesses have now been tested and none moved the number. Historical detail:
  below, and every row differs from 33 up, by up to `3.9e-3` in logit space
  ([note](../experiments/qwen35-9b-b70/notes/2026-09-08-the-fp16-vocabulary-projection-switches-strategy-above-32-rows.md)).
  That is the last matmul before the argmax, it sits outside the fixed-K predicate because it is
  f16 x f16, and its threshold is the only one that matches where the ladders break - exact at 32
  users on both topologies, lossy above. Every intervention arm so far left it untouched. Extending
  fixed-K to the FP16 head, or padding its decode rows to tiers of 32, is the next thing to try.
  Neither slot index nor step drift explains it, and the GEMM's fixed-K covers the two-card shapes,
  so all three are eliminated
  ([note](../experiments/qwen35-9b-b70/notes/2026-09-08-three-candidates-eliminated-for-the-two-card-divergence.md)).
  Copies of one prompt are spread over about three decode steps whether or not they disagree. The
  untouched ground is attention and the GDN recurrent path, neither probed for composition dependence
  the way the norm was; that probe needs no server and no second card.
  What follows is how that was reached.
  Note the cost: the row-wise path costs `-65%` at 64 users, not the `-0.25%` published earlier from
  an arm where the knob never reached the container, so it could not ship even if it worked. Before
  spending cards on another full-suite ladder, read
  [the tie-site note](../experiments/qwen35-9b-b70/notes/2026-09-08-the-divergences-are-a-dozen-fixed-tie-sites.md):
  the 25 divergences across those arms resolve to **12 fixed sites**, each flipping the same token at
  the same position every time, and the rate is near zero on most prompts and about 6% on a handful.
  Filling the batch with the fragile prompts instead of the whole suite gathers events roughly an
  order of magnitude faster, turning a 60-80 pass experiment into one under ten. Enable logprobs when
  doing it: the ladder requests them but the field came back empty, and the margin at the flipped
  token is what would say which mechanism moved it.
- The GEMM is not the only shape-dependent reduction on the path. The RMSNorm this route runs gives
  about 2-3% of rows a last-bit difference once the batch reaches 16
  ([probe](../experiments/qwen35-9b-b70/notes/2026-09-08-the-rmsnorm-is-also-row-count-dependent.md)),
  which is the residue the collective experiment could not remove. Treat "the INT4 route is exact"
  as scoped to the regimes measured, not as a property of the kernel alone.

Open, in the order worth doing:

1. The norm. The option space is now closed and costed
   ([existence](../experiments/qwen35-9b-b70/notes/2026-09-08-a-row-invariant-norm-exists-and-is-not-a-drop-in.md),
   [what is ruled out](../experiments/qwen35-9b-b70/notes/2026-09-08-no-cheap-value-preserving-norm-fix-exists-at-the-torch-level.md)).
   The native op is pure PyTorch, so no oneDNN rebuild is involved, but no rewrite of its reduction
   is both invariant and value-preserving: sum, matmul and unsqueeze formulations all track the
   native mean exactly, float32 accumulation is three times worse than float16, and chunking
   preserves the M=1 oracle only at chunk size 1. The three real options are serialising the variance
   reduction (preserves every hash), switching to the float16 reduction (invariant and cheap, but
   re-qualifies the lane), or writing an invariant kernel. **Option 1 is now measured end to end and
   costs nothing**: +0.06% at single-request shape and -0.2% to +0.6% across every ladder rung up to
   the 64-row threshold, on both the speculative and no-speculation paths, against an isolated ratio
   of about 33x. So the value-preserving fix is viable and the isolated ratio was not predictive.
   **It does not close the identity gap**, measured properly: 20 passes at 64 users per arm, 1280
   requests each, 7 divergent against the control's 9 - a difference of 2 events against a Poisson
   standard error of 4. That rules out removal and any large reduction, not a modest one. Above 64
   rows the knob does not engage and the cost is unmeasured. Neither mechanism removes the gap alone;
   whether the pair does is running now (arm p2, both overlays in one image).
2. Per-channel FP8 row-invariance. Specified in
   [this note](../experiments/qwen35-9b-b70/notes/2026-09-07-per-channel-fp8-row-invariance-specification.md)
   with guard conditions and the eight projection shapes; needs a oneDNN rebuild and a bitwise
   screening pass. Would close the 4B FP8 repeat-exactness failure and the 9B FP8 c16 flip at once.
3. Clean-host replay for all three packets.

Do not re-run the W4A16 determinism pad: measured inert below its threshold and `-13%` at 64 users
above it, buying no identity.

On the Gemma lane, do not re-run the draft-thread sweep expecting a win: 16 threads against the
record's 32 looked `+3.06%` at two samples and `+1.72%` at six, with overlapping ranges and roughly
`p = 0.19`. Not established, and a best case of about 2%.

### Muse-Glimmer-30B Q8/WOQ On Four B70s

Main entries:

- [promoted result](../results/muse-glimmer-30b-q8-woq-b70/README.md)
- [standalone repro](../repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md)
- [complete source snapshots](../patches/muse-glimmer-30b-b70/README.md)
- [structured record](../data/muse-q8-woq-argmax-century-20260813.json)
- [experiment archive](../experiments/muse-glimmer-30b-b70/README.md)

Status: closed and banked 2026-08-13. The original BF16/lossless century
objective was not reached. The operator-approved no-training UD-Q8_K_XL
successor measured two independent canonical means of `100.088` and `100.649
tok/s`; the frozen 15-prompt conventional first-100 median was `161.900 tok/s`
with p10 `108.574` and 15/15 cache-zero. It is target-verified but not BF16,
lossless, universally token-exact, or uniformly above 100. LocalMaxxing
approved it as
[`cmss8515c00n0ms01n3begqgg`](https://www.localmaxxing.com/en/runs/cmss8515c00n0ms01n3begqgg).
Reopen only with a new objective/preregistration.

### Qwen3.6 Family Navigation

Use the [Qwen3.6 family research map](qwen36-research-map.md) before selecting a
Qwen lane. It keeps the current 27B Q8 TP2 record, one-card Q8 baseline,
AutoRound INT4/MTP records, Q4/DFlash and intrinsic-MTP work, native FP8, and
35B Quark archive separate while providing one read order. These identities
must not be merged into a family-level speed claim.

### Qwen3.8 27B On Two ASRock B70s

Main entries:

- [Qwen3.8 model board](../README.md#qwen38-27b-model-board)
- [Q8_0 quality-conservative TP2 reproduction](../repro/qwen38-27b-q8-tp2-asrock-b70/README.md)
- [Q4_K_M target-only TP2 reproduction](../repro/qwen38-27b-q4km-tp2-asrock-b70/README.md)
- [Q4_K_M fusion patch](../patches/qwen38-27b-q4km-tp2-asrock-b70/README.md)
- [target-only optimization ledger](../experiments/qwen38-27b-b70/notes/2026-08-15-target-only-pass2.md)
- [c2 cache-row fusion result](../experiments/qwen38-27b-b70/notes/2026-08-16-q8-c2-cache-row-fusion-neutral.md)
- [distributed greedy argmax result](../experiments/qwen38-27b-b70/notes/2026-08-16-q8-distributed-greedy-argmax-neutral.md)
- [archived contributed GPTQ INT4/MTP route](../community/sergiiob-qwen38-27b-vllm-xpu/STATUS.md)
- [AutoRound INT4/MTP3 lane and replay gates](../repro/qwen38-27b-autoround-int4-b70/README.md)

Status: active as of 2026-08-27. The target-only GGUF records remain Q4_K_M
TP2 at `49.717503 tok/s` conventional (`50.219700` historical helper) and Q8_0
TP2 at `36.772932 tok/s`. The official FP8 route has moved beyond its original
`21.708532 tok/s` graph baseline: the block-W8A16 overlay directly measures
`31.489587 tok/s` at an exact 32K prompt and target-only/MTP0 reaches
`1,112.570323 tok/s` aggregate at c128 under its scoped short-context gate.
The dynamic-MTP single-user headline is pending: `58.391033` used a 128-token
cap and `146.814418` used a selected high-acceptance fixture, so both are
diagnostic only. MTP9
and the subsequent latch/c2 threshold treatments are retained as measured
negatives; no diagnostic treatment is spliced into the package headline.

The strict-greedy distributed-argmax candidate was token-for-token exact
across a position-balanced 48-request replay, but it moved the primary metric
by `-0.057%` and worsened TTFT by `+8.311%`. It is preserved as a closed
mechanism result, not enabled in the reproduction package. The replay also
clarified that the earlier accepted Q8 speed capture was reasoning-enabled,
whereas the current service launcher and quality oracle use reasoning off.

The separate contributed one-card GPTQ INT4 vLLM route is locally B70-tested at 8K.
Native FP16 KV reached `34.160467 tok/s` target-only and `87.605425` MTP4,
faster than the corresponding FP8-KV rows. MTP matched its target and the
loaded draft parameters were verified FP16, but the GPTQ target failed a
deterministic code-result canary passed by Q8/Q4. It remains an experimental
performance lane, not the no-quality-loss deployment. The 131K boundary patch,
power, exact contributor prompt, and broad quality claims remain open.
The exact public model, container, runtime flags, copied benchmark assets, two
patches, safe launcher, reported payload, source hashes, and audit caveats are
captured in the linked packet.

The separate `devan-carlin/Qwen3.8-27B-int4-AutoRound` lane now has an honest
margin-free MTP5 working anchor at `101.170 tok/s` across all 25 prompts and
`92.851 tok/s` on selection-12. It is not promoted: three pairwise comparisons
agree on only 21–22/25 prompts. A fresh target-only A/B now agrees on 24/25;
post-recovery TP2 MTP5 remains 21/25, and a sealed-cache TP1 pair agrees on
only 2/4. The published `101.922`/`100.497` rows used an output-changing margin
and are withdrawal-recommended.

### Qwen3.6 27B Q8_0 Target-Only On Two ASRock B70s

Main entries:

- [promoted lab result](../results/qwen36-27b-q8-tp2-asrock-b70/README.md)
- [standalone reproduction](../repro/qwen36-27b-q8-tp2-asrock-b70/README.md)
- [complete lab source patch](../patches/qwen36-27b-q8-tp2-asrock-b70/README.md)
- [validated community/fork packet](../community/mndodd-qwen36-27b-llamacpp-sycl/README.md)
- [status and provenance boundary](../community/mndodd-qwen36-27b-llamacpp-sycl/STATUS.md)
- [initial compatibility patch](../community/mndodd-qwen36-27b-llamacpp-sycl/patches/0001-asrock-lab-lowram-dnnless-tp2.patch)
- [model board](../README.md#qwen36-27b-model-board)

Status: active target-only TP2 optimization as of 2026-08-14. The quality-cleared
endpoint best uses mndodd's pinned SYCL optimization fork plus the lab's full
exact collective, Q8 handoff, recurrent dispatch, and persistent-state-I/O
stack. It reaches **`35.964046 tok/s`** under conventional 99-interval
accounting or `36.327319 tok/s` under the historical helper. This is
`+15.918%` over the matched mndodd fork baseline (`31.025377` conventional).
All 12 cold completions are 512 tokens, cache-zero, and byte-exact against the
accepted pre-state-I/O control. Direct GDN state I/O added `+3.132%`; direct
convolution state I/O added another `+0.855%` in the final long suite, and the
recurrent RMS/gate/multiply/Q8 tail added `+0.219%` in pooled matched A/Bs.

The earlier one-card fork endpoint reached `17.955800` helper / `17.776242`
conventional, `+3.809%` over its matched control. MTP and DFlash measurements
are support lanes, not substitutes for this target-only objective. Forced SG32,
GDN workgroup packing, batched Q/K normalization with RoPE, Q8 cache hints,
asymmetric tensor split, root-barrier
elision, BMG-forced MMVQ phase ordering, and copy-engine replication did not
win. TP2 graph capture aborted or hung, and the built-in TP2 profiler reset
both compute engines; both remain prohibited. Pass 2 promoted a register-direct
Q8 handoff and direct IMRoPE-to-KV-cache write after clean rebuild and full
exact-output replay. Continue from its
[handoff](../results/qwen36-27b-q8-tp2-asrock-b70/HANDOFF.md) only with a
materially new exact kernel proof; do not recycle rejected doors.

### Laguna S 2.1 INT4 On Four B70s

Main entries:

- [record resume](../experiments/laguna-s-2.1-xpu-b70/RESUME.md)
- [record note](../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-width12-dflash-fp8-w8a16-record.md)
- [campaign transfer ledger](../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-campaign-transfer-ledger.md)
- [KV-cache precision decision](../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-kv-cache-precision-decision.md)
- [source snapshots](../patches/laguna-s-2.1-xpu-b70/README.md)
- [qualified result packet](../results/laguna-s-2.1-int4-b70/README.md)
- [standalone repro](../repro/laguna-s-2.1-int4-b70-102tps-20260726/README.md)
- [metric correction](../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-throughput-window-accounting-correction.md)

Status: approved at `102.971435596 tok/s` under the submitted legacy
100-event/99-interval convention and `101.941721240 tok/s` under conventional
interval accounting. It is 13/13 token-and-text exact against the canonical
q1 teacher, cache-zero on all rows, and approved by LocalMaxxing as
`cms2ccv2d00lps201rej94pjy`. The result uses exact width 12, DFlash depth 11,
an audited 146/145 Breakable PIECEWISE topology, BF16 KV, and 31 runtime
E4M3FN W8A16 DFlash projection conversions per rank.

This lane is sealed and closed; no benchmark or service is active. The
conventional 102 objective remains short by `0.058278760 tok/s`. Reopening it
requires a new preregistration, not a continuation from the superseded
94.920 row.

Poolside's quantized checkpoint officially ships calibrated FP8 KV; BF16 is a
deliberate record-lane override. The earlier B70 A/B doubled cache capacity
with FP8 but slowed short decode and changed output. Keep future official
long-context FP8 service work separate from the BF16 bitwise-exact record.

### Qwen3.6 27B Q8_0 GGUF On One B70

Main entry:

- [adaptive strategy](../experiments/qwen36-27b-q8-gguf-b70/STRATEGY.md)
- [experiment lane](../experiments/qwen36-27b-q8-gguf-b70/README.md)

Status: validated baseline lane as of 2026-08-08. The exact target-only
Unsloth Q8_0 artifact is pinned and verified on USB for a text-only, target-only,
one-B70 baseline with a 32K ceiling. DNN-off passed 12/12 exact at `15.550257
tok/s` median and the full 32K F16-KV retrieval ladder at `28,372 MiB` loaded;
no full-512 throughput result is promoted yet. The historically recorded Q8_0 family result of `15.275 tok/s`
at p512/n128 is only a trend anchor because its raw evidence, revision, and
binary were not retained. F16 KV is validated; Q8 KV is a separate fallback
quality identity and is unnecessary for the requested 32K ceiling. The primary
next target is F16 c2/32K on each of four independent one-GPU processes, using
parallel screening but isolated same-card promotion. MTP and vision remain
optional later lanes.

### Qwen3.6 27B INT4 AutoRound On B70

Main entries:

- [result packet](../results/qwen36-27b-autoround-int4-b70/README.md)
- [handoff](../results/qwen36-27b-autoround-int4-b70/HANDOFF.md)
- [exact 95.385 repro](../repro/qwen36-27b-autoround-int4-b70/README.md)
- [2026-08-15 independent validation](../experiments/qwen36-27b-autoround-int4-b70/validation-20260815/README.md)
- [private source bundle and patches](../patches/qwen36-27b-autoround-int4-b70/record-20260711/README.md)
- [experiment lane](../experiments/qwen36-27b-autoround-int4-b70/README.md)

**Lane closed 2026-08-18.** The retained `95.385` record stands; nothing beat it
like-for-like. Closing evidence:

- [determinism/speed closeout](../notes/2026-08-18-qwen36-int4-determinism-speed-tradeoff.md)
- [closeout source packet](../patches/qwen36-27b-autoround-int4-b70/determinism-closeout-20260818/README.md)
- [determinism reproduction](../repro/qwen36-27b-autoround-int4-b70-determinism-20260818/README.md)

Succeeded by the Qwen3.8 27B INT4 AutoRound lane below.

### Qwen3.8 27B INT4 AutoRound On B70

Opened 2026-08-18. `devan-carlin/Qwen3.8-27B-int4-AutoRound`, vLLM/XPU TP2 with
native MTP speculative decoding. Its tensor architecture is compatible with the
Qwen3.6 INT4 lane, so the pinned source stack runs without a model-specific
code change. The new weights still require independent quality, determinism,
and performance validation. Current margin-free MTP5 anchor: `101.170 tok/s`
on the 25-prompt suite (`92.851` selection-12), with only 21–22/25 pairwise
repeatability. A valid target-only quality oracle now exists, but its A/B is
24/25 and the sealed-cache TP1 MTP5 control is only 2/4. This is research
evidence, not a record.

Distinct from the llama.cpp Q4_K_M target-only Qwen3.8 lane: different runtime,
quantization, and speculation class. Do not merge their rows.

Main entries:

- [lane setup and model manifest](../repro/qwen38-27b-autoround-int4-b70/README.md)
- [baseline evidence](../data/qwen38-27b-autoround-int4-baseline-20260818.json)
- [post-recovery TP1 result](../experiments/qwen38-27b-b70/notes/2026-08-20-postrecovery-marginfree-tp1-runtime-nondeterminism.md)
- [current source/host queue](../repro/qwen38-27b-autoround-int4-b70/REFERENCE-HOST-HANDOFF.md)

Status: active research. The target oracle, post-recovery TP2 repeats, and TP1
control are complete. The immediate queue is a least-intrusive same-cache TP1
trace of the structured-extraction flip at token 225. Only after runtime
determinism and target parity pass should draft-acceptance changes or a record
submission be considered.

### Gemma 4 26B A4B Q8 / INT8 On B70

Main entries:

- [handoff / production bookmark](../results/gemma4-26b-a4b-q8-b70/HANDOFF.md)
- [production service recipe](../results/gemma4-26b-a4b-q8-b70/production-service.md)
- [result packet](../results/gemma4-26b-a4b-q8-b70/README.md)
- [125 tok/s strict repro](../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md)
- [research plan](../results/gemma4-26b-a4b-q8-b70/research-plan.md)
- [reliability protocol](../results/gemma4-26b-a4b-q8-b70/reliability-protocol.md)
- [VDR2 selected-down record note](../results/gemma4-26b-a4b-q8-b70/20260629-vdr2-selected-down-record.md)

Status: production-servable one-B70 backend plus current frontier/reference,
with diminishing returns unless the next change is a larger
verifier/router/speculation or service-prefill design rather than another small
flag sweep.

Best strict fresh-response result:

- llama.cpp `c926ad098`, one B70, UD-Q8_K_XL target/verifier, Q4_0 MTP draft
  verified by the Q8 target;
- fixed realistic cold prompt suite, `cached_tokens=0`, no cache/history reuse;
- reordered-Q8 VDR2, F16 p021 small-ncols, bulk sampled-ID verifier host read,
  VDR2 selected-down fused weighted-sum, final post-norm residual fusion,
  FA-on 32K/VMM;
- `124.97714084813418 tok/s` median generated-token throughput for tokens
  1-100 after TTFT, p10 `103.83610041293263`, mean
  `122.47435471668817`;
- LocalMaxxing `cmr1u77na01k2ld01kalwzs1e`.

Important caveats:

- same-recipe repeatability is noisy: `2.324%` run-median CV and `4.409%` p90
  pairwise absolute run-median delta; do not promote `+1-4%` single-run spikes;
- use paired same-window A/B analysis with
  `scripts/analyze-gemma-realistic-ab.py` for close changes;
- older filled-long `104+` / `176+ tok/s` rows are diagnostic/pre-final-gate
  only;
- draftless `ngram-mod` `245-280 tok/s` rows are warmed/history artifacts, not
  real fresh-response records.

Service/prefill status: UB2048 is the validated long-context candidate for the
service lane. It passed fixed JSON-retrieval gates through `22730` actual
prompt tokens and the corrected `30400` actual-token boundary case with
`cached_tokens=0`, exact outputs, and no paired short-suite decode regression.
It did not beat the short-decode record, so keep UB1024 for short-record
reproduction.

Recent exhausted neighborhoods include adaptive MTP depth caps, tight `p_min`
repeats, grouped reordered-Q8 duplicate-expert MoE, direct VDR2, top-8
reordered-Q8 slot blocking, Q4_K_M/Q5_K_M/Q6_K/Q8_0 draft swaps, fused verifier
argmax, rowpack, non-direct top-k confidence gating, regular-Q8 top1
epilogue/partial reductions, direct BF16 routed gate/up+GEGLU, attention
post-norm fusion, and per-layer post-norm fusion.

### Gemma 4 12B IT INT4 AutoRound

Main entry:

- [experiment packet](../experiments/gemma4-12b-int4-autoround-vllm/README.md)

Status: current model-slot production profile is c8. c10 is research-only;
c12+ hit boundary failures.

### MiniMax M2.7 INT4 AutoRound

Main entries:

- [fresh Ubuntu 24 deployable repro](../repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md)
- [older strict speed repro](../repro/minimax-m27-b70-89tps-20260520/README.md)

Status: strong candidate to revisit when Gemma work stalls or when a
cross-model collective/graph-boundary idea appears. Strict speed lane is
`89.314195` output tok/s / `119.085594` total at p512/n1536; deployable 32K
endpoint baseline is about `83-84` output tok/s.

Future speed work should target hidden-state collective and graph-boundary
fusion, especially MoE-output allreduce plus epilogue or attention `o_proj`
allreduce plus residual/RMSNorm. Do not spend much time on generic env flag
sweeps.

### Qwen3.6 35B A3B Quark W8A8 INT8

Main entries:

- [result packet](../results/qwen36-35b-quark-int8-b70/README.md)
- [research map](qwen36-research-map.md)

Status: closed reference packet for now, but preserve every lesson for a future
return. No valid `>150 tok/s` path was found; best strict 4x baseline is
`93.55 tok/s`. The main carryover lesson is that graph/speculative speed paths
must pass full-scale canaries, not smoke tests.

### Qwen3.6 27B Q4_0 / FP8 Historical Lanes

Main entries:

- [FP8 vLLM/XPU result note](../results/fp8-vllm-xpu-qwen36-2026-05-04.md)
- older notes under `../notes/`

Status: the intensive Q4_0/DFlash SYCL lane closed on 2026-07-13 at a strict
one-B70 record of `47.818818 tok/s`; the `100/200 tok/s` single-session goals
were not reached. Read the
[closure and transfer note](../notes/2026-07-13-qwen27-dflash-sycl-closure.md)
before using its kernel, speculation, graph, or packing artifacts. Reopen only
with one of the concrete scope changes listed there, not another flag sweep.
The separate UD-Q4_K_XL intrinsic-MTP lane's best valid p-min row is `31.480
tok/s`; its [result packet](../results/qwen36-27b-mtp-gguf-q4-b70/README.md)
retains the older LocalMaxxing MTP3 reference. The community native-FP8 TP2
Docker recipe was independently exercised at `30.171 tok/s` median decode on
a different prompt-length benchmark; keep it non-comparable to fixed-suite
rows and start from its [STATUS](../community/dominick253-qwen36-27b-fp8-tp2-docker/STATUS.md).

### DeepSeek V4 Flash REAP/XPU On B70

Main entry:

- [closed result packet](../results/deepseek-v4-flash-k160-b70/README.md)
- [standalone 80.820 tok/s repro](../repro/deepseek-v4-flash-k160-b70-80tps-20260718/README.md)
- [experiment packet](../experiments/deepseek-v4-flash-reap-xpu-b70/README.md)
- [controlling investment-gated plan](../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md)
- [historical lane handoff](../experiments/deepseek-v4-flash-reap-xpu-b70/HANDOFF.md)
- [frontier closeout](../experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-21-deepseek-v4-flash-frontier-closeout.md)

Status: paused/closed on 2026-07-21 at a fully characterized frontier. The best
verified one-session result is the experimental uniform-K160 target with
target-verified DSpark7: `80.820052 tok/s` strict high and `78.287226 tok/s`
three-suite median-of-medians on four B70s, with 36/36 cache-zero realistic
rows and 24/24 exact canaries. LocalMaxxing approved
`cmrquta9905w3lg013m5vxoqx`; no later verified endpoint exceeded it. Reopen
only for the closeout's 10-20M-token EAGLE/hybrid training condition or a new
device-execution mechanism. The public checkpoint remains hash-pruned with
unavailable calibration and must not be described as official true REAP.

Historical rejected fit/support evidence for the oversized Intel AutoRound
artifact remains at
[the original AutoRound experiment packet](../experiments/deepseek-v4-flash-autoround-vllm/README.md).

## Cross-Model Lessons

For evidence-linked strategies and their transfer boundaries, start with
[Cross-Model Patterns Worth Reusing](research-workflow-playbook.md#cross-model-patterns-worth-reusing).

- Lock benchmark identity before interpreting speed. Missing graph mode or a
  changed launcher can create false regressions or false wins.
- Treat fast speculative paths as invalid until canaries pass at scale. The
  Qwen36 lane had multiple 75-199 tok/s "wins" that failed quality or were
  synthetic.
- Preserve negative patches and logs. MiniMax improved because dead ends were
  visible; Qwen36 became hard when failed experiments were not summarized
  quickly.
- Prefer model-specific result packets over large mixed history dumps. Curated
  packets are easier to review and reuse than monolithic experiment ledgers.
- Keep LocalMaxxing payloads and responses in `data/`, but keep API keys outside
  Git as documented in [localmaxxing.md](localmaxxing.md).
- For one-replica-per-GPU work, prefer four independent servers and four
  disjoint experiments before trying tensor parallelism. This is especially
  relevant to Gemma 4 26B A4B, where the goal is to avoid PCIe collectives.
- LocalMaxxing headline submissions must come from the fixed realistic
  cold-response suite. Synthetic filled-long, repeated, warmed, cached,
  n-gram/history, or continuation-learned scores can guide optimization but
  must remain diagnostic unless revalidated by that gate.
- Treat weight, activation, router, draft, and KV precision as separate identity
  fields. A lower-byte KV cache is a capacity candidate until its actual
  attention path, long-context speed, and separately labeled quality gates pass.
- Require runtime execution proof for experimental selectors, assert graph and
  collective work counts, and never infer device health from a probe that did
  not prove it entered.

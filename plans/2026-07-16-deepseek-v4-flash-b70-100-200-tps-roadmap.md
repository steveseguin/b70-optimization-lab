# DeepSeek V4 Flash On Four B70s: 100/200 tok/s Roadmap

Date: **2026-07-16**

Status: **active; easy bounded gates first, specialized Intel decoder strategic**

## Objective And Invariants

The product objective is one active generation, never aggregate throughput:

- **100 tok/s** is the next target for the unchanged DeepSeek V4 Flash K160
  target on the four available Intel Arc Pro B70s;
- **200 tok/s** is the stretch objective for that same one active generation;
- do not shrink, substitute, or silently lower the target model to improve the
  headline;
- every accepted speculative token must be verified by the declared target;
- promotion uses fresh, cached-zero, unpredictable realistic prompts and the
  frozen exactness/rollover gates;
- preserve the qualified 63.851301 tok/s record identity as the rollback and
  same-binary control.

The current record is the TP4+EP QNorm-M2 plus route-direct MTP1 portfolio at
63.851301 tok/s median, 59.718212 p10. With approximately 77.68% first-position
acceptance, it emits about 1.7768 tokens per cycle and implies a roughly
27.83 ms speculative cycle.

At unchanged acceptance:

- 100 tok/s requires about a 17.77 ms cycle;
- 200 tok/s requires about an 8.88 ms cycle.

At the current cycle time:

- 100 tok/s requires about 2.78 emitted tokens per cycle;
- 200 tok/s requires about 5.57 emitted tokens per cycle.

Sub-millisecond wins remain useful but cannot complete the program alone. The
final result needs target-cycle reduction and materially deeper useful
speculation.

## Option 1: Finish High-Value Target-Kernel Fusion

This is the immediate, lower-cost lane.

The first bounded experiment is an M=2 grouped-MXFP4 producer in which gate
and up projections are owned by separate subgroups. The subgroups exchange the
target-equivalent rounded BF16 fragments through SLM so no subgroup owns both B
payloads and both FP32 accumulator sets. This directly addresses the occupancy
failure that closed the bitwise-exact dual-accumulator producer.

Reject the candidate before model integration unless it:

1. matches the canonical remap -> GEMM1 -> clamp-at-10 SwiGLU -> GEMM2 ->
   gather chain bitwise on changed inputs;
2. remains exact across fixed-address graph replays, duplicate routes,
   cross-row overlap, six-local, and valid all-remote EP routes;
3. passes independently on all four physical B70s;
4. saves at least 0.50 ms per 43-layer verifier cycle on the slowest card and
   worst valid route pattern.

Only a passing hardware gate earns a production selector and frozen
same-binary B-A-B service run. Keep MXFP4 N64. N32, N128, four-lane scheduling,
direct gather, routed activation, fused GEMM2 activation, paired dual-payload
GEMM1, gather/shared-add, and unique-route emission remain preserved closures.

Expected role: produce nearer records and reusable Intel primitives. It is not
by itself a credible explanation for the full 10 ms gap to 100 tok/s.

## Option 2: Restructure TP4 Communication And Cycle Coordination

Normal-run evidence attributes roughly 8-9 ms per MTP1 cycle to TP
communication. This is the only measured target-side scope large enough to
close much of the 100 tok/s gap.

Do not reopen generic oneCCL flag sweeps, clone removal, LL geometry, recursive
doubling, or the failed polling resident consumer. A new communication attempt
must change the producer/consumer algebra or reduce collective count. Credible
designs include:

- projection epilogues that publish rank-local fragments directly into a
  reduction-owned buffer;
- consumers that operate on completed reduced fragments without materializing
  another full tensor;
- combining adjacent reductions where target arithmetic and dependency order
  permit it;
- fixed-address, epoch-safe command lists with device-resident MTP state,
  sampling, acceptance, and commit;
- an explicit Xe2/Level Zero transport specialized for the fixed TP4 B70
  topology if oneCCL cannot expose the required producer/consumer boundary.

Every proposal needs a real-tensor upper-bound proof of at least 0.50 ms/cycle
before a TP4 service load. Cross-device profiler timestamps are not accepted as
arrival-skew evidence.

Expected role: combine with Option 1 to make approximately 80-100 tok/s
plausible. It is difficult and correctness-sensitive, but it attacks a large
enough bucket.

## Option 3: Develop Useful Deeper Speculation

The attached MTP2 reuse path is closed: the second position accepts only about
0.5-2.2% and the realistic service path deadlocks. Enabling more positions in
that predictor is not an option.

The credible alternatives are:

- retrained or adapted multi-position MTP heads for this exact target;
- DFlash/DEAGLE-style feature prediction;
- an external draft only if a topology and memory audit proves it useful;
- an exact, fused M=4/M=8 target verifier built from the Intel primitives in
  Options 1 and 4.

Speculation evaluation must follow the frozen freeze-before-reveal contract:

- tune on a development set, then freeze predictor, policy, and thresholds;
- reveal held-out unpredictable prompts once;
- include short and longer contexts, prose, code, math, extraction, and
  adversarially low-locality inputs;
- record per-position acceptance, emitted tokens per cycle, target verifier
  time, draft time, commit/rollback cost, and complete wall throughput;
- prohibit cache reuse, repeated continuation history, prompt-specific
  routing, and post-hoc selection of the best policy per prompt.

TP2 plus two draft B70s is only a feasibility experiment. It proceeds only if
the unchanged target fits TP2, target-only TP2 performance is competitive, and
the two draft cards perform distinct useful work. Duplicating the same draft
prediction is not a speedup. The recovered TP2+DP2+EP4 vLLM topology is only
2.495917 tok/s and cannot be used as evidence that this arrangement is ready.

Expected role: required for a credible 200 tok/s result. At the present cycle
time, 200 tok/s needs roughly 5.6 emitted tokens per cycle; target fusion alone
cannot supply that multiplier.

## Option 4: Build The Intel Equivalent Of HIPfire

This is the strategic, highest-ceiling lane. vLLM can initially remain the
model loader, API shell, and correctness oracle, while a fixed-geometry
SYCL/Level Zero decoder owns the hot decode cycle.

The specialized decoder should provide:

- content-addressed offline-packed per-rank weights for the exact K160 model;
- fixed persistent device addresses and pristine state-reset snapshots;
- M=1/2/4/8 Xe2 kernels with exact target rounding and layout semantics;
- fused attention/QNorm/RoPE/KV insertion boundaries;
- a fused routed-MoE pipeline rather than framework-level remap, GEMM,
  activation, GEMM, and gather operations;
- topology-specialized TP4 communication integrated with producers and
  consumers;
- device-resident draft preparation, sampling, target verification,
  acceptance, rollback, and commit;
- prebuilt kernel modules and executable command lists keyed by model revision,
  pack layout, kernel ABI, shape, addresses, and speculative width;
- a vLLM parity mode that can compare every intermediate boundary against the
  qualified implementation.

Development artifacts should be cached so most kernel iterations avoid model
reload:

- golden real-model M=1/2/4/8 tensors, including routed edge cases;
- per-rank packed weights and manifest hashes;
- immutable graph-address buffer layouts;
- device-state reset images for KV, MHC, compressor, and speculation state;
- hot-loadable kernel shared objects and compile caches keyed by source hash;
- small replay workers that run gates on four cards independently before any
  full TP4 service test.

Expected role: the most credible path to HIPfire-like efficiency, 100 tok/s,
and eventually 200 tok/s when combined with Option 3. It is a substantial
engineering program, not a parameter sweep.

## Recommended Execution Order

### Phase A: Protect And Re-attribute

1. Keep the 63.851301 record binaries, launcher identity, result directory,
   exact outputs, and LocalMaxxing packet immutable.
2. Capture a fresh exact-identity diagnostic twin of the record after the
   QNorm-M2 and route-direct portfolio. Reconcile noncollective device work,
   communication, queue gaps, host coordination, acceptance, and wall cycle.
3. Do not interpret the older pre-portfolio eager profile as the current cycle.

### Phase B: Easy Bounded Kernel Attempt

1. Implement the subgroup-split/SLM-exchange M=2 MXFP4 producer in an isolated
   DeepSeek XPU-kernel worktree.
2. Run the exact real-shape gate on all four B70s concurrently.
3. If the worst-card/worst-route saving is below 0.50 ms/cycle, preserve the
   patch and negative result and stop this design before model loading.
4. If it passes, add a guarded default-off production selector, rebuild once,
   run exact graph gates, and then run a frozen same-binary B-A-B suite.

### Phase C: Large-Bucket Work

1. Use the fresh profile to select a producer/reduction/consumer boundary with
   a conservative ceiling of at least 0.50 ms/cycle.
2. Begin the fixed-buffer, device-resident cycle shell that can later become
   the specialized decoder.
3. Promote individual kernels into that shell instead of accumulating more
   framework graph nodes.

### Phase D: Speculation And Specialized Decoder

1. Build the held-out speculation evaluator before training or selecting a
   deeper predictor.
2. Establish exact M=4/M=8 target-verifier economics.
3. Select MTP adaptation, DFlash/DEAGLE, or an external draft by emitted
   tokens per complete wall cycle, not acceptance percentage alone.
4. Move the winning target and speculation pipeline into the fixed Intel
   decoder hot loop.

## Decision Gates And Reporting

- Preserve every meaningful patch and result, including failures.
- Reject microbenchmarks with an invalid or artificially weak comparator.
- Require changed-input and repeated fixed-address replay exactness.
- Require the worst valid EP route, not an average favorable route, to clear
  hardware gates.
- Require same-binary controls and fresh cached-zero realistic prompts for
  service claims.
- Report only one-active-generation throughput.
- Submit a LocalMaxxing result only after it beats the matching qualified
  record and passes the full identity and correctness contract.
- Report immediately on a qualified new record, a major architectural result,
  or a genuine blocker; otherwise continue through the ordered gates.

## Current First Action

The fresh post-portfolio attribution is complete at 17.8497 ms/cycle of
noncollective device work. The subgroup-split producer is closed before build:
against the now-promoted route-direct baseline its generous all-remote
incremental ceiling is only about 0.123 ms/cycle.

The fixed-M2 producer/allreduce/consumer upper bound cleared Phase C twice, but
the implemented finite event chain is now closed at the production-relevant
graph gate. It is bitwise exact in two 40-epoch eager runs, under rank skew,
and under fixed-address graph replay. Its apparent 5.60-5.70 ms eager saving is
submission overhead that reusable graphs already remove: captured ordinary
XCCL plus MHC takes 4.265725 ms versus 4.156179 ms for the direct chain, only a
0.109546 ms/cycle gain. Do not service-test or portfolio this candidate.

The easy bounded inventory is exhausted. Option 4's first fixed-geometry shell
artifact is now operational: a 150 MiB content-addressed real M=2 corpus and a
no-model four-B70 worker replay the 87-reduction/85-MHC cycle exactly 70/70
times at a 4.209382 ms slowest-rank median. New kernels enter that shell only
when they delete device work or collective traffic. Option 3's held-out
evaluator and exact M=4/M=8 verifier economics are now the next multiplier
gate; attached MTP2 remains closed. Do not revive resident polling, the
rejected in-ring MHC implementations, or generic oneCCL flag sweeps.

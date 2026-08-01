# Laguna S 2.1 optimization victories and transferable methods

Date: 2026-08-01 America/Toronto

Status: **current victory ledger.** This file records what produced real
throughput, what produced useful research leverage without throughput, and
which conditions make each lesson transferable. The protected result remains
`125.4619731637751 tok/s` under conventional 99-interval accounting, 13/13
token-and-text exact, BF16 KV, target 146/145, and draft 14/13. The remaining
gap to 130 is `4.5380268362249 tok/s` (`3.6170536154%`).

The authoritative recipe is [`../RESUME.md`](../RESUME.md). Chronological
details and negative results remain in the individual notes; this is an index,
not a replacement for them.

## Evidence classes

Keep these labels distinct whenever this ledger is extended:

- **Promoted endpoint win:** a complete cold suite passed correctness,
  cache-zero, topology, provenance, and teardown gates and was promoted.
- **Measured endpoint win:** a valid complete endpoint improved, but was not a
  durable promoted record or was later superseded.
- **Component win:** raw output equality and local timing passed. It is not an
  endpoint claim until the complete model crosses over.
- **Research victory:** localization, a stronger oracle, safer harnessing, or a
  negative that closes a costly class of work. It has no tok/s attribution.
- **Projection:** arithmetic about a possible endpoint. Never list it as a
  measured win.

Historical values before the metric correction used 100 event timestamps over
their 99-interval span. The July 26 `102.971435596` result is
`101.941721240 tok/s` conventionally. Do not compare absolute values across
conventions without recomputing from timestamps.

## Proven endpoint ladder

| Stage | Result | Measured contribution | Why it worked | Transferable rule |
| --- | ---: | ---: | --- | --- |
| Deterministic exact DFlash baseline | `33.085825` historical | First valid full-512 baseline | Disabling async scheduling removed a cross-request target/draft stream-state leak while exact M=1 numerical lanes, direct MoE, and fixed-order BF16 reduction established a deterministic teacher | Make the teacher deterministic before optimizing speculation; validity restoration is not automatically a speed win |
| Fused W1 plus route-parallel W2 | `33.267564` historical | `+0.5493%` | Removed two routed launches per layer while restoring enough route-parallel W2 work to retain occupancy | Fuse boundaries without serializing the work distribution that kept the device occupied |
| Route/N-tile interleave | `33.438927` historical | `+0.5151%` | Interleaved workgroups across 80 routes at each N tile; routed component fell `4.237%` with unchanged arithmetic | Workgroup enumeration and wave availability can matter more than source operation count |
| M8 shared-elementwise plus Q/K RMSNorm/RoPE | `33.894985` historical | `+1.3639%` over preceding record | Removed 94 shared-elementwise launches/cycle and reduced Q/K normalization plus RoPE from 144 to 48 launches | Small exact fusions transfer when repeated enough to remove material full-cycle work |
| Breakable PIECEWISE target graph | `92.163522` historical | `+171.91%`, `2.719x` | Captured stateless target compute while preserving 145 necessary eager boundaries, removing dominant Python, launch, and synchronization overhead | Graph the complete repeated compute regions; graph topology and live dependencies are part of correctness |
| Persistent exact-attention metadata | `94.920039` historical | `+2.9909%` | Refreshed query offsets, KV lengths, and block tables in stable owned buffers instead of reconstructing graph-visible state | Persist allocation and metadata only when trace proves it is paid during replay; guard owner, base pointer, view, offset, shape, and aliasing |
| Exact width 12 / DFlash depth 11 | `100.524890` historical diagnostic | `+6.0135%` against matched M8 (`94.822732`) | Useful emissions rose `3.7010` to `3.9552` per cycle while cycle cost rose only about `0.81%` | Sweep verifier width using acceptance and cycle time together; batching must preserve the teacher's per-row arithmetic |
| Width-12 FP8 W8A16 draft projections | `101.941721` conventional (`102.971436` historical) | `+2.4338%` over the prior exact width-12 result under matched historical accounting | Converted 31 disposable draft dense projections to per-output-channel E4M3FN W8A16 and used stable auxiliary workspace; target verification remained exact | Quantize the disposable drafter before the canonical target and require per-worker execution evidence. Do not attribute gain to the intended FP8 draft LM head: its marker was absent |
| Exact scale-vector mainloop | `102.134914` conventional campaign median | `+2.0851%` over matched median control | Named the existing channel-pair GRF directly, removing 32 marshal moves per K tile (`422` to `389` instructions) with identical DPAS and no spill | Inspect final ISA; a prologue edit is credible only when it removes dynamic instructions and survives interleaved endpoint controls |
| Segmented DFlash outer graph | `118.498545` conventional confirmation | About `+16%` over the 102.135 campaign incumbent | Preallocated 13 fixed collective outputs, kept 13 collectives plus six attention calls eager, and captured 20 stateless draft segments | When a whole phase is still eager, segmentation around unsafe boundaries can retain correctness and remove most submission cost |
| Bound DFlash attention subgraphs | `119.598567` conventional | `+0.9283%` over segmented confirmation | Replaced six eager Python attention submissions with six bound graph replays while retaining the 20/19 outer topology | Once a segmented graph is valid, absorb one proven boundary class at a time with unchanged caller-owned outputs |
| Inline DFlash attention | `119.826868` conventional | `+0.1909%` | Inlined the six proven attention bodies into surrounding segments, reducing draft topology from 20/19 to 14/13 | Removing a real graph boundary can transfer even when the arithmetic is unchanged; require a fresh exact endpoint because nesting changes lifetime |
| Decode GRF128 | `121.290561` conventional confirmation | `+1.2215%` | Actual use was about 94 GRFs, but the kernel was pinned to 256-GRF mode. A separate 128-GRF kernel changed permitted residency from four to eight threads/EU without changing arithmetic | Inspect allocated GRF mode separately from observed register use; gate resource-mode variants to exact hot shapes so prefill and draft stay untouched |
| Transposed immutable BF16 scale layout | `122.828558` conventional confirmation | `+1.2680%` over preceding record; `+2.1730%` against adjacent same-DSO control | Cloned `[expert,N,K/32]` to `[expert,K/32,N]` once at load so each decode K-group scale line is contiguous, without changing a BF16 value or operation | Optimize quantization metadata locality, not only packed weights; represent block-prefetch geometry honestly and gate it before endpoint use |
| Exact M12 Q/K RMSNorm plus NeoX RoPE | `124.642413` conventional confirmation | `+1.4767%` | Reduced three kernels to one per target layer while preserving reduction tree, explicit BF16 boundary, weights, cache, and operation order | Shape-specific exact fusions are strongest where they remove repeated device operations and preserve low-precision rounding literally |
| Exact M12 shared elementwise | **`125.461973` conventional** | `+0.6575%`; component saved `0.734276 ms/cycle` | Fused shared-expert SiLU-times-up and routed-scale-plus-shared-add; 192 device operations became 96 over 48 layers | Use an absolute full-cycle millisecond floor. A modest component ratio over many calls can beat a spectacular ratio over a few microseconds |

Primary evidence for the early ladder is the
[campaign transfer ledger](2026-07-26-campaign-transfer-ledger.md). Later
record notes are the [segmented draft graph](2026-07-30-dflash-segmented-graph-preregistration.md),
[attention subgraphs](2026-07-30-segmented-dflash-attention-subgraphs-preregistration.md),
[inline attention](2026-07-30-segmented-dflash-inline-attention-preregistration.md),
[GRF128](2026-07-31-decode-grf128-confirmed-record.md),
[transposed scales](2026-07-31-transposed-decode-scales-confirmed-record.md),
[M12 Q/K RMSNorm plus RoPE](2026-07-31-qknorm-rope-m12-confirmed-record.md),
and [M12 shared elementwise](2026-07-31-shared-elementwise-m12-record.md).

## Other measured wins that should guide future work

- The BF16 router plus persistent DFlash context-KV workspace improved a
  matched endpoint from `98.955285` to `99.720152 tok/s` (`+0.7729%`) without
  changing acceptance. It removed FP32 router overhead and repeated workspace
  allocation/layout work, but missed its promotion floor at that time. The
  router and workspace flags are **already enabled in the current 125.462
  record**, so their saving cannot be added again to a new candidate.
- Native M12 BF16 QKV/O reached `123.126671 tok/s`, `+0.2427%` over its valid
  control, but was below noise and not promoted despite a much larger eager
  component saving. This warns that primitive-dispatch wins can disappear in
  Breakable replay.
- Exact M12 router fusion saved about `0.499 ms` over 47 layers but missed its
  old `0.60 ms` standalone floor. It was later retained in the valid
  router/workspace stack and is part of the protected record identity. Treat
  it as harvested headroom, not a future portfolio member.
- The mapped gather-scale-add component was exact and `1.625x` faster, but its
  projected `0.262 ms/cycle` saving missed the `0.30 ms` floor. Stopping before
  endpoint integration was a research victory.

## Research victories that produced leverage

### First-divergent-tensor exactness localization

Compare raw BF16 tensors in model order—layer input, QKV, Q/K norm, RoPE,
attention, O projection, residual/norm, router, and MoE—and force one operation
at a time to the reference arithmetic. A successful pin moves the first
divergence later; it does not prove the whole model. Opaque copies are required
when tracing graphs so the trace observes replay-time values rather than an
aliased capture buffer. This method found width-dependent attention dispatch,
M-dependent INT4 GEMMs, unordered reductions, atomic MoE paths, and several
graph/eager parity defects before endpoint guessing.

### Exact batching without changing arithmetic

Stride-zero batched M=1 GEMM lanes, pseudo-sequence paged decode, deterministic
direct MoE, and fixed-rank BF16 reconstruction reproduced the fresh q=1 teacher
while reducing collective calls from 777 to 98. The reusable idea is to batch
scheduling and storage while preserving accumulation and reduction order in
each numerical lane. Gate each primitive with raw equality before composing it.

### Topology as an activation and safety oracle

Graph counts caught structural regressions immediately: the valid M12 target
is 146/145, while accidental per-row serialization expanded it to 685/684 and
exhausted the device. Counts prove which structure ran, not that its data were
correct. Require topology, raw/token correctness, and live-dependency evidence
as three separate gates, plus a hard capture-segment ceiling.

### Current target-gather localization

The short two-request bisection found prefixes 0–47 exact and prefix 0–48
inexact. With two gathers per layer, slot 48 is layer 24's attention
O-projection gather; slot 49 is the same layer's MoE/final gather. This is a
useful structural map, **not a performance win and not proof that slot 48 alone
is defective**. Keeping slot 48 eager while capturing later slots still failed,
and prefix 48 later passed request 0 at 512 tokens but failed request 1 at token
0. The preregistered prefix-24 full gate then failed request 0 at token 331
despite exact `122/121` activation, normal speculation, cache zero, and clean
teardown. This closes captured target collectives until a tensor trace explains
the dependency. The lesson is to binary-search structural boundaries under a
fresh service, then separately gate length, request turnover, and rollover. A
mismatch index is diagnostic evidence, never a quality score.

The follow-up row-0 tensor trace closed the ambiguity. At the known failing
position 420/input token 20253, all ranks matched through layer-0 attention and
the O-projection's local output. Captured collective slot 0 then returned the
correct gathered tensor on rank 0 and corrupted tensors on ranks 1–3. The
transferable rule is to compare the first collective's producer, rank-local
value, and consumer-visible output on **every rank**. Rank-0 equality is not a
collective-correctness proof. When inputs and local values match but nonzero
ranks first diverge at the consumer-visible collective result, investigate the
capture/replay completion dependency before changing model arithmetic or KV
state. The mechanism remains a hypothesis until a minimal repair proves it.

### Persist evidence before assertions

The first inline-gather harness proved topology but discarded the response when
its assertion failed, so it could not establish a token mismatch. The revised
harness writes raw HTTP responses before validation. Every failure-sensitive
probe should do the same and classify launch, import, initialization,
collective, verification, teardown, and candidate failures separately.

### Verify execution, reachability, and provenance

- A selector in `identity.txt` is not treatment evidence. Prove the reader and
  call site, launcher propagation, compile-time literal or template argument,
  final ISA change, per-worker runtime marker, and treated count/shape.
- An edit command saying success is not proof that the intended file changed.
  Inspect the file and diff before spending GPU time.
- Hash the object actually mapped in `/proc/self/maps`, including transitive
  DSOs and RUNPATH/RPATH resolution—not a neighboring file with the expected
  name.
- Build treatment and control dispatch policies into reduced native libraries;
  make fallback fatal.
- Keep each binary in its own worktree and assert the mapped DSO hash so commit
  provenance cannot silently describe a different artifact.

### A probe must prove it ran before recovery

The old XCCL wrapper pointed at a nonexistent Python source; summary `0/4`
values were incorrectly interpreted as post-reload, post-FLR, and post-SHM
collective failures. Per-rank stage markers and an unambiguous
`PROBE_RESULT=PASS clean_teardowns=4/4` gate now distinguish unknown from
failure. Missing execution authorizes no privileged recovery.

## Patterns that repeatedly failed to transfer

- Reducing collective payload without removing a round trip: local argmax cut
  4.82 MB/cycle to 768 bytes but slowed the cycle and was 12/13. This TP4 path
  is latency/work-count bound at these sizes.
- Spectacular throughput with abnormal or flat speculative acceptance: draft
  graph capture reached `198–551 tok/s` but replayed stale/specialized state.
  Treat this signature as corruption until disproved.
- Tiny graph-contained microfusions selected by relative speedup alone: an
  attention-gate component was `8.16x` faster but regressed the endpoint.
- Source-level LICM or prefetch sweeps without final-ISA reachability: IGC had
  already hoisted scale work, and an earlier width-12 prefetch sweep changed no
  machine code because the launcher never propagated the knob.
- Wider speculation without acceptance/cycle co-tuning: width 14 was slower and
  12/13; width 16 was slower and 0/13.
- Smaller KV precision as an assumed decode win: FP8 KV doubled capacity but
  was `4.132%` slower in the matched short-context screen and changed outputs.
- Component occupancy intuition without endpoint proof: native M8 BF16 MM and
  several exact kernels were slower after full graph integration.

## Where future wins are most likely

Rank candidates by expected **absolute full-cycle saving**, not novelty:

1. A true M12 grouped-GEMM mainloop or work-distribution change. About 69.2% of
   the profiled target time was in expert-GEMM graph segments. Prior B70 wins
   on other models came from tiny-decode work sharing, exact batched submission,
   and tile/scheduling changes—not dequant prologue shaving. Inspect spill,
   occupancy, DPAS order, barriers, and actual M12 dispatch before integration.
2. A complete repeated boundary that can be absorbed without changing live
   dataflow. Do not retry fixed-address gather variants until first-divergent-
   tensor tracing explains the model-specific cross-request failure.
3. A preregistered portfolio of genuinely new independent exact savings. Audit
   the complete current selector stack first: the M12 router and persistent
   context-KV workspace are already enabled and must not receive duplicate
   projected credit.
4. Persistent storage only where replay-time traces show allocation, copy, or
   layout churn. Do not optimize Python work already amortized by capture.
5. Prefill as a separate lane after decode. Max-batched-token direction is
   model-specific: larger helped Qwen while smaller helped MiniMax.

## Victory-recording template

Whenever an experiment wins, add it here and preserve a focused note containing:

1. evidence class and disposition (`promoted`, `measured`, `component`, or
   `research`);
2. exact control and candidate identity, including source commits and mapped
   binary hashes;
3. conventional metric formula, absolute result, delta, percent, and estimated
   or measured milliseconds per cycle;
4. the mechanism in hardware/runtime terms—not only the flag name;
5. raw component equality and complete endpoint correctness scope;
6. cache, topology/work-count, request-lifetime, and teardown evidence;
7. run roots, structured data, patch/bundle, and LocalMaxxing receipt if
   promoted;
8. applicability boundary: shapes, phase, model family, precision, graph mode,
   and what the result does **not** prove;
9. one next action implied by the result.

The general cross-model form belongs in
[`docs/research-workflow-playbook.md`](../../../docs/research-workflow-playbook.md).

# Ideas and things to try

## Toward 200 tok/s for one conversation, without quality loss (2026-10-29)

Owner direction, 2026-10-29: stop drifting into 1–2% levers and keep the
dramatic opportunities in view. This section is the ranked list. It is planning,
not a result; every number is labelled measured or estimated, with its source.

### Where we are (measured)

- SC117 IQ3_S, four B70s, two pipeline stages each split exactly across two
  cards: **78.29–78.62 tok/s**, outputs identical to build B19
  ([fault-ladder result](research/tp/fault-ladder-2026-10-29/RESULT.md)).
  Two cards: 66.42. Each stage takes about 10.4 ms per step.
- The draft is accepted on 76.1% of guesses; a miss costs about 10 ms and takes
  about 18% of decode time ([miss analysis](research/tp/miss-stall-2026-10-29/ANALYSIS.md)).
  With zero misses the same stage speed would give about 96 tok/s.
- **200 tok/s is 5.0 ms per token.** With today's one-guess pipeline that means
  each stage at about 5 ms *and* almost no misses, or more than one accepted
  token per cycle.

### What the measurements say (correcting the obvious first guess)

- **The GPU is not waiting on launches.** A one-card rank-0 half measured 10.16 ms
  of summed kernel time inside a 10.30 ms device span, with **0.12 ms of gaps**
  between kernels (about 860 launches; [submission screen](research/pp4-review-2026-10-28/submission-graph-screen.txt)).
  Host enqueue (4.9–6 ms per half) overlaps device work. So replaying recorded
  command lists would mostly save host CPU time, not step time. It only pays
  where a host thread becomes the critical path (one thread feeding two cards
  did, and per-card threads fixed it).
- **The time is inside the kernels.** A token reads roughly 4 GB of active
  weights (about 2 GB per stage). Two cards per stage give about 1.2 TB/s, so the
  bandwidth floor is roughly 1.7 ms per stage (estimate) against about 10.4 ms
  measured: kernels run at roughly a fifth to a third of what memory allows.
- **Why kernels are slow:** expert kernels were measured instruction-bound
  (IQ3_S/IQ4_NL unpacking plus 32-bit math; every layout variant tried landed at
  55–74 µs vs 60, [DO-NOT-REPEAT](gsq-rco-iq3s/service-speed/DO-NOT-REPEAT.md));
  about 37% of a step is small work copied to both cards (hyper-connection glue,
  norms, router, combine), and each tiny kernel has a minimum duration of a few
  microseconds even when it does almost nothing.
- **Why deeper speculation lost:** each extra verified row costs about 1.6× on
  rank 0, because the kernels are compute-bound, not weight-bound, so a second
  row pays its full arithmetic again ([miss analysis](research/tp/miss-stall-2026-10-29/ANALYSIS.md)).
  This is the same root cause as above.
- **XMX matrix engines are not available to us** under the exactness rule:
  F32 activations against IQ weights cannot go through DPAS without changing
  rounding. Multi-row work must stay on the vector ALUs.

### Ranked opportunities

| # | Idea | Why it could be big | Rough size (estimate) | First experiment |
| ---: | --- | --- | --- | --- |
| 1 | **Weight-stationary multi-row kernels** for experts and dense GEMVs: load each weight block once and apply it to M = 2–4 rows | Removes the 1.6× per-extra-row cost, which is what blocks deeper speculation; also speeds prompt reading | If an extra row costs ≤1.2× instead of 1.6×, depth 3 becomes a win (below) | Per-site one-card timing at M = 1, 2, 4 for the expert and dense kernels; the one-card profiler is safe (it faulted only with `--tp-replicate`) |
| 2 | **More accepted tokens per cycle**: depth 2–3 MTP chains, or tree drafting (top-2 at the first position) verified in one multi-row pass | The only lever that multiplies tokens per step instead of shaving milliseconds | 2–2.5 accepted tokens per cycle at ≤1.3× cycle cost would give roughly 120–150 tok/s on today's stage speed | Needs #1 first; re-run the depth screen with the new kernels. Prior evidence is mixed, not negative: depth 2 on the two-card pipeline lost 9.6% through reduced overlap, while on the three-target + draft layout depth 3 beat depth 2 by 14% |
| 3 | **Per-layer glue megakernels**: fuse the replicated small ops (norms, HC mix/gate, router, top-k, combine) into a few kernels per layer | Attacks the 37% that more cards never shrink, and about 860 minimum-duration launches | If glue halves: about 1.8–2 ms per stage (estimate) | Rank the glue sites by measured µs and count; build one exact fused layer-tail kernel and gate it bitwise. Earlier two-op fusions were neutral or non-exact (DO-NOT-REPEAT rows 24–25), so fuse whole chains, not pairs |
| 4 | **Faster-to-decode lossless weight layout for experts**: re-encode IQ3_S/IQ4_NL codes into a layout whose dequantized values are identical but cheaper to unpack (pre-expanded indices, SLM-resident grids, per-block int8 codes × the same scale) | Experts are instruction-bound while memory sits at a third of its limit, so trading bytes for instructions can pay | Unknown until a kernel bench; experts are about 22.5% of a half | One-expert microbench: same outputs bit for bit, fewer instructions. Needs VRAM: cards are full at 31.4 / 32.2 GB, see #6 |
| 5 | **One stage across all four cards (TP4) instead of two stages (TP2 × PP2)** | No pipeline, so a miss costs no rank-0 redo (today about 18% of decode time), and multi-token verification becomes a plain batched step | Uncertain: replicated work and exchanges grow with four parties; it pays only together with #1 and #2 | CPU sizing from the existing per-site profile, as done for TP2, before any build |
| 6 | **Experts by expert id (half the experts per card) instead of every card holding every expert** | Frees roughly half the expert VRAM per card for #4 layouts, longer context or speculation buffers | Imbalance (about 6 of 10 slots on the busier card) costs some expert time | Census of freed bytes and measured imbalance on the 12 prompts |
| 7 | **Device-side scheduling (a persistent kernel per layer)** | Removes per-kernel minimum durations entirely | High risk on this hardware (no device-wide barrier; a hang faults the card) | Design study only; bounded waits are mandatory |
| 8 | Recorded command-list replay | Saves host CPU; matters only when a host thread is the critical path | Small for decode today (0.12 ms device gaps) | Revisit if host submission becomes critical again (for example prompt reading) |

### Excluded because they would change outputs or break the rules

Lower-precision activations or KV, XMX/DPAS with rounded inputs, folding norm
scales into weights, split sums across cards, lossy draft acceptance,
prompt-lookup or n-gram drafts (barred from headline benchmarks by the validity
rules), and draft training. Quality stays bit-exact to the target model.

### Census result (2026-10-30, measured on one card per rank)

From the [decode site census](research/decode-site-census-2026-10-30/RESULT.md):

- **Half of every step is small kernels.** Kernels under 20 µs make up 84% of
  launches and about half the GPU time (5.0 ms of rank 0's 10.1 ms, 5.4 of
  rank 1's 11.8 ms). On four cards, 3.8–4.2 ms of that per stage runs on both cards.
- **Checking several rows is expensive today.** There is no multi-row decode
  path: two rows cost 2.0× (run one after another). The batched prompt path costs
  2.7–3.0× at 2–4 rows because its tiles are tuned for 256 rows. The best existing
  exact tiles per site give 1.55× at two rows and 2.2× at four, which is not cheap
  enough to make deeper speculation pay (it needs ≤1.52× at two rows).
- **Experts stay costly with more rows.** Consecutive tokens share only about
  4 of 10 experts, so 2/3/4 rows touch about 16/22/27 distinct experts. Each new
  expert costs 13–20 µs per layer; an extra row on an already-loaded expert costs
  almost nothing.
- **Projection (CPU arithmetic over these tables, not a measurement), four cards:**
  ideal multi-row kernels (#1) with deeper speculation (#2): about 109 tok/s;
  plus glue halved (#3): about 120; plus experts at their memory limit (#4):
  about 144. One stage over four cards (#5): up to about 150. **200 is not
  reached by any combination under realistic costs**, only in an upper bound
  that assumes free misses and perfect stage overlap (206–218).
- **What the list leaves for the rest of the way:** the draft (1.3 ms per chain
  step, about 0.43 ms of it the vocabulary head), about 2 ms per stage of
  card-to-card exchange and waiting on four cards, and acceptance (76% per guess;
  at 90% per position the full stack projects to about 195).

### Ideas the census added

| Idea | Why | Size (estimate) |
| --- | --- | --- |
| Split the replicated small GEMVs (HC low/gate, shared expert, router) across the two cards of a stage by output rows, with direct-store gathers | About 2 ms per stage of weight reads now done on both cards | A few percent: each split saves about 5 µs per site against a 2–3 µs exchange |
| A cheaper draft vocabulary head for chained drafting (for example the most frequent tokens only, falling back to the full head) | Draft head is 0.43 ms of each 1.3 ms chain step; outputs stay exact because the target verifies every token | Matters only at depth 2–3, where the draft costs about 4 ms per cycle; changes acceptance, which must be measured |
| Break down the four-card stage overhead (about 2 ms beyond an ideal split: exchanges, waits at about 70 sync points, snapshot) | Second-largest non-kernel cost on four cards | Unknown until measured; a per-exchange wait trace on the TP harness answers it |
| Tree drafting (top-2 at the first position: 87.6% coverage against 76.1%) | Raises accepted tokens per cycle without draft training | Needs a cheap multi-row pass first |

### Multi-row verification result (2026-10-30, measured)

[multirow-verify-2026-10-30](research/multirow-verify-2026-10-30/RESULT.md): every path is exact, but the
whole pass costs **1.42× / 1.47× at two rows and 2.32× / 2.46× at four** (rank 0 / rank 1), against the
go/no-go of 1.35× and 1.9×. The dense projections now cost about one row's time for two rows (new small-row
tiles, default off). What is left is the routed experts: rows bring new experts, and three exact grouped-expert
kernels were all slower than per-slot one-row kernels. The tiny shared-expert matrices are launch-bound.
Plugging the measured ratios into the census model gives roughly 85 tok/s on four cards at one guess per block
and less at deeper chains, against 78.3 measured today. That is about +9% for a large verifier build (projection,
not measured), so **the verifier (K4) is parked**. Revisit it when the replicated per-layer work and the experts
are cheaper, because both also lower the multi-row ratio.

### Four-card stage overhead (2026-10-30, measured)

[stage-overhead-2026-10-30](research/tp/stage-overhead-2026-10-30/RESULT.md): the overhead is 1.58 ms per half on
rank 0 and 1.68 ms on rank 1 (the census's 1.96 ms used an older 10.82 ms cycle; today's is 10.41–10.45 ms).
About two thirds is split kernels that do not halve (each launch keeps a fixed part: experts on 5 slots run at
0.59–0.70 of their 10-slot time, the GDN recurrence at 0.8, QSA attention not faster at all). The exchanges cost
about 0.2 ms, imbalance between the two cards 0.04–0.06 ms, host event retirement 0.17–0.24 ms; the snapshot is
now negligible. Rebalancing slots, heads or vocabulary rows cannot help.

### Fixed-cost campaign result (2026-10-30, measured)

[fixed-cost-2026-10-30](research/tp/fixed-cost-2026-10-30/RESULT.md): **84.47 / 84.51 tok/s on four cards against
78.90 / 78.60** (1.073×), outputs = B19, from a paired gate+up+SiLU expert launch per card (0.30–0.34 ms per half) and
deferred host event retirement (0.29–0.30 ms per half). The fused GDN kernel, producer-tail exchanges and glue-chain
fusion were each sized at 0.05–0.1 ms per stage and closed. Rank 0 (half + draft, about 9.7 ms) is now the slower
stage in 68–85% of steps. The remaining fixed cost is spread over hundreds of small kernels; the next question is
whether a persistent kernel per layer can remove it wholesale (`research/persistent-layer-2026-10-30/`, in progress).

### Persistent layer kernel (#7) result (2026-10-30, measured, closed)

[persistent-layer-2026-10-30](research/persistent-layer-2026-10-30/RESULT.md): **no-go.**
- A kernel boundary on a B70 costs only 0.63 µs (empty kernel, host ahead) to 1.1 µs (tiny dependent kernel).
- A bounded device-wide barrier costs 0.57 µs plus about 10 ns per arriving group: 1.5 µs at the 64 × 1024 groups
  that fill the card, 6.7 µs at 512 × 128. At most 65,536 work-items can be resident, matching the driver's query.
- The real HC block: 37.45 µs as six launches, 41.04 µs as the best persistent kernel. It is bitwise exact, but slower.
- Projection: −7.7% on four cards as measured; +8.5% at most even with a free barrier.
- The tiny kernels' fixed cost is inside them, not between them.
- Side finding: this bench's plain BF16 HC GEMVs run at 482–529 GB/s against the engine's 400–415 GB/s on the same
  shapes. That is worth about 0.3 ms per half per card if the engine's exact reduction order can be kept.

### Decision rule

Since 2026-10-30 afternoon: one fixed-cost campaign (`research/tp/fixed-cost-2026-10-30/`). In order: a paired
gate+up+SiLU compact expert launch, event retirement off the critical path, one fused GDN small-kernel launch,
exchange stores in the producer's tail, then fusing the largest replicated glue chains. The end gate is fresh
four-card servers A/B/A/B with a target of +7% or more.

Previously (2026-10-30 morning): find where the four-card layout's unexplained ~2 ms per stage goes (exchanges, waits for
the slower card, split-kernel efficiency, host). It is about 18% of the 10.82 ms cycle and is not covered by any
idea above (`research/tp/stage-overhead-2026-10-30/`, in progress). Then cut the replicated per-layer work, which
is about 4 ms per stage: split the HC projections across the pair, and fuse the weightless glue into neighbouring
kernels (each tiny kernel costs at least about 2.5 µs). Prefer a lever that changes tokens per cycle or halves a
stage over another 1–2% trim.

# Ideas from other runtimes

Stage 0, 2026-10-10. Static source and documentation survey only. No borrowed
code, dependency adoption, build, weight download, GPU probe, or external
performance verification. Nine depth-one, blob-filtered clones were read in
`/tmp/own-xpu-ideas-survey`; only selected text blobs were fetched. The clones
and all survey scratch were deleted after this document was written. Commands
used `nice -n 19` and `OMP_NUM_THREADS=2` for clone/read orchestration.

The [owner's objective](../../docs/own-xpu-runtime-objective.md) governs this
survey. This is a lab-authored design note, not contributed runnable work or a
promoted result. The bounded provenance/static-review steps of
[review-model-contribution](../../.agents/skills/review-model-contribution/SKILL.md)
apply. The earlier Strata intake remains
[community-reported](../../community/niko1221-strata-flash-next-quants/STATUS.md).
Other projects below are acknowledged research sources; their B70 effect is
**not measured**. No contributor boost or implementation adoption is claimed.

## How to read the rankings

**High** means the idea attacks a substantial measured overhead or enables a
model to fit. **Medium** means a useful but conditional opportunity requiring a
new census. **Low** means the known kernel is near its measured floor, the idea
addresses another workload/hardware, or it violates the lane's constraints.
These are priorities, not predicted percentages, and capacity gains are not
throughput gains. All priorities assume one compute queue per B70, 32 GB per
card, one to four cards, and overlap through copy engines only.

**I (idea)** means an independently written design can use the observation,
with attribution. **C (code)** means taking the named implementation literally
would require copying/porting upstream code; that is excluded. Each project
has both labels below so a source path never becomes permission to import it.
Intel platform libraries remain ordinary dependencies; IPEX-LLM's model stack,
for example, is not itself a platform-library exception.

## Local evidence that bounds the opportunity

| Evidence | What was actually measured | What it permits us to infer |
| --- | --- | --- |
| [LTX dispatch diagnosis](../ltx25-b70/notes/dispatch-bound-diagnosis-01.md), [receipt](../ltx25-b70/data/dispatch-bound-diagnosis-01.json) | Historical small-shape probe: device copy 536.8 GB/s (rounded 537); BF16 projection effective rates 545.1–573.5 GB/s. Host profiling showed extensive operation issue overhead. | Whole-step ownership is promising; replacing these GEMMs alone is low priority. This was synthetic-weight operator diagnosis, not a Qwen measurement. |
| [27B INT4 cost model](../qwen38-27b-b70/notes/2026-08-19-autoround-int4-step-cost-model.md) | TP2 MTP5: 35.3 ms step, about 22.8 ms accounted, about 12.5 ms residual; wide weight-streaming ops around 540–590 GB/s. | Attack dispatch/state/sampler overhead first. Burst rates above this range for small matrices were L2 artifacts, not a faster DRAM path. These are historical INT4 TP2 shapes, not Stage 1 FP8 TP1 targets. |
| [9B draft-head probe and result](../qwen35-9b-b70/notes/2026-09-10-one-server-for-every-batch-size.md) | Random-weight diagnostic: INT4 M=1 head 0.894 ms, 586 GB/s effective; copy about 573 GB/s one way; argmax 0.03 ms. | GEMV-plus-argmax fusion cannot remove the weight read. Fewer draft bytes are a separate acceptance/quality-policy decision, not the default 27B plan. |
| [Flash-Next M=2 attribution](../qwen38-flash-next-fp8-b70/notes/2026-09-13-a378-a379-row-wise-selector-cost-result.md) | Certified-selector control forward 33.69 ms; MoE 14.2 ms; QSA 4.7; GDN 2.1; row-wise collective excess 1.5; 11.2 ms unattributed. Disabling the all-reduce selector changed output. | Verify orchestration and dense projection attribution deserve priority. The entire 11.2 ms is **not** proven removable glue. Keep serial row arithmetic until a replacement passes the operator census. |
| [Current LTX feasibility correction](../../notes/2026-10-10-sampler-feasibility.md) | Later capture work superseded the old three-quarters-dispatch diagnosis; current video shapes differ. | Do not subtract historical dispatch shares from today's sampler or predict a Qwen speedup from LTX capture results. |

The 27B cost-model note explicitly **retracts** its 6.3 microsecond
"captured collective" interpretation: naive XCCL capture replayed stale data.
A new collective graph must pass changing-input, multi-replay tests before
being timed. Fixed-input replay equality cannot prove that it ran correctly.

## Pinned source inventory

All pins are the fetched default-branch heads observed during this survey,
not statements that these identities are certified or suitable dependencies.
TensorRT-LLM was inspected only under its documentation tree.

| Project / credited authors | Inspected commit |
| --- | --- |
| Strata / Niko1221 and contributors | [`61b3fb5dd3f1e8ec09cf7e4e05208bc6d3c46406`](https://github.com/Niko1221/Strata/tree/61b3fb5dd3f1e8ec09cf7e4e05208bc6d3c46406) |
| llama.cpp / ggml-org and contributors | [`69f201a2051ea9b9e9b50c3cc56afd9e2ae64414`](https://github.com/ggml-org/llama.cpp/tree/69f201a2051ea9b9e9b50c3cc56afd9e2ae64414) |
| ik_llama.cpp / ikawrakow and contributors | [`89bba35c8841618502b2be8273fb5265b405aca1`](https://github.com/ikawrakow/ik_llama.cpp/tree/89bba35c8841618502b2be8273fb5265b405aca1) |
| vLLM / vllm-project and Intel XPU contributors | [`187a0eb98aa42341d703f83421d693fa7585581b`](https://github.com/vllm-project/vllm/tree/187a0eb98aa42341d703f83421d693fa7585581b) |
| SGLang / sgl-project and Intel XPU contributors | [`f9cee8d2b2d96a626db1968ba81e4d72bb31794a`](https://github.com/sgl-project/sglang/tree/f9cee8d2b2d96a626db1968ba81e4d72bb31794a) |
| IPEX-LLM / Intel and contributors | [`de6bce27133ab250f13fd5d549c197519ce16d30`](https://github.com/intel/ipex-llm/tree/de6bce27133ab250f13fd5d549c197519ce16d30) |
| exllamav3 / turboderp and contributors | [`151539c77abc7ab7425d30da7a4e8e3c5c154e7b`](https://github.com/turboderp-org/exllamav3/tree/151539c77abc7ab7425d30da7a4e8e3c5c154e7b) |
| MLC-LLM / mlc-ai and contributors | [`8978ea9aec626d64096aaa92fbc89bda2e3ea802`](https://github.com/mlc-ai/mlc-llm/tree/8978ea9aec626d64096aaa92fbc89bda2e3ea802) |
| TensorRT-LLM documentation / NVIDIA and contributors | [`7179c5b01b9d19acef69a6526330eb72f3b70e10`](https://github.com/NVIDIA/TensorRT-LLM/tree/7179c5b01b9d19acef69a6526330eb72f3b70e10) |

## Strata

Source: [SYCL verifier][strata-verify], `sycl/src/core/expert_cache.cpp`,
`remote_experts.cpp`, `vmm.cpp`, `graph.cpp`, and
`sycl/src/kernels/cuda/{native_mmvq,native_moe}.dp.cpp` at the pin above.
The earlier [Strata review](../../notes/2026-10-10-strata-flash-next-quants.md)
records its provenance and quant-format inventory.

| Idea | Priority and reason |
| --- | --- |
| Expert slot cache, packed expert sources, copy batches, and explicit host/device capacity budgets | **High, capacity; medium, speed.** A two-card Flash-Next quant exceeds aggregate VRAM, so bounded streaming is essential, but host-shadow and PCIe cost decide speed. |
| Record verifier work with stable inputs and explicit commit of recurrent state | **High.** This attacks the local M=2 orchestration opportunity while exposing rollback as a correctness contract. |
| Subgroup-width-specific IQ/K GEMV and fused ordered expert combination | **Medium.** Relevant to a future allowed mixed-GGUF target; keep its exact block decoding, activation precision and expert summation order rather than importing CUDA warp geometry. |
| Peer expert placement and remote expert scheduling | **Medium.** Compare layer/expert splits against measured transfers; asynchronous shared-expert compute has no same-card overlap budget on this B70 design. |
| Graph lifetime and completion-event ownership | **High for reliability, low for direct decode speed.** The source warns that graph destruction can wait implicitly and falsify completion measurements; our teardown must prove idle first. |
| Elastic VMM and compressed KV | **Low / excluded as proposed.** The SYCL VMM implementation is a stub, so CUDA elastic allocation is only an idea; compressed KV is outside the default lossless lane. |

**I:** independently implement expert residency tables, bounded copy pipelines,
nonempty-graph checks and state commit. **C:** Strata's DPCT-migrated runtime,
GGML-derived MMVQ code, grid tables and packers are not our starting code.
Its format conversion can change precision; packing is not automatically
bit-preserving. No Strata checkpoint source overrides official/Unsloth policy.

## llama.cpp SYCL, graph and speculation paths

Source: [SYCL MMVQ][llama-mmvq], `ggml/src/ggml-sycl/dequantize.hpp`,
`ggml-sycl.cpp`, `common/speculative.cpp`, and `src/llama-memory-hybrid.cpp`.

| Idea | Priority and reason |
| --- | --- |
| Separate scale/quant layouts; block-local IQ lookup/sign decoding and K-scale unpacking fused into vector products | **Medium for GGUF, low for existing FP8/INT4 kernels.** Avoid materializing full dequantized matrices, but the certified dense kernels already approach their memory floor. |
| Multi-column MMVQ reuses unpacked weights across verifier rows; selected-expert MMVQ | **Medium.** M=2 is directly relevant, provided row-invariant arithmetic survives a complete shape census. The source's B70-specific thresholds are outside claims until reproduced. |
| SYCL command graphs, graph reuse and stable backend pools | **High.** Use the lifetime and replay ideas to remove host issue work; GGML graph construction itself is not our runtime. |
| MTP accept/reject with separate attention and recurrent-state memory | **High for correctness; medium for speed.** Rejection must roll back GDN state and KV consistently while the target verifies every accepted token. |
| Layer/tensor splits, hybrid KV/recurrent storage and backend buffer lifetime | **Medium.** Budget fixed 16-bit KV and recurrent state per layer, and choose splits from our collective census; the source supplies no B70 GuC teardown proof. |

**I:** block-format contracts, fused unpack scheduling, row reuse, memory
ownership and rollback concepts. **C:** GGML backend/model graphs, quant
kernels/tables and speculative implementation are excluded as code imports.
Q8 activation quantization in a GGUF dot path is not automatically equivalent
to the certified FP8 target. N-gram/history modes are excluded from headline
work; DFlash remains closed for the 27B FP8 lane.

## ik_llama.cpp

Source: [IQ/K matrix multiplication rationale][ik-matmul],
`ggml/src/iqk/iqk_gemm_iquants.cpp`, `ggml/src/ggml-sycl/mmvq.cpp`, and
`docs/speculative.md`.

| Idea | Priority and reason |
| --- | --- |
| Reuse unpacked quant values and scales across multiple input columns | **Medium.** This could help M=2 verification or prefill, but M=1 has no cross-row reuse and the inspected IQK explanation is CPU-oriented. |
| IQ grid/sign-table locality and tiled K/I dot products | **Medium for new GGUF support.** Useful layout questions for B70 subgroups, not evidence that CPU AVX/NEON or CUDA implementations transfer efficiently. |
| Small-row SYCL IQ GEMV specialization and sparse expert dispatch | **Medium.** Measure only formats/shapes in the allowed model's tensor map; retain deterministic routing and ordered expert reduction. |
| Staged MTP/draft verification | **Medium.** Clear stage boundaries suggest replay keys and rollback tests; acceptance improvements cannot be inferred from another model's speculation. |
| Graph, KV, multi-card arena and teardown policies | **Low as new evidence.** The selected files do not establish an independently validated B70 improvement in these areas; use our own graph/census/teardown evidence. |

**I:** amortized dequantization and format-specific blocking. **C:** IQK
kernels, alternative quant implementations and forked GGML code are excluded.
Do not take the source comment's CPU speed percentages as B70 measurements.
Do not acquire a fork-specific quant from an unapproved publisher.

## vLLM XPU

Source: [XPU expert implementation][vllm-moe],
`vllm/v1/worker/xpu_model_runner.py`,
`distributed/device_communicators/xpu_communicator.py`,
`compilation/base_static_graph.py`, and `device_allocator/xpumem.py`.

| Idea | Priority and reason |
| --- | --- |
| Explicit expert quant contracts, workspace sizing, routing/final reduction boundaries | **High for Flash-Next.** MoE is 14.2 ms in the cited M=2 decomposition; eliminate staging/dispatch only where measured, preserving its exact arithmetic. |
| Static graph wrapper separated from model definition and graph-mode selection | **High.** Our own target/MTP/sampler/state replay can avoid framework dispatch while recording every kernel identity. |
| XPU-specific linear/MoE selection instead of generic backend assumptions | **Medium.** Xe2/Xe3 paths and unquantized-input expectations deserve contract tests; avoid writing a new GEMV where local kernels already stream at roofline. |
| Allocator handles/pools and explicit communication interface | **High for memory accounting, medium for speed.** Track host shadows and replay-owned storage; collective cost and stale-capture failures forbid assuming communication vanishes. |
| Paged KV, speculative scheduler and multi-GPU abstractions | **Medium for later serving.** Own only model-specific state and immutable graph keys initially; batching and paging need independent exactness gates. |
| General worker/allocator teardown | **Low as a safety authority.** Our exit-fault probes outrank ordinary upstream process cleanup for this host. |

**I:** modular buffer/quant contracts and ownership separation. **C:** vLLM
model runner, scheduler, MoE implementation and loader are not our base.
The newest surveyed runner aliases graph calls onto `torch.xpu`; that is
source capability, not proof that whole-step MTP is correct on our driver.
Our existing accepted overlay has separate authorship and measured evidence
in [INVENTORY.md](INVENTORY.md).

## SGLang

Source: [XPU full-graph backend][sglang-graph],
`xpu_graph_runner.py` in the same directory,
`hardware_backend/xpu/attention/xpu_gdn_backend.py`,
`hardware_backend/xpu/quantization/int4pack_utils.py`, and
`layers/moe/moe_runner/triton.py` under `python/sglang/srt/`.

| Idea | Priority and reason |
| --- | --- |
| One graph per explicit shape key, static outputs, shared prefill/decode graph pool | **High.** Reduces issue overhead and duplicate graph residency, provided captures with shared storage never overlap. |
| Distinguish AWQ-interleaved and natural compressed-tensors INT4 nibble layouts | **Medium for loader correctness.** Avoid a silently wrong unpacker; same bit width does not mean same storage order or zero-point arithmetic. |
| Separate recurrent GDN state from attention KV and route expert rows into tuned Triton tiles | **High for Flash-Next correctness; medium for speed.** Supports native MTP state handling while retaining our exact serial recurrence and owned tuning census. |
| Graph capability checks, TP boundaries and cleanup | **Medium.** The XPU runner explicitly rejects two-batch overlap and several MLP TP gather/sync cases, consistent with avoiding imaginary same-card overlap. |
| Paged pools and serving cache ideas | **Low for Stage 1; medium later.** Allocation/page layout may help capacity, but prefix/response reuse and compressed KV must stay disabled for the cold suite. |

**I:** graph-key completeness, mutually exclusive shared pools, quant-layout
validation. **C:** graph runner, Triton MoE and GDN implementation are not
imported. Source cleanup clears graph/output dictionaries and pool references;
that is not a queue-quiescence proof for B70. Its compile-error suppression
must not become a silent fallback in a certified run identity.

## Intel IPEX-LLM

Source: [low-bit linear contracts][ipex-linear],
`python/llm/src/ipex_llm/transformers/models/qwen2_moe.py`, and
`transformers/speculative.py`.

| Idea | Priority and reason |
| --- | --- |
| Explicit low-bit type dispatch and backend packing/conversion boundaries | **Medium.** Useful validation checklist for IQ/K and INT4 layout support; use native stored precision without hidden requantization. |
| Merged projections and shape-specialized linear execution | **Low to medium.** Reducing launches may help, but a new dense GEMV cannot promise gains over the local bandwidth-bound implementation. |
| Device-only MoE routing as the inverse of its CPU-ID path | **High.** The inspected M=1 Qwen2 MoE copies expert IDs to CPU and loops there; our design should make this host-read trap impossible. This is a negative example, not a Flash-Next port. |
| Draft/verify separation, ordinary KV and multi-card partition examples | **Medium as concepts.** Preserve target verification, fixed 16-bit KV and exact arithmetic; self-speculation and FP8-cache options are not default choices. |
| Graph arenas and safe teardown | **Low as new evidence.** The selected wrapper/model files do not prove whole-step capture or GuC-safe release; ordinary Python tensor destruction is insufficient. |

**I:** type contracts, fused-projection scheduling and identifying host round
trips. **C:** IPEX-LLM wrappers/model patches and its bundled non-platform
implementations are excluded; oneDNN/oneMKL/Level Zero remain allowable
libraries. No opaque low-bit routine is accepted without matching arithmetic
and dependency identity.

## exllamav3

Source: [small-M GEMV layout][exllama-gemv],
`exllamav3/exllamav3_ext/graph.cu`, `modules/moe_batch_recon.py`,
`model/model_tp_alloc.py`, and `cache/recurrent.py`.

| Idea | Priority and reason |
| --- | --- |
| Register-prefetched GEMV tiles with subgroup-private work and fixed final reduction | **Medium for an off-roofline new format; low for our dense head.** The layout idea transfers, CUDA warp constants and EXL3 arithmetic do not. |
| Batched expert reconstruction only above a measured crossover | **Low for one-token decode; medium for prefill.** The inspected path groups hot experts at prefill and creates dense scratch; it can waste capacity and change rounding if adopted indiscriminately. |
| Stable graph parameters and explicit eager/graph equivalence | **High.** Run identical launch sequences with changing inputs to prove replay, then measure saved dispatch. |
| Memory-ratio TP allocation and shape/dtype pools for recurrent buffers | **Medium to high for capacity.** Bound allocator churn and account peak lifetime, adding our per-rank host-shadow cost and excluded host memory blocks. |
| Cache representations, MTP and cleanup | **Medium for state ownership; low for direct transfer.** Keep 16-bit KV and native verified MTP; CUDA destructor semantics do not prove safe Level Zero teardown. |

**I:** prefetching, lifetime-based pooling and explicit graph/eager controls.
**C:** EXL3 codebooks, quant kernels, CUDA graph parameter patching and TP
runtime are excluded. EXL3 is not a GGUF IQ/K decoder; producing EXL3 weights
would be a new quantization/quality project, not a free repack of FP8.

## MLC-LLM

Source: [allocation/lifetime memory estimator][mlc-memory],
`python/mlc_llm/compiler_pass/attach_cuda_graph_alloc_init_func.py`,
`python/mlc_llm/quantization/group_quantization.py`,
`python/mlc_llm/nn/kv_cache.py`, and
`cpp/serve/engine_actions/auto_spec_decode.cc`.

| Idea | Priority and reason |
| --- | --- |
| Statically planned buffer lifetimes plus precreated graph allocations | **High.** Removes allocator work and makes replay pools auditable; add driver shadows because compiler tensor estimates alone miss host residency. |
| Model-specific compile-time schedules and group-dequant fusion | **Medium.** Specialize only actual model shapes and stored formats; TVM/group INT4 formats do not establish IQ/K support or exact FP8 arithmetic. |
| Decide draft length before entering a fixed graph variant | **Medium.** Could avoid unnecessary drafting later, but graph/state keys and catch-up must preserve target identity; Stage 1 starts at fixed depth. |
| Typed paged KV interface and explicit distributed model loading | **Medium for later serving/capacity.** Separate logical pages from physical buffers and place from measured per-card floors; use 16-bit storage. |
| MoE packing, GEMV geometry and teardown | **Low as direct evidence.** The selected compiler/runtime interfaces do not prove Xe2 kernels or safe GuC teardown; existing local kernels remain the starting inventory. |

**I:** static lifetime analysis, preallocation and typed state interfaces.
**C:** importing TVM/MLC model graphs/compiler/runtime as our base is excluded;
write a small model-family graph specification here instead. CUDA graph
allocation is a conceptual reference, not an Intel implementation dependency.

## TensorRT-LLM documentation (concepts only)

Source: [graph design guide][trt-graph],
`docs/source/features/{parallel-strategy,speculative-decoding,paged-attention-ifb-scheduler}.md`,
and `docs/source/legacy/reference/memory.md`. The last page explicitly says
its backend is removed; its lifetime categories are historical concepts only.

| Idea | Priority and reason |
| --- | --- |
| Capture a fixed decode shape while keeping allocation and scheduling outside | **High.** Matches the local dispatch opportunity; CUDA graph/piecewise examples do not guarantee XPU exactness. |
| Account weights, persistent state, activations, I/O and peak workspace separately | **High for capacity.** Extend this accounting with B70 graph pools, host shadows and bounded copy staging. |
| Target-verified speculation and packed verifier rows | **Medium.** Amortizes weight reads only if acceptance and M=2 exactness survive; no borrowed acceptance or throughput figures. |
| TP versus PP versus EP selected by communication/work balance | **Medium.** Useful alternatives for the placement census; NVIDIA fabric and wide-EP compute/communication overlap assumptions do not carry to one B70 compute queue. |
| Paged KV and inflight request scheduling | **Medium later, low for Stage 1.** Capacity management is useful; compressed KV, request cache reuse and generic batching must not alter the certified single-user authority. |
| IQ/K dequant, Xe GEMV, packed experts and orderly free | **Low as implementation evidence.** These docs supply no B70 code or teardown proof; all kernels and the release protocol must be ours. |

**I:** scheduling, memory categories and communication tradeoffs.
**C:** no TensorRT/CUDA implementation was inspected for reuse or proposed
as a dependency. These are documentation concepts only.

## First five ideas to test

1. **Own the complete replayed decode step — high.** Device-resident inputs,
   native MTP verification, sampler and state commit share one model-specific
   schedule. Credit graph/verification ideas to Strata, llama.cpp, vLLM,
   SGLang and TensorRT-LLM above; start from our owned LTX capture lessons.
2. **Keep routing, acceptance and recurrent updates off the host — high.**
   Credit the verifier/state interfaces above and IPEX-LLM's host-ID path as
   a negative example. First attribute the Flash-Next residual; do not claim
   all unattributed time is removable.
3. **Plan graph/workspace lifetimes with explicit host-shadow budgets — high
   for capacity, medium for speed.** Credit MLC allocation analysis, SGLang
   pool sharing and exllamav3 recurrent pools. Every allocation belongs to a
   census category; active graph storage cannot be recycled early.
4. **Packed resident experts plus bounded copy-engine streaming — high for
   Stage 2 capacity, medium for speed.** Credit Strata's expert cache and
   vLLM/SGLang expert interfaces. Use only allowed quant weights, retain
   routing/expert count, and measure PCIe stalls and host shadows.
5. **Model-specific multi-row dequant/GEMV for genuinely off-roofline shapes
   — medium.** Credit llama.cpp/ik_llama.cpp unpack reuse and exllamav3 tile
   scheduling. Restrict work to measured gaps; do not reopen the dense
   roofline GEMM or draft-head micro-optimization campaigns.

Orderly teardown is a prerequisite for all five, not a speculative tok/s
improvement. No upstream source examined establishes that the B70 exit-fault
class is solved. The [design](DESIGN.md) must use our own quiesce, ordered
release and idle-proof protocol, and Stage 0 authorizes none of its execution.

[strata-verify]: https://github.com/Niko1221/Strata/blob/61b3fb5dd3f1e8ec09cf7e4e05208bc6d3c46406/sycl/src/core/verify.cpp
[llama-mmvq]: https://github.com/ggml-org/llama.cpp/blob/69f201a2051ea9b9e9b50c3cc56afd9e2ae64414/ggml/src/ggml-sycl/mmvq.cpp
[ik-matmul]: https://github.com/ikawrakow/ik_llama.cpp/blob/89bba35c8841618502b2be8273fb5265b405aca1/ggml/src/iqk/iqk_mul_mat.cpp
[vllm-moe]: https://github.com/vllm-project/vllm/blob/187a0eb98aa42341d703f83421d693fa7585581b/vllm/model_executor/layers/fused_moe/experts/xpu_moe.py
[sglang-graph]: https://github.com/sgl-project/sglang/blob/f9cee8d2b2d96a626db1968ba81e4d72bb31794a/python/sglang/srt/hardware_backend/xpu/graph_runner/xpu_full_graph_backend.py
[ipex-linear]: https://github.com/intel/ipex-llm/blob/de6bce27133ab250f13fd5d549c197519ce16d30/python/llm/src/ipex_llm/transformers/low_bit_linear.py
[exllama-gemv]: https://github.com/turboderp-org/exllamav3/blob/151539c77abc7ab7425d30da7a4e8e3c5c154e7b/exllamav3/exllamav3_ext/quant/exl3_gemv_kernel.cuh
[mlc-memory]: https://github.com/mlc-ai/mlc-llm/blob/8978ea9aec626d64096aaa92fbc89bda2e3ea802/python/mlc_llm/compiler_pass/estimate_memory_usage.py
[trt-graph]: https://github.com/NVIDIA/TensorRT-LLM/blob/7179c5b01b9d19acef69a6526330eb72f3b70e10/docs/source/features/torch_compile_and_piecewise_cuda_graph.md

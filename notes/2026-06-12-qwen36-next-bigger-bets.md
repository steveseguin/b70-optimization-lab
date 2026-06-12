# Qwen3.6 35B INT8 Next Experiments And Bigger Bets

Date: 2026-06-12

Current target:

- Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`.
- Hardware: 4x Intel Arc Pro B70 32GB.
- Runtime anchor: vLLM/XPU TP4, Quark W8A8 INT8, 32K context, accepted graph
  cache, no prefix caching.
- Quality constraint: the current Quark W8A8 model remains the source of truth.
  No Qwen3.5 substitutions, no 4-bit/AWQ substitutions, and no speed result is
  promoted without exact sentinel and canary proof.

Current speed anchor:

- Public exact-model Localmaxxing row:
  `cmq8yhxvo001ipb0149aoa79o`, `99.428 tok/s`, c1, 32K context,
  4x Arc Pro B70.
- Restored post-recovery local sanity run:
  `99.728 tok/s` corrected after-first and `98.212 tok/s` e2e at p512/o512/c1.
- Practical interpretation: about `100 tok/s` is now the proven quality baseline.
  The `>200 tok/s` c1 goal needs either verifier-safe speculation or a real
  MoE/kernel architecture improvement. Launch flags alone are unlikely to get
  there.

External signals folded into the backlog:

- Intel's grouped-GEMM issue says realistic route distributions matter for XPU
  MoE tuning and points at extending grouped-GEMM benchmarks with real token
  distributions:
  `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`.
- Intel's Arc Pro B-series vLLM writeup calls out the same MoE bottleneck:
  kernel launch overhead, gate dependency stalls, imbalance between groups, and
  a persistent zero-gap kernel design:
  `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`.
- The Intel Triton-XPU backend docs warn that grid dimension order can cost
  `20%` to `2x`, and explicitly call out MoE kernels where token/tile should
  stay on `axis=0` and expert on a higher axis:
  `https://github.com/intel/intel-xpu-backend-for-triton`.
- The PyTorch persistent grouped-GEMM writeup reinforces the same direction:
  grouped GEMM cuts launch overhead and persistent scheduling improves
  utilization for MoE workloads:
  `https://pytorch.org/blog/accelerating-moes-with-a-triton-persistent-cache-aware-grouped-gemm-kernel/`.
- vLLM's MoE kernel design treats all-to-all backend, activation format,
  quantization format, and async support as first-class tuning axes:
  `https://docs.vllm.ai/en/latest/design/moe_kernel_features/`.
- Public B70 aggregate examples show large multi-request throughput can scale
  even while c1 latency remains around the same band. Treat aggregate B70 rows
  as production-capacity clues, not proof that c1 should automatically double:
  `https://forum.level1techs.com/t/intel-b70-launch-unboxed-and-tested/247873`.

## Immediate Things To Try

1. **Integrate the exact preallocated MoE scratch idea into the real path.**
   The local microbench already shows a manual preallocated Quark W8A8 MoE path
   can match `xpu_fused_moe` exactly while cutting a routecapture6 layer sample
   from roughly `270 us` to roughly `206 us`. The next step is to inspect the
   installed vLLM/vllm-xpu-kernels call path and add a default-off exact scratch
   reuse path around remap, quant1, gemm1, activation, quant2, gemm2, and gather.
   This is the highest-confidence non-speculative next patch because it is
   already exact in isolation.

2. **Build a real-route persistent-MoE layerlet.**
   Reconstruct one Qwen3.6 MoE layer outside the server using captured
   `topk_ids`, Quark W8A8 scales, exact weights, grouped GEMM, SiLU/up-gate,
   down projection, top-k weighting, and gather. The test should compare:
   current `xpu_fused_moe`, preallocated staged path, SYCL-TLA grouped GEMM,
   Triton-XPU grouped GEMM with correct grid axis ordering, and any Intel
   persistent-kernel branch available locally.

3. **Make route-window tuning the kernel fixture, not a side report.**
   Routecapture artifacts should drive every MoE kernel screen. Synthetic uniform
   routing is useful only for basic correctness. Performance claims should use
   real layers such as `9`, `14`, `20`, and `21`, with prompt-class windows and
   active-expert histograms recorded next to timing.

4. **Measure the full token latency budget after recovery.**
   Before writing another large kernel, collect a low-overhead per-token
   breakdown: MoE total, grouped GEMM, quant/remap/gather, attention, TP
   collective, scheduler metadata copies, sampling, and OpenAI/frontdoor
   overhead. The offline endpoint parity already rules out frontdoor overhead;
   now the goal is to rank the remaining in-engine milliseconds.

5. **Try block-size and scheduler metadata changes in an isolated lane.**
   Block size `64` keeps showing up in public B70 aggregate recipes. Test it as
   a c1 metadata and graph-stability lever, not as a memory-headroom lever.
   Capture `block_table`, `num_computed_tokens`, `seq_lens`, host copies, and
   device-lost behavior.

6. **Run a strict 8-bit engine bakeoff.**
   Compare only high-fidelity 8-bit or BF16-compatible routes: current vLLM
   Quark W8A8, newer Intel vLLM/vllm-xpu-kernels stacks, OpenVINO/oneDNN GenAI
   only if Qwen3.6 A3B/GDN/MoE support is real, and any Q8/SYCL route that
   preserves target output. Exclude 4-bit, AWQ, Qwen3.5, and any route that
   changes the target model.

7. **Submit only material public rows.**
   The `99.728 tok/s` local sanity run is slightly above the current public
   `99.428 tok/s` row but not a new class of result. Post it only if we want an
   exact refreshed recovery datapoint; otherwise wait for a result that clears a
   meaningful threshold such as `105`, `120`, or `200 tok/s`.

## Bigger, Bolder Ideas

1. **Persistent B70 MoE kernel for Qwen3.6 A3B decode.**
   Treat this as the main non-speculative `2x` bet. The current decode shape is
   launch- and imbalance-heavy: route packing, quant, grouped GEMM, activation,
   second grouped GEMM, and gather are separate enough that each step pays
   overhead. A B70-native persistent kernel should keep workers resident, pull
   dynamic expert tasks from a queue, preserve exact Quark W8A8 math, and emit
   the same output as `xpu_fused_moe`.

2. **Transactional resident-state verifier for exact speculation.**
   Build a verifier that forks live request state in-engine: immutable KV pages
   are aliased, mutable GDN/Mamba/request metadata is copied or versioned,
   candidate tokens are scored by the current Quark W8A8 model, then the
   transaction either commits or rolls back. This is the safest path to
   `>200 tok/s` because it allows MTP, DFlash, n-gram, or target-trace
   proposers without trusting their quality.

3. **Static one-request latency appliance.**
   vLLM is built for dynamic serving. For the c1 target, prototype a fixed-shape
   one-request engine lane with resident metadata, fixed decode buckets,
   no dynamic scheduler churn, preallocated KV/GDN state, fixed sampling, and
   cached graph provenance. It can live beside the production vLLM service as a
   latency-specialized lane.

4. **Hybrid TP/EP route simulation before implementation.**
   Simulate exact expert ownership from captured routes: TP4, TP2 plus
   replicated attention, EP4, hot-expert replication, and cold-expert sharding.
   Compare activation all-to-all bytes against TP allreduce bytes and include
   32K KV headroom. Implement only if the model predicts a real c1 win.

5. **Tile-native W8A8 repack cache with checksums.**
   At load time, repack expert weights into the layout consumed by the fastest
   XPU grouped-GEMM/persistent kernel. Keep a manifest with source tensor hash,
   permutation, tile format, and output equivalence checks. If this works, it
   becomes an engine-neutral asset usable by vLLM, a custom layerlet, or a
   future SYCL route.

6. **GPU-resident metadata update kernel.**
   The device-lost traces point at metadata-copy paths such as block tables and
   computed-token counters. A tiny resident kernel or graph-safe metadata
   update path could reduce per-token CPU/device synchronization and improve
   stability at the same time.

7. **B70 graph artifact certification.**
   Treat graph cache artifacts as quality-critical binaries. Store cache root,
   generated graph hashes, sentinel tokens, launch command, driver/runtime
   versions, and first-token branch proof. Production starts only from a
   certified cache root; benchmarks from uncertified cache roots are diagnostics.

8. **Target-trace-trained proposer, verified by target.**
   Record accepted target continuations and train or tune a small proposer on
   this exact model's token traces. The proposer is never trusted directly; it
   only feeds the resident-state verifier. This could outperform generic
   n-gram speculation while preserving exact target output.

9. **Production dual-lane architecture.**
   Keep TP4/32K for capacity and long prompts, but also evaluate single-card,
   two-card, or static-lane replicas for low-latency c1 traffic. Public B70
   reports suggest extra cards help aggregate throughput more reliably than
   single-request latency, so production may need routing instead of one
   universal backend.

10. **Upstreamable Qwen3.6 XPU perf packet.**
    Package route windows, exact expected token outputs, grouped-GEMM fixtures,
    launch commands, and failure artifacts into a small public repro for Intel
    and vLLM. The useful upstream artifact is not "Qwen3.6 is slow"; it is a
    route-exact MoE/kernel suite that makes B70 bottlenecks reproducible.

## Promotion Rules

- A speed candidate must pass the accepted provenance guard and the exact
  sentinel positions before it is compared to the public baseline.
- A kernel candidate must prove numeric equivalence against the current
  `xpu_fused_moe` or full endpoint output on captured real routes.
- A speculation candidate must use the current Quark W8A8 model as verifier and
  produce a transaction log with accept/reject/rollback evidence.
- A public benchmark should include command, context length, output length,
  TTFT, c1 decode speed, cache-root provenance, and exact quality artifact.

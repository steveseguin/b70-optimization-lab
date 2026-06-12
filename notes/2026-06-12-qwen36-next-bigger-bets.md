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
- vLLM's public W8A8 INT8 docs still describe the official INT8 compute path
  as NVIDIA-only. The XPU/Quark route must therefore be treated as a
  vendor/local stack with its own correctness and performance proof, not as a
  generic upstream W8A8 path:
  `https://docs.vllm.ai/en/v0.18.0/features/quantization/int8/`.
- The open llm-compressor Qwen3.6 W8A8 issue confirms the model-specific
  quantization details are not trivial: Qwen3.6 uses Qwen3.5 MoE classes,
  fused expert tensors, Gated DeltaNet/linear attention, and needs W8A8
  coverage beyond ordinary dense attention layers:
  `https://github.com/vllm-project/llm-compressor/issues/2787`.
- Public B70 TP fault reports point at host-stack, firmware, PCIe topology,
  and vLLM ProcessGroupXCCL interactions as reliability/perf variables. This
  justifies a controlled host-BOM A/B lane before production hardening:
  `https://github.com/vllm-project/vllm/issues/41663`.
- Public B70 aggregate examples show large multi-request throughput can scale
  even while c1 latency remains around the same band. Treat aggregate B70 rows
  as production-capacity clues, not proof that c1 should automatically double:
  `https://forum.level1techs.com/t/intel-b70-launch-unboxed-and-tested/247873`.
- Public dual-B70 llama.cpp notes are another warning that naive multi-GPU
  layer splitting can fit larger models without improving one-request latency.
  Any multi-GPU speed claim needs true concurrent layer parallelism or a
  measured TP/EP benefit:
  `https://github.com/PMZFX/intel-arc-pro-b70-benchmarks/blob/master/multi-gpu.md`.
- Localmaxxing currently shows one approved public row for this exact INT8
  model/B70/vLLM setup, the existing `99.428 tok/s` c1 baseline:
  `https://localmaxxing.com/api/leaderboard?hfId=nameistoken%2FQwen3.6-35B-A3B-Quark-W8A8-INT8&hardwareName=Arc%20Pro%20B70&engineName=vllm&limit=10`.

## Immediate Things To Try

1. **Measure the exact scratch hook before another endpoint promotion.**
   The local microbench already shows a manual preallocated Quark W8A8 MoE path
   can match `xpu_fused_moe` exactly while cutting a routecapture6 layer sample
   from roughly `270 us` to roughly `206 us`. The existing endpoint screens
   already rejected shared mixed workspace and archived a per-layer scratch
   patch, so the next step is narrower: time the actual
   `xpu_fused_moe(..., scratch=...)` hook in the route-replay microbench and
   compare it against the manual staged path. Promote no source patch unless
   this hook proves a real wrapper-level win that the old endpoint result did
   not capture.

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

8. **Add a host-stack A/B lane, but keep it separate from model tuning.**
   Reproduce the accepted command on the closest Intel-validated B70/XPU stack
   available, then compare against the current Ubuntu 24.04.4/HWE host:
   kernel/KMD, GuC firmware, compute-runtime, oneAPI, oneCCL, PyTorch, vLLM,
   and `vllm-xpu-kernels`. This is a reliability and collective-performance
   test, not permission to change the model.

9. **Build a CCL/topology matrix for c1 latency.**
   Keep the accepted model and graph cache fixed while sweeping only
   `CCL_*`, `FI_*`, affinity, worker placement, and TP shape. Record per-token
   all-reduce time and device reset risk. If TP4 communication is a measurable
   wall, the next engine bet should be TP/EP or static-lane routing, not more
   launch flags.

10. **Instrument command-stream overhead per token.**
    Capture the Level Zero/SYCL command timeline for one accepted decode token:
    kernel count, barriers, host waits, memory copies, and collective launches.
    The B70 persistent-kernel literature says host waiting and kernel launch
    gaps are central MoE losses; our routecapture fixtures need to prove how
    much of the `~10 ms/token` is launch/control overhead.

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

11. **Exact DPAS/XMX utilization audit.**
    Prove whether the hot W8A8 MoE and dense paths are actually issuing the
    intended Intel XMX/DPAS INT8 operations at high occupancy. If they are not,
    the biggest win may be a lower-level kernel/layout issue rather than vLLM
    scheduler tuning. The output should be a table per kernel: shape, layout,
    DPAS/XMX use, occupancy, bandwidth, and launch count.

12. **Quant-output out-variant and fusion campaign.**
    The current scratch hook reuses remap/GEMM/activation buffers, but dynamic
    activation quant still returns fresh tensors. Add an exact out-variant for
    per-token INT8 quantization, then evaluate fusing remap+quant1 and
    activation+quant2. The previously rejected fused SiLU+quant candidate failed
    arithmetic quality, so this must be rebuilt with strict equivalence tests
    before any endpoint run.

13. **Per-layer hot-expert duplicate-and-route experiment.**
    Use routecapture histograms to identify layers where a few experts dominate
    c1 decode. If VRAM allows, duplicate only those hot expert shards or their
    tile-native packed forms across ranks to reduce traffic or imbalance while
    preserving exact weights. Simulate first; implement only if the bytes and
    route windows predict a real latency win.

14. **Minimal exact decode engine outside vLLM.**
    Build a tiny single-request executable for one fixed prompt/output bucket
    that loads the same Quark W8A8 weights, runs the same tokenizer/model math,
    and bypasses vLLM scheduling entirely. This is not a replacement server; it
    is a truth-serum benchmark that tells us whether vLLM control flow is the
    c1 bottleneck or the kernels are.

15. **Two-lane production architecture with exact routing.**
    Keep the stable TP4/32K vLLM service as the general lane, but create a
    latency lane for common c1 chat shapes: fixed buckets, fixed sampling,
    certified graph cache, preallocated state, and stricter admission control.
    Route requests by context/output shape. This can improve user-perceived
    speed without weakening model quality or long-context capacity.

16. **Speculative proposer bakeoff with target-verified rollback.**
    Expand beyond n-gram by testing MTP, target-trace proposer, simple prefix
    trie, and small exact-model-trained proposer, all behind the same
    resident-state verifier. The only promoted metric is accepted target tokens
    per second with exact sentinel parity; raw draft speed does not count.

17. **Upstream branch archaeology and kernel transplant lane.**
    Track Intel `llm-scaler-vllm`, `vllm-xpu-kernels`, Triton-XPU, and oneDNN
    GenAI branches for B70/MoE/W8A8 changes. When a promising kernel appears,
    extract just the route-replay fixture and compare it against our accepted
    artifacts before considering a stack upgrade.

## Promotion Rules

- A speed candidate must pass the accepted provenance guard and the exact
  sentinel positions before it is compared to the public baseline.
- A kernel candidate must prove numeric equivalence against the current
  `xpu_fused_moe` or full endpoint output on captured real routes.
- A speculation candidate must use the current Quark W8A8 model as verifier and
  produce a transaction log with accept/reject/rollback evidence.
- A public benchmark should include command, context length, output length,
  TTFT, c1 decode speed, cache-root provenance, and exact quality artifact.

## 2026-06-12 Follow-up

- Added the route-replay diagnostic fields for the real
  `xpu_fused_moe(..., scratch=...)` hook to
  `scripts/bench-qwen36-int8-moe-kernels.py`.
- Validation run:
  `/home/steve/.venvs/vllm-xpu/bin/python -m py_compile scripts/bench-qwen36-int8-moe-kernels.py`
  passed.
- Import/CLI validation:
  `/home/steve/.venvs/vllm-xpu/bin/python scripts/bench-qwen36-int8-moe-kernels.py --help`
  passed.
- The live accepted TP4 backend was left running. A one-shot `xpu-smi` memory
  check showed roughly `32651 MiB` used on each B70, so the route-replay XPU
  microbench should wait for a clean benchmark window.

## 2026-06-12 Live Decode Budget

Artifact:
`data/qwen36-quark-int8-tp4-live-c1-p512o512-metrics-hist-20260612q.json`.

Command shape:

```bash
/home/steve/.venvs/vllm-xpu/bin/python scripts/measure-openai-endpoint-metrics.py \
  --base-url http://127.0.0.1:18080 \
  --tokenizer /mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118 \
  --prompt-tokens 512 --output-tokens 512 \
  --prompt-kind vllm-random --seed 20260612 \
  --repeats 3 --warmup-output-tokens 32 \
  --endpoint completions --mode stream --ignore-eos --skip-vram
```

Observed direct-backend c1 p512/o512 budget:

- Corrected output throughput after first text chunk: `99.875 tok/s` mean.
- End-to-end output throughput: `98.613 tok/s` mean.
- vLLM TTFT: `74.163 ms` mean.
- vLLM prefill histogram: `69.128 ms` mean.
- vLLM decode histogram: `5116.930 ms` mean for 512 generated tokens.
- vLLM decode per generated token: `9.994 ms/token` mean.
- vLLM inter-token histogram: `10.014 ms/token` mean.
- vLLM queue time: `0.0069 ms` mean.
- vLLM iteration-tokens histogram: `2.0` tokens/step as reported.

Implication:

- The `>200 tok/s` target requires roughly `<=5 ms/token` decode. Queue,
  frontdoor, and normal prefill are too small to be the decisive bottleneck for
  this c1 shape. The next speed work must cut the steady decode path itself:
  MoE/linear-attention kernels, collectives, graph fences, scheduler metadata,
  or exact target-verified speculation.

Next controlled timing profile recipe:

```bash
tmux new -s qwen36-tp4-decode-timing-$(date +%Y%m%d%H%M%S) -- \
  env \
    VLLM_XPU_DECODE_TIMING_ALLOW=1 \
    VLLM_XPU_DECODE_TIMING=1 \
    VLLM_XPU_DECODE_TIMING_SYNC=1 \
    VLLM_XPU_DECODE_TIMING_RANK=0 \
    VLLM_XPU_DECODE_TIMING_STEP_SUMMARY=1 \
    VLLM_XPU_DECODE_TIMING_STEP_EVERY=32 \
    VLLM_XPU_DECODE_TIMING_STEP_SKIP_FIRST=64 \
    LOG_PATH=/tmp/qwen36-tp4-decode-timing.log \
    scripts/launch-qwen36-quark-int8-accepted.sh

/home/steve/.venvs/vllm-xpu/bin/python scripts/measure-openai-endpoint-metrics.py \
  --base-url http://127.0.0.1:18080 \
  --tokenizer /mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118 \
  --prompt-tokens 512 --output-tokens 512 \
  --prompt-kind vllm-random --seed 20260612 \
  --repeats 2 --warmup-output-tokens 32 \
  --endpoint completions --mode stream --ignore-eos --skip-vram \
  --out data/qwen36-quark-int8-tp4-decode-timing-profile-metrics.json

/home/steve/.venvs/vllm-xpu/bin/python scripts/summarize-xpu-decode-timing-log.py \
  --log /tmp/qwen36-tp4-decode-timing.log \
  --out data/qwen36-quark-int8-tp4-decode-timing-profile-summary.json \
  --all-lines
```

`VLLM_XPU_DECODE_TIMING_SYNC=1` intentionally distorts throughput, so this is
for attribution only. It should run in a clean benchmark window, not against the
live accepted service.

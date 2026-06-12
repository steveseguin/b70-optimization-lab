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

Safer next controlled timing profile recipe:

```bash
tmux new -s qwen36-tp4-decode-timing-$(date +%Y%m%d%H%M%S) -- \
  env \
    VLLM_XPU_DECODE_TIMING_ALLOW=1 \
    VLLM_XPU_DECODE_TIMING=1 \
    VLLM_XPU_DECODE_TIMING_SYNC=0 \
    VLLM_XPU_DECODE_TIMING_RANK=0 \
    VLLM_XPU_DECODE_TIMING_LABEL_REGEX='^(xpu_moe[.]|moe_forward_shared[.]custom_op|all_reduce:|gpu_model_runner[.]model_forward|gdn_attention_core_xpu[.]native|logits[.])' \
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

This no-sync version is the default next run. If a synchronized profile is
needed, add a label/category filter first and synchronize only a narrow MoE or
allreduce subset in a clean benchmark window, not against the live accepted
service.

## 2026-06-12 Sync Timing Result And Added Bets

Artifacts:

- Timing log:
  `data/qwen36-quark-int8-tp4-decode-timing-sync-devicelost-20260612r.log`.
- Parsed timing summary:
  `data/qwen36-quark-int8-tp4-decode-timing-sync-devicelost-summary-20260612r.json`.
- Restored accepted-backend log:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-timing-devicelost-20260612s.log`.
- Restored provenance guard:
  `data/qwen36-quark-int8-tp4-accepted-provenance-guard-after-timing-devicelost-20260612s.json`.
- Restored p512/o128 speed sanity:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-timing-devicelost-speed-p512o128-20260612s.json`.

Result:

- The synchronized timing backend crashed during warmup/main measurement with
  Level Zero `UR_RESULT_ERROR_DEVICE_LOST`, first in
  `block_table.copy_to_gpu(num_reqs)`, then with
  `UR_RESULT_ERROR_OUT_OF_RESOURCES` at `num_accepted_tokens.gpu.fill_(1)`.
- The timing hook still emitted a useful partial rank0 summary before shutdown.
  Treat absolute timings as distorted by explicit synchronization, but use the
  ranking as a directional decode-attribution signal.
- Top timing buckets:
  - `moe_forward_shared.custom_op`: `1248` calls, `4837.535 ms` total,
    `3.876 ms` average.
  - `xpu_moe.gemm2_w8a8`: `1248` calls, `1672.690 ms` total,
    `1.340 ms` average.
  - `xpu_moe.gemm1_w8a8`: `1248` calls, `1476.398 ms` total,
    `1.183 ms` average.
  - Largest dense allreduce bucket:
    `all_reduce:(8192, 2048):torch.bfloat16`, `49` calls,
    `122.319 ms` total, `2.496 ms` average.
- Directional takeaway: the W8A8 MoE custom-op and GEMM path dominates this
  profile. Allreduce still matters, but it is secondary in this partial timing
  capture. Queue, frontdoor, and normal prefill were already ruled out by the
  live histogram run.
- The normal accepted backend was restored afterward. Provenance guard passed
  the exact sentinel positions and the restored p512/o128 sanity run measured
  `100.234 tok/s` corrected after first text chunk, `95.391 tok/s` e2e output,
  and `9.901 ms/token` decode histogram. The quality/speed baseline is intact.

Immediate follow-ups:

1. **Replace global sync timing with safer selective profiling.**
   Do not run broad `VLLM_XPU_DECODE_TIMING_SYNC=1` as a default diagnostic
   again. Add a label-regex or category filter so only `xpu_moe.*` and selected
   allreduce labels synchronize, and start with no-sync counters plus periodic
   summaries before enabling any synchronized timing.

2. **Make metadata-copy stability part of every timing run.**
   The crash site was in scheduler/model-runner metadata movement, not inside
   the MoE timing bucket itself. Any future timing branch should record block
   table shape, `num_reqs`, `num_computed_tokens`, candidate-count buffers, and
   whether a host/device copy or fill was the first failing operation.

3. **Move the next speed bet down into W8A8 MoE, not launch flags.**
   The profile points at `gemm1_w8a8`, `gemm2_w8a8`, quant/remap/gather, and
   custom-op wrapper overhead. The next productive branch is a route-exact
   MoE layerlet or lower-level kernel change, not another service flag sweep.

4. **Keep a fast restore loop around risky profiling.**
   Before any synchronized timing, collect current tmux name, launch log,
   graph-cache fragment, and XPU process state. After any device-lost event,
   restore the accepted backend, run provenance guard, then run a short
   p512/o128 speed sanity before continuing.

Additional bigger, bolder ideas:

1. **Selective event-timing ring buffer inside hot kernels.**
   Instead of synchronizing Python labels, add a tiny device-side or low-level
   event recorder around the W8A8 MoE substeps. Dump one compact timeline per
   token after the run. This should reduce timing-induced device loss while
   still exposing launch gaps and kernel overlap.

2. **MoE flight recorder for one decode token.**
   For a single accepted token, capture route IDs, active experts, expert token
   counts, packed shapes, GEMM tile shapes, DPAS/XMX counters, command count,
   and gather/quant buffers. The goal is one file that explains why the token
   costs about `10 ms`, not only which high-level label is slow.

3. **Persistent expert-worker prototype with exact Quark math.**
   Build a small SYCL or Triton-XPU kernel that keeps expert workers resident
   across the two MoE GEMMs and dynamic quant steps for one layer. It must match
   `xpu_fused_moe` on captured routes before endpoint testing. If it cannot
   beat the current route replay fixture by a large margin, it will not close
   the `>200 tok/s` gap.

4. **Expert-parallel shadow simulator using real route windows.**
   Simulate EP4, TP2+EP2, hot-expert replication, and replicated-attention plus
   sharded-expert layouts from routecapture artifacts. Compute bytes moved,
   expected all-to-all/allreduce operations, per-rank hot spots, and VRAM. This
   is the cheapest way to decide if a more radical parallelism change is worth
   implementing.

5. **Graph-safe GPU-resident scheduler metadata.**
   Prototype moving block-table tails, accepted-token counters, and other tiny
   per-step metadata updates onto the device or into graph-stable buffers. This
   targets both latency and the recurring device-lost class around metadata
   copies/fills.

6. **Offline kernel replay binary.**
   Generate a standalone replay executable from captured one-token inputs:
   attention input, MoE routes, expert weights/scales, and collectives mocked or
   isolated. This separates vLLM scheduler noise from kernel reality and makes
   upstream Intel/vLLM conversations much sharper.

7. **Layer-specific tile-native W8A8 repack plus autotune cache.**
   Repack expert tensors into the exact layout needed by the fastest B70 kernel
   per layer, record checksums, and autotune only from real route windows. A
   layer-specific cache is more work than a global layout, but the route scans
   already showed global hot-expert assumptions are unreliable.

8. **Certified static c1 lane as a production sidecar.**
   Keep general vLLM for capacity and long contexts, but prototype a fixed
   p512/p2k decode sidecar with preallocated metadata, certified graph cache,
   fixed sampling, and strict admission control. This is a pragmatic way to get
   user-facing latency down while the general server remains reliable.

9. **Quality-first BF16 differential harness.**
   Continue using Quark W8A8 as the production target, but keep a BF16 fallback
   harness for periodic semantic/logit-rank checks on a small suite. This is
   not a speed candidate; it is an early warning system for kernel changes that
   pass token sentinels but distort nearby probabilities.

10. **Hardware/driver stress lane for profile safety.**
    The timing crash reinforces that B70 performance work needs a separate
    reliability lane. Sweep only host stack, firmware, oneCCL, and runtime
    versions with the accepted command and a fixed quality/speed smoke. Promote
    no kernel change from a stack that increases device-lost rate.

## 2026-06-12 Selective Timing Controls And Safer Profiles

Patch:

- `patches/vllm-qwen36-selective-xpu-decode-timing-20260612.patch`.
- Live source updated:
  `/home/steve/src/vllm/vllm/utils/xpu_decode_timing.py`.
- Accepted launch guard updated:
  `scripts/launch-qwen36-quark-int8-accepted.sh`.

New profiling environment controls:

- `VLLM_XPU_DECODE_TIMING_LABEL_REGEX`: record only labels matching this regex.
- `VLLM_XPU_DECODE_TIMING_EXCLUDE_LABEL_REGEX`: drop labels matching this regex.
- `VLLM_XPU_DECODE_TIMING_SYNC_LABEL_REGEX`: when sync timing is enabled,
  synchronize only matching labels.
- `VLLM_XPU_DECODE_TIMING_SYNC_EXCLUDE_LABEL_REGEX`: exclude matching labels
  from sync timing.
- The accepted launch script strips all four unless
  `VLLM_XPU_DECODE_TIMING_ALLOW=1`, so normal service stays timing-free.

Validation:

- `bash -n scripts/launch-qwen36-quark-int8-accepted.sh` passed.
- `/home/steve/.venvs/vllm-xpu/bin/python -m py_compile
  /home/steve/src/vllm/vllm/utils/xpu_decode_timing.py` passed.
- A small import/filter exercise recorded only `xpu_moe.*` when
  `VLLM_XPU_DECODE_TIMING_LABEL_REGEX='^xpu_moe[.]'`.

No-sync label timing profile:

- Session: `qwen36-tp4-nosync-labeltiming-20260612t`.
- Artifacts:
  - `data/qwen36-quark-int8-tp4-nosync-labeltiming-20260612t.log`.
  - `data/qwen36-quark-int8-tp4-nosync-labeltiming-summary-20260612t.json`.
  - `data/qwen36-quark-int8-tp4-nosync-labeltiming-p512o128-20260612t.json`.
- p512/o128 corrected after-first speed: `100.669 tok/s`.
- p512/o128 e2e output speed: `95.384 tok/s`.
- vLLM decode histogram: `9.863 ms/token`.
- Process summary emitted `28` timing labels and step summary emitted `8`
  decode steps without device loss.
- Active decode-step bucket, no sync:
  - `gpu_model_runner.model_forward`: `5.461 ms/step` mean.
  - `gdn_attention_core_xpu.native`: `1.505 ms/step` mean.
  - `logits.local_argmax_lm_head`: `0.067 ms/step` mean.
  - visible timed total: `7.033 ms/step` mean.
- Interpretation: no-sync timing is safe and useful for call counts and
  host/graph-enqueue visibility, but it is not a real kernel-time profile.
  MoE substep labels appear in the process summary but not in active decode-step
  summaries under accepted graph replay, so no-sync cannot directly rank live
  MoE replay kernels.

Model-forward-only synchronized timing profile:

- Session: `qwen36-tp4-sync-modelonly-20260612u`.
- Artifacts:
  - `data/qwen36-quark-int8-tp4-sync-modelonly-20260612u.log`.
  - `data/qwen36-quark-int8-tp4-sync-modelonly-summary-20260612u.json`.
  - `data/qwen36-quark-int8-tp4-sync-modelonly-p512o64-20260612u.json`.
- Sync was limited to exactly `gpu_model_runner.model_forward`:
  `VLLM_XPU_DECODE_TIMING_LABEL_REGEX='^gpu_model_runner[.]model_forward$'`
  and
  `VLLM_XPU_DECODE_TIMING_SYNC_LABEL_REGEX='^gpu_model_runner[.]model_forward$'`.
- p512/o64 corrected after-first speed under this profiling overhead:
  `96.957 tok/s`.
- vLLM decode histogram under profiling overhead: `10.162 ms/token`.
- Steady active decode-step model-forward timing:
  - mean `8.438 ms/token`.
  - median `8.433 ms/token`.
  - p90 `8.463 ms/token`.
- Process-wide model-forward summary averaged `9.421 ms` over `64` counted
  calls, with a large `71.216 ms` max from non-steady startup/prefill/capture
  work. Use the steady decode-step bucket for c1 decode budgeting.

Restored accepted backend:

- Session: `qwen36-tp4-accepted-restored-after-selective-timing-20260612v`.
- Artifacts:
  - `data/qwen36-quark-int8-tp4-accepted-restored-after-selective-timing-20260612v.log`.
  - `data/qwen36-quark-int8-tp4-accepted-provenance-guard-after-selective-timing-20260612v.json`.
  - `data/qwen36-quark-int8-tp4-accepted-restored-after-selective-timing-speed-p512o128-20260612v.json`.
- Provenance guard passed all exact sentinels after restore.
- Restored p512/o128 corrected after-first speed: `100.196 tok/s`.
- Restored p512/o128 e2e output speed: `95.184 tok/s`.
- Restored decode histogram: `9.906 ms/token`.

New budget:

- The useful c1 decode budget is now approximately:
  - `8.44 ms/token` inside accepted graph model forward.
  - `~1.5 ms/token` outside or around graph forward, including scheduler,
    sampling/logits, stream timing, and measurement-visible overhead.
- The `>200 tok/s` goal needs `<=5 ms/token` overall. A pure outside-graph
  cleanup cannot get there; the model-forward graph must drop to about
  `4.5 ms/token`, or exact target-verified speculation must amortize multiple
  accepted tokens per target forward.

Next best technical target:

1. Build a graph-aware MoE flight recorder or offline replay fixture, because
   active decode graph replay hides Python MoE substep timers.
2. Use the replay fixture to attack the W8A8 MoE path: persistent expert worker,
   tile-native W8A8 repack, out-variant quant buffers, and exact route-window
   scheduling.
3. Keep model-forward-only sync as the safe live regression gate for future
   kernel changes; avoid global sync profiles unless a label filter is active.

## 2026-06-12 CPU MoE Flight Recorder

Script:

- `scripts/qwen36-moe-flight-recorder.py`.

Purpose:

- Convert real route-capture JSONL into layer/window flight records without
  requiring GPUs or interrupting the accepted backend.
- Rank layers by hot-expert coverage, window active expert counts, repeated
  top-k tuple share, and route-window shape. This is the input needed before
  writing persistent MoE kernels, hot-expert replication, tile-native W8A8
  repack caches, or EP/TP simulations.

Routecapture5 exact-ID run:

```bash
python3 scripts/qwen36-moe-flight-recorder.py \
  data/qwen36-quark-int8-tp4-routecapture5-routes-rank0-20260611.jsonl \
  --out data/qwen36-quark-int8-tp4-routecapture5-flight-record-20260612w.json \
  --markdown-out data/qwen36-quark-int8-tp4-routecapture5-flight-record-20260612w.md \
  --require-topk-ids \
  --window-size 16 \
  --hot-sizes 8,16,32,64 \
  --topn 16
```

Artifacts:

- `data/qwen36-quark-int8-tp4-routecapture5-flight-record-20260612w.json`.
- `data/qwen36-quark-int8-tp4-routecapture5-flight-record-20260612w.md`.

Findings from the limited layer-8/layer-20 capture:

- `254` records, `2` layers, `127` decode records per layer.
- Layer `8`: `117` aggregate active experts; top-16 experts cover `54.8%`
  of assignments; top-32 cover `75.5%`; p50 window active experts is `44`.
- Layer `20`: `125` aggregate active experts; top-16 experts cover `53.4%`
  of assignments; top-32 cover `72.9%`; p50 window active experts is `46`.
- p50 top-k tuple share is only `6.25%`, so whole-tuple replay is not the main
  opportunity. Expert-set locality is the opportunity.

Implication:

- A blind global hot-expert remap is still rejected by earlier replay data, but
  layer/window-specific tile-native packing or hot expert replication has enough
  route locality to justify a deeper fixture. For these two layers, a top-32
  hot set captures roughly three quarters of assignments while touching only
  `12.5%` of the experts.
- The next route capture should cover the highest-priority layers `9`, `14`,
  `21`, and all prompt classes, then feed the same flight recorder before any
  persistent-kernel or EP/TP implementation work.

## 2026-06-12 Broader Flight Records And Hotset Planning

New script:

- `scripts/qwen36-moe-hotset-plan.py`.

Purpose:

- Estimate the memory cost and route coverage of exact hot-expert repack or
  replication plans from CPU-only flight records.
- Keep the plan exact: hot experts can use a faster tile-native or persistent
  path, but cold experts must fall back to the same Quark W8A8 math, so this is
  a performance layout change rather than a model-quality change.

New artifacts:

- `data/qwen36-quark-int8-tp4-routecapture6-flight-record-20260612x.json`.
- `data/qwen36-quark-int8-tp4-routecapture6-flight-record-20260612x.md`.
- `data/qwen36-quark-int8-tp4-promptclass-flight-record-20260612x.json`.
- `data/qwen36-quark-int8-tp4-promptclass-flight-record-20260612x.md`.
- `data/qwen36-quark-int8-tp4-routecapture6-hotset-plan-20260612x.json`.
- `data/qwen36-quark-int8-tp4-routecapture6-hotset-plan-20260612x.md`.
- `data/qwen36-quark-int8-tp4-promptclass-hotset-plan-20260612x.json`.
- `data/qwen36-quark-int8-tp4-promptclass-hotset-plan-20260612x.md`.

Routecapture6 exact-ID findings:

- `285` records across layers `9`, `14`, and `21`.
- Layer `9`: top-16 coverage `51.1%`, top-32 `72.2%`, top-64 `91.6%`,
  p50 window active experts `47.0`.
- Layer `21`: top-16 `48.9%`, top-32 `68.3%`, top-64 `86.4%`,
  p50 window active experts `48.5`.
- Layer `14`: top-16 `42.1%`, top-32 `64.5%`, top-64 `87.4%`,
  p50 window active experts `50.0`.
- p50 repeated top-k tuple share is still only `6.25%`, so full-route
  memoization is not the main path. Expert-set locality is the path.

Prompt-class findings:

- `2600` records across layers `8`, `9`, `14`, `20`, and `21`.
- These prompt-class JSONLs have count vectors but no exact `topk_ids`, so
  tuple-share metrics are unavailable.
- Top-32 coverage ranges from `57.8%` to `62.8%`; top-64 ranges from `78.6%`
  to `83.0%`.
- Prompt-class p50 window active experts is lower than routecapture6:
  `22` to `24` experts, which is favorable for persistent workers and
  hotset-local scheduling.

Hotset memory model from the current model config:

- `hidden_size=2048`, `moe_intermediate_size=512`, `num_hidden_layers=40`,
  `num_experts=256`, `tp_size=4`.
- Per local TP-shard expert, including current fp32 scales: `795648` bytes,
  or about `0.759 MiB`.
- One layer top-32 hotset costs about `24.3 MiB/rank`.
- All-layer local-rank estimates:
  - top-16: `485.6 MiB/rank`.
  - top-32: `971.2 MiB/rank`.
  - top-64: `1942.5 MiB/rank`.

Implication:

- A top-32 or top-64 hotset cache is cheap enough to prototype without
  threatening the 32 GiB B70 memory budget. This makes a tile-native W8A8
  repack cache or persistent hot-expert layerlet a serious next target.
- Do not implement another global expert physical remap. Earlier replay showed
  layer/window-specific wins and losses. The better exact design is a hotset
  fast path with cold-expert fallback, gated by layer and route-window evidence.
- Start with layers `9` and `20`. Layer `9` has the best exact-ID coverage in
  routecapture6, while layer `20` remains strong in prompt-class and earlier
  exact-ID captures.
- Keep the model-forward-only synchronized timing profile as the live regression
  gate. Any kernel patch must reduce the `8.44 ms/token` model-forward bucket,
  not only improve an isolated microbench.

External signals checked:

- The current Localmaxxing Arc Pro B70 Qwen snapshot has the accepted
  Qwen3.6 Quark W8A8 INT8 4x B70 run at the top of the public filtered result
  set, with `99.77 tok/s` and 32K context:
  <https://localmaxxing.com/api/leaderboard?hardwareName=Arc%20Pro%20B70&modelFamily=qwen&limit=20>.
- `vllm-xpu-kernels` is the right upstream surface for this work because it
  already exposes XPU MoE, expert remapping, FP8 quantization/GEMM, and grouped
  GEMM kernels:
  <https://github.com/vllm-project/vllm-xpu-kernels>.
- The vLLM XPU migration RFC records the move from IPEX to the dedicated
  `vllm-xpu-kernels` library and notes W8A16/W8A8 FP8 support work:
  <https://github.com/vllm-project/vllm/issues/33214>.
- Intel's newer XPU container notes claim persistent MoE GEMM plus fused
  activation gave Qwen3-30B-A3B a `2.6x` end-to-end improvement:
  <https://github.com/intel/ai-containers/blob/main/vllm/0.10.2-xpu.md>.
- The vLLM Arc Pro B-Series blog explains why persistent MoE matters: it
  removes per-iteration launch/scheduling gaps and keeps work resident despite
  routing dependencies:
  <https://vllm.ai/blog/2025-11-11-intel-arc-pro-b>.
- Public B70 benchmarking outside this repo shows Qwen3.6-35B-A3B MoE is a
  good B70 shape even when run through different engines and quants:
  <https://github.com/PMZFX/intel-arc-pro-b70-benchmarks>.

## Bigger Bolder Ideas After Hotset Planning

1. **Exact hotset persistent MoE layerlets.**
   Build one layer-specific persistent kernel for a top-32 or top-64 hotset.
   It should keep expert workers resident across gate, gather, W8A8 GEMM1,
   fused activation, dynamic quant, W8A8 GEMM2, scatter, and local reduction.
   Cold experts stay on the current exact path. This is the most direct way to
   test whether Intel's reported persistent-MoE class of wins can transfer to
   this exact Quark W8A8 model.

2. **Tile-native W8A8 repack cache with checksum promotion.**
   At load time, duplicate selected hot experts into the exact tile layout
   needed by the fastest B70 grouped-GEMM kernel. Store per-expert checksums and
   a manifest so the cache is reproducible and quality-auditable. The memory
   estimate says all-layer top-64 is only about `1.9 GiB/rank`, so this is now
   practical.

3. **Hybrid replicated-attention plus expert-parallel simulation.**
   Simulate a layout where dense attention and router state are replicated but
   MoE experts are sharded or replicated by hotness. This may remove some TP4
   dense allreduce cost while replacing it with tiny MoE token exchange. Use
   route windows before coding because c1 all-to-all overhead can erase the win.

4. **TP1/TP2 exact latency lane capacity proof.**
   Re-test the same Quark W8A8 model at lower max context and tighter
   `max_num_seqs` on TP1 or TP2. If it fits, it could beat TP4 c1 latency by
   removing cross-card collectives. It would not replace the 32K production
   lane until capacity and quality are proven.

5. **Static single-request decode appliance.**
   Build a fixed-bucket c1 runner outside the full vLLM scheduler that reuses
   the same tokenizer, weights, graph cache, sampling, and quality canaries.
   If it is still near `100 tok/s`, kernels are the ceiling. If it is much
   faster, production should add a certified latency sidecar.

6. **Persistent-MoE transplant bakeoff from newer Intel stack.**
   Isolate the persistent MoE and fused activation pieces from the newest Intel
   XPU container or `vllm-xpu-kernels`, then run them in a tiny route-replay
   harness before touching the accepted server. This avoids a full host-stack
   migration while still testing the big upstream kernel idea.

7. **Target-verified MTP/DFlash sidecar with resident verifier state.**
   Keep speculation on the table, but only with the current Quark W8A8 model as
   the in-engine verifier. The parent-state traces show external refill
   verification is not equivalent enough. The bold version is a transactional
   verifier that can accept several tokens per model-forward without losing
   exact sentinel parity.

8. **Graph-resident metadata lane.**
   Move block-table tail updates, accepted-token counters, slot mappings, and
   small scheduler fills into graph-stable device buffers. This targets both
   the `~1.5 ms/token` outside-forward budget and the device-lost class seen
   around metadata copy/fill operations.

9. **BF16 differential plus route-replay numeric gate.**
   Expand quality validation beyond exact token sentinels by sampling BF16
   fallback logit-rank deltas and replaying captured MoE inputs through old and
   new kernels. This catches subtle kernel drift before a speed candidate ever
   reaches the public endpoint.

10. **Upstreamable performance packet.**
    Package one captured route window, minimal weights/scales slice,
    model-forward timing, and hotset-plan numbers into a tiny repro for Intel
    and vLLM maintainers. The current evidence is specific enough to ask for
    persistent W8A8 MoE support on this model rather than generic "XPU is slow"
    advice.

## 2026-06-12 Layer 9/20 Hotset Manifest

New script:

- `scripts/qwen36-moe-hotset-manifest.py`.

Purpose:

- Build layer-specific hotset manifests from raw route JSONL files, not the
  summarized flight records, so full expert count vectors remain available.
- Combine exact-ID captures with prompt-class captures using source-normalized
  expert scores. This prevents long prompt-class files from dominating shorter
  exact captures.
- Emit replay start indices and command lines for the existing route-replay
  harnesses, so kernel work can start from fixed, reproducible windows.

Artifacts:

- `data/qwen36-quark-int8-tp4-hotset-manifest-l9-l20-20260612y.json`.
- `data/qwen36-quark-int8-tp4-hotset-manifest-l9-l20-20260612y.md`.
- `data/qwen36-quark-int8-tp4-hotset-manifest-l9-route6-dryrun-20260612y.json`.
- `data/qwen36-quark-int8-tp4-hotset-manifest-l20-route5-dryrun-20260612y.json`.
- `data/qwen36-quark-int8-tp4-hotset-manifest-l9-pcmath-dryrun-20260612y.json`.
- `data/qwen36-quark-int8-tp4-hotset-manifest-l20-pcrepetitive-dryrun-20260612y.json`.

Layer results:

- Layer `9` uses six sources: routecapture6 exact plus prompt-class code,
  math, repetitive, structured, and long-natural captures.
  - Source-normalized top-32 mean coverage: `78.4%`.
  - Source-normalized top-32 minimum coverage: `52.0%`.
  - Source-normalized top-64 mean coverage: `88.7%`.
  - Source-normalized top-64 minimum coverage: `75.0%`.
  - Source top-32 union size: `69`; intersection size: `0`.
  - Recommendation: top-64 hotset. Top-32 is worth a memory-minimal subtest,
    but it fails the `0.60` worst-source coverage threshold.
- Layer `20` uses six sources: routecapture5 exact plus the same prompt-class
  sources.
  - Source-normalized top-32 mean coverage: `80.2%`.
  - Source-normalized top-32 minimum coverage: `56.9%`.
  - Source-normalized top-64 mean coverage: `91.0%`.
  - Source-normalized top-64 minimum coverage: `78.4%`.
  - Source top-32 union size: `62`; intersection size: `2`.
  - Recommendation: top-64 hotset. Top-32 is close, but still below the
    worst-source guardrail.

Replay windows validated without GPU execution:

- Layer `9` exact-ID routecapture6:
  - route starts: `0,1,2,46,78`.
  - dry-run records matched: `95`.
  - selected 16-token windows have `37`, `38`, `38`, `58`, and `45` active
    experts.
- Layer `20` exact-ID routecapture5:
  - route starts: `11,12,13,52,63`.
  - dry-run records matched: `127`.
  - selected 16-token windows have `44`, `42`, `42`, `48`, and `42` active
    experts.
- Layer `9` prompt-class math stress windows:
  - route starts: `5,22,52,58,85,211`.
  - selected windows have `56` to `61` active experts.
- Layer `20` prompt-class repetitive stress windows:
  - route starts: `6,33,96,101,159,222`.
  - selected windows have `47` to `61` active experts.

Concrete next implementation target:

1. Prototype a top-64 hotset fast path for layer `9` first, because it has the
   best exact-ID coverage and a wide stress range in replay windows.
2. Keep top-32 as a subtest to measure the speed-memory tradeoff, but do not
   assume it is production-safe unless prompt-class worst-source coverage
   improves or the cold fallback overhead is negligible.
3. Implement as a hotset fast path plus exact cold fallback, not a physical
   global remap. The source top-32 intersections are too small for a global
   hotset to be trustworthy.
4. Use these replay commands as the first gate:
   - `scripts/bench-qwen36-int8-moe-kernels.py` for exact topk rows from
     routecapture6/routecapture5.
   - `scripts/bench-qwen36-route-exact-w8a8-grouped-gemm.py --dry-run` and then
     real grouped-GEMM runs for count-vector prompt-class stress windows.
5. Promote no endpoint change unless the accepted model-forward synchronized
   bucket drops below the current `8.44 ms/token` baseline and exact provenance
   sentinels still pass.

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

## 2026-06-12 Hotset Split Replay Model

Updated script:

- `scripts/bench-qwen36-route-exact-w8a8-grouped-gemm.py`.

New support:

- `--hotset-experts`: supply a logical expert hotset for replay windows.
- `--hotset-cold-mode full|compact|both`: model cold fallback either as the
  original full expert table with hot rows zeroed, or as an upper-bound compact
  cold table containing only active cold experts.
- Dry-run output now reports hot rows, cold rows, hot coverage, hot active
  experts, cold active experts, and cold fallback expert count per selected
  route window.

Artifacts:

- `data/qwen36-quark-int8-tp4-hotset-split-l9-route6-dryrun-20260612z.json`.
- `data/qwen36-quark-int8-tp4-hotset-split-l9-pcmath-dryrun-20260612z.json`.
- `data/qwen36-quark-int8-tp4-hotset-split-l20-route5-dryrun-20260612z.json`.
- `data/qwen36-quark-int8-tp4-hotset-split-l20-pcrepetitive-dryrun-20260612z.json`.

Layer `9` top-64 split:

- Exact-ID routecapture6 windows:
  - hot coverage: `93.8%`, `93.8%`, `93.8%`, `75.0%`, `78.9%`.
  - hot rows out of 128: `120`, `120`, `120`, `96`, `101`.
  - cold rows: `8`, `8`, `8`, `32`, `27`.
  - cold active experts: `5`, `5`, `5`, `22`, `19`.
- Prompt-class math stress windows:
  - hot coverage: `69.5%`, `83.6%`, `77.3%`, `72.7%`, `83.6%`, `83.6%`.
  - cold rows: `39`, `21`, `29`, `35`, `21`, `21`.
  - cold active experts: `30`, `18`, `22`, `26`, `18`, `18`.

Layer `20` top-64 split:

- Exact-ID routecapture5 windows:
  - hot coverage: `85.9%`, `85.9%`, `85.9%`, `87.5%`, `82.0%`.
  - cold rows: `18`, `18`, `18`, `16`, `23`.
  - cold active experts: `16`, `16`, `16`, `11`, `13`.
- Prompt-class repetitive stress windows:
  - hot coverage: `62.5%`, `87.5%`, `87.5%`, `87.5%`, `87.5%`, `87.5%`.
  - cold rows: `48`, `16`, `16`, `16`, `16`, `16`.
  - cold active experts: `34`, `12`, `12`, `13`, `12`, `12`.

Implication:

- Top-64 hotsets are strong enough to justify a real fast-path prototype. They
  move most rows into a small, stable expert set on the exact-ID windows and on
  most prompt-class stress windows.
- The cold fallback is small on most windows, but not free. A naive two-launch
  hotset path can lose to launch overhead unless the hot path is materially
  faster or the cold path is fused/cheap.
- The next implementation should not be only "run grouped GEMM twice." Better
  targets:
  1. a persistent top-64 hotset layerlet with an in-kernel cold fallback queue,
  2. a tile-native hotset repack cache with cold rows sent through the existing
     exact path only when needed,
  3. or a benchmark-only two-launch hot/cold model to establish the minimum
     speedup required before writing the persistent kernel.
- Layer `9` remains first because the exact-ID hot coverage is excellent and
  the stress window range is broad enough to expose fallback overhead.

## 2026-06-12 Follow-Up Ideas Added After Hotset Split

Current constraint:

- The accepted endpoint currently occupies essentially all four B70 cards. Do
  CPU-safe modeling, dry runs, and source inspection while the endpoint is live.
  Real XPU grouped-GEMM or fused-MoE microbenchmarks need a deliberate
  maintenance window where the accepted backend is stopped, benchmarked, and
  restored with the provenance guard.

Immediate things to try next:

1. **Hotset split floor model without GPU allocation.**
   Extend the existing W8A8 kernel-floor or route-replay scripts to estimate
   hot rows, cold rows, active hot experts, active cold experts, and launch
   counts per layer/window. The goal is to answer whether top-64 needs a
   persistent/fused kernel to win, or whether a simpler two-launch benchmark is
   worth testing during a maintenance window.
2. **Layer `9` top-64 GPU microbench during a backend stop.**
   First test only the routecapture6 exact windows with tiny iteration counts,
   then add the math stress windows. Record full-table, hot+full-cold, and
   hot+compact-cold timings. If hot+full-cold is slower, stop spending time on
   two independent grouped GEMMs and move straight to persistent/fused work.
3. **Grouped-GEMM policy override sweep on exact route windows.**
   Inspect and exercise the local XPU grouped-GEMM policy override path against
   the captured layer `9` and `20` windows. The route distributions are now
   realistic enough that a policy sweep can be more informative than synthetic
   uniform expert-count tests.
4. **Top-64 tile-native repack cache.**
   Build a benchmark-only repacked hotset table where the 64 hot experts are
   physically adjacent and aligned for the current XPU tile shape. Cold experts
   remain exact and unchanged. This should reveal whether the main win is from
   better memory/layout locality or from eliminating launches.
5. **Quality gate before endpoint promotion.**
   Every candidate above must pass: exact token sentinels, route-replay numeric
   comparison against the current kernel, prompt-class canaries, and a BF16
   differential spot check. A speed-only MoE microbench is not enough.

Bigger, bolder ideas to keep on the board:

1. **One resident hotset layerlet per high-impact MoE layer.**
   Keep top-64 hot expert weights/scales resident in a layer-local persistent
   kernel, route hot rows in-kernel, and enqueue rare cold rows to the exact
   existing path. This attacks both launch overhead and small-M grouped-GEMM
   underutilization while preserving the same top-k experts and weights.
2. **Fuse hot expert gate/up/SwiGLU/down for the common case.**
   For hot rows only, test a fused exact-arithmetic layerlet that avoids
   materializing the intermediate activation between expert projections. The
   cold fallback remains the existing path. This is larger than a repack but
   could remove memory traffic and launches at the actual decode bottleneck.
3. **Adaptive per-request hotset cache.**
   Use the first few decode tokens or prompt-class route history to choose a
   per-layer hotset for the request, then run exact cold fallback for misses.
   The math is unchanged; only the hot table changes. The risk is scheduler and
   cache churn, so the first version should be offline replay only.
4. **Hybrid TP/EP for MoE layers only.**
   Keep dense/attention TP4, but route MoE experts with expert affinity across
   cards so hot experts are not always narrow TP shards. This is a bigger
   architecture change and may introduce all-to-all overhead, but it is one of
   the few no-quality-loss paths that could materially improve single-request
   MoE utilization on four GPUs.
5. **Static c1 latency lane separate from production aggregate lane.**
   Maintain a warmed, shape-bucketed, low-concurrency service for c1 latency
   experiments while a separate endpoint handles aggregate throughput. This
   would let command graphs, static memory pools, and hotset caches specialize
   aggressively without constraining the eventual production server.
6. **Device-resident scheduler metadata for decode.**
   The recurring stability/performance hazards around metadata copies suggest
   moving more decode-step metadata, block-table decisions, and top-k route
   state onto device-resident buffers. This is not a weight/model change, but
   it could reduce host fences and lower device-lost risk.
7. **Resident-state verifier speculation, not external refill verification.**
   External prompt-logprob/refill checks already diverged from accepted graph
   state. The quality-preserving speculation path is an in-engine copy-on-write
   fork of KV/GDN/request state where the Quark verifier accepts or rejects
   candidate tokens transactionally.
8. **Backend bakeoff with the exact same INT8 weights.**
   Keep `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` fixed, but compare the
   local vLLM/XPU path against Intel-native or Triton/oneDNN/SYCL prototype
   paths for just the captured MoE layerlets. This can expose whether the
   current limit is vLLM scheduling, the grouped-GEMM kernel, or B70 hardware
   utilization.
9. **Upstreamable hotset repro packet.**
   Package the layer `9` and `20` route windows, top-64 manifests, cold fallback
   counts, and a minimal grouped-GEMM benchmark into a standalone repro. This is
   the clearest way to ask Intel/vLLM maintainers for a persistent XPU W8A8 MoE
   kernel without requiring them to run the full 35B model.
10. **Reliability soak as part of speed validation.**
    Treat any `>100 tok/s` improvement as provisional until it survives a
    restart/restore cycle, provenance guard, repeated p512/o512 c1 run, and a
    short mixed prompt-class soak. The target is not just a fast single screen;
    it is a fast path that can become production.

## 2026-06-12 Hotset Split Floor Model

New script:

- `scripts/qwen36-hotset-split-floor-model.py`.

Purpose:

- Consume hotset split dry-run JSON without allocating GPU memory.
- Estimate hot coverage, cold fallback size, compact/full cold table-slot
  ratios, extra launch count, and body-speedup requirements under launch
  overhead scenarios.
- Keep the accepted endpoint live while narrowing the next maintenance-window
  GPU benchmark.

Artifacts:

- `data/qwen36-quark-int8-tp4-hotset-split-floor-model-20260612aa.json`.
- `data/qwen36-quark-int8-tp4-hotset-split-floor-model-20260612aa.md`.

Command:

```bash
python3 scripts/qwen36-hotset-split-floor-model.py \
  --dry-run-json data/qwen36-quark-int8-tp4-hotset-split-l9-route6-dryrun-20260612z.json \
  --dry-run-json data/qwen36-quark-int8-tp4-hotset-split-l9-pcmath-dryrun-20260612z.json \
  --dry-run-json data/qwen36-quark-int8-tp4-hotset-split-l20-route5-dryrun-20260612z.json \
  --dry-run-json data/qwen36-quark-int8-tp4-hotset-split-l20-pcrepetitive-dryrun-20260612z.json \
  --baseline-us 150,200,270 \
  --launch-overhead-us 5,10,20,40 \
  --primary-baseline-us 200 \
  --primary-launch-overhead-us 10 \
  --output-json data/qwen36-quark-int8-tp4-hotset-split-floor-model-20260612aa.json \
  --markdown-out data/qwen36-quark-int8-tp4-hotset-split-floor-model-20260612aa.md
```

Primary scenario:

- Full path normalized to a `200 us` selected MoE layer window.
- Launch overhead scenario: `10 us`.
- Two GEMM stages modeled per MoE layer window.
- Every selected window has a cold fallback, so a simple hot/cold split adds
  `2` launches per full MoE layer window.
- Under this scenario, the split body must be at least `1.11x` faster than the
  full body before the extra launch overhead breaks even.

Compact-cold results:

- Layer `9` routecapture6 exact windows:
  - hot coverage minimum/mean: `75.0%` / `87.0%`.
  - max cold rows: `32`.
  - max active cold experts: `22`.
  - compact table-slot ratio mean/max: `0.29x` / `0.34x`.
- Layer `9` math stress windows:
  - hot coverage minimum/mean: `69.5%` / `78.4%`.
  - max cold rows: `39`.
  - max active cold experts: `30`.
  - compact table-slot ratio mean/max: `0.34x` / `0.37x`.
- Layer `20` routecapture5 exact windows:
  - hot coverage minimum/mean: `82.0%` / `85.5%`.
  - max cold rows: `23`.
  - max active cold experts: `16`.
  - compact table-slot ratio mean/max: `0.31x` / `0.31x`.
- Layer `20` repetitive stress windows:
  - hot coverage minimum/mean: `62.5%` / `83.3%`.
  - max cold rows: `48`.
  - max active cold experts: `34`.
  - compact table-slot ratio mean/max: `0.31x` / `0.38x`.

Decision:

- Full-cold split is not worth a maintenance-window benchmark first. It is
  `1.25x` table slots versus the exact full path and still adds launches.
- Compact-cold split is worth one small maintenance-window microbench because
  it reduces table slots to roughly `0.29x` to `0.38x` of the full table on
  these windows.
- The production target remains persistent/fused hotset fallback, because a
  two-launch compact split still needs enough body speedup to overcome launch
  overhead and row math is unchanged.
- Layer `9` routecapture6 exact windows remain the first GPU test. Then add
  layer `9` math stress. Do not spend endpoint downtime on full-cold split
  unless compact-cold unexpectedly wins and the comparison needs a control.

## 2026-06-12 Layer 9 Hotset Split GPU Microbench

Summary artifact:
`data/qwen36-quark-int8-tp4-hotset-split-l9-route6-gpu-hotsetbench-20260612ac.md`.

Artifacts:

- GPU timing JSON:
  `data/qwen36-quark-int8-tp4-hotset-split-l9-route6-gpu-hotsetbench-20260612ac.json`.
- Run log:
  `data/qwen36-quark-int8-tp4-hotset-split-l9-route6-gpu-hotsetbench-20260612ac.log`.
- XPU state snapshots:
  `data/qwen36-quark-int8-tp4-hotset-split-l9-route6-gpu-hotsetbench-20260612ac-pre-xpusmi-ps.txt`,
  `data/qwen36-quark-int8-tp4-hotset-split-l9-route6-gpu-hotsetbench-20260612ac-poststop-xpusmi-ps.txt`,
  and
  `data/qwen36-quark-int8-tp4-hotset-split-l9-route6-gpu-hotsetbench-20260612ac-postrestore-xpusmi-ps.txt`.
- Restored accepted-backend provenance:
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-hotsetbench-20260612ac.json`.
- Restored speed sanity:
  `data/qwen36-quark-int8-tp4-post-hotsetbench-sanity-repetitive-p512o256-20260612ac.json`.

Result:

- The top-64 layer `9` compact hot/cold split was exact but slower on XPU.
- Exact grouped-GEMM mean total: `213.852 us`.
- Compact hot/cold split mean total: `407.192 us`.
- Mean split/exact ratio: `1.928x` slower.
- The split was slower even on high-coverage windows:
  `1.525x`, `1.990x`, and `2.420x` slower at `93.75%` hot coverage.
- The accepted endpoint restored cleanly after the maintenance window:
  provenance guard passed exact sentinels and the repetitive p512/o256 sanity
  measured `99.157 tok/s` corrected after first text chunk with
  `10.047 ms/generated token` vLLM decode time.

Decision:

- Reject simple two-launch compact hot/cold split as a speed path.
- Do not spend more endpoint downtime on full-cold split, prompt-class
  two-launch split, or "try a different top-N" split variants unless a kernel
  change first removes most hot/cold launch overhead.
- Keep the hotset idea, but only in one-launch or persistent forms:
  in-kernel cold queue, tile-native repack inside the existing grouped-GEMM
  launch, or a persistent layerlet that does hot and fallback work without a
  second Python/dispatcher launch.
- The floor model was useful because it made the maintenance window narrow.
  The GPU result now replaces the floor-model decision: compact split was worth
  exactly one screen, and the screen says no.

Additional things to try from this result:

1. **One-launch hotset fallback kernel.**
   Keep hot and cold experts in one dispatch. The hot path can use a packed
   top-N table, while the cold path pulls exact fallback work from an in-kernel
   queue. This preserves exactness and attacks the launch overhead that killed
   the compact split.

2. **Grouped-GEMM small-shape policy screen.**
   Route replay shows compact fallback shapes such as `64+5`, `64+19`, and
   `64+22`. Build a policy benchmark that chooses between current grouped GEMM,
   direct per-expert GEMM, batched tiny GEMM, and persistent grouped GEMM for
   these shapes. The current kernel path is not optimized for the split sizes.

3. **Tile-native hotset repack used without splitting launches.**
   Repack hot experts into the best B70 tile layout, but feed the existing
   logical route through one kernel path. The fallback remains exact original
   weights. This tests whether layout helps without paying the split launch tax.

4. **Layer-local persistent MoE worker.**
   Prototype one layer that holds route metadata, expert tiles, intermediate
   activation, and quant buffers resident for both MoE GEMMs. This is the
   cleanest non-speculative route to halving the `~10 ms/token` decode budget.

5. **Route-conditioned EP/TP hybrid simulator.**
   Use the same route windows to simulate hot-expert replication, EP4, TP2+EP2,
   and replicated-attention/sharded-expert layouts. If the simulator cannot beat
   TP4 on bytes and imbalance, do not implement a new parallelism scheme.

6. **Decode command-buffer compaction.**
   Count every kernel launch and barrier for one token, then prototype a
   command-graph or persistent-loop lane that keeps the decode step on-device
   across MoE, GDN/linear attention, logits, and sampling metadata updates.

7. **Single-card hot-lane experiment as a control.**
   If TP4 communication or rank imbalance is hiding the best c1 path, run a
   memory-feasible single-card or two-card static lane for short contexts using
   the same exact model and quality sentinels. It may lose capacity but reveal
   whether multi-card TP is the latency wall.

8. **BF16 differential micro-suite for kernel changes.**
   Keep Quark W8A8 as the production target, but periodically compare sentinel
   prompts, route windows, and nearby logit ranks to BF16. This catches
   numerically suspicious "exact enough" kernel changes before they reach the
   live endpoint.

9. **Speculation only with resident target verification.**
   External refill/logprob sidecars already diverged from continuous accepted
   decode, so do not chase sidecar speculation. The bold path is in-engine
   copy-on-write KV/GDN/request state with target-model commit/rollback.

10. **Upstream perf repro packet.**
    Package the hotset negative, route windows, exact sentinel guard, and
    grouped-GEMM shapes into a small Intel/vLLM repro. A negative result with
    real routes is useful: it points maintainers toward persistent/grouped-GEMM
    policy work instead of more split-launch experiments.

## 2026-06-12 Route-Conditioned Parallelism Simulation

New script:

- `scripts/qwen36-route-parallelism-sim.py`.

Artifacts:

- Focused routecapture6 simulation:
  `data/qwen36-quark-int8-tp4-routecapture6-parallelism-sim-20260612ad.json`
  and
  `data/qwen36-quark-int8-tp4-routecapture6-parallelism-sim-20260612ad.md`.
- Prompt-class 16-record window simulation:
  `data/qwen36-quark-int8-tp4-promptclass-parallelism-sim-20260612ad.json`
  and
  `data/qwen36-quark-int8-tp4-promptclass-parallelism-sim-20260612ad.md`.
- Prompt-class 8-record window simulation, added so short code/structured
  traces are represented:
  `data/qwen36-quark-int8-tp4-promptclass-parallelism-sim-w8-20260612ad.json`
  and
  `data/qwen36-quark-int8-tp4-promptclass-parallelism-sim-w8-20260612ad.md`.

What the simulator measures:

- `compute_pressure_vs_tp4`: route-load pressure normalized so `1.0` means
  balanced row-work equal to the current TP4 proxy.
- `communication_row_fraction_proxy`: routed row fraction that still needs
  expert-parallel movement. Plain EP/TP-EP policies are `1.0`; hot replication
  reduces it by localizing hot rows.
- `expert_memory_relative_to_tp4`: per-rank expert-weight memory lower bound
  relative to current TP4. Dense weights and KV are intentionally excluded.

Result:

- Focused routecapture6, 15 windows:
  - `ep4_greedy_static`: mean pressure `1.238`, p95 `1.456`, comm proxy `1.000`.
  - `tp2_ep2_greedy_static`: mean pressure `1.079`, p95 `1.177`, comm proxy `1.000`.
  - `ep4_hot32_replicated_greedy`: mean pressure `1.002`, p95 `1.009`,
    comm proxy `0.311`, memory lower bound `1.375x`.
  - `ep4_hot64_replicated_greedy`: mean pressure `1.000`, p95 `1.000`,
    comm proxy `0.118`, memory lower bound `1.750x`.
- Prompt-class 16-record windows, 150 windows:
  - `ep4_greedy_static`: mean pressure `1.193`, p95 `1.312`, comm proxy `1.000`.
  - `tp2_ep2_greedy_static`: mean pressure `1.069`, p95 `1.156`, comm proxy `1.000`.
  - `ep4_hot64_replicated_greedy`: mean pressure `1.000`, p95 `1.000`,
    comm proxy `0.109`, memory lower bound `1.750x`.
- Prompt-class 8-record windows, 315 windows:
  - `ep4_greedy_static`: mean pressure `1.269`, p95 `1.562`, comm proxy `1.000`.
  - `tp2_ep2_greedy_static`: mean pressure `1.100`, p95 `1.250`, comm proxy `1.000`.
  - `ep4_hot64_replicated_greedy`: mean pressure `1.000`, p95 `1.000`,
    comm proxy `0.110`, memory lower bound `1.750x`.

Decision:

- Plain EP4 is not a clean c1 speed path. Even with static greedy placement it
  keeps the full expert-parallel movement proxy and shows meaningful p95
  imbalance.
- TP2+EP2 is less imbalanced than EP4, but it still keeps the full movement
  proxy and does not obviously halve the `~10 ms/token` decode budget.
- Hot-expert replication remains interesting, but only as an ingredient:
  top-64 replication can reduce routed-row movement to about `0.11x` while
  keeping route-load pressure near the TP4 proxy, at roughly `1.75x` per-rank
  expert-weight memory. It does not reduce MoE compute by itself, so it is not
  enough for `>200 tok/s` without a persistent/tile-native kernel, collective
  removal, or a static latency lane.
- The next implementation bet should not be a broad EP rewrite. The better
  sequence is:
  1. measure current per-rank expert-weight and KV headroom for hot64,
  2. prototype one-layer hot64 replicated routing in route replay only,
  3. pair it with one-launch persistent/tile-native MoE work,
  4. then consider a static c1 sidecar if the replay kernel shows a real
     latency drop.

## 2026-06-12 Hot-Replication Memory Feasibility

New script:

- `scripts/qwen36-hotrep-memory-plan.py`.

Artifacts:

- `data/qwen36-quark-int8-tp4-hotrep-memory-plan-20260612ae.json`.
- `data/qwen36-quark-int8-tp4-hotrep-memory-plan-20260612ae.md`.

Inputs:

- Accepted restore log:
  `/tmp/qwen36-quark-int8-tp4-accepted-restored-after-hotsetbench-20260612ac.log`.
- Live XPU telemetry from `xpu-smi dump -d -1 -m 18 -n 1`.
- Current model config:
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`.

Result:

- Per local-shard expert bytes: `795648`, matching the prior hotset plan and
  route-replay grouped-GEMM dimensions.
- Baseline all-expert MoE weight footprint per rank: `7770.0 MiB`.
- Live accepted lane memory snapshot:
  - device physical memory: `32656 MiB`.
  - max used: `32651.4 MiB`.
  - min free: `4.6 MiB`.
- Runtime KV report from vLLM:
  - available KV cache memory: `20.67 GiB`.
  - GPU KV cache size: `2052915` tokens.
  - maximum 32K-context concurrency: `62.65x`.
- Additional all-layer hot cache storage per rank:
  - hot16: `485.6 MiB`.
  - hot32: `971.2 MiB`.
  - hot64: `1942.5 MiB`.
- KV carve-out required for all-layer hot64:
  - no extra reserve: free about `188405` KV tokens, leaving `56.90x`
    theoretical 32K concurrency.
  - `512 MiB` reserve: free about `238064` KV tokens, leaving `55.38x`.
  - `1024 MiB` reserve: free about `287724` KV tokens, leaving `53.87x`.

Decision:

- Do not try to bolt all-layer hot64 storage onto the current accepted
  TP4/32K/c48 lane as-is. The lane is effectively full by telemetry.
- Hot64 storage is feasible in principle because it is small compared with the
  reported KV cache budget, but it needs an explicit KV/graph memory carve-out
  or a separate lower-context c1 latency lane.
- The next implementation step remains route-replay only:
  1. one-layer hot64 replicated routing,
  2. one-launch or persistent/tile-native execution,
  3. then a low-context sidecar memory screen if the route-replay kernel shows
     a real latency win.
- This keeps the production lane stable while we test whether hot replication
  has speed value before spending VRAM on it.

## 2026-06-12 Hot64 Route Work-Queue Prototype

New script:

- `scripts/qwen36-hotrep-route-plan.py`.

Artifacts:

- Layer 9 routecapture6:
  `data/qwen36-quark-int8-tp4-hotrep-route-plan-l9-route6-20260612af.json`
  and
  `data/qwen36-quark-int8-tp4-hotrep-route-plan-l9-route6-20260612af.md`.
- Layer 20 routecapture5:
  `data/qwen36-quark-int8-tp4-hotrep-route-plan-l20-route5-20260612af.json`
  and
  `data/qwen36-quark-int8-tp4-hotrep-route-plan-l20-route5-20260612af.md`.

Purpose:

- Convert captured exact `topk_ids` into kernel-facing per-rank hot/cold work
  queues and gather maps.
- Preserve exact routing: no expert dropping, no top-k approximation, and no
  prompt-class substitution.
- Keep this as route replay only; no live endpoint restart or production-lane
  VRAM changes.

Result:

- Layer 9, routecapture6, starts `0,1,2,46,78`:
  - assignments/window: `128`.
  - hot64 coverage mean/p95/min: `0.870` / `0.938` / `0.750`.
  - cold rows mean/max: `16.6` / `32.0`.
  - every selected window balances exactly to rows by rank `[32, 32, 32, 32]`.
  - generated JSON includes actual row detail and a complete 128-row gather map
    for each window.
- Layer 20, routecapture5, starts `11,12,13,52,63`:
  - assignments/window: `128`.
  - hot64 coverage mean/p95/min: `0.855` / `0.872` / `0.820`.
  - cold rows mean/max: `18.6` / `23.0`.
  - every selected window balances exactly to rows by rank `[32, 32, 32, 32]`.
  - generated JSON includes actual row detail and a complete 128-row gather map
    for each window.

Decision:

- Hot64 replicated routing is implementable as exact metadata for these
  route-replay windows. The route planner can produce:
  1. per-rank hot rows keyed by compact hot expert,
  2. per-rank cold rows keyed by logical expert,
  3. deterministic rank-local row indices,
  4. and a gather map back to original assignment order.
- This solves the route-metadata side of a one-launch hot64 layerlet, but it is
  not a speed result. The next meaningful gate is a kernel/microbench that
  consumes this exact queue format, runs hot and cold work in one dispatch or
  persistent loop, and compares output exactly against `xpu_fused_moe`.
- If that kernel cannot beat the current exact grouped-GEMM replay on these
  same windows, hot64 should stay a planning artifact rather than a production
  memory carve-out.

## 2026-06-12 Hotrep Route-Plan GEMM Shape Gate

New script:

- `scripts/bench-qwen36-hotrep-route-plan-gemm.py`.

Artifacts:

- Dry-run JSON:
  `data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-dryrun-20260612ag.json`.
- Dry-run summary:
  `data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-dryrun-20260612ag.md`.

Command:

```bash
python3 scripts/bench-qwen36-hotrep-route-plan-gemm.py \
  --dry-run \
  --route-plan-json \
    data/qwen36-quark-int8-tp4-hotrep-route-plan-l9-route6-20260612af.json \
    data/qwen36-quark-int8-tp4-hotrep-route-plan-l20-route5-20260612af.json \
  --output-json data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-dryrun-20260612ag.json \
  --markdown-out data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-dryrun-20260612ag.md
```

Purpose:

- Convert the exact hot64 route work queues into the grouped-GEMM shapes that
  a one-launch or persistent hot-replicated MoE layerlet would need to run.
- Compare three cases without changing the live endpoint:
  1. current exact full logical expert table,
  2. ideal per-rank hot+cold one-launch lower bound,
  3. hot and cold as separate per-rank launches.

Dry-run shape result:

- Current exact full table:
  - rows/window: `128`.
  - experts/table: `256`.
  - active experts/window: mean `43.4`, max `58`.
  - estimated allocation pressure: `128.56 MiB` for `gemm1`,
    `66.52 MiB` for `gemm2`.
- Hotrep per-rank one-launch shape:
  - rows/rank/window: `32`.
  - experts/rank/table: mean `68.1`, max `70`.
  - active experts/rank/window: mean `21.9`, max `25`.
  - estimated allocation pressure: max `35.15 MiB` for `gemm1`,
    `18.18 MiB` for `gemm2`.
- The two-launch hot/cold screen has the same shape pressure, but it will pay
  the same launch-tax failure mode that already made compact hotset splitting
  lose. Keep it as a diagnostic only.

Decision:

- This is a shape gate, not a speed result. It confirms the route-plan format
  produces plausible smaller per-rank work tables before any endpoint or kernel
  change.
- The next clean-XPU benchmark should run this same script without `--dry-run`
  after stopping the accepted endpoint, then restore the accepted backend and
  rerun provenance plus a short speed sanity.
- Promotion bar: a hotrep path only matters if the one-launch/persistent lower
  bound beats the current exact full-table grouped-GEMM replay on these same
  route windows. A two-launch hot/cold win is unlikely based on the previous
  negative GPU result.

Additional larger no-quality-loss ideas to track:

1. **Route-plan to persistent-kernel compiler.**
   Treat the hotrep JSON as an intermediate representation. Compile it into a
   persistent worker queue with fixed rank-local hot tables, cold overflow
   tasks, and deterministic gather maps. This avoids inventing the kernel API
   blind and makes route replay, parity, and production metadata share one
   format.

2. **Graph-resident MoE dispatch sequencer.**
   Move route packing, rows-per-expert metadata, and tiny scheduling decisions
   into graph-stable device buffers. The goal is to reduce host/device fences
   and stop making every decode token rebuild small MoE control structures.

3. **Hot cache as a low-context latency-lane feature only.**
   Do not spend the 32K production KV budget until a route-replay speed result
   exists. If hot64 wins, test it first in a smaller static c1 lane where
   `~2 GiB/rank` for all-layer hot cache is an intentional trade, not hidden
   pressure on the general service.

4. **Expert work-stealing inside a rank group.**
   Static row balance is good in the current windows, but cold experts can
   still create small irregular GEMMs. A persistent kernel could let idle
   workers steal cold expert tiles while preserving exact output order through
   the gather map.

5. **Per-layer route-class autotune cache.**
   Record a small menu of route classes per layer, prompt type, and decode
   phase, then pick a kernel policy from that cache: full table, hotrep
   one-launch, compact active-only, or persistent queue. The policy must be
   selected from route metadata, not from generated text semantics.

6. **XMX/DPAS roofline packet per MoE stage.**
   For each route-window shape, measure whether the XPU kernel is compute-bound,
   bandwidth-bound, or launch-bound. If hotrep reduces allocation but lowers
   DPAS occupancy too much, persistent full-table scheduling may be the better
   route than smaller tables.

7. **C++/SYCL single-layer parity binary.**
   Build one standalone executable that consumes captured hidden states,
   top-k routes, Quark W8A8 expert weights/scales, and the hotrep gather map.
   It should compare byte/logit-level against Python route replay while making
   Level Zero timelines and XMX counters easier to collect.

8. **Verified public perf packet after a real win.**
   When a material result clears a threshold such as `105` or `120 tok/s`,
   publish the Localmaxxing row with the exact command, dry-run shape artifact,
   route-window timing artifact, provenance guard, and quality sentinel file.
   The current `99.428 tok/s` row is still the only public exact-model B70 row
   as of this check, so a real improvement will be easy to distinguish.

## 2026-06-12 Hotrep Route-Plan GEMM Timing Result

Artifacts:

- Timing JSON:
  `data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-timing-20260612ah.json`.
- Timing summary:
  `data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-timing-20260612ah.md`.
- First restore log with device-lost event:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-hotrep-gemm-20260612ah.log`.
- Recovery snapshot:
  `data/qwen36-hotrep-gemm-device-lost-recovery-20260612ah/`.
- Successful second restore log:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-hotrep-gemm-recovery-20260612ah.log`.
- Successful provenance guard:
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-hotrep-gemm-recovery-20260612ah.json`.
- Successful p512/o128 speed smoke:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-hotrep-gemm-recovery-speed-p512o128-20260612ah.json`.

Command:

```bash
ZE_AFFINITY_MASK=0 ONEAPI_DEVICE_SELECTOR=level_zero:0 \
  /home/steve/.venvs/vllm-xpu/bin/python \
  scripts/bench-qwen36-hotrep-route-plan-gemm.py \
  --route-plan-json \
    data/qwen36-quark-int8-tp4-hotrep-route-plan-l9-route6-20260612af.json \
    data/qwen36-quark-int8-tp4-hotrep-route-plan-l20-route5-20260612af.json \
  --output-json data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-timing-20260612ah.json \
  --markdown-out data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-timing-20260612ah.md
```

Result:

- The benchmark ran cleanly on XPU 0 after stopping the accepted TP4 endpoint.
- Mean total grouped-GEMM time across the ten selected route windows:
  - `exact_full`: `189.694 us`.
  - `hotrep_one_launch_rankmax`: `197.037 us`.
  - `hotrep_two_launch_rankmax`: `389.275 us`.
- Stage means:
  - `exact_full/gemm1`: `97.138 us`.
  - `exact_full/gemm2`: `92.556 us`.
  - `hotrep_one_launch/gemm1`: `100.965 us`.
  - `hotrep_one_launch/gemm2`: `96.072 us`.
  - `hotrep_two_launch/gemm1`: `198.532 us`.
  - `hotrep_two_launch/gemm2`: `190.743 us`.

Decision:

- Hot64 route replication is rejected as a grouped-GEMM lower-bound speed path
  for these windows. Even the idealized one-launch rank-max screen is `3.9%`
  slower than the current full-table exact shape, despite the smaller
  per-rank table.
- The likely reason is small-shape/launch/occupancy overhead: shrinking the
  table from `256` experts to about `68-70` experts per rank does not make the
  B70 W8A8 grouped-GEMM kernel faster for this decode shape.
- Do not spend more production-lane downtime on endpoint hot64 replication,
  cold/hot two-launch variants, or KV carve-outs for hot64 unless a different
  persistent/tile-native kernel first reverses this lower-bound result.
- Keep the route-plan JSON format as useful metadata for persistent MoE,
  expert work queues, parity tests, and upstream repros. The data is still
  valuable; the current grouped-GEMM execution strategy is not.

Reliability note:

- The first accepted-backend restore after the microbench reached `/health`,
  then crashed on the first p512/o128 completion with
  `UR_RESULT_ERROR_DEVICE_LOST` in `block_table.copy_to_gpu(num_reqs)`, followed
  by `num_computed_tokens` copy failures. This is the same XPU metadata-copy
  failure class seen in earlier profiling restores.
- Recovery snapshot plus targeted vLLM cleanup succeeded; the four-XPU copy
  smoke passed with correct sums on devices `0-3`.
- The second restore passed the accepted provenance guard:
  `repetitive_kernel_notes` token `4752` at index `14`,
  `natural_latency_plan` token `11436` at index `17`, and token `198` at
  index `25`.
- The second restore speed smoke measured `99.733 tok/s` corrected after first
  text chunk and `9.953 ms/generated token` decode at p512/o128. The accepted
  quality/speed baseline is restored.

Next direction:

- Move hotrep out of the near-term serving path.
- Prioritize either:
  1. persistent/tile-native exact W8A8 MoE that can beat the full-table
     grouped-GEMM lower bound,
  2. graph-resident scheduler metadata to attack both latency and device-lost
     failure modes,
  3. exact target-verified speculation with a transactional resident-state
     verifier.

## 2026-06-12 Block-Table Dirty Commit Patch

New patch and validation:

- Patch:
  `patches/vllm-qwen36-xpu-block-table-dirty-commit-20260612.patch`.
- Validation script:
  `scripts/check-qwen36-block-table-dirty-commit.py`.
- Validation artifact:
  `data/qwen36-block-table-dirty-commit-check-20260612ai.json`.

Purpose:

- Reduce one known XPU reliability and latency pressure point:
  `block_table.copy_to_gpu(num_reqs)`.
- The current path copies the active block-table rows to XPU every prepare
  step. In c1 decode, that row normally changes only when the request is added,
  removed, moved, swapped, or receives a new KV block. For most generated
  tokens, the block table is unchanged.
- The default-off patch adds dirty-row tracking to `BlockTable` and makes
  `commit_block_table()` skip the host-to-XPU copy when no active rows changed,
  or copy only contiguous dirty row ranges when only a subset changed.

Controls:

- Runtime env:
  `VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT=1`.
- Optional stats log:
  `VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT_LOG_EVERY=<N>`.
- Production launch guard:
  `scripts/launch-qwen36-quark-int8-accepted.sh` now strips these env vars
  unless `VLLM_XPU_METADATA_COPY_ALLOW=1` is set.

Validation:

```bash
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile \
  /home/steve/src/vllm/vllm/v1/worker/block_table.py \
  scripts/check-qwen36-block-table-dirty-commit.py

bash -n scripts/launch-qwen36-quark-int8-accepted.sh

/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/check-qwen36-block-table-dirty-commit.py \
  --output-json data/qwen36-block-table-dirty-commit-check-20260612ai.json
```

The CPU-device simulation passed:

- `total` commits: `7`.
- skipped commits: `2`.
- full commits: `1`.
- partial commits: `4`.
- copied dirty rows: `7`.

Decision:

- This is not a speed claim yet. It is a safe, default-off implementation
  candidate that specifically targets the repeated metadata-copy failure class
  observed after risky XPU runs.
- Next controlled A/B gate: launch accepted TP4/32K with
  `VLLM_XPU_METADATA_COPY_ALLOW=1`,
  `VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT=1`, and a moderate
  `VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT_LOG_EVERY`, then run provenance guard and
  p512/o128 plus p512/o512 speed smokes. Promote only if sentinels pass and
  decode latency improves or device-lost frequency drops.

## 2026-06-12 Dirty Block-Table Endpoint A/B

Session:

- `qwen36-tp4-dirty-blocktable-ab-20260612aj`.

Launch:

```bash
VLLM_XPU_METADATA_COPY_ALLOW=1 \
VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT=1 \
VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT_LOG_EVERY=64 \
LOG_PATH=data/qwen36-quark-int8-tp4-dirty-blocktable-ab-20260612aj.log \
scripts/launch-qwen36-quark-int8-accepted.sh
```

Artifacts:

- A/B log:
  `data/qwen36-quark-int8-tp4-dirty-blocktable-ab-20260612aj.log`.
- Provenance guard:
  `data/qwen36-quark-int8-tp4-dirty-blocktable-ab-provenance-20260612aj.json`.
- p512/o128 speed:
  `data/qwen36-quark-int8-tp4-dirty-blocktable-ab-speed-p512o128-20260612aj.json`.
- p512/o512 r2 speed:
  `data/qwen36-quark-int8-tp4-dirty-blocktable-ab-speed-p512o512-r2-20260612aj.json`.
- Restored accepted-backend log:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-dirty-ab-20260612aj.log`.
- Restored accepted-backend provenance:
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-dirty-ab-20260612aj.json`.
- Restored accepted-backend p512/o128 speed:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-dirty-ab-speed-p512o128-20260612aj.json`.

Quality/provenance:

- Provenance guard passed.
- `repetitive_kernel_notes` sentinel index `14`: expected/actual token `4752`.
- `natural_latency_plan` sentinel index `17`: expected/actual token `11436`.
- `natural_latency_plan` sentinel index `25`: expected/actual token `198`.
- Cache fragment matched the accepted TP4/32K no-prefix graph cache root.

Speed result:

- p512/o128:
  - corrected after-first output speed: `100.364 tok/s`.
  - e2e output speed: `95.451 tok/s`.
  - client TTFT: `75.614 ms`.
  - vLLM decode histogram: `9.893 ms/generated token`.
- p512/o512, 2 repeats:
  - corrected after-first output speed: `100.093 tok/s` mean.
  - e2e output speed: `98.814 tok/s` mean.
  - client TTFT: `76.200 ms` mean.
  - vLLM decode histogram: `9.972 ms/generated token` mean.

Dirty-commit counters:

- The patch worked mechanically. The latest visible per-worker counters reached
  roughly `1280` total commit calls with about `1270` skipped, `10` full
  copies, `0` partial copies, and `10` copied rows.
- There were no `DEVICE_LOST`, `Traceback`, or first-error lines in the A/B log
  during the provenance and speed smokes.

Decision:

- Neutral for c1 decode speed. The repeated block-table H2D copy is mostly
  redundant, but removing it did not move the `~10 ms/token` steady decode
  ceiling.
- Keep the patch default-off as a reliability and metadata-copy pressure
  reducer. It may matter more under multi-request churn, request add/remove
  cycles, swap/move events, or risky timing/profiling branches.
- Do not count this as a performance win toward `>200 tok/s`.
- Restore the normal accepted backend after the A/B because the env is still
  experimental.

Restore result:

- Session:
  `qwen36-tp4-accepted-restored-after-dirty-ab-20260612aj`.
- `/health` returned after `53 s`.
- Provenance guard passed all three exact sentinels after restore.
- Restored p512/o128 speed sanity:
  - corrected after-first output speed: `99.256 tok/s`.
  - e2e output speed: `94.425 tok/s`.
  - client TTFT: `76.050 ms`.
  - vLLM decode histogram: `10.003 ms/generated token`.
- The live backend is back on the normal accepted launch path, without the
  dirty block-table env enabled.

Things to try from this result:

1. **Metadata-copy stress soak.**
   Build a churn workload that repeatedly adds, removes, and completes requests
   while generating. Compare default block-table copies versus dirty commits for
   device-lost rate, host-copy count, TTFT p95, and c1 throughput.
2. **Unify tiny scheduler metadata updates.**
   The recurring failures also touched `num_computed_tokens` and
   `num_accepted_tokens`. Treat block tables as one member of a broader
   device-resident metadata project, not the whole project.
3. **Device-side metadata ring.**
   Prototype a graph-safe device buffer for block-table tails, computed-token
   counters, accepted-token counters, and slot maps, then update it with a tiny
   kernel instead of repeated host-to-device copies/fills.
4. **Keep a no-speed regression gate.**
   Any metadata patch must pass exact sentinels and stay within noise of the
   accepted `~100 tok/s` c1 baseline before it is used in risky profiling.
5. **Measure aggregate impact separately.**
   The A/B only tested single-request decode. Dirty commits may still improve
   aggregate throughput or tail latency at `c8`, `c16`, or `c48` where request
   churn and scheduler state are more active.

External context added while planning next steps:

- Localmaxxing currently shows the 4x Arc Pro B70 Qwen3.6-35B result set topped
  by two `~100 tok/s` c1 rows at 32K context, including the exact
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` run:
  <https://localmaxxing.com/api/leaderboard?hardwareName=B70&modelFamily=qwen&limit=20>.
- vLLM's Arc Pro B-series writeup lists the major XPU features that matter to
  this work: multi-GPU scaling, P2P transfer, optimized MoE models, async
  scheduling, prefill/decode disaggregation, n-gram/EAGLE/EAGLE3 speculative
  decoding, and mixed precision recipes:
  <https://vllm.ai/blog/2025-11-11-intel-arc-pro-b>.
- The Intel Triton-XPU grouped-GEMM issue specifically calls out skewed decode
  routing and real token distributions as critical for MoE kernel tuning:
  <https://github.com/intel/intel-xpu-backend-for-triton/issues/6389>.
- vLLM's public XPU page validates Arc Pro B-Series as the hardware target, but
  current recommended-model docs do not replace our exact-model validation:
  <https://docs.vllm.ai/en/stable/models/hardware_supported_models/xpu/>.
- vLLM's public W8A8 INT8 docs still describe the official INT8 compute support
  in NVIDIA terms, so our Quark/XPU path remains a local/vendor path that needs
  its own correctness and performance proof:
  <https://docs.vllm.ai/en/v0.18.0/features/quantization/int8/>.
- IPEX-LLM/OpenVINO/llama.cpp/Vulkan remain useful as control lanes for Intel
  hardware behavior, but they are not production candidates unless they can run
  the same Qwen3.6 A3B target with an 8-bit or BF16-equivalent fidelity gate.

New bigger, bolder ideas to keep visible:

1. **Exact decode appliance outside vLLM.**
   Build a fixed-bucket runner for one c1 shape that loads the exact Quark W8A8
   weights, certified graph/kernel artifacts, and fixed sampling, then bypasses
   the dynamic vLLM scheduler. If it stays near `100 tok/s`, the ceiling is
   kernel/hardware. If it jumps, production should add a latency sidecar.
2. **Persistent MoE kernel compiler from route windows.**
   Turn routecapture windows into generated kernel descriptors: layer, hotset,
   active experts, row maps, tile layout, and exact fallback policy. Generate a
   one-layer persistent worker and compare it against `xpu_fused_moe` before
   trying a server patch.
3. **Tile-native hotset cache with cold queue in one dispatch.**
   Keep top-64 hot experts packed in the fastest B70 layout, but execute hot and
   cold rows in one launch or persistent loop. The two-launch split lost; the
   one-dispatch form is still a serious no-quality-loss path.
4. **TP1/TP2 low-context sidecar as a latency control.**
   Try the exact model at lower max context and lower concurrency on one or two
   cards. The goal is not production capacity; it is to prove whether TP4
   collectives and rank synchronization are part of the c1 wall.
5. **XMX/DPAS proof packet.**
   Profile the hot W8A8 kernels down to DPAS/XMX utilization, occupancy, memory
   bandwidth, and launch gaps. If the current Quark path is not using the
   intended INT8 hardware efficiently, launch-flag tuning will never reach
   `>200 tok/s`.
6. **MTP/EAGLE/DFlash only behind resident target verification.**
   Speculation is still the clearest mathematical route to `>200 tok/s`, but
   only if the current model verifies candidate tokens from in-engine
   copy-on-write KV/GDN/request state. External refill verification is not good
   enough.
7. **Graph-resident decode loop.**
   Investigate keeping the whole single-token decode loop resident across
   scheduler metadata, GDN/linear attention, MoE, logits, and sampling metadata.
   This is larger than a kernel patch, but it attacks command gaps and host
   synchronization directly.
8. **Exact 8-bit engine bakeoff with route fixtures.**
   Compare vLLM/Quark, newer `vllm-xpu-kernels`, Intel container branches,
   OpenVINO/oneDNN GenAI if supported, IPEX-LLM, and llama.cpp/Vulkan as
   route-replay or short-context controls. Exclude 4-bit/AWQ and any Qwen3.5
   substitute.
9. **Host-stack breakglass lane.**
   Keep a separate disk/environment for aggressive Intel stack experiments:
   kernel/KMD, firmware, oneAPI, oneCCL, PyTorch XPU, Triton-XPU, and
   vLLM/vllm-xpu-kernels. A stack that improves speed but increases
   device-lost rate does not enter production.
10. **Public upstream perf packet.**
    Package exact sentinels, route windows, hotrep negative, dirty-copy A/B,
    model-forward timing, and Localmaxxing context into a small repro for Intel
    and vLLM. The ask should be precise: persistent or tile-native W8A8 MoE for
    skewed Qwen3.6 A3B decode on Arc Pro B70.

## 2026-06-12 Route-Exact Grouped-GEMM Roofline Packet

New script:

- `scripts/qwen36-gemm-roofline-from-timing.py`.

Purpose:

- Convert existing route-exact grouped-GEMM event timings into an offline
  roofline packet: GEMM shapes, active experts, estimated math operations,
  active-weight memory lower bound, full-table memory upper bound, effective
  TOPS, and implied bandwidth.
- This is a CPU-only analysis pass over timing JSON. It does not allocate XPU
  memory or interrupt the accepted backend.

Tooling boundary:

- `unitrace`, `oneprof`, and VTune are not installed in this environment.
- `xpu-smi` EU, bandwidth, and engine metrics require elevated MEI access; the
  current user does not have passwordless sudo.
- `intel_gpu_top` cannot see the current Xe devices from this user context.
- Therefore this packet cannot prove DPAS/XMX instruction use directly. It is a
  shape/timing roofline estimate from already-recorded kernel timings.

Command:

```bash
python3 scripts/qwen36-gemm-roofline-from-timing.py \
  --timing-json data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-timing-20260612ah.json \
  --output-json data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-roofline-20260612ak.json \
  --markdown-out data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-roofline-20260612ak.md
```

Artifacts:

- `data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-roofline-20260612ak.json`.
- `data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-roofline-20260612ak.md`.

Key numbers:

- `exact_full/gemm1`:
  - mean timing: `97.138 us`.
  - mean shape: `M=128, K=2048, N=256`.
  - mean active experts: `43.4`.
  - effective math throughput: `1.413 TOPS`.
  - active-weight lower-bound bandwidth: `0.245 TB/s`.
  - full-table upper-bound bandwidth: `1.419 TB/s`.
- `exact_full/gemm2`:
  - mean timing: `92.556 us`.
  - mean shape: `M=128, K=128, N=2048`.
  - mean active experts: `43.4`.
  - effective math throughput: `0.725 TOPS`.
  - active-weight lower-bound bandwidth: `0.133 TB/s`.
  - full-table upper-bound bandwidth: `0.754 TB/s`.
- `hotrep_one_launch_rankmax/gemm1`:
  - mean timing: `100.965 us`.
  - mean shape: `M=32, K=2048, N=256`.
  - effective math throughput: `0.337 TOPS`.
- `hotrep_one_launch_rankmax/gemm2`:
  - mean timing: `96.072 us`.
  - mean shape: `M=32, K=128, N=2048`.
  - effective math throughput: `0.175 TOPS`.
- `hotrep_two_launch_rankmax/cold` drops to roughly `0.050 TOPS` for `gemm1`
  and `0.026 TOPS` for `gemm2`, because the cold fallback is tiny
  (`~5` rows).

Interpretation:

- These effective TOPS are far below what a B70-class INT8 path should deliver
  if it were compute-saturating. The route-exact grouped-GEMM bottleneck is
  consistent with small-M/skewed-expert underutilization, launch/control
  overhead, a non-ideal kernel path, or some mix of those.
- The hotrep negative is now explained more clearly: shrinking the table also
  shrinks `M` per rank, and effective TOPS collapses further. Memory allocation
  pressure improved, but compute utilization got worse.
- This strengthens the decision to avoid more split-launch hot/cold variants.
  The credible no-quality-loss path is one of:
  1. persistent expert workers that keep skewed small-M work resident,
  2. tile-native W8A8 repack plus one-dispatch cold queue,
  3. grouped-GEMM policy/kernel work for real route distributions,
  4. or exact target-verified speculation that accepts multiple target tokens
     per expensive forward.

Next concrete ideas from this packet:

1. **Privilege/tooling lane for real counters.**
   Install or enable `unitrace`/VTune/oneprof, or grant MEI telemetry access to
   collect EU active/stall/idle, memory bandwidth, and DPAS/XMX counters on the
   route-replay GEMM harness.
2. **Grouped-GEMM shape amplification screen.**
   Benchmark synthetic exact-shape variants with larger `M` buckets
   (`128`, `256`, `512`, `1024`) but the same `K/N` and expert skew. If TOPS
   scales sharply with `M`, persistent batching/work aggregation is the right
   kernel direction.
3. **Small-M kernel policy search.**
   Compare current grouped GEMM against per-expert GEMM, packed batched GEMM,
   and persistent grouped GEMM for the observed route windows. The cold rows are
   too small for a normal grouped-GEMM launch to be viable.
4. **One-layer persistent MoE proof.**
   Start with one layer and one captured window. The success metric is not only
   lower microseconds; it must raise effective TOPS materially while matching
   `xpu_fused_moe` numerically.
5. **Upstream perf packet target.**
   Include the roofline packet with route windows, hotrep negative, and exact
   provenance sentinels when asking Intel/vLLM for persistent W8A8 MoE work.

## 2026-06-12 Bigger Bets Refresh And M-Scaling Gate

User direction:

- Keep tracking lessons, future experiments, results, and repro code in this
  repo.
- Continue pursuing speed on the current exact Qwen3.6 Quark W8A8 INT8 model
  without lowering quality.
- Think bigger than launch-flag tuning, but keep every idea tied to a proof
  artifact and a quality gate.

New dry-run artifact:

- Script: `scripts/bench-qwen36-grouped-gemm-m-scaling.py`.
- Dry-run JSON:
  `data/qwen36-quark-int8-tp4-grouped-gemm-mscaling-dryrun-20260612al.json`.
- Dry-run markdown:
  `data/qwen36-quark-int8-tp4-grouped-gemm-mscaling-dryrun-20260612al.md`.
- Validation:
  `python3 -m py_compile scripts/bench-qwen36-grouped-gemm-m-scaling.py`
  passed.
- Inputs:
  - `data/qwen36-quark-int8-tp4-hotrep-route-plan-l9-route6-20260612af.json`.
  - `data/qwen36-quark-int8-tp4-hotrep-route-plan-l20-route5-20260612af.json`.
- Dry-run generated `120` cases: `10` real route windows, `2` GEMM stages,
  and target row buckets `32,64,128,256,512,1024`.
- The artifact is intentionally timing-free. It validates shape construction
  only and should be run on XPU only in a clean benchmark window.

Why this gate matters:

- The roofline packet showed current route-exact grouped GEMM is far below B70
  INT8 compute potential.
- The hotrep split made `M` smaller and got slower, so the next question is
  whether larger `M` buckets recover TOPS.
- If TOPS scales strongly from `M=128` to `M=512/1024`, persistent batching,
  work aggregation, or a static c1 lane that amortizes more routed rows per
  launch is a credible no-quality-loss direction.
- If TOPS stays flat, the blocker is more likely the underlying kernel path,
  data layout, DPAS/XMX utilization, launch/control overhead, or a bad
  small-shape policy. In that case, route batching alone will not get us to
  `>200 tok/s`.

Public signals checked for this refresh:

- Localmaxxing still shows one approved public exact-model B70/vLLM row for
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`: our 4x B70, 32K,
  quality-gated `99.428 tok/s` baseline. No public exact-model faster row was
  found in the filtered result set.
- Intel's grouped-GEMM XPU issue remains aligned with our approach: MoE decode
  routing is skewed, and grouped-GEMM tuning needs realistic route
  distributions rather than only synthetic uniform shapes:
  <https://github.com/intel/intel-xpu-backend-for-triton/issues/6389>.
- Public B70 benchmark data from PMZFX reports Qwen3.6-35B-A3B MoE behavior
  across llama.cpp SYCL/Vulkan and dual-card runs, reinforcing two lessons:
  B70 can run this model family well, and naive multi-GPU layer splitting is
  not proof of better c1 latency:
  <https://github.com/PMZFX/intel-arc-pro-b70-benchmarks>.
- Xe-Forge is relevant as a process idea, not as a drop-in solution: start from
  a correct Triton/SYCL kernel, then run a hardware-in-the-loop optimization
  loop with correctness and performance checks on Intel GPU:
  <https://arxiv.org/html/2605.26118v1>.

## Things To Try Next

1. **Run the grouped-GEMM M-scaling timing screen.**
   Stop the accepted backend, run the new M-scaling script on `xpu:0`, restore
   the accepted backend, then run provenance and p512/o128 speed sanity. The
   decision table is simple: strong TOPS scaling means aggregate/persistent
   work is worth building; flat TOPS means go lower into kernel/layout/counter
   proof first.

2. **Build a one-layer exact MoE replay with hotset and cold fallback.**
   Use layer `9` and layer `20` route windows first. Compare current
   `xpu_fused_moe`, preallocated scratch, current grouped GEMM, top-64
   tile-native hotset, and cold fallback in the same harness. Promotion requires
   numeric equivalence against the current Quark W8A8 path.

3. **Turn M-scaling into a kernel policy search.**
   For the same route windows, compare grouped GEMM, per-expert GEMM,
   batch-packed GEMM, persistent grouped GEMM, and one-dispatch hot/cold queue.
   Record effective TOPS, lower/upper bandwidth bounds, active experts, and
   launch count per case.

4. **Get real DPAS/XMX counters or a credible substitute.**
   The current roofline is timing-derived. The next proof should install or
   enable `unitrace`, VTune, `oneprof`, or MEI telemetry access, then report
   whether the hot W8A8 kernels actually issue high-occupancy DPAS/XMX INT8.
   If privileged counters remain blocked, disassemble the generated kernels and
   at least prove the intended op path.

5. **Transplant, do not migrate, a newer persistent-MoE kernel.**
   Watch Intel `vllm-xpu-kernels`, `llm-scaler-vllm`, and Triton-XPU branches.
   When a persistent W8A8 MoE kernel appears, isolate it behind the route-replay
   harness before changing the accepted server stack.

6. **Prototype a static low-context latency lane.**
   Keep the TP4/32K service as the stable production lane, but test a fixed
   c1 sidecar with lower context, preallocated metadata, certified graph cache,
   and strict admission control. This is not a model-quality compromise; it is
   a serving-shape specialization.

7. **Run a TP/EP/hotset simulation with measured latencies.**
   Update the route-parallelism simulator with measured GEMM and allreduce
   costs, not only movement proxies. This will tell us whether TP2+EP2,
   replicated attention plus sharded experts, or hot-expert replication can
   beat TP4 c1 latency.

8. **Add a BF16/logit-rank differential gate for kernel experiments.**
   Exact token sentinels are necessary but not enough for a deep kernel rewrite.
   Add a small BF16 fallback/logit-rank suite and route-replay numeric checks so
   a candidate cannot silently distort nearby probabilities.

9. **Make reliability a first-class perf metric.**
   Every maintenance-window experiment should record device-lost state,
   recovery snapshot, provenance result, restore time, and post-restore speed.
   A fast kernel that raises reset rate is not production progress.

10. **Prepare the upstreamable packet in parallel.**
    Bundle one route window, minimal weights/scales slice, current timing,
    roofline, M-scaling result, and expected outputs. The packet should be
    small enough that Intel/vLLM maintainers can run it without the full
    production service.

## Bigger, Bolder Ideas Added

1. **Route-window generated MoE kernels.**
   Generate layer/window-specialized kernels from captured route shapes. Keep
   the math exact, but specialize scheduling, tile size, and active expert
   layout to the observed distribution. This is bold because it trades generic
   runtime flexibility for c1 latency, but it fits the static-lane idea.

2. **Resident expert-worker runtime.**
   Instead of launching independent MoE substeps, keep a persistent expert
   worker pool alive on each B70. Workers pull routed rows, run W8A8 GEMM1,
   fused activation/quant, W8A8 GEMM2, and scatter without returning to Python
   or host scheduling between substeps.

3. **Graph-resident decode transaction engine.**
   Build the verifier/speculation path as an in-graph transaction system:
   versioned KV/GDN state, candidate token scoring by the current model,
   accept/rollback buffers, and exact sentinel proof. This is the highest-upside
   path if pure kernel work cannot halve model-forward time.

4. **Automatic Intel-kernel optimization loop.**
   Use the route-replay harness as the evaluator for a Xe-Forge-style loop:
   candidate Triton/SYCL kernels are generated or transformed, compiled, checked
   against exact outputs, benchmarked, and kept only if they improve the
   route-exact fixture.

5. **Whole-block fusion experiment.**
   If MoE-only wins are insufficient, prototype a one-layer whole-block replay
   that fuses or graph-coalesces Gated DeltaNet/attention, MoE, residuals, and
   metadata updates. The aim is to remove barriers around the model-forward
   graph, not change model math.

6. **Hardware topology sidecar.**
   Try the same accepted model on alternative physical topologies if available:
   all four cards, best two cards, one card with lower context, and independent
   replicas. Public B70 data suggests extra cards often improve aggregate
   throughput more than c1 latency; production may need topology-aware routing.

7. **Tile-native hotset cache as a first-class model artifact.**
   Store packed hot expert tensors beside the model with source tensor hashes,
   layer/source coverage, route-class labels, and equivalence checks. Treat it
   like a compiled graph cache: reproducible, certified, and invalidated when
   weights or runtime kernels change.

8. **C1 latency leaderboard packet.**
   Once a material improvement clears `105` or `120 tok/s`, publish a refreshed
   Localmaxxing row with provenance, quality gates, command, and notes. Save
   `>200 tok/s` for a genuinely new class of result, not measurement noise.

9. **Production dual-policy scheduler.**
   Serve the same model through two exact lanes: a stable capacity lane and a
   latency lane with fixed shapes. Route by prompt length, requested output,
   temperature policy, and concurrency. This can improve real user experience
   before a single universal backend exists.

10. **B70 failure-forensics matrix.**
    Systematically vary kernel/KMD, compute-runtime, oneAPI, PyTorch,
    oneCCL/OFI, and graph settings with a tiny accepted smoke. The output is a
    known-good production stack and a list of combinations that increase
    device-lost risk.

## 2026-06-12 M-Scaling Timing Result

Artifacts:

- Broad M-scaling timing:
  `data/qwen36-quark-int8-tp4-grouped-gemm-mscaling-timing-20260612am.json`
  and `.md`.
- Small-M timing:
  `data/qwen36-quark-int8-tp4-grouped-gemm-smallm-timing-20260612an.json`
  and `.md`.
- First restore after broad M-scaling:
  - Log:
    `data/qwen36-quark-int8-tp4-accepted-restored-after-mscaling-20260612am.log`.
  - Provenance:
    `data/qwen36-quark-int8-tp4-accepted-provenance-after-mscaling-20260612am.json`.
  - Speed:
    `data/qwen36-quark-int8-tp4-accepted-restored-after-mscaling-speed-p512o128-20260612am.json`.
- Final restore after small-M screen:
  - Log:
    `data/qwen36-quark-int8-tp4-accepted-restored-after-smallm-20260612an.log`.
  - Provenance:
    `data/qwen36-quark-int8-tp4-accepted-provenance-after-smallm-20260612an.json`.
  - Speed:
    `data/qwen36-quark-int8-tp4-accepted-restored-after-smallm-speed-p512o128-20260612an.json`.

Broad M-scaling result:

| stage | M | mean us | TOPS |
|---|---:|---:|---:|
| `gemm1` | 32 | 111.628 | 0.309 |
| `gemm1` | 64 | 112.938 | 0.605 |
| `gemm1` | 128 | 107.196 | 1.281 |
| `gemm1` | 256 | 102.215 | 2.667 |
| `gemm1` | 512 | 93.805 | 5.731 |
| `gemm1` | 1024 | 106.699 | 10.272 |
| `gemm2` | 32 | 110.462 | 0.154 |
| `gemm2` | 64 | 108.577 | 0.313 |
| `gemm2` | 128 | 101.541 | 0.671 |
| `gemm2` | 256 | 101.566 | 1.340 |
| `gemm2` | 512 | 101.423 | 2.682 |
| `gemm2` | 1024 | 105.324 | 5.193 |

Small-M result:

| stage | M | mean us | TOPS |
|---|---:|---:|---:|
| `gemm1` | 8 | 100.506 | 0.086 |
| `gemm1` | 16 | 93.443 | 0.180 |
| `gemm1` | 24 | 92.881 | 0.271 |
| `gemm1` | 32 | 92.897 | 0.361 |
| `gemm1` | 64 | 93.287 | 0.720 |
| `gemm1` | 128 | 93.285 | 1.439 |
| `gemm2` | 8 | 93.032 | 0.045 |
| `gemm2` | 16 | 93.586 | 0.090 |
| `gemm2` | 24 | 93.702 | 0.134 |
| `gemm2` | 32 | 93.099 | 0.180 |
| `gemm2` | 64 | 93.438 | 0.359 |
| `gemm2` | 128 | 93.972 | 0.715 |

Restoration evidence:

- Both benchmark windows exited cleanly. No device-lost event was observed.
- After the broad M-scaling screen, the accepted backend restored to `/health`
  in `57 s`, provenance passed all exact sentinels, and p512/o128 measured
  `99.604 tok/s` corrected with `9.962 ms/token` decode.
- After the small-M screen, the accepted backend restored to `/health` in
  `57 s`, provenance passed all exact sentinels, and p512/o128 measured
  `99.845 tok/s` corrected with `9.941 ms/token` decode.

Interpretation:

- The XPU grouped-GEMM path has a near-fixed latency floor around
  `93-110 us` for these Qwen3.6 W8A8 MoE shapes.
- Effective TOPS rises roughly with `M` because the launch/kernel floor is
  being amortized. `gemm1` rises from `0.086 TOPS` at `M=8` to `10.272 TOPS`
  at `M=1024`; `gemm2` rises from `0.045 TOPS` to `5.193 TOPS`.
- This explains why hotrep split launches lost: reducing rows per rank makes
  the fixed cost dominate harder.
- For single-user decode, the model pays this small-M floor repeatedly across
  MoE layers. A plain route reshuffle or hot/cold two-launch design will not
  halve latency.
- The no-quality-loss speed path is now narrower:
  1. collapse the fixed MoE cost with persistent/fused expert workers,
  2. make one dispatch handle hotset plus cold fallback without extra launches,
  3. or use exact target-verified speculation so each expensive target forward
     accepts multiple tokens and moves the workload into larger effective `M`.

Next implementation implication:

- Start with a one-layer persistent/fused MoE replay, not another endpoint flag
  sweep.
- The first target should prove it can beat the `~93 us` per-GEMM floor on
  `M=8,16,32` while matching `xpu_fused_moe` numerically.
- If no small-M kernel beats the floor, shift effort to resident-state
  target-verified speculation because larger effective `M` clearly improves
  arithmetic utilization.

## 2026-06-12 Fusion Target Budget And Bigger Bets

Artifacts:

- Budget script:
  `scripts/qwen36-moe-fusion-target-budget.py`.
- Budget report:
  `data/qwen36-quark-int8-moe-fusion-target-budget-20260612ao.md`
  and `.json`.

Budget result:

- Current accepted endpoint decode is `9.941 ms/token`, or `99.845 tok/s`
  corrected after the first streamed text chunk.
- Model-forward-only timing is `8.438 ms/token`, leaving an estimated
  `1.502 ms/token` outside the model-forward bucket.
- A `200 tok/s` c1 target requires `5.000 ms/token` decode.
- If outside-forward overhead is unchanged, the model-forward bucket must save
  `4.941 ms/token`.
- Spread across `40` MoE layers, that means `123.514 us/layer` saved.
- The route-exact primary row replay averages `283.842 us/layer` for current
  `xpu_fused_moe`.
- The exact preallocated staged lower bound averages `214.179 us/layer`, which
  would estimate only `139.781 tok/s` if it transferred perfectly to the
  endpoint.
- The next non-speculative layerlet must therefore reach about
  `160.328 us/layer` or better with exact numeric parity.
- Two independent small-M grouped GEMM dispatches are already `193.538 us`, so
  any viable non-speculative path needs a one-dispatch or persistent layerlet.

External scan:

- Localmaxxing public results currently show our Qwen3.6 W8A8 INT8 B70 row as
  the top B70/Qwen single-stream row visible for this exact model family:
  `~99.77 tok/s`, `76.53 ms` TTFT, 32K context, 4x B70.
  Query:
  `https://localmaxxing.com/api/leaderboard?hardwareName=Arc%20B70&modelFamily=qwen&limit=20`.
- The same scan shows a one-card B70 llama.cpp Qwen3.6 Q4 result around
  `70.35 tok/s`, and a separate 4-card mirrored setup reporting `68.8 tok/s`
  c1 with `338 tok/s` aggregate at higher batch. Those are not acceptable
  target replacements because they are Q4, but they are useful engine and
  topology clues.
- vLLM's generic INT8 W8A8 docs still primarily describe NVIDIA support, so
  our Intel path remains a local/upstream-edge XPU path rather than a mature
  generic INT8 route:
  `https://docs.vllm.ai/en/stable/features/quantization/int8/`.
- `vllm-xpu-kernels` release notes after `v0.1.8` mention MoE grouped-GEMM
  policy updates, small-K behavior, mixed prefill/decode attention routing, and
  FP8 KV cache paged-decode work:
  `https://github.com/vllm-project/vllm-xpu-kernels/releases`.
- Our serving venv reports `vllm 0.20.2rc1.dev2+gc51df4300.d20260523.xpu`,
  `PyTorch 2.11.0+xpu`, Level Zero driver `26.18.38308.1-0`, and
  `vllm-xpu-kernels 0.1.9.dev27+g28e1f5e`. The local kernels tree is at
  `28e1f5e remove transpose from ref_fused_moe (#360)`, after the visible
  grouped-GEMM commits `#333` and `#340`, but the tree is dirty with our local
  experiments.
- The local oneDNN third-party tree documents experimental grouped memory and
  grouped GEMM for MoE workloads behind
  `ONEDNN_EXPERIMENTAL_GROUPED_MEMORY`. This is not a direct fix, but it is a
  candidate one-layer replay backend.
- A current Qwen3.6 W8A8 issue in `llm-compressor` confirms that Qwen3.6 MoE
  W8A8 still needs architecture-specific handling for fused expert tensors and
  hybrid attention:
  `https://github.com/vllm-project/llm-compressor/issues/2787`.
- The Event Tensor / dynamic megakernel paper is a useful north star for our
  specific failure mode: conventional kernel and graph boundaries are the
  bottleneck, and MoE routing creates data-dependent fine-grained tasks:
  `https://arxiv.org/html/2604.13327v2`.

Bigger bets to keep in the queue:

1. **One-dispatch W8A8 MoE layerlet.**
   Build a one-layer XPU replay kernel that fuses route/remap, quant1, GEMM1,
   activation, quant2, GEMM2, and gather under one dispatch boundary. Promotion
   gate: exact parity to `xpu_fused_moe` and `<160 us/layer` on rows=`1`.

2. **Persistent resident expert worker.**
   Keep a small set of workgroups resident across decode steps and feed them
   route windows from device memory. This is harder than a normal custom op, but
   it attacks the measured fixed `93-110 us` launch/kernel floor directly.

3. **Event-Tensor-style MoE scheduler for Xe.**
   Prototype a small device-side task scheduler for routed expert tiles: top-k
   writes counts/events, expert GEMM tiles trigger as soon as rows are ready,
   and gather consumes tile completions without returning to host/PyTorch
   between phases. Treat it as a research branch, not a quick patch.

4. **oneDNN grouped-GEMM replay bakeoff.**
   Build a narrow route-replay harness using oneDNN grouped memory/matmul for
   the exact Qwen3.6 W8A8 shapes. If oneDNN's grouped path beats the current
   small-M floor, use it as a reference or a replacement backend for MoE
   layerlets.

5. **Shape-generated route-window kernels.**
   Capture route histograms over real prompts, identify repeated active-expert
   windows, and generate AOT kernels for the common buckets. Use current generic
   `xpu_fused_moe` only for cold fallback. This preserves quality because the
   math stays exact; only the schedule changes.

6. **TP2 latency lane plus 2x replica capacity lane.**
   Revisit topology with the exact INT8 model: if TP2 fits with the required
   context, it may reduce collective overhead and raise small-M occupancy versus
   TP4. If not, record the memory cliff and keep TP4 for the production lane.

7. **Strict target-verified speculation V2.**
   Stop trying to let speculative mode mutate verifier inputs. Instead create a
   shadow verifier bucket or sidecar that writes draft KV into temporary slots
   and commits only tokens accepted by the target. This is no-quality-loss by
   construction and can amortize the target forward across multiple accepted
   tokens.

8. **Micro-drafter trained on Qwen3.6 trace data.**
   If exact verifier plumbing works, train or distill a tiny B70-friendly
   drafter on Qwen3.6 traces. The drafter can be lower quality because the
   target verifies every accepted token; the quality risk is only in latency and
   stability, not final output correctness.

9. **Whole-token Level Zero command-list runner.**
   For a static c1 decode lane, bypass more Python/vLLM scheduling overhead by
   prebuilding a Level Zero command-list sequence for the fixed decode shape.
   Use it first as an offline model-forward parity harness, not as the public
   endpoint.

10. **Hardware-counter proof before more kernel tuning.**
    Get `unitrace`, VTune, or an equivalent metric path working with MEI/PMU
    access so we can measure XMX/DPAS occupancy and memory pressure directly.
    Timing-derived TOPS already says underfilled small-M, but counters will
    tell us whether the next bottleneck is dispatch, DPAS issue, memory layout,
    or synchronization.

11. **Engine-mining without quantization compromise.**
    Mine llama.cpp SYCL/Vulkan, OpenVINO GenAI, oneDNN, and custom ESIMD kernels
    for scheduling ideas, but do not switch the production target to Q4 or INT4.
    Any borrowed implementation must reproduce the exact W8A8 target outputs.

12. **Upstreamable B70/Qwen3.6 perf packet.**
    Package the route replay, small-M floor, target budget, and exact parity
    checks into a minimal issue/PR-ready repro for `vllm-xpu-kernels`. This may
    attract kernel maintainer attention and gives us a clean artifact even if we
    carry a local patch first.

## 2026-06-12 Fused SiLU+Quant Gate And Fresh Bigger Bets

Artifacts:

- Baseline route replay:
  `data/qwen36-quark-int8-moe-routecapture6-layer9-baseline-gate-20260612ap.md`
  and `.json`.
- Fused SiLU+quant candidate replay:
  `data/qwen36-quark-int8-moe-routecapture6-layer9-fused-siluq-gate-20260612ap.md`
  and `.json`.
- Restored accepted endpoint log:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-siluqgate-20260612ap.log`.
- Restored accepted endpoint provenance:
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-siluqgate-20260612ap.json`.

Result:

- The route-gate fixture uses layer `9`, routecapture6 rank-0 exact-ID routes,
  rows=`1`, starts `0:64:4`, `30` timed iterations, and `5` warmup iterations.
- Baseline current path is exact against `xpu_fused_moe`: max diff `0.000`.
  Its mean `xpu_fused_moe` time is `283.098 us/layer`; preallocated staged
  lower-bound mean is `212.792 us/layer`.
- The fused SiLU+quant candidate is not exact: manual staged and preallocated
  staged paths both show max abs diff `0.750` versus `xpu_fused_moe`.
- Even ignoring the exactness failure, the candidate only moves mean
  `xpu_fused_moe` time to `272.862 us/layer`, far above the `~160 us/layer`
  target needed for a plausible non-speculative `200 tok/s` c1 lane.
- Decision: reject the fused SiLU+quant candidate for the no-quality-loss path.
  Keep any future activation/quant fusion behind strict bit/token parity and
  treat it as a small component cleanup, not the main speed plan.
- After the one-card route replay window, the accepted TP4 endpoint was
  restored on `127.0.0.1:18080`. Provenance passed exact sentinels and parsed
  the expected accepted graph cache root. `xpu-smi ps` showed one TP worker
  owning each B70 with about `32.76 GB` allocated per card and reported
  available KV cache memory in the log is `20.67 GiB`.
- Fresh Localmaxxing exact-model query still shows the approved public row at
  `99.428 tok/s` for this exact model/hardware/engine setup. Do not post the
  tiny `99.728 tok/s` local recovery datapoint as a public win; reserve public
  updates for a material threshold such as `105`, `120`, or `200 tok/s`, or for
  a clearly useful reproducibility packet.

Immediate things to try next:

1. **One-dispatch MoE parity prototype.**
   Stop optimizing individual activation/quant fragments in isolation. Build a
   one-dispatch replay for the full rows=`1` layer-9 MoE path and require exact
   parity plus `<160 us/layer`.

2. **Exact activation/quant out-variant only after parity root-cause.**
   The fused candidate drift means rounding, scale reuse, or BF16/FP32 ordering
   changed. If this path is revisited, first write a tiny scalar/reference
   fixture that proves identical SiLU, quant scale, clamp, and rounding for
   every activation element before timing.

3. **Whole-token command timeline.**
   Use Level Zero tracing or another command-stream view to count kernel
   launches, barriers, host waits, memory copies, and collective launches for
   one accepted decode token. The route replay says fixed dispatch cost is
   likely the bottleneck; the command stream should quantify it.

4. **Hardware-counter access path.**
   Get `unitrace`, VTune, or another XMX/DPAS metric path working with the
   current driver stack. The timing-derived TOPS are too low, but counters are
   needed to decide whether the limiting factor is DPAS issue, occupancy,
   memory layout, or synchronization.

5. **Upstream route-exact repro packet.**
   Package the layer-9 route-gate baseline, failed fused SiLU+quant candidate,
   M-scaling floor, and target budget into a minimal `vllm-xpu-kernels`
   maintainer packet. The useful artifact is a reproducible B70 small-M MoE
   benchmark with exactness gates, not just a throughput complaint.

Fresh bigger ideas to keep on the board:

1. **Resident transactional verifier lane.**
   Build a target-verifier path that versions KV, GDN/Mamba state, sampler
   metadata, and request counters. Draft tokens run in temporary state; only
   target-accepted tokens commit. This is still the cleanest quality-preserving
   route to `>200 tok/s` if a proposer can keep acceptance high.

2. **Device-side routed-expert work queue.**
   Treat Qwen3.6 MoE decode as a dynamic task problem. A small resident device
   scheduler can consume top-k route rows, issue expert tiles as they become
   ready, and gather outputs without round-tripping through host/PyTorch phase
   boundaries.

3. **Tile-native expert cache with certified manifests.**
   Prepack expert weights into the fastest B70/XMX layout at model load time,
   store checksums and layout metadata, and reuse that packed asset across
   vLLM, oneDNN, or a custom layerlet. This spends VRAM/disk to remove runtime
   layout friction without changing model quality.

4. **Static c1 decode appliance beside vLLM.**
   Prototype a fixed-shape single-request lane that bypasses dynamic scheduling:
   preallocated request state, prebuilt graph or command lists, fixed decode
   buckets, and certified graph cache. Keep vLLM TP4 as the general 32K lane;
   route latency-sensitive c1 traffic to the appliance only after quality proof.

5. **Hybrid TP/EP with hot-expert replication.**
   Use captured route windows to simulate TP4, TP2, EP4, and partial hot-expert
   replication. Implement only if the byte model predicts less communication
   and less small-M underfill than today's TP4 path.

6. **Automated kernel-branch archaeology.**
   Build a route-replay CI script that can bisect `vllm-xpu-kernels`,
   intel-xpu-backend-for-triton, oneDNN grouped-GEMM changes, and local patches
   against the same exactness/timing budget. This lets us mine upstream work
   without accidentally taking quality regressions.

7. **Same-model micro-drafter trained from traces.**
   If the transactional verifier lane works, train a tiny same-tokenizer
   proposer on Qwen3.6 target traces. The draft model can be fast and imperfect
   because the target still verifies every committed token.

8. **Benchmark-plus-reliability publication packet.**
   When a real threshold is crossed, post both speed and reliability: exact
   model ID, command, quality gates, provenance JSON, peak VRAM, single-request
   and aggregate throughput, uptime/soak result, and known failure modes. That
   is more valuable than a one-line tok/s leaderboard row.

## 2026-06-12 Fused Prologue Screen And Bigger Lanes

New route-exact prologue artifact:

- Script: `scripts/bench-qwen36-moe-prologue.py`.
- JSON:
  `data/qwen36-quark-int8-moe-prologue-layer9-routecapture6-20260612aq.json`.
- Markdown:
  `data/qwen36-quark-int8-moe-prologue-layer9-routecapture6-20260612aq.md`.

Result:

- The existing `torch.ops._moe_C.fused_moe_prologue` path exactly matched the
  current `rows_per_expert.zero_()+remap_hidden_states` route expansion on
  layer-9 routecapture6 rows=1 windows:
  `max_expand_abs_diff=0.0` and `max_rows_per_expert_diff=0`.
- Current zero+remap mean: `111.108 us`.
- Fused prologue mean: `106.637 us`.
- Mean component delta: `-4.471 us`.
- Decision: keep fused prologue as a correct building block for a
  one-dispatch or persistent MoE layerlet, but do not promote it as a standalone
  endpoint optimization. The measured win is real but too small to close the
  `~10 ms/token` to `<=5 ms/token` c1 target gap.

Restore/provenance:

- Accepted backend restored as
  `qwen36-tp4-accepted-restored-after-prologue-20260612aq`.
- Restore log:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-prologue-20260612aq.log`.
- Provenance guard:
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-prologue-20260612aq.json`.
- Guard result: all exact sentinels passed.
- Frontdoor status after restore: paused for remote generation, local bypass
  enabled, `0` active and `0` queued generations.

External refresh:

- Localmaxxing still shows only one approved exact-model B70/vLLM row for
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`: our existing
  `99.428 tok/s` c1 row. No public exact-model result currently suggests a
  simple config-only path to `>200 tok/s`.
- That keeps the priority order unchanged: first persistent/fused MoE and
  exact verifier-safe speculation, then production split-lane architecture.

New concrete items to try:

1. **Promote fused prologue into a route-replay layerlet, not the endpoint.**
   Wire `fused_moe_prologue` into a standalone layer replay that includes
   quant, both W8A8 grouped GEMMs, activation, second quant, gather, and
   top-k weighting. The gate is exact parity with `xpu_fused_moe` and a layer
   mean below the `~160 us` non-speculative budget.

2. **Add exact out-variants for quant and gather buffers.**
   The prologue component is now clean, but dynamic quant and gather still
   allocate/return tensors. Add exact out-variant APIs for the remaining small
   MoE buffers before attempting another fusion. The gate is byte-for-byte
   parity plus a route-replay timing win.

3. **Build a fixed-shape decode bundle for one bucket.**
   Compile one p512/o512 or p2k/o512 c1 lane with preallocated KV/GDN metadata,
   certified graph cache, fixed sampling, and no dynamic request scheduler
   churn. This is a truth-serum benchmark: if it does not move c1 speed, the
   kernel path dominates; if it does, production needs a split latency lane.

4. **Run a DPAS/XMX proof packet before more kernel speculation.**
   Use the best available Intel tooling on this host, or add a host-stack lane
   with VTune/unitrace if needed, to prove whether the W8A8 GEMMs are issuing
   the expected INT8 DPAS/XMX instructions at useful occupancy. If counters are
   poor, layout/kernel work outranks scheduler work.

5. **Generate route-aware AOT MoE kernels from captured windows.**
   Instead of a generic grouped-GEMM policy, emit a small set of route-window
   kernels for common layer/token patterns. Each kernel carries a route-shape
   manifest, tensor-hash provenance, and a fallback to the generic exact path.

6. **Prototype a transactional verifier sidecar inside vLLM state.**
   Fork request state, alias immutable KV pages, version mutable GDN/Mamba and
   scheduler metadata, run the current Quark W8A8 target as verifier, and commit
   only accepted draft tokens. This is still the cleanest no-quality-loss way
   to exceed `200 tok/s` if non-speculative MoE cannot halve token latency.

7. **Run a B70 host-stack stress matrix as a separate reliability lane.**
   Keep the accepted model and command fixed while varying only KMD/runtime,
   oneAPI, PyTorch, oneCCL, firmware, and PCIe placement. Measure device-lost
   rate, p512/o128 sentinel parity, and c1 speed. Do not mix this with model or
   kernel changes.

8. **Design production around two service classes if the static lane wins.**
   Keep the stable TP4/32K service for long context and aggregate throughput,
   but route low-latency c1 chat shapes to a certified static lane. This avoids
   sacrificing reliability or context length while still improving interactive
   speed.

9. **Prepare an upstreamable route-exact B70 packet.**
   Package the fused-prologue screen, grouped-GEMM M-scaling data, SiLU+quant
   rejection, routecapture windows, exact expected outputs, launch command, and
   provenance guards. The packet should let Intel/vLLM reproduce the small-M
   MoE floor and target the same bottleneck.

10. **Make quality validation multi-layered by default.**
    For every future speed candidate, run exact sentinel parity, prompt-class
    canaries, route-replay numeric parity, and a small BF16 differential/logit
    rank probe. Token sentinels are necessary, but the BF16/logit lane catches
    near-miss probability drift before it becomes production instability.

## 2026-06-12 Full-Layer Fused Prologue Staged Screen

Artifacts:

- Updated harness: `scripts/bench-qwen36-int8-moe-kernels.py`.
- JSON:
  `data/qwen36-quark-int8-moe-routecapture6-layer9-prologue-staged-20260612ar.json`.
- Markdown:
  `data/qwen36-quark-int8-moe-routecapture6-layer9-prologue-staged-20260612ar.md`.
- Restore log:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-prologuestaged-20260612as.log`.
- Provenance guard:
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-prologuestaged-20260612as.json`.

Result:

- The full-layer fused-prologue staged path is exact against current
  `xpu_fused_moe`: max abs diff `0.0`.
- Mean `xpu_fused_moe`: `288.237 us/layer`.
- Mean scratch `xpu_fused_moe`: `258.465 us/layer`.
- Mean exact manual preallocated staged: `216.361 us/layer`.
- Mean fused-prologue staged: `284.705 us/layer`.
- Restored accepted backend health passed after `64s`; provenance passed all
  exact sentinels; frontdoor remained paused with local bypass enabled and
  `0` active / `0` queued generations.

Decision:

- Do not wire the current exposed `fused_moe_prologue` path into the endpoint.
  It is exact, but it is not a meaningful full-layer speed win.
- Root cause: the prologue path emits `expert_first_token_offset`, while the
  exposed W8A8 grouped-GEMM op consumes `int32 rows_per_expert`. The required
  offset-to-count conversion and current glue erase the prologue-only substep
  win.
- The useful next branch is not another endpoint flag. It is one of:
  offset-native W8A8 grouped GEMM, exact quant/gather out-variant cleanup, or a
  larger one-dispatch/persistent MoE layerlet that lets prologue outputs feed
  downstream work without returning through today's Python/Torch ABI boundary.

Concrete next kernel ideas:

1. **Expose offset-native W8A8 grouped GEMM.**
   Add a W8A8 INT8 grouped-GEMM binding that consumes
   `expert_first_token_offset` directly, matching the lower-level grouped-GEMM
   scheduler shape. Gate it with route-replay exactness and compare it against
   both current `rows_per_expert` GEMM and the staged preallocated lower bound.

2. **Add an offset-to-count XPU helper only as a control.**
   A tiny helper that writes `int32 rows_per_expert` from offsets may recover
   some glue overhead, but it still leaves an extra operation. Use it as an ABI
   control, not as the main bet.

3. **Move quant/gather to out-variant APIs.**
   The staged path is still paying tensor-return allocation boundaries for
   dynamic quantization and gather. Exact out-variants are lower risk than
   arithmetic fusion and should be measured before another endpoint attempt.

4. **Keep the persistent/one-dispatch layerlet as the main non-speculative bet.**
   The full-layer fused-prologue result confirms that small standalone
   prologue savings are insufficient. The next plausible `>200 tok/s` path
   needs to remove multiple phase boundaries at once or amortize target forward
   work with exact verifier-safe speculation.

## 2026-06-12 Fresh Ideas After Offset-ABI Review

Scope:

- Keep the model fixed at
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`.
- Keep the quality bar fixed: no Qwen3.5, no 4-bit/AWQ substitute, no public
  row unless the current Quark W8A8 target verifies exact output.
- Treat public faster rows as architecture clues only. A fresh Localmaxxing
  query for `Qwen/Qwen3.6-35B-A3B` shows much faster public rows, but the top
  entries use different hardware and/or different fidelity classes such as
  MQ4-AWQ, NVFP4, Q4_K_M, speculative decoding, or MTP. They do not answer
  whether our B70 Quark W8A8 path should be faster without changing the model.
- The B70-specific filtered query still has our 4x B70 Quark W8A8 vLLM row at
  the top of visible Arc Pro B70 results for this family, with the closest B70
  comparables being llama.cpp Q4 variants. This supports publishing only
  material future wins, not tiny recovery refreshes.

External signals folded into this refresh:

- Localmaxxing model-family leaderboard:
  `https://localmaxxing.com/api/leaderboard?hfId=Qwen%2FQwen3.6-35B-A3B&limit=10`.
- Localmaxxing Arc Pro B70 filtered rows:
  `https://localmaxxing.com/api/leaderboard?hfId=Qwen%2FQwen3.6-35B-A3B&hardwareName=Arc%20Pro%20B70&limit=20`.
- vLLM/XPU B580 tuning question:
  `https://github.com/vllm-project/vllm/issues/35638`.
- Intel Triton-XPU grouped-GEMM performance epic:
  `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`.
- oneDNN grouped-memory grouped-GEMM documentation:
  `https://uxlfoundation.github.io/oneDNN/dev_guide_matmul.html#grouped-gemm-support`.
- PyTorch persistent grouped-GEMM writeup:
  `https://pytorch.org/blog/accelerating-moes-with-a-triton-persistent-cache-aware-grouped-gemm-kernel/`.
- vLLM XPU support matrix:
  `https://docs.vllm.ai/en/stable/models/hardware_supported_models/xpu/`.

New concrete things to try:

1. **Offset-native W8A8 grouped-GEMM prototype, but measure the loop.**
   The local `vllm-xpu-kernels` W8A8 grouped-GEMM path currently takes
   `int32 rows_per_expert` and computes row/tile prefixes inside the kernel.
   A binding-only change is not enough; the prototype needs a launcher/kernel
   variant that consumes `expert_first_token_offset` directly. The first gate
   is not endpoint speed, but a route-replay comparison against:
   current rows-per-expert GEMM, offset-to-count helper, and exact staged lower
   bound. If the kernel still loops all experts per workgroup, this may save
   glue but not the `2x` target.

2. **oneDNN grouped-memory replay as a control, not a migration.**
   oneDNN's grouped memory uses offsets for variable group boundaries, matching
   the prologue output shape more naturally than the current W8A8 exposed ABI.
   Build a narrow replay harness for one layer/window with identical Quark W8A8
   math or a clearly labeled BF16/int8-control variant. If it is slower, close
   the lane. If it is faster, mine its scheduling/layout for the custom kernel.

3. **Route-window persistent worker proof before endpoint downtime.**
   The fastest plausible no-speculative path is still a persistent or
   one-dispatch layerlet. Start with one layer, one route window, and a fixed
   hot/cold queue. It must consume prologue offsets directly, run both W8A8
   GEMMs, preserve exact dynamic quant behavior, and scatter/gather without a
   Python/Torch allocation boundary.

4. **W8A8 kernel roofline packet.**
   Use unitrace, VTune, or the lowest-friction Intel counter path to capture
   DPAS/XMX utilization, occupancy, memory bandwidth, command count, and launch
   gaps for `gemm1_w8a8`, `gemm2_w8a8`, and the full MoE custom op. This tells
   us whether the current bottleneck is math utilization, small-M scheduling,
   memory/layout, or graph/host control overhead.

5. **Static c1 lane as a separate product shape.**
   Prototype a fixed-bucket c1 runner with certified graph cache, preallocated
   request/KV/GDN metadata, fixed sampling, and no dynamic scheduler churn. Do
   not let it replace general TP4/32K serving. Use it to answer whether a
   production split-lane architecture can improve interactive speed without
   weakening long-context reliability.

6. **Target-verified speculation as the parallel track.**
   Keep MTP/DFlash/ngram/tree proposers on the board only behind a resident
   target verifier. The key design is a transactional request-state fork:
   alias immutable KV, version mutable GDN/Mamba/scheduler metadata, score
   candidates with the current Quark W8A8 target, then commit only verified
   tokens. Without this, faster public speculative rows are not comparable.

7. **Current-model micro-drafter, not external-model drafter.**
   Train or fit a tiny same-tokenizer proposer from accepted Qwen3.6 traces,
   but never trust it directly. Its only role is to feed the target verifier.
   This may outperform generic n-gram on prompt classes where n-gram collapsed,
   while preserving the exact target output.

8. **Route-class autotuner.**
   Convert routecapture windows into classes: concentrated hotset, broad
   hotset, cold-heavy, repetitive, math/code/natural. For each class, choose a
   policy: full-table current GEMM, active-only table, hot-cache persistent
   queue, oneDNN control, or custom layerlet. This avoids another global policy
   that wins one layer/window and loses another.

9. **Host-stack reliability matrix with speed as a secondary metric.**
   The repeated device-lost class means a production path needs a separate
   reliability lane: fixed accepted command, fixed graph cache, fixed sentinel
   probes, then vary KMD/runtime/oneAPI/PyTorch/oneCCL/PCIe placement. A stack
   that is 3% faster but less stable is rejected for production.

10. **Upstreamable B70 performance packet.**
    Package the prologue exactness, prologue-staged negative, M-scaling gate,
    hotrep negative, route windows, W8A8 shapes, provenance guard, and the
    public B70 leaderboard context. The ask to Intel/vLLM should be precise:
    "B70 W8A8 small-M MoE decode needs offset-native/persistent grouped GEMM",
    not a broad "XPU is slow" report.

Bigger, bolder ideas to keep visible:

1. **Graph-resident decode loop.**
   Move the whole steady-state c1 decode step into a resident command graph or
   persistent loop: attention/GDN, routing, MoE, collectives, logits, sampling,
   and metadata update. Host only receives committed tokens. This is a large
   engineering branch, but it attacks launch gaps, metadata copies, and
   scheduler churn simultaneously.

2. **Verifier-owned commit protocol.**
   Redesign speculative decode around the verifier, not around the proposer.
   The verifier owns token-state, KV/GDN state, rollback logs, and streaming
   commit. Proposers become replaceable plugins. This could unify MTP, DFlash,
   n-gram, trace-trained drafter, and future hardware-assisted draft paths.

3. **MoE-only hybrid parallelism.**
   Keep attention replicated or TP-light, but route experts with EP/hot-rep
   semantics only where captured routes justify it. The simulator already
   showed hot64 replication can reduce movement pressure but not compute. Pair
   it with persistent/tile-native MoE before attempting any endpoint rewrite.

4. **Tile-native packed-weight artifact registry.**
   At model load or offline prep time, produce per-layer packed W8A8 expert
   artifacts for the fastest B70 layout. Store tensor hashes, tile policy,
   graph-cache compatibility, and replay parity. This turns expensive runtime
   layout work into a certified artifact like the graph cache.

5. **Latency-market production router.**
   Production may not be one backend. Keep general TP4/32K for long-context and
   capacity, add one or more low-context static lanes for c1 chat, and route by
   request shape. Aggregate throughput stays secondary to c1 speed, but this
   makes both measurable instead of forcing one universal compromise.

## 2026-06-12 Additional Bigger Bets After Offset Prototype

Current new local branch:

- A source prototype is in progress for
  `cutlass_grouped_gemm_w8a8_int8_offsets_interface` in local
  `vllm-xpu-kernels`. It adds an offset-native W8A8 grouped-GEMM route that
  accepts `expert_first_token_offset` directly from the fused prologue path.
- This is not yet a speed result. It needs a C++ build, op-presence check,
  route-replay exactness gate, and accepted-backend restore/provenance guard if
  the XPUs are disturbed.
- Expected upside is modest if the kernel still loops across all experts per
  workgroup. The real decision metric is whether offset-native routing removes
  enough glue to make the fused prologue path approach the exact preallocated
  staged lower bound. If it does not, move immediately to persistent/one-dispatch
  MoE rather than polishing the ABI.

Additional things to try:

1. **Offset-op build gate plus route-replay kill switch.**
   Build the offset-native W8A8 op in `vllm-xpu-kernels`, run only the
   routecapture6 layer-9 rows=1 exactness/perf replay, and reject it quickly if
   it cannot beat fused-prologue staged by a material margin. Keep this as a
   one-maintenance-window test, not a multi-day branch.

2. **Expert-loop removal variant.**
   If offset-native GEMM is exact but only a small win, inspect whether the
   kernel still pays a full-expert loop for empty experts. The next variant
   should consume a compact active-expert list plus offsets, so workgroups skip
   cold experts instead of merely seeing zero rows.

3. **Fused hotset plus compact-cold single dispatch.**
   The top-64 hotset floor model says a naive hot/cold split risks launch
   overhead. Try a single dispatch that has fast hot expert tables plus a
   compact cold fallback queue inside the same kernel or layerlet. That preserves
   exact weights while avoiding the two-launch tax.

4. **Route-class graph library.**
   Precompile a small set of graph/layerlet variants by route class:
   concentrated hotset, broad hotset, cold-heavy, repetitive, math/code, and
   natural-chat. At runtime, choose the cheapest exact variant from the current
   route histogram. This is more realistic than a global hot-expert layout.

5. **Layerlet code generator.**
   Generate C++/SYCL or Triton-XPU layerlet code from captured layer metadata:
   expert shapes, W8A8 scales, hotset table, offsets, top-k, and output gather.
   The generated artifact can be specialized per layer while still checking
   tensor hashes and exact replay parity.

6. **MoE microservice inside the process.**
   Treat MoE as a persistent device service with resident queues and buffers,
   called from vLLM through a narrow ABI. The service owns hotset packing,
   active-expert scheduling, W8A8 GEMMs, activation, down projection, and
   gather. vLLM sees the same tensor result, but the device side avoids repeated
   allocation and launch setup.

7. **Single-card and TP2 truth-serum runs.**
   Run controlled c1 probes on single-card or TP2 variants only if memory allows
   the accepted model posture. The goal is not production capacity; it is to
   quantify how much TP4 collectives and graph metadata hurt one-request
   latency. If TP2 c1 is materially faster, revisit production as split lanes
   instead of forcing TP4 to do everything.

8. **Token-step command-list capture.**
   Capture or synthesize one full accepted decode token as a Level Zero command
   list: metadata updates, GDN/attention, MoE, allreduces, logits, sampler, and
   output copy. Replay it as a fixed-shape artifact to separate raw kernel
   latency from vLLM scheduler/control latency.

9. **BF16 shadow differential on a tiny suite.**
   Keep Quark W8A8 as the production target, but periodically compare candidate
   kernels against BF16 fallback on short prompts for logit-rank and semantic
   drift. This is a guardrail for subtle arithmetic changes that pass current
   token sentinels but move probability mass.

10. **Speculative verifier escrow for bonus/reject state.**
    The earlier no-bonus diagnostics exposed how hard rollback is. Build an
    explicit verifier-owned escrow for candidate tokens, token IDs, block-table
    updates, GDN/Mamba state, and streaming output. This is the minimum viable
    substrate for safe MTP/DFlash/tree speculation.

11. **Self-draft from shallow target layers.**
    Instead of an external model, try a proposer that reuses early target-model
    layers or a small adapter trained from target traces. The final output still
    comes only from the full Quark verifier. This may preserve tokenizer/style
    alignment better than generic n-gram and avoids Qwen3.5 substitution.

12. **Prompt-shape admission control.**
    For production, define a latency lane that accepts only shapes with known
    certified graph/cache/provenance and route-class behavior. Everything else
    goes to the general TP4 lane. This is not a quality compromise; it is a
    scheduling/product decision that protects c1 latency.

13. **Upstream performance challenge packet.**
    Publish the smallest route-exact W8A8 MoE repro that shows the gap:
    current grouped GEMM, exact staged lower bound, prologue-staged negative,
    offset prototype result, hotset floor model, and DPAS/XMX counters. This is
    more likely to attract useful Intel/vLLM help than a full server log.

14. **Reliability soak tied to every speed result.**
    Any candidate that touches kernels, graph cache, timing, or metadata needs a
    soak recipe: repeated load, p512/o128 c1, c4 aggregate, provenance sentinels,
    `xpu-smi ps`, and device-lost count. A fast but fragile backend is not a
    production candidate.

## 2026-06-12 Offset GEMM Prototype Gate

What was tested:

- Prototype source patch captured at
  `patches/vllm-xpu-kernels-w8a8-offset-gemm-prototype-20260612.patch`.
- The first local rebuild used a oneAPI 2026 runtime and linked against
  `libsycl.so.9`; reject that artifact for the accepted vLLM runtime. The
  accepted-compatible rebuild used oneAPI 2025.3, linked against
  `libsycl.so.8`, imported cleanly, and passed a basic XPU sync check.
- Route-exact layer-9 routecapture6 rows=1 replay passed exact output parity
  against current `xpu_fused_moe` (`max_abs_diff=0.0`). The offset path is a
  real component win in microbench:
  - `fused_prologue_offset_gemm_total_us_mean`: `213.233 us`
  - `fused_prologue_staged_total_us_mean`: `285.787 us`
  - `preallocated_staged_total_us_mean`: `218.158 us`
  - `xpu_fused_moe_scratch_total_us_mean`: `256.611 us`
- Serving gate failed. The offset-built backend reached `/health`, but the
  first provenance request crashed the engine with
  `UR_RESULT_ERROR_DEVICE_LOST` at `block_table.copy_to_gpu(num_reqs)`, then
  printed `UR_RESULT_ERROR_OUT_OF_RESOURCES` during shutdown. Do not promote
  this endpoint. Serving logs:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-offset-gemm-20260612af.log`
  and
  `data/qwen36-quark-int8-tp4-accepted-restored-after-offset-rollback-20260612ag.log`.
- Live rollback is complete: pre-offset `_xpu_C`, grouped GEMM, and GDN helper
  libraries were restored; the offset op is absent from the live runtime; the
  accepted backend passed exact provenance sentinels after rollback in
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-offset-rollback-20260612ag.json`.

Immediate follow-ups from this gate:

1. **Microbench-only offset plugin.**
   Split the offset prototype out of the full serving library and load it only
   for route-replay tests. This isolates whether the device-lost failure comes
   from device-image size, registration, or the serving call path.

2. **Narrow offset ABI.**
   Rebuild a smaller variant that exposes only the new offset path and avoids
   broad template duplication or ABI churn around the existing count-based
   W8A8 op. If the narrower image serves, promote it through the standard
   quality ladder.

3. **Active-expert list, not just offsets.**
   Check whether the kernel still loops over all experts. If it does, add a
   compact active-expert list so rows=1 decode skips cold experts instead of
   paying an empty-expert loop.

4. **One-dispatch MoE layerlet.**
   The offset microbench nearly reaches the manual preallocated lower bound,
   but the end-to-end target still needs millisecond-level savings. Move beyond
   ABI cleanup toward a single dispatch or persistent layerlet that owns
   prologue, quant, grouped GEMM, activation, down projection, and gather.

5. **First-token metadata failure minimizer.**
   Build a tiny post-load first-completion repro around block-table and graph
   metadata copies. The repeated `block_table.copy_to_gpu` device-lost class is
   now a production blocker category, not just a one-off failure.

6. **Promotion ladder for every kernel candidate.**
   Require this order before any endpoint exposure: import and XPU sync,
   route-microbench exactness, isolated one-token model execution, provenance
   sentinels, 10-minute c1 soak, then c4 aggregate. The offset prototype passed
   only the first two stages.

Larger ideas added after this result:

1. **Device-image budget analysis.**
   Track `.so` size, generated device images, persistent-cache entries, and
   first-use compile behavior before and after each kernel addition. A "small"
   template change may still create a serving-risky XPU image.

2. **Counter-proven small-M DPAS packet.**
   Pair the route replay with XMX/DPAS counters, EU occupancy, memory
   bandwidth, and kernel-launch timing. If offset GEMM is still math-starved at
   rows=1, persistent scheduling is mandatory.

3. **Graph-resident metadata update.**
   Stop treating block-table/GDN metadata copies as fixed overhead. Prototype a
   graph-resident or dirty-copy update path with a stability soak before speed
   timing.

4. **Persistent routed-expert worker.**
   Keep a resident device worker per layer or per hotset that consumes compact
   route tasks and writes exact outputs. This attacks both launch overhead and
   empty-expert work, at the cost of a larger engineering branch.

5. **Target-verified speculation as the high-upside track.**
   If non-speculative MoE work cannot remove roughly `5 ms/token`, the likely
   path to `>200 tok/s` c1 is verifier-owned speculation. The target model must
   score and commit tokens; any drafter remains replaceable and untrusted.

Public context:

- The Localmaxxing Arc Pro B70/Qwen view currently shows our quality-gated
  W8A8 result `cmq9ifq0500b0r8012f27j1xl` at about `99.77 tok/s`, ahead of the
  prior exact-model row. No new result was submitted for this offset prototype
  because it is not serving-safe.
- Faster public B70 Qwen rows using Q4/llama.cpp or other lower-fidelity
  setups are useful architecture clues, not quality-equivalent targets for
  this INT8/Quark production lane.

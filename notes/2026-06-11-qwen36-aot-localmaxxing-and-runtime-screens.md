# Qwen3.6 35B Quark INT8: AOT Census, Localmaxxing Intake, and Runtime Screens

Date: 2026-06-11

## Baseline

Target model stayed fixed throughout:

- `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- 4x Intel Arc Pro B70 32GB
- vLLM XPU TP4
- Quark W8A8 INT8 weights, BF16 runtime activations
- 32K context
- prefix caching disabled
- XPU PIECEWISE graph capture with graph-safe custom all-reduce path

Fresh accepted restore passed the frontdoor quality suite after a prior long-lived process showed repeat/copy instability:

- stale-process failure artifact: `data/qwen36-quark-int8-tp4-noprefix-current-frontdoor-quality-rerun32-20260611.json`
- stale-process speed refresh: `data/qwen36-quark-int8-tp4-noprefix-current-refresh-r4-20260611.json`
- `data/qwen36-quark-int8-tp4-noprefix-accepted-clean-frontdoor-quality-rerun8-20260611.json`
- `data/qwen36-quark-int8-tp4-noprefix-accepted-restored-frontdoor-quality-rerun8-20260611.json`

Clean accepted speed baseline:

| Recipe | Quality | Corrected tok/s | E2E tok/s | TTFT ms | Artifact |
| --- | --- | ---: | ---: | ---: | --- |
| Accepted TP4 c48 | pass | 99.428 | 98.163 | 76.454 | `data/qwen36-quark-int8-tp4-noprefix-accepted-clean-single-r4-20260611.json` |

## AOT Census

Added `scripts/census-qwen36-aot-ops.py` to scan generated vLLM/Inductor cache files for actual custom-op calls and local op neighborhoods. The current accepted cache shows:

- `vllm_all_reduce`: 1364
- `int8_gemm_w8a8`: 1804
- `per_token_quant_int8`: 1368
- `moe_forward_shared`: 368
- `gdn_attention_core`: 480
- `moe_shared_add_allreduce`: none in accepted cache

Artifact:

- `data/qwen36-quark-int8-tp4-noprefix-current-aot-census-20260611.json`

Interpretation: the remaining performance work is not in the old c10d path. The live graph has many XPU INT8 dense boundaries and many vLLM custom all-reduce boundaries. Larger exact boundaries around MoE output, dense quant/GEMM/all-reduce, and GDN projection are more promising than another isolated one-op replacement.

## Runtime Screens

All screens used the same model and quantization. No quality-loss knob was accepted.

| Candidate | Result | Corrected tok/s | E2E tok/s | TTFT ms | Artifact |
| --- | --- | ---: | ---: | ---: | --- |
| MoE shared add + all-reduce custom op | reject, slower | 99.017 | 97.757 | 76.708 | `data/qwen36-quark-int8-tp4-noprefix-moe-shared-addar-single-r4-20260611.json` |
| TP2, GPUs 0,1, max seqs 24 | reject, slower | 91.247 | 90.118 | 81.296 | `data/qwen36-quark-int8-tp2-noprefix-seqs24-single-r4-20260611.json` |
| TP4, max seqs 24 | reject, slower | 98.888 | 97.618 | 77.441 | `data/qwen36-quark-int8-tp4-noprefix-seqs24-single-r4-20260611.json` |
| `CCL_WORKER_COUNT=2` | reject, startup fail | n/a | n/a | n/a | log: `/tmp/qwen36-quark-int8-tp4-32k-noprefix-cclw2-20260611.log` |
| `CCL_REDUCE_SCATTER_MONOLITHIC_KERNEL=1` | reject, neutral/slower | 99.364 | 98.093 | 76.839 | `data/qwen36-quark-int8-tp4-noprefix-cclrsmono-single-r4-20260611.json` |

MoE shared add + all-reduce did enter the graph and passed quality, so the experiment was valid. The updated census for that cache found:

- `moe_shared_add_allreduce`: 336
- `vllm_all_reduce`: 348
- `moe_forward_shared`: 208

Artifact:

- `data/qwen36-quark-int8-tp4-noprefix-moe-shared-addar-aot-census-20260611.json`
- `patches/vllm-qwen36-moe-shared-add-allreduce-customop-rejected-20260611.patch`

`CCL_WORKER_COUNT=2` failed during graph capture with:

```text
oneCCL: coll.cpp:1421 ccl_allreduce_impl: EXCEPTION: |CCL_SYCL| sched algorithms do not support sycl_graph recording, please use sycl_algorithms
```

Do not combine `CCL_WORKER_COUNT=2` with the current XPU graph/collective capture path until the matching oneCCL SYCL algorithm route is identified.

## Localmaxxing Intake

Pulled public data first, then submitted the best clean quality-gated TP4 result after a successful dry run.

Artifacts:

- `data/localmaxxing-b70-qwen-leaderboard-refresh-20260611.json`
- `data/localmaxxing-qwen36-quark-w8a8-int8-refresh-20260611.json`
- `data/localmaxxing-qwen36-quark-w8a8-int8-tp4-noprefix-p512n512-20260611.payload.json`
- `data/localmaxxing-qwen36-quark-w8a8-int8-tp4-noprefix-p512n512-20260611.response.json`
- `data/localmaxxing-qwen36-quark-w8a8-int8-after-submit-20260611.json`

Submitted result:

- Localmaxxing ID: `cmq8yhxvo001ipb0149aoa79o`
- Status: `APPROVED`
- `tokSOut`: `99.428358`
- `ttftMs`: `76.454061`
- `tokSTotal`: `196.325273`
- context: 32768
- prompt/output: p512/n512
- batch/concurrency: 1
- metric note: `tokSOut` is corrected steady-state output throughput after first streamed text chunk; this run did not submit peak VRAM because the measurement used `--skip-vram`.

Public exact-model count after submission for `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`: `1`.

Useful B70/Qwen comparables:

- `Qwen/Qwen3.6-35B-A3B` on one B70 with llama.cpp Q4_K_M: `70.35 tok/s`, ctx8192, TTFT `203 ms`, command includes `-fa 1 -ctk q8_0 -ctv q8_0 -t 1`.
- `Qwen/Qwen3.6-35B-A3B` on four B70 with independent llama.cpp slots: `68.8 tok/s`, ctx32768, one instance per card.

Our clean TP4 vLLM Quark W8A8 run is above those public decode numbers and is now the first public exact-model Localmaxxing row. A stronger follow-up submission should add longer repeat-quality, r8/r10 speed, and measured peak VRAM.

## Web Research Leads

- vLLM Arc Pro B-series blog: https://vllm.ai/blog/2025-11-11-intel-arc-pro-b
  - Relevant because it confirms Arc Pro B-series is an active vLLM XPU optimization target, including multi-GPU scaling and PCIe P2P.
  - The most important hint is the MoE section: Intel calls out persistent single-kernel MoE loops, dynamic work balancing, and prepacked formats as first-class Arc speed levers. That aligns with our census: tiny wrappers around MoE output were not enough; the next real win probably needs persistent MoE/GEMM scheduling or repacked XMX-friendly weights.
- vLLM speculative decoding docs: https://docs.vllm.ai/en/latest/features/speculative_decoding/
  - Relevant because vLLM treats MTP, EAGLE, draft-model, PARD, and custom proposer paths as latency-focused methods, with n-gram/suffix as lighter but lower-gain options. Our n-gram path already proved the quality upside is possible but found a stability bug; model-based speculation is the bigger no-quality-loss lever if the Quark verifier remains final authority.
- vLLM expert parallel docs: https://docs.vllm.ai/en/latest/serving/expert_parallel_deployment/
  - Relevant because EP is designed to increase MoE locality by placing experts on separate GPUs instead of sharding every expert with tensor parallelism. CUDA-oriented dependencies do not directly transfer to XPU, but the architecture direction matters for Qwen3.6 A3B: pure TP4 creates many decode collectives that may be structurally wrong for single-token MoE latency.
- vLLM issue 41663: https://github.com/vllm-project/vllm/issues/41663
  - Relevant because it documents B70/XPU TP initialization and host-stack sensitivity. Our TP2 did serve, but it was slower for this model.
- B70 llama.cpp tuning kit: https://github.com/Hal9000AIML/arc-pro-b70-ubuntu-gpu-speedup-bugfixes
  - Relevant because independent B70 work points at MoE, Q8 reorder, Xe2 tile sizing, small-matmul, and runtime workaround classes as large speed levers.
- B70 setup repo: https://github.com/Hal9000AIML/arc-pro-b70-inference-setup-ubuntu-server
  - Relevant as a comparison point for multi-slot per-card deployment versus one sharded vLLM model.
- B70 benchmark repo: https://github.com/PMZFX/intel-arc-pro-b70-benchmarks
  - Relevant because it is another public B70 measurement set. It reinforces that single-card Qwen3.6-class decode can look reasonable in llama.cpp/Vulkan/SYCL paths, and it gives us another reason to run a strict 8-bit same-model engine bakeoff instead of assuming vLLM/XPU is the only viable serving stack.
- Qwen3.6 speculative-decoding experiment repo: https://github.com/thc1006/qwen3.6-speculative-decoding-rtx3090
  - Relevant because it reports that n-gram and draft-model speculation can fail to produce net gains even on CUDA. That matches our quality-first stance: speculation is still the biggest potential single-user lever, but only verifier-parity results count.
- Intel oneCCL environment docs: https://www.intel.com/content/www/us/en/docs/oneccl/developer-guide-reference/2021-9/environment-variables.html
  - Relevant for `CCL_REDUCE_SCATTER_MONOLITHIC_KERNEL`, fusion, and short-size/worker collective tuning. The monolithic reduce-scatter/all-reduce path was quality-safe but not a speed win today.

## Future Ideas Queue

Near-term no-quality-loss tests:

1. Run a stronger accepted benchmark pack: r8/r10 speed, repeat32/repeat64 quality, and measured peak VRAM. If clean, submit a richer Localmaxxing follow-up or update notes with why the current public row remains the canonical row.
2. Use the census script to compare accepted versus each candidate cache before and after speed runs. Reject no-op candidates earlier and record whether a candidate actually changed the generated graph.
3. Test oneCCL knobs that do not switch to non-graph scheduler algorithms:
   - `CCL_MAX_SHORT_SIZE` for small all-reduce messages.
   - `CCL_FUSION=1` with very conservative thresholds, only if it survives graph capture.
   - `CCL_ALLGATHERV_MONOLITHIC_PIPELINE_KERNEL=1` only if a census or trace shows allgather/allgatherv in the live path.
4. Build exact microbenchmarks around dense `per_token_quant_int8_xpu -> int8_gemm_w8a8 -> all_reduce` shapes from the AOT cache.
5. Investigate GDN projection fusion where duplicated qkvz/ba quantization and INT8 GEMMs dominate repeated small graph regions.
6. Revisit MoE at a lower level than the rejected Python custom-op boundary. The Python boundary was valid but did not remove enough communication/launch work; a real win likely needs XPU-kernel epilogue or MoE prepare/finalize changes.
7. Test TP4 rank/GPU ordering permutations with the same accepted recipe. The B70 topology and oneCCL ring may care about device order even when raw XCCL tests pass.
8. Run a paired accepted-vs-candidate benchmark with VTune/oneprof/Level Zero tracing for p512/n128 and p512/n512. The goal is an operator-level wall-time pie chart before writing more kernels.
9. Capture a production-shaped aggregate run alongside single-request runs: c1/c2/c4/c8/c16/c32/c48 with quality smoke afterward. Single request remains primary, but production settings should not silently destroy aggregate throughput.

Larger branch ideas:

1. Compare vLLM Quark W8A8 against a native Intel/vLLM-friendly INT8/W8A16 or W8A8 checkpoint if one appears for Qwen3.6 35B, with strict quality parity.
2. Evaluate whether the official Qwen3.6 FP8 snapshot's MTP tensors can be used for speculative decode without changing the current Quark INT8 quality profile. Current Quark snapshot does not expose an obvious `mtp.*` path.
3. Keep the llama.cpp B70 work as an implementation clue, not as a model/quantization switch. The user's target remains Qwen3.6 35B, 8-bit, speed plus near-zero quality loss.
4. Try verifier-preserving model speculative decoding with a Qwen3.6-family draft model. This should preserve final quality if vLLM accepts/rejects with the current Quark verifier, but previous n-gram speculation had stability issues, so require repeat64 and long-context gates before any speed claim.
5. Prototype an expert-parallel or hybrid-parallel layout instead of pure TP4. Qwen3.6 A3B is MoE; sharding every dense boundary across four cards creates many all-reduces. A layout that replicates dense/attention where possible and partitions experts may reduce decode collectives, but it is a larger vLLM architecture project.
6. Explore two TP2 replicas for production aggregate only. TP2 was slower for one request, but two independent TP2 replicas may produce better aggregate capacity and fault isolation than one TP4 service. This is not a single-request win, so keep it separate from the main speed metric.
7. Create a persistent ahead-of-time repacked INT8 weight cache for XPU tile-friendly layouts. If current Quark loading/runtime still repacks or uses suboptimal layout per graph shape, persistent repacking could reduce both startup and decode overhead.
8. Build a decode-only fused decoder-layer boundary for small token counts. The AOT census suggests many repeated tiny boundaries; a custom boundary around attention/GDN projection, MoE, residual, and collectives for `num_tokens <= 4` could reduce Python/dispatcher/graph fragmentation, but correctness risk is high.
9. Investigate a same-model llama.cpp SYCL Q8_0 or native 8-bit route as an engine comparison, not a replacement. The public B70 llama.cpp Q4 rows prove that engine can be fast on B70; an 8-bit Qwen3.6 test would tell us whether vLLM/XPU is leaving performance on the table.
10. Try a host/root policy branch only after making it reversible: persistent GPU performance power state, ASPM/runtime power disabled, NUMA pinning, CCL interface pinning, and thermal/fan policy. Prior audit did not prove PCIe is the bottleneck, but host policy can still create jitter.

Bold/high-risk ideas that need strict proof before adoption:

1. Build an exact XPU fused MoE epilogue that combines expert output finalize, shared-expert add, residual, and all-reduce semantics in one registered op. The rejected Python wrapper proved the boundary alone is insufficient; the win needs fewer launches and less intermediate traffic.
2. Implement a tiny-message all-reduce path specialized for the exact BF16 hidden sizes seen in the cache. Raw oneCCL latency may not be the bottleneck, but the graph contains enough collectives that a specialized path could matter if it is graph-safe.
3. Use a verifier-preserving draft model or MTP path to chase 120-150 tok/s without changing final model quality. The quality condition is strict: final token stream must pass baseline hashes/repeat gates, not just look plausible.
4. Investigate expert activation locality: reorder/pack experts or route metadata so active experts for single-token decode hit fewer cards or fewer fragmented memory regions. This could be a real MoE-specific B70 win, but it requires careful parity tests.
5. Prototype a custom scheduler mode for single-stream latency that keeps the accepted graph but strips server-side overhead around streaming, metrics, and request lifecycle. The model core is near 100 tok/s; cutting frontend and stream overhead could improve end-to-end user experience even if kernel tok/s is flat.

## Bigger Bets To Track

These are intentionally larger than ordinary env-var sweeps. The current accepted recipe is probably already close to the easy vLLM/XPU knob ceiling, so the path to `>200 tok/s` single-request decode likely needs one of these.

1. Verifier-preserving speculation as the main quality-safe multiplier.
   - Why it might matter: it is the only near-term path that can plausibly double perceived decode speed without changing the final accepted model distribution.
   - Concrete variants:
     - fix the n-gram mixed prefill/spec decode crash and corruption first, because it is the smallest reproduction.
     - test Qwen3.6-native MTP if the official FP8 MTP tensors can be used as an auxiliary proposer while the current Quark INT8 model remains the verifier.
     - if no native MTP path works, try a same-family Qwen3.6 draft model or a custom proposer class; reject anything that uses Qwen3.5 or 4-bit.
   - Proof required: repeat64 or stronger, long-context needle, exact canary hashes against the current verifier, and at least c1/c2/c4 reliability because the prior failure involved mixed scheduling state.

2. XPU expert-parallel or hybrid-parallel Qwen MoE layout.
   - Why it might matter: pure TP4 shards dense and expert work across every card, then pays collectives repeatedly during single-token decode. A MoE-aware layout could replicate cheap dense pieces, place experts locally, and exchange less data per token.
   - First step: map Qwen3.6 layer/expert sizes and memory per expert to see whether full or partial expert replication fits on four 32GB B70s with 32K KV.
   - Proof required: same final model weights and same output quality, speed at c1 and aggregate c8/c16, plus oneCCL/all-to-all stability under graph capture.

3. Persistent fused MoE kernel for the actual Qwen3.6 INT8 path.
   - Why it might matter: the Intel Arc Pro guidance points at persistent MoE loops and dynamic work balancing. Our rejected MoE shared-add/all-reduce wrapper changed graph boundaries but did not remove enough launches or memory traffic.
   - First step: build a standalone shape-exact MoE microbench from the AOT census and implement a persistent grouped-GEMM/epilogue prototype outside the server before wiring it into vLLM.
   - Proof required: bitwise or tolerance-matched parity against the current staged path on routed expert outputs, then full endpoint quality parity.

4. Tile-friendly persistent INT8 repack cache.
   - Why it might matter: the model's 8-bit weights are quality-acceptable, but their stored layout may not be the fastest layout for B70 XMX/DPAS. A once-per-model repack into native tile order could reduce runtime memory traffic without changing mathematical weights.
   - First step: identify whether `int8_gemm_w8a8` consumes prepacked layouts or repacks/transposes in hot paths; if hot-path layout conversion exists, move it to model-load time and cache it on disk.
   - Proof required: identical dequantized weights and output parity, startup/load timing, and no extra VRAM pressure that breaks 32K context.

5. Decode-only static runner for batch-1 latency.
   - Why it might matter: vLLM is optimized for serving, but our goal prioritizes single-request speed first. A special path with preallocated KV, static graph replay, fewer scheduler transitions, and controlled streaming could quantify server overhead versus model-core overhead.
   - First step: create an offline `LLM.generate` or direct model-runner harness that reuses the same weights/kernels and compares backend core tok/s against the OpenAI streaming endpoint.
   - Proof required: exact tokenizer/template parity, same generation settings, and a route back into production if the delta is real.

6. Same-model engine bakeoff, not a quant downgrade.
   - Why it might matter: public B70 reports suggest llama.cpp/Vulkan/SYCL can be competitive on Qwen3.6-like workloads, but most public rows use 4-bit. A strict 8-bit same-model engine comparison would tell us whether vLLM/XPU overhead or the model/quant itself is the blocker.
   - First step: find or build an 8-bit Qwen3.6 35B GGUF/engine artifact that is not AWQ/4-bit and run the same quality suite. Treat it as a diagnostic unless it can serve 32K and production concurrency.
   - Proof required: no quality regression versus BF16/current Quark gates, exact prompt template parity, and measured VRAM/headroom.

7. Host and topology validation as a separate reliability branch.
   - Why it might matter: host policy is unlikely to double tok/s by itself, but unstable power/PCIe/NUMA settings can hide real kernel gains behind jitter and device-lost incidents.
   - First step: root `lspci -vv` validation, persistent performance power profile, runtime power `on`, BIOS/ASPM check, NUMA pinning, and thermal/fan logging, all behind reversible scripts.
   - Proof required: before/after variance reduction across accepted recipe r10/r20 and no degradation in stability.

8. Upstream-focused XPU backend gap audit.
   - Why it might matter: if vLLM/XPU is missing a true W8A8 or W8A16 fast path for this exact MoE shape, local patches can chase symptoms forever. We should produce minimal repros that Intel/vLLM maintainers can act on.
   - First step: turn AOT shapes into three small repros: dense W8A8 GEMM, routed MoE grouped GEMM, and graph-safe collective fusion.
   - Proof required: each repro includes shape, command, expected throughput, current throughput, and a no-secret artifact suitable for a GitHub issue or upstream PR.

Priority call:

1. Do next: speculation reliability/MTP feasibility, because it is the only realistic `2x` lever that can preserve final-model quality.
2. Do in parallel: shape-exact MoE and dense INT8 microbenches, because they produce durable upstreamable artifacts even if speculation stalls.
3. Keep ready: accepted r10 + peak VRAM + repeat64 quality pack, so every claimed win can be published cleanly.

## Public Follow-Up And Bolder Ideas

Added after checking fresh public Localmaxxing rows and current Arc/XPU optimization threads on 2026-06-11. None of these relax the target: Qwen3.6 35B, 8-bit/high fidelity, current Quark INT8 verifier for accepted quality claims, no Qwen3.5 detours, no 4-bit promotion.

Fresh external signals:

- Localmaxxing now has Qwen3.6 35B MTP rows above `200 tok/s` on NVIDIA-class hardware. The most useful signal is not the hardware comparison; it is that MTP/draft speculation is the path others use to cross the `200 tok/s` single-user line.
- Public `Qwen/Qwen3.6-35B-A3B-FP8` vLLM with DFlash shows `253.7 tok/s` on an RTX PRO 6000 Blackwell at 4K context. That points at verifier-preserving speculation as a real multiplier, not a small knob.
- `unsloth/Qwen3.6-35B-A3B-MTP-GGUF` has public `llama-server --spec-type mtp` rows including `213.87 tok/s` on RTX 4090 and `121.6-195.1 tok/s` on RTX 3090 variants. These are not acceptable quantizations for our production path, but they are useful recipes for MTP draft depth, KV dtype, and server scheduling.
- `GestaltLabs/Qwen3.6-35B-A3B-NSC-ACE-SABER-GGUF-MTP` has public Q8_0-MTP rows around `72-80 tok/s` and other non-8-bit rows above `130 tok/s`. The Q8_0-MTP line is interesting because it proves at least one full-precision-ish MTP GGUF route exists, even if it is not currently our model or engine.
- The Intel/vLLM Arc Pro blog explicitly calls out persistent single-kernel MoE loops, dynamic work balancing, and prepacked formats. That matches our failures: Python-level wrapper boundaries and env-var sweeps are not enough.
- Intel's grouped-GEMM tuning issue says real MoE routing skew and tile configuration dominate grouped GEMM performance. Our current microbench should stop using only synthetic even routing and capture real routed expert distributions from the live model.
- vLLM's XPU backend migration confirms W8A8/W8A16 and MoE kernels are now intended to live in `vllm-xpu-kernels`, so upstreamable shape-exact repros should target that library, not old IPEX paths.
- Community B70 data still says llama.cpp/SYCL can be strong for Qwen3.6 MoE, and Q8_0 on Qwen3.6 35B has been measured on dual B70. It is slower than our current public TP4 result, but it remains a useful 8-bit engine diagnostic, especially if MTP support is easier there first.

Public sources checked:

- `https://localmaxxing.com/api/leaderboard?hardwareName=Arc%20Pro%20B70&modelFamily=qwen&limit=50`
- `https://localmaxxing.com/api/benchmarks?hfId=nameistoken%2FQwen3.6-35B-A3B-Quark-W8A8-INT8&limit=20`
- `https://localmaxxing.com/api/benchmarks?hfId=unsloth%2FQwen3.6-35B-A3B-MTP-GGUF&limit=20`
- `https://localmaxxing.com/api/benchmarks?hfId=GestaltLabs%2FQwen3.6-35B-A3B-NSC-ACE-SABER-GGUF-MTP&limit=20`
- `https://localmaxxing.com/api/benchmarks?hfId=Qwen%2FQwen3.6-35B-A3B-FP8&limit=20`
- `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`
- `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`
- `https://github.com/vllm-project/vllm/issues/33214`
- `https://github.com/PMZFX/intel-arc-pro-b70-benchmarks`

New big bets to track:

1. Build a verifier-preserving speculation ladder.
   - Stage A: repair n-gram/spec trace and prove repeat64/long-context stability on the current Quark verifier.
   - Stage B: use official FP8 MTP tensors or an MTP GGUF sidecar only as a proposer; the Quark INT8 model must still verify every accepted token.
   - Stage C: test DFlash/EAGLE-style proposer routes if XPU support exists or can be ported with the same final-verifier guarantee.
   - Score by accepted-token throughput, acceptance rate, TTFT, and exact quality hashes. Raw draft speed does not count.

2. Capture real router distributions from the accepted endpoint.
   - Add opt-in logging around Qwen3.6 MoE router top-k expert IDs and per-expert token counts for p512/n512 decode.
   - Feed those exact distributions into `vllm-xpu-kernels` grouped-GEMM microbenches.
   - Tune small-M W8A8 policies for the actual long-tail expert pattern instead of synthetic uniform routes.

3. Port or prototype persistent zero-gap MoE for the Quark W8A8 INT8 path.
   - Current XPU grouped GEMM is already selected, but the live path is still multi-stage: remap, quant, grouped GEMM, activation, quant, grouped GEMM, gather.
   - A real win likely requires persistent scheduling across routed expert blocks plus fused activation/finalize, not another Python custom op around the output.
   - Start outside vLLM with a parity microbench before touching the endpoint.

4. Create a tile-friendly INT8 repack cache.
   - If Quark W8A8 weights are not stored in the fastest B70 XMX/DPAS layout, repack once at model-load time and cache with checksums.
   - Keep mathematical scales and weights identical; this is a layout optimization, not a new quantization.
   - Reject if it costs enough VRAM to threaten 32K context.

5. Build a decode-core harness separate from the OpenAI server.
   - Measure direct model-runner decode with identical tokenizer/template/settings and the same graph cache.
   - If direct core throughput is meaningfully above endpoint throughput, create a production "latency lane" that removes server/request/streaming overhead for single-user sessions.
   - If the core is also capped near `100 tok/s`, focus back on kernels and speculation.

6. Run a strict 8-bit engine bakeoff.
   - Candidates: current vLLM Quark W8A8, llama.cpp/SYCL Q8_0 or other real 8-bit GGUF, OpenVINO/oneDNN GenAI 8-bit if Qwen3.6 MoE is supported, and any XPU-native W8A8 path that appears.
   - This is diagnostic unless it keeps the same quality gates, 32K context, and production-serving requirements.
   - Do not count Q4, MXFP4, AWQ, GPTQ-4bit, or Qwen3.5 as acceptable answers to this question.

7. Explore hybrid TP/EP/replica layouts with memory math first.
   - Pure TP4 gives the best current result, but it also creates many tiny collectives during single-token decode.
   - Model a layout that partitions experts while replicating or semi-replicating cheap dense/attention pieces, then decide whether it can fit with 32K KV.
   - If not feasible, use the model to justify why TP4 remains the practical path.

8. Try a separate sidecar drafter on unused host or reduced GPU resources.
   - A small same-family Qwen3.6 drafter or MTP sidecar could run on CPU, one XPU slice, or a separate service if it feeds the Quark verifier cheaply.
   - This only helps if draft latency plus verification is lower than current token-by-token decode.
   - Quality remains preserved only because the Quark verifier owns final output.

9. Build upstream-ready repro bundles.
   - Three minimal tests: routed grouped GEMM with real expert histograms, dense W8A8 GEMM for the repeated AOT shapes, and graph-safe tiny all-reduce for hidden-size collectives.
   - Include exact shapes, oneAPI/kernel versions, B70 topology, current throughput, and expected improvement target.
   - These are the artifacts most likely to get useful help from Intel/vLLM maintainers.

10. Validate host-stack and kernel/driver branch as a controlled experiment.
    - Public B70 data spans newer kernels and oneAPI stacks than our current service. Host policy is unlikely to double speed, but it can hide wins behind jitter or device resets.
    - Test only via a reversible boot/driver profile: power policy, ASPM/runtime power, NUMA pinning, CCL fabric settings, and thermal logging.
    - Measure variance, device errors, and accepted r10 speed before/after.

Near-term priority after this note:

1. Do the speculation feasibility pass first, because it is the only path with credible `>200 tok/s` upside while preserving final-model quality.
2. In parallel, add real-router-distribution capture and feed it into grouped-GEMM tests.
3. Keep the accepted service healthy and use it as the quality oracle for every candidate.

## Speculation Trace Follow-Up

The active verifier model still has no in-checkpoint MTP route:

- current Quark verifier config: `architectures=["Qwen3_5MoeForConditionalGeneration"]`, `model_type=qwen3_5_moe`
- current Quark verifier safetensors index: `0` keys containing `mtp`
- official Qwen FP8 snapshot: `1561` keys containing `mtp`

So MTP cannot be used as an internal current-model drafter. A future MTP test would need the official FP8 MTP weights as an auxiliary proposer while the current Quark INT8 model remains the verifier. That is a separate memory/startup risk and should not be counted as "current model" unless final accepted tokens are still verified by the Quark model.

Added trace tooling for the current n-gram/speculative path:

- `scripts/qwen36-quality-token-trace.py`
  - builds the same exact, repeat, and long-context prompts as the quality suite
  - records prompt hashes, prompt token counts, normalized outputs, output token IDs, and first-token diffs against a baseline JSON
- `scripts/launch-qwen36-quark-int8-ngram5-trace.sh`
  - repeatable launch wrapper for the prior n-gram5 CG128 hold-prefill candidate
  - enables `VLLM_SPEC_DECODE_TRACE_FILE` and bounds trace size with `VLLM_SPEC_DECODE_TRACE_MAX_LINES`
  - keeps the current Quark INT8 model as verifier
- `patches/vllm-qwen36-spec-decode-jsonl-trace-20260611.patch`
  - opt-in scheduler JSONL trace behind `VLLM_SPEC_DECODE_TRACE_FILE`
  - records request id, scheduled draft token IDs, generated token IDs, accepted/rejected counts, and request token counters
  - disabled unless the env var is set

Accepted baseline trace:

- artifact: `data/qwen36-quark-int8-accepted-frontdoor-token-trace-20260611.json`
- compared against accepted quality baseline: `data/qwen36-quark-int8-tp4-noprefix-accepted-frontdoor-quality-rerun32-20260610.json`
- result: `baseline_match_all=true`
- traced outputs:
  - `exact_ok`: `OK`
  - `copy_phrase`: `satin cobalt orbit`
  - `arithmetic`: `60`
  - `json_schema`: `{"answer": "42", "unit": "widgets"}`
  - `repeat_colors`: `blue, green, orange, red` across 4 repeats
  - `long_context_needle`: `B70_QWEN36_NEEDLE_20260609`

Next trace experiment:

1. Launch the prior n-gram candidate with `VLLM_SPEC_DECODE_TRACE_FILE=/tmp/qwen36-ngram-spec-trace.jsonl` and a bounded `VLLM_SPEC_DECODE_TRACE_MAX_LINES`.
2. Run `qwen36-quality-token-trace.py` against the speculative frontdoor/backend with the accepted trace as `--baseline-json`.
3. If the long-context answer diverges, inspect the JSONL rows immediately before the first output-token diff:
   - accepted draft length at the divergence
   - whether a bonus token crossed the stop/EOS point
   - whether GDN recurrent/convolution state advanced over rejected tokens
   - whether request token counters disagree with output token IDs
4. Only after token-level parity passes should n-gram speed numbers count toward the `>200 tok/s` goal.

## N-Gram Trace Result

Launched the prior n-gram5 candidate with scheduler trace enabled:

- launcher: `scripts/launch-qwen36-quark-int8-ngram5-trace.sh`
- trace env: `VLLM_SPEC_DECODE_TRACE_FILE=/tmp/qwen36-ngram5-spec-trace-20260611.jsonl`
- copied trace artifact: `data/qwen36-quark-int8-tp4-ngram5-trace-spec-jsonl-20260611.jsonl`
- token trace artifact: `data/qwen36-quark-int8-tp4-ngram5-trace-frontdoor-token-trace-20260611.json`
- repeat64 quality artifact: `data/qwen36-quark-int8-tp4-ngram5-trace-frontdoor-quality-rerun64-20260611.json`

The short token-trace gate passed:

- `baseline_match_all=true`
- exact, JSON, repeat sample, and long-context token IDs matched the accepted baseline

The stronger repeat64 quality gate failed:

- `pass_all=false`
- `baseline_match_all=false`
- exact OK/copy/arithmetic passed
- JSON schema failed with a repeated `5` loop
- repeat64 produced three bad repeats:
  - `utex// / / / / / / / / / / / / / / / / / / / / / / / / / / / / /`
  - `blue whiskey whiskey whiskey2024-03-14T10:00:00Z`
  - `unyablue, green, orange, red`
- long-context needle still passed: `B70_QWEN36_NEEDLE_20260609`

Scheduler trace summary:

- rows: `30`
- drafts: `122`
- accepted: `113`
- rejected: `9`
- acceptance rate: `92.62%`
- accepted-count histogram: `{0: 2, 1: 4, 2: 3, 4: 2, 5: 19}`

Most important decoded trace rows:

- `chatcmpl-b620cec2a9ac1adc-939b0e39`: 49 draft tokens, 49 accepted, 0 rejected. The scheduled drafts were repeated token id `20`, decoded as `55555`, and the generated stream continued as `555555`. This lines up with the JSON schema failure.
- `chatcmpl-8d9452458a9fd04d-88f24066`: 24 draft tokens, 24 accepted, 0 rejected. The scheduled drafts were repeated token id `593`, decoded as ` / / / / /`, and the generated stream continued the slash loop.
- `chatcmpl-a19f38bbd8c47132-9bd9f8a4`: rejected ` whiskey` and part of a timestamp continuation, matching one repeat64 bad output.

Decision: reject the current n-gram5 candidate for production and for speed claims. It can pass a short token trace, but it fails the quality bar under repeat64. Fully accepted bad loops are a better diagnostic than the earlier long-context failure because they point at speculative-state correctness, proposer history, or mixed scheduling contamination rather than simple sampling variance.

Immediate follow-up ideas for speculation:

1. Add request-id correlation from the quality client to server trace so bad outputs map directly to JSONL rows without inference.
2. Trace proposer source spans: prompt tokens versus generated tokens, and whether accepted/rejected speculative tokens are entering the n-gram lookup history too early.
3. Add a strict debug mode that disables bonus-token emission after accepted draft tokens. If the loops vanish, the issue is likely state advancement around the target bonus token.
4. Add a verifier-only shadow decode for suspect requests: run the same request through accepted non-spec decode immediately after a speculative failure and compare token IDs.
5. Test `num_speculative_tokens=1` and `2` only as diagnostics. They are unlikely to get us near 200 tok/s, but they can localize whether corruption appears only when multiple accepted draft tokens advance state.
6. Test a per-request speculative kill switch for structured outputs and short deterministic prompts. This is not a final answer to the speed goal, but it may let long natural-language generations use speculation while preserving production correctness.

## N-Gram 1/2 Boundary Diagnostic

Added a generic parameterized launcher:

- `scripts/launch-qwen36-quark-int8-ngram-trace.sh`
- controls:
  - `NUM_SPECULATIVE_TOKENS`
  - `PROMPT_LOOKUP_MIN`
  - `PROMPT_LOOKUP_MAX`
  - `TAG`
  - `SPEC_TRACE_FILE`
  - `ENABLE_XPU_GRAPH`
  - `ENFORCE_EAGER`
  - `COMPILE_CONFIG`
  - `CUDAGRAPH_CAPTURE_SIZES`

This lets us test speculation depth without editing launcher code.

Results:

| Candidate | Quality | Corrected tok/s | E2E tok/s | TTFT ms | Decision | Artifact |
| --- | --- | ---: | ---: | ---: | --- | --- |
| n-gram1 | repeat64 pass, baseline match | 94.364 | 93.220 | 77.132 | reject, slower than accepted | `data/qwen36-quark-int8-tp4-ngram1-trace-single-r4-20260611.json` |
| n-gram2 | first request fatal error | n/a | n/a | n/a | reject, unstable | `data/qwen36-quark-int8-tp4-ngram2-trace-first-request-device-lost-20260611.log` |
| n-gram2 no-XPU-graph | short quality pass | 17.784 | 17.771 | 76.437 | diagnostic only, too slow | `data/qwen36-quark-int8-tp4-ngram2-noxpugraph-single-r2-20260611.json` |
| n-gram2 capture-size-3 | repeat64 pass, baseline match | 105.158 | 103.709 | 77.388 | diagnostic, quality-clean but unstable speed gain | `data/qwen36-quark-int8-tp4-ngram2-cg3-single-r4-20260611.json` |
| n-gram3 capture-size-4 | repeat64 fail, accepted loop | not measured | not measured | not measured | reject, corrupts output | `data/qwen36-quark-int8-tp4-ngram3-cg4-frontdoor-quality-rerun64-20260611.json` |
| n-gram3 min4/max12 | repeat64 fail, accepted loop | not measured | not measured | not measured | reject, corrupts output | `data/qwen36-quark-int8-tp4-ngram3-min4-cg4-frontdoor-quality-rerun64-20260611.json` |
| n-gram2 eager/no-graph | survives, quality fail | not measured | not measured | not measured | diagnostic only | `data/qwen36-quark-int8-tp4-ngram2-eager-frontdoor-quality-rerun8-20260611.json` |
| n-gram5 | short trace pass, repeat64 fail | not counted | not counted | not counted | reject, corrupts output | `data/qwen36-quark-int8-tp4-ngram5-trace-frontdoor-quality-rerun64-20260611.json` |

n-gram1 quality artifacts:

- quality: `data/qwen36-quark-int8-tp4-ngram1-trace-frontdoor-quality-rerun64-20260611.json`
- quality scheduler trace: `data/qwen36-quark-int8-tp4-ngram1-trace-quality-spec-jsonl-20260611.jsonl`
- speed scheduler trace: `data/qwen36-quark-int8-tp4-ngram1-trace-speed-spec-jsonl-20260611.jsonl`

n-gram1 trace summaries:

- repeat64 quality run: rows `12`, drafts `12`, accepted `10`, rejected `2`, acceptance rate `83.33%`, histogram `{0: 2, 1: 10}`
- p512/n512 r4 speed run: rows `444`, drafts `444`, accepted `293`, rejected `151`, acceptance rate `65.99%`, histogram `{0: 151, 1: 293}`

n-gram2 failed on the first quality request before any scheduled speculative tokens appeared:

- error: `UR_RESULT_ERROR_DEVICE_LOST`
- failing stack: `block_table.copy_to_gpu -> self.gpu[:n].copy_(self.cpu[:n], non_blocking=True)`
- scheduler output had `scheduled_spec_decode_tokens={}` and `num_scheduled_tokens=17`
- config had `SpeculativeConfig(method='ngram', model=None, num_spec_tokens=2)`

n-gram2 no-XPU-graph diagnostic:

- launch controls: `ENABLE_XPU_GRAPH=0`, `ENFORCE_EAGER=0`
- torch.compile stayed enabled, but `cudagraph_mode=NONE`
- short quality diagnostic passed: exact cases, repeat8, baseline comparison, and 2K long-context needle
- speed was unusable: p512/n512 r2 corrected decode `17.784 tok/s`
- scheduler trace artifact: `data/qwen36-quark-int8-tp4-ngram2-noxpugraph-spec-jsonl-20260611.jsonl`
- trace summary: rows `172`, drafts `344`, accepted `158`, rejected `186`, acceptance rate `45.93%`, histogram `{0: 69, 1: 48, 2: 55}`

n-gram2 capture-size-3 diagnostic:

- launch controls: `ENABLE_XPU_GRAPH=1`, `ENFORCE_EAGER=0`, `CUDAGRAPH_CAPTURE_SIZES=1,2,3,4,8,16,24,32,40,48,56,64,72,80,88,96,104,112,120,128`
- motivation: the default graph capture list skipped exact query length `3`, while n-gram2 uses `1 + num_speculative_tokens = 3` tokens in the mixed decode path
- first `Reply exactly: OK` request survived; this fixed the immediate `UR_RESULT_ERROR_DEVICE_LOST` symptom seen in the default n-gram2 run
- repeat64 plus 4K long-context quality passed and matched the accepted baseline:
  - `data/qwen36-quark-int8-tp4-ngram2-cg3-frontdoor-quality-rerun64-20260611.json`
- speed was not stable enough for a win claim:
  - r2 corrected decode: `141.193 tok/s`, e2e `138.469 tok/s`, TTFT `78.071 ms`
  - r4 corrected decode: `105.158 tok/s`, e2e `103.709 tok/s`, TTFT `77.388 ms`
  - r4 is only about `5.8%` above the accepted baseline and within a range where prompt/repeat effects can dominate
- scheduler trace artifact: `data/qwen36-quark-int8-tp4-ngram2-cg3-spec-jsonl-20260611.jsonl`
- trace summary: rows `685`, drafts `1365`, accepted `1044`, rejected `321`, acceptance rate `76.48%`, histogram `{0: 116, 1: 94, 2: 475}`
- individual long-generation requests ranged from about `46.5%` to `99.0%` draft acceptance, which explains the r2/r4 spread

n-gram3 capture-size-4 diagnostic:

- launch controls: `NUM_SPECULATIVE_TOKENS=3`, `PROMPT_LOOKUP_MIN=2`, `PROMPT_LOOKUP_MAX=5`, `CUDAGRAPH_CAPTURE_SIZES=1,2,3,4,5,6,7,8,16,...,128`
- the service compiled, captured, served, and passed the minimal `Reply exactly: OK` smoke
- repeat64 plus 4K long-context quality failed:
  - exact OK, copy, arithmetic, JSON schema all passed
  - 4K long-context needle passed
  - baseline comparison of first repeat hash still matched
  - repeat stability failed because one repeat emitted `ntag/ntag/ntag/...`
- scheduler trace artifact: `data/qwen36-quark-int8-tp4-ngram3-cg4-spec-jsonl-20260611.jsonl`
- trace summary: rows `15`, drafts `43`, accepted `37`, rejected `6`, acceptance rate `86.05%`, histogram `{0: 2, 2: 2, 3: 11}`
- decoded bad accepted loop: token ids `[91627, 14]` -> `ntag/`, repeatedly fully accepted

n-gram3 strict lookup diagnostic:

- launch controls: `NUM_SPECULATIVE_TOKENS=3`, `PROMPT_LOOKUP_MIN=4`, `PROMPT_LOOKUP_MAX=12`, same exact capture-size list as above
- motivation: check whether short accidental prompt matches caused the `ntag/` loop
- repeat64 plus 4K long-context quality still failed:
  - exact OK, copy, arithmetic, JSON schema all passed
  - 4K long-context needle passed
  - repeat stability produced two bad outputs:
    - `utex utex utex ...`
    - `blue... green, red, yellow` with non-baseline inserted tokens
- scheduler trace artifact: `data/qwen36-quark-int8-tp4-ngram3-min4-cg4-spec-jsonl-20260611.jsonl`
- trace summary: rows `13`, drafts `35`, accepted `34`, rejected `1`, acceptance rate `97.14%`, histogram `{2: 5, 3: 8}`
- decoded bad accepted loop: token ids `[9092, 220]` -> `utex `, repeatedly fully accepted

n-gram2 eager/no-graph diagnostic:

- launch controls: `ENABLE_XPU_GRAPH=0`, `ENFORCE_EAGER=1`, `COMPILE_CONFIG=`
- minimal `Reply exactly: OK` smoke passed
- short quality diagnostic failed: arithmetic returned `58` instead of `60`
- copy, JSON, repeat8, and 2K long-context needle passed
- scheduler trace artifact: `data/qwen36-quark-int8-tp4-ngram2-eager-spec-jsonl-20260611.jsonl`
- trace summary: rows `9`, drafts `18`, accepted `15`, rejected `3`, acceptance rate `83.33%`, histogram `{0: 1, 1: 1, 2: 7}`
- the arithmetic failure did not correspond to a traced draft row, so eager/no-graph itself can perturb outputs on this stack

Interpretation:

- n-gram1 proves the single speculative-token plumbing can pass our quality bar, but it is slower than accepted because its acceptance rate is too low and the speculative machinery adds overhead.
- n-gram2 failing before draft scheduling points at an XPU graph/input-prep stability bug for decode query length `1 + num_speculative_tokens >= 3`, not just a bad n-gram proposer.
- disabling XPU graph while keeping torch.compile avoids the device-loss crash and passes a short quality gate, which strongly localizes the hard failure to XPU graph capture/replay.
- the no-XPU-graph path is about 5.6x slower than accepted, so it is only a diagnostic path.
- adding exact graph capture bucket `3` fixes the n-gram2 first-request device-loss path, so the crash was likely a graph shape dispatch/capture mismatch rather than a general n-gram2 impossibility.
- n-gram2 with the exact capture bucket can be quality-clean under repeat64 and 4K long context, but the speed gain is prompt-sensitive because acceptance varies widely.
- eager/no-graph is not quality-equivalent, so it cannot be used as a production workaround.
- n-gram3 and n-gram5 both produce fully accepted repeated-token loops after the runtime survives startup. Stricter `prompt_lookup_min` does not fix this; it can even increase acceptance of the bad loop. Multi-token n-gram depth above 2 is therefore not a valid route to `>200 tok/s` on this stack until speculative-state correctness is fixed.

Next concrete speculation path:

1. Keep exact capture bucket `3` in the diagnostic launcher and test whether nearby buckets (`5`, `6`, maybe `7`) are needed for deeper speculation before any n-gram3+ run.
2. Split speed tests by prompt class: repetitive benchmark prompt, natural chat prompt, code prompt, and structured-output prompt. N-gram2 only helps when draft acceptance is high.
3. Add an acceptance-rate predictor and dynamic speculative kill switch. If early acceptance drops below a threshold, fall back to accepted non-spec decode for the rest of that request.
4. Add a hard safety cap for n-gram speculation depth: only n-gram2 remains a candidate, and only after prompt-class speed testing. n-gram3+ is quality-rejected.
5. Test an n-gram2 production split only for long free-form completions, never for deterministic structured/copy/math routes until canary parity is stronger.
6. Inspect graph-captured tensor shapes for `decode_query_len=3`, especially input/block-table tensors copied before the first model execute, and file an upstream-quality repro if exact bucket `3` is required on XPU but not captured by default.
7. Keep n-gram1 out of production because it is quality-safe but slower.
8. Do not use eager/no-graph or no-XPU-graph as production workarounds; they exist only to isolate graph correctness.

## N-Gram2 Prompt-Class Screen

Added prompt-class support to `scripts/measure-openai-endpoint-metrics.py`:

- prompt presets: `repetitive`, `natural-chat`, `code`, `structured`, `math-reasoning`
- `--prompt-file`
- `--endpoint completions|chat`
- `--seed`
- `--include-full-text`
- server-reported prompt token accounting when `usage.prompt_tokens` is present

The important fix was preserving both prompt prefix and suffix while fitting filler to the target token budget. The earlier prompt fitter could truncate suffix instructions, which made instruction-style prompts end too early and invalidated prompt-class comparisons.

Seeded chat prompt-class screen, accepted TP4 versus n-gram2 capture-size-3:

| Prompt preset | Accepted corrected tok/s | n-gram2 corrected tok/s | Delta | Notes |
| --- | ---: | ---: | ---: | --- |
| natural-chat | 99.587 | 90.848 | -8.8% | slower than accepted |
| code | 99.612 | 93.728 | -5.9% | slower than accepted |
| structured | 99.445 | 116.362 | +17.0% | not a clean win; n-gram2 stopped at 440/445 output tokens and the long JSON task was invalid/truncated for both paths |
| math-reasoning | 99.402 | 98.391 | -1.0% | effectively neutral/slower |

Artifacts:

- `data/qwen36-quark-int8-tp4-accepted-chat-promptclass-natural-chat-seeded-r2-20260611.json`
- `data/qwen36-quark-int8-tp4-accepted-chat-promptclass-code-seeded-r2-20260611.json`
- `data/qwen36-quark-int8-tp4-accepted-chat-promptclass-structured-seeded-r2-20260611.json`
- `data/qwen36-quark-int8-tp4-accepted-chat-promptclass-math-reasoning-seeded-r2-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram2-cg3-chat-promptclass-natural-chat-seeded-r2-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram2-cg3-chat-promptclass-code-seeded-r2-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram2-cg3-chat-promptclass-structured-seeded-r2-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram2-cg3-chat-promptclass-math-reasoning-seeded-r2-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram2-cg3-chat-promptclass-seeded-spec-jsonl-20260611.jsonl`
- `data/qwen36-quark-int8-tp4-ngram2-cg3-chat-promptclass-seeded-summary-20260611.json`

Aggregate n-gram2 prompt-class trace:

- rows: `662`
- draft tokens: `1321`
- accepted draft tokens: `609`
- rejected draft tokens: `712`
- acceptance rate: `46.10%`

Interpretation:

- n-gram2 is not a general route to `>200 tok/s` for real chat-like prompts. It only helped the structured case, and that case was not clean enough to claim because output length and validity diverged.
- The prompt-class acceptance rate was too low for the speculative machinery to pay for itself on natural chat and code.
- Exact free-form output hashes are diagnostic only. Even accepted seeded long-form repeats were not hash-stable, so broad quality validation needs deterministic canaries, structured validators, semantic judge/eval coverage, and BF16/current-model comparisons rather than raw long-form hash matching.
- n-gram2 remains useful as a diagnostic and maybe a future request-class-specific option. It should not be used as a production default.
- The no-quality-loss single-request path now points away from plain n-gram speculation and toward verifier-preserving MTP/EAGLE/draft work, or real XPU backend/kernel/layout work.

New web-research leads to fold into next experiments:

- vLLM's current CUDA Graph design explicitly separates graph capture modes and can dispatch between full, piecewise, and no-graph paths. That supports testing `FULL_DECODE_ONLY` or `FULL_AND_PIECEWISE` style decode capture as a controlled experiment instead of only changing bucket lists: https://docs.vllm.ai/en/latest/design/cuda_graphs/
- The official vLLM Qwen3.5/Qwen3.6 recipe documents Qwen3.6 MTP speculative decoding with `{"method": "mtp", "num_speculative_tokens": 2}`. Our Quark checkpoint has no MTP tensors, but this reinforces the auxiliary-official-FP8-MTP-drafter idea with the Quark INT8 model as verifier: https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html
- The vLLM Arc Pro B-series post lists n-gram, EAGLE, and EAGLE3 speculative decoding as supported optimization targets on Intel Arc Pro B-series, and emphasizes persistent MoE kernels and dynamic work balancing. Those are the two biggest quality-preserving directions still open: speculation and real MoE kernel work, not small Python boundary wrappers: https://vllm.ai/blog/2025-11-11-intel-arc-pro-b
- The open llm-compressor Qwen3.6 W8A8 issue notes that a clean W8A8 Qwen3.6 path still needs MoE architecture mappings, fused expert tensor handling, and linear-attention coverage. That means our Quark INT8 route is ahead of generic tooling, but also that upstream INT8 quant support may soon become a better foundation: https://github.com/vllm-project/llm-compressor/issues/2787
- Intel's vLLM 0.10.2 XPU container notes claim persistent MoE GEMM and fused activation kernels produced a `2.6x` end-to-end improvement on Qwen3-30B-A3B and `1.5x` on DeepSeek-V2-lite. That makes persistent MoE on our exact Qwen3.6 A3B shapes a top-tier bet, not just a nice-to-have: https://github.com/intel/ai-containers/blob/main/vllm/0.10.2-xpu.md
- The oneCCL environment docs call out small-message thresholds, SYCL-vs-Level-Zero collective thresholds, persistent temporary buffers, and a warning that GPU-buffer `CCL_WORKER_COUNT` values above `1` are not recommended. That matches our worker-count graph failure and suggests exact small-message threshold experiments before more worker-thread tuning: https://www.intel.com/content/www/us/en/docs/oneccl/developer-guide-reference/2021-14/environment-variables.html

## Additional Big Ideas

These are the next larger opportunities to keep in mind while continuing the quality-first work.

1. Auxiliary official-FP8 MTP drafter with Quark INT8 verifier.
   - The current Quark checkpoint has no MTP tensors, but the official FP8 snapshot does. A two-model setup may still preserve final output quality if the Quark INT8 verifier owns acceptance.
   - Risk: extra VRAM and startup complexity. First measurement should be memory headroom plus repeat64 parity, before any throughput benchmark.

2. Production split by request class.
   - Keep the accepted TP4 path as the default for deterministic/structured/short requests.
   - Allow a separately validated speculative path only for long free-form requests after it passes repeat64/needle/canary gates.
   - This could improve user-perceived latency without weakening the highest-risk workload classes.

3. Shape-exact offline runner.
   - Build a direct model-runner benchmark that avoids OpenAI server streaming and request machinery while using the same weights/kernels.
   - If offline decode is much faster than the served endpoint, the next win is scheduler/streaming overhead. If it is also near 100 tok/s, the next win must come from kernels/layout/speculation.

4. Expert-placement simulator.
   - Before implementing expert parallelism, write a small memory/traffic model for Qwen3.6 A3B experts on 4x32GB B70.
   - Estimate TP4 collective bytes per token versus candidate EP/hybrid layouts. This avoids a large vLLM architecture branch unless the math says it can beat TP4 single-token latency.

5. Single-layer MoE kernel bakeoff.
   - Extract one real routed MoE layer shape from the AOT cache and benchmark several XPU implementations outside vLLM:
     - current staged path
     - persistent grouped GEMM
     - prepacked expert weights
     - fused finalize/shared-add/residual epilogue
   - Only wire a kernel into vLLM after the standalone microbench proves a material win.

6. Intel-friendly 8-bit engine bakeoff.
   - Build or find a true 8-bit same-model route for llama.cpp/SYCL or another Intel backend. This is not a 4-bit fallback and not a Qwen3.5 detour.
   - Purpose: decide whether vLLM/XPU is the blocker, not to change the model target prematurely.

7. Upstream issue/PR package.
   - Convert our most stable findings into small reproductions:
     - n-gram speculative accepted-loop quality failure
     - graph-safe oneCCL worker-count failure
     - shape-exact W8A8/MoE microbench deficit
   - This makes it easier to get Intel/vLLM attention where local patching is the wrong scale.

8. Reliability soak before every claimed win.
   - For each candidate that passes quality, run a short stability matrix:
     - c1 speed r8/r10
     - repeat64 quality
     - long-context needle
     - c4/c8 aggregate smoke
     - 30-60 minute loop if it is a production candidate
   - The stale accepted-process failure means runtime age matters; do not trust a cold-only pass.

## Bolder Ideas Added After N-Gram2 Capture-Size Result

These are not next-command items. They are larger directions that could plausibly move single-request decode much more than another launch-flag sweep.

1. Dynamic verifier-preserving speculation policy.
   - Instead of enabling n-gram or a draft model globally, make speculation adaptive per request.
   - Start with n-gram2 or MTP for long natural-language completions, measure early acceptance over the first N speculative windows, and disable speculation for that request if acceptance falls below a threshold.
   - This could keep the rare `140+ tok/s` behavior for easy/repetitive continuations while avoiding overhead on low-acceptance prompts.
   - Proof required: token parity against accepted decode, quality canaries, and prompt-class speed tables.

2. Two-stage proposer ladder.
   - Use a cheap n-gram proposer first, then escalate to MTP/EAGLE only when n-gram acceptance shows the request is predictable.
   - The goal is to avoid paying a heavier proposer cost on prompts where speculation is unlikely to help.
   - This is bigger than a single speculative mode, but it matches what the trace says: acceptance rate, not just draft depth, controls the win.

3. Decode microservice split: prefill service plus latency-specialized decode service.
   - vLLM supports prefill/decode disaggregation as a general architecture direction, and our single-request TTFT is already low while decode is the bottleneck.
   - A decode-only instance could use tighter graph capture, smaller scheduler surfaces, and fewer mixed prefill/decode transitions.
   - Proof required: same model/weights, same output tokens, and a direct comparison of p512/n512 c1 against the normal OpenAI-compatible service.

4. Hybrid TP/EP prototype for Qwen3.6 A3B.
   - Pure TP4 may be structurally expensive for single-token MoE decode because many hidden-state boundaries become collectives.
   - A hybrid layout could keep attention/GDN replicated or lightly sharded while placing routed experts to reduce per-token collective cost.
   - First artifact should be a traffic/memory simulator before touching vLLM internals.

5. Persistent single-token MoE executor.
   - Build a decode-only MoE executor for the exact Qwen3.6 expert shapes with persistent workgroups, prepacked expert weights, fused finalize/shared/residual epilogue, and graph-safe output handoff.
   - This is a real kernel project, but it targets the part of the model where Intel's Arc guidance says large MoE gains exist.
   - Proof required: standalone layer microbench first, endpoint integration second.

6. Static batch-1 graph replay path.
   - Build an offline or internal endpoint path that assumes one active decode stream, fixed max model length, fixed sampling settings, and preallocated KV.
   - This would quantify the gap between vLLM serving generality and the fastest possible single-user decode loop for the same model.
   - If the offline path is much faster, production can use a special low-latency lane for solo sessions.

7. Exact-shape XPU collective replacement.
   - Do not replace all oneCCL. Replace only the small BF16 all-reduce/all-gather shapes that appear repeatedly in the AOT cache.
   - A shape-fixed graph-safe collective could be easier than a general communicator and may pair with fused decoder-layer boundaries.
   - Proof required: microbench latency, graph capture compatibility, and endpoint quality parity.

8. Model-layout fork, not model-quality fork.
   - Keep the same Qwen3.6 Quark W8A8 mathematical weights, but store a second on-disk XPU-native packed layout for DPAS/XMX-friendly access.
   - This avoids a quality tradeoff while testing whether weight layout, not quantization level, is the limiting factor.
   - First check: whether current `int8_gemm_w8a8` hot paths still transpose/repack or read in a suboptimal stride pattern.

9. Same-model 8-bit engine shootout.
   - Build a true 8-bit Qwen3.6 35B artifact for llama.cpp/SYCL or another Intel-native runtime and run the same quality suite.
   - This is a diagnostic to determine whether vLLM/XPU overhead is the ceiling.
   - Reject any route that turns into Qwen3.5, 4-bit, or template-incompatible output.

10. Upstream collaboration package.
    - Package the exact capture-size-3 n-gram2 finding, oneCCL graph worker failure, and AOT shape census into minimal, public repros.
    - This may be faster than locally owning every XPU backend gap if Intel/vLLM maintainers can fix default capture policy or expose the right MoE/kernel hooks.

## Even Bolder Ideas After Prompt-Class Screen

The prompt-class run reduces confidence in plain n-gram speculation. These are larger ideas worth tracking because they could still move the single-user number materially without lowering quality.

1. Quality-gated MTP/EAGLE lane, not plain n-gram.
   - Load the official Qwen3.6 FP8 MTP/EAGLE-capable components as an auxiliary proposer while keeping the Quark W8A8 INT8 model as the verifier.
   - Reject if final accepted tokens fail deterministic canaries, repeat64, long-context needles, or BF16/current-model semantic comparisons.
   - First decision point: memory headroom with auxiliary proposer loaded at 32K, before speed testing.

2. Train or distill a Qwen3.6-specific proposer for our prompt mix.
   - vLLM points at trainable speculators as the high-gain route; off-the-shelf n-gram acceptance is too prompt-sensitive here.
   - A small same-tokenizer Qwen3.6-family proposer, trained against our target chat/code/structured prompts, could produce higher acceptance than n-gram without touching final output quality.
   - This is only acceptable if the verifier remains the current Quark model and every accepted token is still checked.

3. Import or recreate Intel's persistent MoE path for this exact model.
   - Intel's XPU notes report large MoE wins on Qwen3-30B-A3B, which is close enough architecturally to justify a shape-by-shape audit.
   - First work item: identify whether our current vLLM branch actually uses that persistent MoE kernel for the Quark W8A8 path. If not, create a minimal reproducer and patch target.

4. Switch from model-level experiments to layer-level proof.
   - Build a benchmark for one decode token through one actual Qwen3.6 A3B layer using captured shapes and tensors.
   - Measure attention/GDN, routed MoE, shared expert, dense W8A8 GEMM, and collective time independently.
   - This prevents wasting days on flags when one subpath is obviously dominant.

5. Build a reversible solo latency lane.
   - Keep normal vLLM serving for production concurrency, but add a special lane for one active user: static KV, fixed graph capture, fixed sampling, and minimal streaming overhead.
   - If the lane proves faster while preserving output, route solo sessions there and keep aggregate traffic on the accepted service.

6. Use replicas for production but not for the headline metric.
   - If single-request TP4 remains near 100 tok/s, production may still benefit from multiple accepted replicas across B70s or TP2 pairs.
   - Keep this separate from the `>200 tok/s` single-user goal, but track it as the aggregate-throughput plan so production does not wait on a kernel breakthrough.

7. Formalize quality as a benchmark product.
   - Add deterministic canaries, structured validators, code checks, long-context needles, repeat stability, and BF16/current-model side-by-side prompts into one reproducible suite.
   - Publish every speed win with that suite. This is the guardrail that lets us attempt aggressive backend work without fooling ourselves.

8. File upstreamable issues before writing large local forks.
   - Good candidates: XPU graph capture needing exact speculative bucket `3`, n-gram3+ fully accepted bad loops, and oneCCL worker-count graph incompatibility.
   - If maintainers already have the right kernel or capture fix in a newer branch/container, adopting it may be faster than local reimplementation.

## Bigger Bets Added After Public Result Review

Follow-up after posting the accepted Quark W8A8 INT8 result to Localmaxxing and
querying the public board. Keep the target unchanged: Qwen3.6 35B-A3B, true
8-bit or better-quality-equivalent math, no Qwen3.5 detours, no 4-bit fallback
for the production-quality path.

Fresh public signals:

- Our approved Quark W8A8 INT8 entry is `99.428 tok/s` corrected decode,
  `98.163 tok/s` e2e output, p512/n512/c1/r4, `32K` context, on 4x Arc Pro
  B70 with strict frontdoor quality gates.
- The public Arc/B70 root-model entries for Qwen3.6 35B-A3B are mostly
  llama.cpp/SYCL Q4 variants around `68.8-70.35 tok/s` single stream. They are
  useful as Intel-stack signal, but they do not satisfy the current 8-bit
  quality target.
- The fastest public root-model Qwen3.6 35B-A3B single-user results are
  dominated by speculative methods: MTP, DFlash, or custom proposer/verifier
  stacks. That is the strongest external evidence that `>200 tok/s` probably
  needs verifier-preserving speculation or a real MoE/kernel/layout step, not
  another small launch-flag sweep.
- vLLM's Qwen3.5/Qwen3.6 recipe explicitly recommends MTP for low-concurrency
  latency work, while Intel's Arc Pro B-series guidance calls out persistent
  MoE and dynamic work balancing as first-class B-series levers.

Additional bigger ideas to track:

1. XPU MTP/DFlash-style proposer with Quark INT8 verifier.
   - Do not change the verifier. Use the current Quark W8A8 INT8 model to
     accept/reject final tokens.
   - Candidate proposers: official Qwen3.6 FP8 MTP tensors, a same-tokenizer
     Qwen3.6 draft, or a small local proposer trained/distilled only for
     acceptance rate.
   - First proof: memory headroom, canary parity, repeat64, structured JSON,
     and long-context needle before any headline speed number.

2. Import the newest Intel persistent-MoE path rather than re-discovering it.
   - Compare our `vllm-xpu-kernels` path against Intel's current XPU container
     or branch that claims persistent MoE GEMM plus fused activation wins on
     Qwen3-30B-A3B.
   - First proof: a standalone Qwen3.6 shape microbench showing that the
     persistent path actually covers Quark W8A8 INT8, not only FP8/W4 paths.

3. Route-aware expert locality.
   - Log real expert IDs for chat/code/structured/math prompts, then ask
     whether active top-8 experts are randomly distributed or cluster by prompt
     class.
   - If there is locality, try expert remapping/prepacking so frequent expert
     groups land on fewer cards or friendlier memory strides.
   - This preserves output math if only storage/order changes and routing IDs
     are remapped consistently.

4. Hybrid TP/EP layout with a traffic simulator first.
   - TP4 may be paying too many small collectives during single-token decode.
   - Build a byte/time simulator for attention/GDN, routed experts, shared
     expert, and output projection under TP4, TP2, EP4, and hybrid layouts.
   - Only start a vLLM architecture branch if the simulator predicts a clear
     single-token latency win and fits 32GB/card at 32K context.

5. Static solo decode lane.
   - Keep the accepted vLLM service for normal production, but build an
     internal one-user lane with fixed sampling, fixed graph buckets,
     preallocated KV, and minimal streaming/output machinery.
   - If the static lane is much faster, production can route solo sessions to
     it without weakening the general service.

6. Exact-shape collective replacement.
   - The repeated small BF16 hidden-state collectives are a better target than
     generic oneCCL replacement.
   - Create microbench repros for the exact AOT shapes, then test a graph-safe
     Level Zero/SYCL collective or fused collective+residual boundary.

7. XPU-native packed-layout fork of the same weights.
   - Keep the same Quark W8A8 quantized values but write a second packed layout
     optimized for Xe2 DPAS/XMX access.
   - This is a model-layout fork, not a quality fork. The acceptance criterion
     is bit/near-bit parity against the current Quark path under the quality
     suite.

8. OpenVINO/oneDNN GenAI 8-bit feasibility probe.
   - Treat this as an Intel-engine diagnostic, not a model switch.
   - If OpenVINO can run the same Qwen3.6 35B-A3B family with an 8-bit path and
     strong quality gates, it tells us whether vLLM/XPU overhead is the current
     ceiling.

9. Driver, firmware, and platform tuning as a measured matrix.
   - Public B70 posts repeatedly mention kernel/driver sensitivity, GT clock
     pinning, Level Zero behavior, and OS versions.
   - Track `xpu-smi` clocks/power, PCIe/NUMA locality, Resizable BAR, P2P,
     oneCCL thresholds, and `CCL_*` settings alongside every benchmark so a
     software win is not hiding a platform regression.

10. Formal upstream repro bundle.
    - Package three minimal public repros: Quark W8A8 INT8 MoE small-shape
      deficit, graph-safe collective issue, and speculative bucket/acceptance
      behavior.
    - The goal is to make Intel/vLLM maintainers able to reproduce the exact
      bottleneck without the full production stack.

Current prioritization:

1. Do next: determine whether our live Quark W8A8 INT8 MoE path already uses
   Intel's persistent/fused activation work. If not, test the available fused
   SiLU+quant and workspace toggles, then build the shape-exact microbench.
2. Do in parallel: feasibility check for verifier-preserving MTP/DFlash-style
   speculation using Qwen3.6 assets only.
3. Keep production planning separate: accepted TP4 remains the reliability
   baseline until a candidate passes the full quality and soak matrix.

## Fused SiLU+Quant Endpoint Retest

I retested the lower-level XPU MoE fused SiLU+quant hook against the current
accepted runtime after the public-result review.

Candidate env:

- `VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT=1`
- isolated cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-fusesiluquant-32k-noprefix`
- tmux: `qwen36-tp4-fusesiluquant-20260611`
- log: `/tmp/qwen36-quark-int8-tp4-fusesiluquant-20260611.log`

Runtime evidence:

- startup succeeded
- XPU Int8 MoE backend selected
- API `/health`: pass
- graph compile used the isolated cache

Speed artifacts:

- accepted live control:
  `data/qwen36-quark-int8-tp4-accepted-live-r2-20260611.json`
- fused SiLU+quant candidate:
  `data/qwen36-quark-int8-tp4-fusesiluquant-r2-20260611.json`

| metric | accepted live r2 | fused SiLU+quant r2 |
| --- | ---: | ---: |
| corrected output tok/s after first chunk | `99.6087` | `99.4856` |
| output tok/s e2e | `98.3716` | `98.1407` |
| mean client TTFT | `74.68 ms` | `80.58 ms` |

Decision:

- Reject again. This does not improve the single-request speed gate.
- Do not run the full quality gate for this candidate because the speed gate
  failed and prior fused SiLU+quant work already exposed quality/rounding risk.
- Do not spend more time on activation+quant fusion unless the implementation
  first proves exact staged-path parity in the shape microbench.

Restore:

- stopped candidate tmux
- restored accepted service as `qwen36-tp4-accepted-restored-20260611b`
- accepted `/health`: pass
- accepted response smoke: pass

## MoE Route Capture Tooling And Capture-Point Finding

I added diagnostic tooling for real expert-route histograms because Intel's
grouped-GEMM tuning issue explicitly calls out realistic token routing
distribution as a missing input for XPU MoE kernel work, and the Arc Pro
B-series write-up highlights persistent zero-gap MoE scheduling plus dynamic
work balancing as the major MoE lever.

Artifacts:

- vLLM patch artifact:
  `patches/vllm-qwen36-moe-route-capture-20260611.patch`
- diagnostic launcher:
  `scripts/launch-qwen36-quark-int8-route-capture.sh`
- route summarizer:
  `scripts/summarize-qwen36-moe-route-capture.py`
- capture-attempt summary:
  `data/qwen36-quark-int8-tp4-routecapture-attempts-20260611.json`

Implementation notes:

- `VLLM_MOE_ROUTE_CAPTURE_FILE` enables a JSONL capture hook on generic
  `BaseRouter` and leaves the default vLLM path unchanged.
- The hook writes per-call `counts`, `nonzero_experts`, `max_rows_per_expert`,
  shape, PID, rank, layer, and optional `topk_ids`.
- The route-capture wrapper uses an isolated cache, disables XPU graph, and can
  force `--enforce-eager` through `VLLM_EXTRA_ARGS` so production graph caches
  are not polluted.
- `scripts/launch-qwen36-quark-int8-accepted.sh` now preserves the same default
  graph-enabled behavior but allows explicit overrides for diagnostics.

Live result:

- Graph-enabled diagnostic run reached `/health`, but the hook first fired
  inside XPU graph capture and could not perform the CPU read:
  `wait method cannot be used for an event associated with a command graph`.
- I added a stream-capture guard in the hook and restarted with XPU graph
  disabled.
- I then restarted with `--enforce-eager`; logs confirmed
  `enforce_eager=True`, `Cudagraph is disabled under eager mode`, and XPU graph
  disabled.
- Even in eager mode, the generic `BaseRouter` hook produced no route JSONL
  files for the current Qwen3.6 Quark W8A8 INT8 runtime path.

Decision:

- Keep the tooling, but do not treat the generic router hook as sufficient for
  this model.
- The next capture point should move lower into the modular Quark/XPU path:
  `FusedMoEModularMethod.apply`, `FusedMoEKernel.apply`, or
  `vllm/model_executor/layers/fused_moe/experts/xpu_moe.py`, where `topk_ids`
  is definitely handed to the XPU expert kernel.
- This capture gap is useful because it explains why route histograms were not
  available from the generic abstraction despite all 40 layers showing the hook
  as enabled at startup.

Accepted service restore:

- stopped diagnostic route-capture tmux
- restored accepted service as `qwen36-tp4-accepted-restored-20260611c`
- accepted `/health`: pass
- accepted log confirms `enforce_eager=False`, XPU graph enabled, and graph
  capture completed.

## Bigger Bolder Ideas To Try

These are intentionally larger than launch-flag sweeps. The near-term goal is
still single-request speed without quality loss on the current Qwen3.6 35B-A3B
Quark W8A8 INT8 model.

Sources reviewed:

- Intel XPU grouped-GEMM tuning issue:
  `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`
- Intel Arc Pro B-series vLLM blog:
  `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`
- Intel `ai-containers` vLLM XPU release notes:
  `https://github.com/intel/ai-containers/blob/main/vllm/0.17.0-xpu.md`
- vLLM Intel Arc B580 30B+ settings issue:
  `https://github.com/vllm-project/vllm/issues/35638`

Ideas:

1. Capture route histograms at the XPU expert boundary.
   - Move the hook to the Quark/XPU MoE apply path and capture real
     prompt-class distributions for decode and prefill.
   - Use these histograms to tune or choose grouped-GEMM/persistent-MoE
     kernels instead of relying on uniform synthetic distributions.

2. Try the newest Intel XPU kernel stack as a branch comparison.
   - Intel's current container notes switched to `vllm-xpu-kernels` and report
     validated Arc Pro B-series support.
   - A clean branch compare may surface already-implemented persistent MoE,
     speculative, or scheduler changes faster than local reimplementation.

3. Build a persistent-MoE microbench with real captured rows-per-expert.
   - Reproduce the two Qwen3 MoE GEMMs under Quark W8A8 shapes.
   - Compare current XPU path, Intel grouped GEMM, and any persistent zero-gap
     implementation on the exact `topk_ids` distributions.

4. Expert hotness remapping without changing math.
   - If prompt classes repeatedly hit a small subset of experts, repack expert
     storage or remap logical IDs so hot experts have better memory locality.
   - Preserve output by applying the inverse mapping at the routing/kernel
     boundary.

5. Single-user static decode lane.
   - Keep vLLM as the production/concurrency baseline, but prototype a
     one-user path with fixed graph buckets, preallocated KV, fixed sampling,
     minimal output machinery, and no scheduler-generalization overhead.
   - If this proves much faster with identical tokens, route solo sessions to
     it and keep aggregate serving on vLLM.

6. Shape-exact collective replacement.
   - The current TP4 path likely still pays several small hidden-state
     collectives per token.
   - Build a replayable microbench for the exact hidden sizes and test fused
     collective plus residual/RMS or collective plus projection epilogues.

7. Verifier-preserving speculation with an XPU-native proposer.
   - N-gram speculation is not robust enough, but the public leaderboard
     suggests MTP/DFlash-style paths are the most realistic route past
     `200 tok/s`.
   - Keep the Quark W8A8 INT8 model as verifier and treat any proposer as
     disposable unless the full quality suite passes.

8. Quality-suite-as-product before bigger speed claims.
   - Expand canaries into a repeatable gate: deterministic token hashes,
     structured JSON/HTML validators, code execution, math, long-context
     needles, prompt-class screens, and soak tests.
   - Every bold backend change must pass this before a Localmaxxing submission.

9. Intel engine feasibility probe, not a model switch.
   - Test OpenVINO/oneDNN GenAI only to learn whether the same family can run
     faster with a high-quality 8-bit path on B70.
   - If it is fast, mine the layout/kernel strategy; if quality or model
     identity changes, do not promote it.

10. Production split: latency lane plus aggregate replicas.
    - Continue chasing single-request latency on TP4 or a solo lane.
    - Separately plan production aggregate throughput with multiple accepted
      replicas or TP2 pairs if single-request kernel work takes longer.

## Route Capture Correction And Result

Follow-up on the generic-router capture conclusion above: the initial "no route
files" finding was partly a filename-glob mistake. The diagnostic launcher's
default `CAPTURE_FILE` used a literal `{pid}` inside a Bash default-parameter
expansion, and Bash consumed the closing brace. Files were written as malformed
paths such as `/tmp/qwen36-moe-routes-routecapture4-{pid.jsonl}`. The launcher
now builds the default path in two string pieces so Python can substitute
`{pid}` correctly on future runs.

Lower-hook capture was added at three points:

- `BaseRouter` capture, stage `router`.
- `FusedMoEModularMethod.apply`, stage `modular_apply`.
- `QuarkW8A8Int8MoEMethod.apply`, stage `quark_int8_apply`.
- A diagnostic monolithic fallback in `MoERunner._apply_quant_method`, stage
  `runner_pre_monolithic`, for future kernels that hide `topk_ids` inside a
  monolithic apply path.
- incremental patch artifact:
  `patches/vllm-qwen36-moe-route-capture-lower-hooks-20260611.patch`

Bounded routecapture4 diagnostic:

- tmux: `qwen36-tp4-routecapture4-20260611`
- graph/eager controls: XPU graph disabled, `--enforce-eager`
- request: one 22-token prompt, 64 generated tokens
- raw route artifact:
  `data/qwen36-quark-int8-tp4-routecapture4-routes-20260611.jsonl`
- summary artifact:
  `data/qwen36-quark-int8-tp4-routecapture4-summary-20260611.json`
- records: `21,120`
- layers: `40`
- total assignments: `21,312,000`
- stages observed per layer: `router` and `quark_int8_apply`

Interpretation:

- The current Quark W8A8 INT8 path does reach `QuarkW8A8Int8MoEMethod.apply`,
  so it is not using the monolithic fallback for this run.
- The summary double-counts routes because both `router` and
  `quark_int8_apply` captured the same `topk_ids`. For microbench input, use
  one stage only, preferably `quark_int8_apply`, or de-duplicate by
  layer/pid/call/shape.
- The first record shows the large warmup/prefill shape `[8192, 8]`, so the
  current capture is useful for shape discovery but is not yet a clean
  decode-only route histogram. The next capture should filter to one stage,
  use `CAPTURE_LAYER_REGEX` for a few layers, and run a post-warmup decode
  sequence so the histogram reflects steady-state generation.

Accepted service restore after this diagnostic:

- stopped routecapture4
- restored accepted service as `qwen36-tp4-accepted-restored-20260611d`
- accepted `/health`: pass
- accepted log confirms graph capture completed and
  `VLLM_XPU_FORCE_GRAPH_WITH_COMM=1` is active.

## More Big Ideas Added After Real Route Capture

1. Stage-filtered route histograms for actual decode.
   - Capture only `quark_int8_apply`, discard warmup/prefill, and collect
     separate histograms for natural chat, code, structured, and math prompts.
   - Feed those histograms directly into grouped-GEMM and persistent-MoE
     microbenches.

2. GPU-side route counters.
   - The current capture copies `topk_ids` to CPU and therefore cannot be used
     during accepted graph-captured speed runs.
   - A tiny XPU-side histogram op could capture real routes under graph replay
     with much lower perturbation, then flush counts after the request.

3. Hot-expert-aware packing.
   - The route summary already shows strong expert skew. If the skew remains
     stable after decode-only capture, pack hot experts into memory layouts
     that favor contiguous DPAS/XMX access and lower cache/TLB churn.
   - This preserves math if the logical-to-physical expert map is handled at
     the kernel boundary.

4. Route-distribution-aware kernel policy.
   - Instead of one grouped-GEMM policy for all MoE calls, pick kernel
     parameters from the observed rows-per-expert distribution: sparse long
     tail, hot few experts, or near-uniform.
   - This is likely more valuable than synthetic uniform MoE benchmarks.

5. Decode-only route replay harness.
   - Record hidden-state shape, top-k IDs, and expert row counts for one layer,
     then replay the current XPU MoE path outside vLLM.
   - This makes persistent-MoE, prepack, activation fusion, and epilogue
     fusion measurable without full endpoint startup.

6. Kernel-stack branch bakeoff against Intel's newest XPU container.
   - Keep the model/quantization fixed and compare our local stack to the
     newest `vllm-xpu-kernels` container or branch.
   - If Intel already has persistent MoE or better W8A8 policy for Qwen3 A3B
     shapes, porting may beat local kernel ownership.

7. Speculation plus route-aware verifier scheduling.
   - If a proposer is eventually used, route histograms can show whether
     speculative verifier bursts stress different experts than normal decode.
   - A verifier-preserving MTP/EAGLE lane should be benchmarked with route
     capture too; a speedup that overloads one expert shard may not hold under
     real prompt mixes.

8. Production reliability loops tied to route skew.
   - Long-running stale-process failures might correlate with specific graph
     shapes or expert hot spots.
   - Add route-shape counters to future 30-60 minute soaks so reliability bugs
     can be tied to model paths instead of only wall-clock age.

## Decode-Only Route Filters And Exact-ID Capture

Added stage/token filters so route capture can target steady-state decode
instead of mixing warmup, prefill, router, and expert-apply records:

- vLLM env patch artifact:
  `patches/vllm-qwen36-moe-route-capture-stage-token-filters-20260611.patch`
- launcher controls:
  - `CAPTURE_STAGE_REGEX`
  - `CAPTURE_MIN_NUM_TOKENS`
  - `CAPTURE_MAX_NUM_TOKENS`
- summarizer filters:
  - `--stage-regex`
  - `--layer-regex`
  - `--min-num-tokens`
  - `--max-num-tokens`
- summarizer now records `records_loaded`, active filters, and exact
  `topk_tuples` when raw `topk_ids` are present.

Decode-only summary from routecapture4:

- input: `data/qwen36-quark-int8-tp4-routecapture4-routes-20260611.jsonl`
- summary:
  `data/qwen36-quark-int8-tp4-routecapture4-quark-decode-summary-20260611.json`
- filter: `stage_regex=^quark_int8_apply$`, `max_num_tokens=4`
- records loaded: `21,120`
- records summarized: `10,080`
- layers: `40`
- assignments: `80,640`
- stage: `quark_int8_apply`
- decode shapes: all first-layer records were `[1, 8]`
- hottest global experts in this capture: `151`, `35`, `20`, `165`, `47`

Interpretation: decode is not uniform. It has enough expert skew to justify
route-distribution-aware kernel policy, but routecapture4 does not include exact
`topk_ids`, so it is not sufficient for replaying real route tuples.

Exact-ID routecapture5:

- launch controls:
  - `CAPTURE_STAGE_REGEX=^quark_int8_apply$`
  - `CAPTURE_LAYER_REGEX=language_model\\.model\\.layers\\.(8|20)\\.mlp\\.experts`
  - `CAPTURE_MIN_NUM_TOKENS=1`
  - `CAPTURE_MAX_NUM_TOKENS=1`
  - `CAPTURE_INCLUDE_IDS=1`
  - `CAPTURE_MAX_LINES=1000`
- speed artifact from diagnostic request:
  `data/qwen36-quark-int8-tp4-routecapture5-chat-natural-p192o128-20260611.json`
- raw route artifacts:
  - `data/qwen36-quark-int8-tp4-routecapture5-routes-rank0-20260611.jsonl`
  - `data/qwen36-quark-int8-tp4-routecapture5-routes-rank1-20260611.jsonl`
  - `data/qwen36-quark-int8-tp4-routecapture5-routes-rank2-20260611.jsonl`
  - `data/qwen36-quark-int8-tp4-routecapture5-routes-rank3-20260611.jsonl`
- all-rank summary:
  `data/qwen36-quark-int8-tp4-routecapture5-exact-id-summary-20260611.json`
- rank0 replay summary:
  `data/qwen36-quark-int8-tp4-routecapture5-exact-id-rank0-summary-20260611.json`

The diagnostic request is not a speed result because exact-ID CPU capture slows
the model. It exists to produce replay input.

Important routecapture5 findings:

- All four TP ranks recorded duplicate logical routes, so replay should start
  from rank0 or de-duplicate across ranks.
- Rank0 has `254` records: `127` decode tokens for layer 8 and `127` for layer
  20.
- Both layers captured exact `topk_ids` with shape `[1, 8]`.
- Layer 8:
  - active experts: `117`
  - aggregate max expert share: `0.0827`
  - examples:
    - `[77,173,224,180,4,99,191,20]`
    - `[173,4,180,20,61,191,116,84]`
    - `[224,117,151,206,41,121,249,20]`
- Layer 20:
  - active experts: `125`
  - aggregate max expert share: `0.06`
  - examples:
    - `[224,116,237,239,99,56,191,151]`
    - `[237,17,127,223,235,116,104,11]`
    - `[117,206,151,53,41,224,143,203]`

Interpretation:

- Exact top-k tuples are mostly unique per token in this prompt. The first
  replay target is therefore not a repeated-tuple fast path.
- The usable signal is expert frequency skew and layer-specific route shape,
  especially for layer/prompt-class policy selection.
- A real-route microbench should compare:
  - synthetic uniform top-k IDs
  - routecapture5 rank0 exact top-k sequence
  - sorted/hot-expert physical packing with the same logical IDs
  - layer-specific policy choices for layer 8 versus layer 20

Post-restore accepted baseline after the diagnostic:

- tmux: `qwen36-tp4-accepted-restored-20260611e`
- health: pass on `127.0.0.1:18080`
- speed artifact:
  `data/qwen36-quark-int8-tp4-post-restore-chat-natural-p192o128-20260611.json`
- direct chat natural p192/n128:
  - output tok/s after first chunk: `100.156`
  - corrected output tok/s after first chunk: `99.373`
  - e2e output tok/s: `93.442`
  - TTFT: `91.83 ms` client, `90.39 ms` from vLLM metrics

Direct quality gate detail:

- The direct vLLM endpoint emits thinking content unless told otherwise, so the
  direct quality suite must pass:
  `--chat-template-kwargs-json '{"enable_thinking": false}'`
- wrong-mode artifact:
  `data/qwen36-quark-int8-tp4-post-restore-quality-smoke-20260611.json`
- correct no-thinking artifact:
  `data/qwen36-quark-int8-tp4-post-restore-quality-smoke-nothink-20260611.json`
- result: exact canaries, copy phrase, arithmetic, JSON schema, and repeat
  smoke all passed.

## Bigger Ideas Added After Exact Route Capture

1. Route replay before kernel changes.
   - Implemented in `scripts/bench-qwen36-int8-moe-kernels.py` with
     `--route-jsonl`, `--route-layer-regex`, `--route-stage-regex`,
     `--route-min-num-tokens`, `--route-max-num-tokens`, and
     `--route-start-index`.
   - Feed the rank0 exact `topk_ids` sequence into the current microbench so
     future kernel work measures real decode skew, not synthetic uniform routes.
   - This is the next safest engineering step because it changes measurement,
     not model math.
   - Lightweight loader check for layer 8 selected `127` top-k rows and `117`
     active experts from the rank0 routecapture5 JSONL.

2. Layer-specific MoE policy.
   - Layer 8 and layer 20 already show different hot-expert profiles.
   - A single global grouped-GEMM policy may be leaving performance on the table.
   - Try a table-driven policy keyed by layer, top-k shape, and rows-per-expert
     histogram. Keep policy selection outside the math path so parity is easy to
     test.

3. Hot-expert physical packing.
   - Repack expert weights so frequent experts in a layer are physically near
     each other or use a more favorable tile layout.
   - Preserve logical expert IDs by applying a logical-to-physical map at the
     kernel boundary.
   - Quality proof should be straightforward because the numeric weights and
     scales do not change.

4. Decode-route graph specialization.
   - Generate a few graph/kernel variants for observed route classes:
     hot-skewed, long-tail, and near-uniform.
   - Dispatch by a cheap route histogram instead of using one generic path for
     every token.
   - This is higher risk than packing because it changes scheduling, but it
     could matter if branch/launch overhead dominates small-M decode.

5. GPU-side route telemetry.
   - CPU `topk_ids` capture is too invasive for accepted graph-captured speed
     runs.
   - Add a tiny graph-safe XPU histogram collector that increments per-layer
     expert counters and flushes after the request.
   - Use it in reliability soaks to correlate device instability, graph shapes,
     and expert hot spots.

6. Prompt-class expert cache.
   - Capture route histograms for natural chat, code, math, and structured
     prompts separately.
   - If prompt classes have stable expert hot sets, prefetch or pin those expert
     layouts before long decode runs.
   - This is still quality-preserving because it only affects placement/cache
     behavior.

7. Speculation plus route burst analysis.
   - If MTP/DFlash returns, capture verifier route bursts when multiple draft
     tokens are verified together.
   - A speculative path can look fast in token accounting but still overload
     specific expert/layout paths. Route telemetry should be part of the
     speculation quality/performance gate.

8. Upstreamable grouped-GEMM replay artifact.
   - Package the rank0 exact route file plus a small benchmark harness as a
     minimal Intel/vLLM issue or PR.
   - Intel's public grouped-GEMM tuning issue explicitly asks for realistic
     route distributions; this gives them a concrete B70/Qwen3.6 example.

9. Static one-user decode runner with route replay.
   - Build the offline runner around the same route-capture/replay machinery.
   - It should report model-core tok/s independent of OpenAI streaming overhead
     and tell us whether the `~100 tok/s` ceiling is server-side or kernel-side.

10. Production dual-track plan.
    - Keep the accepted TP4 service as the quality oracle and reliability base.
    - Develop route replay, MTP proposer, and static decode lane as opt-in
      branches.
    - Do not promote any branch until it passes no-thinking direct quality,
      frontdoor quality, repeat64 or stronger, and a short stability soak.

## Route Replay Microbench

I stopped the accepted endpoint temporarily to free XPU memory, ran the route
replay microbench on one B70 (`ONEAPI_DEVICE_SELECTOR=level_zero:0`), then
restored the accepted service as `qwen36-tp4-accepted-restored-20260611f`.
Restore health passed after `62s`, and a direct no-thinking chat canary returned
exactly `OK`.

Code changes:

- `scripts/bench-qwen36-int8-moe-kernels.py`
  - route replay: `--route-jsonl`, `--route-layer-regex`,
    `--route-stage-regex`, token-count filters, `--route-start-index`, and
    multi-window `--route-start-indices`
  - hot-expert packing simulation: `--route-pack-hot-experts`

Artifacts:

- summary: `data/qwen36-quark-int8-moe-route-replay-summary-20260611.json`
- synthetic route baseline:
  `data/qwen36-quark-int8-moe-synthetic-uniform-r30-20260611.json`
- routecapture5 layer 8:
  `data/qwen36-quark-int8-moe-routecapture5-layer8-r30-20260611.json`
- routecapture5 layer 8 hot-pack simulation:
  `data/qwen36-quark-int8-moe-routecapture5-layer8-hotpack-r30-20260611.json`
- routecapture5 layer 20:
  `data/qwen36-quark-int8-moe-routecapture5-layer20-r30-20260611.json`
- routecapture5 layer 20 hot-pack simulation:
  `data/qwen36-quark-int8-moe-routecapture5-layer20-hotpack-r30-20260611.json`
- rows=1 r100 confirmations:
  - `data/qwen36-quark-int8-moe-synthetic-uniform-row1-r100-20260611.json`
  - `data/qwen36-quark-int8-moe-routecapture5-layer8-row1-r100-20260611.json`
  - `data/qwen36-quark-int8-moe-routecapture5-layer8-hotpack-row1-r100-20260611.json`
  - `data/qwen36-quark-int8-moe-routecapture5-layer20-row1-r100-20260611.json`
  - `data/qwen36-quark-int8-moe-routecapture5-layer20-hotpack-row1-r100-20260611.json`
- rows=16 r100 confirmations:
  - `data/qwen36-quark-int8-moe-synthetic-uniform-row16-r100-20260611.json`
  - `data/qwen36-quark-int8-moe-routecapture5-layer8-row16-r100-20260611.json`
  - `data/qwen36-quark-int8-moe-routecapture5-layer8-hotpack-row16-r100-20260611.json`
  - `data/qwen36-quark-int8-moe-routecapture5-layer20-row16-r100-20260611.json`
  - `data/qwen36-quark-int8-moe-routecapture5-layer20-hotpack-row16-r100-20260611.json`

Representative commands:

```bash
export PYTHONPATH="/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export ONEAPI_DEVICE_SELECTOR=level_zero:0
export ZE_AFFINITY_MASK=0

/home/steve/.venvs/vllm-xpu/bin/python scripts/bench-qwen36-int8-moe-kernels.py \
  --rows 1,2,4,8,16 \
  --iterations 30 \
  --warmup 5 \
  --route-jsonl data/qwen36-quark-int8-tp4-routecapture5-routes-rank0-20260611.jsonl \
  --route-layer-regex 'layers\.8\.' \
  --output-json data/qwen36-quark-int8-moe-routecapture5-layer8-r30-20260611.json

/home/steve/.venvs/vllm-xpu/bin/python scripts/bench-qwen36-int8-moe-kernels.py \
  --rows 1 \
  --iterations 100 \
  --warmup 10 \
  --route-pack-hot-experts \
  --route-jsonl data/qwen36-quark-int8-tp4-routecapture5-routes-rank0-20260611.jsonl \
  --route-layer-regex 'layers\.8\.' \
  --output-json data/qwen36-quark-int8-moe-routecapture5-layer8-hotpack-row1-r100-20260611.json
```

Key r100 results:

| route | rows | total us | preallocated staged us | active experts | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| synthetic uniform | 1 | `280.177` | `214.114` | `8` | baseline single-token synthetic |
| layer 8 route | 1 | `275.725` | `207.704` | `8` | real route slightly faster |
| layer 8 hot-pack | 1 | `269.063` | `207.094` | `8` | small `2.4%` win over layer 8 raw route |
| layer 20 route | 1 | `293.932` | `225.293` | `8` | real route slower than synthetic |
| layer 20 hot-pack | 1 | `317.498` | `241.818` | `8` | hot-pack hurts this first-token sample |
| synthetic uniform | 16 | `377.275` | `338.070` | `128` | activates many experts |
| layer 8 route | 16 | `275.846` | `213.241` | `39` | much faster due fewer active experts |
| layer 8 hot-pack | 16 | `269.593` | `207.745` | `39` | small `2.3%` win |
| layer 20 route | 16 | `278.397` | `212.985` | `45` | much faster than synthetic |
| layer 20 hot-pack | 16 | `274.965` | `211.205` | `45` | small `1.2%` win |

Interpretation:

- Real route replay matters. Synthetic uniform rows=16 is pessimistic because it
  activates `128` experts, while real layer 8 and layer 20 replay activate only
  `39` and `45` experts respectively.
- For the actual single-token decode shape, physical expert ID/layout effects
  are layer-dependent and not yet large enough to justify a blind global expert
  remap. Layer 8 gained slightly from hot packing; layer 20 lost on the first
  captured row.
- The preallocated staged path is still consistently faster than the
  `xpu_fused_moe` wrapper in isolation, but the existing endpoint
  `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1` screen was already rejected because
  full-model decode did not improve and KV headroom dropped. Do not promote
  scratch reuse on microbench evidence alone.
- The next kernel work should be layer/prompt-route aware:
  1. collect full-prompt-class route captures,
  2. benchmark route windows across multiple `route_start_index` values,
  3. identify layers where physical packing consistently helps,
  4. then prototype a real weight-layout remap only for those layers.

### Route Start-Index Scan

Added `--route-start-indices` to scan multiple captured route windows in one
process. Syntax supports comma lists and Python-style ranges such as
`0:128:16`. I stopped the accepted endpoint, ran a bounded one-B70 scan, then
restored the accepted service as `qwen36-tp4-accepted-restored-20260611g`.
Restore health passed, and the direct no-thinking chat canary returned exactly
`OK`.

Artifacts:

- summary:
  `data/qwen36-quark-int8-moe-routecapture5-startscan-summary-20260611.json`
- layer 8 raw:
  `data/qwen36-quark-int8-moe-routecapture5-layer8-startscan-r15-20260611.json`
- layer 8 hot-pack:
  `data/qwen36-quark-int8-moe-routecapture5-layer8-hotpack-startscan-r15-20260611.json`
- layer 20 raw:
  `data/qwen36-quark-int8-moe-routecapture5-layer20-startscan-r15-20260611.json`
- layer 20 hot-pack:
  `data/qwen36-quark-int8-moe-routecapture5-layer20-hotpack-startscan-r15-20260611.json`

Representative command:

```bash
/home/steve/.venvs/vllm-xpu/bin/python scripts/bench-qwen36-int8-moe-kernels.py \
  --rows 1,16 \
  --iterations 15 \
  --warmup 3 \
  --route-start-indices 0:128:16 \
  --route-jsonl data/qwen36-quark-int8-tp4-routecapture5-routes-rank0-20260611.jsonl \
  --route-layer-regex 'layers\.8\.' \
  --output-json data/qwen36-quark-int8-moe-routecapture5-layer8-startscan-r15-20260611.json
```

Start-window scan summary:

| layer | rows | windows | raw total us | hot-pack total us | hot-pack total delta | preallocated delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 8 | 1 | 8 | `301.105` | `345.485` | `+16.39%` | `+15.38%` |
| 8 | 16 | 8 | `341.296` | `303.902` | `-10.49%` | `-8.51%` |
| 20 | 1 | 8 | `278.416` | `262.954` | `-5.06%` | `-3.23%` |
| 20 | 16 | 8 | `272.476` | `276.398` | `+1.52%` | `+2.59%` |

Interpretation:

- Hot-expert physical packing is not a global win. It helped layer 8 rows=16
  and layer 20 rows=1, but hurt layer 8 rows=1 and layer 20 rows=16.
- The earlier first-window rows=1 result was not sufficient evidence for or
  against remapping. Route window selection changes the sign and magnitude.
- A production-safe layout remap would need layer-specific and likely
  prompt-class-specific proof. A blind global expert remap is rejected.
- The next useful scan is broader route capture across prompt classes, then a
  layer-by-layer heatmap of where packing, grouped-GEMM policy, or persistent
  scheduling consistently wins.

### Route Heatmap Analyzer

Added `scripts/analyze-qwen36-moe-route-heatmap.py` to turn one or more labeled
route summaries/JSONL captures into a layer ranking. It computes route locality
signals including top-N expert share, max expert share, active-expert share,
entropy, and cross-label top-expert overlap. This is a planning tool for
choosing layers for route-window scans, persistent MoE prototypes, or
shape-exact grouped-GEMM repros.

Artifacts:

- all-layer decode plus exact-ID heatmap:
  `data/qwen36-quark-int8-tp4-routecapture-heatmap-20260611.json`
- raw JSONL validation heatmap:
  `data/qwen36-quark-int8-tp4-routecapture5-jsonl-heatmap-20260611.json`

Commands:

```bash
python3 scripts/analyze-qwen36-moe-route-heatmap.py \
  --input decode=data/qwen36-quark-int8-tp4-routecapture4-quark-decode-summary-20260611.json \
  --input exact_ids=data/qwen36-quark-int8-tp4-routecapture5-exact-id-rank0-summary-20260611.json \
  --out data/qwen36-quark-int8-tp4-routecapture-heatmap-20260611.json \
  --limit 24

python3 scripts/analyze-qwen36-moe-route-heatmap.py \
  --input exact_jsonl=data/qwen36-quark-int8-tp4-routecapture5-routes-rank0-20260611.jsonl \
  --stage-regex '^quark_int8_apply$' \
  --max-num-tokens 1 \
  --out data/qwen36-quark-int8-tp4-routecapture5-jsonl-heatmap-20260611.json \
  --limit 12
```

Current top all-layer decode targets by route-locality priority:

| rank | layer | labels | top16 share | max share | active expert share |
| ---: | ---: | --- | ---: | ---: | ---: |
| 1 | 9 | decode | `0.5694` | `0.0813` | `0.3359` |
| 2 | 8 | decode, exact_ids | `0.5856` | `0.0919` | `0.3926` |
| 3 | 21 | decode | `0.5615` | `0.0496` | `0.3594` |
| 4 | 14 | decode | `0.5595` | `0.0774` | `0.3359` |
| 5 | 20 | decode, exact_ids | `0.5738` | `0.0737` | `0.4043` |

Interpretation:

- Layer 9 is now the best first target for a new route-window scan because it
  has the strongest all-layer decode locality signal and was not in the first
  exact-ID route replay.
- Layers 8 and 20 remain useful because exact IDs already exist, but the heatmap
  says layer 21 and layer 14 should join the next capture set.
- Future prompt-class captures should be passed as separate labels so we can
  see whether hot experts persist across natural chat, code, structured, math,
  and repetitive prompts. A layer with high locality and high cross-label
  overlap is the safest layout/kernel target.

### Routecapture6 Exact-ID Scan

Launched a bounded route-capture service for heatmap-selected layers `9`, `14`,
and `21`:

- `CAPTURE_INCLUDE_IDS=1`
- `CAPTURE_LAYER_REGEX='layers\.(9|14|21)\.'`
- `CAPTURE_STAGE_REGEX='^quark_int8_apply$'`
- `CAPTURE_MIN_NUM_TOKENS=1`
- `CAPTURE_MAX_NUM_TOKENS=1`
- diagnostic service: XPU graph disabled, eager route-capture wrapper
- prompt: natural-chat p192/o96, one repeat

The capture service was stopped after collection. I ran the microbench on one
B70, then restored the accepted service as
`qwen36-tp4-accepted-restored-20260611h`. Restore health passed, and the direct
no-thinking canary returned exactly `OK`.

Artifacts:

- prompt run:
  `data/qwen36-quark-int8-tp4-routecapture6-chat-natural-p192o96-20260611.json`
- representative rank0 route IDs:
  `data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`
- route summary:
  `data/qwen36-quark-int8-tp4-routecapture6-exact-id-rank0-summary-20260611.json`
- heatmap:
  `data/qwen36-quark-int8-tp4-routecapture6-heatmap-20260611.json`
- start-scan summary:
  `data/qwen36-quark-int8-moe-routecapture6-startscan-summary-20260611.json`
- per-layer raw/hotpack scans:
  - `data/qwen36-quark-int8-moe-routecapture6-layer9-startscan-r15-20260611.json`
  - `data/qwen36-quark-int8-moe-routecapture6-layer9-hotpack-startscan-r15-20260611.json`
  - `data/qwen36-quark-int8-moe-routecapture6-layer14-startscan-r15-20260611.json`
  - `data/qwen36-quark-int8-moe-routecapture6-layer14-hotpack-startscan-r15-20260611.json`
  - `data/qwen36-quark-int8-moe-routecapture6-layer21-startscan-r15-20260611.json`
  - `data/qwen36-quark-int8-moe-routecapture6-layer21-hotpack-startscan-r15-20260611.json`

Captured route counts:

| layer | records | tokens | active experts | top expert |
| ---: | ---: | ---: | ---: | --- |
| 9 | `95` | `95` | `111` | expert `61`, count `43` |
| 14 | `95` | `95` | `126` | expert `189`, count `37` |
| 21 | `95` | `95` | `119` | expert `243`, count `44` |

Routecapture6 heatmap ranking:

| rank | layer | top16 share | max share | active expert share |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 9 | `0.5105` | `0.0566` | `0.4336` |
| 2 | 21 | `0.4895` | `0.0579` | `0.4648` |
| 3 | 14 | `0.4211` | `0.0487` | `0.4922` |

Route-window scan summary:

| layer | rows | windows | raw total us | hot-pack total us | hot-pack total delta | preallocated delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 9 | 1 | 8 | `289.268` | `276.010` | `-3.78%` | `-3.33%` |
| 9 | 16 | 8 | `271.857` | `275.624` | `+1.60%` | `+5.14%` |
| 14 | 1 | 8 | `283.335` | `293.652` | `+3.63%` | `+3.85%` |
| 14 | 16 | 8 | `271.787` | `305.817` | `+12.57%` | `+17.04%` |
| 21 | 1 | 8 | `292.796` | `316.202` | `+8.72%` | `+5.54%` |
| 21 | 16 | 8 | `314.961` | `303.593` | `-2.31%` | `-1.04%` |

Interpretation:

- The heatmap successfully found high-locality layers, but physical hot-pack
  remap is still not a general decode win.
- Layer 14 should not be a hot-pack remap target from this evidence; it
  regressed for rows=1 and rows=16.
- Layer 9 may be useful for single-token decode layout/policy, but the rows=16
  regression means any change must be guarded by shape/layer policy.
- Layer 21 has the inverse shape behavior: it regressed rows=1 and helped
  rows=16 slightly.
- The next non-speculative speed path should shift from blind physical remap to
  persistent MoE/grouped-GEMM scheduling for high-locality layers, using these
  exact route streams as parity/performance repros.

## Things To Try After Route Replay

Added after the route-replay microbench and another quick pass over public
Arc/XPU/vLLM material. These are ordered by how much signal they should give per
engineering hour, not by ambition.

Immediate experiments:

1. Multi-window route replay.
   - Initial support is implemented and a layer 8/20 scan is recorded above.
   - Next step is to extend it to more layers and prompt classes, then report
     mean/min/max heatmaps instead of isolated windows.
   - Decision rule remains: only consider expert remap if the same layer
     improves across many windows and prompt classes.

2. Full prompt-class route capture.
   - Capture real routes for natural chat, code, structured, math, and
     repetitive prompts.
   - Build per-layer expert histograms and expert-pair/group co-occurrence
     tables.
   - Use those histograms as kernel-tuning input. Intel's grouped-GEMM issue
     explicitly calls out long-tail routing skew as a performance driver, and
     our rows=16 replay already proved synthetic uniform routing is misleading.

3. Shape-exact single-layer replay with real tensors.
   - Move beyond random hidden states: capture one decode token's hidden state,
     router outputs, scales, and expert IDs for a target layer.
   - Replay that layer through the current staged path, preallocated staged path,
     and any new persistent/grouped-GEMM path.
   - This gives a parity target before endpoint integration.

4. XPU graph capture policy screen.
   - Test decode-oriented graph modes and explicit capture buckets for the
     small query lengths we actually use, especially `3`, `4`, `5`, and `6`
     around speculative decode.
   - The n-gram2 capture-size-3 result says graph shape coverage can be the
     difference between device loss and a valid run.

5. oneCCL tiny-collective thresholds.
   - Avoid `CCL_WORKER_COUNT=2` for graph-captured production until the SYCL
     scheduler route is known safe.
   - Test only narrow, reversible small-message thresholds and monolithic
     options tied to AOT-observed hidden-state collective shapes.

6. Accepted-pack validation refresh.
   - Before testing a risky branch, refresh accepted r8/r10 speed, repeat64,
     long-context needle, no-thinking direct canary, and peak VRAM.
   - The stale-process quality failure means candidate comparisons need a
     same-day accepted control, not an old public number.

Medium engineering branches:

1. Import-or-compare Intel's newest persistent MoE path.
   - First try to reproduce the Intel Arc Pro B-series persistent-MoE claims in
     a disposable container or branch against a Qwen3 A3B model.
   - Then check whether the same kernel path covers Quark W8A8 INT8, not just
     MXFP4/FP8 or GPT-OSS recipes.
   - If it does not cover us, use the gap as an upstream issue or patch target.

2. Quark INT8 packed-layout cache.
   - Keep exactly the same quantized values and scales, but store a B70-friendly
     packed layout for repeated W8A8 GEMM reads.
   - Add checksums and a dequantized parity test so it is clearly a layout
     optimization, not a hidden requantization.

3. Static solo latency lane.
   - Build an offline/direct runner first: same tokenizer, same chat template,
     same generation params, same weights, no OpenAI server machinery.
   - If offline decode is much faster than served decode, build a production
     low-latency lane for one active session.
   - If offline decode is still near `100 tok/s`, server overhead is not the
     main blocker.

4. Hybrid TP/EP simulator.
   - Estimate bytes and synchronization points per token for TP4, TP2, EP-like,
     and hybrid layouts before changing vLLM internals.
   - Include 32K KV memory, shared expert, routed experts, GDN/attention, output
     projection, and vocab head.
   - Only branch into a real hybrid layout if the simulator predicts a clear
     single-token latency win.

5. Same-model true-8-bit engine shootout.
   - Compare current vLLM Quark W8A8 with llama.cpp/SYCL Q8_0, OpenVINO GenAI,
     or another Intel-native 8-bit route only if the model/template/quality
     gates can match.
   - This is a diagnostic for whether vLLM/XPU is the ceiling. It is not a
     license to switch to Qwen3.5, AWQ, GPTQ-4bit, or a Q4 GGUF.

Moonshots worth tracking:

1. Self-speculative early-exit proposer.
   - Use lower layers of the same Qwen3.6 model as a cheap proposer and verify
     with the full current Quark INT8 model.
   - Advantage: no separate 35B drafter in VRAM.
   - Risk: Qwen3.6 is not necessarily trained for early-exit logits, so
     acceptance may be poor. Final quality is still preserved only if the full
     verifier accepts every emitted token.

2. Auxiliary FP8 MTP sidecar.
   - The current Quark checkpoint has no MTP tensors, but the official FP8
     checkpoint does.
   - Treat FP8 MTP as a proposer only; the current Quark W8A8 INT8 model remains
     the verifier.
   - First blocker to measure is memory. If two-model serving does not fit at
     32K, test a separate sidecar process or a reduced-context diagnostic before
     spending kernel time.

3. EAGLE/DFlash-style proposer on XPU.
   - Public high-end Qwen3.6 rows above `200 tok/s` are mostly speculative. The
     useful lesson is the architecture, not the hardware comparison.
   - Porting a trainable proposer that has high acceptance on chat/code prompts
     may be a better route than deeper n-gram, which already failed repeat64 at
     depth 3+.

4. Persistent single-token MoE executor.
   - Build a dedicated decode-only executor for the exact Qwen3.6 expert shapes:
     persistent workgroups, dynamic work claiming, prepacked weights, fused
     activation/finalize, and graph-safe output handoff.
   - This is likely the real kernel path if we want a non-speculative 2x.

5. Exact-shape collective plus epilogue fusion.
   - Replace only the repeated BF16 hidden-size collectives seen in the AOT
     census, and fuse the immediate residual/RMS or MoE finalize work where
     mathematically safe.
   - This avoids trying to outbuild all of oneCCL while still targeting the
     expensive small-message path.

6. Route-aware expert placement across cards.
   - If prompt-class captures show stable hot expert groups, place or pack those
     groups to reduce fragmented memory access and possibly reduce cross-card
     movement.
   - This needs routing-ID remap parity tests, because a wrong expert order is a
     silent quality break.

7. Production split if `>200 tok/s` remains blocked.
   - Keep chasing single-request speed, but design production around what is
     already real: a quality-clean TP4 baseline, possible replicas for
     aggregate throughput, and a separate experimental latency lane.
   - Do not let aggregate throughput work obscure the single-user target, but
     track it so production deployment is not waiting on one speculative or
     kernel moonshot.

High-level priority:

1. Next command path: route-start-index scans plus prompt-class route capture.
2. Highest-upside path: verifier-preserving MTP/EAGLE/self-speculation.
3. Highest-durability path: persistent MoE and exact-shape grouped-GEMM repros
   that can be upstreamed to `vllm-xpu-kernels`.

## Additional Bigger Bets And Notes To Try

Added after the route heatmap/startscan work and the fresh Localmaxxing/API
comparison pass. These are not accepted results; they are the next idea bank.

Ideas to try soon:

1. Cross-engine drafter bridge.
   - Run a Qwen3.6 MTP-capable llama.cpp/GGUF sidecar only as a token proposer,
     then verify every proposed token with the current vLLM Quark W8A8 INT8
     service.
   - This might let us borrow mature `--spec-type mtp` behavior without moving
     production serving off the current model.
   - Hard parts: tokenizer/template parity, streaming verifier protocol, KV
     state rewind on rejection, and enough drafter speed to beat the extra IPC.

2. Official-FP8 MTP sidecar extraction.
   - The Quark checkpoint has no `mtp.*` tensors, while the official FP8
     snapshot does. Extract only the MTP/proposer pieces and test whether they
     can run as an auxiliary proposer against the Quark verifier.
   - If the full FP8 target cannot fit beside Quark at 32K, try reduced-context
     sidecar diagnostics before spending time on production integration.
   - Do not count this as quality-preserving unless final tokens are accepted by
     the current Quark verifier.

3. BF16 fallback as a quality oracle, not a runtime target.
   - Build a small logit/route comparison harness: BF16 or official FP8
     reference, current Quark output, and candidate kernel/layout output.
   - For layout-only changes, require identical or tolerance-bounded logits,
     same argmax tokens on deterministic probes, and same routed expert IDs.
   - This is especially important before accepting any prepacked INT8 layout or
     persistent-MoE rewrite where text-only canaries may miss small drift.

4. Layer-specific route policy instead of global hot packing.
   - The heatmap found locality, but blind hotpack was mixed: some layer/shape
     pairs improved and others regressed.
   - Next screen should produce a per-layer/per-rows policy table from
     `routecapture5/6`, then dispatch only the layer+shape combinations with
     positive component-level evidence.
   - Add a component summarizer for remap, quant1, GEMM1, activation, quant2,
     GEMM2, and gather so we know where each route-policy delta comes from.

5. Disposable latest `vllm-xpu-kernels` A/B.
   - Recent upstream release notes mention Xe2 MoE grouped-GEMM policy updates.
     Test a throwaway venv/wheel against the accepted launcher, then immediately
     restore the known-good wheel if it regresses.
   - Required gate: same accepted quality suite, same p512/n512 r4/r8 control,
     and no device-lost during first request.
   - If newer kernels help or break, turn the exact Qwen shapes into a compact
     upstream issue.

6. Upstream repro bundle.
   - Package three standalone repros:
     dense `per_token_quant_int8 -> int8_gemm_w8a8`,
     routed MoE grouped GEMM using real expert histograms, and graph-safe tiny
     BF16 all-reduce plus epilogue.
   - Include exact B70 topology, oneAPI/PyTorch/vLLM versions, current timings,
     and the expected target. This gives Intel/vLLM maintainers something
     concrete enough to act on.

7. Single-user static runner.
   - Measure direct model-runner decode with no OpenAI request lifecycle,
     streaming, metrics, or frontdoor path.
   - If it is materially faster than the served endpoint, create a production
     latency lane. If it is also near `100 tok/s`, stop spending time on server
     overhead and return to kernels/speculation.

8. Hybrid dense-replicated / expert-partitioned memory model.
   - Compute whether replicated dense/GDN/attention plus partitioned experts can
     fit on four 32GB B70 cards at 32K context.
   - If it fits, model the collective count versus TP4. The prize is fewer
     decode all-reduces; the risk is expensive all-to-all or graph-capture
     incompatibility.

9. Route-aware expert placement across cards.
   - Use routecapture heatmaps by prompt class to see if hot expert groups are
     stable enough to place together.
   - This is more ambitious than per-layer hotpack because it can change
     cross-card communication. It needs strict expert-ID remap parity tests.

10. Reliability-first host profile.
    - Keep a reversible profile for power state, runtime power, NUMA pinning,
      CCL interface pinning, thermal/fan logging, and lower-overhead Level Zero
      tracing.
    - Success metric is lower r10/r20 variance and fewer device-lost incidents,
      not a headline speed claim by itself.

Ideas to avoid unless new evidence appears:

- Qwen3.5, AWQ, GPTQ-4bit, or any 4-bit production detour.
- Global hot-expert physical remap without layer/shape gating.
- n-gram depth 3+ for speed claims; repeat64 already found accepted loops.
- `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1`; it was quality-safe but slower and
  reduced KV headroom in the endpoint test.

Current best next implementation order:

1. Accepted r8/r10 + peak VRAM + repeat64 refresh.
2. n-gram2 capture-size-3 reliability retest only as a diagnostic.
3. Latest `vllm-xpu-kernels` disposable A/B.
4. Cross-engine or FP8-MTP sidecar feasibility probe.
5. Layer/shape route-policy prototype only after a stronger component signal.

## Component-Level Route Scan Summary

Added `scripts/summarize-qwen36-route-scan-components.py` to pair raw and
hotpack route-replay JSONs by layer, row count, and route start index. It emits
row-level whole-kernel deltas, preallocated-staged deltas, and primitive
component deltas for `remap`, `quant1`, `gemm1`, `activation`, `quant2`,
`gemm2`, and `gather`.

Artifacts:

- `data/qwen36-quark-int8-moe-routecapture5-component-summary-20260611.json`
- `data/qwen36-quark-int8-moe-routecapture6-component-summary-20260611.json`

Repro commands:

```bash
scripts/summarize-qwen36-route-scan-components.py \
  --pair layer8:data/qwen36-quark-int8-moe-routecapture5-layer8-startscan-r15-20260611.json:data/qwen36-quark-int8-moe-routecapture5-layer8-hotpack-startscan-r15-20260611.json \
  --pair layer20:data/qwen36-quark-int8-moe-routecapture5-layer20-startscan-r15-20260611.json:data/qwen36-quark-int8-moe-routecapture5-layer20-hotpack-startscan-r15-20260611.json \
  --output-json data/qwen36-quark-int8-moe-routecapture5-component-summary-20260611.json \
  --print-table

scripts/summarize-qwen36-route-scan-components.py \
  --pair layer9:data/qwen36-quark-int8-moe-routecapture6-layer9-startscan-r15-20260611.json:data/qwen36-quark-int8-moe-routecapture6-layer9-hotpack-startscan-r15-20260611.json \
  --pair layer14:data/qwen36-quark-int8-moe-routecapture6-layer14-startscan-r15-20260611.json:data/qwen36-quark-int8-moe-routecapture6-layer14-hotpack-startscan-r15-20260611.json \
  --pair layer21:data/qwen36-quark-int8-moe-routecapture6-layer21-startscan-r15-20260611.json:data/qwen36-quark-int8-moe-routecapture6-layer21-hotpack-startscan-r15-20260611.json \
  --output-json data/qwen36-quark-int8-moe-routecapture6-component-summary-20260611.json \
  --print-table
```

Compact primitive-stage table, where negative means hotpack was faster:

| Capture | Rows | Windows | Total delta | Prealloc delta | Largest primitive mean delta |
| --- | ---: | ---: | ---: | ---: | --- |
| layer8 | 1 | 8 | +16.390% | +15.384% | `gemm1 +14.729us / +16.37%` |
| layer8 | 16 | 8 | -10.492% | -8.508% | `gemm2 -12.867us / -10.71%` |
| layer20 | 1 | 8 | -5.060% | -3.230% | `remap -3.157us / -3.03%` |
| layer20 | 16 | 8 | +1.517% | +2.588% | `gemm1 +5.187us / +5.67%` |
| layer9 | 1 | 8 | -3.784% | -3.328% | `gemm1 -3.044us / -2.41%` |
| layer9 | 16 | 8 | +1.596% | +5.144% | `gemm1 +5.448us / +6.11%` |
| layer14 | 1 | 8 | +3.628% | +3.848% | `gemm1 +2.694us / +2.80%` |
| layer14 | 16 | 8 | +12.567% | +17.040% | `gemm2 +11.272us / +12.31%` |
| layer21 | 1 | 8 | +8.724% | +5.539% | `remap +6.807us / +7.67%` |
| layer21 | 16 | 8 | -2.314% | -1.038% | `quant1 -4.020us / -3.16%` |

Interpretation:

- The route/hotpack effect is not a single universal bottleneck. The largest
  primitive-stage delta changes by layer and shape: `gemm1`, `gemm2`, `remap`,
  and `quant1` all appear as the top contributor in different rows.
- This keeps global hot-expert physical remap rejected. It improves some
  windows, but the component-level profile shows it can regress GEMM or remap
  stages in other layer/shape combinations.
- A future route policy should be layer-specific and rows-specific, and it
  should be gated on endpoint-level quality and speed. The microbench evidence
  is useful for deciding where to look, but not strong enough by itself to
  justify a production kernel branch.
- The next durable MoE work is still a persistent/grouped-GEMM scheduler or
  exact-shape upstream repro, not another wrapper around the current staged
  path.

## More Aggressive Ideas After Component Summary

Added after the primitive-stage route scan made global hot-expert packing look
too mixed to be the next main bet. These are larger opportunities to keep in
view while the accepted r8/r10 and quality refresh establishes the control
baseline.

1. Exact greedy logits fast path.
   - For `temperature=0`, the final decision does not need a full materialized
     full-vocab distribution on every rank if each rank can return its local
     top candidate and a graph-safe global max reduction chooses the token.
   - This is quality-preserving only for greedy/decode benchmarks and any
     production lane that explicitly uses deterministic decoding; it is not a
     replacement for sampling.
   - Proof gate: exact token-id stream match against the accepted endpoint for
     repeat64, plus a fallback to the normal logits path for non-greedy
     requests.

2. Token critical-path budget before more kernels.
   - Build a synchronized one-token timing trace that splits decode into
     request/scheduler overhead, embedding, attention/GDN, dense W8A8 GEMMs,
     MoE route/dispatch/GEMMs, collectives, logits, and streaming.
   - The goal is a per-token wall-time budget that says what must be cut to
     reach `200 tok/s` instead of optimizing whichever primitive is easiest to
     benchmark.
   - Proof gate: same accepted run with timing disabled must recover baseline
     speed; timing mode is diagnostic only.

3. Single-stream static latency lane beside the normal server.
   - Keep the production vLLM endpoint for aggregate/concurrency, but prototype
     a c1 latency lane with pinned request state, static graph replay,
     preallocated KV, no metrics hot path, and controlled streaming cadence.
   - If the direct runner beats OpenAI streaming materially, route interactive
     single-user requests there while keeping batch serving unchanged.
   - Proof gate: tokenizer/template parity and exact token stream match against
     the accepted OpenAI endpoint.

4. Attention/KV specialization for batch-1 decode.
   - The MoE path is obvious, but the AOT census also shows repeated GDN and
     dense projection regions. For c1 decode, contiguous KV or a special
     single-sequence page path may remove paged-attention indirection that
     mainly exists for aggregate serving.
   - This should be tested with 32K context because an optimization that only
     helps short context is less useful for the production target.
   - Proof gate: long-context needle plus exact deterministic short-context
     hashes before any speed claim.

5. Verifier federation instead of one monolithic TP4 process.
   - Explore whether two TP2 verifier replicas, or a TP2 verifier plus a small
     proposer lane, can improve perceived single-user latency through
     speculation and failover even though raw TP2 decode was slower.
   - This is not a model downgrade: every accepted token still comes from the
     current Qwen3.6 Quark verifier.
   - Proof gate: report accepted-token throughput, rejection rate, and tail
     latency; raw draft/proposer speed alone does not count.

6. Learned prompt-class routing for safe speed lanes.
   - Use the existing prompt-class and routecapture data to classify requests
     into baseline, speculation, static-lane, or future route-policy modes.
   - The classifier can only choose between quality-preserving verifier paths;
     it must never change weights, quantization, or accepted-token semantics.
   - Proof gate: misclassification must fall back to the accepted baseline, and
     the quality suite should run with forced coverage for every lane.

7. Expert-residency and prefetch experiment.
   - Instead of physically remapping experts globally, keep the accepted expert
     IDs but prefetch or stage the likely next-layer active expert blocks based
     on the previous few tokens and layer route histograms.
   - This may reduce memory stalls without changing route decisions or expert
     math, and it avoids the mixed regressions seen with blind hot packing.
   - Proof gate: no expert-ID changes, same routed outputs within tolerance,
     and an endpoint-level speed win over the same-day accepted control.

8. Quality oracle ladder for kernel rewrites.
   - Promote a standard three-level gate for bold kernels: component numerical
     parity against staged INT8, route/logit parity against BF16 or official FP8
     fallback, then text-level repeat64 plus long-context checks.
   - This lets us attempt bigger rewrites without relying on fragile "looks
     okay" text canaries.
   - Proof gate: every future kernel note should state which rung it reached
     and which artifacts prove it.

9. Upstream collaboration package with a concrete target.
   - Turn the current component summary into a public, minimal B70 issue/PR
     bundle: exact shapes, route histograms, primitive timing table, current
     endpoint result, and the desired `>200 tok/s` latency budget.
   - The ask should be specific: W8A8 grouped-GEMM/MoE and graph-safe tiny
     collectives for Qwen3.6 A3B on Xe2/B70, not generic "make XPU faster".
   - Proof gate: sanitized repro runs outside the private endpoint and can be
     rebuilt by upstream maintainers.

10. Treat `>200 tok/s` as requiring a multiplier, not a knob.
    - Current accepted decode is around `100 tok/s`; env vars and wrapper
      boundaries are giving low-single-digit deltas.
    - The plausible multiplier paths are verifier-preserving speculation,
      exact greedy logits, static single-stream execution, and real persistent
      MoE/GEMM kernels. Everything else should be measured, but not allowed to
      consume the main track indefinitely.

## Accepted Control Refresh: r8, Frontdoor repeat64, VRAM

Refreshed the accepted restored service before trying the next risky branch.
Backend health was `200`, and the active server stayed
`qwen36-tp4-accepted-restored-20260611h`:

```text
/home/steve/.venvs/vllm-xpu/bin/vllm serve ... \
  --served-model-name qwen36-35b-a3b-fp8 \
  --tensor-parallel-size 4 \
  --max-model-len 32768 \
  --max-num-seqs 48 \
  --gpu-memory-utilization 0.95 \
  --no-enable-prefix-caching \
  --compilation-config '{"cudagraph_mode":"PIECEWISE"}'
```

Artifacts:

- direct backend speed r8:
  `data/qwen36-quark-int8-tp4-accepted-clean-single-r8-refresh-20260611.json`
- production/frontdoor speed r4:
  `data/qwen36-quark-int8-tp4-accepted-frontdoor-single-r4-refresh-20260611.json`
- production/frontdoor quality repeat64:
  `data/qwen36-quark-int8-tp4-accepted-frontdoor-quality-rerun64-refresh-20260611.json`
- direct backend default chat-template quality failure:
  `data/qwen36-quark-int8-tp4-accepted-quality-rerun64-refresh-20260611.json`
- direct backend explicit no-thinking quality failure:
  `data/qwen36-quark-int8-tp4-accepted-quality-rerun64-nothink-refresh-20260611.json`
- VRAM/headroom snapshot:
  `data/qwen36-quark-int8-tp4-accepted-vram-snapshot-refresh-20260611.json`

Speed summary:

| Path | Repeats | Corrected output tok/s | E2E output tok/s | TTFT ms | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| direct backend `:18080` completions | 8 | `99.422` mean / `99.514` median | `97.957` mean | `75.644` mean | clean timing, `--skip-vram` |
| frontdoor `:8000` completions | 4 | `99.770` mean / `99.827` median | `98.272` mean | `76.527` mean | production-shaped proxy path |

Quality summary:

- Frontdoor repeat64 passed: exact OK/copy/arithmetic/JSON, repeat hash
  stability, long-context needle recall, and baseline comparisons all true.
- Direct backend default chat-template repeat64 failed as expected because it
  exposed Qwen reasoning preamble instead of the no-thinking production
  behavior.
- Direct backend with explicit `chat_template_kwargs={"enable_thinking": false}`
  still failed JSON, repeat64, and long-context:
  - JSON returned `ixo.`
  - one repeat produced corrupted filler:
    `evoluion. # # # # # # # # # whiskey whiskey whiskey whiskey 1 1`
  - long-context needle mutated to
    `B70_Qw36_NEED36_NEEDle_20260609`
- Direct backend no-thinking single canary still returned exactly `OK`, so the
  direct path is not uniformly broken, but it is not strong enough for
  production quality claims.

VRAM/headroom:

- `xpu-smi discovery` reports `32656.0 MiB` physical memory per B70.
- Snapshot after the accepted 32K service loaded:
  - GPU0: `32654.19 MiB` used, about `1.81 MiB` free by physical-minus-used
  - GPU1: `32651.42 MiB` used, about `4.58 MiB` free
  - GPU2: `32651.39 MiB` used, about `4.61 MiB` free
  - GPU3: `32651.30 MiB` used, about `4.70 MiB` free
- Inline VRAM sampling was intentionally not included in the throughput run:
  `xpu-smi dump` takes about `1.5s` per card on this host, and the metric script
  would poll devices sequentially, contaminating TTFT/e2e timing.

Interpretation:

- The same-day accepted control remains a roughly `99-100 tok/s` single-request
  decode baseline, not close to the `>200 tok/s` target.
- The production frontdoor is mandatory for quality-gated claims. It injects
  `enable_thinking=false`, clamps token limits, rewrites the served model name,
  and serializes active generation at `MAX_ACTIVE_GENERATIONS=1`.
- The current 32K/0.95 memory profile leaves effectively no same-card room for
  an MTP/FP8 sidecar. Sidecar speculation needs a reduced-context diagnostic,
  lower memory-utilization verifier, separate process/card layout, off-device
  proposer, or cross-engine verifier bridge.
- The next speed work should not consume time on another backend-only result
  unless it also passes the frontdoor repeat64 gate.

## Post-Control Branch Decisions and Bigger Bets

Added after the accepted refresh above, a Localmaxxing/B70 scan, and a quick
external pass through current XPU/vLLM performance threads. The main point is
to keep the search space honest: the accepted endpoint is now a solid
`99-100 tok/s` control, so the next work needs multiplier potential rather than
another low-single-digit tweak.

External signals checked:

- Localmaxxing public leaderboard:
  `https://localmaxxing.com/api/leaderboard?modelFamily=qwen&hardwareName=Arc%20Pro%20B70&limit=20`
  - current posted result: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`,
    4x Arc Pro B70, vLLM/XPU, Quark W8A8 INT8, `99.428 tok/s`,
    `76.454 ms` TTFT, `196.325 tok/s` total.
  - closest public B70/Qwen3.6-35B-A3B results in that query were
    llama.cpp/SYCL Q4 runs at about `68.8-70.35 tok/s` single-stream.
  - Interpretation: the current INT8 result is worth keeping public, but it is
    still not close to the `>200 tok/s` single-user target.
- vLLM XPU kernels releases:
  `https://github.com/vllm-project/vllm-xpu-kernels/releases`
  - recent release notes mention Xe2 grouped-GEMM heuristic updates for MoE,
    FP8, and small-K cases. This is directly relevant enough to justify a clean
    disposable A/B, but not by mutating the dirty local kernel tree or the
    active production venv.
- Intel Triton/XPU grouped GEMM tuning epic:
  `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`
  - the issue calls out runtime routing distribution, tile configuration, and
    decode-stage long-tail expert skew as grouped-GEMM performance drivers.
  - This matches our route-capture/component-summary conclusion: synthetic
    uniform microbenchmarks are not enough; exact Qwen3.6 route distributions
    should drive kernel tuning.
- vLLM FP8 KV-cache/attention post:
  `https://vllm.ai/blog/2026-04-22-fp8-kvcache`
  - long-context decode can become KV-memory-bound, and FP8 KV can reduce
    decode cost and memory on validated paths. For this project, this is only a
    gated idea because the quality target does not allow silent cache-precision
    regressions.
- vLLM MoE kernel design docs:
  `https://docs.vllm.ai/en/latest/design/moe_kernel_features/`
  - useful for mapping which MoE prepare/finalize and all2all paths preserve
    quantized activation formats versus quantizing after dispatch.
- MoE parallelism playbook, used only as a conceptual reference:
  `https://rocm.blogs.amd.com/software-tools-optimization/vllm-moe-guide/README.html`
  - it reinforces that TP, DP, and EP have different latency/throughput trade
    offs. It is AMD-focused, so any Intel/XPU conclusion needs direct testing.

Branch decisions:

1. Do not spend the next cycle rerunning n-gram2 as the main path.
   - Best prior n-gram2 capture-size-3 result was quality-clean once and reached
     `105.158 tok/s`, but the prompt-class screen was negative or neutral for
     natural chat, code, and math. Structured output showed a gain, but the
     output-length/validity differences made it unsuitable as a broad claim.
   - Keep n-gram2 as a diagnostic or request-class experiment, not the main
     `>200 tok/s` path.

2. Do not rerun the existing Qwen local-argmax patch as-is.
   - Prior local-argmax artifacts were below today's accepted control:
     default pair all-gather around `97.638 tok/s`, packed all-reduce around
     `98.587 tok/s`, versus the current frontdoor control near `99.770 tok/s`.
   - Timing already showed logits plus sampler below 1 ms/token while
     model-forward is about 8.6 ms/token. The exact greedy idea remains alive
     only if it becomes a deeper fused/top1 path that removes real per-token
     work, not the already-tested patch.

3. Do not install or overwrite the dirty local `vllm-xpu-kernels` tree.
   - `/home/steve/src/vllm-xpu-kernels` and `/home/steve/src/vllm` both contain
     local edits and experiments that must not be clobbered.
   - Any upstream release A/B should use a clean clone, separate build dir, and
     disposable venv, then only swap into the active endpoint after a repeatable
     artifact exists.

4. Keep the production/frontdoor repeat64 gate as mandatory.
   - Direct backend no-thinking checks are not enough. The accepted quality
     claim currently belongs to the frontdoor path, because that path injects
     the correct no-thinking chat-template behavior and caught failures that a
     single backend canary missed.

Bolder ideas to try, ranked by chance of a real multiplier:

1. Clean upstream `vllm-xpu-kernels` A/B for Xe2 grouped-GEMM changes.
   - Build latest upstream in a disposable venv, launch the same model and
     exact flags, then compare p512/n512 speed, repeat64 quality, and per-token
     timing against the accepted control.
   - Success gate: same frontdoor quality pass and at least a measurable
     endpoint gain before looking at code-level tuning.

2. Exact route-distribution grouped-GEMM tuning harness.
   - Convert our route-capture traces into the grouped-GEMM shapes used by
     Qwen3.6 A3B decode, including the long-tail expert distribution and rows
     counts that actually appear at batch 1.
   - Benchmark SYCL-TLA, Triton-XPU, and any local W8A8 grouped-GEMM kernels on
     those exact distributions. Optimize for the recurring hot shapes, not a
     uniform synthetic expert split.
   - Success gate: kernel-level speedup on real distributions, followed by an
     endpoint run that proves the speed survives scheduler, graph, and
     collective overhead.

3. Persistent single-user MoE decode kernel.
   - Prototype a decode-only MoE path that keeps per-layer expert metadata,
     activation staging, quant buffers, and grouped-GEMM launch state resident
     across tokens.
   - The target is to remove repeated route/remap/prealloc overhead and reduce
     launch count. This is a bigger rewrite than hot-expert packing, but it
     attacks the part of the token budget that still dominates.
   - Success gate: component parity first, then exact greedy token parity and
     repeat64 text quality.

4. Expert-parallel and DP+EP shape experiment on 4x B70.
   - Test whether `--enable-expert-parallel`, TP+EP, or a TP/DP hybrid changes
     the MoE memory-bandwidth and collective balance for this A3B model.
   - This is risky for latency because extra collectives can erase gains, but
     it is one of the few server-level switches with true architectural upside.
   - Success gate: clean rollback path, p512/n512 speed, long-context quality,
     and a separate aggregate-throughput measurement so latency and throughput
     are not confused.

5. Static c1 latency runner outside the normal vLLM server loop.
   - Build a controlled single-request lane with pinned tokenizer/template
     state, preallocated KV, fixed graph capture, disabled metrics hot path,
     and deterministic streaming cadence.
   - This is not a production replacement at first. It answers whether vLLM's
     general serving machinery is costing enough latency to justify a separate
     interactive endpoint.
   - Success gate: exact token stream match to the accepted frontdoor and a
     clear split of runner overhead versus model-forward time.

6. Verifier-preserving MTP/speculation with off-card or reduced-context draft.
   - Since 32K/0.95 leaves almost no same-card VRAM, try a draft/proposer that
     does not steal verifier memory: CPU/iGPU, lower-memory same model sidecar,
     separate process, reduced-context diagnostic, or remote draft over LAN.
   - Every token still has to be accepted by the current Qwen3.6 Quark verifier.
   - Success gate: accepted-token throughput, rejection histogram, tail latency,
     and repeat64 quality. Draft speed alone does not count.

7. KV-cache precision and memory budget ladder.
   - Try `--kv-cache-dtype fp8` only as a gated experiment, because it may
     reclaim memory and reduce attention bandwidth, but it is not automatically
     quality-neutral.
   - If quality passes, the regained VRAM might make MTP or larger graph capture
     shapes feasible. If quality fails, keep `kv-cache-dtype auto`.
   - Success gate: long-context needle, repeat64, and BF16/accepted comparisons
     before any speed result is considered valid.

8. Cross-engine 8-bit verifier candidate.
   - Explore whether llama.cpp/SYCL or another Intel-native path can run a true
     8-bit Qwen3.6 35B verifier faster than vLLM while preserving quality.
   - This must not regress to 4-bit. Possible formats to evaluate are Q8_0,
     W8A8, or another native Intel-friendly 8-bit representation that can be
     compared against BF16 and the accepted Quark endpoint.
   - Success gate: same model family, 8-bit weights, quality parity, and a
     reproducible p512/n512 benchmark.

9. Platform and collective critical path audit.
   - Pin GT frequency, verify PCIe/root-complex topology, confirm P2P path and
     oneCCL transport, then microbench all-reduce/all-gather sizes that appear
     in the actual decode trace.
   - The goal is not generic system tuning. It is to find whether one specific
     collective or topology choice is eating the missing latency.
   - Success gate: an exact before/after token budget, not just a microbench
     improvement.

10. Upstream repro package for Intel/vLLM maintainers.
    - Package the accepted control, route histograms, grouped-GEMM shapes,
      component timing, Localmaxxing link, and `>200 tok/s` target into a small
      public issue/PR bundle.
    - Ask for concrete help on W8A8 MoE grouped GEMM, graph-safe collectives,
      and Xe2 decode latency, not general advice.
    - Success gate: maintainers can reproduce at least one kernel benchmark
      without access to this whole workstation.

Immediate next move:

1. Record these decisions in GitHub so we do not loop on rejected branches.
2. Start the clean upstream `vllm-xpu-kernels` A/B in a separate clone/venv.
3. If that is neutral, shift into the route-distribution grouped-GEMM harness,
   because that is the clearest path from local measurements plus external
   XPU guidance to a real speedup without quality loss.

## Clean Upstream Kernel A/B Audit And Expanded Backlog

Follow-up after starting the clean upstream path above:

- Active service/venv state:
  - backend and frontdoor were still healthy before the audit.
  - active `vllm-xpu-kernels` imports from editable local source:
    `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels`.
  - active dist metadata reports `vllm-xpu-kernels
    0.1.9.dev27+g28e1f5e`, but that number is incomplete because the source
    tree is dirty.
  - local dirty source contains the W8A8/Quark work that matters for the
    current result: INT8 grouped GEMM interface, INT8 quantization entry
    points, oneDNN W8A8 additions, and the expanded fused-MoE Python path.
- Clean upstream workspace:
  - clone: `/mnt/fast-ai/vllm-xpu-kernels-ab-20260611`
  - v0.1.9 worktree: `/mnt/fast-ai/vllm-xpu-kernels-ab-20260611-work/v0.1.9`
  - upstream main at audit time: `22dd63a Consolidate fp8 and mxfp8 gemm path
    (#398)`.
  - `v0.1.9` is the newest tag still aligned with active `torch
    2.11.0+xpu`; `v0.1.9.1` and main require `torch 2.12.0+xpu`.
- Decision:
  - Pure upstream `v0.1.9` is not a valid A/B for the current endpoint. It
    loses the dirty local W8A8/Quark code path that produced the accepted
    `99-100 tok/s` result.
  - Do not install a clean upstream wheel over the active venv unless the local
    W8A8 patch set is rebased or recreated in the disposable workspace first.
- Build attempt note:
  - A broad `v0.1.9` wheel build was intentionally stopped. The older build
    path generated hundreds of attention template sources and `1375` ninja
    targets, while the relevant question is W8A8 MoE decode, not rebuilding the
    whole attention matrix.
  - No active service or active venv was changed.

Re-ranked immediate work:

1. Build a route-exact W8A8 grouped-GEMM harness against the current local
   kernels.
   - Use `routecapture5/6` and the component summaries to construct the real
     decode-stage rows-per-expert distributions for Qwen3.6 A3B.
   - Call the current local op directly, especially
     `torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_interface`.
   - This gives a tight loop for kernel policy work without restarting the
     whole model server.

2. Rebase only the relevant upstream grouped-GEMM changes onto the local W8A8
   patch set.
   - Cherry-pick or manually port Xe2 grouped-GEMM heuristic changes only after
     the route-exact harness exists.
   - The gate is kernel latency on real route distributions first, then
     endpoint p512/n512 plus frontdoor repeat64 quality.

3. Create a minimal upstreamable repro bundle.
   - Include route histogram, representative grouped-GEMM shapes, current
     latency, target latency, GPU/driver/version data, and the Localmaxxing
     public result.
   - This should be small enough for Intel/vLLM maintainers to run without the
     full model.

Bigger, bolder ideas to keep on the board:

1. Whole-MoE-layer persistent decode kernel.
   - Fuse or pipeline router/top-k, dispatch, gate/up, SiLU/mul, down, and
     weighted combine for single-token decode.
   - The bold version is one resident per-layer kernel policy instead of
     separate Python/C++ launches and scratch setup for each substep.

2. Route-conditioned expert layout and prefetch.
   - Use captured route heatmaps to reorder expert storage and prefetch likely
     next-token experts.
   - This must remain quality-exact: prediction can only move data earlier, not
     skip verifier work.

3. Topology-aware collective replacement.
   - Microbench the exact all-reduce/all-gather sizes from decode, then test a
     custom Level Zero/oneCCL path or fused residual/RMS/collective boundary if
     one collective is on the critical path.
   - This could matter because four B70s are connected over PCIe, and model
     forward still dominates token time.

4. Expert-parallel variant with replicated dense layers.
   - For a reduced-context diagnostic, trade memory for fewer per-token TP
     collectives by replicating shared dense weights and sharding experts by
     GPU.
   - If it wins latency at 4K/8K, then decide whether production 32K can be
     made to fit with KV or memory-budget changes.

5. Static interactive runner.
   - Build a special c1 path with fixed template state, preallocated KV, fixed
     graph buckets, pinned sampling, and minimal metrics/HTTP overhead.
   - It does not replace vLLM production initially; it answers whether the
     general scheduler path is hiding a large single-user latency tax.

6. Same-quality verifier speculation with external draft.
   - Try a LAN/off-card/iGPU/CPU draft path where every token is verified by
     the current Qwen3.6 INT8 endpoint.
   - Measure accepted tokens per verifier step, rejection histogram, and tail
     latency. Draft-only throughput is not useful.

7. OpenVINO GenAI as a first-class 8-bit verifier branch.
   - External B70 reports and OpenVINO GenAI results suggest it should not stay
     as a vague future idea.
   - Only test formats that preserve the quality goal: BF16 control or real
     8-bit/W8A8. No 4-bit fallback.

8. True 8-bit cross-engine bake-off.
   - Compare vLLM/XPU against llama.cpp/SYCL or Vulkan, OpenVINO, and any
     Intel-native runtime that can run the same model family in real 8-bit.
   - Keep quality gates identical: repeat64, long-context needle, JSON/copy,
     and BF16/accepted-output comparisons.

9. Exact partial-logit/top1 path.
   - Prior local-argmax work was too small, but a deeper fused `lm_head +
     partial top-k + rank reduce` path may still remove avoidable full-logits
     movement.
   - Treat this as a secondary gain after MoE, because current timing says the
     model forward is the main cost.

10. Two-lane production design.
    - Keep one lane optimized for single-user latency and another for aggregate
      throughput/concurrency.
    - This does not lower quality, and it avoids forcing one set of scheduler,
      context, and graph-capture choices to satisfy conflicting workloads.

## Route-Exact W8A8 Grouped-GEMM Harness

Added a narrow kernel harness:

```bash
scripts/bench-qwen36-route-exact-w8a8-grouped-gemm.py
```

Purpose:

- Replay captured Qwen3.6 A3B MoE route distributions directly against the
  local dirty W8A8 op:
  `torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_interface`.
- Separate grouped-GEMM kernel-policy questions from full vLLM server restarts,
  HTTP timing, remap, quantization, activation, and gather overhead.
- Provide both:
  - `exact` mode: full `256` expert rows-per-expert vector, matching the
    current model shape.
  - `compact_active` mode: remaps active experts to dense IDs as a diagnostic
    lower-memory / hot-layout proxy. This is not quality-preserving by itself;
    a real implementation would need matching weight layout and exact routing
    semantics.

Artifacts:

- Dry route/window parse:
  `data/qwen36-quark-int8-w8a8-grouped-gemm-routeexact-dryrun-20260611.json`
- One-case smoke while the live endpoint remained up:
  `data/qwen36-quark-int8-w8a8-grouped-gemm-compact-smoke-20260611.json`
- Eight route-window per-layer scan:
  `data/qwen36-quark-int8-w8a8-grouped-gemm-routeexact-scan-20260611.json`
- Eight route-window size-3 shape scan:
  `data/qwen36-quark-int8-w8a8-grouped-gemm-routeexact-window3-scan-20260611.json`

Validation:

- Script compiled with:

```bash
python3 -m py_compile scripts/bench-qwen36-route-exact-w8a8-grouped-gemm.py
```

- Backend and frontdoor health were still `200` after the XPU scans.
- The live 32K endpoint was not stopped for this harness pass.

Per-layer route-window scan command:

```bash
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/bench-qwen36-route-exact-w8a8-grouped-gemm.py \
  --route-jsonl data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl \
  --route-layer-regex 'layers\.(9|14|21)\.' \
  --route-start-indices 0:96:12 \
  --max-cases 8 \
  --gemm-stage both \
  --compact-active-experts \
  --warmup 5 \
  --iterations 20 \
  --device xpu:3 \
  --output-json data/qwen36-quark-int8-w8a8-grouped-gemm-routeexact-scan-20260611.json
```

Per-layer scan summary, 8 captured decode route cases:

- `exact`, full 256-expert shape:
  - GEMM1: `103.851 us` mean of case means, median `102.553 us`
  - GEMM2: `101.464 us` mean of case means, median `94.312 us`
- `compact_active`, 8 active experts:
  - GEMM1: `103.482 us` mean of case means, median `98.702 us`
  - GEMM2: `106.572 us` mean of case means, median `107.158 us`

Interpretation:

- Simple active-expert compaction did not produce a consistent grouped-GEMM
  win in this kernel. For the exact current per-layer decode shape, the local
  Xe2 W8A8 grouped-GEMM path appears to have an approximately `90-110 us`
  tiny-shape floor whether the expert dimension is full `256` or compacted to
  the active 8 experts.
- This pushes the next optimization away from "just remove inactive experts"
  and toward launch/staging reduction:
  - fused or persistent per-layer MoE decode,
  - quantization plus GEMM fusion,
  - activation plus GEMM2 quant fusion that is actually endpoint-positive,
  - graph-safe scratch reuse and launch reduction,
  - or a kernel policy change that specifically attacks the tiny-shape floor.

Window-size-3 shape scan command:

```bash
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/bench-qwen36-route-exact-w8a8-grouped-gemm.py \
  --route-jsonl data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl \
  --route-layer-regex 'layers\.(9|14|21)\.' \
  --route-start-indices 0:96:12 \
  --route-window-size 3 \
  --max-cases 8 \
  --gemm-stage both \
  --compact-active-experts \
  --warmup 5 \
  --iterations 20 \
  --device xpu:3 \
  --output-json data/qwen36-quark-int8-w8a8-grouped-gemm-routeexact-window3-scan-20260611.json
```

Window-size-3 summary:

- `exact`, full 256-expert shape, 24 total rows and 17-21 active experts:
  - GEMM1: `95.520 us` mean of case means, median `93.591 us`
  - GEMM2: `92.053 us` mean of case means, median `91.328 us`
- `compact_active` varied by active expert count and was generally in the same
  range, about `89-95 us` for the case means.

Important caveat:

- The window-size-3 scan is a shape diagnostic, not a valid model execution
  plan. The captured layers are sequential transformer layers, so their real
  work cannot simply be collapsed into one GEMM without preserving layer
  dependencies and layer-specific weights.
- It still shows that larger grouped-GEMM row counts can amortize the same
  launch/policy floor. That makes the persistent/specialized MoE decode kernel
  idea more interesting than physical expert compaction alone.

## W8A8 Tiny-Shape Kernel Floor And New Backlog

Added a second, more direct floor diagnostic:

```bash
scripts/bench-qwen36-w8a8-kernel-floor.py
```

Purpose:

- Compare the route-exact grouped W8A8 kernel against deliberately simpler
  dense and compact variants.
- Time the surrounding XPU quantization kernels in isolation:
  `per_token_quant_int8_xpu` and `silu_and_mul_quant_int8_xpu`.
- Decide whether the next exact-preserving work should chase expert
  compaction, dense replacement, or launch/fusion/persistence.

Artifacts:

- `data/qwen36-quark-int8-w8a8-kernel-floor-smoke-20260611.json`
- `data/qwen36-quark-int8-w8a8-kernel-floor-routeexact-20260611.json`

Validation:

- Script compiled with:

```bash
python3 -m py_compile scripts/bench-qwen36-w8a8-kernel-floor.py
```

- JSON artifacts were parsed after the run, with finite outputs for every
  benchmark case and quant kernel result.
- Backend and frontdoor health stayed `200` after the XPU scans.

Full route-exact command:

```bash
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/bench-qwen36-w8a8-kernel-floor.py \
  --route-jsonl data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl \
  --route-layer-regex 'layers\.(9|14|21)\.' \
  --route-start-indices 0:96:12 \
  --max-cases 8 \
  --gemm-stage both \
  --include-compact-grouped \
  --include-quant \
  --warmup 5 \
  --iterations 20 \
  --device xpu:3 \
  --output-json data/qwen36-quark-int8-w8a8-kernel-floor-routeexact-20260611.json
```

Results, mean of case means:

| Mode | GEMM1 us | GEMM2 us | Meaning |
| --- | ---: | ---: | --- |
| grouped exact 256 experts | 107.966 | 101.591 | current model-equivalent grouped-GEMM shape |
| grouped compact active experts | 100.967 | 101.609 | diagnostic only unless weights/routes are repacked exactly |
| dense single | 124.061 | 119.116 | not model-equivalent and not faster enough |
| dense active loop | 317.588 | 309.798 | model-shape style, but many launches; clearly worse |

Quant kernel timings:

| Kernel shape | Mean us |
| --- | ---: |
| `quant_hidden_rows8` | 112.492 |
| `quant_hidden_rows24` | 157.407 |
| `quant_inter_rows8` | 88.728 |
| `quant_inter_rows24` | 89.180 |
| `silu_quant_rows8` | 88.569 |
| `silu_quant_rows24` | 90.893 |

Interpretation:

- The current grouped-GEMM op is not losing because it carries 256 expert slots.
  Compacting active experts is mostly neutral at these shapes.
- A naive dense replacement is not the answer. A loop over active experts is
  much worse because it multiplies launches.
- The quantization kernels are as expensive as the tiny GEMMs. For decode, the
  approximate local stage costs look like:
  - hidden quant plus GEMM1: about `112 + 108 us`
  - SiLU/intermediate quant plus GEMM2: about `89 + 102 us`
- The highest-confidence exact-preserving kernel target is now fusion or
  persistence, not another environment knob:
  - fuse quant/staging with W8A8 GEMM1,
  - fuse activation/intermediate quant with W8A8 GEMM2,
  - reuse graph-safe scratch across MoE substeps,
  - or build a persistent per-layer MoE decode kernel that keeps route,
    quant, GEMM1, activation, quant, GEMM2, gather/finalize inside fewer
    launches.

External signals checked during this pass:

- `https://github.com/vllm-project/vllm/issues/35638`
  - Active B580/vLLM-XPU users are still asking about best startup arguments,
    stability, OOM behavior, and multi-GPU strategy for 30B+ models.
- `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`
  - Grouped-GEMM performance on XPU is a known tuning topic. The useful local
    action is not to assume generic Triton defaults are optimal for MoE decode;
    keep our shape-exact repros minimal and upstreamable.
- `https://github.com/vllm-project/vllm-xpu-kernels/releases`
  - Recent `vllm-xpu-kernels` releases explicitly mention Xe2 grouped-GEMM
    heuristic and MoE policy tuning, including small-shape behavior. Our
    `90-110 us` floor is exactly the kind of repro that should be useful.
- `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`
  - Intel/vLLM publicly call out Arc Pro multi-GPU scaling, PCIe P2P,
    well-optimized MoE models, mixed precision, speculative decoding, and
    prefill/decode disaggregation. This supports both the kernel-fusion track
    and a separate scheduler/parallelism track.
- `https://docs.vllm.ai/en/stable/models/hardware_supported_models/xpu/`
  - vLLM validates Intel Arc Pro B-series and marks Qwen MoE-class models as
    supported/optimized in the XPU model table. This means we should keep
    producing exact repros against upstream XPU components rather than treating
    our stack as unsupported.
- `https://embeddedllm.com/blog/benchmarking-llm-inference-intel-arc-pro-b60`
  - Public 4x Arc Pro B60 testing reports strong aggregate behavior at high
    concurrency and explicitly compares standard vLLM versus an Intel-optimized
    build by latency tradeoff. That reinforces the need to track single-request
    speed and aggregate throughput as separate product modes.
- `https://localmaxxing.com/api/leaderboard?hfId=Qwen%2FQwen3.6-35B&hwClass=DISCRETE_GPU&limit=20`
  - The fastest public Qwen3.6 35B rows above `200 tok/s` are using either
    speculation/MTP, 4-bit/NVFP4-class formats, CUDA-specific fast paths, or
    non-Intel hardware. The actionable signal is the architecture pattern
    rather than the quantization choice: speculation and persistent fused paths
    are the routes to cross `200 tok/s`.

Things to try next, evidence-backed:

1. Add a shape-exact fused quant+GEMM microbench.
   - First prototype outside vLLM:
     `BF16 hidden -> per-token scale -> int8 tile -> W8A8 GEMM1`.
   - Compare against current `per_token_quant_int8_xpu + grouped_gemm`.
   - Require tolerance parity against the current staged path before endpoint
     wiring.

2. Add a fused activation+quant+GEMM2 microbench.
   - Target:
     `up/gate BF16 -> SiLU*gate -> per-token quant -> W8A8 GEMM2`.
   - This attacks the measured `~89 us + ~102 us` second-stage floor.
   - It is quality-exact if scales and rounding match the existing kernels.

3. Build a persistent MoE decode skeleton for one layer.
   - Keep route rows, scratch, quant buffers, and output buffers resident.
   - Start with a single layer and synthetic fixed route, then feed captured
     route JSONL cases.
   - Success metric: one-layer parity plus lower wall time than the sum of
     quant/GEMM/activation/finalize kernels.

4. Audit Xe2 grouped-GEMM policy selection for decode.
   - Current source computes average rows per expert with integer division;
     for `8 / 256`, the policy key effectively sees `0`.
   - Test a local policy override for the decode shapes only. This is a small
     patch with a clear microbench pass/fail gate.

5. Make an upstreamable repro bundle.
   - Include one JSON route case, exact tensor shapes, a no-model synthetic
     harness, timings, and expected output tolerance.
   - File it against `vllm-xpu-kernels` only after proving the same result
     outside the full endpoint.

Bigger, bolder ideas to track:

1. XPU MTP sidecar with Quark verifier.
   - Use an FP8/MTP or Qwen3.6-family proposer only to suggest tokens; the
     current Quark INT8 endpoint remains the verifier.
   - This is the most plausible `2x` path without changing final-model
     quality, but only if mixed scheduling is fixed and repeat64 passes.

2. Expert-parallel decode layout for B70.
   - Stop assuming pure TP4 is the right single-token layout.
   - Replicate dense/attention where memory allows, shard experts by GPU, and
     pay fewer all-reduces in decode. Test at 4K/8K first to avoid 32K memory
     constraints obscuring the result.

3. Intel-optimized vLLM/LLM-Scaler branch bakeoff.
   - Keep the same model and 8-bit quality target, but compare the Intel tuned
     serving branch if it is accessible for B70/B60-style systems.
   - Treat this as a production architecture branch, not a replacement for
     local kernel repros.

4. Static c1 runner with server overhead removed.
   - Build a direct runner using the same local kernels and graph captures,
     fixed prompt shape, preallocated KV, no HTTP streaming, and minimal
     scheduler work.
   - If it is much faster than OpenAI streaming, we know to invest in a
     low-latency frontdoor/scheduler path. If it is not, kernel work remains
     the only real lever.

5. Cross-engine 8-bit diagnostic.
   - Build or find a true 8-bit Qwen3.6 35B artifact for llama.cpp SYCL/Vulkan
     or OpenVINO GenAI and run the same quality suite.
   - No 4-bit result can replace the target, but an 8-bit cross-engine result
     would tell us whether vLLM/XPU overhead is unusually high.

6. Quantization-aware layout converter.
   - Convert Quark W8A8 weights once into a B70-native tile layout at model
     load or as an on-disk cache.
   - This keeps math and quality fixed while testing whether the stored weight
     layout is mismatched to Xe2 XMX/DPAS.

7. Decode disaggregation on one host.
   - Run a prefill-optimized lane and a decode-optimized lane with the same
     model weights, using shared prompt cache only if correctness is exact.
   - This is mainly production-facing, but it can keep c1 decode tuned while
     aggregate traffic uses different scheduler choices.

8. Speculative draft on a spare device.
   - Use CPU/iGPU/one B70 partition as a draft lane and TP4 as verifier, or use
     a second low-latency model slot if memory allows.
   - The draft can be lower precision only if every accepted token is verified
     by the current INT8 model and quality tests remain identical.

Priority after this section:

1. Microbench fused quant+GEMM1 and activation+quant+GEMM2.
2. Test a decode-shape Xe2 grouped-GEMM policy override.
3. In parallel, investigate verifier-preserving MTP/speculation because that
   is the only credible route to `>200 tok/s` without changing the accepted
   model distribution.

## Expanded Big-Bet Backlog

Added after checking public B70/XPU signals and the Localmaxxing exact-model
entry.

Current outside reference points:

- Localmaxxing now has the exact Quark W8A8 INT8 model listed at `99.43 tok/s`
  on `4x Intel Arc Pro B70`, with quality-gated notes and 32K context. This is
  the only exact-model public row found in the query.
- Public B70 Qwen3.6 35B rows are mostly llama.cpp `Q4_K_M`/`UD-Q4_K_M`, with
  `~55-70 tok/s` single-stream generation depending on setup. These are useful
  architecture references, but not acceptable substitutes for this task because
  they use 4-bit quantization.
- `intel/intel-xpu-backend-for-triton#6389` directly confirms that MoE decode
  grouped-GEMM performance depends heavily on skewed routing and tile policy.
- Intel/vLLM B-series material emphasizes persistent kernels, multi-GPU
  scaling, P2P/topology, and disaggregated prefill/decode as high-leverage
  areas. Treat those as design hints, not proof for our exact model.

Quality-preserving speed bets:

1. Route-hot expert replication.
   - Decode routing is skewed. Replicate the hottest experts across more GPUs
     and shard only the cold tail.
   - This keeps weights and math unchanged but may reduce cross-GPU traffic and
     per-token expert dispatch latency.
   - Needs route histogram capture by layer over real prompts, then a simulator
     before touching the runtime.

2. Expert-parallel layout instead of pure TP4.
   - TP4 makes every token pay communication costs even when the active expert
     set is tiny.
   - A hybrid layout could replicate attention/dense blocks where memory allows
     and expert-shard the MoE blocks.
   - First test should be short context, because 32K KV memory can hide whether
     the layout itself is better.

3. B70-native W8A8 weight retile cache.
   - Convert Quark W8A8 weights once into the exact Xe2 DPAS-friendly layout
     used by the grouped GEMM.
   - Store the converted layout on disk or in a load-time cache.
   - This does not alter quant values; it only changes memory order. Gate with
     bit/tolerance parity against the current staged path.

4. Fused dequant/scale epilogue.
   - If grouped W8A8 output currently pays extra scale/dequant work outside the
     hottest DPAS loop, move scale application into the GEMM epilogue.
   - This should preserve numerics if rounding order is matched or bounded by
     the current kernel tolerance.

5. One-layer persistent MoE decode kernel.
   - Combine route read, activation quant, GEMM1, activation, second quant,
     GEMM2, and scatter/finalize for one layer.
   - Start synthetic and layer-local. Only after parity should it touch vLLM.
   - This is the boldest kernel path because it attacks both launch overhead
     and scratch traffic.

6. Decode-step command-list batching.
   - The measured tiny kernels are often `~90-110 us`, so launch/queue overhead
     may be a first-order cost.
   - Try Level Zero command list reuse or graph capture around a larger decode
     slice, even before full kernel fusion exists.
   - Success criterion is lower event-timeline wall time without numerical
     differences.

7. Verifier-only speculative decoding.
   - Use the current Quark W8A8 INT8 model as the verifier. A draft/MTP model
     can propose tokens, but no token is accepted unless the current model
     verifies it.
   - This is quality-preserving in the distributional sense when implemented
     correctly, and it is the most realistic path to a `2x` jump.
   - Must pass repeat64, JSON/canary, long-context needle, and BF16/INT8
     comparison before it can be accepted.

8. XPU MTP sidecar.
   - Search for or train/use a Qwen3.6-family MTP proposer small enough to run
     on spare device capacity.
   - Keep the accepted model untouched. The MTP path is only a proposal lane.
   - If no stable XPU implementation exists, document it as blocked rather than
     spending cycles on CUDA-only assumptions.

9. Direct c1 runner without HTTP/scheduler overhead.
   - Build a fixed-shape runner with preallocated KV, no OpenAI server, no
     streaming JSON, and minimal scheduler work.
   - If direct c1 is much faster, optimize the serving path. If it is not,
     focus exclusively on kernels and inter-GPU layout.

10. Cross-engine true 8-bit control.
    - Try llama.cpp SYCL `Q8_0` or OpenVINO GenAI INT8 only as diagnostics.
    - Do not accept 4-bit wins for this target.
    - If a true 8-bit engine is much faster with similar quality, use it to
      identify what vLLM/XPU is leaving on the table.

11. Topology and host-stack A/B.
    - Re-test on the closest Intel-published B-series BOM available: kernel,
      compute-runtime, GuC firmware, oneAPI, oneCCL, and vLLM image/branch.
    - Prior public B70 TP reports mention driver/firmware/topology sensitivity.
      This may not produce a kernel patch, but it can avoid fighting a bad host
      stack.

12. Route-aware AOT specialization.
    - Generate a small family of shape-specialized kernels for common
      per-layer route histograms instead of one generic grouped-GEMM path.
    - Dispatch by captured shape bucket. This preserves exact output if it only
      changes tiling and order within accepted tolerance.
    - Useful only after route histograms prove the buckets are stable.

Production/aggregate bets, kept separate from the single-request goal:

1. One model replica per B70 for aggregate load.
   - If true 8-bit full-model memory plus KV fits at reduced context, compare
     four independent replicas against TP4.
   - This may improve aggregate throughput and tail latency, but it is not a
     direct 32K single-request answer unless full memory fits.

2. Prefill/decode split.
   - Use a prefill-optimized lane for long prompts and a decode-optimized lane
     for streaming.
   - This is promising for production because prefill and decode want different
     batch and scheduling settings.

3. Adaptive routing by request class.
   - Keep the quality model fixed, but route short chat, long-context, code,
     and structured requests to different server configs if benchmarks show
     stable differences.
   - This is operationally useful but must not hide regressions in the headline
     c1 decode metric.

Near-term order:

1. Finish the grouped-GEMM policy override screen already in progress.
2. Add route histogram summaries by layer and prompt class.
3. Prototype fused `quant + GEMM1`.
4. Prototype fused `activation + quant + GEMM2`.
5. Start a verifier-only speculation feasibility spike only after the current
   kernel floor screens are recorded.

## W8A8 Grouped-GEMM Decode Policy Screen

Patch under test:

- Local kernel tree:
  `/home/steve/src/vllm-xpu-kernels`
- File:
  `csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2_interface.hpp`
- Added env override:
  `VLLM_XPU_W8A8_GROUPED_GEMM_POLICY=m16|m32|base`
- Default/unset behavior remains the existing heuristic:
  `A_avg_M <= 8 -> w8a16_policy_m_16`,
  `A_avg_M <= 32 -> w8a16_policy_m_32`,
  otherwise `w8a8_policy`.

Build notes:

- Full editable install with oneAPI 2026.0 failed late while compiling
  `paged_decode_xe2.cpp`; `icpx` was killed after `_xpu_C` and
  `libgrouped_gemm_xe_2.so` had linked. The 2026 artifacts pulled in
  `libsycl.so.9`, which is incompatible with the current 2025-linked package
  import path and caused an import failure/segfault. Those partial temp
  artifacts were quarantined/restored from the known-good package copies.
- Rebuilt only the grouped-GEMM target in the existing 2025.3-compatible build
  dir:

```bash
PATH=/opt/intel/oneapi/compiler/2025.3/bin:$PATH \
  ninja -C /home/steve/src/vllm-xpu-kernels/build/xpu-c-only-2025 \
  -j2 grouped_gemm_xe_2
```

- The rebuilt `libgrouped_gemm_xe_2.so` links against `libsycl.so.8` and was
  copied into `build/temp/` for fresh Python microbench processes.
- Import sanity passed after the swap:
  `torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_interface == True`.
- Backend/frontdoor health after the policy screens:
  `http://127.0.0.1:18080/health -> 200`,
  `http://127.0.0.1:8000/health -> 200`.

Artifacts:

- `data/qwen36-quark-int8-w8a8-policy-m16-smoke-20260611.json`
- `data/qwen36-quark-int8-w8a8-policy-m32-smoke-20260611.json`
- `data/qwen36-quark-int8-w8a8-policy-base-smoke-20260611.json`
- `data/qwen36-quark-int8-w8a8-policy-m16-routeexact-20260611.json`
- `data/qwen36-quark-int8-w8a8-policy-m32-routeexact-20260611.json`
- `data/qwen36-quark-int8-w8a8-policy-base-routeexact-20260611.json`

Full route-exact command pattern:

```bash
VLLM_XPU_W8A8_GROUPED_GEMM_POLICY=<m16|m32|base> \
  /home/steve/.venvs/vllm-xpu/bin/python \
  scripts/bench-qwen36-w8a8-kernel-floor.py \
  --route-jsonl data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl \
  --route-layer-regex 'layers\.(9|14|21)\.' \
  --route-start-indices 0:96:12 \
  --max-cases 8 \
  --gemm-stage both \
  --warmup 5 \
  --iterations 20 \
  --device xpu:3 \
  --output-json data/qwen36-quark-int8-w8a8-policy-<policy>-routeexact-20260611.json
```

Route-exact grouped W8A8 results, mean of case means:

| Policy | GEMM1 us | GEMM2 us | Read |
| --- | ---: | ---: | --- |
| `m16` | 112.936 | 104.377 | current default for decode, because `8 / 256` maps to tiny-M |
| `m32` | 105.793 | 102.627 | best GEMM2, materially better GEMM1 |
| `base` | 104.622 | 103.535 | best GEMM1, neutral/slightly worse than `m32` on GEMM2 |

Interpretation:

- The default tiny-M `m16` policy is probably not the best choice for these
  route-exact W8A8 decode shapes.
- `m32` is the safest next endpoint candidate because it improves both stages
  in this screen: about `6.3%` faster on GEMM1 and `1.7%` faster on GEMM2
  versus `m16`.
- `base` is also promising for GEMM1 but gives back some GEMM2 time. It may be
  useful if endpoint profiles show GEMM1 dominates.
- This is not enough to accept the change for production. Next gate is an
  endpoint restart with `VLLM_XPU_W8A8_GROUPED_GEMM_POLICY=m32`, then:
  speed repeat, quality repeat, and stability repeat. If endpoint-level speed
  does not move, this remains a microbench-only finding.

## Bigger Bolder Ideas Addendum

Added after the W8A8 policy screen and another public B70/XPU scan on
2026-06-11.

Target remains unchanged:

- Qwen3.6 35B A3B, not Qwen3.5.
- 8-bit/high-fidelity path only. No 4-bit promotion.
- Current Quark W8A8 INT8 model remains the accepted verifier unless a
  candidate proves equal or better quality against BF16 and the canary suite.
- Single-request decode speed is the primary goal; aggregate throughput is a
  secondary production goal.

Reference signals checked:

- vLLM Intel Arc Pro B-series notes emphasize MoE persistent kernels, dynamic
  group balancing, multi-GPU/P2P, speculative decoding, and prefill/decode
  disaggregation:
  `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`
- Intel XPU Triton issue `#6389` says grouped-GEMM performance depends strongly
  on real route distributions, especially skewed decode routes:
  `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`
- Public B70 Qwen3.6 rows remain mostly 4-bit llama.cpp diagnostics, not
  substitutes. They are still useful for engine and topology clues:
  `https://github.com/PMZFX/intel-arc-pro-b70-benchmarks`
- Intel/HF notes confirm optimized `FusedMoE` paths exist in both vLLM and
  Transformers for Xe GPUs, so a cross-stack MoE control is worth testing:
  `https://huggingface.co/blog/MatrixYao/intel-gpu`

Concrete next gates already worth running:

1. Endpoint-test the `m32` grouped-GEMM policy.
   - Launch with `VLLM_XPU_W8A8_GROUPED_GEMM_POLICY=m32`.
   - Run p512/n512 single-request speed, quality canary, repeat stability, and
     a short route capture.
   - Accept only if endpoint speed moves and quality/stability are unchanged.

2. Build route histograms by prompt class.
   - Capture per-layer expert distributions for natural chat, code, structured,
     math, repetitive, and long-context prompts.
   - Record hot experts, long-tail depth, top-k concentration, and layer-local
     route stability.
   - Feed these shapes into the grouped-GEMM floor harness instead of relying
     on synthetic or single-route cases.

3. Prototype the two local fusions before touching the full runtime.
   - `activation quant + GEMM1`
   - `activation + output quant + GEMM2`
   - Gate with layer-local numeric parity and route-exact microbench speed
     before considering endpoint integration.

4. Build a direct c1 runner.
   - Fixed shape, preallocated KV, no OpenAI HTTP layer, no streaming JSON,
     minimal scheduler path.
   - If direct c1 is not much faster, the bottleneck is kernel/interconnect.
     If it is faster, the serving path deserves a focused latency audit.

5. Run a true 8-bit cross-engine control.
   - Try llama.cpp SYCL `Q8_0` or OpenVINO GenAI INT8 only as diagnostics.
   - Do not compare 4-bit as a quality-equivalent win.
   - Goal is to learn whether vLLM/XPU is losing time in kernels, scheduling,
     layout, or multi-GPU communication.

Bigger, bolder ideas to keep on the board:

1. Persistent one-layer MoE decode kernel.
   - Combine route read, expert work scheduling, GEMM1, activation, quant,
     GEMM2, and scatter for a single MoE layer.
   - Use dynamic work stealing so hot experts do not leave groups idle.
   - This is the cleanest path to remove launch gaps and scratch traffic, but
     it needs layer-local parity first.

2. Route-hot expert replication.
   - Use the extra VRAM budget to replicate only the hottest experts on every
     GPU while keeping the cold tail sharded.
   - Exact same weights and quant values, different placement only.
   - Simulator first: estimate cross-GPU traffic saved from captured route
     histograms before changing runtime placement.

3. Hybrid parallel layout for A3B.
   - Keep attention/dense parts replicated if memory allows, and expert-parallel
     only the MoE blocks.
   - TP4 may be paying communication costs that are too high for tiny active
     expert sets.
   - Compare short-context first so 32K KV memory does not hide the layout
     signal.

4. Decode command-list capture.
   - Reuse Level Zero command lists or graph-like command buffers around a full
     decode slice.
   - Success criterion is lower event-timeline wall time with identical output.
   - This is a lower-risk alternative to writing a full persistent kernel.

5. B70-native W8A8 retile cache.
   - Convert Quark W8A8 weights once into the exact Xe2 DPAS-friendly layout
     needed by the chosen grouped-GEMM policy.
   - Cache the retiled weights on disk or after load.
   - Quality should be unchanged because values/scales are unchanged; only
     memory order changes.

6. Verifier-preserving speculation/MTP.
   - The current Quark W8A8 INT8 model verifies every accepted token.
   - A draft lane can be smaller, MTP-based, CPU/iGPU-backed, or on spare B70
     capacity, but it cannot define accepted quality.
   - This is the most credible route to a 2x jump if kernel-only wins plateau.

7. Route-bucket AOT kernel family.
   - Compile a small set of kernels for common route histogram buckets by layer.
   - Dispatch based on the captured bucket rather than one generic grouped-GEMM
     policy.
   - Requires stable route buckets across prompt classes.

8. Cross-stack FusedMoE control.
   - Try the same model or a close exact-architecture INT8 artifact through
     Transformers/XPU and OpenVINO GenAI if supported.
   - Use it to isolate whether vLLM scheduling, vLLM kernels, or the model
     artifact layout is the larger tax.

9. NUMA/P2P topology hard audit.
   - Record PCIe lanes, P2P matrix, CPU affinity, IRQ placement, oneCCL/custom
     allreduce settings, and GPU frequency/power state for every accepted run.
   - If TP4 is communication-bound, topology may be worth more than another
     small kernel tune.

10. Long-context split policy.
    - Run separate 2K, 8K, 16K, and 32K c1 decode profiles.
    - If attention dominates only at high context, keep a short-context
      low-latency model slot and a long-context slot with different scheduler
      settings.
    - Same model and quality, different operational profiles.

11. Kernel autotune loop.
    - Feed route-exact cases into an automated search over tile policy,
      group count, prefetch depth, and work assignment.
    - Keep a generated patch plus JSON benchmark artifact per candidate.
    - Borrow the idea from Triton-style tuning, but keep final candidates in
      the SYCL/XPU kernel path if that wins.

12. Production mirror mode for aggregate throughput.
    - If true 8-bit full model plus required KV can fit on fewer than four B70s
      at a useful context, compare independent replicas against TP4.
    - This may improve aggregate throughput and tail latency even if it does
      not solve the single-request 32K headline.

Validation rule for every bold idea:

1. Layer-local parity or deterministic token-trace match where applicable.
2. Quality canary against accepted INT8 and BF16 fallback.
3. Repeat/repetition stress test.
4. p512/n512 single-request speed with warm steady-state repeats.
5. Route capture after the change to ensure it did not merely change prompt
   behavior.
6. Stability soak before any production promotion.

## W8A8 Policy Endpoint Gate

Follow-up to the route-exact grouped-GEMM policy screen.

Runtime procedure:

- Stopped accepted unset-policy endpoint:
  `qwen36-tp4-accepted-restored-20260611h`.
- Started `m32` endpoint:
  `VLLM_XPU_W8A8_GROUPED_GEMM_POLICY=m32`,
  log `/tmp/qwen36-quark-int8-tp4-m32-policy-20260611.log`.
- Started `base` endpoint:
  `VLLM_XPU_W8A8_GROUPED_GEMM_POLICY=base`,
  log `/tmp/qwen36-quark-int8-tp4-base-policy-20260611.log`.
- Restored accepted unset-policy endpoint:
  `qwen36-tp4-accepted-restored-20260611i`,
  log `/tmp/qwen36-quark-int8-tp4-accepted-restored-20260611i.log`.
- Backend/frontdoor health after restore:
  `http://127.0.0.1:18080/health -> 200`,
  `http://127.0.0.1:8000/health -> 200`.

Speed artifacts, p512/n512 streaming completions, r4:

| Runtime policy | Corrected after-first tok/s | E2E output tok/s | TTFT ms | Result |
| --- | ---: | ---: | ---: | --- |
| accepted unset baseline r8 | 99.422 | 97.957 | 75.644 | keep |
| accepted frontdoor r4 | 99.770 | 98.272 | 76.527 | keep |
| `m32` | 98.982 | 97.692 | 78.421 | reject, no endpoint speed win |
| `base` | 98.632 | 97.333 | 79.434 | reject, no endpoint speed win |

Artifacts:

- `data/qwen36-quark-int8-tp4-m32-policy-single-r4-20260611.json`
- `data/qwen36-quark-int8-tp4-base-policy-single-r4-20260611.json`
- accepted baseline:
  `data/qwen36-quark-int8-tp4-accepted-clean-single-r8-refresh-20260611.json`
- accepted frontdoor reference:
  `data/qwen36-quark-int8-tp4-accepted-frontdoor-single-r4-refresh-20260611.json`

Quality gate for `m32`:

- Command used the Qwen text quality suite through the frontdoor, with accepted
  frontdoor quality as baseline:
  `data/qwen36-quark-int8-tp4-accepted-frontdoor-quality-rerun64-refresh-20260611.json`
- Artifact:
  `data/qwen36-quark-int8-tp4-m32-policy-frontdoor-quality-rerun8-20260611.json`
- Result:
  `pass_all=true`, `baseline_match_all=true`, exact cases pass, repeat pass,
  8192-token needle pass.

Interpretation:

- The route-exact microbench result did not survive the full endpoint path.
- `m32` remains useful as evidence that tiny grouped-GEMM policy is not the
  dominant endpoint bottleneck at this shape.
- `base` is also slower, despite the best GEMM1 microbench result.
- Keep the accepted unset-policy runtime for production-candidate operation.
- Next work should move to route histograms, end-to-end decode timeline, fusion
  of quant/GEMM boundaries, direct c1 runner, or verifier-preserving
  speculation/MTP. Small policy-only grouped-GEMM tuning is unlikely to bridge
  the gap to `>200 tok/s`.

## Existing Decode Route Heatmap

After rejecting the endpoint policy overrides, I generated a combined heatmap
from existing decode route captures rather than restarting with route capture
again.

Command:

```bash
python3 scripts/analyze-qwen36-moe-route-heatmap.py \
  --input routecapture5_allranks='data/qwen36-quark-int8-tp4-routecapture5-routes-rank*.jsonl' \
  --input routecapture6_rank0='data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl' \
  --topn 16 \
  --max-num-tokens 1 \
  --out data/qwen36-quark-int8-tp4-routecapture5-6-decode-heatmap-20260611.json \
  --limit 30
```

Artifact:

- `data/qwen36-quark-int8-tp4-routecapture5-6-decode-heatmap-20260611.json`

Top ranked decode route-locality layers:

| Layer | Capture | Records | Top-16 share | Max expert share | Active expert share | Top experts |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 8 | routecapture5 all ranks | 508 | 0.5482 | 0.0827 | 0.4570 | 224, 110, 151, 239, 220, 117, 191, 206 |
| 20 | routecapture5 all ranks | 508 | 0.5344 | 0.0600 | 0.4883 | 224, 191, 151, 237, 117, 41, 53, 239 |
| 9 | routecapture6 rank0 | 95 | 0.5105 | 0.0566 | 0.4336 | 61, 243, 207, 197, 161, 166, 47, 250 |
| 21 | routecapture6 rank0 | 95 | 0.4895 | 0.0579 | 0.4648 | 243, 207, 44, 47, 61, 161, 166, 21 |
| 14 | routecapture6 rank0 | 95 | 0.4211 | 0.0487 | 0.4922 | 189, 52, 64, 194, 67, 160, 96, 167 |

Read:

- Existing natural/decode captures show real locality: top-16 experts can carry
  roughly half of the assignments for some layers.
- This supports hot-expert packing/replication or route-bucket AOT kernels as a
  larger no-quality-loss path.
- It also explains why a simple global grouped-GEMM policy override was too
  blunt. Layer-specific route shape matters more than one global tiny-M policy.

Coverage gap:

- These captures are not yet prompt-class complete. They cover natural-chat-ish
  decode windows and routecapture6 rank0 for layers 9/14/21.
- Before changing expert placement, capture the same route histograms for:
  natural chat, code, structured JSON, math/reasoning, repetitive text, and a
  long-context prompt.
- A good next artifact should rank layers by:
  top-16 share, max expert share, active expert share, cross-prompt top-expert
  Jaccard, and per-call max rows per expert.

Next implementation idea:

- Updated `scripts/measure-openai-endpoint-metrics.py` to include
  `request_started_at_unix` and `request_finished_at_unix` per measured repeat.
  This lets a future prompt-class route-capture run split one route JSONL by
  request time window instead of restarting the model for every prompt preset.
- Add a route-capture helper that runs the five `--prompt-kind preset` classes
  through `measure-openai-endpoint-metrics.py` under the route-capture launcher,
  then emits one combined prompt-class heatmap.
- If the same top experts persist across prompt classes, prototype hot-expert
  replication/packing for layers 8/20 first.

## Prompt-Class Decode Route Capture

Purpose:

- Check whether expert locality survives across prompt classes before investing
  in hot-expert packing, route-bucket kernels, or dynamic placement.
- Keep the speed result out of the decision loop: route capture disables graph
  capture and runs as a diagnostic endpoint only.

Command:

```bash
TAG=promptclass-routecapture-20260611a \
PROMPT_TOKENS=256 \
OUTPUT_TOKENS=64 \
LONG_PROMPT_TOKENS=4096 \
LONG_OUTPUT_TOKENS=32 \
scripts/run-qwen36-promptclass-route-capture.sh
```

Helper scripts added:

- `scripts/filter-qwen36-route-jsonl-by-metric-windows.py`
- `scripts/run-qwen36-promptclass-route-capture.sh`

Runtime:

- Started route capture endpoint:
  `qwen36-tp4-promptclass-routecapture-20260611a`
- Route capture filters:
  `CAPTURE_STAGE_REGEX='^quark_int8_apply$'`,
  `CAPTURE_LAYER_REGEX='layers\.(8|9|14|20|21)\.'`,
  `CAPTURE_MIN_NUM_TOKENS=1`,
  `CAPTURE_MAX_NUM_TOKENS=1`,
  `CAPTURE_INCLUDE_IDS=0`
- Restored accepted endpoint:
  `qwen36-tp4-accepted-restored-after-promptclass-routecapture-20260611a`
- Post-restore health:
  backend `http://127.0.0.1:18080/health -> 200`,
  frontdoor `http://127.0.0.1:8000/health -> 200`
- Live accepted process has route capture and grouped-GEMM policy overrides
  unset.

Artifacts:

- Metrics:
  - `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-natural-chat.json`
  - `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-code.json`
  - `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-structured.json`
  - `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-math-reasoning.json`
  - `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-repetitive.json`
  - `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-long-natural.json`
- Raw route JSONL:
  - `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-1286309.jsonl`
  - `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-1286310.jsonl`
  - `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-1286311.jsonl`
  - `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-1286312.jsonl`
- Split route JSONL:
  - `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-natural-chat.jsonl`
  - `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-code.jsonl`
  - `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-structured.jsonl`
  - `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-math-reasoning.jsonl`
  - `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-repetitive.jsonl`
  - `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-long-natural.jsonl`
- Summary:
  - `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-route-window-summary.json`
  - `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-heatmap.json`

Window split result:

| Label | Route records | Notes |
| --- | ---: | --- |
| natural-chat | 0 | completion ended before a useful decode capture window |
| code | 40 | short completion, 8 records per target layer |
| structured | 20 | short completion, 4 records per target layer |
| math-reasoning | 1260 | 252 records per target layer |
| repetitive | 1260 | 252 records per target layer |
| long-natural | 20 | short completion, 4 records per target layer |
| unmatched | 0 | good timestamp split |
| ambiguous | 0 | no overlapping request-window collisions |

Top prompt-class locality layers, top-16 experts:

| Layer | Labels with records | Mean top-16 share | Mean max expert share | Mean active expert share | Cross-label top-16 Jaccard |
| ---: | --- | ---: | ---: | ---: | ---: |
| 20 | code, structured, math-reasoning, repetitive, long-natural | 0.7980 | 0.1040 | 0.1883 | 0.0690 |
| 21 | code, structured, math-reasoning, repetitive, long-natural | 0.7944 | 0.1032 | 0.1867 | 0.0303 |
| 9 | code, structured, math-reasoning, repetitive, long-natural | 0.7944 | 0.1056 | 0.1938 | 0.0312 |
| 14 | code, structured, math-reasoning, repetitive, long-natural | 0.7940 | 0.1048 | 0.1867 | 0.0741 |
| 8 | code, structured, math-reasoning, repetitive, long-natural | 0.7893 | 0.1012 | 0.1914 | 0.0588 |

Read:

- There is much stronger per-label locality in these bounded diagnostic
  captures than the earlier all-rank natural/decode heatmap. Several labels
  were short, so the `1.0` top-16 shares for code/structured/long-natural are
  useful as a signal, not as a final distribution estimate.
- The low cross-label top-16 Jaccard is the important warning. Expert identity
  changes materially by prompt class, so a single static global hot-expert list
  is probably too blunt.
- Better no-quality-loss candidates are:
  route-bucket AOT kernels, prompt-class/dynamic hotpacks, and runtime
  work-stealing/persistent scheduling that handles skew without preassuming a
  fixed expert set.
- Coverage gap: rerun natural-chat with a forced long-answer prompt file so it
  produces enough decode records. The current natural-chat preset ended too
  quickly.

Next route-analysis tasks:

1. Add a forced-natural prompt file and rerun only the missing natural class.
2. Build a per-label top-expert overlap matrix for layers 8, 9, 14, 20, 21.
3. Simulate hot-expert replication/packing cost from the prompt-class heatmap.
4. Generate candidate route buckets and estimate dispatch hit rate before
   implementing kernel changes.
5. Add request-window split to the route analyzer output so route-capture runs
   can be compared directly to quality/speed artifacts.

## External Signals and Bigger Ideas

Sources checked:

- LocalMaxxing model search/leaderboard:
  `https://localmaxxing.com/api/models/search?q=Qwen3.6&limit=10`
  and
  `https://localmaxxing.com/api/leaderboard?hfId=Qwen%2FQwen3.6-35B-A3B&limit=100`
- vLLM XPU B580 issue:
  `https://github.com/vllm-project/vllm/issues/35638`
- vLLM XPU kernels repo:
  `https://github.com/vllm-project/vllm-xpu-kernels`
- Intel Extension for PyTorch release notes:
  `https://github.com/intel/intel-extension-for-pytorch/releases`
- vLLM Intel Arc Pro B-series blog:
  `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`
- Qwen3.6 B70 llama.cpp write-up:
  `https://bibek-poudel.medium.com/how-to-run-qwen3-6-27b-locally-on-intel-arc-pro-b70-what-actually-works-c96dec67c6f7`

Relevant external findings:

- LocalMaxxing has many Qwen3.6-35B-A3B results above 200 tok/s, but the top
  entries are not our target lane: they use 4-bit/MXFP4/NVFP4, MTP/speculation,
  CUDA/ROCm-specific engines, or much shorter context.
- The closest Intel B70 public references found are llama.cpp/SYCL Q4 records:
  around 70 tok/s single-card and 68.8 tok/s single-stream in a 4-card mirror
  setup, with higher aggregate throughput reported through multiple replicas.
  Our accepted Quark W8A8 TP4 frontdoor result around 99.77 corrected
  after-first tok/s is competitive, but it is not yet near the 200 tok/s
  target.
- The vLLM B-series blog says MoE GEMM scheduling gaps were attacked with a
  persistent work assignment scheme using an atomic next-job counter. That maps
  directly to our low-Jaccard/high-locality prompt-class trace: prompt routes
  are skewed, but the skew moves.
- Intel Extension for PyTorch 2.6/2.7 release notes call out MoE kernels,
  chunked prefill, vLLM/TGI support, and Arc B-series validation. This supports
  checking whether we are missing a newer XPU kernel package or whether vLLM is
  not routing this Quark INT8 path to the strongest backend.
- vLLM's public INT8 W8A8 documentation still describes INT8 compute support in
  NVIDIA terms. That reinforces the local conclusion that XPU INT8 support is
  special-path/kernel-specific rather than a mature generic path.

Bigger no-quality-loss ideas to keep in the backlog:

1. Persistent zero-gap MoE scheduler for XPU W8A8.
   - Implement or route to a persistent grouped-MoE kernel with dynamic
     work-stealing by expert block.
   - Target the moving prompt-class skew directly.
   - Quality risk: none if math is identical and token trace matches.

2. Route-bucket kernel family.
   - Use the route heatmap to define a few common shape buckets per layer.
   - Compile bucket-specific kernels rather than one global policy.
   - Dispatch bucket by current route histogram.

3. Dynamic expert hotpack.
   - Keep canonical weights unchanged, but maintain a packed device-local view
     of recently hot experts for layers 8, 9, 14, 20, and 21.
   - Repack asynchronously or at prompt boundary.
   - Validate with token-trace parity, because packing bugs can be silent.

4. Verifier-preserving MTP/speculation.
   - The accepted W8A8 model remains the verifier.
   - Draft/MTP can be separate, smaller, or lower precision as long as accepted
     tokens are verified by the W8A8 model.
   - This is the most credible path to a 2x single-request jump if exact-kernel
     optimization stalls.

5. Single-card or TP2 plus replica split.
   - Re-evaluate whether TP4 is actually helping single-request decode.
   - If communication dominates, TP2 or one-card W8A8 with shorter context may
     beat TP4 for latency while replicas recover aggregate throughput.
   - This keeps model quality fixed, but may require separate 8K/16K/32K slots.

6. Frontdoor bypass/direct engine mode.
   - Measure direct backend, frontdoor, and in-process runner on the same prompt
     artifacts.
   - If the OpenAI/streaming path costs multiple tok/s, keep a low-latency
     direct path for trusted internal consumers.

7. XPU stack upgrade matrix.
   - Try newer PyTorch/XPU, vLLM, and vLLM XPU kernels in a separate venv.
   - Gate on identical quality canaries and no regression in the accepted
     baseline.
   - Specifically check whether newer MoE kernels or INT8 paths are registered.

8. Topology-aware process layout.
   - Pin workers, IRQs, and communication threads.
   - Record PCIe BDF, affinity, and frequency state per run.
   - If TP traffic crosses a weak path, reorder devices or split service layout.

9. Quality-first benchmark harness upgrade.
   - Standardize every performance candidate with:
     exact prompt hashes, token traces, repeat canary, JSON/structured output,
     coding prompt, math prompt, and 8K/32K needle.
   - Publish only runs with both performance and quality artifacts.

10. LocalMaxxing submission discipline.
    - Submit accepted production-candidate results only, not diagnostic
      route-capture runs.
    - Include exact command, context length, quantization, no-prefix status,
      peak allocated VRAM, and quality-gate notes.

LocalMaxxing publication:

- New submission:
  `cmq9ifq0500b0r8012f27j1xl`
- Status:
  `APPROVED`
- Submitted model page:
  `Qwen/Qwen3.6-35B-A3B`
- Quantization:
  `Quark W8A8 INT8`
- Metric:
  `99.76969927367736` corrected after-first output tok/s,
  `76.52664251509123 ms` TTFT,
  `127.54716796875 GiB` peak total VRAM allocation across four B70s.
- Payload/response artifacts:
  - `data/localmaxxing-qwen36-b70-w8a8-submission-20260611.json`
  - `data/localmaxxing-qwen36-b70-w8a8-response-20260611.json`
- Dry-run issue:
  LocalMaxxing currently rejects `backend=xpu` because the accepted backend enum
  is limited to `cuda`, `rocm`, `metal`, `vulkan`, `cpu`, and `openvino`.
  The final payload omits `backend` rather than mislabeling the run.
- API normalization caveat:
  The response reused/normalized a hardware record for `4x Intel Arc Pro B70`
  and showed `ramGb=15` and `cpu=null`, even though the payload specified
  Threadripper PRO 5955WX and 128 GiB RAM. Keep the local payload artifact as
  the source of truth for system details.
- Existing earlier approved related submission:
  `cmq8yhxvo001ipb0149aoa79o`,
  submitted under `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`,
  `99.42835812273452` tok/s, no peak VRAM metric.

## Weighted Hotpack Follow-Up

Command:

```bash
python3 scripts/analyze-qwen36-route-overlap-hotpack.py \
  --input natural-chat=data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-natural-chat.jsonl \
  --input code=data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-code.jsonl \
  --input structured=data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-structured.jsonl \
  --input math-reasoning=data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-math-reasoning.jsonl \
  --input repetitive=data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-repetitive.jsonl \
  --input long-natural=data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-long-natural.jsonl \
  --topn 16 \
  --hotpack-k 8 \
  --hotpack-k 16 \
  --hotpack-k 32 \
  --hotpack-k 64 \
  --max-buckets 4 \
  --out-json data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-overlap-hotpack.json \
  --out-md data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-overlap-hotpack.md \
  --limit 5
```

Artifacts:

- `scripts/analyze-qwen36-route-overlap-hotpack.py`
- `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-overlap-hotpack.json`
- `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-overlap-hotpack.md`

Top weighted K=16 result:

| Layer | Records | Top-16 union | Top-16 Jaccard | Global K=16 | Label K=16 | Best bucket K=16 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 8 | 520 | 34 | 0.2673 | 0.4010 | 0.4894 | 0.4894 |
| 9 | 520 | 32 | 0.2840 | 0.4135 | 0.5019 | 0.5019 |
| 21 | 520 | 33 | 0.2897 | 0.4212 | 0.5019 | 0.5019 |
| 20 | 520 | 29 | 0.3183 | 0.4385 | 0.5106 | 0.5106 |
| 14 | 520 | 27 | 0.4024 | 0.4231 | 0.5010 | 0.5010 |

K=8/16/32/64 coverage read:

- Global hotpack K=16 only covers about 40-44% of weighted expert
  assignments in the sampled layers.
- Prompt/route-bucket K=16 covers about 49-51%, a consistent 7-9 percentage
  point lift over a global pack.
- Bucket K=32 reaches about 68-72%; bucket K=64 reaches about 88-90%.
- The best K=16 partition is consistent across the sampled layers:
  `code`, `structured`, and `long-natural` group together, while
  `math-reasoning` and `repetitive` each need separate route buckets.

Decision:

- A single static global expert pack is too blunt.
- Prompt/route buckets are real signal and should be kept for scheduling, but
  they are not a standalone path to >200 tok/s. K=16 leaves roughly half of
  routed work outside the hotpack, and K=32 still leaves roughly 28-32%.
- Existing route-exact grouped-GEMM microbenchmarks showed active-expert
  compaction is neutral, and endpoint policy overrides regressed the accepted
  server. Do not spend the next pass only on more static pack knobs.
- Highest-confidence no-quality-loss path remains removing decode-stage idle
  time and kernel overhead while preserving exact math.

Immediate next experiments:

1. Decode-stage timing census.
   - Measure per-token time in scheduler, sampling, attention, each MoE layer,
     all-reduce/collective work, and frontdoor streaming.
   - Goal: identify whether the next 2x has to come from MoE kernels, TP
     communication, scheduler overhead, or output path overhead.

2. Direct c1 runner.
   - Drive the engine without the OpenAI/frontdoor path using the same prompt
     artifacts and token counts.
   - If direct decode is materially faster, create a low-latency internal
     serving path or fix frontdoor pacing.

3. Layer-local fused MoE prototype.
   - Start with layers 8, 9, 14, 20, and 21 because the route-capture signal is
     strongest there.
   - Fuse route compaction, W8A8 activation quant, GEMM1, activation, GEMM2,
     and scatter/reduce where practical.
   - Quality gate: exact token trace parity against accepted W8A8.

4. Persistent zero-gap grouped-MoE kernel.
   - Use dynamic work stealing by expert block, matching the vLLM B-series
     persistent MoE direction.
   - This handles route skew without depending on a static expert list.

## Larger Bets

These are bigger than the next single patch, but they are credible no-quality
or verifier-preserving paths if we want a meaningful jump rather than another
1-3 tok/s:

1. End-to-end resident decode loop.
   - Keep per-layer decode work resident on XPU and avoid host-side launch gaps
     across the full decode step, not just inside one MoE kernel.
   - This is invasive, but it targets exactly the small-batch latency shape.

2. Prompt-class route scheduler.
   - Classify each request into a small route family at prefill or early decode.
   - Use that route family only to choose scheduling/bucket kernels, never to
     alter model outputs.
   - The current trace suggests at least three stable families:
     code/structured/long-natural, math-reasoning, repetitive.

3. TP4 alternatives that preserve the same model.
   - Benchmark TP1, TP2, TP4, and replica layouts with the same W8A8 weights and
     context lengths.
   - If communication dominates single-request decode, a smaller TP degree plus
     replicas may win latency while preserving aggregate capacity.

4. Exact verifier plus speculative draft.
   - Keep the current W8A8 model as verifier.
   - Run a draft model, MTP head, or ngram path only when all accepted tokens
     are verified by the W8A8 model.
   - This can preserve final output quality and may be the fastest path to a
     visible 2x if exact-kernel work stalls.

5. XPU kernel stack fork.
   - Maintain a local branch of `vllm-xpu-kernels` for B70-specific W8A8 MoE
     kernels instead of relying only on upstream release cadence.
   - Upstream or publish only after token-trace parity and reliability gates.

6. Engine split by product mode.
   - Keep a conservative 32K production slot.
   - Add lower-context latency slots, for example 8K/16K, using the same W8A8
     model and quality gates.
   - This does not lower model quality; it trades maximum context for speed in
     workflows that do not need 32K.

7. Topology and power/frequency control as first-class benchmark metadata.
   - Record GPU BDF order, XCCL topology, CPU affinity, IRQ affinity, power
     limit, clocks, thermals, and throttling state in every run.
   - If the cards are waiting on PCIe or worker placement, kernel work alone
     will not solve the single-request path.

8. Quality scoreboard before every speed claim.
   - Require token-trace parity on deterministic prompts where exactness is
     expected.
   - Add small eval sets for coding, JSON schema following, math, long-context
     retrieval, multilingual text, and refusal/safety behavior.
   - Publish speed only with the paired quality artifact.

External idea sources to keep watching:

- vLLM fused MoE kernel feature matrix:
  `https://docs.vllm.ai/en/latest/design/moe_kernel_features/`
- vLLM Intel Arc Pro B-series blog, especially the persistent zero-gap MoE
  discussion:
  `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`
- vLLM XPU kernels:
  `https://github.com/vllm-project/vllm-xpu-kernels`
- vLLM B70/XPU issue tracker examples:
  `https://github.com/vllm-project/vllm/issues/41663`
- Intel Extension for PyTorch releases:
  `https://github.com/intel/intel-extension-for-pytorch/releases`
- Community B70 performance reports:
  `https://www.reddit.com/r/LocalLLaMA/comments/1sgdt7t/my_experience_with_the_intel_arc_pro_b70_for/`
  and
  `https://www.reddit.com/r/LocalLLM/comments/1sfa0iw/2x_intel_arc_b70_benchmark/`

## Frontdoor A-B, Decode Timing, And Fresh Larger Ideas

This pass checked whether the OpenAI-compatible frontend or LAN frontdoor was
holding back single-request decode. It also made the timing/log parse
reproducible instead of relying on ad hoc shell parsing.

Script and launcher changes:

- `scripts/measure-openai-endpoint-metrics.py`
  - Added `--ignore-eos` so fixed-output decode measurements can force the
    requested output length when the model naturally emits EOS early.
  - The artifact now records `ignore_eos`.
- `scripts/launch-qwen36-quark-int8-accepted.sh`
  - Production default still strips timing env vars.
  - Diagnostics can now set `VLLM_XPU_DECODE_TIMING_ALLOW=1` to preserve:
    `VLLM_XPU_DECODE_TIMING`,
    `VLLM_XPU_DECODE_TIMING_SYNC`,
    `VLLM_XPU_DECODE_TIMING_RANK`,
    `VLLM_XPU_DECODE_TIMING_SUMMARY`,
    `VLLM_XPU_DECODE_TIMING_PRINT_EVERY`, and
    `VLLM_XPU_DECODE_TIMING_SKIP_FIRST`.
- `scripts/summarize-xpu-decode-timing-log.py`
  - Parses sparse `[vllm-xpu-timing]` lines and aggregate
    `[vllm-xpu-timing-summary]` lines.
  - Default sample window is the final request window; aggregate summary starts
    after the final HTTP completion line.

Repro commands:

```bash
/home/steve/.venvs/vllm-xpu/bin/python scripts/measure-openai-endpoint-metrics.py \
  --base-url http://127.0.0.1:18080 \
  --tokenizer /mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118 \
  --prompt-tokens 512 \
  --output-tokens 512 \
  --prompt-kind preset \
  --prompt-preset natural-chat \
  --repeats 3 \
  --warmup-output-tokens 32 \
  --endpoint completions \
  --mode stream \
  --ignore-eos \
  --skip-vram \
  --include-full-text \
  --out data/qwen36-quark-int8-tp4-backend-direct-natural-ignoreeos-p512o512-r3-20260611.json

/home/steve/.venvs/vllm-xpu/bin/python scripts/summarize-xpu-decode-timing-log.py \
  --log /tmp/qwen36-quark-int8-tp4-decode-timing-20260611b.log \
  --out data/qwen36-quark-int8-tp4-decode-timing-sync-rank0-lines-20260611b.json \
  --include-raw
```

Artifacts:

- `data/qwen36-quark-int8-tp4-backend-direct-natural-ignoreeos-p512o512-r3-20260611.json`
- `data/qwen36-quark-int8-tp4-frontdoor-natural-ignoreeos-p512o512-r3-20260611.json`
- `data/qwen36-quark-int8-tp4-backend-direct-repetitive-ignoreeos-p512o512-r3-20260611.json`
- `data/qwen36-quark-int8-tp4-frontdoor-repetitive-ignoreeos-p512o512-r3-20260611.json`
- `data/qwen36-quark-int8-tp4-decode-timing-sync-rank0-p512o128-20260611b.json`
- `data/qwen36-quark-int8-tp4-decode-timing-sync-rank0-lines-20260611b.json`
- `data/localmaxxing-b70-qwen36-benchmarks-20260611.json`

Direct backend vs frontdoor:

| Lane | Base URL | Prompt | Corrected after-first tok/s | E2E output tok/s | Client TTFT ms |
| --- | --- | --- | ---: | ---: | ---: |
| Direct backend | `127.0.0.1:18080` | natural-chat | 98.824 | 97.392 | 86.311 |
| LAN frontdoor | `127.0.0.1:8000` | natural-chat | 99.137 | 97.675 | 87.417 |
| Direct backend | `127.0.0.1:18080` | repetitive | 98.656 | 97.361 | 79.168 |
| LAN frontdoor | `127.0.0.1:8000` | repetitive | 98.824 | 97.580 | 76.186 |

Conclusion:

- The frontdoor is not the missing 2x. Direct backend and frontdoor results are
  effectively equal.
- Do not spend the next optimization pass on bypassing the frontdoor unless a
  different benchmark exposes a specific regression.
- The next performance work should stay inside model-forward, XPU kernels,
  graph capture, and collectives.

Decode timing diagnostic:

- Timing run:
  `data/qwen36-quark-int8-tp4-decode-timing-sync-rank0-p512o128-20260611b.json`
- Timing used synchronous XPU measurement, so the observed endpoint speed
  dropped to 60.408 corrected tok/s. This is diagnostic overhead, not a speed
  claim.
- Final request sparse samples:
  - `gpu_model_runner.model_forward`: mean 12.507 ms, median 12.516 ms.
  - `moe_forward_shared.custom_op`: one sparse sample at 5.238 ms.
  - `gpu_model_runner.compute_logits`: mean 0.800 ms.
  - `logits.local_argmax_lm_head`: mean 0.552 ms.
  - `gpu_model_runner.sampler`: mean 0.276 ms.
  - output conversion and bookkeeping stay below 0.1 ms each.
- Aggregate summary across the full diagnostic process:
  - `gpu_model_runner.model_forward`: 28.668 s total, 13.019 ms avg.
  - `moe_forward_shared.custom_op`: 7.117 s total, 5.012 ms avg.
  - `gdn_attention_core_xpu.native`: 6.250 s total, 0.0938 ms avg per
    attention call.
  - `xpu_moe.gemm1_w8a8`: 2.500 s total, 1.761 ms avg.
  - `xpu_moe.gemm2_w8a8`: 2.175 s total, 1.532 ms avg.
  - Some aggregate all-reduce rows include startup/prefill/outlier pollution,
    especially `all_reduce:(512, 2048)` with 65.2 ms avg and 872 ms max. Treat
    those as pointers for deeper per-request tracing, not as clean decode
    steady-state numbers.

External scan, 2026-06-11:

- Intel's current `ai-containers` vLLM XPU notes for Arc Pro B-series say the
  stack includes attention decode optimizations, persistent MoE GEMM, and fused
  activation. They specifically claim Qwen3-30B-A3B saw 2.6x end-to-end
  improvement from the MoE work:
  `https://github.com/intel/ai-containers/blob/main/vllm/0.10.2-xpu.md`
- `vllm-xpu-kernels` is now the purpose-built kernel stack for XPU vLLM and
  lists GDN/XE2 attention, MoE top-k/remap primitives, FP8/MxFP4 quantization,
  and grouped GEMM:
  `https://github.com/vllm-project/vllm-xpu-kernels`
- The vLLM XPU migration RFC says the project moved away from IPEX-heavy
  integration toward `vllm-xpu-kernels` for maintainability and performance,
  and lists XPU scaled-mm, FP8 W8A8, unquantized MoE, FP8 MoE, and MXFP4 MoE as
  completed migration items:
  `https://github.com/vllm-project/vllm/issues/33214`
- Open vLLM-XPU issue #390 says `XpuFusedMoe.apply()` allocates scratch tensors
  on every call and proposes reusable workspaces. This is directly relevant to
  our decode-heavy, one-MoE-call-per-layer-per-token profile:
  `https://github.com/vllm-project/vllm-xpu-kernels/issues/390`
- Open issue #389 tracks GDN speculative metadata shape checks rejecting
  graph-padded DFlash batches. This is relevant if we revisit exact-verifier
  speculation or DFlash:
  `https://github.com/vllm-project/vllm-xpu-kernels/issues/389`
- Intel Triton issue #7062 says an XE-Forge pass reported 2-10x per-shape
  speedups on vLLM unified attention, batched MoE, and fused MoE kernels. This
  needs verification, but it is the clearest external signal that kernel
  regeneration/source-level kernel work can plausibly move more than 1-3 tok/s:
  `https://github.com/intel/intel-xpu-backend-for-triton/issues/7062`
- vLLM's fused MoE modular-kernel design splits the operation into
  top-k/reduce, prepare/finalize, and experts components. That structure maps
  well to local experiments where we replace only the XPU expert component or
  workspace handling first:
  `https://docs.vllm.ai/en/stable/design/fused_moe_modular_kernel/`
- LocalMaxxing public API query for B70/Qwen3.6 returned 5 approved results.
  Our submitted 32K W8A8 run is currently the top returned B70/Qwen3.6 result
  at 99.770 tok/s with 76.527 ms TTFT:
  `data/localmaxxing-b70-qwen36-benchmarks-20260611.json`

New things to try:

1. Reusable XPU MoE workspaces.
   - Prototype the issue #390 idea locally in `vllm-xpu-kernels`.
   - Preallocate remap, GEMM1, activation, GEMM2, rows-per-expert, and mapping
     buffers for stable decode shapes.
   - Quality gate: byte/token parity against current W8A8 for deterministic
     prompts, plus route/count parity.
   - Why it might help: our timing says MoE is a large part of `model_forward`,
     and allocator/runtime overhead hurts small-batch decode.

2. Request-window timing reset.
   - Add a worker-side env option to clear timing counters at the start of a
     request and dump JSON at request end.
   - This removes graph-capture and warmup pollution from all-reduce and MoE
     summaries.
   - Use it before touching collectives so we do not optimize an artifact.

3. Persistent MoE B-series reproduction.
   - Identify the exact persistent MoE GEMM path Intel references in the
     B-series container notes.
   - Build a minimal microbench for Qwen3.6 A3B W8A8 shapes: rows 1, 2, 4, 8,
     16, 32, active experts, top-k, and hidden/intermediate sizes.
   - Compare current Quark W8A8 MoE path against persistent MoE with the same
     routes and weights.

4. XE-Forge-style kernel regeneration trial.
   - Start with one contained kernel, likely fused MoE experts or GDN attention,
     not the whole engine.
   - Use the current timing artifact as the shape target and the accepted model
     as verifier.
   - Do not accept any generated kernel without exact numeric parity and
     long-loop stability.

5. Shape-specialized decode graph family.
   - The final request shows stable decode shapes. Build graph families for the
     common decode sizes rather than one generic graph path.
   - Candidate shapes: single request, graph-padded request, and the common
     route-bucket shapes from the prompt-class capture.

6. TP communication isolation.
   - Run the new request-window timing on TP1, TP2, and TP4 with the same model
     and output length.
   - If `model_forward` shrinks disproportionately at lower TP, move toward
     replica or hybrid layouts for latency and keep TP4 for capacity.

7. Expert-parallel layout prototype.
   - For MoE layers, partition experts instead of tensor-splitting every dense
     boundary.
   - Replicate dense/attention where memory allows, or use TP2 plus expert
     partitioning.
   - This is a major engine change, but it directly targets MoE routing and
     TP collectives while preserving model math.

8. Exact verifier speculation, revisited only after #389-class issues are
   solved.
   - Keep Qwen3.6 W8A8 as verifier.
   - Use a draft only if accepted tokens are verified by the current model.
   - Track acceptance by prompt class; previous n-gram results were weak, but
     MTP/DFlash could still be useful if graph-padded spec metadata is fixed.

9. Lower-context latency slot with same weights.
   - Production can keep a 32K slot.
   - For chat-overlay and coding-assistant traffic that does not need 32K, test
     8K and 16K slots using identical W8A8 weights and identical quality gates.
   - This is not a quality reduction, but it may recover graph/KV/scheduler
     overhead and improve single-request latency.

10. Topology/power experiment as a first-class performance variable.
    - Record BDF order, `ZE_AFFINITY_MASK`, oneCCL transport, CPU affinity,
      NUMA placement, clocks, power caps, and thermals beside every run.
    - Try card-order permutations and CPU binding only after request-window
      timing tells us whether collectives are material.

11. AOT route-bucket kernels, but only after workspace and persistent-kernel
    baselines.
    - The prompt-class route buckets are real, but static hotpack coverage was
      not enough.
    - Use route families to choose precompiled kernels/workspaces, not to alter
      outputs or skip experts.

12. Quality harness expansion before claiming the next win.
    - Add deterministic token-trace tests where possible.
    - Add non-byte-exact semantic evals for current XPU nondeterminism:
      coding, JSON schema, math, retrieval/needle at 8K and 32K, multilingual,
      and tool-call formatting.
    - Pair every speed artifact with a quality artifact and a stability loop.

## Step Timing Instrumentation And MoE Visibility

Implemented opt-in step-level timing in the local vLLM runtime and extended the
log parser to aggregate `[vllm-xpu-timing-step]` JSON records.

Runtime source note:

- `patches/vllm-xpu-step-timing-instrumentation-20260611.md`

Lab-side code changes:

- `scripts/summarize-xpu-decode-timing-log.py`
  - Now parses step JSON lines.
  - Aggregates labels by mean total milliseconds per decode step.
- `scripts/launch-qwen36-quark-int8-accepted.sh`
  - Production default now also strips:
    `VLLM_XPU_DECODE_TIMING_STEP_SUMMARY`,
    `VLLM_XPU_DECODE_TIMING_STEP_EVERY`, and
    `VLLM_XPU_DECODE_TIMING_STEP_SKIP_FIRST`.

Graph-path step timing command:

```bash
tmux new-session -d -s qwen36-tp4-step-timing-20260611c \
  'cd /home/steve/llm-optimizations && \
   VLLM_XPU_DECODE_TIMING_ALLOW=1 \
   VLLM_XPU_DECODE_TIMING=1 \
   VLLM_XPU_DECODE_TIMING_SYNC=1 \
   VLLM_XPU_DECODE_TIMING_RANK=0 \
   VLLM_XPU_DECODE_TIMING_SUMMARY=1 \
   VLLM_XPU_DECODE_TIMING_PRINT_EVERY=0 \
   VLLM_XPU_DECODE_TIMING_SKIP_FIRST=20 \
   VLLM_XPU_DECODE_TIMING_STEP_SUMMARY=1 \
   VLLM_XPU_DECODE_TIMING_STEP_SKIP_FIRST=80 \
   VLLM_XPU_DECODE_TIMING_STEP_EVERY=1 \
   LOG_PATH=/tmp/qwen36-quark-int8-tp4-step-timing-20260611c.log \
   scripts/launch-qwen36-quark-int8-accepted.sh'

/home/steve/.venvs/vllm-xpu/bin/python scripts/measure-openai-endpoint-metrics.py \
  --base-url http://127.0.0.1:18080 \
  --tokenizer /mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118 \
  --prompt-tokens 512 \
  --output-tokens 128 \
  --prompt-kind preset \
  --prompt-preset natural-chat \
  --repeats 1 \
  --warmup-output-tokens 16 \
  --endpoint completions \
  --mode stream \
  --ignore-eos \
  --skip-vram \
  --include-full-text \
  --out data/qwen36-quark-int8-tp4-step-timing-direct-natural-ignoreeos-p512o128-r1-20260611c.json

/home/steve/.venvs/vllm-xpu/bin/python scripts/summarize-xpu-decode-timing-log.py \
  --log /tmp/qwen36-quark-int8-tp4-step-timing-20260611c.log \
  --out data/qwen36-quark-int8-tp4-step-timing-rank0-lines-20260611c.json \
  --include-raw
```

Graph-path results, rank 0, final 64 decode steps:

| Label | Mean total ms/step | Calls/step | Notes |
| --- | ---: | ---: | --- |
| `gpu_model_runner.model_forward` | 12.362 | 1 | Dominant visible region |
| `gdn_attention_core_xpu.native` | 2.713 | 30 | About 0.0904 ms/call |
| `gpu_model_runner.compute_logits` | 0.774 | 1 | Too small for 2x alone |
| `logits.local_argmax_lm_head` | 0.541 | 1 | Too small for 2x alone |
| `gpu_model_runner.sampler` | 0.163 | 1 | Small |
| `gpu_model_runner.select_sample_hidden` | 0.089 | 1 | Small |
| `gpu_model_runner.bookkeeping_sync` | 0.061 | 1 | Small |

Artifact:

- `data/qwen36-quark-int8-tp4-step-timing-rank0-lines-20260611c.json`

Important limitation:

- Python-level MoE labels do not appear during graph replay because the MoE
  Python wrappers are captured into the compiled graph. The graph-path timing
  still proves `model_forward` is the only region large enough to hide the
  missing 2x, but it cannot break down graph-replayed MoE subregions.

Eager MoE visibility run:

```bash
tmux new-session -d -s qwen36-tp4-eager-moe-timing-20260611d \
  'cd /home/steve/llm-optimizations && \
   XPU_GRAPH=0 \
   VLLM_XPU_ENABLE_XPU_GRAPH=0 \
   VLLM_XPU_DECODE_TIMING_ALLOW=1 \
   VLLM_XPU_DECODE_TIMING=1 \
   VLLM_XPU_DECODE_TIMING_SYNC=1 \
   VLLM_XPU_DECODE_TIMING_RANK=0 \
   VLLM_XPU_DECODE_TIMING_SUMMARY=1 \
   VLLM_XPU_DECODE_TIMING_PRINT_EVERY=0 \
   VLLM_XPU_DECODE_TIMING_SKIP_FIRST=8 \
   VLLM_XPU_DECODE_TIMING_STEP_SUMMARY=1 \
   VLLM_XPU_DECODE_TIMING_STEP_SKIP_FIRST=16 \
   VLLM_XPU_DECODE_TIMING_STEP_EVERY=1 \
   VLLM_EXTRA_ARGS=--enforce-eager \
   LOG_PATH=/tmp/qwen36-quark-int8-tp4-eager-moe-timing-20260611d.log \
   scripts/launch-qwen36-quark-int8-accepted.sh'
```

Eager is not a speed candidate. It measured only 8.698 corrected tok/s, but it
exposed MoE and collective labels.

Eager visibility results, rank 0, final 56 decode steps:

| Label | Mean total ms/step | Calls/step | Notes |
| --- | ---: | ---: | --- |
| `gpu_model_runner.model_forward` | 113.605 | 1 | Eager-only, diagnostic |
| `moe_forward_shared.custom_op` | 48.097 | 40 | MoE dominates eager forward |
| `all_reduce:(1, 2048):torch.bfloat16` | 8.357 | 81 | Collective overhead is material in eager |
| `xpu_moe.gemm1_w8a8` | 2.815 | 40 | About 0.0704 ms/call |
| `gdn_attention_core_xpu.native` | 2.756 | 30 | Similar to graph path |
| `xpu_moe.gemm2_w8a8` | 2.493 | 40 | About 0.0623 ms/call |
| `xpu_moe.remap_hidden_states` | 2.482 | 40 | Routing/remap overhead matters |
| `xpu_moe.gemm1_quant` | 2.191 | 40 | Activation quant overhead matters |
| `xpu_moe.gemm2_quant` | 2.097 | 40 | Activation quant overhead matters |
| `xpu_moe.activation` | 1.845 | 40 | Small per call, large across layers |
| `xpu_moe.gather` | 1.758 | 40 | Scatter/gather overhead matters |

Artifacts:

- `data/qwen36-quark-int8-tp4-eager-moe-timing-direct-natural-ignoreeos-p512o64-r1-20260611d.json`
- `data/qwen36-quark-int8-tp4-eager-moe-timing-rank0-lines-20260611d.json`

Restore smoke:

- Restored normal graph backend:
  `qwen36-tp4-accepted-restored-after-step-timing-20260611d`
- Backend and frontdoor health passed.
- No-timing p512/o128 smoke:
  `data/qwen36-quark-int8-tp4-post-step-timing-restore-natural-ignoreeos-p512o128-r1-20260611.json`
- Result:
  101.855 corrected after-first tok/s, 95.702 E2E output tok/s, 90.617 ms
  client TTFT.

Decision:

- The serving layer remains ruled out.
- Logits/sampler/output work is too small for the required 2x.
- GDN attention is visible and stable around 2.7 ms/step; it is worth
  optimizing, but even eliminating it entirely would not get to 200 tok/s.
- The next exact-quality speed work should target graph-replayed `model_forward`
  internals, with emphasis on:
  1. graph-visible MoE timing or C++/SYCL-side timing inside `xpu_fused_moe`;
  2. persistent/fused W8A8 MoE that reduces remap, quant, activation, and
     gather overhead across the 40 MoE calls per token;
  3. graph-captured or fused collectives, because eager shows many small
     all-reduces per token step.

Immediate next technical move:

- Add kernel-side or custom-op-side timing counters to `vllm-xpu-kernels`
  around `xpu_fused_moe` replay, not only Python wrappers.
- Use the graph path, not eager, as the speed gate.
- Keep quality gate unchanged: same W8A8 weights, same routing/math semantics,
  and token/semantic parity checks before accepting any kernel change.

## Step-Timing Follow-up Backlog And Larger Bets

Added after the graph/eager step-timing pass and another public leaderboard
refresh on 2026-06-11.

Public refresh artifacts:

- `data/localmaxxing-qwen36-quark-w8a8-int8-exact-refresh-20260611b.json`
- `data/localmaxxing-arc-b70-qwen-top-refresh-20260611b.json`
- `data/localmaxxing-30b-moe-top-refresh-20260611b.json`

Fresh external signals:

- Exact Quark W8A8 model query still shows the approved
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` row at `99.428 tok/s`.
- The broader Arc Pro B70/Qwen query shows a newer root-model B70 row at
  `99.770 tok/s` with peak VRAM recorded, then public 4-bit llama.cpp rows
  around `68.8-70.35 tok/s`. Treat the newer root-model row as the current
  public B70/Qwen3.6 speed reference, and the exact-model row as the canonical
  exact-artifact reference.
- The 30B-ish MoE public query has a `203.58 tok/s` Qwen3.6-35B-A3B row, but
  it uses RTX 5090 CUDA, NVFP4/FP8, and MTP speculative decoding. This is not
  comparable to the B70 W8A8 path, but it is strong evidence that a real
  `>200 tok/s` single-user result probably needs verifier-preserving
  speculation or a major MoE/layout kernel change.
- vLLM's fused MoE modular-kernel docs split MoE into top-k/reduce,
  prepare/finalize, and experts components. That is a useful implementation
  frame: replace one XPU component at a time instead of forking all MoE logic.
  Source: `https://docs.vllm.ai/en/stable/design/fused_moe_modular_kernel/`
- vLLM's MoE feature docs show modern MoE stacks treat INT8/FP8/FP4 routing,
  dispatch, quantization, and all-to-all policy as separable choices. This
  supports a route-exact component microbench before endpoint changes.
  Source: `https://docs.vllm.ai/en/latest/design/moe_kernel_features/`
- `vllm-xpu-kernels` release notes mention Xe2 grouped-GEMM heuristic work for
  MoE, FP8, and small-K cases. Keep checking whether current local kernels
  already contain the best Xe2 policy before writing new kernels.
  Source: `https://github.com/vllm-project/vllm-xpu-kernels/releases`
- The vLLM XPU migration RFC reinforces that the upstream direction is
  `vllm-xpu-kernels`, not IPEX-heavy glue. Upstreamable XPU kernel work is
  more likely to survive than private Python wrappers.
  Source: `https://github.com/vllm-project/vllm/issues/33214`

Do not spend more time on these unless new evidence appears:

1. `VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT=1`.
   - It is faster in isolation but has already failed arithmetic quality.
2. `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1`.
   - It was quality-safe but endpoint-slower.
3. Local argmax/logits-only work.
   - Step timing shows logits/sampler are too small to produce the required
     multiplier.
4. Frontdoor/server streaming as the main bottleneck.
   - Direct backend and frontdoor were effectively equal at p512/n512.
5. More blind oneCCL env sweeps.
   - Do them only after request-window timing proves collectives are the
     limiting graph-path component.

Ordered next things to try:

1. Route-exact primitive MoE microbench.
   - Extend the existing route-exact harness to time every current primitive:
     route remap, `rows_per_expert.zero_()`, GEMM1 quant, grouped GEMM1,
     activation, `act_output.contiguous()`, GEMM2 quant, grouped GEMM2, gather,
     and output combine.
   - Use captured Qwen3.6 route data, not synthetic routes.
   - Goal: find a component whose full-model share is large enough to matter
     before writing kernels.

2. Endpoint gate for the route-exact grouped-GEMM `m32` lead.
   - The microbench suggests `m32` improves the route-exact W8A8 GEMMs versus
     current tiny-M `m16`.
   - Run endpoint p512/n512, repeat quality, and a stability loop. Reject if
     it does not move endpoint speed.

3. Request-window timing reset.
   - Add a worker option to clear timing counters at request start and dump at
     request end.
   - This is needed before optimizing all-reduce or MoE subregions because the
     current aggregate timing includes graph-capture/prefill/startup pollution.

4. Graph-visible MoE timing.
   - Python wrapper timing disappears under graph replay.
   - Prefer XPU event counters, C++ extension counters, oneprof/VTune traces,
     or a graph-shaped offline runner that still hits compiled kernels.
   - Do not rely on eager timing for speed decisions; use eager only to name
     candidate components.

5. BF16 fallback quality comparator.
   - Keep the current W8A8 model as the production candidate, but compare
     against BF16 fallback on a fixed suite: deterministic canaries, math,
     code, JSON, long-context needle, multilingual, and several open-ended
     chat prompts.
   - Record exact-token matches where deterministic, plus semantic/validator
     scores where BF16 and INT8 can diverge without a clear correctness loss.
   - No speed win should be accepted if this suite exposes systematic quality
     drift.

6. Direct c1 runner.
   - Build an offline/direct model-runner harness with the same weights,
     tokenizer, sampler settings, and graph path but without OpenAI HTTP,
     streaming JSON, and frontdoor lifecycle overhead.
   - If it is near 100 tok/s, the bottleneck is model-core/kernel.
   - If it is much faster, make a single-user production fast lane.

7. Root-level host stability branch.
   - Keep separate from the model-kernel branch.
   - Validate `lspci -vv`, runtime power `on`, performance clock policy,
     CPU/NUMA affinity, fan/thermal stability, and BDF/rank ordering.
   - Goal is lower jitter and fewer device-lost incidents, not a claimed 2x.

Bigger, bolder architecture ideas:

1. Verifier-preserving MTP/DFlash/proposer lane.
   - Highest probability of a 2x jump if it can be made stable.
   - Current Quark W8A8 stays the verifier. Draft tokens may come from official
     Qwen3.6 FP8 MTP tensors, a same-family draft, a DFlash path, or a trained
     local proposer.
   - Required work: fix graph-padded speculative metadata/state corruption,
     then measure acceptance by prompt class and long-context shape.

2. Persistent XPU W8A8 MoE kernel.
   - Combine routing read, dynamic expert work scheduling, grouped GEMM1,
     activation, quant, grouped GEMM2, and gather for decode shapes.
   - Use dynamic work assignment so prompt-dependent expert skew does not leave
     execution lanes idle.
   - Start as a layer-local route-exact microbench, then wire through the vLLM
     modular experts component only after parity is proven.

3. MoE prepare/finalize replacement before expert replacement.
   - The eager profile says remap and gather are not free.
   - A lower-risk first kernel may be an exact prepare/finalize path with
     reusable scratch and better memory layout, leaving grouped GEMM unchanged.
   - This fits vLLM's modular-kernel framing and may be easier to upstream.

4. Route-hot expert replication.
   - Use spare VRAM to replicate hot experts on more cards while keeping the
     cold tail sharded.
   - The route heatmap says a fixed global hotlist is too blunt, so simulate
     prompt-class and layer-local hotsets first.
   - This changes placement only, not weights or math.

5. Hybrid TP/EP layout for Qwen3.6 A3B.
   - Pure TP4 may be paying too many tiny all-reduces for batch-1 decode.
   - Explore replicated dense/attention plus expert partitioning, or TP2 plus
     EP, with the same 32K KV target.
   - This is major engine work but directly attacks the architecture mismatch.

6. B70-native retile/repack cache for Quark W8A8.
   - Convert weights once into Xe2 DPAS-friendly layout for the selected GEMM
     policy, cache it, and avoid runtime layout tax.
   - Values/scales must remain identical. Only memory order changes.

7. Decode-layer command-list capture.
   - Instead of one persistent mega-kernel, capture a full decode slice as a
     Level Zero command-list/graph-style block with fewer host and event gaps.
   - This may provide much of the launch-gap win with lower math risk.

8. Overlapped all-reduce scheduling.
   - Where dependencies allow, launch the next independent projection or MoE
     prepare work while previous hidden-state reductions are in flight, then
     wait at the exact semantic boundary.
   - This must be proven with token-trace parity because moving waits around
     normalization/residual boundaries can silently change math.

9. Same-model 8-bit engine bakeoff.
   - Try OpenVINO GenAI or llama.cpp SYCL Q8/true-8-bit only as diagnostics.
   - The purpose is to locate the bottleneck class: model artifact layout,
     vLLM scheduling, XPU kernels, or TP communication.
   - Do not promote a lower-bit engine as a quality-equivalent replacement.

10. Short-context latency slot.
    - Keep the production 32K slot, but test 2K/8K/16K slots with identical
      W8A8 weights and quality gates.
    - If model-forward timing changes materially with context length, operate
      a same-quality low-latency slot for chat-overlay/coding traffic that does
      not need 32K.

Additional bold ideas added after the next-round planning review:

1. Single-request direct graph runner.
   - Build a minimal decode runner around the same vLLM/XPU kernels and model
     weights, but remove OpenAI serving, request scheduling, streaming, and
     multi-tenant policy from the batch-1 path.
   - This is not a replacement engine yet; it is a bottleneck isolation tool.
   - If it is far faster than vLLM serving, production can keep vLLM for
     concurrency and route latency-critical single-user sessions through a
     same-quality fast lane.

2. TP2-first layout with replicated hot dense work.
   - TP4 may be over-sharding for batch-1 decode. Test whether TP2 can keep
     the full W8A8 weights plus 32K KV inside per-card memory while cutting
     hidden-state collectives.
   - Use the spare two B70s either as a second production replica or for
     selected replicated expert/dense work, not as mandatory TP ranks.

3. Layer-local expert replication instead of global hot packing.
   - The route heatmaps showed a fixed hot-expert order is too blunt.
   - Simulate layer-local hotsets and replicate only the high-traffic experts
     on extra ranks/cards. This could reduce cross-rank traffic without
     changing weights, quantization, or final math.

4. Persistent route scratch and resident row counters.
   - Avoid per-step tiny allocations/clears by keeping route scratch,
     `rows_per_expert`, unpermuted maps, quant buffers, and gather buffers
     resident and zeroing only the touched expert range.
   - Gate this with primitive timing first; if `rows_zero` is tiny, do not
     spend kernel time here.

5. Route-aware grouped-GEMM autotuner.
   - Feed captured route windows into an automated search over grouped-GEMM
     tile shape, expert ordering, split-K, active-expert compaction, and
     output layout.
   - Accept candidates only if they improve both route-exact microbenchmarks
     and endpoint p512/n512. The previous `m32` case proved that a kernel
     microbench lead can disappear at endpoint scope.

6. Import OpenVINO/oneDNN/ITREX kernel ideas, not necessarily the engine.
   - Intel's other stacks may already have better XMX/DPAS W8A8 packing,
     dynamic quantization, or command submission patterns.
   - Use them as reference implementations or diagnostics while keeping the
     current Quark/vLLM quality harness as the acceptance gate.

7. Full decode command-list capture per graph family.
   - Capture not just model-forward but the common decode sequence around MoE,
     attention, residual/all-reduce, logits, and sampler into a reusable Level
     Zero command-list family.
   - This attacks host/event gaps without changing arithmetic. It is a bigger
     runtime project, but it may be less risky than a monolithic mega-kernel.

8. Exact speculative decode with several draft lanes.
   - Treat n-gram, MTP tensors, a small Qwen3.6-family draft, and a learned
     route/prompt-class proposer as interchangeable draft sources.
   - The current model remains the verifier. Quality acceptance is exact-token
     verifier output, plus deterministic replay tests to catch state bugs.
   - This remains the most plausible `>200 tok/s` route if the XPU model-core
     floor stays near `100 tok/s`.

9. End-to-end kernel timeline budget.
   - Produce a token-step budget that sums graph-visible XPU kernels,
     collectives, host stalls, and sampler time for one accepted request.
   - Every bold idea should point to a named millisecond bucket in that budget.
     Otherwise it is likely a distraction.

10. Production split by quality-equivalent service class.
    - Keep one canonical W8A8 model artifact, but run separate slots for
      latency-critical single user, long-context 32K, and aggregate throughput.
    - Slot differences can include TP degree, graph family, context cap,
      scheduler settings, and frontdoor policy, but not lower-fidelity weights.

Decision standard for all bold ideas:

1. Same model verifier or a BF16/current-model quality proof.
2. Route/token trace parity where deterministic.
3. Repeat stability, including long-loop repeated prompts.
4. p512/n512 warm steady-state single-request speed.
5. Aggregate c1/c2/c4/c8/c16/c32/c48 sanity before production promotion.
6. Stability soak after every extension/kernel change.

## Primitive MoE Timing Addendum: Route Counters And Activation Contiguity

Added after extending `scripts/bench-qwen36-int8-moe-kernels.py` to time
`rows_per_expert.zero_()` and `act_output.contiguous()` separately in the
manual route-exact W8A8 MoE path.

Artifacts:

- `data/qwen36-quark-int8-moe-routecapture6-layer9-primitive-r15-20260611b.json`
- `data/qwen36-quark-int8-moe-routecapture6-layer9-hotpack-primitive-r15-20260611b.json`
- `data/qwen36-quark-int8-moe-routecapture6-layer14-primitive-r15-20260611b.json`
- `data/qwen36-quark-int8-moe-routecapture6-layer14-hotpack-primitive-r15-20260611b.json`
- `data/qwen36-quark-int8-moe-routecapture6-layer21-primitive-r15-20260611b.json`
- `data/qwen36-quark-int8-moe-routecapture6-layer21-hotpack-primitive-r15-20260611b.json`
- `data/qwen36-quark-int8-moe-routecapture6-primitive-plus-component-summary-20260611b.json`

Validation:

- `python -m py_compile` passed for the patched benchmark and summarizer.
- `jq empty` passed for all new JSON artifacts.
- Across raw and hotpack route scans, both manual paths matched
  `xpu_fused_moe` exactly: max diff `0.0`.

Command pattern:

```bash
ONEAPI_DEVICE_SELECTOR=level_zero:0 ZE_AFFINITY_MASK=0 \
PYTHONPATH=/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels \
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib \
/home/steve/.venvs/vllm-xpu/bin/python scripts/bench-qwen36-int8-moe-kernels.py \
  --rows 1,16 \
  --route-jsonl data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl \
  --route-layer-regex 'model\.layers\.9\.' \
  --route-start-indices 0:96:12 \
  --iterations 15 \
  --warmup 5 \
  --device xpu \
  --output-json data/qwen36-quark-int8-moe-routecapture6-layer9-primitive-r15-20260611b.json
```

Raw versus hotpack summary:

| label | rows | windows | total delta | prealloc delta | top primitive delta |
| --- | ---: | ---: | ---: | ---: | --- |
| layer9 | 1 | 8 | `+0.758%` | `+1.138%` | `act_contiguous +6.272 us / +11.92%` |
| layer9 | 16 | 8 | `-4.366%` | `-0.959%` | `gemm2 -2.598 us / -2.68%` |
| layer14 | 1 | 8 | `-3.171%` | `-2.853%` | `activation -5.798 us / -6.60%` |
| layer14 | 16 | 8 | `-12.476%` | `-10.573%` | `gemm2 -15.293 us / -12.93%` |
| layer21 | 1 | 8 | `-5.904%` | `-4.523%` | `remap -6.411 us / -5.99%` |
| layer21 | 16 | 8 | `-20.389%` | `-14.644%` | `quant2 -22.031 us / -19.62%` |

Selected raw primitive means:

| label | rows | rows_zero | act_contiguous | activation+contiguous+quant2 | component_sum | fused total | prealloc total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| layer9 | 1 | `75.892 us` | `52.850 us` | `213.678 us` | `723.645 us` | `272.425 us` | `205.267 us` |
| layer9 | 16 | `79.263 us` | `58.500 us` | `229.092 us` | `763.768 us` | `280.981 us` | `212.330 us` |
| layer14 | 1 | `81.413 us` | `56.944 us` | `231.202 us` | `777.140 us` | `290.003 us` | `218.856 us` |
| layer14 | 16 | `90.800 us` | `63.489 us` | `259.696 us` | `881.400 us` | `338.139 us` | `256.758 us` |
| layer21 | 1 | `79.485 us` | `55.880 us` | `225.960 us` | `765.055 us` | `289.570 us` | `219.044 us` |
| layer21 | 16 | `93.980 us` | `64.057 us` | `266.121 us` | `899.224 us` | `350.133 us` | `263.323 us` |

Interpretation:

1. The new primitive labels are useful for relative deltas, but the per-call
   component sum is not endpoint wall-clock truth. Wrapping every tiny call in
   XPU events inflates the manual sum above the fused/preallocated totals.
2. `act_output.contiguous()` appears measurable, but because the activation
   output is already allocated contiguous in this harness, this may be mostly
   event/dispatch overhead rather than a real device copy. Confirm with
   graph-visible profiling before spending kernel time on it.
3. `rows_per_expert.zero_()` is consistently visible at roughly `76-94 us` in
   the event-wrapped manual path. That supports tracking persistent route
   scratch and touched-expert zeroing, but only after request-window timing
   proves this cost exists in the graph replay path.
4. Hotpacking is still not a clean endpoint candidate by itself. It regresses
   layer9 rows=1 and improves rows=16 more strongly, especially layer21. The
   better idea is layer-local route-aware placement/replication, not a single
   global hotpack reorder.
5. The next measured step should be graph-visible MoE timing or a direct c1
   runner. The route-exact microbench is now good enough for candidate
   generation, but endpoint promotion still needs full p512/n512 speed and
   quality gates.

## Offline C1 Runner: HTTP Is Not Hiding A 2x Win

Added after building `scripts/run-qwen36-offline-warm-throughput.py`, a
Qwen3.6-specific in-process `vllm.LLM` diagnostic that mirrors the accepted
TP4/Quark/32K/no-prefix server posture without OpenAI HTTP or LAN frontdoor
streaming.

Artifact:

- `data/qwen36-quark-int8-tp4-offline-c1-p512o512-r4-20260611.json`
- Offline run log: `/tmp/qwen36-offline-c1-p512o512-r4-20260611.log`
- Restore failure log: `/tmp/qwen36-quark-int8-tp4-accepted-restored-after-offline-c1-20260611f.log`
- Successful retry restore log: `/tmp/qwen36-quark-int8-tp4-accepted-restored-after-offline-c1-retry-20260611g.log`

Command:

```bash
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/run-qwen36-offline-warm-throughput.py \
  --input-len 512 \
  --output-len 512 \
  --num-prompts 1 \
  --warmup-repeats 1 \
  --repeats 4 \
  --out data/qwen36-quark-int8-tp4-offline-c1-p512o512-r4-20260611.json
```

Result:

| mode | prompt/output | repeats | mean output tok/s | min | max | mean total tok/s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| offline `vllm.LLM` | p512/o512/c1 | 4 | `96.56` | `91.71` | `98.35` | `193.12` |

Per-repeat output decode rates:

- repeat 0: `98.04 tok/s`
- repeat 1: `91.71 tok/s`
- repeat 2: `98.15 tok/s`
- repeat 3: `98.35 tok/s`

Warmup and initialization:

- Engine init, including compile/capture: `125.76 s`.
- First warmup generation: `17.46 output tok/s`, polluted by final graph/cache
  work and excluded from the measured repeats.

Interpretation:

1. Offline in-process vLLM is effectively the same speed class as the accepted
   backend/frontdoor measurements. HTTP, SSE streaming, and frontdoor routing
   are not hiding a `2x` single-user decode win.
2. The main target remains model-core/runtime: graph-visible MoE, attention/GDN,
   TP collectives, layout, or exact verifier-preserving speculation.
3. The offline script is a useful future diagnostic for engine changes, but it
   is not a quality proof. Token hashes varied across temperature-0 repeats in
   this run, so deterministic/quality claims must continue to use the existing
   frontdoor token-trace and quality suites.
4. This closes the "direct c1 runner" question for now: a specialized offline
   path does not justify production work unless later model-core changes make
   in-process serving diverge from HTTP serving.
5. Reliability note: the first accepted-server restore after the offline run
   reached `/health` but hit `UR_RESULT_ERROR_DEVICE_LOST` on the first small
   completion, inside `block_table.copy_to_gpu`. `xpu-smi` and `torch.xpu`
   still saw all four B70s. Killing the dead session and relaunching the
   accepted server in
   `qwen36-tp4-accepted-restored-after-offline-c1-retry-20260611g` restored
   backend generation and frontdoor health. Treat heavy offline engine
   init/teardown as another case requiring a real post-restore generation
   smoke, not just `/health`.

## Post-Offline Ideas: Bigger No-Quality-Loss Bets

Added after the offline c1 runner showed that HTTP, SSE, and the LAN frontdoor
are not hiding a `2x` win. The current ceiling is inside model execution,
runtime scheduling, TP collectives, or verifier-preserving speculation.

Immediate things to try:

1. Summarize the existing n-gram2/cg3 prompt-class artifacts before launching
   more speculative runs.
   - Extract accepted/rejected draft-token rates by prompt class, loop
     signatures, and any request where speculative output diverges from the
     accepted token trace.
   - Do not promote speculation from speed alone. Promotion requires token
     parity against `data/qwen36-quark-int8-accepted-frontdoor-token-trace-20260611.json`,
     repeat64 stability, and the 8K needle case.
2. Add request-id correlation to the speculative JSONL trace and client
   quality trace.
   - This is required to connect a corrupt repeat output to the exact scheduler
     accept/reject decisions that produced it.
3. Add a strict speculative debug mode that disables any bonus-token emission
   after accepted draft tokens.
   - If repeat-loop corruption disappears, the bug is likely target bonus-state
     advancement or stale token visibility in the n-gram lookup.
4. Run a verifier-only shadow decode on any speculative failure.
   - On divergence, immediately replay the same prompt against the accepted
     baseline with the same frontdoor formatting. This separates model-quality
     concerns from scheduler/state corruption.
5. Use the graph-visible timing path for a short accepted decode window.
   - Target a per-token budget that sums to the observed `~10 ms/token` floor.
     Anything not visible in that budget is not worth optimizing for the
     `>200 tok/s` goal.

Bigger bets worth keeping on the board:

1. Exact sidecar draft speculation.
   - Keep the current Quark W8A8 INT8 model as the final verifier, but run a
     draft lane from a smaller Qwen3.6-family model, a reduced-context copy, or
     the official FP8/MTP-capable checkpoint if it can be loaded as a proposer.
   - This can preserve final output quality because the current verifier still
     accepts or rejects every token. The hard parts are XPU graph metadata,
     scheduler correctness, and avoiding draft overhead that consumes the win.
2. Persistent fused MoE decode kernels.
   - Build a batch-1/token-1 decode kernel family that owns route counting,
     touched-expert zeroing, remap, GEMM1, activation, quant2, GEMM2, and
     weighted combine for the common route shapes.
   - The primitive scan suggests global hotpacking is too blunt. The credible
     version is layer-specific and shape-specific, with exact parity gates.
3. Hybrid TP plus expert-parallel layout.
   - Current TP4 pays collective and small-M penalties everywhere. A bolder
     layout would replicate cheap dense work or hot experts while splitting
     expensive expert work differently per layer.
   - Memory headroom makes partial replication plausible, but it needs a small
     layer-local prototype before touching the full engine.
4. Single-request static lane.
   - Build a c1 decode service path with fixed prompt template state, fixed
     block tables, preallocated KV, and captured command-list or graph replay
     across the full decode loop.
   - This is separate from the high-concurrency production lane. It targets
     latency and single-user tok/s first, with automatic fallback to the
     accepted server if any quality or reliability gate fails.
5. Borrow or upstream B70-specific W8A8 kernels.
   - Mine OpenVINO, oneDNN, ITREX, BigDL, and vLLM/XPU issue threads for
     grouped-GEMM, MoE, and tiny-shape decode kernels that are already tuned
     for Intel GPUs.
   - Package our route histograms, primitive timing, and Localmaxxing result as
     a compact upstream repro so kernel owners can reproduce the exact
     bottleneck.
6. Route-aware prefetch and scratch persistence.
   - Use previous-token/layer route histograms only to prepare memory and
     command choices, not to change math. Possible wins include touched-expert
     zeroing, stable route scratch, and prefetching layer-local hot experts.
7. Same-quality engine bakeoff.
   - Keep the current model and 8-bit target, but test whether OpenVINO/Optimum
     Intel, IPEX-LLM/BigDL, LMDeploy, or a thinner llama.cpp-style path can run
     this exact checkpoint or a mechanically equivalent INT8 conversion.
   - Any candidate must pass the same token-trace and repeat stability gates
     before performance matters.
8. Production split after the speed work.
   - If the final high-speed path is specialized or speculative, expose it as a
     latency class with automatic verifier-baseline fallback. Keep the accepted
     TP4 vLLM path as the reliability floor until the faster lane survives
     repeat quality, long-context, soak, and device-lost recovery tests.

Current prioritization:

1. Fix and instrument verifier-preserving speculation first, because it is the
   only already-plausible path to a single-request `2x` without changing final
   quality.
2. In parallel, build a graph-visible timing budget so non-speculative kernel
   work attacks the largest measured token-time blocks.
3. Use route-exact MoE microbenches for candidate generation only. Endpoint
   speed plus quality gates decide promotion.

## N-Gram2/CG3 Trace Summary: Quality-Clean But Not A Speed Candidate

Added after building `scripts/summarize-qwen36-spec-trace.py` and applying it
to the existing n-gram2/cg3 scheduler traces plus seeded prompt-class
artifacts.

Artifacts:

- `scripts/summarize-qwen36-spec-trace.py`
- `data/qwen36-quark-int8-tp4-ngram2-cg3-spec-summary-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram2-cg3-spec-summary-20260611.md`
- `data/qwen36-quark-int8-tp4-ngram2-cg3-chat-promptclass-spec-jsonl-20260611.jsonl`

Command:

```bash
python3 scripts/summarize-qwen36-spec-trace.py \
  --trace-jsonl data/qwen36-quark-int8-tp4-ngram2-cg3-spec-jsonl-20260611.jsonl \
  --trace-jsonl data/qwen36-quark-int8-tp4-ngram2-cg3-chat-promptclass-spec-jsonl-20260611.jsonl \
  --trace-jsonl data/qwen36-quark-int8-tp4-ngram2-cg3-chat-promptclass-seeded-spec-jsonl-20260611.jsonl \
  --metric-json accepted-natural-chat=data/qwen36-quark-int8-tp4-accepted-chat-promptclass-natural-chat-seeded-r2-20260611.json \
  --metric-json ngram2-natural-chat=data/qwen36-quark-int8-tp4-ngram2-cg3-chat-promptclass-natural-chat-seeded-r2-20260611.json \
  --metric-json accepted-code=data/qwen36-quark-int8-tp4-accepted-chat-promptclass-code-seeded-r2-20260611.json \
  --metric-json ngram2-code=data/qwen36-quark-int8-tp4-ngram2-cg3-chat-promptclass-code-seeded-r2-20260611.json \
  --metric-json accepted-structured=data/qwen36-quark-int8-tp4-accepted-chat-promptclass-structured-seeded-r2-20260611.json \
  --metric-json ngram2-structured=data/qwen36-quark-int8-tp4-ngram2-cg3-chat-promptclass-structured-seeded-r2-20260611.json \
  --metric-json accepted-math-reasoning=data/qwen36-quark-int8-tp4-accepted-chat-promptclass-math-reasoning-seeded-r2-20260611.json \
  --metric-json ngram2-math-reasoning=data/qwen36-quark-int8-tp4-ngram2-cg3-chat-promptclass-math-reasoning-seeded-r2-20260611.json \
  --quality-json ngram2-rerun64=data/qwen36-quark-int8-tp4-ngram2-cg3-frontdoor-quality-rerun64-20260611.json \
  --out-json data/qwen36-quark-int8-tp4-ngram2-cg3-spec-summary-20260611.json \
  --out-md data/qwen36-quark-int8-tp4-ngram2-cg3-spec-summary-20260611.md
```

Trace summary:

| Trace | Rows | Requests | Draft tokens | Accepted | Rejected | Accept rate | Full-accept rows | Full-reject rows | Max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base n-gram2/cg3 | 685 | 14 | 1365 | 1044 | 321 | `76.48%` | `69.64%` | `16.93%` | 147 |
| chat prompt-class | 668 | 12 | 1334 | 617 | 717 | `46.25%` | `36.68%` | `44.31%` | 8 |
| seeded chat prompt-class | 662 | 12 | 1321 | 609 | 712 | `46.10%` | `35.95%` | `43.96%` | 8 |

Seeded prompt-class speed versus accepted:

| Class | Accepted corrected tok/s | N-gram2 corrected tok/s | Delta | Same output-token count |
| --- | ---: | ---: | ---: | --- |
| natural-chat | `99.59` | `90.85` | `-8.77%` | yes |
| code | `99.61` | `93.73` | `-5.91%` | yes |
| structured | `99.44` | `116.36` | `+17.01%` | no; n-gram2 stopped at 440/445 tokens |
| math-reasoning | `99.40` | `98.39` | `-1.02%` | yes |

Quality:

- `data/qwen36-quark-int8-tp4-ngram2-cg3-frontdoor-quality-rerun64-20260611.json`
  reports `pass_all=true` and `baseline_match_all=true`.
- Repeat64 passed with one unique repeat hash.
- The long-context case passed.

Interpretation:

1. N-gram2/cg3 is not showing the same corruption as rejected n-gram1/ngram5
   in this deterministic quality suite, but it also does not provide a useful
   broad speed win.
2. The base synthetic trace has high acceptance (`76.48%`) and long full-accept
   streaks, but chat prompt-class acceptance collapses to about `46%`. This is
   why raw trace acceptance is not enough evidence for production.
3. The only prompt-class speed win is structured output, and it generated fewer
   output tokens than the accepted baseline. Do not count that as a valid speed
   win.
4. The old prompt-class artifacts do not store request IDs or request
   timestamps, so they cannot be joined exactly to scheduler trace rows. The
   current measurement script now records `request_id` and timestamps, so the
   next speculative run can support exact joins.

Decision:

- Do not promote n-gram2/cg3 as a production or Localmaxxing speed candidate.
- Do not spend more time on blind n-gram width sweeps.
- If speculation remains the next `2x` path, first add/validate request-id
  correlation and the strict no-bonus-token debug mode, then re-run prompt-class
  measurements with exact trace joins.

## Spec Decode No-Bonus Debug Hook

Added after the n-gram2/cg3 summary showed that blind n-gram width sweeps are
not the right next step. This is an opt-in diagnostic, not a promoted runtime
change.

Artifacts:

- `patches/vllm-qwen36-spec-decode-no-bonus-debug-20260611.patch`
- `scripts/launch-qwen36-quark-int8-ngram-trace.sh`
- `scripts/summarize-qwen36-spec-trace.py`

Behavior:

- New env flag: `VLLM_XPU_SPEC_DECODE_DISABLE_FULL_ACCEPT_BONUS=1`.
- Launcher convenience knob:
  `DISABLE_FULL_ACCEPT_BONUS=1 scripts/launch-qwen36-quark-int8-ngram-trace.sh`.
- The hook only trims the extra emitted token on full-accept speculative rows,
  where `num_accepted == num_draft_tokens`.
- Partial-rejection rows still emit the verifier replacement token for the
  first rejected draft.
- The scheduler JSONL trace now records:
  - `generated_token_ids`: original verifier output row.
  - `emitted_token_ids`: tokens actually passed to the request/output path.
  - `suppressed_bonus_token_id`: the trimmed token ID, or `null`.
- The summarizer now reports `suppressed_bonus_rows` and keeps old traces
  compatible.

Validation:

- `python3 -m py_compile` passed for the patched scheduler and updated
  summarizer.
- `bash -n` passed for `scripts/launch-qwen36-quark-int8-ngram-trace.sh`.
- The tracked patch passed `git apply --reverse --check` against the current
  local vLLM tree, proving it matches the applied local scheduler edit.
- Existing n-gram2/cg3 summaries were regenerated; old traces show
  `suppressed_bonus_rows=0`, as expected.

Next diagnostic run:

1. Launch the prior failure-oriented n-gram5 path with
   `DISABLE_FULL_ACCEPT_BONUS=1`, bounded JSONL tracing, and request-id-aware
   prompt-class metrics.
2. Run token-trace parity plus repeat64 and the 8K needle case.
3. If repeat-loop corruption disappears, the likely bug is bonus-token state
   advancement or stale accepted-token visibility in the n-gram proposer.
4. If corruption remains, move to request-id-correlated proposer-source tracing
   before trying more speculative widths.

## Additional Bigger Bets And Things To Try

Added after the no-bonus speculative diagnostic hook was implemented. These
are not promotions. They are higher-upside paths that might realistically move
single-request speed while keeping the current Quark INT8 verifier as the final
quality authority.

Things to try soon:

1. Speculative correctness replay harness.
   - Build a small offline replay from the scheduler JSONL rows that replays
     `draft_token_ids`, verifier outputs, accepted counts, emitted tokens, and
     bonus-token suppression without the live server.
   - Use it to reproduce repeat-loop corruption deterministically before
     touching more speculative widths.
   - This should become the gate for any future MTP, DFlash, EAGLE, or n-gram
     path: if the replay cannot explain emitted tokens, the run is not
     publishable.

2. Request-id exact joins everywhere.
   - Extend the client metric artifacts, token trace artifacts, and scheduler
     speculative trace so every generated output can be joined to the exact
     accept/reject rows that produced it.
   - Record request start/end timestamps, prompt class, output token count,
     generated token hashes, and `X-Request-Id`/vLLM request IDs in one
     summary.
   - This is required before we can trust prompt-class speed wins, because the
     old structured n-gram2 apparent win generated fewer tokens.

3. Reduced-context MTP sidecar feasibility spike.
   - Keep the current Quark W8A8 INT8 model as verifier.
   - Try to load official Qwen3.6 FP8 MTP tensors or an MTP GGUF/sidecar only
     as a proposer at shorter context first.
   - Score only accepted verifier tokens. Draft throughput does not count if
     acceptance is low or scheduler overhead erases the win.

4. EAGLE-style trained proposer as a real project.
   - If off-the-shelf MTP cannot be made graph-safe on XPU, train or adapt a
     small same-family proposer from accepted-model traces.
   - This can preserve final quality if every token is still verified by the
     Quark model, but it is a larger effort than n-gram speculation.
   - Track acceptance rate by prompt class before investing in production
     integration.

5. Shape-exact timeline budget before more kernel work.
   - Capture a short accepted p512/n128 decode with XPU/Level Zero events and
     map each token's time into dense quant/GEMM, MoE, GDN/attention, collectives,
     sampling/logits, scheduler, and streaming.
   - The target is a budget that explains the observed `~10 ms/token`; anything
     outside the top blocks should not receive new kernel effort.

6. Router-distribution capture in the live endpoint.
   - Add an opt-in route logger for Qwen3.6 MoE top-k expert IDs, per-layer
     rows-per-expert, and prompt-class labels.
   - Feed those real distributions into grouped-GEMM and hotpack benchmarks
     instead of relying on synthetic or single-capture distributions.

7. Publish-grade accepted pack refresh.
   - Run accepted r10/r20 speed with peak VRAM, repeat64 or repeat128 quality,
     long-context needle, and a short restore/generation reliability smoke.
   - This gives a clean baseline artifact for any future Localmaxxing update
     and for upstream issue reports.

Bigger, bolder engineering ideas:

1. Full verifier-preserving speculation ladder.
   - Stage 1: n-gram correctness and no-bonus replay.
   - Stage 2: MTP sidecar with the current Quark model as verifier.
   - Stage 3: EAGLE/DFlash/custom proposer once request-id trace and repeat
     gates are reliable.
   - This remains the most plausible path to `>200 tok/s` c1 without changing
     final quality, because it can reduce verifier steps per emitted token.

2. Layer-local expert replication using spare VRAM.
   - Instead of pure TP4, replicate the hottest experts for selected layers on
     all cards while sharding colder experts.
   - The goal is to reduce cross-card communication and fragmented tiny GEMMs
     for common single-token routes.
   - Required proof: per-layer memory math, exact route parity, and endpoint
     speed; global expert remap is too blunt.

3. Hybrid TP/EP service lane.
   - Prototype a layout where attention/dense paths are replicated or sharded
     differently from experts.
   - Pure TP4 is good for fitting the model, but it may be structurally poor for
     MoE c1 decode because it pays collectives at many small boundaries.
   - This is a production-scale architecture branch, not a quick env-var screen.

4. Persistent command-list decode loop.
   - Build a c1 lane that keeps KV, block tables, route scratch, sampling
     buffers, and graph/command-list replay resident across the whole decode.
   - The service would be specialized for single-user latency and fall back to
     accepted vLLM for unsupported contexts or failed quality gates.
   - This could expose whether scheduler/dispatcher overhead is now a material
     part of the `~10 ms/token` floor.

5. Persistent fused MoE kernel with real routing.
   - Move beyond Python wrapper boundaries and implement a kernel family that
     owns route count, scratch zeroing, first GEMM, activation, second quant,
     second GEMM, weighted combine, and maybe shared-expert add for actual
     Qwen3.6 shapes.
   - The Intel Arc guidance points in this direction; our wrapper-level MoE
     experiments showed that changing the boundary alone is insufficient.

6. Tile-native W8A8 repack cache.
   - Audit whether Quark weights are consumed in the best B70/XMX tile order.
   - If not, perform a one-time exact INT8 repack at model-load time and cache
     it on disk with a checksum of the original weights and scales.
   - This must prove identical math/dequant semantics before any speed result
     matters.

7. Specialized tiny collective path or collective overlap.
   - The graph still contains many small hidden-size collectives. A graph-safe
     hidden-size-specific all-reduce path, or overlapping the collective with
     independent next-layer work, could matter more than generic oneCCL knobs.
   - Avoid unsafe in-place changes unless aliasing and repeat stability are
     proven across fresh graph captures.

8. Final projection and sampling audit.
   - Measure whether lm-head/logits/sampling is a hidden c1 cost. If it is,
     consider exact W8A8 lm-head, logits chunking with determinism proof, or
     device-side greedy sampling.
   - Prior logits/router shortcuts in other work were risky; exact token hashes
     remain the gate.

9. Same-model 8-bit engine bakeoff as a diagnostic.
   - Try OpenVINO/Optimum Intel, BigDL/IPEX-LLM, LMDeploy, and llama.cpp/SYCL
     only if they can run Qwen3.6 35B at 8-bit/high fidelity with comparable
     prompt formatting.
   - The goal is to learn whether vLLM/XPU is the bottleneck. Do not switch to
     Qwen3.5 or 4-bit to make the benchmark look good.

10. Version-matrix and host-stability branch.
    - Test oneAPI/driver/vLLM-XPU kernel versions, NUMA binding, P2P settings,
      ASPM/runtime-power policy, and thermal/fan policy in a reversible matrix.
    - This is unlikely to produce a `2x` alone, but it can reduce variance and
      device-lost noise enough to make kernel wins measurable.

11. Upstreamable B70 repro package.
    - Turn our data into minimal repros for maintainers: dense W8A8 GEMM,
      routed MoE grouped GEMM, graph-safe tiny collectives, and speculative
      metadata corruption.
    - Include exact shapes, commands, current throughput, target throughput,
      route histograms, and Localmaxxing references.
    - This increases the odds of getting help on missing XPU kernel paths
      instead of carrying a private fork forever.

12. Production dual-lane design.
    - Keep a conservative accepted TP4 lane for reliability and a fast
      experimental lane for latency.
    - Route requests by context length, quality-risk level, and service class.
      Any speculative or specialized lane must have automatic fallback to the
      accepted verifier lane and visible quality telemetry.

Priority after the current diagnostic:

1. Finish the no-bonus n-gram5 token-trace and repeat64 gate.
2. If it fixes corruption, build the replay harness and then test MTP sidecar
   speculation.
3. If it does not fix corruption, stop n-gram width sweeps and trace proposer
   state/request joins.
4. In parallel, build the token-time budget and live route histogram capture,
   because those support both local kernels and upstream repros.

## N-Gram5 No-Bonus Diagnostic Result: Still Reject

Added after launching `NUM_SPECULATIVE_TOKENS=5`, `PROMPT_LOOKUP_MIN=2`,
`PROMPT_LOOKUP_MAX=5`, and `DISABLE_FULL_ACCEPT_BONUS=1` against the current
Quark INT8 verifier.

Artifacts:

- `data/qwen36-quark-int8-tp4-ngram5-nobonus-frontdoor-token-trace-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram5-nobonus-spec-jsonl-20260611.jsonl`
- `data/qwen36-quark-int8-tp4-ngram5-nobonus-spec-summary-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram5-nobonus-spec-summary-20260611.md`

Command:

```bash
/home/steve/.venvs/vllm-xpu/bin/python scripts/qwen36-quality-token-trace.py \
  --base-url http://127.0.0.1:8000 \
  --tokenizer /mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118 \
  --baseline-json data/qwen36-quark-int8-accepted-frontdoor-token-trace-20260611.json \
  --repeat-runs 4 \
  --output-json data/qwen36-quark-int8-tp4-ngram5-nobonus-frontdoor-token-trace-20260611.json
```

Result:

- `baseline_match_all=false`.
- Short exact canaries still matched:
  - `exact_ok`: `OK`
  - `copy_phrase`: `satin cobalt orbit`
  - `arithmetic`: `60`
  - `json_schema`: `{"answer": "42", "unit": "widgets"}`
  - repeat colors: stable `blue, green, orange, red`
- The long-context needle failed:
  - accepted baseline: `B70_QWEN36_NEEDLE_20260609`
  - n-gram5 no-bonus output: `B70_QWEN36!`
- The first output-token divergence is at token index `8`:
  - accepted token: `83098`, decoded as `_NEED`
  - current token: `0`, decoded as `!`

Scheduler trace:

| Rows | Requests | Draft tokens | Accepted | Rejected | Accept rate | Full accept rows | Full reject rows | Suppressed bonus rows |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 3 | 20 | 10 | 10 | `50.00%` | 2 | 2 | 2 |

The failing long-context request had two speculative rows:

1. Full accept row:
   - scheduled draft tokens: `[12952, 54, 923, 18, 21]`
   - decoded: `_Q`, `W`, `EN`, `3`, `6`
   - verifier generated: `[12952, 54, 923, 18, 21, 83098]`
   - no-bonus hook suppressed token `83098` (`_NEED`)
2. Full reject row:
   - scheduled draft tokens: `[841, 62, 17, 15, 17]`
   - verifier generated/emitted: `[0]`, decoded as `!`

Interpretation:

- The no-bonus hook did not repair n-gram5 correctness.
- It did, however, isolate a likely scheduler/speculative state problem:
  suppressing the bonus token after a full-accept row leaves the verifier/proposer
  state misaligned for the next step. The next verifier token became `!` instead
  of `_NEED`.
- Do not run repeat64 or prompt-class speed for this candidate; it already
  fails the accepted token trace.
- Do not spend more time on wider n-gram sweeps until request-id/state replay
  can explain and reproduce the emitted-token sequence.

Next action from this result:

1. Restore the accepted TP4 backend and generation-smoke it.
2. Build the speculative correctness replay harness using this four-row trace
   as the first failing fixture.
3. Extend client token traces with request IDs and timestamps so future
   speculative failures can be joined directly without relying on manual
   request matching.

Restore status:

- Stopped diagnostic tmux session `qwen36-tp4-ngram5-nobonus-20260611h`.
- Relaunched accepted recipe in tmux session
  `qwen36-tp4-accepted-restored-after-ngram5-nobonus-20260611i`.
- Backend `/health` became ready on poll attempt 14.
- Backend direct completion smoke generated successfully.
- Frontdoor `/health` passed and frontdoor chat smoke returned exact `OK`.

## Spec Replay Harness And Request-ID Token Trace

Added after the n-gram5 no-bonus rejection. The goal is to make the next
speculative test joinable and replayable before running any more speculative
widths or proposer variants.

Artifacts:

- `scripts/replay-qwen36-spec-trace.py`
- `data/qwen36-quark-int8-tp4-ngram5-nobonus-spec-replay-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram5-nobonus-spec-replay-20260611.md`
- `data/qwen36-quark-int8-accepted-frontdoor-token-trace-requestids-r4-20260611.json`

Tooling updates:

- `scripts/qwen36-quality-token-trace.py` now records:
  - `response_id`
  - `request_id`
  - `request_started_at_unix`
  - `request_finished_at_unix`
  - selected response headers
- Repeat comparisons now use keys such as `repeat_colors[0]` instead of only
  `repeat_colors`. This fixes a real bug where a bad repeated output could be
  overwritten by a later good repeat and still report `baseline_match_all=true`.

Replay command:

```bash
/home/steve/.venvs/vllm-xpu/bin/python scripts/replay-qwen36-spec-trace.py \
  --trace-jsonl data/qwen36-quark-int8-tp4-ngram5-nobonus-spec-jsonl-20260611.jsonl \
  --tokenizer /mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118 \
  --out-json data/qwen36-quark-int8-tp4-ngram5-nobonus-spec-replay-20260611.json \
  --out-md data/qwen36-quark-int8-tp4-ngram5-nobonus-spec-replay-20260611.md
```

Replay result:

- Rows: `4`
- Requests: `3`
- Joined requests: `0` because the original n-gram5 token-trace artifact was
  produced before request IDs were recorded.
- Suppressed follow-up mismatches: `1`

Mismatch:

- Request `chatcmpl-8f59ad636cb2ec08-965c37d8`
- Trace-emitted text: `_QWEN36!`
- Trace-generated text: `_QWEN36_NEED!`
- Suppressed bonus text: `_NEED`
- Suppressed token `83098` (`_NEED`) was not replayed by the next verifier row;
  the next verifier first token was `0` (`!`).

Accepted request-id trace validation:

```bash
/home/steve/.venvs/vllm-xpu/bin/python scripts/qwen36-quality-token-trace.py \
  --base-url http://127.0.0.1:8000 \
  --tokenizer /mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118 \
  --baseline-json data/qwen36-quark-int8-accepted-frontdoor-token-trace-20260611.json \
  --repeat-runs 4 \
  --output-json data/qwen36-quark-int8-accepted-frontdoor-token-trace-requestids-r4-20260611.json
```

Result:

- `baseline_match_all=true`
- `9` cases
- comparison keys include `repeat_colors[0]`, `repeat_colors[1]`,
  `repeat_colors[2]`, and `repeat_colors[3]`
- every case has a `request_id`

Decision:

- Future speculative token traces must use this request-id-capable script.
- Future speculative replay artifacts should report zero suppressed follow-up
  mismatches before any speed result is considered.
- The old n-gram5 no-bonus fixture remains useful as the first failing replay
  test case.

## Follow-Up Ideas Added After Replay Harness

Added after the replay harness showed the n-gram5 no-bonus failure is a state
alignment issue, not a simple "bonus token bad" issue. These are the items to
keep in the next-try queue while preserving the rule that final accepted output
quality must remain owned by the current Quark W8A8 INT8 verifier.

Immediate diagnostic items:

1. Speculative scheduler state audit.
   - Add trace fields around every speculative update:
     `num_tokens`, `num_computed_tokens`, `num_tokens_with_spec`,
     `num_output_placeholders`, scheduled draft count, generated token count,
     emitted token count, and rejected-token rollback count.
   - The no-bonus hook likely proved that hiding a verifier bonus token without
     rolling back KV/compute state is invalid. Treat it as a diagnostic fixture,
     not as a candidate optimization.
   - Inspect `gpu_model_runner.py`, `rejection_sampler.py`, and proposer update
     ordering before trying another speculative width.

2. Request-id joined speculative failure packs.
   - Every future speculative run should collect both client token trace and
     scheduler JSONL trace with matching request IDs.
   - A valid candidate needs:
     - zero replay mismatches,
     - exact short canary parity,
     - repeat64 pass,
     - long-context needle pass,
     - and no unexplained accepted loops.

3. Verifier-only shadow retry for failed speculative requests.
   - When a speculative trace fails, immediately rerun the same prompt through
     accepted non-spec decode and store the token IDs under the same fixture.
   - This separates proposer/scheduler corruption from model/runtime drift or
     stale-process instability.

4. Speculative graph-shape budget.
   - Record which graph bucket served each decode step: normal decode len=1,
     n-gram2 len=3, n-gram3 len=4, and deeper proposer lengths.
   - The capture-size-3 result suggests XPU graph bucket coverage matters. Do
     not assume a speculative failure is semantic until the graph bucket is
     known.

5. Token-time budget before more kernel patches.
   - Build a per-token timing ledger that separates dense W8A8, GDN/attention,
     routed MoE, shared expert, collectives, logits/sampling, scheduler, and
     streaming.
   - The offline c1 runner already showed the OpenAI/frontdoor stack is not
     hiding a 2x win. The next timing needs to say which model-core region is
     consuming the token.

Near-term no-quality-loss experiments:

1. Quark-verifier MTP sidecar feasibility.
   - The current Quark checkpoint has no MTP tensors, but the official FP8
     snapshot does. Try it only as an auxiliary proposer; the Quark W8A8 INT8
     verifier must accept/reject final tokens.
   - First gate is memory and startup, not speed. Measure VRAM headroom at 32K
     with the accepted service, then with the sidecar loaded.

2. N-gram2 as an adaptive diagnostic, not a default.
   - Keep n-gram2/capture-size-3 available for long predictable completions,
     but disable it dynamically when early acceptance is low.
   - Do not use n-gram3+ again until the accepted-loop state bug has a minimal
     explanation.

3. Real-route grouped-GEMM tuning.
   - Capture live router histograms for natural chat, code, structured, math,
     and the synthetic p512/n512 benchmark.
   - Feed those exact expert distributions into `vllm-xpu-kernels` grouped-GEMM
     microbenches. Synthetic uniform routing is not enough.

4. Persistent MoE coverage check against current Intel XPU branches.
   - Determine whether our live Quark W8A8 path actually uses Intel's newest
     persistent MoE/fused activation work.
   - If it does not, create the smallest Qwen3.6 A3B W8A8 repro that shows the
     missing coverage before writing a large local kernel fork.

5. Exact 8-bit engine bakeoff.
   - Continue treating llama.cpp/SYCL, OpenVINO/oneDNN GenAI, IPEX/BigDL, and
     LMDeploy as diagnostics only unless they can run the same Qwen3.6 35B
     family at true 8-bit/high-fidelity quality with 32K context.
   - Reject any path that quietly becomes Qwen3.5, 4-bit, AWQ, GPTQ-4bit, or a
     prompt-template mismatch.

Bigger and bolder bets:

1. Static solo decode lane.
   - Build a one-user decode path with fixed sampling, fixed graph buckets,
     preallocated KV, and minimal scheduler/streaming surfaces.
   - This is not a quality change. It tests whether vLLM's general serving loop
     is a real single-user latency tax after the offline runner's first result.

2. Whole-token command-list capture.
   - Instead of optimizing isolated ops, try capturing a complete one-token
     decode command sequence for the accepted batch-1 shape.
   - The hypothesis is that many small graph-safe launches and collectives cost
     more than their raw kernels. A persistent command-list replay could reduce
     launch and synchronization gaps.

3. Hybrid TP/EP with expert locality simulation.
   - Model bytes and collectives for TP4, TP2, EP4, and hybrid layouts before
     touching vLLM internals.
   - Include partial expert replication and hot expert placement. If frequent
     experts cluster by prompt class, a layout-only change might reduce
     collectives without changing weights.

4. Layer-local expert replication.
   - Replicate only the hottest routed experts or shared-expert pieces when
     memory allows, leaving rare experts sharded.
   - This is a quality-preserving storage/layout change if routing IDs and
     scales remain exact. It trades VRAM for fewer cross-card operations.

5. XPU-native packed-weight fork.
   - Keep identical Quark W8A8 quantized values, but write a second on-disk
     layout optimized for Xe2 DPAS/XMX access and graph reuse.
   - First prove that the current kernel is layout-bound or doing hot-path
     transposes/repacking. Otherwise this is wasted engineering.

6. Persistent route scratch and allocator elimination.
   - Keep per-request MoE routing maps, sorted-token buffers, quant buffers,
     scale buffers, and gather buffers resident and reused across decode steps.
   - The primitive microbench showed scratch effects can matter, but endpoint
     speed did not improve yet. The next version has to remove real runtime
     allocation/copy boundaries, not just preallocate a few tensors.

7. Collective overlap instead of only collective replacement.
   - For small hidden-state all-reduces, test whether independent route
     preparation, quantization, or next-layer setup can overlap with the
     collective.
   - This may be safer than a custom all-reduce if exact oneCCL semantics stay
     intact.

8. Proposer trained for this workload.
   - If off-the-shelf MTP/EAGLE or n-gram does not reach high acceptance, train
     or distill a small same-tokenizer Qwen3.6 proposer against our natural,
     code, structured, and agentic prompts.
   - The proposer can be approximate; the verifier cannot be. Every final token
     still goes through the Quark verifier.

9. Production quality oracle service.
   - Turn the quality gates into a reusable service: deterministic canaries,
     repeat stability, long-context needles, structured validators, code/task
     checks, and BF16/current-model side-by-side probes.
   - This lets bolder backend work move faster because every candidate is
     rejected automatically when quality drifts.

10. Upstream-first B70 optimization packet.
    - Package the strongest minimal repros for Intel/vLLM:
      speculative bucket/state mismatch, W8A8 Qwen3.6 grouped-GEMM shape,
      tiny graph-safe collective shape, and persistent MoE missing coverage.
    - Include Localmaxxing result IDs, exact commands, generated graph census,
      route histograms, oneAPI/vLLM versions, and expected speed target. This
      may be faster than carrying a private fork for every missing XPU path.

Updated priority:

1. Inspect and trace the speculative scheduler/proposer state mismatch before
   any more n-gram width tests.
2. In parallel, collect live route histograms and a per-token timing budget so
   the next kernel target is evidence-based.
3. Then choose between two large efforts: verifier-preserving MTP/draft
   speculation for a possible 2x multiplier, or persistent MoE/layout work if
   timing proves MoE dominates the single-token path.
4. Keep the accepted TP4 service as the baseline and fallback until a candidate
   survives quality, replay, repeat64, long-context, and short soak gates.

## Speculative State Trace Instrumentation

Added after inspecting the local vLLM scheduler path. This is instrumentation
only; it does not promote a speculative candidate and does not change the
accepted TP4 production lane.

Patch artifact:

- `patches/vllm-qwen36-spec-state-trace-20260611.patch`

Local vLLM changes:

- Enriched the opt-in `VLLM_SPEC_DECODE_TRACE_FILE` scheduler JSONL rows.
- Moved trace emission until after rejected-token counter rollback and after
  emitted tokens are appended/stop-trimmed.
- Added per-row request-state snapshots:
  - `request_state_before_reject_adjust`
  - `request_state_after_reject_adjust`
  - `request_state_after_output_update`
- Added row fields:
  - `num_tokens_scheduled`
  - `new_token_ids_after_stop_check`
  - `stopped`
  - `status_before_stop_check`
- Each request-state snapshot includes prompt/output/token counts,
  `num_tokens_with_spec`, `num_computed_tokens`, output placeholders, current
  spec-token count, max tokens, prefill-chunk state, status, and the last 16
  emitted output tokens.

Tooling updates:

- `scripts/replay-qwen36-spec-trace.py`
  - remains backward-compatible with older traces,
  - now records compact request counter transitions in JSON,
  - and renders a Markdown "Request Counter Transitions" table when new trace
    rows contain state snapshots.
- `scripts/summarize-qwen36-spec-trace.py`
  - now reads output-token counters from either legacy top-level fields or the
    new nested state fields,
  - and tracks min/max computed/token counters from new trace rows.

Validation:

```bash
git -C /home/steve/src/vllm apply --unidiff-zero --reverse --check \
  /home/steve/llm-optimizations/patches/vllm-qwen36-spec-state-trace-20260611.patch

/home/steve/.venvs/vllm-xpu/bin/python -m py_compile \
  /home/steve/src/vllm/vllm/v1/core/sched/scheduler.py

/home/steve/.venvs/vllm-xpu/bin/python -m py_compile \
  scripts/replay-qwen36-spec-trace.py \
  scripts/summarize-qwen36-spec-trace.py

/home/steve/.venvs/vllm-xpu/bin/python scripts/replay-qwen36-spec-trace.py \
  --trace-jsonl data/qwen36-quark-int8-tp4-ngram5-nobonus-spec-jsonl-20260611.jsonl \
  --tokenizer /mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118 \
  --out-json /tmp/qwen36-replay-compat.json \
  --out-md /tmp/qwen36-replay-compat.md

/home/steve/.venvs/vllm-xpu/bin/python scripts/summarize-qwen36-spec-trace.py \
  --trace-jsonl data/qwen36-quark-int8-tp4-ngram5-nobonus-spec-jsonl-20260611.jsonl \
  --out-json /tmp/qwen36-spec-summary-compat.json \
  --out-md /tmp/qwen36-spec-summary-compat.md
```

Results:

- Patch reverse-check passed with `git apply --unidiff-zero --reverse --check`.
- Scheduler and trace tooling `py_compile` passed.
- Replay compatibility on the old no-bonus fixture still reports:
  - rows: `4`
  - requests: `3`
  - suppressed follow-up mismatch count: `1`
- Summary compatibility on the old fixture reports:
  - accept rate: `50.00%`
  - rows: `4`
  - requests: `3`
- The failed first summarizer invocation used the wrong argument name
  (`--trace current=...`) and was rerun correctly with `--trace-jsonl`; it was
  a command error, not a code failure.

Why this matters:

- The existing no-bonus fixture showed the symptom: `_NEED` was suppressed,
  then the next verifier step emitted `!`.
- The next trace can now show the state mechanics: whether
  `num_computed_tokens`, `num_tokens`, `num_tokens_with_spec`, and output
  placeholders agree before rollback, after rollback, and after output append.
- If the counters prove that a suppressed verifier bonus leaves KV/compute
  ahead of request token state, no-bonus is formally rejected as invalid and
  future effort should move to verifier-preserving MTP/draft speculation or a
  correct rollback/recompute design.

Next diagnostic run:

1. Launch a short n-gram5/no-bonus or n-gram2 trace with the new scheduler
   patch and request-id-capable client token trace.
2. Replay the trace and inspect the new counter-transition table.
3. Stop n-gram width experiments unless the state transition is coherent and
   repeat64/long-context parity pass.

## Enriched State-Trace Diagnostic Result

Ran the n-gram5/no-bonus diagnostic again with the enriched scheduler state
trace enabled.

Artifacts:

- client token trace:
  `data/qwen36-quark-int8-tp4-ngram5-nobonus-state-frontdoor-token-trace-20260611.json`
- scheduler trace:
  `data/qwen36-quark-int8-tp4-ngram5-nobonus-state-spec-jsonl-20260611.jsonl`
- replay:
  `data/qwen36-quark-int8-tp4-ngram5-nobonus-state-spec-replay-20260611.json`
  and
  `data/qwen36-quark-int8-tp4-ngram5-nobonus-state-spec-replay-20260611.md`
- summary:
  `data/qwen36-quark-int8-tp4-ngram5-nobonus-state-spec-summary-20260611.json`
  and
  `data/qwen36-quark-int8-tp4-ngram5-nobonus-state-spec-summary-20260611.md`

Result:

- Short canaries, JSON, arithmetic, and repeat-color cases matched the accepted
  request-id baseline.
- The long-context needle still diverged:
  - accepted: `B70_QWEN36_NEEDLE_20260609`
  - n-gram5/no-bonus state trace: `B70_QWEN36!`
- First output-token diff is at token index `8`:
  - current token: `0` (`!`)
  - accepted token: `83098` (`_NEED`)
- Scheduler replay still reports `1` suppressed follow-up mismatch:
  - request `chatcmpl-910ade65c5503c90-a467094e`
  - line `3 -> 4`
  - suppressed token `83098` (`_NEED`)
  - next verifier token `0` (`!`)
- Trace summary:
  - rows: `4`
  - requests: `3`
  - drafted: `20`
  - accepted: `10`
  - rejected: `10`
  - acceptance: `50.00%`
  - full-accept rows: `2`
  - full-reject rows: `2`
  - suppressed-bonus rows: `2`

Important counter transition:

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `chatcmpl-910ade65c5503c90-a467094e` | 3 | 6 | 5 | 0 | 0 | 5 | 5 |
| `chatcmpl-910ade65c5503c90-a467094e` | 4 | 5 | 0 | 5 | -5 | 1 | 1 |

Interpretation:

- The no-bonus hook is not a correct fix. It removes the emitted bonus token
  from the output stream but the verifier/proposer state still behaves as if
  the speculative step advanced differently than the accepted baseline.
- The full-reject row then rolls back computed-token state by `5`, but emits
  `!` where the accepted model should continue with `_NEED`.
- Treat n-gram5/no-bonus as formally rejected. Do not run more speculative
  width sweeps until the rollback/recompute semantics are understood.
- The client token trace does store request IDs, but the scheduler request IDs
  append an internal suffix. Future tooling should support prefix joins such as
  `chatcmpl-910ade65c5503c90` matching
  `chatcmpl-910ade65c5503c90-a467094e`.

Immediate things to try from this result:

1. Add prefix-aware request joining to the replay/summarizer tools so every
   client case maps directly to scheduler rows.
2. Build a verifier-only replay mode for the failed long-context request:
   same prompt, same generated prefix through `B70_QWEN36`, then force the next
   exact verifier step and compare token/KV counters.
3. Prototype a "recompute after suppressed bonus" diagnostic. If we suppress a
   verifier bonus token, explicitly rewind/recompute the next step rather than
   relying on existing speculative state. This is probably slower, but it
   proves whether the bug is state advancement or proposer quality.
4. Add state assertions in debug mode:
   - output length equals expected accepted visible tokens,
   - `num_tokens`, `num_computed_tokens`, and placeholders agree after every
     rollback,
   - suppressed bonus tokens cannot remain in proposer history unless they are
     visible output.
5. Stop treating n-gram depth as a speed project. From here, n-gram is a small
   correctness reproducer for XPU/vLLM speculative state, while the real speed
   project should move to verifier-preserving MTP/draft speculation or kernel
   work.

## Prefix-Aware Trace Join Tooling

Added prefix-aware request joining to the speculative replay and summary tools.
The client traces store request IDs such as `chatcmpl-910ade65c5503c90`, while
the scheduler trace appends an internal suffix such as
`chatcmpl-910ade65c5503c90-a467094e`. The tools now try exact matches first,
then one-sided prefix matches, and record the join method.

Updated files:

- `scripts/replay-qwen36-spec-trace.py`
- `scripts/summarize-qwen36-spec-trace.py`
- regenerated replay/summary artifacts for the n-gram5/no-bonus state run

Validation:

```bash
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile \
  scripts/replay-qwen36-spec-trace.py \
  scripts/summarize-qwen36-spec-trace.py

/home/steve/.venvs/vllm-xpu/bin/python scripts/replay-qwen36-spec-trace.py \
  --trace-jsonl data/qwen36-quark-int8-tp4-ngram5-nobonus-state-spec-jsonl-20260611.jsonl \
  --tokenizer /mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118 \
  --token-trace-json data/qwen36-quark-int8-tp4-ngram5-nobonus-state-frontdoor-token-trace-20260611.json \
  --out-json data/qwen36-quark-int8-tp4-ngram5-nobonus-state-spec-replay-20260611.json \
  --out-md data/qwen36-quark-int8-tp4-ngram5-nobonus-state-spec-replay-20260611.md

/home/steve/.venvs/vllm-xpu/bin/python scripts/summarize-qwen36-spec-trace.py \
  --trace-jsonl data/qwen36-quark-int8-tp4-ngram5-nobonus-state-spec-jsonl-20260611.jsonl \
  --quality-json state=data/qwen36-quark-int8-tp4-ngram5-nobonus-state-frontdoor-token-trace-20260611.json \
  --out-json data/qwen36-quark-int8-tp4-ngram5-nobonus-state-spec-summary-20260611.json \
  --out-md data/qwen36-quark-int8-tp4-ngram5-nobonus-state-spec-summary-20260611.md
```

Results:

- replay now reports `joined_requests=3` for the state diagnostic.
- the bad scheduler request is joined to `long_context_needle
  (scheduler_prefix)`.
- summary now reports:
  - exact matches: `0`
  - prefix matches: `3`
  - timestamp-window join possible: `True`
- old no-bonus fixture compatibility still reports the same `1` suppressed
  follow-up mismatch when no token-trace artifact is supplied.

This strengthens the state diagnosis: the suppressed `_NEED` -> wrong `!`
transition is definitively the long-context canary failure, not an inferred
request mapping.

## Larger Ideas Added After State-Trace Review

Fresh public signals checked during this pass:

- Localmaxxing and independent Qwen3.6 MTP reports keep pointing at MTP/draft
  speculation as the route others use for large single-user decode gains. One
  useful recurring setting is shallow MTP depth, often around `2`, because
  deeper drafts can reduce net acceptance or add too much overhead.
- `vllm-xpu-kernels` release notes and Intel XPU grouped-GEMM tuning issues
  point at MoE GEMM policy updates, mixed prefill/decode attention tuning, and
  real routing distribution as active Intel XPU performance levers.
- Public B70 reports show high aggregate throughput can coexist with weak
  single-stream throughput. That supports keeping single-request decode as the
  primary metric while separately tracking production aggregate capacity.

New bolder bets to track:

1. Shallow MTP first, not maximum-depth MTP.
   - Start with `num_speculative_tokens=2` if an official FP8 MTP sidecar can
     be loaded beside the Quark verifier.
   - Measure acceptance, verifier overhead, and memory before chasing deeper
     drafts.
   - Quality rule stays strict: final accepted tokens must come from the Quark
     W8A8 verifier.

2. Verification-bucket optimization.
   - Speculative decode only helps if verifying multiple proposed tokens is
     faster than verifying them one at a time.
   - Build exact graph buckets for verifier lengths `2`, `3`, `4`, `5`, `6`,
     and `8`, then measure verifier-only cost with known-good proposed tokens.
   - This separates "proposer is bad" from "multi-token verifier graph is too
     slow on XPU".

3. Prefix-safe speculative scheduler test harness.
   - Create a tiny scheduler-level fixture that replays the `_QWEN36_NEEDLE`
     sequence and asserts token counters after full accept, full reject,
     partial reject, bonus emission, and suppressed bonus.
   - This should run without the full server so scheduler bugs can be fixed
     quickly and safely.

4. Same-tokenizer trained proposer.
   - If official MTP cannot fit or cannot integrate cleanly, train/distill a
     small Qwen3.6-family proposer on accepted Quark traces for natural chat,
     code, structured, and agentic prompts.
   - The proposer can be approximate; the verifier must be exact.
   - This is a bigger project, but it is still quality-preserving if every
     final token is verified.

5. Real-router histogram capture before any more MoE tuning.
   - Add live capture for per-layer top-k expert IDs and rows per expert during
     accepted p512/n512 decode and prompt-class runs.
   - Feed those histograms into grouped-GEMM microbenches.
   - Tune for the actual long-tail expert distribution, not uniform synthetic
     rows.

6. Persistent MoE branch against current `vllm-xpu-kernels`.
   - Pull or compare the current Intel/vLLM XPU kernel branch that mentions MoE
     GEMM policy updates.
   - Confirm whether our Quark W8A8 path is using the newest persistent MoE or
     fused activation path.
   - If not, create a minimal Qwen3.6 A3B W8A8 repro before writing a local
     persistent kernel from scratch.

7. Memory-for-latency lane.
   - The accepted service reports substantial KV capacity. For a solo latency
     lane, spend some of that headroom on replicated hot experts, packed
     weights, larger graph buckets, or a small sidecar drafter.
   - Keep the normal 32K production lane intact; this is a separate service
     class for single-user speed.

8. Layer-level roofline and timeline budget.
   - Build a one-token, one-layer harness with captured tensors and route maps.
   - Produce a per-layer time budget: attention/GDN, dense W8A8 GEMM, MoE
     routing, grouped GEMM, shared expert, collectives, sampler/lm-head.
   - Use oneprof/Level Zero counters where possible. The goal is to stop
     guessing which subpath owns the 10 ms/token wall.

9. Whole-token command-list experiment.
   - Capture and replay the entire accepted one-token decode sequence for a
     fixed batch-1 shape, including collectives where graph-safe.
   - If launch/synchronization gaps dominate, this may beat individual kernel
     micro-optimizations without changing math.

10. Exact 8-bit engine shootout with a hard reject filter.
    - Compare vLLM Quark W8A8 with llama.cpp/SYCL Q8_0, OpenVINO/oneDNN GenAI
      8-bit, and any current Intel-native Qwen3.6 35B 8-bit route.
    - Reject immediately if the path becomes 4-bit, Qwen3.5, wrong chat
      template, reduced context, or a quality-mismatched quantization.
    - Use this to decide whether vLLM/XPU is the ceiling or just the current
      best production route.

11. Upstream issue packet with repros, not just notes.
    - Package three public repros:
      - n-gram/no-bonus state mismatch and prefix-join trace,
      - exact graph bucket needed for speculative verifier length `3`,
      - Qwen3.6 W8A8 routed grouped-GEMM shape with real route histograms.
    - Include Localmaxxing public result ID, exact commands, kernel versions,
      and expected target. This is likely to get better Intel/vLLM help than a
      broad "B70 is slow" issue.

12. Reliability and aging as first-class metrics.
    - Every speed candidate should report:
      - cold quality,
      - repeat64,
      - long-context needle,
      - c1 r8/r10 speed,
      - c4/c8 smoke,
      - one short process-aging loop.
    - The stale-process quality failure and device-lost incidents mean runtime
      age is not a secondary detail for production.

Revised priority after this diagnostic:

1. Fix trace joining and scheduler-state proof first.
2. In parallel, start real-router histogram capture and a layer-level time
   budget.
3. Next high-upside branch is shallow MTP/draft speculation with Quark verifier.
4. Next durable backend branch is persistent MoE/grouped-GEMM work using real
   route distributions.
5. Keep Localmaxxing updates for quality-gated accepted results only.

## Route-Hotpack Overlap Addendum And Bigger Bets

Added after the prefix-aware speculation trace join was fixed. This pass used
the existing prompt-class route-capture artifacts, so it did not restart or
disturb the accepted TP4 service.

New artifacts:

- `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-hotpack-overlap.json`
- `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-hotpack-overlap.md`

Command:

```bash
python3 scripts/analyze-qwen36-route-overlap-hotpack.py \
  --input code=data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-code.jsonl \
  --input structured=data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-structured.jsonl \
  --input math=data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-math-reasoning.jsonl \
  --input repetitive=data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-repetitive.jsonl \
  --input long-natural=data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-long-natural.jsonl \
  --topn 16 \
  --hotpack-k 8 \
  --hotpack-k 16 \
  --hotpack-k 32 \
  --hotpack-k 64 \
  --max-buckets 4 \
  --max-num-tokens 1 \
  --out-json data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-hotpack-overlap.json \
  --out-md data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-hotpack-overlap.md \
  --limit 10
```

Scope notes:

- `natural-chat` was excluded from this addendum because the prior split route
  file is empty. Recapture a balanced natural-chat prompt before making any
  production routing decision from these buckets.
- The analysis uses decode-stage records with `max_num_tokens <= 1`, matching
  the single-request latency shape we care about most.

Top layers:

| Layer | Global K16 | Label K16 | Label K32 | Label K64 | Read |
| ---: | ---: | ---: | ---: | ---: | --- |
| 8 | 0.4010 | 0.4894 | 0.6808 | 0.8904 | route buckets help; K16 is not enough |
| 9 | 0.4135 | 0.5019 | 0.6875 | 0.8837 | route buckets help; K16 is not enough |
| 21 | 0.4212 | 0.5019 | 0.6904 | 0.8952 | route buckets help; K16 is not enough |
| 20 | 0.4385 | 0.5106 | 0.7173 | 0.9038 | best sampled K64 coverage |
| 14 | 0.4231 | 0.5010 | 0.7019 | 0.8933 | strongest top-16 overlap |

Read:

- A single static global K16 hotpack is too blunt. It only covers about
  `40-44%` of weighted routed assignments in the most interesting layers.
- Prompt/label K16 lifts coverage to about `49-51%`, but that still leaves
  roughly half of routed work outside the hotpack.
- K32/K64 route buckets are more credible, reaching about `68-72%` and
  `88-90%` coverage respectively, but they trade memory for latency and need
  explicit VRAM math before endpoint work.
- Existing route-exact microbenchmarks say active-expert compaction alone is
  not enough at single-token rows; wider route windows are where hotpacking
  started to show real gains.
- Treat route buckets as scheduling, placement, and kernel-selection signal.
  Do not change routing decisions or expert math.

Immediate things to try from this route pass:

1. Balanced route recapture.
   - Rerun prompt-class route capture with a non-empty `natural-chat` split and
     equalize sample counts so `math` and `repetitive` do not dominate every
     weighted summary.
   - Keep the current artifacts as useful candidate-generation data, not final
     production policy.

2. K32/K64 memory-for-latency math.
   - Compute per-layer VRAM cost to duplicate or repack K32/K64 hot experts for
     layers 8, 9, 14, 20, and 21.
   - Include 32K KV headroom, graph cache, and a potential shallow sidecar
     drafter before deciding whether the memory trade is acceptable.

3. Route-window persistent MoE harness.
   - Use captured route windows with rows/window >= 16, where earlier primitive
     scans showed the strongest hotpack improvement.
   - Start with layers 14 and 21, then expand only if layer-local parity and
     event timing are clean.

4. Prompt-class route scheduler, not prompt-class math.
   - Use early decode route histograms to choose graph buckets, packed expert
     layouts, and scratch buffers.
   - Never alter top-k routing, weights, logits, or accepted tokens.

5. Verifier-bucket speculation in parallel.
   - Build multi-token verifier graph buckets for lengths 2, 3, 4, 5, 6, and 8.
   - This answers whether shallow MTP/draft speculation can pay on XPU before
     spending time on a large proposer integration.

6. Layer-level timeline budget.
   - Produce a one-token accepted decode trace that sums to the observed
     `~10 ms/token`: attention/GDN, dense W8A8, routed MoE, shared expert,
     collectives, lm-head/sampling, scheduler, and streaming.
   - Future kernel work should target only blocks that are visible in this
     budget.

7. Upstreamable route repro.
   - Package a minimal Qwen3.6 A3B W8A8 routed grouped-GEMM repro with the
     route histograms above, exact tensor shapes, current timing, and target
     timing.
   - Target `vllm-xpu-kernels` and Intel grouped-GEMM maintainers rather than
     hiding all work in a private server patch.

External signals checked for bigger ideas:

- `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`
  - vLLM/Intel explicitly point at persistent zero-gap MoE kernels and dynamic
    work balancing for Arc Pro B-series. This matches our result: static
    hotpacks and Python boundaries are too weak.
- `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`
  - Intel's grouped-GEMM tuning thread calls out decode-stage routing skew and
    tile configuration as first-order MoE performance factors.
- `https://github.com/vllm-project/vllm-xpu-kernels`
  - The XPU custom kernel home is the right target for durable W8A8/MoE work,
    not old IPEX-only paths.
- `https://docs.vllm.ai/en/stable/design/fused_moe_modular_kernel/`
  - vLLM's modular fused-MoE design is a useful reference for breaking the
    route/count/permute/GEMM/finalize problem into swappable components.
- `https://github.com/PMZFX/intel-arc-pro-b70-benchmarks`
  - Public B70 data reinforces the pattern: aggregate and prompt processing can
    look good while single-stream generation remains the hard problem.
- `https://localmaxxing.com/en/hardware/DISCRETE_GPU%3Aintel%20arc%20pro%20b70?name=Intel+Arc+Pro+B70`
  - Keep using public rows as comparison points, but only submit our own
    quality-gated accepted results.

Bigger, bolder ideas added from this pass:

1. Route-conditioned persistent MoE, not global hotpacking.
   - Generate a small set of per-layer route families from real histograms.
   - For each family, use persistent work assignment, touched-expert scratch,
     W8A8 activation quant, grouped GEMM1, activation, grouped GEMM2, and
     finalize in one resident path.
   - This is the most direct non-speculative backend path to a real jump.

2. Memory-for-latency solo lane.
   - Keep the production 32K TP4 lane conservative.
   - Add a solo speed lane that spends available headroom on K64 hot experts,
     tile-native packed weights, larger verifier buckets, or an MTP sidecar.
   - It must fall back to the accepted verifier lane when context, memory, or
     quality gates are not satisfied.

3. TP/EP layout simulator before code.
   - Build a byte/collective model for TP4, TP2+replicas, expert parallel,
     hybrid TP/EP, and layer-local expert replication.
   - Include route histograms from the hotpack artifacts.
   - Only prototype layouts whose simulated communication reduction is large
     enough to plausibly beat the current `~100 tok/s` c1 ceiling.

4. Whole-token command-list decode.
   - Try capturing or replaying the whole batch-1 decode step, not just one
     kernel, for fixed graph buckets.
   - If synchronization gaps dominate, this could beat isolated micro-kernel
     tuning while preserving exact math.

5. Speculation as an architectural lane, not an n-gram sweep.
   - Use the prefix-joined failure fixture to repair scheduler correctness.
   - Then test shallow MTP or a sidecar proposer with Quark W8A8 as the final
     verifier. Start at depth 2.
   - Promote only if final token traces match accepted output across repeat,
     structured, code, math, and long-context gates.

6. Exact 8-bit engine bakeoff as a ceiling detector.
   - Compare current vLLM Quark W8A8 against llama.cpp/SYCL Q8_0, OpenVINO or
     oneDNN GenAI 8-bit, BigDL/IPEX, and any current Intel-native W8A8 route.
   - This is not permission to use Qwen3.5, AWQ, GPTQ-4bit, or a prompt
     mismatch. It is a diagnostic for whether vLLM/XPU is the ceiling.

7. B70 roofline packet.
   - Pair route histograms with oneprof/Level Zero counters, XMX occupancy,
     memory bandwidth, and oneCCL timing for a single accepted decode window.
   - This should tell us whether to spend engineering on MoE compute,
     collectives, scheduler gaps, or memory layout.

8. Production reliability as a promotion gate.
   - Every bold candidate needs cold quality, repeat64, long-context needle,
     c1 speed, c4/c8 smoke, short process-aging, and post-restore generation
     smoke.
   - Recent stale-process and device-lost findings make this part of
     performance work, not a final cleanup task.

## No-Bonus Accounting Diagnostic And Bigger Follow-Ups

Added after the strict no-bonus speculative diagnostic was corrected and rerun.
This still does not promote n-gram5/no-bonus; it turns the old failure into a
cleaner repro and points the next work away from blind width sweeps.

New or updated artifacts:

- `scripts/check-qwen36-spec-no-bonus-state.py`
- `scripts/replay-qwen36-spec-trace.py`
- `patches/vllm-qwen36-spec-no-bonus-accounting-20260611.patch`
- `data/qwen36-quark-int8-tp4-ngram5-nobonus-accounting-frontdoor-token-trace-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram5-nobonus-accounting-spec-jsonl-20260611.jsonl`
- `data/qwen36-quark-int8-tp4-ngram5-nobonus-accounting-spec-replay-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram5-nobonus-accounting-spec-replay-20260611.md`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-nobonus-accounting-text-smoke-20260611.json`

What changed:

- The opt-in no-bonus diagnostic now accounts for a suppressed full-accept
  target bonus token as uncommitted work. It rolls back one computed token and
  one async output placeholder, matching the visible output stream instead of
  silently advancing request state past the hidden token.
- `scripts/check-qwen36-spec-no-bonus-state.py` is a focused CPU scheduler
  fixture for that exact accounting behavior. It asserts that a suppressed
  bonus token is not emitted and that `num_computed_tokens` stays one token
  behind `num_tokens`, ready to replay the suppressed position.
- `scripts/replay-qwen36-spec-trace.py` now reports accounting mismatches in
  addition to suppressed-follow-up mismatches.

Validation:

```bash
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile \
  scripts/replay-qwen36-spec-trace.py \
  scripts/check-qwen36-spec-no-bonus-state.py

/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/check-qwen36-spec-no-bonus-state.py
```

The regression fixture passed with:

```json
{"passed": true, "num_computed_tokens": 13, "num_tokens": 14, "output_tokens": [101, 201, 202, 203, 204, 205], "suppressed_bonus": 999}
```

Replay reads:

- Old no-bonus state fixture: `accounting_mismatch_count=2`. This proves the
  previous diagnostic was internally inconsistent: it hid a bonus token but
  still counted that position as committed.
- New live no-bonus/accounting trace: `accounting_mismatch_count=0`, so the
  accounting bug is fixed.
- New live no-bonus/accounting trace still has
  `suppressed_followup_mismatch_count=1`, and the frontdoor token trace still
  fails the long-context needle.

Current rejection:

- Accepted baseline: `B70_QWEN36_NEEDLE_20260609`
- Patched n-gram5/no-bonus/accounting diagnostic:
  `B70_QWEN36_NEEDLE_2020609`
- First token divergence is in the date body: the diagnostic emits token `15`
  where baseline emitted token `21`.
- Replay shows the remaining mismatch as suppressed token `21` followed by
  verifier token `15`.

Decision:

- Reject n-gram5/no-bonus again.
- Stop treating the failure as the old computed-token accounting bug.
- Stop doing n-gram width sweeps until we can either reproduce and fix the
  verifier/proposer state path or replace n-gram with a verifier-preserving
  MTP/draft lane.
- The accepted TP4 recipe was restored in tmux session
  `qwen36-tp4-accepted-restored-after-nobonus-accounting-20260611m`; backend
  `/health`, frontdoor `/health`, and the frontdoor text quality canary passed
  with `pass_all=true`.

Things to try next from this result:

1. Verifier-only recompute probe.
   - On a row that suppresses a bonus token, immediately run a verifier-only
     one-token continuation from the visible token prefix and compare it with
     the next scheduler token.
   - If verifier-only returns the suppressed token but the speculative path
     does not, the bug is in scheduler/proposer state, not model math.

2. Minimal failing scheduler fixture from the real trace.
   - Reduce the `long_context_needle` trace to the few rows around token `21`.
   - Unit-test request counters, placeholder count, spec token list, and
     proposer update order without needing four B70s or a full model launch.

3. Verifier-bucket timing before MTP integration.
   - Build graph buckets for verifier lengths `2,3,4,5,6,8`.
   - Measure whether multi-token verification is fast enough on XPU to make a
     shallow proposer worthwhile. If verifier length `3` is already slow, MTP
     integration will not reach `>200 tok/s` without deeper kernel work.

4. Shallow MTP sidecar with Quark verifier.
   - Do not switch production quality to the official FP8 or a GGUF MTP model.
   - Use an auxiliary Qwen3.6 MTP/draft source only to propose tokens; the
     current Quark W8A8 INT8 model remains the final verifier.
   - Start at depth `2` and require exact token-trace parity before measuring
     speed.

5. Exact draft-model lane for repetitive/locality-heavy prompts only.
   - Keep n-gram2 as a diagnostic/request-class lane, not a global production
     path.
   - It may still be useful for route/acceptance instrumentation or a guarded
     assistant-mode fast lane if repeat64 and long-context gates remain clean.

6. Speculation kill switch with automatic fallback.
   - A production prototype should be able to disable speculation per request
     after any replay mismatch, repeat instability, long-context divergence, or
     process-aging failure.
   - The accepted no-prefix verifier lane remains the baseline service.

New bigger, bolder ideas to track:

1. Dual-lane production architecture.
   - Conservative lane: current accepted TP4 Quark W8A8 verifier, 32K context,
     strict stability.
   - Speed lane: same verifier plus shallow proposer/MTP, route buckets, and
     larger preallocated graph buckets.
   - Router promotes requests to the speed lane only after prompt/context and
     health checks, and falls back without changing user-visible output.

2. Token-level flight recorder.
   - For every candidate, store request id, emitted token ids, scheduler state
     transitions, route histograms, graph bucket, and first-token timing.
   - This turns intermittent corruption into searchable fixtures instead of
     one-off logs.

3. One-token roofline snapshot.
   - Capture one accepted decode token with oneprof/Level Zero counters and
     classify time into dense W8A8, routed MoE, shared expert, attention/GDN,
     collectives, logits/sampling, scheduler, and streaming.
   - This is the fastest way to decide whether the next month belongs to MoE
     kernels, speculation, collectives, or server overhead.

4. XPU persistent-MoE branch with real route windows.
   - Use route windows from actual prompts, not synthetic even routing.
   - Prototype a persistent route/count/permute/W8A8 GEMM/finalize path for
     layers 14 and 21 first.
   - Only wire into vLLM after standalone parity and event timing prove a real
     margin.

5. Memory-for-latency mode.
   - Explicitly budget spare VRAM for K64 hot experts, packed tile-native
     weights, larger verifier buckets, or a small sidecar proposer.
   - This should be a separate service profile, because production aggregate
     capacity and maximum 32K concurrency may prefer a different memory split.

6. Whole decode command-list replay.
   - Capture/replay the complete batch-1 decode step for stable graph buckets.
   - If the model is launch/synchronization bound, this could beat isolated
     kernel polishing while preserving the exact accepted math.

7. Same-model 8-bit engine bakeoff with quality oracle.
   - Compare current vLLM/XPU against llama.cpp/SYCL Q8_0, OpenVINO/oneDNN
     GenAI 8-bit, BigDL/IPEX, and any Intel-native W8A8 path that appears.
   - The bakeoff is only useful if it uses Qwen3.6 35B, 8-bit/high-fidelity
     weights, the same prompt template, and the same token-level quality oracle.

8. Upstreamable B70 speculative/MoE repro pack.
   - Package the no-bonus accounting fixture, the remaining suppressed-token
     mismatch, a verifier-bucket timing repro, and a real-route grouped-GEMM
     repro for `vllm-xpu-kernels`.
   - A concise upstream packet is more likely to attract Intel/vLLM help than
     a broad performance complaint.

Revised priority:

1. Keep the accepted TP4 service as the only promoted lane.
2. Build the verifier-only recompute probe and real-trace scheduler fixture.
3. In parallel, collect one-token roofline data and route windows.
4. Choose the next large branch from evidence:
   - shallow MTP/draft if verifier buckets are cheap and state is repairable;
   - persistent MoE/layout if decode time is MoE/collective dominated;
   - same-model engine bakeoff if vLLM/XPU overhead looks structural.

## Verifier Follow-Up Probe, Standard N-Gram5 Rejection, And Larger Bets

Added after the no-bonus accounting run. This closes the loop on whether the
remaining no-bonus failure is model/verifier disagreement or hidden speculative
state.

New artifacts:

- `scripts/probe-qwen36-verifier-followup.py`
- `data/qwen36-quark-int8-tp4-ngram5-nobonus-accounting-verifier-followup-probe-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram5-standard-device-lost-20260611.json`

Verifier follow-up result:

- Input replay: `data/qwen36-quark-int8-tp4-ngram5-nobonus-accounting-spec-replay-20260611.json`
- Failing case: `long_context_needle`
- Visible emitted prefix before the mismatch: `B70_QWEN36_NEEDLE_202`
- Suppressed full-accept bonus token: token id `21`, text `6`
- Next speculative/verifier token after suppression: token id `15`, text `0`
- `/generative_scoring` prompt length: `7643` tokens
- Score for suppressed `6` over `{6, 0}`: `0.9999974387187055`
- Score for wrong `0` over `{0, 6}`: `0.00000226032348933062`

Conclusion:

- The accepted Quark verifier strongly prefers the suppressed token when asked
  from the visible output prefix.
- The n-gram5/no-bonus/accounting failure is not verifier model math.
- Scheduler counter accounting was fixed, but suppressing a verified full-accept
  bonus token still leaves some hidden KV/proposer/scheduler state ahead of the
  visible stream.
- Counter rollback alone is insufficient. A real fix needs KV/proposer rewind,
  or we should stop suppressing verifier-approved bonus tokens.

Standard n-gram5 with the verifier bonus intact:

- Launch path: `scripts/launch-qwen36-quark-int8-ngram-trace.sh`
- Settings: `num_speculative_tokens=5`, `prompt_lookup_min=2`,
  `prompt_lookup_max=5`, `DISABLE_FULL_ACCEPT_BONUS=0`
- Capture sizes: `1,2,3,4,5,6,8,16,24,32,40,48,56,64,80,96,112,128`
- Backend health reached and graph capture completed.
- First frontdoor quality request failed with HTTP 500 and killed the backend.
- Fatal error: `UR_RESULT_ERROR_DEVICE_LOST`
- Stack location: `block_table.copy_to_gpu` from
  `gpu_model_runner._prepare_inputs`.
- Scheduler context: first request, `prompt_token_ids_len=17`,
  `num_scheduled_tokens=17`, `scheduled_spec_decode_tokens={}`,
  `step_counter=0`.
- No speculative trace rows were produced because the crash happened during the
  first prefill request.

Decision:

- Reject standard n-gram5 under the current graph/spec setup.
- Do not claim quality or speed from this run.
- If revisited, test a smaller graph bucket set, eager/no-graph, or a direct
  block-table prefill repro only as a stability diagnostic.
- The accepted TP4 service was restored in tmux session
  `qwen36-tp4-accepted-restored-after-ngram5-standard-dl-20260611o`.
  Backend `/health`, frontdoor `/health`, and the frontdoor text quality smoke
  passed with `pass_all=true`, `baseline_match_all=true`, `repeat_pass=true`,
  and `long_context_pass=true`.
- Restore artifact:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-ngram5-standard-dl-text-smoke-20260611.json`

External signals checked for bigger ideas:

- vLLM's Intel Arc Pro B-series post lists n-gram, EAGLE, EAGLE3, async
  scheduling, prefill/decode disaggregation, and persistent MoE as supported or
  relevant B-series directions:
  https://vllm.ai/blog/2025-11-11-intel-arc-pro-b
- Public B70/Qwen notes continue to point at SYCL and MoE models as the more
  promising local path than Vulkan or dense-only models:
  https://github.com/PMZFX/intel-arc-pro-b70-benchmarks
- A recent W8A8 Qwen3.6-35B-A3B issue in `llm-compressor` shows exact
  high-fidelity INT8 support remains an active upstream concern:
  https://github.com/vllm-project/llm-compressor/issues/2787
- A recent XPU/B70 vLLM issue involving resets/device faults is consistent with
  treating device-loss failures as first-class stability blockers, not just
  benchmark noise:
  https://github.com/vllm-project/vllm/issues/41663

New things to try next:

1. Bonus-intact n-gram5 stability isolate.
   - Keep the verifier bonus intact.
   - Reproduce the first-prefill device loss with a minimal block-table copy
     test, then with smaller capture buckets.
   - If it only fails under graph capture, the candidate is a graph/runtime
     stability issue rather than an n-gram correctness issue.

2. KV/proposer rewind proof.
   - Build a minimal trace fixture that suppresses a full-accept bonus token,
     then explicitly rewinds or invalidates the proposer/KV state.
   - The pass condition is strict: the next visible token must be the suppressed
     token, and token traces must match accepted output.

3. Verifier-bucket timing before any MTP/EAGLE integration.
   - Measure verifier lengths `2,3,4,5,6,8` through graph buckets.
   - If those buckets are expensive or unstable, model-based speculation will
     not reach the `>200 tok/s` single-request target on this stack.

4. EAGLE/EAGLE3 or trained same-tokenizer draft behind Quark verifier.
   - Use the current Quark W8A8 model as the final verifier.
   - A draft/MTP/EAGLE model may propose, but it must not define final output.
   - Start at depth `2`; require exact token-trace parity across deterministic,
     repeat, structured, code, math, and long-context gates before timing.

5. Static solo decode lane.
   - Build a special c1 latency path with preallocated KV/block tables,
     fixed graph buckets, no prefix cache, and minimal scheduler churn.
   - This is more intrusive than tuning vLLM flags, but it attacks the evidence
     that offline/HTTP overhead is not the 2x bottleneck while block-table and
     graph/runtime boundaries still matter.

6. Whole-token command-list replay.
   - Capture the full batch-1 decode step, including dense W8A8, MoE,
     attention/GDN, collectives, logits, and sampling.
   - If Level Zero launch/sync gaps dominate, whole-step replay could beat
     isolated micro-kernel patches without changing math.

7. Memory-for-latency profile.
   - Spend spare B70 VRAM deliberately: K32/K64 hot expert replicas, tile-native
     repacked W8A8 weights, larger verifier buckets, persistent scratch, or a
     sidecar proposer.
   - Keep this separate from the production max-concurrency profile; memory
     spent on c1 latency may reduce 32K c48 capacity.

8. Persistent route-window MoE.
   - Use real route windows from prompt-class captures.
   - Start with layers 14 and 21, where prior route/hotpack screens were most
     informative.
   - Target route/count/permute/activation/GEMM/finalize as one persistent
     path, not a collection of small wrapper changes.

9. Expert-locality TP/EP simulation.
   - Use route histograms to simulate TP4, TP2+replicas, EP, and hybrid layouts.
   - Prototype only if the communication and duplicated-weight math predicts a
     large single-request win.

10. Fused logits/argmax path.
    - For greedy temperature-0 canaries, investigate whether the final
      projection plus argmax can avoid materializing full logits.
    - This is quality-sensitive: promotion requires exact token parity, not
      approximate top-k agreement.

11. Same-model 8-bit engine bakeoff.
    - Compare vLLM/XPU against llama.cpp/SYCL Q8_0, OpenVINO/oneDNN GenAI
      8-bit, BigDL/IPEX, and any current Intel-native W8A8 path.
    - Constraints are strict: Qwen3.6 35B, high-fidelity 8-bit, same chat
      template, no Qwen3.5, no 4-bit, and token-level quality oracle.

12. Upstreamable B70 repro packet.
    - Package the no-bonus accounting fixture, verifier-followup proof,
      standard n-gram5 device-loss log, route-window grouped-GEMM timing, and
      Localmaxxing accepted result.
    - A precise Intel/vLLM repro packet is more likely to produce backend help
      than another local flag sweep.

Revised large-opportunity order:

1. Restore and preserve the accepted TP4 service after every experiment.
2. Finish the verifier/proposer state isolate.
3. In parallel, collect one-token roofline and verifier-bucket timing.
4. Choose one high-upside branch:
   - EAGLE/MTP/draft if verifier buckets are cheap and state is fixable;
   - persistent MoE/layout if route-window timing dominates;
   - static solo decode/command-list replay if scheduler/graph sync dominates;
   - engine bakeoff if vLLM/XPU overhead looks structural.

## Generative-Scoring Bucket Proxy And Branch Decision

Added after the verifier-followup probe. The goal was to get low-risk timing
evidence for "verifier bucket" shape sensitivity without disturbing the
accepted TP4 service.

New artifacts:

- `scripts/probe-qwen36-generative-scoring-buckets.py`
- `data/qwen36-quark-int8-tp4-generative-scoring-buckets-p512-20260611.json`
- `data/qwen36-quark-int8-tp4-generative-scoring-buckets-p8192-20260611.json`
- `data/qwen36-quark-int8-tp4-current-speed-sanity-p512o256-r2-20260611.json`

Important caveat:

- `/generative_scoring` is not a true speculative decode verifier benchmark.
- It builds fresh `query + item` prompts and scores next-token labels.
- That means it exercises prefill-style prompt+item work, not a KV-resident
  decode step with existing cache.
- Use this only as a stability/shape proxy. Do not use it to claim MTP/EAGLE
  speed viability.

p512 proxy result:

- Query length: `512` tokens.
- Item lengths: `0,1,2,3,4,5,6,8,12,16`.
- Measured latency stayed flat around `75-80 ms`.
- Item length did not produce a clear monotonic cost signal at this prompt
  length; noise and graph/prefill behavior dominate.

p8192 proxy result:

| Item tokens | Mean elapsed ms | Delta vs item0 |
| ---: | ---: | ---: |
| 0 | `726.72` | `0.00` |
| 1 | `738.65` | `+11.94` |
| 2 | `752.52` | `+25.81` |
| 4 | `755.35` | `+28.64` |
| 8 | `757.40` | `+30.68` |
| 16 | `755.56` | `+28.84` |

Interpretation:

- The proxy is stable and usage accounting matches `prompt_tokens + item_tokens`.
- Small candidate items are cheap relative to the full 8K prefill, but the
  first couple of extra tokens still add visible latency in this API path.
- The result does not answer the real question: whether a KV-resident verifier
  bucket of length `2-8` can run cheaply enough during decode.
- A lower-level harness must measure vLLM's actual decode-time scheduled token
  counts with existing KV state.

Current speed sanity after the proxy:

- Direct backend p512/o256, natural-chat preset, r2.
- Corrected after-first output throughput: `99.31 tok/s` mean.
- End-to-end output throughput: `96.46 tok/s` mean.
- Client TTFT: `86.34 ms` mean.
- vLLM TTFT metric: `74.98 ms` mean.
- This confirms the accepted service did not regress during the proxy run.
- Backend `/health`, frontdoor `/health`, and a post-proxy frontdoor text smoke
  also passed with `pass_all=true`, `baseline_match_all=true`,
  `repeat_pass=true`, and `long_context_pass=true`.
- Smoke artifact:
  `data/qwen36-quark-int8-tp4-post-scoring-bucket-text-smoke-20260611.json`

Branch decision from current evidence:

1. Do not spend more time on HTTP `/generative_scoring` as a speed predictor.
   - It is useful for correctness probes like "which next token does the
     accepted verifier prefer?"
   - It is not useful enough for decode-bucket timing because it recomputes the
     prompt.

2. Build a real KV-resident verifier-bucket harness next.
   - Target scheduled decode token counts `1,2,3,4,5,6,8`.
   - Measure model-forward time, graph bucket use, and stability with existing
     KV state.
   - This can be a vLLM runner diagnostic, an offline `LLM` runner patch, or a
     minimal engine-core fixture; it should not route through HTTP scoring.

3. Keep persistent MoE/route-window work as the durable backend branch.
   - Existing graph step timing still says visible `model_forward` dominates:
     about `12.36 ms/token` under synchronized graph-path timing.
   - Visible non-forward regions are too small for a 2x win: logits about
     `0.77 ms`, sampler about `0.16 ms`, and bookkeeping about `0.06 ms`.
   - Eager diagnostic timing exposes MoE as the largest internal component when
     graph replay is disabled: `moe_forward_shared.custom_op` about `48.10 ms`
     of `113.61 ms` eager forward.

4. Keep the static solo decode lane as the third branch.
   - It is justified only if the real KV verifier-bucket or future command-list
     timing shows scheduler/block-table/graph-sync overhead large enough to
     beat kernel work.

Immediate next implementation target:

1. Add a decode-bucket diagnostic inside vLLM that records actual scheduled
   decode token count, whether the graph bucket was used, and rank-0
   `model_forward` timing for bucket sizes `1,2,3,4,5,6,8`.
2. Run it first on the accepted lane without speculation if possible, then on a
   shallow bonus-intact speculative lane only after the first-prefill device-loss
   isolate is understood.
3. Promote nothing until token traces match the accepted baseline and the
   endpoint survives repeat/long-context reliability gates.

## Bigger-Bet Backlog Refresh After Localmaxxing/External Scan

Added after saving fresh public leaderboard snapshots and reviewing current
upstream signals for XPU, Intel Arc, speculative decode, and GPU INT8/MoE
primitives.

New artifacts:

- `data/localmaxxing-b70-qwen-leaderboard-ideas-refresh-20260611.json`
- `data/localmaxxing-arc-qwen-leaderboard-ideas-refresh-20260611.json`

External/API signals checked:

- Localmaxxing exact B70/Qwen query has the current Quark W8A8 INT8 TP4 result
  as the top B70 Qwen row at `99.77 tok/s`, ahead of the earlier
  quality-gated `99.43 tok/s` row and public B70 llama.cpp Q4 rows around
  `68-70 tok/s`.
- The broader Localmaxxing Qwen query shows the strongest Qwen3.6 35B-A3B
  rows using DFlash-style speculative decoding on another platform at about
  `102 tok/s`, with notes claiming a large gain over its autoregressive
  baseline. Treat the hardware as not comparable, but the direction is useful:
  large single-user gains are coming from verifier-preserving speculation, not
  ordinary server flags.
- vLLM release notes show active Intel XPU work around block FP8, MoE fallback,
  reduced XPU MoE host overhead, GPTQ int4, and speculative/MTP directions.
  This makes a latest-XPU-branch comparison worth tracking, but only behind the
  current quality and stability gates.
- IPEX-LLM continues to advertise Intel GPU, Arc/B-series, vLLM, llama.cpp,
  Ollama, FP8/FP6/FP4/INT4, and FlashMoE paths. It is not a direct answer for
  high-fidelity W8A8 INT8, but it is a credible engine/kernel source for an
  8-bit bakeoff or for borrowing MoE scheduling ideas.
- oneDNN GPU/SYCL docs confirm GPU primitive support, multiple datatypes
  including FP8 and int8, MatMul, and BRGEMM. That keeps a lower-level
  oneDNN/BRGEMM-style MoE micro-harness on the table for small decode batches.

Near-term notes to add to the "things to try" list:

1. Real KV-resident decode-bucket timing.
   - Add rank-0 timing metadata for actual scheduled token counts, spec-token
     lengths, graph bucket, decode/prefill request split, and `model_forward`.
   - Do not infer MTP viability from `/generative_scoring`; it recomputes
     prompt+item and is only a stability/correctness proxy.

2. Verifier-only replay against accepted KV state.
   - Use the no-bonus accounting failure fixture where suppressed token `21`
     should be followed by `6` but the speculative path produced `0`.
   - Run the accepted verifier one token at a time from the same visible prefix.
   - If accepted verifier still prefers `6`, the remaining bug is hidden
     speculative/proposer/KV state, not model quality.

3. Bonus-intact speculation stability isolate.
   - Standard n-gram5 with the verifier bonus intact crashed during initial
     prefill at `block_table.copy_to_gpu`.
   - Reproduce with smaller graph buckets and eager/no-graph diagnostics before
     any speed attempt. Device loss is a stability blocker.

4. Shallow exact draft lane.
   - Try a depth-2 draft/MTP/EAGLE/DFlash-style path where the current Quark
     W8A8 model remains the final verifier.
   - Promotion condition is token-trace parity, not semantic similarity.
   - Start at small depth because verifier buckets and XPU graph stability are
     not yet proven.

5. Latest XPU branch comparison.
   - Build or test a current vLLM/XPU stack only as a side lane.
   - Look specifically for MoE host-overhead reductions, FP8/block-FP8 changes,
     MTP wiring, and graph/speculative stability fixes.
   - Keep the accepted TP4 service available for fallback and quality baseline.

Bigger, bolder ideas to track:

1. DFlash/DDTree-style rollback verifier for Qwen3.6 35B.
   - The Localmaxxing signal says rollback/tree speculation can be a real lever
     for Qwen3.6-family models.
   - For our no-quality-loss rule, the tree proposes only; the Quark W8A8 model
     verifies final tokens.
   - Build it as a sidecar first, not intertwined with the accepted service.

2. Early-exit or partial-layer self-draft.
   - Use the same tokenizer and same model family, but run a cheaper partial
     network to propose candidate tokens.
   - This spends compute to reduce verifier steps; it may be better than
     n-gram because acceptance can be high on non-repetitive chat.
   - Quality remains exact because the final verifier owns output.

3. Memory-for-latency expert replication.
   - Use spare B70 memory to replicate hot experts, shared experts, final
     projection shards, or tile-native W8A8 packed weights.
   - Start from the route-capture evidence: K32/K64 route sets cover much more
     traffic than K16, while K16 is too blunt.
   - Separate this from production max-concurrency mode because it spends memory
     that 32K/c48 serving may need.

4. Persistent route-window MoE kernel.
   - Fuse route count, permute, activation, grouped GEMM, and finalize for a
     short decode route window.
   - This is the main non-speculative path if `model_forward` and MoE continue
     to dominate the one-token timing budget.

5. Static solo decode lane.
   - Preallocate KV/block tables, fix graph buckets, disable unnecessary
     scheduler churn, and specialize for batch/concurrency 1.
   - This sacrifices generality for single-request speed, which matches the
     current primary objective.

6. Whole-token Level Zero command-list capture.
   - Capture/replay a full decode step rather than only individual kernels.
   - This could reduce launch/sync boundaries across dense W8A8, attention/GDN,
     MoE, collectives, logits, and sampling while keeping identical math.

7. oneDNN/BRGEMM MoE kernel experiment.
   - Prototype a small decode-batch expert GEMM harness using oneDNN GPU/SYCL
     primitives or BRGEMM-like packing ideas.
   - Compare against current XPU custom-op timing on real captured expert
     shapes before considering integration.

8. Communication-avoidance layout.
   - Simulate TP4, TP2 plus replicated hot experts, and hybrid TP/EP layouts
     using real route histograms.
   - Promote only if the duplicated-weight and communication math predicts a
     large c1 win, not a small aggregate-throughput gain.

9. Exact final-logits shortcut.
   - For greedy temperature-0 canaries, test whether final projection/argmax can
     avoid full logits materialization.
   - This is high risk for correctness; require exact token and repeat parity.

10. True 8-bit engine bakeoff.
    - Compare vLLM/XPU Quark W8A8 with llama.cpp/SYCL Q8-class paths,
      OpenVINO/oneDNN GenAI, IPEX/BigDL, and any Intel-native 8-bit route.
    - Constraints remain strict: Qwen3.6 35B, high-fidelity 8-bit, same
      template, no Qwen3.5, no 4-bit substitution.

11. Production dual-lane design.
    - Keep a conservative accepted TP4 lane for correctness, stability, and
      32K/c48 planning.
    - Add an opt-in speed lane for speculative/static-solo/memory-for-latency
      experiments with automatic fallback when the quality oracle fails.

12. Upstream-first repro packet.
    - Package the no-bonus accounting proof, verifier-followup preference,
      bonus-intact n-gram5 device loss, route-window MoE timing, and exact
      Localmaxxing rows.
    - This is the clearest way to get Intel/vLLM help on XPU graph/spec/MoE
      issues that are too deep for local flag tuning.

Revised opportunity order:

1. Instrument real decode buckets and one-token timing.
2. Fix or bypass speculative state problems with verifier-preserving draft
   lanes.
3. In parallel, build route-window MoE timing around real captured expert
   shapes.
4. If timing points to graph/scheduler boundaries, prototype static solo decode
   and whole-token command-list capture.
5. Keep a separate engine-bakeoff branch so we notice if vLLM/XPU is the local
   ceiling rather than the model/hardware ceiling.

## KV-Resident Decode-Bucket Timing Metadata And Accepted-Lane Probe

Added a real decode-step timing grouping path so future speculative/MTP/EAGLE
work can measure actual KV-resident scheduled-token buckets instead of relying
on `/generative_scoring`.

New or updated artifacts:

- `scripts/summarize-xpu-decode-timing-log.py`
- `patches/vllm-qwen36-decode-bucket-timing-metadata-20260611.patch`
- `data/qwen36-quark-int8-tp4-decode-bucket-timing-p512o96-20260611.json`
- `data/qwen36-quark-int8-tp4-decode-bucket-timing-summary-20260611.json`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-bucket-timing-text-smoke-20260611.json`

Instrumentation details:

- The local vLLM timing metadata now records:
  - `scheduled_token_counts`
  - `scheduled_token_histogram`
  - `scheduled_spec_lengths`
  - `scheduled_spec_histogram`
  - `max_scheduled_spec_tokens`
  - `computed_token_counts`
  - `decode_req_count`
  - `prefill_req_count`
  - `is_pure_decode`
  - `decode_bucket`
  - batch descriptor token/request counts
- The summarizer now emits `step_summary_by_bucket`, grouped by graph mode,
  pure-decode status, scheduled token bucket, spec-token max, batch size, and
  padded/unpadded token counts.
- Validation passed:
  - `py_compile` for the local vLLM runner and summarizer.
  - `git apply --reverse --check` for
    `patches/vllm-qwen36-decode-bucket-timing-metadata-20260611.patch` against
    the current local vLLM tree.
  - `git diff --check` for the lab repo changes.

One instrumentation bug was found and fixed:

- The first timing request failed with HTTP `500` because
  `num_tokens_across_dp` can be `None` on this path and the metadata attempted
  `int(None)`.
- The patch now serializes it as `None` when absent.
- This was an instrumentation-only failure; no speed or quality result was
  claimed from the failed request.

Accepted-lane timing probe:

- Runtime: accepted TP4/Quark/32K/no-prefix recipe with timing enabled.
- Timing env:
  - `VLLM_XPU_DECODE_TIMING=1`
  - `VLLM_XPU_DECODE_TIMING_SYNC=1`
  - `VLLM_XPU_DECODE_TIMING_RANK=0`
  - `VLLM_XPU_DECODE_TIMING_STEP_SUMMARY=1`
  - `VLLM_XPU_DECODE_TIMING_STEP_SKIP_FIRST=32`
- Probe shape:
  - direct backend `/v1/completions`
  - prompt `512`
  - output `96`
  - warmup output `16`
  - natural-chat preset
  - batch/concurrency `1`
  - ignore EOS

Important caveat:

- The run uses `VLLM_XPU_DECODE_TIMING_SYNC=1`, so endpoint throughput is
  intentionally slowed by synchronization and timing overhead.
- Use the bucket timings to understand shape and component cost. Do not use this
  run as a promoted speed benchmark.

Endpoint-facing diagnostic metrics under synchronized timing:

- Corrected after-first output throughput: `65.99 tok/s`.
- End-to-end output throughput: `60.18 tok/s`.
- Client TTFT: `155.46 ms`.
- vLLM TTFT metric: `139.50 ms`.

Bucket summary:

| Field | Value |
| --- | --- |
| step lines summarized | `80` |
| cudagraph mode | `PIECEWISE` |
| pure decode | `true` |
| decode bucket | `1` |
| max scheduled tokens | `1` |
| max scheduled spec tokens | `0` |
| scheduled token histogram | `{"1": 80}` |
| scheduled spec histogram | `{"0": 80}` |
| mean model_forward per step | `12.393 ms` |
| mean visible timed work per step | `16.759 ms` |

Top visible timed regions in the bucket-1 group:

| Region | Mean total ms/step |
| --- | ---: |
| `gpu_model_runner.model_forward` | `12.393` |
| `gdn_attention_core_xpu.native` | `2.730` |
| `gpu_model_runner.compute_logits` | `0.780` |
| `logits.local_argmax_lm_head` | `0.542` |
| `gpu_model_runner.sampler` | `0.163` |

Interpretation:

- This is the first confirmed KV-resident bucket-1 timing with the actual
  accepted graph path and current model.
- Small post-forward regions are not large enough to get anywhere close to a
  `2x` single-user gain by themselves.
- The next high-upside test is still verifier-preserving multi-token decode:
  measure bucket `2,3,4,5,6,8` with the same metadata once the speculation
  stability/correctness issue is isolated.
- If verifier buckets are expensive or unstable, shift effort to persistent MoE,
  static solo decode, and whole-token command-list capture.

Restore status:

- Timing backend was stopped.
- Accepted no-timing backend was restored in tmux session
  `qwen36-tp4-accepted-restored-after-bucket-timing-20260611q`.
- Backend `/health` and frontdoor `/health` passed.
- Frontdoor text smoke passed with `pass_all=true`,
  `baseline_match_all=true`, `repeat_pass=true`, and long-context pass.

## Bigger Bolder Ideas After Bucket-1 Timing

The bucket-1 timing confirms that tiny post-forward edits are unlikely to
produce a 2x single-request win. The next ideas should be larger and should
still preserve final-token quality by either keeping the same verifier or
matching current INT8 math exactly.

External leads checked:

- vLLM RFC `vllm-project/vllm#33214` tracks the Intel backend migration from
  IPEX to `vllm-xpu-kernels`, including XPU scaled-mm, FP8 W8A8, FP8 MoE, and
  MoE kernel work:
  `https://github.com/vllm-project/vllm/issues/33214`.
- oneDNN v3.13 documents experimental grouped memory and grouped GEMM support
  for MoE workloads, plus profiling hooks that could make a clean Intel GPU
  primitive shootout possible:
  `https://uxlfoundation.github.io/oneDNN/dev_guide_experimental.html`.
- PyTorch's persistent cache-aware grouped-GEMM MoE writeup is CUDA/Triton
  oriented, but the design target maps well to this bottleneck: keep worker
  groups alive, feed them a route-aware tile queue, and reduce per-expert launch
  and scheduling overhead:
  `https://pytorch.org/blog/accelerating-moes-with-a-triton-persistent-cache-aware-grouped-gemm-kernel/`.
- Intel's current vLLM/XPU material explicitly mentions INT8/FP8 support,
  chunked prefill, data parallelism, and experimental expert parallelism. That
  makes a TP/EP or DP/EP simulation worth doing instead of only tuning TP4:
  `https://github.com/intel/ai-containers/blob/main/vllm/0.14.1-xpu.md`.

Larger things to try:

1. XPU-kernel-forward branch.
   - Diff the current local vLLM fork against the newest `vllm-xpu-kernels`
     migration points and selectively test XPU scaled-mm/FP8-MoE kernel changes.
   - This may be the fastest path if local work is chasing problems upstream has
     already moved into the dedicated XPU kernel library.

2. oneDNN grouped-GEMM MoE harness.
   - Build a standalone route-capture replay harness that feeds real Qwen3.6
     layer/expert shapes into oneDNN grouped matmul on XPU.
   - Compare exact component timings against current vLLM/XPU custom ops before
     any integration work.

3. Persistent XPU grouped-GEMM prototype.
   - Borrow the persistent grouped-GEMM design, not the CUDA implementation.
   - Use route histograms to build a persistent tile scheduler for top-k experts
     and avoid the current many-small-work scheduling pattern.

4. Static solo decode lane.
   - Create a dedicated c1 path that gives up broad dynamic serving features for
     one hot, stable decode shape.
   - Goal: capture or replay a whole token step across dense W8A8, GDN
     attention, MoE, collectives, logits, and sampling with fewer host/runtime
     boundaries than general vLLM serving.

5. Memory-for-latency layout.
   - The model footprint leaves much more VRAM headroom than expected, so spend
     memory to reduce communication and routing latency.
   - Candidates: replicate hot experts, duplicate final projection/logits
     helpers, keep per-prompt-class expert packs resident, or run two TP2 lanes
     with different hot-expert placements.

6. Hybrid TP/EP simulation before implementation.
   - Use captured route histograms to estimate whether TP4, TP2+replication,
     TP+EP, or DP+EP reduces layer-time enough for c1.
   - Only build a real engine path if the model predicts a large single-request
     win, not just better aggregate throughput.

7. Verifier-preserving sidecar proposer.
   - Stop blind n-gram width sweeps.
   - Build or adapt a same-tokenizer proposer trained/distilled for Qwen3.6
     next-token sequences, with the current Quark model still verifying all
     accepted tokens.
   - Quality remains verifier-bound; speed depends on acceptance and bucket-2+
     verifier timing.

8. Verifier-bucket first decision gate.
   - Use the new decode-bucket metadata to measure true bucket `2,3,4,5,6,8`
     verifier costs.
   - If bucket costs scale sublinearly, speculation is still the biggest win.
     If they scale near-linearly or destabilize, prioritize MoE/layout/static
     decode instead.

9. Whole-step Level Zero command-list capture.
   - Prototype command-list capture around the full decode step, not isolated
     kernels.
   - This is a bigger systems bet: fewer host submits and sync points while
     preserving the exact same kernels and math.

10. Exact 8-bit engine shootout.
    - Keep Qwen3.6 35B and high-fidelity 8-bit fixed, then compare current
      vLLM/XPU against OpenVINO/oneDNN GenAI, llama.cpp/SYCL Q8-class paths,
      IPEX/BigDL, LMDeploy if XPU-capable, and newer vLLM-XPU builds.
    - No 4-bit substitutions and no Qwen3.5 substitutions.

11. Root/firmware/software matrix.
    - Do a controlled driver/kernel/Level Zero/oneCCL matrix once root access is
      available.
    - The B70 link display quirk probably is not the main bottleneck, but
      reversible power/runtime policy plus stack-version testing may expose a
      free stability or latency win.

12. Upstreamable B70 repro package.
    - Package the exact bucket-1 timing, speculative accounting fixtures,
      route-capture overlap, Localmaxxing row, and launch scripts into a clean
      issue/PR packet for Intel/vLLM.
    - If the bottleneck is inside the backend kernel roadmap, a good repro may
      save more time than local patching.

Priority after this checkpoint:

1. Measure verifier buckets `2,3,4,5,6,8`.
2. In parallel, build the oneDNN grouped-GEMM MoE route replay harness.
3. Run a current vLLM-XPU/kernel-library delta check.
4. If verifier buckets look good, invest in a real sidecar proposer or MTP
   adaptation.
5. If verifier buckets look bad, move to persistent MoE, hybrid TP/EP, and
   static solo decode.

## Speculative Verifier Bucket Scaling Probe

Ran short diagnostic n-gram speculative timing probes with synchronized XPU
timing enabled. These are not promoted speed results because
`VLLM_XPU_DECODE_TIMING_SYNC=1` slows serving, and the n-gram paths are not
quality-promoted. The point was to answer whether multi-token verifier buckets
are expensive enough to kill speculation as a no-quality-loss route.

New or updated artifacts:

- `scripts/launch-qwen36-quark-int8-ngram-trace.sh`
- `data/qwen36-quark-int8-tp4-ngram2-bucket-timing-repetitive-p512o160-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram2-bucket-timing-repetitive-summary-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram2-bucket-timing-natural-p512o160-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram2-bucket-timing-natural-summary-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram2-bucket-timing-spec-summary-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram2-bucket-timing-spec-summary-20260611.md`
- `data/qwen36-quark-int8-tp4-ngram5-bucket-timing-repetitive-p512o128-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram5-bucket-timing-repetitive-summary-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram5-bucket-timing-spec-summary-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram5-bucket-timing-spec-summary-20260611.md`
- `data/qwen36-quark-int8-tp4-ngram7-bucket-timing-repetitive-p512o96-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram7-bucket-timing-repetitive-summary-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram7-bucket-timing-spec-summary-20260611.json`
- `data/qwen36-quark-int8-tp4-ngram7-bucket-timing-spec-summary-20260611.md`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-spec-bucket-timing-text-smoke-20260611.json`

Launcher change:

- `scripts/launch-qwen36-quark-int8-ngram-trace.sh` now mirrors the accepted
  launcher timing guard: timing env vars stay disabled by default, but are
  preserved when `VLLM_XPU_DECODE_TIMING_ALLOW=1` is set.

Bucket timing results:

| Path | Prompt | corrected tok/s under timing sync | bucket | max spec | steps | mean model_forward ms | mean visible timed ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| accepted reference | natural p512/o96 | `65.99` | `1` | `0` | `80` | `12.393` | `16.759` |
| n-gram2 | repetitive p512/o160 | `90.54` | `3` | `2` | `27` | `15.435` | `17.294` |
| n-gram2 | natural p512/o160 | `81.16` | `3` | `2` | `33` | `15.269` | `17.184` |
| n-gram5 | repetitive p512/o128 | `84.67` | `6` | `5` | `17` | `15.544` | `17.102` |
| n-gram7 | repetitive p512/o96 | `96.29` | `8` | `7` | `9` | `18.883` | `20.420` |

Bucket-1 comparison inside the same speculative runs:

- n-gram2 natural bucket-1: `12.241 ms` model forward, `16.491 ms` visible.
- n-gram5 repetitive bucket-1: `12.269 ms` model forward, `16.548 ms` visible.
- n-gram7 repetitive bucket-1: `12.301 ms` model forward, `16.566 ms` visible.

Spec trace summaries:

| Path | trace rows | drafts | accepted | rejected | acceptance | full accept rows | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| n-gram2 mixed probes | `71` | `142` | `112` | `30` | `78.87%` | `70.42%` | `22` |
| n-gram5 repetitive | `19` | `92` | `38` | `54` | `41.30%` | `21.05%` | `2` |
| n-gram7 repetitive | `10` | `70` | `38` | `32` | `54.29%` | `30.00%` | `2` |

Interpretation:

- Verifier bucket scaling is favorable. Bucket `3` and `6` model-forward time
  is only about `15.3-15.5 ms` versus `12.2-12.4 ms` for bucket `1`; bucket
  `8` is `18.9 ms`.
- This means a high-acceptance verifier-preserving proposer could plausibly
  reach the `>200 tok/s` single-user target without changing final-token
  quality, because the current verifier is not close to linear in scheduled
  token count.
- The current n-gram proposer is the wrong production path. n-gram2 acceptance
  can be good on repetitive/easy prompts, but earlier quality gates rejected
  n-gram variants on prompt-class and long-context behavior. n-gram5/n-gram7
  also lose too much acceptance even when bucket cost is favorable.
- The next speculation work should be a real same-tokenizer sidecar/MTP/EAGLE
  proposer or a verifier-only replay harness, not more blind n-gram width
  sweeps.

Restore status:

- Stopped the n-gram timing backend.
- Restored accepted no-timing backend in tmux session
  `qwen36-tp4-accepted-restored-after-spec-bucket-timing-20260611u`.
- Backend `/health` and frontdoor `/health` passed.
- Frontdoor text smoke passed with `pass_all=true`,
  `baseline_match_all=true`, `repeat_pass=true`, and long-context pass.

Revised priority:

1. Use bucket-scaling evidence to prioritize verifier-preserving sidecar/MTP
   speculation over more n-gram tuning.
2. Keep route/MoE work alive in parallel, but treat it as second path unless
   sidecar acceptance cannot be made high and exact.
3. Build a tiny scorer for speculative candidates: expected visible time per
   emitted token from bucket timings, acceptance, and rejection pattern.
4. Use that scorer before launching further long experiments.

## MTP Asset Inspection And Bigger Bets

Added after the bucket-scaling probe, before the next launch attempt. The main
lesson is that the local vLLM tree already has more Qwen3.5/Qwen3.6 MTP support
than the current Quark checkpoint exposes, so the next useful experiment should
be a carefully isolated hybrid-proposer test rather than another n-gram sweep.

Local facts:

- Current Quark verifier checkpoint:
  `/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118`
- Official FP8 checkpoint:
  `/mnt/fast-ai/llm-cache/hf/hub/models--Qwen--Qwen3.6-35B-A3B-FP8/snapshots/95a723d08a9490559dae23d0cff1d9466213d989`
- Both configs report Qwen3.6/Qwen3.5-MoE shape compatibility:
  `40` layers, hidden size `2048`, `256` experts, `8` experts per token,
  `mtp_num_hidden_layers=1`, and `mtp_use_dedicated_embeddings=false`.
- The current Quark safetensors index has `62696` keys and `0` MTP keys.
- The official FP8 safetensors index has `64196` keys and `1560` MTP keys.
- The official `mtp.safetensors` payload resolves to an `815M` local blob.
- Local vLLM has `Qwen3_5MTP` and `Qwen3_5MoeMTP` registered, plus
  `vllm.config.speculative` support that maps Qwen `qwen3_5_moe` to
  `Qwen3_5MoeMTP` for `method="mtp"`.
- Local vLLM also has `VLLM_QWEN35_MTP_FORCE_FP8_BLOCK=1`, which forces the
  MTP drafter linear layers to block-FP8 quantization. That matches the official
  FP8 MTP tensor format and is exactly the kind of compatibility knob needed
  for a first test.
- vLLM's documented MTP launch shape is:
  `--speculative-config '{"method":"mtp","num_speculative_tokens":1}'`.
  A local test fixture also uses `num_speculative_tokens=2` and
  `max_model_len=32768` for Qwen FP8 MTP.

Immediate thing to try:

1. Build a disposable hybrid model directory that keeps the current Quark
   verifier weights/config as the target, but adds the official FP8
   `mtp.safetensors` and index entries as a drafter-only asset.
2. Launch with `VLLM_QWEN35_MTP_FORCE_FP8_BLOCK=1` and:
   `--speculative-config '{"method":"mtp","num_speculative_tokens":1,"max_model_len":32768}'`.
3. Use a tiny output first: health, one exact canary, then request-id token
   trace and replay.
4. Promote to speed testing only if the exact accepted baseline token stream is
   preserved across repeat colors and the long-context needle.
5. If launch fails because vLLM insists that the target checkpoint itself owns
   the MTP tensors, do not hack quality behavior. Instead, turn the failure into
   a small patch or repro that teaches vLLM to load a same-shape auxiliary MTP
   payload while keeping the Quark verifier as the final authority.

Risks and guardrails:

- Do not count the official FP8 model as the promoted model unless the final
  tokens are verified by the Quark INT8 verifier. The target remains the current
  Quark INT8 model.
- Do not use Qwen3.5, AWQ, GPTQ-4bit, Q4, or MXFP4 as an answer to the user's
  8-bit Qwen3.6 target.
- Do not trust semantic-looking output. The quality gate is exact canary hashes,
  repeat stability, long-context needle, and request-id joined speculative
  replay.
- Treat MTP speed as invalid until `suppressed_bonus` and scheduler counter
  accounting are clean. The previous n-gram/no-bonus work found real state
  accounting issues.

Bigger, bolder ideas worth tracking:

1. Hybrid Quark-verifier plus official-FP8-MTP service.
   - If the simple symlink/index hybrid works, tune `num_speculative_tokens=1`,
     then `2`, and score expected speed from the measured bucket costs.
   - This is the most direct no-quality-loss route to `>200 tok/s`: the Quark
     verifier remains final, while the MTP path buys larger verifier buckets.

2. Auxiliary-MTP loader patch for vLLM.
   - Add an explicit field such as `mtp_model` or `auxiliary_weights` to
     `speculative_config`, so Qwen MTP tensors can live outside the target
     checkpoint.
   - This is cleaner than mutating model directories and would be upstreamable
     if it keeps final verification semantics unchanged.

3. Same-tokenizer learned proposer.
   - Train or fit a tiny Qwen3.6-specific proposer on traces from the current
     verifier, using the same tokenizer and accepted prompt templates.
   - It can be much smaller than the target model because wrong drafts are
     rejected. The quality risk is bounded by the verifier; the performance risk
     is poor acceptance or extra latency.

4. Partial-layer self-drafter.
   - Use the first N target layers or a compressed side branch as a draft model,
     then verify with the full Quark model.
   - This spends no trust on a different quantized model, but it needs careful
     vLLM plumbing to avoid duplicating too much work.

5. Branch-budget speculative scorer.
   - Before running long experiments, predict speed from:
     `acceptance_rate`, `full_accept_streaks`, bucket cost by scheduled tokens,
     and rejection rollback cost.
   - This should prevent more blind n-gram sweeps and tell us whether a proposer
     needs 60%, 75%, or 90% acceptance to beat the target.

6. Verifier-only multi-token stress harness.
   - Feed synthetic perfect drafts into the verifier to measure the upper bound
     of bucket `2,3,4,6,8,12` without proposer noise.
   - If the upper bound cannot cross `200 tok/s`, speculation is not enough. If
     it can, the whole problem becomes proposer quality and state correctness.

7. Route-aware MTP plus MoE co-design.
   - Capture whether MTP buckets change expert routing patterns compared with
     bucket-1 decode.
   - If route locality improves across multi-token buckets, speculation and
     persistent MoE can compound instead of competing.

8. Memory-for-latency expert placement.
   - Use the unusually comfortable VRAM headroom to replicate or prepack hot
     experts by route bucket, prompt class, or recent-window histogram.
   - This is larger than a kernel flag but may reduce tiny all-reduces and
     scattered expert reads for c1 decode.

9. Persistent decode command graph.
   - Capture a whole token step, including GDN attention, MoE, collectives,
     logits, and sampling, into a reusable command-list path for stable c1
     service.
   - This preserves math and could reduce host/dispatcher overhead, but it is a
     serious systems branch.

10. XPU MoE upstream sprint.
    - Turn our real routed shapes into minimal `vllm-xpu-kernels` or oneDNN
      grouped-GEMM benchmarks and compare against the current endpoint's timing
      budget.
    - The end state should be either a local persistent grouped-GEMM prototype
      or a clean Intel/vLLM issue with enough detail for maintainers to act.

11. Production dual-lane design.
    - Keep the accepted non-speculative Quark TP4 service as the reliability
      lane.
    - Add a speculative latency lane behind an automatic exact-quality canary
      and fallback. This lets production benefit from MTP only when health and
      quality are clean.

12. Bigger benchmark publication packet.
    - When a real win appears, publish not just `tokSOut`, but TTFT, peak VRAM,
      context length, exact command, quality-gate summary, and whether the
      result is non-speculative or verifier-preserving speculative.
    - This makes Localmaxxing results useful for others and keeps us honest
      about which speedups preserve quality.

Updated priority after this inspection:

1. Build the disposable hybrid MTP launch path and expect the first run to be a
   mechanics test, not a benchmark.
2. Add a perfect-draft verifier upper-bound harness if the hybrid launch path
   blocks.
3. Keep route capture and oneDNN/vLLM-XPU grouped-GEMM work as the parallel
   fallback.
4. Keep the accepted TP4 service as the quality oracle and restore it after each
   diagnostic launch.

## Hybrid MTP Mechanics Result

Added after the disposable hybrid MTP launch. The mechanics worked better than
expected, but the quality gate rejected the path.

New helper scripts:

- `scripts/create-qwen36-quark-fp8-mtp-hybrid.py`
- `scripts/launch-qwen36-quark-int8-hybrid-mtp.sh`

Hybrid checkpoint construction:

- output: `/mnt/fast-ai/qwen36-quark-int8-fp8-mtp-hybrid`
- Quark source weight count: `62696`
- official FP8 `mtp.*` weight count: `1560`
- merged index weight count: `64256`
- borrowed file: official FP8 `mtp.safetensors`
- target/verifier remains the Quark W8A8 INT8 checkpoint; only the MTP proposer
  tensors are borrowed.

Launch result:

- `method="mtp"` resolved to `Qwen3_5MoeMTP`.
- `VLLM_QWEN35_MTP_FORCE_FP8_BLOCK=1` selected
  `XPUBF16Fp8BlockScaledMMLinearKernel` for the drafter linear layers.
- vLLM detected the MTP model and shared target embedding/lm-head weights with
  the draft model.
- The server loaded and served with both default async scheduling and explicit
  `--no-async-scheduling`.

Quality result:

- Async hybrid MTP r1 frontdoor token trace passed exact baseline parity:
  `data/qwen36-quark-int8-tp4-hybrid-mtp-frontdoor-token-trace-r1-20260611.json`.
- Async hybrid MTP r4 failed exact parity:
  `data/qwen36-quark-int8-tp4-hybrid-mtp-frontdoor-token-trace-r4-20260611.json`.
  Failures included corrupted copy, arithmetic, and repeat-color outputs.
- Backend-direct r1 trace was an invalid comparison because it bypassed the
  frontdoor request shaping and thinking suppression:
  `data/qwen36-quark-int8-tp4-hybrid-mtp-token-trace-r1-20260611.json`.
- No-async hybrid MTP r4 also failed exact parity:
  `data/qwen36-quark-int8-tp4-hybrid-mtp-noasync-frontdoor-token-trace-r4-20260611.json`.
  The narrower failure was still decisive: long-context needle changed from
  `B70_QWEN36_NEEDLE_20260609` to
  `B Lebens Mourinho \_QWEN36\_NEEDLE\_20260609`.

Decision:

- Reject the hybrid FP8-MTP proposer path as a speed candidate.
- Do not run speed or Localmaxxing submission for it.
- Keep the scripts and traces because they are useful mechanics and failure
  fixtures.
- The problem is not simply async scheduling; disabling async scheduling removed
  some corruption modes but did not preserve long-context token parity.

Restore status:

- Accepted Quark INT8 service restored in tmux session
  `qwen36-tp4-accepted-restored-after-hybrid-mtp-20260611x`.
- Backend `/health` and frontdoor `/health` passed.
- Short frontdoor text smoke passed exact arithmetic/copy/JSON/repeat checks:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-hybrid-mtp-text-smoke-20260611.json`.
- Restored non-MTP service reported `20.67 GiB` available KV cache memory per
  rank and `62.65x` maximum concurrency for 32768-token requests.

## Public Result And Additional External Leads

Localmaxxing now has the newer generic-base public row in addition to the exact
Quark-model row:

- ID: `cmq9ifq0500b0r8012f27j1xl`
- HF ID: `Qwen/Qwen3.6-35B-A3B`
- Engine/quant: vLLM, Quark W8A8 INT8
- Hardware: 4x Intel Arc Pro B70 32GB
- Result: `99.769699` output tok/s, `76.526643 ms` TTFT
- Peak VRAM: `127.547168 GB` total allocation, about `31.89 GiB` per B70
- Artifact: `data/localmaxxing-b70-qwen36-benchmarks-20260611.json`

Additional web-search leads checked:

- vLLM XPU B70/B580 public issue:
  https://github.com/vllm-project/vllm/issues/35638
- vLLM XPU kernel migration/RFC:
  https://github.com/vllm-project/vllm/issues/33214
- vLLM XPU kernel repository:
  https://github.com/vllm-project/vllm-xpu-kernels
- Intel quantization support docs:
  https://docs.vllm.ai/en/stable/features/quantization/inc/
- vLLM XPU hardware support docs:
  https://docs.vllm.ai/en/stable/models/hardware_supported_models/xpu/
- Public B70 Qwen3.5/Qwen3.6-class performance reports continue to show that
  low double-digit to roughly 70 tok/s is common without deeper kernel/layout
  work. Our current `~100 tok/s` row is strong, but still far from the user's
  desired interactive target.

New larger ideas from this result:

1. Build a verifier-only perfect-draft harness before another MTP implementation
   attempt. The bucket timing says speculation has enough theoretical upside;
   the MTP run says the current proposer integration cannot be trusted. A
   perfect-draft fixture can separate verifier bucket correctness from proposer
   state corruption.
2. Create an auxiliary-MTP loader rather than an index-spliced model directory.
   The symlink hybrid proved vLLM can instantiate the drafter, but the failure
   suggests shared model/config assumptions may be leaking into generation
   state. A first-class `mtp_model` or `mtp_weights` field would make the
   boundary explicit and easier to audit.
3. Add a long-context speculative invariant suite. Short r1 canaries were not
   enough; long-context needle parity caught both n-gram no-bonus and hybrid MTP
   problems. Future speculative tests should always include at least one
   request-id joined long-context case before any speed measurement.
4. Try a same-tokenizer learned proposer only after a perfect-draft upper bound.
   The final verifier can preserve quality, but proposer quality must be high
   enough to overcome the extra drafter forward. Train or fit it from current
   Quark traces, not from Qwen3.5 or 4-bit outputs.
5. Explore a single-card or TP2 replica latency lane using the current 8-bit
   model only. Pure TP4 is winning today, but public B70 data suggests
   single-card engines can be competitive for Qwen3.6-class models. A strict
   same-model 8-bit bakeoff could reveal whether cross-card collectives are
   dominating c1 latency.
6. Prototype route-local expert replication with the current VRAM headroom. The
   restored non-MTP service reserves nearly all VRAM for KV, but the actual
   model memory is only about `8.58 GiB` per rank. A latency lane with lower
   max concurrency could spend memory on hot expert copies or prepacked expert
   layouts without changing model math.
7. Build a whole-token timeline budget that includes the server path, not just
   synchronized kernel timing. The offline c1 runner showed HTTP/frontdoor is
   not a 2x loss, but exact per-token command timing could still expose smaller
   launch, sampling, or streaming costs worth cleaning up.
8. Turn the hybrid MTP corruption into an upstreamable minimal repro. The repro
   should include the disposable index script, the exact r1 pass/r4 fail, and the
   no-async long-context failure. This is more actionable than a vague "MTP is
   corrupt on XPU" report.
9. Keep persistent MoE/grouped-GEMM as the fallback path, not a side quest. If
   perfect-draft verifier math cannot reach the target, then speculation cannot
   deliver `>200 tok/s`, and the next credible path is persistent XPU MoE plus
   communication/layout surgery.
10. Production idea: run two lanes once any speculative candidate becomes
    quality-clean. The default lane stays accepted non-spec Quark TP4; the
    speculative lane handles latency-sensitive single requests and auto-falls
    back when long-context/repeat canaries fail.

Immediate next priority:

1. Build the perfect-draft or verifier-only multi-token harness.
2. In parallel, produce a minimal hybrid-MTP failure pack for local debugging and
   potential upstream issue/PR.
3. Stop testing MTP speed until exact long-context parity is restored.
4. Continue MoE route/locality work as the non-speculative fallback.

## Verifier Upper Bound And Bigger Ideas Addendum

Added after turning the bucket timing data into an explicit upper-bound artifact
and refreshing public Arc/Qwen/vLLM leaderboard data.

New artifacts:

- `scripts/analyze-qwen36-verifier-upper-bound.py`
- `data/qwen36-quark-int8-tp4-verifier-upper-bound-20260611.json`
- `data/qwen36-quark-int8-tp4-verifier-upper-bound-20260611.md`
- `data/localmaxxing-intel-arc-pro-b70-qwen-vllm-leaderboard-20260611c.json`
- `data/localmaxxing-qwen36-base-top-20260611c.json`

Upper-bound readout:

| Bucket | Best model-forward ms | Perfect model tok/s | Perfect endpoint-scaled tok/s | Draft accept fraction for 200 tok/s |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 12.241 | 81.69 | 99.77 | n/a |
| 3 | 15.269 | 196.47 | 239.95 | 100.0% |
| 6 | 15.544 | 386.01 | 471.42 | 42.2% |
| 8 | 18.883 | 423.66 | 517.41 | 39.7% |

Interpretation:

- Multi-token verifier work is clearly sublinear on this stack. If the draft
  tokens are correct and the scheduler accounting is clean, bucket 6/8 has
  enough timing headroom for the user's `>200 tok/s` single-request target
  without changing final model quality.
- The current n-gram and hybrid FP8-MTP integrations are still rejected. The
  upper-bound result does not make them valid; it says an exact proposer is
  worth building.
- Bucket 3 is marginal on raw synchronized model-forward timing and clears
  `200 tok/s` only after endpoint normalization. Treat bucket 3 as a minimum
  viable debug shape, not the likely final target.
- Bucket 6/8 should be the next serious verifier harness target because they
  need only roughly `40-42%` average draft-token acceptance to clear `200 tok/s`
  by model-forward math.

Fresh public comparison:

- Exact Intel Arc Pro B70 + vLLM + Qwen leaderboard refresh shows our current
  Quark W8A8 INT8 rows ranked first and second among B70/vLLM/Qwen entries:
  `99.769699 tok/s` on the generic base row and `99.428358 tok/s` on the exact
  Quark model row.
- The global Qwen3.6 35B base leaderboard still has higher NVIDIA/AMD rows,
  many using speculative decode, lower-bit quantization, or non-equivalent
  engines. They are useful directionally but are not quality-equivalent
  replacements for this target.
- Public B70 reports continue to reinforce the same split: vLLM/XPU is strong
  on prefill and multi-GPU serving, while decode needs either better quantized
  kernels/layout or verifier-preserving speculation.

External leads to keep in the queue:

- vLLM XPU hardware docs now list Arc Pro B-series as validated hardware and
  show the supported model/quantization direction:
  `https://docs.vllm.ai/en/v0.22.1/models/hardware_supported_models/xpu/`.
- The PMZFX B70 benchmark notes report vLLM's XMX/flash-attention prefill lead,
  but also that decode is often memory-bandwidth bound and quantized engine
  support matters:
  `https://github.com/PMZFX/intel-arc-pro-b70-benchmarks/blob/master/engine-comparison.md`.
- The public vLLM XPU issue for dual Arc B580 remains relevant as a settings
  and upstream-discussion lead:
  `https://github.com/vllm-project/vllm/issues/35638`.
- EmbeddedLLM's 4x B60 comparison reports that Intel's optimized LLM-Scaler
  build improved TPOT by about `20-25%` versus a standard vLLM build in their
  workload. This is not our model, but it justifies an 8-bit, same-quality
  LLM-Scaler/OpenVINO/vLLM-XPU bakeoff:
  `https://embeddedllm.com/blog/benchmarking-llm-inference-intel-arc-pro-b60`.

New bigger, bolder things to try:

1. Oracle-draft verifier harness inside vLLM.
   - Feed known-good token IDs from an accepted trace back into the scheduler as
     draft tokens, keyed by request ID or prompt hash.
   - This would measure true KV-resident multi-token verification without
     proposer noise and would catch the same accounting bugs that broke
     n-gram/no-bonus.
   - Success criterion: bucket 3/6/8 token streams exactly match accepted output
     while traces report zero rollback/accounting mismatches.

2. DFlash/MTP hidden-state index audit.
   - Public DFlash results mention an off-by-one patch where the drafter read
     the wrong hidden state and acceptance collapsed. Our hybrid MTP failures
     look like a related class of state-position bug.
   - Inspect XPU MTP/DFlash paths for prompt/output index, bonus-token,
     async-scheduler, and no-async differences before trying another proposer.

3. Auxiliary proposer API instead of index-spliced checkpoints.
   - Make MTP weights a separate explicit asset, not merged into the verifier
     checkpoint directory.
   - This should reduce accidental config/weight sharing and make it easier to
     keep the Quark verifier as the only quality authority.

4. Confidence-gated learned proposer trained from Quark traces.
   - Train or fit a same-tokenizer proposer from accepted Quark outputs and
     route it through strict verifier rejection.
   - It can be tiny if confidence-gated; the verifier preserves quality, and
     low-confidence steps simply fall back to bucket 1.

5. Bucket-aware static decode lane.
   - Create a latency service class with lower max concurrency and preallocated
     bucket 6/8 graph shapes.
   - If this preserves exact output, it can spend some of the current KV
     headroom on graph stability, hot expert placement, and lower scheduler
     overhead while the normal TP4 lane stays production-safe.

6. Memory-for-latency expert replication.
   - The restored service has large effective concurrency headroom; a dedicated
     c1/c4 latency lane can trade some KV capacity for hot expert copies or
     tile-native prepacked expert weights.
   - Use real router histograms, not static guesses. Global K16 hotpacking was
     too blunt; route-window or prompt-class hotsets are more credible.

7. Same-quality LLM-Scaler/OpenVINO/vLLM-XPU shootout.
   - Keep model family, 8-bit/high-fidelity quantization, prompt template, 32K
     context, and quality gates fixed.
   - The goal is not switching to 4-bit or Qwen3.5; it is finding whether Intel's
     optimized stack already has a better W8A8/W8A16 decode path we can use or
     port.

8. Whole-token command-list capture.
   - Instead of optimizing one kernel at a time, capture the complete decode
     token path: attention/GDN, MoE, collectives, logits, sampling, and state
     updates.
   - This is a serious systems branch, but it matches the evidence that many
     small boundaries remain after the easy custom-op work.

9. Upstreamable B70/XPU minimal repro packet.
   - Package three concrete repros: W8A8 dense GEMM, routed MoE grouped GEMM,
     and MTP/speculative state corruption.
   - Include shape data, exact commands, token-trace failure fixtures, and
     current throughput. This may be the fastest way to get Intel/vLLM kernel
     help instead of carrying every patch locally.

Updated priority:

1. Implement the oracle/perfect-draft verifier harness from accepted token
   traces.
2. Audit MTP/DFlash state indexing using the hybrid MTP failure pack.
3. Start real-router histogram capture for MoE placement and grouped-GEMM work.
4. Plan a same-quality 8-bit engine shootout only after the current verifier
   harness tells us whether speculation can really cross the target.

## Expanded Things To Try After Oracle Harness

Added after stepping back from the verifier upper-bound result and the failed
hybrid-MTP quality gates. These are intentionally bolder than ordinary launch
flag sweeps, but each still preserves the rule: the current Quark INT8 model is
the final quality authority unless a candidate passes a stricter BF16/current
comparison.

Near-term experiments:

1. Oracle-draft verification at several widths.
   - Use accepted completion token traces to inject perfect draft tokens through
     vLLM's speculative scheduler.
   - Run `k=3`, `k=5`, `k=6`, and `k=8` with both eager and graph modes.
   - Record exact token parity, accepted-token rate, rollback/accounting
     mismatches, TTFT, and per-token throughput.
   - Decision rule: if perfect-draft `k=6/8` cannot exceed `200 tok/s` with
     exact output, stop speculation work and move the priority to MoE/layout.

2. Recompute-after-reject verifier diagnostic.
   - For n-gram and MTP failures, force the scheduler to recompute one clean
     bucket-1 step after every reject or suppressed bonus token.
   - If quality recovers, the bug is scheduler/KV state accounting; if not, the
     bug is proposer token/state indexing or verifier inputs.
   - This is a debugging path only, not a promoted serving mode unless the
     recompute cost is negligible.

3. Speculative acceptance predictor.
   - Use existing n-gram/MTP traces to classify prompt windows by likely
     acceptance rate before enabling speculation.
   - Disable speculation automatically for long-context/repeat patterns where
     the failure fixtures cluster.
   - This will not create a `2x` win alone, but it can make future speculation
     safe enough for production fallback.

4. Token-trace quality oracle as a CI gate.
   - Promote request-id joined token traces, replay checks, and long-context
     canaries into one command that every speculative or kernel candidate must
     pass before speed measurement.
   - Include repeat64, copy/arithmetic/JSON canaries, and at least one
     long-context needle.
   - This avoids wasting time on fast-but-corrupt branches.

5. Real-router histogram capture during accepted serving.
   - Add low-overhead router top-k capture for a short accepted run across
     natural chat, code, math, structured output, and repetitive prompts.
   - Use the histograms for real grouped-GEMM/MoE microbench inputs and for
     deciding hot expert replication candidates.
   - Synthetic uniform routes should no longer drive MoE decisions.

Medium engineering branches:

1. First-class auxiliary proposer API.
   - Stop symlink/index-splicing MTP tensors into the verifier checkpoint.
   - Add an explicit auxiliary proposer path with separate model config,
     tokenizer validation, KV/state ownership, and final-verifier-only output.
   - This is the cleaner path for official FP8 MTP tensors, EAGLE/DFlash, or a
     learned same-tokenizer proposer.

2. Self-speculative shallow verifier branch.
   - Explore a LayerSkip-style or early-exit drafter from the same Qwen3.6
     verifier weights: run a partial stack to propose, then verify with the full
     stack.
   - Quality can be preserved because the full stack verifies every token.
   - The hard question is whether the partial stack is cheaper enough on B70 to
     beat current bucket-1 decode.

3. Sidecar drafter pipeline.
   - Run a small same-tokenizer Qwen3.6 drafter, MTP sidecar, or partial-stack
     proposer in a separate process/GPU lane while the TP4 verifier handles
     accepted tokens.
   - Useful only if drafter latency overlaps verifier work or if its output is
     highly accepted.
   - Keep the sidecar on 8-bit/high-fidelity or BF16/FP8 draft assets; no
     Qwen3.5 or 4-bit detours.

4. Latency-lane service class.
   - Keep the normal TP4 accepted service for production reliability and
     concurrency.
   - Add a separate c1/c4 lane with lower max concurrency, fixed bucket graphs,
     reduced scheduler overhead, and memory allocated to hot expert copies or
     prepacked layouts.
   - Compare user-visible TTFT and steady decode, not just model-forward timing.

5. Hybrid TP/EP simulator before implementation.
   - Model expert memory, dense/attention replication cost, KV cost at 32K, and
     all-to-all/all-reduce message sizes.
   - Candidate layouts: TP2+EP2, replicated dense plus expert partitioning, two
     TP2 replicas for aggregate, and layer-local expert replication.
   - Only implement if the memory math predicts fewer collectives for c1 while
     retaining acceptable c8/c16 aggregate capacity.

6. Persistent MoE route-window kernel.
   - Build a standalone parity microbench using real route windows and Quark
     W8A8 weights/scales.
   - Fuse route remap, activation, second quant, grouped GEMM, gather/finalize,
     and optional shared-expert add where mathematically safe.
   - Start as a `vllm-xpu-kernels` repro; wire into vLLM only after parity and
     isolated speed are proven.

7. Tile-native W8A8 repack cache.
   - Determine whether current INT8 GEMMs consume an optimal B70/XMX layout or
     pay transpose/repack/strided-memory costs in hot paths.
   - If not, repack once at load time with checksummed cache files.
   - This keeps weights/scales identical and changes only layout.

8. Whole-token command-list or persistent graph capture.
   - Capture the complete decode path for a fixed bucket: GDN/attention, MoE,
     collectives, logits, sampling, and request-state update.
   - The goal is fewer host/runtime transitions rather than one more tiny
     kernel replacement.
   - Treat this as a c1 latency-lane branch, not the default production path
     until reliability is proven.

Moonshots that might be worth a separate branch:

1. Quark-trace-trained proposer.
   - Generate a large local corpus from the accepted Quark model, then train a
     tiny same-tokenizer draft head or prompt-class proposer.
   - It may be enough to draft only common continuations, punctuation, code
     syntax, and structural JSON tokens with high confidence.
   - Reject any output not accepted by the Quark verifier.

2. Route-aware speculation.
   - Use router/hot expert features to predict where the verifier is likely to
     be cheap or where a draft model is likely to agree.
   - Dynamically choose `k=1`, `k=3`, `k=6`, or no-spec per request window.
   - This combines the two strongest signals so far: bucket sublinearity and
     route locality.

3. Memory-for-latency hot expert copies.
   - Dedicate part of the 32GB cards to duplicated hot experts or duplicated
     prepacked expert tiles for a latency lane.
   - Sacrifice max 32K concurrency only on that lane.
   - Use prompt-class K32/K64 hotsets rather than a single global K16 mapping.

4. XPU-native 8-bit engine shootout with one quality harness.
   - Compare current vLLM Quark W8A8, llama.cpp/SYCL Q8_0 or equivalent 8-bit,
     OpenVINO/oneDNN GenAI, LLM-Scaler, and any current vLLM-XPU-kernels branch
     that supports Qwen3.6 MoE.
   - Same prompts, same no-thinking chat template, 32K context, same repeat and
     long-context gates.
   - This is diagnostic unless a candidate also serves production traffic.

5. Upstream packet and bounty-quality repros.
   - Package three minimal public repros: W8A8 dense GEMM underperforming shape,
     routed MoE grouped GEMM from real histograms, and speculative MTP state
     corruption on XPU.
   - Include commands, shape metadata, expected versus current throughput, and
     token-trace failures.
   - This may unlock help faster than carrying increasingly deep local patches.

Updated action order:

1. Finish the oracle verifier harness and record whether perfect draft actually
   crosses `200 tok/s` on this hardware.
2. If yes, invest in proposer correctness: auxiliary MTP/DFlash/self-spec and
   acceptance prediction.
3. If no, pivot to persistent MoE, hybrid TP/EP, and 8-bit engine shootout.
4. In all cases, keep the accepted TP4 service and token-trace oracle as the
   reliability baseline.

## Oracle Draft Harness First Probe

Added the first opt-in oracle-draft harness for vLLM's n-gram proposer path.
This is not a production feature; it is a diagnostic to separate multi-token
verifier timing/correctness from proposer quality.

New artifacts:

- `scripts/qwen36-completion-oracle-trace.py`
- `scripts/launch-qwen36-quark-int8-oracle-trace.sh`
- `patches/vllm-qwen36-oracle-draft-ngram-proposer-20260611.patch`
- accepted trace seed:
  `data/qwen36-quark-int8-tp4-oracle-completions-accepted-20260611.json`
- eager oracle result:
  `data/qwen36-quark-int8-tp4-oracle5-eager-completions-20260611.json`
- eager oracle spec summary:
  `data/qwen36-quark-int8-tp4-oracle5-eager-spec-summary-20260611.json`
  and
  `data/qwen36-quark-int8-tp4-oracle5-eager-spec-summary-20260611.md`
- restored accepted frontdoor smoke:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-oracle-frontdoor-text-smoke-20260611.json`

Validation:

- `python3 -m py_compile scripts/qwen36-completion-oracle-trace.py`
- `bash -n scripts/launch-qwen36-quark-int8-oracle-trace.sh`
- `git apply --reverse --check` passed for
  `patches/vllm-qwen36-oracle-draft-ngram-proposer-20260611.patch` against the
  current local vLLM tree.

Eager `k=5` result:

- The oracle hook did activate:
  `/tmp/qwen36-oracle5-eager-draft-20260611b.jsonl` recorded `24` matched draft
  rows across the two completion cases.
- vLLM's speculative trace recorded `6` scheduler rows across `2` requests.
- Acceptance over the traced scheduler rows was `73.33%`.
- Exact output parity failed against the accepted graph baseline:
  `baseline_match_all=false`.
- Both cases first diverged at output-token index `14`:
  - `natural_latency_plan`: accepted baseline token `4779` (`memory`) versus
    eager oracle verifier token `29541` (`reliability`).
  - `repetitive_kernel_notes`: accepted baseline token `4752` versus eager
    oracle verifier token `6126`.
- Interpretation: this proves draft injection and trace plumbing work, but it
  is not a valid speed result. Eager/no-graph generation does not reproduce the
  accepted graph baseline for these raw completion prompts, so it cannot answer
  the perfect-draft quality question.

Graph `k=5` result:

- The graph-mode oracle service compiled and reached `/health`, but then hit
  `UR_RESULT_ERROR_DEVICE_LOST` on an external chat request before the local
  completion probe could run.
- The crash happened in `gpu_input_batch._make_sampling_metadata` while copying
  sampling metadata to XPU, after a `prompt_token_ids_len=2386` external request.
- No graph-mode oracle quality or speed number is valid.
- Next graph oracle attempt should be isolated from the production/frontdoor
  traffic path, ideally on a separate port or with the frontdoor paused, because
  external chat traffic can consume the experiment before the controlled probe.

Restore status:

- Accepted non-spec backend restored in tmux session
  `qwen36-tp4-accepted-restored-after-oracle-20260611b`.
- Backend `/health` passed.
- Frontdoor `/health` passed.
- Frontdoor short text smoke passed all exact/copy/arithmetic/JSON/repeat
  checks with `pass_all=true`.
- Direct backend chat smoke still failed the arithmetic canary (`58` instead of
  `60`), which is consistent with earlier notes that production quality claims
  must use the frontdoor/request policy rather than raw backend chat.
  Artifact:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-oracle-text-smoke-20260611.json`.

Next oracle work:

1. Isolate the graph-mode oracle probe from external traffic.
2. Record a graph-mode accepted completion baseline immediately before the
   oracle run, using the exact same endpoint posture, to avoid eager/graph or
   fresh-process drift.
3. Run `k=3`, then `k=6/8` only after `k=5` exact parity is clean.
4. Add a one-command report that joins oracle draft rows, scheduler spec rows,
   and client token diffs by request ID/prefix.

## Isolated Graph Oracle Probe

The follow-up graph oracle run was isolated from frontdoor traffic on backend
port `18081`, with a fresh graph-mode accepted baseline captured immediately
before the oracle run.

New artifacts:

- same-posture accepted graph baseline:
  `data/qwen36-quark-int8-tp4-oracle-isolated-accepted-graph-20260611.json`
- graph `k=5` oracle completions:
  `data/qwen36-quark-int8-tp4-oracle5-graph-isolated-completions-20260611.json`
- graph `k=5` oracle spec summary:
  `data/qwen36-quark-int8-tp4-oracle5-graph-isolated-spec-summary-20260611.json`
  and
  `data/qwen36-quark-int8-tp4-oracle5-graph-isolated-spec-summary-20260611.md`
- restore smoke attempts:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-isolated-oracle-frontdoor-text-smoke-20260611.json`,
  `data/qwen36-quark-int8-tp4-accepted-restored-after-isolated-oracle-frontdoor-text-smoke-rerun-20260611.json`,
  and
  `data/qwen36-quark-int8-tp4-accepted-restored-after-notes-retry-frontdoor-text-smoke-20260611.json`.

Result:

- The graph oracle service did not device-lost during the controlled run.
- The scheduler trace recorded `8` rows over `2` requests, `40` proposed
  draft tokens, `31` accepted tokens, `9` rejected tokens, and `77.50%`
  traced acceptance.
- Exact parity still failed against the same-posture accepted graph baseline:
  `baseline_match_all=false`.
- First diffs:
  - `natural_latency_plan`: output-token index `25`, oracle token `271`,
    accepted baseline token `198`.
  - `repetitive_kernel_notes`: output-token index `14`, oracle token `6126`,
    accepted baseline token `4752`.

Interpretation:

- This is the strongest negative speculation result so far. The proposer was
  an oracle over the accepted output trace, yet the speculative verifier path
  still changed the final token stream.
- Therefore the current bottleneck is not just proposer quality. The active
  suspect set is speculative scheduler accounting, KV/block-table state,
  graph-bucket state reuse, or accept/reject rollback behavior on XPU.
- No oracle speed number is valid until exact parity is restored. A high
  acceptance rate with changed output is a correctness failure, not a win.

Restore caveat:

- Accepted backend was restored again in tmux session
  `qwen36-tp4-accepted-restored-after-notes-retry-20260611b`.
- Backend `/health` and frontdoor `/health` pass.
- The short frontdoor smoke after the isolated oracle run still fails the
  arithmetic exact canary (`58` instead of `60`) while exact `OK`, copy,
  JSON, and repeat stability pass. Backend logs show continuing external
  `10.0.0.214` traffic during smoke attempts, so this is not a clean isolated
  quality measurement.
- Do not promote or publish a new quality result from this restore state until
  the frontdoor canary is rerun in an isolated window or replaced with a
  request-id token-trace baseline. The prior accepted restore before the
  isolated oracle probe did pass the same short frontdoor smoke.

Next diagnostic order:

1. Run an isolated oracle `k=1` graph probe.
   - If `k=1` fails exact parity, any speculative path is corrupting verifier
     state on this stack.
   - If `k=1` passes, the bug is likely in multi-token accept/reject,
     full-accept bonus, rollback, or graph bucket transitions.
2. Add per-row KV/block-table and `num_computed_tokens` accounting checks.
   The replay harness already found accounting bugs once; the next trace needs
   state before schedule, after verification, after rollback, and after output
   append.
3. Build a verifier-only shadow replay for the two isolated completion cases.
   The goal is to ask the same graph-mode verifier for the next token after
   each speculative row and prove whether the speculative row's replacement
   token matches no-spec verifier output.
4. Add a logit-hash or top-k checksum at the verification boundary for tiny
   probes. Full logits are too expensive for production, but a debug checksum
   over the chosen token and a small top-k set would pinpoint whether the
   verifier math or scheduler state diverges first.
5. Rerun restore quality in an isolated frontdoor window. The service is
   healthy, but the current last smoke is not clean enough for promotion.

Additional larger ideas to track:

1. First-class auxiliary proposer API for vLLM/XPU.
   - The current oracle was bolted onto the n-gram proposer. A cleaner path is
     a sidecar proposer API that returns draft token ids plus provenance, while
     the existing Quark verifier remains the only source of final accepted
     output.
   - This would let us test official FP8 MTP tensors, DFlash/EAGLE-like
     heads, and trained local proposers without pretending they are part of
     the Quark INT8 checkpoint.

2. Speculative-state minimizer for upstream.
   - Package the two isolated completion prompts, oracle trace, and failed
     token diffs into a tiny deterministic repro.
   - Strip it down until it fails on `k=1` or only on `k>1`; that determines
     whether this belongs to scheduler accounting or multi-token verifier
     rollback.
   - This is likely more valuable to vLLM/Intel than a large service log.

3. Route-aware verifier buckets.
   - Multi-token verifier bucket timings already show enough sublinear headroom
     for `>200 tok/s` if correctness is fixed.
   - Instead of fixed `k`, choose `k` from router/sequence features: small `k`
     for unstable long-context or high-divergence prompts, larger `k` when
     routed experts and recent token patterns are stable.

4. Memory-for-latency expert hotsets in a dedicated c1 lane.
   - Use the prompt-class route histograms to duplicate K32/K64 hot expert
     tiles or prepacked layouts only for a low-concurrency latency service.
   - This intentionally trades some 32K aggregate headroom for lower
     single-request decode latency, while the c48 production lane remains
     conservative.

5. Whole-token graph replay instead of kernel-by-kernel patching.
   - The AOT census suggests the easy one-op wrappers are exhausted.
   - A bolder path is one static decode command graph per bucket that covers
     attention/GDN, routed MoE, collectives, logits, and sampling handoff.
   - This is risky, but it targets host/runtime transitions directly.

6. Same-quality engine bakeoff with a shared oracle harness.
   - Test vLLM Quark W8A8, llama.cpp/SYCL Q8_0 or equivalent real 8-bit,
     OpenVINO/oneDNN GenAI, LLM-Scaler, and newer `vllm-xpu-kernels` branches
     under the same request-id token-trace gates.
   - Treat other engines as diagnostics unless they keep 32K context,
     production serving, and the same no-quality-loss bar.

7. Upstreamable B70/XPU repro bundle.
   - Bundle three standalone repros: oracle/speculative state corruption,
     routed W8A8 grouped-GEMM with real expert histograms, and graph-safe
     tiny hidden-size collectives.
   - Include exact shapes, oneAPI/vLLM commits, commands, expected behavior,
     and current B70 timings.
   - This may unlock help faster than deeper local-only patches.

## Oracle k=1 Probe

The next diagnostic tested whether the oracle failure is caused by multi-token
width/bonus logic or whether speculative decode is already unsafe at a single
draft token.

Artifacts:

- full-length clean isolated accepted-baseline failure:
  `data/qwen36-quark-int8-tp4-oracle-k1-clean-baseline-devicelost-20260611.json`
- short accepted graph baseline, p512/o32:
  `data/qwen36-quark-int8-tp4-oracle-k1-short-accepted-graph-20260611.json`
- short graph `k=1` oracle completions:
  `data/qwen36-quark-int8-tp4-oracle1-short-graph-completions-20260611.json`
- short graph `k=1` oracle spec summary:
  `data/qwen36-quark-int8-tp4-oracle1-short-graph-spec-summary-20260611.json`
  and
  `data/qwen36-quark-int8-tp4-oracle1-short-graph-spec-summary-20260611.md`
- restore smoke after the baseline device-lost:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-k1-devicelost-frontdoor-text-smoke-20260611.json`
- restore smokes after the short `k=1` oracle:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-oracle1-short-frontdoor-text-smoke-20260611.json`,
  `data/qwen36-quark-int8-tp4-accepted-restored-after-oracle1-short-frontdoor-text-smoke-rerun-20260611.json`,
  and
  `data/qwen36-quark-int8-tp4-accepted-restored-after-oracle1-short-frontdoor-text-smoke-rerun2-20260611.json`.

Clean full-length attempt:

- Both prior model backends were stopped before launching the clean accepted
  graph baseline on `18081`.
- The baseline reached `/health`, then the first p512/o128 controlled
  completion hit `UR_RESULT_ERROR_DEVICE_LOST` before writing the JSON trace.
- Primary error site:
  `vllm/v1/worker/block_table.py commit_block_table -> copy_to_gpu`.
- Secondary error site:
  `WorkerAsyncOutputCopy` waiting on an XPU event.
- This is a reliability failure independent of oracle quality. It also means
  the full p512/o128 `k=1` comparison was not completed.

Short p512/o32 `k=1` result:

- Baseline was captured from the freshly restored accepted graph backend.
- The `k=1` oracle backend on `18081` reached `/health` and completed both
  controlled completion cases.
- Scheduler trace: `15` rows, `2` requests, `15` drafted tokens, `14`
  accepted tokens, `1` rejected token, `93.33%` acceptance.
- Exact parity failed: `baseline_match_all=false`.
- First diffs:
  - `natural_latency_plan`: output-token index `14`, accepted baseline token
    `4779`, oracle result token `29541`.
  - `repetitive_kernel_notes`: output-token index `15`, accepted baseline
    token `16401`, oracle result token `11436`.

Interpretation:

- The failure is not a draft-width problem. Even a one-token oracle draft can
  perturb the final output stream.
- The old full-accept bonus/suppression theory is not sufficient either:
  `k=1` used no suppressed bonus rows and still diverged.
- The next useful speculation work is below proposer quality: scheduler state,
  block-table/KV state, graph-bucket state, sampled-token accounting, and
  verifier input construction.
- Do not spend more time on n-gram width sweeps, MTP speed runs, or sidecar
  proposer tuning until `k=1` exact parity is fixed.

Next state-debug ideas:

1. Add block-table/KV snapshots around each speculative scheduler row.
   - Capture request id, token ids, block table row, slot mappings,
     `num_computed_tokens`, `num_tokens_with_spec`, and output placeholders
     before schedule, before verifier forward, after verifier forward, after
     rollback, and after output append.
2. Add a verifier-only single-step replay for the failed p512/o32 rows.
   - For each row, reconstruct the no-spec context and ask the verifier for
     exactly one next token.
   - Compare that token with the speculative verifier's replacement/bonus
     token.
3. Run `k=1` with graph disabled only as a localization step.
   - If eager `k=1` also diverges, the bug is in scheduler/request accounting.
   - If eager passes and graph fails, inspect graph-bucket state reuse and
     `gpu_input_batch` metadata copies.
4. Reduce to one prompt and tiny output.
   - The current p512/o32 case is enough to fail, but a p64/o16 or p1/o8 repro
     would be much easier to send upstream.
5. Build a public-safe failure pack.
   - Include the two prompts, accepted token ids, oracle token ids, scheduler
     rows, and exact first-diff indices.
   - This should become the upstream vLLM/XPU speculative decode issue if local
     inspection does not quickly find the counter/state bug.

Restore/reliability status after this probe:

- Accepted backend was restored in tmux session
  `qwen36-tp4-accepted-restored-after-oracle1-short-20260611a`.
- Backend `/health` and frontdoor `/health` pass.
- A short frontdoor smoke immediately after the earlier device-lost restore
  passed all exact/copy/arithmetic/JSON/repeat checks.
- After the short `k=1` oracle restore, three short frontdoor smoke attempts
  were not quality-clean:
  - first: arithmetic failed (`58` instead of `60`), repeat passed.
  - second: arithmetic failed and repeat failed.
  - third: arithmetic passed, repeat failed with corrupted text.
- The frontdoor pause file is only checked at startup in the current script, so
  it cannot dynamically isolate smoke tests from live external traffic.
- Treat the service as up but not production-quality-clean until an isolated
  frontdoor window or request-id token trace proves repeat stability again.

Production/reliability follow-ups:

1. Add dynamic frontdoor pause/drain support.
   - The current static startup-only pause is not enough for safe backend
     experiments or isolated quality gates.
   - A dynamic pause should stop accepting new generation requests, expose
     active/queued counts, and let existing requests drain before backend
     replacement.
2. Add a local-only quality lane.
   - Run the exact same request defaults as the public frontdoor but bind to
     localhost and max-active `1`, so canaries are not mixed with external
     traffic.
3. Add post-restore repeat token tracing.
   - The repeat failures insert unrelated tokens/non-English fragments, which
     looks more like request/state contamination than ordinary arithmetic
     weakness.
   - Capture request ids and token ids for the failed repeat case before
     another speed experiment.

## Bigger Ideas Addendum After Oracle k=1

The current evidence says ordinary launch-flag tuning is unlikely to close the
gap from roughly `100 tok/s` to the user's `>200 tok/s` single-request target.
The `k=1` oracle failure also says speculation must be made verifier-correct
before it can be treated as a speed path. The next backlog should therefore
split into reliability isolation, exact correctness proof, and larger runtime
architecture bets.

Items to carry forward immediately:

1. Dynamic frontdoor pause/drain.
   - The frontdoor must reject new generation requests when a pause file is
     present, continue serving `/status`, and expose a drain endpoint so backend
     swaps and quality canaries can run without live-traffic contamination.
   - This is production infrastructure, not a speed feature, but it prevents
     false quality failures and unsafe backend replacement.

2. Local-only quality lane.
   - Add a localhost-bound frontdoor with the same model rewrite, thinking-off
     template kwargs, max-output defaults, and max-active `1`.
   - Use it for post-restore canaries, request-id token traces, and quality
     gates before exposing the backend through the public LAN route.

3. Post-restore repeat flight recorder.
   - Capture prompt, request id, scheduler id, token ids, timestamps, and
     response headers for the repeat-color failures.
   - The failure shape looks like request/state contamination; a semantic-only
     smoke is not enough.

4. Speculative verifier-state minimizer.
   - Turn the isolated `k=1` oracle failure into a tiny reproducible fixture:
     one prompt, short output, accepted token ids, oracle token ids, scheduler
     row state, block-table metadata, and first-diff token.
   - This is the most useful upstream artifact if local inspection does not
     quickly find the scheduler/KV/block-table bug.

5. Verifier-only single-step replay.
   - For each failed speculative row, reconstruct the no-spec context and ask
     the Quark verifier for exactly one next token.
   - If the verifier-only token matches the accepted baseline but the
     speculative verifier token does not, the bug is in speculative input state.
     If it also differs, look at graph-bucket reuse or request construction.

6. Exact logit/top-k checksum mode.
   - Add a debug-only checksum over the chosen token and a small top-k set at
     the verification boundary.
   - This narrows first divergence to either model math, verifier input state,
     sampling/logit post-processing, or output accounting.

External signals worth tracking:

- vLLM has had a specific Intel XPU speculative-decoding tracker:
  https://github.com/vllm-project/vllm/issues/26963
- Recent vLLM release notes show Intel XPU sampler/all-reduce work and CPU
  W8A16/W8A8 quant kernels, which are useful implementation references even if
  not directly usable on B70:
  https://github.com/vllm-project/vllm/releases
- The vLLM roadmap explicitly calls out redesigned speculative decode,
  scheduler-overhead reduction, expert parallelism, online expert movement, and
  communication/compute pipelining:
  https://github.com/vllm-project/vllm/issues/15735
- A recent CPU speculative-decoding issue reports `2.15x-2.72x` TPOT speedups
  in an older stack and severe regression/crashes in a newer one. Treat this as
  a signal to bisect scheduler/spec-decode logic, not as a CPU result to copy:
  https://github.com/vllm-project/vllm/issues/44191
- A Qwen3.6 MTP issue reports long-sequence speculative state corruption with
  invalid draft tokens despite low KV memory usage. This reinforces that any
  Qwen3.6 MTP/sidecar path needs long-context torture tests, not just short
  speed demos:
  https://github.com/vllm-project/vllm/issues/40756

Bigger, bolder experiments:

1. Verifier-preserving speculation ladder.
   - Start with the oracle `k=1` fixture. Only after exact parity is restored,
     test `k=2/4/8`, then real n-gram, then MTP/EAGLE/DFlash-style proposers.
   - The Quark W8A8 model remains the only final-output authority; draft models
     only propose.

2. Sidecar MTP from the official FP8 checkpoint.
   - The Quark checkpoint lacks MTP tensors, but the official FP8 snapshot has
     them. Test whether a small FP8/MTP sidecar can propose tokens while the
     Quark INT8 verifier accepts/rejects.
   - Quality risk is bounded by the verifier; implementation risk is state
     alignment and long-context stability.

3. Spec-decode algorithm/version bisect.
   - Compare the current vLLM speculative scheduler against the older code paths
     that reportedly delivered real TPOT speedups in CPU runs.
   - The goal is not CPU serving; it is finding whether a scheduler/accounting
     regression explains our XPU `k=1` oracle failure.

4. Hybrid TP/EP memory-for-latency lane.
   - Use route histograms to simulate moving from pure TP4 to a layout that
     duplicates hot experts or assigns expert shards for lower single-request
     latency.
   - If the simulation says latency can drop materially, build a dedicated c1
     lane separate from the aggregate c48 service.

5. Persistent route-window MoE.
   - Keep route maps, per-expert counts, activation scratch, and packed expert
     tiles resident across decode steps for stable route windows.
   - This attacks the repeated route/finalize overhead that primitive timing
     keeps exposing.

6. Whole-token command-list capture.
   - Capture an entire decode bucket, not individual kernels: GDN/attention,
     routed MoE, residual/all-reduce, logits, sampler handoff.
   - This is harder than kernel patches, but it targets host/runtime overhead
     directly.

7. XPU-native 8-bit engine shootout with one quality oracle.
   - Compare local vLLM, latest vLLM/XPU branches, OpenVINO/oneDNN GenAI,
     LLM-Scaler, ipex-llm/llama.cpp-style 8-bit paths, and any Qwen3.6-capable
     Intel-friendly runner under the same prompt set, 32K context requirement,
     token trace, and no-quality-loss gate.
   - Reject anything that wins speed by changing model class, context length,
     output tokens, or final token stream.

8. Static solo-decode service class.
   - Build a no-batching, fixed-shape, c1-only path for latency-sensitive
     requests. It can spend extra VRAM on duplicated hot data and static graph
     buckets because aggregate throughput is not its job.
   - Keep the accepted TP4 production lane as fallback.

9. Expert hotset VRAM trade study.
   - Quantify how much of the remaining B70 VRAM can be spent on K32/K64
     prompt-class hotsets, replicated dense projections, and prepacked W8A8
     tiles without harming 32K KV capacity.
   - Only build if memory math predicts a real latency win.

10. Upstream-first B70 repro packet.
    - Package three standalone repros: speculative `k=1` state corruption,
      real-route W8A8 MoE timing/hotset overlap, and graph-safe all-reduce or
      command-list overhead.
    - Include exact commands, oneAPI/vLLM commits, shapes, expected token ids,
      and current B70 timings so Intel/vLLM maintainers can reproduce without
      the full service.

11. Localmaxxing race harness.
    - Automate benchmark payload generation, dry-run validation, quality-gate
      attachment, and public submission for only approved rows.
    - Keep it useful for comparison too: pull nearby Qwen/B70 rows before each
      new speed push and record what class of engine is winning.

Priority order from here:

1. Implement dynamic pause/drain and local-only quality lane so future canaries
   are isolated.
2. Build the `k=1` verifier-state minimizer and verifier-only replay.
3. If `k=1` can be made exact, re-open verifier-preserving speculation. If it
   cannot, switch the main speed path to persistent MoE/command-list/static
   solo-decode work while preparing the upstream repro packet.

## Dynamic Frontdoor Pause and Local Quality Lane

Implemented the first production/reliability follow-up from the oracle notes:

- `scripts/openai-lan-frontdoor.py`
  - Pause file is now dynamic instead of startup-only.
  - `/status` and `/frontdoor/status` report `pause_file`, `paused`,
    `drain_timeout_s`, model rewrite settings, output-token defaults, and
    chat-template kwargs.
  - New generation requests return HTTP `503` with
    `error.type=frontdoor_paused` while the pause file exists.
  - Existing active requests are not interrupted.
  - `/drain` and `/frontdoor/drain` wait for active/queued generations to reach
    zero or return a drain timeout.
- `scripts/run-openai-frontdoor-profile.sh`
  - Exposes `FRONTDOOR_DRAIN_TIMEOUT_S`.
  - Keeps the request defaults that make the public OpenAI route match the
    no-thinking Qwen quality posture.
- `scripts/run-qwen36-local-quality-frontdoor.sh`
  - Adds a localhost-only quality lane on `127.0.0.1:18082`.
  - Defaults to max-active `1`, backend `127.0.0.1:18080`, no-thinking chat
    template kwargs, model rewrite to `qwen36-35b-a3b-fp8`, and a separate
    `/tmp/qwen36-local-quality-frontdoor.pause` pause file.

Validation:

- `python3 -m py_compile scripts/openai-lan-frontdoor.py`
- `bash -n scripts/run-openai-frontdoor-profile.sh scripts/run-qwen36-local-quality-frontdoor.sh`
- Local lane status on `127.0.0.1:18082` reported:
  - `paused=false`
  - `max_active_generations=1`
  - `drain_timeout_s=300.0`
  - `pause_file=/tmp/qwen36-local-quality-frontdoor.pause`
  - model rewrite and no-thinking defaults enabled
- Dynamic pause test:
  - touched `/tmp/qwen36-local-quality-frontdoor.pause`
  - POST `/v1/chat/completions` returned HTTP `503`
  - response `error.type=frontdoor_paused`
  - generation counter stayed at `0`, proving the paused request did not enter
    the backend queue.
- Drain test:
  - after clearing the pause file, `/frontdoor/drain` returned
    `drained=true`, `waited_s=0.0`, `active=0`, `queued=0`.

Local quality-lane canaries:

- First short local quality smoke:
  `data/qwen36-quark-int8-tp4-local-quality-frontdoor-text-smoke-20260611.json`
  - `pass_all=false`
  - arithmetic failed: expected `60`, observed `58`
  - repeat stability passed four runs
- Second short local quality smoke:
  `data/qwen36-quark-int8-tp4-local-quality-frontdoor-text-smoke-rerun-20260611.json`
  - `pass_all=false`
  - arithmetic passed
  - repeat stability failed: first repeat emitted
    `伪“f”“f”“f”“f”“f”“f”“f whiskey whiskey whiskey whiskey“f”“f”“`
    instead of `blue, green, orange, red`

Interpretation:

- The local-only frontdoor path works and can isolate future tests from public
  LAN request handling.
- The current accepted backend restore is still not quality-clean. Its failure
  pattern persists even under localhost-only, max-active-1 access.
- Do not publish new speed or quality results from this backend state.
- Next reliability action should be a clean accepted-backend restore followed
  by the local quality lane, then the public frontdoor, before any more
  speculative or kernel speed work.

## Paused Public Frontdoor and Restore Incident

After validating the dynamic pause path, the public frontdoor on port `8000`
was restarted under the new code and intentionally paused via
`/tmp/qwen36-35b-a3b-fp8-requant-frontdoor-not-paused` before backend restore.

Public-frontdoor validation:

- `/frontdoor/status` reported `paused=true`, `active=0`, `queued=0`,
  `max_active_generations=48`.
- A public POST `/v1/chat/completions` while paused returned HTTP `503` with
  `error.type=frontdoor_paused`.
- `total_generation_requests` remained `0`, proving paused public traffic did
  not enter the backend queue.
- `/frontdoor/drain` returned `drained=true`, `active=0`, `queued=0`.

Clean graph restore attempts:

1. `qwen36-tp4-accepted-clean-restore-after-frontdoor-pause-20260611b`
   - Log:
     `/tmp/qwen36-quark-int8-tp4-accepted-clean-restore-after-frontdoor-pause-20260611b.log`
   - Backend reached `/health` after `52s`.
   - The first local quality-lane generation returned HTTP `500`.
   - Failure site: `block_table.copy_to_gpu` in
     `vllm/v1/worker/block_table.py`.
   - Error: `UR_RESULT_ERROR_DEVICE_LOST`.
   - Scheduler dump showed `speculative_config=None`,
     `prompt_token_ids_len=17`, `step_counter=0`, and
     `scheduled_spec_decode_tokens={}`.

2. `qwen36-tp4-accepted-clean-restore-retry2-paused-20260611c`
   - Log:
     `/tmp/qwen36-quark-int8-tp4-accepted-clean-restore-retry2-paused-20260611c.log`
   - Backend reached `/health` after `63s`.
   - The first local quality-lane generation again returned HTTP `500`.
   - Same failure class: `UR_RESULT_ERROR_DEVICE_LOST` at
     `block_table.copy_to_gpu`, again with `speculative_config=None` and
     `step_counter=0`.

Fallback eager/no-graph attempt:

- Session: `qwen36-tp4-eager-fallback-paused-20260611d`.
- Launch overrides:
  - `XPU_GRAPH=0`
  - `VLLM_XPU_ENABLE_XPU_GRAPH=0`
  - `VLLM_XPU_FORCE_GRAPH_WITH_COMM=0`
  - `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=0`
  - `VLLM_EXTRA_ARGS='--enforce-eager'`
- Log:
  `/tmp/qwen36-quark-int8-tp4-eager-fallback-paused-20260611d.log`
- Backend reached `/health` after `50s` and remained alive through two short
  local quality-lane canaries.
- Artifacts:
  `data/qwen36-quark-int8-tp4-eagerfallback-local-quality-frontdoor-text-smoke-r8-20260611.json`
  and
  `data/qwen36-quark-int8-tp4-eagerfallback-local-quality-frontdoor-text-smoke-rerun-r8-20260611.json`.
- Both canaries:
  - `pass_all=false`
  - `baseline_match_all=true`
  - exact `OK`, copy phrase, and JSON passed
  - arithmetic failed with `58` instead of expected `60`
  - repeat stability passed `8/8`

Current safety state after this incident:

- Public frontdoor remains paused.
- Eager fallback backend is alive on `127.0.0.1:18080`, but it is not
  quality-clean and should not be exposed as a production result.
- The dynamic pause work prevented external traffic from hitting either failed
  graph restore.

Interpretation and next actions:

- The repeated graph restore failure is not speculative decode; the scheduler
  dump shows no speculative config and failure on the first prefill request.
- `/health` is not sufficient after restore. The required restore gate is now:
  backend health, first-generation smoke, local quality-lane canary, then
  public-frontdoor canary.
- Eager/no-graph avoids the device-lost failure in this run but does not pass
  the exact quality suite.
- Next work should inspect why the accepted graph restore now device-losts at
  `block_table.copy_to_gpu` on the first request. Candidate checks:
  1. stale Level Zero/oneCCL state after repeated graph/spec experiments,
  2. block-table copy path or NHD KV layout regression,
  3. graph cache corruption in the accepted cache root,
  4. current local vLLM changes from speculative instrumentation affecting
     non-spec first prefill,
  5. XPU device reset requirement after repeated `UR_RESULT_ERROR_DEVICE_LOST`.

## Fresh Graph Cache Restore, Paused-Local Gate, and Larger Backlog

Added after the fresh-cache restore recovered quality and after another external
scan of Qwen3.6, vLLM/XPU, B70, and Localmaxxing signals.

Runtime state and quality gates:

- The stale accepted graph cache path was no longer trustworthy after repeated
  graph/spec/device-lost experiments. Two restores reached `/health` but
  device-losted on the first request at `block_table.copy_to_gpu`.
- A fresh graph-cache root recovered the accepted graph path:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-freshrestore-20260611d`.
- Fresh-cache backend session:
  `qwen36-tp4-graph-freshcache-paused-20260611d`.
- Fresh-cache backend log:
  `/tmp/qwen36-quark-int8-tp4-graph-freshcache-paused-20260611d.log`.
- Backend reached `/health` after `131s`.
- Localhost quality lane on `127.0.0.1:18082` passed both:
  - `data/qwen36-quark-int8-tp4-freshcache-local-quality-frontdoor-text-smoke-r8-20260611.json`
    - `pass_all=true`
    - `baseline_match_all=true`
  - `data/qwen36-quark-int8-tp4-freshcache-local-quality-frontdoor-full-r8-20260611.json`
    - `pass_all=true`
    - `baseline_match_all=true`
    - long-context needle passed
- An unpaused public-frontdoor full r8 attempt on port `8000` failed:
  `data/qwen36-quark-int8-tp4-freshcache-public-frontdoor-full-r8-20260611.json`.
  - `pass_all=false`
  - `baseline_match_all=true`
  - exact arithmetic failed: expected `60`, observed `58`
  - repeat and long-context were otherwise clean
  - frontdoor logs showed external `10.0.0.214` generation traffic interleaved
    with the canary, so this is treated as a contaminated public-isolation
    failure, not as a fresh-cache backend rejection.

Frontdoor improvement:

- `scripts/openai-lan-frontdoor.py` now supports
  `FRONTDOOR_PAUSE_ALLOW_LOCAL=1` (default on).
- While the dynamic pause file exists:
  - non-loopback generation requests still return HTTP `503` /
    `frontdoor_paused`,
  - loopback generation requests may pass through the real public route for
    local canaries,
  - status reports `pause_allow_local`.
- `scripts/run-openai-frontdoor-profile.sh` exports
  `FRONTDOOR_PAUSE_ALLOW_LOCAL`.
- The public frontdoor was restarted under the local-bypass code in session
  `qwen36-public-frontdoor-paused-localbypass-20260611b`.
- Paused-local public full r8 passed through `http://127.0.0.1:8000`:
  `data/qwen36-quark-int8-tp4-freshcache-public-frontdoor-pausedlocal-full-r8-20260611.json`.
  - `pass_all=true`
  - `baseline_match_all=true`
  - exact arithmetic/copy/JSON/OK passed
  - repeat stability passed `8/8`
  - long-context needle passed
- The temporary local quality-lane session
  `qwen36-local-quality-frontdoor-freshcache-20260611f` was stopped after the
  public paused-local gate passed.
- The public frontdoor was then unpaused. Post-gate status included:
  - `paused=false`
  - `pause_allow_local=true`
  - `active_generations=0`
  - `queued_generations=0`
  - backend `/health` returned HTTP `200`
  - `total_generation_requests` is live and should not be used as a static
    canary value after unpause

New restore policy:

1. Treat graph cache roots as disposable after `UR_RESULT_ERROR_DEVICE_LOST`,
   vLLM scheduler instrumentation changes, XPU kernel changes, or graph/env
   flag changes.
2. Prefer fresh, content-addressed cache roots keyed by model snapshot, vLLM
   commit, local patchset, xpu-kernel commit, oneAPI/driver stack, and graph
   env flags.
3. `/health` is not a restore proof. Required gate:
   backend health, first-generation smoke, localhost quality lane, paused-local
   public frontdoor full r8, then unpause.
4. Public canaries should use the paused-local bypass so LAN traffic cannot
   contaminate deterministic quality checks.

External signals checked:

- Hugging Face Qwen3.6 FP8 model card says the official FP8 artifact uses
  fine-grained FP8 with block size 128 and is intended to be compatible with
  vLLM/SGLang/KTransformers. This reinforces that official FP8 remains a valid
  reference path, but the current accepted service still uses the Quark W8A8
  INT8 verifier for quality claims.
  Source: https://huggingface.co/Qwen/Qwen3.6-35B-A3B-FP8
- vLLM's Qwen3.6 recipe describes the model as `35B total / 3B active` with
  `256` experts, `8` routed plus `1` shared, and shows official MTP speculative
  launch syntax. This keeps MTP/DFlash-style work on the list, but our local
  Quark verifier must pass exact token parity before any speed claim.
  Source: https://recipes.vllm.ai/Qwen/Qwen3.6-35B-A3B
- vLLM's Intel Arc Pro B-Series write-up highlights the same MoE bottleneck we
  keep measuring: per-iteration expert GEMM launches, gate dependency stalls,
  and idle device time. Their persistent zero-gap MoE design and dynamic
  balancing are directly relevant to a no-quality-loss backend rewrite.
  Source: https://vllm.ai/blog/2025-11-11-intel-arc-pro-b
- The public dual-B70 vLLM issue documents GP faults / BCS resets under TP and
  FP8 on a host stack different from Intel's validation BOM, plus stable
  results under some collective/graph variants. This supports treating host
  stack and XCCL/Level Zero matrix testing as an optimization/reliability item,
  not just an ops chore.
  Source: https://github.com/vllm-project/vllm/issues/41663
- Intel's current Xe GPU enablement write-up says Intel is upstreaming vLLM,
  SGLang, PyTorch, and FusedMoE paths for Arc Pro B70/B65-class hardware. That
  makes a latest-XPU-branch shootout and upstream repro packet worth doing.
  Source: https://huggingface.co/blog/MatrixYao/intel-gpu
- vLLM block-table docs confirm the block-table object owns host/device
  tensors, block sizing, and pinned-memory decisions. Since our restore failures
  hit `block_table.copy_to_gpu`, a resident/precommitted block-table experiment
  is a reasonable reliability and latency target.
  Source: https://docs.vllm.ai/en/v0.19.1/api/vllm/v1/worker/block_table/
- Localmaxxing refresh artifacts:
  - `data/localmaxxing-qwen36-quark-b70-pausedlocal-refresh-20260611.json`
  - `data/localmaxxing-qwen-b70-vllm-pausedlocal-refresh-20260611.json`
  - exact Quark W8A8 INT8/B70 row remains
    `cmq8yhxvo001ipb0149aoa79o` at `99.43 tok/s` output, batch `1`,
    context `32768`
  - broader B70/vLLM/Qwen rows still put the current Quark run at the top of
    the visible B70 Qwen3.6 35B-class set, but nowhere near the `200 tok/s`
    single-request target.

New things to try next, ordered by risk/return:

1. Fresh-cache discipline and automatic cache invalidation.
   - Build a small launcher helper that creates graph-cache roots from a hash of
     model snapshot, vLLM commit, local patches, xpu-kernel build id, driver
     versions, graph flags, and key env vars.
   - On first-generation `block_table.copy_to_gpu` device-lost, mark that cache
     root bad and force a cold recapture before another restore attempt.
   - Quality impact: none; this is reliability isolation.

2. Resident block-table / KV-slot precommit experiment.
   - The failing path is host-to-device block-table copy before first prefill.
     Test whether a fixed c1 lane can pre-allocate and precommit request slots,
     block tables, and KV metadata on XPU, then only update a small device-side
     cursor per request.
   - Success criterion: no token changes, lower TTFT variance, and no
     first-request device-lost after cold restore.

3. Static c1 decode lane.
   - Build a latency lane with fixed shapes, fixed max output buckets, no
     public batching, and no scheduler complexity beyond one active request.
   - It can spend more VRAM on duplicated hot data, fixed block tables, and
     captured decode command lists because aggregate throughput is not its job.
   - Keep the current c48 frontdoor as the aggregate lane and fallback.

4. Persistent zero-gap MoE for Qwen3.6 routed layers.
   - Use the vLLM Intel Arc blog design as the target: one persistent kernel
     loop, dynamic group balancing, and no per-expert launch gaps.
   - Start from our route-capture histograms and Qwen3.6 shapes, not synthetic
     equal-route workloads.
   - Candidate implementations: extend current XPU fused-MoE, prototype
     oneDNN/BRGEMM batched kernels, or upstream a B70-specific persistent
     grouped-GEMM path.

5. Route-bucket expert replication.
   - Spend spare VRAM on K32/K64 hot expert tiles for prompt-class buckets.
   - The route-overlap work showed K64 covers about `88-90%` of weighted expert
     assignments in high-signal layers; test whether duplicating those tiles or
     pinning them per rank cuts TP communication and routed-MoE latency.
   - Gate on full quality, 32K KV capacity, and p512/o512 single-request speed.

6. Verifier-only speculation repair before any MTP speed claim.
   - Current oracle `k=1` failure proves the scheduler/KV/spec path can perturb
     final output even with perfect draft tokens.
   - Build a minimal verifier-only fixture that replays one accepted token ahead
     with exact KV/block-table state checksums. No n-gram/MTP timing until this
     is exact.
   - If exact, reopen MTP/DFlash/DDTree with the Quark verifier as final
     authority.

7. Learned same-tokenizer proposer, not lower-bit verifier.
   - Train or distill a small Qwen3.6-tokenizer proposer from accepted Quark
     traces, but never allow it to emit final tokens without Quark verification.
   - This can be faster than forcing official FP8 MTP tensors into the Quark
     checkpoint layout, and quality remains verifier-bound.

8. True 8-bit engine shootout.
   - Compare current vLLM/XPU, latest vLLM XPU branches, LLM-Scaler, OpenVINO
     GenAI/oneDNN, SGLang if Qwen3.6/XPU works, and llama.cpp SYCL/Vulkan
     8-bit paths.
   - Same model family, same 32K requirement, same token-trace quality oracle.
   - Reject any row that wins by using 4-bit, shorter context, fewer output
     tokens, different base model, or nonmatching final token stream.

9. Host-stack/BOM A/B.
   - Test the stack closer to Intel's validated B-Series image/BOM on a spare
     disk: OS/kernel, GuC firmware, compute-runtime, oneCCL, oneAPI, and
     `vllm-xpu-kernels` versions.
   - Goal is not just stability; it may unlock faster collective or graph paths
     without code changes.

10. Whole-token Level Zero command-list capture.
    - Capture complete decode buckets: GDN/attention, MoE, residual/all-reduce,
      logits, sampling handoff.
    - This is a bigger systems bet than a kernel tweak, but it attacks host
      submit/sync overhead directly while preserving arithmetic.

11. Production dual-lane router.
    - Keep c48 aggregate throughput service conservative.
    - Add a c1 latency lane only after it passes the paused-local full r8 gate.
    - Router sends deterministic canaries and high-risk requests to the
      conservative lane; fast lane automatically falls back on any quality or
      health anomaly.

12. Upstreamable B70 repro packs.
    - Prepare three minimal packs:
      1. `block_table.copy_to_gpu` first-generation device-lost with stale cache
         versus fresh cache,
      2. oracle `k=1` speculative output drift with exact token fixtures,
      3. route-window MoE timing/hotset data for Qwen3.6 shapes.
    - Include exact launch commands, versions, env flags, expected outputs, and
      Localmaxxing row IDs so maintainers can reproduce and compare.

Current priority after this addendum:

1. Keep the fresh-cache accepted graph service online and quality-gated.
2. Commit the paused-local bypass and new artifacts.
3. Build the fresh-cache hash/invalidation helper.
4. Start the resident block-table/static-c1 lane experiments.
5. In parallel, reduce oracle `k=1` speculation drift into an upstreamable
   state-checksum fixture.

## Oracle k=1 Drift Fixture and Bigger Bets

The oracle `k=1` short graph run is now reduced into a compact token-parity
fixture:

- `scripts/reduce-qwen36-oracle-fixture.py`
- `data/qwen36-quark-int8-tp4-oracle-k1-drift-fixture-20260611.json`
- `data/qwen36-quark-int8-tp4-oracle-k1-drift-fixture-20260611.md`
- `data/qwen36-quark-int8-tp4-oracle-k1-drift-replay-20260611.json`
- `data/qwen36-quark-int8-tp4-oracle-k1-drift-replay-20260611.md`

Result:

- Exact match: `false`
- Mismatches: `2/2`
- Scheduler rows: `15`
- Draft tokens: `15`
- Accepted draft tokens: `14`
- Rejected draft tokens: `1`
- Accept rate: `93.33%`
- Replay accounting mismatches: `0`
- Suppressed-follow-up mismatches: `0`

Case-level diagnosis:

- `natural_latency_plan`
  - first diff output index: `14`
  - accepted token: `29541` / ` reliability`
  - candidate token: `4779` / ` memory`
  - scheduler row: `7`
  - emission role: `verifier_bonus_after_full_accept`
  - scheduled: `[11]`
  - generated: `[11, 4779]`
- `repetitive_kernel_notes`
  - first diff output index: `15`
  - accepted token: `11436` / ` hardware`
  - candidate token: `16401` / ` decode`
  - scheduler row: `15`
  - emission role: `replacement_after_reject`
  - scheduled: `[11436]`
  - generated: `[16401]`

The important conclusion is that the blocker is not proposer quality. Even a
perfect one-token oracle path perturbs final output. That makes all DFlash,
MTP, n-gram, and learned-proposer speed claims invalid until this fixture is
exact. The likely failure zone is speculative verifier state equivalence:
GDN/attention/MoE KV state, block-table state, token-position accounting, or
the multi-token verifier step that emits accepted draft plus the bonus/reject
token.

Localmaxxing refresh:

- `data/localmaxxing-qwen36-30b-top-continue-20260611.json`
- The public `Qwen3.6`/30B-class rows above `200 tok/s` are mostly DFlash,
  MTP/speculation, different quantization such as NVFP4/FP8, or different
  hardware/runtime stacks.
- This supports pursuing verifier-preserving speculation, but only after the
  oracle fixture passes.

Hard gates for future speculation:

1. This oracle `k=1` fixture must be exact before any speculation timing.
2. A patch must pass paused-local public full r8 quality after fixture parity.
3. Speed rows must include request-id token traces and scheduler traces.
4. Any Localmaxxing result must clearly state whether speculation was enabled.

Things to try next:

1. Disable verifier bonus emission for oracle `k=1`, but recompute the next
   token from the final visible token state instead of only hiding the bonus
   token. The previous no-bonus hook proved hiding is not a real rewind.
2. Add lightweight state fingerprints at speculative row boundaries:
   request position, block table slice, KV block ids, selected GDN state shapes,
   and output-token counters. The goal is to locate the first state difference
   before comparing logits.
3. Add a verifier-only "serial fallback inside speculative scheduler" mode:
   run through the speculative scheduling code path but commit exactly one
   verified token per step. If this drifts, the scheduler/block-table path is
   guilty; if it passes, the multi-token verifier row is guilty.
4. Build a tiny upstream repro from the two-case fixture with no frontdoor and
   no public traffic. This is small enough for vLLM/XPU maintainers to inspect.
5. Re-run the fixture on eager mode, graph mode with a fresh cache, and graph
   mode after cache restore. If only restored graph drifts, graph cache or
   stale device state is implicated; if all drift, scheduler/spec logic is.
6. Try `k=0` or "draft scheduled but ignored" instrumentation to see whether
   merely scheduling draft tokens mutates block-table/KV state.
7. Compare logits for the exact first divergent position through
   `/generative_scoring` and an internal KV-resident path. The HTTP scoring
   probe showed verifier math is correct for the visible prefix; the remaining
   question is whether the internal speculative prefix is actually the same.

Bigger, bolder ideas worth keeping on the board:

1. A first-class auxiliary proposer API for vLLM/XPU. Instead of overloading
   n-gram/MTP internals, make a clean contract: proposer suggests token ids,
   Quark verifier owns acceptance, state updates, and final emissions.
2. A Quark-trace-trained same-tokenizer proposer. Train a small draft model or
   adapter on our accepted traces and request classes. Quality remains bound to
   the Quark INT8 verifier, but acceptance could be much better than n-gram.
3. Self-speculative shallow verifier branch. Reuse early Qwen3.6 layers or a
   low-depth side branch as the draft source, but keep final tokens verifier
   exact. This may avoid the official FP8 MTP layout mismatch.
4. Static solo latency lane with duplicate memory. Use spare B70 memory for a
   c1-only service: fixed block tables, fixed graph buckets, duplicated hot
   experts, and no aggregate batching compromises.
5. Persistent zero-gap MoE with real route windows. The Intel B70 blog points
   at per-expert launch gaps and idle device time; a persistent routed-MoE loop
   using captured Qwen3.6 route histograms is the biggest non-speculation win.
6. Memory-for-latency expert hotsets. Duplicate K32/K64 route-bucket expert
   tiles across ranks or pre-place them near the rank that consumes them. Spend
   VRAM to reduce routed-MoE communication and fetch latency.
7. Hybrid TP/EP simulator before implementation. Simulate expert locality and
   communication for TP4, TP2+EP2, and layer-local expert replication using
   the existing route captures. Implement only the layout with a credible
   roofline.
8. Whole-token Level Zero command-list replay. Capture an entire decode bucket,
   including attention/GDN, MoE, all-reduces, logits, and sampling handoff, to
   attack host-submit overhead without changing arithmetic.
9. Latest-stack 8-bit shootout. Compare current vLLM/XPU against latest
   vLLM XPU branches, LLM-Scaler, OpenVINO GenAI/oneDNN, and SGLang if it
   supports this model/hardware. Same 32K context, same INT8/W8A8-or-better
   quality rule, same token traces.
10. Intel-validated BOM boot disk. Test the closest available Intel B-Series
    validation stack: kernel, firmware, compute-runtime, oneAPI, oneCCL, IPEX,
    and vllm-xpu-kernels. A software-stack jump may beat another local patch.
11. Speculative verifier bucket kernels. If oracle parity is repaired, optimize
    verifier buckets directly for `k=3/5/6/8`, because prior bucket timing
    showed the model has enough sublinear headroom to exceed `200 tok/s`.
12. Production dual-lane router with automatic baseline fallback. Keep the
    conservative lane as the quality authority and add an aggressive latency
    lane only when it continuously passes token-trace canaries.
13. Public bounty-quality repro packet. Package the B70/Qwen3.6 artifacts:
    first-generation `block_table.copy_to_gpu` device-lost, oracle `k=1`
    drift, route-window MoE histograms, launch commands, versions, and
    Localmaxxing row IDs. This could attract upstream attention faster than
    local-only debugging.

Updated priority:

1. Keep the fresh-cache accepted service stable and quality-gated.
2. Commit this fixture and note update.
3. Turn the oracle `k=1` fixture into an automated regression gate.
4. Add speculative state fingerprints and a serial-fallback-inside-spec mode.
5. In parallel, begin static c1 and persistent-MoE work because they do not
   depend on speculative correctness.

## Oracle Fixture Gate and Ignore-Drafts Diagnostic

The reduced oracle fixture now has an executable checker:

- `scripts/check-qwen36-oracle-fixture.py`

Current known-drift gate:

```bash
python3 scripts/check-qwen36-oracle-fixture.py \
  --fixture data/qwen36-quark-int8-tp4-oracle-k1-drift-fixture-20260611.json \
  --replay-json data/qwen36-quark-int8-tp4-oracle-k1-drift-replay-20260611.json \
  --mode known-drift \
  --expected-mismatches 2 \
  --expected-roles verifier_bonus_after_full_accept,replacement_after_reject
```

This passed with:

- `ok=true`
- `case_count=2`
- `mismatch_count=2`
- roles:
  - `verifier_bonus_after_full_accept`
  - `replacement_after_reject`

Future repaired speculation gate:

```bash
python3 scripts/check-qwen36-oracle-fixture.py \
  --fixture <new-reduced-fixture.json> \
  --replay-json <new-replay.json>
```

Default mode is `exact`; it requires:

- `exact_match_all=true`
- `mismatch_count=0`
- replay rows parse cleanly
- all scheduler requests join to token cases
- replay accounting mismatch count is `0`
- suppressed-follow-up mismatch count is `0`

New diagnostic patch:

- `patches/vllm-qwen36-spec-ignore-drafts-diagnostic-20260611.patch`
- Local vLLM tree has the same change applied in
  `/home/steve/src/vllm/vllm/v1/core/sched/scheduler.py`.
- `scripts/launch-qwen36-quark-int8-ngram-trace.sh` now accepts
  `IGNORE_DRAFTS=1`.

New env:

```bash
VLLM_XPU_SPEC_DECODE_IGNORE_DRAFTS=1
```

Intent:

- Keep speculative config and proposer plumbing active.
- Do not feed draft tokens into the verifier.
- Schedule only the normal non-spec verifier token for that request.
- Clear pending draft tokens after the step as usual.
- This separates scheduler/config side effects from actual speculative-token
  execution and commit/rollback behavior.

Interpretation matrix for the isolated oracle run:

1. `IGNORE_DRAFTS=1` passes exact parity.
   - The generic spec-enabled scheduler/config path is probably not enough to
     corrupt output.
   - The failure is likely in speculative token execution, GDN/KV state update,
     multi-token verifier bucket behavior, or commit/rollback of the extra
     verifier/replacement token.
   - Next: add state fingerprints around speculative rows and repair actual
     draft execution.
2. `IGNORE_DRAFTS=1` still drifts.
   - Mere speculative scheduling/proposer plumbing can perturb state.
   - Next: inspect request counters, block table allocation, lookahead blocks,
     and request `spec_token_ids` lifetime even when drafts are not executed.
3. `IGNORE_DRAFTS=1` device-losts.
   - The instability is not limited to speculative model math.
   - Next: repeat with a fresh graph cache, then eager mode, and include the
     result in the upstream `block_table.copy_to_gpu`/graph-cache repro packet.

Recommended isolated run when public traffic can be paused:

```bash
PORT=18081 \
TAG=oracle1-ignore-drafts-graph \
NUM_SPECULATIVE_TOKENS=1 \
PROMPT_LOOKUP_MIN=2 \
PROMPT_LOOKUP_MAX=5 \
ORACLE_TRACE=data/qwen36-quark-int8-tp4-oracle-k1-short-accepted-graph-20260611.json \
SPEC_TRACE_FILE=/tmp/qwen36-oracle1-ignore-drafts-graph-spec-trace-20260611.jsonl \
IGNORE_DRAFTS=1 \
scripts/launch-qwen36-quark-int8-oracle-trace.sh
```

Then capture completions for the two short oracle prompts, replay the scheduler
trace, reduce the fixture, and run the checker in exact mode. Do not benchmark
or submit any speculation speed row until the exact gate passes.

Validation for this tracking step:

- `python3 -m py_compile scripts/check-qwen36-oracle-fixture.py scripts/reduce-qwen36-oracle-fixture.py`
- `bash -n scripts/launch-qwen36-quark-int8-ngram-trace.sh scripts/launch-qwen36-quark-int8-oracle-trace.sh`
- known-drift gate command above
- `/home/steve/.venvs/vllm-xpu/bin/python -m py_compile vllm/v1/core/sched/scheduler.py`
- `git apply --reverse --check patches/vllm-qwen36-spec-ignore-drafts-diagnostic-20260611.patch`

## Force-Block FP8 MTP Loader Result

Followed up the MTP asset inspection by testing the official Qwen3.6 FP8 MTP
sidecar directly as a proposer while keeping the current Quark W8A8 INT8 model
as the target/verifier.

Launch shape:

```bash
VLLM_QWEN35_MTP_FORCE_FP8_BLOCK=1 \
VLLM_EXTRA_ARGS='--speculative-config {"method":"mtp","model":"/mnt/fast-ai/llm-cache/hf/hub/models--Qwen--Qwen3.6-35B-A3B-FP8/snapshots/95a723d08a9490559dae23d0cff1d9466213d989","num_speculative_tokens":1,"draft_tensor_parallel_size":4}' \
./scripts/launch-qwen36-quark-int8-accepted.sh
```

Positive result:

- `VLLM_QWEN35_MTP_FORCE_FP8_BLOCK=1` gets the FP8 MTP sidecar past the earlier
  `w2_weight_scale_inv` style loader failure.
- The service loaded both target and drafter models, selected block-FP8 XPU
  linear kernels for the drafter, and completed graph capture.
- Loaded sidecar memory was still small enough for the 32K target:
  `Model loading took 8.79 GiB`, with reported GPU KV capacity around
  `1.74M` tokens versus roughly `2.05M` on the accepted non-MTP service.

Negative result:

- The first mixed chat/completions probe fatally failed after the MTP load. That
  run included overlapping requests and showed a target-model compile/autotune
  failure, so it was not a clean final diagnosis.
- The clean solo completions probe also failed, before any scheduled MTP draft
  tokens appeared:
  - scheduler dump had `scheduled_spec_decode_tokens={}`
  - request had `prompt_token_ids_len=502`
  - worker failed in `block_table.copy_to_gpu`
  - Level Zero error: `UR_RESULT_ERROR_DEVICE_LOST`
- A follow-up shutdown path then reported `UR_RESULT_ERROR_OUT_OF_RESOURCES`.

Artifacts:

- `data/qwen36-quark-int8-tp4-mtp1-fp8sidecar-forceblock-mixed-crash-20260611a.txt`
- `data/qwen36-quark-int8-tp4-mtp1-fp8sidecar-forceblock-modelinput-trace-mixed-crash-20260611a.jsonl`
- `data/qwen36-quark-int8-tp4-mtp1-fp8sidecar-forceblock-spec-trace-mixed-crash-20260611a.jsonl`
- `data/qwen36-quark-int8-tp4-mtp1-fp8sidecar-forceblock-solo-crash-20260611a.txt`

Decision: do not count force-block FP8 MTP as a speed or quality win yet. It is
a loader breakthrough and a useful repro, not a production candidate. The next
MTP work should isolate whether the device-lost trigger is memory pressure,
graph-capture coverage, sidecar block table/KV sizing, or a generic
speculative-config first-request issue.

Immediate force-block MTP diagnostics to try later:

1. Relaunch MTP with lower `gpu_memory_utilization` such as `0.90` and `0.85`.
   If the solo request stops device-losting, treat this as a memory/headroom
   issue before testing speed.
2. Relaunch MTP with `max_num_seqs=1` and lower `max_num_batched_tokens` for a
   pure single-user latency lane. This should determine whether scheduler/KV
   allocation size is the trigger.
3. Relaunch MTP with target eager/no-graph, or with a capture list that includes
   the exact verifier bucket sizes MTP will schedule. This is diagnostic only;
   it will likely be too slow, but it can separate graph capture failures from
   MTP math failures.
4. Try `max_model_len=16384` only as a temporary isolation run. It is not the
   production target, but it can prove whether 32K KV headroom is the reason the
   sidecar first request loses the device.
5. Add first-request block-table logging around the MTP sidecar path:
   block ids, lookahead blocks, block table rows copied, and per-rank values.
   The crash point is early enough that a small log may make the repro upstream
   useful.
6. If any safer MTP launch reaches generation, run exact canary hashes,
   repeat64, long-context needle, and the oracle fixture before speed testing.

## Bigger Bolder Ideas After Force-Block MTP

These are larger than ordinary configuration sweeps. The easy knobs are not
moving c1 decode enough, and force-block MTP proved that the path to `>200 tok/s`
probably needs either verifier-preserving speculation repair or a real XPU MoE
backend change.

1. Perfect-draft upper-bound runner.
   - Feed synthetic perfect draft tokens into the current Quark verifier without
     using any proposer model.
   - Measure verifier buckets `k=1,2,3,4,6,8,12` under the same graph/cache path.
   - If perfect drafts cannot exceed `200 tok/s`, MTP/draft work cannot solve
     the goal by itself. If they can, all effort should move to proposer
     correctness and acceptance rate.

2. Shadow-verifier speculative lane.
   - Keep the production accepted model online, then send every aggressive-lane
     request through a background verifier comparison for the first N tokens.
   - Automatically drop back to the baseline lane if token hashes diverge,
     acceptance rate collapses, or the first-request device-lost signature
     appears.
   - This could let us test risky high-upside scheduler/MTP changes without
     exposing users to bad output.

3. Real-router trace corpus.
   - Log Qwen3.6 expert IDs and per-expert token counts for accepted prompts:
     p512/n512, chat, code, math, structured, and long-context.
   - Build grouped-GEMM and MoE-finalize microbenches from those histograms.
   - This turns the MoE work from generic tuning into shape/routing-specific B70
     tuning.

4. Hot-expert duplication model.
   - Use route histograms to estimate whether duplicating the most common
     routed experts or shared-expert paths on each B70 can reduce TP4
     collectives enough for c1 decode.
   - This is a memory trade: reject immediately if it breaks 32K KV, but keep it
     if it only costs a few GiB and removes repeated cross-rank traffic.

5. XPU W8A8 persistent MoE branch.
   - Prototype outside vLLM first: routed int8 grouped GEMM, activation, second
     grouped GEMM, shared-expert add, and finalize in as few graph-safe kernels
     as possible.
   - The prior Python-level shared-add/all-reduce wrapper proved that simply
     changing boundaries is not enough.
   - The likely win is persistent scheduling, less intermediate memory traffic,
     and fewer launch/collective points.

6. Fast static decode lane.
   - Build a direct runner for batch-1 decode that preallocates KV, bypasses
     OpenAI server lifecycle overhead, and replays static graph buckets.
   - This is not a replacement for production vLLM unless it proves a large
     endpoint/core gap, but it can tell us whether the remaining 100 tok/s wall
     is server overhead or model kernels.

7. Same-model 8-bit engine bakeoff.
   - Test current vLLM/XPU against llama.cpp SYCL Q8_0, OpenVINO GenAI/oneDNN,
     and any emerging vllm-xpu-kernels branch that supports Qwen3.6 MoE 8-bit.
   - This is not permission to use Q4/AWQ/GPTQ. It is a diagnostic to find out
     whether vLLM/XPU is the bottleneck.

8. Upstreamable B70 repro bundle.
   - Package the force-block MTP device-lost, n-gram oracle drift, route
     histograms, AOT op census, exact launch commands, and Localmaxxing result.
   - Target vLLM XPU and `vllm-xpu-kernels` maintainers with minimal repros,
     not a giant production script.

9. Driver/runtime stack A/B disk.
   - Build a second boot/profile with the newest Intel compute runtime,
     oneCCL, oneAPI, vllm-xpu-kernels, and kernel stack that public B70 users
     are succeeding with.
   - Keep the current stack intact. The metric is variance, first-request
     device-lost rate, and accepted r10 speed, not just one lucky run.

10. Learned B70-friendly micro-drafter.
    - Distill a tiny same-tokenizer proposer from traces of the current Quark
      model, optimized for B70-friendly small matmuls rather than general model
      quality.
    - Wrong drafts are rejected, so final quality remains with the Quark
      verifier. The risk is acceptance rate and proposer latency.

Updated priority after the MTP force-block result:

1. Restore the accepted service after every failed sidecar/spec run.
2. Build the perfect-draft verifier upper-bound test before more proposer work.
3. Add route-histogram logging and shape-exact MoE microbenches.
4. Retry force-block MTP only with explicit memory/graph isolation controls.
5. Prepare an upstream repro packet once the first-request device-lost case is
   reproducible from a clean launch.

The isolated run was not executed in this step because the accepted TP4 public
service is currently healthy and unpaused. Keep this diagnostic for the next
paused/isolated window.

## Ignore-Drafts Diagnostic Result

The `IGNORE_DRAFTS=1` oracle `k=1` diagnostic was executed in an isolated
window.

Procedure:

1. Paused the public frontdoor by creating
   `/tmp/qwen36-35b-a3b-fp8-requant-frontdoor-not-paused`.
2. Waited for `active_generations=0` and `queued_generations=0`.
3. Stopped accepted backend session
   `qwen36-tp4-graph-freshcache-paused-20260611d`.
4. Launched diagnostic backend:

```bash
PORT=18081 \
TAG=oracle1-ignore-drafts-graph \
NUM_SPECULATIVE_TOKENS=1 \
PROMPT_LOOKUP_MIN=2 \
PROMPT_LOOKUP_MAX=5 \
ORACLE_TRACE=/home/steve/llm-optimizations/data/qwen36-quark-int8-tp4-oracle-k1-short-accepted-graph-20260611.json \
SPEC_TRACE_FILE=/tmp/qwen36-oracle1-ignore-drafts-graph-spec-trace-20260611a.jsonl \
VLLM_XPU_ORACLE_DRAFT_LOG=/tmp/qwen36-oracle1-ignore-drafts-graph-draft-20260611a.jsonl \
LOG_PATH=/tmp/qwen36-quark-int8-tp4-oracle1-ignore-drafts-20260611a.log \
TORCHINDUCTOR_CACHE_DIR=/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-oracle1-ignore-drafts-20260611a/torchinductor \
VLLM_CACHE_ROOT=/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-oracle1-ignore-drafts-20260611a/vllm \
IGNORE_DRAFTS=1 \
scripts/launch-qwen36-quark-int8-oracle-trace.sh
```

5. Captured two p512/o32 oracle completions against `http://127.0.0.1:18081`.
6. Reduced the accepted-vs-candidate fixture.
7. Stopped the diagnostic backend.
8. Restored the accepted fresh-cache backend on `18080`.
9. Ran paused-local public full r8 through `http://127.0.0.1:8000`.
10. Removed the pause file and rechecked public status/backend health.

Artifacts:

- diagnostic completions:
  `data/qwen36-quark-int8-tp4-oracle1-ignore-drafts-graph-completions-20260611.json`
- reduced fixture:
  `data/qwen36-quark-int8-tp4-oracle1-ignore-drafts-drift-fixture-20260611.json`
  and
  `data/qwen36-quark-int8-tp4-oracle1-ignore-drafts-drift-fixture-20260611.md`
- oracle draft proposer log:
  `data/qwen36-quark-int8-tp4-oracle1-ignore-drafts-draft-20260611.jsonl`
- restore quality gate:
  `data/qwen36-quark-int8-tp4-restored-after-ignore-drafts-public-frontdoor-pausedlocal-full-r8-20260611.json`

Observed diagnostic result:

- The diagnostic backend reached `/health`.
- No scheduler spec trace file was produced at
  `/tmp/qwen36-oracle1-ignore-drafts-graph-spec-trace-20260611a.jsonl`.
- This confirms that the scheduler did not feed draft tokens into verifier
  speculative rows under `IGNORE_DRAFTS=1`.
- The oracle draft log did run:
  - JSONL rows: `256`
  - matched rows: `188`
- Output parity:
  - `baseline_match_all=false`
  - reduced fixture `exact_match_all=false`
  - mismatch count: `1/2`
  - `natural_latency_plan`: exact match
  - `repetitive_kernel_notes`: mismatch at output index `15`
    - accepted token: `11436` / ` hardware`
    - candidate token: `16401` / ` decode`

Checker output in exact mode:

```json
{
  "case_count": 2,
  "errors": [
    "fixture is not exact_match_all=true",
    "expected 0 mismatches, found 1"
  ],
  "fixture": "data/qwen36-quark-int8-tp4-oracle1-ignore-drafts-drift-fixture-20260611.json",
  "mismatch_count": 1,
  "mode": "exact",
  "ok": false,
  "roles": []
}
```

Interpretation:

- The original oracle `k=1` drift was `2/2`.
- `IGNORE_DRAFTS=1` improved the failure to `1/2`, so actual speculative
  token execution/commit contributes to part of the previous drift.
- However, one prompt still drifts with zero scheduler spec rows, so the
  remaining failure is upstream of draft-token commit/rollback.
- The likely fault zone is now narrower:
  - presence of `speculative_config`,
  - drafter/proposer plumbing,
  - model-runner graph/metadata changes caused by speculative mode,
  - graph capture/cache differences with speculative config active,
  - or request/input batch metadata changes even when
    `scheduled_spec_decode_tokens` is empty.

Restore result:

- Accepted backend restored with fresh-cache root
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-freshrestore-20260611d`.
- Paused-local public full r8 passed:
  - `pass_all=true`
  - `baseline_match_all=true`
  - exact arithmetic/copy/JSON/OK passed
  - repeat stability passed
  - long-context needle passed
- Public frontdoor was unpaused.
- Final status:
  - `paused=false`
  - `active_generations=0`
  - `queued_generations=0`
  - backend health `200`

Next isolation branch:

1. Run the same `IGNORE_DRAFTS=1` diagnostic with `ENFORCE_EAGER=1`.
   - If eager passes, graph/spec-config capture is implicated.
   - If eager drifts, model-runner/spec-config code path is implicated before
     graph capture.
2. Add a "spec config present, proposer disabled" mode.
   - Goal: determine whether the mere presence of `speculative_config` changes
     model-runner or graph shapes enough to alter tokens.
3. Add model-runner input metadata diff traces for the first decode rows when
   `scheduled_spec_decode_tokens` is empty:
   - input ids,
   - positions,
   - slot mapping,
   - mamba/GDN metadata,
   - cudagraph bucket id,
   - logits processor path.
4. If graph-only, run fresh-cache versus restored-cache A/B for
   `IGNORE_DRAFTS=1`.
5. If spec-config-only, inspect vLLM's spec-mode model-runner branches and
   patch them so no scheduled draft tokens means identical verifier inputs to
   the accepted non-spec path.

## Next Ideas And Bigger Bets Addendum

Added after the `IGNORE_DRAFTS=1` diagnostic and another current-source sweep.
The target is unchanged: Qwen3.6 35B, 8-bit/high-fidelity final verifier,
single-request speed first, aggregate throughput second, and no promotion
without exact quality/reliability gates.

Fresh source signals:

- `https://github.com/vllm-project/vllm-xpu-kernels`
  - vLLM XPU kernel work is now concentrated in `vllm-xpu-kernels`, including
    attention, MoE routing/remap/gather, quantization, and grouped GEMM. Future
    kernel work should target this repo shape instead of old one-off IPEX
    experiments.
- `https://docs.vllm.ai/en/v0.18.0/models/hardware_supported_models/xpu/`
  - Arc Pro B-Series is an explicitly validated vLLM XPU hardware target, and
    Qwen MoE-family models are part of the recommended XPU model set.
- `https://docs.vllm.ai/en/latest/features/speculative_decoding/`
  - vLLM documents EAGLE, MTP, draft-model, PARD, MLP, n-gram, suffix, and
    custom proposer methods. Model-based methods are the plausible latency
    multipliers; n-gram remains a diagnostic only until exact parity is fixed.
- `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`
  - Intel's grouped-GEMM performance epic calls out runtime routing skew and
    tile configuration as first-order MoE performance variables. This directly
    supports capturing real Qwen3.6 router distributions before tuning more
    grouped-GEMM or hotpack kernels.
- `https://docs.vllm.ai/en/stable/features/quantization/int8/`
  - vLLM's W8A8 path is calibration-sensitive and should be evaluated with
    strict prompt-template parity. For our current model, keep Quark W8A8 as the
    final verifier unless a new 8-bit artifact passes the same gates.
- `https://intel.github.io/intel-extension-for-pytorch/xpu/latest/tutorials/features/int8_overview_xpu.html`
  - Intel's GPU INT8 docs emphasize graph/TorchScript fusion for best INT8
    performance. That reinforces our own result: isolated Python wrappers are
    unlikely to win; graph-visible fused boundaries or native kernels are the
    right level.

Near-term things to try:

1. `IGNORE_DRAFTS=1` eager A/B.
   - Purpose: split graph-capture/spec-config effects from model-runner
     metadata effects.
   - Required proof: exact p512/o32 oracle fixture parity before expanding.

2. "Spec-config placebo" mode.
   - Create a launch path where speculative config is present, the proposer is
     constructed, but no request receives speculative scheduling metadata.
   - If this drifts, the bug is in model-runner or graph selection triggered by
     spec config alone.

3. Model-runner first-row tensor diff.
   - Log positions, input IDs, slot mapping, block table handles, GDN/Mamba
     metadata, graph bucket, and logits-processor state for accepted versus
     spec-placebo/ignore-drafts.
   - Goal: find the first non-identical verifier input, not just the first
     output-token mismatch.

4. Real-router distribution capture.
   - Add opt-in route logging for a small accepted p512/o512 suite.
   - Feed exact layer/expert/token histograms into grouped-GEMM and MoE
     microbenches.
   - Stop using synthetic uniform routing as promotion evidence.

5. vLLM-XPU-kernels shape lab.
   - Build three standalone repros from the live AOT census:
     dense W8A8 GEMM, routed grouped GEMM, and graph-safe collective/finalize.
   - Each repro should include shape, dtype, route histogram, latency, expected
     parity tolerance, and command line.

6. Static batch-1 decode-core runner.
   - Strip OpenAI serving, queueing, metrics, and streaming from the test path.
   - If core decode remains near `100 tok/s`, server overhead is not the
     blocker. If it jumps, build a production latency lane around that path.

7. Peak-VRAM and headroom measurement pack.
   - The last strong Localmaxxing row skipped VRAM. Capture per-card peak
     allocation and free headroom during p512/o512 and 32K quality runs.
   - This decides whether memory-for-latency ideas can fit at 32K or require a
     separate 8K/16K low-latency service class.

Bolder branches:

1. First-class auxiliary proposer API for Qwen3.6 on XPU.
   - Use the current Quark INT8 model as the only final verifier.
   - Draft candidates can come from official FP8 MTP tensors, a same-tokenizer
     sidecar, or a custom proposer, but accepted output must remain byte-for-byte
     equal to the non-spec verifier baseline.
   - This is still the most credible path to `>200 tok/s` single-user because
     the bucket timing upper bounds show enough verifier headroom.

2. Verifier-bucket graph specialization.
   - Instead of generic speculative rows, create fixed graph buckets for
     verifier widths `1/2/3/5/8` and prove each bucket has identical verifier
     inputs to the accepted path.
   - This may avoid scheduler/block-table drift while preserving sublinear
     multi-token verification.

3. Persistent route-window MoE kernel.
   - Use real route histograms and persistent scratch to keep expert tiles hot
     across a short decode window.
   - Fuse route remap, activation, second quant, grouped GEMM, gather/finalize,
     and only then consider all-reduce/residual epilogues.
   - Do not wire into the endpoint until the standalone parity harness passes.

4. Tile-native W8A8 repack cache.
   - Repack Quark INT8 weights once into the fastest B70/XMX layout and cache
     with checksums.
   - This is a layout optimization, not a new quantization; dequantized weights
     and output gates must remain unchanged.

5. Memory-for-latency service class.
   - If full 32K leaves little headroom, offer a separate 8K or 16K
     quality-equivalent latency lane that uses freed VRAM for draft heads,
     hot-expert copies, or static graph buffers.
   - This is not a replacement for the 32K production target, but it may produce
     a usable single-user fast lane without lowering model precision.

6. Hybrid TP/EP simulator before implementation.
   - Estimate communication for pure TP4 versus expert-local layouts using the
     captured route histograms.
   - If the simulator cannot show a large reduction in decode collectives, do
     not spend time on a full vLLM architecture branch.

7. End-to-end XPU timeline budget.
   - Use VTune/oneprof/Level Zero traces to classify every token into XMX
     compute, memory traffic, collectives, graph replay, Python/runtime, and
     frontdoor streaming.
   - This should be the tie-breaker between speculation, MoE kernels, repack,
     and serving-lane work.

8. Strict 8-bit engine shootout.
   - Compare current vLLM Quark W8A8, llama.cpp/SYCL Q8_0 or equivalent 8-bit
     GGUF, OpenVINO/oneDNN GenAI if Qwen3.6 MoE is supported, and any new
     XPU-native W8A8 path.
   - Same prompts, same chat template, same 32K gate where possible, and no
     4-bit or Qwen3.5 rows mixed into the decision.

9. Upstreamable B70 repro bundle.
   - Turn the failing/spec-sensitive cases and the slow grouped-GEMM shapes into
     small public issues/PRs for `vllm`, `vllm-xpu-kernels`, and Intel Triton
     XPU.
   - Include exact artifacts, shape dumps, command snippets, and quality-drift
     fixtures so maintainers can act without access to the whole service.

Priority order:

1. Fix or isolate spec-mode verifier drift (`IGNORE_DRAFTS=1` eager, placebo,
   tensor diff).
2. In parallel, capture real route histograms and build the shape lab.
3. Re-run accepted r8/r10 plus peak VRAM after any service restore.
4. Only after parity is exact, benchmark proposer/MTP/spec speed.
5. If speculation remains blocked, shift primary effort to persistent MoE and
   tile-native W8A8 repack.

## Eager Ignore-Drafts Control Result

The next isolation branch tested whether the remaining `IGNORE_DRAFTS=1`
graph-mode drift was caused by graph capture or by non-graph
speculative/model-runner plumbing.

Procedure:

1. Paused and drained the public frontdoor.
2. Stopped the accepted graph backend.
3. Launched an eager `IGNORE_DRAFTS=1` oracle `k=1` backend on `18081`:

```bash
PORT=18081 \
TAG=oracle1-ignore-drafts-eager \
NUM_SPECULATIVE_TOKENS=1 \
PROMPT_LOOKUP_MIN=2 \
PROMPT_LOOKUP_MAX=5 \
ORACLE_TRACE=/home/steve/llm-optimizations/data/qwen36-quark-int8-tp4-oracle-k1-short-accepted-graph-20260611.json \
SPEC_TRACE_FILE=/tmp/qwen36-oracle1-ignore-drafts-eager-spec-trace-20260611a.jsonl \
VLLM_XPU_ORACLE_DRAFT_LOG=/tmp/qwen36-oracle1-ignore-drafts-eager-draft-20260611a.jsonl \
IGNORE_DRAFTS=1 \
ENFORCE_EAGER=1 \
ENABLE_XPU_GRAPH=0 \
COMPILE_CONFIG= \
scripts/launch-qwen36-quark-int8-oracle-trace.sh
```

4. Captured the same two p512/o32 oracle completion prompts.
5. Stopped the eager spec backend.
6. Launched a no-spec eager accepted control on `18081` with
   `--enforce-eager`, `XPU_GRAPH=0`, and `VLLM_XPU_ENABLE_XPU_GRAPH=0`.
7. Captured the same two p512/o32 completion prompts.
8. Restored the accepted graph backend on `18080`.
9. Ran paused-local public full r8 through the frontdoor.
10. Removed the pause file and verified public status/backend health.

Artifacts:

- eager ignore-drafts completions:
  `data/qwen36-quark-int8-tp4-oracle1-ignore-drafts-eager-completions-20260611.json`
- eager ignore-drafts fixture:
  `data/qwen36-quark-int8-tp4-oracle1-ignore-drafts-eager-drift-fixture-20260611.json`
  and
  `data/qwen36-quark-int8-tp4-oracle1-ignore-drafts-eager-drift-fixture-20260611.md`
- eager ignore-drafts draft log:
  `data/qwen36-quark-int8-tp4-oracle1-ignore-drafts-eager-draft-20260611.jsonl`
- no-spec eager control completions:
  `data/qwen36-quark-int8-tp4-accepted-eager-control-completions-20260611.json`
- no-spec eager control fixture:
  `data/qwen36-quark-int8-tp4-accepted-eager-control-drift-fixture-20260611.json`
  and
  `data/qwen36-quark-int8-tp4-accepted-eager-control-drift-fixture-20260611.md`
- restore quality gate:
  `data/qwen36-quark-int8-tp4-restored-after-eager-control-public-frontdoor-pausedlocal-full-r8-20260611.json`

Observed diagnostic result:

- Eager `IGNORE_DRAFTS=1` reached `/health`.
- The log confirmed eager mode disabled torch.compile/CUDAGraphs and
  `VLLM_XPU_ENABLE_XPU_GRAPH=0` disabled XPU graph.
- No scheduler spec trace file was produced under
  `/tmp/qwen36-oracle1-ignore-drafts-eager-spec-trace-20260611a.jsonl`.
- Eager oracle draft logging still ran:
  - JSONL rows: `256`
  - matched rows: `128`
- Eager `IGNORE_DRAFTS=1` versus the graph accepted baseline:
  - `baseline_match_all=false`
  - reduced fixture `exact_match_all=false`
  - mismatch count: `2/2`
  - `natural_latency_plan`: first diff at output index `17`
  - `repetitive_kernel_notes`: first diff at output index `15`
- No-spec eager control versus the graph accepted baseline:
  - `baseline_match_all=false`
  - reduced fixture `exact_match_all=false`
  - mismatch count: `2/2`
  - first diffs matched the eager `IGNORE_DRAFTS=1` run.
- Direct eager-control comparison:
  - `natural_latency_plan`: no-spec eager output equals eager
    `IGNORE_DRAFTS=1` output exactly.
  - `repetitive_kernel_notes`: no-spec eager output equals eager
    `IGNORE_DRAFTS=1` output exactly.

Interpretation:

- Eager mode is not a clean isolator against the graph accepted baseline for
  these prompts. The no-spec eager control already drifts `2/2`.
- In eager mode, speculative config plus `IGNORE_DRAFTS=1` adds no observable
  drift beyond ordinary eager behavior on the two-prompt fixture.
- The prior graph-mode result remains the useful spec diagnostic:
  `IGNORE_DRAFTS=1` graph improved from `2/2` oracle drift to `1/2`, but one
  graph-mode prompt still drifted with no scheduled draft tokens.
- Therefore the next useful branch is not more eager testing. It is graph-mode
  `speculative_config` placebo plus model-runner input metadata diff:
  - graph accepted, no spec config;
  - graph spec config present, proposer constructed, no draft metadata;
  - graph `IGNORE_DRAFTS=1`;
  - compare first decode row input IDs, positions, slot mapping, block tables,
    GDN/Mamba metadata, graph bucket, and logits path.

Restore result:

- Accepted graph backend restored in tmux session
  `qwen36-tp4-accepted-restored-after-eager-control-20260611a`.
- Paused-local public full r8 passed:
  - `pass_all=true`
  - `baseline_match_all=true`
  - exact arithmetic/copy/JSON/OK passed
  - repeat stability passed
  - long-context needle passed
- Public frontdoor was unpaused.
- Final status:
  - `paused=false`
  - `active_generations=0`
  - `queued_generations=0`
  - backend health `200`

Next action:

1. Implement a graph-mode spec-placebo launcher/env:
   speculative code paths initialized, but no `spec_token_ids` or lookahead
   blocks attached to requests.
2. Add a first-row graph metadata trace around model-runner input preparation.
3. Compare accepted graph versus graph placebo versus graph `IGNORE_DRAFTS=1`
   before attempting any more MTP, DFlash, or n-gram speed runs.

## Follow-Up Idea Expansion

This follow-up adds the items from the post-eager-control discussion and a
fresh public-reference sweep. The working assumption is unchanged: no 4-bit,
no Qwen3.5 substitution, and no quality-loss speed claims. The target remains
Qwen3.6 35B A3B on 8-bit weights with the current Quark verifier as the
quality anchor.

Public/reference observations to keep in mind:

- Localmaxxing now shows a near-equivalent base-model B70 row at
  `99.769699 tok/s`, `76.526643 ms` TTFT, and `127.547168 GB` peak VRAM for
  `Qwen/Qwen3.6-35B-A3B` on 4x B70, plus the exact-model Quark W8A8 INT8 row
  at `99.428358 tok/s`. If that peak is aggregate device memory, full 32K
  production is essentially using all four 32GB cards, so memory-for-latency
  ideas probably need an 8K/16K fast lane or a lower `max_num_seqs` variant.
- Intel's `intel/vllm:0.10.2-xpu` notes call out Arc Pro B-series validation,
  persistent MoE GEMM plus fused activation work, and Qwen3-30B-A3B support.
  This reinforces that persistent MoE scheduling and XPU-kernel shape work are
  more plausible than more Python wrapper boundaries.
- vLLM's XPU migration RFC says the backend is moving from IPEX toward
  `vllm-xpu-kernels` for performance, maintainability, and purpose-built
  inference kernels, with fp8 gemm/model support and fp8 MoE listed as done in
  that migration stream. Any local kernel work should be framed as a shape
  repro that can land in that layer, not as a long-lived one-off fork.
- The public vLLM B70 TP=2 issue is a useful stability warning: standalone
  XCCL/SYCL can pass while vLLM TP worker initialization still trips driver,
  firmware, PCIe, or ProcessGroupXCCL interactions. Every topology/runtime
  change needs a restore plan and a reliability gate.
- vLLM docs list Arc Pro B-series as validated XPU hardware and Qwen3-30B-A3B
  as a recommended text model. They do not make Qwen3.6 35B Quark INT8 a
  turnkey path, so our exact-model artifacts remain valuable upstream repros.
- Generic vLLM INT8 W8A8 documentation is mostly CUDA-oriented today. Treat
  Intel-friendly INT8 as a kernel/backend gap to measure and upstream, not as
  something already solved by the public docs.

Immediate additions to the things-to-try list:

1. Add the graph placebo and model-input trace before touching speed again.
   The exact comparison should be:
   - accepted graph, no speculative config;
   - graph with speculative config constructed but zero draft metadata;
   - graph `IGNORE_DRAFTS=1`;
   - optional graph oracle `k=1` after the first three line up.
   Compare first decode row `input_ids`, positions, slot mappings, block
   tables, scheduled-token counts, logits indices, graph bucket, and any
   GDN/Mamba metadata.

2. Capture per-rank peak VRAM during the accepted recipe and during the
   richer Localmaxxing-style benchmark. The current public peak-VRAM clue is
   useful but too coarse; we need per-card headroom before allocating draft
   buffers, expert copies, or repacked weights.

3. Create a real-route histogram recorder for Qwen3.6 A3B decode:
   per-layer active expert ids, token counts per expert, local/remote expert
   ownership under TP4, and repeated-expert locality over a short decode
   window. This becomes input to both the MoE microbench and the hybrid TP/EP
   simulator.

4. Build a shape-lab repo section from the live AOT census:
   - dense `per_token_quant_int8 -> int8_gemm_w8a8 -> all_reduce`;
   - routed MoE grouped GEMM/finalize;
   - graph-safe tiny hidden-state collective;
   - GDN projection quant/GEMM reuse.
   Each repro needs shape, dtype, route histogram where applicable, command,
   observed latency, and parity tolerance.

5. Run a strict 8-bit engine shootout only if the artifact is genuinely
   Qwen3.6 35B-class and 8-bit. Candidate lanes:
   - current vLLM Quark W8A8 INT8;
   - llama.cpp/SYCL Q8_0 or equivalent 8-bit GGUF if available;
   - OpenVINO/oneDNN GenAI only if Qwen3.6 MoE and 32K serving are supported.
   Exclude AWQ/4-bit and Qwen3.5 results from decisions.

6. Treat host/topology work as reliability and variance reduction, not the
   main `2x` path. Still worth doing behind reversible scripts:
   BIOS/ASPM check, runtime power `on`, persistent performance profile,
   NUMA pinning, oneCCL interface pinning, thermal/fan logging, and root
   `lspci -vv` link validation.

7. Prepare a clean upstream issue bundle once the trace lands:
   one issue for graph/spec scheduler drift, one for exact W8A8 dense/MoE
   shapes, and one for any B70/oneCCL graph-capture instability. Include
   minimal scripts and no service secrets.

Bigger bolder branches worth serious time:

1. Verifier-preserving speculative decode remains the most realistic
   `>200 tok/s` path. The current model must stay the verifier. Draft sources
   can be n-gram, official Qwen3.6 MTP tensors, or a same-tokenizer sidecar,
   but the promoted output has to pass exact canaries, repeat64, and
   long-context gates. The next engineering task is proving the verifier input
   rows are identical under placebo/ignore-drafts before chasing throughput.

2. A decode-only static runner for batch-1 latency should quantify how much
   time is in model core versus serving stack. If direct model-runner replay is
   still about `100 tok/s`, the problem is kernel/layout/collective. If it
   jumps materially, production can grow a dedicated low-latency lane without
   changing weights.

3. A hybrid TP/EP simulator should come before any full architecture patch.
   Use real route histograms and memory accounting to estimate pure TP4 versus
   expert-local or expert-replicated layouts. Only implement if the model shows
   a large predicted cut in decode collectives while still fitting 32K or a
   clearly labeled lower-context fast lane.

4. Persistent MoE for the exact Qwen3.6 INT8 shapes is the main kernel bet.
   The rejected MoE shared-add/all-reduce Python wrapper proved a boundary
   change alone is not enough. The plausible win is one persistent route-window
   kernel that fuses route remap, activation, second quant, grouped GEMM,
   gather/finalize, and only then considers all-reduce/residual epilogues.

5. Tile-native W8A8 repack cache is the main layout bet. If the hot path is
   paying for suboptimal Quark layout, build a load-time/offline repack into
   B70/XMX-friendly tile order with checksums. This must preserve dequantized
   weights and output parity; it is not a new quantization.

6. Memory-for-latency service classes may be necessary. Full 32K appears
   memory-tight. A separate 8K or 16K lane could use the freed VRAM for static
   graph buffers, draft heads, hot-expert copies, or larger capture buckets.
   Keep it separate from the 32K production promise, but measure it because it
   may be the difference between "usable interactive" and "benchmark only".

7. Upstreamable XPU backend work should be shaped around `vllm-xpu-kernels`,
   not scattered local hooks. If the dense W8A8, MoE grouped GEMM, or graph
   collective repros show clear gaps, turn them into focused PRs/issues with
   numbers. That is more likely to compound than another private env flag.

8. Continuous quality gates need to become cheap enough to run after every
   kernel branch:
   - exact two-prompt canary for scheduler/model-input drift;
   - repeat32/repeat64 text stability;
   - long-context needle at 8K and 32K;
   - arithmetic/copy/JSON structured tasks;
   - c1 speed plus c2/c4/c8 aggregate smoke.

Revised priority order:

1. Implement graph placebo plus model-input trace.
2. Re-run accepted graph, graph placebo, and graph `IGNORE_DRAFTS=1` on the
   same two-prompt fixture.
3. Restore service and run paused-local public r8 quality.
4. Capture per-card VRAM and route histograms.
5. If trace parity is clean, resume verifier-preserving speculation/MTP.
6. If trace parity is not clean, fix graph scheduler/model-input drift before
   any more performance claims.

## Additional Ambitious Ideas

Late-pass additions after checking current public Arc/XPU and vLLM kernel
signals. These are not accepted wins; they are work queues with explicit proof
requirements.

Fresh signals to remember:

- Recent Intel Arc llama.cpp discussion claims SYCL speculative decoding moved
  from slower-than-baseline to a meaningful win after porting a multi-column
  MMVQ path, with the largest reported gain on Q8. Treat this as a clue that
  the "verify multiple draft tokens in one efficient column batch" kernel shape
  may matter more than the proposer itself.
- `vllm-xpu-kernels` is now the natural target for durable XPU work. It already
  owns attention, MoE routing helpers, quantization, grouped GEMM, and related
  custom ops, so any real B70 W8A8/MoE improvement should become a small repro
  or patch there rather than only a local vLLM service hack.
- The vLLM XPU migration RFC marks FP8/W8A8/W8A16 scaled-MM work as part of the
  XPU kernel migration path. That makes a "missing kernel path" less likely as a
  binary yes/no issue and more likely a shape/layout/scheduling issue for this
  exact Qwen3.6 MoE decode workload.
- Public Qwen3.6 speculative-decoding reports still show draft models can make
  things worse or buggy when tensor split, KV, and scheduler state are wrong.
  Our quality gate failures line up with that: speculation is the right bold
  lane, but only after model-input parity is proven.

More ideas to try or scope:

1. Multi-token verifier kernel shape.
   - Build a microbench that verifies 1, 2, 3, 4, and 8 candidate decode tokens
     through the current Quark verifier without changing final sampling.
   - Measure whether the verifier's matmul/MoE path gets better occupancy from
     multiple columns, independent of n-gram quality.
   - If the speedup exists, fix proposer correctness around that shape; if it
     does not, MTP will need a much faster draft path to matter.

2. Speculation placebo as a permanent correctness tool.
   - Keep graph placebo and model-input trace as a reusable harness, not a
     one-off bug hunt.
   - Every future speculative method should first prove that "drafts supplied
     but ignored" equals accepted baseline at token, position, slot mapping,
     sequence length, logits index, and block-table level.
   - This turns speculation bugs from vague output drift into a concrete row
     mismatch.

3. Small-M grouped GEMM policy table for real route histograms.
   - Log actual Qwen3.6 top-k expert distributions during decode and build a
     table of recurring grouped GEMM shapes.
   - For each shape bucket, test tile sizes, split-K choices, prepack layout,
     and persistent scheduling outside vLLM.
   - If a shape-specific policy beats the generic path, upstream the dispatch
     rule with the histogram artifact.

4. Hot-expert replication experiment.
   - If route histograms show persistent expert skew, test duplicating only the
     hottest expert weights across ranks or pinning them to local memory.
   - This trades memory for fewer remote/collective stalls and may be viable in
     a 16K or 8K latency lane even if it does not fit the full 32K promise.
   - Proof requirement: same exact weights, same output quality, clear memory
     accounting, and route-specific speed wins.

5. Graph bucket compression.
   - Current graph capture has many bucket sizes. Test whether a smaller set of
     exact decode/spec buckets reduces capture overhead, cache pressure, or
     runtime branch churn without losing the query lengths needed for stable
     speculation.
   - Pair this with model-input trace so a graph-bucket change cannot silently
     alter slot mappings.

6. KV and GDN state audit under speculation.
   - Qwen3.6's recurrent/convolution-style state makes speculative rejection
     riskier than a plain transformer path.
   - Add a debug snapshot around any GDN/recurrent state update when draft
     tokens are accepted or rejected.
   - If accepted loops happen with perfect token verification, the hidden state
     advancement path is a prime suspect.

7. OpenVINO/oneDNN GenAI control run.
   - Not a production switch yet. Use it as a same-hardware reference for
     oneDNN scheduling, weight layout, and MoE execution if Qwen3.6 MoE W8A8 or
     high-fidelity INT8 is supported.
   - Reject it if it requires 4-bit, Qwen3.5, a lower context target, or prompt
     template drift.

8. Async disaggregated prefill/decode only if it helps c1.
   - vLLM supports prefill/decode disaggregation conceptually, but our target is
     single active request first. Most disaggregation helps aggregate throughput.
   - Still worth a small test if it lets decode stay in a cleaner static graph
     while prefill runs separately.

9. "Latency lane" production profile.
   - Keep the 32K production route as the quality oracle, but consider a
     separately advertised low-latency route at 8K/16K if memory buys draft
     heads, hot-expert copies, larger graph buckets, or lower jitter.
   - This does not solve the main 32K target, but it may produce a usable
     product surface while the full-context kernel work continues.

10. Upstream collaboration package.
    - Prepare a no-secret tarball for Intel/vLLM maintainers with:
      route histograms, W8A8 dense/MoE microbench shapes, graph-capture env,
      oneCCL settings, B70 topology, and accepted-vs-candidate quality outputs.
    - The ask should be narrow: improve this exact small-batch Qwen3.6 MoE
      W8A8 decode shape on B70, not "make XPU faster."

Hard filters that remain in force:

- no 4-bit promotion;
- no Qwen3.5 detour;
- no speed claim without accepted quality parity;
- no production switch without repeat stability, long-context, and restore
  tests;
- do not publish Localmaxxing rows for speculative runs until repeat64 and
  baseline comparison are clean.

## Graph Placebo Trace Findings And Bolder Follow-Ups

Added after the graph-placebo/model-input trace pass. This is the current
highest-signal diagnostic result for the speculative branch.

New artifacts:

- `data/qwen36-quark-int8-tp4-accepted-modelinput-completions-20260611f.json`
- `data/qwen36-quark-int8-tp4-accepted-modelinput-trace-20260611f.jsonl`
- `data/qwen36-quark-int8-tp4-placebo-modelinput-completions-20260611a.json`
- `data/qwen36-quark-int8-tp4-placebo-modelinput-trace-20260611a.jsonl`
- `data/qwen36-quark-int8-tp4-placebo-modelinput-drift-fixture-20260611a.json`
- `data/qwen36-quark-int8-tp4-placebo-modelinput-drift-fixture-20260611a.md`
- `patches/vllm-qwen36-spec-placebo-model-input-trace-20260611.patch`
- `patches/vllm-qwen36-active-gpu-model-runner-input-trace-20260611.patch`

Finding:

- Graph placebo still drifted from the accepted baseline even with no scheduled
  draft tokens and empty `spec_token_ids`.
- The first model-input row already differs in KV slot mappings while
  `input_ids`, `positions`, `logits_indices`, and scheduled speculative-token
  metadata match.
- Accepted first-row slot starts by attention group:
  `[32768]`, `[65536]`, `[98304]`, `[2304]`.
- Placebo first-row slot starts by attention group:
  `[32768]`, `[98304]`, `[163840]`, `[4032]`.
- Placebo also disabled async scheduling, changed graph capture size coverage
  from max `96` to max `128`, and reduced effective KV capacity from
  `2,052,915` tokens to `1,955,157` tokens with the same reported available KV
  memory.

Interpretation:

- The current n-gram/spec branch is not yet failing because the proposer chose
  bad tokens. It is failing earlier: the presence of speculative configuration
  changes scheduler/KV/cache layout state before any actual draft row is used.
- This makes future speculative results unpublishable until the placebo path
  has exact model-input parity with accepted graph mode.
- The next useful control is an accepted no-spec run with async scheduling
  explicitly disabled. If that reproduces the drift, the async/scheduler
  transition is the primary culprit. If it still matches accepted, the
  speculative KV/lookahead/capture configuration is the primary culprit.

Things to add to the immediate queue:

1. Fix the block-table trace capture to use `BlockTable.get_cpu_tensor()` or
   `BlockTable.get_numpy_array()` instead of treating `BlockTable` as a tensor.
   Slot mappings were enough to expose the current drift, but block tables are
   needed for a clean upstream repro.
2. Run accepted graph with async scheduling disabled and compare against
   accepted graph and graph placebo on the same reduced two-prompt fixture.
3. Run a graph-placebo control with capture sizes forced to the accepted set if
   the launcher can expose that cleanly. The goal is to separate async
   scheduling, graph bucket, and KV capacity effects.
4. Add `scheduler_config`, graph bucket/capture size, KV capacity, and
   lookahead-block metadata to the model-input trace rows. These should be
   printed next to the first mismatch, not inferred from logs later.
5. Treat every future speculative method as a two-stage gate:
   - stage 1: placebo model-input parity;
   - stage 2: real drafted-token quality and speed.

Fresh external signals checked:

- vLLM recipe for `Qwen/Qwen3.6-35B-A3B` shows native MTP serving with
  `--speculative-config '{"method": "mtp", "num_speculative_tokens": 2}'`.
  Source: `https://recipes.vllm.ai/Qwen/Qwen3.6-35B-A3B`
- Localmaxxing now has a `203.58 tok/s` Qwen3.6 35B-class row using
  `qwen3_next_mtp` with `num_speculative_tokens=4` on an RTX 5090. This is
  not an acceptable production quantization for this work
  (`Infatoshi/Qwen3.6-35B-A3B-NVFP4-FP8`), but it confirms that Qwen3.6-native
  MTP is a real `>200 tok/s` recipe class when the backend supports it.
- `Qwen/Qwen3.6-35B-A3B-FP8` has a public DFlash row at `253.7 tok/s` on an
  RTX PRO 6000 Blackwell with `num_speculative_tokens=4` and
  `FULL_AND_PIECEWISE` graph mode. Again, hardware/quant are not our target,
  but the shape of the win is useful.
- The public `vllm-xpu-kernels` repository is the durable target for Intel XPU
  backend work. Shape-exact W8A8 dense/MoE repros should be aimed there rather
  than carried forever as private vLLM hooks.
- Intel grouped-GEMM tuning notes emphasize that decode-stage MoE routing is
  skewed and tile-sensitive. Our next MoE microbench should use live route
  histograms, not synthetic even expert distributions.

New bolder ideas to track:

1. Qwen3.6-native MTP sidecar with Quark verifier.
   - Use official FP8/MTP or another Qwen3.6-native MTP source only as the
     proposer. The current Quark W8A8 INT8 model remains the final verifier.
   - First solve placebo parity. Then try `num_speculative_tokens=1,2,4` with
     exact acceptance-rate logging and repeat64 gates.
   - This is the most plausible `>200 tok/s` path without changing final model
     quality.

2. DFlash sidecar as a separate proposer family.
   - DFlash rows show large wins on NVIDIA-class systems, and a Qwen3.6
     drafter exists publicly.
   - It may be hard on XPU today, but it is worth scoping because it decouples
     draft generation from the full MoE verifier.
   - Reject it unless the Quark verifier decides final tokens and exact quality
     gates pass.

3. Multi-column verifier kernel.
   - Speculation is only useful if verifying several candidate tokens at once
     improves verifier utilization. Build a microbench that feeds 1, 2, 4, and
     8 candidate columns through the current Quark verifier path and measures
     dense, GDN, MoE, and collective time separately.
   - If multi-column verification is not faster on B70, MTP/DFlash will need a
     very high acceptance rate to matter.

4. Scheduler/KV invariant test suite.
   - Convert the current model-input trace comparison into a reusable test that
     fails on slot mapping, block table, logits index, graph bucket, or hidden
     state metadata drift.
   - Run it for no-spec accepted, async-disabled accepted, graph placebo,
     ignore-drafts, n-gram, MTP, and DFlash candidates.
   - This becomes the safety rail for all big speed work.

5. XPU kernel issue package.
   - Prepare no-secret repros for:
     - W8A8 dense `per_token_quant_int8 -> int8_gemm_w8a8 -> all_reduce`;
     - real-route MoE grouped GEMM/finalize;
     - graph-safe tiny collective;
     - multi-column verifier shape.
   - Include accepted Localmaxxing result ID `cmq8yhxvo001ipb0149aoa79o`,
     exact model ID, B70 topology, command, and measured latency.

6. Hot-expert cache with context-tier accounting.
   - If route histograms show stable hot experts, try duplicating only the hot
     expert weights or prepacked forms on every rank.
   - Measure it as a memory-for-latency trade: probably not viable at full 32K
     unless headroom is larger than expected, but potentially viable for an
     8K/16K low-latency lane.

7. Decode-core bypass harness.
   - Build a direct model-runner decode harness that avoids OpenAI server
     streaming and request lifecycle overhead while using the exact same
     weights, tokenizer, graph mode, and kernels.
   - If core decode is far above endpoint decode, production can add a
     dedicated low-latency route. If it is still near `100 tok/s`, keep effort
     on kernels/speculation.

8. Production-grade benchmark pack before the next public post.
   - Capture r10 or r20 speed, repeat64 quality, 8K/32K long-context needle,
     per-card peak VRAM, active graph/cache metadata, and endpoint restore
     proof.
   - Only publish speculative or lower-context results if the notes clearly
     label the route and the quality gates are clean.

## Async-Disabled Control, MTP Sidecar Failure, And Larger Bets

Added after the accepted no-spec async-disabled control and the first
Qwen3.6-native MTP sidecar load attempt. This sharpens the speculative branch:
we now have a scheduler correctness problem independent of real draft tokens,
and a separate FP8-MTP loader gap.

New artifacts:

- `data/qwen36-quark-int8-tp4-accepted-noasync-modelinput-completions-20260611a.json`
- `data/qwen36-quark-int8-tp4-accepted-noasync-modelinput-trace-20260611a.jsonl`
- `data/qwen36-quark-int8-tp4-accepted-noasync-modelinput-drift-fixture-20260611a.json`
- `data/qwen36-quark-int8-tp4-accepted-noasync-modelinput-drift-fixture-20260611a.md`
- `data/qwen36-quark-int8-tp4-mtp1-fp8sidecar-startup-failure-20260611a.txt`
- runtime log:
  `/tmp/qwen36-quark-int8-tp4-accepted-noasync-modelinput-20260611a.log`
- runtime log:
  `/tmp/qwen36-quark-int8-tp4-mtp1-fp8sidecar-modelinput-20260611a.log`

Accepted no-spec with `--no-async-scheduling`:

- It used the same accepted-style KV capacity and graph coverage:
  `2,052,915` KV tokens and capture buckets up to `96`.
- It still failed exact parity against accepted graph mode on the two-prompt
  oracle fixture.
- Natural prompt first diff: token index `25`, newline vs double-newline /
  thinking preamble.
- Repetitive prompt first diff: token index `14`, then the candidate repeats
  the prompt and stops at `49` tokens.
- Its early slot mappings match accepted graph mode, not graph-placebo mode.
  This means the no-async control exposed a scheduler/sampling/output drift
  even before the speculative KV-layout drift seen in placebo.

Interpretation:

- The n-gram/spec branch is now gated by two issues:
  1. async-disabled no-spec output drift;
  2. speculative-config KV/slot-layout drift.
- Do not spend more time on n-gram throughput until the no-async fixture and
  graph-placebo fixture both pass exact parity.
- MTP and DFlash remain more promising than n-gram because vLLM can keep async
  scheduling enabled for those methods, but they still need the same verifier
  input invariant tests.

MTP sidecar attempt:

- The current Quark W8A8 INT8 checkpoint advertises
  `mtp_num_hidden_layers: 1` in config metadata, but its safetensor index does
  not contain `mtp`, `nextn`, `shared_head`, `model.layers.48`, or
  `model.layers.49` tensors.
- The official cached `Qwen/Qwen3.6-35B-A3B-FP8` snapshot does contain MTP
  tensors, so it was tested as a proposer-only sidecar while keeping the Quark
  model as final verifier.
- vLLM accepted the MTP config and kept async scheduling enabled, but failed
  during worker weight loading with:
  `KeyError: 'layers.0.mlp.experts.w2_weight_scale_inv'`.
- Likely root cause: `Qwen3_5MTP.load_weights` is entering an FP8 MoE scale
  path where the instantiated MTP parameter dictionary does not expose the
  expected expert `*_weight_scale_inv` parameters. This looks like an
  MTP-plus-FP8-MoE loader integration gap, not a model-quality problem.

Immediate things to try:

1. Retry the same FP8 MTP sidecar with explicit draft quantization in
   `speculative_config`, first `"quantization":"fp8"`, then
   `"quantization":"compressed-tensors"` if vLLM accepts it.
2. Inspect `vllm/model_executor/models/qwen3_5_mtp.py` around the failed
   `w2_weight_scale_inv` lookup and compare it with the normal Qwen3.6 FP8 MoE
   loader. Patch the loader or quant config plumbing, not verifier math.
3. Add the model-input invariant gate to every candidate:
   `input_ids`, positions, logits indices, slot mappings, block tables, graph
   capture size, scheduler mode, lookahead blocks, and KV capacity.
4. Add a specific "no-async accepted parity" CI-like check, because it is a
   smaller repro than real speculation and should be easier to hand upstream.
5. If MTP loads, test `num_speculative_tokens=1` first, then `2`, then `3/4`
   only if acceptance rate remains stable and the repeat64 + long-context gates
   pass.

Fresh external signals worth tracking:

- vLLM's Qwen3.6-35B-A3B recipe documents official MTP serving syntax with
  `--speculative-config '{"method": "mtp", "num_speculative_tokens": 2}'`.
  Source: `https://recipes.vllm.ai/Qwen/Qwen3.6-35B-A3B`
- The same recipe shows the DGX Spark/Blackwell recipe using MTP with
  `num_speculative_tokens=3`, FP8 KV cache, lower context, and constrained
  concurrency. That suggests `k=3` may be a practical sweep point, but only
  after `k=1` loads and passes quality gates.
- Intel's Arc Pro B-Series vLLM writeup explicitly calls out MoE
  optimization, speculative decoding, async scheduling, prefill/decode
  disaggregation, TP/PP/DP, and PCIe P2P as supported optimization areas.
  Source: `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`
- The open vLLM XPU issue for dual Arc B580 30B+ serving is worth watching as a
  nearby consumer-Arc configuration signal:
  `https://github.com/vllm-project/vllm/issues/35638`
- A public Qwen3.6 speculative repo reports that matched flags and disabling
  prefix caching changed a vLLM MTP result from negative to positive on 2x3090.
  We already run prefix caching disabled, but this reinforces that every spec
  run needs a strict matched-flags control.
  Source: `https://github.com/thc1006/qwen3.6-speculative-decoding-rtx3090`
- Intel/Xe2 public material cites high INT8 theoretical throughput on
  Battlemage-class GPUs. Our current single-request decode being around
  `100 tok/s` after the best clean tuning means the likely losses are launch,
  routing, collective, graph, and small-shape utilization, not raw INT8 TOPS.
  Source: `https://arxiv.org/html/2508.06753v2`

Bigger, bolder ideas to keep on the board:

1. Make "scheduler equivalence" an upstreamable correctness patch.
   - Build a tiny, no-secret repro where accepted async graph and no-async
     graph must produce identical greedy tokens for fixed seed and fixed
     prompts.
   - If XPU async-disabled mode is drifting due to scheduler, logits ordering,
     or cache metadata, fixing that could unlock all speculative methods at
     once.

2. Repair Qwen3.6 FP8 MTP as proposer-only, not as a new production model.
   - The final token source remains Quark W8A8 INT8.
   - If the sidecar only proposes, then small numeric differences in the FP8
     sidecar can reduce acceptance but cannot lower final answer quality.
   - This is still the cleanest path to `>200 tok/s` if XPU can verify multiple
     accepted tokens efficiently.

3. Quark-compatible MTP transplant.
   - If loader repair is ugly, create a local proposer checkpoint that contains
     only Qwen3.6 MTP tensors plus the minimum config/index changes needed for
     vLLM to load it as a draft.
   - Keep all verifier weights and logits from the existing Quark checkpoint.
   - This might avoid forcing the full official FP8 checkpoint through the same
     quantization path as the verifier.

4. Learned micro-drafter distilled from the current Quark endpoint.
   - Train or fit a very small same-tokenizer draft head on traces generated by
     the current Quark model.
   - The verifier still decides final tokens, so quality is preserved; the
     risk is only speed/acceptance.
   - This is bolder than native MTP but could be tailored to B70-friendly
     kernels and short candidate lengths.

5. Expert-parallel or hybrid TP/EP decode experiment.
   - TP4 may be spending too much single-token time in all-reduce and
     cross-rank MoE logistics.
   - Test whether routing experts by rank, or duplicating only hot shared/hot
     routed experts, beats pure TP for c1 decode.
   - Measure memory cost explicitly against the 32K production target.

6. Persistent decode loop for one-token and multi-column verifier.
   - Intel's own MoE direction mentions persistent-loop style kernels. Build a
     microbench that keeps the decode loop resident and feeds one token, two
     candidate columns, and four candidate columns through the exact Qwen3.6
     dense/GDN/MoE shapes.
   - If launch overhead is a major tax, this could matter more than another
     high-level vLLM flag.

7. Route-histogram-driven grouped GEMM/prepack.
   - Collect real expert-route histograms from our prompts and benchmark
     skewed distributions, not uniform synthetic expert traffic.
   - Prepack or reorder W8A8 expert weights for the hot shapes and test whether
     grouped GEMM overhead drops.

8. Collective surgery.
   - Profile every per-token collective on TP4 and test alternatives:
     fused GEMM+all-reduce, reduce-scatter/all-gather variants, oneCCL knobs,
     peer-copy settings, and rank placement.
   - If all-reduce is the c1 ceiling, no quantization or draft trick will hit
     `>200 tok/s` until this is addressed.

9. Core-decode harness as a second product route.
   - Build a direct in-process decode API that bypasses OpenAI server request
     lifecycle, streaming overhead, and tokenizer detours while still using the
     same vLLM model runner and weights.
   - If it is materially faster, production can expose a low-latency lane
     without changing model quality.

10. OpenVINO/oneDNN Graph or IPEX-LLM export probe for the current INT8 shape.
    - This is a bigger departure from vLLM, but Intel's native graph stack may
      have better small-batch INT8/XMX scheduling for this exact architecture.
    - It is only acceptable if the exported model is token-identical or final
      logits remain verifier-equivalent under the same quality suite.

11. Two-tier serving with a fast verifier lane and full-context lane.
    - Keep the 32K context route as the correctness and production-default
      target.
    - Offer an explicitly labeled 8K/16K low-latency route only if the freed
      memory buys hot-expert duplication, larger graph buckets, or MTP sidecar
      headroom without quality drift.

12. Upstream bounty-style repro package.
    - Package the no-async drift fixture, MTP loader failure, W8A8 dense/MoE
      microbench shapes, route histograms, B70 topology, and Localmaxxing row.
    - Aim it at vLLM/XPU and `vllm-xpu-kernels` maintainers with one question:
      "What is the missing XPU path for Qwen3.6 c1 W8A8 MoE decode?"

Latest status pointer:

- The force-block FP8 MTP sidecar result is recorded above under
  "Force-Block FP8 MTP Loader Result".
- Short version: loader breakthrough, not a production win. The sidecar loads
  with `VLLM_QWEN35_MTP_FORCE_FP8_BLOCK=1`, but the clean solo completions run
  device-losts in `block_table.copy_to_gpu` before any scheduled MTP draft
  tokens appear.
- Next highest-value experiments are:
  1. perfect-draft verifier upper-bound runner
  2. real-router trace corpus for MoE microbenches
  3. force-block MTP retry with explicit memory/graph isolation controls
  4. upstreamable B70 repro packet for vLLM/vllm-xpu-kernels

## Perfect-Draft K4 Upper-Bound Probe

This run tested whether the current verifier path can benefit from perfect
drafts before spending more time on real proposer/MTP work. The drafter was the
local oracle path in `NgramProposer`: it reads the accepted baseline completion
tokens and proposes the exact next baseline tokens. This is the best-case
acceptance setup for the current speculative scheduler path.

Procedure:

1. Captured a fresh accepted p512/o256 baseline from the current Quark W8A8
   INT8 verifier on `18080`.
2. Paused and drained the public frontdoor.
3. Stopped the accepted backend.
4. Launched an isolated oracle backend on `18081` with:

```bash
NUM_SPECULATIVE_TOKENS=4 \
ORACLE_TRACE=data/qwen36-quark-int8-tp4-perfectdraft-k4-accepted-p512o256-20260611.json \
CUDAGRAPH_CAPTURE_SIZES=1,2,3,4,5,6,7,8,16,24,32,40,48,56,64,72,80,88,96,104,112,120,128 \
scripts/launch-qwen36-quark-int8-oracle-trace.sh
```

5. Ran the same p512/o256 completion prompts against the oracle backend.
6. Restored the accepted backend on `18080`, smoke-tested backend and
   frontdoor, then removed the pause marker.

Artifacts:

- accepted baseline:
  `data/qwen36-quark-int8-tp4-perfectdraft-k4-accepted-p512o256-20260611.json`
- candidate completions:
  `data/qwen36-quark-int8-tp4-perfectdraft-k4-candidate-p512o256-20260611a.json`
- scheduler summary:
  `data/qwen36-quark-int8-tp4-perfectdraft-k4-spec-summary-20260611a.json`
  and
  `data/qwen36-quark-int8-tp4-perfectdraft-k4-spec-summary-20260611a.md`
- reduced drift fixture:
  `data/qwen36-quark-int8-tp4-perfectdraft-k4-drift-fixture-20260611a.json`
  and
  `data/qwen36-quark-int8-tp4-perfectdraft-k4-drift-fixture-20260611a.md`
- raw traces:
  `data/qwen36-quark-int8-tp4-perfectdraft-k4-spec-trace-20260611a.jsonl`
  and
  `data/qwen36-quark-int8-tp4-perfectdraft-k4-draft-20260611a.jsonl`

Result:

- Quality failed:
  - `baseline_match_all=false`
  - reduced fixture `exact_match_all=false`
  - mismatch count: `2/2`
- First diffs:
  - `natural_latency_plan`: output index `17`, accepted ` and`, candidate
    ` hardware`
  - `repetitive_kernel_notes`: output index `5`, accepted ` output`,
    candidate ` input`
- Scheduler trace:
  - rows: `5`
  - requests: `2`
  - draft tokens: `20`
  - accepted: `17`
  - rejected: `3`
  - acceptance rate: `85.0%`
  - histogram: `{1: 1, 4: 4}`
- Endpoint timing:
  - accepted baseline combined: `88.765 tok/s` e2e
  - perfect-draft k4 candidate combined: `16.370 tok/s` e2e
  - candidate `natural_latency_plan`: `8.963 tok/s`
  - candidate `repetitive_kernel_notes`: `94.304 tok/s`

Interpretation:

- This did not measure a useful `>200 tok/s` upper bound. The speculative path
  drifted early, so the oracle stopped matching after only a few rows and the
  run mostly became a slow/ordinary decode with broken parity.
- Perfect drafts are not enough until the stage-1 scheduler/model-input
  invariants are fixed. The current problem is before real proposer quality:
  exact drafted tokens can still lead to different verifier output.
- The `k=4` run reinforces the earlier placebo/no-async findings. Do not run
  more MTP/DFlash/n-gram speed sweeps until graph-mode no-spec, placebo, and
  oracle paths have matching verifier inputs and exact output parity.

Next action after this result:

1. Prioritize scheduler/model-input invariant repair over proposer quality.
2. Add block-table trace capture using the proper `BlockTable` accessors.
3. Build a reusable accepted-vs-placebo input parity checker.
4. In parallel, start real-router histogram capture because it is independent
   of speculative correctness and feeds the MoE/kernel path.

## Post-PerfectDraft Idea Backlog

The latest public-data refresh is saved in:

- `data/localmaxxing-qwen36-35b-a3b-top-after-perfectdraft-20260611.json`
- `data/localmaxxing-qwen-30b-class-top-after-perfectdraft-20260611.json`

Source links:

- `https://localmaxxing.com/api/leaderboard?hfId=Qwen%2FQwen3.6-35B-A3B&limit=20`
- `https://localmaxxing.com/api/leaderboard?modelFamily=qwen&paramSize=30&limit=30`
- `https://www.localmaxxing.com/en/api-docs`
- `https://recipes.vllm.ai/Qwen/Qwen3.6-35B-A3B`

External signals to keep in mind:

- Localmaxxing has Qwen3.6 35B-class rows above `200 tok/s`, but the fastest
  rows mostly lean on either native MTP/speculation, DFlash, NVFP4/FP4-class
  weights, Blackwell-specific compile paths, or non-XPU engines. They are
  useful directionally; they are not direct proof that our exact Quark W8A8
  INT8 verifier can hit the same numbers without backend work.
- vLLM's Qwen3.6 recipe documents native MTP serving for
  `Qwen/Qwen3.6-35B-A3B`, so MTP is a real upstream path for this model family.
  Our current Quark checkpoint lacks MTP tensors, and the FP8 sidecar loader
  still device-losts before useful draft rows. Treat MTP as a proposer-sidecar
  engineering problem, not a final-model replacement.
- Intel/XPU examples continue to validate Arc/B-series inference support, but
  the missing piece for this workload remains a fast, stable small-batch
  Qwen3.6 A3B MoE W8A8 path: route packing, grouped GEMM, collectives, and
  graph capture all have to work together.

Immediate items now on the list:

1. Block-table parity instrumentation.
   - Fix the model-input trace to record `BlockTable` state through
     `get_cpu_tensor()`, `get_numpy_array()`, or `get_gpu_tensor(num_reqs)`
     instead of trying to serialize the object directly.
   - Goal: prove whether the accepted, no-async, placebo, oracle, and MTP
     loader paths feed identical verifier input tables before their first
     output-token divergence.

2. Accepted-vs-placebo parity checker.
   - Add a row-by-row trace comparator that normalizes volatile request IDs and
     compares input IDs, positions, logits indices, slot mappings, block
     tables, scheduled-token counts, graph bucket, and speculative metadata.
   - Make this a gate: no speculative speed claim counts unless the parity
     checker reports exact verifier-input agreement up to the divergence point.

3. Real-router histogram capture.
   - Collect actual expert IDs and per-expert row counts from accepted
     prompt-class traffic.
   - Feed those histograms into the primitive MoE hotpack and grouped-GEMM
     microbenches so kernel work targets real Qwen3.6 decode distributions.

4. Token-level timing budget.
   - Record per-token wall time and split it into scheduler, attention,
     MoE route/remap, grouped GEMM, all-reduce, logits, and stream overhead.
   - Use this to decide whether the next `2x` attempt should be speculation,
     MoE kernels, collectives, or runtime scheduling.

5. Publish-grade benchmark refresh.
   - Once a candidate beats the accepted baseline, rerun r8/r10 with peak VRAM,
     TTFT, prompt/output token counts, exact quality suite, repeat64, 8K needle,
     and frontdoor/backend health.
   - Submit only quality-clean results; keep negative experiments in the repo
     notes, not on the public leaderboard.

Bigger bets worth pursuing if the parity tooling does not reveal a small bug:

1. First-class Quark-verifier MTP sidecar.
   - Build a proposer-only sidecar from the official Qwen3.6 FP8/MTP tensors or
     a same-tokenizer trained proposer, but always verify with the current
     Quark W8A8 INT8 model.
   - Success condition: accepted-vs-sidecar exact text/token parity plus a
     measured acceptance/overhead curve showing a plausible path past `200
     tok/s`.

2. DFlash-style drafter for XPU.
   - Port only the algorithmic shape first: draft multiple tokens from a cheap
     lane, then replay through the Quark verifier.
   - The bold version is a small XPU-resident drafter with its own command list
     and no host round trips; the conservative version is a diagnostic drafter
     that proves scheduler correctness before optimizing.

3. Persistent Qwen3.6 A3B MoE executor.
   - Replace the current small-batch route/remap/grouped-GEMM path with a
     persistent executor specialized for `top_k`, active hidden size, and the
     accepted Quark tensor layout.
   - Keep row packing, expert metadata, activation quantization, and W8A8 GEMM
     inside one long-lived execution plan instead of rebuilding transient
     scratch every token.

4. Layer-local hot expert replication.
   - Use real histograms to identify stable hot experts per layer, then
     replicate only those experts across ranks or place them on the rank that
     pays the least collective cost.
   - Quality does not change if weights and routing are identical; the risk is
     memory pressure and synchronization complexity.

5. Hybrid TP/EP layout for single-user decode.
   - Simulate a layout where dense attention remains TP4, but MoE expert work
     is routed more like expert parallelism for decode rows.
   - This is a large runtime change, but it directly attacks the likely
     underutilization from four GPUs doing tiny per-rank MoE fragments.

6. Direct single-request graph runner.
   - Build a narrow offline runner for one request, fixed batch shape, fixed
     decode graph buckets, no OpenAI server, no SSE, no general scheduler.
   - If this cannot beat the service path materially, it closes off a whole
     class of host/runtime-overhead guesses. If it does, port the winning
     pieces back into production.

7. Whole-token command-list capture.
   - Try to capture the complete decode token path, including scheduler-visible
     graph buckets, attention, MoE, collectives, and logits, as a replayable XPU
     command sequence.
   - This is more ambitious than piecewise graph capture and may need static
     slot/block-table layouts, but it is one of the few paths that could remove
     enough launch/synchronization overhead for a large jump.

8. XPU-native W8A8 weight retile cache.
   - Build a persistent converted-weight cache that stores the exact tile/order
     expected by the fastest XPU GEMM/MoE kernels.
   - The current `8.49 GiB` loaded-weight number is plausible for 8-bit
     active/compressed MoE metadata, but runtime can still pay retile/repack
     costs unless the serving format is kernel-native.

9. Same-model 8-bit engine bakeoff.
   - Keep the final model exact or verifier-equivalent, then test vLLM/XPU,
     llama.cpp SYCL/GGUF W8-ish paths, OpenVINO/oneDNN GenAI if Qwen3.6 MoE is
     supported, SGLang if XPU coverage is usable, and any new Intel/vLLM XPU
     kernel branch.
   - This is not a license to switch to 4-bit; it is a way to find whether the
     bottleneck is vLLM's current XPU path versus the hardware.

10. Production service classes instead of one universal endpoint.
    - Long-context, high-concurrency, and short-interactive requests may need
      different graph/cache/concurrency settings.
    - A short-context single-request lane could use aggressive fixed-shape
      graph capture and lower scheduler generality, while a 32K production lane
      keeps conservative stability settings.

11. Upstreamable B70 repro packet.
    - Package the parity traces, the perfect-draft drift fixture, the no-async
      and placebo artifacts, and the primitive MoE timing evidence into a small
      public issue/repro for vLLM/XPU and Intel kernel maintainers.
    - The ask should be narrow: exact Qwen3.6 A3B W8A8 small-batch decode on
      Arc/B70 needs fast MoE and correct speculative verifier-state handling.

12. Reliability as a first-class benchmark axis.
    - Track device-lost frequency, graph-cache cold-start behavior, long-lived
      process repeat quality, and restore-after-experiment health checks as
      metrics beside tok/s.
    - A `150 tok/s` candidate that device-losts under soak is less useful than
      a `115 tok/s` candidate that survives production traffic.

## Model-Input Parity Tooling And Block-Table Trace Patch

Added the first reusable verifier-input parity tool and patched the local vLLM
trace instrumentation so the next accepted/placebo/speculative trace can expose
real block-table contents instead of serializing an error.

Code/artifacts:

- `scripts/check-qwen36-model-input-parity.py`
- `patches/vllm-qwen36-model-input-blocktable-trace-20260611.patch`
- `data/qwen36-quark-int8-tp4-accepted-vs-placebo-modelinput-parity-20260611a.json`
- `data/qwen36-quark-int8-tp4-accepted-vs-placebo-modelinput-parity-20260611a.md`
- `data/qwen36-quark-int8-tp4-accepted-vs-noasync-modelinput-parity-20260611a.json`
- `data/qwen36-quark-int8-tp4-accepted-vs-noasync-modelinput-parity-20260611a.md`

Patch details:

- Active runner: `vllm/v1/worker/gpu_model_runner.py`
  - The old trace path tried to run tensor serialization on a `BlockTable`
    object, yielding `AttributeError("'BlockTable' object has no attribute
    'detach'")` in every trace row.
  - The patch now records block-table state through `get_cpu_tensor()`,
    `get_numpy_array()`, `get_device_tensor(num_reqs)`, and
    `num_blocks_per_row` when those accessors exist.
- Newer GPU runner: `vllm/v1/worker/gpu/model_runner.py`
  - The patch records prepared input block tables, `num_blocks`, persistent
    input block tables, and persistent staged GPU block tables.
- This is env-gated behind `VLLM_XPU_MODEL_INPUT_TRACE_FILE`, so normal serving
  is unaffected.

Existing-trace parity results:

- Accepted vs placebo:
  - rows compared: `80`
  - `match_all=false`
  - first mismatch: row `0`, `attn.slot_mappings.1.head[0]`
  - accepted value: `65536`
  - placebo value: `98304`
  - interpretation: verifier-visible slot mappings differ before any output
    token history can explain drift. The old block-table records were broken,
    so the next runtime trace must rerun with the patched accessors to identify
    the allocator/table source of the slot shift.
- Accepted vs accepted-noasync:
  - rows compared: `80`
  - `match_all=false`
  - first mismatch: row `26`, `input_batch.input_ids.head[0]`
  - interpretation: no-async agrees through the earlier prefill/decode rows and
    only diverges after the output-token stream differs. This is less suspicious
    than placebo and helps rank placebo/block-table repair first.

Validation:

```bash
python3 -m py_compile scripts/check-qwen36-model-input-parity.py
python3 -m py_compile \
  /home/steve/src/vllm/vllm/v1/worker/gpu_model_runner.py \
  /home/steve/src/vllm/vllm/v1/worker/gpu/model_runner.py
python3 scripts/check-qwen36-model-input-parity.py \
  --left data/qwen36-quark-int8-tp4-accepted-modelinput-trace-20260611f.jsonl \
  --right data/qwen36-quark-int8-tp4-placebo-modelinput-trace-20260611a.jsonl \
  --left-label accepted \
  --right-label placebo \
  --output-json data/qwen36-quark-int8-tp4-accepted-vs-placebo-modelinput-parity-20260611a.json \
  --output-md data/qwen36-quark-int8-tp4-accepted-vs-placebo-modelinput-parity-20260611a.md
python3 scripts/check-qwen36-model-input-parity.py \
  --left data/qwen36-quark-int8-tp4-accepted-modelinput-trace-20260611f.jsonl \
  --right data/qwen36-quark-int8-tp4-accepted-noasync-modelinput-trace-20260611a.jsonl \
  --left-label accepted \
  --right-label accepted-noasync \
  --output-json data/qwen36-quark-int8-tp4-accepted-vs-noasync-modelinput-parity-20260611a.json \
  --output-md data/qwen36-quark-int8-tp4-accepted-vs-noasync-modelinput-parity-20260611a.md
```

Next action:

1. Rerun accepted and placebo traces with the patched block-table accessors.
2. Use the parity checker as the gate for any repaired speculation run.
3. If the new block-table traces show allocator/table drift, isolate whether it
   comes from graph capture size, async scheduling, lookahead/spec block
   reservation, or KV-cache capacity/layout differences.

## Bolder Idea Addendum After Model-Input Parity

Added after the first accepted/placebo parity checker showed an immediate
slot-mapping mismatch. These are things to try without changing the final
quality rule: the current Quark W8A8 INT8 model remains the verifier and every
candidate must pass exact token/quality gates before any speed claim counts.

Immediate cleanup before more speed runs:

1. Restore and harden the accepted service before isolated trace work.
   - Current frontdoor/backend health must be checked before and after every
     speculative or sidecar experiment.
   - Add a small restore checklist: backend `/health`, backend generation,
     frontdoor `/health`, local-only exact token trace, and external traffic
     pause/drain state.
   - This prevents a stale or device-lost backend from contaminating quality
     and performance notes.

2. Make static block-table parity the first speculation gate.
   - Rerun accepted/placebo/no-async/oracle traces with fixed block-table
     accessors.
   - If placebo already shifts slot mappings at row 0, build a minimal
     allocator fixture before touching MTP, DFlash, or n-gram width again.
   - A plausible fix branch is deterministic slot/block allocation for
     single-stream c1 tests, even if production keeps the general allocator.

3. Prove the perfect-draft upper bound only after parity is clean.
   - Reuse the oracle/perfect-draft harness, but require verifier-input parity
     through the first divergent token.
   - If perfect draft still cannot exceed the baseline after parity repair,
     speculation is not the near-term 2x path on this vLLM/XPU stack.
   - If perfect draft jumps meaningfully, then invest in MTP/sidecar proposer
     work.

Larger things to try:

1. Deterministic KV arena for solo decode.
   - Preallocate a fixed KV/block arena for one request and hold block IDs,
     slot mappings, graph bucket, and cache positions stable across accepted,
     placebo, and speculative runs.
   - This is narrower than production vLLM scheduling, but it can prove whether
     scheduler/block-table movement is the source of verifier drift.
   - If it works, fold it into a production single-request latency lane.

2. Multi-column verifier graph buckets.
   - Instead of treating speculation as scheduler magic around ordinary decode,
     create explicit graph buckets for verifying 2, 4, and 8 candidate columns
     with stable slot tables.
   - The drafter can be n-gram, MTP, or sidecar; the key is that the verifier
     graph sees a deterministic shape and deterministic cache layout.
   - This is a cleaner path to DFlash/EAGLE-style gains than trying to patch
     generic speculative scheduling blind.

3. Quark-compatible MTP sidecar with tiny verifier integration.
   - Keep the current Quark checkpoint untouched.
   - Load only the official Qwen3.6 MTP/proposer tensors in a sidecar process
     or auxiliary model runner, then feed candidates into the Quark verifier.
   - Score the sidecar on end-to-end accepted-token speed, not draft speed. A
     fast sidecar that causes low acceptance or scheduler drift is not useful.

4. Learned B70-native micro-drafter.
   - Generate a trace corpus from the current Quark verifier and train a small
     same-tokenizer drafter/head for common interactive patterns.
   - This can be B70-friendly: shallow, static shape, low memory, and optimized
     for high acceptance at candidate length 2-4.
   - Quality remains unchanged only if the Quark verifier owns final tokens.

5. Route-to-kernel compiler for Qwen3.6 A3B MoE.
   - Capture real route windows, then generate or select specialized grouped
     GEMM schedules for the observed layer/prompt route patterns.
   - Start with a runtime policy table; the bold version emits route-window
     specific command lists or Triton/SYCL kernels.
   - This attacks the likely real bottleneck: small, skewed expert work rather
     than uniform synthetic MoE microbench traffic.

6. Hot-expert memory-for-latency mode.
   - Use route histograms to duplicate only high-probability experts or shared
     expert fragments on multiple ranks.
   - The weights and routing stay identical, so quality should be unchanged;
     the tradeoff is VRAM versus fewer cross-rank fragments and collectives.
   - Make this a separate service class if it cannot fit with full 32K context.

7. Hybrid TP/EP simulator before runtime surgery.
   - Build a memory/traffic model for TP4, TP2x2 replicas, TP+expert parallel,
     and hot-expert replication.
   - Feed it real route histograms, KV size, W8A8 weight memory, and collective
     timings.
   - Only implement the layout if the model predicts a credible c1 decode win.

8. Whole-token command-list runner.
   - Capture the complete one-token path as a stable Level Zero command-list
     sequence: attention, GDN projection, MoE route/remap, W8A8 GEMMs,
     collectives, logits, and sampling.
   - This is a moonshot because it likely needs static slots and fixed graph
     buckets, but it could remove enough launch/synchronization overhead to
     matter.

9. XPU W8A8 kernel branch against `vllm-xpu-kernels`.
   - Move from Python/vLLM wrapper experiments to shape-exact kernel work:
     dense W8A8 small-M GEMM, routed grouped GEMM, activation plus second
     quant, and MoE finalize.
   - Package every microbench with exact shapes and parity checks so it can be
     upstreamed or shared with Intel/vLLM maintainers.

10. Exact 8-bit engine shootout with production constraints.
    - Test current vLLM Quark W8A8 against llama.cpp/SYCL Q8-ish GGUF,
      OpenVINO/oneDNN GenAI, SGLang XPU if usable, and any new Intel 8-bit
      Qwen3.6 path.
    - This is not a model downgrade exercise. Reject Q4/AWQ/GPTQ-4bit and any
      Qwen3.5 detour for the final candidate.
    - The diagnostic question is whether vLLM/XPU is the bottleneck or whether
      B70 is currently capped by the model/kernel shape itself.

11. Reliability scoreboard beside speed scoreboard.
    - Track device-lost count, graph cold-start failure rate, long-lived
      process repeat drift, restore time, and health-smoke pass rate for every
      candidate.
    - Add this to Localmaxxing notes when publishing strong results. A fast
      benchmark that cannot survive restore/soak is not production progress.

12. Upstream or bounty-style public packet.
    - Prepare a minimal public issue package: exact model ID, hardware, kernel
      stack, Localmaxxing row, block-table parity fixture, perfect-draft drift,
      and routed MoE microbench shapes.
    - Ask a precise question: what XPU path is missing for Qwen3.6 A3B W8A8
      c1 decode on B70?
    - This may be the fastest way to get help on low-level kernels while local
      work continues on parity and router histograms.

Current priority ordering:

1. Restore accepted service health and rerun the fixed block-table traces.
2. Fix or isolate model-input parity before more speculative speed claims.
3. In parallel, collect real-router histograms and token timing because that
   branch does not depend on speculative correctness.
4. After parity is clean, rerun perfect-draft `k=4` as the upper-bound test.
5. Choose the next major branch from evidence:
   - if perfect draft is fast and clean, build the MTP/sidecar/proposer path;
   - if perfect draft is still slow, prioritize persistent MoE, W8A8 kernels,
     and hybrid TP/EP layout work.

## Roadmap-Update Reliability Restore

After the roadmap update, a non-invasive health check found the public
frontdoor returning `502` and `127.0.0.1:18080` refusing connections. The
backend process tree was still partly alive, but no TCP listener remained.

Root observation from the active log:

- log: `/tmp/qwen36-quark-int8-tp4-restored-after-perfectdraft-k4-20260611a.log`
- session: `qwen36-tp4-accepted-restored-after-perfectdraft-k4-20260611a`
- the backend had served repeated remote `10.0.0.214` requests, then stalled on
  a large structured-output request with `prompt_token_ids_len=5907`,
  `max_tokens=2048`, and `structured_outputs.json_object=True`
- fatal error: `TimeoutError: RPC call to sample_tokens timed out`
- vLLM then reported `EngineDeadError`, stopped the HTTP server, and left stale
  worker processes behind

Restore procedure:

1. Created the frontdoor pause file
   `/tmp/qwen36-35b-a3b-fp8-requant-frontdoor-not-paused`, so remote generation
   returns `frontdoor_paused` while loopback requests remain allowed.
2. Called `/drain`; active and queued generation counts were both zero.
3. Killed only the stale accepted backend tmux session and its leftover vLLM
   worker PIDs.
4. Relaunched the accepted backend in
   `qwen36-tp4-accepted-restored-after-roadmap-20260611a` using the fresh graph
   cache root:
   `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-freshrestore-20260611d`
5. Verified:
   - backend `/health`: `200`
   - backend `/v1/models`: served `qwen36-35b-a3b-fp8`
   - direct backend chat smoke: `OK`
   - frontdoor loopback chat smoke while paused: `OK`
   - frontdoor `/health`: `200`
   - frontdoor `/drain`: active `0`, queued `0`, paused `true`

Decision:

- Leave remote public generation paused for now; local loopback bypass through
  port `8000` works and the backend is healthy.
- Before unpausing remote traffic again, add or run a guard for large
  structured-output requests, because the latest fatal incident was not a
  normal small canary. At minimum, monitor `sample_tokens` timeout frequency and
  consider lowering remote `max_active_generations` or routing structured JSON
  to a conservative lane.

## Corrected Spec-Placebo Block-Table Findings And Larger Bets

Added after rerunning accepted graph mode and graph spec-placebo with fixed
BlockTable trace accessors. This replaces the earlier slot-mapping-only
diagnosis with direct block-table evidence.

Artifacts:

- `data/qwen36-quark-int8-tp4-accepted-modelinput-fresh-p512o32-20260611g.json`
- `data/qwen36-quark-int8-tp4-accepted-modelinput-trace-20260611g.jsonl`
- `data/qwen36-quark-int8-tp4-spec-placebo-modelinput-p512o32-20260611a.json`
- `data/qwen36-quark-int8-tp4-spec-placebo-modelinput-trace-20260611a.jsonl`
- `data/qwen36-quark-int8-tp4-accepted-vs-spec-placebo-modelinput-parity-20260611a.json`
- `data/qwen36-quark-int8-tp4-accepted-vs-spec-placebo-modelinput-parity-20260611a.md`

Main observation:

- Fresh accepted graph and graph spec-placebo both ran the same two p512/o32
  completion fixtures.
- Spec-placebo still drifted `2/2` versus the accepted graph baseline.
- The first verifier-input mismatch is row `0`, before any generated token
  divergence can explain it.
- `scheduled_spec_decode_tokens={}`, `use_spec_decode=false`, and
  `spec_token_ids=[[]]` on that row, so the mismatch is caused by speculative
  config/plumbing rather than actual draft tokens.
- The mismatch is now visible as attention block-table allocation:
  - accepted group 0 block table: shape `[1, 1]`, row head `[1]`
  - spec-placebo group 0 block table: shape `[1, 2]`, row head `[1, 2]`
  - accepted groups 1/2 similarly use one attention block, while placebo uses
    two blocks per attention group
  - GDN/mamba block groups also shift to different ID ranges
- The spec-placebo backend also reported lower KV capacity (`1,955,157` tokens)
  than the accepted graph backend (`2,052,915` tokens), consistent with extra
  speculative/lookahead block reservation.

Conclusion:

- The next speculation repair is not proposer quality. It is allocator/input
  parity.
- Do not benchmark MTP, DFlash, EAGLE, n-gram widths, or oracle speed again
  until accepted graph and spec-placebo graph produce identical model-input
  rows on the reduced fixture.
- The first target is a zero-lookahead placebo path: speculative config present,
  no draft tokens, no extra reserved KV blocks, identical block tables, identical
  slot mappings, identical graph bucket, and identical output tokens.

Validation commands:

```bash
/home/steve/.venvs/vllm-xpu/bin/python scripts/qwen36-completion-oracle-trace.py \
  --base-url http://127.0.0.1:18081 \
  --prompt-tokens 512 \
  --output-tokens 32 \
  --output-json data/qwen36-quark-int8-tp4-accepted-modelinput-fresh-p512o32-20260611g.json \
  --timeout 240

/home/steve/.venvs/vllm-xpu/bin/python scripts/qwen36-completion-oracle-trace.py \
  --base-url http://127.0.0.1:18081 \
  --prompt-tokens 512 \
  --output-tokens 32 \
  --baseline-json data/qwen36-quark-int8-tp4-accepted-modelinput-fresh-p512o32-20260611g.json \
  --output-json data/qwen36-quark-int8-tp4-spec-placebo-modelinput-p512o32-20260611a.json \
  --timeout 240

python3 scripts/check-qwen36-model-input-parity.py \
  --left data/qwen36-quark-int8-tp4-accepted-modelinput-trace-20260611g.jsonl \
  --right data/qwen36-quark-int8-tp4-spec-placebo-modelinput-trace-20260611a.jsonl \
  --left-label accepted \
  --right-label spec-placebo \
  --output-json data/qwen36-quark-int8-tp4-accepted-vs-spec-placebo-modelinput-parity-20260611a.json \
  --output-md data/qwen36-quark-int8-tp4-accepted-vs-spec-placebo-modelinput-parity-20260611a.md \
  --max-mismatches 12
```

Source scan worth tracking:

- vLLM/Intel public B-series notes say current XPU vLLM work includes MoE
  optimization, DP/TP/PP, async scheduling, prefill/decode disaggregation, and
  n-gram/EAGLE/EAGLE3 speculation:
  `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`
- vLLM XPU is actively moving toward the separate `vllm-xpu-kernels` library:
  `https://github.com/vllm-project/vllm/issues/33214`
- `vllm-xpu-kernels` release notes now mention mixed prefill/decode attention
  tuning and MoE grouped-GEMM policy updates, including FP8 and small-K cases:
  `https://github.com/vllm-project/vllm-xpu-kernels/releases`
- Intel's grouped-GEMM tuning issue explicitly calls out decode-stage route
  skew and suggests real token distributions as the tuning input, matching the
  route-capture/hotpack evidence from this lab:
  `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`
- The `vllm-xpu-kernels` issue list has an open TurboQuant KV-cache feasibility
  item and GDN kernel exposure requests; both are relevant but quality-risked
  until exact canaries pass:
  `https://github.com/vllm-project/vllm-xpu-kernels/issues`
- A recent Intel GPU inference paper lists B580-class Battlemage hardware at
  `456 GB/s` GDDR6 bandwidth and `233 TOPS` INT8 peak. That reinforces that our
  `~100 tok/s` c1 endpoint is not plausibly compute-peak limited; launch,
  routing, collectives, memory movement, or scheduler shape effects are likely
  dominating:
  `https://arxiv.org/html/2508.06753v2`
- Localmaxxing public exact-model query still shows the current approved B70
  row as the top and only exact `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
  result at `99.428358` tok/s output, `76.454061 ms` TTFT, and `196.325273`
  total tok/s:
  `https://localmaxxing.com/api/benchmarks?hfId=nameistoken%2FQwen3.6-35B-A3B-Quark-W8A8-INT8&limit=20`

Concrete things to try next:

1. Zero-lookahead spec-placebo repair.
   - Find where vLLM reserves extra speculative/lookahead KV blocks on XPU.
   - Add an opt-in diagnostic mode where speculative config exists but
     `num_speculative_tokens=0` semantically, allocator state matches no-spec,
     and the drafter path is inert.
   - Gate on `match_all=true` from
     `check-qwen36-model-input-parity.py` before any speed work.

2. Deterministic solo KV arena.
   - For c1 single-request latency tests, preallocate fixed block IDs and reuse
     the same slot/block tables across accepted, placebo, oracle, and future
     proposer modes.
   - This is a narrower production lane than general vLLM scheduling, but it
     could remove both correctness drift and allocator overhead for the user's
     most important case.

3. Static verifier-bucket runner.
   - Build explicit verifier graphs for bucket sizes `1,2,3,4,6,8` with fixed
     KV layout and fixed candidate columns.
   - Feed candidates from n-gram/oracle/MTP only after the verifier graph path
     itself is proven identical in placebo mode.
   - This is the clean path toward using the earlier bucket-timing headroom
     (`bucket 6/8` sublinear forward time) without corrupting output.

4. Auxiliary proposer API instead of model grafting.
   - Stop trying to make official FP8 MTP tensors look like part of the Quark
     checkpoint until the state-index issue is understood.
   - Define a sidecar interface: proposer returns candidate token IDs plus
     metadata; Quark verifier owns final token emission.
   - This keeps quality unchanged by construction if verifier parity and
     rollback accounting pass.

5. Quark-trace-trained micro-drafter.
   - Generate a corpus from the current Quark verifier under production prompts
     and train a tiny same-tokenizer drafter for length `2-4` candidates.
   - Optimize for acceptance and low XPU latency, not language-model quality.
   - This could beat n-gram acceptance on natural/chat prompts while keeping
     final output verified by the current model.

6. Route-window persistent MoE kernel in `vllm-xpu-kernels`.
   - Use real route histograms from this lab as the benchmark input instead of
     synthetic uniform rows.
   - Target small-M W8A8 grouped GEMM, route/remap, activation, second quant,
     and combine/finalize as one persistent decode kernel path.
   - This aligns with Intel's public grouped-GEMM tuning direction and avoids
     pretending endpoint speed will move from isolated dense GEMM flags alone.

7. Layer-local hot-expert memory-for-latency lane.
   - Use K32/K64 route coverage to duplicate only the hottest experts or expert
     fragments on selected ranks.
   - Quality should be bit-identical if the same weights are used; the tradeoff
     is VRAM and possibly lower max context/concurrency in a latency lane.
   - Simulate before implementing: route histograms, per-rank memory, all-reduce
     traffic, and expected c1 decode savings.

8. Hybrid TP/EP layout simulator.
   - Model TP4, TP2+expert-parallel, TP2x2 replicas, and hot-expert replicated
     layouts using measured collectives and real routes.
   - Single-user speed may prefer less TP for some layers if TP4 collectives and
     small-M fragmentation dominate.
   - Reject layouts that cannot preserve 32K service or exact outputs unless
     they become an explicitly separate short-context class.

9. Whole-token Level Zero command-list runner.
   - Capture one complete decode token as a fixed command-list sequence:
     attention, GDN, MoE routing, W8A8 GEMMs, collectives, logits, sampler.
   - This is a larger lift than graph-cache tweaks, but it is one of the few
     ideas that attacks launch/synchronization overhead directly.

10. Direct XPU kernel shootout with exact shapes.
    - Build a small suite around our actual generated graph shapes:
      dense W8A8 small-M GEMM, GDN projection, MoE grouped GEMM, finalize, and
      all-reduce boundaries.
    - Compare current vLLM path, `vllm-xpu-kernels` latest, oneDNN grouped GEMM
      where applicable, and a hand-tuned SYCL/Triton-XPU prototype.
    - Only promote a kernel if endpoint canaries pass exact parity.

11. KV-cache compression as a VRAM/headroom experiment, not a speed claim.
    - Track TurboQuant/KV-cache work because it may unlock larger batch/context
      or memory-for-latency expert replication.
    - Do not use it for the primary quality target unless exact token canaries,
      long-context needle, and repeat stability pass.

12. Upstreamable B70 repro packet.
    - Bundle the exact Localmaxxing row, block-table parity fixture, bucket
      timing evidence, route histogram evidence, and a tiny script that shows
      spec-placebo row-0 block-table drift.
    - Post it upstream only with a narrow ask: how should XPU speculative
      decode allocate lookahead blocks without changing verifier inputs?

Current priority order:

1. Restore accepted backend and keep public remote traffic paused until the
   large structured-output crash path has a guard.
2. Repair zero-lookahead placebo parity.
3. If parity is clean, rerun perfect-draft/oracle bucket tests as the speed
   upper bound.
4. If bucket tests still show `>200 tok/s` endpoint-normalized headroom, build
   the sidecar proposer path.
5. In parallel, collect route histograms and shape-exact XPU kernel timings for
   the MoE/static-runner fallback path.

Restore after this diagnostic:

- Stopped isolated spec-placebo session:
  `qwen36-tp4-spec-placebo-modelinput-20260611a`
- Relaunched accepted backend session:
  `qwen36-tp4-accepted-restored-after-spec-placebo-20260611a`
- Restore log:
  `/tmp/qwen36-quark-int8-tp4-accepted-restored-after-spec-placebo-20260611a.log`
- Backend `/health`: `200`
- Backend `/v1/models`: serving `qwen36-35b-a3b-fp8` from current Quark W8A8
  INT8 snapshot
- Direct backend chat smoke: `OK`
- Frontdoor loopback chat smoke: `OK`
- Frontdoor `/status`: `paused=true`, `pause_allow_local=true`,
  `active_generations=0`, `queued_generations=0`, backend
  `http://127.0.0.1:18080`
- Remote generation remains intentionally paused.

## Zero-Lookahead Placebo Repair

Added after the corrected BlockTable finding. The prior placebo mode already
cleared scheduled draft tokens and scheduler lookahead, but Qwen3.6's GDN/mamba
KV spec still baked `num_speculative_blocks=1` into the cache layout whenever a
speculative config was present. That lower-level reservation caused the row-0
block-table drift and reduced KV capacity.

Patch:

- `patches/vllm-qwen36-spec-placebo-zero-mamba-blocks-20260611.patch`
- Local source touched:
  `/home/steve/src/vllm/vllm/model_executor/layers/mamba/abstract.py`
- Behavior:
  - If `VLLM_XPU_SPEC_DECODE_PLACEBO=1`, `MambaSpec.num_speculative_blocks`
    is forced to `0`.
  - Normal speculative runs keep `num_speculative_blocks =
    speculative_config.num_speculative_tokens`.
  - This keeps the diagnostic narrow: speculative config/proposer plumbing can
    still be constructed, but the verifier/cache layout is no longer shifted by
    unused speculative mamba blocks.

New artifacts:

- `data/qwen36-quark-int8-tp4-accepted-modelinput-zerolookahead-p512o32-20260611a.json`
- `data/qwen36-quark-int8-tp4-accepted-modelinput-zerolookahead-trace-20260611a.jsonl`
- `data/qwen36-quark-int8-tp4-spec-placebo-zerolookahead-p512o32-20260611a.json`
- `data/qwen36-quark-int8-tp4-spec-placebo-zerolookahead-trace-20260611a.jsonl`
- `data/qwen36-quark-int8-tp4-accepted-vs-spec-placebo-zerolookahead-parity-20260611a.json`
- `data/qwen36-quark-int8-tp4-accepted-vs-spec-placebo-zerolookahead-parity-20260611a.md`
- `data/qwen36-quark-int8-tp4-accepted-noasync-modelinput-p512o32-20260611a.json`
- `data/qwen36-quark-int8-tp4-accepted-noasync-modelinput-trace-20260611a.jsonl`
- `data/qwen36-quark-int8-tp4-accepted-noasync-vs-spec-placebo-zerolookahead-parity-20260611a.json`
- `data/qwen36-quark-int8-tp4-accepted-noasync-vs-spec-placebo-zerolookahead-parity-20260611a.md`

Results:

- Patched spec-placebo KV capacity is back to `2,052,915` tokens, matching
  no-spec accepted. The old unpatched placebo reported `1,955,157` tokens.
- Accepted graph async vs patched spec-placebo:
  - output parity: still false, `2/2` fixture drift.
  - model-input parity: first mismatch moved from row `0` BlockTable shape to
    row `26` `input_batch.input_ids.head[0]`.
  - Interpretation: the block-table/cache-layout bug is fixed; the remaining
    mismatch appears only after the first sampled-token fork.
- No-spec accepted with async explicitly disabled vs patched spec-placebo:
  - output parity: `baseline_match_all=true`.
  - model-input parity: `match_all=true` over all `64` rows.
  - Interpretation: patched placebo now exactly matches the no-async verifier
    path. The remaining difference from the current production accepted run is
    async scheduling, not unused speculative block allocation.

Validation:

```bash
python3 -m py_compile \
  /home/steve/src/vllm/vllm/model_executor/layers/mamba/abstract.py \
  /home/steve/src/vllm/vllm/v1/core/sched/scheduler.py \
  /home/steve/src/vllm/vllm/v1/core/single_type_kv_cache_manager.py \
  /home/steve/src/vllm/vllm/v1/worker/gpu_model_runner.py \
  /home/steve/src/vllm/vllm/v1/worker/mamba_utils.py

python3 scripts/check-qwen36-model-input-parity.py \
  --left data/qwen36-quark-int8-tp4-accepted-modelinput-zerolookahead-trace-20260611a.jsonl \
  --right data/qwen36-quark-int8-tp4-spec-placebo-zerolookahead-trace-20260611a.jsonl \
  --left-label accepted \
  --right-label spec-placebo-zerolookahead \
  --output-json data/qwen36-quark-int8-tp4-accepted-vs-spec-placebo-zerolookahead-parity-20260611a.json \
  --output-md data/qwen36-quark-int8-tp4-accepted-vs-spec-placebo-zerolookahead-parity-20260611a.md \
  --max-mismatches 20

python3 scripts/check-qwen36-model-input-parity.py \
  --left data/qwen36-quark-int8-tp4-accepted-noasync-modelinput-trace-20260611a.jsonl \
  --right data/qwen36-quark-int8-tp4-spec-placebo-zerolookahead-trace-20260611a.jsonl \
  --left-label accepted-noasync \
  --right-label spec-placebo-zerolookahead \
  --output-json data/qwen36-quark-int8-tp4-accepted-noasync-vs-spec-placebo-zerolookahead-parity-20260611a.json \
  --output-md data/qwen36-quark-int8-tp4-accepted-noasync-vs-spec-placebo-zerolookahead-parity-20260611a.md \
  --max-mismatches 20
```

Decision:

- Keep the zero-mamba-block placebo patch as the new correctness gate.
- Future speculation speed tests should compare against a no-async accepted
  baseline first, because n-gram speculative config disables async scheduling.
- Production/no-quality-loss policy is still stricter: before promotion, either
  make speculative mode preserve the current async accepted output, or move the
  production accepted baseline to a no-async quality-gated recipe and rerun the
  full canary suite plus speed benchmarks.
- Next useful experiment: run patched oracle/perfect-draft in this no-async
  parity lane to see whether bucket-verifier speed headroom survives once the
  verifier/cache layout is clean.

## Post-Repair Ideas And Bigger Bets

Added after the zero-lookahead placebo repair. These are ideas to keep on the
board while pursuing more speed without lowering the quality bar. They do not
change the target model or quantization: the accepted verifier remains
`nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`, and 4-bit/Qwen3.5 detours are
out of scope.

External signals checked during this pass:

- `https://github.com/vllm-project/vllm-xpu-kernels`
  - vLLM's Intel GPU custom-op work is now factored into a dedicated XPU kernel
    repository using SYCL/DPC++ and oneDNN-style primitives. Future shape-exact
    W8A8/MoE repros should target this layer instead of only patching Python
    wrappers in the main vLLM tree.
- `https://github.com/vllm-project/vllm-xpu-kernels/releases`
  - Recent XPU kernel releases mention Xe2 paged decode, mixed
    prefill/decode attention handling, MoE grouped-GEMM policy updates, and
    small-K FP8/MoE tuning. This is a concrete reason to run an isolated latest
    XPU-kernel bakeoff.
- `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`
  - Intel/vLLM call out persistent zero-gap MoE kernels and report high Arc Pro
    MoE GEMM efficiency. This reinforces that durable wins probably require a
    real persistent MoE path, not another boundary-only custom op.
- `https://recipes.vllm.ai/Qwen/Qwen3.6-35B-A3B`
  - The official vLLM recipe shows MTP speculative decode for Qwen3.6. Our
    current Quark snapshot lacks MTP weights, so this is a sidecar/proposer
    idea only unless a quality-equivalent verifier checkpoint changes.
- `https://huggingface.co/z-lab/Qwen3.6-35B-A3B-DFlash`
  - A Qwen3.6 35B-A3B DFlash drafter exists. It is not a verifier replacement,
    but it is a candidate proposer if vLLM/XPU can run the draft path while the
    Quark INT8 model verifies every token.
- `https://jarvislabs.ai/blog/qwen36-mtp-llamacpp-rtxpro6000`
  - Public Q8_0 llama.cpp data shows MTP improved Qwen3.6 35B-A3B MoE decode
    from `193.36` to `225.48` tok/s on RTX PRO 6000, a `1.17x` gain. The
    lesson is realistic: MTP may cross `200 tok/s`, but MoE gains can be much
    smaller than dense-model gains.
- `https://kaitchup.substack.com/p/dflash-vs-mtp-qwen36-speculative`
  - Current Qwen3.6 speculative work compares DFlash and MTP across vLLM and
    llama.cpp, and warns that bad configuration can make speculation slower.
    That matches our gate: speed claims must include acceptance rate, repeat
    quality, long-context quality, and request-class coverage.
- `https://github.com/ggml-org/llama.cpp/issues/23769`
  - B70/Vulkan plus Qwen3.6 MoE/MTP still has public crash reports. Treat
    llama.cpp MTP/Q8 tests as diagnostic, not a production shortcut, until the
    exact 8-bit model, context, and stability gates pass on our stack.

Immediate things to try:

1. Run the patched oracle/perfect-draft upper-bound test in the no-async parity
   lane.
   - This is now the cleanest speculation speed question: with placebo matching
     no-async accepted exactly, can a perfect proposer produce endpoint-level
     speed above `200 tok/s` without perturbing verifier inputs?
   - If the answer is no, stop spending major time on MTP/DFlash/proposer work
     and move effort to MoE/static-runner paths.
   - If the answer is yes, build the sidecar proposer path behind the Quark
     verifier.

2. Measure no-async accepted as a possible latency-lane baseline.
   - Speculative modes already disable async scheduling in practice. We need to
     know the no-async speed/quality cost directly, not infer it from parity
     traces.
   - Promotion rule: no-async can become a production latency lane only after
     full repeat64, long-context, structured-output, and p512/n512 r8/r10 speed
     gates. Exact parity against the old async baseline is useful evidence, but
     the real standard is no quality regression under the published gates.

3. Add logits/top-k fingerprints to the model-input parity lane.
   - Token parity tells us where outputs fork; logits/top-k checksums tell us
     whether the verifier math changed before sampling.
   - This should distinguish harmless sampled-token ordering differences from
     actual KV/GDN/verifier-state corruption.

4. Build a latest `vllm-xpu-kernels` isolated bakeoff.
   - Use a separate venv/cache root and the same current model.
   - Minimal targets: p512/n512 c1 speed, repeat quality, AOT census, route
     microbench, and a rollback note.
   - Do not touch the stable production backend until the isolated stack passes
     quality.

5. Capture real route histograms at endpoint time.
   - Route-exact data should include prompt class, layer, top-k experts, active
     expert count per token, and hot-window locality.
   - Feed those histograms into grouped-GEMM policy tests and the hybrid TP/EP
     simulator; synthetic even routing is not enough.

Bigger, bolder ideas:

1. Quark-verifier MTP sidecar.
   - Use official Qwen3.6 MTP assets or a GGUF-derived MTP path only to propose
     tokens.
   - The current Quark INT8 endpoint remains the verifier and final sampler.
   - Success criteria: exact canary quality, high accepted-token rate, no
     placebo/model-input drift, and net endpoint speed gain after scheduler
     overhead.

2. DFlash sidecar behind the current verifier.
   - DFlash drafts blocks in parallel and may avoid some serial MTP limits.
   - Risk: XPU support and integration overhead may erase draft gains.
   - Gate: same as MTP, with extra long-context and structured-output checks
     because block-draft methods can fail in prompt-class-specific ways.

3. Static no-scheduler c1 decode lane.
   - Build a direct runner with preallocated KV, fixed `batch=1`, fixed
     no-prefix/no-async posture, and graph replay over decode buckets.
   - Purpose: quantify whether vLLM serving/scheduler/block-table overhead is
     a large part of the missing `2x`.
   - Production version could be a latency class for single interactive users,
     while the existing vLLM path handles aggregate traffic.

4. Persistent MoE decode kernel using real route windows.
   - Combine route/remap, grouped W8A8 GEMM, activation, second quant, expert
     combine, shared-expert add, and finalize into a route-window persistent
     path.
   - This is the most likely non-speculation route to a structural win because
     Qwen3.6 A3B is MoE and public Arc work points at persistent MoE kernels.

5. Hybrid TP/EP and hot-expert replication.
   - Spend VRAM to reduce communication and tiny-M fragmentation.
   - Simulate before implementation:
     - TP4 current baseline.
     - TP2 plus replicated dense/attention.
     - expert-parallel or expert-sharded MoE.
     - hot-expert copies per layer/rank.
   - Quality should be identical if weights and math stay identical; the trade
     is memory versus single-request latency.

6. XPU-native W8A8 retile/repack cache.
   - If current Quark weight layout is not optimal for B70 XMX/DPAS, build a
     one-time load-time repack into tile-native layout and cache it on disk.
   - This should not change model quality because weights are mathematically
     identical; it only changes physical layout.
   - Gate with dequant/weight checksums and exact output quality.

7. Strict same-model 8-bit engine shootout.
   - Compare vLLM/XPU against llama.cpp SYCL/Vulkan only with an 8-bit
     Qwen3.6 35B-A3B artifact and identical prompt template/quality gates.
   - Use it to diagnose whether vLLM/XPU is leaving large speed on the table.
   - Do not promote 4-bit rows or mismatched model families as substitutes.

8. Upstream/bounty-quality XPU repro packet.
   - Package three minimal repros:
     - spec-placebo block-table/KV allocation parity.
     - Qwen3.6 real-route MoE grouped-GEMM shapes.
     - tiny decode all-reduce/collective shapes from the AOT census.
   - Include scripts, exact shapes, expected/current output, and no secrets.
   - This is how to get help from Intel/vLLM maintainers without asking them to
     reconstruct our entire production setup.

Current priority after adding these ideas:

1. Perfect-draft/oracle in the no-async parity lane.
2. No-async accepted quality/speed baseline.
3. Logits/top-k fingerprints to separate sampling fork from verifier drift.
4. Latest `vllm-xpu-kernels` isolated bakeoff.
5. Route histograms and persistent MoE microbench work in parallel.

## No-Async Oracle Lane Result And Bigger Follow-Ups

Added after running the first patched oracle/perfect-draft probes in the
no-async parity lane. This is now the most important speculative-decode
correctness evidence:

- `p512/o32`, oracle `k=5`, no-async lane:
  - exact output parity versus the no-async accepted baseline:
    `baseline_match_all=true`.
  - scheduler trace: `52/52` draft tokens accepted, `100.0%` accept rate,
    `12` rows, `2` requests.
  - warmed short fixture signal: repetitive case `0.190s` versus accepted
    `0.415s`. This is useful as a direction check, not a publishable speed
    claim because the output is too short and one case includes startup/compile
    noise.
- `p512/o128`, oracle `k=5`, no-async lane:
  - exact output parity failed: `baseline_match_all=false`.
  - scheduler trace: `31/40` draft tokens accepted, `77.5%` accept rate.
  - first output diffs: `natural_latency_plan` at token index `25`,
    `repetitive_kernel_notes` at token index `14`.
- `p512/o128`, oracle `k=1`, no-async lane:
  - exact output parity still failed: `baseline_match_all=false`.
  - scheduler trace: `14/14` draft tokens accepted, `100.0%` accept rate.
  - both fixtures drifted at output token index `14`.

Interpretation:

- The short `o32` result proves the patched lane can accept oracle drafts and
  sometimes preserve final output exactly.
- The longer `o128` `k=1` result is the real blocker. It accepted every single
  one-token oracle draft and still diverged, so the failure is below draft
  quality, draft width, and full-accept bonus behavior.
- Do not promote DFlash, MTP, n-gram, or any other proposer until oracle `k=1`
  has exact parity over the longer fixture. Otherwise a faster drafter can
  silently accelerate a different verifier state.
- No Localmaxxing submission is warranted from these oracle probes. The
  quality gate failed on the longer fixture and the `>200 tok/s` single-user
  goal has not been achieved.

Artifacts:

- `data/qwen36-quark-int8-tp4-accepted-noasync-oraclelane-p512o32-20260611b.json`
- `data/qwen36-quark-int8-tp4-oracle5-noasynclane-p512o32-20260611b.json`
- `data/qwen36-quark-int8-tp4-oracle5-noasynclane-spec-summary-20260611b.json`
- `data/qwen36-quark-int8-tp4-oracle5-noasynclane-spec-summary-20260611b.md`
- `data/qwen36-quark-int8-tp4-accepted-noasync-oraclelane-p512o128-20260611b.json`
- `data/qwen36-quark-int8-tp4-oracle5-noasynclane-p512o128-20260611b.json`
- `data/qwen36-quark-int8-tp4-oracle5-noasynclane128-spec-summary-20260611b.json`
- `data/qwen36-quark-int8-tp4-oracle5-noasynclane128-spec-summary-20260611b.md`
- `data/qwen36-quark-int8-tp4-oracle5-noasynclane128-drift-fixture-20260611b.json`
- `data/qwen36-quark-int8-tp4-oracle5-noasynclane128-drift-fixture-20260611b.md`
- `data/qwen36-quark-int8-tp4-oracle1-noasynclane-p512o128-20260611b.json`
- `data/qwen36-quark-int8-tp4-oracle1-noasynclane128-spec-summary-20260611b.json`
- `data/qwen36-quark-int8-tp4-oracle1-noasynclane128-spec-summary-20260611b.md`
- `data/qwen36-quark-int8-tp4-oracle1-noasynclane128-drift-fixture-20260611b.json`
- `data/qwen36-quark-int8-tp4-oracle1-noasynclane128-drift-fixture-20260611b.md`

Fresh public signals checked during this update:

- `https://github.com/vllm-project/vllm-xpu-kernels`
  - The repo lists XPU custom kernels for RMS/layer norm, activation,
    Flash/GDN/Xe2 attention, MoE top-k/remapping/gather, FP8/MxFP4
    quantization/GEMM, and grouped GEMM. This supports making XPU-kernel-level
    repros rather than only main-tree Python wrapper patches.
- `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`
  - Intel/vLLM's Arc Pro B-series writeup calls out persistent MoE loops,
    dynamic balancing, prepack, multi-GPU scaling, and PCIe P2P. That points
    away from small env sweeps and toward persistent MoE/layout work.
- `https://huggingface.co/z-lab/Qwen3.6-35B-A3B-DFlash`
  - DFlash is explicitly a drafter that must be paired with Qwen3.6-35B-A3B.
    It remains interesting only behind our current Quark verifier after the
    oracle verifier-state bug is fixed.
- `https://github.com/thc1006/qwen3.6-speculative-decoding-rtx3090`
  - Public Qwen3.6 A3B speculative work reports no net speedup for that
    specific Ampere/llama.cpp/draft setup. Treat this as a warning to require
    end-to-end speed and quality, not just acceptance-rate optimism.
- `https://pytorch.org/blog/accelerating-moe-model/`
  - The MoE locality work reports large kernel speedups from scheduling and
    locality for skinny MoE inference GEMMs. The portable lesson for B70 is to
    optimize real routed MoE memory locality, not just raw GEMM math.
- `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`
  - Intel XPU grouped-GEMM tuning notes explicitly call for real token
    distributions instead of synthetic routing. This matches the route
    histogram backlog.
- `https://docs.vllm.ai/en/latest/design/moe_kernel_features/`
  - vLLM's MoE design now has explicit modular prepare/finalize, all2all, and
    experts-kernel interfaces. Hybrid TP/EP experiments should use those
    boundaries as the architecture map.
- `data/localmaxxing-qwen36-fp8-top-refresh-20260611c.json`
  - Public exact `Qwen/Qwen3.6-35B-A3B-FP8` rows currently include `253.7`
    tok/s on RTX PRO 6000 Blackwell and `140.01` tok/s on dual RTX 3090.
    Hardware is not comparable, but it reinforces that the model class can run
    much faster when the engine/speculation path is right.
- `data/localmaxxing-qwen36-dflash-refresh-20260611c.json`
  - No public exact `z-lab/Qwen3.6-35B-A3B-DFlash` Localmaxxing rows were
    returned by the API at this check.

Immediate corrective work to try next:

1. Add logits/top-k fingerprints around the `k=1` token-14 divergence.
   - Record verifier top-k token IDs, top-k logits, sampled/greedy token, and a
     compact checksum for hidden state before each emitted token.
   - Compare accepted no-async versus oracle `k=1`. If logits differ before the
     first token mismatch, we have verifier-state/KV drift. If logits match but
     sampling diverges, the bug is in sampling/request accounting.

2. Add a request-id joined model-input trace for the two `o128` fixtures.
   - Current traces are useful but not enough to join every internal row to the
     client case cleanly.
   - Add case labels or explicit prompt hashes into the scheduler/model-runner
     trace so row 14 can be inspected without guesswork.

3. Trace GDN/mamba state, positions, and block tables across the first 20 decode
   steps.
   - The old zero-lookahead bug lived in Qwen3.6's mamba block allocation.
     The new `k=1` drift could be another speculative update path that changes
     mamba/GDN state even when every draft is "correct".

4. Build a tiny deterministic oracle `k=1` replay fixture.
   - Use one prompt, fixed tokens through index 20, no HTTP/frontdoor, no
     concurrent requests.
   - The target is a minimal upstreamable repro that fails in seconds and can be
     shared with vLLM/Intel maintainers without production context.

5. Keep the accepted service on the current quality-gated non-spec path.
   - The accepted backend has been restored after this diagnostic in tmux
     session `qwen36-tp4-accepted-restored-after-oracle-noasynclane-20260611b`
     with backend `/health`, model listing, and frontdoor local-bypass `OK`
     smoke passing.
   - Direct backend chat bypasses the frontdoor's `enable_thinking=false`
     template and is not the exact operational canary.

Bigger, bolder ideas to keep on the board:

1. Speculative verifier-state repair as a standalone project.
   - Treat "oracle `k=1` exact parity for 128+ tokens" as the first milestone.
   - Only after that, re-enable MTP/DFlash/ngram trials.
   - This is less glamorous than a drafter, but it is the key that makes every
     no-quality-loss speculation path viable.

2. Whole-token replay runner.
   - Build a direct runner that captures one full token step as a Level Zero or
     XPU graph command sequence and replays it with fixed KV/block-table state.
   - Goal: eliminate scheduler and dynamic graph churn for batch-1 latency,
     then compare exact outputs to vLLM.

3. Persistent route-window MoE executor.
   - Capture real route windows from accepted traffic, group them by layer and
     hot experts, and feed those windows to a persistent XPU grouped-GEMM path.
   - Include expert remapping, activation, quant, output combine, and
     shared-expert/finalize work. The rejected Python boundary proved partial
     wrapping is not enough.

4. Memory-for-latency hot expert copies.
   - Spend unused VRAM to replicate the hottest layer-local experts on more
     ranks, reducing cross-rank MoE traffic for common route windows.
   - Gate with route histograms and exact output parity; the weights are
     identical, only placement changes.

5. Hybrid TP/EP single-user layout.
   - Simulate a layout that does not all-reduce every tiny dense/MoE boundary
     across TP4.
   - Candidate designs: TP2 dense plus EP MoE, replicated attention plus sharded
     experts, or per-layer expert placement based on actual route histograms.

6. XPU W8A8/MxFP8 kernel branch audit.
   - Compare current Quark `int8_gemm_w8a8` behavior against latest
     `vllm-xpu-kernels` W8A8/MxFP8 paths in an isolated environment.
   - Success is not just "new wheel installed"; require AOT census changes,
     speed, and quality.

7. 8-bit engine bakeoff with a real production bar.
   - Test llama.cpp SYCL/Vulkan or SGLang only with Qwen3.6 35B 8-bit/high
     fidelity, 32K-capable settings, and the same quality suite.
   - A faster but 4-bit or different-family result does not count. A slower
     result can still teach us about scheduler/spec/MoE architecture.

8. Upstream-quality issue packet.
   - Package the oracle `k=1` drift, block-table parity tools, route histograms,
     and grouped-GEMM shapes into small reproducible issues.
   - The best external help will come from precise artifacts: exact model,
     trace rows, current/expected token IDs, commands, and no secrets.

9. Production dual-lane design.
   - Keep a conservative non-spec lane as the quality baseline.
   - Add a latency lane only after exact oracle/spec parity and reliability
     pass. Frontdoor should be able to route, pause, drain, and fall back by
     health/quality canary result.

Updated priority:

1. Fix oracle `k=1` exact parity over `p512/o128`.
2. Add logits/top-k and request-id model-input joins around token 14.
3. Build the minimal upstreamable speculative-state repro.
4. In parallel, capture route histograms and start persistent MoE microbench
   work against real routed distributions.
5. Only after (1) passes, return to MTP/DFlash speed work and publish any new
   Localmaxxing result.

## Oracle k=1 Logprob Fingerprints

Added after rerunning the no-async accepted baseline and oracle `k=1` fixture
with completions API `logprobs=5`.

What changed:

- `scripts/qwen36-completion-oracle-trace.py` now accepts `--logprobs N` and
  stores both the raw OpenAI-compatible completion logprob payload and a
  normalized token-id/top-k view.
- Added `scripts/compare-qwen36-logprob-fingerprints.py` to compare selected
  token IDs, top-k signatures, and same-rank logprob deltas between two
  completion trace artifacts.

Results:

- Accepted no-async logprob baseline completed both `p512/o128` fixtures.
- Oracle `k=1` with the accepted logprob baseline as oracle source still failed
  exact output parity:
  - `natural_latency_plan`: first selected-token diff at output index `14`,
    accepted token `29541` (` reliability`) versus oracle token `4779`
    (` memory`).
  - `repetitive_kernel_notes`: first selected-token diff at output index `14`,
    accepted token `4752` (` unique`) versus oracle token `6126` (`PU`).
- Scheduler trace again shows oracle `k=1` accepted every draft token:
  `14/14`, `100.00%`, `14` rows, `2` requests.
- The logprob comparison proves the verifier distribution is already different
  before the selected-token fork:
  - `natural_latency_plan`: first top-k signature diff at row `0`; top-1 stayed
    `Continue`, but the accepted run ranked `Focus` second while oracle ranked
    `<|im_end|>` second, and the shared top-1 logprob differed by about
    `0.07417`.
  - `repetitive_kernel_notes`: first same-rank top-1 logprob delta appeared at
    row `0`; first top-k signature diff appeared at row `2`; selected token
    drift still appeared at row `14`.
- The model-input parity checker also mismatches at row `0`:
  `attn.block_tables.0.cpu.head` is `[1]` for accepted no-async and `[1, 2]`
  for oracle `k=1`. The first row has `scheduled_spec_decode_tokens={}`,
  `spec_token_ids=[[]]`, and `use_spec_decode=false`, so this is allocation /
  verifier-input state drift before draft tokens are active.

Artifacts:

- `data/qwen36-quark-int8-tp4-accepted-noasync-logprobs-p512o128-20260611c.json`
- `data/qwen36-quark-int8-tp4-accepted-noasync-logprobs-modelinput-trace-20260611c.jsonl`
- `data/qwen36-quark-int8-tp4-oracle1-logprobs-p512o128-20260611c.json`
- `data/qwen36-quark-int8-tp4-oracle1-logprobs-modelinput-trace-20260611c.jsonl`
- `data/qwen36-quark-int8-tp4-oracle1-logprobs-spec-20260611c.jsonl`
- `data/qwen36-quark-int8-tp4-oracle1-logprobs-draft-20260611c.jsonl`
- `data/qwen36-quark-int8-tp4-oracle1-logprobs-spec-summary-20260611c.json`
- `data/qwen36-quark-int8-tp4-oracle1-logprobs-spec-summary-20260611c.md`
- `data/qwen36-quark-int8-tp4-accepted-vs-oracle1-logprobs-compare-20260611c.json`
- `data/qwen36-quark-int8-tp4-accepted-vs-oracle1-logprobs-compare-20260611c.md`
- `data/qwen36-quark-int8-tp4-accepted-vs-oracle1-logprobs-modelinput-parity-20260611c.json`
- `data/qwen36-quark-int8-tp4-accepted-vs-oracle1-logprobs-modelinput-parity-20260611c.md`

Decision:

- This strengthens the previous conclusion: oracle `k=1` is not a sampling-only
  drift. The verifier logits/top-k are already perturbed by speculative-mode
  cache/block-table state before any draft token is scheduled.
- The next highest-value experiment is an opt-in actual-spec diagnostic that
  zeros or hides speculative blocks for n-gram/oracle proposers only, then
  reruns:
  - no-logprob `p512/o32` and `p512/o128` parity,
  - logprob `p512/o128` parity,
  - model-input row-0 block-table parity,
  - spec summary acceptance.
- Do not apply that diagnostic as production behavior without proving that
  GDN/mamba state rollback still works for accepted and rejected draft tokens.

Operational note:

- Accepted backend was restored after this diagnostic in tmux session
  `qwen36-tp4-accepted-restored-after-logprob-oracle-20260611c`; backend
  `/health` and frontdoor local-bypass `OK` smoke passed. Frontdoor remains
  paused for remote users with local bypass enabled.

## Oracle k=1 No-Mamba-Spec-Blocks Diagnostic

The next isolated graph diagnostic tested whether the oracle/n-gram row-0
block-table drift was caused only by Qwen3.6 GDN/mamba speculative block
reservation.

Local vLLM change under test:

- Add opt-in `VLLM_XPU_NGRAM_NO_MAMBA_SPEC_BLOCKS=1`.
- When the speculative method is `ngram` or `ngram_gpu`, set
  `MambaSpec.num_speculative_blocks=0`.
- Leave normal no-spec, placebo repair, MTP, DFlash, and draft-model paths
  unchanged.

Launcher support:

- `scripts/launch-qwen36-quark-int8-ngram-trace.sh` now accepts
  `NGRAM_NO_MAMBA_SPEC_BLOCKS=1`.

Run:

- Diagnostic backend: `qwen36-tp4-oracle1-nomambaspec-20260611d` on
  `127.0.0.1:18081`.
- Fresh graph cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-oracle1-nomambaspec-20260611d`.
- Oracle source:
  `data/qwen36-quark-int8-tp4-accepted-noasync-oraclelane-p512o128-20260611b.json`.
- Probe: two `p512/o128` completion fixtures.

Result:

- Output parity still failed: `baseline_match_all=false`.
- `natural_latency_plan` first output-token diff moved to index `3`.
- `repetitive_kernel_notes` first output-token diff also appeared at index `3`.
- Scheduler summary recorded only `4` draft rows across `2` requests, with
  `2` accepted and `2` rejected (`50.00%` acceptance). This is worse than the
  prior oracle `k=1` logprob run and shows the diagnostic changed behavior but
  did not repair correctness.
- Model-input parity versus the accepted no-async lane still fails. The first
  row-order diff is `tp_rank` ordering noise, but the immediate real drift is
  still attention slot mapping shape/value drift: accepted rows carry one slot
  where the diagnostic carries two, then subsequent rows are offset. Hiding
  Mamba speculative blocks is therefore insufficient; a second speculative
  reservation/accounting path remains active.

Artifacts:

- `data/qwen36-quark-int8-tp4-oracle1-nomambaspec-p512o128-20260611d.json`
- `data/qwen36-quark-int8-tp4-oracle1-nomambaspec-modelinput-trace-20260611d.jsonl`
- `data/qwen36-quark-int8-tp4-oracle1-nomambaspec-spec-20260611d.jsonl`
- `data/qwen36-quark-int8-tp4-oracle1-nomambaspec-draft-20260611d.jsonl`
- `data/qwen36-quark-int8-tp4-oracle1-nomambaspec-spec-summary-20260611d.json`
- `data/qwen36-quark-int8-tp4-oracle1-nomambaspec-spec-summary-20260611d.md`
- `data/qwen36-quark-int8-tp4-accepted-vs-oracle1-nomambaspec-modelinput-parity-20260611d.json`
- `data/qwen36-quark-int8-tp4-accepted-vs-oracle1-nomambaspec-modelinput-parity-20260611d.md`
- `data/qwen36-quark-int8-tp4-restored-after-nomambaspec-frontdoor-ok-smoke-r2-20260611d.json`
- `patches/vllm-qwen36-ngram-no-mamba-spec-blocks-diagnostic-20260611.patch`

Patch note: the patch artifact is a diff from the unpatched local vLLM base, so
it includes the earlier tracked placebo `num_speculative_blocks=0` repair as
context plus the new no-mamba-spec-block diagnostic flag.

Decision:

- Reject the no-mamba-spec-blocks diagnostic as a correctness fix.
- Keep it as a useful negative control: the zero-lookahead placebo bug was
  real, but actual n-gram/oracle speculation has another verifier-input drift
  source besides `MambaSpec.num_speculative_blocks`.
- Do not time this path or use it for production.

Operational restore:

- Accepted backend restored in
  `qwen36-tp4-accepted-restored-after-nomambaspec-20260611d`.
- Backend `/health` passed after `54s`.
- Paused-local public frontdoor exact smoke returned `OK`.
- Final frontdoor status: remote generation paused, loopback bypass enabled,
  active `0`, queued `0`.

Next concrete repair items:

1. Add a rank/request-normalized model-input comparator so rank-order noise is
   removed before comparing slot/block drift.
2. Add `speculative_config` metadata, KV block allocator counters, slot mapping
   allocator counters, and cache-manager free/used block counts to the
   model-input trace.
3. Add a graph-mode `spec-config/no-proposer` diagnostic: construct the spec
   config but bypass proposer setup, so the scheduler/model runner can be
   compared with and without proposer-side allocations.
4. Add a graph-mode `num_speculative_tokens=0` diagnostic, if vLLM allows it,
   to separate "spec config exists" from "lookahead width exists".
5. Trace the first 20 decode steps by request ID with top-k/logprob checksum,
   input IDs, positions, slot mappings, block tables, and GDN/mamba state
   version counters.
6. Build the minimal upstreamable repro around one prompt and the first four
   generated tokens, because this diagnostic now diverges at index `3`.

More bigger/bolder ideas to keep in scope:

Fresh source refresh for this addendum:

- vLLM speculative decoding docs still frame model-based methods such as EAGLE,
  MTP, draft models, PARD, and MLP as the best latency-reduction methods, with
  n-gram/suffix as lighter, usually smaller-gain paths:
  https://docs.vllm.ai/en/stable/features/speculative_decoding/
- The current vLLM speculative config docs expose graph-affecting config hash
  warnings and include `ngram`, `suffix`, `eagle`, `eagle3`, and `mtp` as
  active methods. That supports making spec-config/no-proposer and
  zero-width/zero-draft controls explicit:
  https://docs.vllm.ai/en/latest/api/vllm/config/speculative/
- vLLM's suffix decoding docs describe adaptive pattern matching over prompt
  plus previous generations. Once verifier-input parity is fixed, suffix
  decoding is worth testing as a lightweight alternative to plain n-gram:
  https://docs.vllm.ai/en/latest/features/speculative_decoding/suffix/
- The public engine-args docs keep quantization configuration and per-layer
  quant specs visible as first-class config. That keeps the strict 8-bit
  engine bakeoff in scope without accepting a 4-bit shortcut:
  https://docs.vllm.ai/en/latest/configuration/engine_args/

1. **Static solo decode lane.** Build a batch-1 service class with a
   precommitted KV/block-table arena and fixed graph replay for one request at
   a time. This may bypass much of the scheduler/block-table churn that keeps
   perturbing spec-mode verifier inputs.
2. **Verifier-input contract tests in CI.** Treat model-input parity as a first
   class quality gate: exact output can pass by luck, but slot/block parity
   catches silent state drift before speed work.
3. **Speculative scheduler bisect.** Run the oracle fixture against adjacent
   vLLM commits or targeted local reverts around scheduler/spec block-manager
   changes. If an older commit has exact `k=1` parity, forward-port the fix
   instead of continuing blind local patches.
4. **Custom proposer API outside vLLM internals.** Feed draft tokens through a
   narrow external proposer interface only after verifier-input parity is
   exact. This avoids entangling a B70-specific drafter with scheduler internals
   while still letting us try DFlash, EAGLE, n-gram, or a learned micro-drafter.
5. **KV-resident verifier-bucket runner.** Build a lower-level harness that
   verifies 1, 2, 4, 8, and 16 candidate tokens from an existing KV state
   without HTTP scoring. This gives a realistic bound for MTP/EAGLE before
   investing in a drafter.
6. **Route-window compiler.** Capture real accepted-route windows and generate
   layer-specific grouped-GEMM schedules for the hot expert mixes, including
   prepare/finalize and shared-expert handling.
7. **Memory-for-latency hotset mode.** Spend spare VRAM on replicated hot
   experts, duplicated dense projections, or rank-local route caches if it
   reduces all-reduce/all-to-all pressure for the common path.
8. **Hybrid TP/EP prototype.** Use the current route histograms to simulate
   TP2 dense plus expert-parallel MoE, replicated attention plus sharded
   experts, and per-layer hot expert replication. Only build the best-looking
   layout.
9. **Whole-token command-list capture.** Try a fixed-shape Level Zero command
   list for a complete decode token, not just per-op XPU graphs. The goal is to
   collapse launch/dispatcher overhead for c1.
10. **B70-native W8A8 retile cache.** Repack current Quark INT8 weights into
    the exact tile/layout expected by the fastest XPU GEMM kernels and persist
    it as a startup artifact. Quality should be unchanged because weights and
    scales are identical.
11. **Strict 8-bit engine shootout.** Run Qwen3.6 35B with high-fidelity 8-bit
    on llama.cpp SYCL/Vulkan, OpenVINO/ITREX if viable, and SGLang/vLLM
    variants. The purpose is architectural comparison, not a switch to 4-bit
    or a different model.
12. **Reliability scoreboard as a benchmark dimension.** Record first-gen
    device-losts, restore time, repeat-quality pass rate, and long-context pass
    rate next to tok/s. A 120 tok/s recipe that crashes on first request is not
    a usable win.
13. **Upstream/bounty-quality repro packet.** Package the oracle `k=1` drift,
    no-mamba negative control, block/slot trace, launch commands, and exact
    token diffs as an issue-ready artifact for vLLM/Intel. This is likely to
    get better external help than a broad performance complaint.

## Rank-Normalized Parity And Bigger Opportunity Refresh

Added after the no-mamba-spec-blocks negative control. The goal of this
addendum is to separate facts we now know from larger bets worth tracking.

New local tooling:

- `scripts/check-qwen36-model-input-parity.py` now has
  `--align-by tp-rank-step`.
- The new mode buckets rows by `tp_rank`, compares the nth row inside each
  rank, and strips `tp_rank`/`dcp_rank` fields after alignment.
- This removes rank-order noise from multi-XPU traces before comparing block
  tables, slot mappings, and scheduler-visible input state.

Rank-normalized evidence:

- No-mamba-spec-blocks diagnostic:
  - artifact:
    `data/qwen36-quark-int8-tp4-accepted-vs-oracle1-nomambaspec-modelinput-parity-tprank-20260611e.json`
  - left/right rows: `1024` accepted no-async rows versus `1016` oracle
    no-mamba rows.
  - aligned rows: `1016`, split evenly as `254` rows per TP rank on the
    oracle side.
  - first real mismatch after rank normalization:
    `tp_rank=0`, `rank_step=1`, left row `7`, right row `4`,
    `attn.slot_mappings.0.head`, `[33270]` versus `[33270, 33271]`.
  - interpretation: the no-mamba diagnostic removed the earlier row-0 mamba
    block-table signal, but actual n-gram/oracle speculation still widens the
    verifier input at the next decode step. This is now an attention/slot
    reservation or actual-spec verifier-row problem, not just
    `MambaSpec.num_speculative_blocks`.
- Original logprob oracle:
  - artifact:
    `data/qwen36-quark-int8-tp4-accepted-vs-oracle1-logprobs-modelinput-parity-tprank-20260611e.json`
  - left/right rows: `1024` accepted no-async rows versus `968` oracle rows.
  - aligned rows: `968`, split as `242` rows per TP rank on the oracle side.
  - first real mismatch after rank normalization:
    `tp_rank=0`, `rank_step=0`, left row `1`, right row `0`,
    `attn.block_tables.0.cpu.head`, `[1]` versus `[1, 2]`.
  - interpretation: the original logprob oracle still proves speculative
    configuration can perturb block tables before any selected-token fork.

Decision:

- Keep `--align-by tp-rank-step` as the default diagnostic lens for TP4
  speculation investigations.
- Do not interpret file-order row 0 mismatches without checking rank-normalized
  output first.
- The next repair needs trace metadata and counters, not another blind
  speculative-width sweep.

Next concrete diagnostics:

1. Add trace metadata for speculative method, `num_spec_tokens`, proposer type,
   draft-model presence, graph/capture mode, block size, and max block counts.
2. Add per-request state snapshots to the trace: prompt tokens, output tokens,
   computed tokens, spec-token length, `prev_num_draft_len`, and
   `num_tokens_no_spec`.
3. Add block-table and slot-mapping allocator counters: free/used blocks, row
   width, group widths, and any GDN/mamba state version counters that can be
   exposed cheaply.
4. Run a `spec-config/no-proposer` diagnostic: construct speculative config but
   bypass proposer creation and spec-token injection. This separates config
   hash/block-manager effects from proposer effects.
5. Run a `num_speculative_tokens=0` or zero-width actual-spec diagnostic if
   vLLM allows it. This separates "spec exists" from "lookahead/scheduled
   verifier row exists".
6. Create a minimal upstream repro around one prompt, four generated tokens,
   rank-normalized block/slot tables, and the exact output fork at token index
   `3`.

Fresh external signals checked:

- Intel's current vLLM/XPU container docs still frame Intel GPU support as an
  active vLLM target, but XPU support remains backend-specific enough that
  shape-exact repros matter more than generic CUDA advice:
  `https://github.com/intel/ai-containers/blob/main/vllm/0.14.1-xpu.md`
- vLLM's public INT8 W8A8 quantization docs emphasize acceleration from
  weight+activation INT8, but the documented support note is CUDA-oriented.
  Treat this as evidence that XPU W8A8 needs its own kernel validation, not as
  proof the fast path already exists for B70:
  `https://docs.vllm.ai/en/v0.18.0/features/quantization/int8/`
- The vLLM XPU backend migration RFC points toward `vllm-xpu-kernels` as the
  right home for Intel GPU kernel work. New B70 repros should target that
  library when possible:
  `https://github.com/vllm-project/vllm/issues/33214`
- vLLM's hybrid KV-cache manager docs call out mixed attention/Mamba layouts
  and speculative decoding cases as special memory-layout cases. That matches
  our block-table findings and supports making verifier-input parity a first
  class gate:
  `https://docs.vllm.ai/en/stable/design/hybrid_kv_cache_manager/`
- Public B70 community measurements remain mixed. One public benchmark repo
  reports strong single-card Qwen3.6 MoE results with llama.cpp/GGUF, while
  Localmaxxing currently shows our Quark W8A8 TP4 row among the top public B70
  Qwen rows. Use those as engine/kernel clues, not permission to switch to
  4-bit:
  `https://github.com/PMZFX/intel-arc-pro-b70-benchmarks`
  and `https://localmaxxing.com/en/hardware/DISCRETE_GPU%3Aintel%20arc%20pro%20b70?name=Intel+Arc+Pro+B70`
- Localmaxxing public Qwen3.6 35B rows still show the clearest `>200 tok/s`
  single-user path is model-based speculation/MTP/DFlash on mature backends.
  We should borrow the architecture, not the quantization or hardware
  assumptions.

Bigger, bolder ideas worth tracking:

1. **Speculation outside vLLM's scheduler path.**
   - Build an auxiliary proposer sidecar that suggests tokens out-of-process.
   - Verify those tokens with a static verifier-bucket call in the current
     Quark INT8 model instead of using vLLM's speculative scheduler state.
   - Why bold: avoids the current block-table/spec-state bug entirely if the
     verifier bucket can be made fast enough.
   - Proof: exact token parity, repeat64, long-context, and measured verifier
     bucket tok/s before any endpoint integration.

2. **Official-MTP-as-proposer, Quark-as-verifier.**
   - The current Quark checkpoint lacks obvious MTP tensors, but the official
     FP8 snapshot has them. Treat those tensors or an MTP GGUF as a draft
     proposer only.
   - Why bold: keeps final accepted quality tied to the current Quark verifier
     while testing the same class of multiplier that hits `>200 tok/s`
     elsewhere.
   - Risk: tokenizer/template parity and hidden-state compatibility may fail;
     reject if any verified token stream drifts.

3. **Latency-first single-request runner.**
   - Build a special c1 lane with fixed KV arena, preallocated block tables,
     static graph replay, local-only streaming, and minimal scheduler state.
   - Why bold: vLLM serving machinery may be structurally wrong for the
     fastest single-user path, especially while continuous batching and spec
     state interact with hybrid KV.
   - Proof: same model weights, same OpenAI-compatible prompt template, exact
     output parity, and a clean handoff path back to production service code.

4. **Hybrid TP/EP with replicated dense/GDN and sharded experts.**
   - Pure TP4 pays many single-token collectives. A Qwen A3B layout could
     replicate attention/GDN or shared dense pieces and shard/replicate experts
     based on real route frequencies.
   - Why bold: this changes the parallelism structure instead of shaving one
     op at a time.
   - First step: memory model per layer/expert using current 32K KV footprint
     and measured free VRAM.

5. **Hot-expert memory-for-latency mode.**
   - Spend spare VRAM duplicating hot experts or hot expert tiles on multiple
     ranks to avoid remote dispatch/all-reduce work for common routes.
   - Why bold: MoE route skew can turn memory headroom into latency reduction.
   - Proof: real router histograms from accepted runs, not synthetic uniform
     routing.

6. **Route-window persistent MoE executor.**
   - Capture real decode route windows and generate persistent grouped-GEMM
     schedules for the common expert mixes, including prepare/finalize and
     shared expert work.
   - Why bold: Intel guidance and our failures both imply Python/custom-op
     wrappers are not enough; the win needs a real persistent MoE kernel.
   - Proof: standalone shape-exact parity first, then endpoint parity.

7. **B70-native W8A8 tile cache.**
   - Repack current Quark W8A8 weights into the exact DPAS/XMX tile layout
     consumed by the fastest XPU kernels and persist the packed cache.
   - Why bold: avoids changing mathematical weights while removing runtime
     layout friction.
   - Proof: identical dequantized weights/scales, no output drift, startup and
     runtime timing, and no 32K-context VRAM regression.

8. **Strict 8-bit engine bakeoff.**
   - Compare same-model or equivalent high-fidelity 8-bit Qwen3.6 35B on
     vLLM/XPU, llama.cpp SYCL/Vulkan, OpenVINO/GenAI or ITREX where feasible,
     and any SGLang/XPU route that supports the required quant.
   - Why bold: if another engine gives much faster high-fidelity single-user
     decode, vLLM becomes a serving integration target rather than the only
     optimization surface.
   - Rule: no 4-bit promotion, no Qwen3.5 detour, no quality shortcut.

9. **Whole-token command-list capture.**
   - Capture a full decode token as one Level Zero command-list sequence with
     fixed shapes instead of relying only on per-op graph capture.
   - Why bold: collapse dispatch/graph boundaries across dense, MoE, GDN, and
     collectives for c1.
   - Proof: exact output parity and repeated device-lost stress tests.

10. **Public repro and crowd loop.**
    - Publish the best clean Localmaxxing row, then publish issue-ready
      minimal repro packets for the hard gaps: W8A8 XPU grouped GEMM, hybrid
      KV/spec block drift, and graph-safe collective fusion.
    - Why bold: Intel/vLLM maintainers and B70 users can help if the problem is
      precise and reproducible.
    - Proof: no private model paths, no secrets, small artifacts, and exact
      commands.

Working priority:

1. Repair or bypass verifier-input drift in speculative mode.
2. If that stalls, build the sidecar verifier-bucket harness to quantify the
   speculation ceiling outside vLLM's scheduler.
3. In parallel, collect real router histograms and build the shape-exact MoE /
   W8A8 kernel suite for `vllm-xpu-kernels`.
4. Keep accepted TP4 r10/repeat64/peak-VRAM packaging ready as the stable
   public baseline.

## Trace Metadata Instrumentation

Added a low-risk local vLLM trace instrumentation patch so the next speculative
diagnostic can identify which state changes before the verifier token stream
forks.

Patch artifact:

- `patches/vllm-qwen36-model-input-trace-metadata-20260611f.patch`

Local source touched:

- `/home/steve/src/vllm/vllm/v1/worker/gpu_model_runner.py`

New trace fields:

- `config.max_model_len`, `config.max_num_tokens`, `config.max_num_reqs`
- `config.num_spec_tokens`
- `config.use_async_scheduling`
- `config.use_async_spec_decode`
- `config.speculative.method`
- `config.speculative.num_speculative_tokens`
- `config.speculative.draft_model_config_present`
- `config.speculative.uses_draft_model`
- `config.speculative.use_ngram_gpu`
- `config.speculative.use_eagle`
- `config.speculative.use_dflash`
- `config.speculative.uses_extract_hidden_states`
- `config.speculative.enforce_eager`
- `config.cache.cache_dtype`
- `config.cache.kv_cache_dtype`
- `config.cache.configured_block_size`
- `config.cache.num_kv_cache_groups`
- per-cache-group `spec_type`, `block_size`, `num_speculative_blocks`, and
  `sliding_window` when present
- `input_batch.num_tokens_no_spec`
- `input_batch.num_prompt_tokens_cpu`
- `input_batch.num_accepted_tokens_cpu`
- `input_batch.request_states`, including prompt/output/computed token counts,
  `prev_num_draft_len`, per-group block-id lengths/heads, and recent output
  token IDs

Checker update:

- `scripts/check-qwen36-model-input-parity.py` now canonicalizes the new
  request-state records by dropping volatile `req_id` values and comparing the
  numeric/request-block fields.
- It also compares `num_tokens_no_spec`, `num_prompt_tokens_cpu`, and
  `num_accepted_tokens_cpu` when present.

Validation:

- `python3 -m py_compile scripts/check-qwen36-model-input-parity.py /home/steve/src/vllm/vllm/v1/worker/gpu_model_runner.py`
- `git -C /home/steve/src/vllm apply --reverse --check patches/vllm-qwen36-model-input-trace-metadata-20260611f.patch`
- `git diff --check`

Decision:

- This patch does not alter scheduler/model behavior; it only enriches
  `VLLM_XPU_MODEL_INPUT_TRACE_FILE` rows.
- Do not restart production traffic just to exercise it. Use it on the next
  isolated `18081` diagnostic run.

Next run shape:

1. Relaunch accepted no-async trace and oracle/no-mamba trace with the metadata
   patch active.
2. Compare with `--align-by tp-rank-step`.
3. Inspect the first mismatch and answer:
   - did `config.cache.groups[*].num_speculative_blocks` differ?
   - did `num_tokens_no_spec` or `prev_num_draft_len` differ before slot
     widening?
   - did request block-id heads widen before scheduler spec tokens were
     populated?
4. If the answer points to config/proposer setup rather than scheduled draft
   rows, implement `spec-config/no-proposer`.
5. If the answer points to actual scheduled verifier rows, switch effort to the
   sidecar verifier-bucket path or a scheduler patch that verifies draft tokens
   without widening baseline attention inputs.

## Metadata Trace Diagnostic Result

Ran the accepted no-async versus oracle `k=1` no-mamba-spec-blocks diagnostic
with the trace metadata patch active. This is now the sharpest evidence for the
remaining speculative correctness blocker.

Artifacts:

- `data/qwen36-quark-int8-tp4-accepted-noasync-metadata-p512o128-20260611f.json`
- `data/qwen36-quark-int8-tp4-accepted-noasync-metadata-trace-20260611f.jsonl`
- `data/qwen36-quark-int8-tp4-oracle1-nomambaspec-metadata-p512o128-20260611f.json`
- `data/qwen36-quark-int8-tp4-oracle1-nomambaspec-metadata-trace-20260611f.jsonl`
- `data/qwen36-quark-int8-tp4-oracle1-nomambaspec-metadata-spec-summary-20260611f.md`
- `data/qwen36-quark-int8-tp4-accepted-vs-oracle1-nomambaspec-metadata-parity-tprank-20260611f.md`
- `data/qwen36-quark-int8-tp4-oracle1-nomambaspec-metadata-drift-fixture-20260611f.md`

Result:

- Accepted no-async source run generated a usable `p512/o128` fixture. One
  prompt stopped early at `49` tokens, but it was still sufficient as an oracle
  source for the matched prompt set.
- Oracle `k=1`, no-mamba-spec-blocks, no-async run still failed exact output
  parity: `baseline_match_all=false`.
- Spec trace summary: `4` rows, `2` requests, `50.00%` accepted draft-token
  rate.
- Rank-normalized model-input parity compared `712` rows from accepted against
  the first `712` rows from oracle across all four TP ranks. The first expected
  config mismatch is `config.num_spec_tokens` (`0` accepted, `1` oracle).
- The first real verifier-input mismatch is at `tp_rank=0`, `rank_step=1`,
  `attn.slot_mappings.0.head`: accepted schedules one verifier token
  `[33270]`, while oracle schedules verifier plus draft slot
  `[33270, 33271]`.

Important metadata observations:

- At rank step `0`, accepted and oracle cache groups match exactly:
  - `4` cache groups.
  - groups `0`, `1`, and `2` are `MambaSpec` with
    `num_speculative_blocks=0`.
  - group `3` is `FullAttentionSpec`, block size `576`.
  - request block IDs match: `[[1], [2], [3], [4]]`.
  - block-id lengths match: `[1, 1, 1, 1]`.
  - `prev_num_draft_len=0` on both sides.
  - `num_tokens_no_spec`, prompt token counts, computed token counts, and
    accepted-token counters match.
- At rank step `1`, the oracle path has actual scheduled speculation state:
  - accepted `scheduler.total_num_scheduled_tokens=1`.
  - oracle `scheduler.total_num_scheduled_tokens=2`.
  - oracle `scheduled_spec_decode_tokens` contains one token, with head
    `[440]`.
  - oracle `spec_token_ids=[[440]]`.
  - oracle `prev_num_draft_len=1`.
  - block IDs and block tables still match, so this is not the old Mamba block
    reservation bug.

Conclusion:

- The no-mamba metadata run proves the old row-0 speculative cache reservation
  issue is not the current blocker.
- The remaining drift starts when vLLM schedules a real speculative verifier
  row with draft width `2`, widening attention slot mappings and request
  accounting relative to the accepted no-spec baseline.
- Do not spend more time on `MambaSpec.num_speculative_blocks` for the actual
  oracle/ngram path unless new evidence appears.
- The next repair should target how actual draft verification is scheduled:
  either a shadow/sidecar verifier bucket that does not mutate baseline request
  state, or a scheduler patch that verifies draft tokens using temporary KV and
  commits only accepted tokens.

Reliability note:

- The first accepted restore after this diagnostic hit
  `UR_RESULT_ERROR_DEVICE_LOST` on TP2 during XPU graph capture. A clean retry
  restore in `qwen36-tp4-accepted-restored-after-metadata-retry-20260611f`
  reached `/health` after `62s`.
- Frontdoor loopback smoke through the paused local-bypass path returned `OK`.
  Current frontdoor state remains paused for remote traffic with local bypass
  enabled.

## Things To Try: Bigger V2

These ideas build on the metadata result above. They assume the current Quark
W8A8 INT8 model remains the quality authority.

1. Shadow verifier bucket inside vLLM.
   - Add an internal verifier API that scores a draft continuation against a
     temporary KV/slot view, without updating the live request's block table,
     `prev_num_draft_len`, output-token history, or scheduler accounting.
   - Commit only the accepted prefix back into the live request state.
   - Why it may help: it attacks the exact slot-widening fault now observed at
     `rank_step=1`.
   - First proof: oracle `k=1` must match accepted no-async exactly on
     `p512/o128`, then repeat64 and long-context gates.

2. Out-of-process sidecar verifier.
   - Keep the production accepted backend untouched and launch a local verifier
     sidecar that receives `(prompt, generated_so_far, draft_tokens)` and
     returns accepted prefix length.
   - Start slow and correct, then optimize the sidecar path only if parity is
     exact.
   - Why it may help: it bypasses vLLM's speculative scheduler state entirely,
     giving a ceiling for perfect-draft speed without corrupting the serving
     engine.

3. Static decode lane for single-user c1.
   - Build a direct model-runner lane with preallocated KV, static block IDs,
     fixed graph replay, and minimal scheduler transitions.
   - Use the same tokenizer and chat template as the frontdoor.
   - Why it may help: the offline `LLM.generate` test showed no HTTP/SSE `2x`
     win, but a lower-level static lane can still quantify pure model-core
     speed without vLLM request machinery.

4. DFlash/MTP as proposer only, never as the quality source.
   - DFlash exists for Qwen3.6 35B and drafts multiple tokens in parallel, but
     use it only as a proposer. The current Quark model must verify every
     token before any result is counted.
   - First step: see whether DFlash or MTP can be wired to the shadow verifier
     bucket above. Avoid native vLLM speculative scheduling until the
     slot-widening issue is fixed.

5. Route-aware real-MoE kernel suite in `vllm-xpu-kernels`.
   - Capture real accepted-run expert routes and build microbenches around
     those distributions, not synthetic even routing.
   - Target persistent grouped GEMM, prepare/finalize, shared expert add, and
     scratch allocation. The upstream `vllm-xpu-kernels` issue list already has
     open items for per-call MoE scratch allocation and GDN/DFlash shape checks.
   - Why it may help: the vLLM XPU backend has moved kernel work into
     `vllm-xpu-kernels`; upstreamable shape repros should target that layer.

6. TP/EP simulator before implementation.
   - Write a memory/latency simulator for pure TP4 versus hybrid TP/EP versus
     hot-expert replication, using actual expert sizes, route histograms, KV
     footprint, and observed collective timings.
   - Why it may help: expert parallelism is explicitly supported in newer Intel
     XPU vLLM release notes, but a blind implementation would be expensive.

7. Graph-capture reliability campaign.
   - Device-lost during restore is now a repeated pattern after intense
     diagnostic sessions. Track graph-capture failures as a first-class metric:
     session name, log path, TP rank, graph size, cache root, uptime, and prior
     diagnostic type.
   - Try a reversible stabilization branch: fixed device order, fresh cache
     root per diagnostic, one cold idle period before restore, and host stack
     validation against Intel's published B70 BOM.

8. Public/upstream repro packet.
   - Reduce the speculative slot-widening issue to a small no-secret repro:
     accepted no-async trace, oracle `k=1` no-mamba trace, first mismatch row,
     and exact launch flags.
   - Also prepare separate kernel repros for W8A8 dense GEMM, route-skewed MoE,
     and graph-safe collectives.
   - Why it may help: this is now precise enough that Intel/vLLM maintainers or
     other B70 users can reproduce it without needing our whole service.

Additional public leads checked:

- `https://github.com/vllm-project/vllm-xpu-kernels`
- `https://github.com/vllm-project/vllm-xpu-kernels/issues`
- `https://github.com/intel/ai-containers/blob/main/vllm/0.17.0-xpu.md`
- `https://docs.vllm.ai/en/stable/models/hardware_supported_models/xpu/`
- `https://huggingface.co/z-lab/Qwen3.6-35B-A3B-DFlash`

Priority update:

1. Fix or bypass the speculative verifier row-width mutation.
2. Build a shadow/sidecar verifier harness before trying more MTP/DFlash speed
   runs.
3. In parallel, start the route-capture plus `vllm-xpu-kernels` microbench
   suite, because that work remains valuable even if speculation takes longer.
4. Treat graph-capture device-lost as a reliability metric, not just a nuisance.

## Prompt-Logprob Verifier Bucket Probe

Added a correctness-first sidecar verifier proxy:

- script: `scripts/probe-qwen36-prompt-logprob-verifier-buckets.py`
- fresh current accepted baseline:
  `data/qwen36-quark-int8-tp4-accepted-current-p512o128-20260611g.json`
- stale-baseline check:
  `data/qwen36-quark-int8-tp4-accepted-current-vs-metadata-p512o64-20260611g.json`
- initial no-async-fixture probe:
  `data/qwen36-quark-int8-tp4-prompt-logprob-verifier-buckets-20260611g.json`
  and `.md`
- current-backend probe:
  `data/qwen36-quark-int8-tp4-prompt-logprob-verifier-buckets-current-20260611g.json`
  and `.md`

Method:

- Send `prompt_token_ids + accepted_prefix_token_ids + draft_token_ids` to
  `/v1/completions` as token IDs.
- Use `prompt_logprobs=1`, `temperature=0`, `return_token_ids=true`, and
  `add_special_tokens=false`.
- Accept a draft prefix while every teacher-forced draft token has verifier
  rank `1`.
- Mutate the first draft token as a negative control; it should accept zero
  tokens.

Current-backend result:

| Window | Perfect all-rank1 | Perfect accepted / draft | Negative controls |
| ---: | ---: | ---: | ---: |
| 1 | 4/4 | 4/4 | 2/2 reject first |
| 2 | 4/4 | 8/8 | 2/2 reject first |
| 4 | 4/4 | 16/16 | 2/2 reject first |
| 8 | 3/4 | 30/32 | 2/2 reject first |
| 16 | 1/4 | 32/64 | 2/2 reject first |
| 32 | 1/4 | 52/128 | 2/2 reject first |

Interpretation:

- The rejection rule is sane: all mutated-first-token controls reject at prefix
  length `0`.
- Short windows prove the token-id prompt and prompt-logprob path are wired
  correctly.
- Longer perfect-draft windows are not always rank-1 under teacher-forced
  prefill even when those tokens came from the current accepted greedy decode.
  So this probe is a useful diagnostic, but it is not a production verifier and
  not a substitute for a KV-resident shadow verifier.
- The result strengthens the case for temporary-KV verification inside vLLM:
  a sidecar that re-prefills every candidate is both slow and semantically
  different enough on Qwen3.6/GDN/MoE sequences to be unsafe as the final
  acceptance authority.

## Rolling Re-Prefill Verifier Probe

After the prompt-logprob probe, tightened token capture first:

- `scripts/qwen36-completion-oracle-trace.py` now requests
  `return_token_ids=true`, stores API-returned output token IDs, and records
  retokenized text IDs separately.
- Fresh API-token-ID baseline:
  `data/qwen36-quark-int8-tp4-accepted-current-apiids-p512o128-20260611h.json`
- It matches the prior current baseline exactly:
  `baseline_match_all=true`, and both cases have
  `api_vs_retokenized_output_token_ids_match=true`.

Added a rolling one-token verifier probe:

- script: `scripts/probe-qwen36-rolling-next-token-verifier.py`
- short artifact:
  `data/qwen36-quark-int8-tp4-rolling-next-token-verifier-current-p512o32-20260611h.json`
  and `.md`
- full artifact using API token IDs:
  `data/qwen36-quark-int8-tp4-rolling-next-token-verifier-apiids-p512o128-20260611h.json`
  and `.md`

Method:

- For each accepted output position, send
  `prompt_token_ids + accepted_output_token_ids[:position]` as token IDs to
  `/v1/completions`.
- Ask the accepted backend for exactly one next token with `temperature=0`,
  `top_p=1.0`, `seed=20260611`, `return_token_ids=true`, and
  `add_special_tokens=false`.
- Compare that one generated token to the accepted baseline token at the same
  position.

Full result:

| Case | Checked | Matched | First mismatch |
| --- | ---: | ---: | --- |
| `natural_latency_plan` | 128 | 122 | pos `17`: expected `11436`, got `321` |
| `repetitive_kernel_notes` | 128 | 126 | pos `14`: expected `4752`, got `6126` |

Important decoded example:

- In `repetitive_kernel_notes`, the accepted incremental decode reaches a
  prefix ending in `Intel X` and then emits token `4752` (` unique`).
- A fresh one-token re-prefill request from the same token prefix emits token
  `6126` (`PU`), continuing the original prompt phrase `Intel XPU`.

Conclusion:

- Re-prefill verification is not semantically aligned with the accepted
  incremental decode for this Qwen3.6/GDN/MoE path.
- A production sidecar cannot reconstruct verifier state from token IDs and
  re-prefill every prefix. It would verify a different state trajectory.
- The next verifier-safe speculation target must preserve rolling model state:
  either an in-engine temporary-KV/request-state fork, or a rolling sidecar
  engine that is advanced token-by-token in lockstep with accepted output and
  never rebuilds accepted output prefixes through prefill.
- This makes prompt-logprob and rolling re-prefill probes diagnostic artifacts
  only. They are useful for rejecting unsafe verifier designs, not for
  production acceptance.

## Fresh External Signals

Refreshed exact-model and related public feeds:

- exact Quark W8A8 row:
  `data/localmaxxing-qwen36-quark-w8a8-int8-refresh-20260611g.json`
  - still `1` exact-model public row
  - current public row remains `cmq8yhxvo001ipb0149aoa79o` at
    `99.428358` output tok/s, `76.454061 ms` TTFT
- FP8 comparison feed:
  `data/localmaxxing-qwen36-fp8-refresh-20260611g.json`
  - includes a `253.7 tok/s` public FP8/DFlash-style signal on different
    hardware/engine assumptions
- MTP comparison feed:
  `data/localmaxxing-qwen36-unsloth-mtp-refresh-20260611g.json`
  - useful only as a speculation recipe source; it is not our quantization or
    accepted model

Fresh issue/search leads:

- `https://github.com/vllm-project/vllm/issues/40756`
  - Qwen3.6 FP8 MTP long-sequence crash with invalid `-1` scheduled drafts.
    This matches our concern that the stock speculative state path needs
    verifier-state isolation before promotion.
- `https://github.com/vllm-project/vllm/issues/43559`
  - prefix caching plus MTP changes quality on a Qwen3.6 classification task.
    Keep prefix caching disabled in speed/quality gates until speculation is
    independently proven.
- `https://github.com/vllm-project/vllm/issues/34650`
  - speculative scheduling can move token counters ahead of actual accepted
    output, breaking reasoning-end detection. This is another concrete example
    of scheduler/accounting drift, close to our `prev_num_draft_len` and slot
    mapping findings.
- `https://github.com/ggml-org/llama.cpp/issues/23149`
  - llama.cpp SYCL MTP on Qwen3.6 also has garbled/truncated output reports.
    This keeps llama.cpp/SYCL MTP as a diagnostic branch, not an immediate
    production escape hatch.
- `https://github.com/ggml-org/llama.cpp/discussions/23313`
  - Intel GPU SYCL performance data is active and worth watching for B70/Q8
    engine-bakeoff clues.

## Things To Try: Bolder V3

These are bigger than ordinary knob sweeps. They preserve the current rule:
Qwen3.6 35B, 8-bit/high-fidelity weights, current Quark INT8 model as the
quality authority, no Qwen3.5 detours, and no 4-bit promotion.

1. Temporary-KV verifier fork.
   - Add a verifier path that forks the request state, KV pointers, block
     tables, GDN/Mamba recurrent state, and slot mappings for a draft window.
   - Run the verifier on the fork, then commit only the accepted prefix to the
     live request.
   - This directly targets the observed failure: actual speculation widens the
     live verifier row at `rank_step=1`.

2. Rolling sidecar verifier with its own KV, not prompt-logprob re-prefill.
   - Keep a second local verifier engine synchronized with the accepted output
     prefix.
   - Draft windows are checked against that sidecar's live KV, avoiding full
     re-prefill and avoiding mutation of the production request state.
   - Use it first for oracle/perfect-draft upper bounds, then for MTP/DFlash
     proposer tests.

3. Verified speculative streaming buffer.
   - Let a fast proposer draft ahead, but hold speculative text in a private
     buffer until the Quark verifier commits it.
   - This avoids user-visible corrupted loops even if the proposer path is
     aggressive.
   - Measure user-perceived latency separately from raw accepted-token speed.

4. Speculation heatmap by prompt class.
   - Record acceptance rate, first divergence, and bad-loop signatures for
     natural chat, code, structured JSON, arithmetic, repeat stability, and
     long-context needles.
   - Use the heatmap to disable speculation for structured/exact tasks while
     continuing natural-language experiments. This is not the final speed win,
     but it can make reliability work less all-or-nothing.

5. GDN/Mamba state audit.
   - The no-mamba metadata run cleared one cache-block bug, but Qwen3.6 still
     has GDN/Mamba recurrent/convolution state that can be advanced over
     rejected tokens if scheduler accounting is wrong.
   - Add trace points for state rows before and after accepted/rejected drafts.
   - A good test is oracle `k=1`: if even perfect one-token drafts drift, some
     state is being advanced in the wrong place.

6. Real-router capture as a first-class benchmark input.
   - Log expert IDs, route counts, and per-layer route skew from accepted
     p512/n512 and prompt-class runs.
   - Replay those exact distributions through `vllm-xpu-kernels` grouped-GEMM
     and MoE prepare/finalize microbenches.
   - This should replace synthetic uniform routing in future kernel decisions.

7. Hot-expert memory-for-latency plan.
   - Use real route histograms to decide whether the hottest experts can be
     duplicated or placed to reduce cross-card traffic.
   - Run memory math against 32K KV before coding anything.
   - This is a possible single-user latency win if pure TP4 is overpaying for
     MoE collectives.

8. Single-stream Level Zero command-graph runner.
   - Capture a whole decode token as a static command graph for batch-1:
     attention/GDN, MoE, residual/norm, collectives, and logits.
   - Keep it separate from production until it exactly matches accepted token
     traces.
   - Goal: quantify whether vLLM graph fragmentation/dispatcher overhead is
     a hard `~100 tok/s` ceiling.

9. Strict 8-bit engine bakeoff with quality gates.
   - Try current vLLM Quark W8A8, llama.cpp/SYCL or Vulkan Q8_0, OpenVINO/
     oneDNN GenAI if Qwen3.6 MoE is supported, and any native XPU W8A8 path.
   - Count only runs that preserve quality against BF16/current Quark gates,
     support 32K context, and do not use AWQ/GPTQ-4bit/Q4/MXFP4.
   - Purpose: learn whether vLLM/XPU is the bottleneck, not to lower quality.

10. Upstream/bounty packet branch.
    - Package the smallest reproductions for:
      - speculative slot-mapping drift,
      - MTP/prefix-cache/accounting quality hazards,
      - route-skewed W8A8 MoE grouped GEMM,
      - graph-safe tiny collectives.
    - Include public artifacts, launch flags, environment, and expected versus
      actual behavior.
    - This can bring Intel/vLLM help while local work continues.

11. Reliability scoreboard.
    - Track every restore and diagnostic with startup time, graph-capture
      outcome, TP rank of any failure, cache root, host uptime, and frontdoor
      pause/drain state.
    - Treat `UR_RESULT_ERROR_DEVICE_LOST` as a regression metric. Speed wins
      that increase device-lost frequency do not graduate.

12. Production service split after speed proof.
    - Keep a conservative accepted lane for structured/exact requests.
    - Add a latency lane only after verifier-isolated speculation passes
      repeat64/long-context and request-class gates.
    - Keep two TP2 or c1/c4 replica experiments for aggregate throughput, but
      do not confuse them with the single-request `>200 tok/s` goal.

## Things To Try: Bolder V4

Added after the prompt-logprob and rolling re-prefill verifier probes. The main
new lesson is that "same token prefix" is not enough for this model family:
GDN/MoE incremental state can pick a different next token after full re-prefill
than the live accepted decoder picked. Future verifier work must preserve model
state, not just token IDs.

Local vLLM streaming-input/session finding:

- vLLM V1 has an internal `AsyncLLM.generate()` path that accepts an async
  generator of `StreamingInput` chunks.
- The scheduler keeps a resumable request, enters
  `WAITING_FOR_STREAMING_REQ`, appends the next prompt chunk, and keeps computed
  output tokens as part of the next prompt.
- Current behavior deliberately discards the final sampled token from the prior
  chunk before resuming. That makes it useful as a harness candidate, but not a
  direct speculative verifier.
- The public OpenAI chat/completions frontdoor does not expose this text-session
  mechanism today. The visible integration is realtime transcription, where
  generated token IDs are fed back through an input queue.

New concrete follow-ups:

1. Streaming-input verifier harness.
   - Build a small local Python harness against `AsyncLLM.generate()` with an
     async `StreamingInput` generator.
   - Feed accepted token IDs back one chunk at a time and test whether the
     resident-KV session matches accepted incremental decode better than
     re-prefill did.
   - If it matches, use it as the first rolling-sidecar prototype. If it still
     drifts, the production answer must be in-engine request-state forking.

2. State fingerprint trace.
   - Add opt-in hashes for per-step KV block IDs, slot mappings,
     GDN/Mamba recurrent/convolution state, and selected routed-expert state.
   - Compare accepted decode, prompt-logprob re-prefill, streaming-input
     continuation, and speculative decode at the first divergent token.
   - The goal is to identify whether drift comes from recurrent state,
     speculative placeholder accounting, cache-block layout, or sampling/logits
     differences.

3. Copy-on-write KV/request fork.
   - Prototype a verifier request fork that shares immutable prefix blocks and
     writes speculative blocks into scratch space.
   - Commit accepted blocks and request counters only after verification.
   - This is the cleanest in-engine architecture if streaming-input cannot
     model the live state accurately.

4. Two-lane verifier graph.
   - Instead of mutating the live request with draft tokens, run draft
     verification as a second lane in the same decode graph/batch.
   - The live lane produces the canonical next token; the verifier lane checks a
     draft window using copied state. Only the accepted prefix is merged.
   - This is high-risk but could keep graph efficiency while isolating state.

5. Spec-shape graph-bucket autotuner.
   - Generate capture sizes directly from speculative config:
     `1 + num_speculative_tokens` plus nearby padding buckets.
   - The n-gram2 `capture-size-3` result proved a missing bucket can produce
     device loss on XPU. Make the bucket list derived, not hand-maintained.
   - Track bucket hit/miss, compile count, and device-loss frequency.

6. MTP proposer without hybrid checkpoint mutation.
   - Load official Qwen3.6 FP8 MTP tensors in a separate proposer process or
     sidecar service, leaving the Quark W8A8 INT8 checkpoint untouched.
   - The current Quark verifier must still approve every emitted token.
   - This avoids pretending the Quark checkpoint has native MTP, while still
     testing the only public path that plausibly crosses `200 tok/s`.

7. Early-exit/self-draft proposer.
   - Use hidden states from earlier verifier layers as a lightweight draft
     source, then verify with the full Quark model.
   - This may be easier than a separate draft model if hidden-state extraction
     can be made cheap and state-safe on XPU.
   - It only counts if final tokens match the accepted verifier gates.

8. Real-route MoE locality optimizer.
   - Build expert co-activation matrices from accepted prompt-class runs.
   - Try expert physical reordering, hot-expert packing, and hot-expert
     duplication plans before changing kernels.
   - The memory budget must include 32K KV and production headroom. If hot
     duplication does not fit, record that instead of forcing it.

9. Column-major / locality-aware W8A8 grouped-GEMM prototype.
   - The PyTorch MoE locality work showed large gains from scheduling that
     reuses columns of expert weights for skinny MoE GEMMs.
   - Port the idea to shape-exact XPU W8A8 grouped GEMM using real routed
     expert histograms, not uniform synthetic routing.
   - Keep it as a standalone parity microbench until it beats the current
     `vllm-xpu-kernels` path.

10. Decode-only static graph runner.
    - Build an offline single-stream runner that bypasses OpenAI serving,
      output merging, metrics, and request queue overhead.
    - Reuse the same model weights and XPU kernels, then compare core decode
      tok/s to endpoint tok/s.
    - If the core is far faster, build a production latency lane. If not, stop
      chasing server overhead and focus on kernels/speculation.

11. Strict Q8/W8A8 engine bakeoff.
    - Re-run engine comparisons only with 8-bit/high-fidelity candidates:
      vLLM Quark W8A8, llama.cpp SYCL/Vulkan Q8_0, OpenVINO/oneDNN GenAI if it
      supports Qwen3.6 MoE, and any native XPU W8A8 stack.
    - Do not count Q4, AWQ, GPTQ-4bit, MXFP4, or Qwen3.5.
    - The bakeoff answers whether vLLM/XPU is structurally slow for this model.

12. Disaggregated prefill/decode experiment.
    - Treat prefill and decode as different workloads. Keep TP4 for 32K prefill
      if it is best, but test whether decode can move to a lower-collective
      layout after the prompt is resident.
    - This likely needs KV transfer or a custom runner, so it belongs after
      state fingerprinting.

13. Upstreamable XPU kernel packet.
    - Target `vllm-xpu-kernels`, because current vLLM direction is to move XPU
      kernels there.
    - Package three shape-exact repros: W8A8 dense GEMM, route-skewed W8A8 MoE
      grouped GEMM, and graph-safe tiny collectives.
    - Include expected speed targets based on the accepted `99.4 tok/s` service
      and the `>200 tok/s` single-user goal.

14. Quality scoreboard expansion.
    - Keep the current repeat64/needle/canary gates, but add:
      - API token ID capture for every promoted speed run,
      - prompt-class acceptance histograms for speculation,
      - BF16/current-Quark semantic diffs for any engine-bakeoff candidate,
      - startup/restart/device-lost counts for reliability.
    - Any result that is faster but weakens the gate stays diagnostic.

Priority update:

1. First implement the streaming-input verifier harness. It is the cheapest way
   to test whether a resident-KV sidecar can be semantically aligned.
2. If streaming-input aligns, turn it into a rolling sidecar benchmark with
   perfect drafts and MTP proposer experiments.
3. If streaming-input drifts, move directly to copy-on-write request/KV fork.
4. In parallel, keep real-route MoE capture and W8A8 grouped-GEMM microbenches
   moving, because they remain useful even if speculation takes longer.

Sources/leads for this V4 queue:

- `https://docs.vllm.ai/en/latest/features/speculative_decoding/`
- `https://github.com/vllm-project/vllm-xpu-kernels`
- `https://docs.vllm.ai/en/latest/design/moe_kernel_features/`
- `https://github.com/vllm-project/vllm/issues/33214`
- `https://github.com/vllm-project/vllm/issues/26963`
- `https://github.com/PMZFX/intel-arc-pro-b70-benchmarks`
- `https://pytorch.org/blog/accelerating-moe-model/`

## Streaming-Input Verifier Harness

Added `scripts/probe-qwen36-streaming-input-verifier.py`.

Purpose:

- Test vLLM's internal streaming-input/session path as a resident-KV verifier
  candidate.
- Feed the accepted baseline prompt once, ask for one token, then feed the
  accepted baseline token back as the next `StreamingInput` chunk.
- Compare each generated one-token continuation to the accepted API-token
  baseline without full-prefix re-prefill.

Why this matters:

- The rolling re-prefill probe proved that full-prefix re-prefill can drift
  from the live accepted decoder, for example `Intel X` -> ` unique` in the
  accepted stream but `Intel X` -> `PU` after fresh re-prefill.
- Streaming-input continuation should keep the resident session state and
  compute the fed accepted token incrementally. If it aligns, it is a plausible
  sidecar-verifier substrate. If it drifts, the next path is in-engine
  copy-on-write request/KV forking.

Implementation notes:

- Uses `AsyncLLM.generate()` with an async generator of `StreamingInput`
  chunks.
- Uses `TokensPrompt(prompt_token_ids=[...])` so the baseline API token IDs are
  authoritative.
- Uses `SamplingParams(max_tokens=1, temperature=0, top_p=1.0,
  output_kind=DELTA, detokenize=False)`.
- Feeds the expected accepted token back after each observed token. This is
  deliberate: we are testing whether the verifier can stay aligned to the
  accepted baseline prefix, not whether its first mismatch should poison later
  positions.
- Defaults to prefix caching disabled, because prefix-cache/speculation quality
  interactions are not yet cleared.

Preflight artifacts:

- `data/qwen36-quark-int8-tp4-streaming-input-verifier-preflight-20260611.json`
- `data/qwen36-quark-int8-tp4-streaming-input-verifier-preflight-20260611.md`

Preflight command:

```bash
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/probe-qwen36-streaming-input-verifier.py \
  --preflight-only \
  --baseline-json data/qwen36-quark-int8-tp4-accepted-current-apiids-p512o128-20260611h.json \
  --limit-cases 1 \
  --max-tokens-per-case 4 \
  --output-json data/qwen36-quark-int8-tp4-streaming-input-verifier-preflight-20260611.json \
  --output-md data/qwen36-quark-int8-tp4-streaming-input-verifier-preflight-20260611.md
```

Preflight result:

- case count: `1`
- loaded case: `natural_latency_plan`
- prompt tokens: `502`
- output tokens available: `128`
- no vLLM engine was started
- syntax check passed with `/home/steve/.venvs/vllm-xpu/bin/python -m py_compile`

Full-run command for a maintenance window:

```bash
PYTHONPATH=/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels \
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:${LD_LIBRARY_PATH:-} \
ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 \
ZE_AFFINITY_MASK=0,1,2,3 \
CCL_ATL_TRANSPORT=ofi \
CCL_TOPO_P2P_ACCESS=1 \
VLLM_XPU_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 \
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES=1 \
VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP=1 \
VLLM_XPU_CUSTOM_ALLREDUCE_GRAPH_CLONE_INPUT=1 \
VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT=1 \
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/probe-qwen36-streaming-input-verifier.py \
  --baseline-json data/qwen36-quark-int8-tp4-accepted-current-apiids-p512o128-20260611h.json \
  --limit-cases 2 \
  --max-tokens-per-case 32 \
  --stop-on-first-mismatch \
  --output-json data/qwen36-quark-int8-tp4-streaming-input-verifier-current-p512o32-YYYYMMDD.json \
  --output-md data/qwen36-quark-int8-tp4-streaming-input-verifier-current-p512o32-YYYYMMDD.md
```

Current runtime decision:

- The live Quark W8A8 backend is resident in tmux session
  `qwen36-tp4-accepted-restored-after-oracle1-short-20260611a`.
- Frontdoor status at the time of this note: active `0`, queued `0`, paused
  for public traffic with local traffic allowed.
- The resident service owns the four XPUs, so the full streaming-input probe
  was not launched in this pass. Run it after a deliberate service drain/stop or
  on an isolated XPU slice.

## Full Streaming-Input Result And New Bigger Ideas

Ran the full streaming-input verifier after draining/stopping the resident
backend, then restored the accepted backend.

Artifacts:

- `data/qwen36-quark-int8-tp4-streaming-input-verifier-current-p512o32-20260611i.json`
- `data/qwen36-quark-int8-tp4-streaming-input-verifier-current-p512o32-20260611i.md`

Result:

- `all_matched`: `false`
- loaded cases: `2`
- executed before stop: `natural_latency_plan`
- checked tokens: `26`
- matched tokens: `25`
- first mismatch: position `25`, expected token `198` (`"\n"`), generated token
  `271` (`"\n\n"`)
- session throughput in this harness: `1.80 tok/s`; this is harness overhead
  and is not a production speed metric.

Interpretation:

- The simple `StreamingInput` sidecar verifier is not safe enough to promote.
- The mismatch is a small whitespace branch after a repeated sentence, not a
  major semantic divergence, but exact-token parity is the right gate for a
  verifier that would accept or reject speculative tokens.
- This result narrows the next debug pass: reproduce token position `25` with
  top-k logprobs from accepted API decode, streaming-input decode, and
  prompt-logprob re-prefill. If token `198` and `271` are near ties, we need
  deterministic state/seed parity. If they are not near ties, the streaming
  session state is not equivalent to the accepted decoder state.
- Because the streaming-input path drifted, the next quality-safe architecture
  is still in-engine copy-on-write request/KV forking, not an external
  sidecar that replays accepted tokens.

Fresh external/public checks from this pass:

- Exact Localmaxxing row for
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`: still one public row,
  `99.428 tok/s`, TP4, 4x Arc Pro B70, current Quark W8A8 recipe.
- Arc Pro B70 + Qwen public rows now show our exact-model row near the top of
  the B70/Qwen set, with the close duplicate base-model row at about
  `99.77 tok/s`.
- vLLM's XPU documentation now lists Arc Pro B-series as validated hardware.
- vLLM's Qwen3.5/Qwen3.6 recipe records Qwen3.6 35B-A3B as a 35B total /
  3B-active MoE with `256` experts and `8 routed + 1 shared` experts. That
  reinforces that MoE routing and collectives, not dense parameter count alone,
  are the likely decode bottleneck.
- Intel's grouped-GEMM tuning issue explicitly calls out decode-stage routing
  skew and tile configuration as major MoE performance factors.
- The open B580/XPU vLLM issue is asking the same class of questions we are:
  Xe2 Flash Attention, KV dtype, block size, MP versus Ray, and mandatory
  environment variables. No accepted upstream recipe appears to solve this yet.

Sources checked:

- `https://localmaxxing.com/api/leaderboard?hfId=nameistoken%2FQwen3.6-35B-A3B-Quark-W8A8-INT8&limit=20`
- `https://localmaxxing.com/api/leaderboard?modelFamily=qwen&hardwareName=Arc%20Pro%20B70&engineName=vllm&limit=20`
- `https://docs.vllm.ai/en/v0.18.0/models/hardware_supported_models/xpu/`
- `https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html`
- `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`
- `https://github.com/vllm-project/vllm/issues/35638`

Additional things to try:

1. Streaming-input mismatch microscope.
   - Add a narrow replay mode for `natural_latency_plan` positions `20-28`.
   - Capture top-k logprobs and decoded text for accepted API decode,
     streaming-input decode, and rolling prompt-logprob re-prefill.
   - Try no-async scheduling, cumulative output mode, and exact accepted API
     sampling parameters before rejecting the path permanently.

2. Copy-on-write KV/request fork.
   - Implement the verifier inside the vLLM engine where the accepted request
     already owns the correct KV state.
   - Fork the request state, score one or more candidate draft tokens, then
     discard the fork.
   - This is the cleanest quality-preserving route after the streaming-input
     sidecar drift.

3. Router-distribution capture from real decode.
   - Log Qwen3.6 top-k expert IDs and per-expert token counts during p512/n512
     accepted decode.
   - Feed the real skew into grouped-GEMM microbenches instead of synthetic
     even routing.
   - Use the captured distribution to decide whether expert hotset pinning or
     partial expert duplication is plausible on four B70s.

4. Latency-mode expert hotset experiment.
   - Create a diagnostic slot with a shorter context cap to free VRAM, while
     keeping the same 8-bit model weights.
   - Use the freed memory to test replicated hot experts or alternate EP/TP
     layouts.
   - This is not the final 32K production slot, but it can answer whether VRAM
     headroom is blocking a faster MoE layout.

5. XPU grouped-GEMM tile autotune for the actual routed shapes.
   - Build a microbench from live router captures.
   - Sweep tile sizes, expert sorting, token grouping, and prepacked layout in
     `vllm-xpu-kernels`.
   - Promote only if the full endpoint passes repeat64, canary hash, and
     BF16/current-Quark comparison gates.

6. Persistent MoE/decode loop prototype.
   - Move beyond Python custom-op wrappers and test a persistent single-kernel
     MoE path for small decode batches.
   - Include expert routing, W8A8 grouped GEMM, shared expert add, and final
     reduction/epilogue where feasible.
   - This is high-risk but maps directly to the external Intel Arc MoE
     optimization signals.

7. Graph-safe tiny collective specialization.
   - Extract the exact hidden-size all-reduce/reduce-scatter shapes from the
     AOT census.
   - Prototype a graph-safe low-latency path for these small BF16 messages.
   - The prior custom all-reduce path helped, but the remaining graph still has
     enough collectives that a shape-specialized route could matter.

8. MTP/proposer sidecar without changing the verifier.
   - Keep the current Quark INT8 model as the final verifier.
   - Test official Qwen3.6 MTP assets, DFlash/EAGLE-style proposers, or a
     smaller Qwen3.6-family draft only as candidate-token generators.
   - Score accepted-token throughput and exact output parity, not draft-model
     throughput.

9. Same-model 8-bit engine bakeoff.
   - Find or build a Qwen3.6 35B 8-bit GGUF/SYCL or other Intel-friendly engine
     route.
   - Do not promote 4-bit results, but use llama.cpp/SYCL as a diagnostic for
     whether vLLM/XPU is leaving single-request latency on the table.

10. Repro pack for upstream.
    - Package three small, no-secret repros for maintainers:
      - W8A8 dense GEMM shape from the accepted graph,
      - route-skewed MoE grouped GEMM shape from real decode,
      - graph-safe tiny collective shape from TP4.
    - Include current throughput, target throughput, env, commit SHAs, and the
      exact Arc Pro B70 topology.

11. Production-stability shadow loop.
    - Once a candidate shows speed, run c1/c2/c4/c8/c16/c32/c48 with a
      repeat-quality smoke after each stage.
    - Track device-lost events, restart time, first-token latency, peak VRAM,
      and route drift.
    - This prevents us from accepting a fast but fragile graph-capture path.

12. Localmaxxing publication packet v2.
    - For the next public result, submit only after r8/r10 speed, peak VRAM,
      repeat64, and a short reliability loop are all captured.
    - Keep the exact command snippet and notes clean enough for others with
      B70 cards to reproduce without private paths or API keys.

## Mismatch Logprob Microscope

Added `scripts/probe-qwen36-mismatch-logprob-microscope.py` and extended
`scripts/probe-qwen36-streaming-input-verifier.py` with `--logprobs` so the
streaming-input sidecar drift can be inspected at the exact divergent token.

Artifacts:

- `data/qwen36-quark-int8-tp4-accepted-logprobs-after-streamver-p512o32-20260611j.json`
- `data/qwen36-quark-int8-tp4-streaming-input-verifier-logprobs-current-p512o27-20260611j.json`
- `data/qwen36-quark-int8-tp4-streaming-input-verifier-logprobs-current-p512o27-20260611j.md`
- `data/qwen36-quark-int8-tp4-mismatch-logprob-microscope-pos25-20260611j.json`
- `data/qwen36-quark-int8-tp4-mismatch-logprob-microscope-pos25-20260611j.md`

Result at `natural_latency_plan`, output position `25`:

| Probe | Top token | Expected `198` (`"\n"`) | Streaming `271` (`"\n\n"`) |
| --- | --- | --- | --- |
| streaming-input | `271` | rank 2, logprob `-0.797245` | rank 1, logprob `-0.672245` |
| accepted decode | `198` | rank 1, logprob `-0.737163` | rank 2, logprob `-0.737163` |
| rolling re-prefill next-token | `271` | rank 2, logprob `-0.936827` | rank 1, logprob `-0.561827` |
| prompt-logprob refill | `198` | rank 1, logprob `-0.720617` | rank 2, logprob `-0.720617` |

Interpretation:

- The accepted endpoint still exactly matches the first 32 baseline tokens when
  asked for only 32 tokens, so the live restored service remains aligned with
  the accepted trace for this fixture.
- The mismatch token is a near/tie newline branch, but the important detail is
  directional: accepted decode and prompt-logprob scoring place `198` and `271`
  on an exact tie with `198` first, while streaming-input and rolling re-prefill
  rank `271` above `198`.
- That makes external replay sidecars too fragile for exact-token verification.
  They can be useful diagnostics, but they cannot safely accept speculative
  tokens unless the final verifier runs from the accepted request's resident
  state.
- The next speed architecture should be in-engine copy-on-write request/KV
  forking: keep the accepted request state authoritative, fork it to score draft
  tokens, then discard the fork. This preserves final-model quality better than
  trying to recreate the same state in a second request.

Concrete next steps:

1. Inspect vLLM V1 request/KV state ownership for the accepted request path:
   scheduler request object, block table/KV cache handles, and sequence output
   state.
2. Identify the smallest fork point that can score one candidate token without
   committing it to the public stream.
3. Build a k=1 oracle candidate first: the draft token is the known accepted
   baseline token, and the forked verifier must accept it without changing the
   parent request output.
4. Only after k=1 oracle parity passes should MTP/DFlash/ngram proposer work
   resume. The proposer is secondary; preserving verifier state is the gate.

## Copy-On-Write Verifier Source Map And Bigger Bets

Added after the streaming-input verifier and logprob microscope proved that
external token replay is too fragile for exact speculative acceptance. The next
speed path should keep the current Quark W8A8 INT8 request state authoritative
and make every proposer disposable until the target verifier accepts tokens.

Source map from the local vLLM V1 tree:

| Component | Local source | Relevant state | Fork implication |
| --- | --- | --- | --- |
| Authoritative request | `/home/steve/src/vllm/vllm/v1/request.py:59` | `Request` owns prompt IDs, output IDs, all-token IDs, `spec_token_ids`, and `num_computed_tokens`. | The parent request's `_output_token_ids`, `_all_token_ids`, and `num_computed_tokens` must be unchanged while a verifier fork is scored. |
| Output commit | `/home/steve/src/vllm/vllm/v1/request.py:211` and `/home/steve/src/vllm/vllm/v1/core/sched/scheduler.py:1781` | `append_output_token_ids()` updates both output and all-token lists; `_update_request_with_output()` is the public commit path. | A COW verifier must not call this on the parent until acceptance is decided. |
| Scheduler ownership | `/home/steve/src/vllm/vllm/v1/core/sched/scheduler.py:163` | `self.requests` is the scheduler-side owner of active `Request` objects. | The cleanest fork point is scheduler-owned, not an OpenAI sidecar request. |
| Scheduled compute advance | `/home/steve/src/vllm/vllm/v1/core/sched/scheduler.py:1090` | `_update_after_schedule()` advances `num_computed_tokens` after scheduling; rejected/spec tokens are adjusted later. | The fork needs scratch `num_computed_tokens` accounting or a separate scratch request ID. |
| Streaming session mutation | `/home/steve/src/vllm/vllm/v1/core/sched/scheduler.py:1116` | Streaming updates discard the prior final sampled token and rewrite prompt/output state. | This likely explains why the streaming-input sidecar can drift and should not be promoted as the verifier. |
| KV allocation | `/home/steve/src/vllm/vllm/v1/core/kv_cache_manager.py:225` | `allocate_slots()` allocates blocks for new and lookahead tokens, then caches only finalized tokens capped at `request.num_tokens`. | Scratch verifier rows should use scratch request IDs/blocks and be freed after scoring. Parent block IDs must remain unchanged. |
| Worker cached state | `/home/steve/src/vllm/vllm/v1/worker/gpu_input_batch.py:34` and `:337` | `CachedRequestState` mirrors request tokens, block IDs, computed token count, and output IDs; `InputBatch.add_request()` adds rows and block table entries. | A k=1 oracle can be implemented as a scratch cached request row that shares immutable prefix block IDs and appends only scratch candidate slots. |
| Spec token injection | `/home/steve/src/vllm/vllm/v1/worker/gpu_input_batch.py:485` | `update_req_spec_token_ids()` writes scheduled speculative IDs into the worker token buffer. | The current spec path mutates live row width/state; the COW path should score candidates in a separate verifier row. |

Minimal k=1 oracle algorithm:

1. Let the accepted request generate or expose the next baseline token, but do
   not emit it through a speculative path.
2. Create an internal scratch verifier request with the same prompt/output
   prefix metadata, the same immutable prefix block IDs, and a different
   scratch request ID.
3. Allocate scratch slots only for the one candidate token and run the verifier
   forward pass.
4. Assert the scratch verifier accepts the known baseline token.
5. Free scratch blocks and remove the scratch worker row.
6. Assert the parent request's token IDs, block IDs, and `num_computed_tokens`
   are byte-for-byte unchanged before the normal parent commit path runs.

Promotion gates for any verifier implementation:

- k=1 oracle accepts every baseline token for the existing `natural_latency_plan`.
- Parent request token IDs and KV block IDs are unchanged during scratch scoring.
- Scratch blocks are freed and do not pollute prefix cache or public streams.
- Logprob fingerprints match accepted greedy decode on near-tie positions such
  as token position `25` (`198` vs `271`).
- Existing quality gates still pass: exact canaries, repeat64, structured JSON,
  math/code prompts, long-context needle, and BF16/current-Quark comparison.

Bigger, bolder ideas to keep in the backlog:

1. **Two-lane in-engine verifier graph.**
   - Run a public parent lane and a scratch verifier lane in the same engine
     step. The scratch lane can score a small candidate tree while the parent
     state remains untouched.
   - Why it might matter: it avoids the sidecar replay drift and removes HTTP /
     scheduler round trips from speculative verification.
   - Proof required: k=1 oracle parity, then k=2/4 candidate acceptance without
     parent state mutation.

2. **Dynamic DFlash/MTP budget instead of fixed long lookahead.**
   - DFlash officially supports Qwen3.6 35B-A3B, but public reports show
     acceptance can collapse when the lookahead is too long or SWA/target hidden
     state handling is wrong.
   - Start with small budgets (`2-5`) and adapt per prompt class, accepted
     position, and recent acceptance rate. Do not chase draft throughput; chase
     accepted-token throughput after Quark verification.
   - This stays quality-preserving because the Quark INT8 verifier remains the
     final accept/reject authority.

3. **Route-aware persistent MoE kernel suite.**
   - Capture real Qwen3.6 route distributions from accepted p512/n512 decode,
     then tune grouped GEMM on those exact skewed shapes instead of synthetic
     even routing.
   - Target `vllm-xpu-kernels`, not one-off Python wrappers, because upstream
     Intel XPU work is moving there and MoE decode is dominated by routing
     skew, grouped GEMM launch overhead, shared expert add, and tiny epilogues.
   - Bold target: persistent decode kernel or fused route/sort/grouped-GEMM/
     shared-expert epilogue for batch-1 and small-batch A3B.

4. **Expert placement and hotset replication.**
   - Use route captures to find hot experts by layer and prompt class.
   - Create a latency-only slot with lower context or smaller KV reservation to
     free VRAM, then replicate hot experts or avoid cross-card fetch/reduce for
     the hottest paths.
   - This is separate from the final 32K production slot; it answers whether
     memory headroom or TP communication is the real single-request ceiling.

5. **TP4 versus EP/replica architecture test.**
   - Current TP4 gives the best exact-model public result, but TP4 also pays
     small collective costs every token.
   - Test whether expert-parallel or partial-replica layouts can reduce
     per-token communication while preserving the same 8-bit weights.
   - Do not use 4-bit as the solution; use lower-context latency slots only as
     a diagnostic to buy room for replicated 8-bit pieces.

6. **Graph-safe tiny collective specialization.**
   - The current stack already has custom collective work, but remaining
     decode-time hidden-size collectives may still dominate latency at batch 1.
   - Build shape-exact microbenches for the TP4 hidden-size all-reduce /
     reduce-scatter calls and either fuse them into adjacent RMS/epilogue work
     or replace them with a graph-safe low-latency path.

7. **Same-model high-fidelity engine bakeoff.**
   - Compare vLLM/XPU Quark W8A8 against any available 8-bit/high-fidelity
     path that can run Qwen3.6 35B-A3B on Intel: llama.cpp SYCL Q8/8-bit if it
     exists, OpenVINO/oneDNN GenAI if the GDN/MoE model is supported, SGLang XPU
     if viable, and native `vllm-xpu-kernels` routes.
   - Goal is not to switch blindly; it is to determine whether vLLM scheduler,
     MoE kernels, or Intel backend kernels are the main bottleneck.

8. **Quality validation expansion.**
   - Keep exact-token gates for deterministic canaries, but add logprob
     fingerprint gates around known near ties, BF16 fallback comparisons, a
     small lm-eval/API eval suite, and longer reliability loops after every
     speed win.
   - The failure mode we just saw is subtle enough that text-only smoke tests
     are not enough.

9. **Localmaxxing publication packet v3.**
   - Our exact-model public row is already the only Quark W8A8 INT8 row and the
     base-model duplicate is currently the top public Arc Pro B70 Qwen3.6 35B
     entry.
   - Next submission should include peak VRAM, command flags, quality gate
     hashes, reliability loop length, and a clean explanation of whether the
     speedup came from COW speculation, route-aware kernels, or collectives.

External notes that shaped this addendum:

- vLLM's public INT8 W8A8 docs still describe INT8 compute support in NVIDIA
  terms, which reinforces that our Intel Quark W8A8 path is relying on local or
  emerging XPU-specific work rather than a mature stock INT8 route:
  `https://docs.vllm.ai/en/stable/features/quantization/int8/`
- Intel/vLLM roadmap items point XPU quantization and kernel work toward
  `vllm-xpu-kernels`, especially for platform-specific quantization methods:
  `https://github.com/vllm-project/vllm/issues/33214` and
  `https://github.com/vllm-project/vllm/issues/37979`
- Intel's grouped-GEMM tuning issue explicitly calls out decode-stage MoE route
  skew and real token distributions as critical tuning inputs:
  `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`
- DFlash has a Qwen3.6 35B-A3B drafter, but its docs/discussions make the same
  point our probes do: target hidden state/SWA correctness and acceptance
  tuning matter more than raw proposer speed:
  `https://github.com/z-lab/dflash` and
  `https://huggingface.co/z-lab/Qwen3.6-35B-A3B-DFlash`

## Copy-On-Write Gate Extension

Extended `scripts/check-qwen36-oracle-fixture.py` so a future COW verifier patch
can prove two things at once:

1. Speculative verification actually ran.
2. The final token stream still matched the accepted baseline exactly.

New opt-in flags:

- `--expect-spec-active`
- `--min-draft-tokens`
- `--min-accepted-tokens`
- `--min-accept-rate-pct`
- `--require-spec-join`
- `--spec-summary` to override or provide a standalone spec summary JSON.

Current known-drift gate:

```bash
python3 scripts/check-qwen36-oracle-fixture.py \
  --fixture data/qwen36-quark-int8-tp4-oracle-k1-drift-fixture-20260611.json \
  --replay-json data/qwen36-quark-int8-tp4-oracle-k1-drift-replay-20260611.json \
  --mode known-drift \
  --expected-mismatches 2 \
  --expected-roles verifier_bonus_after_full_accept,replacement_after_reject \
  --expect-spec-active \
  --min-draft-tokens 15 \
  --min-accepted-tokens 14 \
  --min-accept-rate-pct 90 \
  --require-spec-join
```

Result on the current fixture:

- pass in `known-drift` mode;
- `draft_tokens=15`, `accepted=14`, `accept_rate_pct=93.3333`, `requests=2`;
- emission roles remain `verifier_bonus_after_full_accept` and
  `replacement_after_reject`.

The same fixture intentionally fails in exact COW mode:

```bash
python3 scripts/check-qwen36-oracle-fixture.py \
  --fixture data/qwen36-quark-int8-tp4-oracle-k1-drift-fixture-20260611.json \
  --replay-json data/qwen36-quark-int8-tp4-oracle-k1-drift-replay-20260611.json \
  --mode exact \
  --expect-spec-active \
  --min-draft-tokens 15 \
  --min-accepted-tokens 14 \
  --min-accept-rate-pct 90 \
  --require-spec-join
```

That exact command is the first pass target for the next scheduler/KV patch: it
must report `ok=true` while keeping speculative activity nonzero. If it only
passes with speculation disabled, it does not move the speed goal forward.

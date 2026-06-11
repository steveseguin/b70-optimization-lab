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

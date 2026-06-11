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

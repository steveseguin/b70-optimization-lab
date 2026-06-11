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

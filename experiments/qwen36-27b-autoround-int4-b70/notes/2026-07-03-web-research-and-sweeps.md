# 2026-07-03 Qwen3.6 27B AutoRound Web Research And Sweep Ledger

Model lane: `Intel/Qwen3.6-27B-int4-AutoRound` on one Intel Arc Pro B70 per
replica. Goal is fresh-response single-session decode, not warmed/cache reuse.

## Web Research Findings

Sources checked while the first local sweeps were running:

- Intel model card:
  <https://huggingface.co/Intel/Qwen3.6-27B-int4-AutoRound>
  - This checkpoint is INT4 AutoRound, group size 128, derived from
    `Qwen/Qwen3.6-27B`.
  - The card's vLLM example uses TP1, `max_model_len=2048`,
    `--reasoning-parser qwen3`, and
    `--speculative-config '{"method":"qwen3_next_mtp","num_speculative_tokens":2}'`.
- vLLM Qwen3.6 27B recipe:
  <https://recipes.vllm.ai/Qwen/Qwen3.6-27B>
  - vLLM classifies 27B as dense, hybrid GDN attention, multimodal, 262K
    native context, MTP supported for low-latency decoding.
  - Recipe says INT4 should fit a single 24GB GPU, so one B70 per replica is
    the right starting topology. Avoid TP unless a later result proves the
    PCIe cost is worth it.
  - It calls out MTP as the key low-latency path.
- vLLM Qwen3.5/Qwen3.6 guide:
  <https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html>
  - For Qwen hybrid models, `--default-chat-template-kwargs
    '{"enable_thinking": false}'` is the documented way to disable reasoning by
    default.
  - Prefix caching for Mamba cache align mode is experimental.
  - `num_speculative_tokens` is a real tuning axis; higher values can improve
    latency but acceptance/throughput trade off.
  - Reducing `max_cudagraph_capture_size` is the recommended fix when graph
    capture size exceeds mamba cache size.
- Lorbus AutoRound model card:
  <https://huggingface.co/Lorbus/Qwen3.6-27B-int4-AutoRound>
  - Plain AutoRound can quantize `mtp.fc` into `fc.qweight`, while vLLM expects
    `fc.weight`, producing 0% MTP acceptance.
  - Lorbus dequantizes only `mtp.fc` back to BF16 and claims typical 80-90%
    draft acceptance.
  - Local Intel checkpoint is not showing 0% acceptance in this runtime, but if
    acceptance stalls or MTP regressions appear, inspect `mtp.fc` loading before
    deeper kernel work.
- vLLM issue 35387:
  <https://github.com/vllm-project/vllm/issues/35387>
  - Qwen hybrid MTP can regress latency; reporter suspects host copying
    accepted-token counts before mamba postprocess.
  - Treat MTP overhead and accepted-token postprocess as likely hot paths.
- vLLM issue 40756:
  <https://github.com/vllm-project/vllm/issues/40756>
  - Qwen3.6 27B MTP with `num_spec_tokens=5` has crash reports on long
    requests.
  - Keep MTP5+ as a long-context risk until short-context MTP3/4 are clean.
- vLLM issue 45540:
  <https://github.com/vllm-project/vllm/issues/45540>
  - Intel Arc + Qwen3.6 27B reports degenerate repeated output with
    `--kv-cache-dtype fp8`; `auto` works in that report.
  - Do not switch KV dtype to FP8 for headline quality until a strict
    correctness gate proves it.
- Puget B70 multi-GPU article:
  <https://www.pugetsystems.com/labs/articles/intel-arc-pro-b70-multi-gpu-ai-inference-performance/>
  - Their FP16 TP4 Qwen3.6 27B single-user result is only 13.1 tok/s, while
    higher concurrency scales aggregate throughput.
  - This supports the current one-quantized-copy-per-GPU plan for research:
    avoid TP4 PCIe overhead unless a specific experiment requires it.
- tedivm/k0zakinio Qwen3.6 Docker stack:
  <https://github.com/tedivm/qwen36-27b-docker>
  - Uses Lorbus AutoRound INT4, MTP3, KV FP8, `max_num_batched_tokens=8192`,
    and chunked prefill/prefix cache for service throughput.
  - For our strict fresh-response lane, treat MTP3 and higher batched-token
    limits as useful experiments, but do not use prefix/cache warmed results as
    headline evidence.

Working hypotheses from the search:

1. MTP is the main speed lever; token count needs a local sweep rather than
   assuming Intel's MTP2 example is optimal.
2. MTP3 is worth testing because several external Qwen3.6 stacks use it as the
   sweet spot.
3. `max_num_batched_tokens=1024` is probably too conservative for this model.
   Test 2048/4096/8192 after finding the best MTP token count.
4. Do not use KV FP8, prefix caching, or warmed n-gram/history as record
   claims. They can be diagnostic/service-side only until strict gates pass.
5. If acceptance unexpectedly collapses, inspect `mtp.fc` loading and consider
   comparing against Lorbus' BF16-`mtp.fc` variant.

## Local Diagnostic Baseline

All rows here are diagnostic unless explicitly promoted later. They are
fresh-ish OpenAI requests with prompt cache disabled, but current vLLM omits
`prompt_tokens_details.cached_tokens` when the value is zero, and text chunks
are not exact token events. Use Prometheus metric deltas for diagnostics and
the stricter final gate for any promoted result.

Common identity:

- model snapshot:
  `/mnt/fast-ai/llm-cache/hf/hub/models--Intel--Qwen3.6-27B-int4-AutoRound/snapshots/abc86de19eb1ebbf6a7df4582341325c22ddcb7d`
- vLLM source import: `/home/steve/src/vllm`
- vLLM version: `0.20.2rc1.dev13+g9557d9108.d20260620`
- torch: `2.11.0+xpu`
- quantization: `inc`
- dtype: BF16 runtime around INT4 weights
- topology: TP1, one B70, one sequence
- prompt/output diagnostic: natural-chat preset, p512/o512, repeats=3
- request extra:
  `{"chat_template_kwargs":{"enable_thinking":false}}`

### First Results

| label | graph | MTP tokens | max capture | max batched | corrected after-first tok/s | decode ms/token | iteration tokens/step | file |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| no-spec | off | 0 | n/a | 1024 | 22.545 | 44.269 | 1.994 | `data/qwen36-27b-autoround-int4-b70-baselines/nospec-xpugraph0-ctx2048-metrics-p512o512-r3-20260703T014757Z.json` |
| MTP2 | off | 2 | n/a | 1024 | 39.256 | 25.425 | 4.219 | `data/qwen36-27b-autoround-int4-b70-baselines/mtp2-xpugraph0-ctx2048-metrics-p512o512-r3-20260703T014408Z.json` |
| MTP2 | on | 2 | 4 | 1024 | 41.142 | 24.258 | 4.184 | `data/qwen36-27b-autoround-int4-b70-baselines/mtp2-xpugraph1-cg4-ctx2048-metrics-p512o512-r3-20260703T015350Z.json` |
| MTP1 | on | 1 | 4 | 1024 | 37.547 | 26.581 | 3.438 | `data/qwen36-27b-autoround-int4-b70-baselines/mtp1-xpugraph1-cg4-ctx2048-metrics-p512o512-r3-20260703T020244Z.json` |
| MTP3 | on | 3 | 8 | 1024 | 43.780 | 22.798 | 4.980 | `data/qwen36-27b-autoround-int4-b70-baselines/mtp3-xpugraph1-cg8-ctx2048-metrics-p512o512-r3-20260703T020245Z.json` |
| MTP4 | on | 4 | 8 | 1024 | 41.391 | 24.113 | 5.236 | `data/qwen36-27b-autoround-int4-b70-baselines/mtp4-xpugraph1-cg8-ctx2048-metrics-p512o512-r3-20260703T020245Z.json` |

Interpretation:

- MTP is real and useful on this local Intel checkpoint: MTP2 graph-off is
  about +74% versus no-spec graph-off.
- XPU graph helps only modestly at MTP2 (`39.256 -> 41.142`, about +5%).
- MTP3 is the current diagnostic best (`43.780 tok/s`) and should be the base
  for the next short-context sweeps.
- MTP4 increases accepted/attempted tokens per step, but the added verifier /
  proposer overhead beats the token gain. Do not pursue MTP4 until another
  change reduces per-step overhead.
- These numbers are far below the user's Gemma 26B target, but they are already
  substantially above public full-precision TP4 B70 numbers for this dense
  model. The current optimization frontier is reducing MTP/GDN overhead, not
  switching to TP4.

## Active Next Sweep

Recycle GPU1-GPU3 into MTP3 graph-on runs with larger
`MAX_NUM_BATCHED_TOKENS`:

- GPU1/port 19411: MTP3, graph on, `max_capture=8`, `max_batched=2048`;
- GPU2/port 19412: MTP3, graph on, `max_capture=8`, `max_batched=4096`;
- GPU3/port 19413: MTP3, graph on, `max_capture=8`, `max_batched=8192`.

Run the same p512/o512 metrics diagnostic against all three. If a larger
batched-token value wins, rerun it once on GPU0 or as an A/B on multiple GPUs
before making it the new default.

## Batched-Token Sweep Result

Result: negative for the one-request short-context decode target.

| label | graph | MTP tokens | max capture | max batched | corrected after-first tok/s | decode ms/token | iteration tokens/step | file |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| MTP3 | on | 3 | 8 | 1024 | 43.780 | 22.798 | 4.980 | `data/qwen36-27b-autoround-int4-b70-baselines/mtp3-xpugraph1-cg8-ctx2048-metrics-p512o512-r3-20260703T020245Z.json` |
| MTP3 | on | 3 | 8 | 2048 | 40.371 | 24.723 | 4.538 | `data/qwen36-27b-autoround-int4-b70-baselines/mtp3-xpugraph1-cg8-mbt2048-ctx2048-metrics-p512o512-r3-20260703T020823Z.json` |
| MTP3 | on | 3 | 8 | 4096 | 40.361 | 24.728 | 4.578 | `data/qwen36-27b-autoround-int4-b70-baselines/mtp3-xpugraph1-cg8-mbt4096-ctx2048-metrics-p512o512-r3-20260703T020823Z.json` |
| MTP3 | on | 3 | 8 | 8192 | 41.895 | 23.823 | 4.771 | `data/qwen36-27b-autoround-int4-b70-baselines/mtp3-xpugraph1-cg8-mbt8192-ctx2048-metrics-p512o512-r3-20260703T020823Z.json` |

Interpretation:

- The vLLM warning about increasing `max_num_batched_tokens` is not a
  single-session short decode win here.
- `8192` is better than 2048/4096 but still below the default 1024 result.
- Keep `MAX_NUM_BATCHED_TOKENS=1024` for the short decode lane.
- Larger values may still matter for high-concurrency service or long-context
  prompt processing; keep those as separate service/context experiments.

Next low-risk runtime branches:

1. Add simple `VLLM_EXTRA_ARGS` passthrough to the experiment launcher so flags
   such as `--generation-config vllm` and `--no-async-scheduling` can be tested
   without editing the script.
2. Test `--generation-config vllm` on MTP3/1024. Server logs warn the model
   generation config overrides vLLM sampling defaults; requests use
   deterministic settings, so this is likely small, but it is cheap.
3. Test `--no-async-scheduling` on MTP3/1024 only if generation-config does not
   move the needle. It may reduce correctness risk in hybrid paths but can also
   harm throughput.

## Runtime-Flag Sweep Result

Result: negative/neutral. Keep async scheduling enabled; do not add
`--generation-config vllm` as a speed claim.

The first attempt to launch these variants failed because killing the API
listeners by port left previous `EngineCore` children orphaned and holding
GPU1-GPU3 memory. Cleanup used exact stale process IDs and left GPU0's MTP2
reference server running. Future process recycling should kill both the vLLM
API process and any orphan `VLLM::EngineCore` children for that experiment.

| label | graph | MTP tokens | max capture | max batched | extra args | corrected after-first tok/s | decode ms/token | iteration tokens/step | file |
| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| MTP3 baseline | on | 3 | 8 | 1024 | none | 43.780 | 22.798 | 4.980 | `data/qwen36-27b-autoround-int4-b70-baselines/mtp3-xpugraph1-cg8-ctx2048-metrics-p512o512-r3-20260703T020245Z.json` |
| MTP3 genconfig | on | 3 | 8 | 1024 | `--generation-config vllm` | 43.559 | 22.913 | 4.909 | `data/qwen36-27b-autoround-int4-b70-baselines/mtp3-xpugraph1-cg8-genconfig-ctx2048-metrics-p512o512-r3-20260703T021629Z.json` |
| MTP3 noasync | on | 3 | 8 | 1024 | `--no-async-scheduling` | 40.574 | 24.598 | 4.727 | `data/qwen36-27b-autoround-int4-b70-baselines/mtp3-xpugraph1-cg8-noasync-ctx2048-metrics-p512o512-r3-20260703T021629Z.json` |
| MTP3 genconfig noasync | on | 3 | 8 | 1024 | `--generation-config vllm --no-async-scheduling` | 41.089 | 24.291 | 4.771 | `data/qwen36-27b-autoround-int4-b70-baselines/mtp3-xpugraph1-cg8-genconfig-noasync-ctx2048-metrics-p512o512-r3-20260703T021629Z.json` |

Interpretation:

- The generation-config warning is worth cleaning up for reproducibility, but
  not a measured decode win.
- Async scheduling is part of the current speed path for this model; disabling
  it loses about 7%.
- Next high-impact branch is not another vLLM frontend flag. Test the Lorbus
  AutoRound variant that keeps `mtp.fc.weight` BF16, because target quality is
  still verifier-checked by the same target model family while draft acceptance
  may improve.

## Spec-Metrics Harness Update

The local OpenAI metrics harness now accepts extra request JSON and records
speculative decoding counters from vLLM metrics. This matters for Qwen3.6 27B
because MTP speed is bounded by both verifier cost and draft acceptance, and a
plain tok/s number alone hides which side moved.

Baseline re-measure on the ready Intel MTP3 graph server:

| label | graph | MTP tokens | max capture | corrected after-first tok/s | decode ms/token | iteration tokens/step | draft acceptance | accepted draft / gen token | file |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Intel MTP3 specmetrics | on | 3 | 8 | 42.528 | 23.469 | 4.816 | 47.393% | 0.586 | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-specmetrics-p512o512-r3-20260703T023156Z.json` |

The acceptance rate confirms this Intel package is not in the 0%-acceptance
failure mode described by Lorbus, but it is also nowhere near the claimed
80-90% acceptance. Comparing against the Lorbus BF16-`mtp.fc` packaging remains
the highest-value model-identity experiment once the download completes.

## GDN / Verifier Hot-Path Probe

Noether's local source audit pointed at accepted-state postprocess and
draft-only/local-argmax as bounded probes. GPU2/GPU3 were used while the Lorbus
checkpoint download continued.

| label | graph | MTP tokens | changed env | corrected after-first tok/s | decode ms/token | iteration tokens/step | draft acceptance | accepted draft / gen token | status | file |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Intel MTP3 baseline | on | 3 | none | 42.528 | 23.469 | 4.816 | 47.393% | 0.586 | diagnostic baseline | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-specmetrics-p512o512-r3-20260703T023156Z.json` |
| no accepted-state postprocess | on | 3 | `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0` | 46.306 | 21.553 | 4.816 | 47.393% | 0.586 | diagnostic speed win, correctness-risky | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-noacceptedpost-specmetrics-p512o512-r3-20260703T023540Z.json` |
| draft-only + local argmax | on | 3 | `VLLM_XPU_SPEC_DECODE_DRAFT_ONLY=1 VLLM_XPU_LOCAL_ARGMAX_DECODE=1 VLLM_XPU_LOCAL_ARGMAX_SPEC_ONLY=1` | n/a | n/a | n/a | collapsed during run | n/a | closed negative; server generated ~0.3-1.6 tok/s and the harness was interrupted | n/a |

Interpretation:

- Disabling non-align accepted-state postprocess improves the diagnostic by
  about `+8.9%` with identical acceptance counters, so the removed work is
  directly on the hot path.
- This is **not** a promotable result. A deterministic same-prompt
  realistic128 comparison against the baseline changed `2/12` output hashes
  (`risk-register`, `performance-hypotheses`), even though the first previews
  looked superficially similar. Files:
  `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-baseline-realistic128-20260703T024156Z.json`
  and
  `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-noacceptedpost-realistic128-20260703T024156Z.json`.
- The useful engineering direction is not permanently disabling the postprocess
  blindly; it is making that state update cheaper or proving a narrower safe
  elision for the single-session MTP3 path.
- Draft-only/local-argmax is not a speed path in this runtime. It stalled
  badly enough that the diagnostic was cancelled instead of waiting for the
  full p512/o512 repeats; do not repeat it without a source-level reason.

Static spec metadata sensitivity:

| label | graph | MTP tokens | changed env | corrected after-first tok/s | decode ms/token | iteration tokens/step | draft acceptance | accepted draft / gen token | status | file |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| static metadata disabled | on | 3 | `VLLM_XPU_GDN_DISABLE_SPEC_STATIC_GRAPH_METADATA=1` | 42.576 | 23.442 | 4.816 | 47.393% | 0.586 | no-win / neutral | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-staticmetaoff-specmetrics-p512o512-r3-20260703T024612Z.json` |

Interpretation: disabling static GDN spec metadata does not change the
single-session diagnostic enough to matter. Keep static metadata enabled.

Launcher hygiene note: early graph labels used `COMPILATION_CONFIG` as an
environment variable, but the experiment launcher did not pass it through to
`vllm serve`. The launcher now emits and passes `--compilation-config` when
`COMPILATION_CONFIG` is set. Re-test capture-size variants after that fix
instead of trusting pre-fix labels.

## Corrected Capture / Native-Fallback Probes

After fixing the launcher to pass `--compilation-config`, the real
capture-size-4 MTP3 run resolved to `cudagraph_capture_sizes=[1,2,4]` in the
engine log. It was a regression.

| label | graph | MTP tokens | max capture | changed env | corrected after-first tok/s | decode ms/token | iteration tokens/step | draft acceptance | accepted draft / gen token | status | file |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Intel MTP3 baseline | on | 3 | 8 | none | 42.528 | 23.469 | 4.816 | 47.393% | 0.586 | diagnostic baseline | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-specmetrics-p512o512-r3-20260703T023156Z.json` |
| corrected cg4 | on | 3 | 4 | `COMPILATION_CONFIG={"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":4}` | 40.822 | 24.449 | 4.599 | 43.741% | 0.566 | no-win | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg4-real-specmetrics-p512o512-r3-20260703T024922Z.json` |
| native fallback prefill-only | on | 3 | 8 | `VLLM_XPU_GDN_NATIVE_FALLBACK=prefill` | 42.344 | 23.571 | 4.816 | 47.393% | 0.586 | no-win / neutral | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-nativefallback-prefill-specmetrics-p512o512-r3-20260703T024922Z.json` |

Interpretation:

- Keep capture size 8 for MTP3. Capture size 4 excludes a shape the runtime
  benefits from and lowers acceptance/step size on this diagnostic.
- Narrowing native GDN fallback to `prefill` does not improve this MTP3 path.
  Do not use it as a speed flag without a new source reason.

## Lorbus BF16-`mtp.fc` Variant

Download completed:

```text
/mnt/fast-ai/llm-cache/hf/hub/models--Lorbus--Qwen3.6-27B-int4-AutoRound/snapshots/c3aea2d531678621989e5e2db034e32b22536e79
```

Tested side-by-side on GPU2/GPU3 with the corrected launcher.

| label | graph | MTP tokens | max capture | corrected after-first tok/s | decode ms/token | iteration tokens/step | draft acceptance | accepted draft / gen token | status | file |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Intel MTP3 baseline | on | 3 | 8 | 42.528 | 23.469 | 4.816 | 47.393% | 0.586 | current Intel diagnostic reference | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-specmetrics-p512o512-r3-20260703T023156Z.json` |
| Lorbus MTP2 | on | 2 | 4 | 41.857 | 23.844 | 4.272 | 57.773% | 0.537 | no-win | `data/qwen36-27b-autoround-int4-b70-baselines/lorbus-mtp2-xpugraph1-cg4-specmetrics-p512o512-r3-20260703T025416Z.json` |
| Lorbus MTP3 | on | 3 | 8 | 41.398 | 24.110 | 4.683 | 45.161% | 0.574 | no-win | `data/qwen36-27b-autoround-int4-b70-baselines/lorbus-mtp3-xpugraph1-cg8-specmetrics-p512o512-r3-20260703T025416Z.json` |

Interpretation:

- Lorbus does not improve this local vLLM/XPU stack. The advertised BF16
  `mtp.fc` packaging does not produce the expected 80-90% acceptance here.
- Lorbus MTP2 shows higher fractional acceptance than Intel MTP3, but lower
  accepted draft tokens per generated token and lower throughput.
- Keep Intel MTP3 as the current diagnostic baseline unless a source-level
  loader/packing fix changes acceptance materially.

## Qwen3NextMTP Packed-Module Metadata Probe

Noether flagged that `Qwen3NextMTP.packed_modules_mapping` mapped
`gate_up_proj` to `["up_proj", "down_proj"]` even though the MTP loader stacks
`gate_proj/up_proj`, and the base `Qwen3NextForCausalLM` mapping also uses
`["gate_proj", "up_proj"]`. A one-line source patch was tested and then
reverted:

```text
patches/qwen36-27b-autoround-int4-b70/qwen3-next-mtp-packed-modules-gate-up-fix-20260703.patch
```

Result: no-win. The metadata change did not improve Intel acceptance or
throughput and slightly hurt Lorbus.

| label | graph | MTP tokens | max capture | changed source | corrected after-first tok/s | draft acceptance | accepted draft / gen token | iteration tokens/step | status | file |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- | --- |
| Intel baseline | on | 3 | 8 | none | 42.528 | 47.393% | 0.586 | 4.816 | baseline | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-specmetrics-p512o512-r3-20260703T023156Z.json` |
| Intel packed-map fix | on | 3 | 8 | `gate_up_proj=["gate_proj","up_proj"]` | 42.551 | 47.393% | 0.586 | 4.816 | no-win / no-op | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-packedmapfix-xpugraph1-cg8-specmetrics-p512o512-r3-20260703T025839Z.json` |
| Lorbus baseline | on | 3 | 8 | none | 41.398 | 45.161% | 0.574 | 4.683 | baseline | `data/qwen36-27b-autoround-int4-b70-baselines/lorbus-mtp3-xpugraph1-cg8-specmetrics-p512o512-r3-20260703T025416Z.json` |
| Lorbus packed-map fix | on | 3 | 8 | `gate_up_proj=["gate_proj","up_proj"]` | 41.165 | 44.749% | 0.574 | 4.641 | no-win | `data/qwen36-27b-autoround-int4-b70-baselines/lorbus-mtp3-packedmapfix-xpugraph1-cg8-specmetrics-p512o512-r3-20260703T025839Z.json` |

Interpretation:

- The suspicious metadata does not affect this AutoRound INT4 MTP acceptance
  path, at least in this runtime. Do not carry the patch forward.
- Active vLLM source was restored after the experiment; the patch remains only
  as an artifact to avoid rediscovering it.

## Corrected vLLM-Random Synthetic MTP Sweep

After the launcher fix, a separate synthetic diagnostic used
`prompt_kind=vllm-random`, completions endpoint, `p512/o512`, `repeats=3`,
`ignore_eos`, and no chat-template request extra. This is useful for screening
MTP/graph shape changes, but it is **not** a fresh-response headline result:
the prompt is synthetic/repetitive, the output can be easy for the MTP draft,
and it does not exercise the fixed realistic prompt suite.

Do not compare these rows directly against the earlier natural-chat rows above
or against LocalMaxxing records.

| label | graph | MTP tokens | max capture | max batched | corrected after-first tok/s | decode ms/token | iteration tokens/step | draft acceptance | accepted draft / gen token | status | file |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| MTP2 cg8 | on | 2 | 8 | 1024 | 55.704 | 17.883 | 5.919 | 98.55% | 0.662 | diagnostic | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp2-xpugraph1-cg8-real-specmetrics-p512o512-r3-20260703T030850Z.json` |
| MTP3 cg8 | on | 3 | 8 | 1024 | 66.807 | 14.911 | 7.817 | 97.69% | 0.744 | diagnostic | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-clean-specmetrics-p512o512-r3-20260703T030507Z.json` |
| MTP4 cg8 | on | 4 | 8 | 1024 | 74.263 | 13.413 | 9.660 | 96.67% | 0.793 | diagnostic | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp4-xpugraph1-cg8-real-specmetrics-p512o512-r3-20260703T030850Z.json` |
| MTP5 cg8 | on | 5 | 8 | 1024 | 81.157 | 12.274 | 11.378 | 95.28% | 0.828 | diagnostic | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp5-xpugraph1-cg8-real-specmetrics-p512o512-r3-20260703T030850Z.json` |
| MTP5 cg8 mbt2048 | on | 5 | 8 | 2048 | 81.140 | 12.277 | 11.378 | 95.28% | 0.828 | no-win | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp5-xpugraph1-cg8-mbt2048-specmetrics-p512o512-r3-20260703T031846Z.json` |
| MTP5 cg16 | on | 5 | 16 | 1024 | **81.773** | **12.182** | 11.378 | 95.51% | 0.830 | current best synthetic diagnostic | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp5-xpugraph1-cg16-specmetrics-p512o512-r3-20260703T031846Z.json` |
| MTP6 cg8 | on | 6 | 8 | 1024 | 78.599 | 12.674 | 11.770 | 83.14% | 0.838 | no-win | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp6-xpugraph1-cg8-real-specmetrics-p512o512-r3-20260703T031436Z.json` |
| MTP6 cg16 | on | 6 | 16 | 1024 | 78.556 | 12.680 | 11.770 | 83.14% | 0.838 | no-win | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp6-xpugraph1-cg16-specmetrics-p512o512-r3-20260703T032251Z.json` |
| MTP7 cg8 | on | 7 | 8 | 1024 | 73.512 | 13.551 | 11.770 | 71.26% | 0.838 | no-win | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp7-xpugraph1-cg8-real-specmetrics-p512o512-r3-20260703T031436Z.json` |

Interpretation:

- Synthetic/repetitive acceptance peaks at MTP5. Higher MTP counts add draft
  work faster than they add accepted tokens.
- `max_cudagraph_capture_size=16` gives only a small synthetic MTP5 gain
  (`81.157 -> 81.773`, about `+0.8%`) and does not help MTP6.
- Keep **MTP5, cg16, max_batched=1024** as the current synthetic search
  reference, but do not promote it.

## Cold Realistic Suite Checks

The fixed realistic suite was run once per prompt, but these rows are still
research-only:

- vLLM still omitted explicit `cached_tokens=0` before the local reporting
  patch below, so the strict policy classifies these as incomplete.
- SSE deltas contain multiple generated tokens, so `tokens 1-100 after TTFT`
  cannot be measured from chunk offsets alone.
- Completions mode bypasses the chat template and emits `<think>` text; chat
  mode is cleaner for quality, but current chat streaming also groups deltas.

| label | API mode | graph | MTP tokens | max capture | median full-output tok/s after TTFT | median wall tok/s | median TTFT ms | validity | file |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| MTP3 cg8 | chat | on | 3 | 8 | 47.564 | 39.392 | 596.7 | incomplete | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-realistic128-clean-20260703T031026Z.json` |
| MTP5 cg8 | chat | on | 5 | 8 | 43.755 | 33.833 | 953.9 | incomplete | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp5-xpugraph1-cg8-realistic128-clean-20260703T031026Z.json` |
| MTP3 cg8 | completions | on | 3 | 8 | 57.172 | 45.029 | 589.3 | incomplete; emits `<think>` | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-realistic128-completions-20260703T031136Z.json` |
| MTP5 cg8 | completions | on | 5 | 8 | **63.840** | 43.529 | 914.9 | incomplete; emits `<think>` | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp5-xpugraph1-cg8-realistic128-completions-20260703T031136Z.json` |
| MTP5 cg16 | completions | on | 5 | 16 | 62.453 | 43.567 | 881.6 | incomplete; emits `<think>` | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp5-xpugraph1-cg16-realistic128-completions-20260703T032353Z.json` |
| MTP5 cg16 + zero-details patch | chat | on | 5 | 16 | 43.879 | 33.659 | 905.1 | `cached_tokens=0`, but still incomplete token-window timing | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp5-xpugraph1-cg16-realistic128-chat-zerocache-20260703T032850Z.json` |

Interpretation:

- The MTP5 synthetic win does not cleanly transfer to chat-mode cold prompts;
  MTP3 was faster in the chat full-output diagnostic (`47.564` vs patched
  MTP5/cg16 at `43.879`).
- Completions mode shows MTP5 faster on full-output after-TTFT, but output
  quality is not representative because it exposes thinking text and one row
  produced repeated punctuation. Use completions as a timing diagnostic only
  unless prompts are manually chat-templated.
- The next validity task is instrumentation, not another LocalMaxxing attempt.

## Prompt-Token Details Reporting Patch

Strict promotion requires explicit `usage.prompt_tokens_details.cached_tokens=0`
for every measured request. This vLLM checkout omitted the field when zero
because the OpenAI serving paths used truthiness checks such as
`if self.enable_prompt_tokens_details and num_cached_tokens`.

Local patch applied and preserved as:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-prompt-tokens-details-zero-20260703.patch
```

It changes the check to `num_cached_tokens is not None` for chat completions,
text completions, and disaggregated generate usage. This is a reporting-only
patch; it does not affect generation math or throughput. Restart servers after
applying it before expecting explicit zero cached-token details.

Validated on a restarted MTP5/cg16 server:

- non-stream chat and completions both returned
  `usage.prompt_tokens_details.cached_tokens=0`;
- the fixed realistic chat suite reported `cached_tokens=0` for all 12 prompts
  in
  `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp5-xpugraph1-cg16-realistic128-chat-zerocache-20260703T032850Z.json`.

## Token-ID Timing Gate

vLLM can stream generated token IDs when requests include
`"return_token_ids": true`. The realistic-suite harness now has
`--return-token-ids`; when enabled it expands streamed token-id counts into
token-id receipt timestamps and uses that as the primary `tokens 1-100 after
TTFT` metric. Text deltas remain grouped and are diagnostic only.

This resolved the previous token-window blocker without using cache/reuse or
repeated prompts. The timing source is still stream-chunk granularity: if a
chunk contains multiple token IDs, those IDs share the same client receipt
timestamp. Record `token_timing_source=openai_stream_token_ids_chunk_timestamp`
with every promoted-style result.

Strict Qwen-suite chat results, all with:

- fixed Qwen realistic suite
  `repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json`;
- 12 unique prompts, each prompt once;
- `cached_tokens=0` on every row;
- `return_token_ids=true`;
- thinking disabled through chat template kwargs.

| label | API mode | graph | MTP tokens | max capture | median tok/s 1-100 after TTFT | p10 | mean | median full-output tok/s after TTFT | median wall tok/s | median TTFT ms | validity | file |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| MTP3 cg8 | chat | on | 3 | 8 | **48.003** | 43.959 | 47.590 | 47.836 | 38.505 | 636.3 | valid | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-realistic128-chat-tokenids-20260703T033403Z.json` |
| MTP3 cg8 Qwen-suite rerun | chat | on | 3 | 8 | **47.624** | 43.998 | 48.403 | 48.484 | 39.072 | 637.3 | valid/current repro artifact | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-realistic128-chat-tokenids-qwensuite-20260703T034112Z.json` |
| MTP4 cg8 | chat | on | 4 | 8 | 45.669 | 43.031 | 46.415 | 45.934 | 36.895 | 691.4 | valid/no-win | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp4-xpugraph1-cg8-realistic128-chat-tokenids-20260703T033703Z.json` |
| MTP5 cg16 | chat | on | 5 | 16 | 43.771 | 39.464 | 44.701 | 43.712 | 32.999 | 961.3 | valid/no-win | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp5-xpugraph1-cg16-realistic128-chat-tokenids-20260703T033501Z.json` |

Interpretation:

- MTP3/cg8 is the current best valid fresh-response Qwen27 INT4 baseline.
- MTP5/cg16 remains the best synthetic `vllm-random` screen (`81.773 tok/s`),
  but it loses badly on realistic chat. Do not promote synthetic acceptance as
  real-world throughput.
- MTP4/MTP5 increase TTFT and reduce realistic median throughput. Candidate
  work should target verifier/GDN/spec accepted-state overhead, not simply
  increasing speculative-token count.
- The Qwen-suite rerun is the clean repro artifact because its embedded suite
  id is `qwen36-27b-autoround-int4-b70-realistic-v1`.

## Post-Gate Realistic Ladder: No-Spec, MTP2, MTP3 cg16

After committing the first token-ID gate checkpoint, three missing realistic
controls were run against patched servers while keeping the same Qwen suite and
fresh-response policy.

| label | API mode | graph | MTP tokens | max capture | median tok/s 1-100 after TTFT | p10 | mean | median full-output tok/s after TTFT | median wall tok/s | median TTFT ms | validity | file |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| no-spec cg8 | chat | on | 0 | 8 | 31.179 | 31.136 | 31.196 | 31.231 | 29.961 | 174.6 | valid control; one first-request graph/prefill TTFT outlier | `data/qwen36-27b-autoround-int4-b70-baselines/intel-nospec-xpugraph1-cg8-realistic128-chat-tokenids-qwensuite-20260703T035124Z.json` |
| MTP2 cg8 | chat | on | 2 | 8 | 45.638 | 43.494 | 45.406 | 46.449 | 40.603 | 389.0 | valid speed gate but no-win; one suspicious repetitive first output | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp2-xpugraph1-cg8-realistic128-chat-tokenids-qwensuite-20260703T035043Z.json` |
| MTP3 cg16 | chat | on | 3 | 16 | 50.750 | 43.744 | 49.847 | 49.113 | 40.771 | 541.3 | high observation, not promoted | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg16-realistic128-chat-tokenids-qwensuite-20260703T035043Z.json` |
| MTP3 cg16 repeat | chat | on | 3 | 16 | 47.045 | 42.268 | 47.662 | 47.928 | 38.788 | 630.6 | valid but confirms cg16 is variance/inconclusive | `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg16-realistic128-chat-tokenids-qwensuite-confirm-20260703T035252Z.json` |

Interpretation:

- No-spec is a useful clean control at ~31.2 tok/s after TTFT; speculation is
  contributing roughly +50% on this realistic suite.
- MTP2 is not better than MTP3 and showed a poor first response with repeated
  punctuation/section markers. Do not use it as the quality baseline without a
  separate quality review.
- MTP3 with capture size 16 can produce a high row, but the immediate repeat
  fell below the existing MTP3/cg8 repro (`47.045` vs `47.624`). Treat cg16 as
  inconclusive/no-promote unless a larger paired repeat shows a stable win.
- Current stable baseline to beat remains MTP3/cg8 with the Qwen-suite repro
  artifact at `47.624 tok/s` and support at `48.003 tok/s`.

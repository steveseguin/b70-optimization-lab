# Gemma 4 26B Q8 Service Node Profile: SWA-Left-Bound Baseline

Date: 2026-07-02

Status: diagnostic only. No headline claim and no LocalMaxxing submission.

## Purpose

Profile the current validated service/prefill lane after the SWA left-bound
optimization to identify the next real prompt-processing hotspot. This run was
intentionally short-output (`MAX_TOKENS=32`) to keep node profiling manageable,
so exact long-context JSON validation failed due truncation. Treat all
throughput numbers here as profiler-perturbed diagnostics only.

## Run Identity

- launcher:
  `repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh`
- source/runtime: llama.cpp `c926ad098`, B70/SYCL, GPU0 only
- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`, Q8 target lane
- draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`, `n_max=3`, `n_min=2`,
  `p_min=0.0475`
- context: `CTX_SIZE=32768`, `FLASH_ATTN=on`, `GGML_SYCL_ENABLE_VMM=1`
- service/prefill flags:
  - `BATCH_SIZE=2048`
  - `UBATCH_SIZE=1024`
  - `LLAMA_PREFILL_UBATCH_SIZE=2048`
  - `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`
  - `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1`
  - `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048`
- profiler flags:
  - `GGML_SYCL_NODE_PROFILE=1`
  - `GGML_SYCL_NODE_PROFILE_EVERY=1`
  - `GGML_SYCL_NODE_PROFILE_DETAIL=1`
- case: `lc-12288-early`, actual prompt tokens `16213`, `cached_tokens=0`

Artifacts:

- aggregate:
  `data/gemma4-long-context-service-gate-20260702T065350Z-service-nodeprofile-swalb1.json`
- run summary:
  `data/gemma4-q8-gpu0-longctx-service-nodeprofile-swalb-ctx32768-o32-20260702T065350Z-service-nodeprofile-swalb1/summary.json`
- local raw profiler log, ignored by Git via `data/**/*.log` unless explicitly
  force-added:
  `data/gemma4-q8-gpu0-longctx-service-nodeprofile-swalb-ctx32768-o32-20260702T065350Z-service-nodeprofile-swalb1/server.stdout.log`
  The useful top-30 profile excerpt is embedded below so the committed note is
  self-contained.

## Validity

- `bench_rc=1`: expected for this diagnostic because `MAX_TOKENS=32` truncated
  the exact JSON retrieval response.
- long-context gate: failed, `quality_pass_all=false`.
- canary: passed (`4` rows).
- freshness: `cached_tokens=0`; one fixed long-context prompt, no reuse.
- do not submit or promote this run. Use it only as hotspot evidence.

Observed profiler-perturbed metrics:

- approximate prefill: `1199.6807198592928 tok/s`
- TTFT: `13.514429074013606 s`
- decode after TTFT: `91.58053258222012 tok/s`
- wall-clock: `2.3081614337929013 tok/s`

## Final Node Profile Hotspots

The final node-profile block reported `graphs=96`, `unique_nodes=1423`,
`top=30`. The top entries were:

| Rank | Total ms | Calls | Avg ms | Node |
| ---: | ---: | ---: | ---: | --- |
| 1 | 622.230 | 38 | 16.374 | `FLASH_ATTN_EXT:__fattn__-5` |
| 2 | 612.903 | 38 | 16.129 | `FLASH_ATTN_EXT:__fattn__-17` |
| 3 | 612.733 | 38 | 16.125 | `FLASH_ATTN_EXT:__fattn__-23` |
| 4 | 612.457 | 38 | 16.117 | `FLASH_ATTN_EXT:__fattn__-11` |
| 5 | 609.387 | 38 | 16.037 | `FLASH_ATTN_EXT:__fattn__-29` |
| 6 | 189.938 | 38 | 4.998 | `MUL_MAT_ID:ffn_moe_gate_up-29` |
| 7 | 174.059 | 38 | 4.580 | `MUL_MAT_ID:ffn_moe_gate_up-0` |
| 8 | 159.978 | 96 | 1.666 | `FLASH_ATTN_EXT:__fattn__-0` |
| 9 | 144.289 | 96 | 1.503 | `FLASH_ATTN_EXT:__fattn__-3` |
| 10 | 142.331 | 96 | 1.483 | `FLASH_ATTN_EXT:__fattn__-1` |
| 11 | 139.965 | 96 | 1.458 | `FLASH_ATTN_EXT:__fattn__-2` |
| 12 | 137.213 | 38 | 3.611 | `FLASH_ATTN_EXT:__fattn__-6` |
| 13 | 135.873 | 38 | 3.576 | `FLASH_ATTN_EXT:__fattn__-12` |
| 14 | 135.361 | 38 | 3.562 | `FLASH_ATTN_EXT:__fattn__-24` |
| 15 | 134.874 | 38 | 3.549 | `FLASH_ATTN_EXT:__fattn__-18` |
| 16 | 134.762 | 38 | 3.546 | `FLASH_ATTN_EXT:__fattn__-15` |
| 17 | 134.689 | 38 | 3.544 | `FLASH_ATTN_EXT:__fattn__-21` |
| 18 | 134.666 | 38 | 3.544 | `FLASH_ATTN_EXT:__fattn__-14` |
| 19 | 134.439 | 38 | 3.538 | `FLASH_ATTN_EXT:__fattn__-13` |
| 20 | 134.435 | 38 | 3.538 | `FLASH_ATTN_EXT:__fattn__-27` |
| 21 | 134.180 | 38 | 3.531 | `FLASH_ATTN_EXT:__fattn__-25` |
| 22 | 134.110 | 38 | 3.529 | `FLASH_ATTN_EXT:__fattn__-20` |
| 23 | 134.040 | 38 | 3.527 | `FLASH_ATTN_EXT:__fattn__-10` |
| 24 | 134.037 | 38 | 3.527 | `FLASH_ATTN_EXT:__fattn__-8` |
| 25 | 133.959 | 38 | 3.525 | `FLASH_ATTN_EXT:__fattn__-16` |
| 26 | 133.844 | 38 | 3.522 | `FLASH_ATTN_EXT:__fattn__-7` |
| 27 | 133.825 | 38 | 3.522 | `FLASH_ATTN_EXT:__fattn__-28` |
| 28 | 133.665 | 38 | 3.517 | `FLASH_ATTN_EXT:__fattn__-19` |
| 29 | 133.586 | 38 | 3.515 | `FLASH_ATTN_EXT:__fattn__-4` |
| 30 | 133.375 | 38 | 3.510 | `FLASH_ATTN_EXT:__fattn__-9` |

The five dominant `FLASH_ATTN_EXT` nodes (`5`, `17`, `23`, `11`, `29`) have
full/global-shape details like:

```text
node{FLASH_ATTN_EXT:__fattn__-5 type=f32 ne=[512,16,2,1]}
src0{PERMUTE:Qcur_pos-5 type=f32 ne=[512,2,16,1]}
src1{PERMUTE:cache_k_l5 type=f16 ne=[512,256,2,1]}
src2{PERMUTE:cache_v_l5 type=f16 ne=[512,256,2,1]}
src3{NONE:SYCL0#attn_inp_kq_mask#0 type=f16 ne=[256,2,1,1]}
```

This differs from the many smaller SWA-ish FlashAttention nodes around
`3.5 ms` average. After SWA left-bound, the dominant service/prefill cost is no
longer the SWA window work; it is the full/global FlashAttention layers.

## Interpretation

The useful frontier is structural global FlashAttention work, not more SWA
left-bound or prefill-ubatch retuning:

- keep the validated service recipe (`ncols2=8`, prefill ubatch `2048`, SWA
  left-bound at min-Q `2048`) as the control;
- do not revisit `ncols2=16`, global right-bound host metadata,
  global causal fast-mask, hot-shape `nbatch_K=32/128`, or broad scheduler
  knobs unless the kernel shape changes materially;
- inspect the SYCL FlashAttention path for the global GQA shape
  `Q=[512,2,16,1]`, `K/V=[512,256,2,1]`, mask `[256,2,1,1]`;
- any candidate source change must run long-context A/B plus GPU crossover with
  exact JSON validation and then rerun the short decode guard to prove no
  record-lane regression.

Possible source entry points for the next design pass:

- `ggml/src/ggml-sycl/fattn-common.hpp`
- `ggml/src/ggml-sycl/fattn.cpp`
- `ggml/src/ggml-sycl/ggml-sycl.cpp`

The goal is not another environment knob sweep. The profile says to make the
global full-attention tile/scheduling path cheaper for Gemma GQA at long
context while leaving the current short decode record recipe untouched.

## Addendum: one-token prefill-focused profile

The first diagnostic used `MAX_TOKENS=32`, so it mixed prompt processing with
32 generated tokens. A follow-up profiler-only run used `MAX_TOKENS=1` and
`CANARY_REPEATS=0` to isolate TTFT/prefill as much as the harness permits:

- stamp: `20260702Tprefill1-nodeprofile-swalb1`
- aggregate:
  `data/gemma4-long-context-service-gate-20260702Tprefill1-nodeprofile-swalb1.json`
- run summary:
  `data/gemma4-q8-gpu0-longctx-service-nodeprofile-prefill1-swalb-ctx32768-o1-20260702Tprefill1-nodeprofile-swalb1/summary.json`
- local raw profiler log, ignored by Git via `data/**/*.log`:
  `data/gemma4-q8-gpu0-longctx-service-nodeprofile-prefill1-swalb-ctx32768-o1-20260702Tprefill1-nodeprofile-swalb1/server.stdout.log`

Validity is still diagnostic only:

- `bench_rc=1`, exact long-context JSON failed because `MAX_TOKENS=1` truncates
  the required answer;
- canary rows completed: `0` by design;
- `cached_tokens=0`;
- prompt tokens: `16213`;
- approximate prefill: `1197.266494005386 tok/s`;
- TTFT: `13.541680220048875 s`.

The one-token profile confirms that the same full/global FlashAttention layers
dominate TTFT/prefill, and their isolated per-call cost is larger than the
32-token mixed profile suggested:

| Rank | Total ms | Calls | Avg ms | Node |
| ---: | ---: | ---: | ---: | --- |
| 1 | 616.143 | 11 | 56.013 | `FLASH_ATTN_EXT:__fattn__-5` |
| 2 | 608.342 | 11 | 55.304 | `FLASH_ATTN_EXT:__fattn__-23` |
| 3 | 606.263 | 11 | 55.115 | `FLASH_ATTN_EXT:__fattn__-17` |
| 4 | 605.759 | 11 | 55.069 | `FLASH_ATTN_EXT:__fattn__-11` |
| 5 | 602.447 | 11 | 54.768 | `FLASH_ATTN_EXT:__fattn__-29` |
| 6 | 173.335 | 11 | 15.758 | `MUL_MAT_ID:ffn_moe_gate_up-29` |
| 7 | 165.421 | 11 | 15.038 | `MUL_MAT_ID:ffn_moe_gate_up-0` |
| 8 | 149.002 | 12 | 12.417 | `FLASH_ATTN_EXT:__fattn__-0` |
| 9 | 135.533 | 11 | 12.321 | `FLASH_ATTN_EXT:__fattn__-12` |

The top global detail shape remained:

```text
node{FLASH_ATTN_EXT:__fattn__-5 type=f32 ne=[512,16,2,1]}
src0{PERMUTE:Qcur_pos-5 type=f32 ne=[512,2,16,1]}
src1{PERMUTE:cache_k_l5 type=f16 ne=[512,256,2,1]}
src2{PERMUTE:cache_v_l5 type=f16 ne=[512,256,2,1]}
src3{NONE:SYCL0#attn_inp_kq_mask#0 type=f16 ne=[256,2,1,1]}
```

This strengthens the conclusion: the next service/prefill source work should
target the global `DKQ=576`, `DV=512`, GQA tile path for this shape. It should
not be justified from the earlier mixed decode profile alone.

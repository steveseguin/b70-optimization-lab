# 2026-06-29 upstream harvest and prefill/context ladder

Purpose: continue from the `115.8466634928202 tok/s` valid Gemma Q8 short
decode record without repeating closed config/source lanes.

## Upstream llama.cpp harvest

Fetched `origin/master` from `ggml-org/llama.cpp` after local record commit
`c926ad098` and reviewed changes touching the measured hot areas:

- `ggml/src/ggml-sycl/*`
- `src/models/gemma4.cpp`
- `src/llama-context.cpp`
- `common/sampling.cpp`
- `common/speculative.cpp`
- `tools/server/*`

No cherry-pick was selected for the active short-decode source stack.

Relevant upstream items:

- `e9fb3b3fc` SYCL tensor split-mode: useful for future TP/multi-GPU models, but
  not for the current one-full-Gemma-replica-per-B70 lane.
- `9bebfcb4b` SYCL norm UT fixes and `e7e3f3509` softmax clamp: correctness
  changes, not mapped to the current LM-head/routed-MoE hot path.
- `d1b34251b` / `fa72bc682` DFlash: already tested locally as a Gemma/Qwen
  research lane and far too slow on the current SYCL path; not a short-record
  cherry-pick.
- Server/UI/log refactors: not expected to affect the fixed cold single-session
  decode metric.

Decision: do not mix upstream into the dirty record source without a specific
hot-path diff. Preserve the current source stack and continue with either a new
measured verifier-kernel design or a separate prompt/long-context lane.

## Prefill/context ladder

Added reusable wrapper:

- `repro/gemma4-26b-a4b-q8-b70/run-vdr2-prefill-ladder.sh`

This wrapper runs the current VDR2 selected-down record recipe with synthetic
but unique cold prompts at different prompt/context lengths. It is explicitly
diagnostic:

- `REALISTIC_GATE=0`
- `BENCH_PROMPT_MODE=filled-long-unique`
- `cached_tokens=0` should still be recorded, but the prompts are synthetic;
- `headline_eligible_for_gemma_q8=false`
- `localmaxxing_submission_allowed=false`

Initial ladder launched:

| GPU | Prompt target | Context | Output | Purpose |
| ---: | ---: | ---: | ---: | --- |
| 0 | 128 | 2048 | 16 | short-prompt TTFT control |
| 1 | 512 | 2048 | 16 | medium prompt |
| 2 | 2048 | 4096 | 16 | 2K prompt |
| 3 | 4096 | 8192 | 16 | 4K prompt |

Initial ladder result:

- aggregate: `data/gemma4-prefill-ladder-20260629T161253Z.json`
- all four lanes passed;
- all benchmark requests reported `cached_tokens=0`;
- all prompts were unique (`filled-long-unique`);
- canaries passed in every lane;
- this is still diagnostic-only and not LocalMaxxing/headline eligible.

| GPU | Requested prompt | Actual prompt median | Context | Median TTFT | Median decode after TTFT | Median wall tok/s | Notes |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | 128 | 290 | 2048 | 0.353 s | 143.039 tok/s | 34.416 | short prompt/control |
| 1 | 512 | 788 | 2048 | 0.578 s | 131.991 tok/s | 22.899 | medium prompt |
| 2 | 2048 | 2791 | 4096 | 1.804 s | 110.424 tok/s | 8.210 | 2K request / ~2.8K actual |
| 3 | 4096 | 5464 | 8192 | 3.535 s | 103.723 tok/s | 4.337 | 4K request / ~5.5K actual; one slow decode row produced higher variance |

The ladder is separate from short-decode record promotion. Any future
prompt-processing optimization must rerun the short record recipe afterward to
prove no regression in the `115.846` lane.

Next diagnostic ladder should push toward 8K/12K/16K/20K requested prompts with
short outputs and one or two repeats. Because the synthetic prompt generator
overshoots the requested prompt size by roughly `1.3x`, do not jump directly to
32K requested tokens under a 32K context. Probe fit/TTFT first, keep
`REALISTIC_GATE=0`, and continue recording these rows as service/context
diagnostics only.

## Higher prompt/context probe

Second ladder:

- command shape:
  `MAX_TOKENS=8 BENCH_REPEATS=1 CANARY_REPEATS=2 LADDER_SPECS="0:8192:16384 1:12000:16384 2:16000:32768 3:20000:32768" repro/gemma4-26b-a4b-q8-b70/run-vdr2-prefill-ladder.sh`
- aggregate: `data/gemma4-prefill-ladder-20260629T161813Z.json`
- all lanes passed and reported `cached_tokens=0`;
- still diagnostic-only, not a short-decode record or LocalMaxxing evidence.

| GPU | Requested prompt | Actual prompt | Context | Output | TTFT | Decode after TTFT | Wall tok/s | Interpretation |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | 8192 | 11076 | 16384 | 8 | 7.939 s | 77.860 tok/s | 0.995 | 16K context still usable at ~11K actual prompt |
| 1 | 12000 | 16164 | 16384 | 8 | 18.366 s | 17.502 tok/s | 0.425 | near-full 16K context causes sharp decode slowdown |
| 2 | 16000 | 21511 | 32768 | 8 | 33.217 s | 1.502 tok/s | 0.208 | 32K context / long prompt hits severe decode cliff |
| 3 | 20000 | 26862 | 32768 | 8 | 42.615 s | 1.675 tok/s | 0.169 | 32K context / very long prompt still fits, but decode is not service-usable |

The server logs show prompt eval throughput around:

- `~1405 tok/s` for 11076 tokens at `ctx=16384`;
- `~649 tok/s` for 21511 tokens at `ctx=32768`;
- `~632 tok/s` for 26862 tokens at `ctx=32768`.

The more important finding is decode behavior. The `ctx=32768` lanes show very
slow eval timings even around the short canary requests before the long
benchmark row. This suggests the cliff may be tied to 32K context sizing /
graph reuse / KV/SWA behavior, not only to actual prompt length. Next isolating
run should hold `ctx=32768` constant and sweep short-to-mid prompts before any
source work.

## 32K context isolation

Third ladder:

- command shape:
  `MAX_TOKENS=16 BENCH_REPEATS=1 CANARY_REPEATS=2 LADDER_SPECS="0:128:32768 1:4096:32768 2:8192:32768 3:12000:32768" repro/gemma4-26b-a4b-q8-b70/run-vdr2-prefill-ladder.sh`
- aggregate: `data/gemma4-prefill-ladder-20260629T162133Z.json`
- diagnostic-only; not LocalMaxxing/headline eligible.

| GPU | Requested prompt | Actual prompt | Context | Output | Status | TTFT | Decode after TTFT | Interpretation |
| ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| 0 | 128 | n/a | 32768 | 16 | FAIL | n/a | n/a | second canary hit `UR_RESULT_ERROR_DEVICE_LOST` after first canary decoded at only `0.26 tok/s` |
| 1 | 4096 | 5597 | 32768 | 16 | PASS | 10.481 s | 3.119 tok/s | 32K context is already decode-unusable at ~5.6K actual prompt |
| 2 | 8192 | 11076 | 32768 | 16 | PASS | 12.929 s | 3.006 tok/s | same prompt size that gave `77.860 tok/s` at 16K context collapses at 32K context |
| 3 | 12000 | 16164 | 32768 | 16 | PASS | 21.992 s | 3.352 tok/s | 32K context remains very slow even with clean pass |

Conclusion: do **not** use the current record MTP recipe with `ctx=32768` as a
service/default long-context mode. It can fit some long prompts, but decode
throughput collapses to ~3 tok/s and at least one short-prompt 32K canary
triggered a Level Zero `UR_RESULT_ERROR_DEVICE_LOST` in
`common_speculative_impl_draft_mtp::draft`. Keep the short-decode record at its
validated context size, and treat 32K work as a separate stability/graph/KV
lane. Future long-context work should test no-spec or lower-spec settings at
32K before touching the short-record recipe.

## 32K no-spec control

Fourth ladder:

- command shape:
  `MAX_TOKENS=16 BENCH_REPEATS=1 CANARY_REPEATS=2 EXTRA_LLAMA_ARGS="--parallel 1 --cache-ram 0 --ctx-checkpoints 0" LADDER_SPECS="0:128:32768 1:4096:32768 2:8192:32768 3:12000:32768" repro/gemma4-26b-a4b-q8-b70/run-vdr2-prefill-ladder.sh`
- aggregate: `data/gemma4-prefill-ladder-20260629T162703Z.json`
- all four lanes passed;
- no device loss;
- no speculative decoding (`common_speculative_init: no implementations specified for speculative decoding`);
- still diagnostic-only, not LocalMaxxing/headline eligible.

| GPU | Requested prompt | Actual prompt | Context | Output | TTFT | Decode after TTFT | Wall tok/s | Interpretation |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | 128 | 294 | 32768 | 16 | 0.585 s | 83.611 tok/s | 20.600 | 32K context is stable without MTP at short prompt |
| 1 | 4096 | 5597 | 32768 | 16 | 4.103 s | 64.742 tok/s | 3.678 | much faster than MTP-at-32K (`3.119 tok/s`) |
| 2 | 8192 | 11076 | 32768 | 16 | 7.590 s | 57.445 tok/s | 2.033 | much faster than MTP-at-32K (`3.006 tok/s`) |
| 3 | 12000 | 16164 | 32768 | 16 | 15.558 s | 52.277 tok/s | 1.009 | stable long prompt, still below short-context record decode |

Conclusion: the catastrophic 32K failure is MTP-specific. Plain no-spec 32K is
stable and service-usable for long-context diagnostics, though decode degrades
with prompt length. Do not enable the current Q4_0 MTP draft at `ctx=32768`
until a lower-risk spec configuration is separately validated. For service
mode, a pragmatic split is:

- short/medium context: validated MTP record recipe;
- 32K context: no-spec fallback until a lower-spec or graph-safe draft path is
  proven.

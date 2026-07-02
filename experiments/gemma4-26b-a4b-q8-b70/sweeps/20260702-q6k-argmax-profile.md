# Gemma 4 26B Q8: Q6_K Draft Argmax Substage Profile

Date: 2026-07-02

## Purpose

Answer why recent work has not produced a new valid Gemma 4 26B Q8 record and
decide whether the hot MTP draft `q6_K` argmax nodes are a credible next source
patch.

The current promoted record remains:

- `data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`
- primary metric: `124.97714084813418 tok/s`
- fixed realistic cold suite, each prompt once, `cached_tokens=0` every row
- UD-Q8_K_XL target/verifier with Q4_0 MTP draft

## Why Progress Is Slow

Recent source/config lanes have mostly produced useful closures rather than a
new headline number. The remaining record path is noisy and high effort:

- current MTP lane repeatability has about `4.409%` p90 same-recipe run-median
  variation, so single-run `+1-4%` apparent wins are not trustworthy;
- easy flags are closed: p_min/n_min/depth, no-bonus/adaptive/late-head,
  accept-prefix row-by-row, top1 epilogues, LM-head one-column subgroup/DMMV,
  draft tile16, MoE rowpack/grouped variants, and recent FlashAttention retunes;
- source-level experiments require a full SYCL AOT rebuild, which can spend
  several minutes in `ocloc` even for a narrow patch.

Two independent subagent audits agreed: the remaining credible short-decode
work is not config roulette. The verifier lane needs a true non-serial
row-adaptive backend op; the non-verifier lane first needed a draft argmax
substage profile before attempting a Q6_K tile rewrite.

## Patch

Default-off diagnostic patch added:

- `LLAMA_SYCL_MUL_MAT_ARGMAX_PROFILE=1`
- optional `LLAMA_SYCL_MUL_MAT_ARGMAX_PROFILE_EVERY=N`

Scope:

- only profiles `GGML_TYPE_Q6_K`, `nvec == 1`, non-top2
  `MUL_MAT_ARGMAX` nodes whose name starts with
  `mtp_direct_argmax_unroll_token_`;
- waits after hidden-state quantization, tile/dot, and tile reduction so the
  substage times are real;
- diagnostic only: it changes timing behavior and should not be used for
  headline throughput.

Source snapshots:

- preedit:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-q6k-argmax-profile-preedit-source.patch`
- profiler patch:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-q6k-argmax-profile-source.patch`

Build result:

```text
libggml-sycl.so.0.15.2:
631d64c52a004efd52d94a79eefbb89ba3cd2a43298e4934f04da5062799ab8d
llama-server:
a09986a24283972a3b45443aa897e7d04760e689a0b406e3f630e4e7bd4d49f7
```

## Diagnostic Run

Command:

```bash
cd /home/steve/llm-optimizations
GPU_INDEX=0 PORT=19340 \
LABEL=gemma4-q8-gpu0-q6k-argmax-profile-20260702T140917Z-q6kargmaxprof \
CTX_SIZE=32768 FLASH_ATTN=on GGML_SYCL_ENABLE_VMM=1 \
GGML_SYCL_DISABLE_GRAPH=1 \
CANARY_REPEATS=4 MAX_TOKENS=128 \
REALISTIC_GATE=1 REALISTIC_METRIC_TOKENS=100 READINESS_TIMEOUT_S=900 \
LLAMA_SYCL_MUL_MAT_ARGMAX_PROFILE=1 \
LLAMA_SYCL_MUL_MAT_ARGMAX_PROFILE_EVERY=128 \
LLAMA_SERVER_SPEC_PROFILE=1 \
bash repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh
```

Evidence:

- `data/gemma4-q8-gpu0-q6k-argmax-profile-20260702T140917Z-q6kargmaxprof/summary.json`
- `data/gemma4-q8-gpu0-q6k-argmax-profile-20260702T140917Z-q6kargmaxprof/realistic-suite.json`
- `data/gemma4-q8-gpu0-q6k-argmax-profile-20260702T140917Z-q6kargmaxprof/chat-canary.json`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-q6k-argmax-profile-20260702T140917Z-q6kargmaxprof.server.log`

Validity:

- canary: `16/16` rows pass
- fixed realistic suite: pass
- `cached_tokens=0` for every prompt
- each prompt once as a cold response
- no cache/history/n-gram/checkpoint acceleration

Do not promote throughput from this run: graph was disabled and the profiler
inserts synchronizing waits. The observed median was `119.25864091241473 tok/s`,
which is diagnostic only.

## Profile Result

Last stable profiler block:

```text
sycl argmax profile: q6k_mtp_direct total_calls=1792
pos=0 calls=598 avg_ms total=0.508 quant=0.092 tile=0.389 reduce=0.026 other=0.001
pos=1 calls=597 avg_ms total=0.508 quant=0.095 tile=0.388 reduce=0.024 other=0.001
pos=2 calls=597 avg_ms total=0.505 quant=0.093 tile=0.387 reduce=0.024 other=0.001
```

Server spec profile at end:

```text
draft_ms=1778.260 calls=673 draft_tokens=1812 avg=2.642 ms
target_decode_ms=16702.392 calls=673 tokens=3928 avg=24.818 ms avg_token=4.252 ms
target_prompt_ms=4427.184 calls=56 tokens=1499 avg=79.057 ms avg_token=2.953 ms
target_generation_ms=12275.208 calls=617 tokens=2429 avg=19.895 ms avg_token=5.054 ms
```

Interpretation:

- Q6_K draft argmax is real cost, but it is not mostly launch/reduce overhead.
- About `76-77%` of each direct draft argmax node is tile/dot work
  (`~0.388-0.389 ms`).
- Quantization is about `18%` (`~0.092-0.095 ms`).
- Final reduction is only about `5%` (`~0.024-0.026 ms`).
- Other overhead is negligible.

## Decision

Do not write another scratch/reduce or tile-subgroup micro patch for this lane.
The profiler says the easy overhead is too small to clear the current
measurement bar.

A future Q6_K draft argmax win would need a real tile/dot rewrite, for example
a new direct top1 kernel that materially improves the `q6_K x q8_1` dot path or
removes hidden-state quantization without making the tile slower. Expected
upside from quant/reduce-only work is below the current variance floor.

Current best next options:

1. **Short-decode, high risk:** true non-serial row-adaptive verifier backend op
   that avoids actual Q8 LM-head work after first mismatch while preserving the
   full-bonus semantics.
2. **Short-decode, high risk:** Q6_K draft argmax tile rewrite, but only if
   there is a concrete dot-layout idea, not another reducer retune.
3. **Prompt/service lane:** separate from the short-decode record; continue only
   with exact long-context validation plus a short-suite decode guard.

No LocalMaxxing submission was made.

# Laguna DFlash bulletproof full-512 gate

Date: 2026-07-22

## Result first

- Staged exact median: **33.08582521189141 tok/s** for generated tokens
  1-100 after TTFT across the fixed 13-prompt realistic suite with
  `max_tokens=512`.
- Independent exact support median: **33.103677158430045 tok/s**.
- Prior blocked staged row: 31.77427774785138 tok/s at `max_tokens=128`.
  The validated full-512 result is 1.31154746404003 tok/s / **4.1277%** faster.
- DFlash A versus q=1: **13/13** complete token arrays, all cache-zero.
- DFlash B versus q=1: **13/13** complete token arrays, all cache-zero.
- DFlash A versus B: **13/13** complete token arrays.
- Deliberate 512-token response then next request: **2/2** exact on each
  fresh DFlash start.
- The 863-input-token rollover prompt: **1/1** exact on each start, with a
  512-token response.
- DFlash B acceptance: **4,642 / 12,040 = 38.55481727574751%**. DFlash A
  accepted 4,641 / 12,047 = 38.524113887274844%.
- This is a valid first Laguna LocalMaxxing record candidate under the full
  512-token contract. It is staged only; Claude retains submission authority.

## Root cause

The original full-512 run was 12/13 exact. `python-lru-cache` generated an
exact 512-token response, then `python-debug-window` diverged at output token
**0**. The wrong first token was not stable across asynchronous reproductions,
which ruled out a fixed greedy tie or a deterministic length-boundary error.

Target-side traces for the failing second request established the first bad
component:

1. All **132/132 input token IDs** matched an independent tokenizer render.
2. Positions were exactly `0..131`.
3. The layer-0 `attn-input` hidden/residual tensor already differed in
   **44/132 rows**.
4. The divergence therefore occurred in the target embedding / initial
   tensor-parallel reduction boundary, before QKV, paged KV access, attention,
   MoE routing, fixed-rank reductions inside the decoder, or sampling.

The carrier was the previous request's still-live asynchronous DFlash
model-runner/GPU stream state crossing into the next target prefill. In other
words, request A had returned at the API boundary while speculative target /
draft execution state and the shared embedding-collective pipeline were not a
safe boundary for request B. This was not stale logical token input, a reused
KV page, draft token history, or an unwritten deterministic reduction buffer.

The causal control was decisive: the identical A512 -> B sequence became
fully exact when DFlash asynchronous scheduling was disabled. Conversely,
disabling asynchronous scheduling on the nonspeculative q=1 teacher changes
its numerical execution contract (12/13 arrays differ later in generation),
so serialization must be scoped to DFlash rather than applied globally.

Diagnostic evidence:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/diagnose-stateleak-baseline-20260722T1400Z
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/traces/diagnose-stateleak-baseline-20260722T1400Z
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/diagnose-stateleak-q1-20260722T1400Z
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/traces/diagnose-stateleak-q1-20260722T1400Z
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/diagnose-stateleak-noasync-20260722T1400Z
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/diagnose-stateleak-inputtrace-20260722T1400Z
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/traces/diagnose-stateleak-inputtrace-20260722T1400Z
```

## Fix

`serve_laguna.sh` now adds `--no-async-scheduling` only for `dflash` and
`dflash-piecewise`. This serializes the scheduler/model-runner handoff at the
request boundary while preserving the batched q=8 target verifier inside each
request. The q=1 teacher keeps its original asynchronous scheduling contract.

The vLLM diagnostic hook can dump target `input_ids`, positions, or supplied
embeddings before embedding when `VLLM_LAGUNA_TARGET_TRACE_INPUTS=1`; it is
otherwise inert. A proposed restriction of exact attention to a new verifier
context tag failed 1/13 and was reverted. That negative run is preserved at:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/bulletproof-dflash-A-b84d326-6fc06b0-20260722T141541Z
```

## Reproducibility evidence

Canonical q=1 teacher, asynchronous scheduling enabled:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/bulletproof-q1-canonical-cb616c6-6fc06b0-20260722T142908Z
```

The fresh teacher also matched the preceding deterministic q=1 teacher
13/13, including long-then-next and rollover.

DFlash A and B, each a fresh engine process with asynchronous scheduling
disabled:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/bulletproof-dflash-fixed-A-cb616c6-6fc06b0-20260722T142210Z
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/bulletproof-dflash-fixed-B-cb616c6-6fc06b0-20260722T144020Z
```

Machine-readable comparisons:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/bulletproof-exactness-q1-vs-two-dflash-cb616c6-6fc06b0-20260722.json
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/bulletproof-repro-A-vs-B-cb616c6-6fc06b0-20260722.json
```

All 26 DFlash requests reported `cached_tokens=0`. Both starts used one
TP4+EP4 session, DP1, PP1, `max_num_seqs=1`, BF16 compute/KV, NHD KV, block
size 64, eager mode, prefix cache off, greedy draft, standard target rejection,
and the unchanged INT4 target. No response reuse, history acceleration,
context checkpoint, warmed prompt, or concurrent generation was used.

## Source and native identity

- vLLM branch: `experiment/laguna-s-2.1-xpu-bringup-20260721`
- vLLM commit: `cb616c67028117d80e0f3921e87de340c867ab4e`
- XPU kernels branch: `experiment/laguna-s-2.1-fwht-20260721`
- XPU kernels commit: `6fc06b08cd10a9e9e7d15e62e1afcf06e7ab6c73`
- No native rebuild was required for this Python/launcher fix.
- `_xpu_C.abi3.so`: `671ce1111b854ca4f3a5275af6d0b701c4dc4b18d78c47f12dfdf10a98bbe103`
- `_moe_C.abi3.so`: `f222d3e2d2a8a331e3c85f12e0d02a17aa7a89147bbbcc8ac2c2a816629a405f`
- `libgrouped_gemm_xe_2.so`: `285c9bce2001d05b89719645d8afa98a93b589e476fe6e540582009ec90e9f2a`

The DeepSeek option-4 branches and all `preserve/*` tags were untouched. All
Laguna runtime writes stayed under CorsairExternal; no `/mnt/fast-ai` write or
DeepSeek held-out pack was used.

## Staged payload and next lever

The previous blocked 31.774 queue entry was replaced by:

```text
data/localmaxxing-laguna-s-2.1-int4-b70-dflash-bulletproof-33.086tok-20260722.queue.json
```

The payload passes the LocalMaxxing helper's `--dry-run` preflight. Do not
submit without Claude's gate.

The next performance lever remains the 47 layer-level deterministic EP
all-gather + fixed-rank sum pairs, followed by a persistent/fused direct M8
MoE transaction. Preserve DFlash-only request serialization while measuring
it; removing that boundary reopens the correctness bug.

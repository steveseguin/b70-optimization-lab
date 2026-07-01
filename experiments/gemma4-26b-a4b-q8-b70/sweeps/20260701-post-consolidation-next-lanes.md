# 2026-07-01 Post-Consolidation Next Lanes

Status: active planning note after worktree consolidation. No benchmark result
or LocalMaxxing submission is implied.

## Workspace State

New optimization work should run only from `/home/steve/llm-optimizations`.
The detached `/home/steve/qwen36-results-main` worktree is audit/read-only.
See `notes/worktree-consolidation-20260701.md`.

The active llama.cpp Gemma source tree was snapshotted before new work:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-post-consolidation-current-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-post-consolidation-current-source.diffstat`

## Decode / Short-Record Lane

The current promoted path remains Q8 target/verifier + Q4_0 MTP draft with the
fixed cold realistic suite. Current record is `124.97714084813418 tok/s`, with
`cached_tokens=0` and `realistic_final_gate.passed=true`.

Current verifier shape:

- full-bonus MTP verification rows are `[last_sampled, draft0, draft1, draft2]`;
- all four rows are output rows and `spec_i_batch=[0,1,2,3]` feeds
  `common_sampler_sample_and_accept_n()`;
- backend sampled IDs avoid full logits host copy, but the target still pays
  target graph plus Q8 output/argmax work;
- profiles say target/verifier graph dominates; sampler-side accept logic is
  negligible.

Why prior accept-prefix attempts lost:

- v1 serialized rows in `ggml_sycl_mul_mat_vec_q8_0_reorder_argmax_accept_prefix()`
  and launched tile/reduce per row. It was exact, but gave up the efficient
  multi-row Q8 path and still did not skip transformer-body rows.
- v2 restored multi-row argmax first, then masked sampled IDs after mismatch.
  It saved no real LM-head/target work and added overhead.
- late-head/prefix-tail variants added a second graph/head boundary that ran
  too frequently because full-match-plus-bonus is common.

Most plausible decode v3:

1. **Candidate-bound exact LM-head proof with fallback.** For draft verifier
   rows, the candidate token is known. Compute the exact Q8 dot for that
   candidate, prove with conservative output-weight/hidden-state bounds that no
   other vocab row can exceed it, and emit the candidate only when proven.
   Fallback uses the current exact full-vocab top1 path, preserving mismatch
   correctness. Bonus row remains current full top1. This is exact but needs a
   careful source design; first useful step is to measure feasibility/proof
   rate before relying on it for performance.
2. **True backend row-gated accept-prefix.** Compute/reduce row 0, conditionally
   compute row 1/2/bonus inside one backend dependency chain, avoiding the v1
   host-loop launch overhead. This is higher risk and still cannot skip
   transformer-body rows.

Do not run more launch-flag or p_min/ubatch roulette for the short record unless
paired with one of the source mechanisms above.

## Prompt Processing / Long-Context Service Lane

The balanced service identity is:

```bash
BATCH_SIZE=2048
UBATCH_SIZE=1024
LLAMA_PREFILL_UBATCH_SIZE=2048
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8
CTX_SIZE=32768
FLASH_ATTN=on
GGML_SYCL_ENABLE_VMM=1
```

Closed knobs:

- phase prefill `2112/2176/2240/2304/2816/3072` do not preserve decode as well
  as `2048`;
- `GGML_SYCL_FATTN_DV512_GQA8_NCOLS1=1/4` are slower than implicit `ncols1=2`;
- `nbatch_fa=128` is noise/negative for the selected tile;
- disabling existing `KV_max` scan is negative;
- mask-scanned `KV_min` gave a real prefill gain but risks short-decode
  regression;
- low-threshold host left-bound such as `MIN_Q=128` regresses protected MTP
  full512 decode.

Most plausible service source lane: fast exact host SWA left-bound builder or a
per-tile left-bound representation, gated to large prefill only
(`LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048`) so the short-decode graph
is not touched. Any service win must still pass a short fixed-suite guard before
being promoted as a deployment recipe.

## Immediate Next Step

Start with decode-side feasibility, not another benchmark repeat. Inspect and
prototype only if the implementation can preserve exact Q8 target verification,
bonus semantics, and the current multi-row verifier efficiency. If that proves
too invasive for a bounded patch, switch to the SWA-left-bound service lane and
keep it separate from LocalMaxxing short-decode claims.

## Update: SWA left-bound fast builder closed negative

The first prompt-processing source lane after consolidation was tested and closed
negative: `20260701-swa-left-bound-fast-negative.md`. The default-off
`LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_FAST=1` host moving-left-bound builder
passed exact long-context validation and `cached_tokens=0`, but lost about
`0.77%` median prefill throughput versus same-window controls. Do not promote
that flag; keep the patch/result only as a preserved negative artifact.

The build issue encountered during this lane was environmental, not source-level:
the existing `q8reorder-vdr2` build directory is a oneAPI 2026.0 build and must
be rebuilt with `/opt/intel/oneapi/setvars.sh --force` sourced so the SYCL/OpenMP
link and AOT device build can find the proper runtime libraries.


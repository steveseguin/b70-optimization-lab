# Gemma 4 26B Q8 Frontier Audit After Closed Knobs

Date: 2026-07-02

Status: planning / guardrail note. No benchmark claim and no LocalMaxxing
submission.

## Purpose

Continue the Gemma 4 26B A4B Q8 optimization effort without retesting closed
lanes or producing stale workspace drift. The active target remains the fixed
realistic cold suite and the current headline remains:

- `124.97714084813418 tok/s` median generated-token throughput for tokens
  1-100 after TTFT;
- evidence:
  `data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`;
- Q8 target/verifier:
  `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- Q4_0 MTP draft, target-verified accepted tokens, `cached_tokens=0` on every
  prompt.

## What Was Rechecked

This audit re-read the current lane packet, recent sweep notes, active source
implementation, and active environment-flag inventory. The goal was to find
either an existing default-off flag that was not already closed, or a bounded
source patch that could move the current record without changing quality.

No hidden easy knob was found.

## Closed / Do Not Retest As-Is

Short-decode / verifier paths already closed for the current record identity:

- plain deeper MTP (`n_max > 3`), alternate MTP draft quantizations, `p_min`,
  `n_min`, thread, unroll, and ubatch roulette;
- `LLAMA_SPEC_ADAPTIVE_MTP=1`: already tested as adaptive-depth cap, rejected;
- no-bonus, adaptive bonus, late-head bonus, prefix-tail, and staged MTP3:
  either lose the bonus pipeline or add an extra graph/head boundary;
- accept-prefix v1: exact but serial row tile/reduce per verifier row;
- accept-prefix v2: computes all rows then masks after mismatch, so it saves no
  actual LM-head work;
- accept-prefix top1 epilogue (`LLAMA_SYCL_ACCEPT_PREFIX_TOP1_EPILOGUE=1`):
  exact but still row-by-row/serial; four-lane A/B lost `-9.80%`;
- regular Q8 top1 epilogue and partial top1 epilogue: valid but slower than the
  current sampled-ID path;
- direct sampled-ID egress / pointer-only variants: parity failures or crashes;
- candidate-bound LM-head proof in its current form: not credible unless it can
  avoid full-vocab Q8 LM-head work;
- post-argmax sampled-ID compact copy: current `copy_tensor_async_ints_by_row`
  already performs a contiguous async copy for verifier sampled rows, so there
  is no obvious row-copy loop to remove.

Target-side / no-spec / config paths already closed or not promotable:

- packed GEGLU all, LM-head one-column subgroup/DMMV/no-reorder family;
- attention/per-layer post-norm combo: no-spec signal exists, but the MTP
  same-window follow-up stayed below record and inconclusive;
- `BATCH/UBATCH=1152`, rowpack=2, and same-family target-side microchanges for
  the short headline;
- source flags that are present but undocumented in the flag inventory were
  mostly debug flags or sub-knobs of already rejected adaptive MTP.

Prompt/service paths already closed or separated from headline short decode:

- validated service default remains GQA8 + phase prefill + SWA left-bound:
  `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`,
  `LLAMA_PREFILL_UBATCH_SIZE=2048`,
  `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1`,
  `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048`;
- global causal fast-mask: valid but `+0.047%` noise;
- global host-derived right-bound: valid but `-1.18%` prefill regression;
- hot-shape `nbatch_K=32/128`: valid but only `+0.08%` to `+0.14%`, below the
  service promotion threshold;
- `ncols2=16`, forced `ncols1`, KV-max-scan disable, and SWA fast-builder
  variants are closed negative.

## Current Frontier

Further progress is source-design work, not flag search.

### Short Decode

Only two source mechanisms still look meaningfully distinct:

1. **True row-adaptive verifier inside one backend path.**
   Preserve the current full-bonus verifier semantics, but avoid actual Q8
   LM-head work for verifier rows after a mismatch without serial per-row host
   launches. This is not accept-prefix v1/v2: it must either express the
   dependency inside a single efficient backend path or otherwise avoid the
   launch/reduction overhead that made v1 lose.

2. **A real candidate-bound LM-head certificate.**
   This is only useful if it proves the known draft candidate wins without
   scanning the full vocab most of the time, while falling back to current exact
   top1 on uncertain/mismatch rows. Candidate-vs-max that still scans the full
   output matrix is not useful.

Both are high-effort and require parity-first validation. Any implementation
must preserve:

- exact Q8 target verification;
- first-mismatch true target token;
- full-match bonus row;
- `cached_tokens=0`;
- fixed realistic cold-suite validation.

### Prompt / Service

The service lane is already valid and useful. The remaining global
FlashAttention hotspot likely needs a structural tile/scheduling rewrite rather
than more per-tile bound metadata or constants. If pursued, keep it separate
from the LocalMaxxing short-decode headline and require:

- exact long-context JSON validation;
- `cached_tokens=0`;
- A/B plus GPU crossover;
- short fixed-suite guard showing no decode regression.

## Recommended Next Action

Do not launch another known-closed flag/config run. Choose one:

1. start a parity-first prototype for true backend row-adaptive verification;
2. start a feasibility/proof-rate study for a genuine candidate-bound LM-head
   certificate;
3. if prioritizing service instead of short decode, profile and redesign the
   global FlashAttention tile rather than retuning constants.

If none of these is funded, the correct state is to preserve the current
`124.977 tok/s` Q8 record and move to another model/lane rather than accumulate
more stale Gemma config artifacts.

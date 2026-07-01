# Gemma 4 26B A4B Q8 Sweep Ledger

Use this folder for short summaries of active Gemma 4 B70 sweeps. Large logs
belong under `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/`; record the log
path here instead of copying huge files into Git.

## Sweep Entry Template

```markdown
# <label>

Date:
Owner/agent:
GPU / port:

## Hypothesis

Why this should improve valid single-session decode without lowering quality.

## Run Identity

- model repo:
- filename:
- file bytes:
- model revision:
- runtime:
- runtime commit/version:
- backend:
- GPU:
- context:
- batch / ubatch:
- KV cache dtype:
- API mode:
- seed:
- command:
- env delta:
- server log:

## Result

- chat canary:
- output tok/s:
- wall tok/s:
- TTFT:
- prefill tok/s:
- peak VRAM:
- repeat stats:

## Decision

Win / loss / inconclusive / follow-up.

## Artifacts

- benchmark JSON:
- canary JSON:
- payload queue:
- response log:
- patch or diff:
```

## Rules

- Keep one entry per meaningful experiment family.
- Preserve failed runs if they rule out a knob, patch, or runtime path.
- Do not promote a sweep from this folder into `results/` until it passes the
  validity gate documented in
  [`../../../results/gemma4-26b-a4b-q8-b70/validity-gates.md`](../../../results/gemma4-26b-a4b-q8-b70/validity-gates.md).

## Recent Entries

- `20260701-geglu-down-matmul-epilogue-current-negative.md`: current-stack
  screen of `LLAMA_GEMMA4_MOE_GEGLU_DOWN_MATMUL_EPILOGUE=1`. Strict
  fresh-response 128-token lanes all passed canary, uniqueness, and
  `cached_tokens=0`, but the candidate was roughly `38-42 tok/s` slower than
  paired controls. Closed negative; compact summary:
  [`../../../data/gemma4-geglu-down-matmul-epilogue-current-negative-20260701.json`](../../../data/gemma4-geglu-down-matmul-epilogue-current-negative-20260701.json).
- `20260701-swa-fattn-host-left-bound.md`: host-derived SWA FlashAttention
  left-bound retry. Low thresholds regress the protected MTP full512 lane, but
  `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048` gives repeated
  long-context prefill wins (`+18.09%`, `+20.66%` cross-over) while MTP
  full512 A/B and cross-over stayed flat/positive. The current source patch
  defaults the enabled threshold to `2048`; explicit lower thresholds remain
  rejected. Treat as a service/prefill lane, not a LocalMaxxing headline decode
  record.
- `20260701-sycl-fattn-kv-min-template-prefill-negative.md`: isolated
  large-prefill-only KV-min FlashAttention tile retry. Four-lane long-context
  A/B was valid but negative (`-0.75%` prefill), so the patch was archived and
  not promoted.

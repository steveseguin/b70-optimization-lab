# 2026-06-26 Gemma 4 26B Q8 Record Repeat and Next Source Lane

## Outcome

Current valid fresh-response one-B70 Q8-target headline:

- run: `data/gemma4-q8-gpu0-currentrecord-control-fullrepeat-20260626T230510Z/`
- row0 after TTFT: `103.9826628154082 tok/s`
- support mean after TTFT: `104.09604904731648 tok/s`
- wall row0: `90.47935762548245 tok/s`
- canary: `1536/1536`
- cached tokens: all benchmark rows `0`
- LocalMaxxing: `cmqvjupek02pgqr01d46algvg`

This is an exact-stack repeat of the previous route-cache/fused-output recipe,
not a new mechanism. Treat it as a variance-class micro-record over
`103.95374341972274 tok/s` (`cmqviful602p0qr01vp27jw5i`).

## Validity / Freshness Check

The usual `filled-long` benchmark still uses a repeated prompt, so row0 is the
fresh-response headline and later rows are support-only even when
`cached_tokens=0`.

A new harness mode was added:

- `BENCH_PROMPT_MODE=filled-long-unique`
- `BENCH_PROMPT_MODE=filled-fixed-line-unique`

These create a deterministic different prompt per repeat and store row-level
`prompt_sha256`. A small current-stack unique-prompt screen:

- run: `data/gemma4-q8-gpu1-currentrecord-unique-fresh-screen-20260626T231140Z/`
- canary: `256/256`
- row0: `100.8959686363723 tok/s`
- fresh-eligible mean: `101.16162483108214 tok/s`
- cached tokens: all rows `0`

This confirms the repeated-prompt support mean should stay support-only unless
using unique prompt mode.

## Loss / Exhausted Variant

The `LLAMA_GEMMA4_MOE_WEIGHTED_SUM_2D=1` +
`LLAMA_SPEC_VERIFY_SOFTCAP_ARGMAX=1` full validation lost:

- run: `data/gemma4-q8-gpu3-currentrecord-wsum2d-softcapargmax-full-20260626T230510Z/`
- row0: `102.19007367061532 tok/s`
- canary: `1536/1536`
- cached tokens: all rows `0`

Do not continue this flag combination.

## Next Useful Source Lane

Gemma remains the focus. MiniMax TP4 repair is optional side work only.

The next plausible source patch is **not** naive full MoE fusion. Existing
experiments already show that broad selected-down / GEGLU / down epilogue
variants tend to lose when they disrupt the tuned Q8 matmul schedule.

Highest-ROI source direction:

- preserve the existing fast Q8 gate/up and down matmul path;
- fold the tiny selected softmax into the existing selected-down weighted-sum
  epilogue so the graph does not materialize a separate weights tensor/kernel;
- guard tightly to Gemma4 Q8 verifier shapes (`n_tokens <= 8`,
  `n_expert_used <= 8`, Q8_0 gate/up and down, F32 logits/activations, I32
  ids, no LoRA, no expert bias, no warmup).

A naive one-kernel router + gate/up + GEGLU + down + weighted-sum op is risky
because it either recomputes gate/up per output row or carries too much
intermediate state in private/local memory. The patch should fuse a small
epilogue boundary, not replace tuned matmul scheduling.

# 2026-07-03 - Bonus Argmax Fast Path No-Win

## Goal

Avoid the full sampler call for speculative **bonus** rows in the strict
all-greedy/no-logprobs path. This does not remove LM-head compute; it only
replaces bonus-row sampler plumbing with a direct `argmax` over the already
computed bonus logits.

This was a bounded screen before the deeper fused LM-head top-1 work.

## Patch

Patch artifact:

`patches/qwen36-27b-autoround-int4-b70/vllm-spec-bonus-argmax-fastpath-no-win-20260703.patch`

Default-off flag:

`VLLM_XPU_SPEC_DECODE_BONUS_ARGMAX_FASTPATH=1`

Safety guards:

- all-greedy only;
- no random sampling;
- no logprobs / logprob token ids;
- no penalties;
- no allowed-token masks;
- no bad words;
- no active thinking-budget forcing;
- no active non-argmax-invariant logits processors.

Fallback remains the normal bonus sampler for any richer sampling/logprob case.

## Results

Standalone strict fresh-response candidate:

```bash
LABEL=qwen27-int8lmhead-bonusargmax-mtp3-cg8-realistic128-chat-tokenids-qwensuite \
GPU_INDEX=1 PORT=19411 \
VLLM_XPU_LM_HEAD_INT8=1 \
VLLM_XPU_SPEC_DECODE_BONUS_ARGMAX_FASTPATH=1 \
scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

Artifact:

`data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-bonusargmax-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T160739Z.json`

- gate passed;
- `cached_tokens=0`;
- median tokens 1-100 after TTFT: `62.551370267657624 tok/s`;
- p10: `58.113300681272456`;
- mean: `63.30355893872339`;
- median TTFT: `608.9900495135225 ms`.

Same-window A/B:

Control, GPU2:

`data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-control-gpu2-samewindow-bonusargmax-realistic128-chat-tokenids-qwensuite-20260703T161011Z.json`

- gate passed;
- `cached_tokens=0`;
- median: `62.60860919531282 tok/s`;
- p10: `57.86541230571755`;
- mean: `62.951111064291105`.

Candidate, GPU3:

`data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-bonusargmax-gpu3-samewindow-realistic128-chat-tokenids-qwensuite-20260703T161011Z.json`

- gate passed;
- `cached_tokens=0`;
- median: `62.32029632557057 tok/s`;
- p10: `57.94497636015865`;
- mean: `62.846296673261655`.

## Decision

No promotion and no LocalMaxxing submission.

The patch is valid but does not beat the current runtime INT8 LM-head record
(`62.62792826965406 tok/s`) and loses the same-window A/B. This confirms that
bonus sampler plumbing is not the useful bottleneck.

## Follow-Up

Proceed to the real seam: exact compact/fused LM-head top-1 for greedy
verification before full logits are materialized. The verifier needs target
argmax IDs and target-owned bonus IDs; it does not need `[rows, vocab]` logits
for the strict greedy/no-logprobs suite.

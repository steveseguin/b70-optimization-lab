# 2026-07-03 Exact argmax verifier no-win

This experiment tested the first follow-up from
`2026-07-03-lmhead-verifier-bottleneck.md`: avoid passing full target logits
through the rejection sampler for exact greedy speculative decoding.

## Patch

Patch artifact:
`patches/qwen36-27b-autoround-int4-b70/vllm-exact-spec-argmax-only-no-win-20260703.patch`

Default-off flags:

- `VLLM_XPU_LOCAL_ARGMAX_DECODE=1`;
- `VLLM_XPU_LOCAL_ARGMAX_SPEC_ONLY=1`;
- `VLLM_XPU_SPEC_DECODE_ARGMAX_ONLY=1`.

The patch added an exact `greedy_sample_from_argmax` helper that reuses the
existing `rejection_greedy_sample_kernel`. It preserves normal greedy
speculative semantics:

- accepted draft prefix;
- target replacement on first mismatch;
- target-owned bonus token on full accept.

It is not the existing `VLLM_XPU_SPEC_DECODE_DRAFT_ONLY` path, which is invalid
for promoted use because it deliberately omits replacement/bonus tokens.

## Result

Command shape:

```bash
LABEL=intel-mtp3-cg8-promotesource-argmaxonly-realistic128-chat-tokenids-qwensuite \
GPU_INDEX=1 PORT=19411 \
VLLM_XPU_LOCAL_ARGMAX_DECODE=1 \
VLLM_XPU_LOCAL_ARGMAX_SPEC_ONLY=1 \
VLLM_XPU_SPEC_DECODE_ARGMAX_ONLY=1 \
VLLM_XPU_LOCAL_ARGMAX_DEBUG=1 \
VLLM_XPU_LOCAL_ARGMAX_DEBUG_LIMIT=64 \
scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

Result JSON:
`data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-cg8-promotesource-argmaxonly-realistic128-chat-tokenids-qwensuite-20260703T111331Z.json`

Strict fresh gate:

- `passed=true`;
- `cached_tokens=0` for all 12 prompts;
- median `52.543055702369855 tok/s`;
- p10 `47.52718519201445`;
- mean `53.74783673116317`;
- TTFT median `534.2791469302028 ms`.

Server debug confirmed the new path was active:

```text
XPU local argmax rank=0: enabled
XPU local argmax rank=0: using precomputed sampled_token_ids for exact spec argmax
```

## Decision

No-win. The current conservative promoted record is `53.522 tok/s`, and the
same-family support rows are `53.992` and `54.861 tok/s`. Exact argmax-only
target verification is correct but does not beat the current recipe.

Interpretation: on TP1, target `get_top_tokens` still pays the full LM-head
matmul; this patch only avoids some full-logits sampler plumbing and therefore
does not address the real `~4.4 ms` LM-head cost. Preserve the patch, but do
not keep it active or promote it.

Next bounded lane: proposer-side local argmax / `get_top_tokens` for the MTP
draft model, then deeper AutoRound/INC LM-head top-1 or candidate-vs-max kernel
work if config-level argmax also fails.

# 2026-07-03 Lorbus AutoRound variant no-win

This screen tested `Lorbus/Qwen3.6-27B-int4-AutoRound` against the current
Intel AutoRound lane. The Lorbus model card says the main difference from a
plain AutoRound export is that `mtp.fc` is dequantized back to BF16 so vLLM's
Qwen MTP loader can use the MTP head natively. That made it worth testing as a
same-family W4A16/INT4 model variant, not as a lower-quality quantization.

## Result

Command shape:

```bash
MODEL_DIR=/mnt/fast-ai/llm-cache/hf/hub/models--Lorbus--Qwen3.6-27B-int4-AutoRound/snapshots/c3aea2d531678621989e5e2db034e32b22536e79 \
LABEL=qwen27-lorbus-autoround-int8lmhead-mtp3-cg8-realistic128-chat-tokenids-qwensuite \
GPU_INDEX=0 PORT=19410 \
VLLM_XPU_LM_HEAD_INT8=1 \
scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

Result JSON:
`data/qwen36-27b-autoround-int4-b70-baselines/qwen27-lorbus-autoround-int8lmhead-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T163036Z.json`

Strict fresh gate:

- `realistic_final_gate.passed=true`;
- `cached_tokens=0` for all 12 prompts;
- each prompt run once as a cold response;
- median `61.979635455229726 tok/s`;
- p10 `58.21671660143884`;
- mean `63.037791294510015`;
- TTFT median `604.7343024984002 ms`.

## Decision

Valid no-win. The current Intel AutoRound + runtime INT8 LM-head record remains
`62.62792826965406 tok/s` median, with same-window support at
`62.276492398420544 tok/s`.

Lorbus is close and has a slightly better p10 than the record row, but median
throughput is below the current headline and within normal Qwen variance. Do
not submit or promote. Keep the local Lorbus snapshot as a future compatibility
reference because its `mtp.fc` layout may be useful if upstream vLLM changes
how it loads Qwen MTP modules.

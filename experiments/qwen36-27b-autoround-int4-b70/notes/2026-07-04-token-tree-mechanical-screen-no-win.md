# 2026-07-04 - Qwen27 token-tree mechanical screen no-win

## Summary

Existing vLLM `speculative_token_tree` support is mechanically usable with the
Qwen27 webhie/BF16-scale INT8-LM-head lane on XPU, but it does not beat the
current MTP3/cg8 record family.

The useful result is not a promoted throughput claim; this was a 24-prompt
calibration-suite screen with quality disabled. All completed rows still used
fresh prompts, `cached_tokens=0`, token-id timing, and no history/cache reuse,
so they are valid diagnostics.

## Runs

Current same-suite control:

- label: `qwen27-webhie-mtp3-control-calib-20260704T160805Z`
- config: standard MTP3/cg8 record recipe
- result: `63.87114397331328 tok/s` median tokens 1-100 after TTFT
- p10/mean: `57.92272477825735` / `64.00776528905877`
- TTFT median: `633.4349070675671 ms`
- status: smoke passed, strict fresh gate passed, `cached_tokens=0` on `24/24`
- compact summary:
  `../../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-mtp3-control-calib-20260704T160805Z-candidate-summary-20260704T160805Z.json`

Binary depth-2 tree:

- first attempt:
  `qwen27-webhie-tree-binary-depth2-calib-20260704T160212Z`
  failed before readiness because `num_speculative_tokens` was omitted from the
  explicit speculative config.
- corrected config:
  `{"method":"qwen3_next_mtp","num_speculative_tokens":6,"speculative_token_tree":"[(0,), (1,), (0, 0), (0, 1), (1, 0), (1, 1)]"}`
- result: `60.526139340583555 tok/s` median tokens 1-100 after TTFT
- p10/mean: `54.79767408882262` / `61.30693247268758`
- TTFT median: `1255.4371505975723 ms`
- status: smoke passed, strict fresh gate passed, `cached_tokens=0` on `24/24`
- compact summary:
  `../../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-tree-binary-depth2-calib-20260704T160237Z-candidate-summary-20260704T160237Z.json`

Root top-3 depth-1 tree:

- config:
  `{"method":"qwen3_next_mtp","num_speculative_tokens":3,"speculative_token_tree":"[(0,), (1,), (2,)]"}`
- result: `63.10680415393871 tok/s` median tokens 1-100 after TTFT
- p10/mean: `59.00945112007436` / `63.37923206124052`
- TTFT median: `630.6324229808524 ms`
- status: smoke passed, strict fresh gate passed, `cached_tokens=0` on `24/24`
- compact summary:
  `../../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-tree-root3-depth1-calib-20260704T160806Z-candidate-summary-20260704T160806Z.json`

Root top-2 depth-1 tree:

- config:
  `{"method":"qwen3_next_mtp","num_speculative_tokens":2,"speculative_token_tree":"[(0,), (1,)]"}`
- status: readiness/load stall. The server log stopped moving at
  `2026-07-04 12:08:46 -0400` during drafter checkpoint load, after printing
  `Loading safetensors checkpoint shards: 75% Completed | 6/8`.
- run directory:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-tree-root2-depth1-calib-20260704T160805Z`
- interpretation: do not spend more time on this exact root-only shape unless
  another change makes token-tree generation promising. Root top-3 already
  tested the same cheap root-alternative idea and lost to the MTP3 control.

## Interpretation

The source path explains the loss. In
`/home/steve/src/vllm/vllm/v1/spec_decode/llm_base_proposer.py`,
tree drafting enters `propose_tree()` and explicitly computes full draft logits
for the root and then full logits for the draft rows at each later tree level.
The binary depth-2 shape improves mean acceptance length in the server logs,
but buys that with extra full-vocab draft LM-head work and a six-node verifier
shape. The cheap root-only top-3 shape avoids the second tree-level draft
forward, but it still does not beat ordinary MTP3 on the same calibration
suite.

Result:

- Do not promote or submit any token-tree row.
- Do not reopen config-only `speculative_token_tree` sweeps on this exact
  Qwen27 recipe.
- Tree/branching remains conceptually relevant only if the branch design avoids
  the current dense full-logits cost, recomputes dependent draft rows legally,
  and improves target-verified accepted tokens per target step enough to offset
  wider verification.

## Next action

Keep MTP3/cg8 as the current record recipe. The next credible optimization
work is still a real source/kernel change:

1. reduce LM-head calls or rows before full-vocab GEMM;
2. find a oneDNN/XPU-integrated top-ID or candidate-score epilogue that avoids
   materializing dense logits and avoids a second reduction launch;
3. build a materially stronger target-matched drafter or branch/regenerate
   design, with held-out acceptance and quality validation before endpoint
   testing.

# 2026-07-06 - Qwen3.5 0.8B external draft-model probe: mechanically repaired, zero acceptance

## Summary

External `Qwen/Qwen3.5-0.8B` was tested as a `draft_model` proposer for the
current Qwen3.6 27B AutoRound/webhie INT4 lane. This was motivated by
llama.cpp/Hipfire-adjacent reports that Qwen3.5 0.8B can be a useful draft for
Qwen3.6 27B in some code-prompt setups.

Result: **closed no-win for this vLLM/XPU Qwen27 lane**. The compatibility
patch got the server to readiness and graph capture, but live spec metrics
showed **0 accepted draft tokens** across repeated intervals, with generation
only around `2.3-2.6 tok/s`. The strict 512-token suite was intentionally
interrupted because it would only measure a very slow rejected-draft path.

Do not submit, promote, or use this as a speed claim.

## Final attempted config

- Target:
  `/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e`
- Draft:
  `/mnt/fast-ai/llm-cache/hf/models--Qwen--Qwen3.5-0.8B/snapshots/2fc06364715b967f1860aea9cf38778875588b17`
- `QWEN36_27B_ENABLE_MTP=0`
- `QWEN36_27B_SPECULATIVE_CONFIG='{"method":"draft_model","model":"<draft>","num_speculative_tokens":8,"draft_tensor_parallel_size":1}'`
- `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'`
- `VLLM_XPU_SPEC_DECODE_TEXT_ONLY_MULTIMODAL_OK=1`
- `RUN_QUALITY=0`, diagnostic only

## Blockers fixed on the way

The first several attempts were useful compatibility archaeology:

1. `codex1`: vLLM rewrote explicit `{"method":"draft_model"}` into
   `method='mtp'` for Qwen3.5 because `SpeculativeConfig.hf_config_override`
   auto-detected Qwen3.5 MTP model types. This loaded
   `qwen3_5_mtp.py` and failed hidden-size weight loading.
2. `codex2`: preserving explicit `draft_model` moved forward, then hit the
   generic vLLM multimodal guard because the target is Qwen3.6 multimodal-class
   even for text-only requests.
3. `codex3`: text-only multimodal override moved forward, then hit the
   generic M-RoPE unsupported guard.
4. `codex4`: flat 1D text-position override moved forward, but the draft was
   still being wrapped as an MTP model during `ModelConfig(... hf_overrides=...)`,
   causing `missing a required argument: 'hidden_states'` in dummy run.
5. `codex5`: disabling `hf_config_override` for explicit external
   `draft_model` loaded Qwen3.5 as plain `Qwen3_5ForConditionalGeneration`,
   then hit `All drafting layers should belong to the same kv cache group`.
6. `codex6`: generic proposer mixed-KV metadata support moved forward, then hit
   mixed draft KV block sizes `[64, 2048]`.
7. `codex7`: per-KV-group block sizes moved forward. Server reached readiness,
   graph captured, smoke passed, but acceptance stayed at zero.

The compatibility patch is preserved here:

- `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-qwen35-08b-explicit-draftmodel-compat-zeroaccept-20260706.patch`
- SHA256:
  `db01dd4d5b1db49185fb57ede6322a93510c0c17dfc8d8d7b5ab48e3a039810c`

The patch artifact includes the relevant active source diff for:

- `vllm/config/speculative.py`
- `vllm/v1/spec_decode/llm_base_proposer.py`
- `vllm/v1/worker/gpu_model_runner.py`

It is an experiment artifact, not a promoted production patch.

## Follow-up correction: keep mixed draft-KV metadata opt-in

Later on 2026-07-06, the current ReplaySSM record recipe reproduced at only
`~60-61 tok/s` after this external-draft patch because the patch broadened
mixed draft-KV metadata construction from DFlash-only to any
`draft_kv_cache_gids`. Normal intrinsic Qwen MTP then carried
`_draft_common_attn_metadata_by_gid` and paid the slower per-group slot-mapping
path even though the record recipe does not need mixed external-draft KV
metadata.

The active source was repaired by guarding that behavior:

- DFlash still gets mixed draft-KV metadata by default;
- future external-draft experiments must opt in with
  `VLLM_XPU_SPEC_DECODE_MIXED_DRAFT_KV_METADATA=1`;
- normal intrinsic Qwen MTP returns to the record path.

Focused follow-up patch and note:

- `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-mixed-draft-kv-metadata-guard-20260706.patch`
- `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-06-mixed-draft-kv-metadata-guard-and-draft-int4-group-screen.md`

Do not reapply the broad mixed-KV metadata behavior from this patch to the
normal MTP record path.

## Evidence

Final run:

- run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-qwen35-08b-draftmodel-multikv-blocks-k8-cg8-20260706Tqwen35draft08b-k8-codex7`
- compact summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-qwen35-08b-draftmodel-multikv-blocks-k8-cg8-zeroaccept-summary-20260706Tqwen35draft08b-k8-codex7.json`
- smoke:
  `data/qwen36-27b-autoround-int4-b70-baselines/smoke-qwen27-qwen35-08b-draftmodel-multikv-blocks-k8-cg8-20260706Tqwen35draft08b-k8-codex7.json`
- result: smoke passed, `cached_tokens=0`, content was the expected JSON
  answer.
- graph capture: `Graph capturing finished in 3 secs, took 0.37 GiB`.
- readiness: server started and `/v1/models` returned `200 OK`.
- draft metadata: `Initialized draft model attention over KV groups [11, 12, 13, 14]`.

Live spec metrics before interrupt:

```text
Accepted: 0 tokens, Drafted: 176 tokens, Per-position acceptance rate:
0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000

Accepted: 0 tokens, Drafted: 200 tokens, ...
Accepted: 0 tokens, Drafted: 208 tokens, ...
Accepted: 0 tokens, Drafted: 200 tokens, ...
Accepted: 0 tokens, Drafted: 208 tokens, ...
```

Observed generation throughput while rejecting every draft was only
`~2.3-2.6 tok/s`, far below the `67.519 tok/s` current strict record.

## Interpretation

This pair is mechanically interesting but not a viable short-decode speed lane
as tested. If revisiting external draft models, first run a cheap acceptance
oracle or a very short endpoint probe and require nonzero acceptance before a
full strict run. The next promising external-draft attempt should use a draft
that is known to be target-aligned on fresh chat-style Qwen3.6 27B outputs,
not just code-prompt or repeated-prompt claims.

## Next action

Return to stronger-drafter or deeper target-forward work. The current best
valid result remains:

- `webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 target LM-head BF16 scales + runtime INT4 draft LM-head BF16 scales`
- strict fresh median `67.51904968102535 tok/s`
- LocalMaxxing `cmr8rg5d900glqr01g4fesy6i`

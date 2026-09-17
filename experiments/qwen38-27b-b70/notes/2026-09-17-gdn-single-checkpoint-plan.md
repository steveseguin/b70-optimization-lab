# Plan: single-checkpoint recurrent state for GDN speculative decoding (lossless long context on one card)

## Why

At MTP depth K, vLLM keeps `1 + K` copies of every GDN layer's recurrent state per request
(`MambaSpec.num_speculative_blocks = num_speculative_tokens`, `model_executor/layers/mamba/abstract.py`), because the
speculative decode kernel writes the state after each draft position so the accepted prefix's state can be selected
without recomputation. For Qwen3.8-27B that is 48 layers x 3.25 MiB per copy: 0.15 GiB with no draft, **0.9 GiB at
depth 5**. On one B70 that is the difference between 24K and 32K+ of context at depth 5 (attention KV is 64 KB per
token; 32K needs 2.0 GiB of it).

vLLM already solves this for Kimi-K3's KDA layers: **RecoverSSM** keeps one checkpoint per request
(`spec_state_slots = 1`), verifies the whole draft window off that checkpoint, and after acceptance runs a commit pass
that replays the accepted tokens from the checkpoint to produce the new state. Outputs are unchanged by construction:
the committed state is the same function of the same accepted tokens, computed once instead of stored K+1 times.

## Where the pieces are (vLLM 0.29 in the R310 image, `/opt/venv/lib/python3.12/site-packages/vllm`)

| Piece | KDA today | GDN today |
| --- | --- | --- |
| Spec slots per request | `models/kimi_k3/nvidia/kda_metadata.py:320` `spec_state_slots = 1 if use_recoverssm else num_spec + 1` | `v1/attention/backends/gdn_attn.py:127` `spec_state_indices_tensor (bs, num_spec + 1)` |
| KV spec | `mamba/abstract.py:81` `num_speculative_blocks = 0 if use_kda_recoverssm else num_speculative_tokens` | same line, always `num_speculative_tokens` |
| Verify kernel | `models/kimi_k3/nvidia/ops/recoverssm.py` (1,067 lines: verify from one checkpoint, write nothing per slot) | `vllm-xpu-kernels` `gated_delta_rule_spec` writes one state per draft position (the lab's r310 build) |
| Commit after acceptance | `RecoverSSMMetadata.commit_recoverssm_state(num_accepted)` (`v1/attention/backends/recoverssm_metadata.py`) called from `v1/worker/gpu/model_states/recoverssm.py::RecoverSSMState.commit_step` | none |
| Runner integration | the `v1/worker/gpu/` runner (the V2 model runner) records and commits per step | this lane serves with `VLLM_USE_V2_MODEL_RUNNER=0` (V1 runner) |
| Switch | `config/cache.py:207` `use_kda_recoverssm` | none |

## Work items (in order)

1. **Commit kernel for GDN (XPU).** A chunked delta-rule pass over `num_accepted` tokens (1 to K+1) per request starting
   from the checkpoint state, writing the new checkpoint. The lab's own non-spec GDN path (`gated_delta_rule_non_spec`
   with `has_initial_state`) already computes exactly this for prefill chunks; the commit is that kernel on a tiny
   chunk. The R310 fences apply.
2. **Verify path without per-slot writes.** Either keep the current spec kernel and simply not allocate the K extra
   slots (it must then write only the checkpoint slot, or a scratch buffer), or reuse the KDA verify structure. The
   XPU kernel's `spec_state_indices` handling is the place.
3. **Metadata and spec.** A `use_gdn_recoverssm` cache flag mirrored on `MambaSpec.num_speculative_blocks` and
   `GDNAttentionMetadataBuilder` (`spec_state_slots = 1`), plus a `RecoverSSMMetadata` implementation for GDN.
4. **Runner.** Either port `RecoverSSMState.record_step / commit_step` into the V1 runner path this lane uses, or move
   the lane to the V2 runner (that is its own qualification: the V2 runner was measured slower on this lane in
   September and is off by contract).
5. **Gates.** Same-image no-MTP reference, strict 12/12, the 64-prompt sequential oracle plus queued passes, the
   2K-16K screen, the chat quality suite, the logprob replay, on one and two cards. Then the memory result: expected
   attention-only budget at depth 5 on one card is 2.9 + 0.75 GiB, enough for 32K with margin at 0.975.

## Cost and risk

Two to four days of kernel and runner work, all on the research image, gated before any package change. The main
risk is the runner split (V1 in production, RecoverSSM plumbing in V2). The payoff is lossless 32K+ on one card at
full depth and a smaller KV footprint on two cards as well.

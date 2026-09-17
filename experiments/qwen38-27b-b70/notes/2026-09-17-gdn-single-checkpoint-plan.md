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

## What the XPU kernel already has (source: `/mnt/fast-ai/build/kernels-r310-gdn-barriers-20260915/vllm-xpu-kernels/csrc/xpu/gdn_attn/`)

`gdn_attn_interface.cpp` exposes the speculative path with `spec_state_indices_tensor [num_spec_decodes, K+1]` and a
`num_accepted_tokens [num_spec_decodes]` argument: the step already knows how many draft tokens the previous step
accepted and selects the base slot from it. The non-speculative path takes `has_initial_state` and
`non_spec_state_indices_tensor`, i.e. a chunked pass from a given state into a given slot, which is the commit pass.

Concrete design for GDN: (1) verify computes all K+1 outputs from the checkpoint slot alone (the same recurrence the
spec kernel runs today, minus the per-slot state writes) and stashes that step's projected q, k, v, gate and beta for
the K+1 positions per layer (a few MiB in total); (2) after acceptance, one launch per layer replays `num_accepted`
positions from the checkpoint into the checkpoint slot using the non-spec path with `has_initial_state`; (3) the
MambaSpec then needs one slot per request. The recompute costs about what the spec kernels cost today (1.3 ms per
step on one card) and frees 0.75 GiB per request at depth 5.

## Cost and risk

Two to four days of kernel and runner work, all on the research image, gated before any package change. The main
risk is the runner split (V1 in production, RecoverSSM plumbing in V2). The payoff is lossless 32K+ on one card at
full depth and a smaller KV footprint on two cards as well.

## Implementation (r311, 2026-09-17, untested until the ckpt-1 campaign)

The plan above assumed a separate commit launch. The implementation folds the commit into the next step instead, so
no launch is added and the drafter (a full-attention layer, no recurrent state) is untouched:

- **Kernel** ([patch r311](../patches/vllm-xpu-kernels-gdn-single-checkpoint-r311-20260917.patch), built by
  [`build-kernels-0.1.14.1-r311-gdn-checkpoint.sh`](../docker/rebase-v0290/build-kernels-0.1.14.1-r311-gdn-checkpoint.sh)
  into the R311 image, [`Dockerfile.r311-gdn-checkpoint`](../docker/rebase-v0290/Dockerfile.r311-gdn-checkpoint)).
  `gated_delta_rule_spec_kernel` gets a second protocol selected by a non-null `stash` pointer: every column of the
  slot table is the request's one block; the kernel loads that block, replays the first `num_accepted_tokens` rows of
  the previous window's stashed `{q, k, v, b, a}` (the values exactly as the kernel loaded them then), writes the
  block once (the commit), then runs the new window from registers without writing any state, and stashes the new
  window's rows. Per-token arithmetic is one shared `step()`; the per-slot protocol and the no-MTP path are unchanged.
  `stash_meta[block] = {parity, len}` selects the buffer to replay from and the new rows go to the other buffer, so no
  work-group reads what another writes. A commit mode (1-D slot table, zero window tokens, `commit_mask`) replays for
  requests leaving the speculative path. New op `gdn_attention_ckpt` = `gdn_attention` + `stash, stash_meta,
  stash_rows, commit_num_accepted?, commit_mask?`; the old ops are untouched.
- **Overlay** [`b70-gdn-checkpoint`](../overlays/b70-gdn-checkpoint/b70_gdn_checkpoint.py) (`B70_GDN_CHECKPOINT=1`,
  active only with a speculative config): the Qwen3-Next Mamba spec gets `num_speculative_blocks = 0` and a third
  in-page state, the stash `(2, K+1, 2*nk*hk + nv*hv + 2*nv)` in the model dtype (0.24 MiB per block per layer at
  depth 5, against the 5 x 3.25 MiB it replaces); the GDN layer binds it and `forward_xpu` calls a registered custom
  op `vllm.b70_gdn_attention_core_ckpt` that mirrors the image's split-mixed / spec-group dispatch with the new op;
  the metadata builder widens column 0 of the block table to the active window width, attaches the non-spec rows'
  accepted counts and `has_initial_state` as the commit inputs, and records the meta updates (spec rows: flip parity,
  len = width; non-spec rows: len = 0). Those updates are applied at the first GDN layer of the next forward, i.e.
  after every kernel of the step that recorded them and before any kernel that reads them.
- **Bookkeeping cases:** first speculative step after a prefill (len 0, no replay); a freed block reused by a new
  request (stale meta, but the first chunk has no initial state, so no commit, and its build zeroes len); chunked
  prefill continuation (len 0); a decode without drafts after a speculative step (commit with that step's accepted
  count; the stock path reads column 0 there, i.e. the state after the window's first token only).
- **Gates:** [`run-20260917-fp8-ckpt1-campaign.py`](../scripts/run-20260917-fp8-ckpt1-campaign.py): one card at
  24,576 (strict twice, ladder, 2K/8K/16K, chat quality, logprob replay vs the R310 no-MTP references), then 32,768 at
  0.975 with the 30,720 probe, then the two-card service back.

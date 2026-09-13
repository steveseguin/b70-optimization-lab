#!/usr/bin/env python3
"""R307 (2026-09-13): GDN state hand-off for one-token steps after a speculative step.

Defect (found with experiments/qwen35-4b-b70/probes/max-len-boundary-probe.py on R304, Qwen3.5-4B, depth 3,
max-model-len 256, prompt length 14): the final token of a request that generates exactly to max_model_len differs
from the greedy no-speculation output; the same request at max-model-len 512 is byte-exact. Token-level dump: only
index 241 of 242 differs.

Cause: at the boundary the scheduler clamps the last step to one token (max_model_len - computed - 1), so a request
that ran speculative steps takes one plain decode step. The XPU GDN spec kernels leave the live state at slot/row
(num_accepted - 1) of the request's block-table row / conv line (initial state read from that position on the
next spec step); the non-spec kernels read SSM slot 0 and conv rows [0, width - 1). Both are only right when the
previous step accepted exactly one token. Upstream main carries the same transition (vllm/v1/attention/backends/
gdn_attn.py collapses zero-draft batches to the non-spec path), so this is not XPU-specific in principle.

Fix: (1) the model runner flags a one-token decode step of a running request whose previous step accepted more
than one token by giving it draft count 0 instead of -1; (2) the GDN metadata builder turns those rows into
plain decodes and carries their block-table rows and accepted counts; (3) the GDN layer copies SSM slot
(accepted - 1) to slot 0 and shifts the conv window rows [accepted - 1, accepted - 1 + width - 1) down to row 0
before its kernels run. No kernel path changes; nothing happens on steps where every request has drafts.
Applies on top of R304 (needs the PR #53542 active-width hunks). Usage: r307-gdn-state-handoff.py [site-packages]"""
import pathlib, sys

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/venv/lib/python3.12/site-packages")
MARK = "R307 GDN state hand-off"


def edit(path, old, new, count=1):
    text = path.read_text()
    assert text.count(old) == count, f"{path}: anchor count {text.count(old)} != {count}\n{old}"
    path.write_text(text.replace(old, new))


# ---------------------------------------------------------------- 1. model runner
runner = root / "vllm/v1/worker/gpu_model_runner.py"
text = runner.read_text()
assert MARK not in text, "runner already patched"
assert "num_scheduled_tokens: np.ndarray," in text
edit(runner,
'''            spec_decode_metadata = self._calc_spec_decode_metadata(
                num_draft_tokens, cu_num_tokens
            )
''',
'''            # R307 GDN state hand-off (2026-09-13): flag one-token decode steps
            # that follow a speculative step which accepted more than one token.
            # Their live GDN state sits at slot/row (accepted - 1); the GDN
            # backend hands it back to slot/row 0 before the non-spec kernels
            # run (GDNAttentionMetadataBuilder.build). Happens at the
            # max_model_len boundary and whenever the drafter is skipped.
            if self._gdn_state_handoff_enabled():
                one_token_decode = (
                    (num_decode_draft_tokens < 0)
                    & (num_scheduled_tokens[:num_reqs] == 1)
                    & (
                        self.input_batch.num_computed_tokens_cpu[:num_reqs]
                        >= self.input_batch.num_prompt_tokens[:num_reqs]
                    )
                )
                if one_token_decode.any():
                    accepted = self._gdn_prev_step_accepted_counts(num_reqs)
                    num_decode_draft_tokens[one_token_decode & (accepted > 1)] = 0
            spec_decode_metadata = self._calc_spec_decode_metadata(
                num_draft_tokens, cu_num_tokens
            )
''')
edit(runner,
'''    def _calc_spec_decode_metadata(
''',
'''    def _gdn_state_handoff_enabled(self) -> bool:
        """R307 GDN state hand-off: speculative decoding on a model with GDN layers."""
        cached = self.__dict__.get("_r307_gdn_handoff")
        if cached is None:
            groups = list(self._attn_group_iterator())
            if not groups:
                return False
            from vllm.v1.attention.backends.gdn_attn import GDNAttentionMetadataBuilder

            cached = self.num_spec_tokens > 0 and any(
                isinstance(group.get_metadata_builder(), GDNAttentionMetadataBuilder)
                for group in groups
            )
            self.__dict__["_r307_gdn_handoff"] = cached
        return cached

    def _gdn_prev_step_accepted_counts(self, num_reqs: int) -> np.ndarray:
        """R307: per-request (accepted drafts + 1) of the previous step, on the CPU.

        Rows without a previous step report 1. Under async spec decode the CPU
        copy of num_accepted_tokens is optimistic, so read the previous step's
        valid sampled-token counts instead (one event sync; only reached on
        steps that contain a one-token decode of a speculative request).
        """
        counts = self.num_accepted_tokens.np[:num_reqs].copy()
        if self.use_async_spec_decode:
            valid = self._get_valid_sampled_token_count()
            prev = self.input_batch.prev_req_id_to_index
            if valid and prev:
                for idx, req_id in enumerate(self.input_batch.req_ids[:num_reqs]):
                    prev_idx = prev.get(req_id)
                    if prev_idx is not None and prev_idx < len(valid):
                        counts[idx] = valid[prev_idx]
        return counts

    def _calc_spec_decode_metadata(
''')

# ---------------------------------------------------------------- 2. GDN metadata builder
gdn = root / "vllm/v1/attention/backends/gdn_attn.py"
text = gdn.read_text()
assert MARK not in text, "gdn_attn already patched"
assert "active_spec_width = 0" in text, "needs the R304 (PR #53542) hunks"
edit(gdn,
'''    num_accepted_tokens: torch.Tensor | None = None  # shape: [batch,]
''',
'''    num_accepted_tokens: torch.Tensor | None = None  # shape: [batch,]

    # R307 GDN state hand-off: rows taking a one-token step right after a
    # speculative step that accepted more than one token.
    handoff_state_indices: torch.Tensor | None = None  # shape: [num_handoff, num_spec + 1]
    handoff_num_accepted: torch.Tensor | None = None  # shape: [num_handoff,]
''')
edit(gdn,
'''        spec_sequence_masks_cpu: torch.Tensor | None = None
        active_spec_width = 0
''',
'''        spec_sequence_masks_cpu: torch.Tensor | None = None
        active_spec_width = 0
        # R307 GDN state hand-off: the runner gives draft count 0 (not -1) to a
        # one-token decode step that follows a speculative step which accepted
        # more than one token. Its live state sits at slot/row (accepted - 1);
        # the model layer copies it to slot/row 0 before the kernels run, and
        # here the row is classified as a plain decode.
        handoff_state_indices: torch.Tensor | None = None
        handoff_num_accepted: torch.Tensor | None = None
        if (
            self.use_spec_decode
            and num_decode_draft_tokens_cpu is not None
            and num_accepted_tokens is not None
        ):
            handoff_mask_cpu = num_decode_draft_tokens_cpu == 0
            if bool(handoff_mask_cpu.any()):
                handoff_rows = async_tensor_h2d(
                    handoff_mask_cpu.nonzero().squeeze(1),
                    device=query_start_loc.device,
                )
                handoff_state_indices = block_table_tensor[
                    handoff_rows, : self.num_spec + 1
                ]
                handoff_num_accepted = num_accepted_tokens[handoff_rows]
                num_decode_draft_tokens_cpu = num_decode_draft_tokens_cpu.clone()
                num_decode_draft_tokens_cpu[handoff_mask_cpu] = -1
''')
edit(gdn,
'''            non_spec_token_indx=non_spec_token_indx,
            num_accepted_tokens=num_accepted_tokens,
            nums_dict=nums_dict,
''',
'''            non_spec_token_indx=non_spec_token_indx,
            num_accepted_tokens=num_accepted_tokens,
            handoff_state_indices=handoff_state_indices,
            handoff_num_accepted=handoff_num_accepted,
            nums_dict=nums_dict,
''')
edit(gdn,
'''        num_decode_draft_tokens_cpu = (num_accepted_tokens - 1).cpu()
''',
'''        num_decode_draft_tokens_cpu = (num_accepted_tokens - 1).cpu()
        # R307: a zero here means "one-token capture row", never a hand-off.
        num_decode_draft_tokens_cpu[num_decode_draft_tokens_cpu == 0] = -1
''')

# ---------------------------------------------------------------- 3. GDN layer
layer = root / "vllm/model_executor/layers/mamba/gdn/qwen_gdn_linear_attn.py"
text = layer.read_text()
assert MARK not in text, "layer already patched"
assert "is_conv_state_dim_first()" in text
edit(layer,
'''        assert isinstance(attn_metadata, GDNAttentionMetadata)

        if (
            self.enable_packed_recurrent_decode
''',
'''        assert isinstance(attn_metadata, GDNAttentionMetadata)

        if attn_metadata.handoff_state_indices is not None:
            self._r307_state_handoff(attn_metadata)

        if (
            self.enable_packed_recurrent_decode
''')
edit(layer,
'''    def _forward_core(
''',
'''    def _r307_state_handoff(self, attn_metadata: GDNAttentionMetadata) -> None:
        """R307 GDN state hand-off (2026-09-13).

        Requests taking a one-token step right after a speculative step that
        accepted more than one token: the spec kernels left the live SSM state
        at slot (accepted - 1) of the block-table row and the live conv window
        at rows [accepted - 1, accepted - 1 + width - 1) of the conv line, while
        the non-spec kernels read slot 0 and rows [0, width - 1). Copy the
        accepted SSM state to slot 0 and shift the conv window down to row 0
        before this layer's kernels run. Device-side only; no host sync.
        """
        rows = attn_metadata.handoff_state_indices
        accepted = attn_metadata.handoff_num_accepted
        assert rows is not None and accepted is not None
        col = (accepted.to(torch.int64) - 1).clamp_(min=0)
        src = rows.gather(1, col.unsqueeze(1)).squeeze(1).to(torch.int64)
        dst = rows[:, 0].to(torch.int64)
        conv_state = (
            self.kv_cache[0]
            if is_conv_state_dim_first()
            else self.kv_cache[0].transpose(-1, -2)
        )
        ssm_state = self.kv_cache[1]
        ssm_state[dst] = ssm_state[src]
        window = self.conv1d.weight.size(2) - 1
        lines = conv_state[dst]  # [num_handoff, dim, state_len] (a copy)
        idx = (col.unsqueeze(1) + torch.arange(window, device=col.device)).unsqueeze(1)
        idx = idx.expand(-1, lines.size(1), -1)
        conv_state[dst, :, :window] = lines.gather(2, idx)

    def _forward_core(
''')
for p in (runner, gdn, layer):
    compile(p.read_text(), str(p), "exec")
print("R307 patched:", runner, gdn, layer)

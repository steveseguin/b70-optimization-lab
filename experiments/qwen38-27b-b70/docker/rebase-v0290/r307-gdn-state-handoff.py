#!/usr/bin/env python3
"""R307 (2026-09-13): GDN state hand-off at speculative width changes (max_model_len boundary), and one XPU kernel
call per speculative width.

Defect 1 (max-len-boundary-probe.py on R304, Qwen3.5-4B, depth 3, max-model-len 256, prompt length 14): the final
token of a request that generates exactly to max_model_len differs from the greedy no-speculation output; the same
request at max-model-len 512 is byte-exact; only index 241 of 242 differs. The debug image shows the request's last
step is a partial speculative group of width 3 (the scheduler clamps to max_model_len - computed - 1) right after
a fully accepted step (num_accepted = 4). PR #53542 slices the state-index tensor to the active width, but the XPU
spec kernels read each row's initial SSM state from column (num_accepted - 1) of that tensor, so a width below the
previous acceptance indexes past the row: a stale slot on R304's single staging buffer (silent wrong state, the
flipped token) or a null/garbage slot on R306's per-width buffers (UR_RESULT_ERROR_DEVICE_LOST). The CUDA/Triton
kernel indexes the same way, so the PR has the same latent defect upstream.

Defect 2 (same probe with --concurrency 4): several requests reaching the boundary at different steps put
different widths in one batch, and the XPU kernel requires one width per call ("Expected spec_token ==
num_spec_decodes * (num_speculative_tokens + 1)"): the engine dies.

Defect 3 (analysis; the one-token case): when the last step is a single token, the request drops to the non-spec
kernels, which read SSM slot 0 and conv rows [0, width - 1) while the live state sits at slot/row (accepted - 1).

Fix: (a) the GDN metadata builder hands the live state of every spec row that is narrower than num_spec + 1 back
to slot/row 0 (block-table row + accepted count carried in the metadata; num_accepted reset to 1), and records the
per-row widths when they are mixed; (b) the model runner flags a one-token decode step of a running request whose
previous step accepted more than one token (draft count 0 instead of -1; under async spec decode it reads the
previous step's valid-sampled counts), the builder turns that row into a plain decode with the same hand-off;
(c) the XPU fused op performs the hand-off (SSM slot copy, conv window shift) before its kernels and, on a
mixed-width step, runs one pure kernel call per width. No kernel changes; nothing happens on steps where every
request carries the full draft width. Applies on top of R304 + the R306 contiguous staging fix.
Usage: r307-gdn-state-handoff.py [site-packages]"""
import pathlib, sys

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/venv/lib/python3.12/site-packages")
MARK = "R307 GDN state hand-off"


def edit(path, old, new, count=1):
    text = path.read_text()
    assert text.count(old) == count, f"{path}: anchor count {text.count(old)} != {count}\n{old}"
    path.write_text(text.replace(old, new))


# ---------------------------------------------------------------- 1. model runner: flag one-token steps
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

    # R307 GDN state hand-off: rows whose live state must move to slot/row 0
    # before the kernels run (one-token steps after an accepted draft, and
    # spec rows narrower than num_spec + 1). Per-row spec widths (spec order,
    # CPU) are set only when a batch mixes widths.
    handoff_state_indices: torch.Tensor | None = None  # shape: [num_handoff, num_spec + 1]
    handoff_num_accepted: torch.Tensor | None = None  # shape: [num_handoff,]
    spec_query_lens_cpu: torch.Tensor | None = None  # shape: [num_spec_decodes,]
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
        # the XPU op copies it to slot/row 0 before the kernels run, and here
        # the row is classified as a plain decode.
        handoff_state_indices: torch.Tensor | None = None
        handoff_num_accepted: torch.Tensor | None = None
        spec_query_lens_cpu: torch.Tensor | None = None
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
'''            assert 1 < active_spec_width <= self.num_spec + 1
''',
'''            assert 1 < active_spec_width <= self.num_spec + 1
            # R307 GDN state hand-off, partial width: the spec kernels read
            # each row's initial state from column (num_accepted - 1) of the
            # width-sliced indices, and the previous step's acceptance can put
            # that column past a row narrower than num_spec + 1 (a partial
            # final group at max_model_len after a fully accepted step). Hand
            # every such row's live state back to slot/row 0 in the XPU op and
            # read it from there (num_accepted := 1). Record the per-row widths
            # when the batch mixes them: the XPU kernel takes one width per
            # call, so the op runs one call per width.
            spec_query_lens_cpu = query_lens_cpu[spec_sequence_masks_cpu]
            partial_mask_cpu = spec_sequence_masks_cpu & (
                query_lens_cpu < self.num_spec + 1
            )
            if bool(partial_mask_cpu.any()):
                assert num_accepted_tokens is not None
                partial_rows = async_tensor_h2d(
                    partial_mask_cpu.nonzero().squeeze(1),
                    device=query_start_loc.device,
                )
                partial_state_indices = block_table_tensor[
                    partial_rows, : self.num_spec + 1
                ]
                partial_num_accepted = num_accepted_tokens[partial_rows]
                num_accepted_tokens = num_accepted_tokens.clone()
                num_accepted_tokens[partial_rows] = 1
                if handoff_state_indices is None:
                    handoff_state_indices = partial_state_indices
                    handoff_num_accepted = partial_num_accepted
                else:
                    handoff_state_indices = torch.cat(
                        [handoff_state_indices, partial_state_indices]
                    )
                    handoff_num_accepted = torch.cat(
                        [handoff_num_accepted, partial_num_accepted]
                    )
            if not bool((spec_query_lens_cpu == active_spec_width).all()):
                spec_query_lens_cpu = spec_query_lens_cpu.clone()
            else:
                spec_query_lens_cpu = None
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
            spec_query_lens_cpu=spec_query_lens_cpu,
            nums_dict=nums_dict,
''')
edit(gdn,
'''        num_decode_draft_tokens_cpu = (num_accepted_tokens - 1).cpu()
''',
'''        num_decode_draft_tokens_cpu = (num_accepted_tokens - 1).cpu()
        # R307: a zero here means "one-token capture row", never a hand-off.
        num_decode_draft_tokens_cpu[num_decode_draft_tokens_cpu == 0] = -1
''')

# ---------------------------------------------------------------- 3. XPU fused op
ops = root / "vllm/_xpu_ops.py"
text = ops.read_text()
assert MARK not in text, "_xpu_ops already patched"
edit(ops,
'''def _gdn_attention_core_xpu_impl(
''',
'''def _r307_gdn_state_handoff(layer, conv_state, ssm_state, attn_metadata) -> None:
    """R307 GDN state hand-off (2026-09-13).

    Rows whose live state the spec kernels left at SSM slot (accepted - 1) of
    the block-table row and conv rows [accepted - 1, accepted - 1 + width - 1)
    of the conv line, but which the next kernel call reads from slot 0 / rows
    [0, width - 1): copy the accepted SSM state to slot 0 and shift the conv
    window down to row 0. Device-side only; a no-op copy for accepted == 1.
    conv_state is (lines, state_len, dim) on XPU (SD layout); (lines, dim,
    state_len) is handled too.
    """
    rows = attn_metadata.handoff_state_indices
    accepted = attn_metadata.handoff_num_accepted
    assert rows is not None and accepted is not None
    col = (accepted.to(torch.int64) - 1).clamp_(min=0)
    src = rows.gather(1, col.unsqueeze(1)).squeeze(1).to(torch.int64)
    dst = rows[:, 0].to(torch.int64)
    ssm_state[dst] = ssm_state[src]
    dim, width = layer.conv1d.weight.size(0), layer.conv1d.weight.size(2)
    window = width - 1
    lines = conv_state[dst]
    offsets = col.unsqueeze(1) + torch.arange(window, device=col.device)
    if conv_state.size(-1) == dim:
        idx = offsets.unsqueeze(2).expand(-1, -1, lines.size(2))
        conv_state[dst, :window] = lines.gather(1, idx)
    else:
        idx = offsets.unsqueeze(1).expand(-1, lines.size(1), -1)
        conv_state[dst, :, :window] = lines.gather(2, idx)


def _gdn_attention_core_xpu_impl(
''')
edit(ops,
'''    num_actual_tokens = attn_metadata.num_actual_tokens
    num_accepted_tokens = attn_metadata.num_accepted_tokens

    num_prefills = attn_metadata.num_prefills
''',
'''    num_actual_tokens = attn_metadata.num_actual_tokens
    num_accepted_tokens = attn_metadata.num_accepted_tokens

    # R307 GDN state hand-off: move the live state of the flagged rows to
    # slot/row 0 before any kernel of this layer runs.
    if getattr(attn_metadata, "handoff_state_indices", None) is not None:
        _r307_gdn_state_handoff(self, conv_state, ssm_state, attn_metadata)
    _mixed_widths = getattr(attn_metadata, "spec_query_lens_cpu", None) is not None

    num_prefills = attn_metadata.num_prefills
''')
edit(ops,
'''    if _group_spec or (os.environ.get("VLLM_XPU_GDN_SPLIT_MIXED", "0") == "1" and (
''',
'''    if _group_spec or _mixed_widths or (os.environ.get("VLLM_XPU_GDN_SPLIT_MIXED", "0") == "1" and (
''')
edit(ops,
'''        if spec_token_indx is not None and spec_token_indx.numel() > 0:
            st = spec_token_indx.long()
            n_sp = st.numel()
''',
'''        if _mixed_widths and spec_token_indx is not None and spec_token_indx.numel() > 0:
            # R307: the XPU spec kernel takes one width per call. Run one pure
            # call per width (rows gathered, outputs scattered back), each with
            # the width-sliced state indices. Only on partial-group steps.
            logger.warning_once("R307 GDN mixed-width spec step split by width")
            st = spec_token_indx.long()
            lens_cpu = attn_metadata.spec_query_lens_cpu.tolist()
            starts = [0]
            for length in lens_cpu:
                starts.append(starts[-1] + int(length))
            for w in sorted(set(int(x) for x in lens_cpu)):
                sel = [s for s, length in enumerate(lens_cpu) if int(length) == w]
                tok_local = torch.cat(
                    [torch.arange(starts[s], starts[s + 1], device=dev) for s in sel]
                )
                rows = st[tok_local]
                n_g = len(sel) * w
                sel_t = torch.tensor(sel, dtype=torch.int64, device=dev)
                out_s = torch.zeros((n_g,) + tuple(core_attn_out.shape[1:]), dtype=core_attn_out.dtype, device=dev)
                z_s = torch.empty_like(out_s)
                qs_g = torch.arange(0, n_g + 1, w, dtype=torch.int32, device=dev)
                acc_g = num_accepted_tokens[sel_t].contiguous() if num_accepted_tokens is not None else None
                _kernel(out_s, z_s, projected_states_qkvz[rows].contiguous(),
                        projected_states_ba[rows].contiguous(), 0, 0, len(sel), None,
                        None, torch.empty(0, dtype=torch.int32, device=dev), None,
                        qs_g, torch.arange(n_g, dtype=torch.int32, device=dev),
                        spec_state_indices_tensor[sel_t, :w].contiguous(), acc_g, n_g)
                core_attn_out[rows] = out_s
                z[rows] = z_s
        elif spec_token_indx is not None and spec_token_indx.numel() > 0:
            st = spec_token_indx.long()
            n_sp = st.numel()
''')
for p in (runner, gdn, ops):
    compile(p.read_text(), str(p), "exec")
print("R307 patched:", runner, gdn, ops)

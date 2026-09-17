"""Single-checkpoint GDN recurrent state for speculative decoding (research overlay, r311). B70_GDN_CHECKPOINT=1.

Stock vLLM gives every request 1 + K Mamba state blocks (K = num_speculative_tokens) so the speculative delta-rule
kernel can write the state after each window token and the next step can start from the accepted prefix. On
Qwen3.8-27B that is 48 layers x 3.25 MiB x K extra per request (0.78 GiB at depth 5). This overlay keeps one block
per request and, with the r311 kernel (`_xpu_C.gdn_attention_ckpt`), stashes the window's {q, k, v, b, a} inside the
page instead; the next step replays the accepted prefix from the stash onto the checkpoint (the same operations the
per-slot kernel performed when it wrote the slot the stock path would have loaded), commits it, and continues.
Requests leaving the speculative path (a decode without drafts, a continued prefill) get the replay as a commit pass.

What changes (only when a speculative config is present):
  * the Qwen3-Next Mamba spec: `num_speculative_blocks = 0`, a third state (the stash) and its dtype,
  * the GDN layer: a stash view bound next to the conv and SSM states, `forward_xpu` calling the checkpoint op,
  * the GDN metadata builder: the (n, width) slot table becomes n copies of column 0, the non-spec rows get their
    accepted counts and commit mask, and the per-block {parity, len} table is updated once per step
    (after the previous step's kernels, before this step's).
Every gate compares the result with the same-image no-MTP reference; nothing here changes the no-MTP path.
"""
import os


def register():
    if os.environ.get('B70_GDN_CHECKPOINT', '').strip() != '1':
        return
    import dataclasses
    import torch
    from vllm.logger import init_logger
    from vllm.model_executor.layers.mamba.gdn import qwen_gdn_linear_attn as layer_mod
    from vllm.model_executor.models import qwen3_next as model_mod
    from vllm.v1.attention.backends import gdn_attn as builder_mod
    from vllm import _xpu_ops
    from vllm.utils.torch_utils import direct_register_custom_op
    from vllm.compilation.breakable_cudagraph import eager_break_during_capture

    logger = init_logger('b70_gdn_checkpoint')
    if not hasattr(torch.ops._xpu_C, 'gdn_attention_ckpt'):
        raise RuntimeError('b70_gdn_checkpoint: the kernel library has no gdn_attention_ckpt (needs the r311 build)')
    Layer = layer_mod.QwenGatedDeltaNetAttention
    Model = model_mod.Qwen3NextForCausalLM
    Builder = builder_mod.GDNAttentionMetadataBuilder
    if getattr(Layer, '_b70_gdn_checkpoint', False):
        return
    state = {'meta': None, 'pending_current': [], 'pending_previous': [], 'last_ctx': None, 'stash_rows': 0}

    # ---------------- state shapes: one block per request, plus the stash ----------------
    def stash_shape(tp, nk, nv, hk, hv, num_spec):
        row = 2 * (nk // tp) * hk + (nv // tp) * hv + 2 * (nv // tp)
        return (2, num_spec + 1, row)

    def num_spec_of(vllm_config):
        sc = vllm_config.speculative_config
        return int(sc.num_speculative_tokens) if sc and sc.num_speculative_tokens else 0

    orig_model_shape = Model.get_mamba_state_shape_from_config.__func__
    orig_model_dtype = Model.get_mamba_state_dtype_from_config.__func__
    orig_model_copy = Model.get_mamba_state_copy_func.__func__

    def model_shape(cls, vllm_config):
        shapes = tuple(orig_model_shape(cls, vllm_config))
        k = num_spec_of(vllm_config)
        if k == 0:
            return shapes
        hf = vllm_config.model_config.hf_text_config
        tp = vllm_config.parallel_config.tensor_parallel_size
        return shapes + (stash_shape(tp, hf.linear_num_key_heads, hf.linear_num_value_heads, hf.linear_key_head_dim,
                                     hf.linear_value_head_dim, k),)

    def model_dtype(cls, vllm_config):
        dtypes = tuple(orig_model_dtype(cls, vllm_config))
        if num_spec_of(vllm_config) == 0:
            return dtypes
        return dtypes + (vllm_config.model_config.dtype,)

    def model_copy(cls):
        from vllm.model_executor.layers.mamba.mamba_utils import get_temporal_copy_spec
        return tuple(orig_model_copy(cls)) + (get_temporal_copy_spec,)

    Model.get_mamba_state_shape_from_config = classmethod(model_shape)
    Model.get_mamba_state_dtype_from_config = classmethod(model_dtype)
    Model.get_mamba_state_copy_func = classmethod(model_copy)

    def layer_stash_shape(self):
        return stash_shape(self.tp_size, self.num_k_heads, self.num_v_heads, self.head_k_dim, self.head_v_dim, self.num_spec)

    orig_spec = Layer.get_kv_cache_spec

    def get_kv_cache_spec(self, vllm_config):
        spec = orig_spec(self, vllm_config)
        if spec is None or num_spec_of(vllm_config) == 0:
            return spec
        spec = dataclasses.replace(spec, shapes=tuple(spec.shapes) + (layer_stash_shape(self),),
                                   dtypes=tuple(spec.dtypes) + (vllm_config.model_config.dtype,),
                                   num_speculative_blocks=0)
        logger.warning('b70_gdn_checkpoint: %s one state block per request, page %d bytes (stash %s)',
                       self.prefix, spec.page_size_bytes, layer_stash_shape(self))
        return spec

    Layer.get_kv_cache_spec = get_kv_cache_spec

    orig_init = Layer.__init__

    def __init__(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        self.register_buffer('_xpu_stash', torch.empty(0, dtype=self.model_config.dtype,
                                                        device=self._xpu_ssm_state.device), persistent=False)

    Layer.__init__ = __init__

    def bind_kv_cache(self, kv_cache):
        """As MambaBase.bind_kv_cache, with the stash as the third state; allocates the shared {parity, len} table."""
        from math import prod
        from vllm.utils.torch_utils import get_dtype_size
        shapes = list(self.get_state_shape())
        dtypes = list(self.get_state_dtype())
        if self.num_spec > 0:
            shapes.append(layer_stash_shape(self))
            dtypes.append(self.model_config.dtype)
        pages = kv_cache.squeeze(dim=(1, 2))
        states, offset = [], 0
        for shape, dtype in zip(shapes, dtypes):
            nbytes = prod(shape) * get_dtype_size(dtype)
            states.append(pages[:, offset:offset + nbytes].view(dtype).view(-1, *shape))
            offset += nbytes
        self.kv_cache = tuple(states)
        self._xpu_conv_state.set_(self.kv_cache[0])
        self._xpu_ssm_state.set_(self.kv_cache[1])
        if self.num_spec > 0:
            self._xpu_stash.set_(self.kv_cache[2])
            if state['meta'] is None:
                state['meta'] = torch.zeros((self.kv_cache[1].size(0), 2), dtype=torch.int32, device=self.kv_cache[1].device)
                state['stash_rows'] = self.num_spec + 1
                logger.warning('b70_gdn_checkpoint: stash meta for %d blocks, %d rows', state['meta'].size(0), state['stash_rows'])

    Layer.bind_kv_cache = bind_kv_cache

    # ---------------- metadata: one column, commit inputs, deferred meta updates ----------------
    orig_build = Builder.build

    def build(self, common_prefix_len, common_attn_metadata, num_accepted_tokens=None, num_decode_draft_tokens_cpu=None,
              fast_build=False):
        md = orig_build(self, common_prefix_len, common_attn_metadata, num_accepted_tokens, num_decode_draft_tokens_cpu, fast_build)
        if self.num_spec == 0:
            return md
        m = common_attn_metadata
        num_reqs = m.num_reqs
        md.gdn_stash_meta = state['meta']
        md.gdn_stash_rows = state['stash_rows']
        md.gdn_commit_num_accepted = None
        md.gdn_commit_mask = None
        if md.num_spec_decodes > 0 and md.spec_state_indices_tensor is not None:
            qlc = m.query_start_loc_cpu
            lens = qlc[1:num_reqs + 1] - qlc[:num_reqs]
            spec_mask_cpu = num_decode_draft_tokens_cpu[:num_reqs] >= 0
            width = int(lens[spec_mask_cpu].max().item())
            cols = md.spec_state_indices_tensor[:, :1]
            md.spec_state_indices_tensor = cols.expand(-1, width).contiguous()
            if state['meta'] is not None:
                state['pending_current'].append((cols.reshape(-1).long(), width))
        else:
            spec_mask_cpu = None
        ns = md.non_spec_state_indices_tensor
        if ns is not None and ns.numel() > 0 and md.num_prefills + md.num_decodes > 0:
            n_non_spec = md.num_prefills + md.num_decodes
            if num_accepted_tokens is not None:
                if spec_mask_cpu is not None:
                    keep = torch.nonzero(~spec_mask_cpu).flatten().to(num_accepted_tokens.device, non_blocking=True)
                    acc = num_accepted_tokens[:num_reqs].index_select(0, keep)
                else:
                    acc = num_accepted_tokens[:n_non_spec]
                md.gdn_commit_num_accepted = acc.to(torch.int32).contiguous()
                if md.has_initial_state is not None:
                    md.gdn_commit_mask = md.has_initial_state.to(torch.bool).contiguous()
                else:
                    md.gdn_commit_mask = torch.ones(n_non_spec, dtype=torch.bool, device=ns.device)
            if state['meta'] is not None:
                state['pending_current'].append((ns.reshape(-1).long(), 0))
        return md

    Builder.build = build

    def apply_pending():
        meta = state['meta']
        for blocks, width in state['pending_previous']:
            if width > 0:
                meta[blocks, 0] = 1 - meta[blocks, 0]
                meta[blocks, 1] = width
            else:
                meta[blocks, 1] = 0
        state['pending_previous'] = state['pending_current']
        state['pending_current'] = []

    # ---------------- the core op under the checkpoint protocol ----------------
    def core_impl(core_attn_out: torch.Tensor, z: torch.Tensor, projected_states_qkvz: torch.Tensor,
                  projected_states_ba: torch.Tensor, conv_state: torch.Tensor, ssm_state: torch.Tensor,
                  stash: torch.Tensor, layer_name: str) -> None:
        from vllm.forward_context import get_forward_context
        forward_context = get_forward_context()
        self = forward_context.no_compile_layers[layer_name]
        raw = forward_context.attn_metadata
        if raw is None:
            return
        md = raw[self.prefix]
        meta = getattr(md, 'gdn_stash_meta', None)
        if meta is None:
            # Profiling / warm-up runs before the caches are bound: the plain kernel on the widened slot table.
            _xpu_ops._gdn_attention_core_xpu_impl(core_attn_out, z, projected_states_qkvz, projected_states_ba,
                                                  conv_state, ssm_state, layer_name)
            return
        if forward_context is not state['last_ctx']:
            state['last_ctx'] = forward_context
            apply_pending()
        num_actual_tokens = md.num_actual_tokens
        num_accepted_tokens = md.num_accepted_tokens
        num_prefills, num_decodes, num_spec_decodes = md.num_prefills, md.num_decodes, md.num_spec_decodes
        has_initial_state = md.has_initial_state
        non_spec_query_start_loc = md.non_spec_query_start_loc
        non_spec_token_indx = md.non_spec_token_indx
        non_spec_state_indices_tensor = md.non_spec_state_indices_tensor
        if non_spec_state_indices_tensor is not None:
            non_spec_state_indices_tensor = non_spec_state_indices_tensor.contiguous()
        spec_query_start_loc = md.spec_query_start_loc
        spec_token_indx = md.spec_token_indx
        spec_state_indices_tensor = md.spec_state_indices_tensor
        spec_sequence_masks = md.spec_sequence_masks
        if spec_sequence_masks is not None:
            if non_spec_token_indx is not None:
                non_spec_token_indx = non_spec_token_indx.to(torch.int32)
            if spec_token_indx is not None:
                spec_token_indx = spec_token_indx.to(torch.int32)
        commit_acc, commit_mask = md.gdn_commit_num_accepted, md.gdn_commit_mask
        rows = md.gdn_stash_rows
        conv_weights = self.conv1d.weight.view(self.conv1d.weight.size(0), self.conv1d.weight.size(2))

        def _kernel(out, zz, qkvz, ba, n_prefills, n_decodes, n_spec, his, ns_qs, ns_tok, ns_state, sp_qs, sp_tok, sp_state,
                    n_acc, n_tokens, c_acc, c_mask):
            torch.ops._xpu_C.gdn_attention_ckpt(
                out, zz, qkvz, ba, self.num_k_heads, self.num_v_heads, self.head_k_dim, self.head_v_dim,
                conv_state=conv_state, ssm_state=ssm_state, conv_weights=conv_weights, conv_bias=self.conv1d.bias,
                activation=self.activation, A_log=self.A_log, dt_bias=self.dt_bias,
                num_prefills=n_prefills, num_decodes=n_decodes, num_spec_decodes=n_spec, has_initial_state=his,
                non_spec_query_start_loc=ns_qs, non_spec_token_indx=ns_tok, non_spec_state_indices_tensor=ns_state,
                spec_query_start_loc=sp_qs, spec_token_indx=sp_tok, spec_state_indices_tensor=sp_state,
                num_accepted_tokens=n_acc, num_actual_tokens=n_tokens, tp_size=self.tp_size,
                reorder_input=not self.gqa_interleaved_layout,
                stash=stash, stash_meta=meta, stash_rows=rows, commit_num_accepted=c_acc, commit_mask=c_mask)

        _spec_group = int(os.environ.get('VLLM_XPU_GDN_SPEC_GROUP', '16'))
        _group_spec = (_spec_group > 0 and num_spec_decodes > _spec_group and spec_sequence_masks is not None
                       and spec_token_indx is not None)
        if _group_spec or (os.environ.get('VLLM_XPU_GDN_SPLIT_MIXED', '0') == '1' and (
                (num_prefills > 0 and num_decodes > 0) or (num_spec_decodes > 0 and (num_prefills > 0 or num_decodes > 0)))):
            # Same split as the R156/R228 image path (pure calls per class), with the commit inputs sliced alongside.
            logger.warning_once('b70_gdn_checkpoint: split-mixed step executed')
            dev = core_attn_out.device
            if spec_sequence_masks is None:
                d, n = num_decodes, num_actual_tokens
                _kernel(core_attn_out[:d], z[:d], projected_states_qkvz[:d], projected_states_ba[:d], 0, d, 0,
                        has_initial_state[:d], torch.arange(d + 1, dtype=torch.int32, device=dev), None,
                        non_spec_state_indices_tensor[:d], None, None, None, None, d,
                        None if commit_acc is None else commit_acc[:d].contiguous(),
                        None if commit_mask is None else commit_mask[:d].contiguous())
                _kernel(core_attn_out[d:n], z[d:n], projected_states_qkvz[d:n], projected_states_ba[d:n], num_prefills, 0, 0,
                        has_initial_state[d:], (non_spec_query_start_loc[d:] - d).to(torch.int32).contiguous(), None,
                        non_spec_state_indices_tensor[d:].contiguous(), None, None, None, None, n - d,
                        None if commit_acc is None else commit_acc[d:].contiguous(),
                        None if commit_mask is None else commit_mask[d:].contiguous())
                return
            if spec_token_indx is not None and spec_token_indx.numel() > 0:
                st = spec_token_indx.long()
                n_sp = st.numel()
                _n_spec_tok = int(getattr(md, 'num_spec_decode_tokens', 0) or 0)
                _q = _n_spec_tok // num_spec_decodes if num_spec_decodes else 0
                if _q > 0 and _q * num_spec_decodes == _n_spec_tok and n_sp == _n_spec_tok:
                    sp_qs_cpu = [i * _q for i in range(num_spec_decodes + 1)]
                else:
                    sp_qs_cpu = spec_query_start_loc[:num_spec_decodes + 1].to('cpu', non_blocking=False).tolist()
                group = _spec_group if _spec_group > 0 else num_spec_decodes
                for s0 in range(0, num_spec_decodes, group):
                    s1 = min(s0 + group, num_spec_decodes)
                    t0, t1 = int(sp_qs_cpu[s0]), int(sp_qs_cpu[s1])
                    rws = st[t0:t1]
                    n_g = t1 - t0
                    out_s = torch.zeros((n_g,) + tuple(core_attn_out.shape[1:]), dtype=core_attn_out.dtype, device=dev)
                    z_s = torch.empty_like(out_s)
                    qs_g = (spec_query_start_loc[s0:s1 + 1] - t0).to(torch.int32).contiguous()
                    acc_g = num_accepted_tokens[s0:s1].contiguous() if num_accepted_tokens is not None else None
                    _kernel(out_s, z_s, projected_states_qkvz[rws].contiguous(), projected_states_ba[rws].contiguous(), 0, 0,
                            s1 - s0, None, None, torch.empty(0, dtype=torch.int32, device=dev), None, qs_g,
                            torch.arange(n_g, dtype=torch.int32, device=dev), spec_state_indices_tensor[s0:s1].contiguous(),
                            acc_g, n_g, None, None)
                    core_attn_out[rws] = out_s
                    z[rws] = z_s
            if non_spec_token_indx is not None and non_spec_token_indx.numel() > 0:
                nt = non_spec_token_indx.long()
                qs = non_spec_query_start_loc
                lens = (qs[1:] - qs[:-1])
                n_seq = lens.numel()
                his = has_initial_state if has_initial_state is not None else torch.zeros(n_seq, dtype=torch.bool, device=dev)
                dec_mask = (lens == 1) & his
                seq_ids = torch.arange(n_seq, device=dev)
                for is_dec in (True, False):
                    sel = seq_ids[dec_mask] if is_dec else seq_ids[~dec_mask]
                    if sel.numel() == 0:
                        continue
                    starts = qs[:-1][sel]; ends = qs[1:][sel]
                    rws = torch.cat([torch.arange(int(a_), int(b_), device=dev) for a_, b_ in zip(starts.tolist(), ends.tolist())])
                    tok = nt[rws]
                    n_t = tok.numel()
                    out_p = torch.zeros((n_t,) + tuple(core_attn_out.shape[1:]), dtype=core_attn_out.dtype, device=dev)
                    z_p = torch.empty_like(out_p)
                    sub_qs = torch.zeros(sel.numel() + 1, dtype=torch.int32, device=dev)
                    torch.cumsum(lens[sel].to(torch.int32), dim=0, out=sub_qs[1:])
                    _kernel(out_p, z_p, projected_states_qkvz[tok].contiguous(), projected_states_ba[tok].contiguous(),
                            0 if is_dec else sel.numel(), sel.numel() if is_dec else 0, 0, his[sel].contiguous(), sub_qs, None,
                            non_spec_state_indices_tensor[sel].contiguous(), None, None, None, None, n_t,
                            None if commit_acc is None else commit_acc[sel].contiguous(),
                            None if commit_mask is None else commit_mask[sel].contiguous())
                    core_attn_out[tok] = out_p
                    z[tok] = z_p
            return
        _kernel(core_attn_out, z, projected_states_qkvz, projected_states_ba, num_prefills, num_decodes, num_spec_decodes,
                has_initial_state, non_spec_query_start_loc, non_spec_token_indx, non_spec_state_indices_tensor,
                spec_query_start_loc, spec_token_indx, spec_state_indices_tensor, num_accepted_tokens, num_actual_tokens,
                commit_acc, commit_mask)

    def core_fake(core_attn_out: torch.Tensor, z: torch.Tensor, projected_states_qkvz: torch.Tensor,
                  projected_states_ba: torch.Tensor, conv_state: torch.Tensor, ssm_state: torch.Tensor,
                  stash: torch.Tensor, layer_name: str) -> None:
        return

    direct_register_custom_op(op_name='b70_gdn_attention_core_ckpt', op_func=eager_break_during_capture(core_impl),
                              mutates_args=['core_attn_out', 'z', 'conv_state', 'ssm_state', 'stash'], fake_impl=core_fake)

    def forward_xpu(self, hidden_states):
        num_tokens = hidden_states.size(0)
        projected_states_qkvz, _ = self.in_proj_qkvz(hidden_states)
        if (num_tokens >= layer_mod._XPU_DETERMINISTIC_BA_MIN_TOKENS
                and self.in_proj_ba.weight.dtype in (torch.float16, torch.bfloat16)):
            projected_states_ba = torch.ops.vllm.qwen_gdn_ba_prefill_xpu(hidden_states, self.in_proj_ba.weight)
        else:
            projected_states_ba, _ = self.in_proj_ba(hidden_states)
        core_attn_out = torch.zeros((num_tokens, self.num_v_heads // self.tp_size, self.head_v_dim),
                                    dtype=hidden_states.dtype, device=hidden_states.device)
        z = torch.empty_like(core_attn_out)
        if self.num_spec > 0:
            torch.ops.vllm.b70_gdn_attention_core_ckpt(core_attn_out, z, projected_states_qkvz, projected_states_ba,
                                                       self._xpu_conv_state, self._xpu_ssm_state, self._xpu_stash, self.prefix)
        else:
            torch.ops.vllm.gdn_attention_core_xpu(core_attn_out, z, projected_states_qkvz, projected_states_ba,
                                                  self._xpu_conv_state, self._xpu_ssm_state, self.prefix)
        z_shape_og = z.shape
        core_attn_out = core_attn_out.reshape(-1, core_attn_out.shape[-1])
        z = z.reshape(-1, z.shape[-1])
        core_attn_out = self.norm(core_attn_out, z)
        core_attn_out = core_attn_out.reshape(z_shape_og)
        core_attn_out = core_attn_out.flatten(-2)
        out, _ = self.out_proj(core_attn_out)
        return out

    Layer.forward_xpu = forward_xpu
    Layer._b70_gdn_checkpoint = True
    logger.warning('b70_gdn_checkpoint: installed (one GDN state block per request; replay-commit from the stash)')

"""Deterministic one-card GDN prefill: run the delta rule in fixed head groups (research overlay).

Enabled only with B70_GDN_HEAD_GROUPS=G (G >= 2). On one B70 the XPU chunked
gated-delta-rule kernel intermittently returns different core_attn_out values
for identical prefill calls with 48 value heads and >= 1,024 tokens (the final
recurrent state stays identical); with 24 heads per call (the TP2 per-rank
shape) it was bitwise stable in every census. Heads are independent in the delta
rule, so for pure non-spec prefill calls this overlay runs the unchanged conv
stage once and the unchanged delta-rule stage once per contiguous head group,
each call shaped exactly like one TP rank. Op-level census: the grouped result
equals an unglitched whole call bitwise and repeats exactly. Decode and
speculative calls are passed to the original fused op untouched.
"""
import os

_ORIGINAL = {}


def grouped_gdn_attention(core_attn_out, z, projected_states_qkvz, projected_states_ba, num_k_heads, num_v_heads,
                          head_k_dim, head_v_dim, *, conv_state, ssm_state, conv_weights, conv_bias, activation,
                          A_log, dt_bias, num_prefills, num_decodes, num_spec_decodes, has_initial_state,
                          non_spec_query_start_loc, non_spec_token_indx, non_spec_state_indices_tensor,
                          spec_query_start_loc, spec_token_indx, spec_state_indices_tensor, num_accepted_tokens,
                          num_actual_tokens, tp_size, reorder_input, groups):
    import torch

    ops = torch.ops._xpu_C
    q, k, v, b, a = ops.causal_conv1d_non_spec(
        z, projected_states_qkvz, projected_states_ba, num_k_heads, num_v_heads, head_k_dim, head_v_dim,
        conv_state, conv_weights, conv_bias, activation, num_prefills, num_decodes, 0, has_initial_state,
        non_spec_query_start_loc, non_spec_token_indx, non_spec_state_indices_tensor, num_actual_tokens,
        tp_size, reorder_input)
    k_local, v_local = q.shape[1], v.shape[1]
    kh, vh = k_local // groups, v_local // groups
    for g in range(groups):
        ks, vs = slice(g * kh, (g + 1) * kh), slice(g * vh, (g + 1) * vh)
        out_g = torch.zeros((core_attn_out.shape[0], vh, head_v_dim), dtype=core_attn_out.dtype,
                            device=core_attn_out.device)
        # A head slice of the state cache keeps each slot contiguous; the kernel indexes slots by stride(0).
        state_g = ssm_state[:, vs]
        ops.gated_delta_rule_non_spec(
            out_g, q[:, ks].contiguous(), k[:, ks].contiguous(), v[:, vs].contiguous(),
            b[vs].contiguous(), a[vs].contiguous(), num_v_heads, head_v_dim,
            A_log[vs].contiguous(), dt_bias[vs].contiguous(), state_g, num_prefills, num_decodes, 0,
            has_initial_state, non_spec_query_start_loc, non_spec_token_indx, non_spec_state_indices_tensor,
            num_actual_tokens, tp_size * groups)
        core_attn_out[:num_actual_tokens, vs] = out_g[:num_actual_tokens]


def register():
    groups = int(os.environ.get('B70_GDN_HEAD_GROUPS', '0') or 0)
    if groups < 2:
        return
    import torch
    import vllm_xpu_kernels._xpu_C  # noqa: F401  (registers _xpu_C ops)
    from vllm.logger import init_logger

    logger = init_logger('b70_gdn_head_groups')
    if 'gdn_attention' in _ORIGINAL:
        return
    original = torch.ops._xpu_C.gdn_attention
    _ORIGINAL['gdn_attention'] = original

    def gdn_attention(core_attn_out, z, projected_states_qkvz, projected_states_ba, num_k_heads, num_v_heads,
                      head_k_dim, head_v_dim, **kw):
        tp_size = kw['tp_size']
        k_local, v_local = num_k_heads // tp_size, num_v_heads // tp_size
        if (kw['num_prefills'] > 0 and kw['num_decodes'] == 0 and kw['num_spec_decodes'] == 0
                and kw['spec_token_indx'] is None and k_local % groups == 0 and v_local % groups == 0
                and v_local // groups >= 1):
            if not _ORIGINAL.get('logged'):
                logger.warning('b70_gdn_head_groups: prefill delta rule runs in %d head groups of %d', groups,
                               v_local // groups)
                _ORIGINAL['logged'] = True
            return grouped_gdn_attention(core_attn_out, z, projected_states_qkvz, projected_states_ba, num_k_heads,
                                         num_v_heads, head_k_dim, head_v_dim, groups=groups, **kw)
        return original(core_attn_out, z, projected_states_qkvz, projected_states_ba, num_k_heads, num_v_heads,
                        head_k_dim, head_v_dim, **kw)

    setattr(torch.ops._xpu_C, 'gdn_attention', gdn_attention)
    logger.warning('b70_gdn_head_groups: enabled with %d groups for pure prefill calls', groups)

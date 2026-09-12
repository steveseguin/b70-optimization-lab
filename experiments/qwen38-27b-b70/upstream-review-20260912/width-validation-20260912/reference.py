# Derived from vllm-xpu-kernels efc85bc8 tests/gdn_attn/test_gdn_attn.py.
# Apache-2.0 upstream source. Local adaptations documented in README.
import math
import torch
import torch.nn.functional as F


def _extract_qkv_b_a_z(
    projected_states_qkvz,
    projected_states_ba,
    num_actual_tokens,
    num_k_heads,
    num_v_heads,
    head_k_dim,
    head_v_dim,
    tp_size,
    reorder_input,
):
    """Replicate the qkv/ba split done in `ref_gdn_attention` and return
    the post-reorder qkv (for conv1d), b, a, z tensors plus split sizes."""
    if reorder_input:
        key_dim = head_k_dim * num_k_heads
        value_dim = head_v_dim * num_v_heads
        q_size = key_dim // tp_size
        k_size = q_size
        v_size = value_dim // tp_size
        z_size = v_size
        q_tmp, k_tmp, v_tmp, z_tmp = projected_states_qkvz.split(
            [q_size, k_size, v_size, z_size], dim=-1
        )
        q_tmp = q_tmp.reshape(q_tmp.size(0), -1, head_k_dim)
        k_tmp = k_tmp.reshape(k_tmp.size(0), -1, head_k_dim)
        v_tmp = v_tmp.reshape(
            v_tmp.size(0), -1, num_v_heads // num_k_heads * head_v_dim
        )
        z_tmp = z_tmp.reshape(
            z_tmp.size(0), -1, num_v_heads // num_k_heads * head_v_dim
        )
        projected_states_qkvz = (
            torch.cat([q_tmp, k_tmp, v_tmp, z_tmp], dim=-1)
            .reshape(q_tmp.size(0), -1)
            .contiguous()
        )

        b, a = projected_states_ba.chunk(2, dim=-1)
        b = b.reshape(b.size(0), -1, num_v_heads // num_k_heads)
        a = a.reshape(a.size(0), -1, num_v_heads // num_k_heads)
        projected_states_ba = (
            torch.cat([b, a], dim=-1).reshape(b.size(0), -1).contiguous()
        )

    projected_states_ba = projected_states_ba.reshape(
        num_actual_tokens, num_k_heads // tp_size, (2 * num_v_heads // num_k_heads)
    )
    b, a = torch.split(
        projected_states_ba,
        [num_v_heads // num_k_heads, num_v_heads // num_k_heads],
        dim=-1,
    )
    b = b.reshape(num_actual_tokens, num_v_heads // tp_size)
    a = a.reshape(num_actual_tokens, num_v_heads // tp_size)

    split_qkvz = [
        head_k_dim,
        head_k_dim,
        num_v_heads // num_k_heads * head_v_dim,
        num_v_heads // num_k_heads * head_v_dim,
    ]
    projected_states_qkvz = projected_states_qkvz.reshape(
        num_actual_tokens,
        num_k_heads // tp_size,
        (2 * head_k_dim + 2 * num_v_heads // num_k_heads * head_v_dim),
    )
    q_split, k_split, v_split, z_split = torch.split(
        projected_states_qkvz, split_qkvz, dim=-1
    )
    q_split = q_split.reshape(num_actual_tokens, num_k_heads // tp_size * head_k_dim)
    k_split = k_split.reshape(num_actual_tokens, num_k_heads // tp_size * head_k_dim)
    v_split = v_split.reshape(
        num_actual_tokens,
        num_k_heads // tp_size * num_v_heads // num_k_heads * head_v_dim,
    )
    qkv = torch.cat((q_split, k_split, v_split), dim=-1).reshape(
        num_actual_tokens,
        num_k_heads
        // tp_size
        * (2 * head_k_dim + num_v_heads // num_k_heads * head_v_dim),
    )
    z_global = z_split.reshape(num_actual_tokens, num_v_heads // tp_size, head_v_dim)
    return qkv, b, a, z_global


def ref_gdn_attention_spec(
    core_attn_out,
    z,
    projected_states_qkvz,
    projected_states_ba,
    num_k_heads,
    num_v_heads,
    head_k_dim,
    head_v_dim,
    conv_state,
    ssm_state,
    conv_weights,
    conv_bias,
    activation,
    A_log,
    dt_bias,
    num_spec_decodes,
    spec_query_start_loc,
    spec_token_indx,
    spec_state_indices_tensor,
    num_accepted_tokens,
    num_actual_tokens,
    tp_size,
    reorder_input,
):
    """Spec-decode reference. Conv uses the single-cache-line sliding-window
    convention (column 0 + row offset); ssm keeps the token-indexed
    convention (per-step writeback to every column)."""
    eps = 0.000001
    scale = 1.0 / math.sqrt(head_k_dim)
    dtype = projected_states_qkvz.dtype
    width = conv_weights.shape[-1]
    rep = num_v_heads // num_k_heads
    K = int(spec_query_start_loc[1] - spec_query_start_loc[0])
    qkv_elems_size = (
        num_k_heads
        // tp_size
        * (2 * head_k_dim + num_v_heads // num_k_heads * head_v_dim)
    )

    qkv, b, a, z_global = _extract_qkv_b_a_z(
        projected_states_qkvz,
        projected_states_ba,
        num_actual_tokens,
        num_k_heads,
        num_v_heads,
        head_k_dim,
        head_v_dim,
        tp_size,
        reorder_input,
    )

    # Scatter z into output at the spec token positions.
    spec_indx_long = spec_token_indx.to(torch.long)
    z[spec_indx_long] = z_global[spec_indx_long]

    A_log_exp = -torch.exp(A_log)
    softplus = torch.nn.Softplus(beta=1.0, threshold=20.0)
    conv_bias_f = conv_bias.to(torch.float) if conv_bias is not None else None

    split_qkv = [
        num_k_heads // tp_size * head_k_dim,
        num_k_heads // tp_size * head_k_dim,
        num_k_heads // tp_size * num_v_heads // num_k_heads * head_v_dim,
    ]

    for n in range(num_spec_decodes):
        start = int(spec_query_start_loc[n].item())
        end = int(spec_query_start_loc[n + 1].item())
        assert end - start == K, (end - start, K)
        globals_ = spec_token_indx[start:end].to(torch.long)

        naccepted = int(num_accepted_tokens[n].item())
        init_col = max(naccepted - 1, 0)
        init_slot = int(spec_state_indices_tensor[n, init_col].item())  # ssm
        conv_slot = int(spec_state_indices_tensor[n, 0].item())  # conv, col 0
        conv_state_len = width - 2 + K
        conv_init_row = init_col

        # conv1d: window = rows [init_row, init_row + width - 1), col 0
        conv_line = conv_state[conv_slot]
        prior = conv_line[conv_init_row : conv_init_row + (width - 1)].clone()
        qkv_batch = qkv[globals_]  # [K, qkv_elems]
        qkv_conv_input = torch.cat([prior, qkv_batch], dim=0)
        # Roll the line: history from init_row+1, then the K draft inputs.
        new_conv_line = conv_line.clone()
        hist_rows = conv_state_len - K
        if hist_rows > 0:
            new_conv_line[:hist_rows] = conv_line[
                conv_init_row + 1 : conv_init_row + 1 + hist_rows
            ]
        new_conv_line[hist_rows:conv_state_len] = qkv_batch
        conv_state[conv_slot] = new_conv_line

        qkv_conv_in = qkv_conv_input.transpose(0, 1).unsqueeze(0).to(torch.float32)
        qkv_conv_out = F.conv1d(
            qkv_conv_in,
            conv_weights.unsqueeze(1).to(torch.float32),
            conv_bias_f,
            padding=0,
            groups=qkv_elems_size,
        )
        qkv_conv_out = (
            qkv_conv_out if activation is None else F.silu(qkv_conv_out)
        ).to(dtype=dtype)
        qkv_conv_out = qkv_conv_out.transpose(-2, -1).reshape(K, qkv_elems_size)

        q_out, k_out, v_out = torch.split(qkv_conv_out, split_qkv, dim=-1)
        q_out = q_out.reshape(K, num_k_heads // tp_size, head_k_dim)
        k_out = k_out.reshape(K, num_k_heads // tp_size, head_k_dim)
        v_out = v_out.reshape(K, num_v_heads // tp_size, head_v_dim)

        # ---- SSM recurrence (same as non-spec, just per-step writeback) ----
        ssm_state_batch = ssm_state[init_slot].to(torch.float32).clone()

        b_batch = b[globals_].to(torch.float32)
        a_batch = a[globals_].to(torch.float32)
        beta_batch = torch.sigmoid(b_batch)
        g_batch = torch.exp(A_log_exp * softplus(a_batch + dt_bias))

        q_all = q_out.to(torch.float32)
        k_all = k_out.to(torch.float32)
        v_all = v_out.to(torch.float32)
        q_all = q_all * torch.rsqrt(q_all.pow(2).sum(-1, keepdim=True) + eps)
        k_all = k_all * torch.rsqrt(k_all.pow(2).sum(-1, keepdim=True) + eps)
        q_all = q_all * scale
        if rep > 1:
            q_all = q_all.repeat_interleave(rep, dim=1)
            k_all = k_all.repeat_interleave(rep, dim=1)

        for t in range(K):
            g_t = g_batch[t]
            beta_t = beta_batch[t]
            q_t = q_all[t]
            k_t = k_all[t]
            v_t = v_all[t]

            ssm_state_batch *= g_t.unsqueeze(-1).unsqueeze(-1)
            kv_mem_t = torch.einsum("vhk,vk->vh", ssm_state_batch, k_t)
            delta_t = (v_t - kv_mem_t) * beta_t.unsqueeze(-1)
            ssm_state_batch.add_(torch.einsum("vh,vk->vhk", delta_t, k_t))

            out_t = torch.einsum("vhk,vk->vh", ssm_state_batch, q_t).to(dtype)
            core_attn_out[globals_[t]] = out_t
            # Per-step ssm-state writeback to cache_indices[n, t].
            ssm_state[int(spec_state_indices_tensor[n, t].item())] = ssm_state_batch.to(
                ssm_state.dtype
            )

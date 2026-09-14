"""Actual tiny BF16 CPU fixture extracted from the pinned Python-boundary gate; arithmetic unchanged."""

def make_block(torch, BasicAVTransformerBlock, comfy):
    block = BasicAVTransformerBlock(v_dim=32, a_dim=32, v_heads=1, a_heads=1, vd_head=32, ad_head=32, v_context_dim=32, a_context_dim=32, apply_gated_attention=True, cross_attention_adaln=True, dtype=torch.bfloat16, device='cpu', operations=comfy.ops.manual_cast).eval()
    generator = torch.Generator(device='cpu').manual_seed(20260913)
    with torch.no_grad():
        for name, parameter in block.named_parameters():
            value = torch.randn(parameter.shape, generator=generator, dtype=torch.float32) * 0.02
            if name.endswith('q_norm.weight') or name.endswith('k_norm.weight'):
                value += 1
            parameter.copy_(value)
    return block

def make_inputs(torch, CompressedTimestep, tokens, seed):
    gen = torch.Generator(device='cpu').manual_seed(seed)

    def rand(*shape):
        return torch.randn(shape, generator=gen, dtype=torch.bfloat16, device='cpu') * 0.1

    def rope(n):
        angle = torch.randn((1, n, 1, 16), generator=gen, dtype=torch.float32)
        c, s = (angle.cos(), angle.sin())
        return (torch.stack((torch.stack((c, -s), -1), torch.stack((s, c), -1)), -2), True)

    def video_time(width):
        return CompressedTimestep(rand(1, 4, width), tokens // 4, per_frame=True)
    return ((rand(1, tokens, 32), rand(1, 26, 32)), {'v_context': rand(1, 8, 32), 'a_context': rand(1, 8, 32), 'v_timestep': video_time(9 * 32), 'a_timestep': rand(1, 26, 9 * 32), 'v_pe': rope(tokens), 'a_pe': rope(26), 'v_cross_pe': rope(tokens), 'a_cross_pe': rope(26), 'v_cross_scale_shift_timestep': video_time(4 * 32), 'a_cross_scale_shift_timestep': rand(1, 26, 4 * 32), 'v_cross_gate_timestep': video_time(32), 'a_cross_gate_timestep': rand(1, 26, 32), 'v_prompt_timestep': rand(1, 1, 2 * 32), 'a_prompt_timestep': rand(1, 1, 2 * 32), 'transformer_options': {}})

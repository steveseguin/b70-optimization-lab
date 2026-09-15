"""What does rebuilding the RoPE rotation matrices every step cost?

_precompute_freqs_cis runs four times per forward (video, audio, and the two
cross-attention sets), so 44 times per clip. Its output depends only on the
positions, the head count and the dtype -- all constant across the steps of a
stage -- so memoising it is bitwise exact by construction.
"""
import json, time
import torch

torch.use_deterministic_algorithms(True, warn_only=False)
torch.manual_seed(0)
DEV, DT = 'xpu:0', torch.bfloat16

def freqs_cis_matrix(freqs, pad_size, split_mode, num_attention_heads, out_dtype):
    cos_freq = freqs.cos().to(out_dtype)
    sin_freq = freqs.sin().to(out_dtype)
    if pad_size:
        matrix_pad_size = pad_size if split_mode else pad_size // 2
        cos_padding = torch.ones_like(cos_freq[:, :, :matrix_pad_size])
        sin_padding = torch.zeros_like(sin_freq[:, :, :matrix_pad_size])
        cos_freq = torch.cat((cos_padding, cos_freq), dim=-1)
        sin_freq = torch.cat((sin_padding, sin_freq), dim=-1)
    B, T, half_HD = cos_freq.shape
    cos_freq = cos_freq.reshape(B, T, num_attention_heads, half_HD // num_attention_heads)
    sin_freq = sin_freq.reshape(B, T, num_attention_heads, half_HD // num_attention_heads)
    rotation_matrix = torch.stack((cos_freq, -sin_freq, sin_freq, cos_freq), dim=-1)
    return rotation_matrix.reshape(*rotation_matrix.shape[:-1], 2, 2), split_mode

def timeit(fn, iters=50, warmup=10):
    for _ in range(warmup): fn()
    torch.xpu.synchronize(DEV)
    t0 = time.perf_counter()
    for _ in range(iters): fn()
    torch.xpu.synchronize(DEV)
    return (time.perf_counter() - t0) / iters

# (name, tokens, half_HD, heads) -- the four sites per forward
SITES = [
    ('video pe',        64,  2048, 32),
    ('video pe',        256, 2048, 32),
    ('audio pe',        26,  1024, 32),
    ('av cross video',  64,  1024, 32),
    ('av cross video',  256, 1024, 32),
    ('av cross audio',  26,  1024, 32),
]
rows = []
for name, T, half_HD, heads in SITES:
    freqs = torch.randn(1, T, half_HD, dtype=torch.float32, device=DEV)
    ms = timeit(lambda: freqs_cis_matrix(freqs, 0, False, heads, DT)) * 1e3
    out, _ = freqs_cis_matrix(freqs, 0, False, heads, DT)
    rows.append({'site': name, 'tokens': T, 'half_HD': half_HD, 'ms': round(ms, 4),
                 'out_shape': list(out.shape),
                 'out_MB': round(out.numel() * out.element_size() / 2**20, 2)})
    del freqs, out
    torch.xpu.empty_cache()

# a clip: 8 stage-1 steps and 3 stage-2 steps, four sites each
def pick(name, T):
    return next(r['ms'] for r in rows if r['site'] == name and r['tokens'] == T)
s1 = pick('video pe', 64) + pick('audio pe', 26) + pick('av cross video', 64) + pick('av cross audio', 26)
s2 = pick('video pe', 256) + pick('audio pe', 26) + pick('av cross video', 256) + pick('av cross audio', 26)
clip = (s1 * 8 + s2 * 3) / 1e3
print(json.dumps({'per_site': rows,
                  'per_step_stage1_ms': round(s1, 3), 'per_step_stage2_ms': round(s2, 3),
                  'clip_total_s': round(clip, 4),
                  'sampler_s': 1.929, 'share_of_sampler_pct': round(clip / 1.929 * 100, 1),
                  'note': 'memoising these is bitwise exact: identical inputs, identical output tensors'},
                 indent=2))

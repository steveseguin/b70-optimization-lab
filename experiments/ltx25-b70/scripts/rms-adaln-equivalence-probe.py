"""Is the fused rms_adaln the video path uses bitwise equal to the unfused
sequence the audio path uses? If yes, the audio path can use it too, losslessly.
"""
import sys, torch
PK = '/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-graph-capture-38/source'
sys.path.insert(0, PK)
torch.xpu.set_device(3)
DEV = 'xpu:3'
torch.use_deterministic_algorithms(True)

import comfy.quant_ops
import comfy.ldm.common_dit

def bits(t):
    return t.view(torch.int16) if t.dtype == torch.bfloat16 else t

torch.manual_seed(0)
for name, shape in (('audio [1,26,2048]', (1, 26, 2048)),
                    ('video [1,256,4096]', (1, 256, 4096)),
                    ('video [1,64,4096]', (1, 64, 4096))):
    x = torch.randn(*shape, dtype=torch.bfloat16, device=DEV)
    scale = torch.randn(*shape, dtype=torch.bfloat16, device=DEV) * 0.1
    shift = torch.randn(*shape, dtype=torch.bfloat16, device=DEV) * 0.1
    eager = comfy.ldm.common_dit.rms_norm(x) * (1 + scale) + shift
    try:
        fused = comfy.quant_ops.ck.rms_adaln(x, scale, shift)
    except Exception as e:
        print('%-22s rms_adaln FAILED: %s' % (name, str(e)[:80])); continue
    same = torch.equal(bits(fused), bits(eager))
    if same:
        print('%-22s BITWISE EQUAL' % name)
    else:
        d = (fused.float() - eager.float()).abs()
        ne = (bits(fused) != bits(eager)).sum().item()
        print('%-22s DIFFERS: %d/%d elements, max abs %.3e'
              % (name, ne, x.numel(), d.max().item()))

"""One bounded post-incident health assessment of all four B70s.

Tiny exclusive copy/compute per card plus directed peer copies. Stops at the
first failure. No xpu-smi, no driver reset, no power or memory setting change.
"""
import json, time
import torch

res = {'devices': torch.xpu.device_count(), 'checks': [], 'status': 'unknown'}
try:
    torch.use_deterministic_algorithms(True, warn_only=False)
    torch.manual_seed(0)
    n = torch.xpu.device_count()
    assert n == 4, f'expected four devices, saw {n}'
    for i in range(n):
        d = f'xpu:{i}'
        p = torch.xpu.get_device_properties(i)
        # exact host round trip
        a = torch.arange(1 << 20, dtype=torch.float32)
        g = a.to(d)
        back = g.cpu()
        assert torch.equal(a, back), f'{d} copy round trip differs'
        # deterministic compute with an exactly representable answer
        x = torch.full((512, 512), 2.0, dtype=torch.float32, device=d)
        y = torch.full((512, 512), 3.0, dtype=torch.float32, device=d)
        z = x @ y
        assert torch.equal(z, torch.full((512, 512), 6.0 * 512, dtype=torch.float32, device=d)), f'{d} matmul differs'
        # bf16 path, the dtype the lane actually runs
        bx = torch.full((1024, 1024), 1.0, dtype=torch.bfloat16, device=d)
        bz = bx @ bx
        assert torch.equal(bz, torch.full((1024, 1024), 1024.0, dtype=torch.bfloat16, device=d)), f'{d} bf16 matmul differs'
        torch.xpu.synchronize(i)
        res['checks'].append({'device': d, 'name': p.name,
                              'total_GiB': round(p.total_memory / 2**30, 2),
                              'copy_roundtrip': 'exact', 'fp32_matmul': 'exact', 'bf16_matmul': 'exact'})
        del a, g, back, x, y, z, bx, bz
        torch.xpu.empty_cache()
    # directed peer copies both ways between every pair
    peers = []
    for i in range(n):
        for j in range(n):
            if i == j: continue
            src = torch.arange(1 << 18, dtype=torch.float32, device=f'xpu:{i}')
            dst = torch.empty_like(src, device=f'xpu:{j}')
            dst.copy_(src)
            torch.xpu.synchronize(j)
            assert torch.equal(dst.cpu(), src.cpu()), f'peer copy xpu:{i}->xpu:{j} differs'
            peers.append(f'{i}->{j}')
            del src, dst
    torch.xpu.empty_cache()
    res['peer_copies'] = {'pairs': len(peers), 'all_exact': True}
    res['status'] = 'healthy'
except BaseException as error:
    res['status'] = 'FAILED'
    res['error'] = repr(error)
print(json.dumps(res, indent=2))

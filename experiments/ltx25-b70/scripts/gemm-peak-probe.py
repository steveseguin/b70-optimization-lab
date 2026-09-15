"""B70 bf16 GEMM ceiling and copy roofline, on an idle card.

The question this answers: the LTX video stream computes about 159 GFLOP per
block at 256 tokens in 2.68 ms, which is ~59 TFLOP/s. Is that the hardware's
ceiling (so the sampler is at its floor) or a long way under it?
"""
import time, torch

DEV = 'xpu:3'
torch.xpu.set_device(3)


def timed(fn, iters=30, warm=8):
    for _ in range(warm):
        fn()
    torch.xpu.synchronize(DEV)
    t0 = time.perf_counter()
    for _ in range(iters):
        fn()
    torch.xpu.synchronize(DEV)
    return (time.perf_counter() - t0) / iters


# copy roofline
n = 1 << 27  # 128 Mi bf16 = 256 MB
a = torch.empty(n, dtype=torch.bfloat16, device=DEV)
b = torch.empty(n, dtype=torch.bfloat16, device=DEV)
s = timed(lambda: b.copy_(a), iters=20)
print('copy roofline: %.1f GB/s' % (2 * n * 2 / s / 1e9))

print('\n%-22s %10s %10s %12s' % ('shape (M,K,N)', 'ms', 'TFLOP/s', 'GB/s weights'))
shapes = [
    (256, 4096, 4096), (256, 4096, 16384), (256, 16384, 4096),
    (1024, 3840, 3840), (1024, 3840, 15360), (1024, 15360, 3840),
    (4096, 4096, 4096), (8192, 8192, 8192),
    (26, 4096, 4096),
]
for M, K, N in shapes:
    try:
        x = torch.randn(M, K, dtype=torch.bfloat16, device=DEV)
        w = torch.randn(K, N, dtype=torch.bfloat16, device=DEV)
        s = timed(lambda: torch.mm(x, w))
        tf = 2 * M * K * N / s / 1e12
        gb = K * N * 2 / s / 1e9
        print('%-22s %10.4f %10.1f %12.1f' % (f'{M},{K},{N}', s * 1e3, tf, gb))
        del x, w
        torch.xpu.empty_cache()
    except Exception as e:
        print('%-22s FAILED %s' % (f'{M},{K},{N}', str(e)[:60]))

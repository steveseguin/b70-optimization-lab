import sys, time, torch
for mb in (257, 300, 384, 448, 496, 500, 511, 512):
    n = mb * 1024 * 1024 // 2
    src = torch.zeros(n, dtype=torch.float16); src[::4097] = 1.5
    print(f'SIZE_BEGIN {mb} MiB', flush=True)
    t0 = time.perf_counter(); dst = src.to('xpu'); torch.xpu.synchronize(); dt = time.perf_counter() - t0
    ok = bool(torch.equal(dst[::4097].cpu(), src[::4097]))
    print(f'SIZE_END {mb} MiB upload_s={dt:.3f} GBps={n*2/dt/1e9:.2f} equal={ok}', flush=True)
    del dst, src

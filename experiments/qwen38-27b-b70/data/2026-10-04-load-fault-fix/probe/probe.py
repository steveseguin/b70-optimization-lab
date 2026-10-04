import os, sys, time, torch
n = 124160 * 5120                      # the 1.27 GB embedding / output-layer weight, as FP16
gen = torch.Generator().manual_seed(1)
src = torch.randint(-30000, 30000, (n,), dtype=torch.int16, generator=gen).view(torch.float16)
ref = src.view(torch.int16)[::4097].clone()
torch.xpu.synchronize()
t0 = time.perf_counter()
dst = src.to('xpu')
torch.xpu.synchronize()
dt = time.perf_counter() - t0
back = dst.view(torch.int16)[::4097].cpu()
small = torch.arange(1000, dtype=torch.float16).to('xpu')          # a small copy, already on the CPU path
t1 = time.perf_counter(); d2 = dst.clone(); torch.xpu.synchronize(); dclone = time.perf_counter() - t1   # card-to-card copy
print(f'PROBE upload_s={dt:.3f} GBps={n*2/dt/1e9:.2f} equal={bool(torch.equal(ref, back))} clone_s={dclone:.3f} clone_equal={bool(torch.equal(d2.view(torch.int16)[::4097].cpu(), ref))}', flush=True)

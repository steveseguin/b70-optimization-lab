import sys, time, torch
sys.path.insert(0, '/work')
import b70_chunked_upload as cu
MIB = 1024 * 1024
n = 124160 * 5120
gen = torch.Generator().manual_seed(1)
src = torch.randint(-30000, 30000, (n,), dtype=torch.int16, generator=gen).view(torch.float16).view(124160, 5120)
copy, to = torch.Tensor.copy_, torch.Tensor.to
dev = lambda v: v if isinstance(v, torch.device) else torch.device(v) if isinstance(v, str) else None
done = []
torch.Tensor.copy_ = cu.wrap_copy(copy, 256 * MIB, 128 * MIB, counter=done)
torch.Tensor.to = cu.wrap_to(to, copy, torch.empty, dev, 256 * MIB, 128 * MIB, counter=done)
try:
    print('CHUNKED_BEGIN', flush=True)
    dst = torch.empty(124160, 5120, dtype=torch.float16, device='xpu')
    t0 = time.perf_counter(); dst.copy_(src); torch.xpu.synchronize(); t_copy = time.perf_counter() - t0
    t0 = time.perf_counter(); dst2 = src.to('xpu'); torch.xpu.synchronize(); t_to = time.perf_counter() - t0
    param = torch.nn.Parameter(torch.empty(124160, 5120, dtype=torch.float16, device='xpu'))
    param.data.copy_(src); torch.xpu.synchronize()
    print('CHUNKED_END', flush=True)
finally:
    torch.Tensor.copy_, torch.Tensor.to = copy, to
full = lambda t: bool(torch.equal(t.cpu().view(torch.int16), src.view(torch.int16)))  # bit patterns: the random data contains NaNs
print(f'PROBE copy_s={t_copy:.3f} to_s={t_to:.3f} uploads_chunked={len(done)} equal_copy={full(dst)} equal_to={full(dst2)} equal_param={full(param.data)}', flush=True)

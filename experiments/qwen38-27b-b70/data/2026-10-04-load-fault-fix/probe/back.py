import sys, time, torch
sys.path.insert(0, '/work')
import b70_chunked_upload as cu
MIB = 1024 * 1024
gen = torch.Generator().manual_seed(2)
src = torch.randint(-30000, 30000, (248320 * 5120,), dtype=torch.int16, generator=gen).view(torch.float16).view(248320, 5120)  # 2.5 GB
copy, to = torch.Tensor.copy_, torch.Tensor.to
dev = lambda v: v if isinstance(v, torch.device) else torch.device(v) if isinstance(v, str) else None
done = []
torch.Tensor.copy_ = cu.wrap_copy(copy, 256 * MIB, 128 * MIB, counter=done)
torch.Tensor.to = cu.wrap_to(to, copy, torch.empty, dev, 256 * MIB, 128 * MIB, counter=done)
try:
    print('CHUNKED_BEGIN', flush=True)
    card = src.to('xpu'); torch.xpu.synchronize()
    t0 = time.perf_counter(); back = card.data.to('cpu'); dt = time.perf_counter() - t0
    print('CHUNKED_END', flush=True)
finally:
    torch.Tensor.copy_, torch.Tensor.to = copy, to
print(f'PROBE back_s={dt:.3f} transfers_chunked={len(done)} equal={bool(torch.equal(back.view(torch.int16), src.view(torch.int16)))}', flush=True)

"""Time the draft INT4 lm_head kernel at decode M on one B70, in isolation, against roofline.
Run inside the lane image: docker run --rm -w / --device /dev/dri ... IMAGE python3 /bench/draft-head-microbench.py
Random weights: the kernel's speed does not depend on values, and the draft head need not be exact anyway."""
import time, torch
import vllm_xpu_kernels._xpu_C  # noqa: F401
dev = torch.device("xpu")
K, N, G = 4096, 248320, 128
packed_k = K // 8
qweight = torch.randint(0, 2**31 - 1, (N, packed_k), dtype=torch.int32, device=dev).t()  # [K/8, N] view as the layer keeps it
scales = (torch.rand((K // G, N), device=dev, dtype=torch.float32) * 0.01 + 0.001).to(torch.bfloat16).contiguous()
qzeros = torch.tensor([8], dtype=torch.int8, device=dev)
w16 = torch.randn((N, K), device=dev, dtype=torch.float16)
def timeit(fn, iters=30, warm=5):
    for _ in range(warm): fn()
    torch.xpu.synchronize(); t = time.perf_counter()
    for _ in range(iters): fn()
    torch.xpu.synchronize(); return (time.perf_counter() - t) / iters * 1e3
int4_bytes = N * K // 2 + scales.numel() * 2
print(f"N={N} K={K} group={G}: int4 weight+scales {int4_bytes/1e6:.0f} MB, fp16 weight {N*K*2/1e6:.0f} MB")
for M in (1, 2, 3, 4, 8, 16):
    x = torch.randn((M, K), device=dev, dtype=torch.float16)
    ms_int4 = timeit(lambda: torch.ops._xpu_C.int4_gemm_w4a16(x, qweight, None, scales, qzeros, G, None))
    logits = torch.ops._xpu_C.int4_gemm_w4a16(x, qweight, None, scales, qzeros, G, None)
    ms_argmax = timeit(lambda: logits.argmax(dim=-1))
    ms_fp16 = timeit(lambda: torch.matmul(x, w16.t()))
    print(f"M={M:2d}: int4 head {ms_int4:6.3f} ms ({int4_bytes/ms_int4/1e6:6.0f} GB/s eff)  argmax {ms_argmax:6.3f} ms  fp16 matmul {ms_fp16:6.3f} ms ({N*K*2/ms_fp16/1e6:5.0f} GB/s)")
# a copy roofline: how fast can this card stream the int4 bytes at all
buf = torch.empty(int4_bytes // 2, dtype=torch.float16, device=dev); dst = torch.empty_like(buf)
ms_copy = timeit(lambda: dst.copy_(buf))
print(f"device copy of the same bytes: {ms_copy:.3f} ms -> {2*int4_bytes/ms_copy/1e6:.0f} GB/s (read+write)")

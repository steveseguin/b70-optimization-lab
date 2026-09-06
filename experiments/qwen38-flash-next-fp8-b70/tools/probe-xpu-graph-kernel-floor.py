import os, time, torch
device = torch.device("xpu:0"); torch.xpu.set_device(device)
sizes = {"tiny(1e3)": 1000, "small(1e5)": 100_000, "medium(1e6)": 1_000_000, "large(1e7, 40 MB bf16)": 10_000_000}
for label, n in sizes.items():
    a = torch.randn(n, device=device, dtype=torch.bfloat16); b = torch.randn(n, device=device, dtype=torch.bfloat16)
    G = torch.xpu.XPUGraph(); stream = torch.xpu.Stream()
    with torch.xpu.stream(stream):
        for _ in range(4): c = torch.add(a, b)
        torch.xpu.synchronize()
        with torch.xpu.graph(G, stream=stream):
            for _ in range(288): c = torch.add(a, b)
    torch.xpu.synchronize()
    for _ in range(3): G.replay()
    torch.xpu.synchronize(); t0 = time.perf_counter(); reps = 20
    for _ in range(reps): G.replay()
    torch.xpu.synchronize(); t1 = time.perf_counter()
    per = 1e6 * (t1 - t0) / reps / 288
    print(f"GRAPH 288 x add {label}: {1e3*(t1-t0)/reps:.3f} ms per replay = {per:.1f} us per kernel", flush=True)
# eager launch rate for comparison (tiny)
a = torch.randn(1000, device=device, dtype=torch.bfloat16); b = torch.randn(1000, device=device, dtype=torch.bfloat16)
torch.xpu.synchronize(); t0 = time.perf_counter()
for _ in range(2000): c = torch.add(a, b)
torch.xpu.synchronize(); t1 = time.perf_counter(); print(f"EAGER tiny add: {1e6*(t1-t0)/2000:.1f} us per kernel (CPU-bound launch rate)")

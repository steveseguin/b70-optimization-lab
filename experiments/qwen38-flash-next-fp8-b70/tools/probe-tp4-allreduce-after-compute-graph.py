#!/usr/bin/env python3
"""Four-card XCCL all-reduce cost when real compute precedes it, eager and inside an XPUGraph.
Per rank: 48 x [busy kernel (K bf16 dim x dim matmuls on a static buffer, --dim 2048 ~0.15 ms each) -> [1,2560] BF16 all-reduce],
measured (a) busy alone, (b) all-reduce alone, (c) busy then all-reduce, each eager (device syncs) and as a
captured graph replay; K in --pad-iters (0 = memset-like no-op). Skew-free by construction (identical work
per rank), so any excess of (c) over (a)+(b) is the collective waiting on the preceding compute, not rank skew.
Serving CCL environment; refuses to run beside a model server.
    probe-tp4-allreduce-after-compute-graph.py --out <json> [--iters 30] [--pad-iters 0,1,3,6]
"""
from __future__ import annotations
import argparse, json, os, statistics, subprocess, sys, time

def refuse_active_model_server() -> None:
    out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
    if any(("EngineCore" in l or "Worker_TP" in l or "vllm serve" in l) for l in out.splitlines()):
        sys.exit("refusing to run beside a model server")

def worker(rank, world, args, result_path):
    import torch, torch.distributed as dist
    os.environ["MASTER_ADDR"] = "127.0.0.1"; os.environ["MASTER_PORT"] = str(args.port)
    device = torch.device(f"xpu:{rank}"); torch.xpu.set_device(device)
    dist.init_process_group("xccl", rank=rank, world_size=world)
    buf = torch.full((args.dim, args.dim), 0.001, dtype=torch.bfloat16, device=device)
    if args.busy == "triton":
        import triton, triton.language as tl
        @triton.jit
        def _busy_kernel(x_ptr, n, REPS: tl.constexpr, BLOCK: tl.constexpr):
            pid = tl.program_id(0)
            offs = pid * BLOCK + tl.arange(0, BLOCK)
            m = offs < n
            v = tl.load(x_ptr + offs, mask=m, other=0.0)
            for _ in range(REPS):
                v = v * 1.0001 + 0.5
            tl.store(x_ptr + offs, v, mask=m)
        tbuf = torch.zeros(args.dim * args.dim * 4, device=device, dtype=torch.float32)
        tn = tbuf.numel()
        def busy(k):
            for _ in range(k): _busy_kernel[(triton.cdiv(tn, 1024),)](tbuf, tn, REPS=64, BLOCK=1024)
    else:
        def busy(k):
            for _ in range(k): torch.matmul(buf, buf)
    x = torch.randn(1, 2560, device=device).to(torch.bfloat16)
    L = 48
    def seq(k, do_busy, do_ar):
        for _ in range(L):
            if do_busy: busy(k)
            if do_ar: dist.all_reduce(x)
    def wall(fn, n):
        for _ in range(5): fn()
        torch.xpu.synchronize(); dist.barrier(); ts = []
        for _ in range(n):
            torch.xpu.synchronize(); dist.barrier()
            t0 = time.perf_counter(); fn(); torch.xpu.synchronize(); ts.append(1e3 * (time.perf_counter() - t0))
        return dict(median_ms=round(statistics.median(ts), 3), min_ms=round(min(ts), 3), max_ms=round(max(ts), 3))
    res = {}
    for k in [int(v) for v in args.pad_iters.split(",")]:
        row = {}
        for name, db, da in (("busy", True, False), ("allreduce", False, True), ("busy_then_allreduce", True, True)):
            if name == "busy" and k == 0: continue
            fn = lambda: seq(k, db, da)
            row[f"eager_{name}"] = wall(fn, args.iters)
            s = torch.xpu.Stream()
            with torch.xpu.stream(s):
                for _ in range(3): fn()
            torch.xpu.synchronize(); dist.barrier()
            g = torch.xpu.XPUGraph()
            with torch.xpu.graph(g, stream=s):
                fn()
            torch.xpu.synchronize(); dist.barrier()
            row[f"graph_{name}"] = wall(lambda: g.replay(), args.iters)
        res[f"pad{k}"] = row
        if rank == 0: print(f"{args.busy} pad{k}", json.dumps(row), flush=True)
    dist.barrier()
    if rank == 0: json.dump(res, open(result_path, "w"), indent=1)
    dist.destroy_process_group()

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True); ap.add_argument("--iters", type=int, default=30)
    ap.add_argument("--pad-iters", default="0,1,3,6"); ap.add_argument("--port", type=int, default=29517)
    ap.add_argument("--world", type=int, default=4); ap.add_argument("--dim", type=int, default=2048); ap.add_argument("--busy", choices=("matmul","triton"), default="matmul")
    args = ap.parse_args(); refuse_active_model_server()
    import torch.multiprocessing as mp
    mp.set_start_method("spawn", force=True)
    procs = [mp.Process(target=worker, args=(r, args.world, args, args.out)) for r in range(args.world)]
    for p in procs: p.start()
    for p in procs: p.join()
    return max(p.exitcode for p in procs)

if __name__ == "__main__":
    raise SystemExit(main())

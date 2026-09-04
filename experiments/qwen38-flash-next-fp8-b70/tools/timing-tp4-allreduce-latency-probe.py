#!/usr/bin/env python3
"""Four-card XCCL all-reduce latency on B70s under the serving CCL environment.

Times (a) one [1,N] BF16 all-reduce, (b) one [2,N] all-reduce, (c) two [1,N]
all-reduces issued back to back synchronously (the row-wise exact path),
(d) two [1,N] all-reduces issued with async_op=True and then waited (a
candidate cheaper exact path). Per-call wall-clock on rank 0 with device
synchronizes; all ranks participate.

    timing-tp4-allreduce-latency-probe.py --out <json> [--iters 300] [--widths 2560,10240]
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
    res = {}
    for width in [int(w) for w in args.widths.split(",")]:
        x1 = torch.randn(1, width, device=device).to(torch.bfloat16)
        x2 = torch.randn(2, width, device=device).to(torch.bfloat16)
        def t(fn):
            for _ in range(30): fn()
            torch.xpu.synchronize(); dist.barrier()
            times = []
            for _ in range(args.iters):
                torch.xpu.synchronize(); t0 = time.perf_counter(); fn(); torch.xpu.synchronize(); times.append(1e3 * (time.perf_counter() - t0))
            return {"mean_ms": statistics.mean(times), "median_ms": statistics.median(times), "p90_ms": sorted(times)[int(0.9 * len(times))], "max_ms": max(times)}
        def single(): y = x1.clone(); dist.all_reduce(y)
        def batched(): y = x2.clone(); dist.all_reduce(y)
        def rowwise_sync():
            for i in range(2): y = x2[i:i+1].clone(); dist.all_reduce(y)
        def rowwise_async():
            ys = [x2[i:i+1].clone() for i in range(2)]
            hs = [dist.all_reduce(y, async_op=True) for y in ys]
            for h in hs: h.wait()
        res[str(width)] = {"single_1xN": t(single), "batched_2xN": t(batched), "rowwise_sync_2x1xN": t(rowwise_sync), "rowwise_async_2x1xN": t(rowwise_async)}
    dist.barrier()
    if rank == 0:
        json.dump(res, open(result_path, "w"))
    dist.destroy_process_group()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True); ap.add_argument("--iters", type=int, default=300)
    ap.add_argument("--widths", default="2560,10240"); ap.add_argument("--port", type=int, default=29523); ap.add_argument("--world", type=int, default=4)
    args = ap.parse_args(); refuse_active_model_server()
    import torch.multiprocessing as mp
    tmp = args.out + ".partial"
    mp.spawn(worker, args=(args.world, args, tmp), nprocs=args.world, join=True)
    res = json.load(open(tmp)); os.remove(tmp)
    ccl_env = {k: v for k, v in os.environ.items() if k.startswith(("CCL_", "FI_"))}
    json.dump({"schema_version": 1, "classification": "b70_tp4_xccl_allreduce_latency", "world": args.world, "iters": args.iters, "ccl_env": ccl_env, "results": res}, open(args.out, "w"), indent=2)
    for w, r in res.items():
        print(w, {k: round(v["median_ms"], 3) for k, v in r.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

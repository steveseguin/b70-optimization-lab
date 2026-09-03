#!/usr/bin/env python3
"""Row-count dependence of the TP4 XCCL all-reduce on four B70s.

The MTP1 verification step all-reduces [2, N] BF16 partial sums where the
MTP0 decode step all-reduces [1, N]. Runs four ranks (one per card) with the
serving CCL environment, all-reduces fixed random BF16 rows batched and one
row at a time, and reports whether the batched rows equal the single-row
results bit for bit. Also reports repeatability of each call.

    equivalence-tp4-allreduce-m2-vs-m1-probe.py --out <json> [--rows 2] [--width 2560]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys


def refuse_active_model_server() -> None:
    out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
    if any(("EngineCore" in l or "Worker_TP" in l or "vllm serve" in l) for l in out.splitlines()):
        sys.exit("refusing to run beside a model server")


def worker(rank: int, world: int, args, result_path: str) -> None:
    import torch
    import torch.distributed as dist
    os.environ["MASTER_ADDR"] = "127.0.0.1"
    os.environ["MASTER_PORT"] = str(args.port)
    device = torch.device(f"xpu:{rank}")
    torch.xpu.set_device(device)
    dist.init_process_group("xccl", rank=rank, world_size=world)
    g = torch.Generator(device="cpu").manual_seed(args.seed + rank)
    sha = lambda t: hashlib.sha256(t.contiguous().cpu().view(torch.int16).numpy().tobytes()).hexdigest()
    widths = [int(w) for w in args.widths.split(",")]
    rows_list = [int(m) for m in args.rows.split(",")]
    records = []
    for width in widths:
        for trial in range(args.trials):
            base = (torch.randn(max(rows_list), width, generator=g) * args.scale).to(torch.bfloat16).to(device)

            def allreduce(x):
                y = x.clone()
                dist.all_reduce(y)
                torch.xpu.synchronize()
                return y

            singles = torch.cat([allreduce(base[i:i + 1]) for i in range(max(rows_list))], dim=0)
            singles2 = torch.cat([allreduce(base[i:i + 1]) for i in range(max(rows_list))], dim=0)
            for m in rows_list:
                batched = allreduce(base[:m])
                batched2 = allreduce(base[:m])
                diff = (batched.float() - singles[:m].float()).abs()
                records.append({
                    "width": width, "rows": m, "trial": trial, "rank": rank,
                    "batched_repeatable": bool(torch.equal(batched, batched2)),
                    "single_repeatable": bool(torch.equal(singles, singles2)),
                    "batched_equals_singles": bool(torch.equal(batched, singles[:m])),
                    "rows_differing": [int(i) for i in range(m) if bool((diff[i] > 0).any())],
                    "elements_differing": int((diff > 0).sum()), "max_abs_diff": float(diff.max()),
                    "sha256_batched": sha(batched), "sha256_singles": sha(singles[:m]),
                })
    dist.barrier()
    with open(f"{result_path}.rank{rank}", "w") as f:
        json.dump(records, f)
    dist.destroy_process_group()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rows", default="1,2,3,4")
    ap.add_argument("--widths", default="2560,10240")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--seed", type=int, default=20260903)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--port", type=int, default=29517)
    ap.add_argument("--world", type=int, default=4)
    args = ap.parse_args()
    refuse_active_model_server()
    import torch.multiprocessing as mp
    tmp = args.out + ".partial"
    mp.spawn(worker, args=(args.world, args, tmp), nprocs=args.world, join=True)
    per_rank = {r: json.load(open(f"{tmp}.rank{r}")) for r in range(args.world)}
    for r in range(args.world):
        os.remove(f"{tmp}.rank{r}")
    ccl_env = {k: v for k, v in os.environ.items() if k.startswith(("CCL_", "FI_"))}
    summary = []
    for i, rec in enumerate(per_rank[0]):
        same_across_ranks = all(per_rank[r][i]["sha256_batched"] == rec["sha256_batched"] for r in range(args.world))
        summary.append({**{k: rec[k] for k in ("width", "rows", "trial", "batched_repeatable", "single_repeatable", "batched_equals_singles", "rows_differing", "elements_differing", "max_abs_diff")}, "ranks_agree": same_across_ranks})
    verdict = {(s["width"], s["rows"]): all(t["batched_equals_singles"] for t in summary if (t["width"], t["rows"]) == (s["width"], s["rows"])) for s in summary}
    result = {"schema_version": 1, "classification": "b70_tp4_xccl_allreduce_m_vs_m1_equivalence", "world": args.world,
              "ccl_env": ccl_env, "seed": args.seed, "trials": args.trials, "scale": args.scale,
              "verdict_by_width_rows": [{"width": w, "rows": m, "batched_equals_singles_all_trials": v} for (w, m), v in sorted(verdict.items())],
              "records_rank0": summary, "records_all_ranks": per_rank}
    with open(args.out, "w") as f:
        json.dump(result, f, indent=2)
    for v in result["verdict_by_width_rows"]:
        print(json.dumps(v))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

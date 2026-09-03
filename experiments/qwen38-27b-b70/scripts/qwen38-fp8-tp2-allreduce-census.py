#!/usr/bin/env python3
"""Two-rank XCCL all-reduce census (R151d): for FP16 [rows,5120] messages at the
row counts a TP2 step produces (decode 1..128 rows, prefill up to 2048), check that
the reduced value equals the correctly rounded fp16 sum, that row i's result does
not depend on how many rows share the message, and that repeats are identical."""
import json, os, sys
import torch, torch.distributed as dist

ROWS = [1, 2, 4, 8, 16, 24, 32, 33, 48, 64, 96, 128, 256, 480, 512, 900, 1024, 2048]


def main():
    lr = int(os.environ["LOCAL_RANK"]); rank = int(os.environ["RANK"]); torch.xpu.set_device(lr)
    dist.init_process_group("xccl"); dev = torch.device(f"xpu:{lr}")
    g = torch.Generator(device="cpu"); g.manual_seed(20260902)
    full = [torch.randn((2048, 5120), generator=g, dtype=torch.float32) * 3 for _ in range(2)]
    mine = full[rank].to(torch.float16).to(dev); other = full[1 - rank].to(torch.float16).to(dev)
    exact = (mine.float() + other.float()).to(torch.float16)  # correctly rounded fp16 sum
    naive = mine + other
    ref_rows = {}
    rows = []
    for n in ROWS:
        x = mine[:n].clone(); dist.all_reduce(x); torch.xpu.synchronize()
        x2 = mine[:n].clone(); dist.all_reduce(x2); torch.xpu.synchronize()
        eq_exact = torch.equal(x, exact[:n]); eq_naive = torch.equal(x, naive[:n]); rep = torch.equal(x, x2)
        prefix_ok = all(torch.equal(x[:k], ref_rows[k]) for k in ref_rows if k < n)
        ref_rows[n] = x.clone()
        md = float((x.float() - exact[:n].float()).abs().max())
        row = {"rows": n, "bytes": n * 5120 * 2, "equals_correctly_rounded_sum": eq_exact, "equals_fp16_add": eq_naive, "repeat_equal": rep, "prefix_equal_smaller_messages": prefix_ok, "max_abs_diff_vs_exact": md}
        rows.append(row)
        if rank == 0: print(row, flush=True)
    if rank == 0:
        out = {"rows": rows, "all_exact": all(r["equals_correctly_rounded_sum"] for r in rows), "all_repeat": all(r["repeat_equal"] for r in rows), "all_prefix_invariant": all(r["prefix_equal_smaller_messages"] for r in rows)}
        open(sys.argv[1], "w").write(json.dumps(out, indent=1)); print({k: out[k] for k in ("all_exact", "all_repeat", "all_prefix_invariant")}, flush=True)
    dist.barrier(device_ids=[lr]); dist.destroy_process_group()


if __name__ == "__main__":
    main()

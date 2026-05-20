import os
import time

import torch
import torch.distributed as dist


def main() -> None:
    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    torch.xpu.set_device(local_rank)
    dist.init_process_group("xccl")

    tokens = int(os.environ.get("MINIMAX_QK_IPC_TOKENS", "1"))
    iters = int(os.environ.get("MINIMAX_QK_IPC_ITERS", "200"))
    warmup = int(os.environ.get("MINIMAX_QK_IPC_WARMUP", "20"))
    synchronize_each = (
        os.environ.get("MINIMAX_QK_IPC_SYNC_EACH", "1") == "1"
    )

    x = torch.ones((tokens, 2), device="xpu", dtype=torch.float32) * (
        rank + 1
    )
    for _ in range(warmup):
        y = x.clone()
        dist.all_reduce(y)
        if synchronize_each:
            torch.xpu.synchronize()

    dist.barrier()
    torch.xpu.synchronize()
    start = time.perf_counter()
    for _ in range(iters):
        y = x.clone()
        dist.all_reduce(y)
        if synchronize_each:
            torch.xpu.synchronize()
    torch.xpu.synchronize()
    dist.barrier()
    elapsed = time.perf_counter() - start

    if rank == 0:
        print(
            "bench "
            f"tokens={tokens} iters={iters} warmup={warmup} "
            f"sync_each={synchronize_each} "
            f"elapsed_s={elapsed:.6f} "
            f"ms_per_iter={elapsed * 1000 / iters:.6f}",
            flush=True,
        )

    dist.destroy_process_group()


if __name__ == "__main__":
    main()

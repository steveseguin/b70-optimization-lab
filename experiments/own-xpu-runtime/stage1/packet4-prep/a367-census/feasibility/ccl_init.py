#!/usr/bin/env python3
"""Four spawned XCCL ranks. Parent NEVER uses ProcessContext.join (kills peers)."""
import os
from pathlib import Path
import sys
import time
import traceback
from common import Stages, arguments, finished, ready_go, wait_file


def rendezvous(args, rank, name):
    (args.output / f'{name}-{rank}').touch()
    for peer in range(4):
        wait_file(args.output / f'{name}-{peer}', args.output)


def worker(rank, args, store_path):
    stages = Stages(args.output, rank)
    initialized = False
    try:
        stages.mark('import_torch')
        import torch
        import torch.distributed as dist
        if not torch.__version__.startswith('2.11.') or not dist.is_xccl_available():
            raise RuntimeError('A367 torch 2.11 with XCCL required; no backend fallback')
        os.environ.update(LOCAL_RANK=str(rank), RANK=str(rank), WORLD_SIZE='4', LOCAL_WORLD_SIZE='4')
        torch.set_num_threads(1)
        stages.mark('device_setup')
        torch.xpu.set_device(rank)
        small = torch.ones(4096 // 4, dtype=torch.float32, device=f'xpu:{rank}')
        large = torch.ones(64 * 1024 * 1024 // 4, dtype=torch.float32, device=f'xpu:{rank}')
        torch.xpu.synchronize()
        stages.mark('before_init_barrier')
        rendezvous(args, rank, 'before-init')
        stages.mark('init_process_group')
        # Exact default A367 branch: XPUPlatform.dist_backend == xccl;
        # multiproc_executor selects file://; parallel_state creates FileStore
        # and passes store with init_method=None. No shortened PG timeout.
        store = dist.FileStore(str(store_path), 4)
        dist.init_process_group(backend='xccl', init_method=None, store=store,
                                world_size=4, rank=rank, timeout=None)
        initialized = True
        stages.mark('init_complete')
        rendezvous(args, rank, 'before-small')
        stages.mark('all_reduce_4k')
        # Force lazy communicator initialization WHILE tracing is still paused.
        dist.all_reduce(small)
        torch.xpu.synchronize()
        stages.mark('all_reduce_4k_complete')
        ready_go(args, stages)
        rendezvous(args, rank, 'before-large')
        stages.mark('all_reduce_64m')
        dist.all_reduce(large)
        torch.xpu.synchronize()
        stages.mark('all_reduce_64m_complete')
        # Fixed inputs sum to four. Reads are outside collectives/capture.
        if not torch.equal(small, torch.full_like(small, 4)) or not torch.equal(large, torch.full_like(large, 4)):
            raise RuntimeError('all_reduce result is not four on every element')
        stages.mark('before_destroy_barrier')
        rendezvous(args, rank, 'before-destroy')
        stages.mark('destroy_process_group')
        dist.destroy_process_group()
        initialized = False
        stages.mark('destroy_complete')
        finished(args, stages)
    except BaseException:
        (args.output / 'abort').touch()
        stages.mark('error')
        traceback.print_exc()
        if initialized:
            stages.mark('error_destroy_process_group')
            dist.destroy_process_group()  # May wait; never kill peers to escape.
        raise
    finally:
        stages.closed.set()


def main():
    args = arguments(__doc__)
    # FileStore must be on local ext4, just like the A367 scratch placement.
    scratch = Path('/home/steve/.cache/a367-tracefeas') / args.output.parent.name / args.output.name
    scratch.mkdir(parents=True, exist_ok=False)
    import torch.multiprocessing as mp
    context = mp.spawn(worker, args=(args, scratch / 'rendezvous'), nprocs=4, join=False)
    # ProcessContext.join terminates remaining ranks after any rank failure.
    # Poll individual Process objects instead; each rank owns its own cleanup.
    while any(p.exitcode is None for p in context.processes):
        for process in context.processes:
            process.join(timeout=.1)
            if process.exitcode not in (None, 0):
                (args.output / 'abort').touch()
        time.sleep(.1)
    return 0 if all(p.exitcode == 0 for p in context.processes) else 1


if __name__ == '__main__':
    sys.exit(main())

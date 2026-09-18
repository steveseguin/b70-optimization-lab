"""Two-rank allreduce as one allgather plus a fixed-order local add (research overlay). Enabled with B70_ALLGATHER_ALLREDUCE=1.

On two tensor-parallel ranks a sum-allreduce is exactly `x_rank0 + x_rank1`. The stock XPU communicator issues
oneCCL's ring allreduce (reduce-scatter + allgather, ~223 us per call on this host for decode-size tensors, 134 calls
per decode step). This overlay replaces `XpuCommunicator.all_reduce` for world size 2 with a single
`all_gather_into_tensor` (~116 us) followed by `gathered[0] + gathered[1]` on each rank. The add is elementwise in a
fixed rank order, so both ranks compute bit-identical results, and the value is the same sum of the same two
half-products the ring kernel computes (floating-point addition of two operands is commutative). Any other world size
falls through to the original method. Nothing changes for the no-MTP reference, which runs under the same overlay.
"""
import os


def register():
    if os.environ.get('B70_ALLGATHER_ALLREDUCE', '').strip() != '1':
        return
    import torch
    import torch.distributed as dist
    from vllm.logger import init_logger
    from vllm.distributed.device_communicators import xpu_communicator as module

    logger = init_logger('b70_allgather_allreduce')
    cls = module.XpuCommunicator
    if getattr(cls, '_b70_allgather_allreduce', False):
        return
    original = cls.all_reduce
    counter = {'calls': 0}

    def all_reduce(self, input_):
        if self.world_size != 2:
            return original(self, input_)
        x = input_.contiguous()
        gathered = torch.empty((2,) + tuple(x.shape), dtype=x.dtype, device=x.device)
        dist.all_gather_into_tensor(gathered, x, group=self.device_group)
        if counter['calls'] == 0:
            logger.warning('b70_allgather_allreduce: two-rank allreduce replaced by allgather + fixed-order add (first call shape %s %s)',
                           tuple(x.shape), x.dtype)
        counter['calls'] += 1
        return gathered[0] + gathered[1]

    cls.all_reduce = all_reduce
    cls._b70_allgather_allreduce = True
    logger.warning('b70_allgather_allreduce: installed on XpuCommunicator')

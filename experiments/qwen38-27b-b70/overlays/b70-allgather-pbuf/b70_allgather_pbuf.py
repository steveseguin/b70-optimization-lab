"""Two-rank allreduce as one allgather + fixed-order add, with a persistent gather buffer per decode shape (research overlay).

Enabled with B70_ALLGATHER_PBUF=1. It is the shipped `b70_allgather_allreduce` overlay with one change: the
`(2,) + shape` gather buffer is allocated once per (shape, dtype, device) and reused, instead of `torch.empty` on every
call. A steady depth-5 decode step issues 155 collectives in four shapes (6x5120 and 1x5120 dominate), so this removes
about 144 device allocations per step. Candidate (e)'s "cheaper sibling" in notes/2026-09-18-two-card-exchange-fusion-memo.md.

Arithmetic: unchanged by construction. The same `all_gather_into_tensor` fills the same layout and the same
`gathered[0] + gathered[1]` produces a NEW tensor, so nothing downstream ever aliases the buffer.

Why reuse is ordered correctly: the next gather can only start once its input `x` exists, and `x` is produced by
kernels that were queued after the previous call's add (the add's result feeds the residual/norm that leads to the
next `x`). So the previous reader of the buffer has finished before the next writer starts, on the same assumptions
the fresh-buffer version already relies on to read a completed `x`. The exactness gates are the proof, not this
paragraph: any race shows up as a non-identical token.

Only small tensors are kept (rows <= B70_ALLGATHER_PBUF_MAX_ROWS, default 64): prefill chunks come in many lengths and
would otherwise pin a buffer per length. Larger inputs take the fresh-buffer path, identical to the shipped overlay.
Do not enable together with B70_ALLGATHER_ALLREDUCE=1; this overlay refuses to install over it.
"""
import os


def register():
    if os.environ.get('B70_ALLGATHER_PBUF', '').strip() != '1':
        return
    import torch
    import torch.distributed as dist
    from vllm.logger import init_logger
    from vllm.distributed.device_communicators import xpu_communicator as module

    logger = init_logger('b70_allgather_pbuf')
    cls = module.XpuCommunicator
    if getattr(cls, '_b70_allgather_pbuf', False):
        return
    if getattr(cls, '_b70_allgather_allreduce', False) or os.environ.get('B70_ALLGATHER_ALLREDUCE', '').strip() == '1':
        raise RuntimeError('b70_allgather_pbuf: B70_ALLGATHER_ALLREDUCE=1 is also set; enable exactly one of the two overlays')
    original = cls.all_reduce
    max_rows = int(os.environ.get('B70_ALLGATHER_PBUF_MAX_ROWS', '64'))
    buffers = {}
    counter = {'calls': 0, 'reused': 0, 'fresh': 0}

    def all_reduce(self, input_):
        if self.world_size != 2:
            return original(self, input_)
        x = input_.contiguous()
        shape = tuple(x.shape)
        rows = shape[0] if len(shape) > 1 else 1
        if rows <= max_rows:
            key = (shape, x.dtype, x.device)
            gathered = buffers.get(key)
            if gathered is None:
                gathered = buffers[key] = torch.empty((2,) + shape, dtype=x.dtype, device=x.device)
                logger.warning('b70_allgather_pbuf: persistent gather buffer %d for shape %s %s', len(buffers), shape, x.dtype)
            else:
                counter['reused'] += 1
        else:
            gathered = torch.empty((2,) + shape, dtype=x.dtype, device=x.device)
            counter['fresh'] += 1
        dist.all_gather_into_tensor(gathered, x, group=self.device_group)
        counter['calls'] += 1
        if counter['calls'] in (1, 10000, 100000):
            logger.warning('b70_allgather_pbuf: %d calls, %d reused a buffer, %d fresh (large), %d shapes kept',
                           counter['calls'], counter['reused'], counter['fresh'], len(buffers))
        return gathered[0] + gathered[1]

    cls.all_reduce = all_reduce
    cls._b70_allgather_pbuf = True
    logger.warning('b70_allgather_pbuf: installed on XpuCommunicator (persistent buffers for <= %d rows)', max_rows)

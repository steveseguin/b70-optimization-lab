"""Move large tensors between host and card in pieces while the model loads. On when installed; B70_CHUNKED_UPLOAD=0 turns it off.

Why (notes/2026-10-04-gpu-fault-mtp-start.md): every model-load GPU fault on this host is the copy engine reading a
temporary mapping of host memory at GPU address 0x800400200000 that is not mapped at that instant. Measured on the
R310 image with the runtime's own allocation log: a CPU-to-card copy of 256 MiB or less goes through the runtime's
staging buffers and creates no such mapping; a copy of 512 MiB or more creates one (EXTERNAL_HOST_PTR). The only
tensors that large in this model are the 1.27 GB embedding and output-layer weights, eight uploads per two-card start.

The same mapping is made for a large copy from the card back to host memory (the one-card lane moves its 2.5 GB
embedding to host memory that way), so both directions are covered.

What this does: while `GPUModelRunner.load_model` runs, `Tensor.copy_` and `Tensor.to` between CPU and the card are done in
pieces of B70_CHUNKED_UPLOAD_CHUNK_MIB (default 128) when the tensor is larger than B70_CHUNKED_UPLOAD_OVER_MIB
(default 256). The same bytes arrive; only the route changes. Both methods are restored when the load ends, so
serving and compiled code never see the wrappers. A copy that also changes the number type (the checkpoint stores
these weights in another 16-bit format than the server runs) is converted piece by piece by the same method, element
by element as before. Anything that is not a plain same-shape, contiguous CPU-to-card copy goes to the original
method untouched and is named in the load log.
"""
import os

MIB = 1024 * 1024


def pieces(count, element_size, chunk_bytes):
    step = max(1, chunk_bytes // element_size)
    return [(start, min(start + step, count)) for start in range(0, count, step)]


def eligible(dst, src, over_bytes, card):
    """A large CPU-to-card copy of the same shape. The dtypes may differ: each piece then converts exactly as the
    whole copy would, element by element."""
    return ({src.device.type, dst.device.type} == {'cpu', card} and src.shape == dst.shape
            and src.is_contiguous() and dst.is_contiguous() and not src.is_sparse and src.layout == dst.layout
            and dst.numel() * dst.element_size() > over_bytes)


def skipped(dst, src, over_bytes, card):
    """Why a large CPU-to-card copy was left to the original method (for the load log); '' if it is not one."""
    if not hasattr(src, 'device') or {src.device.type, dst.device.type} != {'cpu', card}:
        return ''
    if max(src.numel() * src.element_size(), dst.numel() * dst.element_size()) <= over_bytes:
        return ''
    return (f'shape {tuple(src.shape)} -> {tuple(dst.shape)}, {src.dtype} -> {dst.dtype}, '
            f'contiguous {src.is_contiguous()}/{dst.is_contiguous()}')


def chunked_copy(dst, src, chunk_bytes, copy):
    flat_dst, flat_src = dst.view(-1), src.view(-1)
    for start, stop in pieces(flat_src.numel(), max(src.element_size(), dst.element_size()), chunk_bytes):
        copy(flat_dst[start:stop], flat_src[start:stop])
    return dst


def wrap_copy(original, over_bytes, chunk_bytes, card='xpu', counter=None, missed=None):
    def copy_(self, src, *args, **kwargs):
        if hasattr(src, 'device') and eligible(self, src, over_bytes, card):
            if counter is not None:
                counter.append(self.numel() * self.element_size())
            return chunked_copy(self, src, chunk_bytes, original)
        if missed is not None:
            why = skipped(self, src, over_bytes, card)
            if why:
                missed.append('copy_ ' + why)
        return original(self, src, *args, **kwargs)
    return copy_


def wrap_to(original, copy, empty, device_of, over_bytes, chunk_bytes, card='xpu', counter=None, missed=None):
    """`Tensor.to(device)` with only a device (positional or keyword) and a large contiguous tensor crossing between
    host and card, in either direction."""
    def to(self, *args, **kwargs):
        target = None
        if len(args) == 1 and not kwargs:
            target = device_of(args[0])
        elif not args and set(kwargs) == {'device'}:
            target = device_of(kwargs['device'])
        if (target is not None and {target.type, self.device.type} == {'cpu', card} and self.is_contiguous()
                and not self.is_sparse and self.numel() * self.element_size() > over_bytes):
            out = empty(self.shape, dtype=self.dtype, device=target)
            if counter is not None:
                counter.append(self.numel() * self.element_size())
            return chunked_copy(out, self, chunk_bytes, copy)
        if (missed is not None and self.numel() * self.element_size() > over_bytes and target is not None
                and {target.type, self.device.type} == {'cpu', card}):
            missed.append(f'to shape {tuple(self.shape)} {self.dtype} args {[str(a)[:40] for a in args]} {sorted(kwargs)}')
        return original(self, *args, **kwargs)
    return to


def register():
    if os.environ.get('B70_CHUNKED_UPLOAD', '1').strip() != '1':  # on wherever the overlay is installed; 0 turns it off
        return
    over = int(os.environ.get('B70_CHUNKED_UPLOAD_OVER_MIB', '256')) * MIB
    chunk = int(os.environ.get('B70_CHUNKED_UPLOAD_CHUNK_MIB', '128')) * MIB
    import torch
    from vllm.logger import init_logger
    from vllm.v1.worker import gpu_model_runner as module

    logger = init_logger('b70_chunked_upload')
    cls = module.GPUModelRunner
    if getattr(cls, '_b70_chunked_upload', False):
        return
    original_load = cls.load_model

    def device_of(value):
        if isinstance(value, torch.device):
            return value
        if isinstance(value, str):
            return torch.device(value)
        return None

    def load_model(self, *args, **kwargs):
        copy, to, done, missed = torch.Tensor.copy_, torch.Tensor.to, [], []
        torch.Tensor.copy_ = wrap_copy(copy, over, chunk, counter=done, missed=missed)
        torch.Tensor.to = wrap_to(to, copy, torch.empty, device_of, over, chunk, counter=done, missed=missed)
        try:
            return original_load(self, *args, **kwargs)
        finally:
            torch.Tensor.copy_, torch.Tensor.to = copy, to
            logger.warning('b70_chunked_upload: %d transfers over %d MiB went between host and card in %d MiB pieces (%.2f GiB)',
                           len(done), over // MIB, chunk // MIB, sum(done) / 2**30)
            for line in missed[:20]:
                logger.warning('b70_chunked_upload: large host/card transfer left to the original method: %s', line)

    cls.load_model = load_model
    cls._b70_chunked_upload = True

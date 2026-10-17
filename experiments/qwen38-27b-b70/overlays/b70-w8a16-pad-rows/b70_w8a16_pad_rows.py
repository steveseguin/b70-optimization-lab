"""Few-row FP8 W8A16 GEMMs of listed shapes run padded in the faster row class (research overlay, B70_W8A16_PAD_ROWS=1).

Why (notes/2026-10-17-fp8-step-floor.md): oneDNN's W8A16 matmul (`_xpu_C::fp8_gemm_w8a16`) picks its kernel by the
number of rows. For the MLP down projection at TP2 (K 8704, N 5120) the 10-04 census
(data/2026-10-04-fp8-multiuser/census/census.json) times 215 us at 1-4 rows, 104 us at 5 and 76 us from 6 rows up,
while the other five shapes are flat. Each drafter pass runs that GEMM with one row, so depth 5 pays about
5 x 140 us = 0.7 ms per step for nothing; a no-drafting decode pays it in all 64 layers (about 9 ms per token).

What it does: for a call with fewer than B70_W8A16_PAD_ROWS_TO rows (default 6) whose weight shape is listed in
B70_W8A16_PAD_ROWS_SHAPES ("KxN,KxN", default "8704x5120"), the activation is padded with zero rows to that count,
the same oneDNN op runs, and the real rows are returned. Larger calls and other shapes are untouched.

Why the answers cannot change: the census found this shape row-invariant across every row count from 1 to 512 (row r
of an M-row call bit-identical to row r of any other), real rows independent of what the padding rows hold, and
repeat-deterministic. That census was on the R310 environment (torch 2.13, the same oneDNN matmul source as R314);
a census on R314 at the server's own scale layout is required before a timing claim
(scripts/census-w8a16-pad-rows.py).

The padded call is a vLLM custom op (`torch.ops.vllm.b70_w8a16_padded`), so the compiled graph sees one opaque op
whose row count is only read at run time; no graph is specialised on it.
"""
import os

DEFAULT_SHAPES = '8704x5120'


def parse_shapes(text):
    shapes = set()
    for item in (text or '').split(','):
        item = item.strip().lower()
        if not item:
            continue
        k, n = item.split('x')
        shapes.add((int(k), int(n)))
    return shapes


def padded(a, pad_to, gemm):
    """gemm(a_padded) for a 2-D activation with fewer than pad_to rows, rows [:m] returned; else gemm(a)."""
    import torch

    m = a.shape[0]
    if m >= pad_to or m == 0:
        return gemm(a)
    a_padded = torch.cat([a, a.new_zeros((pad_to - m, a.shape[1]))], dim=0)
    return gemm(a_padded)[:m]


def wants(shapes, use_w8a16, a, b):
    """b is the [N, K] weight as apply_block_scaled_mm receives it."""
    return bool(use_w8a16) and a.dim() == 2 and (int(b.shape[1]), int(b.shape[0])) in shapes


def install(kernel_cls, shapes, pad_to, op):
    if getattr(kernel_cls, '_b70_w8a16_pad_rows', False):
        return False
    original = kernel_cls.apply_block_scaled_mm

    def apply_block_scaled_mm(self, A, B, As, Bs):
        if wants(shapes, getattr(self, '_use_w8a16', False), A, B):
            return op(A, B.t(), Bs.t(), pad_to)
        return original(self, A, B, As, Bs)

    apply_block_scaled_mm.__doc__ = original.__doc__
    kernel_cls.apply_block_scaled_mm = apply_block_scaled_mm
    kernel_cls._b70_w8a16_pad_rows = True
    return True


def register():
    if os.environ.get('B70_W8A16_PAD_ROWS', '').strip() != '1':
        return
    import torch
    from vllm.logger import init_logger

    logger = init_logger('b70_w8a16_pad_rows')
    if not hasattr(torch.ops._xpu_C, 'fp8_gemm_w8a16'):
        logger.warning('b70_w8a16_pad_rows: no _xpu_C::fp8_gemm_w8a16 in this process; not installed')
        return
    shapes = parse_shapes(os.environ.get('B70_W8A16_PAD_ROWS_SHAPES', DEFAULT_SHAPES))
    pad_to = int(os.environ.get('B70_W8A16_PAD_ROWS_TO', '6') or 6)
    from vllm.model_executor.kernels.linear.scaled_mm import xpu as module
    from vllm.utils.torch_utils import direct_register_custom_op

    if not hasattr(torch.ops.vllm, 'b70_w8a16_padded'):
        def b70_w8a16_padded(a: torch.Tensor, q_weight: torch.Tensor, weight_scale: torch.Tensor,
                             pad_to: int) -> torch.Tensor:
            return padded(a, pad_to, lambda x: torch.ops._xpu_C.fp8_gemm_w8a16(x, q_weight, weight_scale, None))

        def b70_w8a16_padded_fake(a: torch.Tensor, q_weight: torch.Tensor, weight_scale: torch.Tensor,
                                  pad_to: int) -> torch.Tensor:
            return torch.empty((a.shape[0], q_weight.shape[1]), dtype=a.dtype, device=a.device)

        direct_register_custom_op('b70_w8a16_padded', b70_w8a16_padded, fake_impl=b70_w8a16_padded_fake)
    if install(module.XPUFp8BlockScaledMMKernel, shapes, pad_to, torch.ops.vllm.b70_w8a16_padded):
        logger.warning('b70_w8a16_pad_rows 0.1.0: installed on XPUFp8BlockScaledMMKernel.apply_block_scaled_mm '
                       '(calls under %d rows padded for K x N in %s)', pad_to,
                       ', '.join('%dx%d' % s for s in sorted(shapes)))

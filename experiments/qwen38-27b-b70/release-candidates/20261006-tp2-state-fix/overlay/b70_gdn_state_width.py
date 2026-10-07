"""Give the GDN speculative kernels every previous-step state slot (unqualified TP2 release candidate, B70_GDN_STATE_WIDTH=1).

REQUIRES the r314 kernel library (patches/vllm-xpu-kernels-gdn-spec-state-row-stride-r314-20261004.patch).
An old interface can reject multirow narrow views as noncontiguous, but a single-row narrow view can still be
contiguous despite its wider row stride. Contiguity rejection is NOT a kernel identity gate: the candidate
launcher must independently verify the required R314 kernel/library identity before serving requests.

The defect (vLLM 0.29 XPU, R310/R313 images). After a verify step accepts `a` tokens of a request, the next step's
SSM spec kernel reads that request's starting state from column a - 1 of `spec_state_indices_tensor`
(csrc/xpu/gdn_attn/gated_delta_rule.hpp:392-395, no bound check). The metadata builder slices the tensor to the
widest request of the NEXT step: `block_table_tensor[spec_mask, :active_spec_width]` (vllm/v1/attention/backends/
gdn_attn.py:338-340 and 359-361). When the next step is narrower than `a`, the read lands in the next request's
row or past the tensor: a wrong starting state. Reached by long copy drafts followed by a normal draft, and in the
stock engine when max_model_len narrows the last step after a well-accepted one (R307 "Defect 1", 2026-09-13).

Why not simply make the tensor wider: the kernels take the number of tokens per request in this step from the
tensor's width (gdn_attn_interface.cpp:96/:119, gated_delta_rule.hpp:705, causal_conv1d.hpp:1039). They address
elements through stride(0) though, so a [n, width] VIEW of [n, num_spec + 1] block-table rows keeps the width
(= tokens per request, every check unchanged) and makes columns up to num_spec readable. r314 only relaxes the
interface's is_contiguous() check to "rows contiguous".

What this overlay does, only when a spec step is narrower than num_spec + 1 (the block table row's slot count):
  * GDNAttentionMetadataBuilder.build: the returned `spec_state_indices_tensor` becomes
    `block_table_tensor[spec_mask, :num_spec + 1][:, :width]` -- same shape, same values, row stride num_spec + 1.
    (With full CUDA graphs the stock tensor is already a [:batch, :width] view of the persistent
    [max_bs, num_spec + 1] buffer; the overlay fills that buffer's remaining columns from the same block-table rows.)
  * vllm/_xpu_ops.py grouped path (more than VLLM_XPU_GDN_SPEC_GROUP spec requests, or VLLM_XPU_GDN_SPLIT_MIXED=1
    with prefills in the step): `spec_state_indices_tensor[s0:s1].contiguous()` would copy only `width` columns, so
    it becomes `spec_state_indices_tensor[s0:s1]`. For a contiguous tensor `.contiguous()` returns the tensor
    itself, so this edit is a no-op for every step the builder leaves alone.
Steps already at full width are returned untouched (same tensor object). The exact largest `num_accepted_tokens`
is not known on the host without a device sync (under async scheduling the CPU copy is 1 and the GPU corrects it,
gpu_model_runner.py:2153-2157 / 2167-2184), so the overlay exposes all num_spec + 1 slots; any `a` is <= num_spec + 1.

Why results are identical where the slice was already wide enough (every a <= width): the kernels read element
[n, c] at n * stride(0) + c, which is the same value for every c < width in both layouts; the starting-state read is
column a - 1 < width; the SSM writes go to columns t < size(1) only (gated_delta_rule.hpp:411 and :510-511); the conv
kernel uses column 0 only (causal_conv1d.hpp:681) and its row range comes from num_accepted_tokens and size(1). No
other XPU consumer reads the tensor (qwen_gdn_linear_attn.forward_xpu -> torch.ops.vllm.gdn_attention_core_xpu ->
_xpu_ops._gdn_attention_core_xpu_impl), and `active_spec_width` is used only inside build().
"""
import inspect
import os
import textwrap

CANDIDATE = '20261006-tp2-state-fix'

GROUP_ANCHOR = 'spec_state_indices_tensor[s0:s1].contiguous()'
GROUP_REPLACEMENT = 'spec_state_indices_tensor[s0:s1]'


def full_width(num_spec, block_table):
    """Columns the kernels may need: one slot per verify row of the widest possible step."""
    full = int(num_spec) + 1
    if full < 2 or block_table.dim() != 2 or int(block_table.shape[1]) < full:
        raise RuntimeError('b70_gdn_state_width: missing full speculative state slots')
    return full


def widen(builder, md, block_table, spec_mask_cpu, null_block_id):
    """Keep the active width while exposing every previous-step slot; reject unsupported layouts.

    CPU metadata only: this does not read accepted counts back from the device.
    Non-speculative steps are unchanged. Speculative steps must satisfy the pinned contract.
    """
    if not md.num_spec_decodes:
        return 'unchanged'
    sst = md.spec_state_indices_tensor
    if sst is None or sst.dim() != 2 or spec_mask_cpu is None:
        raise RuntimeError('b70_gdn_state_width: invalid speculative metadata')
    width, n = int(sst.shape[1]), int(md.num_spec_decodes)
    full = full_width(builder.num_spec, block_table)
    if n < 1 or width < 1 or width > full or int(sst.shape[0]) < n:
        raise RuntimeError('b70_gdn_state_width: invalid speculative dimensions')
    if spec_mask_cpu.dim() != 1 or int(spec_mask_cpu.shape[0]) != int(block_table.shape[0]):
        raise RuntimeError('b70_gdn_state_width: invalid speculative mask')
    rows = block_table[spec_mask_cpu, :full]
    if int(rows.shape[0]) != n or rows.dtype != sst.dtype or rows.device != sst.device:
        raise RuntimeError('b70_gdn_state_width: incompatible selected state rows')
    if width == full:
        return 'unchanged'
    buf = getattr(builder, 'spec_state_indices_tensor', None)
    if (buf is not None and sst.numel() and buf.numel()
            and sst.untyped_storage().data_ptr() == buf.untyped_storage().data_ptr()):
        # Pinned full-graph layout: a leading [:batch, :width] view of the persistent buffer.
        if (buf.dim() != 2 or sst.stride(1) != 1 or buf.stride(1) != 1
                or sst.stride(0) != buf.stride(0) or int(sst.stride(0)) < full
                or full > int(buf.shape[1]) or int(sst.shape[0]) > int(buf.shape[0])
                or sst.storage_offset() != buf.storage_offset()):
            raise RuntimeError('b70_gdn_state_width: unsupported graph state layout')
        buf[:n, width:full].copy_(rows[:, width:], non_blocking=True)
        buf[n:int(sst.shape[0]), width:full].fill_(null_block_id)
        return 'graph-buffer'
    if int(sst.shape[0]) != n:
        raise RuntimeError('b70_gdn_state_width: unsupported padded state layout')
    md.spec_state_indices_tensor = rows[:, :width]
    return 'view'


def wrap_build(original, gdn):
    def build(self, common_prefix_len, common_attn_metadata, num_accepted_tokens=None,
              num_decode_draft_tokens_cpu=None, fast_build=False):
        md = original(self, common_prefix_len, common_attn_metadata, num_accepted_tokens,
                      num_decode_draft_tokens_cpu, fast_build)
        sst = getattr(md, 'spec_state_indices_tensor', None)
        if not getattr(md, 'num_spec_decodes', 0):
            return md
        if sst is None or sst.dim() != 2 or num_decode_draft_tokens_cpu is None:
            raise RuntimeError('b70_gdn_state_width: invalid speculative builder result')
        width = int(sst.shape[1])
        full = int(self.num_spec) + 1
        if width < 1 or width > full or int(sst.shape[0]) < int(md.num_spec_decodes):
            raise RuntimeError('b70_gdn_state_width: invalid speculative builder dimensions')
        if width == full:
            if sst.stride(1) != 1 or sst.stride(0) < full:
                raise RuntimeError('b70_gdn_state_width: unsupported full-width state layout')
            return md
        m = common_attn_metadata
        block_table = gdn.mamba_get_block_table_tensor(
            m.block_table_tensor, m.seq_lens, self.kv_cache_spec, self.vllm_config.cache_config.mamba_cache_mode)
        widen(self, md, block_table, num_decode_draft_tokens_cpu >= 0, gdn.NULL_BLOCK_ID)   # gdn_attn.py:236
        return md
    build._b70_gdn_state_width = True
    return build


def patch_group_path(module):
    """Drop the width-truncating `.contiguous()` in the grouped spec path of _gdn_attention_core_xpu_impl.

    The registered custom op holds this function object (eager_break_during_capture wrapper), so its code object
    is replaced in place. Returns False (and changes nothing) if the anchor is not exactly once in the source."""
    fn = module._gdn_attention_core_xpu_impl
    if getattr(fn, '_b70_gdn_state_width', False):
        if getattr(fn, '_b70_state_width_candidate', None) != CANDIDATE:
            raise RuntimeError('b70_gdn_state_width: another overlay already patched the grouped path')
        return True
    src = textwrap.dedent(inspect.getsource(fn))
    if src.count(GROUP_ANCHOR) != 1:
        return False
    namespace = {}
    exec(compile(src.replace(GROUP_ANCHOR, GROUP_REPLACEMENT), inspect.getsourcefile(fn) or '<b70>', 'exec'),
         module.__dict__, namespace)
    new = namespace[fn.__name__]
    if new.__code__.co_freevars != fn.__code__.co_freevars:
        return False
    fn.__code__ = new.__code__
    fn._b70_gdn_state_width = True
    fn._b70_state_width_candidate = CANDIDATE
    return True


def register():
    if os.environ.get('B70_GDN_STATE_WIDTH') != '1':
        return
    from vllm.logger import init_logger
    from vllm.v1.attention.backends import gdn_attn as gdn

    logger = init_logger('b70_gdn_state_width')
    cls = gdn.GDNAttentionMetadataBuilder
    if getattr(cls, '_b70_gdn_state_width', False):
        if getattr(cls, '_b70_state_width_candidate', None) != CANDIDATE:
            raise RuntimeError('b70_gdn_state_width: another overlay already patched the builder')
        return
    expected = ('self', 'common_prefix_len', 'common_attn_metadata', 'num_accepted_tokens',
                'num_decode_draft_tokens_cpu', 'fast_build')
    signature = inspect.signature(cls.build)
    if tuple(signature.parameters) != expected or any(
            p.kind not in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            for p in signature.parameters.values()):
        raise RuntimeError('b70_gdn_state_width: unsupported metadata builder signature')
    try:
        from vllm import _xpu_ops
        grouped_ok = patch_group_path(_xpu_ops)
    except Exception as exc:
        raise RuntimeError('b70_gdn_state_width: cannot patch grouped speculative path') from exc
    if not grouped_ok:
        raise RuntimeError('b70_gdn_state_width: grouped speculative source contract did not match')
    cls.build = wrap_build(cls.build, gdn)
    cls._b70_gdn_state_width = True
    cls._b70_state_width_candidate = CANDIDATE
    logger.warning('b70_gdn_state_width: candidate %s enabled; requires the r314 _xpu_C; '
                   'GPU/package qualification pending', CANDIDATE)

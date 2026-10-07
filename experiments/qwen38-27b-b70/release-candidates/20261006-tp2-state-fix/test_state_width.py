"""CPU check of overlays/b70-gdn-state-width with small fake objects (no vLLM, no GPU).

The fakes mirror the stock pieces the overlay touches (vLLM 0.29 XPU, R310/R313 images):
  * FakeBuilder.build = the spec branch of GDNAttentionMetadataBuilder.build: mask = draft counts >= 0
    (gdn_attn.py:236), width = widest spec row (:295-297), `block_table_tensor[mask, :width]` (:338-340 / :359-361),
    and the full-CUDA-graph staging into a persistent [max_bs, num_spec + 1] buffer (:463-478).
  * kernel() = the indexing of the SSM spec kernel (gated_delta_rule.hpp:392-395, :411, :510-511): element [n, c] is
    read at n * stride(0) + c of the underlying storage, the start state from column num_accepted - 1 (no bound
    check: past the storage it reads garbage), one state write per verify row t < size(1) into column t; plus the
    interface check (gdn_attn_interface.cpp:82-84 before r314: contiguous; r314: rows contiguous).
  * fake_xpu_ops.py = the grouped spec path of _xpu_ops._gdn_attention_core_xpu_impl (:242-257) with the same
    `spec_state_indices_tensor[s0:s1].contiguous()` line.
The recurrence is a stand-in (h = h * decay + x), float64, so "equal" means the same slots were read and written.

Run with an existing CPU-capable torch Python (CPU tensors only):
  <python-with-torch> test_state_width.py -v
"""
import importlib.util
import os
import sys
import tempfile
import textwrap
import types
import unittest
from pathlib import Path
from unittest import mock

import torch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    'b70_gdn_state_width', HERE / 'overlay/b70_gdn_state_width.py')
ov = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ov)

NULL = 0
GARBAGE = 1.0e6
DIM = 3


# ------------------------------------------------------------------------------------------------- fakes
def kernel(ssm, x, sst, acc, r314=True):
    """Spec SSM kernel stand-in. ssm: [slots, DIM] float64 (mutated). x: [n * rows, DIM]. Returns out [n * rows, DIM]."""
    if r314:
        if not (sst.stride(1) == 1 and sst.stride(0) >= sst.shape[1]):
            raise RuntimeError('spec_state_indices_tensor rows must be contiguous')
    elif not sst.is_contiguous():
        raise RuntimeError('spec_state_indices_tensor must be contiguous')
    n, rows = sst.shape
    flat = torch.empty(0, dtype=sst.dtype).set_(sst.untyped_storage())
    base, stride = sst.storage_offset(), sst.stride(0)

    def elem(b, c):
        addr = base + b * stride + c
        return int(flat[addr]) if addr < flat.numel() else None

    out = torch.empty((n * rows, DIM), dtype=torch.float64)
    for b in range(n):
        col = max(int(acc[b]) - 1, 0)
        slot = elem(b, col)
        h = ssm[slot].clone() if slot is not None else torch.full((DIM,), GARBAGE, dtype=torch.float64)
        for t in range(rows):
            h = h * 0.5 + x[b * rows + t]
            out[b * rows + t] = h
            ssm[elem(b, t)] = h          # writes only columns t < size(1)
    return out


GDN_FAKE_SRC = textwrap.dedent('''
    def _gdn_attention_core_xpu_impl(ssm, x, spec_state_indices_tensor, num_accepted_tokens, group):
        n, w = spec_state_indices_tensor.shape
        outs = []
        for s0 in range(0, n, group):
            s1 = min(s0 + group, n)
            outs.append(KERNEL(ssm, x[s0 * w:s1 * w], spec_state_indices_tensor[s0:s1].contiguous(),
                               num_accepted_tokens[s0:s1]))
        return torch.cat(outs)
''')


def load_fake_xpu_ops(tmpdir, src=GDN_FAKE_SRC):
    path = Path(tmpdir) / f'fake_xpu_ops_{abs(hash(src))}.py'
    path.write_text('import torch\n' + src)
    s = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(s)
    s.loader.exec_module(module)
    module.KERNEL = kernel
    return module


def fake_gdn_module():
    gdn = types.ModuleType('vllm.v1.attention.backends.gdn_attn')
    gdn.NULL_BLOCK_ID = NULL
    gdn.calls = {'block_table': 0}

    def mamba_get_block_table_tensor(block_table, seq_lens, kv_cache_spec, mode):
        gdn.calls['block_table'] += 1
        return block_table                       # "none" mode returns the table as is

    gdn.mamba_get_block_table_tensor = mamba_get_block_table_tensor

    class GDNAttentionMetadataBuilder:
        def __init__(self, num_spec, cudagraph=False, max_bs=8):
            self.num_spec = num_spec
            self.kv_cache_spec = None
            self.vllm_config = types.SimpleNamespace(cache_config=types.SimpleNamespace(mamba_cache_mode='none'))
            self.use_full_cuda_graph = cudagraph
            self.spec_state_indices_tensor = torch.full((max_bs, num_spec + 1), -7, dtype=torch.int32)

        def build(self, common_prefix_len, common_attn_metadata, num_accepted_tokens=None,
                  num_decode_draft_tokens_cpu=None, fast_build=False):
            m = common_attn_metadata
            block_table_tensor = gdn.mamba_get_block_table_tensor(m.block_table_tensor, m.seq_lens, None, 'none')
            mask = num_decode_draft_tokens_cpu >= 0
            n = int(mask.sum())
            qlens = m.query_start_loc_cpu[1:] - m.query_start_loc_cpu[:-1]
            width = int(qlens[mask].max())
            assert 1 < width <= self.num_spec + 1
            sst = block_table_tensor[mask, :width]
            acc = num_accepted_tokens[mask]
            if self.use_full_cuda_graph:
                batch = m.num_reqs
                self.spec_state_indices_tensor[:n, :width].copy_(sst)
                sst = self.spec_state_indices_tensor[:batch, :width]
                sst[n:].fill_(NULL)
            return types.SimpleNamespace(spec_state_indices_tensor=sst, num_spec_decodes=n, num_accepted_tokens=acc)

    gdn.GDNAttentionMetadataBuilder = GDNAttentionMetadataBuilder
    return gdn


def install_fakes(tmpdir):
    gdn = fake_gdn_module()
    xpu_ops = load_fake_xpu_ops(tmpdir)
    vllm = types.ModuleType('vllm')
    logger_mod = types.ModuleType('vllm.logger')
    import logging
    logger_mod.init_logger = logging.getLogger
    v1 = types.ModuleType('vllm.v1')
    att = types.ModuleType('vllm.v1.attention')
    backends = types.ModuleType('vllm.v1.attention.backends')
    vllm.logger, vllm.v1, vllm._xpu_ops = logger_mod, v1, xpu_ops
    v1.attention, att.backends, backends.gdn_attn = att, backends, gdn
    mods = {'vllm': vllm, 'vllm.logger': logger_mod, 'vllm.v1': v1, 'vllm.v1.attention': att,
            'vllm.v1.attention.backends': backends, 'vllm.v1.attention.backends.gdn_attn': gdn,
            'vllm._xpu_ops': xpu_ops}
    return mods, gdn, xpu_ops


def step_metadata(block_table, widths):
    """Common metadata of one pure spec step: request i verifies widths[i] rows."""
    qsl = torch.tensor([0] + list(torch.tensor(widths).cumsum(0).tolist()), dtype=torch.int32)
    return types.SimpleNamespace(block_table_tensor=block_table, seq_lens=None, query_start_loc_cpu=qsl,
                                 num_reqs=len(widths))


def block_table_for(n, num_spec, offset=1):
    # request i owns slots offset + i * (num_spec + 1) + [0 .. num_spec]; slot 0 is the null block
    return (offset + torch.arange(n * (num_spec + 1), dtype=torch.int32)).view(n, num_spec + 1)


# ------------------------------------------------------------------------------------------------- tests
class StateWidthTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mods, self.gdn, self.xpu_ops = install_fakes(self.tmp.name)
        self.stock_build = self.gdn.GDNAttentionMetadataBuilder.build
        with mock.patch.dict(sys.modules, self.mods), mock.patch.dict(os.environ, {'B70_GDN_STATE_WIDTH': '1'}):
            ov.register()
        self.cls = self.gdn.GDNAttentionMetadataBuilder

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, builder, widths, accepted, overlay=True):
        n, k = len(widths), builder.num_spec
        bt = block_table_for(n, k)
        fn = self.cls.build if overlay else self.stock_build
        return fn(builder, 0, step_metadata(bt, widths), torch.tensor(accepted, dtype=torch.int32),
                  torch.tensor([w - 1 for w in widths], dtype=torch.int32)), bt

    # --- registration
    def test_register_gated_and_idempotent(self):
        self.assertTrue(getattr(self.cls, '_b70_gdn_state_width', False))
        self.assertTrue(self.xpu_ops._gdn_attention_core_xpu_impl._b70_gdn_state_width)
        self.assertEqual(ov.CANDIDATE, '20261006-tp2-state-fix')
        self.assertEqual(self.cls._b70_state_width_candidate, ov.CANDIDATE)
        self.assertEqual(self.xpu_ops._gdn_attention_core_xpu_impl._b70_state_width_candidate, ov.CANDIDATE)
        wrapped = self.cls.build
        with mock.patch.dict(sys.modules, self.mods), mock.patch.dict(os.environ, {'B70_GDN_STATE_WIDTH': '1'}):
            ov.register()
        self.assertIs(self.cls.build, wrapped)
        mods, gdn, xpu_ops = install_fakes(self.tmp.name)
        with mock.patch.dict(sys.modules, mods), mock.patch.dict(os.environ, {'B70_GDN_STATE_WIDTH': '0'}):
            ov.register()
        self.assertFalse(getattr(gdn.GDNAttentionMetadataBuilder, '_b70_gdn_state_width', False))

    def test_missing_anchor_refuses_explicit_activation(self):
        mods, gdn, _ = install_fakes(self.tmp.name)
        mods['vllm._xpu_ops'] = mods['vllm']._xpu_ops = load_fake_xpu_ops(
            self.tmp.name, GDN_FAKE_SRC.replace('.contiguous()', '.clone()'))
        stock = gdn.GDNAttentionMetadataBuilder.build
        with mock.patch.dict(sys.modules, mods), mock.patch.dict(os.environ, {'B70_GDN_STATE_WIDTH': '1'}):
            with self.assertRaisesRegex(RuntimeError, 'source contract'):
                ov.register()
        self.assertIs(gdn.GDNAttentionMetadataBuilder.build, stock)

    # --- builder
    def test_full_width_step_untouched(self):
        b = self.cls(num_spec=5)
        calls = self.gdn.calls['block_table']
        md, bt = self.build(b, [6, 6], [6, 3])
        self.assertEqual(self.gdn.calls['block_table'], calls + 1)      # full-width path has no extra indexing or allocation
        self.assertTrue(md.spec_state_indices_tensor.is_contiguous())
        self.assertTrue(torch.equal(md.spec_state_indices_tensor, bt[:, :6]))

    def test_narrow_step_same_shape_values_wider_rows(self):
        for k, widths in ((9, [6, 6, 6]), (5, [3]), (16, [6, 2])):
            b = self.cls(num_spec=k)
            stock, _ = self.build(b, widths, [1] * len(widths), overlay=False)
            md, bt = self.build(b, widths, [1] * len(widths))
            sst = md.spec_state_indices_tensor
            self.assertEqual(tuple(sst.shape), tuple(stock.spec_state_indices_tensor.shape))
            self.assertTrue(torch.equal(sst, stock.spec_state_indices_tensor))
            self.assertEqual(sst.stride(), (k + 1, 1))
            flat = torch.empty(0, dtype=sst.dtype).set_(sst.untyped_storage())
            self.assertTrue(torch.equal(flat[sst.storage_offset():].view(len(widths), k + 1), bt))

    def test_cudagraph_branch_fills_buffer_keeps_object(self):
        b = self.cls(num_spec=9, cudagraph=True, max_bs=4)
        md, bt = self.build(b, [6, 6], [1, 1])
        sst = md.spec_state_indices_tensor
        self.assertEqual(sst.untyped_storage().data_ptr(), b.spec_state_indices_tensor.untyped_storage().data_ptr())
        self.assertTrue(torch.equal(b.spec_state_indices_tensor[:2], bt))
        self.assertTrue(torch.equal(sst, bt[:, :6]))

    # --- kernel-level: neutral when wide enough, correct when not
    def test_identical_kernel_results_when_already_wide_enough(self):
        torch.manual_seed(0)
        for k, widths in ((9, [6, 6, 6]), (5, [4, 4]), (16, [6])):
            for acc_pat in range(6):
                b = self.cls(num_spec=k)
                n, w = len(widths), widths[0]
                acc = [(acc_pat + i) % w + 1 for i in range(n)]          # every a <= width
                stock, _ = self.build(b, widths, acc, overlay=False)
                md, _ = self.build(b, widths, acc)
                ssm0 = torch.randn(1 + n * (k + 1), DIM, dtype=torch.float64)
                x = torch.randn(n * w, DIM, dtype=torch.float64)
                s_stock, s_ov = ssm0.clone(), ssm0.clone()
                o_stock = kernel(s_stock, x, stock.spec_state_indices_tensor, stock.num_accepted_tokens, r314=False)
                o_ov = kernel(s_ov, x, md.spec_state_indices_tensor, md.num_accepted_tokens, r314=True)
                self.assertTrue(torch.equal(o_stock, o_ov))
                self.assertTrue(torch.equal(s_stock, s_ov))               # same slots written, nothing extra

    def test_old_kernel_rejects_multirow_view(self):
        b = self.cls(num_spec=9)
        md, _ = self.build(b, [6, 6], [8, 2])
        with self.assertRaises(RuntimeError):
            kernel(torch.zeros(40, DIM, dtype=torch.float64), torch.zeros(12, DIM, dtype=torch.float64),
                   md.spec_state_indices_tensor, md.num_accepted_tokens, r314=False)

    def engine(self, k, plan, overlay, grouped=False):
        """Run several requests through steps plan = [(widths, accepted), ...] (accepted = tokens of that step kept,
        so it becomes the next step's num_accepted_tokens). Returns the kept outputs per request."""
        torch.manual_seed(1)
        n = len(plan[0][0])
        b = self.cls(num_spec=k)
        ssm = torch.zeros(1 + n * (k + 1), DIM, dtype=torch.float64)
        prev_acc = [1] * n
        kept = [[] for _ in range(n)]
        for widths, accepted in plan:
            md, _ = self.build(b, widths, prev_acc, overlay=overlay)
            w = widths[0]
            x = torch.randn(n * w, DIM, dtype=torch.float64)
            if grouped:
                out = self.xpu_ops._gdn_attention_core_xpu_impl(ssm, x, md.spec_state_indices_tensor,
                                                                md.num_accepted_tokens, 2)
            else:
                out = kernel(ssm, x, md.spec_state_indices_tensor, md.num_accepted_tokens, r314=overlay)
            for i in range(n):
                kept[i].append((x[i * w:i * w + accepted[i]], out[i * w:i * w + accepted[i]]))
            prev_acc = list(accepted)
        return kept

    @staticmethod
    def serial_reference(kept_i):
        """One token at a time over every kept input of request i."""
        h = torch.zeros(DIM, dtype=torch.float64)
        ref = []
        for xs, _ in kept_i:
            for xrow in xs:
                h = h * 0.5 + xrow
                ref.append(h.clone())
        return torch.stack(ref), torch.cat([o for _, o in kept_i])

    def check_engine(self, k, plan, grouped=False):
        ok = all(torch.equal(*self.serial_reference(r)) for r in self.engine(k, plan, True, grouped))
        stock = all(torch.equal(*self.serial_reference(r)) for r in self.engine(k, plan, False, grouped))
        return ok, stock

    def test_long_acceptance_then_narrow_step(self):
        # K = 9 copy-draft shape: a 10-row verify keeps 8, the next step is a normal 6-row draft.
        plan = [([10, 10, 10], [8, 3, 10]), ([6, 6, 6], [6, 2, 1]), ([10, 10, 10], [10, 7, 9]), ([6, 6, 6], [4, 6, 6])]
        ok, stock = self.check_engine(9, plan)
        self.assertTrue(ok)
        self.assertFalse(stock)                                           # the defect, reproduced
        ok_g, stock_g = self.check_engine(9, plan, grouped=True)
        self.assertTrue(ok_g)
        self.assertFalse(stock_g)

    def test_context_end_narrowing_stock_engine(self):
        # shipped depth 5: a fully accepted 6-row step, then the last step clamped to 3 rows by max_model_len.
        plan = [([6], [6]), ([3], [3])]
        ok, stock = self.check_engine(5, plan)
        self.assertTrue(ok)
        self.assertFalse(stock)

    def test_no_change_when_never_narrower(self):
        plan = [([6, 6], [6, 1]), ([6, 6], [2, 6]), ([6, 6], [5, 5])]
        ok, stock = self.check_engine(5, plan)
        self.assertTrue(ok and stock)

    def test_group_path_patch_neutral_for_contiguous(self):
        torch.manual_seed(2)
        sst = block_table_for(3, 5)[:, :6].contiguous()
        acc = torch.tensor([6, 1, 4], dtype=torch.int32)
        x = torch.randn(18, DIM, dtype=torch.float64)
        s1, s2 = torch.randn(25, DIM, dtype=torch.float64), None
        s2 = s1.clone()
        o1 = self.xpu_ops._gdn_attention_core_xpu_impl(s1, x, sst, acc, 2)
        o2 = kernel(s2, x, sst, acc, r314=False)
        self.assertTrue(torch.equal(o1, o2) and torch.equal(s1, s2))


class CandidateContractTests(unittest.TestCase):
    setUp = StateWidthTest.setUp
    tearDown = StateWidthTest.tearDown
    build = StateWidthTest.build
    def test_bad_signature_does_not_mutate_grouped_path(self):
        mods, gdn, ops = install_fakes(self.tmp.name)
        gdn.GDNAttentionMetadataBuilder.build = lambda self, unexpected: None
        before = ops._gdn_attention_core_xpu_impl.__code__
        with mock.patch.dict(sys.modules, mods), mock.patch.dict(os.environ, {'B70_GDN_STATE_WIDTH': '1'}):
            with self.assertRaisesRegex(RuntimeError, 'signature'):
                ov.register()
        self.assertIs(ops._gdn_attention_core_xpu_impl.__code__, before)

    def test_existing_research_overlay_refused(self):
        mods, gdn, _ = install_fakes(self.tmp.name)
        gdn.GDNAttentionMetadataBuilder._b70_gdn_state_width = True
        with mock.patch.dict(sys.modules, mods), mock.patch.dict(os.environ, {'B70_GDN_STATE_WIDTH': '1'}):
            with self.assertRaisesRegex(RuntimeError, 'another overlay'):
                ov.register()

    def test_duplicate_anchor_refused(self):
        ops = load_fake_xpu_ops(self.tmp.name, GDN_FAKE_SRC.replace(
            'outs = []', 'outs = []  # spec_state_indices_tensor[s0:s1].contiguous()'))
        before = ops._gdn_attention_core_xpu_impl.__code__
        self.assertFalse(ov.patch_group_path(ops))
        self.assertIs(ops._gdn_attention_core_xpu_impl.__code__, before)

    def test_missing_slots_selected_row_mismatch_and_padding_refused(self):
        b = self.cls(num_spec=5)
        for shape, n, mask, error in (
                ((2, 5), 2, [True, True], 'missing full'),
                ((2, 6), 2, [True, False], 'selected state rows'),
                ((2, 6), 1, [True, False], 'padded state layout')):
            table = torch.arange(shape[0] * shape[1], dtype=torch.int32).view(*shape)
            md = types.SimpleNamespace(num_spec_decodes=n, spec_state_indices_tensor=table[:, :3].clone())
            with self.subTest(error=error), self.assertRaisesRegex(RuntimeError, error):
                ov.widen(b, md, table, torch.tensor(mask), NULL)

    def test_graph_buffer_padding_cleared_and_object_retained(self):
        b = self.cls(num_spec=5, cudagraph=True, max_bs=4)
        table = block_table_for(2, 5)
        b.spec_state_indices_tensor[:2, :3] = table[:, :3]
        md = types.SimpleNamespace(num_spec_decodes=2, spec_state_indices_tensor=b.spec_state_indices_tensor[:, :3])
        old = md.spec_state_indices_tensor
        self.assertEqual(ov.widen(b, md, table, torch.tensor([True, True]), NULL), 'graph-buffer')
        self.assertIs(md.spec_state_indices_tensor, old)
        self.assertTrue(torch.equal(b.spec_state_indices_tensor[:2], table))
        self.assertTrue(torch.equal(b.spec_state_indices_tensor[2:, 3:], torch.zeros((2, 3), dtype=torch.int32)))

    def test_offset_graph_view_refused_before_writing(self):
        b = self.cls(num_spec=5, cudagraph=True, max_bs=4)
        original = b.spec_state_indices_tensor.clone()
        md = types.SimpleNamespace(num_spec_decodes=2, spec_state_indices_tensor=b.spec_state_indices_tensor[1:3, :3])
        with self.assertRaisesRegex(RuntimeError, 'graph state layout'):
            ov.widen(b, md, block_table_for(2, 5), torch.tensor([True, True]), NULL)
        self.assertTrue(torch.equal(b.spec_state_indices_tensor, original))

    def test_single_row_contiguity_is_not_a_kernel_identity_gate(self):
        b = self.cls(num_spec=5)
        md, table = self.build(b, [3], [6])
        sst = md.spec_state_indices_tensor
        self.assertEqual(tuple(sst.shape), (1, 3))
        self.assertEqual(sst.stride(), (6, 1))
        self.assertTrue(sst.is_contiguous())
        # PyTorch ignores the single-row stride for contiguity. The old check
        # passes even though this does not identify the required R314 binary.
        storage = torch.empty(0, dtype=sst.dtype).set_(sst.untyped_storage())
        self.assertTrue(torch.equal(storage[sst.storage_offset():sst.storage_offset() + 6], table[0]))
        states = torch.arange(7 * DIM, dtype=torch.float64).view(7, DIM)
        x = torch.ones(3, DIM, dtype=torch.float64)
        old_states, new_states = states.clone(), states.clone()
        old = kernel(old_states, x, sst, md.num_accepted_tokens, r314=False)
        new = kernel(new_states, x, sst, md.num_accepted_tokens, r314=True)
        self.assertTrue(torch.equal(old, new))
        self.assertTrue(torch.equal(old_states, new_states))
        self.assertTrue(torch.equal(old[0], states[int(table[0, 5])] * 0.5 + x[0]))

    def test_nonzero_offset_grouped_view_reads_correct_previous_slots(self):
        # The second group has a nonzero storage offset; compare it to the whole batch.
        torch.manual_seed(7)
        b = self.cls(num_spec=5)
        md, _ = self.build(b, [3, 3, 3, 3], [6, 5, 6, 4])
        self.assertGreater(md.spec_state_indices_tensor[2:].storage_offset(), 0)
        states = torch.randn(25, DIM, dtype=torch.float64)
        grouped_states, whole_states = states.clone(), states.clone()
        x = torch.randn(12, DIM, dtype=torch.float64)
        grouped = self.xpu_ops._gdn_attention_core_xpu_impl(
            grouped_states, x, md.spec_state_indices_tensor, md.num_accepted_tokens, 2)
        whole = kernel(whole_states, x, md.spec_state_indices_tensor, md.num_accepted_tokens)
        self.assertTrue(torch.equal(grouped, whole))
        self.assertTrue(torch.equal(grouped_states, whole_states))

    def test_missing_speculative_tensor_refused_but_nonspec_unchanged(self):
        b = self.cls(num_spec=5)
        md = types.SimpleNamespace(num_spec_decodes=1, spec_state_indices_tensor=None)
        with self.assertRaisesRegex(RuntimeError, 'invalid speculative metadata'):
            ov.widen(b, md, block_table_for(1, 5), torch.tensor([True]), NULL)
        md.num_spec_decodes = 0
        self.assertEqual(ov.widen(b, md, None, None, NULL), 'unchanged')


if __name__ == '__main__':
    unittest.main()

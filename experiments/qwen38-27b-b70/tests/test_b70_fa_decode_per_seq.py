"""CPU check of the per-sequence decode wrapper with a stub attention function (no vLLM, no GPU)."""
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parents[1]


def install(min_k='229'):
    calls = []

    def flash_attn_varlen_func(*args, **kw):
        calls.append({'B': kw['q'].shape[0], 'max_k': kw['max_seqlen_k'], 'used': kw['seqused_k'].tolist(),
                      'table': kw['block_table'].tolist(), 'cu': kw['cu_seqlens_q'].tolist()})
        kw['out'].copy_(kw['q'] * 2)
        return kw['out']

    fa = types.ModuleType('flash_attn'); fa.flash_attn_varlen_func = flash_attn_varlen_func
    mods = {'vllm': types.ModuleType('vllm'), 'vllm.logger': types.ModuleType('vllm.logger'), 'vllm.v1': types.ModuleType('v1'),
            'vllm.v1.attention': types.ModuleType('attention'), 'vllm.v1.attention.backends': types.ModuleType('backends'),
            'vllm.v1.attention.backends.flash_attn': fa}
    mods['vllm.logger'].init_logger = lambda name: types.SimpleNamespace(warning=lambda *a, **k: None)
    mods['vllm.v1.attention.backends'].flash_attn = fa
    sys.modules.update(mods)
    os.environ.update(B70_FA_DECODE_PER_SEQ='1', B70_FA_DECODE_PER_SEQ_MIN_K=min_k)
    spec = importlib.util.spec_from_file_location('perseq', HERE / 'overlays/b70-fa-decode-per-seq/b70_fa_decode_per_seq.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); module.register()
    return fa, calls


def kwargs(lengths, queries_per_seq=1):
    B = len(lengths) * queries_per_seq
    return dict(q=torch.arange(B * 3, dtype=torch.float32).view(B, 1, 3), k=None, v=None, out=torch.zeros(B, 1, 3),
                cu_seqlens_q=torch.arange(0, B + 1, queries_per_seq, dtype=torch.int32), max_seqlen_q=queries_per_seq,
                seqused_k=torch.tensor(lengths, dtype=torch.int32), max_seqlen_k=max(lengths), causal=True,
                block_table=torch.arange(len(lengths) * 4, dtype=torch.int32).view(len(lengths), 4))


class PerSeqTest(unittest.TestCase):
    def test_long_keys_split_per_sequence(self):
        fa, calls = install()
        kw = kwargs([1645, 6524, 300])
        out = fa.flash_attn_varlen_func(**kw)
        self.assertTrue(torch.equal(out, kw['q'] * 2))
        self.assertEqual([c['B'] for c in calls], [1, 1, 1])
        self.assertEqual([c['max_k'] for c in calls], [1645, 6524, 300])          # each sequence's own length
        self.assertEqual([c['used'] for c in calls], [[1645], [6524], [300]])
        self.assertEqual([c['table'] for c in calls], [[[0, 1, 2, 3]], [[4, 5, 6, 7]], [[8, 9, 10, 11]]])
        self.assertEqual({tuple(c['cu']) for c in calls}, {(0, 1)})

    def test_short_keys_and_single_sequence_pass_through(self):
        fa, calls = install()
        fa.flash_attn_varlen_func(**kwargs([100, 200, 229]))
        self.assertEqual([c['B'] for c in calls], [3])
        calls.clear()
        fa.flash_attn_varlen_func(**kwargs([6524]))
        self.assertEqual([c['B'] for c in calls], [1])

    def test_multi_query_calls_pass_through(self):
        fa, calls = install()
        kw = kwargs([6524], queries_per_seq=6)                                       # an MTP verify step or a prefill chunk
        fa.flash_attn_varlen_func(**kw)
        self.assertEqual([c['B'] for c in calls], [6])


if __name__ == '__main__':
    unittest.main()

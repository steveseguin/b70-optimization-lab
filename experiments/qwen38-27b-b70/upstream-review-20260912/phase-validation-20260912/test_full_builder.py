# ruff: noqa: F401, F821
# Names/imports consumed by the dynamically executed pinned upstream AST.
"""Run unchanged PR tests against actual builder methods with CPU-only dependency adapters.

Adapters replace config/model resolution and import plumbing, not builder logic.
This is not an installed-vLLM integration test or device/graph execution.
"""

import ast
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace, ModuleType
from typing import Any, Literal

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parent


class CommonAttentionMetadata(SimpleNamespace):
    def replace(self, **kwargs):
        return CommonAttentionMetadata(**(vars(self) | kwargs))

    def compute_num_computed_tokens(self):
        return self.seq_lens - self.query_start_loc.diff()


class AttentionMetadataBuilder:
    def __class_getitem__(cls, arg):
        return cls

    def _init_reorder_batch_threshold(self, *args):
        pass


class AttentionBackend:
    pass


AttentionCGSupport = SimpleNamespace(UNIFORM_BATCH=1)
VllmConfig = KVCacheSpec = object
MambaSpec = SimpleNamespace
NULL_BLOCK_ID = 0
PAD_SLOT_ID = -1
PIN_MEMORY = False


def async_tensor_h2d(x, device):
    return x.to(device)


def np_to_pinned_tensor(x):
    return torch.from_numpy(x.copy())


triton = SimpleNamespace(cdiv=lambda x, y: (x + y - 1) // y)


def extract_functions(filename, names):
    tree = ast.parse((ROOT / filename).read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(nodes) == len(names)
    for n in nodes:
        n.decorator_list = []
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, "exec"), globals())


extract_functions(
    "utils.py",
    [
        "split_decodes_and_prefills",
        "compute_causal_conv1d_metadata",
        "mamba_get_block_table_tensor",
    ],
)
extract_functions(
    "index.py", ["prepare_lens", "prepare_chunk_indices", "prepare_chunk_offsets"]
)

for name, attrs in {
    "vllm.model_executor.layers.mamba.gdn.qwen_gdn_linear_attn": {
        "_resolve_gdn_prefill_backend": lambda c: (None, "triton")
    },
    "vllm.third_party.flash_linear_attention.ops.utils": {"FLA_CHUNK_SIZE": 64},
    "vllm.third_party.flash_linear_attention.ops.index": {
        "prepare_chunk_indices": prepare_chunk_indices,
        "prepare_chunk_offsets": prepare_chunk_offsets,
    },
}.items():
    mod = ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod

arm = os.environ.get("GDN_ARM", "candidate")
filename = "gdn_attn.py" if arm == "candidate" else "gdn_attn.stock.py"
tree = ast.parse((ROOT / filename).read_text())
tree.body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
exec(compile(tree, filename, "exec"), globals())


class GraphMode:
    def __init__(self, full=False):
        self.full = full

    def has_full_cudagraphs(self):
        return self.full


CUDAGraphMode = SimpleNamespace(FULL_AND_PIECEWISE=GraphMode(True))
SpeculativeConfig = SimpleNamespace


def create_vllm_config(**kwargs):
    return SimpleNamespace(
        compilation_config=SimpleNamespace(
            cudagraph_mode=GraphMode(), max_cudagraph_capture_size=128
        ),
        speculative_config=None,
        scheduler_config=SimpleNamespace(max_num_seqs=128),
        cache_config=SimpleNamespace(mamba_cache_mode="none"),
    )


@dataclass
class BatchSpec:
    seq_lens: list[int]
    query_lens: list[int]

    @property
    def batch_size(self):
        return len(self.seq_lens)

    def compute_num_tokens(self):
        return sum(self.query_lens)


def create_common_attn_metadata(batch, block_size, device):
    starts = (
        torch.tensor([0] + batch.query_lens, dtype=torch.int32)
        .cumsum(0)
        .to(torch.int32)
    )
    seqs = torch.tensor(batch.seq_lens, dtype=torch.int32)
    return CommonAttentionMetadata(
        query_start_loc=starts,
        query_start_loc_cpu=starts,
        seq_lens=seqs,
        seq_lens_cpu_upper_bound=seqs,
        max_query_len=max(batch.query_lens),
        num_actual_tokens=sum(batch.query_lens),
        num_reqs=batch.batch_size,
        is_prefilling=None,
        block_table_tensor=torch.arange(
            batch.batch_size * 8, dtype=torch.int32
        ).reshape(batch.batch_size, 8)
        + 1,
    )


tests = ast.parse((ROOT / "test_gdn_metadata_builder.py").read_text())
tests.body = [n for n in tests.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
exec(compile(tests, "upstream-pr-tests.py", "exec"), globals())


@pytest.mark.parametrize("full", [False, True])
def test_extra_reused_staging_buffers(full):
    builder = _create_gdn_builder(full_cuda_graph=full)
    old = create_common_attn_metadata(BatchSpec([100, 50], [1, 1]), 16, DEVICE)
    builder.build(0, old)
    fresh = create_common_attn_metadata(BatchSpec([101, 1], [1, 1]), 16, DEVICE)
    fresh = fresh.replace(
        is_prefilling=torch.tensor([False, True]),
        block_table_tensor=fresh.block_table_tensor + 100,
    )
    meta = builder.build(0, fresh)
    assert meta.num_prefills == 1
    assert meta.prefill_state_indices.tolist() == [109]
    assert meta.prefill_has_initial_state.tolist() == [False]
    assert meta.non_spec_state_indices_tensor.tolist() == [101, 109]


@pytest.mark.parametrize("full", [False, True])
def test_extra_stale_phase_on_zero_padding(full):
    builder = _create_gdn_builder(full_cuda_graph=full)
    batch = BatchSpec([100, 1, 0], [1, 1, 0])
    m = create_common_attn_metadata(batch, 16, DEVICE).replace(
        is_prefilling=torch.tensor([False, True, True]), num_actual_tokens=3
    )
    meta = builder.build(0, m)
    assert (meta.num_decodes, meta.num_prefills, meta.num_prefill_tokens) == (1, 1, 1)
    assert meta.prefill_query_start_loc.tolist() == [0, 1]
    assert meta.prefill_has_initial_state.tolist() == [False]


def test_extra_short_resume_long_extend_fresh():
    builder = _create_gdn_builder()
    m = create_common_attn_metadata(
        BatchSpec([100, 65, 90, 1], [1, 1, 3, 1]), 16, DEVICE
    )
    meta = builder.build(
        0, m.replace(is_prefilling=torch.tensor([False, True, True, True]))
    )
    assert (meta.num_decodes, meta.num_prefills) == (2, 2)
    assert meta.prefill_has_initial_state.tolist() == [True, False]
    assert meta.prefill_query_start_loc.tolist() == [0, 3, 4]

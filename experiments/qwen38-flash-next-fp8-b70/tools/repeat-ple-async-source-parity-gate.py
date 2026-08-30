#!/usr/bin/env python3
"""Compare the actual synchronous and async Qwen PLE lookup source on TP4."""

import argparse
import hashlib
import json
import os
from types import SimpleNamespace

import torch
import torch.nn as nn
import torch.nn.functional as F

from vllm.config import set_current_vllm_config
from vllm.distributed import (
    destroy_distributed_environment,
    destroy_model_parallel,
)
from vllm.distributed.parallel_state import (
    ensure_model_parallel_initialized,
    init_distributed_environment,
)
from vllm.engine.arg_utils import EngineArgs
from vllm.model_executor.layers.vocab_parallel_embedding import (
    VocabParallelEmbedding,
)
from vllm.models.qwen4_exp.nvidia.ple_layer import Qwen4ExpNGramEmbedding
from vllm.utils.torch_utils import get_accelerator_view_from_cpu_tensor


class _RawEmbeddingMethod:
    def embedding(
        self, layer: VocabParallelEmbedding, input_ids: torch.Tensor
    ) -> torch.Tensor:
        return F.embedding(input_ids, layer.weight)


def _fp8_values(rows: torch.Tensor, columns: torch.Tensor) -> torch.Tensor:
    values = ((rows * 17 + columns * 31) % 241 - 120).to(torch.float32) / 32
    return values.to(torch.float8_e4m3fn)


def _digest(value: torch.Tensor) -> str:
    raw = value.contiguous().view(torch.uint8).numpy().tobytes()
    return hashlib.sha256(raw).hexdigest()


def _make_module(
    *,
    device: torch.device,
    rank: int,
    world_size: int,
    max_tokens: int,
    heads: int,
    head_dim: int,
    local_vocab: int,
) -> Qwen4ExpNGramEmbedding:
    global_vocab = local_vocab * world_size
    global_start = rank * local_vocab
    local_rows = torch.arange(local_vocab, dtype=torch.int64).unsqueeze(1)
    columns = torch.arange(head_dim, dtype=torch.int64).unsqueeze(0)
    host_weight = _fp8_values(global_start + local_rows, columns).pin_memory()
    uva_weight = get_accelerator_view_from_cpu_tensor(host_weight)

    embedding = VocabParallelEmbedding.__new__(VocabParallelEmbedding)
    nn.Module.__init__(embedding)
    embedding.tp_size = world_size
    embedding.shard_indices = SimpleNamespace(
        org_vocab_start_index=global_start,
        org_vocab_end_index=global_start + local_vocab,
        num_org_vocab_padding=0,
        added_vocab_start_index=global_vocab,
        added_vocab_end_index=global_vocab,
    )
    embedding.quant_method = _RawEmbeddingMethod()
    embedding.weight = nn.Parameter(uva_weight, requires_grad=False)
    embedding.weight._vllm_is_uva_offloaded = True

    module = Qwen4ExpNGramEmbedding.__new__(Qwen4ExpNGramEmbedding)
    nn.Module.__init__(module)
    module.eos_token_id = 0
    module.ngram_size = 3
    module.ngram_heads = heads
    module.heads_per_ngram = heads // 2
    module.head_dim = head_dim
    module.embedding_dim = heads * head_dim
    module.ngram_embedding = embedding
    module.positions_buffer = torch.arange(max_tokens, dtype=torch.int64, device=device)
    module.padded_buffer = torch.full(
        (1, max_tokens), module.eos_token_id, dtype=torch.int64, device=device
    )
    per_head_vocab = global_vocab // heads
    module.ngram_heads_vocab_sizes = torch.full(
        (heads,), per_head_vocab, dtype=torch.int64, device=device
    )
    module.ngram_heads_offsets = (
        torch.arange(heads, dtype=torch.int64, device=device) * per_head_vocab
    )
    module.layer_multipliers = torch.tensor(
        [1237, 3457, 7919], dtype=torch.int64, device=device
    )
    module._xpu_uva_prefetch_enabled = True
    module._xpu_uva_prefetch_stream = torch.xpu.Stream()
    module._xpu_uva_prefetch_input_ready = torch.xpu.Event()
    module._xpu_uva_prefetch_lookup_done = torch.xpu.Event()
    module._xpu_uva_prefetch_buffer = torch.empty(
        max_tokens,
        module.embedding_dim,
        dtype=embedding.weight.dtype,
        device=device,
    )
    module._xpu_uva_prefetch_ids = None
    module._xpu_uva_prefetch_num_tokens = 0
    # Retain the pinned allocation explicitly for the lifetime of its XPU view.
    module._source_parity_host_weight = host_weight
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--rows", type=int, default=64)
    parser.add_argument("--heads", type=int, default=16)
    parser.add_argument("--head-dim", type=int, default=160)
    parser.add_argument("--local-vocab", type=int, default=4096)
    parser.add_argument("--repeats", type=int, default=100)
    args = parser.parse_args()
    if (
        args.heads % 2
        or min(args.rows, args.heads, args.head_dim, args.local_vocab, args.repeats)
        <= 0
    ):
        raise ValueError("dimensions/repeats must be positive and heads must be even")

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    device = torch.device(f"xpu:{local_rank}")
    torch.xpu.set_device(device)

    engine_args = EngineArgs(
        model=args.model,
        tokenizer=args.model,
        trust_remote_code=False,
        tensor_parallel_size=world_size,
        language_model_only=True,
        enforce_eager=True,
        max_model_len=args.rows,
        max_num_seqs=1,
        max_num_batched_tokens=args.rows,
    )
    vllm_config = engine_args.create_engine_config(usage_context=None)
    init_distributed_environment(
        world_size=world_size,
        rank=rank,
        distributed_init_method="env://",
        local_rank=local_rank,
        backend="xccl",
    )
    try:
        with set_current_vllm_config(vllm_config):
            ensure_model_parallel_initialized(
                tensor_model_parallel_size=world_size,
                pipeline_model_parallel_size=1,
                backend="xccl",
            )
            module = _make_module(
                device=device,
                rank=rank,
                world_size=world_size,
                max_tokens=args.rows,
                heads=args.heads,
                head_dim=args.head_dim,
                local_vocab=args.local_vocab,
            )
            row_pattern = [args.rows, 1, max(1, args.rows * 2 // 3), 2]
            captures: list[tuple[str, torch.Tensor, torch.Tensor]] = []
            for repeat in range(args.repeats):
                row_count = row_pattern[repeat % len(row_pattern)]
                generation = f"rows_{row_count}_phase_{repeat % len(row_pattern)}"
                offset = (repeat % len(row_pattern)) * 104729
                input_ids = (
                    torch.arange(row_count, device=device, dtype=torch.int64)
                    + 1
                    + offset
                )
                query_start_loc = torch.tensor(
                    [0, row_count], device=device, dtype=torch.int64
                )
                ngram_context = torch.tensor(
                    [[offset + 7, offset + 11]], device=device, dtype=torch.int64
                )
                ngram_ids = module._compute_ngram_ids(
                    input_ids, query_start_loc, ngram_context
                )
                synchronous = module.ngram_embedding(ngram_ids).flatten(-2)
                module.start_xpu_uva_prefetch(
                    torch.empty(0, device=device),
                    input_ids,
                    query_start_loc,
                    ngram_context,
                )
                asynchronous = module._finalize_xpu_uva_prefetch(row_count)
                captures.append(
                    (
                        generation,
                        synchronous.view(torch.int8).clone(),
                        asynchronous.view(torch.int8).clone(),
                    )
                )
            torch.xpu.synchronize()

        hashes: dict[str, set[str]] = {}
        parity = []
        for generation, synchronous, asynchronous in captures:
            sync_cpu = synchronous.cpu()
            async_cpu = asynchronous.cpu()
            parity.append(bool(torch.equal(sync_cpu, async_cpu)))
            hashes.setdefault(generation, set()).add(_digest(async_cpu))
        generation_hashes = {
            generation: sorted(values) for generation, values in hashes.items()
        }
        repeatable = all(len(values) == 1 for values in generation_hashes.values())
        result = {
            "actual_source_methods": [
                "Qwen4ExpNGramEmbedding._compute_ngram_ids",
                "VocabParallelEmbedding.forward",
                "Qwen4ExpNGramEmbedding.start_xpu_uva_prefetch",
                "Qwen4ExpNGramEmbedding._finalize_xpu_uva_prefetch",
            ],
            "async_matches_synchronous_all": all(parity),
            "dtype": "float8_e4m3fn_via_int8_tp_reduce",
            "generation_output_sha256": generation_hashes,
            "generations_repeatable": repeatable,
            "head_dim": args.head_dim,
            "heads": args.heads,
            "local_vocab": args.local_vocab,
            "rank": rank,
            "repeats": args.repeats,
            "row_pattern": row_pattern,
            "world_size": world_size,
        }
        print(json.dumps(result, sort_keys=True), flush=True)
        if not all(parity) or not repeatable:
            raise SystemExit(1)
    finally:
        destroy_model_parallel()
        destroy_distributed_environment()


if __name__ == "__main__":
    main()

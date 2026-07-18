#!/usr/bin/env python3
"""Validate guarded vLLM M=4/M=8 dispatch on four XPU ranks.

This is a wrapper/integration gate over captured real M=2 tensors. It does not
claim sequential speculative acceptance or endpoint throughput.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from unittest.mock import patch
import weakref

import torch
import torch.distributed as dist


OUTPUT_NAMES = (
    "residual_out",
    "next_post_mix",
    "next_comb_mix",
    "layer_input",
)


def load_record(root: Path, rank: int, category: str) -> dict:
    return json.loads((root / f"rank{rank}" / category / "000.json").read_text())


def load_tensor(
    root: Path, record: dict, name: str, device: torch.device
) -> torch.Tensor:
    return torch.load(
        root / record["tensors"][name]["blob"],
        map_location="cpu",
        weights_only=True,
    ).to(device)


def tile_rows(tensor: torch.Tensor, width: int) -> torch.Tensor:
    if tensor.ndim == 0 or tensor.shape[0] != 2:
        return tensor
    return torch.cat([tensor] * (width // 2), dim=0).contiguous()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    # These selectors are import-time constants in the candidate vLLM tree.
    if os.environ.get("VLLM_XPU_V4_MHC_POST_PRE_FIXED_WIDTH_MAX_M") != "8":
        raise RuntimeError("fixed-width MHC max must be 8")
    if os.environ.get("VLLM_XPU_V4_SEGMENTED_ALLREDUCE_MAX_M") != "8":
        raise RuntimeError("segmented all-reduce max must be 8")
    if os.environ.get("VLLM_XPU_V4_INPLACE_ALLREDUCE_M2") != "1":
        raise RuntimeError("qualified M=2 in-place all-reduce must be enabled")

    from vllm.distributed import parallel_state
    from vllm.distributed.parallel_state import GroupCoordinator
    from vllm.models.deepseek_v4.xpu.model import DeepseekV4DecoderLayer

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    if world_size != 4:
        raise RuntimeError(f"requires four ranks, got {world_size}")

    torch.xpu.set_device(local_rank)
    device = torch.device(f"xpu:{local_rank}")
    dist.init_process_group(backend="xccl", device_id=device)
    root = args.corpus.resolve()

    mhc_record = load_record(root, rank, "mhc_post_pre_m2")
    layer = DeepseekV4DecoderLayer.__new__(DeepseekV4DecoderLayer)
    torch.nn.Module.__init__(layer)
    layer.hidden_size = 4096
    layer.hc_mult = 4
    layer.rms_norm_eps = mhc_record["rms_eps"]
    layer.hc_eps = mhc_record["hc_eps"]
    layer.hc_post_alpha = mhc_record["hc_post_alpha"]
    layer.hc_sinkhorn_iters = mhc_record["sinkhorn_iters"]
    layer._mhc_post_pre_fixed_buffers = {}

    mhc_results = {}
    for width in (4, 8):

        def load_mhc(name: str) -> torch.Tensor:
            return tile_rows(load_tensor(root, mhc_record, name, device), width)

        actual = layer._mhc_post_pre(
            load_mhc("x_reduced"),
            load_mhc("residual"),
            load_mhc("post_mix"),
            load_mhc("comb_res_mix"),
            load_tensor(root, mhc_record, "fn", device),
            load_tensor(root, mhc_record, "hc_scale", device),
            load_tensor(root, mhc_record, "hc_base", device),
        )
        expected = tuple(load_mhc(name) for name in OUTPUT_NAMES)
        torch.xpu.synchronize(device)
        mismatches = [
            int((output != reference).sum().item())
            for output, reference in zip(actual, expected, strict=True)
        ]
        mhc_results[str(width)] = mismatches

    allreduce_record = load_record(root, rank, "allreduce_m2")
    collective_results = {}
    for width in (4, 8):
        local_partial = tile_rows(
            load_tensor(root, allreduce_record, "local_partial", device), width
        )
        expected = tile_rows(
            load_tensor(root, allreduce_record, "reduced", device), width
        )

        calls = []

        class WrapperGroup:
            world_size = 4
            unique_name = "tp:mwidth-wrapper-gate"
            use_custom_op_call = True

            def _all_reduce_inplace(self, chunk: torch.Tensor) -> None:
                calls.append({"shape": list(chunk.shape), "group_name": group_name})
                dist.all_reduce(chunk)

            all_reduce = GroupCoordinator.all_reduce

        group = WrapperGroup()
        group_name = group.unique_name
        parallel_state._groups[group_name] = weakref.ref(group)

        def reject_wide(*_args, **_kwargs):
            raise AssertionError("wide out-of-place all-reduce was reached")

        with patch.object(
            torch.ops.vllm,
            "all_reduce",
            new=reject_wide,
        ):
            actual = group.all_reduce(local_partial)
            captured_graphs = []

            def capture_backend(graph_module, _example_inputs):
                captured_graphs.append(str(graph_module.graph))
                return graph_module.forward

            compiled_all_reduce = torch.compile(
                lambda tensor: group.all_reduce(tensor),
                backend=capture_backend,
                fullgraph=True,
                dynamic=False,
            )
            compiled_actual = compiled_all_reduce(local_partial.clone())
        del parallel_state._groups[group_name]
        torch.xpu.synchronize(device)
        graph_text = "\n".join(captured_graphs)
        collective_results[str(width)] = {
            "mismatches": int((actual != expected).sum().item()),
            "compiled_mismatches": int((compiled_actual != expected).sum().item()),
            "calls": calls,
            "compiled_graph": graph_text,
            "compiled_graph_has_segmented_op": "segmented_m2_all_reduce" in graph_text,
            "compiled_graph_has_wide_op": "torch.ops.vllm.all_reduce" in graph_text,
        }

    passed = all(not any(row) for row in mhc_results.values()) and all(
        row["mismatches"] == 0
        and row["compiled_mismatches"] == 0
        and len(row["calls"]) == int(width)
        and all(call["shape"] == [2, 4096] for call in row["calls"])
        and row["compiled_graph_has_segmented_op"]
        and not row["compiled_graph_has_wide_op"]
        for width, row in collective_results.items()
    )
    rank_result = {
        "rank": rank,
        "device": torch.xpu.get_device_name(device),
        "mhc_mismatches": mhc_results,
        "segmented_collectives": collective_results,
        "passed": passed,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rank_path = args.output.with_suffix(f".rank{rank}.json")
    rank_path.write_text(json.dumps(rank_result, indent=2, sort_keys=True) + "\n")
    dist.barrier()

    if rank == 0:
        ranks = [
            json.loads(args.output.with_suffix(f".rank{item}.json").read_text())
            for item in range(world_size)
        ]
        result = {
            "classification": "deepseek_v4_mwidth_vllm_wrapper_gate",
            "scope": "guarded wrapper exactness; not endpoint throughput or acceptance",
            "corpus": str(root),
            "world_size": world_size,
            "passed": all(row["passed"] for row in ranks),
            "ranks": ranks,
        }
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps(result, indent=2, sort_keys=True))

    dist.barrier()
    dist.destroy_process_group()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

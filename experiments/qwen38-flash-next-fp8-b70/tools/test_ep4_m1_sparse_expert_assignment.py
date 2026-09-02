#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import torch

import ep4_m1_sparse_expert_assignment as gate


def test_actual_all_four_expert_maps() -> None:
    covered: list[int] = []
    for rank in range(gate.EP_SIZE):
        expert_map = gate.build_contiguous_ep4_expert_map(rank)
        first = rank * gate.LOCAL_EXPERTS
        assert torch.equal(
            expert_map[first : first + gate.LOCAL_EXPERTS],
            torch.arange(gate.LOCAL_EXPERTS, dtype=torch.int32),
        )
        assert int((expert_map >= 0).sum()) == gate.LOCAL_EXPERTS
        covered.extend(torch.nonzero(expert_map >= 0).reshape(-1).tolist())
    assert covered == list(range(gate.GLOBAL_EXPERTS))


@pytest.mark.parametrize("seed", [20260827, 20260828, 20260829])
def test_100_changing_inputs_all_four_maps(seed: int) -> None:
    generator = torch.Generator(device="cpu").manual_seed(seed)
    seen: set[tuple[int, ...]] = set()
    for _ in range(100):
        topk_ids = (
            torch.randperm(gate.GLOBAL_EXPERTS, generator=generator, dtype=torch.int64)[
                : gate.TOP_K
            ]
            .to(torch.int32)
            .reshape(1, gate.TOP_K)
        )
        seen.add(tuple(topk_ids.reshape(-1).tolist()))
        before = topk_ids.clone()
        for rank in range(gate.EP_SIZE):
            gate.assert_exact_assignment(
                topk_ids, gate.build_contiguous_ep4_expert_map(rank)
            )
        assert torch.equal(topk_ids, before)
    assert len(seen) == 100


@pytest.mark.parametrize("rank", range(gate.EP_SIZE))
def test_adversarial_local_hit_patterns(rank: int) -> None:
    expert_map = gate.build_contiguous_ep4_expert_map(rank)
    for label, topk_ids in gate.adversarial_routes(rank).items():
        gate.assert_exact_assignment(topk_ids, expert_map)
        sorted_ids, expert_ids, num_post = gate.sparse_m1_ep4_candidate(
            topk_ids, expert_map
        )
        expected_hits = int(label.rsplit("_", 1)[1])
        assert int(num_post.item()) == expected_hits * gate.BLOCK_SIZE_M
        active_blocks = int(num_post.item()) // gate.BLOCK_SIZE_M
        assert active_blocks == expected_hits
        assert int((sorted_ids != gate.FLAT_TOKENS).sum()) == expected_hits
        assert torch.all(expert_ids[active_blocks:] == 0)
        assert torch.all(sorted_ids[int(num_post.item()) :] == gate.FLAT_TOKENS)


def test_stable_global_order_and_all_three_outputs() -> None:
    topk_ids = torch.tensor(
        [[511, 0, 384, 127, 256, 128, 383, 255, 1, 510]], dtype=torch.int32
    )
    expert_map = gate.build_contiguous_ep4_expert_map(3)
    sorted_ids, expert_ids, num_post = gate.sparse_m1_ep4_candidate(
        topk_ids, expert_map
    )
    assert sorted_ids[: 48 : gate.BLOCK_SIZE_M].tolist() == [2, 9, 0]
    assert torch.all(sorted_ids[48:] == gate.FLAT_TOKENS)
    assert expert_ids.tolist() == [0, 126, 127, 0, 0, 0, 0, 0, 0, 0]
    assert num_post.tolist() == [48]
    gate.assert_exact_assignment(topk_ids, expert_map)


def test_general_map_orders_by_mapped_local_id() -> None:
    expert_map = gate.build_contiguous_ep4_expert_map(0).clone()
    expert_map[0], expert_map[127] = expert_map[127].clone(), expert_map[0].clone()
    topk_ids = torch.tensor(
        [[400, 127, 300, 0, 200, 1, 511, 126, 128, 255]], dtype=torch.int32
    )
    sorted_ids, expert_ids, num_post = gate.sparse_m1_ep4_candidate(
        topk_ids, expert_map
    )
    assert sorted_ids[: 64 : gate.BLOCK_SIZE_M].tolist() == [1, 5, 7, 3]
    assert expert_ids.tolist() == [0, 1, 126, 127, 0, 0, 0, 0, 0, 0]
    assert num_post.tolist() == [64]
    gate.assert_exact_assignment(topk_ids, expert_map)


def test_zero_tail_and_active_local_expert_zero_are_disambiguated_by_num_post() -> None:
    rank0_map = gate.build_contiguous_ep4_expert_map(0)
    no_local = torch.tensor(
        [[128, 129, 130, 131, 132, 133, 134, 135, 136, 137]], dtype=torch.int32
    )
    sorted_ids, expert_ids, num_post = gate.sparse_m1_ep4_candidate(no_local, rank0_map)
    assert num_post.tolist() == [0]
    assert expert_ids.tolist() == [0] * gate.MAX_BLOCKS
    assert sorted_ids.tolist() == [gate.FLAT_TOKENS] * gate.MAX_PADDED_TOKENS

    local_zero = torch.tensor(
        [[128, 129, 0, 131, 132, 133, 134, 135, 136, 137]], dtype=torch.int32
    )
    sorted_ids, expert_ids, num_post = gate.sparse_m1_ep4_candidate(
        local_zero, rank0_map
    )
    assert num_post.tolist() == [gate.BLOCK_SIZE_M]
    assert expert_ids.tolist() == [0] * gate.MAX_BLOCKS
    assert sorted_ids[0].item() == 2
    assert torch.all(sorted_ids[1:] == gate.FLAT_TOKENS)
    gate.assert_exact_assignment(local_zero, rank0_map)


def test_candidate_does_not_mutate_routes_or_expert_map() -> None:
    topk_ids = torch.tensor(
        [[511, 0, 384, 127, 256, 128, 383, 255, 1, 510]], dtype=torch.int32
    )
    expert_map = gate.build_contiguous_ep4_expert_map(2)
    topk_before = topk_ids.clone()
    map_before = expert_map.clone()
    gate.sparse_m1_ep4_candidate(topk_ids, expert_map)
    assert torch.equal(topk_ids, topk_before)
    assert torch.equal(expert_map, map_before)


@pytest.mark.parametrize(
    ("topk_ids", "error"),
    [
        (torch.zeros((1, 10), dtype=torch.int64), TypeError),
        (torch.arange(10, dtype=torch.int32), ValueError),
        (torch.zeros((1, 10), dtype=torch.int32), ValueError),
        (
            torch.tensor([[0, 1, 2, 3, 4, 5, 6, 7, 8, 512]], dtype=torch.int32),
            ValueError,
        ),
    ],
)
def test_invalid_contract_fails_closed(
    topk_ids: torch.Tensor, error: type[Exception]
) -> None:
    with pytest.raises(error):
        gate.sparse_m1_ep4_candidate(topk_ids, gate.build_contiguous_ep4_expert_map(0))


def test_cpu_runner_is_explicitly_not_launch_authorized() -> None:
    path = Path(__file__).with_name("run-ep4-m1-sparse-expert-assignment-cpu.py")
    spec = importlib.util.spec_from_file_location("ep4_m1_sparse_cpu_runner", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.run_suite()
    assert result["launch_authorized"] is False
    assert result["endpoint_authorized"] is False
    assert result["gpu_execution_authorized"] is False
    assert result["input_tensors_unchanged"] is True
    assert result["coverage"]["changing_rank_cases"] == 1200
    assert result["coverage"]["adversarial_rank_cases"] == 16

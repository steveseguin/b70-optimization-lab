#!/usr/bin/env python3
"""CPU references for a sparse M=1, top-k=10, EP4 assignment candidate.

This is experiment-local correctness code.  It does not patch vLLM and it is
not an XPU or endpoint launcher.
"""

from __future__ import annotations

from collections.abc import Callable

import torch

GLOBAL_EXPERTS = 512
LOCAL_EXPERTS = 128
EP_SIZE = 4
TOP_K = 10
BLOCK_SIZE_M = 16
FLAT_TOKENS = TOP_K
MAX_PADDED_TOKENS = TOP_K * BLOCK_SIZE_M
MAX_BLOCKS = MAX_PADDED_TOKENS // BLOCK_SIZE_M


Assignment = tuple[torch.Tensor, torch.Tensor, torch.Tensor]


def build_contiguous_ep4_expert_map(ep_rank: int) -> torch.Tensor:
    """Build the exact contiguous 512 -> 128 expert map used by the TP4 gate."""
    if not 0 <= ep_rank < EP_SIZE:
        raise ValueError(f"ep_rank must be in [0, {EP_SIZE}), got {ep_rank}")
    expert_map = torch.full((GLOBAL_EXPERTS,), -1, dtype=torch.int32)
    first = ep_rank * LOCAL_EXPERTS
    expert_map[first : first + LOCAL_EXPERTS] = torch.arange(
        LOCAL_EXPERTS, dtype=torch.int32
    )
    return expert_map


def _validate(topk_ids: torch.Tensor, expert_map: torch.Tensor) -> None:
    if topk_ids.device.type != "cpu" or expert_map.device.type != "cpu":
        raise ValueError("this preregistered reference is CPU-only")
    if topk_ids.dtype != torch.int32:
        raise TypeError(f"topk_ids must be int32, got {topk_ids.dtype}")
    if topk_ids.shape != (1, TOP_K):
        raise ValueError(f"topk_ids must have shape (1, {TOP_K})")
    if expert_map.dtype != torch.int32 or expert_map.shape != (GLOBAL_EXPERTS,):
        raise ValueError("expert_map must be an int32 tensor with shape (512,)")
    flat = topk_ids.reshape(-1)
    if bool(torch.any(flat < 0)) or bool(torch.any(flat >= GLOBAL_EXPERTS)):
        raise ValueError("topk_ids must be global expert IDs in [0, 512)")
    if int(torch.unique(flat).numel()) != TOP_K:
        raise ValueError("M=1 TopKGating contract requires ten unique expert IDs")
    local = expert_map[expert_map >= 0]
    if local.numel() != LOCAL_EXPERTS or not torch.equal(
        torch.sort(local).values, torch.arange(LOCAL_EXPERTS, dtype=torch.int32)
    ):
        raise ValueError("expert_map must contain each local expert exactly once")
    if bool(torch.any((expert_map < -1) | (expert_map >= LOCAL_EXPERTS))):
        raise ValueError("expert_map values must be -1 or a local expert ID")


def _empty_outputs() -> Assignment:
    return (
        torch.full((MAX_PADDED_TOKENS,), FLAT_TOKENS, dtype=torch.int32),
        torch.zeros((MAX_BLOCKS,), dtype=torch.int32),
        torch.zeros((1,), dtype=torch.int32),
    )


def generic_512_scan_authority(
    topk_ids: torch.Tensor, expert_map: torch.Tensor
) -> Assignment:
    """Independent CPU authority matching mapped-local filtering semantics."""
    _validate(topk_ids, expert_map)
    flat = topk_ids.reshape(-1)
    sorted_token_ids, expert_ids, num_tokens_post_pad = _empty_outputs()
    block = 0
    # Production maps before counting. Scan all 512 map entries here to keep
    # this authority independent of the ten-entry sparse candidate.
    for local_expert in range(LOCAL_EXPERTS):
        matches = torch.nonzero(expert_map == local_expert, as_tuple=False).reshape(-1)
        if matches.numel() != 1:
            raise ValueError("expert_map must map exactly one global ID per local ID")
        global_expert = int(matches.item())
        positions = torch.nonzero(flat == global_expert, as_tuple=False).reshape(-1)
        if positions.numel() == 0:
            continue
        start = block * BLOCK_SIZE_M
        sorted_token_ids[start : start + positions.numel()] = positions.to(torch.int32)
        expert_ids[block] = local_expert
        block += 1
    num_tokens_post_pad[0] = block * BLOCK_SIZE_M
    return sorted_token_ids, expert_ids, num_tokens_post_pad


def sparse_m1_ep4_candidate(
    topk_ids: torch.Tensor, expert_map: torch.Tensor
) -> Assignment:
    """Filter and order only the selected experts, preserving all three outputs."""
    _validate(topk_ids, expert_map)
    flat = topk_ids.reshape(-1)
    # Production maps global to local first and ignores remote (-1) entries.
    # Secondary position key makes stable order explicit.
    selected = sorted(
        (
            (int(expert_map[int(global_expert)]), position)
            for position, global_expert in enumerate(flat)
            if int(expert_map[int(global_expert)]) >= 0
        ),
        key=lambda item: (item[0], item[1]),
    )
    sorted_token_ids, expert_ids, num_tokens_post_pad = _empty_outputs()
    for block, (local_expert, position) in enumerate(selected):
        sorted_token_ids[block * BLOCK_SIZE_M] = position
        expert_ids[block] = local_expert
    num_tokens_post_pad[0] = len(selected) * BLOCK_SIZE_M
    return sorted_token_ids, expert_ids, num_tokens_post_pad


def assert_exact_assignment(
    topk_ids: torch.Tensor,
    expert_map: torch.Tensor,
    candidate: Callable[[torch.Tensor, torch.Tensor], Assignment] = (
        sparse_m1_ep4_candidate
    ),
) -> None:
    authority = generic_512_scan_authority(topk_ids, expert_map)
    actual = candidate(topk_ids, expert_map)
    names = ("sorted_token_ids", "expert_ids", "num_tokens_post_pad")
    for name, expected_tensor, actual_tensor in zip(names, authority, actual):
        if not torch.equal(expected_tensor, actual_tensor):
            raise AssertionError(
                f"{name} differs from the generic 512-expert authority"
            )


def adversarial_routes(ep_rank: int) -> dict[str, torch.Tensor]:
    """Return boundary/interleaved cases with 0, 1, 5, and 10 local hits."""
    expert_map = build_contiguous_ep4_expert_map(ep_rank)
    local_ids = torch.nonzero(expert_map >= 0, as_tuple=False).reshape(-1).tolist()
    remote_ids = torch.nonzero(expert_map < 0, as_tuple=False).reshape(-1).tolist()
    local_pick = [local_ids[0], local_ids[-1], *local_ids[1:9]]
    remote_pick = [remote_ids[0], remote_ids[-1], *remote_ids[1:9]]

    def interleave(local_hits: int) -> torch.Tensor:
        values: list[int] = []
        locals_left = local_pick[:local_hits]
        remotes_left = remote_pick[: TOP_K - local_hits]
        while locals_left or remotes_left:
            if remotes_left:
                values.append(remotes_left.pop())
            if locals_left:
                values.append(locals_left.pop())
        return torch.tensor(values[:TOP_K], dtype=torch.int32).reshape(1, TOP_K)

    return {
        "local_hits_0": interleave(0),
        "local_hits_1": interleave(1),
        "local_hits_5": interleave(5),
        "local_hits_10": interleave(10),
    }

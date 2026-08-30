#!/usr/bin/env python3
"""Check Qwen3.8 PLE chunked-prefill state reset and repeatability on XPU."""

import argparse
import hashlib
import json
from types import SimpleNamespace

import torch
import torch.nn as nn

from vllm.models.qwen4_exp.nvidia.ple_layer import Qwen4ExpPLELayer


def tensor_sha256(tensor: torch.Tensor) -> str:
    raw = tensor.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
    return hashlib.sha256(raw).hexdigest()


def make_chunk(
    chunk_index: int,
    chunk_tokens: int,
    hidden: int,
    device: torch.device,
) -> torch.Tensor:
    indices = torch.arange(chunk_tokens * hidden, dtype=torch.int64, device=device)
    values = ((indices * 17 + chunk_index * 31) % 251 - 125).to(torch.float32)
    return (values / 128).to(torch.bfloat16).reshape(chunk_tokens, hidden)


def run_trajectory(
    layer: Qwen4ExpPLELayer,
    *,
    chunks: int,
    chunk_tokens: int,
    conv_state: torch.Tensor,
    conv_weights: torch.Tensor,
    device: torch.device,
) -> tuple[str, str]:
    output_hash = hashlib.sha256()
    # Slot 0 is NULL_BLOCK_ID and must remain reserved for padding. Exercise
    # the first real cache slot so state read/write behavior is admissible.
    state_indices = torch.tensor([1], dtype=torch.int64, device=device)
    query_start_loc = torch.tensor([0, chunk_tokens], dtype=torch.int32, device=device)

    for chunk_index in range(chunks):
        metadata = SimpleNamespace(
            non_spec_query_start_loc=query_start_loc,
            has_initial_states_p=torch.tensor(
                [chunk_index > 0], dtype=torch.bool, device=device
            ),
            max_prefill_query_len=chunk_tokens,
        )
        inputs = make_chunk(chunk_index, chunk_tokens, conv_state.shape[1], device)
        output = layer._short_conv_dilated_prefill_batched(
            inputs,
            metadata,
            conv_state,
            conv_weights,
            state_indices,
            num_prefills=1,
            num_decode_tokens=0,
            num_prefill_tokens=chunk_tokens,
        )
        torch.xpu.synchronize()
        output_hash.update(
            output.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
        )

    return output_hash.hexdigest(), tensor_sha256(conv_state)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", type=int, default=64)
    parser.add_argument("--chunk-tokens", type=int, default=64)
    parser.add_argument("--hidden", type=int, default=10240)
    parser.add_argument("--conv-state-len", type=int, default=9)
    parser.add_argument("--dilation", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()
    if (
        min(
            args.chunks,
            args.chunk_tokens,
            args.hidden,
            args.conv_state_len,
            args.dilation,
            args.repeats,
        )
        <= 0
    ):
        raise ValueError("all dimensions and repeat counts must be positive")
    if args.conv_state_len % args.dilation:
        raise ValueError("conv-state-len must be divisible by dilation")

    device = torch.device("xpu:0")
    torch.xpu.set_device(device)
    layer = Qwen4ExpPLELayer.__new__(Qwen4ExpPLELayer)
    nn.Module.__init__(layer)
    layer.conv_state_len = args.conv_state_len
    layer.short_conv_dilation = args.dilation
    kernel = args.conv_state_len // args.dilation + 1
    weight_indices = torch.arange(args.hidden * kernel, dtype=torch.int64)
    conv_weights = (
        (((weight_indices * 13) % 127 - 63).to(torch.float32) / 256)
        .to(torch.bfloat16)
        .reshape(args.hidden, kernel)
        .to(device)
    )

    clean_results: list[tuple[str, str]] = []
    dirty_results: list[tuple[str, str]] = []
    pair_differences: list[dict[str, object]] = []
    with torch.inference_mode():
        for _ in range(args.repeats):
            clean_state = torch.zeros(
                2,
                args.hidden,
                args.conv_state_len,
                dtype=torch.bfloat16,
                device=device,
            )
            dirty_state = torch.zeros_like(clean_state)
            dirty_state[1].fill_(7)
            clean_result = run_trajectory(
                layer,
                chunks=args.chunks,
                chunk_tokens=args.chunk_tokens,
                conv_state=clean_state,
                conv_weights=conv_weights,
                device=device,
            )
            dirty_result = run_trajectory(
                layer,
                chunks=args.chunks,
                chunk_tokens=args.chunk_tokens,
                conv_state=dirty_state,
                conv_weights=conv_weights,
                device=device,
            )
            clean_results.append(clean_result)
            dirty_results.append(dirty_result)
            clean_cpu = clean_state.cpu()
            dirty_cpu = dirty_state.cpu()
            numeric_difference = clean_cpu.float() - dirty_cpu.float()
            clean_bytes = clean_cpu.contiguous().view(torch.uint8)
            dirty_bytes = dirty_cpu.contiguous().view(torch.uint8)
            pair_differences.append(
                {
                    "differing_bytes": int((clean_bytes != dirty_bytes).sum()),
                    "differing_values": int((clean_cpu != dirty_cpu).sum()),
                    "max_abs_difference": float(numeric_difference.abs().max()),
                    "output_hash_match": clean_result[0] == dirty_result[0],
                    "state_hash_match": clean_result[1] == dirty_result[1],
                }
            )

    clean_unique = sorted(set(clean_results))
    dirty_unique = sorted(set(dirty_results))
    report = {
        "chunk_tokens": args.chunk_tokens,
        "chunks": args.chunks,
        "conv_state_len": args.conv_state_len,
        "dilation": args.dilation,
        "dirty_first_chunk_reset_matches_clean": clean_unique == dirty_unique,
        "dirty_unique_trajectory_hashes": dirty_unique,
        "clean_unique_trajectory_hashes": clean_unique,
        "hidden": args.hidden,
        "pair_differences": pair_differences,
        "repeats": args.repeats,
        "tokens_per_trajectory": args.chunks * args.chunk_tokens,
    }
    print(json.dumps(report, sort_keys=True), flush=True)
    if len(clean_unique) != 1 or len(dirty_unique) != 1 or clean_unique != dirty_unique:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

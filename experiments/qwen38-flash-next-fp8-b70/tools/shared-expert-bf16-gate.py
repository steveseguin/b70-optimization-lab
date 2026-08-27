#!/usr/bin/env python3
"""Exercise one real Flash-Next shared expert, one TP4 shard at a time."""

import argparse
import json
import time
from pathlib import Path

import torch
import torch.nn.functional as F
import vllm_xpu_kernels._C  # noqa: F401
from safetensors import safe_open

def summarize(name: str, value: torch.Tensor, started: float) -> dict[str, object]:
    torch.xpu.synchronize()
    host = value.float().cpu()
    result = {
        "event": "phase_pass",
        "phase": name,
        "seconds": time.monotonic() - started,
        "shape": list(value.shape),
        "finite": bool(torch.isfinite(host).all()),
        "max_abs": float(host.abs().max()),
        "mean_abs": float(host.abs().mean()),
    }
    print(json.dumps(result, sort_keys=True), flush=True)
    if not result["finite"]:
        raise RuntimeError(f"non-finite output after {name}: {result}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tokens", type=int, choices=(1, 64), required=True)
    parser.add_argument("--tp-rank", type=int, choices=range(4), default=0)
    parser.add_argument(
        "--activation",
        choices=("custom", "native"),
        default="custom",
        help="Use the XPU custom op or its mathematically equivalent torch path.",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=Path("/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8"),
    )
    args = parser.parse_args()

    torch.manual_seed(20260826)
    hidden_size = 2560
    shared_intermediate = 640
    local_intermediate = shared_intermediate // 4
    first = args.tp_rank * local_intermediate
    last = first + local_intermediate
    device = torch.device("xpu:0")
    dtype = torch.bfloat16
    shard = args.model_path / "model-00003-of-00131.safetensors"
    if not shard.is_file():
        raise FileNotFoundError(shard)

    prefix = "model.language_model.layers.0.mlp"
    keys = {
        "gate": f"{prefix}.shared_expert.gate_proj.weight",
        "up": f"{prefix}.shared_expert.up_proj.weight",
        "down": f"{prefix}.shared_expert.down_proj.weight",
        "expert_gate": f"{prefix}.shared_expert_gate.weight",
    }
    with safe_open(shard, framework="pt", device="cpu") as checkpoint:
        missing = sorted(set(keys.values()) - set(checkpoint.keys()))
        if missing:
            raise KeyError(f"shared-expert tensors missing from {shard}: {missing}")
        gate = checkpoint.get_tensor(keys["gate"])[first:last].contiguous()
        up = checkpoint.get_tensor(keys["up"])[first:last].contiguous()
        down = checkpoint.get_tensor(keys["down"])[:, first:last].contiguous()
        expert_gate = checkpoint.get_tensor(keys["expert_gate"]).contiguous()

    expected = {
        "gate": [local_intermediate, hidden_size],
        "up": [local_intermediate, hidden_size],
        "down": [hidden_size, local_intermediate],
        "expert_gate": [1, hidden_size],
    }
    actual = {
        "gate": list(gate.shape),
        "up": list(up.shape),
        "down": list(down.shape),
        "expert_gate": list(expert_gate.shape),
    }
    if actual != expected:
        raise RuntimeError(f"unexpected TP4 shared-expert shapes: {actual}")
    if any(t.dtype != dtype for t in (gate, up, down, expert_gate)):
        raise RuntimeError("shared-expert checkpoint tensors are not all BF16")

    identity = {
        "tokens": args.tokens,
        "tp_rank": args.tp_rank,
        "tp_size": 4,
        "hidden_size": hidden_size,
        "shared_intermediate_size": shared_intermediate,
        "local_intermediate_size": local_intermediate,
        "activation": args.activation,
        "checkpoint_shard": shard.name,
        "checkpoint_shapes": actual,
        "dtype": str(dtype),
    }
    print(json.dumps({"event": "start", "identity": identity}, sort_keys=True), flush=True)

    load_started = time.monotonic()
    gate_up_weight = torch.cat((gate, up), dim=0).to(device)
    down_weight = down.to(device)
    expert_gate_weight = expert_gate.to(device)
    torch.xpu.synchronize()
    print(
        json.dumps(
            {
                "event": "weights_ready",
                "seconds": time.monotonic() - load_started,
                "bytes": sum(
                    tensor.numel() * tensor.element_size()
                    for tensor in (gate_up_weight, down_weight, expert_gate_weight)
                ),
            },
            sort_keys=True,
        ),
        flush=True,
    )

    hidden_cpu = torch.randn((args.tokens, hidden_size), dtype=dtype).mul_(0.01)
    hidden = hidden_cpu.to(device)

    phase = time.monotonic()
    gate_up_output = F.linear(hidden, gate_up_weight)
    summarize("gate_up_linear", gate_up_output, phase)

    phase = time.monotonic()
    if args.activation == "custom":
        activated = torch.empty(
            (args.tokens, local_intermediate), dtype=dtype, device=device
        )
        torch.ops._C.silu_and_mul(activated, gate_up_output)
    else:
        activated = F.silu(gate_up_output[..., :local_intermediate]) * gate_up_output[
            ..., local_intermediate:
        ]
    summarize("silu_and_mul", activated, phase)

    phase = time.monotonic()
    down_output = F.linear(activated, down_weight)
    summarize("down_linear", down_output, phase)

    phase = time.monotonic()
    gate_output = F.linear(hidden, expert_gate_weight)
    summarize("shared_expert_gate_linear", gate_output, phase)

    phase = time.monotonic()
    output = torch.sigmoid(gate_output) * down_output
    final = summarize("sigmoid_multiply", output, phase)
    print(
        json.dumps(
            {
                "status": "pass",
                "identity": identity,
                "output_shape": final["shape"],
                "output_finite": final["finite"],
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

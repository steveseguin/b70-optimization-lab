#!/usr/bin/env python3
"""Run one real-weight HC combine+norm C/A/C arm under XPU graph replay."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import time
from typing import Any, Callable

from safetensors import safe_open
import torch


MODEL_REVISION = "bcd9f01ddc9cff2316eb84281bebcd5b058bddce"
MODEL_INDEX_SHA256 = "0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6"
MODEL_CONFIG_SHA256 = "99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d"
AUTHORITY_SOURCE = Path(
    "/home/steve/src/vllm-current-main/vllm/models/qwen4_exp/amd/ops/hc.py"
)
AUTHORITY_SOURCE_SHA256 = (
    "a2ed67ce6240a150a75247097f0a49b4652d5bf1f5db1cdaf34ad5ec52faa8da"
)
CALLS_PER_CYCLE = 95
EXACT_REPLAYS = 100
TIMING_WARMUPS = 10
TIMING_BATCHES = 9
ITERATIONS_PER_BATCH = 50
EPS = 1e-6

SENTINELS = {
    "l0-attn": {
        "layer": 0,
        "role": "attn",
        "shard": "model-00001-of-00131.safetensors",
        "weight": "model.language_model.layers.0.attn_hyper_connection.hc_norm.weight",
        "weight_sha256": "0a3213d5fbfe4043a4800e3ca12cd05c3e7ced745f5aca03fc67ada75d169f98",
    },
    "l0-mlp": {
        "layer": 0,
        "role": "mlp",
        "shard": "model-00003-of-00131.safetensors",
        "weight": "model.language_model.layers.0.mlp_hyper_connection.hc_norm.weight",
        "weight_sha256": "e1da29c3232c056fb6869275c5cbbe527d591b88dd967e747716e23f1a89a5bb",
    },
    "l47-attn": {
        "layer": 47,
        "role": "attn",
        "shard": "model-00118-of-00131.safetensors",
        "weight": "model.language_model.layers.47.attn_hyper_connection.hc_norm.weight",
        "weight_sha256": "90c3284c07d7dfe2d81ba6ceae92d8b914591094fbefc2717b7505a78facb816",
    },
    "l47-mlp": {
        "layer": 47,
        "role": "mlp",
        "shard": "model-00120-of-00131.safetensors",
        "weight": "model.language_model.layers.47.mlp_hyper_connection.hc_norm.weight",
        "weight_sha256": "66863fc1e9cae0568b923baf5fce89002527f53fd721e89ab5c1968a7d297452",
    },
}

CORE_PATH = Path(__file__).with_name("hc_combine_norm_exact_staged.py")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tensor_sha256(tensor: torch.Tensor) -> str:
    return hashlib.sha256(
        tensor.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
    ).hexdigest()


def pair_series_sha256(
    pairs: list[tuple[torch.Tensor, torch.Tensor]],
) -> str:
    digest = hashlib.sha256()
    for combined, normalized in pairs:
        digest.update(
            combined.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
        )
        digest.update(
            normalized.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
        )
    return digest.hexdigest()


def load_core() -> Any:
    spec = importlib.util.spec_from_file_location("q38_hc_exact_staged", CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import candidate core: {CORE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ancestor_pids() -> set[int]:
    """Return this process and every ancestor up to init.

    The frozen runner launches the gate as `setsid env ... timeout ... python
    gate --model-path <checkpoint>`, so the `timeout` and `env` ancestors carry
    the checkpoint path in their own command lines. They are the gate's own
    lineage, not a model server, and must not trip the refusal.
    """
    pids: set[int] = set()
    pid = os.getpid()
    while pid > 1 and pid not in pids:
        pids.add(pid)
        try:
            fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
            pid = int(fields[1])
        except (OSError, IndexError, ValueError):
            break
    return pids


def refuse_active_model_server() -> None:
    own = _ancestor_pids()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) in own:
            continue
        try:
            cmdline = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        lowered = cmdline.lower()
        if "qwen3.8-flash-next-fp8" in lowered or (
            "vllm" in lowered and "api_server" in lowered
        ):
            raise RuntimeError(
                f"active model/server process blocks component gate: {entry.name}"
            )


def verify_external_model_mount(model: Path) -> dict[str, str]:
    result = subprocess.run(
        ["findmnt", "-no", "SOURCE,FSTYPE,TARGET", "--target", str(model)],
        check=True,
        capture_output=True,
        text=True,
    )
    fields = result.stdout.strip().split()
    if fields != ["/dev/sda2", "fuseblk", "/mnt/usb-models"]:
        raise RuntimeError(f"external checkpoint mount identity drifted: {fields}")
    return {"source": fields[0], "fstype": fields[1], "target": fields[2]}


def load_weight(model: Path, sentinel: str) -> tuple[torch.Tensor, dict[str, Any]]:
    identity = SENTINELS[sentinel]
    index_path = model / "model.safetensors.index.json"
    config_path = model / "config.json"
    if file_sha256(index_path) != MODEL_INDEX_SHA256:
        raise RuntimeError("model index drifted")
    if file_sha256(config_path) != MODEL_CONFIG_SHA256:
        raise RuntimeError("model config drifted")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("weight_map", {}).get(identity["weight"]) != identity["shard"]:
        raise RuntimeError("sentinel-to-shard mapping drifted")
    shard = (model / identity["shard"]).resolve()
    with safe_open(shard, framework="pt", device="cpu") as handle:
        weight = handle.get_tensor(identity["weight"]).contiguous()
    if weight.shape != (10240,) or weight.dtype != torch.bfloat16:
        raise RuntimeError("sentinel weight shape or dtype drifted")
    actual_hash = tensor_sha256(weight)
    if actual_hash != identity["weight_sha256"]:
        raise RuntimeError("sentinel weight bytes drifted")
    stat = shard.stat()
    return weight, {
        **identity,
        "shard_path": str(shard),
        "shard_size": stat.st_size,
        "weight_sha256": actual_hash,
    }


def make_cpu_inputs(core: Any, seed: int, replay: int) -> tuple[torch.Tensor, ...]:
    generator = torch.Generator(device="cpu").manual_seed(seed * 1000 + replay)
    residual = (
        torch.randn(
            (CALLS_PER_CYCLE, 1, core.HYPER_HIDDEN_SIZE),
            generator=generator,
            dtype=torch.bfloat16,
        )
        * 0.1
    ).contiguous()
    block = (
        torch.randn(
            (CALLS_PER_CYCLE, 1, core.HIDDEN_SIZE),
            generator=generator,
            dtype=torch.bfloat16,
        )
        * 0.1
    ).contiguous()
    injection = (
        torch.randn(
            (CALLS_PER_CYCLE, 1, core.HC_COUNT),
            generator=generator,
            dtype=torch.bfloat16,
        )
        * 2.0
    ).contiguous()
    return residual, block, injection


def cycle(
    operation: Callable[..., tuple[torch.Tensor, torch.Tensor]],
    residual: torch.Tensor,
    block: torch.Tensor,
    injection: torch.Tensor,
    parameter: torch.Tensor,
) -> list[tuple[torch.Tensor, torch.Tensor]]:
    return [
        operation(residual[i], block[i], injection[i], parameter, EPS)
        for i in range(CALLS_PER_CYCLE)
    ]


def assert_pairs_equal(
    actual: list[tuple[torch.Tensor, torch.Tensor]],
    expected: list[tuple[torch.Tensor, torch.Tensor]],
    label: str,
) -> None:
    if len(actual) != CALLS_PER_CYCLE or len(expected) != CALLS_PER_CYCLE:
        raise AssertionError(f"{label}: incomplete 95-call output")
    for index, (actual_pair, expected_pair) in enumerate(zip(actual, expected)):
        if not torch.equal(actual_pair[0], expected_pair[0]):
            raise AssertionError(f"{label}: combined output differs at call {index}")
        if not torch.equal(actual_pair[1], expected_pair[1]):
            raise AssertionError(f"{label}: normalized output differs at call {index}")


def run_adversarial_suite(core: Any, weight: torch.Tensor, affine: torch.Tensor) -> str:
    bits = torch.tensor(
        [
            0x0000,
            0x8000,
            0x0001,
            0x8001,
            0x007F,
            0x807F,
            0x0080,
            0x8080,
            0x3F80,
            0xBF80,
            0x41BE,
            0xC1BE,
            0x4180,
            0xC180,
        ],
        dtype=torch.uint16,
    ).view(torch.bfloat16)

    def expand(count: int) -> torch.Tensor:
        repeats = (count + bits.numel() - 1) // bits.numel()
        return bits.repeat(repeats)[:count].reshape(1, -1).contiguous().to("xpu")

    residual = expand(core.HYPER_HIDDEN_SIZE)
    block = expand(core.HIDDEN_SIZE).flip(-1).contiguous()
    injection = (
        torch.tensor([[0x41BE, 0xC1BE, 0x0001, 0x8001]], dtype=torch.uint16)
        .view(torch.bfloat16)
        .to("xpu")
    )
    authority = core.torch_authority_hc_combine_norm(
        residual, block, injection, weight, EPS
    )
    candidate = core.exact_staged_hc_combine_norm(
        residual, block, injection, affine, EPS
    )
    torch.xpu.synchronize()
    if not all(torch.equal(a, b) for a, b in zip(authority, candidate)):
        raise AssertionError("adversarial BF16 candidate differs from authority")
    if not all(torch.isfinite(value).all().item() for value in candidate):
        raise AssertionError("adversarial BF16 candidate is nonfinite")
    return pair_series_sha256([candidate])


def timed_graph(graph: torch.xpu.XPUGraph) -> tuple[float, list[float]]:
    for _ in range(TIMING_WARMUPS):
        graph.replay()
    torch.xpu.synchronize()
    samples: list[float] = []
    for _ in range(TIMING_BATCHES):
        started = time.perf_counter_ns()
        for _ in range(ITERATIONS_PER_BATCH):
            graph.replay()
        torch.xpu.synchronize()
        samples.append(
            (time.perf_counter_ns() - started) / ITERATIONS_PER_BATCH / 1000.0
        )
    return statistics.median(samples), samples


def read_control_authority(path: Path) -> dict[str, Any]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not lines:
        raise ValueError("control authority is empty")
    value = json.loads(lines[-1])
    if (
        value.get("status") != "pass"
        or value.get("classification")
        != "qwen38_hc_combine_norm_exact_xpu_graph_component"
    ):
        raise ValueError("control authority header is invalid")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--sentinel", choices=sorted(SENTINELS), required=True)
    parser.add_argument(
        "--seed", type=int, choices=[20260826, 20260827, 20260830], required=True
    )
    parser.add_argument(
        "--arm", choices=["control-before", "candidate", "control-after"], required=True
    )
    parser.add_argument("--control-authority-json", type=Path)
    args = parser.parse_args()

    if args.model_revision != MODEL_REVISION:
        raise RuntimeError("model revision drifted")
    if args.arm == "control-before" and args.control_authority_json is not None:
        raise ValueError("control-before cannot consume an authority")
    if args.arm != "control-before" and args.control_authority_json is None:
        raise ValueError("candidate/control-after require control authority")
    if file_sha256(AUTHORITY_SOURCE) != AUTHORITY_SOURCE_SHA256:
        raise RuntimeError("live HC authority source drifted")
    refuse_active_model_server()
    model = args.model_path.resolve()
    mount = verify_external_model_mount(model)
    weight_cpu, weight_identity = load_weight(model, args.sentinel)
    core = load_core()
    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        raise RuntimeError("selector must expose exactly one XPU")

    weight = weight_cpu.to("xpu")
    affine = core.build_exact_norm_affine(weight)
    core.validate_exact_norm_affine(weight, affine)
    adversarial_sha256 = run_adversarial_suite(core, weight, affine)

    residual = torch.empty(
        (CALLS_PER_CYCLE, 1, core.HYPER_HIDDEN_SIZE),
        dtype=torch.bfloat16,
        device="xpu",
    )
    block = torch.empty(
        (CALLS_PER_CYCLE, 1, core.HIDDEN_SIZE),
        dtype=torch.bfloat16,
        device="xpu",
    )
    injection = torch.empty(
        (CALLS_PER_CYCLE, 1, core.HC_COUNT),
        dtype=torch.bfloat16,
        device="xpu",
    )
    if args.arm == "candidate":
        operation = core.exact_staged_hc_combine_norm
        parameter = affine
    else:
        operation = core.torch_authority_hc_combine_norm
        parameter = weight

    first_inputs = make_cpu_inputs(core, args.seed, 0)
    residual.copy_(first_inputs[0])
    block.copy_(first_inputs[1])
    injection.copy_(first_inputs[2])
    graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(graph):
        graph_outputs = cycle(operation, residual, block, injection, parameter)
    torch.xpu.synchronize()

    graph_hashes: list[str] = []
    for replay in range(EXACT_REPLAYS):
        values = make_cpu_inputs(core, args.seed, replay)
        residual.copy_(values[0])
        block.copy_(values[1])
        injection.copy_(values[2])
        eager_authority = cycle(
            core.torch_authority_hc_combine_norm,
            residual,
            block,
            injection,
            weight,
        )
        if args.arm == "candidate":
            eager_candidate = cycle(operation, residual, block, injection, parameter)
            assert_pairs_equal(eager_candidate, eager_authority, "eager candidate")
        graph.replay()
        torch.xpu.synchronize()
        assert_pairs_equal(graph_outputs, eager_authority, "graph replay")
        graph_hashes.append(pair_series_sha256(graph_outputs))

    if len(set(graph_hashes)) != EXACT_REPLAYS:
        raise AssertionError("changing-input graph hash series is not unique")
    authority_path: str | None = None
    matches_control = True
    if args.control_authority_json is not None:
        authority_path = str(args.control_authority_json.resolve())
        control = read_control_authority(args.control_authority_json)
        matches_control = (
            control.get("identity", {}).get("sentinel") == args.sentinel
            and control.get("identity", {}).get("seed") == args.seed
            and control.get("correctness", {}).get("graph_hashes") == graph_hashes
        )
        if not matches_control:
            raise AssertionError(
                "arm hash series differs from control-before authority"
            )

    median_us, samples_us = timed_graph(graph)
    if not math.isfinite(median_us) or median_us <= 0:
        raise AssertionError("graph timing is invalid")
    print(
        json.dumps(
            {
                "schema_version": 1,
                "status": "pass",
                "classification": "qwen38_hc_combine_norm_exact_xpu_graph_component",
                "identity": {
                    "model_path": str(model),
                    "model_revision": MODEL_REVISION,
                    "model_index_sha256": MODEL_INDEX_SHA256,
                    "model_config_sha256": MODEL_CONFIG_SHA256,
                    "model_mount": mount,
                    "sentinel": args.sentinel,
                    "layer": weight_identity["layer"],
                    "role": weight_identity["role"],
                    "seed": args.seed,
                    "weight": weight_identity,
                    "authority_source": str(AUTHORITY_SOURCE),
                    "authority_source_sha256": AUTHORITY_SOURCE_SHA256,
                    "candidate_core": str(CORE_PATH.resolve()),
                    "candidate_core_sha256": file_sha256(CORE_PATH),
                    "shape": {
                        "residual": [1, 10240],
                        "block_output": [1, 2560],
                        "injection_logits": [1, 4],
                        "norm_weight": [10240],
                        "hc_count": 4,
                    },
                    "dtype": "bfloat16",
                },
                "treatment": {
                    "arm": args.arm,
                    "runtime_delta": (
                        "hoist exact 1.0 + norm_weight.float() outside graph"
                        if args.arm == "candidate"
                        else "unchanged Torch XPU authority"
                    ),
                    "sigmoid_changed": False,
                    "rsqrt_changed": False,
                    "arithmetic_order_changed": False,
                    "explicit_bf16_combine_rounding_preserved": True,
                },
                "correctness": {
                    "calls_per_graph_cycle": CALLS_PER_CYCLE,
                    "exact_replays": EXACT_REPLAYS,
                    "both_outputs_exact_to_eager_authority": True,
                    "unique_graph_hashes": len(set(graph_hashes)),
                    "graph_hashes": graph_hashes,
                    "control_authority_path": authority_path,
                    "matches_control_authority": matches_control,
                    "adversarial_bf16_passed": True,
                    "adversarial_pair_sha256": adversarial_sha256,
                    "cached_affine_validated_before_capture": True,
                },
                "graph": {
                    "capture": "clean static torch.xpu.XPUGraph",
                    "timing_excludes_input_copy_and_exactness_checks": True,
                    "warmups": TIMING_WARMUPS,
                    "batches": TIMING_BATCHES,
                    "iterations_per_batch": ITERATIONS_PER_BATCH,
                    "cycle_median_us": median_us,
                    "cycle_samples_us": samples_us,
                },
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Reconstruct exact real Laguna M8 routes for the W1 timing gate."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

import torch

import vllm_xpu_kernels._moe_C as moe_extension


EXPECTED_KERNEL_ROOT = Path(
    "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc"
).resolve()
ROUTER_GATE_PATH = (
    Path(__file__).resolve().parent / "gate_laguna_m8_bf16_router_topk.py"
)


def tensor_hash(tensor: torch.Tensor) -> str:
    raw = (
        tensor.detach()
        .cpu()
        .contiguous()
        .view(torch.uint8)
        .numpy()
        .tobytes()
    )
    return hashlib.sha256(raw).hexdigest()


def load_router_gate() -> Any:
    spec = importlib.util.spec_from_file_location(
        "laguna_router_gate_fixture_source", ROUTER_GATE_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load router gate from {ROUTER_GATE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path, required=True)
    args = parser.parse_args()

    if os.environ.get("ZE_AFFINITY_MASK") != "0":
        raise RuntimeError("fixture extraction requires ZE_AFFINITY_MASK=0")
    if torch.xpu.device_count() != 1:
        raise RuntimeError("fixture extraction requires exactly one visible XPU")
    torch.xpu.set_device(0)
    extension_path = Path(moe_extension.__file__).resolve()
    expected_extension = (
        EXPECTED_KERNEL_ROOT / "vllm_xpu_kernels" / "_moe_C.abi3.so"
    )
    if extension_path != expected_extension:
        raise RuntimeError(
            f"wrong MoE extension resolved: {extension_path}"
        )

    gate = load_router_gate()
    sources = gate.production_source_manifest(
        gate.DEFAULT_MODEL_ROOT,
        gate.DEFAULT_TRACE_DIRS,
    )
    runtime_fixtures, production_report = gate.prepare_production_fixtures(
        torch, sources
    )
    if len(runtime_fixtures) != 3 * 47:
        raise RuntimeError("expected three complete 47-layer fixture sets")

    fixtures = []
    aggregate = hashlib.sha256()
    for runtime_fixture in runtime_fixtures:
        evidence = runtime_fixture.evidence
        trace_set = int(evidence["trace_set"])
        layer = int(evidence["layer"])
        trace_path = Path(evidence["trace_path"])
        trace_payload = torch.load(
            trace_path, map_location="cpu", weights_only=True
        )
        hidden = trace_payload["hidden_states"].clone().contiguous()
        reference = gate.allocate_outputs(torch)
        candidate = gate.allocate_outputs(torch)
        gate.reference_call(
            torch,
            runtime_fixture.logits,
            runtime_fixture.bias,
            reference,
        )
        gate.candidate_call(
            torch,
            runtime_fixture.logits,
            runtime_fixture.bias,
            candidate,
        )
        torch.xpu.synchronize()
        equal = gate.output_equal(torch, reference, candidate)
        if equal != [True, True, True]:
            raise RuntimeError(
                f"router reconstruction mismatch set={trace_set} layer={layer}"
            )
        weights = candidate[0].detach().cpu().clone().contiguous()
        ids = candidate[1].detach().cpu().clone().contiguous()
        source_rows = candidate[2].detach().cpu().clone().contiguous()
        if (
            hidden.dtype != torch.bfloat16
            or tuple(hidden.shape) != (8, 3072)
            or weights.dtype != torch.float32
            or tuple(weights.shape) != (8, 10)
            or ids.dtype != torch.int32
            or tuple(ids.shape) != (8, 10)
            or source_rows.dtype != torch.int32
            or tuple(source_rows.shape) != (8, 10)
        ):
            raise RuntimeError(
                f"fixture contract drift set={trace_set} layer={layer}"
            )
        hashes = {
            "hidden": tensor_hash(hidden),
            "topk_weights": tensor_hash(weights),
            "topk_ids": tensor_hash(ids),
            "source_rows": tensor_hash(source_rows),
        }
        if hashes["hidden"] != evidence["hidden_sha256"]:
            raise RuntimeError(
                f"hidden hash drift set={trace_set} layer={layer}"
            )
        aggregate.update(
            (
                f"{trace_set}:{layer}:{hashes['hidden']}:"
                f"{hashes['topk_weights']}:{hashes['topk_ids']}:"
                f"{hashes['source_rows']}\n"
            ).encode("ascii")
        )
        fixtures.append(
            {
                "trace_set": trace_set,
                "layer": layer,
                "hidden_states": hidden,
                "topk_weights": weights,
                "topk_ids": ids,
                "source_rows": source_rows,
                "hashes": hashes,
                "source": evidence,
            }
        )

    fixture_sets = {
        trace_set: [
            fixture
            for fixture in fixtures
            if fixture["trace_set"] == trace_set
        ]
        for trace_set in range(3)
    }
    if any(
        [fixture["layer"] for fixture in fixture_sets[trace_set]]
        != list(range(1, 48))
        for trace_set in range(3)
    ):
        raise RuntimeError("fixture sets are not complete ordered layers 1..47")

    payload = {
        "format": "laguna-w1-real-m8-timing-fixtures-v1",
        "fixture_count": len(fixtures),
        "trace_sets": 3,
        "layers_per_set": 47,
        "aggregate_tensor_sha256": aggregate.hexdigest(),
        "production_source_aggregate_sha256": production_report[
            "aggregate_fixture_sha256"
        ],
        "fixtures": fixtures,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, args.out)
    manifest = {
        key: value for key, value in payload.items() if key != "fixtures"
    }
    manifest.update(
        {
            "artifact_path": str(args.out.resolve()),
            "artifact_sha256": gate.sha256_file(args.out),
            "moe_extension_path": str(extension_path),
            "moe_extension_sha256": gate.sha256_file(extension_path),
            "router_gate_path": str(ROUTER_GATE_PATH),
            "router_gate_sha256": gate.sha256_file(ROUTER_GATE_PATH),
            "source_manifest": sources,
        }
    )
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({key: value for key, value in manifest.items()
                      if key != "source_manifest"}, indent=2))


if __name__ == "__main__":
    main()

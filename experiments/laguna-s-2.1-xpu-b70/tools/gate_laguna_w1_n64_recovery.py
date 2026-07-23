#!/usr/bin/env python3
"""Fail-closed N64-only recovery oracle for Laguna routed W1.

This tool deliberately never dispatches the N128 treatment.  It replays the
deterministic pre-campaign correctness corpus with the incumbent N64 path and
compares every input and stage hash against the retained, SHA-256-pinned
pre-incident formal component result for the selected physical card.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import torch


TOOL_DIR = Path(__file__).resolve().parent
BASE_GATE_PATH = TOOL_DIR / "gate_laguna_w1_n128.py"
BASE_GATE_SHA256 = (
    "17491ad377178c5ef693d737f21b77bac4c80413d1abec17c8cdb3678eaa62b7"
)
VLLM_ROOT = Path("/home/steve/src/deepseek-v4-vllm-xpu-dspark")
VLLM_COMMIT = "8936aac144929190c1e53f8b8624ca397ce16f5b"
KERNEL_ROOT = Path("/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc")
KERNEL_COMMIT = "c59aaadbbfd350c2b5f4ad663e247c2811ae3181"
MOE_EXTENSION = KERNEL_ROOT / "vllm_xpu_kernels/_moe_C.abi3.so"
MOE_EXTENSION_SHA256 = (
    "0057b266d567731a9f9f592cefd9103bbf027ebb83c876d26c17ffb09994a3a0"
)
REFERENCE_SUMMARY = Path(
    "/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/"
    "runs/w1-n128-formal2-aggregate-c59aaad-8f2345e-20260723T053000-0400/"
    "summary.json"
)
REFERENCE_SUMMARY_SHA256 = (
    "bb48793e711cdb20889e888092344d35f0f3c7cb0e85bc120f63f51cff39b932"
)
REFERENCE_RESULTS = {
    0: (
        Path(
            "/media/steve/CorsairExternal/llm-optimization-artifacts/"
            "laguna-s-2.1/runs/"
            "w1-n128-formal2-card0-c59aaad-8f2345e-20260723T052500-0400/"
            "result.json"
        ),
        "753a0f9cddca015f8a7505be4ec3220a422cf230bb293e097fefdf4614594fc6",
    ),
    1: (
        Path(
            "/media/steve/CorsairExternal/llm-optimization-artifacts/"
            "laguna-s-2.1/runs/"
            "w1-n128-formal2-card1-c59aaad-8f2345e-20260723T051000-0400/"
            "result.json"
        ),
        "5189be770962212d563afa910d3b8b4cb6e8ec53b0199011f17e4e3da47457c9",
    ),
    2: (
        Path(
            "/media/steve/CorsairExternal/llm-optimization-artifacts/"
            "laguna-s-2.1/runs/"
            "w1-n128-formal2-card2-c59aaad-8f2345e-20260723T051500-0400/"
            "result.json"
        ),
        "0d9577cf73269dd8f229cc162fd08d9e38e7b1ce041672f8419cfb44194cc068",
    ),
    3: (
        Path(
            "/media/steve/CorsairExternal/llm-optimization-artifacts/"
            "laguna-s-2.1/runs/"
            "w1-n128-formal2-card3-c59aaad-8f2345e-20260723T052000-0400/"
            "result.json"
        ),
        "c5ee9c93cad1ec317bcab4d561a6df48f928aefa56ceee10fe2e747e096fb158",
    ),
}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head(path: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def load_base_gate():
    actual_sha256 = file_hash(BASE_GATE_PATH)
    if actual_sha256 != BASE_GATE_SHA256:
        raise RuntimeError(
            f"frozen base gate hash mismatch: {actual_sha256}"
        )
    spec = importlib.util.spec_from_file_location(
        "laguna_w1_n128_frozen_gate", BASE_GATE_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import frozen gate: {BASE_GATE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def reference_contract(reference: dict[str, Any], rank: int) -> dict[str, Any]:
    cases = reference.get("pre_correctness", {}).get("cases")
    runtime = reference.get("runtime", {})
    physical = runtime.get("physical_device", {})
    checks = {
        "top_level_pass": reference.get("passed") is True,
        "formal_component_pass": reference.get("formal_component_pass") is True,
        "formal_mode": reference.get("mode") == "formal",
        "rank": reference.get("rank") == rank,
        "pre_correctness_pass": (
            reference.get("pre_correctness", {}).get("passed") is True
        ),
        "case_count": isinstance(cases, list) and len(cases) == 64,
        "physical_device_id": physical.get("device_id") == rank,
        "extension_sha256": (
            runtime.get("extension_sha256")
            == "f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8"
        ),
        "grouped_gemm_sha256": (
            runtime.get("grouped_gemm_sha256")
            == "fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96"
        ),
    }
    exact_fields = (
        "n64_vs_n128_w1",
        "n64_vs_n128_activation",
        "n64_vs_n128_w2",
        "n64_vs_n128_output",
    )
    checks["historical_n64_equals_n128_bitwise"] = bool(cases) and all(
        case.get("passed") is True
        and all(
            case.get("comparisons", {}).get(field, {}).get("torch_equal") is True
            and case.get("comparisons", {}).get(field, {}).get("raw_equal") is True
            and case.get("comparisons", {}).get(field, {}).get("raw_differences")
            == 0
            for field in exact_fields
        )
        for case in cases or []
    )
    return {"passed": all(checks.values()), "checks": checks, "cases": cases or []}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rank", type=int, required=True, choices=range(4))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    temporary_out = args.out.with_name(args.out.name + ".tmp")
    if args.out.exists() or temporary_out.exists():
        raise RuntimeError(
            f"oracle output path must be fresh: {args.out}"
        )

    affinity = os.environ.get("ZE_AFFINITY_MASK")
    selector = os.environ.get("ONEAPI_DEVICE_SELECTOR")
    if affinity != str(args.rank):
        raise RuntimeError(
            f"--rank {args.rank} requires ZE_AFFINITY_MASK={args.rank}, "
            f"got {affinity!r}"
        )
    if selector != "level_zero:0":
        raise RuntimeError(
            "oracle requires ONEAPI_DEVICE_SELECTOR=level_zero:0 after physical "
            f"affinity selection, got {selector!r}"
        )

    gate = load_base_gate()
    if torch.xpu.device_count() != 1:
        raise RuntimeError(
            "oracle requires exactly one visible XPU after physical affinity"
        )
    torch.xpu.set_device(0)

    if gate.file_hash(REFERENCE_SUMMARY) != REFERENCE_SUMMARY_SHA256:
        raise RuntimeError("historical aggregate summary hash mismatch")
    reference_path, reference_sha256 = REFERENCE_RESULTS[args.rank]
    if gate.file_hash(reference_path) != reference_sha256:
        raise RuntimeError("historical per-card reference hash mismatch")
    reference = json.loads(reference_path.read_text())
    contract = reference_contract(reference, args.rank)
    if not contract["passed"]:
        raise RuntimeError(
            "historical reference contract failed: "
            + json.dumps(contract["checks"], sort_keys=True)
        )

    source_identity = {
        "base_gate_path": str(BASE_GATE_PATH),
        "base_gate_sha256": file_hash(BASE_GATE_PATH),
        "vllm_commit": git_head(VLLM_ROOT),
        "kernel_commit": git_head(KERNEL_ROOT),
        "moe_extension_path": str(MOE_EXTENSION),
        "moe_extension_sha256": file_hash(MOE_EXTENSION),
    }
    expected_source_identity = {
        "base_gate_path": str(BASE_GATE_PATH),
        "base_gate_sha256": BASE_GATE_SHA256,
        "vllm_commit": VLLM_COMMIT,
        "kernel_commit": KERNEL_COMMIT,
        "moe_extension_path": str(MOE_EXTENSION),
        "moe_extension_sha256": MOE_EXTENSION_SHA256,
    }
    if source_identity != expected_source_identity:
        raise RuntimeError(
            "source identity mismatch: "
            + json.dumps(source_identity, sort_keys=True)
        )

    observed_w1_n_tiles: list[int] = []
    original_call_fused_w1 = gate.call_fused_w1

    def n64_only_call_fused_w1(*call_args, **call_kwargs):
        tile = call_kwargs.get("w1_n_tile")
        if tile != 64:
            raise RuntimeError(
                f"recovery oracle rejected non-N64 dispatch: {tile!r}"
            )
        observed_w1_n_tiles.append(tile)
        return original_call_fused_w1(*call_args, **call_kwargs)

    gate.call_fused_w1 = n64_only_call_fused_w1

    model = gate.allocate_model_tensors(args.rank)
    runtime = gate.runtime_identity(args.rank)
    reference_runtime = reference["runtime"]
    runtime_matches_reference = (
        runtime["extension_sha256"] == reference_runtime["extension_sha256"]
        and runtime["grouped_gemm_sha256"]
        == reference_runtime["grouped_gemm_sha256"]
        and runtime["schema"] == reference_runtime["schema"]
        and runtime["physical_device"] == reference_runtime["physical_device"]
    )

    constant_before = {
        "w2": gate.tensor_hash(model.w2),
        "s2": gate.tensor_hash(model.s2),
        "expert_map": gate.tensor_hash(model.expert_map),
    }
    cases: list[dict[str, Any]] = []
    for expected in contract["cases"]:
        epoch = int(expected["epoch"])
        hidden, weights, ids = gate.make_epoch_inputs(
            args.rank, epoch, 8, model
        )
        input_before = gate.input_hashes(hidden, model, weights, ids)
        first = gate.allocate_buffers()
        repeat = gate.allocate_buffers()

        gate.run_complete_path(hidden, model, weights, ids, first, 64)
        gate.run_complete_path(hidden, model, weights, ids, repeat, 64)
        torch.xpu.synchronize()

        mapped = model.expert_map[ids].reshape(-1)
        local = mapped >= 0
        routes = 8 * gate.TOPK
        actual = {
            "inputs": input_before,
            "w1": gate.tensor_hash(first.gemm1[:routes][local]),
            "activation": gate.tensor_hash(first.activation[:routes][local]),
            "output": gate.tensor_hash(first.output[:8]),
        }
        replay = {
            "w1": gate.tensor_hash(repeat.gemm1[:routes][local]),
            "activation": gate.tensor_hash(repeat.activation[:routes][local]),
            "output": gate.tensor_hash(repeat.output[:8]),
        }
        expected_hashes = {
            "inputs": expected["inputs"],
            "w1": expected["w1"],
            "activation": expected["activation"],
            "output": expected["output"],
        }
        repeat_bitwise = {
            "w1": gate.exact_comparison(
                first.gemm1[:routes][local], repeat.gemm1[:routes][local]
            ),
            "activation": gate.exact_comparison(
                first.activation[:routes][local],
                repeat.activation[:routes][local],
            ),
            "gemm2": gate.exact_comparison(
                first.gemm2[:routes][local], repeat.gemm2[:routes][local]
            ),
            "output": gate.exact_comparison(
                first.output[:8], repeat.output[:8]
            ),
        }
        input_after = gate.input_hashes(hidden, model, weights, ids)
        remote_untouched = gate.remote_rows_untouched(first, local, 8) and (
            gate.remote_rows_untouched(repeat, local, 8)
        )
        matches_reference = actual == expected_hashes
        repeat_matches = replay == {
            "w1": actual["w1"],
            "activation": actual["activation"],
            "output": actual["output"],
        } and all(
            item["torch_equal"]
            and item["raw_equal"]
            and item["raw_differences"] == 0
            for item in repeat_bitwise.values()
        )
        passed = (
            matches_reference
            and repeat_matches
            and input_before == input_after
            and remote_untouched
        )
        cases.append(
            {
                "epoch": epoch,
                "passed": passed,
                "inputs_unchanged": input_before == input_after,
                "remote_rows_untouched": remote_untouched,
                "actual_matches_historical_reference": matches_reference,
                "repeat_matches_first_bitwise": repeat_matches,
                "expected": expected_hashes,
                "actual": actual,
                "repeat": replay,
                "repeat_bitwise": repeat_bitwise,
            }
        )

    constant_after = {
        "w2": gate.tensor_hash(model.w2),
        "s2": gate.tensor_hash(model.s2),
        "expert_map": gate.tensor_hash(model.expert_map),
    }
    checks = {
        "historical_reference_contract": contract["passed"],
        "runtime_matches_historical_reference": runtime_matches_reference,
        "all_64_cases_pass": len(cases) == 64
        and all(case["passed"] for case in cases),
        "constant_inputs_unchanged": constant_before == constant_after,
        "constants_match_historical_reference": (
            constant_before == reference["constant_input_hashes"]
        ),
        "source_identity_matches": source_identity == expected_source_identity,
        "exactly_128_w1_calls_observed": len(observed_w1_n_tiles) == 128,
        "only_n64_dispatched": set(observed_w1_n_tiles) == {64},
        "n128_not_executed": 128 not in observed_w1_n_tiles,
    }
    result = {
        "passed": all(checks.values()),
        "oracle_gate_evaluated": True,
        "mode": "oracle-n64",
        "rank": args.rank,
        "device": torch.xpu.get_device_name(0),
        "executed_w1_n_tiles": sorted(set(observed_w1_n_tiles)),
        "observed_w1_call_count": len(observed_w1_n_tiles),
        "n128_executed": 128 in observed_w1_n_tiles,
        "runtime": runtime,
        "source_identity": source_identity,
        "historical_reference": {
            "aggregate_summary_path": str(REFERENCE_SUMMARY),
            "aggregate_summary_sha256": REFERENCE_SUMMARY_SHA256,
            "per_card_path": str(reference_path),
            "per_card_sha256": reference_sha256,
            "reference_semantics": (
                "stored N128 hashes proven bitwise equal to incumbent N64 by "
                "the retained pre-incident formal component result"
            ),
        },
        "checks": checks,
        "constant_input_hashes": constant_before,
        "cases": cases,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with temporary_out.open("w") as handle:
        handle.write(json.dumps(result, indent=2) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary_out, args.out)
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "mode": result["mode"],
                "rank": result["rank"],
                "device": result["device"],
                "executed_w1_n_tiles": result["executed_w1_n_tiles"],
                "n128_executed": result["n128_executed"],
                "checks": result["checks"],
            },
            indent=2,
        )
    )
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

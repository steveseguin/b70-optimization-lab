#!/usr/bin/env python3
"""Generate the CPU-only Laguna gather/finalize fixture manifest."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import gate_laguna_m8_gather_finalize_component as contract
import run_laguna_m8_gather_finalize_component as runner


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def _downstream(torch: Any) -> dict[str, Any]:
    seed = 0x6A472021

    def rnd(
        shape: tuple[int, ...],
        offset: int,
        dtype: Any,
        scale: float = 1.0,
    ) -> Any:
        return runner._randn(shape, seed ^ offset, scale, torch).to(dtype)

    tensors = {
        "rank_tail": rnd(
            (runner.RANKS - 1, runner.TOKENS, runner.HIDDEN),
            0x111,
            torch.bfloat16,
        ),
        "residual_base": rnd(
            (runner.TOKENS, runner.HIDDEN),
            0x222,
            torch.bfloat16,
        ),
        "norm_weight": (1.0 + rnd((runner.HIDDEN,), 0x333, torch.float32, 0.01)).to(
            torch.bfloat16
        ),
    }
    require(
        all(tensor.device.type == "cpu" for tensor in tensors.values()),
        "fixture generator created a non-CPU tensor",
    )
    return {
        "format": "laguna-m8-post-moe-fused-add-rmsnorm-v1",
        "seed": seed,
        "epsilon": 1e-6,
        "expected_cpu_static_input_hashes": {
            name: runner._tensor_hash(tensor, torch) for name, tensor in tensors.items()
        },
    }


def build_manifest(torch: Any) -> dict[str, Any]:
    seeds = [
        contract.RANDOM_SEED_BASE + index * contract.RANDOM_SEED_STRIDE
        for index in range(contract.RANDOM_FIXTURES)
    ]
    value: dict[str, Any] = {
        "format": contract.FIXTURE_FORMAT,
        "corpus_version": contract.FIXTURE_CORPUS_VERSION,
        "random_full": {
            "algorithm": "torch_cpu_generator_manual_seed_randn_v1",
            "seeds": seeds,
        },
        "coverage": {
            "finite_bf16": {
                "excluded_exponent": 255,
                "count": contract.FINITE_BF16_COUNT,
                "routed": True,
                "shared": True,
            },
            "special_classes": [
                "positive_zero",
                "negative_zero",
                "subnormal",
                "infinity",
                "nan",
            ],
            "weight_edges": [
                "positive_zero",
                "negative_zero",
                "positive_subnormal",
                "negative_subnormal",
                "near_one",
            ],
            "tie_even": True,
            "route_patterns": [
                "all_local",
                "all_remote",
                "mixed_remote_zero",
            ],
            "slot_rows": {"slots": 10, "rows": 80},
        },
        "downstream": _downstream(torch),
        "expected_cpu_input_hashes": {},
    }
    specs = runner._corpus_specs(value)
    runner._validate_spec_coverage(specs)
    require(
        [spec["id"] for spec in specs] == contract.fixture_spec_ids(),
        "runner/packet fixture ID grammar drift",
    )
    finite = runner._finite_bf16_bits(torch)
    hashes: dict[str, dict[str, str]] = {}
    for spec in specs:
        item = runner._make_cpu_fixture(spec, finite, torch)
        require(
            all(
                item[name].device.type == "cpu"
                for name in ("routes", "weights", "shared", "route_map")
            ),
            f"non-CPU fixture tensor: {spec['id']}",
        )
        hashes[spec["id"]] = runner._input_hashes(
            item["routes"],
            item["weights"],
            item["shared"],
            item["route_map"],
            torch,
        )
    value["expected_cpu_input_hashes"] = hashes
    return value


def write_manifest(path: Path, value: dict[str, Any]) -> None:
    contract._nvme(path, False)
    require(
        path.is_absolute()
        and path.is_relative_to(contract.ARTIFACT / "authorizations")
        and path.parent.is_dir()
        and not path.parent.is_symlink()
        and not path.exists()
        and not path.is_symlink(),
        "fresh internal-NVMe authorization path required",
    )
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o644,
    )
    try:
        payload = contract.canonical(value) + b"\n"
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            require(written > 0, "short fixture-manifest write")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    import torch

    require(
        not torch.xpu.is_initialized(),
        "XPU was initialized before CPU fixture construction",
    )
    value = build_manifest(torch)
    require(
        not torch.xpu.is_initialized(),
        "CPU fixture construction initialized XPU",
    )
    write_manifest(args.out, value)
    contract.validate_fixture_manifest(args.out)
    print(contract.sha(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

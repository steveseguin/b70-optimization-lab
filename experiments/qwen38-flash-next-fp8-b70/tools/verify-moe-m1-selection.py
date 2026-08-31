#!/usr/bin/env python3
"""Emit a fail-closed receipt for the production-M1 MoE configuration.

This helper performs no inference.  The endpoint launcher runs it in the exact
server environment immediately before ``vllm serve`` so the receipt binds the
official vLLM resolver, selected map key, effective launch configuration, and
the source files that pass that configuration into the Triton MoE kernel.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


EXPECTED_CONFIG_SHA256 = (
    "91e5d8b692da3febbba7cb07ee4fdab319909da0c82c1fda95b92dc42d680464"
)
EXPECTED_FUSED_MOE_SHA256 = (
    "7072eb06237be9d33dcb0ef7101410f886a6363c98cbee70a014c68b70f639cb"
)
EXPECTED_TRITON_MOE_SHA256 = (
    "312d4da6f6869b22ed8c179f39f839cfbac2f77f5b01060c001f353d2310a6e5"
)
EXPECTED_KEYS = [1, 4, 8, 16, 32, 64, 128]
EXPECTED_M1_CONFIG = {
    "BLOCK_SIZE_M": 16,
    "BLOCK_SIZE_N": 64,
    "BLOCK_SIZE_K": 128,
    "GROUP_SIZE_M": 1,
    "SPLIT_K": 1,
    "num_warps": 8,
    "num_stages": 4,
}


class SelectionContractError(RuntimeError):
    """Raised when the live MoE selection identity is not exact."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_map(raw: dict[str, Any]) -> dict[int, dict[str, int]]:
    result = {int(key): value for key, value in raw.items() if key != "triton_version"}
    if sorted(result) != EXPECTED_KEYS:
        raise SelectionContractError(f"unexpected tuning keys: {sorted(result)}")
    if result[1] != EXPECTED_M1_CONFIG:
        raise SelectionContractError(f"M1 configuration drifted: {result[1]}")
    if any(result[key].get("num_warps") != 4 for key in EXPECTED_KEYS if key != 1):
        raise SelectionContractError("the candidate is not an M1-only warp change")
    return result


def select_key(configs: dict[int, dict[str, int]], requested_m: int) -> int:
    return min(configs, key=lambda key: abs(key - requested_m))


def build_receipt(config_file: Path, vllm_source: Path) -> dict[str, Any]:
    config_file = config_file.resolve()
    vllm_source = vllm_source.resolve()
    if sha256_file(config_file) != EXPECTED_CONFIG_SHA256:
        raise SelectionContractError("M1 tuned-config hash drifted")
    expected_folder = str(config_file.parent)
    if os.environ.get("VLLM_TUNED_CONFIG_FOLDER") != expected_folder:
        raise SelectionContractError(
            "live tuned-config folder differs from the receipt"
        )

    fused_moe_source = vllm_source / "vllm/model_executor/layers/fused_moe/fused_moe.py"
    triton_moe_source = (
        vllm_source / "vllm/model_executor/layers/fused_moe/experts/triton_moe.py"
    )
    if sha256_file(fused_moe_source) != EXPECTED_FUSED_MOE_SHA256:
        raise SelectionContractError("fused_moe source drifted")
    if sha256_file(triton_moe_source) != EXPECTED_TRITON_MOE_SHA256:
        raise SelectionContractError("Triton MoE source drifted")

    configs = normalize_map(json.loads(config_file.read_text(encoding="utf-8")))
    requested_m = 1
    selected_key = select_key(configs, requested_m)
    selected_config = configs[selected_key]

    from vllm.model_executor.layers.fused_moe.fused_moe import (
        get_moe_configs,
        try_get_optimal_moe_config,
    )

    get_moe_configs.cache_clear()
    official_config = try_get_optimal_moe_config(
        (128, 1280, 2560),
        (128, 2560, 640),
        10,
        "fp8_w8a8",
        requested_m,
        [128, 128],
    )
    if selected_key != 1 or selected_config["num_warps"] != 8:
        raise SelectionContractError("M1 did not resolve to eight warps")
    if official_config != selected_config:
        raise SelectionContractError(
            f"official resolver differs from selected key: {official_config}"
        )

    return {
        "schema_version": 1,
        "status": "passed",
        "classification": "prelaunch_live_environment_moe_selection_receipt",
        "requested_m": requested_m,
        "selected_batch_key": selected_key,
        "effective_config": selected_config,
        "official_resolver_match": True,
        "candidate_scope": "key_1_only",
        "config_file": str(config_file),
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "source_contract": {
            "fused_moe_sha256": EXPECTED_FUSED_MOE_SHA256,
            "triton_moe_sha256": EXPECTED_TRITON_MOE_SHA256,
            "semantics": (
                "fused_experts derives M from hidden_states.size(0), resolves the "
                "nearest map key, and passes the returned config to Triton"
            ),
        },
        "not_inference_evidence": True,
    }


def write_exclusive(path: Path, payload: dict[str, Any]) -> None:
    path = path.resolve()
    if path.exists():
        raise SelectionContractError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp.{os.getpid()}")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-file", type=Path, required=True)
    parser.add_argument("--vllm-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_exclusive(args.output, build_receipt(args.config_file, args.vllm_source))


if __name__ == "__main__":
    main()

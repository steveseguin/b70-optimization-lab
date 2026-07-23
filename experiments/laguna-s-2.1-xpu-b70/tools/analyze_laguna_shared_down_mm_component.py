#!/usr/bin/env python3
"""Fail-closed four-card analyzer for Laguna shared-down native M8 MM."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import torch


ARTIFACT_ROOT_LITERAL = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1")
ARTIFACT_ROOT = ARTIFACT_ROOT_LITERAL.resolve()
NVME_SOURCE = "/dev/nvme0n1p2"
NVME_FSTYPE = "ext4"
EXPECTED_BOOT_ID = "0b7f98a5-e50a-46a5-81ea-15938b55317a"
EXPECTED_DEVICE_NAME = "Intel(R) Arc(TM) Pro B70 Graphics"
EXPECTED_MODEL_CONFIG_PATH = Path(
    "/mnt/fast-ai/llm-models/laguna-s-2.1/int4/config.json"
)
EXPECTED_MODEL_CONFIG_SHA256 = (
    "9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6"
)
MAIN_REPO = Path("/home/steve/llm-optimizations").resolve()
VLLM_REPO = Path("/home/steve/src/deepseek-v4-vllm-xpu-dspark").resolve()
KERNEL_REPO = Path("/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc").resolve()
EXPECTED_HARNESS_SHA256 = (
    "187f3ffe1769bd00310befd56e64b3d8e48713245532a1dff8b6088de5e121b6"
)
EXPECTED_HARNESS_PATH = (
    MAIN_REPO / "experiments/laguna-s-2.1-xpu-b70/tools/gate_laguna_shared_down_mm.py"
)
EXPECTED_VLLM_COMMIT = "75d4660463407975c16bd33711499ca560bf2034"
EXPECTED_KERNEL_COMMIT = "c59aaadbbfd350c2b5f4ad663e247c2811ae3181"
EXPECTED_BINARY_SHA256 = {
    "_C": "126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2",
    "_xpu_C": "f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8",
    "_moe_C": "0057b266d567731a9f9f592cefd9103bbf027ebb83c876d26c17ffb09994a3a0",
    "libgrouped_gemm_xe_2": (
        "fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96"
    ),
}
EXPECTED_BINARY_PATHS = {
    "_C": KERNEL_REPO / "vllm_xpu_kernels/_C.abi3.so",
    "_xpu_C": KERNEL_REPO / "vllm_xpu_kernels/_xpu_C.abi3.so",
    "_moe_C": KERNEL_REPO / "vllm_xpu_kernels/_moe_C.abi3.so",
    "libgrouped_gemm_xe_2": (KERNEL_REPO / "vllm_xpu_kernels/libgrouped_gemm_xe_2.so"),
}
EXPECTED_PHYSICAL_DEVICES = {
    0: {
        "device_id": 0,
        "uuid": "00000000-0000-0023-0000-0000e2238086",
        "pci_bdf_address": "0000:23:00.0",
        "drm_device": "/dev/dri/card3",
    },
    1: {
        "device_id": 1,
        "uuid": "00000000-0000-0027-0000-0000e2238086",
        "pci_bdf_address": "0000:27:00.0",
        "drm_device": "/dev/dri/card4",
    },
    2: {
        "device_id": 2,
        "uuid": "00000000-0000-0043-0000-0000e2238086",
        "pci_bdf_address": "0000:43:00.0",
        "drm_device": "/dev/dri/card0",
    },
    3: {
        "device_id": 3,
        "uuid": "00000000-0000-0047-0000-0000e2238086",
        "pci_bdf_address": "0000:47:00.0",
        "drm_device": "/dev/dri/card2",
    },
}
EXPECTED_RECORD_ENVIRONMENT = {
    "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM": "1",
    "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "1",
    "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "1",
    "VLLM_XPU_EXACT_SPEC_ATTN": "1",
    "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1",
    "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2": "1",
    "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE": "1",
    "VLLM_XPU_LAGUNA_M8_W1_N_TILE": "64",
    "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM": "0",
    "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": "0",
    "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION": "0",
    "VLLM_XPU_LAGUNA_M8_REMOTE_ZERO": "0",
    "VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM": "0",
    "VLLM_XPU_ENABLE_XPU_GRAPH": "0",
    "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH": "0",
    "VLLM_XPU_FORCE_GRAPH_WITH_COMM": "0",
    "VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE": "0",
    "XPU_GRAPH": "0",
    "VLLM_USE_AOT_COMPILE": "0",
}
EXPECTED_RANKS = {0, 1, 2, 3}
EXPECTED_EPOCHS = 128
EXPECTED_POST_REPLAY_EPOCHS = 32
EXPECTED_BLOCKS = 31
EXPECTED_CYCLES_PER_ARM = 64
EXPECTED_WARM_CYCLES = 20
EXPECTED_TARGET_LAYERS = 47
MIN_BLOCK_WINS = 28
MIN_CYCLE_SAVING_MS = 0.15
ROWS = 8
K_DIM = 256
N_DIM = 3072
WEIGHT_SCALE = 0.02


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_text_command(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def git_identity(repo: Path) -> dict[str, object]:
    commit = run_text_command(["git", "-C", str(repo), "rev-parse", "HEAD"])
    status = run_text_command(
        [
            "git",
            "-C",
            str(repo),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ]
    )
    return {
        "path": str(repo),
        "commit": commit,
        "clean": not status,
        "status_porcelain": status.splitlines(),
        "status_sha256": hashlib.sha256(status.encode()).hexdigest(),
    }


def path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def verify_nvme_mount() -> None:
    if ARTIFACT_ROOT != ARTIFACT_ROOT_LITERAL:
        raise RuntimeError(
            "Laguna artifact root itself is a symlink or resolved-path alias"
        )
    mount = subprocess.run(
        [
            "findmnt",
            "--noheadings",
            "--output",
            "SOURCE,FSTYPE",
            "--target",
            str(ARTIFACT_ROOT),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    reported_mounts = [
        tuple(line.split(None, 1))
        for line in mount.stdout.splitlines()
        if len(line.split(None, 1)) == 2
    ]
    if mount.returncode != 0 or (NVME_SOURCE, NVME_FSTYPE) not in reported_mounts:
        raise RuntimeError(
            "Laguna artifact root is not on the required local NVMe/ext4 "
            f"identity ({NVME_SOURCE}, {NVME_FSTYPE})"
        )


def require_local_result_path(path: Path, *, must_exist: bool) -> Path:
    if not path.is_absolute():
        raise RuntimeError(f"result path must be absolute: {path}")
    if path.suffix != ".json":
        raise RuntimeError(f"result path must end in .json: {path}")
    if must_exist:
        if not path.exists():
            raise RuntimeError(f"required card result does not exist: {path}")
        resolved = path.resolve(strict=True)
    else:
        if path.exists() or path.is_symlink():
            raise RuntimeError(
                f"refusing to overwrite or follow existing result path: {path}"
            )
        resolved = path.parent.resolve(strict=False) / path.name
    if not path_is_within(resolved, ARTIFACT_ROOT):
        raise RuntimeError(
            "result path is outside the required Laguna local-NVMe artifact "
            f"root: {resolved}"
        )
    if str(resolved).startswith(("/media/", "/mnt/usb-models/")):
        raise RuntimeError(f"removable-media result path rejected: {resolved}")
    return resolved


def initialize_output(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved_after_create = path.parent.resolve(strict=True) / path.name
    if resolved_after_create != path or not path_is_within(
        resolved_after_create, ARTIFACT_ROOT
    ):
        raise RuntimeError(
            f"output parent escaped the local artifact root: {resolved_after_create}"
        )
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write("{}\n")
        handle.flush()
        os.fsync(handle.fileno())


def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    encoded = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(encoded)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def load_result(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def sha256_string_list(values: list[str]) -> str:
    return hashlib.sha256("".join(values).encode()).hexdigest()


def finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def close(left: object, right: object) -> bool:
    return (
        finite_number(left)
        and finite_number(right)
        and math.isclose(
            float(left),
            float(right),
            rel_tol=1e-9,
            abs_tol=1e-9,
        )
    )


def sha256_argument(value: str) -> str:
    normalized = value.lower()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise argparse.ArgumentTypeError("expected a 64-digit SHA256")
    return normalized


def argument_values(argv: list[object], name: str) -> list[str | None]:
    values: list[str | None] = []
    for index, value in enumerate(argv):
        if value != name:
            continue
        if index + 1 >= len(argv) or not isinstance(argv[index + 1], str):
            values.append(None)
        else:
            values.append(argv[index + 1])
    return values


def valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value.lower())
    )


def cpu_bf16_random(
    shape: tuple[int, ...],
    *,
    seed: int,
    scale: float,
) -> torch.Tensor:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    return (
        torch.randn(shape, dtype=torch.float32, generator=generator)
        .mul_(scale)
        .to(torch.bfloat16)
    )


@lru_cache(maxsize=EXPECTED_EPOCHS)
def deterministic_fixture_sha256(epoch: int) -> str:
    seed = 730_000 + epoch * 10
    tensors = [
        cpu_bf16_random((ROWS, K_DIM), seed=seed, scale=0.5),
        cpu_bf16_random(
            (N_DIM, K_DIM),
            seed=seed + 1,
            scale=WEIGHT_SCALE,
        ),
        cpu_bf16_random((ROWS, N_DIM), seed=seed + 2, scale=0.1),
    ]
    tensors.extend(
        cpu_bf16_random(
            (ROWS, N_DIM),
            seed=seed + 3 + peer,
            scale=0.1,
        )
        for peer in range(3)
    )
    digest = hashlib.sha256()
    for tensor in tensors:
        digest.update(tensor.contiguous().view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def raw_output_manifest_exact(
    raw_outputs: object,
    output_sha256: object,
) -> bool:
    if not isinstance(raw_outputs, dict):
        return False
    for name in ("down", "shared_routed_add", "fixed_rank_sum", "aggregate"):
        pair = raw_outputs.get(name)
        if not (
            isinstance(pair, dict)
            and set(pair) == {"control", "candidate"}
            and valid_sha256(pair.get("control"))
            and pair.get("control") == pair.get("candidate")
        ):
            return False
    repeat = raw_outputs.get("candidate_repeat")
    if not (
        isinstance(repeat, dict)
        and set(repeat) == {"first", "repeat"}
        and valid_sha256(repeat.get("first"))
        and repeat.get("first") == repeat.get("repeat")
    ):
        return False
    aggregate = raw_outputs["aggregate"]
    return aggregate["candidate"] == output_sha256


def validate_timing(timing: dict[str, Any]) -> tuple[dict[str, bool], dict[str, Any]]:
    blocks = timing.get("blocks_detail")
    checks: dict[str, bool] = {
        "timing_object": isinstance(timing, dict),
        "top_level_timing_pass": timing.get("passed") is True,
        "target_layers": (
            timing.get("target_layers_per_cycle") == EXPECTED_TARGET_LAYERS
        ),
        "warm_cycles": timing.get("warm_cycles_per_arm") == EXPECTED_WARM_CYCLES,
        "block_count": timing.get("blocks") == EXPECTED_BLOCKS,
        "cycles_per_arm": (
            timing.get("cycles_per_arm_per_block") == EXPECTED_CYCLES_PER_ARM
        ),
        "threshold_wins": timing.get("minimum_block_wins") == MIN_BLOCK_WINS,
        "threshold_saving": close(
            timing.get("minimum_cycle_saving_ms"), MIN_CYCLE_SAVING_MS
        ),
        "block_detail_count": (
            isinstance(blocks, list) and len(blocks) == EXPECTED_BLOCKS
        ),
    }
    if not isinstance(blocks, list) or len(blocks) != EXPECTED_BLOCKS:
        return checks, {}

    savings: list[float] = []
    controls: list[float] = []
    candidates: list[float] = []
    detail_exact = True
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            detail_exact = False
            continue
        names = (
            "A1_control_ms",
            "B1_candidate_ms",
            "B2_candidate_ms",
            "A2_control_ms",
            "paired_control_ms",
            "paired_candidate_ms",
            "saving_ms",
        )
        if block.get("block") != index or not all(
            finite_number(block.get(name)) for name in names
        ):
            detail_exact = False
            continue
        control = (float(block["A1_control_ms"]) + float(block["A2_control_ms"])) / 2.0
        candidate = (
            float(block["B1_candidate_ms"]) + float(block["B2_candidate_ms"])
        ) / 2.0
        saving = control - candidate
        if not (
            close(block["paired_control_ms"], control)
            and close(block["paired_candidate_ms"], candidate)
            and close(block["saving_ms"], saving)
        ):
            detail_exact = False
        controls.append(control)
        candidates.append(candidate)
        savings.append(saving)

    checks["every_block_recomputed"] = detail_exact and len(savings) == EXPECTED_BLOCKS
    if len(savings) != EXPECTED_BLOCKS:
        return checks, {}
    wins = sum(saving > 0.0 for saving in savings)
    median_saving = statistics.median(savings)
    control_median = statistics.median(controls)
    candidate_median = statistics.median(candidates)
    relative = median_saving / control_median if control_median else 0.0
    checks.update(
        {
            "reported_wins_recomputed": (timing.get("candidate_block_wins") == wins),
            "reported_median_saving_recomputed": close(
                timing.get("median_saving_ms_per_cycle"), median_saving
            ),
            "reported_control_median_recomputed": close(
                timing.get("control_median_ms_per_cycle"), control_median
            ),
            "reported_candidate_median_recomputed": close(
                timing.get("candidate_median_ms_per_cycle"), candidate_median
            ),
            "reported_relative_recomputed": close(
                timing.get("median_relative_saving"), relative
            ),
            "wins_gate": wins >= MIN_BLOCK_WINS,
            "saving_gate": median_saving >= MIN_CYCLE_SAVING_MS,
        }
    )
    return checks, {
        "wins": wins,
        "median_saving_ms_per_cycle": median_saving,
        "control_median_ms_per_cycle": control_median,
        "candidate_median_ms_per_cycle": candidate_median,
        "median_relative_saving": relative,
    }


def validate_exactness(
    exactness: dict[str, Any],
) -> tuple[dict[str, bool], dict[str, Any]]:
    epochs = exactness.get("epochs_detail")
    post = exactness.get("post_timing_replay_detail")
    checks: dict[str, bool] = {
        "exactness_object": isinstance(exactness, dict),
        "epoch_count": exactness.get("epochs") == EXPECTED_EPOCHS,
        "checks_per_epoch": exactness.get("checks_per_epoch") == 4,
        "raw_exact_claim": exactness.get("all_raw_exact") is True,
        "repeat_claim": (exactness.get("candidate_repeat_deterministic") is True),
        "inputs_claim": exactness.get("inputs_unchanged") is True,
        "unique_fixture_claim": (
            exactness.get("unique_fixture_hashes") == EXPECTED_EPOCHS
        ),
        "unique_output_claim": (
            exactness.get("unique_output_hashes") == EXPECTED_EPOCHS
        ),
        "post_epoch_count": (
            exactness.get("post_timing_replay_epochs") == EXPECTED_POST_REPLAY_EPOCHS
        ),
        "post_exact_claim": (exactness.get("post_timing_replay_exact") is True),
        "epoch_detail_count": (
            isinstance(epochs, list) and len(epochs) == EXPECTED_EPOCHS
        ),
        "post_detail_count": (
            isinstance(post, list) and len(post) == EXPECTED_POST_REPLAY_EPOCHS
        ),
    }
    if not isinstance(epochs, list) or len(epochs) != EXPECTED_EPOCHS:
        return checks, {}
    fixture_hashes: list[str] = []
    output_hashes: list[str] = []
    epochs_exact = True
    for index, epoch in enumerate(epochs):
        if not isinstance(epoch, dict):
            epochs_exact = False
            continue
        equal = epoch.get("equal")
        fixture_hash = epoch.get("fixture_sha256")
        output_hash = epoch.get("output_sha256")
        if not (
            epoch.get("epoch") == index
            and epoch.get("inputs_unchanged") is True
            and isinstance(equal, dict)
            and set(equal)
            == {
                "down",
                "candidate_repeat",
                "shared_routed_add",
                "fixed_rank_sum",
            }
            and all(value is True for value in equal.values())
            and valid_sha256(fixture_hash)
            and fixture_hash == deterministic_fixture_sha256(index)
            and valid_sha256(output_hash)
            and raw_output_manifest_exact(
                epoch.get("raw_outputs"),
                output_hash,
            )
        ):
            epochs_exact = False
            continue
        fixture_hashes.append(fixture_hash)
        output_hashes.append(output_hash)

    checks["every_epoch_recomputed"] = (
        epochs_exact
        and len(fixture_hashes) == EXPECTED_EPOCHS
        and len(output_hashes) == EXPECTED_EPOCHS
    )
    if len(fixture_hashes) != EXPECTED_EPOCHS:
        return checks, {}
    checks.update(
        {
            "fixture_hashes_unique_recomputed": (
                len(set(fixture_hashes)) == EXPECTED_EPOCHS
            ),
            "output_hashes_unique_recomputed": (
                len(set(output_hashes)) == EXPECTED_EPOCHS
            ),
            "aggregate_fixture_recomputed": (
                exactness.get("aggregate_fixture_sha256")
                == sha256_string_list(fixture_hashes)
            ),
            "aggregate_output_recomputed": (
                exactness.get("aggregate_output_sha256")
                == sha256_string_list(output_hashes)
            ),
        }
    )
    post_exact = (
        isinstance(post, list)
        and len(post) == EXPECTED_POST_REPLAY_EPOCHS
        and all(
            isinstance(item, dict)
            and item.get("epoch") == index
            and item.get("fixture_sha256") == fixture_hashes[index]
            and item.get("output_sha256") == output_hashes[index]
            and item.get("inputs_unchanged") is True
            and isinstance(item.get("equal"), dict)
            and set(item["equal"])
            == {
                "down",
                "candidate_repeat",
                "shared_routed_add",
                "fixed_rank_sum",
            }
            and all(value is True for value in item["equal"].values())
            and raw_output_manifest_exact(
                item.get("raw_outputs"),
                item.get("output_sha256"),
            )
            for index, item in enumerate(post)
        )
    )
    checks["post_replay_recomputed"] = post_exact
    return checks, {
        "aggregate_fixture_sha256": sha256_string_list(fixture_hashes),
        "aggregate_output_sha256": sha256_string_list(output_hashes),
    }


def validate_card(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    rank = payload.get("rank")
    identity = payload.get("identity")
    expected = payload.get("expected_identity")
    frozen = payload.get("frozen_protocol")
    exactness = payload.get("exactness")
    shared_down_path = payload.get("vllm_shared_down_path")
    timing = payload.get("timing")
    geometry = payload.get("geometry")
    identity = identity if isinstance(identity, dict) else {}
    expected = expected if isinstance(expected, dict) else {}
    frozen = frozen if isinstance(frozen, dict) else {}
    exactness = exactness if isinstance(exactness, dict) else {}
    shared_down_path = shared_down_path if isinstance(shared_down_path, dict) else {}
    timing = timing if isinstance(timing, dict) else {}
    geometry = geometry if isinstance(geometry, dict) else {}
    checkpoint_metadata = shared_down_path.get("checkpoint_metadata")
    checkpoint_metadata = (
        checkpoint_metadata if isinstance(checkpoint_metadata, dict) else {}
    )

    repositories = identity.get("repositories")
    repositories = repositories if isinstance(repositories, dict) else {}
    main_git = repositories.get("main")
    vllm_git = repositories.get("vllm")
    kernel_git = repositories.get("kernels")
    main_git = main_git if isinstance(main_git, dict) else {}
    vllm_git = vllm_git if isinstance(vllm_git, dict) else {}
    kernel_git = kernel_git if isinstance(kernel_git, dict) else {}
    binaries = identity.get("binaries")
    binaries = binaries if isinstance(binaries, dict) else {}
    environment = identity.get("record_environment")
    environment = environment if isinstance(environment, dict) else {}
    physical = identity.get("physical_device")
    physical = physical if isinstance(physical, dict) else {}
    runtime = identity.get("runtime")
    runtime = runtime if isinstance(runtime, dict) else {}
    unfiltered_physical = physical.get("unfiltered_physical_device")
    filtered_logical = physical.get("filtered_logical_device")
    unfiltered_physical = (
        unfiltered_physical if isinstance(unfiltered_physical, dict) else {}
    )
    filtered_logical = filtered_logical if isinstance(filtered_logical, dict) else {}
    xpu_smi = identity.get("xpu_smi")
    xpu_smi = xpu_smi if isinstance(xpu_smi, dict) else {}
    filtered_discovery = xpu_smi.get("filtered")
    unfiltered_discovery = xpu_smi.get("unfiltered")
    filtered_discovery = (
        filtered_discovery if isinstance(filtered_discovery, dict) else {}
    )
    unfiltered_discovery = (
        unfiltered_discovery if isinstance(unfiltered_discovery, dict) else {}
    )
    filtered_devices = filtered_discovery.get("device_list")
    unfiltered_devices = unfiltered_discovery.get("device_list")
    filtered_devices = filtered_devices if isinstance(filtered_devices, list) else []
    unfiltered_devices = (
        unfiltered_devices if isinstance(unfiltered_devices, list) else []
    )
    command_argv = identity.get("command_argv")
    command_argv = command_argv if isinstance(command_argv, list) else []

    exactness_checks, exactness_recomputed = validate_exactness(exactness)
    timing_checks, timing_recomputed = validate_timing(timing)
    expected_physical = EXPECTED_PHYSICAL_DEVICES.get(rank, {})
    physical_fields_exact = bool(expected_physical) and all(
        unfiltered_physical.get(field) == value
        for field, value in expected_physical.items()
    )
    filtered_fields_exact = bool(expected_physical) and all(
        filtered_logical.get(field) == value
        for field, value in expected_physical.items()
        if field != "device_id"
    )
    rank_arguments = argument_values(command_argv, "--rank")
    mode_arguments = argument_values(command_argv, "--mode")
    output_arguments = argument_values(command_argv, "--out")
    harness_sha_arguments = argument_values(
        command_argv,
        "--expected-script-sha256",
    )
    epoch_arguments = argument_values(command_argv, "--epochs")
    counter_call_arguments = argument_values(command_argv, "--counter-calls")
    checks: dict[str, bool] = {
        "format": payload.get("format") == "laguna-shared-down-mm-component-v2",
        "status": payload.get("status") == "component-card-passed",
        "top_level_pass": payload.get("passed") is True,
        "component_card_pass": payload.get("component_card_passed") is True,
        "four_card_not_preclaimed": (
            payload.get("four_card_component_passed") is False
        ),
        "counter_not_evaluated": payload.get("counter_gate_evaluated") is False,
        "counter_not_authorized": (
            payload.get("counter_execution_authorized") is False
        ),
        "endpoint_not_authorized": payload.get("endpoint_authorized") is False,
        "no_model_generation": (payload.get("model_generation_performed") is False),
        "rank_valid": rank in EXPECTED_RANKS,
        "expected_harness_sha": (
            expected.get("script_sha256") == EXPECTED_HARNESS_SHA256
        ),
        "runtime_harness_sha": (
            isinstance(identity.get("script"), dict)
            and identity["script"].get("sha256") == EXPECTED_HARNESS_SHA256
            and identity["script"].get("path") == str(EXPECTED_HARNESS_PATH)
        ),
        "expected_vllm_commit": (expected.get("vllm_commit") == EXPECTED_VLLM_COMMIT),
        "expected_kernel_commit": (
            expected.get("kernel_commit") == EXPECTED_KERNEL_COMMIT
        ),
        "expected_binaries": (expected.get("binary_sha256") == EXPECTED_BINARY_SHA256),
        "expected_binary_paths": (
            expected.get("binary_paths")
            == {name: str(path) for name, path in EXPECTED_BINARY_PATHS.items()}
        ),
        "expected_boot": expected.get("boot_id") == EXPECTED_BOOT_ID,
        "expected_model_config": (
            expected.get("model_config_path") == str(EXPECTED_MODEL_CONFIG_PATH)
            and expected.get("model_config_sha256") == EXPECTED_MODEL_CONFIG_SHA256
        ),
        "expected_physical": (expected.get("physical_device") == expected_physical),
        "artifact_root": expected.get("artifact_root") == str(ARTIFACT_ROOT),
        "main_git_clean": (
            main_git.get("clean") is True and main_git.get("path") == str(MAIN_REPO)
        ),
        "main_git_commit_present": (
            isinstance(main_git.get("commit"), str) and len(main_git["commit"]) == 40
        ),
        "vllm_git": (
            vllm_git.get("clean") is True
            and vllm_git.get("commit") == EXPECTED_VLLM_COMMIT
            and vllm_git.get("path") == str(VLLM_REPO)
        ),
        "kernel_git": (
            kernel_git.get("clean") is True
            and kernel_git.get("commit") == EXPECTED_KERNEL_COMMIT
            and kernel_git.get("path") == str(KERNEL_REPO)
        ),
        "environment": all(
            environment.get(name) == value
            for name, value in EXPECTED_RECORD_ENVIRONMENT.items()
        ),
        "affinity": environment.get("ZE_AFFINITY_MASK") == str(rank),
        "selector": environment.get("ONEAPI_DEVICE_SELECTOR") == "level_zero:0",
        "command_rank": rank_arguments == [str(rank)],
        "command_mode": mode_arguments in ([], ["full"]),
        "command_harness_sha": harness_sha_arguments == [EXPECTED_HARNESS_SHA256],
        "command_epochs": epoch_arguments in ([], [str(EXPECTED_EPOCHS)]),
        "command_counter_calls": counter_call_arguments in ([], ["13"]),
        "command_output": (
            len(output_arguments) == 1
            and output_arguments[0] is not None
            and Path(str(output_arguments[0])).resolve() == path
        ),
        "physical_declared_rank": physical.get("declared_rank") == rank,
        "physical_expected": physical_fields_exact,
        "filtered_physical_fields": filtered_fields_exact,
        "filtered_logical_zero": filtered_logical.get("device_id") == 0,
        "filtered_discovery_one": (
            len(filtered_devices) == 1 and filtered_devices[0] == filtered_logical
        ),
        "unfiltered_discovery_four": (
            len(unfiltered_devices) == 4
            and {
                device.get("device_id")
                for device in unfiltered_devices
                if isinstance(device, dict)
            }
            == EXPECTED_RANKS
            and any(
                device == unfiltered_physical
                for device in unfiltered_devices
                if isinstance(device, dict)
            )
        ),
        "uuid_bdf_binding": physical.get("uuid_bdf_binding_exact") is True,
        "one_visible_xpu": runtime.get("visible_torch_xpu_count") == 1,
        "b70": runtime.get("visible_torch_xpu_name") == EXPECTED_DEVICE_NAME,
        "kernel_untainted": runtime.get("kernel_taint") == "0",
        "boot_id": runtime.get("boot_id") == EXPECTED_BOOT_ID,
        "geometry": (
            geometry.get("rows") == 8
            and geometry.get("k") == 256
            and geometry.get("n") == 3072
            and geometry.get("target_layers") == EXPECTED_TARGET_LAYERS
            and geometry.get("control") == "stride-zero B=8 M=1 BF16 BMM"
            and geometry.get("candidate") == "native M=8 BF16 MM"
        ),
        "frozen_protocol": (
            frozen.get("rows") == 8
            and frozen.get("k") == 256
            and frozen.get("n") == 3072
            and frozen.get("target_layers") == EXPECTED_TARGET_LAYERS
            and frozen.get("exact_epochs") == EXPECTED_EPOCHS
            and frozen.get("post_replay_epochs") == EXPECTED_POST_REPLAY_EPOCHS
            and frozen.get("timing_kind") == "steady component timing"
            and frozen.get("warm_cycles_per_arm") == EXPECTED_WARM_CYCLES
            and frozen.get("timing_blocks") == EXPECTED_BLOCKS
            and frozen.get("cycles_per_arm") == EXPECTED_CYCLES_PER_ARM
            and frozen.get("minimum_block_wins") == MIN_BLOCK_WINS
            and close(
                frozen.get("minimum_cycle_saving_ms"),
                MIN_CYCLE_SAVING_MS,
            )
            and frozen.get("eviction_bytes_once_per_arm") == 134_217_728
        ),
        "real_shared_down_path": (
            shared_down_path.get("passed") is True
            and shared_down_path.get("scope")
            == (
                "actual RowParallelLinear forward at the checkpoint-selected "
                "unquantized local shared-down geometry"
            )
            and checkpoint_metadata.get("config_path")
            == str(EXPECTED_MODEL_CONFIG_PATH)
            and checkpoint_metadata.get("config_sha256") == EXPECTED_MODEL_CONFIG_SHA256
            and checkpoint_metadata.get("runtime_online_transform_count") == 0
            and checkpoint_metadata.get("down_offline_weight_output_transform") is True
            and shared_down_path.get("quant_method") == "UnquantizedLinearMethod"
            and shared_down_path.get("runtime_transform_modules") == []
            and shared_down_path.get("reduce_results") is False
            and shared_down_path.get("candidate_mm_calls") == 1
            and shared_down_path.get("incumbent_bmm_calls") == 2
            and shared_down_path.get("candidate_output_raw_exact") is True
            and shared_down_path.get("unmarked_output_raw_exact") is True
            and shared_down_path.get("m7_tail_output_raw_exact") is True
            and shared_down_path.get("bad_layout_failed_closed") is True
        ),
    }
    checks.update(
        {f"exactness:{name}": value for name, value in exactness_checks.items()}
    )
    checks.update({f"timing:{name}": value for name, value in timing_checks.items()})
    for name, expected_sha in EXPECTED_BINARY_SHA256.items():
        binary = binaries.get(name)
        checks[f"binary:{name}"] = (
            isinstance(binary, dict)
            and binary.get("sha256") == expected_sha
            and Path(str(binary.get("path"))).resolve() == EXPECTED_BINARY_PATHS[name]
        )

    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "rank": rank,
        "physical_uuid": unfiltered_physical.get("uuid"),
        "physical_bdf": unfiltered_physical.get("pci_bdf_address"),
        "main_commit": main_git.get("commit"),
        "vllm_commit": vllm_git.get("commit"),
        "kernel_commit": kernel_git.get("commit"),
        "boot_id": runtime.get("boot_id"),
        "aggregate_fixture_sha256": exactness_recomputed.get(
            "aggregate_fixture_sha256"
        ),
        "aggregate_output_sha256": exactness_recomputed.get("aggregate_output_sha256"),
        "timing": timing_recomputed,
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--card-result",
        action="append",
        type=Path,
        required=True,
        help="per-card component JSON; provide exactly four times",
    )
    parser.add_argument(
        "--expected-analyzer-sha256",
        type=sha256_argument,
        required=True,
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    verify_nvme_mount()
    analyzer_path = Path(__file__).resolve()
    analyzer_sha256 = sha256_file(analyzer_path)
    if analyzer_sha256 != args.expected_analyzer_sha256:
        raise RuntimeError(
            f"analyzer SHA256 {analyzer_sha256} != {args.expected_analyzer_sha256}"
        )
    if len(args.card_result) != 4:
        raise SystemExit("exactly four --card-result paths are required")
    card_paths = [
        require_local_result_path(path, must_exist=True) for path in args.card_result
    ]
    if len(set(card_paths)) != 4:
        raise SystemExit("four distinct --card-result paths are required")
    output = require_local_result_path(args.out, must_exist=False)
    cards = [validate_card(path, load_result(path)) for path in card_paths]
    ranks = [card["rank"] for card in cards]
    physical_uuids = {card["physical_uuid"] for card in cards}
    physical_bdfs = {card["physical_bdf"] for card in cards}
    fixture_hashes = {card["aggregate_fixture_sha256"] for card in cards}
    output_hashes = {card["aggregate_output_sha256"] for card in cards}
    main_commits = {card["main_commit"] for card in cards}
    vllm_commits = {card["vllm_commit"] for card in cards}
    kernel_commits = {card["kernel_commit"] for card in cards}
    boot_ids = {card["boot_id"] for card in cards}
    aggregate_checks = {
        "all_cards_recomputed_pass": all(card["passed"] for card in cards),
        "exact_declared_ranks": set(ranks) == EXPECTED_RANKS,
        "four_distinct_physical_uuids": (
            len(physical_uuids) == 4 and None not in physical_uuids
        ),
        "four_distinct_physical_bdfs": (
            len(physical_bdfs) == 4 and None not in physical_bdfs
        ),
        "identical_fixture_aggregate": (
            len(fixture_hashes) == 1 and None not in fixture_hashes
        ),
        "identical_output_aggregate": (
            len(output_hashes) == 1 and None not in output_hashes
        ),
        "one_clean_main_commit": (len(main_commits) == 1 and None not in main_commits),
        "frozen_vllm_commit": vllm_commits == {EXPECTED_VLLM_COMMIT},
        "frozen_kernel_commit": kernel_commits == {EXPECTED_KERNEL_COMMIT},
        "one_boot": len(boot_ids) == 1 and None not in boot_ids,
    }
    analyzer_git = git_identity(MAIN_REPO)
    if analyzer_git.get("clean") is not True:
        raise RuntimeError("main worktree is dirty during aggregate analysis")
    aggregate_checks["analyzer_main_matches_cards"] = main_commits == {
        analyzer_git.get("commit")
    }
    component_passed = all(aggregate_checks.values())
    result: dict[str, object] = {
        "format": "laguna-shared-down-mm-four-card-component-v2",
        "status": (
            "component-passed-counter-tooling-freeze-next"
            if component_passed
            else "component-failed-stop-before-counters"
        ),
        "passed": component_passed,
        "component_passed": component_passed,
        "counter_tooling_construction_authorized": component_passed,
        "counter_execution_authorized": False,
        "counter_gate_evaluated": False,
        "endpoint_authorized": False,
        "model_generation_performed": False,
        "created_utc": utc_now(),
        "command_argv": list(sys.argv),
        "analyzer": {
            "path": str(analyzer_path),
            "sha256": analyzer_sha256,
            "expected_sha256": args.expected_analyzer_sha256,
            "main_git": analyzer_git,
        },
        "frozen_identity": {
            "harness_sha256": EXPECTED_HARNESS_SHA256,
            "vllm_commit": EXPECTED_VLLM_COMMIT,
            "kernel_commit": EXPECTED_KERNEL_COMMIT,
            "binary_sha256": EXPECTED_BINARY_SHA256,
        },
        "required_ranks": sorted(EXPECTED_RANKS),
        "declared_ranks": ranks,
        "aggregate_fixture_sha256": (
            next(iter(fixture_hashes)) if len(fixture_hashes) == 1 else None
        ),
        "aggregate_output_sha256": (
            next(iter(output_hashes)) if len(output_hashes) == 1 else None
        ),
        "aggregate_checks": aggregate_checks,
        "cards": sorted(
            cards,
            key=lambda card: card["rank"] if isinstance(card["rank"], int) else 99,
        ),
    }
    initialize_output(output)
    atomic_write_json(output, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "passed": component_passed,
                "output": str(output),
                "counter_execution_authorized": False,
                "endpoint_authorized": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if component_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

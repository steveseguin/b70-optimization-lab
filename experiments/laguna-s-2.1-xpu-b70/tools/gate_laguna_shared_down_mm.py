#!/usr/bin/env python3
"""Fail-closed component gate for Laguna shared-down native M=8 BF16 MM.

The control is the exact target verifier's stride-zero batch of eight M=1
BMMs.  The candidate changes only the shared-expert down projection core to a
native M=8 MM:

    control:   B=8, M=1, K=256, N=3072 stride-zero BF16 BMM
    candidate: M=8, K=256, N=3072 BF16 MM

Gate/up, the exact shared SiLU/multiply, shared+routed scale/add, and the
fixed-rank reduction boundaries are unchanged.  Synthetic downstream values
are checked here only to prove that an exact down output remains exact through
those literal boundaries; endpoint quality still requires the canonical
teacher.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import torch


ARTIFACT_ROOT_LITERAL = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1")
ARTIFACT_ROOT = ARTIFACT_ROOT_LITERAL.resolve()
NVME_SOURCE = "/dev/nvme0n1p2"
NVME_FSTYPE = "ext4"
EXPECTED_BOOT_ID = "0b7f98a5-e50a-46a5-81ea-15938b55317a"
EXPECTED_DEVICE_NAME = "Intel(R) Arc(TM) Pro B70 Graphics"
MODEL_CONFIG_LITERAL = Path("/mnt/fast-ai/llm-models/laguna-s-2.1/int4/config.json")
MODEL_CONFIG_PATH = MODEL_CONFIG_LITERAL.resolve()
EXPECTED_MODEL_CONFIG_SHA256 = (
    "9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6"
)
MAIN_REPO = Path("/home/steve/llm-optimizations").resolve()
VLLM_REPO = Path("/home/steve/src/deepseek-v4-vllm-xpu-dspark").resolve()
KERNEL_REPO = Path("/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc").resolve()
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
RECORD_ENVIRONMENT_NAMES = (
    "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM",
    "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE",
    "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE",
    "VLLM_XPU_EXACT_SPEC_ATTN",
    "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE",
    "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2",
    "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE",
    "VLLM_XPU_LAGUNA_M8_W1_N_TILE",
    "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM",
    "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK",
    "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION",
    "VLLM_XPU_LAGUNA_M8_REMOTE_ZERO",
    "VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM",
    "VLLM_XPU_ENABLE_XPU_GRAPH",
    "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH",
    "VLLM_XPU_FORCE_GRAPH_WITH_COMM",
    "VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE",
    "XPU_GRAPH",
    "VLLM_USE_AOT_COMPILE",
    "ONEAPI_DEVICE_SELECTOR",
    "ZE_AFFINITY_MASK",
    "PYTHONPATH",
)
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
ROWS = 8
K_DIM = 256
N_DIM = 3072
TARGET_LAYERS = 47
MIN_EXACT_EPOCHS = 128
POST_REPLAY_EPOCHS = 32
TIMING_BLOCKS = 31
CYCLES_PER_ARM = 64
WARM_CYCLES = 20
MIN_BLOCK_WINS = 28
MIN_CYCLE_SAVING_MS = 0.15
WEIGHT_SCALE = 0.02
EVICT_ELEMENTS = 33_554_432


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_text_command(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
) -> str:
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env=env,
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


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def require_local_nvme_path(path: Path, *, must_exist: bool) -> Path:
    require(
        ARTIFACT_ROOT == ARTIFACT_ROOT_LITERAL,
        "Laguna artifact root itself is a symlink or resolved-path alias",
    )
    require(path.is_absolute(), f"path must be absolute: {path}")
    require(path.suffix == ".json", f"result path must end in .json: {path}")
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
    require(
        mount.returncode == 0 and (NVME_SOURCE, NVME_FSTYPE) in reported_mounts,
        "Laguna artifact root is not on the required local NVMe/ext4 "
        f"identity ({NVME_SOURCE}, {NVME_FSTYPE})",
    )
    if must_exist:
        require(path.exists(), f"required result does not exist: {path}")
        resolved = path.resolve(strict=True)
    else:
        require(
            not path.exists() and not path.is_symlink(),
            f"refusing to overwrite or follow existing result path: {path}",
        )
        resolved = path.parent.resolve(strict=False) / path.name
    require(
        _path_is_within(resolved, ARTIFACT_ROOT),
        "result path is outside the required Laguna local-NVMe artifact "
        f"root: {resolved}",
    )
    require(
        not str(resolved).startswith(("/media/", "/mnt/usb-models/")),
        f"removable-media result path rejected: {resolved}",
    )
    return resolved


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


def initialize_result(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved_after_create = path.parent.resolve(strict=True) / path.name
    require(
        resolved_after_create == path
        and _path_is_within(resolved_after_create, ARTIFACT_ROOT),
        f"output parent escaped the local artifact root: {resolved_after_create}",
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o644)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write("{}\n")
        handle.flush()
        os.fsync(handle.fileno())
    atomic_write_json(path, payload)


def xpu_smi_discovery(env: dict[str, str]) -> dict[str, object]:
    payload = json.loads(run_text_command(["xpu-smi", "discovery", "-j"], env=env))
    require(isinstance(payload, dict), "xpu-smi discovery is not an object")
    devices = payload.get("device_list")
    require(isinstance(devices, list), "xpu-smi discovery lacks device_list")
    return payload


def validate_physical_device(
    rank: int,
    *,
    filtered: dict[str, object],
    unfiltered: dict[str, object],
) -> dict[str, object]:
    filtered_devices = filtered["device_list"]
    unfiltered_devices = unfiltered["device_list"]
    require(
        isinstance(filtered_devices, list) and len(filtered_devices) == 1,
        "affinity-filtered xpu-smi discovery must expose exactly one device",
    )
    visible = filtered_devices[0]
    require(isinstance(visible, dict), "filtered xpu-smi device is invalid")
    require(
        visible.get("device_id") == 0,
        "affinity-filtered physical card was not renumbered to logical zero",
    )
    require(
        isinstance(unfiltered_devices, list) and len(unfiltered_devices) == 4,
        "unfiltered xpu-smi discovery must expose exactly four devices",
    )
    physical = next(
        (
            device
            for device in unfiltered_devices
            if isinstance(device, dict) and device.get("device_id") == rank
        ),
        None,
    )
    require(physical is not None, f"physical rank {rank} absent from xpu-smi")
    expected = EXPECTED_PHYSICAL_DEVICES[rank]
    for field, expected_value in expected.items():
        require(
            physical.get(field) == expected_value,
            f"physical rank {rank} {field}={physical.get(field)!r}, "
            f"expected {expected_value!r}",
        )
    for field in ("uuid", "pci_bdf_address", "drm_device", "device_name"):
        require(
            visible.get(field) == physical.get(field),
            f"filtered logical device 0 {field} does not bind to physical rank {rank}",
        )
    return {
        "declared_rank": rank,
        "filtered_logical_device": visible,
        "unfiltered_physical_device": physical,
        "expected_physical_device": expected,
        "uuid_bdf_binding_exact": True,
    }


def collect_runtime_identity(
    rank: int,
    *,
    expected_script_sha256: str,
) -> dict[str, object]:
    import vllm
    from vllm.model_executor.models import laguna

    script_path = Path(__file__).resolve()
    script_sha256 = sha256_file(script_path)
    require(
        script_sha256 == expected_script_sha256,
        f"harness SHA256 {script_sha256} != {expected_script_sha256}",
    )

    repositories = {
        "main": git_identity(MAIN_REPO),
        "vllm": git_identity(VLLM_REPO),
        "kernels": git_identity(KERNEL_REPO),
    }
    require(repositories["main"]["clean"] is True, "main worktree is dirty")
    require(repositories["vllm"]["clean"] is True, "vLLM worktree is dirty")
    require(repositories["kernels"]["clean"] is True, "kernel worktree is dirty")
    require(
        repositories["vllm"]["commit"] == EXPECTED_VLLM_COMMIT,
        "vLLM commit drift",
    )
    require(
        repositories["kernels"]["commit"] == EXPECTED_KERNEL_COMMIT,
        "kernel commit drift",
    )

    record_environment = {
        name: os.environ.get(name) for name in RECORD_ENVIRONMENT_NAMES
    }
    for name, expected in EXPECTED_RECORD_ENVIRONMENT.items():
        require(
            record_environment[name] == expected,
            f"record environment {name}={record_environment[name]!r}, "
            f"expected {expected!r}",
        )
    require(
        record_environment["ZE_AFFINITY_MASK"] == str(rank),
        f"rank {rank} requires ZE_AFFINITY_MASK={rank}",
    )
    require(
        record_environment["ONEAPI_DEVICE_SELECTOR"] == "level_zero:0",
        "ONEAPI_DEVICE_SELECTOR must be level_zero:0 after affinity selection",
    )

    filtered_env = dict(os.environ)
    unfiltered_env = dict(os.environ)
    unfiltered_env.pop("ZE_AFFINITY_MASK", None)
    unfiltered_env.pop("ONEAPI_DEVICE_SELECTOR", None)
    filtered_discovery = xpu_smi_discovery(filtered_env)
    unfiltered_discovery = xpu_smi_discovery(unfiltered_env)
    physical_device = validate_physical_device(
        rank,
        filtered=filtered_discovery,
        unfiltered=unfiltered_discovery,
    )

    modules = {
        name: importlib.import_module(f"vllm_xpu_kernels.{name}")
        for name in ("_C", "_xpu_C", "_moe_C")
    }
    binaries: dict[str, dict[str, str]] = {}
    for name, module in modules.items():
        module_path = Path(module.__file__).resolve()
        require(
            module_path == EXPECTED_BINARY_PATHS[name],
            f"loaded {name} path drift: {module_path}",
        )
        binaries[name] = {
            "path": str(module_path),
            "sha256": sha256_file(module_path),
        }
    grouped_path = (
        Path(modules["_xpu_C"].__file__).resolve().parent / "libgrouped_gemm_xe_2.so"
    ).resolve()
    binaries["libgrouped_gemm_xe_2"] = {
        "path": str(grouped_path),
        "sha256": sha256_file(grouped_path),
    }
    for name, expected in EXPECTED_BINARY_SHA256.items():
        require(
            Path(binaries[name]["path"]) == EXPECTED_BINARY_PATHS[name],
            f"{name} path drift",
        )
        require(
            binaries[name]["sha256"] == expected,
            f"{name} SHA256 drift",
        )

    vllm_module_path = Path(vllm.__file__).resolve()
    laguna_module_path = Path(laguna.__file__).resolve()
    require(
        _path_is_within(vllm_module_path, VLLM_REPO)
        and _path_is_within(laguna_module_path, VLLM_REPO),
        "loaded vLLM/Laguna source is outside the frozen vLLM repo",
    )
    require(
        torch.xpu.device_count() == 1,
        "gate requires exactly one visible torch XPU",
    )
    torch.xpu.set_device(0)
    device_name = torch.xpu.get_device_name(0)
    require(
        device_name == EXPECTED_DEVICE_NAME,
        f"visible device name {device_name!r} != {EXPECTED_DEVICE_NAME!r}",
    )
    boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    kernel_taint = Path("/proc/sys/kernel/tainted").read_text().strip()
    require(boot_id == EXPECTED_BOOT_ID, f"boot identity drift: {boot_id}")
    require(kernel_taint == "0", f"kernel is tainted: {kernel_taint}")

    return {
        "captured_utc": utc_now(),
        "command_argv": list(sys.argv),
        "script": {
            "path": str(script_path),
            "sha256": script_sha256,
        },
        "repositories": repositories,
        "vllm_module_path": str(vllm_module_path),
        "laguna_module_path": str(laguna_module_path),
        "binaries": binaries,
        "record_environment": record_environment,
        "physical_device": physical_device,
        "runtime": {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "python": sys.version,
            "torch": torch.__version__,
            "xpu_smi_version": run_text_command(["xpu-smi", "--version"]),
            "boot_id": boot_id,
            "kernel_taint": kernel_taint,
            "visible_torch_xpu_count": torch.xpu.device_count(),
            "visible_torch_xpu_name": device_name,
        },
        "xpu_smi": {
            "filtered": filtered_discovery,
            "unfiltered": unfiltered_discovery,
        },
    }


def raw_sha256(*tensors: torch.Tensor) -> str:
    digest = hashlib.sha256()
    for tensor in tensors:
        raw = tensor.detach().cpu().contiguous().view(torch.uint8)
        digest.update(raw.numpy().tobytes())
    return digest.hexdigest()


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


def make_fixture(
    *,
    rank: int,
    epoch: int,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, tuple[torch.Tensor, ...]]:
    # Every physical card receives the same rank-invariant changing corpus.
    # `rank` remains an explicit call argument so the result binds the observed
    # device identity without allowing the numerical fixture to drift by card.
    _ = rank
    seed = 730_000 + epoch * 10
    rows = cpu_bf16_random(
        (ROWS, K_DIM),
        seed=seed,
        scale=0.5,
    ).to("xpu")
    weight = cpu_bf16_random(
        (N_DIM, K_DIM),
        seed=seed + 1,
        scale=WEIGHT_SCALE,
    ).to("xpu")
    routed = cpu_bf16_random(
        (ROWS, N_DIM),
        seed=seed + 2,
        scale=0.1,
    ).to("xpu")
    other_ranks = tuple(
        cpu_bf16_random(
            (ROWS, N_DIM),
            seed=seed + 3 + peer,
            scale=0.1,
        ).to("xpu")
        for peer in range(3)
    )
    return rows, weight, routed, other_ranks


def stride_zero_bmm_reference(
    rows: torch.Tensor,
    weight: torch.Tensor,
) -> torch.Tensor:
    require(
        rows.ndim == 2 and 1 <= rows.shape[0] <= ROWS and rows.shape[1] == K_DIM,
        "bad reference rows shape",
    )
    require(tuple(weight.shape) == (N_DIM, K_DIM), "bad incumbent weight shape")
    weight_t = weight.t().unsqueeze(0).expand(rows.shape[0], -1, -1)
    require(weight_t.stride(0) == 0, "incumbent lost stride-zero batch")
    output = torch.bmm(rows.unsqueeze(1), weight_t).squeeze(1)
    require(output.dtype == torch.bfloat16, "incumbent output is not BF16")
    return output


def incumbent_bmm(rows: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    require(tuple(rows.shape) == (ROWS, K_DIM), "bad incumbent rows shape")
    return stride_zero_bmm_reference(rows, weight)


def candidate_mm(rows: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    require(tuple(rows.shape) == (ROWS, K_DIM), "bad candidate rows shape")
    require(tuple(weight.shape) == (N_DIM, K_DIM), "bad candidate weight shape")
    output = torch.mm(rows, weight.t())
    require(output.dtype == torch.bfloat16, "candidate output is not BF16")
    return output


def downstream(
    down: torch.Tensor,
    routed: torch.Tensor,
    other_ranks: tuple[torch.Tensor, ...],
) -> tuple[torch.Tensor, torch.Tensor]:
    scaled = routed.clone()
    scaled.mul_(2.5)
    combined = down + scaled
    reduced = combined.clone()
    for peer in other_ranks:
        reduced.add_(peer)
    return combined, reduced


def compare_epoch(
    *,
    rank: int,
    epoch: int,
) -> dict[str, object]:
    rows, weight, routed, other_ranks = make_fixture(rank=rank, epoch=epoch)
    inputs_before = raw_sha256(rows, weight, routed, *other_ranks)
    control_down = incumbent_bmm(rows, weight)
    candidate_down = candidate_mm(rows, weight)
    candidate_repeat = candidate_mm(rows, weight)
    control_combined, control_reduced = downstream(
        control_down,
        routed,
        other_ranks,
    )
    candidate_combined, candidate_reduced = downstream(
        candidate_down,
        routed,
        other_ranks,
    )
    inputs_after = raw_sha256(rows, weight, routed, *other_ranks)

    pairs = {
        "down": (control_down, candidate_down),
        "candidate_repeat": (candidate_down, candidate_repeat),
        "shared_routed_add": (control_combined, candidate_combined),
        "fixed_rank_sum": (control_reduced, candidate_reduced),
    }
    equal = {
        name: torch.equal(control, candidate)
        and raw_sha256(control) == raw_sha256(candidate)
        for name, (control, candidate) in pairs.items()
    }
    raw_outputs = {
        "down": {
            "control": raw_sha256(control_down),
            "candidate": raw_sha256(candidate_down),
        },
        "candidate_repeat": {
            "first": raw_sha256(candidate_down),
            "repeat": raw_sha256(candidate_repeat),
        },
        "shared_routed_add": {
            "control": raw_sha256(control_combined),
            "candidate": raw_sha256(candidate_combined),
        },
        "fixed_rank_sum": {
            "control": raw_sha256(control_reduced),
            "candidate": raw_sha256(candidate_reduced),
        },
        "aggregate": {
            "control": raw_sha256(
                control_down,
                control_combined,
                control_reduced,
            ),
            "candidate": raw_sha256(
                candidate_down,
                candidate_combined,
                candidate_reduced,
            ),
        },
    }
    require(all(equal.values()), f"rank {rank} epoch {epoch}: exactness failure")
    require(
        all(
            pair["control"] == pair["candidate"]
            for name, pair in raw_outputs.items()
            if name != "candidate_repeat"
        )
        and raw_outputs["candidate_repeat"]["first"]
        == raw_outputs["candidate_repeat"]["repeat"],
        f"rank {rank} epoch {epoch}: raw digest mismatch",
    )
    require(
        inputs_before == inputs_after,
        f"rank {rank} epoch {epoch}: candidate mutated an input",
    )
    require(
        bool(torch.isfinite(candidate_reduced).all().item()),
        f"rank {rank} epoch {epoch}: non-finite output",
    )
    return {
        "epoch": epoch,
        "equal": equal,
        "raw_outputs": raw_outputs,
        "inputs_unchanged": True,
        "fixture_sha256": inputs_before,
        "output_sha256": raw_outputs["aggregate"]["candidate"],
    }


def make_timing_corpus(
    rank: int,
) -> list[tuple[torch.Tensor, torch.Tensor]]:
    corpus = []
    for layer in range(TARGET_LAYERS):
        rows, weight, _routed, _other_ranks = make_fixture(
            rank=rank,
            epoch=10_000 + layer,
        )
        corpus.append((rows, weight))
    return corpus


def run_cycles(
    call: Callable[[torch.Tensor, torch.Tensor], torch.Tensor],
    corpus: list[tuple[torch.Tensor, torch.Tensor]],
    *,
    cycles: int,
    offset: int,
) -> torch.Tensor:
    output = None
    for cycle in range(cycles):
        start = (offset + cycle) % len(corpus)
        for index in range(len(corpus)):
            rows, weight = corpus[(start + index) % len(corpus)]
            output = call(rows, weight)
    require(output is not None, "timing arm did not execute")
    return output


def timed_arm_ms_per_cycle(
    call: Callable[[torch.Tensor, torch.Tensor], torch.Tensor],
    corpus: list[tuple[torch.Tensor, torch.Tensor]],
    evict: torch.Tensor,
    *,
    offset: int,
) -> float:
    evict.add_(1)
    torch.xpu.synchronize()
    started_ns = time.perf_counter_ns()
    output = run_cycles(
        call,
        corpus,
        cycles=CYCLES_PER_ARM,
        offset=offset,
    )
    torch.xpu.synchronize()
    require(output.numel() == ROWS * N_DIM, "timing output shape drift")
    elapsed_ms = (time.perf_counter_ns() - started_ns) / 1_000_000.0
    return elapsed_ms / CYCLES_PER_ARM


def run_timing(rank: int) -> dict[str, object]:
    corpus = make_timing_corpus(rank)
    evict = torch.zeros(EVICT_ELEMENTS, dtype=torch.float32, device="xpu")
    run_cycles(
        incumbent_bmm,
        corpus,
        cycles=WARM_CYCLES,
        offset=0,
    )
    run_cycles(
        candidate_mm,
        corpus,
        cycles=WARM_CYCLES,
        offset=0,
    )
    torch.xpu.synchronize()

    blocks = []
    savings = []
    for block in range(TIMING_BLOCKS):
        base_offset = (block * 11) % TARGET_LAYERS
        control_first = timed_arm_ms_per_cycle(
            incumbent_bmm,
            corpus,
            evict,
            offset=base_offset,
        )
        candidate_first = timed_arm_ms_per_cycle(
            candidate_mm,
            corpus,
            evict,
            offset=(base_offset + 13) % TARGET_LAYERS,
        )
        candidate_second = timed_arm_ms_per_cycle(
            candidate_mm,
            corpus,
            evict,
            offset=(base_offset + 29) % TARGET_LAYERS,
        )
        control_second = timed_arm_ms_per_cycle(
            incumbent_bmm,
            corpus,
            evict,
            offset=(base_offset + 41) % TARGET_LAYERS,
        )
        control = (control_first + control_second) / 2.0
        candidate = (candidate_first + candidate_second) / 2.0
        saving = control - candidate
        savings.append(saving)
        blocks.append(
            {
                "block": block,
                "A1_control_ms": control_first,
                "B1_candidate_ms": candidate_first,
                "B2_candidate_ms": candidate_second,
                "A2_control_ms": control_second,
                "paired_control_ms": control,
                "paired_candidate_ms": candidate,
                "saving_ms": saving,
            }
        )

    wins = sum(saving > 0.0 for saving in savings)
    median_saving = statistics.median(savings)
    control_median = statistics.median(block["paired_control_ms"] for block in blocks)
    candidate_median = statistics.median(
        block["paired_candidate_ms"] for block in blocks
    )
    passed = wins >= MIN_BLOCK_WINS and median_saving >= MIN_CYCLE_SAVING_MS
    return {
        "passed": passed,
        "target_layers_per_cycle": TARGET_LAYERS,
        "corpus_weight_bytes": TARGET_LAYERS * N_DIM * K_DIM * 2,
        "warm_cycles_per_arm": WARM_CYCLES,
        "blocks": TIMING_BLOCKS,
        "cycles_per_arm_per_block": CYCLES_PER_ARM,
        "minimum_block_wins": MIN_BLOCK_WINS,
        "minimum_cycle_saving_ms": MIN_CYCLE_SAVING_MS,
        "candidate_block_wins": wins,
        "control_median_ms_per_cycle": control_median,
        "candidate_median_ms_per_cycle": candidate_median,
        "median_saving_ms_per_cycle": median_saving,
        "median_relative_saving": (
            median_saving / control_median if control_median else 0.0
        ),
        "blocks_detail": blocks,
    }


def load_model_metadata_contract() -> tuple[dict[str, Any], dict[str, object]]:
    require(
        MODEL_CONFIG_PATH == MODEL_CONFIG_LITERAL,
        "active Laguna model config is a symlink or resolved-path alias",
    )
    require(
        _path_is_within(MODEL_CONFIG_PATH, Path("/mnt/fast-ai").resolve()),
        "active Laguna model config is outside local NVMe",
    )
    config_sha256 = sha256_file(MODEL_CONFIG_PATH)
    require(
        config_sha256 == EXPECTED_MODEL_CONFIG_SHA256,
        f"Laguna model config SHA256 drift: {config_sha256}",
    )
    config = json.loads(MODEL_CONFIG_PATH.read_text())
    quantization = config.get("quantization_config")
    require(isinstance(quantization, dict), "model lacks quantization_config")
    ignore = quantization.get("ignore")
    require(isinstance(ignore, list), "quantization ignore contract is invalid")
    shared_down_ignore = r"re:.*\.mlp\.shared_expert\.down_proj$"
    require(
        shared_down_ignore in ignore,
        "shared-expert down projection is not explicitly unquantized",
    )
    transform_config = quantization.get("transform_config")
    require(isinstance(transform_config, dict), "transform_config is absent")
    groups = transform_config.get("config_groups")
    require(isinstance(groups, dict), "transform config_groups are absent")
    applications = [
        application
        for group in groups.values()
        if isinstance(group, dict)
        for application in group.get("apply", [])
        if isinstance(application, dict)
    ]
    locations = [application.get("location") for application in applications]
    require(
        locations and set(locations) == {"weight_input", "weight_output"},
        "checkpoint transform contract is no longer offline-only",
    )
    require(
        all(location not in {"input", "output"} for location in locations),
        "checkpoint unexpectedly requests an online runtime transform",
    )
    weight_output_targets = {
        target
        for application in applications
        if application.get("location") == "weight_output"
        for target in application.get("targets", [])
    }
    require(
        r"re:.*down_proj$" in weight_output_targets,
        "down projection lost its frozen offline weight-output transform",
    )
    return quantization, {
        "config_path": str(MODEL_CONFIG_PATH),
        "config_sha256": config_sha256,
        "shared_down_unquantized_ignore": shared_down_ignore,
        "transform_locations": locations,
        "runtime_online_transform_count": 0,
        "down_offline_weight_output_transform": True,
    }


def verify_vllm_shared_down_path(rank: int) -> dict[str, object]:
    """Exercise the actual RowParallelLinear path selected by model metadata."""
    from vllm.model_executor import parameter as parameter_module
    from vllm.model_executor.layers import linear
    from vllm.model_executor.layers.quantization.compressed_tensors.compressed_tensors import (  # noqa: E501
        CompressedTensorsConfig,
    )

    quantization, metadata = load_model_metadata_contract()
    quant_config = CompressedTensorsConfig.from_config(copy.deepcopy(quantization))
    old_parameter_rank = parameter_module.get_tensor_model_parallel_rank
    old_parameter_size = parameter_module.get_tensor_model_parallel_world_size
    try:
        # Standalone component processes have no distributed group. This patch
        # affects fixture parameter metadata only; the exercised forward is
        # the real RowParallelLinear implementation at the exact local shape.
        parameter_module.get_tensor_model_parallel_rank = lambda: 0
        parameter_module.get_tensor_model_parallel_world_size = lambda: 1
        layer = linear.RowParallelLinear(
            input_size=K_DIM,
            output_size=N_DIM,
            bias=False,
            input_is_parallel=True,
            params_dtype=torch.bfloat16,
            reduce_results=False,
            quant_config=quant_config,
            prefix="model.layers.1.mlp.shared_expert.down_proj",
            return_bias=False,
            disable_tp=True,
        ).to("xpu")
    finally:
        parameter_module.get_tensor_model_parallel_rank = old_parameter_rank
        parameter_module.get_tensor_model_parallel_world_size = old_parameter_size
    require(
        isinstance(layer.quant_method, linear.UnquantizedLinearMethod),
        "checkpoint metadata did not select UnquantizedLinearMethod",
    )
    runtime_transform_modules = [
        type(module).__name__
        for module in layer.modules()
        if type(module).__name__ == "HadamardTransform"
    ]
    require(
        not runtime_transform_modules,
        "offline-only checkpoint unexpectedly created a runtime transform",
    )
    layer.xpu_exact_spec_rows = True
    layer.xpu_laguna_m8_shared_down_mm = True
    candidate_m8_marker_enabled = layer.xpu_laguna_m8_shared_down_mm is True
    require(layer.reduce_results is False, "shared-down local path would reduce")

    rows, weight, _routed, _other_ranks = make_fixture(
        rank=rank,
        epoch=20_000,
    )
    with torch.no_grad():
        layer.weight.copy_(weight)
    require(
        raw_sha256(layer.weight) == raw_sha256(weight),
        "real layer weight copy changed bytes",
    )
    expected_candidate = candidate_mm(rows, weight)
    expected_control = incumbent_bmm(rows, weight)
    expected_tail = stride_zero_bmm_reference(rows[:7], weight)

    old_exact = linear._xpu_is_exact_decode_or_verifier_rows
    old_bmm = torch.bmm
    old_mm = torch.mm
    mm_calls = 0
    bmm_calls = 0
    try:
        linear._xpu_is_exact_decode_or_verifier_rows = lambda _: True

        def counted_mm(*args, **kwargs):
            nonlocal mm_calls
            mm_calls += 1
            return old_mm(*args, **kwargs)

        def forbidden_bmm(*_args, **_kwargs):
            raise AssertionError("candidate silently dispatched incumbent BMM")

        torch.mm = counted_mm
        torch.bmm = forbidden_bmm
        actual_candidate = layer(rows)
        candidate_exact = torch.equal(
            actual_candidate,
            expected_candidate,
        ) and raw_sha256(actual_candidate) == raw_sha256(expected_candidate)
        require(candidate_exact, "real shared-down candidate output mismatch")
        require(mm_calls == 1, f"real shared-down path issued {mm_calls} MM calls")

        noncontiguous_weight = weight.t().contiguous().t()
        require(
            not noncontiguous_weight.is_contiguous(),
            "bad-contract weight is contiguous",
        )
        layer.weight = torch.nn.Parameter(
            noncontiguous_weight,
            requires_grad=False,
        )
        try:
            layer(rows)
        except RuntimeError as error:
            bad_layout_failed_closed = "weight is not contiguous" in str(error)
        else:
            bad_layout_failed_closed = False
        require(
            bad_layout_failed_closed,
            "real shared-down bad-layout dispatch did not fail closed",
        )

        layer.weight = torch.nn.Parameter(weight, requires_grad=False)
        layer.xpu_laguna_m8_shared_down_mm = False
        unmarked_m8_marker_enabled = layer.xpu_laguna_m8_shared_down_mm is True

        def forbidden_mm(*_args, **_kwargs):
            raise AssertionError("unmarked/tail shared-down path used native MM")

        def counted_bmm(*args, **kwargs):
            nonlocal bmm_calls
            bmm_calls += 1
            return old_bmm(*args, **kwargs)

        torch.mm = forbidden_mm
        torch.bmm = counted_bmm
        unmarked = layer(rows)
        layer.xpu_laguna_m8_shared_down_mm = True
        m7_tail_marker_enabled = layer.xpu_laguna_m8_shared_down_mm is True
        tail = layer(rows[:7])
        unmarked_exact = torch.equal(
            unmarked,
            expected_control,
        ) and raw_sha256(unmarked) == raw_sha256(expected_control)
        tail_exact = torch.equal(tail, expected_tail) and raw_sha256(
            tail
        ) == raw_sha256(expected_tail)
        require(
            unmarked_exact and tail_exact and bmm_calls == 2,
            "unmarked or M7 real shared-down path left incumbent BMM",
        )
    finally:
        linear._xpu_is_exact_decode_or_verifier_rows = old_exact
        torch.bmm = old_bmm
        torch.mm = old_mm

    passed = bool(
        candidate_exact
        and bad_layout_failed_closed
        and unmarked_exact
        and tail_exact
        and candidate_m8_marker_enabled
        and not unmarked_m8_marker_enabled
        and m7_tail_marker_enabled
        and mm_calls == 1
        and bmm_calls == 2
    )
    return {
        "scope": (
            "actual RowParallelLinear forward at the checkpoint-selected "
            "unquantized local shared-down geometry"
        ),
        "checkpoint_metadata": metadata,
        "quant_method": type(layer.quant_method).__name__,
        "runtime_transform_modules": runtime_transform_modules,
        "reduce_results": layer.reduce_results,
        "candidate_m8_marker_enabled": candidate_m8_marker_enabled,
        "unmarked_m8_marker_enabled": unmarked_m8_marker_enabled,
        "m7_tail_marker_enabled": m7_tail_marker_enabled,
        "candidate_mm_calls": mm_calls,
        "incumbent_bmm_calls": bmm_calls,
        "candidate_output_raw_exact": candidate_exact,
        "unmarked_output_raw_exact": unmarked_exact,
        "m7_tail_output_raw_exact": tail_exact,
        "bad_layout_failed_closed": bad_layout_failed_closed,
        "passed": passed,
    }


def run_counter_fixture(
    rank: int,
    candidate: bool,
    calls: int,
) -> dict[str, object]:
    """Emit a direct-call fixture for later frozen counter tooling.

    This is deliberately not a unitrace runner or a hardware-counter gate.
    """
    rows, weight, _routed, _other_ranks = make_fixture(
        rank=rank,
        epoch=30_000,
    )
    evict = torch.zeros(EVICT_ELEMENTS, dtype=torch.float32, device="xpu")
    call = candidate_mm if candidate else incumbent_bmm
    output_hashes = []
    for _ in range(calls):
        evict.add_(1)
        output = call(rows, weight)
        torch.xpu.synchronize()
        output_hashes.append(raw_sha256(output))
    require(
        len(set(output_hashes)) == 1,
        "counter-mode output was not repeat deterministic",
    )
    return {
        "rank": rank,
        "treatment": "candidate-native-mm" if candidate else "control-bmm",
        "calls": calls,
        "completion_boundary_per_call": True,
        "eviction_bytes_per_call": EVICT_ELEMENTS * 4,
        "output_sha256": output_hashes[0],
        "fixture_generation_passed": True,
        "fixture_only": True,
        "unitrace_executed": False,
        "counter_gate_evaluated": False,
        "counter_execution_authorized": False,
    }


def sha256_argument(value: str) -> str:
    normalized = value.lower()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise argparse.ArgumentTypeError("expected a 64-digit SHA256")
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rank", type=int, choices=range(4), required=True)
    parser.add_argument(
        "--mode",
        choices=(
            "full",
            "counter-fixture-control",
            "counter-fixture-candidate",
        ),
        default="full",
    )
    parser.add_argument("--epochs", type=int, default=MIN_EXACT_EPOCHS)
    parser.add_argument("--counter-calls", type=int, default=13)
    parser.add_argument(
        "--expected-script-sha256",
        type=sha256_argument,
        required=True,
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    output = require_local_nvme_path(args.out, must_exist=False)
    require(args.epochs == MIN_EXACT_EPOCHS, "exactly 128 epochs are frozen")
    require(args.counter_calls == 13, "exactly 13 counter-fixture calls are frozen")
    payload: dict[str, Any] = {
        "format": (
            "laguna-shared-down-mm-component-v2"
            if args.mode == "full"
            else "laguna-shared-down-mm-counter-fixture-v2"
        ),
        "status": "running",
        "passed": False,
        "started_utc": utc_now(),
        "mode": args.mode,
        "rank": args.rank,
        "component_card_passed": None,
        "four_card_component_passed": False,
        "counter_gate_evaluated": False,
        "counter_execution_authorized": False,
        "endpoint_authorized": False,
        "model_generation_performed": False,
        "frozen_protocol": {
            "rows": ROWS,
            "k": K_DIM,
            "n": N_DIM,
            "target_layers": TARGET_LAYERS,
            "exact_epochs": MIN_EXACT_EPOCHS,
            "post_replay_epochs": POST_REPLAY_EPOCHS,
            "timing_kind": "steady component timing",
            "warm_cycles_per_arm": WARM_CYCLES,
            "timing_blocks": TIMING_BLOCKS,
            "cycles_per_arm": CYCLES_PER_ARM,
            "minimum_block_wins": MIN_BLOCK_WINS,
            "minimum_cycle_saving_ms": MIN_CYCLE_SAVING_MS,
            "eviction_bytes_once_per_arm": EVICT_ELEMENTS * 4,
        },
        "expected_identity": {
            "script_sha256": args.expected_script_sha256,
            "vllm_commit": EXPECTED_VLLM_COMMIT,
            "kernel_commit": EXPECTED_KERNEL_COMMIT,
            "binary_sha256": EXPECTED_BINARY_SHA256,
            "binary_paths": {
                name: str(path) for name, path in EXPECTED_BINARY_PATHS.items()
            },
            "boot_id": EXPECTED_BOOT_ID,
            "model_config_path": str(MODEL_CONFIG_PATH),
            "model_config_sha256": EXPECTED_MODEL_CONFIG_SHA256,
            "physical_device": EXPECTED_PHYSICAL_DEVICES[args.rank],
            "artifact_root": str(ARTIFACT_ROOT),
        },
    }
    initialize_result(output, payload)

    def checkpoint(phase: str) -> None:
        payload["last_checkpoint"] = {"phase": phase, "utc": utc_now()}
        atomic_write_json(output, payload)

    try:
        identity = collect_runtime_identity(
            args.rank,
            expected_script_sha256=args.expected_script_sha256,
        )
        payload["identity"] = identity
        checkpoint("identity-validated")

        if args.mode != "full":
            payload["counter_fixture"] = run_counter_fixture(
                args.rank,
                candidate=args.mode == "counter-fixture-candidate",
                calls=args.counter_calls,
            )
            payload["passed"] = True
            payload["status"] = "counter-fixture-generated"
        else:
            epochs = [
                compare_epoch(rank=args.rank, epoch=epoch)
                for epoch in range(args.epochs)
            ]
            fixture_hashes = [epoch["fixture_sha256"] for epoch in epochs]
            output_hashes = [epoch["output_sha256"] for epoch in epochs]
            require(
                len(set(fixture_hashes)) == args.epochs,
                "changing fixture corpus is not unique",
            )
            require(
                len(set(output_hashes)) == args.epochs,
                "changing output corpus is not unique",
            )
            payload["exactness"] = {
                "epochs": args.epochs,
                "checks_per_epoch": 4,
                "all_raw_exact": True,
                "candidate_repeat_deterministic": True,
                "inputs_unchanged": True,
                "unique_fixture_hashes": len(set(fixture_hashes)),
                "unique_output_hashes": len(set(output_hashes)),
                "aggregate_fixture_sha256": hashlib.sha256(
                    "".join(fixture_hashes).encode()
                ).hexdigest(),
                "aggregate_output_sha256": hashlib.sha256(
                    "".join(output_hashes).encode()
                ).hexdigest(),
                "epochs_detail": epochs,
            }
            checkpoint("pre-timing-exactness")

            shared_down_path = verify_vllm_shared_down_path(args.rank)
            payload["vllm_shared_down_path"] = shared_down_path
            checkpoint("real-shared-down-path")

            timing = run_timing(args.rank)
            payload["timing"] = timing
            checkpoint("steady-timing")

            post_replay = [
                compare_epoch(rank=args.rank, epoch=epoch)
                for epoch in range(POST_REPLAY_EPOCHS)
            ]
            replay_matches = all(
                post["fixture_sha256"] == epochs[index]["fixture_sha256"]
                and post["output_sha256"] == epochs[index]["output_sha256"]
                for index, post in enumerate(post_replay)
            )
            require(replay_matches, "post-timing replay changed exact outputs")
            payload["exactness"]["post_timing_replay_epochs"] = POST_REPLAY_EPOCHS
            payload["exactness"]["post_timing_replay_exact"] = replay_matches
            payload["exactness"]["post_timing_replay_detail"] = post_replay
            component_passed = bool(
                timing["passed"] and shared_down_path["passed"] and replay_matches
            )
            payload.update(
                {
                    "geometry": {
                        "rows": ROWS,
                        "k": K_DIM,
                        "n": N_DIM,
                        "target_layers": TARGET_LAYERS,
                        "control": "stride-zero B=8 M=1 BF16 BMM",
                        "candidate": "native M=8 BF16 MM",
                    },
                    "status": (
                        "component-card-passed"
                        if component_passed
                        else "component-card-failed"
                    ),
                    "passed": component_passed,
                    "component_card_passed": component_passed,
                }
            )
        payload["completed_utc"] = utc_now()
        checkpoint("complete")
    except BaseException as error:
        payload.update(
            {
                "status": "error",
                "passed": False,
                "component_card_passed": False,
                "completed_utc": utc_now(),
                "error_type": type(error).__name__,
                "error": str(error),
                "traceback": traceback.format_exc(),
            }
        )
        checkpoint("error")
        raise

    print(
        json.dumps(
            {
                "status": payload["status"],
                "passed": payload["passed"],
                "rank": payload["rank"],
                "output": str(output),
                "component_card_passed": payload["component_card_passed"],
                "counter_execution_authorized": False,
                "endpoint_authorized": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

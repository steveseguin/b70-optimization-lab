#!/usr/bin/env python3
"""Minimal direct-call fixture for Laguna shared-down cold counter capture.

The fixture deliberately starts no subprocesses.  A separately frozen runner
performs Git, profiler, physical-device, and idle checks before launching this
process under unitrace.  This process verifies its direct runtime identity,
constructs one rank-invariant BF16 fixture, and issues exactly thirteen
completion-bounded selected GEMMs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch

import gate_laguna_shared_down_mm as gate


ARTIFACT_ROOT_LITERAL = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1")
ARTIFACT_ROOT = ARTIFACT_ROOT_LITERAL.resolve()
NVME_MOUNT = Path("/mnt/fast-ai")
NVME_SOURCE = "/dev/nvme0n1p2"
NVME_FSTYPE = "ext4"
GATE_PATH = Path(__file__).with_name("gate_laguna_shared_down_mm.py").resolve()
EXPECTED_GATE_SHA256 = (
    "df8496f1f405e8b786dff0b96b7c320944c5d0133cce0bfcc2e36150ab1e0f12"
)
EXPECTED_PYTHON_SHA256 = (
    "202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8"
)
EXPECTED_TORCH_VERSION = "2.12.0+xpu"
TORCH_PACKAGE = Path(
    "/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/site-packages/torch"
)
EXPECTED_TORCH_FILES = {
    "__init__": {
        "path": str(TORCH_PACKAGE / "__init__.py"),
        "sha256": ("d9dfff4b75d46e4c75572200a3466b70231d05b0318e38ac1bd121789165fb49"),
    },
    "_C": {
        "path": str(TORCH_PACKAGE / "_C.cpython-312-x86_64-linux-gnu.so"),
        "sha256": ("deff36272fed31705b74c8f1da372baaaf659c0229d3ce57daab8894e6dc7e84"),
    },
    "libtorch_xpu": {
        "path": str(TORCH_PACKAGE / "lib/libtorch_xpu.so"),
        "sha256": ("63b7a56723482bc35d31842f442f6e903ef0b7fbd741c1a4ae309123bbc90572"),
    },
    "libtorch_cpu": {
        "path": str(TORCH_PACKAGE / "lib/libtorch_cpu.so"),
        "sha256": ("bbf261729e5f190124060318435d9aa39cbb17a12377f2fb999ac6f531125315"),
    },
    "libtorch": {
        "path": str(TORCH_PACKAGE / "lib/libtorch.so"),
        "sha256": ("b5a183867725fb49b7262172c15f94d51fa1e393d34e43d4cdc5d328cd037ab6"),
    },
    "libc10": {
        "path": str(TORCH_PACKAGE / "lib/libc10.so"),
        "sha256": ("1231da9267e3d80bfb0affc3116fc88fff26fa201d83e0c41f46efb6d300736a"),
    },
    "libc10_xpu": {
        "path": str(TORCH_PACKAGE / "lib/libc10_xpu.so"),
        "sha256": ("7ab1b1f2ab4a25ea9364b614fe43f264b3d0eb0786a3af93be74f4769394df12"),
    },
}
EXPECTED_PYTHONPATH = f"{gate.VLLM_REPO}:{gate.KERNEL_REPO}"
ROWS = 8
K_DIM = 256
N_DIM = 3072
EPOCH = 30_000
CALLS = 13
EVICTION_BYTES = 128 * 1024 * 1024
EVICTION_ELEMENTS = EVICTION_BYTES // 4


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_argument(value: str) -> str:
    normalized = value.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise argparse.ArgumentTypeError("expected a 64-digit SHA-256")
    return normalized


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _decode_mount_field(value: str) -> str:
    return re.sub(
        r"\\([0-7]{3})",
        lambda match: chr(int(match.group(1), 8)),
        value,
    )


def mount_identity() -> dict[str, str]:
    """Read mount identity without starting a process inside unitrace."""
    candidates: list[tuple[int, str, str, str]] = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        before, separator, after = line.partition(" - ")
        require(bool(separator), "malformed /proc/self/mountinfo row")
        left = before.split()
        right = after.split()
        require(len(left) >= 6 and len(right) >= 2, "short mountinfo row")
        mount_point = _decode_mount_field(left[4])
        try:
            NVME_MOUNT.relative_to(Path(mount_point))
        except ValueError:
            continue
        candidates.append(
            (len(mount_point), mount_point, right[0], _decode_mount_field(right[1]))
        )
    require(bool(candidates), f"no mount identity found for {NVME_MOUNT}")
    _length, mount_point, filesystem, source = max(candidates)
    require(
        filesystem == NVME_FSTYPE and source == NVME_SOURCE,
        "Laguna artifact root is not on the frozen local NVMe/ext4 mount",
    )
    require(
        os.stat(ARTIFACT_ROOT).st_dev == os.stat(NVME_MOUNT).st_dev,
        "Laguna artifact root device differs from /mnt/fast-ai",
    )
    return {
        "target": str(NVME_MOUNT),
        "mount_point": mount_point,
        "source": source,
        "filesystem": filesystem,
    }


def require_output_path(path: Path) -> Path:
    require(
        ARTIFACT_ROOT == ARTIFACT_ROOT_LITERAL
        and not ARTIFACT_ROOT_LITERAL.is_symlink(),
        "Laguna artifact root is a symlink or resolved-path alias",
    )
    require(path.is_absolute() and path.suffix == ".json", "bad fixture output path")
    require(
        not path.exists() and not path.is_symlink(), "fixture output already exists"
    )
    parent = path.parent.resolve(strict=True)
    resolved = parent / path.name
    require(
        resolved == path
        and _path_is_within(resolved, ARTIFACT_ROOT)
        and not str(resolved).startswith(("/media/", "/mnt/usb-models/")),
        "fixture output escaped the frozen local-NVMe artifact root",
    )
    mount_identity()
    return resolved


def atomic_exclusive_json(path: Path, payload: dict[str, Any]) -> None:
    encoded = (
        json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o644,
    )
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def direct_runtime_identity(rank: int, fixture_path: Path) -> dict[str, Any]:
    require(sha256_file(GATE_PATH) == EXPECTED_GATE_SHA256, "frozen gate SHA drift")
    require(
        sha256_file(gate.MODEL_CONFIG_PATH) == gate.EXPECTED_MODEL_CONFIG_SHA256,
        "model config SHA drift",
    )
    for name, expected in gate.EXPECTED_BINARY_SHA256.items():
        binary_path = gate.EXPECTED_BINARY_PATHS[name]
        require(
            binary_path.is_file() and sha256_file(binary_path) == expected,
            f"frozen binary identity drift: {name}",
        )
    require(
        sha256_file(Path(sys.executable)) == EXPECTED_PYTHON_SHA256,
        "Python interpreter SHA drift",
    )
    require(torch.__version__ == EXPECTED_TORCH_VERSION, "Torch version drift")
    require(
        Path(torch.__file__).resolve()
        == Path(EXPECTED_TORCH_FILES["__init__"]["path"]),
        "Torch module path drift",
    )
    require(
        Path(torch._C.__file__).resolve() == Path(EXPECTED_TORCH_FILES["_C"]["path"]),
        "Torch _C module path drift",
    )
    for name, expected in EXPECTED_TORCH_FILES.items():
        torch_path = Path(expected["path"])
        require(
            torch_path.is_file() and sha256_file(torch_path) == expected["sha256"],
            f"Torch/XPU runtime file SHA drift: {name}",
        )

    environment_names = set(gate.RECORD_ENVIRONMENT_NAMES) | {
        "PYTHONHASHSEED",
        "PYTHONNOUSERSITE",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONPYCACHEPREFIX",
        "PATH",
        "LANG",
        "LC_ALL",
        "HOME",
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "SYCL_CACHE_DIR",
        "TMPDIR",
        "TMP",
        "TEMP",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "TORCHINDUCTOR_CACHE_DIR",
        "TRITON_CACHE_DIR",
        "NUMBA_CACHE_DIR",
        "HF_HOME",
        "TRANSFORMERS_CACHE",
        "VLLM_CACHE_ROOT",
    }
    environment = {name: os.environ.get(name) for name in sorted(environment_names)}
    for name, expected in gate.EXPECTED_RECORD_ENVIRONMENT.items():
        require(
            environment.get(name) == expected,
            f"record environment {name} drift",
        )
    require(
        environment.get("ZE_AFFINITY_MASK") == str(rank),
        f"rank {rank} requires ZE_AFFINITY_MASK={rank}",
    )
    require(
        environment.get("ONEAPI_DEVICE_SELECTOR") == "level_zero:0",
        "ONEAPI_DEVICE_SELECTOR must be level_zero:0",
    )
    require(
        environment.get("PYTHONPATH") == EXPECTED_PYTHONPATH,
        "PYTHONPATH drift",
    )
    for name in (
        "HOME",
        "SYCL_CACHE_DIR",
        "TMPDIR",
        "TMP",
        "TEMP",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "TORCHINDUCTOR_CACHE_DIR",
        "TRITON_CACHE_DIR",
        "NUMBA_CACHE_DIR",
        "HF_HOME",
        "TRANSFORMERS_CACHE",
        "VLLM_CACHE_ROOT",
        "PYTHONPYCACHEPREFIX",
    ):
        value = environment.get(name)
        require(
            isinstance(value, str)
            and value.startswith("/mnt/fast-ai/")
            and not value.startswith(("/media/", "/mnt/usb-models/")),
            f"{name} is not on local NVMe",
        )
    require(
        environment.get("PYTHONHASHSEED") == "0"
        and environment.get("PYTHONNOUSERSITE") == "1"
        and environment.get("PYTHONDONTWRITEBYTECODE") == "1"
        and environment.get("OMP_NUM_THREADS") == "1"
        and environment.get("MKL_NUM_THREADS") == "1",
        "counter fixture determinism environment drift",
    )
    require(
        environment.get("PATH")
        == "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        and environment.get("LANG") == "C.UTF-8"
        and environment.get("LC_ALL") == "C.UTF-8"
        and environment.get("HOME") is not None,
        "counter fixture hermetic base environment drift",
    )

    boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    kernel_taint = Path("/proc/sys/kernel/tainted").read_text().strip()
    require(boot_id == gate.EXPECTED_BOOT_ID, f"boot identity drift: {boot_id}")
    require(kernel_taint == "0", f"kernel is tainted: {kernel_taint}")
    require(torch.xpu.device_count() == 1, "fixture requires one visible XPU")
    torch.xpu.set_device(0)
    device_name = torch.xpu.get_device_name(0)
    require(
        device_name == gate.EXPECTED_DEVICE_NAME,
        f"visible XPU name drift: {device_name!r}",
    )

    uname = os.uname()
    return {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "uid": os.getuid(),
        "argv": list(sys.argv),
        "fixture": {
            "path": str(fixture_path),
            "sha256": sha256_file(fixture_path),
        },
        "gate": {
            "path": str(GATE_PATH),
            "sha256": EXPECTED_GATE_SHA256,
        },
        "model_config": {
            "path": str(gate.MODEL_CONFIG_PATH),
            "sha256": gate.EXPECTED_MODEL_CONFIG_SHA256,
        },
        "binaries": {
            name: {
                "path": str(gate.EXPECTED_BINARY_PATHS[name]),
                "sha256": expected,
            }
            for name, expected in gate.EXPECTED_BINARY_SHA256.items()
        },
        "torch_identity": {
            "version": EXPECTED_TORCH_VERSION,
            "files": EXPECTED_TORCH_FILES,
        },
        "environment": environment,
        "runtime": {
            "uname": {
                "sysname": uname.sysname,
                "nodename": uname.nodename,
                "release": uname.release,
                "version": uname.version,
                "machine": uname.machine,
            },
            "python": sys.version,
            "python_executable": sys.executable,
            "python_sha256": EXPECTED_PYTHON_SHA256,
            "torch": torch.__version__,
            "torch_path": str(Path(torch.__file__).resolve()),
            "boot_id": boot_id,
            "kernel_taint": kernel_taint,
            "visible_torch_xpu_count": torch.xpu.device_count(),
            "visible_torch_xpu_name": device_name,
        },
        "declared_physical_rank": rank,
        "expected_physical_device": gate.EXPECTED_PHYSICAL_DEVICES[rank],
        "mount": mount_identity(),
        "subprocesses_started": 0,
    }


def make_rank_invariant_fixture() -> tuple[torch.Tensor, torch.Tensor]:
    seed = 730_000 + EPOCH * 10
    rows = gate.cpu_bf16_random(
        (ROWS, K_DIM),
        seed=seed,
        scale=0.5,
    ).to("xpu")
    weight = gate.cpu_bf16_random(
        (N_DIM, K_DIM),
        seed=seed + 1,
        scale=gate.WEIGHT_SCALE,
    ).to("xpu")
    require(
        tuple(rows.shape) == (ROWS, K_DIM)
        and tuple(weight.shape) == (N_DIM, K_DIM)
        and rows.dtype == weight.dtype == torch.bfloat16
        and rows.is_contiguous()
        and weight.is_contiguous(),
        "counter fixture geometry/dtype/layout drift",
    )
    return rows, weight


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rank", choices=range(4), type=int, required=True)
    parser.add_argument("--arm", choices=("control", "candidate"), required=True)
    parser.add_argument(
        "--expected-fixture-sha256",
        type=sha256_argument,
        required=True,
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    fixture_path = Path(__file__).resolve()
    require(
        sha256_file(fixture_path) == args.expected_fixture_sha256,
        "fixture source SHA mismatch",
    )
    output = require_output_path(args.out)
    identity = direct_runtime_identity(args.rank, fixture_path)
    rows, weight = make_rank_invariant_fixture()
    torch.xpu.synchronize()
    input_sha256 = {
        "rows": gate.raw_sha256(rows),
        "weight": gate.raw_sha256(weight),
        "combined": gate.raw_sha256(rows, weight),
    }

    call = gate.incumbent_bmm if args.arm == "control" else gate.candidate_mm
    eviction = torch.zeros(EVICTION_ELEMENTS, dtype=torch.float32, device="xpu")
    torch.xpu.synchronize()
    output_hashes: list[str] = []
    for _index in range(CALLS):
        eviction.add_(1)
        torch.xpu.synchronize()
        value = call(rows, weight)
        torch.xpu.synchronize()
        output_hashes.append(gate.raw_sha256(value))
    require(
        len(output_hashes) == CALLS and len(set(output_hashes)) == 1,
        "selected-call output bytes are not deterministic",
    )

    payload: dict[str, Any] = {
        "format": "laguna-shared-down-mm-cold-counter-fixture-v1",
        "status": "fixture-complete",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "identity": identity,
        "rank": args.rank,
        "arm": args.arm,
        "epoch": EPOCH,
        "geometry": {
            "rows": ROWS,
            "k": K_DIM,
            "n": N_DIM,
            "dtype": "torch.bfloat16",
            "rows_contiguous": True,
            "weight_contiguous": True,
        },
        "calls": CALLS,
        "selected_gemm_calls": CALLS,
        "completion_boundary_before_each_call": True,
        "completion_boundary_after_each_call": True,
        "eviction_bytes_before_each_call": EVICTION_BYTES,
        "input_sha256": input_sha256,
        "fixture_sha256": input_sha256["combined"],
        "output_sha256": output_hashes[0],
        "all_output_sha256": output_hashes,
        "counter_execution_performed": True,
        "counter_gate_evaluated": False,
        "endpoint_preregistration_construction_authorized": False,
        "endpoint_authorized": False,
        "model_generation_performed": False,
        "payload_created": False,
        "submission_performed": False,
    }
    atomic_exclusive_json(output, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "out": str(output),
                "pid": os.getpid(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

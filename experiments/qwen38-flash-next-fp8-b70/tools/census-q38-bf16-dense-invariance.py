#!/usr/bin/env python3
"""Classify batch/row invariance of Flash-Next's real BF16 dense GEMMs.

The default action is CPU-only plan emission.  A device cell requires the
explicit ``run-cell`` subcommand and executes exactly one real-weight
family/sentinel/seed/replica tuple on one selected B70.  It never starts vLLM,
loads the complete checkpoint, or changes runtime source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any


EXTERNAL_MOUNT = Path("/mnt/usb-models")
EXTERNAL_SOURCE = "/dev/sda2"
EXTERNAL_FSTYPE = "fuseblk"
MODEL = EXTERNAL_MOUNT / "llm-models/Qwen3.8-Flash-Next-FP8"
MODEL_REVISION = "bcd9f01ddc9cff2316eb84281bebcd5b058bddce"
MODEL_INDEX_SHA256 = "0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6"
MODEL_CONFIG_SHA256 = "99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d"
VLLM_HEAD = "cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9"
KERNEL_HEAD = "e421889999bc1e5a5f11044d14548b9afdba644d"
TORCH_VERSION = "2.11.0+xpu"
TORCH_BUILD_CONFIG_SHA256 = (
    "98a0850b0ebb9d008a0dcb75c976d375ae99153c60b91281d91209fd6bbf9dd5"
)
PYTHON_VERSION = "3.12.13"
LIBSYCL = Path("/home/steve/.venvs/vllm-xpu/lib/libsycl.so.8")
LIBSYCL_SHA256 = "0336997fdfed9b2e6385e9f1cea2395eb5e130d3e5e9c943df5b0c10c1b5e57f"
LIBTORCH_XPU = Path(
    "/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib/libtorch_xpu.so"
)
LIBTORCH_XPU_SHA256 = "ee584edab22b995637c5f6ec83fc10dea5931469c86cf2ad91952bb3e1108290"
VLLM_TREE = Path("/home/steve/src/vllm-current-main")
KERNEL_TREE = Path("/home/steve/src/vllm-xpu-kernels")
EVIDENCE_BASE = Path("/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70")
EVIDENCE_ROOT = EVIDENCE_BASE / "bf16-dense-invariance-phase1-20260902-a1"
LOCK_PATH = Path("/tmp/q38-bf16-dense-invariance-phase1.lock")
CLEARANCE = EVIDENCE_BASE / "host/20260901-root-nvme-link-clearance-v1.json"
CLEARANCE_VALIDATOR = Path(__file__).with_name(
    "validate-q38-root-nvme-link-clearance-v1.py"
)
CLEARANCE_VALIDATOR_SHA256 = (
    "2293b3588a275e15a630b813d7a273e650eb64c49eaacedcf212f99fe485d5a5"
)
A28_SUMMARY = EVIDENCE_BASE / (
    "qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt28/"
    "profile-summary-recovered-v3.json"
)
A28_SUMMARY_SHA256 = "13549ec9be6d923960b0e7d654560e0a56097e8e2f226ca6b9aa660d13cf0fa1"
A28_CATALOG = (
    Path(__file__).parent.parent
    / "data/20260902-a28-bf16-dense-shape-catalog-top200.json"
)
A28_CATALOG_SHA256 = "688ac468d9114391f5411afd433a5ce52748f2120d6985d4e02bf2b467ef4969"
MODEL_RECEIPT = Path(
    "/mnt/fast-ai/llm-models/.verification/Qwen3.8-Flash-Next-FP8-20260827.json"
)
MODEL_RECEIPT_SHA256 = (
    "6ae22291119e8c8a01597bda9fe4b1fb5850912655ec188e363a88eb6de58470"
)
MODEL_TREE_METADATA_SHA256 = (
    "4a3793bd4a795ea6761b3d322200b4a1fd8300cdeb75cc127d330d513f590eb2"
)
EXPECTED_INTERPRETER = Path("/home/steve/.venvs/vllm-xpu/bin/python")
EXPECTED_PYTHON_PREFIX = Path("/home/steve/.venvs/vllm-xpu")
SAFETENSORS_VERSION = "0.7.0"
CELL_TIMEOUT_SECONDS = 600
PLAN_TIMEOUT_SECONDS = 21600
MIN_MEM_AVAILABLE_KIB = 16 * 1024 * 1024
MIN_SWAP_FREE_KIB = 6 * 1024 * 1024
SANITIZED_ENVIRONMENT = {
    "HOME": "/home/steve",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "ONEAPI_DEVICE_SELECTOR": "level_zero:0",
    "PATH": "/home/steve/.venvs/vllm-xpu/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "PYTHONNOUSERSITE": "1",
    "PYTHONSAFEPATH": "1",
    "Q38_BF16_DENSE_CENSUS_EXECUTE": "YES",
}
GEMM_ENV_PREFIXES = (
    "CCL_",
    "DNNL_",
    "I_MPI_",
    "KMP_",
    "LD_",
    "MKL_",
    "ONEAPI_",
    "OMP_",
    "Q38_",
    "SYCL_",
    "TORCH_",
    "VLLM_",
    "ZE_",
)
EXPECTED_NATIVE_LIBRARIES = {
    "sycl": ("libsycl.so.8", LIBSYCL_SHA256),
    "torch_xpu_and_onednn_provider": ("libtorch_xpu.so", LIBTORCH_XPU_SHA256),
    "onemkl_blas": (
        "libmkl_sycl_blas.so.5",
        "32b18de9a2ef6c75129ebd1b9f5c86b73eb2f845af60276ae18c7d60dcbbf13b",
    ),
    "onemkl_core": (
        "libmkl_core.so.2",
        "4dbb39b7adf44ecc400c78d5489aa54379cb0056e1ac4e0490e234b9f92c9582",
    ),
    "level_zero_loader": (
        "libze_loader.so.1.28.2",
        "0fe232b18985ae078dd546b57bc6d11bacf1030834c0544f7e3feb53ed71c1d0",
    ),
    "level_zero_gpu": (
        "libze_intel_gpu.so.1.15.38308",
        "26fa68779adb03b200a8c3001cf81e59fc9a3d63e0f38627ec0005ffce574e7a",
    ),
}

PRODUCTION_M_VALUES = (1, 2, 4, 8, 16, 32, 48, 64)
DIAGNOSTIC_M_VALUES = (128, 192, 256)
M_VALUES = PRODUCTION_M_VALUES + DIAGNOSTIC_M_VALUES
SEEDS = (2026090201, 2026090202, 2026090203)
REPLICAS = (1, 2)
REPEATS = 20
PERMUTATIONS = ("reverse", "cyclic", "random")
EXPECTED_TOTAL_GEMMS = 532

# A and B are the exact aten::mm views seen in A28: A[M,K] contiguous and
# B[K,N] a transposed row-major checkpoint weight (stride [1,K]).
FAMILIES: dict[str, dict[str, Any]] = {
    "hc_down_inject": {
        "k": 10240,
        "n": 336,
        "calls": 96,
        "sentinels": (
            {"id": "layer00-attn-r0", "layer": 0, "branch": "attn", "tp_rank": 0},
            {"id": "layer47-mlp-r3", "layer": 47, "branch": "mlp", "tp_rank": 3},
        ),
    },
    "final_hc_down": {
        "k": 10240,
        "n": 320,
        "calls": 1,
        "sentinels": (
            {"id": "final-r0", "tp_rank": 0},
            {"id": "final-r3", "tp_rank": 3},
        ),
    },
    "hc_up": {
        "k": 320,
        "n": 10240,
        "calls": 97,
        "sentinels": (
            {"id": "layer00-attn-r0", "layer": 0, "branch": "attn", "tp_rank": 0},
            {"id": "final-r3", "tp_rank": 3},
        ),
    },
    "gdn_qkvz": {
        "k": 2560,
        "n": 4096,
        "calls": 36,
        "sentinels": (
            {"id": "layer00-r0", "layer": 0, "tp_rank": 0},
            {"id": "layer46-r3", "layer": 46, "tp_rank": 3},
        ),
    },
    "full_qkv": {
        "k": 2560,
        "n": 3584,
        "calls": 12,
        "sentinels": (
            {"id": "layer03-r0", "layer": 3, "tp_rank": 0},
            {"id": "layer47-r3", "layer": 47, "tp_rank": 3},
        ),
    },
    "shared_gate_up": {
        "k": 2560,
        "n": 320,
        "calls": 48,
        "sentinels": (
            {"id": "layer00-r0", "layer": 0, "tp_rank": 0},
            {"id": "layer47-r3", "layer": 47, "tp_rank": 3},
        ),
    },
    "router": {
        "k": 2560,
        "n": 512,
        "calls": 48,
        "sentinels": (
            {"id": "layer00-r0", "layer": 0, "tp_rank": 0},
            {"id": "layer47-r3", "layer": 47, "tp_rank": 3},
        ),
    },
    "qsa_indexer": {
        "k": 2560,
        "n": 640,
        "calls": 12,
        "sentinels": (
            {"id": "layer03-r0", "layer": 3, "tp_rank": 0},
            {"id": "layer47-r3", "layer": 47, "tp_rank": 3},
        ),
    },
    "gdn_ba": {
        "k": 2560,
        "n": 24,
        "calls": 36,
        "sentinels": (
            {"id": "layer00-r0", "layer": 0, "tp_rank": 0},
            {"id": "layer46-r3", "layer": 46, "tp_rank": 3},
        ),
    },
    "shared_gate": {
        "k": 2560,
        "n": 1,
        "calls": 48,
        "sentinels": (
            {"id": "layer00-r0", "layer": 0, "tp_rank": 0},
            {"id": "layer47-r3", "layer": 47, "tp_rank": 3},
        ),
    },
    "shared_down": {
        "k": 160,
        "n": 2560,
        "calls": 48,
        "sentinels": (
            {"id": "layer00-r0", "layer": 0, "tp_rank": 0},
            {"id": "layer47-r3", "layer": 47, "tp_rank": 3},
        ),
    },
    "attn_out": {
        "k": 1536,
        "n": 2560,
        "calls": 48,
        "sentinels": (
            {"id": "gdn-layer00-r0", "layer": 0, "kind": "gdn", "tp_rank": 0},
            {"id": "full-layer47-r3", "layer": 47, "kind": "full", "tp_rank": 3},
        ),
    },
    "ple_key": {
        "k": 2560,
        "n": 10240,
        "calls": 1,
        "sentinels": (
            {"id": "ple-key-r0", "tp_rank": 0},
            {"id": "ple-key-r3", "tp_rank": 3},
        ),
    },
    "ple_value": {
        "k": 2560,
        "n": 2560,
        "calls": 1,
        "sentinels": (
            {"id": "ple-value-r0", "tp_rank": 0},
            {"id": "ple-value-r3", "tp_rank": 3},
        ),
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def catalog_summary() -> dict[str, Any]:
    shapes = []
    for family, spec in FAMILIES.items():
        shapes.append(
            {
                "family": family,
                "a": ["M", spec["k"]],
                "b": [spec["k"], spec["n"]],
                "a_stride": [spec["k"], 1],
                "b_stride": [1, spec["k"]],
                "calls_per_token": spec["calls"],
                "sentinels": list(spec["sentinels"]),
            }
        )
    return {
        "families": shapes,
        "family_count": len(shapes),
        "calls_per_token": sum(item["calls_per_token"] for item in shapes),
    }


def validate_catalog() -> None:
    summary = catalog_summary()
    if summary["family_count"] != 14:
        raise ValueError("the complete A28 catalogue must contain exactly 14 families")
    if summary["calls_per_token"] != EXPECTED_TOTAL_GEMMS:
        raise ValueError(
            f"dense multiplicities sum to {summary['calls_per_token']}, not 532"
        )
    if set(PRODUCTION_M_VALUES) & set(DIAGNOSTIC_M_VALUES):
        raise ValueError("production and diagnostic M sets overlap")
    if max(PRODUCTION_M_VALUES) != 64 or min(DIAGNOSTIC_M_VALUES) <= 64:
        raise ValueError("M>64 must remain diagnostic-only")
    for family, spec in FAMILIES.items():
        if spec["k"] <= 0 or spec["n"] <= 0 or spec["calls"] <= 0:
            raise ValueError(f"invalid catalogue dimensions for {family}")
        if len(spec["sentinels"]) != 2:
            raise ValueError(f"{family} must have two Phase-1 sentinels")
        if len({item["id"] for item in spec["sentinels"]}) != 2:
            raise ValueError(f"duplicate sentinel id for {family}")
    if sha256(A28_CATALOG) != A28_CATALOG_SHA256:
        raise ValueError("expanded A28 top-200 catalog identity drift")
    derived = json.loads(A28_CATALOG.read_text(encoding="utf-8"))
    observed = sorted(
        (row["k"], row["n"], row["calls_per_token"])
        for row in derived.get("families", [])
    )
    expected = sorted(
        (spec["k"], spec["n"], spec["calls"]) for spec in FAMILIES.values()
    )
    if observed != expected or derived.get("calls_per_token") != EXPECTED_TOTAL_GEMMS:
        raise ValueError("runtime catalog does not match expanded A28 top-200 artifact")


def phase1_plan() -> list[dict[str, Any]]:
    validate_catalog()
    cells = []
    for family, spec in FAMILIES.items():
        for sentinel in spec["sentinels"]:
            for seed in SEEDS:
                for replica in REPLICAS:
                    cells.append(
                        {
                            "family": family,
                            "sentinel": sentinel["id"],
                            "tp_rank": sentinel["tp_rank"],
                            "seed": seed,
                            "replica": replica,
                            "m_values": list(M_VALUES),
                        }
                    )
    return cells


def cell_filename(cell: dict[str, Any]) -> str:
    return (
        f"{cell['family']}--{cell['sentinel']}--seed{cell['seed']}--"
        f"replica{cell['replica']}.json"
    )


def resolve_sentinel(family: str, sentinel_id: str) -> dict[str, Any]:
    if family not in FAMILIES:
        raise ValueError(f"unknown family: {family}")
    matches = [s for s in FAMILIES[family]["sentinels"] if s["id"] == sentinel_id]
    if len(matches) != 1:
        raise ValueError(f"unknown sentinel for {family}: {sentinel_id}")
    return dict(matches[0])


def inverse_permutation(permutation: list[int]) -> list[int]:
    if sorted(permutation) != list(range(len(permutation))):
        raise ValueError("not a permutation")
    inverse = [0] * len(permutation)
    for index, source in enumerate(permutation):
        inverse[source] = index
    return inverse


def _git_head(path: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _git_relevant_status(path: Path) -> str:
    # These source trees are identity/provenance inputs, not import paths. Reject
    # every tracked edit; untracked build-source/vendor trees are excluded because
    # the executable contract hashes the actual mapped runtime libraries instead.
    return subprocess.run(
        ["git", "-C", str(path), "status", "--porcelain", "--untracked-files=no"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def sanitized_subprocess_environment() -> dict[str, str]:
    return dict(SANITIZED_ENVIRONMENT)


def verify_worker_environment(
    environment: dict[str, str] | None = None,
) -> dict[str, str]:
    environment = dict(os.environ if environment is None else environment)
    relevant = {
        key: value
        for key, value in environment.items()
        if key in SANITIZED_ENVIRONMENT or key.startswith(GEMM_ENV_PREFIXES)
    }
    if relevant != SANITIZED_ENVIRONMENT:
        raise RuntimeError(
            f"GEMM-relevant environment is not sanitized: {sorted(relevant)}"
        )
    return relevant


def loaded_native_library_contract(maps_text: str | None = None) -> dict[str, Any]:
    if maps_text is None:
        maps_text = Path("/proc/self/maps").read_text(encoding="utf-8")
    mapped = {
        Path(line.split()[-1]).resolve()
        for line in maps_text.splitlines()
        if "/" in line.split()[-1] and not line.split()[-1].endswith(" (deleted)")
    }
    result = {}
    for role, (basename, expected_sha) in EXPECTED_NATIVE_LIBRARIES.items():
        matches = sorted(path for path in mapped if path.name == basename)
        if len(matches) != 1:
            raise RuntimeError(f"ambiguous or absent {role} mapping: {matches}")
        actual_sha = sha256(matches[0])
        if actual_sha != expected_sha:
            raise RuntimeError(f"loaded {role} identity drift: {actual_sha}")
        result[role] = {"path": str(matches[0]), "sha256": actual_sha}
    standalone_dnnl = sorted(
        path for path in mapped if path.name.startswith("libdnnl.so")
    )
    if standalone_dnnl:
        raise RuntimeError(
            f"unexpected standalone oneDNN provider is mapped: {standalone_dnnl}"
        )
    result["onednn_provider"] = {
        "kind": "torch_xpu_integrated",
        "path": result["torch_xpu_and_onednn_provider"]["path"],
        "sha256": result["torch_xpu_and_onednn_provider"]["sha256"],
    }
    return result


def parse_findmnt(payload: str) -> dict[str, str]:
    rows = json.loads(payload).get("filesystems", [])
    if len(rows) != 1:
        raise RuntimeError("external checkpoint must resolve to exactly one mount")
    row = {str(key).lower(): str(value) for key, value in rows[0].items()}
    observed = {key: row.get(key, "") for key in ("source", "fstype", "target")}
    expected = {
        "source": EXTERNAL_SOURCE,
        "fstype": EXTERNAL_FSTYPE,
        "target": str(EXTERNAL_MOUNT),
    }
    if observed != expected:
        raise RuntimeError(f"external checkpoint mount drift: {observed} != {expected}")
    return observed


def verify_external_mount() -> dict[str, str]:
    if MODEL.is_symlink() or not MODEL.is_dir():
        raise RuntimeError(f"external checkpoint is absent or symlinked: {MODEL}")
    payload = subprocess.run(
        ["findmnt", "-J", "-o", "SOURCE,FSTYPE,TARGET", "--target", str(MODEL)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout
    return parse_findmnt(payload)


def read_meminfo(text: str | None = None) -> dict[str, int]:
    if text is None:
        text = Path("/proc/meminfo").read_text(encoding="utf-8")
    wanted = {"MemAvailable", "SwapFree"}
    values = {}
    for line in text.splitlines():
        fields = line.split()
        key = fields[0].rstrip(":") if fields else ""
        if key in wanted and len(fields) >= 2:
            values[key] = int(fields[1])
    if set(values) != wanted:
        raise RuntimeError("MemAvailable/SwapFree are unavailable")
    return values


def count_aer_events(text: str) -> int:
    markers = ("aer: corrected", "pcie bus error")
    return sum(
        any(marker in line.lower() for marker in markers) for line in text.splitlines()
    )


def validate_admission(*, include_smart: bool = True) -> dict[str, Any]:
    """Fail before evidence creation or device imports unless this boot is cleared."""
    mount = verify_external_mount()
    if sha256(CLEARANCE_VALIDATOR) != CLEARANCE_VALIDATOR_SHA256:
        raise RuntimeError("current-boot clearance validator identity drift")
    clearance_run = subprocess.run(
        [
            str(EXPECTED_INTERPRETER),
            str(CLEARANCE_VALIDATOR),
            "--clearance-json",
            str(CLEARANCE),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    clearance = json.loads(clearance_run.stdout)
    if clearance.get("status") != "pass":
        raise RuntimeError("current-boot NVMe clearance did not pass")
    memory = read_meminfo()
    if memory["MemAvailable"] < MIN_MEM_AVAILABLE_KIB:
        raise RuntimeError("MemAvailable is below the bounded census floor")
    if memory["SwapFree"] < MIN_SWAP_FREE_KIB:
        raise RuntimeError("SwapFree is below the bounded census floor")
    discovery = subprocess.run(
        ["xpu-smi", "discovery", "-j"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    devices = json.loads(discovery.stdout).get("device_list", [])
    if len(devices) != 4:
        raise RuntimeError(f"expected exact four-B70 topology, got {len(devices)}")
    journal = subprocess.run(
        ["journalctl", "-k", "-b", "--no-pager"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    aer_events = count_aer_events(journal.stdout)
    smart = None
    if include_smart:
        smart_run = subprocess.run(
            ["nvme", "smart-log", "-o", "json", "/dev/nvme0"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        smart = json.loads(smart_run.stdout)
        if (
            int(smart.get("critical_warning", -1)) != 0
            or int(smart.get("media_errors", -1)) != 0
        ):
            raise RuntimeError("root NVMe SMART is not clean")
    return {
        "mount": mount,
        "clearance": clearance,
        "memory_kib": memory,
        "aer_event_count": aer_events,
        "xpu_device_count": len(devices),
        "smart": smart,
    }


def verify_static_identity() -> dict[str, Any]:
    required = {
        MODEL / "model.safetensors.index.json": MODEL_INDEX_SHA256,
        MODEL / "config.json": MODEL_CONFIG_SHA256,
        LIBSYCL: LIBSYCL_SHA256,
        LIBTORCH_XPU: LIBTORCH_XPU_SHA256,
        A28_SUMMARY: A28_SUMMARY_SHA256,
        A28_CATALOG: A28_CATALOG_SHA256,
        MODEL_RECEIPT: MODEL_RECEIPT_SHA256,
    }
    observed = {}
    for path, expected in required.items():
        actual = sha256(path)
        if actual != expected:
            raise RuntimeError(f"identity mismatch for {path}: {actual} != {expected}")
        observed[str(path)] = actual
    heads = {"vllm": _git_head(VLLM_TREE), "xpu_kernels": _git_head(KERNEL_TREE)}
    if heads != {"vllm": VLLM_HEAD, "xpu_kernels": KERNEL_HEAD}:
        raise RuntimeError(f"source identity drift: {heads}")
    dirty = {
        "vllm": _git_relevant_status(VLLM_TREE),
        "xpu_kernels": _git_relevant_status(KERNEL_TREE),
    }
    if any(dirty.values()):
        raise RuntimeError(f"relevant source tree is dirty: {dirty}")
    if Path(sys.executable).resolve() != EXPECTED_INTERPRETER.resolve():
        raise RuntimeError(f"interpreter identity drift: {sys.executable}")
    if Path(sys.prefix).resolve() != EXPECTED_PYTHON_PREFIX.resolve():
        raise RuntimeError(f"Python environment prefix drift: {sys.prefix}")
    if sys.version.split()[0] != PYTHON_VERSION:
        raise RuntimeError(f"Python identity drift: {sys.version.split()[0]}")
    return {
        "files": observed,
        "heads": heads,
        "tracked_source_clean": True,
        "python": PYTHON_VERSION,
        "interpreter": str(EXPECTED_INTERPRETER),
        "python_prefix": str(EXPECTED_PYTHON_PREFIX),
        "a28_summary_sha256": A28_SUMMARY_SHA256,
        "a28_catalog_sha256": A28_CATALOG_SHA256,
        "model_receipt_sha256": MODEL_RECEIPT_SHA256,
        "model_tree_metadata_sha256": MODEL_TREE_METADATA_SHA256,
    }


def refuse_active_accelerator_owner() -> None:
    needles = (
        b"vllm serve",
        b"VLLM::Worker",
        b"VLLM::Engine",
        b"qwen38-flash-next-fp8-tp",
    )
    owners = []
    render_owners = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) in {os.getpid(), os.getppid()}:
            continue
        try:
            command = (proc / "cmdline").read_bytes().replace(b"\0", b" ")
            comm = (proc / "comm").read_bytes()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if any(needle in command + b" " + comm for needle in needles):
            owners.append(int(proc.name))
        try:
            for descriptor in (proc / "fd").iterdir():
                try:
                    target = os.readlink(descriptor)
                except (FileNotFoundError, PermissionError, ProcessLookupError):
                    continue
                if target.startswith("/dev/dri/renderD"):
                    render_owners.append((int(proc.name), target))
                    break
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    if owners:
        raise RuntimeError(f"active model/server process detected: {owners}")
    if render_owners:
        raise RuntimeError(f"another process owns a render node: {render_owners}")


def acquire_component_lock():
    import fcntl

    handle = LOCK_PATH.open("w", encoding="utf-8")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        handle.close()
        raise RuntimeError(
            "another BF16 dense census process holds the lock"
        ) from error
    return handle


def source_tensor_names(family: str, sentinel: dict[str, Any]) -> list[str]:
    layer = sentinel.get("layer")
    branch = sentinel.get("branch")
    prefix = f"model.language_model.layers.{layer}"
    if family == "hc_down_inject":
        base = f"{prefix}.{branch}_hyper_connection"
        return [
            f"{base}.input_mix_weight_down.weight",
            f"{base}.block_inject_weight.weight",
        ]
    if family == "hc_up":
        base = (
            "model.language_model.hyper_connection_mixer"
            if layer is None
            else f"{prefix}.{branch}_hyper_connection"
        )
        return [f"{base}.input_mix_weight_up.weight"]
    if family == "final_hc_down":
        return [
            "model.language_model.hyper_connection_mixer.input_mix_weight_down.weight"
        ]
    if family == "gdn_qkvz":
        return [
            f"{prefix}.linear_attn.in_proj_qkv.weight",
            f"{prefix}.linear_attn.in_proj_z.weight",
        ]
    if family == "full_qkv":
        return [f"{prefix}.self_attn.{name}_proj.weight" for name in ("q", "k", "v")]
    if family == "shared_gate_up":
        return [
            f"{prefix}.mlp.shared_expert.{name}_proj.weight" for name in ("gate", "up")
        ]
    if family == "router":
        return [f"{prefix}.mlp.gate.weight"]
    if family == "qsa_indexer":
        return [f"{prefix}.self_attn.indexer.index_qk_proj.weight"]
    if family == "gdn_ba":
        return [f"{prefix}.linear_attn.in_proj_{name}.weight" for name in ("b", "a")]
    if family == "shared_gate":
        return [f"{prefix}.mlp.shared_expert_gate.weight"]
    if family == "shared_down":
        return [f"{prefix}.mlp.shared_expert.down_proj.weight"]
    if family == "attn_out":
        arm = (
            "linear_attn.out_proj" if sentinel["kind"] == "gdn" else "self_attn.o_proj"
        )
        return [f"{prefix}.{arm}.weight"]
    if family in {"ple_key", "ple_value"}:
        arm = "key_proj" if family == "ple_key" else "value_proj"
        return [f"model.language_model.layers.1.ple.{arm}.weight"]
    raise ValueError(f"no source tensors for {family}")


def build_shard_contract() -> dict[str, Any]:
    index_path = MODEL / "model.safetensors.index.json"
    weight_map = json.loads(index_path.read_text(encoding="utf-8"))["weight_map"]
    tensor_names: set[str] = set()
    for family, spec in FAMILIES.items():
        for sentinel in spec["sentinels"]:
            tensor_names.update(source_tensor_names(family, sentinel))
    missing = sorted(tensor_names - set(weight_map))
    if missing:
        raise RuntimeError(f"catalog source tensors absent from checkpoint: {missing}")
    shard_names = sorted({weight_map[name] for name in tensor_names})
    receipt = json.loads(MODEL_RECEIPT.read_text(encoding="utf-8"))
    contract = receipt.get("contract", {})
    if (
        contract.get("tree_metadata_sha256") != MODEL_TREE_METADATA_SHA256
        or contract.get("revision") != MODEL_REVISION
        or contract.get("index_sha256") != MODEL_INDEX_SHA256
    ):
        raise RuntimeError("historical model verifier receipt identity drift")
    verified_files = {row["path"]: row for row in receipt.get("files", [])}
    shards = {}
    for name in shard_names:
        path = MODEL / name
        stat = path.stat()
        expected = verified_files.get(name, {})
        if expected.get("digest_kind") != "lfs_sha256":
            raise RuntimeError(f"shard lacks a preregistered LFS SHA: {name}")
        actual_sha = sha256(path)
        if stat.st_size != expected.get("size") or actual_sha != expected.get("digest"):
            raise RuntimeError(
                f"external checkpoint shard differs from verified receipt: {name}"
            )
        shards[name] = {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": actual_sha,
        }
    return {
        "schema": "neural.download.qwen38-flash-next.bf16-dense-shards.v1",
        "model_index_sha256": MODEL_INDEX_SHA256,
        "model_receipt_sha256": MODEL_RECEIPT_SHA256,
        "tree_metadata_sha256": MODEL_TREE_METADATA_SHA256,
        "source_tensors": sorted(tensor_names),
        "shards": shards,
    }


def validate_shard_contract(value: dict[str, Any]) -> str:
    if value.get("model_index_sha256") != MODEL_INDEX_SHA256:
        raise RuntimeError("shard contract model index drift")
    if value.get("model_receipt_sha256") != MODEL_RECEIPT_SHA256:
        raise RuntimeError("shard contract verifier-receipt drift")
    if value.get("tree_metadata_sha256") != MODEL_TREE_METADATA_SHA256:
        raise RuntimeError("shard contract tree-metadata drift")
    if sha256(MODEL_RECEIPT) != MODEL_RECEIPT_SHA256:
        raise RuntimeError("historical model verifier receipt file drift")
    receipt = json.loads(MODEL_RECEIPT.read_text(encoding="utf-8"))
    verified_files = {row["path"]: row for row in receipt.get("files", [])}
    for name, expected in value.get("shards", {}).items():
        stat = (MODEL / name).stat()
        observed = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
        if observed != {key: expected[key] for key in observed}:
            raise RuntimeError(f"checkpoint shard stat drift: {name}")
        if len(expected.get("sha256", "")) != 64:
            raise RuntimeError(f"checkpoint shard SHA is invalid: {name}")
        preregistered = verified_files.get(name, {})
        if (
            preregistered.get("digest_kind") != "lfs_sha256"
            or preregistered.get("digest") != expected["sha256"]
            or preregistered.get("size") != expected["size"]
        ):
            raise RuntimeError(
                f"shard contract is not anchored to verified receipt: {name}"
            )
    return canonical_sha256(value)


def _checkpoint_reader():
    import torch
    from safetensors import safe_open

    index = json.loads((MODEL / "model.safetensors.index.json").read_text())[
        "weight_map"
    ]

    def read(name: str):
        if name not in index:
            raise KeyError(f"checkpoint tensor is absent: {name}")
        shard = MODEL / index[name]
        with safe_open(shard, framework="pt", device="cpu") as handle:
            tensor = handle.get_tensor(name).contiguous()
        if tensor.dtype != torch.bfloat16:
            raise RuntimeError(f"{name} is not BF16: {tensor.dtype}")
        return tensor, shard.name

    return read


def load_weight(family: str, sentinel: dict[str, Any]):
    """Reconstruct the exact TP4-local row-major runtime weight [N,K]."""
    import torch

    read = _checkpoint_reader()
    rank = int(sentinel["tp_rank"])
    layer = sentinel.get("layer")
    shards: set[str] = set()
    tensors: set[str] = set()

    def get(name: str):
        tensor, shard = read(name)
        shards.add(shard)
        tensors.add(name)
        return tensor

    if family == "hc_down_inject":
        branch = sentinel["branch"]
        prefix = f"model.language_model.layers.{layer}.{branch}_hyper_connection"
        down = get(f"{prefix}.input_mix_weight_down.weight")
        inject = get(f"{prefix}.block_inject_weight.weight")
        padding = torch.zeros((12, 10240), dtype=torch.bfloat16)
        weight = torch.cat((down, inject, padding), dim=0)
    elif family == "hc_up":
        if layer is None:
            name = (
                "model.language_model.hyper_connection_mixer.input_mix_weight_up.weight"
            )
        else:
            branch = sentinel["branch"]
            name = (
                f"model.language_model.layers.{layer}.{branch}_hyper_connection."
                "input_mix_weight_up.weight"
            )
        weight = get(name)
    elif family == "final_hc_down":
        weight = get(
            "model.language_model.hyper_connection_mixer.input_mix_weight_down.weight"
        )
    elif family == "gdn_qkvz":
        prefix = f"model.language_model.layers.{layer}.linear_attn"
        qkv = get(f"{prefix}.in_proj_qkv.weight")
        z = get(f"{prefix}.in_proj_z.weight")
        weight = torch.cat(
            (
                qkv[rank * 512 : (rank + 1) * 512],
                qkv[2048 + rank * 512 : 2048 + (rank + 1) * 512],
                qkv[4096 + rank * 1536 : 4096 + (rank + 1) * 1536],
                z[rank * 1536 : (rank + 1) * 1536],
            ),
            dim=0,
        )
    elif family == "full_qkv":
        prefix = f"model.language_model.layers.{layer}.self_attn"
        q = get(f"{prefix}.q_proj.weight")
        k = get(f"{prefix}.k_proj.weight")
        v = get(f"{prefix}.v_proj.weight")
        kv = rank // 2
        weight = torch.cat(
            (
                q[rank * 3072 : (rank + 1) * 3072],
                k[kv * 256 : (kv + 1) * 256],
                v[kv * 256 : (kv + 1) * 256],
            ),
            dim=0,
        )
    elif family == "shared_gate_up":
        prefix = f"model.language_model.layers.{layer}.mlp.shared_expert"
        gate = get(f"{prefix}.gate_proj.weight")
        up = get(f"{prefix}.up_proj.weight")
        weight = torch.cat(
            (
                gate[rank * 160 : (rank + 1) * 160],
                up[rank * 160 : (rank + 1) * 160],
            ),
            dim=0,
        )
    elif family == "router":
        weight = get(f"model.language_model.layers.{layer}.mlp.gate.weight")
    elif family == "qsa_indexer":
        weight = get(
            f"model.language_model.layers.{layer}.self_attn.indexer.index_qk_proj.weight"
        )
    elif family == "gdn_ba":
        prefix = f"model.language_model.layers.{layer}.linear_attn"
        b = get(f"{prefix}.in_proj_b.weight")
        a = get(f"{prefix}.in_proj_a.weight")
        weight = torch.cat(
            (
                b[rank * 12 : (rank + 1) * 12],
                a[rank * 12 : (rank + 1) * 12],
            ),
            dim=0,
        )
    elif family == "shared_gate":
        weight = get(
            f"model.language_model.layers.{layer}.mlp.shared_expert_gate.weight"
        )
    elif family == "shared_down":
        weight = get(
            f"model.language_model.layers.{layer}.mlp.shared_expert.down_proj.weight"
        )[:, rank * 160 : (rank + 1) * 160]
    elif family == "attn_out":
        if sentinel["kind"] == "gdn":
            name = f"model.language_model.layers.{layer}.linear_attn.out_proj.weight"
        else:
            name = f"model.language_model.layers.{layer}.self_attn.o_proj.weight"
        weight = get(name)[:, rank * 1536 : (rank + 1) * 1536]
    elif family == "ple_key":
        weight = get("model.language_model.layers.1.ple.key_proj.weight")
    elif family == "ple_value":
        weight = get("model.language_model.layers.1.ple.value_proj.weight")
    else:
        raise ValueError(f"no weight loader for {family}")

    weight = weight.contiguous()
    expected = (FAMILIES[family]["n"], FAMILIES[family]["k"])
    if tuple(weight.shape) != expected:
        raise RuntimeError(f"{family} weight shape {tuple(weight.shape)} != {expected}")
    expected_tensors = sorted(source_tensor_names(family, sentinel))
    if sorted(tensors) != expected_tensors:
        raise RuntimeError(f"{family} source tensor identity drift")
    return weight, sorted(shards), expected_tensors


def tensor_sha256(tensor, *, chunk_bytes: int = 32 * 1024 * 1024) -> str:
    """Hash tensors in bounded chunks, including BF16 tensors on XPU."""
    raw = tensor.detach().contiguous().view(-1).view(dtype=__import__("torch").uint8)
    digest = hashlib.sha256()
    for start in range(0, raw.numel(), chunk_bytes):
        chunk = raw[start : start + chunk_bytes].cpu().numpy().tobytes()
        digest.update(chunk)
    return digest.hexdigest()


def permutation_indices(kind: str, m: int, seed: int):
    import torch

    if kind == "reverse":
        return torch.arange(m - 1, -1, -1, dtype=torch.long)
    if kind == "cyclic":
        return torch.roll(torch.arange(m, dtype=torch.long), shifts=1)
    if kind == "random":
        generator = torch.Generator(device="cpu").manual_seed(seed + m * 1009)
        return torch.randperm(m, generator=generator)
    raise ValueError(f"unknown permutation: {kind}")


def atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite evidence: {path}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def summarize_evidence(root: Path) -> dict[str, Any]:
    plan = phase1_plan()
    failures = []
    exact = 0
    records: dict[tuple[str, str, int, int], dict[str, Any]] = {}
    for cell in plan:
        path = root / "cells" / cell_filename(cell)
        if not path.is_file():
            raise RuntimeError(f"planned cell evidence is missing: {path}")
        record = json.loads(path.read_text(encoding="utf-8"))
        identity = record.get("identity", {})
        observed = {
            "family": identity.get("family"),
            "sentinel": identity.get("sentinel", {}).get("id"),
            "seed": identity.get("seed"),
            "replica": identity.get("replica"),
        }
        expected = {key: cell[key] for key in observed}
        if observed != expected:
            raise RuntimeError(
                f"cell identity drift in {path}: {observed} != {expected}"
            )
        if record.get("all_cells_exact") is True:
            exact += 1
        else:
            failures.append({**expected, "path": str(path)})
        records[(cell["family"], cell["sentinel"], cell["seed"], cell["replica"])] = (
            record
        )
    cross_process_failures = []
    weight_hashes: dict[tuple[str, str], set[str]] = {}
    for family, spec in FAMILIES.items():
        for sentinel in spec["sentinels"]:
            key2 = (family, sentinel["id"])
            weight_hashes[key2] = set()
            for seed in SEEDS:
                left = records[(family, sentinel["id"], seed, 1)]
                right = records[(family, sentinel["id"], seed, 2)]
                for record in (left, right):
                    identity = record.get("identity", {})
                    weight_hashes[key2].add(identity.get("weight_sha256"))
                comparable = {
                    "input_sha256": left.get("identity", {}).get("input_sha256"),
                    "weight_sha256": left.get("identity", {}).get("weight_sha256"),
                    "singleton_authority_sha256": left.get("identity", {}).get(
                        "singleton_authority_sha256"
                    ),
                    "results_sha256": canonical_sha256(left.get("results")),
                }
                peer = {
                    "input_sha256": right.get("identity", {}).get("input_sha256"),
                    "weight_sha256": right.get("identity", {}).get("weight_sha256"),
                    "singleton_authority_sha256": right.get("identity", {}).get(
                        "singleton_authority_sha256"
                    ),
                    "results_sha256": canonical_sha256(right.get("results")),
                }
                if None in comparable.values() or comparable != peer:
                    cross_process_failures.append(
                        {"family": family, "sentinel": sentinel["id"], "seed": seed}
                    )
    weight_failures = [
        {"family": family, "sentinel": sentinel, "unique_weight_hashes": sorted(hashes)}
        for (family, sentinel), hashes in weight_hashes.items()
        if len(hashes) != 1 or None in hashes
    ]
    all_exact = not failures and not cross_process_failures and not weight_failures
    return {
        "schema": "neural.download.qwen38-flash-next.bf16-dense-invariance-summary.v1",
        "status": "complete",
        "classification": "component_only_phase1_census",
        "planned_processes": len(plan),
        "completed_processes": len(plan),
        "exact_processes": exact,
        "noninvariant_processes": failures,
        "cross_process_failures": cross_process_failures,
        "reconstructed_weight_failures": weight_failures,
        "all_phase1_cells_exact": all_exact,
        "production_m_values": list(PRODUCTION_M_VALUES),
        "diagnostic_only_m_values": list(DIAGNOSTIC_M_VALUES),
        "endpoint_or_speed_credit": False,
        "next": (
            "Expand only hot or noninvariant families to every integer M=1..64; "
            "do not change endpoint dispatch from Phase-1 evidence alone."
        ),
    }


def run_plan() -> Path:
    if os.environ.get("Q38_BF16_DENSE_CENSUS_EXECUTE") != "YES":
        raise RuntimeError("set Q38_BF16_DENSE_CENSUS_EXECUTE=YES to run the plan")
    initial_health = validate_admission()
    verify_static_identity()
    refuse_active_accelerator_owner()
    root = EVIDENCE_ROOT.resolve()
    if not root.is_relative_to(EVIDENCE_BASE.resolve()):
        raise RuntimeError("evidence root escaped the frozen evidence base")
    root.mkdir(parents=True, exist_ok=False)
    (root / "cells").mkdir()
    shard_contract = build_shard_contract()
    shard_contract_path = root / "shard-contract.json"
    atomic_write_json(shard_contract_path, shard_contract)
    shard_contract_sha = validate_shard_contract(shard_contract)
    tool = Path(__file__).resolve()
    deadline = time.monotonic() + PLAN_TIMEOUT_SECONDS
    for cell in phase1_plan():
        if time.monotonic() >= deadline:
            raise TimeoutError("Phase-1 plan exceeded its frozen total timeout")
        before = validate_admission()
        if before["aer_event_count"] != initial_health["aer_event_count"]:
            raise RuntimeError("new AER event observed before a cell")
        output = root / "cells" / cell_filename(cell)
        command = [
            sys.executable,
            str(tool),
            "run-cell",
            "--family",
            cell["family"],
            "--sentinel",
            cell["sentinel"],
            "--seed",
            str(cell["seed"]),
            "--replica",
            str(cell["replica"]),
            "--output",
            str(output),
            "--shard-contract",
            str(shard_contract_path),
            "--shard-contract-sha256",
            shard_contract_sha,
        ]
        subprocess.run(
            command,
            check=True,
            env=sanitized_subprocess_environment(),
            timeout=min(CELL_TIMEOUT_SECONDS, max(1, int(deadline - time.monotonic()))),
        )
        after = validate_admission()
        if after["aer_event_count"] != before["aer_event_count"]:
            raise RuntimeError("new AER event observed during a cell")
        validate_shard_contract(shard_contract)
    summary_path = root / "summary.json"
    summary = summarize_evidence(root)
    summary["initial_health"] = initial_health
    summary["final_health"] = validate_admission()
    summary["shard_contract_sha256"] = shard_contract_sha
    atomic_write_json(summary_path, summary)
    return summary_path


def run_cell(args: argparse.Namespace) -> dict[str, Any]:
    if os.environ.get("Q38_BF16_DENSE_CENSUS_EXECUTE") != "YES":
        raise RuntimeError("set Q38_BF16_DENSE_CENSUS_EXECUTE=YES for a device cell")
    verify_worker_environment()
    if os.environ.get("ONEAPI_DEVICE_SELECTOR") != "level_zero:0":
        raise RuntimeError("ONEAPI_DEVICE_SELECTOR must be exactly level_zero:0")
    if (
        os.environ.get("PYTHONNOUSERSITE") != "1"
        or os.environ.get("PYTHONSAFEPATH") != "1"
    ):
        raise RuntimeError("isolated Python environment is required")
    if args.seed not in SEEDS or args.replica not in REPLICAS:
        raise ValueError("seed/replica is outside the frozen Phase-1 plan")
    signal.alarm(CELL_TIMEOUT_SECONDS)
    admission = validate_admission()
    if args.shard_contract is None or args.shard_contract_sha256 is None:
        raise RuntimeError("a driver-created shard contract is required")
    if args.shard_contract.is_symlink() or not args.shard_contract.is_file():
        raise RuntimeError("shard contract is absent or symlinked")
    shard_contract = json.loads(args.shard_contract.read_text(encoding="utf-8"))
    contract_sha = validate_shard_contract(shard_contract)
    if contract_sha != args.shard_contract_sha256:
        raise RuntimeError("shard contract canonical SHA drift")
    _component_lock = acquire_component_lock()
    identity = verify_static_identity()
    refuse_active_accelerator_owner()

    import torch
    import torch.nn.functional as F
    import safetensors

    if torch.__version__ != TORCH_VERSION:
        raise RuntimeError(f"Torch identity drift: {torch.__version__}")
    torch_build_config_sha = hashlib.sha256(
        torch.__config__.show().encode()
    ).hexdigest()
    if torch_build_config_sha != TORCH_BUILD_CONFIG_SHA256:
        raise RuntimeError(
            f"Torch/oneDNN build identity drift: {torch_build_config_sha}"
        )
    if safetensors.__version__ != SAFETENSORS_VERSION:
        raise RuntimeError(f"Safetensors identity drift: {safetensors.__version__}")
    if not torch.xpu.is_available() or torch.xpu.device_count() < 1:
        raise RuntimeError("no selected XPU is available")
    sentinel = resolve_sentinel(args.family, args.sentinel)
    weight_cpu, shards, source_tensors = load_weight(args.family, sentinel)
    if not set(shards).issubset(shard_contract["shards"]):
        raise RuntimeError("selected checkpoint shard is outside the frozen contract")
    generator = torch.Generator(device="cpu").manual_seed(args.seed)
    input_cpu = (
        torch.randn((max(M_VALUES), FAMILIES[args.family]["k"]), generator=generator)
        .mul_(0.01)
        .to(torch.bfloat16)
    )
    device = torch.device("xpu:0")
    weight = weight_cpu.to(device)
    inputs = input_cpu.to(device)
    torch.xpu.synchronize()
    input_hash_before = tensor_sha256(inputs)
    weight_hash_before = tensor_sha256(weight)

    # Singleton output is the row-isolation authority.  Cache it once per row
    # and reuse it for every M instead of rerunning 256 M1 calls per M cell.
    singleton_hashes = []
    singleton = None
    for _ in range(2):
        singleton_rows = [
            F.linear(inputs[row : row + 1], weight) for row in range(max(M_VALUES))
        ]
        candidate = torch.cat(singleton_rows, dim=0)
        torch.xpu.synchronize()
        singleton_hashes.append(tensor_sha256(candidate))
        if singleton is None:
            singleton = candidate
    if len(set(singleton_hashes)) != 1:
        raise RuntimeError("singleton authority is not repeat-qualified")
    assert singleton is not None
    if singleton.dtype != torch.bfloat16 or tuple(singleton.shape) != (
        max(M_VALUES),
        FAMILIES[args.family]["n"],
    ):
        raise RuntimeError("singleton authority returned an invalid shape or dtype")
    singleton_finite = bool(torch.isfinite(singleton).all().item())

    m_results = []
    for m in M_VALUES:
        output = F.linear(inputs[:m], weight)
        torch.xpu.synchronize()
        output_finite = bool(torch.isfinite(output).all().item())
        if output.dtype != torch.bfloat16 or tuple(output.shape) != (
            m,
            FAMILIES[args.family]["n"],
        ):
            raise RuntimeError(f"M={m} returned an invalid shape or dtype")
        output_hash = tensor_sha256(output)
        repeat_hashes = []
        for _ in range(REPEATS):
            repeated = F.linear(inputs[:m], weight)
            torch.xpu.synchronize()
            repeat_hashes.append(tensor_sha256(repeated))
        row_authority = singleton[:m]
        row_exact = bool(torch.equal(output, row_authority))
        permutations = {}
        for kind in PERMUTATIONS:
            order_cpu = permutation_indices(kind, m, args.seed)
            order = order_cpu.to(device)
            inverse = torch.tensor(
                inverse_permutation(order_cpu.tolist()), dtype=torch.long, device=device
            )
            permuted = F.linear(inputs[:m].index_select(0, order), weight)
            restored = permuted.index_select(0, inverse)
            torch.xpu.synchronize()
            permutations[kind] = {
                "exact": bool(torch.equal(restored, output)),
                "restored_sha256": tensor_sha256(restored),
            }
        m_results.append(
            {
                "m": m,
                "scope": "production" if m <= 64 else "diagnostic_only",
                "output_sha256": output_hash,
                "unique_repeat_sha256": sorted(set(repeat_hashes)),
                "same_m_repeatable": len(set(repeat_hashes)) == 1
                and repeat_hashes[0] == output_hash,
                "finite": output_finite,
                "all_rows_match_m1_authority": row_exact,
                "permutations": permutations,
                "all_permutations_exact": all(
                    v["exact"] for v in permutations.values()
                ),
            }
        )
        del output, row_authority

    input_hash_after = tensor_sha256(inputs)
    weight_hash_after = tensor_sha256(weight)
    if input_hash_after != input_hash_before or weight_hash_after != weight_hash_before:
        raise RuntimeError("input or weight mutated during the cell")
    all_exact = all(
        singleton_finite
        and row["finite"]
        and row["same_m_repeatable"]
        and row["all_rows_match_m1_authority"]
        and row["all_permutations_exact"]
        for row in m_results
    )
    native_libraries = loaded_native_library_contract()
    return {
        "schema": "neural.download.qwen38-flash-next.bf16-dense-invariance-cell.v1",
        "status": "classified",
        "classification": "component_only_real_weight_bf16_dense_invariance",
        "identity": {
            **identity,
            "model": "Qwen/Qwen3.8-Flash-Next-FP8",
            "model_revision": MODEL_REVISION,
            "model_index_sha256": MODEL_INDEX_SHA256,
            "model_config_sha256": MODEL_CONFIG_SHA256,
            "torch": TORCH_VERSION,
            "torch_build_config_sha256": torch_build_config_sha,
            "safetensors": SAFETENSORS_VERSION,
            "family": args.family,
            "sentinel": sentinel,
            "seed": args.seed,
            "replica": args.replica,
            "checkpoint_shards": shards,
            "source_tensors": source_tensors,
            "shard_contract_sha256": contract_sha,
            "weight_sha256": weight_hash_before,
            "input_sha256": input_hash_before,
            "singleton_authority_sha256": singleton_hashes[0],
            "admission": admission,
            "gemm_environment": verify_worker_environment(),
            "loaded_native_libraries": native_libraries,
        },
        "shape": {
            "a": ["M", FAMILIES[args.family]["k"]],
            "weight_nk": list(weight.shape),
            "b_stride": list(weight.T.stride()),
            "calls_per_token": FAMILIES[args.family]["calls"],
        },
        "protocol": {
            "m_values": list(M_VALUES),
            "production_m_values": list(PRODUCTION_M_VALUES),
            "diagnostic_only_m_values": list(DIAGNOSTIC_M_VALUES),
            "repeats": REPEATS,
            "permutations": list(PERMUTATIONS),
            "authority": "same XPU F.linear evaluated one row at a time",
            "authority_repeats": 2,
        },
        "results": m_results,
        "all_cells_exact": all_exact,
        "promotion_authority": False,
        "endpoint_or_speed_credit": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("plan", help="emit the frozen CPU-only Phase-1 plan")
    subparsers.add_parser(
        "run-plan", help="run all frozen cells as separate fresh processes"
    )
    worker = subparsers.add_parser("run-cell", help="run one explicitly selected cell")
    worker.add_argument("--family", choices=tuple(FAMILIES), required=True)
    worker.add_argument("--sentinel", required=True)
    worker.add_argument("--seed", type=int, choices=SEEDS, required=True)
    worker.add_argument("--replica", type=int, choices=REPLICAS, required=True)
    worker.add_argument("--output", type=Path, required=True)
    worker.add_argument("--shard-contract", type=Path)
    worker.add_argument("--shard-contract-sha256")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    validate_catalog()
    if args.command in (None, "plan"):
        plan = {
            "schema": "neural.download.qwen38-flash-next.bf16-dense-invariance-plan.v1",
            "catalog": catalog_summary(),
            "production_m_values": list(PRODUCTION_M_VALUES),
            "diagnostic_only_m_values": list(DIAGNOSTIC_M_VALUES),
            "seeds": list(SEEDS),
            "replicas": list(REPLICAS),
            "cell_processes": phase1_plan(),
            "cell_process_count": len(phase1_plan()),
            "execution_authorized_by_plan_emission": False,
        }
        print(json.dumps(plan, indent=2, sort_keys=True))
        return
    if args.command == "run-plan":
        summary_path = run_plan()
        print(json.dumps({"status": "complete", "summary": str(summary_path)}))
        return
    result = run_cell(args)
    atomic_write_json(args.output.resolve(), result)
    print(json.dumps({"status": "written", "path": str(args.output.resolve())}))


if __name__ == "__main__":
    main()

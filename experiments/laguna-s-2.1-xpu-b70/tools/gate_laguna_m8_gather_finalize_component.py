#!/usr/bin/env python3
"""CPU-only authorization compiler for the bounded Laguna M8 component phase.

This prepares one timing/exactness capture only.  It deliberately cannot
declare a component or endpoint pass: mandatory counter evidence is a later,
separately authorized phase.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

MAIN = Path("/home/steve/llm-optimizations")
ARTIFACT = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1")
NVME_SOURCE, NVME_FSTYPE = "/dev/nvme0n1p2", "ext4"
PYTHON = Path("/home/steve/.venvs/deepseek-v4-xpu/bin/python")
VLLM_REPO = Path("/home/steve/src/deepseek-v4-vllm-xpu-dspark")
KERNELS_REPO = Path("/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc")
COMPILER = Path("/opt/intel/oneapi/compiler/2025.3/bin/icpx")
FORMAT = "laguna-m8-gather-finalize-timing-exactness-authorization-v2"
PHASE = "component_timing_exactness_phase"
FROZEN_VLLM_COMMIT = "5519c08c168838b7e0a418499603b907f127cbf9"
FROZEN_KERNELS_COMMIT = "4772f727590c51b72add79350b913d098cf67872"
TOOLING_PARENT_COMMIT = "d338610eabb59cdb9321ceb3d485f2a7bdb31ba2"
PACKET_REPO_PATH = (
    "data/laguna-s-2.1-gather-finalize-phase-a-authorization-20260724.json"
)
BINARY_ARCHIVE_ROOT = ARTIFACT / "binaries/gather-finalize-4772f72-20260724T075721Z"
CANDIDATE_MOE_PATH = BINARY_ARCHIVE_ROOT / "candidate-_moe_C.abi3.so"
CANDIDATE_MOE_SHA256 = (
    "6a6794249421aceb51f14980a3e2c0b0a9d7b492abf2f8d25b129b86f099bc5b"
)
FORBIDDEN_ROOT = "/media/steve/CorsairExternal"
PREREG = "experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-routed-gather-finalize-fusion-preregistration.md"
SOURCE_FREEZE = "experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-routed-gather-finalize-stage0-source-freeze.md"
SOURCE_FREEZE_JSON = (
    "data/laguna-s-2.1-gather-finalize-stage0-source-freeze-20260724.json"
)
CARD_MAPPING_EVIDENCE = (
    "data/laguna-s-2.1-shared-gate-up-m8-component-authorization-20260724T051216Z.json"
)
W2_RUNTIME_NOTE = (
    "experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-routed-w1-n128-component-gate.md"
)
W2_RUNTIME_DATA = "data/laguna-s-2.1-fused-w1-route-w2-record-20260722.json"
SCALE_ADD_EXACTNESS_NOTE = "experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-shared-elementwise-component-result.md"
SCALE_ADD_EXACTNESS_DATA = (
    "data/laguna-s-2.1-shared-elementwise-component-20260723.json"
)

CARDS = {
    0: {
        "logical_device_id": 0,
        "uuid": "00000000-0000-0023-0000-0000e2238086",
        "pci_bdf_address": "0000:23:00.0",
        "drm_device": "/dev/dri/card3",
    },
    1: {
        "logical_device_id": 1,
        "uuid": "00000000-0000-0027-0000-0000e2238086",
        "pci_bdf_address": "0000:27:00.0",
        "drm_device": "/dev/dri/card4",
    },
    2: {
        "logical_device_id": 2,
        "uuid": "00000000-0000-0043-0000-0000e2238086",
        "pci_bdf_address": "0000:43:00.0",
        "drm_device": "/dev/dri/card0",
    },
    3: {
        "logical_device_id": 3,
        "uuid": "00000000-0000-0047-0000-0000e2238086",
        "pci_bdf_address": "0000:47:00.0",
        "drm_device": "/dev/dri/card2",
    },
}
TOOLS = {
    "contract": "experiments/laguna-s-2.1-xpu-b70/tools/gate_laguna_m8_gather_finalize_component.py",
    "fixture_generator": "experiments/laguna-s-2.1-xpu-b70/tools/generate_laguna_m8_gather_finalize_fixture.py",
    "runner": "experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_m8_gather_finalize_component.py",
    "analyzer": "experiments/laguna-s-2.1-xpu-b70/tools/analyze_laguna_m8_gather_finalize_component.py",
    "coordinator": "experiments/laguna-s-2.1-xpu-b70/tools/orchestrate_laguna_m8_gather_finalize_component.py",
    "tests": "experiments/laguna-s-2.1-xpu-b70/tools/test_laguna_m8_gather_finalize_component.py",
}
TOOL_STATES = {name: "REVIEWABLE_PENDING_COUNTER_PHASE" for name in TOOLS}
LIBRARIES = (
    "_C.abi3.so",
    "_xpu_C.abi3.so",
    "_moe_C.abi3.so",
    "libgrouped_gemm_xe_2.so",
)
INSTALLED_LIBRARY_PATHS = {
    name: KERNELS_REPO / "vllm_xpu_kernels" / name for name in LIBRARIES
}
CANDIDATE_LIBRARY_PATHS = {
    "_C.abi3.so": BINARY_ARCHIVE_ROOT / "shared-_C.abi3.so",
    "_xpu_C.abi3.so": BINARY_ARCHIVE_ROOT / "shared-_xpu_C.abi3.so",
    "_moe_C.abi3.so": CANDIDATE_MOE_PATH,
    "libgrouped_gemm_xe_2.so": (BINARY_ARCHIVE_ROOT / "shared-libgrouped_gemm_xe_2.so"),
}
INCUMBENT_LIBRARY_PATHS = {
    **CANDIDATE_LIBRARY_PATHS,
    "_moe_C.abi3.so": BINARY_ARCHIVE_ROOT / "incumbent-_moe_C.abi3.so",
}
NATIVE_W2_PATH = "csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2_interface.hpp"
PYTHON_W2_PATH = "vllm_xpu_kernels/fused_moe_interface.py"
RECORD_KERNELS_COMMIT = "b6076ce1249ffee0e30bee528f4cd15c3bffb234"
NATIVE_W2_SHA256 = "7b78e141e4a320ed0f46f01ff40cdcff5e93144ac31b8642bee079eb8ceb4bc6"
FIXTURE_FORMAT = "laguna-m8-gather-finalize-fixture-manifest-v2"
FIXTURE_CORPUS_VERSION = "laguna-m8-gather-finalize-corpus-v2"
FINITE_BF16_COUNT = 65280
RANDOM_FIXTURES = 256
RANDOM_SEED_BASE = 0x6A4700
RANDOM_SEED_STRIDE = 7919
MODEL_CONFIG = Path("/mnt/fast-ai/llm-models/laguna-s-2.1/int4/config.json")
MODEL_CONFIG_SHA256 = "9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6"

SELECTORS = {
    "VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE": "1",
    "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1",
    "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2": "1",
    "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE": "1",
    "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "1",
    "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "1",
    "VLLM_XPU_LAGUNA_M8_W1_N_TILE": "64",
    "VLLM_XPU_EXACT_SPEC_ATTN": "1",
    "VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM": "0",
    "VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM": "0",
    "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM": "0",
    "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM": "0",
    "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": "0",
    "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION": "0",
    "VLLM_XPU_LAGUNA_M8_REMOTE_ZERO": "0",
    "VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM": "0",
    "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH": "0",
    "VLLM_USE_AOT_COMPILE": "0",
    "VLLM_XPU_ENABLE_XPU_GRAPH": "0",
    "VLLM_XPU_FORCE_GRAPH_WITH_COMM": "0",
    "VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE": "0",
    "XPU_GRAPH": "0",
}
NEGATIVE_STATES = {
    "eager_only": True,
    "graphs_disabled": True,
    "aot_disabled": True,
    "compile_disabled": True,
    "dflash_disabled": True,
    "prefill_disabled": True,
    "network_authorized": False,
    "service_authorized": False,
    "model_generation_authorized": False,
    "endpoint_authorized": False,
    "payload_authorized": False,
    "submission_authorized": False,
    "reboot_authorized": False,
    "external_corsair_authorized": False,
    "full_component_pass_claim_authorized": False,
}
FALSE_ACTIONS = {
    key: value for key, value in NEGATIVE_STATES.items() if key.endswith("authorized")
}
PROTOCOL = {
    "status": PHASE,
    "counter_phase_required": True,
    "counter_phase_complete": False,
    "campaigns_authorized": 1,
    "retry_authorized": False,
    "rank_order": [0, 1, 2, 3],
    "tokens": 8,
    "hidden_size": 3072,
    "topk": 10,
    "local_experts": 64,
    "control_launches_per_cycle": 94,
    "candidate_launches_per_cycle": 47,
    "warm_cycles_per_arm": 20,
    "abba_blocks": 31,
    "cycles_per_arm_per_block": 64,
    "arm_order": "A-B-B-A",
    "minimum_wins": 28,
    "minimum_median_saving_ms_per_47_layer_cycle": 0.15,
    "timed_scope": "MoeGather_then_laguna_m8_scale_add versus laguna_m8_moe_gather_finalize only",
    "post_timing_exact_replay_required": True,
    "one_failure_stops_campaign": True,
    "strict_idle_seconds": 65,
    "strict_idle_minimum_samples": 30,
    "runner_timeout_seconds": 1800,
    "analyzer_timeout_seconds": 180,
    "per_card_independent_validation_required": True,
    "endpoint_authorized": False,
    "full_component_pass_authorized": False,
}


def require(ok: bool, why: str) -> None:
    if not ok:
        raise RuntimeError(why)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def write_authorization(path: Path, value: dict[str, Any]) -> None:
    """Create one canonical packet without redirects, aliases, or overwrite."""
    require(
        path.is_absolute()
        and path.parent.is_dir()
        and not path.parent.is_symlink()
        and not path.exists()
        and not path.is_symlink(),
        "unsafe authorization output path",
    )
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        descriptor = os.open(
            path.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o644,
            dir_fd=parent,
        )
        try:
            payload = canonical(value) + b"\n"
            offset = 0
            while offset < len(payload):
                written = os.write(descriptor, payload[offset:])
                require(written > 0, "short authorization write")
                offset += written
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.fsync(parent)
    finally:
        os.close(parent)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _validate_tools_commit(commit: str) -> None:
    require(_is_commit(commit), "invalid tools commit")
    require(
        git(MAIN, "rev-parse", commit + "^") == TOOLING_PARENT_COMMIT,
        "tools commit is not the one allowed child of the source-freeze anchor",
    )
    changed = git(
        MAIN, "diff-tree", "--no-commit-id", "--name-only", "-r", commit
    ).splitlines()
    require(
        len(changed) == len(TOOLS) and set(changed) == set(TOOLS.values()),
        "tools commit must contain exactly the frozen Phase-A tools",
    )


def _is_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _is_commit(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(char in "0123456789abcdef" for char in value)
    )


def _strict(value: object, keys: set[str], label: str) -> dict[str, Any]:
    require(isinstance(value, dict) and set(value) == keys, f"{label} schema drift")
    return value


def _forbid_usb(value: object) -> None:
    if isinstance(value, str):
        require(
            FORBIDDEN_ROOT not in value and "/mnt/usb" not in value,
            "USB path forbidden",
        )
    elif isinstance(value, dict):
        for item in value.values():
            _forbid_usb(item)
    elif isinstance(value, list):
        for item in value:
            _forbid_usb(item)


def _nvme(path: Path, exists: bool) -> None:
    require(
        path.is_absolute() and not path.is_symlink() and path.is_relative_to(ARTIFACT),
        "internal NVMe path required",
    )
    target = path if exists else path.parent
    if exists:
        require(path.is_file() and not path.is_symlink(), "required NVMe file absent")
    out = subprocess.run(
        [
            "findmnt",
            "--noheadings",
            "--output",
            "SOURCE,FSTYPE",
            "--target",
            str(target),
        ],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.splitlines()
    require(
        [NVME_SOURCE, NVME_FSTYPE] in [line.split() for line in out],
        "internal NVMe ext4 required",
    )


def _record_file(path: Path, *, allow_symlink: bool = False) -> dict[str, str]:
    require(
        path.is_file() and (allow_symlink or not path.is_symlink()),
        f"required regular file absent or unsafe symlink: {path}",
    )
    return {
        "path": str(path),
        "resolved_path": str(path.resolve(strict=True)),
        "sha256": sha(path),
    }


def _host_identity() -> dict[str, Any]:
    driver, loader = (
        Path("/usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1"),
        Path("/lib/x86_64-linux-gnu/libze_loader.so.1"),
    )
    torch_root = (
        Path("/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/site-packages")
        / "torch"
    )
    version = subprocess.run(
        [str(COMPILER), "--version"], check=True, capture_output=True, text=True
    ).stdout
    return {
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "kernel_release": platform.release(),
        "kernel_taint": Path("/proc/sys/kernel/tainted").read_text().strip(),
        "python": {**_record_file(PYTHON, allow_symlink=True), "version": sys.version},
        "compiler": {
            **_record_file(COMPILER),
            "version_sha256": hashlib.sha256(version.encode()).hexdigest(),
        },
        "level_zero_driver": _record_file(driver, allow_symlink=True),
        "level_zero_loader": _record_file(loader, allow_symlink=True),
        "torch_init": _record_file(torch_root / "__init__.py"),
        "torch_version": _record_file(torch_root / "version.py"),
        "libtorch_xpu": _record_file(torch_root / "lib/libtorch_xpu.so"),
    }


def _module_origins() -> dict[str, dict[str, str]]:
    """Static origin proof; no candidate module is imported during authorization."""
    return {
        "vllm": _record_file(VLLM_REPO / "vllm/__init__.py"),
        "vllm_xpu_kernels": _record_file(KERNELS_REPO / "vllm_xpu_kernels/__init__.py"),
        "installed_moe_extension": _record_file(
            INSTALLED_LIBRARY_PATHS["_moe_C.abi3.so"]
        ),
    }


def _extract_unique(text: str, start: str, end: str, label: str) -> str:
    require(text.count(start) == 1, f"{label} start marker is not unique")
    start_index = text.index(start)
    require(text.count(end, start_index) == 1, f"{label} end marker is not unique")
    return text[start_index : text.index(end, start_index)]


def _native_w2_block(commit: str) -> str:
    source = git(KERNELS_REPO, "show", f"{commit}:{NATIVE_W2_PATH}")
    return _extract_unique(
        source,
        "    if (w1_only) return;\n",
        "\n  return output;\n}\n\nat::Tensor cutlass_grouped_gemm_m2",
        f"{commit} native W2",
    )


def _python_w2_call(commit: str) -> str:
    source = git(KERNELS_REPO, "show", f"{commit}:{PYTHON_W2_PATH}")
    matches: list[ast.Call] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "cutlass_grouped_gemm_m8_topk_int4_interface":
            continue
        if (
            node.args
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "act_scratch"
        ):
            matches.append(node)
    require(
        len(matches) == 1, f"{commit} must contain exactly one route-parallel W2 call"
    )
    return ast.dump(matches[0], annotate_fields=True, include_attributes=False)


def _w2_source_block_hashes() -> dict[str, Any]:
    record_native = _native_w2_block(RECORD_KERNELS_COMMIT)
    candidate_native = _native_w2_block(FROZEN_KERNELS_COMMIT)
    require(candidate_native == record_native, "native W2 launcher block changed")
    require(
        candidate_native.count("M8TopkInt4W2ReduceLauncher<w4a16_policy_m_8, id_type>")
        == 1,
        "native N64 W2 launcher count drift",
    )
    native_hash = hashlib.sha256(candidate_native.encode()).hexdigest()
    require(native_hash == NATIVE_W2_SHA256, "native W2 known hash drift")

    record_python = _python_w2_call(RECORD_KERNELS_COMMIT)
    candidate_python = _python_w2_call(FROZEN_KERNELS_COMMIT)
    require(candidate_python == record_python, "Python route-parallel W2 call changed")
    python_hash = hashlib.sha256(candidate_python.encode()).hexdigest()
    return {
        "baseline_commit": RECORD_KERNELS_COMMIT,
        "candidate_commit": FROZEN_KERNELS_COMMIT,
        "native": {
            "path": NATIVE_W2_PATH,
            "identical": True,
            "sha256": native_hash,
            "launcher_count": 1,
            "policy": "w4a16_policy_m_8 (N64)",
        },
        "python": {
            "path": PYTHON_W2_PATH,
            "identical": True,
            "ast_call_sha256": python_hash,
            "call_count": 1,
        },
    }


def _evidence() -> dict[str, dict[str, str]]:
    paths = {
        "preregistration": PREREG,
        "source_freeze_note": SOURCE_FREEZE,
        "source_freeze_data": SOURCE_FREEZE_JSON,
        "card_mapping": CARD_MAPPING_EVIDENCE,
        "w2_runtime_note": W2_RUNTIME_NOTE,
        "w2_runtime_data": W2_RUNTIME_DATA,
        "scale_add_exactness_note": SCALE_ADD_EXACTNESS_NOTE,
        "scale_add_exactness_data": SCALE_ADD_EXACTNESS_DATA,
    }
    return {
        name: {"path": path, "sha256": sha(MAIN / path)} for name, path in paths.items()
    }


def _model_identity() -> dict[str, Any]:
    require(
        MODEL_CONFIG.is_file()
        and not MODEL_CONFIG.is_symlink()
        and MODEL_CONFIG.is_relative_to(Path("/mnt/fast-ai/llm-models")),
        "internal NVMe model config required",
    )
    mount = subprocess.run(
        [
            "findmnt",
            "--noheadings",
            "--output",
            "SOURCE,FSTYPE",
            "--target",
            str(MODEL_CONFIG),
        ],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.splitlines()
    require(
        [NVME_SOURCE, NVME_FSTYPE] in [line.split() for line in mount],
        "model config is not on internal NVMe/ext4",
    )
    config = json.loads(MODEL_CONFIG.read_text())
    require(
        config.get("model_type") == "laguna"
        and config.get("hidden_size") == 3072
        and config.get("num_experts") == 256
        and config.get("num_experts_per_tok") == 10
        and config.get("rms_norm_eps") == 1e-6,
        "Laguna model config identity drift",
    )
    record = _record_file(MODEL_CONFIG)
    require(record["sha256"] == MODEL_CONFIG_SHA256, "model config hash drift")
    return {
        **record,
        "model_type": "laguna",
        "hidden_size": 3072,
        "num_experts": 256,
        "topk": 10,
        "rms_norm_eps": 1e-6,
    }


def fixture_spec_ids() -> list[str]:
    chunks = math.ceil(FINITE_BF16_COUNT / (8 * 3072))
    values = [f"random-full-{index:03d}" for index in range(RANDOM_FIXTURES)]
    values.extend(
        f"routed-finite-slot-{slot}-chunk-{chunk}"
        for slot in range(10)
        for chunk in range(chunks)
    )
    values.extend(f"shared-finite-chunk-{chunk}" for chunk in range(chunks))
    values.extend(
        (
            "special-bf16-classification",
            "fp32-weight-edges",
            "tie-even-midpoints",
            "all-local",
            "all-remote",
            "mixed-remote-zero",
        )
    )
    values.extend(f"canonical-slot-{slot}" for slot in range(10))
    return values


def validate_fixture_manifest(path: Path) -> dict[str, Any]:
    _nvme(path, True)
    raw = path.read_bytes()
    value = json.loads(raw)
    require(raw == canonical(value) + b"\n", "fixture must be canonical JSON")
    keys = {
        "format",
        "corpus_version",
        "random_full",
        "coverage",
        "downstream",
        "expected_cpu_input_hashes",
    }
    _strict(value, keys, "fixture")
    require(
        value["format"] == FIXTURE_FORMAT
        and value["corpus_version"] == FIXTURE_CORPUS_VERSION,
        "fixture version drift",
    )
    seeds = [
        RANDOM_SEED_BASE + index * RANDOM_SEED_STRIDE
        for index in range(RANDOM_FIXTURES)
    ]
    require(
        value["random_full"]
        == {
            "algorithm": "torch_cpu_generator_manual_seed_randn_v1",
            "seeds": seeds,
        },
        "fixture random seed grammar drift",
    )
    require(
        value["coverage"]
        == {
            "finite_bf16": {
                "excluded_exponent": 255,
                "count": FINITE_BF16_COUNT,
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
        "fixture coverage grammar drift",
    )
    hashes = value["expected_cpu_input_hashes"]
    expected_ids = fixture_spec_ids()
    input_keys = {
        "routes_bf16_le_sha256",
        "weights_fp32_le_sha256",
        "shared_bf16_le_sha256",
        "route_map_uint32_le_sha256",
    }
    require(
        isinstance(hashes, dict)
        and set(hashes) == set(expected_ids)
        and len(hashes) == len(expected_ids)
        and all(
            isinstance(item, dict)
            and set(item) == input_keys
            and all(_is_sha(digest) for digest in item.values())
            for item in hashes.values()
        ),
        "fixture CPU input hash manifest drift",
    )
    downstream = _strict(
        value["downstream"],
        {"format", "seed", "epsilon", "expected_cpu_static_input_hashes"},
        "fixture downstream",
    )
    require(
        downstream["format"] == "laguna-m8-post-moe-fused-add-rmsnorm-v1"
        and downstream["seed"] == 0x6A472021
        and downstream["epsilon"] == 1e-6,
        "fixture downstream identity drift",
    )
    static_hashes = downstream["expected_cpu_static_input_hashes"]
    require(
        isinstance(static_hashes, dict)
        and set(static_hashes) == {"rank_tail", "residual_base", "norm_weight"}
        and all(_is_sha(digest) for digest in static_hashes.values()),
        "fixture downstream static hash drift",
    )
    return value


def _binary_manifest(path: Path) -> dict[str, dict[str, dict[str, str]]]:
    _nvme(path, True)
    raw_bytes = path.read_bytes()
    raw = json.loads(raw_bytes)
    require(
        raw_bytes == canonical(raw) + b"\n",
        "binary manifest must be canonical JSON",
    )
    require(
        isinstance(raw, dict) and set(raw) == {"installed", "candidate", "incumbent"},
        "binary manifest roles drift",
    )
    expected_paths = {
        "installed": INSTALLED_LIBRARY_PATHS,
        "candidate": CANDIDATE_LIBRARY_PATHS,
        "incumbent": INCUMBENT_LIBRARY_PATHS,
    }
    manifest: dict[str, dict[str, dict[str, str]]] = {}
    for role, entries in raw.items():
        require(
            isinstance(entries, dict) and set(entries) == set(LIBRARIES),
            f"{role} library set drift",
        )
        require(
            entries
            == {name: str(value) for name, value in expected_paths[role].items()},
            f"{role} library paths drift from frozen archive/live mapping",
        )
        manifest[role] = {
            name: _record_file(Path(value))
            for name, value in entries.items()
            if isinstance(value, str) and Path(value).is_absolute()
        }
        require(
            set(manifest[role]) == set(LIBRARIES),
            f"{role} paths must be absolute regular files",
        )
    candidate = manifest["candidate"]
    require(
        candidate["_moe_C.abi3.so"]
        == {
            "path": str(CANDIDATE_MOE_PATH),
            "resolved_path": str(CANDIDATE_MOE_PATH.resolve(strict=True)),
            "sha256": CANDIDATE_MOE_SHA256,
        },
        "candidate _moe_C staging identity drift",
    )
    for name in LIBRARIES:
        require(
            manifest["installed"][name]["sha256"] == candidate[name]["sha256"],
            "installed must equal candidate for every library",
        )
        if name == "_moe_C.abi3.so":
            require(
                candidate[name]["sha256"] != manifest["incumbent"][name]["sha256"],
                "candidate _moe_C must differ from incumbent",
            )
        else:
            require(
                candidate[name]["sha256"] == manifest["incumbent"][name]["sha256"],
                "unchanged library differs from incumbent",
            )
    return manifest


def environment(root: str | Path, rank: int) -> dict[str, str]:
    root = Path(root)
    require(rank in CARDS, "invalid rank")
    runtime = root.parent / f"{root.name}-runtime"
    cache = runtime / "cache"
    return {
        "ACTIVE_REQUESTS": "1",
        "TP": "4",
        "EP": "4",
        "DP": "1",
        "PP": "1",
        "DRAFT_FLASH_DEPTH": "7",
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "PYTHONPATH": f"{VLLM_REPO}:{KERNELS_REPO}",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "VLLM_NO_USAGE_STATS": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "VLLM_XPU_RUN_DEVICE_TESTS": "0",
        "HOME": str(runtime / "home"),
        "TMPDIR": str(runtime / "tmp"),
        "TMP": str(runtime / "tmp"),
        "TEMP": str(runtime / "tmp"),
        "XDG_CACHE_HOME": str(cache / "xdg"),
        "XDG_CONFIG_HOME": str(cache / "xdg-config"),
        "XDG_DATA_HOME": str(cache / "xdg-data"),
        "XDG_STATE_HOME": str(cache / "xdg-state"),
        "HF_HOME": str(cache / "huggingface"),
        "TRANSFORMERS_CACHE": str(cache / "transformers"),
        "VLLM_CACHE_ROOT": str(cache / "vllm"),
        "TRITON_CACHE_DIR": str(cache / "triton"),
        "NUMBA_CACHE_DIR": str(cache / "numba"),
        "PYTHONPYCACHEPREFIX": str(cache / "pycache"),
        "SYCL_CACHE_DIR": str(cache / "sycl"),
        "TORCHINDUCTOR_CACHE_DIR": str(cache / "torchinductor"),
        "ONEAPI_DEVICE_SELECTOR": "level_zero:0",
        "ZE_AFFINITY_MASK": str(rank),
        **SELECTORS,
    }


def coordinator_environment(root: str | Path) -> dict[str, str]:
    return environment(root, 0)


def _paths(packet_path: Path, root: Path, fixture: Path) -> dict[str, Any]:
    cards = []
    for rank, physical in CARDS.items():
        card_root = root / f"card{rank}"
        runtime_root = card_root.parent / f"{card_root.name}-runtime"
        result = card_root / "component-result.json"
        cards.append(
            {
                "rank": rank,
                "physical": physical,
                "output_root": str(card_root),
                "runtime_root": str(runtime_root),
                "result": str(result),
                "environment": environment(card_root, rank),
                "runner_argv": [
                    str(PYTHON),
                    str(MAIN / TOOLS["runner"]),
                    "--authorization",
                    str(packet_path),
                    "--fixture",
                    str(fixture),
                    "--rank",
                    str(rank),
                ],
                "validator_argv": [
                    str(PYTHON),
                    str(MAIN / TOOLS["analyzer"]),
                    "--authorization",
                    str(packet_path),
                    "--card-result",
                    str(result),
                    "--single-card-rank",
                    str(rank),
                ],
            }
        )
    aggregate = root / "timing-exactness-aggregate.json"
    analyzer_argv = [
        str(PYTHON),
        str(MAIN / TOOLS["analyzer"]),
        "--authorization",
        str(packet_path),
    ]
    for card in cards:
        analyzer_argv.extend(["--card-result", card["result"]])
    analyzer_argv.extend(["--out", str(aggregate)])
    return {
        "cards": cards,
        "coordinator_argv": [
            str(PYTHON),
            str(MAIN / TOOLS["coordinator"]),
            "--authorization",
            str(packet_path),
            "--fixture",
            str(fixture),
        ],
        "analyzer_argv": analyzer_argv,
        "aggregate_path": str(aggregate),
        "preflight_failure_path": str(
            root.parent / f"{root.name}-preflight-failure.json"
        ),
        "campaign_terminal_path": str(root / "campaign-terminal.json"),
    }


def frozen_hashes(fixture: Path, binary_manifest: Path) -> dict[str, str]:
    require(
        git(MAIN, "status", "--porcelain=v1", "--untracked-files=all") == "",
        "main must be clean",
    )
    for repo, commit in (
        (VLLM_REPO, FROZEN_VLLM_COMMIT),
        (KERNELS_REPO, FROZEN_KERNELS_COMMIT),
    ):
        require(
            git(repo, "status", "--porcelain=v1", "--untracked-files=all") == ""
            and git(repo, "rev-parse", "HEAD") == commit,
            "source checkout drift",
        )
    tools_commit = git(MAIN, "rev-parse", "HEAD")
    _validate_tools_commit(tools_commit)
    return {
        **{name: sha(MAIN / item) for name, item in TOOLS.items()},
        "fixture": sha(fixture),
        "binary_manifest": sha(binary_manifest),
        "main_tools_commit": tools_commit,
    }


def template(
    *,
    fixture: Path,
    binary_manifest: Path,
    output_root: Path,
    packet_path: Path,
    hashes: dict[str, str],
) -> dict[str, Any]:
    validate_fixture_manifest(fixture)
    _nvme(output_root, False)
    require(
        packet_path.is_absolute()
        and packet_path.parent == MAIN / "data"
        and packet_path == MAIN / PACKET_REPO_PATH
        and not packet_path.exists()
        and not packet_path.is_symlink(),
        "fresh main data packet required",
    )
    require(
        output_root.parent.is_dir()
        and not output_root.parent.is_symlink()
        and not output_root.exists(),
        "fresh campaign root required",
    )
    evidence = _evidence()
    w2 = _w2_source_block_hashes()
    scale_add = evidence["scale_add_exactness_data"]
    integration_contract = {
        "canonical_control_map": "torch.arange(80).view(8,10)",
        "canonical_control_map_uint32_le_sha256": hashlib.sha256(
            b"".join(index.to_bytes(4, "little") for index in range(80))
        ).hexdigest(),
        "w2_identity_unchanged": True,
        "w2_arguments_unchanged": True,
        "w2_calls_in_matched_trace": 13,
        "w2_workgroups_per_call_per_card": 3840,
        "w2_policy": "w4a16_policy_m_8 (N64)",
        "source_proof": w2,
        "runtime_proof_note": evidence["w2_runtime_note"],
        "runtime_record_data": evidence["w2_runtime_data"],
    }
    packet = {
        "format": FORMAT,
        "status": PHASE,
        "packet_path": str(packet_path),
        "source": {
            "vllm_repo": str(VLLM_REPO),
            "vllm_commit": FROZEN_VLLM_COMMIT,
            "kernels_repo": str(KERNELS_REPO),
            "kernels_commit": FROZEN_KERNELS_COMMIT,
            "main_tools_commit": hashes["main_tools_commit"],
        },
        "host_identity": _host_identity(),
        "model_identity": _model_identity(),
        "module_origins": _module_origins(),
        "binary_manifest_source": {
            "path": str(binary_manifest),
            "sha256": hashes["binary_manifest"],
        },
        "binary_manifest": _binary_manifest(binary_manifest),
        "fixture": {"path": str(fixture), "sha256": hashes["fixture"]},
        "evidence": evidence,
        "integration_evidence_ids": [
            f"{name}:{record['sha256']}" for name, record in sorted(evidence.items())
        ],
        "integration_contract": integration_contract,
        "prior_incumbent_scale_add_exhaustive_evidence": {
            "path": str(MAIN / scale_add["path"]),
            "sha256": scale_add["sha256"],
            "evidence_id": (f"scale_add_exactness_data:{scale_add['sha256']}"),
        },
        "w2_source_block_hashes": w2,
        "tools": {
            name: {
                "path": path,
                "sha256": hashes[name],
                "state": TOOL_STATES[name],
            }
            for name, path in TOOLS.items()
        },
        "selectors": SELECTORS,
        "negative_states": NEGATIVE_STATES,
        "protocol": PROTOCOL,
        "campaign_root": str(output_root),
        "coordinator_environment": coordinator_environment(output_root),
        "authorization_tracking": {
            "repository": str(MAIN),
            "packet_repo_path": str(packet_path.relative_to(MAIN)),
            "tools_commit": hashes["main_tools_commit"],
            "required_commit_shape": "one_clean_auth_only_child",
        },
        "downstream": FALSE_ACTIONS,
        **_paths(packet_path, output_root, fixture),
    }
    validate(packet)
    return packet


def validate(packet: dict[str, Any]) -> None:
    required = {
        "format",
        "status",
        "packet_path",
        "source",
        "host_identity",
        "model_identity",
        "module_origins",
        "binary_manifest_source",
        "binary_manifest",
        "fixture",
        "evidence",
        "integration_evidence_ids",
        "integration_contract",
        "prior_incumbent_scale_add_exhaustive_evidence",
        "w2_source_block_hashes",
        "tools",
        "selectors",
        "negative_states",
        "protocol",
        "campaign_root",
        "coordinator_environment",
        "authorization_tracking",
        "downstream",
        "cards",
        "coordinator_argv",
        "analyzer_argv",
        "aggregate_path",
        "preflight_failure_path",
        "campaign_terminal_path",
    }
    _strict(packet, required, "packet")
    _forbid_usb(packet)
    require(
        packet["format"] == FORMAT
        and packet["status"] == PHASE
        and packet["protocol"] == PROTOCOL
        and packet["selectors"] == SELECTORS
        and packet["negative_states"] == NEGATIVE_STATES
        and packet["downstream"] == FALSE_ACTIONS,
        "phase or protocol drift",
    )
    source = packet["source"]
    require(
        source
        == {
            "vllm_repo": str(VLLM_REPO),
            "vllm_commit": FROZEN_VLLM_COMMIT,
            "kernels_repo": str(KERNELS_REPO),
            "kernels_commit": FROZEN_KERNELS_COMMIT,
            "main_tools_commit": source["main_tools_commit"],
        }
        and _is_commit(source["main_tools_commit"]),
        "source identity drift",
    )
    require(
        packet["authorization_tracking"]
        == {
            "repository": str(MAIN),
            "packet_repo_path": PACKET_REPO_PATH,
            "tools_commit": source["main_tools_commit"],
            "required_commit_shape": "one_clean_auth_only_child",
        },
        "authorization tracking drift",
    )
    fixture = packet["fixture"]
    require(
        isinstance(fixture, dict)
        and set(fixture) == {"path", "sha256"}
        and _is_sha(fixture["sha256"]),
        "fixture packet schema drift",
    )
    validate_fixture_manifest(Path(fixture["path"]))
    require(sha(Path(fixture["path"])) == fixture["sha256"], "fixture identity drift")
    binary_source = packet["binary_manifest_source"]
    require(
        isinstance(binary_source, dict)
        and set(binary_source) == {"path", "sha256"}
        and _is_sha(binary_source["sha256"]),
        "binary manifest source schema drift",
    )
    _nvme(Path(binary_source["path"]), True)
    require(
        sha(Path(binary_source["path"])) == binary_source["sha256"]
        and _binary_manifest(Path(binary_source["path"])) == packet["binary_manifest"],
        "binary manifest source drift",
    )
    evidence = _evidence()
    w2 = _w2_source_block_hashes()
    require(
        packet["model_identity"] == _model_identity(),
        "model identity drift",
    )
    require(
        packet["evidence"] == evidence and packet["w2_source_block_hashes"] == w2,
        "prior evidence/W2 source identity drift",
    )
    require(
        packet["integration_evidence_ids"]
        == [f"{name}:{record['sha256']}" for name, record in sorted(evidence.items())],
        "integration evidence IDs drift",
    )
    scale_add = evidence["scale_add_exactness_data"]
    require(
        packet["prior_incumbent_scale_add_exhaustive_evidence"]
        == {
            "path": str(MAIN / scale_add["path"]),
            "sha256": scale_add["sha256"],
            "evidence_id": (f"scale_add_exactness_data:{scale_add['sha256']}"),
        },
        "prior scale/add exactness binding drift",
    )
    integration = packet["integration_contract"]
    require(
        integration
        == {
            "canonical_control_map": "torch.arange(80).view(8,10)",
            "canonical_control_map_uint32_le_sha256": hashlib.sha256(
                b"".join(index.to_bytes(4, "little") for index in range(80))
            ).hexdigest(),
            "w2_identity_unchanged": True,
            "w2_arguments_unchanged": True,
            "w2_calls_in_matched_trace": 13,
            "w2_workgroups_per_call_per_card": 3840,
            "w2_policy": "w4a16_policy_m_8 (N64)",
            "source_proof": w2,
            "runtime_proof_note": evidence["w2_runtime_note"],
            "runtime_record_data": evidence["w2_runtime_data"],
        },
        "integration contract drift",
    )
    require(
        packet["module_origins"] == _module_origins(),
        "pinned PYTHONPATH module-origin drift",
    )
    require(
        set(packet["tools"]) == set(TOOLS)
        and all(
            packet["tools"][name]
            == {
                "path": path,
                "sha256": packet["tools"][name]["sha256"],
                "state": TOOL_STATES[name],
            }
            and _is_sha(packet["tools"][name]["sha256"])
            for name, path in TOOLS.items()
        ),
        "tool inventory/state drift",
    )
    root = Path(packet["campaign_root"])
    _nvme(root, False)
    paths = _paths(Path(packet["packet_path"]), root, Path(fixture["path"]))
    require(
        all(packet[key] == value for key, value in paths.items())
        and packet["coordinator_environment"] == coordinator_environment(root),
        "argv/environment drift",
    )
    _binary_manifest_live(packet["binary_manifest"])


def _binary_manifest_live(manifest: object) -> None:
    require(
        isinstance(manifest, dict)
        and set(manifest) == {"installed", "candidate", "incumbent"},
        "binary manifest schema drift",
    )
    for role, entries in manifest.items():
        require(
            isinstance(entries, dict) and set(entries) == set(LIBRARIES),
            f"{role} library inventory drift",
        )
        for item in entries.values():
            require(
                isinstance(item, dict)
                and set(item) == {"path", "resolved_path", "sha256"}
                and _record_file(Path(item["path"])) == item,
                "live binary identity drift",
            )
    expected_paths = {
        "installed": INSTALLED_LIBRARY_PATHS,
        "candidate": CANDIDATE_LIBRARY_PATHS,
        "incumbent": INCUMBENT_LIBRARY_PATHS,
    }
    for role, entries in manifest.items():
        require(
            {name: item["path"] for name, item in entries.items()}
            == {name: str(path) for name, path in expected_paths[role].items()},
            f"{role} live path mapping drift",
        )
    candidate = manifest["candidate"]
    require(
        candidate["_moe_C.abi3.so"]["path"] == str(CANDIDATE_MOE_PATH)
        and candidate["_moe_C.abi3.so"]["sha256"] == CANDIDATE_MOE_SHA256,
        "candidate archive identity drift",
    )
    for name in LIBRARIES:
        require(
            manifest["installed"][name]["sha256"] == candidate[name]["sha256"],
            "installed/candidate mismatch",
        )
        require(
            (candidate[name]["sha256"] != manifest["incumbent"][name]["sha256"])
            == (name == "_moe_C.abi3.so"),
            "unexpected binary delta",
        )


def validate_execution_packet(packet: dict[str, Any], authorization: Path) -> None:
    require(
        authorization.is_absolute()
        and authorization.is_file()
        and not authorization.is_symlink(),
        "unsafe authorization",
    )
    raw = authorization.read_bytes()
    require(
        raw == canonical(packet) + b"\n"
        and str(authorization) == packet["packet_path"],
        "authorization canonical/path drift",
    )
    validate(packet)
    require(
        git(MAIN, "status", "--porcelain=v1", "--untracked-files=all") == "",
        "main must be clean",
    )
    source = packet["source"]
    _validate_tools_commit(source["main_tools_commit"])
    for repo_key, commit_key in (
        ("vllm_repo", "vllm_commit"),
        ("kernels_repo", "kernels_commit"),
    ):
        repo = Path(source[repo_key])
        require(
            git(repo, "status", "--porcelain=v1", "--untracked-files=all") == ""
            and git(repo, "rev-parse", "HEAD") == source[commit_key],
            "candidate source checkout drift",
        )
    require(
        _host_identity() == packet["host_identity"],
        "boot/compiler/runtime identity drift",
    )
    head, tracking = git(MAIN, "rev-parse", "HEAD"), packet["authorization_tracking"]
    require(
        git(MAIN, "rev-parse", head + "^") == tracking["tools_commit"]
        and git(
            MAIN, "diff-tree", "--no-commit-id", "--name-only", "-r", head
        ).splitlines()
        == [tracking["packet_repo_path"]],
        "tracked child must be packet-only",
    )
    require(
        subprocess.run(
            ["git", "-C", str(MAIN), "show", f"{head}:{tracking['packet_repo_path']}"],
            check=True,
            capture_output=True,
        ).stdout
        == raw,
        "tracked packet blob drift",
    )
    for name, record in packet["tools"].items():
        require(
            sha(MAIN / record["path"]) == record["sha256"], f"tool hash drift: {name}"
        )
    for card in packet["cards"]:
        physical = card["physical"]
        device = (
            Path("/sys/class/drm") / Path(physical["drm_device"]).name / "device"
        ).resolve(strict=True)
        require(
            device.name == physical["pci_bdf_address"]
            and (device / "vendor").read_text().strip() == "0x8086"
            and (device / "device").read_text().strip() == "0xe223",
            "sysfs B70 mapping drift",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--print-authorization", action="store_true")
    action.add_argument("--write-authorization", action="store_true")
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--binary-manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--packet-path", type=Path, required=True)
    args = parser.parse_args()
    packet = template(
        fixture=args.fixture,
        binary_manifest=args.binary_manifest,
        output_root=args.output_root,
        packet_path=args.packet_path,
        hashes=frozen_hashes(args.fixture, args.binary_manifest),
    )
    if args.write_authorization:
        write_authorization(args.packet_path, packet)
    else:
        print(canonical(packet).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

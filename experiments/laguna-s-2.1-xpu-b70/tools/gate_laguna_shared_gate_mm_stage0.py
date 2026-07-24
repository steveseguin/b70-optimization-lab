#!/usr/bin/env python3
"""CPU-only, fail-closed evidence contract for Laguna shared-gate stage zero.

There is intentionally no torch/vLLM/XPU/model/timing/profiler/network path in
this file.  The future runtime adapter and runner are explicit frozen
placeholders and cannot be authorized while they remain unimplemented.
"""

from __future__ import annotations

import argparse
import base64
import functools
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Iterable

ARTIFACT_ROOT_LITERAL = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1")
NVME_SOURCE, NVME_FSTYPE = "/dev/nvme0n1p2", "ext4"
FORMAT = "laguna-shared-gate-m8-stage0-fixtures-v5"
AUTHORIZATION_FORMAT = "laguna-shared-gate-m8-stage0-authorization-v5"
RESULT_FORMAT = "laguna-shared-gate-m8-stage0-result-v5"
ADAPTER_STATE = "READY_STAGE0_EXECUTION"
ROWS, HIDDEN, PROJECTION, EPOCHS, BASE_SEED = 8, 3072, 256, 128, 730000
DTYPE, BYTE_ORDER = "bfloat16", "little"
PREREG_PATH = "experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-shared-gate-native-m8-mm-preregistration.md"
PREREG_SHA256 = "fce4daed9cecc57febe1c81671b2bee24484a66dd4cee374dd573eb23947f852"
EXPECTED_BOOT_ID = "0b7f98a5-e50a-46a5-81ea-15938b55317a"
EXPECTED_VLLM_COMMIT = "3dae2ce383a009624bc6ff3e8660851fab5c12e0"
EXPECTED_KERNEL_COMMIT = "c59aaadbbfd350c2b5f4ad663e247c2811ae3181"
EXPECTED_MODEL_CONFIG_SHA256 = (
    "9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6"
)
EXPECTED_BINARY_SHA256 = {
    "_C.abi3.so": "126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2",
    "_xpu_C.abi3.so": "f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8",
    "_moe_C.abi3.so": "0057b266d567731a9f9f592cefd9103bbf027ebb83c876d26c17ffb09994a3a0",
    "libgrouped_gemm_xe_2.so": "fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96",
}
EXPECTED_CARD0 = {
    "logical_device_id": 0,
    "uuid": "00000000-0000-0023-0000-0000e2238086",
    "pci_bdf_address": "0000:23:00.0",
    "drm_device": "/dev/dri/card3",
}
EXPECTED_DEVICE_NAME = "Intel(R) Arc(TM) Pro B70 Graphics"
EXPECTED_RUNTIME_OBSERVED_IDENTITY = {
    "python_version": "3.12.13 (main, May 10 2026, 19:30:01) [Clang 22.1.3 ]",
    "python_executable": "/home/steve/.venvs/deepseek-v4-xpu/bin/python",
    "torch_version": "2.12.0+xpu",
    "files": {
        "python": {
            "path": "/home/steve/.venvs/deepseek-v4-xpu/bin/python",
            "resolved_path": (
                "/home/steve/.local/share/uv/python/"
                "cpython-3.12.13-linux-x86_64-gnu/bin/python3.12"
            ),
            "sha256": (
                "202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8"
            ),
        },
        "torch_init": {
            "path": (
                "/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/"
                "site-packages/torch/__init__.py"
            ),
            "resolved_path": (
                "/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/"
                "site-packages/torch/__init__.py"
            ),
            "sha256": (
                "d9dfff4b75d46e4c75572200a3466b70231d05b0318e38ac1bd121789165fb49"
            ),
        },
        "torch_version": {
            "path": (
                "/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/"
                "site-packages/torch/version.py"
            ),
            "resolved_path": (
                "/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/"
                "site-packages/torch/version.py"
            ),
            "sha256": (
                "454023e3d6adf79f58a7441ffdebc8cf63c9ded2809a254817fa436f9dc7b5c3"
            ),
        },
        "libtorch_xpu": {
            "path": (
                "/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/"
                "site-packages/torch/lib/libtorch_xpu.so"
            ),
            "resolved_path": (
                "/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/"
                "site-packages/torch/lib/libtorch_xpu.so"
            ),
            "sha256": (
                "63b7a56723482bc35d31842f442f6e903ef0b7fbd741c1a4ae309123bbc90572"
            ),
        },
        "level_zero_driver": {
            "path": "/usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1",
            "resolved_path": (
                "/usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1.15.38308"
            ),
            "sha256": (
                "26fa68779adb03b200a8c3001cf81e59fc9a3d63e0f38627ec0005ffce574e7a"
            ),
        },
        "level_zero_loader": {
            "path": "/lib/x86_64-linux-gnu/libze_loader.so.1",
            "resolved_path": "/usr/lib/x86_64-linux-gnu/libze_loader.so.1.28.2",
            "sha256": (
                "0fe232b18985ae078dd546b57bc6d11bacf1030834c0544f7e3feb53ed71c1d0"
            ),
        },
    },
}
DISPATCH_REJECTION_EXCEPTIONS = {
    "bad_rows": {
        "type": "RuntimeError",
        "message": (
            "VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM=1 diverged from its exact eager "
            "Laguna shared-gate contract: rows are not contiguous"
        ),
    },
    "bad_weight_layout": {
        "type": "RuntimeError",
        "message": (
            "VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM=1 diverged from its exact eager "
            "Laguna shared-gate contract: shared-gate weight is not contiguous"
        ),
    },
}
TOOL_PATHS = {
    "fixture_generator": "experiments/laguna-s-2.1-xpu-b70/tools/gate_laguna_shared_gate_mm_stage0.py",
    "result_analyzer": "experiments/laguna-s-2.1-xpu-b70/tools/analyze_laguna_shared_gate_mm_stage0.py",
    "cpu_tests": "experiments/laguna-s-2.1-xpu-b70/tools/test_analyze_laguna_shared_gate_mm_stage0.py",
    "runtime_adapter": "experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_shared_gate_mm_stage0.py",
    "runtime_tests": "experiments/laguna-s-2.1-xpu-b70/tools/test_run_laguna_shared_gate_mm_stage0.py",
    "runtime_runner": "experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_shared_gate_mm_stage0.sh",
}
SOURCE_PATHS = (
    "vllm/compilation/decorators.py",
    "vllm/envs.py",
    "vllm/forward_context.py",
    "vllm/model_executor/layers/linear.py",
    "vllm/model_executor/models/laguna.py",
    "tests/models/test_laguna_shared_gate_mm.py",
    "tests/models/test_laguna_shared_down_mm.py",
)
TOOL_STATES = {
    "fixture_generator": "CPU_ONLY_REVIEWED",
    "result_analyzer": "CPU_ONLY_REVIEWED",
    "cpu_tests": "CPU_ONLY_REVIEWED",
    "runtime_adapter": ADAPTER_STATE,
    "runtime_tests": "CPU_ONLY_REVIEWED",
    "runtime_runner": ADAPTER_STATE,
}
PRE_ACTIONS = (
    "component_tooling_construction_authorized",
    "component_execution_authorized",
    "timing_authorized",
    "other_card_authorized",
    "counter_authorized",
    "endpoint_authorized",
    "service_authorized",
    "model_generation_authorized",
    "payload_authorized",
    "submission_authorized",
    "reboot_authorized",
    "network_authorized",
)
RESULT_ACTIONS = tuple(
    action.replace("_authorized", "_performed") for action in PRE_ACTIONS
)
PASS_NEXT_ACTIONS = {
    action: action == "component_tooling_construction_authorized"
    for action in PRE_ACTIONS
}
TENSOR_SPECS = (
    ("hidden_input", 1, (ROWS, HIDDEN)),
    ("gate_weight", 2, (PROJECTION, HIDDEN)),
    ("up_weight", 3, (PROJECTION, HIDDEN)),
    ("down_weight", 4, (HIDDEN, PROJECTION)),
    ("routed_input", 5, (ROWS, HIDDEN)),
    ("reduction_peer_0", 6, (ROWS, HIDDEN)),
    ("reduction_peer_1", 7, (ROWS, HIDDEN)),
    ("reduction_peer_2", 8, (ROWS, HIDDEN)),
)
CASE_NAMES = {
    0: "finite_random",
    1: "finite_random",
    2: "finite_random",
    3: "finite_random",
    4: "signed_zero_subnormal",
    5: "bounded_large_finite",
    6: "cancellation_heavy",
    7: "bf16_boundary_overlay",
}
FINITE_HIGH_BYTE_TRANSLATION = bytes(
    ((value & 0x80) | (0x3B + value % 9)) for value in range(256)
)
NEGATE_HIGH_BYTE_TRANSLATION = bytes(value ^ 0x80 for value in range(256))
NONFINITE_HIGH_FLAG = bytes(1 if (value & 0x7F) == 0x7F else 0 for value in range(256))


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_all(fd: int, payload: bytes) -> None:
    pending = memoryview(payload)
    while pending:
        written = os.write(fd, pending)
        require(written > 0, "short write while sealing JSON evidence")
        pending = pending[written:]


def is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def is_commit(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(char in "0123456789abcdef" for char in value)
    )


def tensor_byte_count(shape: Iterable[int]) -> int:
    elements = 1
    for dimension in shape:
        require(isinstance(dimension, int) and dimension > 0, "invalid tensor shape")
        elements *= dimension
    return elements * 2


def bf16_all_finite(raw_bf16_le: bytes) -> bool:
    """True only when no little-endian BF16 word has exponent 0xff."""
    require(len(raw_bf16_le) % 2 == 0, "BF16 raw byte length must be even")
    high = raw_bf16_le[1::2]
    candidates = high.translate(NONFINITE_HIGH_FLAG)
    if b"\x01" not in candidates:
        return True
    return not any(
        (high_byte & 0x7F) == 0x7F and low_byte & 0x80
        for low_byte, high_byte in zip(raw_bf16_le[0::2], high, strict=True)
    )


def canonical_tensor_sha256(
    label: str, shape: tuple[int, ...], raw_bf16_le: bytes
) -> str:
    require(
        isinstance(label, str) and label and "\0" not in label, "invalid tensor label"
    )
    require(
        len(raw_bf16_le) == tensor_byte_count(shape),
        f"wrong BF16 byte count for {label}",
    )
    header = canonical_json_bytes(
        {"label": label, "shape": list(shape), "dtype": DTYPE, "byte_order": BYTE_ORDER}
    )
    return sha256_bytes(
        b"laguna-stage0-tensor-v3\0"
        + len(header).to_bytes(8, "big")
        + header
        + raw_bf16_le
    )


def tensor_record(
    label: str, shape: tuple[int, ...], raw: bytes, *, include_raw: bool = False
) -> dict[str, Any]:
    record = {
        "label": label,
        "shape": list(shape),
        "dtype": DTYPE,
        "byte_order": BYTE_ORDER,
        "raw_bf16_le_sha256": sha256_bytes(raw),
        "canonical_sha256": canonical_tensor_sha256(label, shape, raw),
        "finite": bf16_all_finite(raw),
    }
    if include_raw:
        record["raw_bf16_le_base64"] = base64.b64encode(raw).decode("ascii")
    return record


def _write_word(raw: bytearray, index: int, word: int) -> None:
    raw[index * 2 : index * 2 + 2] = word.to_bytes(2, "little")


def _overlay(raw: bytearray, case: int) -> None:
    words, stride = len(raw) // 2, max(1, len(raw) // 2 // 257)
    patterns: tuple[int, ...] | None = None
    if case == 4:
        patterns = (0x0000, 0x8000, 0x0001, 0x8001, 0x007F, 0x807F)
    elif case == 5:
        patterns = (0x4280, 0x4300, 0x4340, 0xC280, 0xC300, 0xC340)
    elif case == 6:
        raw[3::4] = raw[3::4].translate(NEGATE_HIGH_BYTE_TRANSLATION)
    elif case == 7:
        patterns = (0x3F7E, 0x3F7F, 0x3F80, 0x3F81, 0xBF7E, 0xBF7F, 0xBF80, 0xBF81)
    if patterns is not None:
        for index in range(0, words, stride):
            _write_word(raw, index, patterns[(index // stride) % len(patterns)])


def fixture_bytes(epoch: int, field_id: int, shape: tuple[int, ...]) -> bytes:
    require(
        0 <= epoch < EPOCHS and 1 <= field_id <= len(TENSOR_SPECS),
        "fixture seed is out of contract",
    )
    seed = BASE_SEED + 32 * epoch + field_id
    raw = bytearray(
        hashlib.shake_256(f"laguna-stage0-bf16:{seed}".encode()).digest(
            tensor_byte_count(shape)
        )
    )
    raw[1::2] = raw[1::2].translate(FINITE_HIGH_BYTE_TRANSLATION)
    _overlay(raw, epoch % 8)
    last = int.from_bytes(raw[-2:], "little")
    _write_word(
        raw, len(raw) // 2 - 1, (last & 0xFF80) | ((epoch * 17 + field_id * 29) & 0x7F)
    )
    result = bytes(raw)
    require(bf16_all_finite(result), "fixture generator emitted NaN or infinity")
    return result


def fixture_entry(epoch: int) -> dict[str, Any]:
    tensors = []
    for label, field_id, shape in TENSOR_SPECS:
        record = tensor_record(label, shape, fixture_bytes(epoch, field_id, shape))
        record.update({"field_id": field_id, "seed": BASE_SEED + 32 * epoch + field_id})
        tensors.append(record)
    entry = {
        "epoch": epoch,
        "case": epoch % 8,
        "case_name": CASE_NAMES[epoch % 8],
        "tensors": tensors,
    }
    entry["epoch_sha256"] = sha256_bytes(canonical_json_bytes(entry))
    return entry


def fixture_manifest_digest(manifest: dict[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _build_manifest() -> dict[str, Any]:
    epochs = [fixture_entry(epoch) for epoch in range(EPOCHS)]
    require(
        all(
            len({entry["tensors"][field]["canonical_sha256"] for entry in epochs})
            == EPOCHS
            for field in range(len(TENSOR_SPECS))
        ),
        "fixture replay",
    )
    manifest: dict[str, Any] = {
        "format": FORMAT,
        "stage": "stage0",
        "adapter_state": ADAPTER_STATE,
        "base_seed": BASE_SEED,
        "epoch_count": EPOCHS,
        "seed_formula": "base_seed + 32 * epoch + field_id",
        "case_formula": "epoch % 8",
        "case_counts": {
            "finite_random": 64,
            "signed_zero_subnormal": 16,
            "bounded_large_finite": 16,
            "cancellation_heavy": 16,
            "bf16_boundary_overlay": 16,
        },
        "finite_inputs_only": True,
        "rank_invariant": True,
        "geometry": {
            "hidden": [ROWS, HIDDEN],
            "gate_weight": [PROJECTION, HIDDEN],
            "up_weight": [PROJECTION, HIDDEN],
            "down_weight": [HIDDEN, PROJECTION],
            "routed": [ROWS, HIDDEN],
            "reduction_peers": 3,
            "dtype": DTYPE,
            "byte_order": BYTE_ORDER,
        },
        "epochs": epochs,
        "ordered_epoch_hashes_sha256": sha256_bytes(
            canonical_json_bytes([entry["epoch_sha256"] for entry in epochs])
        ),
        "pre_actions": {action: False for action in PRE_ACTIONS},
    }
    manifest["manifest_sha256"] = fixture_manifest_digest(manifest)
    return manifest


@functools.lru_cache(maxsize=1)
def _canonical_manifest_json() -> bytes:
    return canonical_json_bytes(_build_manifest())


def frozen_fixture_manifest() -> dict[str, Any]:
    return json.loads(_canonical_manifest_json())


def validate_fixture_manifest(manifest: dict[str, Any]) -> None:
    require(
        canonical_json_bytes(manifest) == _canonical_manifest_json(),
        "fixture manifest is not the canonical finite corpus",
    )


def _require_nvme_mount(path: Path) -> None:
    completed = subprocess.run(
        ["findmnt", "--noheadings", "--output", "SOURCE,FSTYPE", "--target", str(path)],
        text=True,
        capture_output=True,
        check=False,
    )
    require(
        completed.returncode == 0
        and [NVME_SOURCE, NVME_FSTYPE]
        in [line.split() for line in completed.stdout.splitlines()],
        "path is not required NVMe/ext4",
    )


def require_nvme_artifact_path(
    path: Path, *, suffix: str | None = None, must_exist: bool = False
) -> Path:
    root = ARTIFACT_ROOT_LITERAL
    require(
        root.exists()
        and root.is_dir()
        and not root.is_symlink()
        and path.is_absolute(),
        "invalid artifact root/path",
    )
    require(suffix is None or path.suffix == suffix, "artifact suffix drift")
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise RuntimeError("artifact path escapes NVMe root") from error
    require(
        relative.parts and all(part not in {"", ".", ".."} for part in relative.parts),
        "invalid artifact relative path",
    )
    _require_nvme_mount(root)
    current, resolved_root = root, root.resolve(strict=True)
    for part in relative.parts:
        current /= part
        if current.exists() or current.is_symlink():
            require(
                not current.is_symlink()
                and current.resolve(strict=True).is_relative_to(resolved_root),
                "symlink/artifact escape",
            )
    if must_exist:
        require(
            path.exists() and not path.is_symlink(),
            "required artifact absent/symlinked",
        )
        _require_nvme_mount(path.resolve(strict=True))
    return path


def exclusive_json(path: Path, value: dict[str, Any]) -> None:
    require_nvme_artifact_path(path, suffix=".json")
    root, relative = (
        ARTIFACT_ROOT_LITERAL,
        path.relative_to(ARTIFACT_ROOT_LITERAL).parts,
    )
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    directory_fd = root_fd
    try:
        for part in relative[:-1]:
            try:
                os.mkdir(part, 0o755, dir_fd=directory_fd)
            except FileExistsError:
                pass
            next_fd = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory_fd
            )
            if directory_fd != root_fd:
                os.close(directory_fd)
            directory_fd = next_fd
        _require_nvme_mount(path.parent)
        output_fd = os.open(
            relative[-1],
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o644,
            dir_fd=directory_fd,
        )
        try:
            write_all(output_fd, canonical_json_bytes(value) + b"\n")
            os.fsync(output_fd)
        finally:
            os.close(output_fd)
        os.fsync(directory_fd)
    finally:
        if directory_fd != root_fd:
            os.close(directory_fd)
        os.close(root_fd)


def _strict(value: dict[str, Any], keys: set[str], name: str) -> None:
    require(set(value) == keys, f"{name} has missing/unrecognized fields")


def _tool_records(hashes: dict[str, str]) -> dict[str, Any]:
    return {
        name: {
            "path": TOOL_PATHS[name],
            "sha256": hashes[name],
            "state": TOOL_STATES[name],
        }
        for name in TOOL_PATHS
    }


def expected_environment(output_root: str) -> dict[str, str]:
    runtime = f"{output_root}/runtime"
    return {
        "ACTIVE_REQUESTS": "1",
        "DP": "1",
        "DRAFT_FLASH_DEPTH": "7",
        "EP": "4",
        "HF_HOME": f"{runtime}/cache/huggingface",
        "HF_HUB_OFFLINE": "1",
        "HOME": f"{runtime}/home",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "MKL_NUM_THREADS": "1",
        "NUMBA_CACHE_DIR": f"{runtime}/cache/numba",
        "OMP_NUM_THREADS": "1",
        "ONEAPI_DEVICE_SELECTOR": "level_zero:0",
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "PP": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": (
            "/home/steve/src/deepseek-v4-vllm-xpu-dspark:"
            "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc"
        ),
        "PYTHONPYCACHEPREFIX": f"{runtime}/cache/pycache",
        "SYCL_CACHE_DIR": f"{runtime}/cache/sycl",
        "TEMP": f"{runtime}/tmp",
        "TMP": f"{runtime}/tmp",
        "TMPDIR": f"{runtime}/tmp",
        "TORCHINDUCTOR_CACHE_DIR": f"{runtime}/cache/torchinductor",
        "TP": "4",
        "TRANSFORMERS_CACHE": f"{runtime}/cache/transformers",
        "TRANSFORMERS_OFFLINE": "1",
        "TRITON_CACHE_DIR": f"{runtime}/cache/triton",
        "VLLM_CACHE_ROOT": f"{runtime}/cache/vllm",
        "VLLM_NO_USAGE_STATS": "1",
        "VLLM_USE_AOT_COMPILE": "0",
        "VLLM_XPU_ENABLE_XPU_GRAPH": "0",
        "VLLM_XPU_EXACT_SPEC_ATTN": "1",
        "VLLM_XPU_FORCE_GRAPH_WITH_COMM": "0",
        "VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE": "0",
        "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1",
        "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH": "0",
        "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM": "0",
        "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": "0",
        "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION": "0",
        "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2": "1",
        "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "1",
        "VLLM_XPU_LAGUNA_M8_REMOTE_ZERO": "0",
        "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE": "1",
        "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "1",
        "VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM": "1",
        "VLLM_XPU_LAGUNA_M8_W1_N_TILE": "64",
        "XDG_CACHE_HOME": f"{runtime}/cache/xdg",
        "XDG_CONFIG_HOME": f"{runtime}/cache/xdg-config",
        "XDG_DATA_HOME": f"{runtime}/cache/xdg-data",
        "XDG_STATE_HOME": f"{runtime}/cache/xdg-state",
        "XPU_GRAPH": "0",
        "ZE_AFFINITY_MASK": "0",
    }


def authorization_template(
    fixture: dict[str, Any],
    *,
    hashes: dict[str, str],
    output_root: str,
    packet_path: str | None = None,
    fixture_path: str | None = None,
) -> dict[str, Any]:
    """Schema-complete synthetic packet; hashes are replaced only at freeze."""
    validate_fixture_manifest(fixture)
    packet_path = packet_path or (
        "/home/steve/llm-optimizations/data/"
        "laguna-s-2.1-shared-gate-m8-stage0-authorization.json"
    )
    fixture_path = fixture_path or str(
        ARTIFACT_ROOT_LITERAL / "authorizations/shared-gate-m8-stage0-fixture.json"
    )
    result_path = f"{output_root}/stage0-result.json"
    adapter_path = f"/home/steve/llm-optimizations/{TOOL_PATHS['runtime_adapter']}"
    runner_path = f"/home/steve/llm-optimizations/{TOOL_PATHS['runtime_runner']}"
    try:
        packet_repo_path = str(
            Path(packet_path).relative_to("/home/steve/llm-optimizations")
        )
    except ValueError as error:
        raise RuntimeError(
            "authorization packet must be inside the main repo"
        ) from error
    return {
        "format": AUTHORIZATION_FORMAT,
        "phase": "stage0",
        "adapter_state": ADAPTER_STATE,
        "packet_path": packet_path,
        "preregistration": {"path": PREREG_PATH, "sha256": PREREG_SHA256},
        "tools": _tool_records(hashes),
        "fixture": {
            "path": fixture_path,
            "file_sha256": hashes["fixture_file"],
            "manifest_sha256": fixture["manifest_sha256"],
            "ordered_epoch_hashes_sha256": fixture["ordered_epoch_hashes_sha256"],
            "epoch_count": EPOCHS,
        },
        "source": {
            "main_commit": hashes["main_commit"],
            "vllm_commit": EXPECTED_VLLM_COMMIT,
            "kernel_commit": EXPECTED_KERNEL_COMMIT,
            "files": {path: hashes[path] for path in SOURCE_PATHS},
        },
        "authorization_tracking": {
            "repository": "/home/steve/llm-optimizations",
            "packet_repo_path": packet_repo_path,
            "tools_commit": hashes["main_commit"],
            "required_commit_shape": "one_clean_auth_only_child",
        },
        "runtime": {
            "xpu_driver": "1.15.38308+1",
            "observed_identity": EXPECTED_RUNTIME_OBSERVED_IDENTITY,
            "eager": True,
            "aot_compile": False,
            "xpu_graph": False,
        },
        "binaries": dict(EXPECTED_BINARY_SHA256),
        "model": {
            "config_path": ("/mnt/fast-ai/llm-models/laguna-s-2.1/int4/config.json"),
            "config_sha256": EXPECTED_MODEL_CONFIG_SHA256,
            "target_revision": "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb",
            "dflash_revision": "5e07c246915c86dc6920fead03d019989224f2ba",
        },
        "device": dict(EXPECTED_CARD0),
        "boot_id": EXPECTED_BOOT_ID,
        "protocol": {
            "physical_card": 0,
            "epochs": EPOCHS,
            "rows": ROWS,
            "gate_geometry": [ROWS, HIDDEN, PROJECTION],
            "target_stack": "TP4_EP4_DP1_PP1_DFlash7_q1",
            "stage_scope": (
                "one_card_actual_forward_primitive_with_simulated_fixed_rank_downstream"
            ),
            "timing_allowed": False,
        },
        "argv": [
            "/home/steve/.venvs/deepseek-v4-xpu/bin/python",
            adapter_path,
            "--authorization",
            packet_path,
            "--fixture",
            fixture_path,
            "--result",
            result_path,
        ],
        "runner_argv": [
            runner_path,
            "--authorization",
            packet_path,
            "--fixture",
            fixture_path,
            "--output-root",
            output_root,
        ],
        "environment": expected_environment(output_root),
        "storage": {
            "artifact_root": str(ARTIFACT_ROOT_LITERAL),
            "source": NVME_SOURCE,
            "fstype": NVME_FSTYPE,
            "output_root": output_root,
            "result_path": result_path,
            "packet_path": packet_path,
            "fixture_path": fixture_path,
            "runtime_root": f"{output_root}/runtime",
            "usb_allowed": False,
        },
        "pre_actions": {action: False for action in PRE_ACTIONS},
    }


def validate_authorization(packet: dict[str, Any], fixture: dict[str, Any]) -> None:
    validate_fixture_manifest(fixture)
    _strict(
        packet,
        {
            "format",
            "phase",
            "adapter_state",
            "packet_path",
            "preregistration",
            "tools",
            "fixture",
            "source",
            "authorization_tracking",
            "runtime",
            "binaries",
            "model",
            "device",
            "boot_id",
            "protocol",
            "argv",
            "runner_argv",
            "environment",
            "storage",
            "pre_actions",
        },
        "authorization",
    )
    require(
        packet["format"] == AUTHORIZATION_FORMAT
        and packet["phase"] == "stage0"
        and packet["adapter_state"] == ADAPTER_STATE,
        "authorization phase/adapter drift",
    )
    require(
        packet["preregistration"]
        == {
            "path": PREREG_PATH,
            "sha256": PREREG_SHA256,
        },
        "preregistration SHA drift",
    )
    _strict(packet["tools"], set(TOOL_PATHS), "tool identities")
    for name, record in packet["tools"].items():
        _strict(record, {"path", "sha256", "state"}, f"tool {name}")
        require(
            record["path"] == TOOL_PATHS[name]
            and is_sha256(record["sha256"])
            and record["state"] == TOOL_STATES[name],
            "tool identity drift",
        )
    fixture_identity = packet["fixture"]
    _strict(
        fixture_identity,
        {
            "path",
            "file_sha256",
            "manifest_sha256",
            "ordered_epoch_hashes_sha256",
            "epoch_count",
        },
        "fixture identity",
    )
    require(
        is_sha256(fixture_identity["file_sha256"])
        and fixture_identity["manifest_sha256"] == fixture["manifest_sha256"]
        and fixture_identity["ordered_epoch_hashes_sha256"]
        == fixture["ordered_epoch_hashes_sha256"]
        and fixture_identity["epoch_count"] == EPOCHS,
        "fixture linkage drift",
    )
    source = packet["source"]
    _strict(
        source,
        {"main_commit", "vllm_commit", "kernel_commit", "files"},
        "source identity",
    )
    require(
        is_commit(source["main_commit"])
        and source["vllm_commit"] == EXPECTED_VLLM_COMMIT
        and source["kernel_commit"] == EXPECTED_KERNEL_COMMIT
        and is_commit(source["vllm_commit"])
        and is_commit(source["kernel_commit"]),
        "source commit drift",
    )
    require(
        set(source["files"]) == set(SOURCE_PATHS)
        and all(is_sha256(value) for value in source["files"].values()),
        "source file hash drift",
    )
    tracking = packet["authorization_tracking"]
    try:
        packet_repo_path = str(
            Path(packet["packet_path"]).relative_to("/home/steve/llm-optimizations")
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError(
            "authorization packet must be inside the main repo"
        ) from error
    require(
        tracking
        == {
            "repository": "/home/steve/llm-optimizations",
            "packet_repo_path": packet_repo_path,
            "tools_commit": source["main_commit"],
            "required_commit_shape": "one_clean_auth_only_child",
        },
        "authorization tracking drift",
    )
    require(
        packet["runtime"]
        == {
            "xpu_driver": "1.15.38308+1",
            "observed_identity": EXPECTED_RUNTIME_OBSERVED_IDENTITY,
            "eager": True,
            "aot_compile": False,
            "xpu_graph": False,
        }
        and packet["binaries"] == EXPECTED_BINARY_SHA256,
        "runtime/binary drift",
    )
    require(
        packet["model"]
        == {
            "config_path": ("/mnt/fast-ai/llm-models/laguna-s-2.1/int4/config.json"),
            "config_sha256": EXPECTED_MODEL_CONFIG_SHA256,
            "target_revision": "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb",
            "dflash_revision": "5e07c246915c86dc6920fead03d019989224f2ba",
        },
        "model drift",
    )
    storage = packet["storage"]
    expected_storage = {
        "artifact_root": str(ARTIFACT_ROOT_LITERAL),
        "source": NVME_SOURCE,
        "fstype": NVME_FSTYPE,
        "output_root": storage.get("output_root"),
        "result_path": f"{storage.get('output_root')}/stage0-result.json",
        "packet_path": packet["packet_path"],
        "fixture_path": fixture_identity["path"],
        "runtime_root": f"{storage.get('output_root')}/runtime",
        "usb_allowed": False,
    }
    require(storage == expected_storage, "storage key/identity drift")
    require_nvme_artifact_path(Path(storage["output_root"]))
    require_nvme_artifact_path(Path(fixture_identity["path"]), suffix=".json")
    packet_path = Path(packet["packet_path"])
    require(
        packet_path.is_absolute()
        and packet_path.suffix == ".json"
        and packet_path.resolve(strict=False).is_relative_to(
            Path("/home/steve/llm-optimizations").resolve()
        ),
        "packet path is not tracked in the main repository",
    )
    _require_nvme_mount(packet_path.parent)
    require(
        packet["device"] == EXPECTED_CARD0
        and packet["boot_id"] == EXPECTED_BOOT_ID
        and packet["protocol"]
        == {
            "physical_card": 0,
            "epochs": EPOCHS,
            "rows": ROWS,
            "gate_geometry": [ROWS, HIDDEN, PROJECTION],
            "target_stack": "TP4_EP4_DP1_PP1_DFlash7_q1",
            "stage_scope": (
                "one_card_actual_forward_primitive_with_simulated_fixed_rank_downstream"
            ),
            "timing_allowed": False,
        }
        and packet["environment"] == expected_environment(storage["output_root"]),
        "device/boot/protocol/environment drift",
    )
    adapter_path = f"/home/steve/llm-optimizations/{TOOL_PATHS['runtime_adapter']}"
    expected_argv = [
        "/home/steve/.venvs/deepseek-v4-xpu/bin/python",
        adapter_path,
        "--authorization",
        packet["packet_path"],
        "--fixture",
        fixture_identity["path"],
        "--result",
        storage["result_path"],
    ]
    runner_path = f"/home/steve/llm-optimizations/{TOOL_PATHS['runtime_runner']}"
    expected_runner_argv = [
        runner_path,
        "--authorization",
        packet["packet_path"],
        "--fixture",
        fixture_identity["path"],
        "--output-root",
        storage["output_root"],
    ]
    require(
        packet["argv"] == expected_argv
        and packet["runner_argv"] == expected_runner_argv
        and packet["pre_actions"] == {action: False for action in PRE_ACTIONS},
        "argv/action escalation",
    )


def packet_digest(packet: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(packet))


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def frozen_hashes(fixture_path: Path) -> dict[str, str]:
    """Compute an authorization identity only from clean frozen checkouts."""
    main_repo = Path("/home/steve/llm-optimizations")
    vllm_repo = Path("/home/steve/src/deepseek-v4-vllm-xpu-dspark")
    kernel_repo = Path("/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc")
    for repo, expected_commit in (
        (vllm_repo, EXPECTED_VLLM_COMMIT),
        (kernel_repo, EXPECTED_KERNEL_COMMIT),
    ):
        require(
            _git(repo, "status", "--porcelain=v1", "--untracked-files=all") == ""
            and _git(repo, "rev-parse", "HEAD") == expected_commit,
            f"source checkout is not frozen: {repo}",
        )
    require(
        _git(main_repo, "status", "--porcelain=v1", "--untracked-files=all") == "",
        "main tooling checkout is not clean",
    )
    require(
        Path("/proc/sys/kernel/random/boot_id").read_text().strip() == EXPECTED_BOOT_ID,
        "boot changed before authorization freeze",
    )
    require_nvme_artifact_path(fixture_path, suffix=".json", must_exist=True)
    hashes = {
        name: sha256_file(main_repo / relative) for name, relative in TOOL_PATHS.items()
    }
    hashes.update(
        {relative: sha256_file(vllm_repo / relative) for relative in SOURCE_PATHS}
    )
    hashes["fixture_file"] = sha256_file(fixture_path)
    hashes["main_commit"] = _git(main_repo, "rev-parse", "HEAD")
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--emit-fixtures", type=Path)
    mode.add_argument("--print-authorization", action="store_true")
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    manifest = frozen_fixture_manifest()
    validate_fixture_manifest(manifest)
    if args.emit_fixtures is not None:
        require(
            args.fixture is None and args.output_root is None,
            "fixture emission accepts no authorization arguments",
        )
        exclusive_json(args.emit_fixtures, manifest)
        return 0
    require(
        args.fixture is not None and args.output_root is not None,
        "authorization printing requires --fixture and --output-root",
    )
    require(not args.output_root.exists(), "authorized output root already exists")
    fixture = json.loads(args.fixture.read_text())
    validate_fixture_manifest(fixture)
    require(fixture == manifest, "fixture file differs from frozen generator")
    hashes = frozen_hashes(args.fixture)
    packet = authorization_template(
        fixture,
        hashes=hashes,
        output_root=str(args.output_root),
        fixture_path=str(args.fixture),
    )
    validate_authorization(packet, fixture)
    print(canonical_json_bytes(packet).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

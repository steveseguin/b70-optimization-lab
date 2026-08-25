#!/usr/bin/env python3
"""Bounded same-binary Qwen3.6 Q8 TP1 SYCL-graph parent sentinel.

The default mode is inert. ``--check`` performs CPU-only artifact and DSO
checks. Only ``--execute`` with the exact acknowledgement can run the GPU0
compute gate and the graph-off/graph-cache8 deterministic canary pair.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from typing import Any, Iterator, Mapping, Sequence


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
MANIFEST = LANE / "data/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-prereg.json"
MODEL_VERIFIER = REPO / "scripts/verify-neural-download-model.py"
MODEL_VERIFIER_SHA256 = "f9fbe5968e4bcd3437bb7cdf64ce215968e8958bc935ec8b4c8e76a6d24f84b2"
PROTECTED = REPO / "experiments/qwen38-27b-b70/data/2026-08-23-qwen38-current-main-overlay-manifest.json"
PROTECTED_SHA256 = "4eb3eeb81e40099a64ba0444743074e6b044295ff566c1abc11d864902abb454"

CAMPAIGN_ID = "qwen36-q8-f16-tp1-graph-sentinel-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"
RUN_ROOT = Path("/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-graph-sentinel-20260825-r1")
MODEL = Path("/mnt/usb-models/models/qwen36-27b-q8-gguf/Qwen3.6-27B-Q8_0.gguf")
BINARY = Path("/home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp/bin/llama-cli")
CMAKE_CACHE = Path("/home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp/CMakeCache.txt")
BUILD_NINJA = Path("/home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp/build.ninja")
MODEL_SIZE = 28595763424
MODEL_SHA256 = "f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce"
MODEL_VIEW_TIMEOUT_SECONDS = 1200
BINARY_SIZE = 662784
BINARY_SHA256 = "6d38f7c31e7c5b7ca7299c8b38dd31c356d86e0514bd406546c789eca7b73dcc"
CMAKE_CACHE_SHA256 = "0930be75442696207b47bcaff3f0f19e2630b8e201a128659d903eba71070aab"
BUILD_NINJA_SHA256 = "7c4ef3c5c9323ea778e816a5b4bb2fc15bd3fcdd1655565d6711ab84f0fb57af"

GPU0_RENDER_LINK = Path("/dev/dri/by-path/pci-0000:23:00.0-render")
COMPUTE_PYTHON = Path("/home/steve/.venvs/vllm-xpu/bin/python")
COMPUTE_PYTHON_REALPATH = Path(
    "/home/steve/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12"
)
COMPUTE_PYTHON_SHA256 = "202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8"
TORCH_METADATA = Path(
    "/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/"
    "torch-2.11.0+xpu.dist-info/METADATA"
)
TORCH_METADATA_SHA256 = "8650a25aeacc3d62c590121d7b6c6e627dbd0ab21ead03951347cb657aed6587"
TORCH_LIBRARY_PATH = "/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib"

CANONICAL_LOCKS = [
    "/run/lock/muse-glimmer-gpu-exclusive.lock",
    "/tmp/b70-benchmark.lock",
    "/tmp/b70-gpu0.lock",
    "/run/user/1000/qwen36-b70-gpu-leases/gpu0.lock",
]
UNSAFE_GRAPH_VARIABLES = (
    "SYCL_GRAPH_FORCE_NATIVE_RECORDING",
    "GGML_SYCL_GRAPH_RECORD_QUEUE",
    "GGML_SYCL_GRAPH_REPLAY_NO_UPDATE",
)
REJECTED_EXACT = {"LD_LIBRARY_PATH", "LIBRARY_PATH", *UNSAFE_GRAPH_VARIABLES}
REJECTED_EXACT.update(
    {
        "LD_PRELOAD", "LD_AUDIT", "PYTHONPATH", "PYTHONHOME",
        "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    }
)
REJECTED_PREFIXES = (
    "GIT_",
    "GGML_", "LLAMA_", "ONEAPI_", "SYCL_", "UR_", "ZE_", "ZES_",
    "XPU_", "CCL_", "ONECCL_", "FI_", "OMP_", "KMP_", "MKL_",
)
PACKET_PATHS = (
    "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-prereg.json",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/notes/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-preregistration.md",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q8-f16-tp1-graph-parent-sentinel-r1.py",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/test_qwen36_q8_f16_tp1_graph_parent_sentinel.py",
)
CONTROL_ENV = {
    "PATH": "/usr/bin:/bin",
    "HOME": "/tmp",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_TERMINAL_PROMPT": "0",
}
LLAMA_EXECUTABLES = frozenset(
    {"llama-bench", "llama-batched-bench", "llama-server", "llama-cli"}
)
VLLM_COMMS = frozenset({"VLLM::EngineCore", "VLLM::EngineCor"})

ONEAPI_LIBRARY_PATH = ":".join(
    (
        "/opt/intel/oneapi/tcm/1.5/lib",
        "/opt/intel/oneapi/umf/1.1/lib",
        "/opt/intel/oneapi/tcm/1.5/env/../lib",
        "/opt/intel/oneapi/tbb/2023.0/env/../lib/intel64/gcc4.8",
        "/opt/intel/oneapi/pti/1.0/lib",
        "/opt/intel/oneapi/mkl/2026.0/lib",
        "/opt/intel/oneapi/dnnl/2026.0/lib",
        "/opt/intel/oneapi/debugger/2026.0/opt/debugger/lib",
        "/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib",
        "/opt/intel/oneapi/compiler/2026.0/lib",
    )
)
BASE_ENV = {
    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "LD_LIBRARY_PATH": ONEAPI_LIBRARY_PATH,
    "ONEAPI_DEVICE_SELECTOR": "level_zero:*",
    "ZE_AFFINITY_MASK": "0",
    "ZES_ENABLE_SYSMAN": "1",
    "UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS": "1",
    "SYCL_CACHE_PERSISTENT": "0",
    "GGML_SYCL_ENABLE_DNN": "1",
    "GGML_SYCL_ENABLE_OPT": "1",
    "GGML_SYCL_ENABLE_VMM": "1",
    "GGML_SYCL_FUSE_MMVQ_ADD": "0",
    "GGML_SYCL_FUSE_MMVQ_ADD_RMS_Q8": "0",
    "GGML_SYCL_FUSE_SWIGLU_Q8": "0",
    "GGML_SYCL_FUSE_SSM_CONV_SILU": "0",
    "GGML_SYCL_FUSE_SSM_CONV_CACHE": "0",
    "GGML_SYCL_FUSE_SSM_CONV_QK_NORM": "0",
    "GGML_SYCL_FUSE_GDN_CACHE": "0",
    "GGML_SYCL_FUSE_GDN_RAW_GATES": "0",
    "GGML_SYCL_FUSE_GDN_EPILOGUE": "0",
    "GGML_SYCL_CYCLE_TIMING": "0",
    "GGML_SYCL_OP_TIMING": "0",
    "GGML_SYCL_Q4_0_MMVQ_SIMD4": "0",
    "GGML_SYCL_XE2_Q4_M6_FFN": "0",
    "GGML_SYCL_XE2_Q4_M6_PACK_LIMIT": "0",
    "GGML_SYCL_XE2_Q4_M6_PACK_CACHE": "",
    "GGML_SYCL_XE2_Q4_M6_COMPARE": "0",
    "GGML_SYCL_XE2_Q4_M6_GATE_UP": "0",
    "GGML_SYCL_XE2_GDN_QKVZAB": "0",
    "GGML_SYCL_XE2_Q6_M6_TOP1": "0",
    "GGML_SYCL_XE2_Q6_TARGET_M6_TOP1": "0",
    "GGML_SYCL_XE2_Q6_TARGET_M6_TOP1_SHADOW": "0",
    "LLAMA_MTP_DEVICE_UNROLL": "0",
    "LLAMA_MTP_CYCLE_TIMING": "0",
    "LLAMA_DFLASH_CYCLE_TIMING": "0",
    "LLAMA_DFLASH_FUSED_TOP1": "0",
    "LLAMA_DFLASH_TARGET_VERIFY_TOP1_COMPARE": "0",
    "LLAMA_DFLASH_TARGET_VERIFY_TOP1_FORCE_READ_FAIL": "0",
    "LLAMA_DFLASH_TOP1_FORCE_READ_FAIL": "0",
}

PROMPT = (
    "Write a concise deterministic paragraph explaining why checksum-pinned "
    "A/B tests isolate one runtime variable."
)
COMMON_ARGV = (
    str(BINARY), "-m", str(MODEL), "-dev", "SYCL0", "-ngl", "99",
    "-sm", "none", "-c", "2048", "-n", "64", "-b", "512", "-ub",
    "512", "-fa", "on", "-ctk", "f16", "-ctv", "f16", "-t", "16",
    "--poll", "50", "--seed", "42", "--temp", "0", "--ignore-eos",
    "--no-conversation", "--no-display-prompt", "--simple-io",
    "--no-warmup", "--prompt", PROMPT,
)
COMPUTE_CODE = """
import torch
assert torch.xpu.is_available()
assert torch.xpu.device_count() == 1
torch.xpu.set_device(0)
x = torch.ones((1024, 1024), device="xpu")
y = float((x + 1).sum().cpu().item())
torch.xpu.synchronize()
assert y == 2097152.0
print("device_count 1")
print("ok 2097152.0")
""".strip()

SUMMARY_RE = re.compile(
    r"\[SYCL-GRAPH\] summary device=(?P<device>\d+) "
    r"requested=(?P<requested>\d+) compatibility_rejected=(?P<compatibility_rejected>\d+) "
    r"device_unsupported=(?P<device_unsupported>\d+) cache_entries=(?P<cache_entries>\d+) "
    r"cache_limit=(?P<cache_limit>\d+) cache_hit=(?P<cache_hit>\d+) "
    r"cache_miss=(?P<cache_miss>\d+) cache_full=(?P<cache_full>\d+) "
    r"direct_replay=(?P<direct_replay>\d+) recorded=(?P<recorded>\d+) "
    r"created=(?P<created>\d+) updated=(?P<updated>\d+) "
    r"recreated=(?P<recreated>\d+) replayed=(?P<replayed>\d+)"
)


class GateError(RuntimeError):
    """A frozen campaign contract was not satisfied."""


class CampaignInterrupted(GateError):
    """The parent received SIGINT or SIGTERM during a bounded campaign."""


class ProcessCleanupError(GateError):
    """A child process group could not be proven empty after TERM/KILL."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot load JSON: {path}") from exc
    if not isinstance(value, dict):
        raise GateError(f"expected JSON object: {path}")
    return value


def create_json(path: Path, value: Any) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
    except FileExistsError as exc:
        raise GateError(f"refusing to overwrite: {path}") from exc


def verify_artifact(path: Path, size: int | None, digest: str, label: str) -> None:
    if not path.is_file():
        raise GateError(f"missing {label}: {path}")
    if size is not None and path.stat().st_size != size:
        raise GateError(f"{label} size changed: {path.stat().st_size}")
    observed = sha256_file(path)
    if observed != digest:
        raise GateError(f"{label} SHA-256 changed: {observed}")


def validate_manifest(value: Mapping[str, Any]) -> None:
    selectors = value.get("selectors") or {}
    model = value.get("model") or {}
    runtime = value.get("runtime") or {}
    canary = value.get("canary") or {}
    lifecycle = value.get("lifecycle") or {}
    interpretation = value.get("interpretation") or {}
    compute = value.get("gpu_compute_gate") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-graph-parent-sentinel-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and selectors.get("revision") == "qwen3.6-27b"
        and selectors.get("artifact_id") == "qwen36-27b-unsloth-q8-0-82d411a"
        and selectors.get("quantization") == "Q8_0"
        and selectors.get("tp") == 1
        and selectors.get("mtp") == 0
        and selectors.get("kv") == "f16"
        and selectors.get("graph_comparison") == ["off-cache0", "on-cache8"]
        and model.get("path") == str(MODEL)
        and model.get("size_bytes") == MODEL_SIZE
        and model.get("sha256") == MODEL_SHA256
        and model.get("repository") == "unsloth/Qwen3.6-27B-GGUF"
        and model.get("revision") == "82d411acf4a06cfb8d9b073a5211bf410bfc29bf"
        and model.get("artifact_last_change_commit")
        == "9e3417c2ce78c6214c8be9cb7a8b0927b1be2c8b"
        and model.get("embedded_mtp_capability") is False
        and model.get("direct_and_ordinary_must_match") is True
        and model.get("views_coherent_required") is True
        and runtime.get("thin_launcher", {}).get("path") == str(BINARY)
        and runtime.get("thin_launcher", {}).get("size_bytes") == BINARY_SIZE
        and runtime.get("thin_launcher", {}).get("sha256") == BINARY_SHA256
        and runtime.get("cmake_cache")
        == {
            "path": str(CMAKE_CACHE), "sha256": CMAKE_CACHE_SHA256,
            "required_fragment": "GGML_SYCL_GRAPH:BOOL=ON",
        }
        and runtime.get("build_ninja")
        == {
            "path": str(BUILD_NINJA), "sha256": BUILD_NINJA_SHA256,
            "required_fragment": "-DGGML_SYCL_GRAPH",
        }
        and runtime.get("build_root") == str(BINARY.parents[1])
        and runtime.get("source_provenance", {}).get("repository")
        == "/home/steve/src/llama.cpp"
        and runtime.get("source_provenance", {}).get("recorded_head")
        == "e3546c7948e3af463d0b401e6421d5a4c2faf565"
        and runtime.get("source_provenance", {}).get("tree_classification")
        == "historical-protected-dirty-build"
        and tuple(canary.get("common_argv") or ()) == COMMON_ARGV
        and canary.get("control_environment")
        == {"GGML_SYCL_ENABLE_GRAPH": "0", "GGML_SYCL_GRAPH_CACHE_SIZE": "0"}
        and canary.get("candidate_environment")
        == {"GGML_SYCL_ENABLE_GRAPH": "1", "GGML_SYCL_GRAPH_CACHE_SIZE": "8"}
        and tuple(canary.get("unsafe_variables_must_be_unset") or ())
        == UNSAFE_GRAPH_VARIABLES
        and compute.get("physical_card") == 0
        and compute.get("pci_bdf") == "0000:23:00.0"
        and compute.get("render_node") == str(GPU0_RENDER_LINK)
        and compute.get("ze_affinity_mask") == "0"
        and compute.get("python") == str(COMPUTE_PYTHON)
        and compute.get("python_realpath") == str(COMPUTE_PYTHON_REALPATH)
        and compute.get("python_sha256") == COMPUTE_PYTHON_SHA256
        and compute.get("torch_metadata") == str(TORCH_METADATA)
        and compute.get("torch_metadata_sha256") == TORCH_METADATA_SHA256
        and lifecycle.get("output_root") == str(RUN_ROOT)
        and lifecycle.get("output_fstype") == "ext4"
        and lifecycle.get("exact_ack") == ACK
        and lifecycle.get("arm_timeout_seconds") == 900
        and lifecycle.get("compute_timeout_seconds") == 40
        and lifecycle.get("model_view_timeout_seconds")
        == MODEL_VIEW_TIMEOUT_SECONDS
        and lifecycle.get("term_grace_seconds") == 10
        and lifecycle.get("requires_clean_pushed_main") is True
        and lifecycle.get("requires_no_server_or_container") is True
        and lifecycle.get("required_locks") == CANONICAL_LOCKS
        and lifecycle.get("reject_inherited_exact")
        == [
            "LD_LIBRARY_PATH", "LIBRARY_PATH", "LD_PRELOAD", "LD_AUDIT",
            "PYTHONPATH", "PYTHONHOME", "GIT_*",
        ]
        and lifecycle.get("artifacts_are_create_only") is True
        and lifecycle.get("hard_process_group_timeout") == "TERM then KILL"
        and lifecycle.get("terminal_receipt_required") is True
        and lifecycle.get("cleanup_required") is True
        and lifecycle.get("signal_cleanup_required") is True
        and lifecycle.get("packet_and_artifact_postflight_required") is True
        and interpretation.get("classification") == "parent-sentinel-only"
        and interpretation.get("seven_cell_expansion_authorized") is False
        and interpretation.get("site_publication_authorized") is False
        and interpretation.get("record_or_submission_authorized") is False
        and interpretation.get("speed_measurement_or_floor") is None
        and interpretation.get("historical_featured_speeds_are_immutable") is True
        and interpretation.get("protected_overlay_manifest")
        == str(PROTECTED.relative_to(REPO))
        and interpretation.get("protected_overlay_manifest_sha256") == PROTECTED_SHA256
    ):
        raise GateError("graph parent-sentinel manifest invariant failed")
    libraries = runtime.get("effective_shared_libraries")
    if not isinstance(libraries, list) or len(libraries) != 34:
        raise GateError("exactly 34 effective shared-library rows are required")
    sonames = [row.get("soname") for row in libraries if isinstance(row, dict)]
    if len(sonames) != 34 or len(set(sonames)) != 34:
        raise GateError("effective shared-library rows are malformed or duplicated")


def reject_inherited_environment(environment: Mapping[str, str]) -> list[str]:
    return sorted(
        name for name in environment
        if name in REJECTED_EXACT or name.startswith(REJECTED_PREFIXES)
    )


def parse_ldd_output(output: str) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for raw in output.splitlines():
        line = raw.strip()
        if not line or line.startswith("linux-vdso"):
            continue
        if "not found" in line:
            raise GateError(f"unresolved shared library: {line}")
        if " => " in line:
            soname, right = line.split(" => ", 1)
            path = right.split(" ", 1)[0]
        elif line.startswith("/"):
            path = line.split(" ", 1)[0]
            soname = Path(path).name
        else:
            raise GateError(f"unparsed ldd row: {line}")
        canonical = str(Path(path).resolve(strict=True))
        if soname in resolved:
            raise GateError(f"duplicate ldd soname: {soname}")
        resolved[soname] = canonical
    return resolved


def base_environment(root: Path) -> dict[str, str]:
    value = dict(BASE_ENV)
    value.update(
        {
            "HOME": str(root / "home"),
            "XDG_CACHE_HOME": str(root / "xdg-cache"),
            "SYCL_CACHE_DIR": str(root / "sycl-cache"),
            "TMPDIR": str(root / "tmp"),
        }
    )
    for name in UNSAFE_GRAPH_VARIABLES:
        value.pop(name, None)
    return value


def verify_libraries(manifest: Mapping[str, Any]) -> list[dict[str, str]]:
    environment = base_environment(RUN_ROOT / "static")
    result = subprocess.run(
        ["/usr/bin/ldd", str(BINARY)], env=environment, text=True,
        capture_output=True, check=False, timeout=30,
    )
    if result.returncode != 0:
        raise GateError(f"ldd failed: {(result.stderr or result.stdout).strip()[:500]}")
    observed = parse_ldd_output(result.stdout)
    expected_rows = manifest["runtime"]["effective_shared_libraries"]
    expected = {row["soname"]: row for row in expected_rows}
    if set(observed) != set(expected):
        raise GateError(
            "effective DSO set changed: "
            f"added={sorted(set(observed) - set(expected))}, "
            f"missing={sorted(set(expected) - set(observed))}"
        )
    receipt: list[dict[str, str]] = []
    for soname in sorted(expected):
        path = Path(observed[soname])
        row = expected[soname]
        if str(path) != row["realpath"]:
            raise GateError(f"effective path changed for {soname}: {path}")
        digest = sha256_file(path)
        if digest != row["sha256"]:
            raise GateError(f"effective DSO changed for {soname}: {digest}")
        receipt.append({"soname": soname, "realpath": str(path), "sha256": digest})
    return receipt


def static_check() -> tuple[dict[str, Any], list[dict[str, str]]]:
    manifest = load_json(MANIFEST)
    validate_manifest(manifest)
    verify_artifact(BINARY, BINARY_SIZE, BINARY_SHA256, "llama-cli thin launcher")
    verify_artifact(CMAKE_CACHE, None, CMAKE_CACHE_SHA256, "CMake cache")
    verify_artifact(BUILD_NINJA, None, BUILD_NINJA_SHA256, "build.ninja")
    if "GGML_SYCL_GRAPH:BOOL=ON" not in CMAKE_CACHE.read_text(encoding="utf-8"):
        raise GateError("CMake cache does not prove GGML_SYCL_GRAPH=ON")
    if "-DGGML_SYCL_GRAPH" not in BUILD_NINJA.read_text(encoding="utf-8"):
        raise GateError("build.ninja does not prove the graph compiler define")
    verify_artifact(MODEL_VERIFIER, None, MODEL_VERIFIER_SHA256, "model verifier")
    verify_artifact(PROTECTED, None, PROTECTED_SHA256, "protected speed manifest")
    verify_artifact(COMPUTE_PYTHON_REALPATH, None, COMPUTE_PYTHON_SHA256, "compute Python")
    if COMPUTE_PYTHON.resolve(strict=True) != COMPUTE_PYTHON_REALPATH:
        raise GateError("compute Python realpath changed")
    verify_artifact(TORCH_METADATA, None, TORCH_METADATA_SHA256, "Torch metadata")
    if not MODEL.is_file() or MODEL.stat().st_size != MODEL_SIZE:
        raise GateError("model is missing or its size changed")
    libraries = verify_libraries(manifest)
    return manifest, libraries


def git_output(*args: str) -> str:
    return subprocess.check_output(
        ["/usr/bin/git", "-C", str(REPO), *args],
        text=True, env=CONTROL_ENV, timeout=30,
    ).strip()


def packet_blobs() -> dict[str, str]:
    result: dict[str, str] = {}
    for relative in PACKET_PATHS:
        row = git_output("ls-tree", "HEAD", "--", relative)
        if not row or "\t" not in row:
            raise GateError(f"packet path is not tracked at HEAD: {relative}")
        metadata, observed_path = row.split("\t", 1)
        mode, kind, blob = metadata.split()
        if mode != "100644" or kind != "blob" or observed_path != relative:
            raise GateError(f"unexpected packet tree identity: {row}")
        if git_output("hash-object", relative) != blob:
            raise GateError(f"packet worktree bytes differ from HEAD: {relative}")
        result[relative] = blob
    return result


def verify_clean_pushed_main(
    *, expected_head: str | None = None,
    expected_packet_blobs: Mapping[str, str] | None = None,
) -> tuple[str, dict[str, str]]:
    if git_output("branch", "--show-current") != "main":
        raise GateError("lab repository must be on main")
    if git_output("status", "--porcelain=v1", "--untracked-files=all"):
        raise GateError("lab repository must be completely clean")
    head = git_output("rev-parse", "HEAD")
    if expected_head is not None and head != expected_head:
        raise GateError(f"lab HEAD changed during campaign: {head}")
    if git_output("rev-parse", "origin/main") != head:
        raise GateError("lab main is not pushed to origin/main")
    remote = subprocess.check_output(
        ["/usr/bin/timeout", "30s", "/usr/bin/git", "-C", str(REPO),
         "ls-remote", "--exit-code", "origin", "refs/heads/main"],
        text=True, env=CONTROL_ENV,
    ).split()[0]
    if remote != head:
        raise GateError("lab main differs from live origin/main")
    blobs = packet_blobs()
    if expected_packet_blobs is not None and blobs != dict(expected_packet_blobs):
        raise GateError("packet blob identity changed during campaign")
    return head, blobs


def nearest_existing(path: Path) -> Path:
    current = path
    while not current.exists():
        if current.parent == current:
            raise GateError(f"no existing ancestor for {path}")
        current = current.parent
    return current


def verify_fresh_ext4() -> None:
    if RUN_ROOT.exists():
        raise GateError(f"create-only run root already exists: {RUN_ROOT}")
    parent = nearest_existing(RUN_ROOT.parent)
    fstype = subprocess.check_output(
        ["/usr/bin/findmnt", "-n", "-o", "FSTYPE", "-T", str(parent)],
        text=True, env=CONTROL_ENV, timeout=30,
    ).strip()
    if fstype != "ext4":
        raise GateError(f"run root must resolve to ext4, got {fstype!r}")


@contextlib.contextmanager
def campaign_locks() -> Iterator[list[str]]:
    handles = []
    try:
        for value in CANONICAL_LOCKS:
            path = Path(value)
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = path.open("a+b")
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise GateError(f"campaign lock is held: {path}") from exc
            handles.append(handle)
        yield list(CANONICAL_LOCKS)
    finally:
        for handle in reversed(handles):
            handle.close()


def sudo_docker_ps() -> str:
    password_path = Path("/home/steve/SUDOPASSWORD.txt")
    if not password_path.is_file():
        raise GateError("sudo password file is unavailable for container scan")
    with password_path.open("rb") as password:
        result = subprocess.run(
            ["/usr/bin/sudo", "-S", "-p", "", "/usr/bin/docker", "ps", "-q"],
            env=CONTROL_ENV, stdin=password,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=30,
        )
    if result.returncode != 0:
        raise GateError("Docker running-container scan failed")
    return result.stdout.decode("utf-8", errors="strict").strip()


def is_active_model_process(comm: str, argv: Sequence[str]) -> bool:
    argv0 = Path(argv[0]).name if argv else ""
    if comm in LLAMA_EXECUTABLES or argv0 in LLAMA_EXECUTABLES:
        return True
    if comm in VLLM_COMMS or argv0 in VLLM_COMMS:
        return True
    if argv0 == "vllm" and len(argv) > 1 and argv[1] == "serve":
        return True
    return argv0.startswith("python") and any(
        item == "-m" and index + 1 < len(argv)
        and argv[index + 1].startswith("vllm.entrypoints")
        for index, item in enumerate(argv)
    )


def active_model_processes() -> list[str]:
    matches = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            comm = (entry / "comm").read_text(encoding="utf-8").strip()
            raw = (entry / "cmdline").read_bytes()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        argv = [part.decode(errors="replace") for part in raw.split(b"\0") if part]
        if is_active_model_process(comm, argv):
            matches.append(f"{entry.name}:{comm}")
    return matches


def require_idle() -> None:
    processes = active_model_processes()
    if processes:
        raise GateError("active model processes: " + ", ".join(processes))
    if sudo_docker_ps():
        raise GateError("a Docker container is running")
    if not GPU0_RENDER_LINK.is_symlink() or GPU0_RENDER_LINK.resolve().name != "renderD130":
        raise GateError("GPU0 render-node mapping changed")
    result = subprocess.run(
        ["/usr/bin/fuser", str(GPU0_RENDER_LINK.resolve())],
        env=CONTROL_ENV, capture_output=True, check=False,
        timeout=30,
    )
    if result.returncode == 0:
        raise GateError("GPU0 render node is owned by another process")
    if result.returncode != 1:
        raise GateError("GPU0 render-node owner scan failed")


def process_group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def stop_process_group(process: subprocess.Popen[bytes], grace_seconds: float) -> dict[str, Any]:
    receipt: dict[str, Any] = {"term_sent": False, "kill_sent": False}
    blocked = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
    try:
        process.poll()
        if process_group_exists(process.pid):
            try:
                os.killpg(process.pid, signal.SIGTERM)
                receipt["term_sent"] = True
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + grace_seconds
        while process_group_exists(process.pid) and time.monotonic() < deadline:
            process.poll()
            time.sleep(0.05)
        if process_group_exists(process.pid):
            try:
                os.killpg(process.pid, signal.SIGKILL)
                receipt["kill_sent"] = True
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + grace_seconds
        while process_group_exists(process.pid) and time.monotonic() < deadline:
            process.poll()
            time.sleep(0.05)
        try:
            process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired as exc:
            raise ProcessCleanupError(
                f"process-group leader {process.pid} survived KILL"
            ) from exc
        receipt["process_group_empty"] = not process_group_exists(process.pid)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, blocked)
    if not receipt["process_group_empty"]:
        raise ProcessCleanupError(
            f"process group {process.pid} survived TERM/KILL cleanup"
        )
    return receipt


@contextlib.contextmanager
def caught_campaign_signals() -> Iterator[None]:
    previous: dict[int, Any] = {}
    interrupted = False

    def interrupt(signum: int, _frame: Any) -> None:
        nonlocal interrupted
        if interrupted:
            return
        interrupted = True
        for value in (signal.SIGINT, signal.SIGTERM):
            signal.signal(value, signal.SIG_IGN)
        raise CampaignInterrupted(f"campaign interrupted by signal {signum}")

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.getsignal(signum)
        signal.signal(signum, interrupt)
    try:
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def run_process_group(
    *, name: str, argv: Sequence[str], environment: Mapping[str, str],
    stdout_path: Path, stderr_path: Path, timeout_seconds: float,
    grace_seconds: float = 10,
) -> dict[str, Any]:
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    begin = time.monotonic()
    timed_out = False
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        process = subprocess.Popen(
            list(argv), env=dict(environment), cwd=REPO, stdout=stdout, stderr=stderr,
            start_new_session=True,
        )
        cleanup = {"term_sent": False, "kill_sent": False, "process_group_empty": False}
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            cleanup = stop_process_group(process, grace_seconds)
    receipt = {
        "name": name,
        "pid": process.pid,
        "pgid": process.pid,
        "started_utc": started,
        "elapsed_seconds": time.monotonic() - begin,
        "return_code": process.returncode,
        "timed_out": timed_out,
        **cleanup,
    }
    if timed_out:
        raise GateError(f"{name} timed out; process group was cleaned")
    if process.returncode != 0:
        raise GateError(f"{name} exited {process.returncode}")
    return receipt


def model_verifier_environment(root: Path) -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(root / "home"),
        "XDG_CACHE_HOME": str(root / "xdg-cache"),
        "TMPDIR": str(root / "tmp"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
    }


def verify_model_views(root: Path) -> dict[str, Any]:
    root.mkdir(exist_ok=False)
    for name in ("home", "xdg-cache", "tmp"):
        (root / name).mkdir(exist_ok=False)
    verifier_input = root / "model-manifest.json"
    verifier_result = root / "result.json"
    create_json(
        verifier_input,
        {
            "format": "neural-download-model-manifest-v1",
            "repository": "unsloth/Qwen3.6-27B-GGUF",
            "revision": "82d411acf4a06cfb8d9b073a5211bf410bfc29bf",
            "files": [{"name": MODEL.name, "sha256": MODEL_SHA256}],
        },
    )
    receipt = run_process_group(
        name="direct-then-ordinary-model-verifier",
        argv=[
            "/usr/bin/python3", "-I", "-B", str(MODEL_VERIFIER),
            str(verifier_input), str(MODEL.parent), "--json", str(verifier_result),
        ],
        environment=model_verifier_environment(root),
        stdout_path=root / "stdout.log",
        stderr_path=root / "stderr.log",
        timeout_seconds=MODEL_VIEW_TIMEOUT_SECONDS,
    )
    value = load_json(verifier_result)
    files = value.get("files")
    if value.get("status") != "verified" or not isinstance(files, list) or len(files) != 1:
        raise GateError("direct/ordinary model verifier did not certify one exact file")
    row = files[0]
    if not isinstance(row, dict) or not (
        row.get("name") == MODEL.name
        and row.get("expected") == MODEL_SHA256
        and row.get("direct_sha256") == MODEL_SHA256
        and row.get("ordinary_sha256") == MODEL_SHA256
        and row.get("direct_ok") is True
        and row.get("ordinary_ok") is True
        and row.get("views_coherent") is True
        and row.get("ok") is True
        and row.get("direct_mode") in {"odirect", "dd-iflag-direct"}
    ):
        raise GateError("direct/ordinary model verifier result violated the frozen contract")
    create_json(root / "process-receipt.json", receipt)
    return {
        "status": "verified",
        "method_order": [row["direct_mode"], "ordinary-unbuffered"],
        "direct_sha256": row["direct_sha256"],
        "ordinary_sha256": row["ordinary_sha256"],
        "views_coherent": True,
        "verifier": str(MODEL_VERIFIER),
        "verifier_sha256": MODEL_VERIFIER_SHA256,
        "timeout_seconds": MODEL_VIEW_TIMEOUT_SECONDS,
        "process_receipt": receipt,
    }


def compute_environment(root: Path) -> dict[str, str]:
    return {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": str(root / "home"), "XDG_CACHE_HOME": str(root / "xdg-cache"),
        "TMPDIR": str(root / "tmp"), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
        "LD_LIBRARY_PATH": TORCH_LIBRARY_PATH, "ZE_AFFINITY_MASK": "0",
        "PYTHONNOUSERSITE": "1", "PYTHONSAFEPATH": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def run_compute_gate(root: Path) -> dict[str, Any]:
    for name in ("home", "xdg-cache", "tmp"):
        (root / name).mkdir(parents=True, exist_ok=False)
    receipt = run_process_group(
        name="gpu0-compute-gate",
        argv=[str(COMPUTE_PYTHON), "-I", "-B", "-c", COMPUTE_CODE],
        environment=compute_environment(root),
        stdout_path=root / "stdout.log", stderr_path=root / "stderr.log",
        timeout_seconds=40,
    )
    output = (root / "stdout.log").read_text(encoding="utf-8")
    if output != "device_count 1\nok 2097152.0\n":
        raise GateError(f"GPU0 compute oracle changed: {output!r}")
    receipt.update(
        {"passed": True, "physical_card": 0, "ze_affinity_mask": "0",
         "oracle": "sum(x+1)==2097152.0", "visible_xpu_count": 1}
    )
    create_json(root / "receipt.json", receipt)
    return receipt


def arm_environment(root: Path, graph: str, cache: str) -> dict[str, str]:
    value = base_environment(root)
    value["GGML_SYCL_ENABLE_GRAPH"] = graph
    value["GGML_SYCL_GRAPH_CACHE_SIZE"] = cache
    if any(name in value for name in UNSAFE_GRAPH_VARIABLES):
        raise GateError("unsafe native/record-queue/no-update graph variable leaked")
    return value


def prepare_arm_root(root: Path) -> None:
    root.mkdir(exist_ok=False)
    for name in ("home", "xdg-cache", "sycl-cache", "tmp"):
        (root / name).mkdir(exist_ok=False)


def parse_graph_summary(text: str) -> dict[str, int]:
    matches = list(SUMMARY_RE.finditer(text))
    if len(matches) != 1:
        raise GateError(f"expected exactly one SYCL graph summary, got {len(matches)}")
    return {name: int(value) for name, value in matches[0].groupdict().items()}


def validate_control_graph_log(text: str) -> dict[str, int]:
    for marker in ("GGML_SYCL_GRAPH: yes", "GGML_SYCL_ENABLE_GRAPH: 0", "GGML_SYCL_GRAPH_CACHE_SIZE: 0"):
        if marker not in text:
            raise GateError(f"control graph-off marker absent: {marker}")
    summary = parse_graph_summary(text)
    forbidden = (
        "[SYCL-GRAPH] requested", "[SYCL-GRAPH] recording_entered",
        "[SYCL-GRAPH] replayed", "[SYCL-GRAPH] direct_replay",
    )
    leaked = [marker for marker in forbidden if marker in text]
    if leaked:
        raise GateError(f"graph-off control emitted graph-action markers: {leaked}")
    if summary["device"] != 0:
        raise GateError(f"graph-off control summary used the wrong device: {summary}")
    if any(summary[name] != 0 for name in (
        "requested", "compatibility_rejected", "device_unsupported", "cache_entries",
        "cache_limit", "cache_hit", "cache_miss", "cache_full", "direct_replay",
        "recorded", "created", "updated", "recreated", "replayed",
    )):
        raise GateError(f"graph-off control executed graph work: {summary}")
    return summary


def validate_candidate_graph_log(text: str) -> dict[str, int]:
    required_markers = (
        "GGML_SYCL_GRAPH: yes", "GGML_SYCL_ENABLE_GRAPH: 1",
        "GGML_SYCL_GRAPH_CACHE_SIZE: 8", "[SYCL-GRAPH] summary",
    )
    missing = [marker for marker in required_markers if marker not in text]
    if missing:
        raise GateError(f"candidate graph evidence absent: {missing}")
    positive_markers = (
        r"\[SYCL-GRAPH\] requested device=0 count=[1-9][0-9]*\b",
        r"\[SYCL-GRAPH\] recording_entered device=0 count=[1-9][0-9]*\b",
        r"\[SYCL-GRAPH\] replayed device=0 count=[1-9][0-9]*\b",
        r"\[SYCL-GRAPH\] direct_replay device=0 count=[1-9][0-9]*\b",
    )
    absent_positive = [pattern for pattern in positive_markers if re.search(pattern, text) is None]
    if absent_positive:
        raise GateError(f"candidate positive graph-action evidence absent: {absent_positive}")
    summary = parse_graph_summary(text)
    if summary["device"] != 0:
        raise GateError(f"candidate graph summary used the wrong device: {summary}")
    if summary["compatibility_rejected"] != 0:
        raise GateError(f"candidate graph compatibility rejection: {summary}")
    if summary["device_unsupported"] != 0 or summary["cache_limit"] != 8:
        raise GateError(f"candidate graph device/cache contract failed: {summary}")
    if any(summary[name] <= 0 for name in (
        "requested", "cache_hit", "direct_replay", "recorded", "created", "replayed",
    )):
        raise GateError(f"candidate requested graph but did not record/replay/cache-hit: {summary}")
    return summary


def run_arm(root: Path, name: str, graph: str, cache: str) -> dict[str, Any]:
    prepare_arm_root(root)
    environment = arm_environment(root, graph, cache)
    create_json(
        root / "identity.json",
        {
            "arm": name, "binary": str(BINARY), "binary_sha256": BINARY_SHA256,
            "model": str(MODEL), "model_sha256": MODEL_SHA256,
            "argv": list(COMMON_ARGV),
            "graph_environment": {
                "GGML_SYCL_ENABLE_GRAPH": graph,
                "GGML_SYCL_GRAPH_CACHE_SIZE": cache,
            },
            "unsafe_graph_variables_present": [
                item for item in UNSAFE_GRAPH_VARIABLES if item in environment
            ],
            "cache_zero_contract": {
                "fresh_process": True, "fresh_arm_local_directories": True,
                "prompt_cache_argument_present": any("prompt-cache" in arg for arg in COMMON_ARGV),
                "response_or_history_reuse": False,
            },
        },
    )
    receipt = run_process_group(
        name=name, argv=COMMON_ARGV, environment=environment,
        stdout_path=root / "output.bin", stderr_path=root / "stderr.log",
        timeout_seconds=900,
    )
    output = (root / "output.bin").read_bytes()
    if not output:
        raise GateError(f"{name} produced empty deterministic output")
    text = (root / "stderr.log").read_text(encoding="utf-8", errors="replace")
    graph_summary = (
        validate_control_graph_log(text) if graph == "0"
        else validate_candidate_graph_log(text)
    )
    receipt.update(
        {
            "passed": True, "output_bytes": len(output),
            "output_sha256": hashlib.sha256(output).hexdigest(),
            "graph_summary": graph_summary, "cache_zero": True,
        }
    )
    create_json(root / "receipt.json", receipt)
    return receipt


def evidence_hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "terminal-receipt.json"
    }


def model_stat_fingerprint() -> dict[str, int]:
    value = MODEL.stat()
    return {
        "device": value.st_dev,
        "inode": value.st_ino,
        "mode": value.st_mode,
        "size_bytes": value.st_size,
        "mtime_ns": value.st_mtime_ns,
    }


def execute(acknowledgement: str) -> dict[str, Any]:
    if acknowledgement != ACK:
        raise GateError(f"exact acknowledgement required: {ACK}")
    inherited = reject_inherited_environment(os.environ)
    if inherited:
        raise GateError("refusing inherited runtime environment: " + ", ".join(inherited))
    repo_head, frozen_packet_blobs = verify_clean_pushed_main()
    verify_fresh_ext4()
    manifest, libraries = static_check()
    frozen_model_stat = model_stat_fingerprint()
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    state = "failed"
    stage = "pre-root"
    error: str | None = None
    cleanup_passed = False
    terminal_signal_mask: set[signal.Signals] | None = None
    control: dict[str, Any] | None = None
    candidate: dict[str, Any] | None = None
    with campaign_locks() as locks:
        try:
            stage = "create-run-root"
            require_idle()
            RUN_ROOT.mkdir(mode=0o700, parents=True, exist_ok=False)
            stage = "model-view-verification"
            model_views = verify_model_views(RUN_ROOT / "model-view-verification")
            create_json(RUN_ROOT / "model-view-verification-receipt.json", model_views)
            create_json(RUN_ROOT / "effective-shared-libraries.json", libraries)
            create_json(
                RUN_ROOT / "campaign-identity.json",
                {
                    "campaign_id": CAMPAIGN_ID, "repo_head": repo_head,
                    "packet_blobs": frozen_packet_blobs,
                    "manifest": str(MANIFEST.relative_to(REPO)),
                    "manifest_snapshot": manifest,
                    "source_provenance_limitation": manifest["runtime"]["source_provenance"]["limitation"],
                },
            )
            stage = "gpu0-compute-gate"
            compute_root = RUN_ROOT / "gpu0-compute-gate"
            compute_root.mkdir(exist_ok=False)
            run_compute_gate(compute_root)
            require_idle()
            stage = "control-graph0-cache0"
            control = run_arm(RUN_ROOT / "control-graph0-cache0", stage, "0", "0")
            require_idle()
            stage = "candidate-graph1-cache8"
            candidate = run_arm(RUN_ROOT / "candidate-graph1-cache8", stage, "1", "8")
            require_idle()
            control_bytes = (RUN_ROOT / "control-graph0-cache0/output.bin").read_bytes()
            candidate_bytes = (RUN_ROOT / "candidate-graph1-cache8/output.bin").read_bytes()
            if control_bytes != candidate_bytes:
                raise GateError("graph-off and graph-cache8 deterministic outputs differ")
            create_json(
                RUN_ROOT / "parity-receipt.json",
                {
                    "passed": True, "exact_output_bytes": True,
                    "cache_zero_both_arms": True,
                    "sha256": hashlib.sha256(control_bytes).hexdigest(),
                    "control_bytes": len(control_bytes), "candidate_bytes": len(candidate_bytes),
                    "same_binary": True,
                    "control_binary_sha256": BINARY_SHA256,
                    "candidate_binary_sha256": BINARY_SHA256,
                    "interpretation": "output parity only; this is not a seven-cell context curve",
                },
            )
            stage = "packet-and-artifact-postflight"
            post_head, post_packet_blobs = verify_clean_pushed_main(
                expected_head=repo_head,
                expected_packet_blobs=frozen_packet_blobs,
            )
            post_manifest, post_libraries = static_check()
            if post_manifest != manifest or post_libraries != libraries:
                raise GateError("manifest or effective artifact closure changed during campaign")
            if model_stat_fingerprint() != frozen_model_stat:
                raise GateError("model filesystem identity changed during campaign")
            require_idle()
            create_json(
                RUN_ROOT / "postflight-seal.json",
                {
                    "passed": True,
                    "repo_head": post_head,
                    "packet_blobs": post_packet_blobs,
                    "effective_shared_libraries": post_libraries,
                    "model_stat_fingerprint": frozen_model_stat,
                    "protected_overlay_manifest_sha256": PROTECTED_SHA256,
                    "binary_sha256": BINARY_SHA256,
                },
            )
            cleanup_passed = True
            state = "passed-parent-sentinel-only"
            stage = "complete"
            terminal_signal_mask = signal.pthread_sigmask(
                signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM}
            )
        except BaseException as exc:
            terminal_signal_mask = signal.pthread_sigmask(
                signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM}
            )
            error = str(exc)
            cleanup_failure = isinstance(exc, ProcessCleanupError)
            if RUN_ROOT.exists():
                try:
                    require_idle()
                    cleanup_passed = not cleanup_failure
                except Exception as cleanup_exc:
                    cleanup_passed = False
                    error = f"{error}; cleanup gate: {cleanup_exc}"
            else:
                signal.pthread_sigmask(signal.SIG_SETMASK, terminal_signal_mask)
                raise GateError(error or "pre-root campaign failure") from exc
        try:
            terminal = {
                "schema": "neural.download.qwen36-llama-graph-parent-sentinel-terminal.v1",
                "campaign_id": CAMPAIGN_ID, "terminal": True, "state": state,
                "stage": stage, "started_utc": started,
                "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "repo_head": repo_head, "run_root": str(RUN_ROOT), "locks": locks,
                "cleanup_passed": cleanup_passed, "error": error,
                "binary_sha256": BINARY_SHA256, "model_sha256": MODEL_SHA256,
                "control": control, "candidate": candidate,
                "seven_cell_expansion_authorized": False,
                "site_publication_authorized": False,
                "record_or_submission_authorized": False,
                "speed_measurement_or_floor": None,
                "historical_featured_speeds_are_immutable": True,
                "source_provenance_limitation": manifest["runtime"]["source_provenance"]["limitation"],
                "evidence_sha256": evidence_hashes(RUN_ROOT),
            }
            create_json(RUN_ROOT / "terminal-receipt.json", terminal)
        finally:
            assert terminal_signal_mask is not None
            signal.pthread_sigmask(signal.SIG_SETMASK, terminal_signal_mask)
    if state != "passed-parent-sentinel-only":
        raise GateError(error or "parent sentinel failed")
    return terminal


def plan(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "mode": "plan", "status": "preregistered-not-launched",
        "campaign_id": CAMPAIGN_ID, "default_is_inert": True,
        "exact_ack": ACK, "output_root": str(RUN_ROOT),
        "arms": manifest["selectors"]["graph_comparison"],
        "parent_sentinel_only": True, "seven_cell_expansion_authorized": False,
        "writes_performed": False,
    }


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="run CPU-only frozen checks")
    mode.add_argument("--execute", action="store_true", help="run the bounded GPU sentinel")
    parser.add_argument("--ack", default="", help="exact execution acknowledgement")
    return parser


def main() -> int:
    args = make_parser().parse_args()
    try:
        manifest = load_json(MANIFEST)
        validate_manifest(manifest)
        if args.execute:
            with caught_campaign_signals():
                result = execute(args.ack)
        elif args.check:
            _, libraries = static_check()
            result = {
                **plan(manifest), "mode": "check", "status": "passed",
                "effective_shared_library_count": len(libraries),
            }
        else:
            result = plan(manifest)
    except (GateError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

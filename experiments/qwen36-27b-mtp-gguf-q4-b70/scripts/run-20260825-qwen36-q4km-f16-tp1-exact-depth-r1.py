#!/usr/bin/env python3
"""Run the frozen Qwen3.6 Q4_K_M F16-KV TP1 exact-depth curve.

This packet deliberately reuses the already-tested Qwen3.8 llama-bench
lifecycle adapter as checksum-pinned infrastructure. Model bytes, selectors,
arguments, receipts, and interpretation remain Qwen3.6-specific.
"""

from __future__ import annotations

import copy
import contextlib
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterator


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
MANIFEST = LANE / "data/2026-08-25-qwen36-q4km-f16-tp1-exact-depth-prereg.json"
BASE_MANIFEST = (
    REPO
    / "experiments/qwen38-27b-b70/data/"
    "2026-08-25-qwen38-q4kxl-q8-tp1-exact-depth-prereg.json"
)
BASE_ADAPTER = (
    REPO
    / "experiments/qwen38-27b-b70/scripts/"
    "run-20260825-qwen38-q4kxl-q8-tp1-exact-depth-r1.py"
)
BASE_MANIFEST_SHA256 = (
    "86775bd326675c7d66d27695d2b9ec8bf8bdd320181efffac01eefc4bf572af4"
)
BASE_ADAPTER_SHA256 = (
    "c30e9cee51bd4f5083f4ab57efca794fa89caec2a0e0e1aaf427b02c00b78875"
)
CAMPAIGN_ID = "qwen36-q4km-f16-tp1-exact-depth-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"
DEPTHS = [0, 2048, 4096, 8192, 16384, 24576, 32768]
CANONICAL_LOCKS = [
    "/run/lock/muse-glimmer-gpu-exclusive.lock",
    "/tmp/b70-benchmark.lock",
    "/tmp/b70-gpu0.lock",
    "/run/user/1000/qwen36-b70-gpu-leases/gpu0.lock",
]


def _load_module():
    spec = importlib.util.spec_from_file_location("qwen36_q4km_exact_depth_base", BASE_ADAPTER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import lifecycle adapter: {BASE_ADAPTER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASE = _load_module()
ORIGINAL_STATIC_CHECK = BASE.static_check
ORIGINAL_WRITE_JSON_EXCLUSIVE = BASE.write_json_exclusive


def load_manifest() -> dict[str, Any]:
    try:
        value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BASE.GateError(f"invalid Qwen3.6 campaign manifest: {exc}") from exc
    if BASE.sha256_file(BASE_MANIFEST) != BASE_MANIFEST_SHA256:
        raise BASE.GateError("referenced runtime manifest changed")
    if BASE.sha256_file(BASE_ADAPTER) != BASE_ADAPTER_SHA256:
        raise BASE.GateError("referenced lifecycle adapter changed")
    runtime_manifest = json.loads(BASE_MANIFEST.read_text(encoding="utf-8"))
    expanded = copy.deepcopy(value)
    expanded["runtime"] = copy.deepcopy(runtime_manifest["runtime"])
    expanded["environment"] = copy.deepcopy(runtime_manifest["environment"])
    return expanded


def validate_manifest(value: dict[str, Any]) -> None:
    selectors = value.get("selectors") or {}
    model = value.get("model") or {}
    runtime = value.get("runtime") or {}
    lifecycle = value.get("lifecycle") or {}
    interpretation = value.get("interpretation") or {}
    reference = value.get("runtime_reference") or {}
    expected_argv = [
        runtime.get("binary", {}).get("path"),
        "-m", model.get("path"), "-dev", "SYCL0", "-ngl", "99",
        "-sm", "layer", "-p", "2048", "-n", "128", "-d",
        "0,2048,4096,8192,16384,24576,32768", "-b", "2048",
        "-ub", "512", "-fa", "on", "-ctk", "f16", "-ctv", "f16",
        "-t", "16", "--poll", "50", "-r", "5", "-o", "json",
    ]
    if not (
        value.get("schema") == "neural.download.qwen36-llama-exact-depth-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and selectors.get("revision") == "qwen3.6-27b"
        and selectors.get("artifact_id")
        == "qwen36-27b-unsloth-mtp-q4-k-m-5cb35eb"
        and selectors.get("quantization") == "Q4_K_M"
        and selectors.get("tp") == 1
        and selectors.get("mtp") == 0
        and selectors.get("graph_mode") == "off"
        and selectors.get("kv") == "f16"
        and selectors.get("active_context_tokens") == DEPTHS
        and model.get("revision") == "5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace"
        and model.get("size_bytes") == 17106773120
        and model.get("sha256")
        == "a7cbd3ecc0e3f9b333edee61ae66bc87ed713c5d49587a8355814722ed329e0f"
        and runtime.get("source_head") == BASE.SOURCE_HEAD
        and reference.get("manifest_sha256") == BASE_MANIFEST_SHA256
        and reference.get("adapter_sha256") == BASE_ADAPTER_SHA256
        and value.get("argv") == expected_argv
        and value.get("environment", {}).get("GGML_SYCL_ENABLE_GRAPH") == "0"
        and lifecycle.get("exact_ack") == ACK
        and lifecycle.get("output_fstype") == "ext4"
        and lifecycle.get("required_locks") == CANONICAL_LOCKS
        and lifecycle.get("artifacts_are_create_only") is True
        and interpretation.get("speed_floor") is None
        and interpretation.get("new_quality_gate") is False
        and interpretation.get("cell_gain_on_pass") == 7
        and interpretation.get("historical_featured_speeds_are_immutable") is True
        and interpretation.get("cross_revision_or_quantization_transfer_allowed")
        is False
    ):
        raise BASE.GateError("Qwen3.6 campaign manifest invariant failed")
    libraries = runtime.get("effective_shared_libraries")
    if not isinstance(libraries, list) or len(libraries) != 32:
        raise BASE.GateError("exactly 32 effective shared-library rows are required")


def static_check() -> dict[str, Any]:
    manifest = load_manifest()
    validate_manifest(manifest)
    if BASE.sha256_file(BASE.PARSER) != BASE.EXPECTED_PARSER_SHA256:
        raise BASE.GateError("exact-depth parser changed")
    if BASE.sha256_file(BASE.PROTECTED) != BASE.EXPECTED_PROTECTED_SHA256:
        raise BASE.GateError("protected historical speed manifest changed")
    return manifest


def active_model_processes() -> list[str]:
    """Reject every known llama/vLLM benchmark or serving executable."""
    matches: list[str] = []
    exact_comms = {"llama-bench", "llama-batched-bench", "llama-server"}
    cmdline_markers = (
        "llama-bench",
        "llama-batched-bench",
        "llama-server",
        "vllm.entrypoints",
        "vllm serve",
        "VLLM::EngineCore",
    )
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            comm = (entry / "comm").read_text(encoding="utf-8").strip()
            cmdline = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                errors="replace"
            )
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if comm in exact_comms or any(marker in cmdline for marker in cmdline_markers):
            matches.append(f"{entry.name}:{comm}")
    return matches


@contextlib.contextmanager
def campaign_locks() -> Iterator[None]:
    """Own the host-wide and both legacy/current GPU0 campaign locks."""
    paths = [Path(value) for value in CANONICAL_LOCKS]
    handles = []
    try:
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = path.open("a+b")
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise BASE.GateError(f"campaign lock is held: {path}") from exc
            handles.append(handle)
        yield
    finally:
        for handle in reversed(handles):
            handle.close()


def metadata(manifest: dict[str, Any], libraries: list[list[str]]) -> dict[str, Any]:
    return {
        "schema": "llama-bench-exact-depth-metadata-v1",
        "receipt_id": CAMPAIGN_ID,
        "declared_depths": DEPTHS,
        "binary": {
            **manifest["runtime"]["binary"],
            "source_head": BASE.SOURCE_HEAD,
            "effective_shared_libraries": libraries,
        },
        "model": manifest["model"],
        "argv": manifest["argv"],
        "env": manifest["environment"],
        "cell_selectors": {
            key: item
            for key, item in manifest["selectors"].items()
            if key not in {"active_context_tokens", "graph_mode"}
        },
        "graph": {
            "requested": False,
            "capture": {"count": 0, "source": "GGML_SYCL_ENABLE_GRAPH=0"},
            "replay": {"count": 0, "source": "GGML_SYCL_ENABLE_GRAPH=0"},
        },
    }


def write_json_exclusive(path: Path, value: Any) -> None:
    if path.name == "terminal-receipt.json" and isinstance(value, dict):
        value = copy.deepcopy(value)
        value["schema"] = "neural.download.qwen36-llama-exact-depth-terminal.v1"
    ORIGINAL_WRITE_JSON_EXCLUSIVE(path, value)


BASE.MANIFEST = MANIFEST
BASE.CAMPAIGN_ID = CAMPAIGN_ID
BASE.ACK = ACK
BASE.load_manifest = load_manifest
BASE.validate_manifest = validate_manifest
BASE.static_check = static_check
BASE.metadata = metadata
BASE.write_json_exclusive = write_json_exclusive
BASE.active_model_processes = active_model_processes
BASE.campaign_locks = campaign_locks


if __name__ == "__main__":
    raise SystemExit(BASE.main())

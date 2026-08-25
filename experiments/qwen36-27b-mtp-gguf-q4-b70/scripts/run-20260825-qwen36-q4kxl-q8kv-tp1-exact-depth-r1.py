#!/usr/bin/env python3
"""Run the frozen Qwen3.6 UD-Q4_K_XL q8_0-KV TP1 exact-depth curve."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
MANIFEST = LANE / "data/2026-08-25-qwen36-q4kxl-q8kv-tp1-exact-depth-prereg.json"
REFERENCE_MANIFEST = (
    LANE / "data/2026-08-25-qwen36-q4kxl-f16-tp1-exact-depth-prereg.json"
)
REFERENCE_ADAPTER = (
    LANE / "scripts/run-20260825-qwen36-q4kxl-f16-tp1-exact-depth-r1.py"
)
REFERENCE_MANIFEST_SHA256 = (
    "c5ee61e18dde93bba58edb0f03784dbc1972a82811e6b2275366c412a849fd04"
)
REFERENCE_ADAPTER_SHA256 = (
    "144485f2bc33b0daf03419c73836081cb3dba4b211da0b4812c93c859e0837be"
)
CAMPAIGN_ID = "qwen36-q4kxl-q8kv-tp1-exact-depth-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"
DEPTHS = [0, 2048, 4096, 8192, 16384, 24576, 32768]
CANONICAL_LOCKS = [
    "/run/lock/muse-glimmer-gpu-exclusive.lock",
    "/tmp/b70-benchmark.lock",
    "/tmp/b70-gpu0.lock",
    "/run/user/1000/qwen36-b70-gpu-leases/gpu0.lock",
]


def _load_reference():
    spec = importlib.util.spec_from_file_location(
        "qwen36_q4kxl_q8kv_reference", REFERENCE_ADAPTER
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import lifecycle adapter: {REFERENCE_ADAPTER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


REFERENCE = _load_reference()
ENGINE = REFERENCE.BASE
ORIGINAL_REFERENCE_LOAD_MANIFEST = REFERENCE.load_manifest
ORIGINAL_WRITE_JSON_EXCLUSIVE = ENGINE.write_json_exclusive


def load_manifest() -> dict[str, Any]:
    try:
        value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ENGINE.GateError(f"invalid Qwen3.6 q8_0 campaign manifest: {exc}") from exc
    if ENGINE.sha256_file(REFERENCE_MANIFEST) != REFERENCE_MANIFEST_SHA256:
        raise ENGINE.GateError("referenced Qwen3.6 F16 manifest changed")
    if ENGINE.sha256_file(REFERENCE_ADAPTER) != REFERENCE_ADAPTER_SHA256:
        raise ENGINE.GateError("referenced Qwen3.6 F16 lifecycle adapter changed")
    reference = ORIGINAL_REFERENCE_LOAD_MANIFEST()
    expanded = copy.deepcopy(value)
    expanded["runtime"] = copy.deepcopy(reference["runtime"])
    expanded["environment"] = copy.deepcopy(reference["environment"])
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
        "-ub", "512", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0",
        "-t", "16", "--poll", "50", "-r", "5", "-o", "json",
    ]
    if not (
        value.get("schema") == "neural.download.qwen36-llama-exact-depth-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and selectors.get("revision") == "qwen3.6-27b"
        and selectors.get("artifact_id")
        == "qwen36-27b-unsloth-mtp-ud-q4-k-xl-4085665"
        and selectors.get("quantization") == "UD-Q4_K_XL"
        and selectors.get("tp") == 1
        and selectors.get("mtp") == 0
        and selectors.get("graph_mode") == "off"
        and selectors.get("kv") == "q8_0"
        and selectors.get("active_context_tokens") == DEPTHS
        and model.get("revision") == "5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace"
        and model.get("revision_binding_source")
        == "https://huggingface.co/api/models/unsloth/Qwen3.6-27B-MTP-GGUF/revision/5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace?blobs=true"
        and model.get("size_bytes") == 17909097600
        and model.get("sha256")
        == "4085665ee36d82a672a238a43f0e5643f2f0e39f2d7bd5d373f0ef10ecf53095"
        and runtime.get("source_head") == ENGINE.SOURCE_HEAD
        and reference.get("manifest_sha256") == REFERENCE_MANIFEST_SHA256
        and reference.get("adapter_sha256") == REFERENCE_ADAPTER_SHA256
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
        raise ENGINE.GateError("Qwen3.6 q8_0 campaign manifest invariant failed")
    libraries = runtime.get("effective_shared_libraries")
    if not isinstance(libraries, list) or len(libraries) != 32:
        raise ENGINE.GateError("exactly 32 effective shared-library rows are required")
    if len({row[0] for row in libraries if len(row) == 4}) != 32:
        raise ENGINE.GateError("shared-library inventory is malformed or duplicated")


def static_check() -> dict[str, Any]:
    manifest = load_manifest()
    validate_manifest(manifest)
    if ENGINE.sha256_file(ENGINE.PARSER) != ENGINE.EXPECTED_PARSER_SHA256:
        raise ENGINE.GateError("exact-depth parser changed")
    if ENGINE.sha256_file(ENGINE.PROTECTED) != ENGINE.EXPECTED_PROTECTED_SHA256:
        raise ENGINE.GateError("protected historical speed manifest changed")
    return manifest


def metadata(manifest: dict[str, Any], libraries: list[list[str]]) -> dict[str, Any]:
    return {
        "schema": "llama-bench-exact-depth-metadata-v1",
        "receipt_id": CAMPAIGN_ID,
        "declared_depths": DEPTHS,
        "binary": {
            **manifest["runtime"]["binary"],
            "source_head": ENGINE.SOURCE_HEAD,
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


# Reuse the F16 wrapper's corrected process census and four-lock implementation.
if REFERENCE.CANONICAL_LOCKS != CANONICAL_LOCKS:
    raise RuntimeError("referenced Qwen3.6 lock contract changed")
ENGINE.MANIFEST = MANIFEST
ENGINE.CAMPAIGN_ID = CAMPAIGN_ID
ENGINE.ACK = ACK
ENGINE.load_manifest = load_manifest
ENGINE.validate_manifest = validate_manifest
ENGINE.static_check = static_check
ENGINE.metadata = metadata
ENGINE.write_json_exclusive = write_json_exclusive
ENGINE.active_model_processes = REFERENCE.active_model_processes
ENGINE.campaign_locks = REFERENCE.campaign_locks


if __name__ == "__main__":
    raise SystemExit(ENGINE.main())

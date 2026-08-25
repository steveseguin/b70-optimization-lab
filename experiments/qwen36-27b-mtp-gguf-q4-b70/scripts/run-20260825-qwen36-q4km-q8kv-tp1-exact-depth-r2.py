#!/usr/bin/env python3
"""Run the fresh Qwen3.6 Q4_K_M q8_0-KV exact-depth r2 campaign."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any, Sequence


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
MANIFEST = LANE / "data/2026-08-25-qwen36-q4km-q8kv-tp1-exact-depth-r2-prereg.json"
REFERENCE_MANIFEST = LANE / "data/2026-08-25-qwen36-q4km-q8kv-tp1-exact-depth-prereg.json"
REFERENCE_ADAPTER = LANE / "scripts/run-20260825-qwen36-q4km-q8kv-tp1-exact-depth-r1.py"
REFERENCE_MANIFEST_SHA256 = "043b411ab5d0fae6b508a4e323dfcd73b747be18270c88b5db4ee34a4edad81f"
REFERENCE_ADAPTER_SHA256 = "d1fd544ce257969cd370c6e132da5665396ef9248094deed22e37d933de77b1d"
FAILURE_RECORD = LANE / "data/2026-08-25-qwen36-q4km-q8kv-tp1-exact-depth-r1-failure.json"
FAILURE_RECORD_SHA256 = "e69e497d598102bc71b70224bb9c9cc1f19f5986315f2e9d3835f08c7331d30e"
FAILURE_NOTE = LANE / "notes/2026-08-25-qwen36-q4km-q8kv-tp1-exact-depth-r1-failure.md"
FAILURE_NOTE_SHA256 = "a08b7a41a963c20be1333a1539ce8b0902e56464cbefcabd2400162364b66ff1"
CAMPAIGN_ID = "qwen36-q4km-q8kv-tp1-exact-depth-20260825-r2"
ACK = f"RUN {CAMPAIGN_ID}"
DEPTHS = [0, 2048, 4096, 8192, 16384, 24576, 32768]
CANONICAL_LOCKS = [
    "/run/lock/muse-glimmer-gpu-exclusive.lock",
    "/tmp/b70-benchmark.lock",
    "/tmp/b70-gpu0.lock",
    "/run/user/1000/qwen36-b70-gpu-leases/gpu0.lock",
]
LLAMA_EXECUTABLES = frozenset({"llama-bench", "llama-batched-bench", "llama-server"})
LLAMA_COMMS = LLAMA_EXECUTABLES | {"llama-batched-b"}
VLLM_ENGINE_NAMES = frozenset({"VLLM::EngineCore", "VLLM::EngineCor"})


def _load_reference():
    spec = importlib.util.spec_from_file_location("qwen36_q4km_q8kv_r1_reference", REFERENCE_ADAPTER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import lifecycle adapter: {REFERENCE_ADAPTER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


REFERENCE = _load_reference()
ENGINE = REFERENCE.ENGINE
ORIGINAL_REFERENCE_LOAD_MANIFEST = REFERENCE.load_manifest
ORIGINAL_WRITE_JSON_EXCLUSIVE = ENGINE.write_json_exclusive
ORIGINAL_CAMPAIGN_LOCKS = ENGINE.campaign_locks


def is_active_model_process(comm: str, argv: Sequence[str]) -> bool:
    """Classify executable identity without matching evidence filenames."""
    argv0 = Path(argv[0]).name if argv else ""
    if comm in LLAMA_COMMS or argv0 in LLAMA_EXECUTABLES:
        return True
    if comm in VLLM_ENGINE_NAMES or argv0 in VLLM_ENGINE_NAMES:
        return True
    if argv0 == "vllm" and len(argv) > 1 and argv[1] == "serve":
        return True
    return argv0.startswith("python") and any(
        item == "-m" and index + 1 < len(argv)
        and argv[index + 1].startswith("vllm.entrypoints")
        for index, item in enumerate(argv)
    )


def active_model_processes() -> list[str]:
    matches: list[str] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            comm = (entry / "comm").read_text(encoding="utf-8").strip()
            raw = (entry / "cmdline").read_bytes()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        argv = [item.decode(errors="replace") for item in raw.split(b"\0") if item]
        if is_active_model_process(comm, argv):
            matches.append(f"{entry.name}:{comm}")
    return matches


def load_manifest() -> dict[str, Any]:
    try:
        value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ENGINE.GateError(f"invalid Qwen3.6 r2 campaign manifest: {exc}") from exc
    for path, expected, label in (
        (REFERENCE_MANIFEST, REFERENCE_MANIFEST_SHA256, "r1 manifest"),
        (REFERENCE_ADAPTER, REFERENCE_ADAPTER_SHA256, "r1 adapter"),
        (FAILURE_RECORD, FAILURE_RECORD_SHA256, "r1 failure record"),
        (FAILURE_NOTE, FAILURE_NOTE_SHA256, "r1 failure note"),
    ):
        if ENGINE.sha256_file(path) != expected:
            raise ENGINE.GateError(f"referenced {label} changed")
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
    quarantine = value.get("r1_quarantine") or {}
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
        and selectors.get("artifact_id") == "qwen36-27b-unsloth-mtp-q4-k-m-5cb35eb"
        and selectors.get("quantization") == "Q4_K_M"
        and selectors.get("tp") == 1
        and selectors.get("mtp") == 0
        and selectors.get("graph_mode") == "off"
        and selectors.get("kv") == "q8_0"
        and selectors.get("active_context_tokens") == DEPTHS
        and model.get("sha256") == "a7cbd3ecc0e3f9b333edee61ae66bc87ed713c5d49587a8355814722ed329e0f"
        and runtime.get("source_head") == ENGINE.SOURCE_HEAD
        and reference.get("manifest_sha256") == REFERENCE_MANIFEST_SHA256
        and reference.get("adapter_sha256") == REFERENCE_ADAPTER_SHA256
        and value.get("argv") == expected_argv
        and value.get("environment", {}).get("GGML_SYCL_ENABLE_GRAPH") == "0"
        and lifecycle.get("exact_ack") == ACK
        and lifecycle.get("output_root").endswith("-r2")
        and lifecycle.get("output_fstype") == "ext4"
        and lifecycle.get("required_locks") == CANONICAL_LOCKS
        and lifecycle.get("process_classifier")
        == "exact llama comm/argv0 plus token-aware vLLM EngineCore, Python -m entrypoint, or vllm serve identity"
        and lifecycle.get("artifacts_are_create_only") is True
        and quarantine.get("failure_record_sha256") == FAILURE_RECORD_SHA256
        and quarantine.get("failure_note_sha256") == FAILURE_NOTE_SHA256
        and quarantine.get("raw_row_reuse_allowed") is False
        and quarantine.get("cells_publishable_from_r1") == 0
        and interpretation.get("speed_floor") is None
        and interpretation.get("new_quality_gate") is False
        and interpretation.get("cell_gain_on_pass") == 7
        and interpretation.get("r1_rows_transfer_allowed") is False
    ):
        raise ENGINE.GateError("Qwen3.6 q8_0 r2 manifest invariant failed")
    libraries = runtime.get("effective_shared_libraries")
    if not isinstance(libraries, list) or len(libraries) != 32:
        raise ENGINE.GateError("exactly 32 effective shared-library rows are required")


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
        "binary": {**manifest["runtime"]["binary"], "source_head": ENGINE.SOURCE_HEAD, "effective_shared_libraries": libraries},
        "model": manifest["model"],
        "argv": manifest["argv"],
        "env": manifest["environment"],
        "cell_selectors": {key: item for key, item in manifest["selectors"].items() if key not in {"active_context_tokens", "graph_mode"}},
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
        value["r1_rows_reused"] = False
    ORIGINAL_WRITE_JSON_EXCLUSIVE(path, value)


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
ENGINE.active_model_processes = active_model_processes
ENGINE.campaign_locks = ORIGINAL_CAMPAIGN_LOCKS


if __name__ == "__main__":
    raise SystemExit(ENGINE.main())

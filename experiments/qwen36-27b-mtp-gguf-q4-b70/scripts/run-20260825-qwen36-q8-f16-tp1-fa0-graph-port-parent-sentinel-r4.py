#!/usr/bin/env python3
"""Sealed R4 parent sentinel for the final cache-scaled fa0 graph source."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
R2_SCRIPT = HERE / "run-20260825-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-r2.py"
SPEC = importlib.util.spec_from_file_location("qwen36_fa0_graph_port_r2_lifecycle_for_r4", R2_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import mature lifecycle: {R2_SCRIPT}")
R2 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = R2
SPEC.loader.exec_module(R2)
BASE = R2.BASE
ORIGINAL_LOAD_JSON = R2.ORIGINAL_LOAD_JSON
ORIGINAL_CREATE_JSON = R2.ORIGINAL_CREATE_JSON

OVERLAY = BASE.LANE / "data/2026-08-25-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-r4-prereg.json"
NOTE = BASE.LANE / "notes/2026-08-25-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-r4-preregistration.md"
CAMPAIGN_ID = "qwen36-q8-f16-tp1-fa0-graph-port-sentinel-20260825-r4"
RUN_ROOT = Path("/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-fa0-graph-port-sentinel-20260825-r4")
ACK = f"RUN {CAMPAIGN_ID}"

R2_MANIFEST_REL = "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-r2-prereg.json"
R2_MANIFEST = BASE.REPO / R2_MANIFEST_REL
R2_MANIFEST_SHA256 = "175c59eb9a2a2eb95c45f92a0c20c0bd543279d46a4b0e2051ed745db0093a96"
SOURCE = R2.SOURCE
SOURCE_HEAD = R2.SOURCE_HEAD
SOURCE_PATH_HASHES = {
    "ggml/src/ggml-sycl/common.hpp": "ce4c8541381f9e1043e15b21359c8c828fc17f20c48672afb0c6d646c02b7805",
    "ggml/src/ggml-sycl/ggml-sycl.cpp": "25152136d7e7ff9e96822127f320f08ccb4fa200af607f33afaa05a318cbbd6a",
}
CAPACITY_PATCH_REL = "patches/qwen36-27b-mtp-gguf-q4-b70/llamacpp-fa0-graph-cache-q8-capacity-scaled-r3-20260825.patch"
CAPACITY_PATCH = BASE.REPO / CAPACITY_PATCH_REL
CAPACITY_PATCH_SHA256 = "3def9e5eeb42d9bd1dc4b0c759092572db178651ecafc5255943753bd8b485f6"
CAPACITY_PREREG_REL = "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-fa0-graph-cache-q8-capacity-scaled-r3-prereg.json"
CAPACITY_PREREG_SHA256 = "738349e396d9322136dcdb6995d1d1bc21dfce4f6d58b3ec38d850189b70f334"
CAPACITY_BUILD_REL = "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-fa0-graph-cache-q8-capacity-scaled-r3-build-result.json"
CAPACITY_BUILD_SHA256 = "95c287bf5dddbc1416e331e0dd3395b8e8119aa0072e427f9c87ae0d62f947be"

BUILD_ROOT = R2.BUILD_ROOT
BINARY = R2.BINARY
GRAPH_BACKEND = R2.GRAPH_BACKEND
CMAKE_CACHE = R2.CMAKE_CACHE
MAKEFILE = R2.MAKEFILE
SYCL_FLAGS = R2.SYCL_FLAGS
BINARY_SIZE = 736520
BINARY_SHA256 = "68ab26cf34f821a40afb5a05374360e8343b9b802c927fd0850fcd7bf3c7e1fd"
BACKEND_SIZE = 329322096
BACKEND_SHA256 = "7d03bc06f46f188fd6ecd47034a878a2bd96d20a752a6a0731121176e101c8e2"
CMAKE_CACHE_SHA256 = "39852126a74e193d99fe9ee2a0a2553d6afc9f6ed2b77b7b853bb25dd689d461"
MAKEFILE_SHA256 = "db2b9dcc0296571e4f76b48402649af56376ea81582c49ca0442b9b35070298f"
SYCL_FLAGS_SHA256 = "c52e473c20c9e06f30b5558445d210791e88047fc0dd6e4585f9fa634fd0a727"
SERVER_IMPL_SHA256 = "63dcf154a547aa8611be00625a3c72b190cbdfcdc6a139679ee165c170c93a6b"

PACKET_PATHS = R2.PACKET_PATHS + (
    CAPACITY_PATCH_REL, CAPACITY_PREREG_REL, CAPACITY_BUILD_REL,
    str(OVERLAY.relative_to(BASE.REPO)), str(NOTE.relative_to(BASE.REPO)),
    str(Path(__file__).resolve().relative_to(BASE.REPO)),
    "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/test_qwen36_q8_f16_tp1_fa0_graph_port_parent_sentinel_r4.py",
)


def load_overlay() -> dict[str, Any]:
    return ORIGINAL_LOAD_JSON(OVERLAY)


def validate_overlay(value: Mapping[str, Any]) -> None:
    source = value.get("source_delta") or {}
    runtime = value.get("runtime_delta") or {}
    lifecycle = value.get("lifecycle") or {}
    authority = value.get("authority") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-fa0-graph-port-parent-sentinel-r4-overlay.v1"
        and value.get("state") == "sealed-preregistered-not-launched"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("sealed_r2_base") == {
            "manifest_path": R2_MANIFEST_REL, "manifest_sha256": R2_MANIFEST_SHA256}
        and source == {
            "common_hpp_sha256": SOURCE_PATH_HASHES["ggml/src/ggml-sycl/common.hpp"],
            "ggml_sycl_cpp_sha256": SOURCE_PATH_HASHES["ggml/src/ggml-sycl/ggml-sycl.cpp"],
            "incremental_patch_path": CAPACITY_PATCH_REL,
            "incremental_patch_sha256": CAPACITY_PATCH_SHA256,
            "prereg_path": CAPACITY_PREREG_REL, "prereg_sha256": CAPACITY_PREREG_SHA256,
            "build_result_path": CAPACITY_BUILD_REL, "build_result_sha256": CAPACITY_BUILD_SHA256,
        }
        and runtime.get("llama_cli") == {"size_bytes": BINARY_SIZE, "sha256": BINARY_SHA256}
        and runtime.get("graph_backend") == {"size_bytes": BACKEND_SIZE, "sha256": BACKEND_SHA256}
        and runtime.get("cmake_cache_sha256") == CMAKE_CACHE_SHA256
        and runtime.get("makefile_sha256") == MAKEFILE_SHA256
        and runtime.get("sycl_flags_sha256") == SYCL_FLAGS_SHA256
        and runtime.get("fresh_ldd_closure_count") == 34
        and runtime.get("fresh_ldd_changed_rows") == {
            "libggml-sycl.so.0": BACKEND_SHA256,
            "libllama-server-impl.so": SERVER_IMPL_SHA256,
        }
        and runtime.get("fresh_ldd_unchanged_rows_inherited_from_sealed_r2") == 32
        and lifecycle == {
            "output_root": str(RUN_ROOT), "exact_ack": ACK, "create_only": True,
            "predecessor_roots_immutable": True, "generated_tokens_per_arm": 64,
            "same_binary_arms": ["off-cache0", "on-cache8"],
        }
        and authority == {
            "parent_sentinel_only": True, "curve_authorized": False,
            "site_publication_authorized": False, "speed_claim_authorized": False,
            "quality_claim_authorized": False, "record_or_submission_authorized": False,
            "protected_graph_off_values_may_be_replaced": False,
            "historical_featured_speeds_are_immutable": True,
        }
    ):
        raise BASE.GateError("fa0 graph-port R4 overlay invariant failed")


def synthesize_manifest(r2: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    validate_overlay(overlay)
    value = copy.deepcopy(dict(r2))
    value["schema"] = "neural.download.qwen36-llama-fa0-graph-port-parent-sentinel-r4-runtime.v1"
    value["campaign_id"] = CAMPAIGN_ID
    value["purpose"] = overlay["purpose"]
    value["source"]["post_r4_sha256"] = SOURCE_PATH_HASHES
    value["source"].pop("post_r2_sha256", None)
    value["source"]["capacity_scaled_overlay"] = copy.deepcopy(overlay["source_delta"])
    value["source"]["provenance"] = {
        "classification": "fa0-graph-port-pointer-stable-q8-memo-cache-scaled-final",
        "limitation": "R4 is only a TP1 parent mechanism/parity retry; it grants no curve, site, speed, or replacement authority.",
    }
    value["runtime"]["binary"] = {"path": str(BINARY), "size_bytes": BINARY_SIZE, "sha256": BINARY_SHA256}
    value["runtime"]["graph_backend"] = {"path": str(GRAPH_BACKEND), "size_bytes": BACKEND_SIZE, "sha256": BACKEND_SHA256}
    value["runtime"]["cmake_cache"]["sha256"] = CMAKE_CACHE_SHA256
    value["runtime"]["makefile"]["sha256"] = MAKEFILE_SHA256
    value["runtime"]["sycl_flags"]["sha256"] = SYCL_FLAGS_SHA256
    value["runtime"]["source_provenance"] = copy.deepcopy(value["source"]["provenance"])
    replacements = {
        "libggml-sycl.so.0": BACKEND_SHA256,
        "libllama-server-impl.so": SERVER_IMPL_SHA256,
    }
    seen: set[str] = set()
    for row in value["runtime"]["effective_shared_libraries"]:
        if row["soname"] in replacements:
            row["sha256"] = replacements[row["soname"]]
            seen.add(row["soname"])
    if seen != set(replacements) or len(value["runtime"]["effective_shared_libraries"]) != 34:
        raise BASE.GateError("sealed R2 closure cannot be transformed into audited R4 closure")
    value["lifecycle"]["output_root"] = str(RUN_ROOT)
    value["lifecycle"]["exact_ack"] = ACK
    value["lifecycle"]["predecessor_roots_immutable"] = True
    value["interpretation"]["terminal_pass_state"] = "passed-r4-parent-sentinel-only"
    value["r4_overlay"] = copy.deepcopy(dict(overlay))
    return value


def load_manifest() -> dict[str, Any]:
    return synthesize_manifest(ORIGINAL_LOAD_JSON(R2_MANIFEST), load_overlay())


def validate_manifest(value: Mapping[str, Any]) -> None:
    if dict(value) != load_manifest():
        raise BASE.GateError("R4 synthesized manifest changed outside its sealed overlay")
    if value["runtime"]["source_provenance"] != value["source"]["provenance"]:
        raise BASE.GateError("R4 runtime/source provenance mismatch")
    if value["canary"].get("generated_tokens_per_arm") != 64:
        raise BASE.GateError("R4 must retain both exact 64-token arms")


def git_source(*args: str) -> str:
    return subprocess.check_output(
        ["/usr/bin/git", "-C", str(SOURCE), *args], text=True,
        env=BASE.CONTROL_ENV, timeout=30,
    ).strip()


def verify_source() -> None:
    if git_source("rev-parse", "HEAD") != SOURCE_HEAD:
        raise BASE.GateError("R4 source HEAD changed")
    expected = "\n".join(f" M {path}" for path in SOURCE_PATH_HASHES)
    observed = subprocess.check_output(
        ["/usr/bin/git", "-C", str(SOURCE), "status", "--porcelain=v1", "--untracked-files=all"],
        text=True, env=BASE.CONTROL_ENV, timeout=30,
    ).rstrip("\n")
    if observed != expected:
        raise BASE.GateError("R4 source has non-frozen changes")
    for relative, digest in SOURCE_PATH_HASHES.items():
        BASE.verify_artifact(SOURCE / relative, None, digest, f"R4 source {relative}")
    BASE.verify_artifact(CAPACITY_PATCH, None, CAPACITY_PATCH_SHA256, "capacity-scaled incremental patch")
    BASE.verify_artifact(BASE.REPO / CAPACITY_PREREG_REL, None, CAPACITY_PREREG_SHA256, "capacity preregistration")
    BASE.verify_artifact(BASE.REPO / CAPACITY_BUILD_REL, None, CAPACITY_BUILD_SHA256, "capacity build result")
    result = subprocess.run(
        ["/usr/bin/git", "-C", str(SOURCE), "apply", "--reverse", "--check", str(CAPACITY_PATCH)],
        env=BASE.CONTROL_ENV, capture_output=True, text=True, timeout=30, check=False,
    )
    if result.returncode != 0:
        raise BASE.GateError("capacity-scaled incremental patch is not reverse-applicable")


def verify_build() -> None:
    BASE.verify_artifact(BINARY, BINARY_SIZE, BINARY_SHA256, "R4 llama-cli")
    BASE.verify_artifact(GRAPH_BACKEND, BACKEND_SIZE, BACKEND_SHA256, "R4 graph backend")
    BASE.verify_artifact(CMAKE_CACHE, None, CMAKE_CACHE_SHA256, "R4 CMake cache")
    BASE.verify_artifact(MAKEFILE, None, MAKEFILE_SHA256, "R4 Makefile")
    BASE.verify_artifact(SYCL_FLAGS, None, SYCL_FLAGS_SHA256, "R4 SYCL flags")
    observed = R2.R1.cmake_values(CMAKE_CACHE.read_text(encoding="utf-8"))
    changed = {name: observed.get(name) for name, expected in R2.EXPECTED_CMAKE.items() if observed.get(name) != expected}
    if changed:
        raise BASE.GateError(f"R4 CMake identity changed: {changed}")
    flags = SYCL_FLAGS.read_text(encoding="utf-8")
    if "-DGGML_SYCL_GRAPH" not in flags or "GGML_SYCL_HOST_MEM_FALLBACK" in flags:
        raise BASE.GateError("R4 SYCL compile flags changed")


def static_check() -> tuple[dict[str, Any], list[dict[str, str]]]:
    overlay = load_overlay()
    validate_overlay(overlay)
    BASE.verify_artifact(R2_MANIFEST, None, R2_MANIFEST_SHA256, "sealed R2 identity manifest")
    manifest = synthesize_manifest(ORIGINAL_LOAD_JSON(R2_MANIFEST), overlay)
    validate_manifest(manifest)
    verify_source()
    verify_build()
    BASE.BINARY = BINARY
    BASE.BINARY_SIZE = BINARY_SIZE
    BASE.BINARY_SHA256 = BINARY_SHA256
    BASE.verify_artifact(BASE.MODEL_VERIFIER, None, BASE.MODEL_VERIFIER_SHA256, "model verifier")
    BASE.verify_artifact(BASE.PROTECTED, None, BASE.PROTECTED_SHA256, "protected speed manifest")
    BASE.verify_artifact(BASE.COMPUTE_PYTHON_REALPATH, None, BASE.COMPUTE_PYTHON_SHA256, "compute Python")
    BASE.verify_artifact(BASE.TORCH_METADATA, None, BASE.TORCH_METADATA_SHA256, "Torch metadata")
    if not R2.MODEL.is_file() or R2.MODEL.stat().st_size != R2.MODEL_SIZE:
        raise BASE.GateError("target Q8 model is missing or changed")
    libraries = BASE.verify_libraries(manifest)
    backend_rows = [row for row in libraries if row["soname"] == "libggml-sycl.so.0"]
    if len(backend_rows) != 1 or backend_rows[0]["sha256"] != BACKEND_SHA256:
        raise BASE.GateError("effective R4 backend DSO does not match sealed backend")
    return manifest, libraries


def create_json(path: Path, value: Any) -> None:
    if path.name == "terminal-receipt.json" and isinstance(value, Mapping):
        value = {
            **value,
            "schema": "neural.download.qwen36-llama-fa0-graph-port-parent-sentinel-r4-terminal.v1",
            "parent_sentinel_only": True,
            "curve_authorized": False,
            "site_publication_authorized": False,
            "speed_claim_authorized": False,
            "protected_graph_off_values_may_be_replaced": False,
        }
    ORIGINAL_CREATE_JSON(path, value)


BASE.CAMPAIGN_ID = CAMPAIGN_ID
BASE.ACK = ACK
BASE.RUN_ROOT = RUN_ROOT
BASE.MANIFEST = OVERLAY
BASE.BINARY = BINARY
BASE.BINARY_SIZE = BINARY_SIZE
BASE.BINARY_SHA256 = BINARY_SHA256
BASE.PACKET_PATHS = PACKET_PATHS
BASE.load_json = lambda path: load_manifest() if path == OVERLAY else ORIGINAL_LOAD_JSON(path)
BASE.validate_manifest = validate_manifest
BASE.static_check = static_check
BASE.create_json = create_json


if __name__ == "__main__":
    raise SystemExit(BASE.main())

#!/usr/bin/env python3
"""Inert, fail-closed R2 parent sentinel for the fa0 graph-port memo repair.

R2 preserves the failed R1 evidence and uses a rebuilt identity plus a distinct output root.
Both ``--check`` and ``--execute`` are deliberately blocked until the
incremental pointer-stable memo overlay and the rebuilt same-binary runtime
identity have been sealed in the R2 preregistration.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
R1_SCRIPT = HERE / "run-20260825-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-r1.py"
SPEC = importlib.util.spec_from_file_location("qwen36_fa0_graph_port_parent_sentinel_r1_lifecycle", R1_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import R1 lifecycle: {R1_SCRIPT}")
R1 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = R1
SPEC.loader.exec_module(R1)
BASE = R1.BASE
ORIGINAL_LOAD_JSON = R1.ORIGINAL_LOAD_JSON
ORIGINAL_CREATE_JSON = R1.ORIGINAL_CREATE_JSON

MANIFEST = BASE.LANE / "data/2026-08-25-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-r2-prereg.json"
NOTE = BASE.LANE / "notes/2026-08-25-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-r2-preregistration.md"
CAMPAIGN_ID = "qwen36-q8-f16-tp1-fa0-graph-port-sentinel-20260825-r2"
RUN_ROOT = Path("/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-fa0-graph-port-sentinel-20260825-r2")
ACK = f"RUN {CAMPAIGN_ID}"

SOURCE = Path("/home/steve/src/llama.cpp-q38-tp1-graph-port")
SOURCE_HEAD = "fa0f3b25a47f346858a4d0d169f5181aa424b110"
SOURCE_PATH_HASHES = {
    "ggml/src/ggml-sycl/common.hpp": "ce4c8541381f9e1043e15b21359c8c828fc17f20c48672afb0c6d646c02b7805",
    "ggml/src/ggml-sycl/ggml-sycl.cpp": "f0c4bda8beb3c0b06c72edc202fcc074d72e031433a4eacd8a91b8acf5f468a0",
}

BASE_PATCH_REL = "patches/qwen36-27b-mtp-gguf-q4-b70/llamacpp-fa0-graph-cache-evidence-port-20260825.patch"
BASE_PATCH = BASE.REPO / BASE_PATCH_REL
BASE_PATCH_SHA256 = "1a8589f894fde7d87aac35c59bc81e3701bf7f6d9ba54f35808ae262325d7892"
BASE_SOURCE_MANIFEST_REL = "patches/qwen36-27b-mtp-gguf-q4-b70/source-manifest.json"
BASE_SOURCE_MANIFEST = BASE.REPO / BASE_SOURCE_MANIFEST_REL
BASE_SOURCE_MANIFEST_SHA256 = "2a4c315a5429c458b80e6aa55396e3ce31af44fac76905d78a6155ea75a7ae1c"

MEMO_PATCH_REL = "patches/qwen36-27b-mtp-gguf-q4-b70/llamacpp-fa0-graph-cache-q8-pointer-stable-r2-20260825.patch"
MEMO_PATCH = BASE.REPO / MEMO_PATCH_REL
MEMO_SOURCE_MANIFEST_REL = "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-fa0-graph-cache-q8-pointer-stable-r2-prereg.json"
MEMO_SOURCE_MANIFEST = BASE.REPO / MEMO_SOURCE_MANIFEST_REL
PLACEHOLDER_PATCH_SHA256 = "FILL_AFTER_INCREMENTAL_PATCH_FREEZE"
PLACEHOLDER_MANIFEST_SHA256 = "FILL_AFTER_INCREMENTAL_MANIFEST_FREEZE"
PLACEHOLDER_BUILD_SHA256 = "FILL_AFTER_R2_BUILD"
PLACEHOLDER_DSO_CLOSURE = "FILL_AFTER_R2_LDD_CLOSURE"

BUILD_ROOT = SOURCE / "build-sycl-aot-bmg-g31-graph-port"
BINARY = BUILD_ROOT / "bin/llama-cli"
GRAPH_BACKEND = BUILD_ROOT / "bin/libggml-sycl.so"
CMAKE_CACHE = BUILD_ROOT / "CMakeCache.txt"
MAKEFILE = BUILD_ROOT / "Makefile"
SYCL_FLAGS = BUILD_ROOT / "ggml/src/ggml-sycl/CMakeFiles/ggml-sycl.dir/flags.make"

MODEL = R1.MODEL
MODEL_SIZE = R1.MODEL_SIZE
MODEL_SHA256 = R1.MODEL_SHA256
PROMPT = R1.PROMPT
COMMON_ARGV = (
    str(BINARY), "-m", str(MODEL), "-dev", "SYCL0", "-ngl", "99",
    "-sm", "none", "-c", "2048", "-n", "64", "-b", "512", "-ub",
    "512", "-fa", "on", "-ctk", "f16", "-ctv", "f16", "-t", "16",
    "--poll", "50", "--seed", "42", "--temp", "0", "--ignore-eos",
    "--no-conversation", "--no-display-prompt", "--simple-io", "--no-warmup",
    "--single-turn", "--no-show-timings", "--log-verbosity", "4",
    "--prompt", PROMPT,
)
EXACT_RUNTIME_KNOBS = R1.EXACT_RUNTIME_KNOBS
EXPECTED_CMAKE = R1.EXPECTED_CMAKE
REQUIRED_LOCKS = R1.REQUIRED_LOCKS
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

PACKET_PATHS = R1.PACKET_PATHS + (
    MEMO_PATCH_REL,
    MEMO_SOURCE_MANIFEST_REL,
    str(MANIFEST.relative_to(BASE.REPO)),
    str(NOTE.relative_to(BASE.REPO)),
    str(Path(__file__).resolve().relative_to(BASE.REPO)),
    "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/test_qwen36_q8_f16_tp1_fa0_graph_port_parent_sentinel_r2.py",
)


def load_manifest() -> dict[str, Any]:
    return ORIGINAL_LOAD_JSON(MANIFEST)


def _hash_or_placeholder(value: object, placeholder: str) -> bool:
    return value == placeholder or SHA256_RE.fullmatch(str(value)) is not None


def _artifact_row_is_unsealed_or_sealed(row: object, path: Path) -> bool:
    if not isinstance(row, Mapping) or row.get("path") != str(path):
        return False
    if row.get("size_bytes") is None and row.get("sha256") == PLACEHOLDER_BUILD_SHA256:
        return True
    return (
        isinstance(row.get("size_bytes"), int)
        and row["size_bytes"] > 0
        and SHA256_RE.fullmatch(str(row.get("sha256", ""))) is not None
    )


def validate_manifest(value: Mapping[str, Any]) -> None:
    selectors = value.get("selectors") or {}
    model = value.get("model") or {}
    source = value.get("source") or {}
    runtime = value.get("runtime") or {}
    canary = value.get("canary") or {}
    lifecycle = value.get("lifecycle") or {}
    acceptance = value.get("acceptance") or {}
    interpretation = value.get("interpretation") or {}
    overlay = source.get("incremental_memo_overlay") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-fa0-graph-port-parent-sentinel-r2-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and value.get("build_identity_status") in {
            "UNSEALED_AWAITING_R2_PATCH_BUILD_AND_DSO_HASHES", "sealed"
        }
        and selectors == {
            "revision": "qwen3.6-27b", "artifact_id": "qwen36-27b-unsloth-q8-0-82d411a",
            "quantization": "Q8_0", "runtime_family": "llama.cpp SYCL", "tp": 1,
            "mtp": 0, "kv": "f16", "graph_comparison": ["off-cache0", "on-cache8"],
        }
        and model.get("path") == str(MODEL)
        and model.get("size_bytes") == MODEL_SIZE
        and model.get("sha256") == MODEL_SHA256
        and source.get("path") == str(SOURCE)
        and source.get("base_head") == SOURCE_HEAD
        and source.get("required_modified_paths") == list(SOURCE_PATH_HASHES)
        and source.get("post_r2_sha256") == SOURCE_PATH_HASHES
        and source.get("base_graph_port") == {
            "patch_path": BASE_PATCH_REL, "patch_sha256": BASE_PATCH_SHA256,
            "source_manifest_path": BASE_SOURCE_MANIFEST_REL,
            "source_manifest_sha256": BASE_SOURCE_MANIFEST_SHA256,
        }
        and overlay.get("patch_path") == MEMO_PATCH_REL
        and _hash_or_placeholder(overlay.get("patch_sha256"), PLACEHOLDER_PATCH_SHA256)
        and overlay.get("source_manifest_path") == MEMO_SOURCE_MANIFEST_REL
        and _hash_or_placeholder(overlay.get("source_manifest_sha256"), PLACEHOLDER_MANIFEST_SHA256)
        and overlay.get("classification") == "incremental-pointer-stable-q8-memo-graph-repair-only"
        and overlay.get("common_hpp_must_remain_unchanged") is True
        and overlay.get("graph_off_semantics_must_remain_unchanged") is True
        and runtime.get("build_root") == str(BUILD_ROOT)
        and _artifact_row_is_unsealed_or_sealed(runtime.get("binary"), BINARY)
        and _artifact_row_is_unsealed_or_sealed(runtime.get("graph_backend"), GRAPH_BACKEND)
        and runtime.get("cmake_cache", {}).get("path") == str(CMAKE_CACHE)
        and _hash_or_placeholder(runtime.get("cmake_cache", {}).get("sha256"), PLACEHOLDER_BUILD_SHA256)
        and runtime.get("makefile", {}).get("path") == str(MAKEFILE)
        and _hash_or_placeholder(runtime.get("makefile", {}).get("sha256"), PLACEHOLDER_BUILD_SHA256)
        and runtime.get("sycl_flags", {}).get("path") == str(SYCL_FLAGS)
        and _hash_or_placeholder(runtime.get("sycl_flags", {}).get("sha256"), PLACEHOLDER_BUILD_SHA256)
        and runtime.get("required_cmake") == EXPECTED_CMAKE
        and runtime.get("effective_shared_libraries_scope") == R1.load_manifest()["runtime"]["effective_shared_libraries_scope"]
        and runtime.get("effective_shared_libraries_status") in {
            PLACEHOLDER_DSO_CLOSURE, "sealed"
        }
        and isinstance(runtime.get("effective_shared_libraries"), list)
        and canary.get("common_argv") == list(COMMON_ARGV)
        and canary.get("base_runtime_knobs") == EXACT_RUNTIME_KNOBS
        and canary.get("control_environment_delta") == {
            "GGML_SYCL_ENABLE_GRAPH": "0", "GGML_SYCL_GRAPH_CACHE_SIZE": "0"}
        and canary.get("candidate_environment_delta") == {
            "GGML_SYCL_ENABLE_GRAPH": "1", "GGML_SYCL_GRAPH_CACHE_SIZE": "8"}
        and canary.get("unsafe_graph_variables_forbidden") == list(BASE.UNSAFE_GRAPH_VARIABLES)
        and canary.get("same_new_binary_required") is True
        and canary.get("exact_output_bytes_required") is True
        and canary.get("generated_tokens_per_arm") == 64
        and lifecycle.get("output_root") == str(RUN_ROOT)
        and lifecycle.get("exact_ack") == ACK
        and lifecycle.get("arm_timeout_seconds") == 900
        and lifecycle.get("child_stdin") == "/dev/null"
        and lifecycle.get("requires_clean_pushed_main") is True
        and lifecycle.get("artifacts_are_create_only") is True
        and lifecycle.get("r1_evidence_must_remain_immutable") is True
        and lifecycle.get("required_locks") == list(REQUIRED_LOCKS)
        and acceptance.get("control_all_graph_counters_zero") is True
        and acceptance.get("candidate_cache_limit") == 8
        and acceptance.get("candidate_cache_full") == 0
        and acceptance.get("candidate_replayed_equals_requested") is True
        and acceptance.get("strict_counter_conservation") is True
        and acceptance.get("exact_output_parity") is True
        and interpretation.get("terminal_pass_state") == "passed-r2-parent-sentinel-only"
        and interpretation.get("curve_authorized") is False
        and interpretation.get("site_publication_authorized") is False
        and interpretation.get("speed_claim_authorized") is False
        and interpretation.get("quality_claim_authorized") is False
        and interpretation.get("record_or_submission_authorized") is False
        and interpretation.get("historical_featured_speeds_are_immutable") is True
        and interpretation.get("protected_graph_off_values_may_be_replaced") is False
    ):
        raise BASE.GateError("fa0 graph-port R2 parent manifest invariant failed")


def require_sealed_packet_identity(manifest: Mapping[str, Any]) -> None:
    if manifest.get("build_identity_status") != "sealed":
        raise BASE.GateError("R2 packet is unsealed; fill incremental patch, build, backend, and DSO hashes")
    if manifest["runtime"].get("effective_shared_libraries_status") != "sealed":
        raise BASE.GateError("sealed R2 DSO closure status is absent")
    overlay = manifest["source"]["incremental_memo_overlay"]
    for key in ("patch_sha256", "source_manifest_sha256"):
        if SHA256_RE.fullmatch(str(overlay.get(key, ""))) is None:
            raise BASE.GateError(f"sealed incremental overlay {key} is absent")
    runtime = manifest["runtime"]
    for label in ("binary", "graph_backend"):
        row = runtime[label]
        if not isinstance(row.get("size_bytes"), int) or row["size_bytes"] <= 0:
            raise BASE.GateError(f"sealed R2 {label} size is absent")
        if SHA256_RE.fullmatch(str(row.get("sha256", ""))) is None:
            raise BASE.GateError(f"sealed R2 {label} SHA-256 is absent")
    rows = runtime.get("effective_shared_libraries")
    if not isinstance(rows, list) or not rows:
        raise BASE.GateError("sealed R2 effective DSO closure is absent")
    sonames: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"soname", "realpath", "sha256"}:
            raise BASE.GateError("sealed R2 effective DSO row schema changed")
        if not row["soname"] or row["soname"] in sonames or not Path(row["realpath"]).is_absolute():
            raise BASE.GateError("sealed R2 DSO row is duplicated or non-canonical")
        if SHA256_RE.fullmatch(str(row["sha256"])) is None:
            raise BASE.GateError("sealed R2 effective DSO SHA-256 is absent")
        sonames.add(row["soname"])
    backend_rows = [row for row in rows if row["soname"].startswith("libggml-sycl.so")]
    if len(backend_rows) != 1:
        raise BASE.GateError("sealed R2 DSO closure must contain exactly one libggml-sycl backend")
    backend = runtime["graph_backend"]
    if (
        backend_rows[0]["realpath"] != str(GRAPH_BACKEND.resolve(strict=True))
        or backend_rows[0]["sha256"] != backend["sha256"]
    ):
        raise BASE.GateError("sealed R2 libggml-sycl DSO is not the hashed graph backend")


def git_source(*args: str) -> str:
    return subprocess.check_output(
        ["/usr/bin/git", "-C", str(SOURCE), *args], text=True,
        env=BASE.CONTROL_ENV, timeout=30,
    ).strip()


def verify_source(manifest: Mapping[str, Any]) -> None:
    if git_source("rev-parse", "HEAD") != SOURCE_HEAD:
        raise BASE.GateError("focused graph-port R2 source HEAD changed")
    expected_status = "\n".join(f" M {path}" for path in SOURCE_PATH_HASHES)
    observed_status = subprocess.check_output(
        ["/usr/bin/git", "-C", str(SOURCE), "status", "--porcelain=v1", "--untracked-files=all"],
        text=True, env=BASE.CONTROL_ENV, timeout=30,
    ).rstrip("\n")
    if observed_status != expected_status:
        raise BASE.GateError("focused graph-port R2 source has non-frozen changes")
    BASE.verify_artifact(BASE_PATCH, None, BASE_PATCH_SHA256, "focused graph-port base patch")
    BASE.verify_artifact(BASE_SOURCE_MANIFEST, None, BASE_SOURCE_MANIFEST_SHA256, "base graph-port source manifest")
    overlay = manifest["source"]["incremental_memo_overlay"]
    BASE.verify_artifact(MEMO_PATCH, None, overlay["patch_sha256"], "incremental pointer-stable memo patch")
    BASE.verify_artifact(MEMO_SOURCE_MANIFEST, None, overlay["source_manifest_sha256"], "incremental memo source manifest")
    for relative, digest in SOURCE_PATH_HASHES.items():
        BASE.verify_artifact(SOURCE / relative, None, digest, f"R2 source {relative}")
    result = subprocess.run(
        ["/usr/bin/git", "-C", str(SOURCE), "apply", "--reverse", "--check", str(MEMO_PATCH)],
        env=BASE.CONTROL_ENV, capture_output=True, text=True, timeout=30, check=False,
    )
    if result.returncode != 0:
        raise BASE.GateError("incremental pointer-stable memo patch is not exactly reverse-applicable")


def install_runtime_identity(manifest: Mapping[str, Any]) -> None:
    binary = manifest["runtime"]["binary"]
    BASE.BINARY = BINARY
    BASE.BINARY_SIZE = binary["size_bytes"]
    BASE.BINARY_SHA256 = binary["sha256"]


def base_environment(root: Path) -> dict[str, str]:
    value = R1.base_environment(root)
    value["HOME"] = str(root / "home")
    value["XDG_CACHE_HOME"] = str(root / "xdg-cache")
    value["SYCL_CACHE_DIR"] = str(root / "sycl-cache")
    value["TMPDIR"] = str(root / "tmp")
    return value


def verify_build(manifest: Mapping[str, Any]) -> None:
    runtime = manifest["runtime"]
    BASE.verify_artifact(BINARY, runtime["binary"]["size_bytes"], runtime["binary"]["sha256"], "R2 llama-cli")
    BASE.verify_artifact(GRAPH_BACKEND, runtime["graph_backend"]["size_bytes"], runtime["graph_backend"]["sha256"], "R2 graph backend")
    BASE.verify_artifact(CMAKE_CACHE, None, runtime["cmake_cache"]["sha256"], "R2 CMake cache")
    BASE.verify_artifact(MAKEFILE, None, runtime["makefile"]["sha256"], "R2 Makefile")
    BASE.verify_artifact(SYCL_FLAGS, None, runtime["sycl_flags"]["sha256"], "R2 SYCL flags")
    observed = R1.cmake_values(CMAKE_CACHE.read_text(encoding="utf-8"))
    changed = {name: observed.get(name) for name, expected in EXPECTED_CMAKE.items() if observed.get(name) != expected}
    if changed:
        raise BASE.GateError(f"R2 CMake identity changed: {changed}")
    flags = SYCL_FLAGS.read_text(encoding="utf-8")
    if "-DGGML_SYCL_GRAPH" not in flags or "GGML_SYCL_HOST_MEM_FALLBACK" in flags:
        raise BASE.GateError("R2 SYCL graph compile flags changed")


def validate_candidate_graph_log(text: str) -> dict[str, int]:
    forbidden = (
        "persistent SYCL graph Q8 memo exhausted",
        "persistent SYCL graph Q8 memo allocation failed",
        "wait cannot be called for a queue which is recording",
    )
    for marker in forbidden:
        if marker in text:
            raise BASE.GateError(f"candidate hit forbidden pointer-stability failure: {marker}")
    return R1.validate_candidate_graph_log(text)


def static_check() -> tuple[dict[str, Any], list[dict[str, str]]]:
    manifest = load_manifest()
    validate_manifest(manifest)
    require_sealed_packet_identity(manifest)
    install_runtime_identity(manifest)
    verify_source(manifest)
    verify_build(manifest)
    BASE.verify_artifact(BASE.MODEL_VERIFIER, None, BASE.MODEL_VERIFIER_SHA256, "model verifier")
    BASE.verify_artifact(BASE.PROTECTED, None, BASE.PROTECTED_SHA256, "protected speed manifest")
    if not MODEL.is_file() or MODEL.stat().st_size != MODEL_SIZE:
        raise BASE.GateError("target Q8 model is missing or its size changed")
    return manifest, BASE.verify_libraries(manifest)


def create_json(path: Path, value: Any) -> None:
    if path.name == "terminal-receipt.json" and isinstance(value, Mapping):
        value = {
            **value,
            "schema": "neural.download.qwen36-llama-fa0-graph-port-parent-sentinel-r2-terminal.v1",
            "source_base_head": SOURCE_HEAD,
            "source_post_r2_sha256": SOURCE_PATH_HASHES,
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
BASE.MANIFEST = MANIFEST
BASE.MODEL = MODEL
BASE.MODEL_SIZE = MODEL_SIZE
BASE.MODEL_SHA256 = MODEL_SHA256
BASE.BINARY = BINARY
BASE.CMAKE_CACHE = CMAKE_CACHE
BASE.BUILD_NINJA = MAKEFILE
BASE.COMMON_ARGV = COMMON_ARGV
BASE.PACKET_PATHS = PACKET_PATHS
BASE.CANONICAL_LOCKS = list(REQUIRED_LOCKS)
BASE.load_json = lambda path: load_manifest() if path == MANIFEST else ORIGINAL_LOAD_JSON(path)
BASE.validate_manifest = validate_manifest
BASE.base_environment = base_environment
BASE.validate_candidate_graph_log = validate_candidate_graph_log
BASE.static_check = static_check
BASE.create_json = create_json


if __name__ == "__main__":
    raise SystemExit(BASE.main())

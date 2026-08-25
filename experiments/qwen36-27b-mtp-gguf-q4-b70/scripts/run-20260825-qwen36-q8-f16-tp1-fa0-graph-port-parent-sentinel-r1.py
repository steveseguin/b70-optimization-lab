#!/usr/bin/env python3
"""Fail-closed parent sentinel for the focused fa0 SYCL graph port.

The default mode is inert.  ``--check`` remains CPU-only, and both ``--check``
and ``--execute`` reject the preregistration until the new binary and every
effective DSO identity have been filled and sealed.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
R5_SCRIPT = HERE / "run-20260825-qwen36-q8-f16-tp1-graph-parent-sentinel-r5.py"
SPEC = importlib.util.spec_from_file_location("qwen36_graph_parent_sentinel_r5_lifecycle", R5_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import mature R5 lifecycle: {R5_SCRIPT}")
R5 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = R5
SPEC.loader.exec_module(R5)
BASE = R5.BASE
ORIGINAL_LOAD_JSON = BASE.load_json
ORIGINAL_CREATE_JSON = BASE.create_json
ORIGINAL_R4_CANDIDATE_VALIDATOR = R5.R4.validate_candidate_graph_log

MANIFEST = BASE.LANE / "data/2026-08-25-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-prereg.json"
NOTE = BASE.LANE / "notes/2026-08-25-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-preregistration.md"
CAMPAIGN_ID = "qwen36-q8-f16-tp1-fa0-graph-port-sentinel-20260825-r1"
RUN_ROOT = Path("/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-fa0-graph-port-sentinel-20260825-r1")
ACK = f"RUN {CAMPAIGN_ID}"

SOURCE = Path("/home/steve/src/llama.cpp-q38-tp1-graph-port")
SOURCE_HEAD = "fa0f3b25a47f346858a4d0d169f5181aa424b110"
SOURCE_PATH_HASHES = {
    "ggml/src/ggml-sycl/common.hpp": "ce4c8541381f9e1043e15b21359c8c828fc17f20c48672afb0c6d646c02b7805",
    "ggml/src/ggml-sycl/ggml-sycl.cpp": "024fda2f9e667aa82cfdac64c079b5cb932e6a40e90031ad16cfd142bec93544",
}
PATCH_REL = "patches/qwen36-27b-mtp-gguf-q4-b70/llamacpp-fa0-graph-cache-evidence-port-20260825.patch"
PATCH = BASE.REPO / PATCH_REL
PATCH_SHA256 = "1a8589f894fde7d87aac35c59bc81e3701bf7f6d9ba54f35808ae262325d7892"
SOURCE_MANIFEST_REL = "patches/qwen36-27b-mtp-gguf-q4-b70/source-manifest.json"
SOURCE_MANIFEST = BASE.REPO / SOURCE_MANIFEST_REL
SOURCE_MANIFEST_SHA256 = "2a4c315a5429c458b80e6aa55396e3ce31af44fac76905d78a6155ea75a7ae1c"

BUILD_ROOT = SOURCE / "build-sycl-aot-bmg-g31-graph-port"
BINARY = BUILD_ROOT / "bin/llama-cli"
GRAPH_BACKEND = BUILD_ROOT / "bin/libggml-sycl.so"
CMAKE_CACHE = BUILD_ROOT / "CMakeCache.txt"
MAKEFILE = BUILD_ROOT / "Makefile"
SYCL_FLAGS = BUILD_ROOT / "ggml/src/ggml-sycl/CMakeFiles/ggml-sycl.dir/flags.make"
CMAKE_CACHE_SHA256 = "39852126a74e193d99fe9ee2a0a2553d6afc9f6ed2b77b7b853bb25dd689d461"
MAKEFILE_SHA256 = "db2b9dcc0296571e4f76b48402649af56376ea81582c49ca0442b9b35070298f"
SYCL_FLAGS_SHA256 = "c52e473c20c9e06f30b5558445d210791e88047fc0dd6e4585f9fa634fd0a727"

MODEL = Path("/mnt/usb-models/models/qwen36-27b-q8-gguf/Qwen3.6-27B-Q8_0.gguf")
MODEL_SIZE = 28595763424
MODEL_SHA256 = "f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce"
PROMPT = "Write a concise deterministic paragraph explaining why checksum-pinned A/B tests isolate one runtime variable."
COMMON_ARGV = (
    str(BINARY), "-m", str(MODEL), "-dev", "SYCL0", "-ngl", "99",
    "-sm", "none", "-c", "2048", "-n", "64", "-b", "512", "-ub",
    "512", "-fa", "on", "-ctk", "f16", "-ctv", "f16", "-t", "16",
    "--poll", "50", "--seed", "42", "--temp", "0", "--ignore-eos",
    "--no-conversation", "--no-display-prompt", "--simple-io", "--no-warmup",
    "--single-turn", "--no-show-timings", "--log-verbosity", "4",
    "--prompt", PROMPT,
)

EXACT_RUNTIME_KNOBS = {
    "ONEAPI_DEVICE_SELECTOR": "level_zero:0",
    "UR_L0_USE_IMMEDIATE_COMMANDLISTS": "1",
    "UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD": "1",
    "GGML_SYCL_COMM_SINGLE_KERNEL": "1",
    "GGML_META_FUSE_ALLREDUCE_ADD": "1",
    "GGML_META_FUSE_ALLREDUCE_ADD_RMS_MUL": "1",
    "GGML_SYCL_COMM_FUSED_Q8": "1",
    "GGML_SYCL_FUSED_SWIGLU_Q8": "1",
    "GGML_SYCL_FUSED_ATTN_Q8": "1",
    "GGML_SYCL_FUSED_GDN_Q8": "1",
    "GGML_SYCL_FUSED_MMVQ_PAIR": "1",
    "GGML_SYCL_FUSED_MMVQ_SWIGLU_Q4K": "1",
    "GGML_SYCL_FUSED_MMVQ_PAIR_GDN": "1",
    "GGML_SYCL_FUSED_MMVQ_TRIPLE_ATTN": "1",
    "GGML_SYCL_FUSED_MMVQ_TRIPLE_GDN": "1",
    "GGML_SYCL_FUSED_MMVQ_QUAD_GDN": "1",
    "GGML_SYCL_FUSED_GDN_BETA_SIGMOID": "1",
    "GGML_SYCL_FUSED_CONCAT_STATE": "1",
    "GGML_SYCL_FUSED_GDN_STATE_IO": "1",
    "GGML_SYCL_FUSED_CONV_STATE_IO": "1",
    "GGML_SYCL_COMM_DIRECT_Q8": "2",
    "GGML_SYCL_FUSED_ROPE_SET_ROWS": "1",
    "GGML_SYCL_COMM_REDUCE_VEC4": "1",
    "GGML_SYCL_FUSED_QK_NORM_ROPE": "1",
    "GGML_SYCL_FUSED_CONV_SILU_L2": "1",
    "GGML_SYCL_FUSE_EXT": "31",
    "GGML_SYCL_QDEDUP_STATS": "1",
    "GGML_SYCL_MMQ_Q4K_REORDER": "1",
}

EXPECTED_CMAKE = {
    "CMAKE_BUILD_TYPE": "Release", "GGML_SYCL": "ON",
    "GGML_SYCL_DEVICE_ARCH": "bmg_g31", "GGML_SYCL_DNN": "OFF",
    "GGML_SYCL_F16": "ON", "GGML_SYCL_GRAPH": "ON",
    "GGML_SYCL_HOST_MEM_FALLBACK": "OFF",
    "GGML_SYCL_SUPPORT_LEVEL_ZERO_API": "ON", "GGML_SYCL_TARGET": "INTEL",
}
REQUIRED_LOCKS = (
    "/run/lock/muse-glimmer-gpu-exclusive.lock",
    "/tmp/b70-benchmark.lock",
    "/tmp/b70-gpu0.lock",
    "/run/user/1000/qwen36-b70-gpu-leases/gpu0.lock",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

PACKET_PATHS = R5.BASE.PACKET_PATHS + (
    "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-fa0-graph-cache-port-prereg.json",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/notes/2026-08-25-qwen36-fa0-graph-cache-port-preregistration.md",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/test_fa0_graph_cache_port_patch.py",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-fa0-graph-port-build-result.json",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/notes/2026-08-25-qwen36-fa0-graph-port-build-result.md",
    "patches/qwen36-27b-mtp-gguf-q4-b70/README.md",
    PATCH_REL, SOURCE_MANIFEST_REL,
    str(MANIFEST.relative_to(BASE.REPO)), str(NOTE.relative_to(BASE.REPO)),
    str(Path(__file__).resolve().relative_to(BASE.REPO)),
    "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/test_qwen36_q8_f16_tp1_fa0_graph_port_parent_sentinel.py",
)


def load_manifest() -> dict[str, Any]:
    return ORIGINAL_LOAD_JSON(MANIFEST)


def validate_manifest(value: Mapping[str, Any]) -> None:
    selectors = value.get("selectors") or {}
    model = value.get("model") or {}
    source = value.get("source") or {}
    runtime = value.get("runtime") or {}
    canary = value.get("canary") or {}
    lifecycle = value.get("lifecycle") or {}
    acceptance = value.get("acceptance") or {}
    interpretation = value.get("interpretation") or {}
    patch = source.get("patch") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-fa0-graph-port-parent-sentinel-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and value.get("build_identity_status") in {
            "UNSEALED_AWAITING_LLAMA_CLI_AND_DSO_HASHES", "sealed"
        }
        and selectors == {
            "revision": "qwen3.6-27b", "artifact_id": "qwen36-27b-unsloth-q8-0-82d411a",
            "quantization": "Q8_0", "runtime_family": "llama.cpp SYCL", "tp": 1,
            "mtp": 0, "kv": "f16", "graph_comparison": ["off-cache0", "on-cache8"],
        }
        and model.get("path") == str(MODEL)
        and model.get("size_bytes") == MODEL_SIZE and model.get("sha256") == MODEL_SHA256
        and source.get("path") == str(SOURCE) and source.get("base_head") == SOURCE_HEAD
        and source.get("required_modified_paths") == list(SOURCE_PATH_HASHES)
        and source.get("post_apply_sha256") == SOURCE_PATH_HASHES
        and patch == {"path": PATCH_REL, "sha256": PATCH_SHA256,
                         "source_manifest": SOURCE_MANIFEST_REL,
                         "source_manifest_sha256": SOURCE_MANIFEST_SHA256}
        and runtime.get("build_root") == str(BUILD_ROOT)
        and (runtime.get("binary") or {}).get("path") == str(BINARY)
        and (runtime.get("graph_backend") or {}).get("path") == str(GRAPH_BACKEND)
        and runtime.get("cmake_cache") == {"path": str(CMAKE_CACHE), "sha256": CMAKE_CACHE_SHA256}
        and runtime.get("makefile") == {"path": str(MAKEFILE), "sha256": MAKEFILE_SHA256}
        and runtime.get("sycl_flags") == {"path": str(SYCL_FLAGS), "sha256": SYCL_FLAGS_SHA256}
        and runtime.get("required_cmake") == EXPECTED_CMAKE
        and runtime.get("effective_shared_libraries_scope")
        == "ldd-link-time-closure; runtime-loaded Level Zero and Unified Runtime driver components are outside this list and are identified by the inherited device/postflight receipts"
        and canary.get("common_argv") == list(COMMON_ARGV)
        and canary.get("base_runtime_knobs_source")
        == "experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4kxl-q8-tp1-exact-depth-prereg.json"
        and canary.get("base_runtime_knobs") == EXACT_RUNTIME_KNOBS
        and canary.get("control_environment_delta") == {
            "GGML_SYCL_ENABLE_GRAPH": "0", "GGML_SYCL_GRAPH_CACHE_SIZE": "0"}
        and canary.get("candidate_environment_delta") == {
            "GGML_SYCL_ENABLE_GRAPH": "1", "GGML_SYCL_GRAPH_CACHE_SIZE": "8"}
        and canary.get("unsafe_graph_variables_forbidden") == list(BASE.UNSAFE_GRAPH_VARIABLES)
        and canary.get("same_new_binary_required") is True
        and canary.get("exact_output_bytes_required") is True
        and canary.get("fresh_process_local_cache_roots_both_arms") is True
        and lifecycle.get("output_root") == str(RUN_ROOT)
        and lifecycle.get("exact_ack") == ACK and lifecycle.get("child_stdin") == "/dev/null"
        and lifecycle.get("arm_timeout_seconds") == 900
        and lifecycle.get("live_origin_equality_required_prelaunch") is True
        and lifecycle.get("local_launch_head_and_packet_blobs_frozen_postlaunch") is True
        and lifecycle.get("live_origin_equality_required_postlaunch") is False
        and lifecycle.get("required_locks") == list(REQUIRED_LOCKS)
        and acceptance.get("control_all_graph_counters_zero") is True
        and acceptance.get("candidate_cache_limit") == 8
        and acceptance.get("candidate_cache_full") == 0
        and acceptance.get("candidate_replayed_equals_requested") is True
        and acceptance.get("exact_output_parity") is True
        and interpretation.get("terminal_pass_state") == "passed-parent-sentinel-only"
        and interpretation.get("seven_cell_expansion_authorized") is False
        and interpretation.get("site_publication_authorized") is False
        and interpretation.get("record_or_submission_authorized") is False
        and interpretation.get("quality_claim_authorized") is False
        and interpretation.get("speed_measurement_or_floor") is None
        and interpretation.get("historical_featured_speeds_are_immutable") is True
        and interpretation.get("graph_estimates_forbidden") is True
        and runtime.get("source_provenance") == source.get("provenance")
    ):
        raise BASE.GateError("fa0 graph-port parent manifest invariant failed")


def require_sealed_build_identity(manifest: Mapping[str, Any]) -> None:
    runtime = manifest["runtime"]
    if manifest.get("build_identity_status") != "sealed":
        raise BASE.GateError("build identity is unsealed; fill llama-cli/backend/effective-DSO identities")
    for label in ("binary", "graph_backend"):
        row = runtime[label]
        if not isinstance(row.get("size_bytes"), int) or row["size_bytes"] <= 0:
            raise BASE.GateError(f"sealed {label} size is absent")
        if SHA256_RE.fullmatch(str(row.get("sha256", ""))) is None:
            raise BASE.GateError(f"sealed {label} SHA-256 is absent")
    rows = runtime.get("effective_shared_libraries")
    if not isinstance(rows, list) or not rows:
        raise BASE.GateError("sealed effective DSO closure is absent")
    sonames: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"soname", "realpath", "sha256"}:
            raise BASE.GateError("effective DSO row schema changed")
        if not row["soname"] or row["soname"] in sonames or not Path(row["realpath"]).is_absolute():
            raise BASE.GateError("effective DSO row is duplicated or non-canonical")
        if SHA256_RE.fullmatch(str(row["sha256"])) is None:
            raise BASE.GateError("effective DSO SHA-256 is absent")
        sonames.add(row["soname"])
    backend_rows = [row for row in rows if row["soname"].startswith("libggml-sycl.so")]
    backend = runtime["graph_backend"]
    if len(backend_rows) != 1:
        raise BASE.GateError("sealed DSO closure must contain exactly one libggml-sycl backend")
    if (
        backend_rows[0]["realpath"] != str(GRAPH_BACKEND.resolve(strict=True))
        or backend_rows[0]["sha256"] != backend["sha256"]
    ):
        raise BASE.GateError("sealed libggml-sycl DSO is not the hashed graph backend")


def git_source(*args: str) -> str:
    return subprocess.check_output(
        ["/usr/bin/git", "-C", str(SOURCE), *args], text=True,
        env=BASE.CONTROL_ENV, timeout=30,
    ).strip()


def verify_source() -> None:
    if git_source("rev-parse", "HEAD") != SOURCE_HEAD:
        raise BASE.GateError("focused graph-port source HEAD changed")
    expected_status = "\n".join(f" M {path}" for path in SOURCE_PATH_HASHES)
    observed_status = subprocess.check_output(
        ["/usr/bin/git", "-C", str(SOURCE), "status", "--porcelain=v1", "--untracked-files=all"],
        text=True, env=BASE.CONTROL_ENV, timeout=30,
    ).rstrip("\n")
    if observed_status != expected_status:
        raise BASE.GateError("focused graph-port source has non-frozen changes")
    BASE.verify_artifact(PATCH, None, PATCH_SHA256, "focused graph-port patch")
    BASE.verify_artifact(SOURCE_MANIFEST, None, SOURCE_MANIFEST_SHA256, "graph-port source manifest")
    for relative, digest in SOURCE_PATH_HASHES.items():
        BASE.verify_artifact(SOURCE / relative, None, digest, f"ported source {relative}")
    result = subprocess.run(
        ["/usr/bin/git", "-C", str(SOURCE), "apply", "--reverse", "--check", str(PATCH)],
        env=BASE.CONTROL_ENV, capture_output=True, text=True, timeout=30, check=False,
    )
    if result.returncode != 0:
        raise BASE.GateError("tracked graph port is not exactly reverse-applicable")


def cmake_values(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line.startswith(("//", "#")) or ":" not in line or "=" not in line:
            continue
        left, value = line.split("=", 1)
        name, _kind = left.split(":", 1)
        result[name] = value
    return result


def install_runtime_identity(manifest: Mapping[str, Any]) -> None:
    binary = manifest["runtime"]["binary"]
    BASE.BINARY = BINARY
    BASE.BINARY_SIZE = binary["size_bytes"]
    BASE.BINARY_SHA256 = binary["sha256"]


def base_environment(root: Path) -> dict[str, str]:
    value = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
        "LD_LIBRARY_PATH": BASE.ONEAPI_LIBRARY_PATH,
        **EXACT_RUNTIME_KNOBS,
        "HOME": str(root / "home"), "XDG_CACHE_HOME": str(root / "xdg-cache"),
        "SYCL_CACHE_DIR": str(root / "sycl-cache"), "TMPDIR": str(root / "tmp"),
    }
    value.pop("GGML_SYCL_ENABLE_GRAPH", None)
    value.pop("GGML_SYCL_GRAPH_CACHE_SIZE", None)
    for name in BASE.UNSAFE_GRAPH_VARIABLES:
        value.pop(name, None)
    return value


def verify_build(manifest: Mapping[str, Any]) -> None:
    runtime = manifest["runtime"]
    BASE.verify_artifact(BINARY, runtime["binary"]["size_bytes"], runtime["binary"]["sha256"], "new llama-cli")
    BASE.verify_artifact(GRAPH_BACKEND, runtime["graph_backend"]["size_bytes"], runtime["graph_backend"]["sha256"], "new graph backend")
    BASE.verify_artifact(CMAKE_CACHE, None, CMAKE_CACHE_SHA256, "graph-port CMake cache")
    BASE.verify_artifact(MAKEFILE, None, MAKEFILE_SHA256, "graph-port Makefile")
    BASE.verify_artifact(SYCL_FLAGS, None, SYCL_FLAGS_SHA256, "graph-port SYCL flags")
    observed = cmake_values(CMAKE_CACHE.read_text(encoding="utf-8"))
    changed = {name: observed.get(name) for name, value in EXPECTED_CMAKE.items() if observed.get(name) != value}
    if changed:
        raise BASE.GateError(f"graph-port CMake identity changed: {changed}")
    flags = SYCL_FLAGS.read_text(encoding="utf-8")
    if "-DGGML_SYCL_GRAPH" not in flags:
        raise BASE.GateError("SYCL graph compile definition is absent")
    if "GGML_SYCL_HOST_MEM_FALLBACK" in flags:
        raise BASE.GateError("host-memory fallback unexpectedly compiled")


def validate_candidate_graph_log(text: str) -> dict[str, int]:
    summary = ORIGINAL_R4_CANDIDATE_VALIDATOR(text)
    if summary["cache_miss"] <= 0:
        raise BASE.GateError(f"candidate did not prove a fresh cache miss: {summary}")
    if summary["cache_full"] != 0:
        raise BASE.GateError(f"candidate graph cache filled: {summary}")
    if summary["replayed"] != summary["requested"]:
        raise BASE.GateError(f"candidate did not replay every graph request: {summary}")
    if summary["requested"] != summary["cache_hit"] + summary["cache_miss"]:
        raise BASE.GateError(f"candidate request/cache accounting diverged: {summary}")
    if summary["cache_hit"] != summary["direct_replay"]:
        raise BASE.GateError(f"candidate cache-hit/direct-replay accounting diverged: {summary}")
    if not (
        summary["cache_miss"]
        == summary["recorded"]
        == summary["created"]
        == summary["cache_entries"]
    ):
        raise BASE.GateError(f"candidate miss/create/cache-entry accounting diverged: {summary}")
    if summary["updated"] != 0 or summary["recreated"] != 0:
        raise BASE.GateError(f"candidate unexpectedly updated or recreated graphs: {summary}")
    return summary


def static_check() -> tuple[dict[str, Any], list[dict[str, str]]]:
    manifest = load_manifest()
    validate_manifest(manifest)
    require_sealed_build_identity(manifest)
    install_runtime_identity(manifest)
    verify_source()
    verify_build(manifest)
    BASE.verify_artifact(BASE.MODEL_VERIFIER, None, BASE.MODEL_VERIFIER_SHA256, "model verifier")
    BASE.verify_artifact(BASE.PROTECTED, None, BASE.PROTECTED_SHA256, "protected speed manifest")
    BASE.verify_artifact(BASE.COMPUTE_PYTHON_REALPATH, None, BASE.COMPUTE_PYTHON_SHA256, "compute Python")
    if BASE.COMPUTE_PYTHON.resolve(strict=True) != BASE.COMPUTE_PYTHON_REALPATH:
        raise BASE.GateError("compute Python realpath changed")
    BASE.verify_artifact(BASE.TORCH_METADATA, None, BASE.TORCH_METADATA_SHA256, "Torch metadata")
    if not MODEL.is_file() or MODEL.stat().st_size != MODEL_SIZE:
        raise BASE.GateError("target Q8 model is missing or its size changed")
    return manifest, BASE.verify_libraries(manifest)


def create_json(path: Path, value: Any) -> None:
    if path.name == "terminal-receipt.json" and isinstance(value, Mapping):
        value = {
            **value,
            "schema": "neural.download.qwen36-llama-fa0-graph-port-parent-sentinel-terminal.v1",
            "source_base_head": SOURCE_HEAD,
            "source_port_patch_sha256": PATCH_SHA256,
            "mechanism_and_exact_output_parity_only": True,
            "quality_claim_authorized": False,
            "graph_estimates_forbidden": True,
        }
    ORIGINAL_CREATE_JSON(path, value)


# Rebind the mature R5 lifecycle to this isolated source, new same-binary pair,
# exact packet, accepted Q8/F16 knobs, and stricter evidence gates.
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

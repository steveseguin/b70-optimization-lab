#!/usr/bin/env python3
"""Seven-cell q8_0-KV graph curve on the focused fa0 port.

Default mode is inert. Checks and execution fail closed until build and parent
receipt placeholders are sealed. Each depth runs in a fresh process so graph
evidence is attributable to that exact cell.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
from typing import Any, Mapping


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
MANIFEST = LANE / "data/2026-08-25-qwen36-q8-q8kv-tp1-fa0-graph-exact-depth-prereg.json"
NOTE = LANE / "notes/2026-08-25-qwen36-q8-q8kv-tp1-fa0-graph-exact-depth-preregistration.md"
PARENT_SCRIPT = LANE / "scripts/run-20260825-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-r1.py"
Q8_OFF_SCRIPT = LANE / "scripts/run-20260825-qwen36-q8-q8kv-tp1-exact-depth-r1.py"


def import_file(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import frozen dependency: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PARENT = import_file("qwen36_fa0_graph_parent_for_q8kv_curve", PARENT_SCRIPT)
Q8_OFF = import_file("qwen36_q8_q8kv_graph_off_reference", Q8_OFF_SCRIPT)
BASE = PARENT.BASE
ENGINE = Q8_OFF.ENGINE

CAMPAIGN_ID = "qwen36-q8-q8kv-tp1-fa0-graph-exact-depth-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"
RUN_ROOT = Path("/mnt/fast-ai/bench-results/qwen36-q8-q8kv-tp1-fa0-graph-exact-depth-20260825-r1")
DEPTHS = [0, 2048, 4096, 8192, 16384, 24576, 32768]
MODEL = PARENT.MODEL
BINARY = PARENT.BUILD_ROOT / "bin/llama-bench"
GRAPH_BACKEND = PARENT.GRAPH_BACKEND
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

COMMON_ARGV = (
    str(BINARY), "-m", str(MODEL), "-dev", "SYCL0", "-ngl", "99",
    "-sm", "layer", "-p", "2048", "-n", "128", "-b", "2048",
    "-ub", "512", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0",
    "-t", "16", "--poll", "50", "-r", "5", "-o", "json",
)

Q8_OFF_REFERENCE = {
    "manifest": "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-q8-q8kv-tp1-exact-depth-prereg.json",
    "manifest_sha256": "24924133fb2a81ca7c368018d9a136067fb38d380904f14cfec4dacf698365e2",
    "runner": "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q8-q8kv-tp1-exact-depth-r1.py",
    "runner_sha256": "e266eed67e136078c65dd1a31ba569dd2b65be38e067fb84efbb6da2954c6596",
    "result": "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-q8-q8kv-tp1-exact-depth-result.json",
    "result_sha256": "74b6373258eb2db816f5d5bbe5f69f1478313f818e3e826733b8500d45be2e59",
    "result_note": "experiments/qwen36-27b-mtp-gguf-q4-b70/notes/2026-08-25-qwen36-q8-q8kv-tp1-exact-depth-result.md",
    "result_note_sha256": "4aab0de3ff9b293289e6a16bd3b47d605a0f607b60d71ac27f04f170e96f56ea",
}
PACKET_PATHS = tuple(Q8_OFF_REFERENCE[key] for key in ("manifest", "runner", "result", "result_note")) + (
    "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-prereg.json",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/notes/2026-08-25-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-preregistration.md",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-r1.py",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/test_qwen36_q8_f16_tp1_fa0_graph_port_parent_sentinel.py",
    "patches/qwen36-27b-mtp-gguf-q4-b70/llamacpp-fa0-graph-cache-evidence-port-20260825.patch",
    "patches/qwen36-27b-mtp-gguf-q4-b70/source-manifest.json",
    str(MANIFEST.relative_to(REPO)), str(NOTE.relative_to(REPO)),
    str(Path(__file__).resolve().relative_to(REPO)),
    "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/test_qwen36_q8_q8kv_tp1_fa0_graph_exact_depth.py",
    "scripts/parse-llama-bench-exact-depth.py",
)


class GateError(RuntimeError):
    """A frozen curve gate was not satisfied."""


def load_manifest() -> dict[str, Any]:
    try:
        value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateError(f"invalid q8-KV graph manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise GateError("q8-KV graph manifest must be an object")
    return value


def expected_environment() -> dict[str, str]:
    value = copy.deepcopy(Q8_OFF.load_manifest()["environment"])
    value["GGML_SYCL_ENABLE_GRAPH"] = "1"
    value["GGML_SYCL_GRAPH_CACHE_SIZE"] = "8"
    return value


def validate_manifest(value: Mapping[str, Any]) -> None:
    selectors = value.get("selectors") or {}
    model = value.get("model") or {}
    runtime = value.get("runtime") or {}
    source = value.get("source") or {}
    parent = value.get("parent_sentinel") or {}
    workload = value.get("workload") or {}
    evidence = value.get("graph_acceptance_per_cell") or {}
    quality = value.get("q8_kv_publication_gate") or {}
    lifecycle = value.get("lifecycle") or {}
    interpretation = value.get("interpretation") or {}
    reference = value.get("accepted_graph_off_reference") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-fa0-graph-exact-depth-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and value.get("build_identity_status") in {
            "UNSEALED_AWAITING_LLAMA_BENCH_AND_DSO_HASHES", "sealed"}
        and value.get("parent_identity_status") in {
            "UNSEALED_AWAITING_PASSED_PARENT_RECEIPTS", "sealed"}
        and selectors == {
            "revision": "qwen3.6-27b", "artifact_id": "qwen36-27b-unsloth-q8-0-82d411a",
            "quantization": "Q8_0", "runtime_family": "llama.cpp SYCL", "tp": 1,
            "mtp": 0, "graph_mode": "on", "kv": "q8_0",
            "active_context_tokens": DEPTHS,
        }
        and model.get("path") == str(MODEL) and model.get("size_bytes") == PARENT.MODEL_SIZE
        and model.get("sha256") == PARENT.MODEL_SHA256
        and model.get("direct_sha256") == PARENT.MODEL_SHA256
        and model.get("ordinary_sha256") == PARENT.MODEL_SHA256
        and model.get("embedded_mtp_capability") is False
        and all(reference.get(key) == item for key, item in Q8_OFF_REFERENCE.items())
        and source.get("path") == str(PARENT.SOURCE) and source.get("base_head") == PARENT.SOURCE_HEAD
        and source.get("required_modified_paths") == list(PARENT.SOURCE_PATH_HASHES)
        and source.get("post_apply_sha256") == PARENT.SOURCE_PATH_HASHES
        and (source.get("patch") or {}).get("sha256") == PARENT.PATCH_SHA256
        and runtime.get("build_root") == str(PARENT.BUILD_ROOT)
        and (runtime.get("binary") or {}).get("path") == str(BINARY)
        and (runtime.get("graph_backend") or {}).get("path") == str(GRAPH_BACKEND)
        and runtime.get("cmake_cache") == {"path": str(PARENT.CMAKE_CACHE), "sha256": PARENT.CMAKE_CACHE_SHA256}
        and runtime.get("makefile") == {"path": str(PARENT.MAKEFILE), "sha256": PARENT.MAKEFILE_SHA256}
        and runtime.get("sycl_flags") == {"path": str(PARENT.SYCL_FLAGS), "sha256": PARENT.SYCL_FLAGS_SHA256}
        and runtime.get("required_cmake") == PARENT.EXPECTED_CMAKE
        and value.get("environment") == expected_environment()
        and workload.get("execution_shape") == "seven-fresh-processes-one-depth-each"
        and workload.get("common_argv") == list(COMMON_ARGV)
        and workload.get("per_cell_depth_argv") == ["-d", "{active_context_tokens}"]
        and workload.get("timeout_seconds_per_cell") == 1800
        and workload.get("child_stdin") == "/dev/null"
        and evidence.get("device") == 0 and evidence.get("cache_limit") == 8
        and evidence.get("compatibility_rejected") == 0
        and evidence.get("device_unsupported") == 0 and evidence.get("cache_full") == 0
        and evidence.get("replayed_equals_requested") is True
        and evidence.get("all_seven_depths_required") is True
        and parent.get("campaign_id") == PARENT.CAMPAIGN_ID
        and parent.get("required_state") == "passed-parent-sentinel-only"
        and parent.get("required_same_build_root") is True
        and parent.get("required_exact_output_parity") is True
        and quality.get("status") == "pending-separate-parity-and-quality-receipt"
        and quality.get("same_model_build_and_q8_0_kv_required") is True
        and quality.get("graph_off_on_exact_output_parity_required") is True
        and quality.get("q8_0_kv_quality_battery_required") is True
        and quality.get("required_before_site_publication") is True
        and quality.get("site_publication_authority") is False
        and lifecycle.get("output_root") == str(RUN_ROOT) and lifecycle.get("exact_ack") == ACK
        and lifecycle.get("output_fstype") == "ext4"
        and lifecycle.get("required_locks") == list(BASE.CANONICAL_LOCKS)
        and lifecycle.get("artifacts_are_create_only") is True
        and lifecycle.get("live_origin_equality_required_prelaunch") is True
        and lifecycle.get("local_launch_head_and_packet_blobs_frozen_postlaunch") is True
        and lifecycle.get("live_origin_equality_required_postlaunch") is False
        and interpretation.get("speed_floor") is None
        and interpretation.get("graph_estimates_forbidden") is True
        and interpretation.get("measured_graph_cells_only") is True
        and interpretation.get("site_publication_authorized") is False
        and interpretation.get("record_or_submission_authorized") is False
        and interpretation.get("quality_claim_authorized") is False
        and interpretation.get("protected_graph_off_values_are_immutable") is True
        and interpretation.get("graph_on_cells_are_append_only") is True
        and interpretation.get("cross_kv_transfer_allowed") is False
    ):
        raise GateError("q8-KV graph exact-depth manifest invariant failed")


def require_sha(value: object, field: str) -> str:
    result = str(value)
    if SHA256_RE.fullmatch(result) is None:
        raise GateError(f"{field} is not sealed")
    return result


def require_sealed_build(manifest: Mapping[str, Any]) -> None:
    if manifest.get("build_identity_status") != "sealed":
        raise GateError("graph curve build identity is unsealed")
    runtime = manifest["runtime"]
    for name in ("binary", "graph_backend"):
        row = runtime[name]
        if not isinstance(row.get("size_bytes"), int) or row["size_bytes"] <= 0:
            raise GateError(f"{name} size is unsealed")
        require_sha(row.get("sha256"), f"{name} SHA-256")
    libraries = runtime.get("effective_shared_libraries")
    if not isinstance(libraries, list) or len(libraries) != 32:
        raise GateError("effective DSO closure is unsealed; exactly 32 rows are required")
    sonames: set[str] = set()
    for row in libraries:
        if not isinstance(row, list) or len(row) != 4 or not all(isinstance(item, str) for item in row):
            raise GateError("effective DSO row schema changed")
        if row[0] in sonames or not Path(row[2]).is_absolute():
            raise GateError("effective DSO closure is duplicated or non-canonical")
        require_sha(row[3], f"effective DSO {row[0]}")
        sonames.add(row[0])


def verify_json_receipt(path: Path, digest: str, label: str) -> dict[str, Any]:
    BASE.verify_artifact(path, None, require_sha(digest, label), label)
    value = BASE.load_json(path)
    if not isinstance(value, dict):
        raise GateError(f"{label} is not a JSON object")
    return value


def verify_parent(manifest: Mapping[str, Any]) -> dict[str, str]:
    if manifest.get("parent_identity_status") != "sealed":
        raise GateError("graph parent receipt identity is unsealed")
    parent = manifest["parent_sentinel"]
    terminal = verify_json_receipt(Path(parent["terminal_receipt"]), parent["terminal_sha256"], "parent terminal")
    identity = verify_json_receipt(Path(parent["campaign_identity_receipt"]), parent["campaign_identity_sha256"], "parent identity")
    parity = verify_json_receipt(Path(parent["parity_receipt"]), parent["parity_receipt_sha256"], "parent parity")
    snapshot = identity.get("manifest_snapshot") or {}
    parent_runtime = snapshot.get("runtime") or {}
    if not (
        terminal.get("campaign_id") == PARENT.CAMPAIGN_ID
        and terminal.get("state") == "passed-parent-sentinel-only"
        and terminal.get("cleanup_passed") is True
        and terminal.get("source_base_head") == PARENT.SOURCE_HEAD
        and terminal.get("source_port_patch_sha256") == PARENT.PATCH_SHA256
        and identity.get("campaign_id") == PARENT.CAMPAIGN_ID
        and parent_runtime.get("build_root") == manifest["runtime"]["build_root"]
        and (parent_runtime.get("graph_backend") or {}).get("sha256")
        == manifest["runtime"]["graph_backend"]["sha256"]
        and parity.get("passed") is True and parity.get("exact_output_bytes") is True
        and parity.get("same_binary") is True
    ):
        raise GateError("passed parent does not bind this exact graph build and parity")
    return {
        "terminal_sha256": parent["terminal_sha256"],
        "campaign_identity_sha256": parent["campaign_identity_sha256"],
        "parity_sha256": parent["parity_receipt_sha256"],
    }


def verify_references() -> None:
    for key in ("manifest", "runner", "result", "result_note"):
        BASE.verify_artifact(REPO / Q8_OFF_REFERENCE[key], None, Q8_OFF_REFERENCE[f"{key}_sha256"], f"accepted graph-off {key}")
    BASE.verify_artifact(ENGINE.PARSER, None, ENGINE.EXPECTED_PARSER_SHA256, "exact-depth parser")
    BASE.verify_artifact(ENGINE.PROTECTED, None, ENGINE.EXPECTED_PROTECTED_SHA256, "protected speed manifest")


def verify_build(manifest: Mapping[str, Any]) -> None:
    runtime = manifest["runtime"]
    BASE.verify_artifact(BINARY, runtime["binary"]["size_bytes"], runtime["binary"]["sha256"], "graph llama-bench")
    BASE.verify_artifact(GRAPH_BACKEND, runtime["graph_backend"]["size_bytes"], runtime["graph_backend"]["sha256"], "graph backend")
    BASE.verify_artifact(PARENT.CMAKE_CACHE, None, PARENT.CMAKE_CACHE_SHA256, "graph CMake cache")
    BASE.verify_artifact(PARENT.MAKEFILE, None, PARENT.MAKEFILE_SHA256, "graph Makefile")
    BASE.verify_artifact(PARENT.SYCL_FLAGS, None, PARENT.SYCL_FLAGS_SHA256, "graph SYCL flags")
    observed = PARENT.cmake_values(PARENT.CMAKE_CACHE.read_text(encoding="utf-8"))
    if any(observed.get(name) != item for name, item in PARENT.EXPECTED_CMAKE.items()):
        raise GateError("graph CMake settings changed")
    flags = PARENT.SYCL_FLAGS.read_text(encoding="utf-8")
    if "-DGGML_SYCL_GRAPH" not in flags or "GGML_SYCL_HOST_MEM_FALLBACK" in flags:
        raise GateError("graph/fallback compiler identity changed")


def static_check() -> tuple[dict[str, Any], dict[str, str]]:
    manifest = load_manifest()
    validate_manifest(manifest)
    require_sealed_build(manifest)
    parent = verify_parent(manifest)
    verify_references()
    PARENT.verify_source()
    verify_build(manifest)
    BASE.verify_artifact(BASE.MODEL_VERIFIER, None, BASE.MODEL_VERIFIER_SHA256, "model verifier")
    if not MODEL.is_file() or MODEL.stat().st_size != PARENT.MODEL_SIZE:
        raise GateError("target-only Q8 model is missing or changed")
    environment = ENGINE.oneapi_environment(RUN_ROOT / "static", manifest["environment"])
    if ENGINE.effective_libraries(BINARY, environment) != manifest["runtime"]["effective_shared_libraries"]:
        raise GateError("effective DSO closure changed")
    return manifest, parent


def packet_blobs() -> dict[str, str]:
    result: dict[str, str] = {}
    for relative in PACKET_PATHS:
        row = BASE.git_output("ls-tree", "HEAD", "--", relative)
        if not row or "\t" not in row:
            raise GateError(f"packet path is not tracked at HEAD: {relative}")
        metadata, observed = row.split("\t", 1)
        mode, kind, blob = metadata.split()
        if mode != "100644" or kind != "blob" or observed != relative:
            raise GateError(f"unexpected packet identity: {row}")
        if BASE.git_output("hash-object", relative) != blob:
            raise GateError(f"packet bytes differ from HEAD: {relative}")
        result[relative] = blob
    return result


def verify_clean_pushed_main(*, expected_head: str | None = None, expected_blobs: Mapping[str, str] | None = None) -> tuple[str, dict[str, str]]:
    if BASE.git_output("branch", "--show-current") != "main":
        raise GateError("lab repository must remain on main")
    if BASE.git_output("status", "--porcelain=v1", "--untracked-files=all"):
        raise GateError("lab repository must be clean")
    head = BASE.git_output("rev-parse", "HEAD")
    if expected_head is None:
        if BASE.git_output("rev-parse", "origin/main") != head:
            raise GateError("lab main is not pushed")
        remote = subprocess.check_output(
            ["/usr/bin/timeout", "30s", "/usr/bin/git", "-C", str(REPO), "ls-remote", "--exit-code", "origin", "refs/heads/main"],
            text=True, env=BASE.CONTROL_ENV,
        ).split()[0]
        if remote != head:
            raise GateError("lab main differs from live origin/main")
    elif head != expected_head:
        raise GateError("local launch HEAD changed during campaign")
    blobs = packet_blobs()
    if expected_blobs is not None and blobs != dict(expected_blobs):
        raise GateError("packet blob identity changed during campaign")
    return head, blobs


def verify_fresh_ext4() -> None:
    if RUN_ROOT.exists():
        raise GateError(f"create-only root already exists: {RUN_ROOT}")
    parent = BASE.nearest_existing(RUN_ROOT.parent)
    fstype = subprocess.check_output(
        ["/usr/bin/findmnt", "-n", "-o", "FSTYPE", "-T", str(parent)],
        text=True, env=BASE.CONTROL_ENV, timeout=30,
    ).strip()
    if fstype != "ext4":
        raise GateError(f"run root must resolve to ext4, got {fstype!r}")


def create_json(path: Path, value: Any) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)


def cell_argv(depth: int) -> tuple[str, ...]:
    if depth not in DEPTHS:
        raise GateError(f"undeclared active context: {depth}")
    return COMMON_ARGV + ("-d", str(depth))


def cell_environment(common: Mapping[str, str], root: Path) -> dict[str, str]:
    value = dict(common)
    value.update({
        "HOME": str(root / "home"), "XDG_CACHE_HOME": str(root / "xdg-cache"),
        "SYCL_CACHE_DIR": str(root / "sycl-cache"), "TMPDIR": str(root / "tmp"),
    })
    for name in BASE.UNSAFE_GRAPH_VARIABLES:
        value.pop(name, None)
    return value


def parse_graph_summary(text: str) -> dict[str, int]:
    summary = BASE.parse_graph_summary(text)
    if not (
        summary["device"] == 0
        and summary["cache_limit"] == 8
        and summary["compatibility_rejected"] == 0
        and summary["device_unsupported"] == 0
        and summary["cache_full"] == 0
        and summary["requested"] > 0
        and summary["cache_hit"] > 0
        and summary["cache_miss"] > 0
        and summary["direct_replay"] > 0
        and summary["recorded"] > 0
        and summary["created"] > 0
        and summary["replayed"] > 0
        and summary["replayed"] == summary["requested"]
    ):
        raise GateError(f"per-cell graph evidence gate failed: {summary}")
    return summary


def run_cell(depth: int, common_environment: Mapping[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root = RUN_ROOT / f"depth-{depth}"
    root.mkdir(exist_ok=False)
    for name in ("home", "xdg-cache", "sycl-cache", "tmp"):
        (root / name).mkdir(exist_ok=False)
    argv = cell_argv(depth)
    environment = cell_environment(common_environment, root)
    create_json(root / "identity.json", {"depth": depth, "argv": list(argv), "environment": environment})
    process = BASE.run_process_group(
        name=f"graph-depth-{depth}", argv=argv, environment=environment,
        stdout_path=root / "llama-bench.json", stderr_path=root / "llama-bench.stderr.log",
        timeout_seconds=1800,
    )
    rows = json.loads((root / "llama-bench.json").read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) or row.get("n_depth") != depth for row in rows):
        raise GateError(f"depth {depth} benchmark rows are absent or mislabeled")
    graph = parse_graph_summary((root / "llama-bench.stderr.log").read_text(encoding="utf-8", errors="replace"))
    receipt = {**process, "depth": depth, "graph_summary": graph, "row_count": len(rows), "passed": True}
    create_json(root / "receipt.json", receipt)
    return rows, receipt


def metadata(manifest: Mapping[str, Any], libraries: list[list[str]], receipts: list[dict[str, Any]]) -> dict[str, Any]:
    aggregate = {name: sum(row["graph_summary"][name] for row in receipts) for name in receipts[0]["graph_summary"]}
    return {
        "schema": "llama-bench-exact-depth-metadata-v1",
        "receipt_id": CAMPAIGN_ID,
        "declared_depths": DEPTHS,
        "binary": {**manifest["runtime"]["binary"], "source_head": PARENT.SOURCE_HEAD, "effective_shared_libraries": libraries},
        "model": manifest["model"],
        "argv": list(COMMON_ARGV + ("-d", ",".join(str(item) for item in DEPTHS))),
        "cell_argv": {str(depth): list(cell_argv(depth)) for depth in DEPTHS},
        "env": manifest["environment"],
        "cell_selectors": {key: item for key, item in manifest["selectors"].items() if key not in {"active_context_tokens", "graph_mode"}},
        "graph": {
            "requested": True,
            "capture": {"count": aggregate["created"], "source": "seven per-cell SYCL-GRAPH summaries"},
            "replay": {"count": aggregate["replayed"], "source": "seven per-cell SYCL-GRAPH summaries"},
            "per_cell": {str(row["depth"]): row["graph_summary"] for row in receipts},
        },
        "execution_shape": "seven-fresh-processes-one-depth-each",
    }


def execute(acknowledgement: str) -> int:
    if acknowledgement != ACK:
        raise GateError(f"exact acknowledgement required: {ACK}")
    inherited = BASE.reject_inherited_environment(os.environ)
    if inherited:
        raise GateError("refusing inherited runtime environment: " + ", ".join(inherited))
    head, blobs = verify_clean_pushed_main()
    verify_fresh_ext4()
    manifest, parent_receipts = static_check()
    model_stat = BASE.model_stat_fingerprint()
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    state, stage, error = "failed", "pre-root", None
    cell_receipts: list[dict[str, Any]] = []
    terminal_mask: set[signal.Signals] | None = None
    with BASE.campaign_locks() as locks:
        try:
            BASE.require_idle()
            RUN_ROOT.mkdir(mode=0o700, parents=True, exist_ok=False)
            stage = "model-verification"
            model_views = BASE.verify_model_views(RUN_ROOT / "model-view-verification")
            create_json(RUN_ROOT / "model-view-verification-receipt.json", model_views)
            stage = "gpu0-compute-gate"
            compute = RUN_ROOT / "gpu0-compute-gate"
            compute.mkdir(exist_ok=False)
            BASE.run_compute_gate(compute)
            BASE.require_idle()
            libraries = manifest["runtime"]["effective_shared_libraries"]
            common_environment = ENGINE.oneapi_environment(RUN_ROOT, manifest["environment"])
            all_rows: list[dict[str, Any]] = []
            for depth in DEPTHS:
                stage = f"graph-depth-{depth}"
                rows, receipt = run_cell(depth, common_environment)
                all_rows.extend(rows)
                cell_receipts.append(receipt)
                BASE.require_idle()
            create_json(RUN_ROOT / "llama-bench.json", all_rows)
            create_json(RUN_ROOT / "graph-evidence.json", cell_receipts)
            create_json(RUN_ROOT / "effective-shared-libraries.json", libraries)
            create_json(RUN_ROOT / "metadata.json", metadata(manifest, libraries, cell_receipts))
            stage = "exact-depth-parser"
            parser_env = {"PATH": "/usr/bin:/bin", "HOME": str(RUN_ROOT / "parser-home"), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
            (RUN_ROOT / "parser-home").mkdir(exist_ok=False)
            parser = BASE.run_process_group(
                name="exact-depth-parser",
                argv=[sys.executable, "-B", str(ENGINE.PARSER), "--bench-json", str(RUN_ROOT / "llama-bench.json"), "--metadata", str(RUN_ROOT / "metadata.json"), "--output", str(RUN_ROOT / "exact-depth-receipt.json"), "--create"],
                environment=parser_env, stdout_path=RUN_ROOT / "parser.stdout.json",
                stderr_path=RUN_ROOT / "parser.stderr.log", timeout_seconds=120,
            )
            receipt = BASE.load_json(RUN_ROOT / "exact-depth-receipt.json")
            if not (receipt.get("status") == "passed" and (receipt.get("gate") or {}).get("exact_cell_ready") is True and len(receipt.get("cells") or []) == 7):
                raise GateError("exact-depth parser did not accept all seven graph cells")
            stage = "postflight"
            post_head, post_blobs = verify_clean_pushed_main(expected_head=head, expected_blobs=blobs)
            post_manifest, post_parent = static_check()
            if post_manifest != manifest or post_parent != parent_receipts or BASE.model_stat_fingerprint() != model_stat:
                raise GateError("artifact, parent, or model identity changed during campaign")
            BASE.require_idle()
            create_json(RUN_ROOT / "postflight-seal.json", {"passed": True, "repo_head": post_head, "packet_blobs": post_blobs, "parser_process": parser})
            state, stage = "passed-measurement-only", "complete"
            terminal_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
        except BaseException as exc:
            terminal_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
            error = str(exc)
            if not RUN_ROOT.exists():
                signal.pthread_sigmask(signal.SIG_SETMASK, terminal_mask)
                raise GateError(error) from exc
            try:
                BASE.require_idle()
            except Exception as cleanup_exc:
                error = f"{error}; cleanup: {cleanup_exc}"
        try:
            terminal = {
                "schema": "neural.download.qwen36-llama-fa0-graph-exact-depth-terminal.v1",
                "campaign_id": CAMPAIGN_ID, "terminal": True, "state": state,
                "stage": stage, "started_utc": started,
                "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "repo_head": head, "locks": locks, "error": error,
                "cell_receipts": cell_receipts,
                "graph_estimates_used": False,
                "site_publication_authorized": False,
                "record_or_submission_authorized": False,
                "quality_claim_authorized": False,
                "q8_kv_parity_and_quality_gate_pending": True,
                "protected_graph_off_values_are_immutable": True,
                "evidence_sha256": {str(path.relative_to(RUN_ROOT)): BASE.sha256_file(path) for path in sorted(RUN_ROOT.rglob("*")) if path.is_file() and path.name != "terminal-receipt.json"},
            }
            create_json(RUN_ROOT / "terminal-receipt.json", terminal)
        finally:
            assert terminal_mask is not None
            signal.pthread_sigmask(signal.SIG_SETMASK, terminal_mask)
    print(json.dumps(terminal, indent=2, sort_keys=True))
    return 0 if state == "passed-measurement-only" else 20


def plan(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "campaign_id": CAMPAIGN_ID, "state": "preregistered-not-launched",
        "default_is_inert": True, "output_root": str(RUN_ROOT), "ack": ACK,
        "depths": DEPTHS, "kv": "q8_0", "graph": "on",
        "build_identity_status": manifest["build_identity_status"],
        "parent_identity_status": manifest["parent_identity_status"],
        "graph_estimates_forbidden": True,
        "site_publication_authorized": False, "writes_performed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--ack", default="")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest()
        validate_manifest(manifest)
        if args.execute:
            with BASE.caught_campaign_signals():
                return execute(args.ack)
        if args.check:
            static_check()
            result = {**plan(manifest), "status": "PASS", "mode": "check"}
        else:
            result = plan(manifest)
    except (GateError, BASE.GateError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail-closed r2 rerun for Qwen3.6 Q4_0 TP1 exact-depth evidence.

The default mode is inert. ``--check`` performs CPU-only static checks.
``--execute`` is the only mode that can launch the frozen GPU benchmark and
requires the exact acknowledgement. R1 is always quarantined; this runner can
publish only fresh r2 rows.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterator, Mapping


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
R1_RUNNER = HERE / "run-20260825-qwen36-q4-0-tp1-mtp0-q8kv-exact-depth-r1.py"
R1_RUNNER_SHA256 = "37eb4fddb3023ef0777ecb9dc9dc9f2bf529205c91f223d7b41ab6c239c2659f"
R1_MANIFEST = LANE / "data/2026-08-25-qwen36-q4-0-tp1-mtp0-q8kv-exact-depth-r1.json"
R1_MANIFEST_SHA256 = "b83dcb08ceaf8ad479489b322c6bf4c1cba8ae5ea52b9ce68d101bb04d2f77b0"
R1_FAILURE = LANE / "data/2026-08-25-qwen36-q4-0-tp1-mtp0-q8kv-exact-depth-r1-failure.json"
R1_FAILURE_SHA256 = "85a8a9eb412a1bf7e70a31730b22101fba9392dbf83c8590d1610163421a98db"
R1_FAILURE_NOTE = LANE / "notes/2026-08-25-qwen36-q4-0-tp1-mtp0-q8kv-exact-depth-r1-failure.md"
R1_FAILURE_NOTE_SHA256 = "1777f16c6dd7385329283d089b367d01535b40ed5abee1ff4d17d103e4d1505d"
R1_ROOT = Path("/home/steve/qwen36-matrix-runs/q4-0-tp1-mtp0-q8kv-exact-depth-20260825-r1")

MANIFEST = LANE / "data/2026-08-25-qwen36-q4-0-tp1-mtp0-q8kv-exact-depth-r2.json"
CAMPAIGN_ID = "qwen36-q4-0-tp1-mtp0-q8kv-exact-depth-20260825-r2"
STAGE_ID = "d1-exact-depths"
ACK = f"RUN {CAMPAIGN_ID} {STAGE_ID} r2"
RUN_ROOT = Path(
    "/home/steve/qwen36-matrix-runs/q4-0-tp1-mtp0-q8kv-exact-depth-20260825-r2"
)

SYCL_DSO = Path(
    "/home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp/bin/"
    "libggml-sycl.so.0.16.0"
)
SYCL_DSO_SHA256 = "5b53c03bf2702cc3a2b8146b1da8fd437f8b30400f3016bb2a75473c4345a6a3"
CMAKE_CACHE = Path("/home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp/CMakeCache.txt")
CMAKE_CACHE_SHA256 = "0930be75442696207b47bcaff3f0f19e2630b8e201a128659d903eba71070aab"
BUILD_NINJA = Path("/home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp/build.ninja")
BUILD_NINJA_SHA256 = "7c4ef3c5c9323ea778e816a5b4bb2fc15bd3fcdd1655565d6711ab84f0fb57af"
SOURCE_REPO = Path("/home/steve/src/llama.cpp")
SOURCE_COMMIT = "e3546c7948e3af463d0b401e6421d5a4c2faf565"
SOURCE_PATH = "ggml/src/ggml-sycl/ggml-sycl.cpp"
SOURCE_ENV_PATH = "ggml/src/ggml-sycl/common.cpp"
COMPETING_COMMIT = "c5f880c94ac3fda8237ecbf3fbb60cfe3a908983"

R1_EVIDENCE_SHA256 = {
    "llama-bench.json": "a2861354ff5b93e8d311cf86ac7b56ef7e7b352a7bb74dc5199760c93ae537d1",
    "llama-bench.stderr.log": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "metadata.json": "898b5e1503822bb5702043a3da22d5bd52ee822fec4de75b77c6537f0435eee7",
    "terminal-receipt.json": "13734d5da5a81921013d94b2fb7af89b5219238a9a02328c32454533e6e33d8a",
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R1 = load_module("qwen36_q4_exact_depth_r1_frozen", R1_RUNNER)
CampaignError = R1.CampaignError


def _require_fragment(text: str, fragment: str, label: str) -> None:
    if fragment not in text:
        raise CampaignError(f"graph-off attestation missing {label}: {fragment!r}")


def validate_manifest(value: Mapping[str, Any]) -> None:
    identity = value.get("run_identity") or {}
    binary = value.get("binary") or {}
    bench = value.get("benchmark_contract") or {}
    execution = value.get("execution_contract") or {}
    attestation = value.get("graph_off_attestation") or {}
    quarantine = value.get("r1_quarantine") or {}
    quality = value.get("quality_boundary") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-exact-depth-campaign.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and identity.get("artifact_id") == "qwen36-27b-unsloth-mtp-q4-0-20c9c45"
        and identity.get("artifact_revision") is None
        and identity.get("model_sha256") == R1.MODEL_SHA256
        and identity.get("tensor_parallel_size") == 1
        and identity.get("mtp_depth") == 0
        and identity.get("speculation_profile") == "target only"
        and identity.get("graph_mode") == "off"
        and identity.get("kv_cache_dtype") == "q8_0"
        and identity.get("runtime_build_number") == 9976
        and identity.get("runtime_commit") == SOURCE_COMMIT
        and binary.get("sha256") == R1.BINARY_SHA256
        and binary.get("implementation_sha256") == R1.IMPL_SHA256
        and binary.get("sycl_backend_sha256") == SYCL_DSO_SHA256
        and tuple(bench.get("declared_depths") or ()) == R1.DEPTHS
        and tuple(bench.get("argv") or ()) == R1.ARGV
        and bench.get("parser_sha256") == R1.PARSER_SHA256
        and bench.get("measurement_class") == "raw-engine"
        and bench.get("is_http_serving_metric") is False
        and bench.get("includes_quality_gate") is False
        and bench.get("speed_floor") is None
        and execution.get("exact_ack") == ACK
        and execution.get("run_root") == str(RUN_ROOT)
        and execution.get("create_only") is True
        and execution.get("required_locks") == [
            "/run/lock/muse-glimmer-gpu-exclusive.lock",
            "/tmp/b70-benchmark.lock",
            "/tmp/b70-gpu0.lock",
            "/run/user/1000/qwen36-b70-gpu-leases/gpu0.lock",
        ]
        and attestation.get("runtime_stderr_markers_required") is False
        and (attestation.get("controlled_environment") or {}).get(
            "GGML_SYCL_ENABLE_GRAPH"
        ) == "0"
        and quarantine.get("raw_row_reuse_allowed") is False
        and quarantine.get("cells_publishable_from_r1") == 0
        and quality.get("current_packet_quality_state") == "not-tested"
        and quality.get("historical_support_sha256")
        == R1.HISTORICAL_QUALITY_SHA256
    ):
        raise CampaignError("r2 campaign manifest invariant failed")


def verify_r1_quarantine() -> dict[str, Any]:
    expected = (
        (R1_RUNNER, R1_RUNNER_SHA256, "r1 runner"),
        (R1_MANIFEST, R1_MANIFEST_SHA256, "r1 manifest"),
        (R1_FAILURE, R1_FAILURE_SHA256, "r1 failure record"),
        (R1_FAILURE_NOTE, R1_FAILURE_NOTE_SHA256, "r1 failure note"),
    )
    for path, digest, label in expected:
        if not path.is_file() or R1.sha256_file(path) != digest:
            raise CampaignError(f"{label} is missing or changed: {path}")
    failure = R1.load_json(R1_FAILURE)
    if not (
        failure.get("status") == "failed-closed"
        and (failure.get("failure") or {}).get("cells_published") == 0
        and (failure.get("failure") or {}).get("retry_performed") is False
        and (failure.get("failure") or {}).get("raw_row_count") == 14
    ):
        raise CampaignError("r1 failure boundary changed")
    for name, digest in R1_EVIDENCE_SHA256.items():
        path = R1_ROOT / name
        if not path.is_file() or R1.sha256_file(path) != digest:
            raise CampaignError(f"r1 evidence changed: {path}")
    terminal = R1.load_json(R1_ROOT / "terminal-receipt.json")
    if terminal.get("status") != "failed":
        raise CampaignError("r1 terminal failure was rewritten")
    commit_time = R1.require_ok(
        R1.command(
            ["git", "-C", str(REPO), "show", "-s", "--format=%aI", COMPETING_COMMIT]
        ),
        "competing commit lookup",
    )
    if commit_time != "2026-08-25T10:26:34-04:00":
        raise CampaignError(f"competing commit identity changed: {commit_time}")
    touched = R1.require_ok(
        R1.command(
            ["git", "-C", str(REPO), "show", "--format=", "--name-only", COMPETING_COMMIT]
        ),
        "competing commit path lookup",
    )
    if "qwen38-q4km-tp1-batched-ladder-20260825-r1-attempt2/summary.json" not in touched:
        raise CampaignError("competing GPU0 result is not present in the pinned commit")
    return {
        "status": "quarantined",
        "r1_run_root": str(R1_ROOT),
        "cells_publishable": 0,
        "raw_row_reuse_allowed": False,
        "competing_commit": COMPETING_COMMIT,
        "competing_commit_time": commit_time,
    }


def verify_graph_off_attestation() -> dict[str, Any]:
    for path, digest, label in (
        (SYCL_DSO, SYCL_DSO_SHA256, "SYCL backend DSO"),
        (CMAKE_CACHE, CMAKE_CACHE_SHA256, "CMake cache"),
        (BUILD_NINJA, BUILD_NINJA_SHA256, "build.ninja"),
    ):
        if not path.is_file() or R1.sha256_file(path) != digest:
            raise CampaignError(f"{label} is missing or changed: {path}")

    cache_text = CMAKE_CACHE.read_text(encoding="utf-8")
    ninja_text = BUILD_NINJA.read_text(encoding="utf-8")
    _require_fragment(cache_text, "GGML_SYCL_GRAPH:BOOL=ON", "compile flag")
    _require_fragment(ninja_text, "-DGGML_SYCL_GRAPH", "compiler define")

    source = R1.require_ok(
        R1.command(
            ["git", "-C", str(SOURCE_REPO), "show", f"{SOURCE_COMMIT}:{SOURCE_PATH}"]
        ),
        "committed graph-gate source",
    )
    _require_fragment(
        source,
        'g_ggml_sycl_enable_graph = ggml_sycl_get_env("GGML_SYCL_ENABLE_GRAPH", 0);',
        "source environment load",
    )
    _require_fragment(
        source,
        "if (g_ggml_sycl_enable_graph) {",
        "source graph-entry guard",
    )
    env_source = R1.require_ok(
        R1.command(
            [
                "git", "-C", str(SOURCE_REPO), "show",
                f"{SOURCE_COMMIT}:{SOURCE_ENV_PATH}",
            ]
        ),
        "committed environment-reader source",
    )
    _require_fragment(
        env_source,
        'sscanf(user_device_string, " %u", &n) == 1',
        "source unsigned environment parser",
    )

    strings = R1.require_ok(R1.command(["strings", "-a", str(SYCL_DSO)]), "DSO strings")
    for fragment in (
        "GGML_SYCL_GRAPH: yes",
        "GGML_SYCL_ENABLE_GRAPH",
        "GGML_SYCL_GRAPH_CACHE_SIZE",
    ):
        _require_fragment(strings, fragment, "exact DSO string")

    get_env = R1.require_ok(
        R1.command(
            [
                "objdump", "-d", "-C", "--start-address=0x240060",
                "--stop-address=0x240098", str(SYCL_DSO),
            ]
        ),
        "get-env disassembly",
    )
    for fragment in (
        "0000000000240060 <ggml_sycl_get_env(char const*, int)>",
        "240065:",
        "mov    %esi,%ebx",
        "call   1a3930 <getenv@plt>",
        "call   1a3dc0 <__isoc23_sscanf@plt>",
        "24008c:",
        "mov    0xc(%rsp),%ebx",
        "240090:",
        "mov    %ebx,%eax",
    ):
        _require_fragment(get_env, fragment, "get-env machine-code proof")

    initialization = R1.require_ok(
        R1.command(
            [
                "objdump", "-d", "-C", "--start-address=0x1aa04b",
                "--stop-address=0x1aa08d", str(SYCL_DSO),
            ]
        ),
        "graph initialization disassembly",
    )
    for fragment in (
        "1aa04b:",
        "lea    0xa6c834(%rip),%rdi",
        "1aa052:",
        "xor    %esi,%esi",
        "1aa054:",
        "call   1a1fb0 <ggml_sycl_get_env(char const*, int)@plt>",
        "g_ggml_sycl_enable_graph",
        "1aa060:",
        "mov    %eax,(%rcx)",
        "g_ggml_sycl_graph_cache_size",
    ):
        _require_fragment(initialization, fragment, "graph initialization proof")

    dispatch = R1.require_ok(
        R1.command(
            [
                "objdump", "-d", "-C", "--start-address=0x1bafee",
                "--stop-address=0x1bb0c0", str(SYCL_DSO),
            ]
        ),
        "graph dispatch disassembly",
    )
    for fragment in (
        "1bafee:",
        "g_ggml_sycl_enable_graph",
        "1baff5:",
        "cmpl   $0x0,(%rax)",
        "1baff8:",
        "je     1bb0ae",
        "1bb0ae:",
        "call   1bce00 <ggml_backend_sycl_graph_compute_impl",
    ):
        _require_fragment(dispatch, fragment, "graph dispatch proof")

    if not (
        R1.CONTROLLED_ENV.get("GGML_SYCL_ENABLE_GRAPH") == "0"
        and R1.CONTROLLED_ENV.get("GGML_SYCL_GRAPH_CACHE_SIZE") == "0"
    ):
        raise CampaignError("controlled graph-off environment changed")
    return {
        "schema": "neural.download.qwen36-graph-off-static-attestation.v1",
        "status": "passed",
        "classification": "graph-off",
        "sycl_backend": {"path": str(SYCL_DSO), "sha256": SYCL_DSO_SHA256},
        "compile_support": {
            "GGML_SYCL_GRAPH": True,
            "meaning": "graph support compiled; runtime gate is authoritative",
        },
        "source_reference": {
            "commit": SOURCE_COMMIT,
            "graph_path": SOURCE_PATH,
            "environment_reader_path": SOURCE_ENV_PATH,
        },
        "machine_code": {
            "get_env": "0x240060",
            "graph_env_initialization": "0x1aa04b-0x1aa08d",
            "zero_bypass_to_ordinary_compute": "0x1bafee-0x1bb0b9",
        },
        "controlled_environment": {
            "GGML_SYCL_ENABLE_GRAPH": "0",
            "GGML_SYCL_GRAPH_CACHE_SIZE": "0",
        },
        "runtime_stderr_markers_used": False,
    }


def verify_static() -> tuple[dict[str, Any], list[dict[str, str]]]:
    manifest = R1.load_json(MANIFEST)
    validate_manifest(manifest)
    verify_r1_quarantine()
    R1.verify_artifact(R1.MODEL, R1.MODEL_SIZE, R1.MODEL_SHA256, "model")
    R1.verify_artifact(R1.BINARY, R1.BINARY_SIZE, R1.BINARY_SHA256, "llama-bench")
    if R1.sha256_file(R1.PARSER) != R1.PARSER_SHA256:
        raise CampaignError("exact-depth parser changed")
    if R1.sha256_file(R1.HISTORICAL_QUALITY) != R1.HISTORICAL_QUALITY_SHA256:
        raise CampaignError("historical quality citation changed")
    r1_manifest = R1.load_json(R1_MANIFEST)
    environment = R1.effective_environment(RUN_ROOT)
    libraries = R1.verify_libraries(r1_manifest, environment)
    implementation = next(
        (row for row in libraries if row["soname"] == "libllama-bench-impl.so"),
        None,
    )
    sycl = next((row for row in libraries if row["soname"] == "libggml-sycl.so.0"), None)
    if implementation is None or implementation["sha256"] != R1.IMPL_SHA256:
        raise CampaignError("exact llama-bench implementation is not effective")
    if sycl is None or sycl["sha256"] != SYCL_DSO_SHA256:
        raise CampaignError("attested SYCL backend is not the effective DSO")
    verify_graph_off_attestation()
    return manifest, libraries


@contextlib.contextmanager
def campaign_locks() -> Iterator[list[str]]:
    lock_paths = [
        Path("/run/lock/muse-glimmer-gpu-exclusive.lock"),
        Path("/tmp/b70-benchmark.lock"),
        Path("/tmp/b70-gpu0.lock"),
        Path(f"/run/user/{os.getuid()}/qwen36-b70-gpu-leases/gpu0.lock"),
    ]
    handles = []
    try:
        for path in lock_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = path.open("a+")
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise CampaignError(f"campaign lock is held: {path}") from exc
            handles.append(handle)
        yield [str(path) for path in lock_paths]
    finally:
        for handle in reversed(handles):
            handle.close()


def verify_idle() -> None:
    if R1.docker_ps():
        raise CampaignError("a Docker container is already running")
    processes = R1.command(
        [
            "pgrep",
            "-af",
            r"[E]ngineCore|[v]llm serve|[l]lama-server|[l]lama-bench|[l]lama-batched-bench",
        ]
    )
    if processes.returncode not in (0, 1):
        raise CampaignError("model-process scan failed")
    if processes.returncode == 0 and processes.stdout.strip():
        raise CampaignError("a model or benchmark process is already running")
    render_nodes = sorted(Path("/dev/dri").glob("renderD*"))
    if not render_nodes:
        raise CampaignError("no render nodes are present")
    for node in render_nodes:
        users = R1.command(["fuser", str(node)])
        if users.returncode not in (0, 1):
            raise CampaignError(f"render-node owner scan failed: {node}")
        if users.returncode == 0 and (users.stdout.strip() or users.stderr.strip()):
            raise CampaignError(f"a process already owns render node {node}")


def metadata(environment: Mapping[str, str]) -> dict[str, Any]:
    result = R1_METADATA(environment)
    proof = "pre-run exact-DSO static graph-off attestation plus controlled environment"
    result["graph"]["capture"]["source"] = proof
    result["graph"]["replay"]["source"] = proof
    result["graph"]["static_attestation"] = {
        "receipt": "graph-off-attestation.json",
        "sycl_backend_sha256": SYCL_DSO_SHA256,
        "runtime_stderr_markers_used": False,
    }
    return result


def run_benchmark(run_root: Path, environment: Mapping[str, str]) -> int:
    # Repeat all exclusion and graph gates under every held lock immediately
    # before the only GPU subprocess is created.
    verify_idle()
    attestation = verify_graph_off_attestation()
    attestation["campaign_id"] = CAMPAIGN_ID
    attestation["attested_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    R1.create_bytes(
        run_root / "graph-off-attestation.json", R1.canonical_bytes(attestation)
    )
    stdout_path = run_root / "llama-bench.json"
    stderr_path = run_root / "llama-bench.stderr.log"
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        result = subprocess.run(
            R1.ARGV,
            check=False,
            stdout=stdout,
            stderr=stderr,
            env=dict(environment),
        )
    if result.returncode != 0:
        raise CampaignError(f"llama-bench failed with rc={result.returncode}")
    try:
        raw = json.loads(stdout_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CampaignError("llama-bench stdout is not valid JSON") from exc
    if not isinstance(raw, list) or not raw:
        raise CampaignError("llama-bench stdout is not a nonempty JSON row array")
    return len(raw)


def terminal_receipt(**kwargs: Any) -> dict[str, Any]:
    result = R1_TERMINAL_RECEIPT(**kwargs)
    result["graph_off_attestation"] = {
        "path": "graph-off-attestation.json",
        "sycl_backend_sha256": SYCL_DSO_SHA256,
        "method": "pre-run exact-DSO static proof plus controlled environment",
        "runtime_stderr_markers_used": False,
    }
    result["r1_evidence_reused"] = False
    result["r1_cells_publishable"] = 0
    return result


# Retarget the already tested r1 lifecycle machinery while replacing the two
# broken boundaries: incomplete exclusion/locking and impossible log markers.
R1_METADATA = R1.metadata
R1_TERMINAL_RECEIPT = R1.terminal_receipt
R1.CAMPAIGN_ID = CAMPAIGN_ID
R1.STAGE_ID = STAGE_ID
R1.ACK = ACK
R1.RUN_ROOT = RUN_ROOT
R1.verify_static = verify_static
R1.campaign_locks = campaign_locks
R1.verify_idle = verify_idle
R1.metadata = metadata
R1.run_benchmark = run_benchmark
R1.terminal_receipt = terminal_receipt


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="show the inert plan")
    mode.add_argument("--check", action="store_true", help="run CPU-only static checks")
    mode.add_argument("--execute", action="store_true", help="launch fresh r2 GPU work")
    parser.add_argument("--ack", default="", help="exact execution acknowledgement")
    return parser


def main() -> int:
    args = make_parser().parse_args()
    try:
        manifest = R1.load_json(MANIFEST)
        validate_manifest(manifest)
        if args.execute:
            result = R1.execute(args.ack)
        elif args.check:
            _, libraries = verify_static()
            result = {
                "mode": "check",
                "status": "passed",
                "campaign_id": CAMPAIGN_ID,
                "graph_off_attestation": "passed",
                "r1_rows_reusable": False,
                "effective_shared_library_count": len(libraries),
                "writes_performed": False,
            }
        else:
            result = {
                "mode": "plan",
                "status": "planned-not-launched",
                "campaign_id": CAMPAIGN_ID,
                "exact_ack": ACK,
                "run_root": str(RUN_ROOT),
                "declared_depths": list(R1.DEPTHS),
                "r1_rows_reusable": False,
                "measurement_class": "raw-engine",
                "includes_quality_gate": False,
                "writes_performed": False,
            }
    except (CampaignError, OSError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

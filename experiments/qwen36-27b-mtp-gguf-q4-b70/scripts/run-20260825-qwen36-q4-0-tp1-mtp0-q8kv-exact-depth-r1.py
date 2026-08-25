#!/usr/bin/env python3
"""Fail-closed Qwen3.6 Q4_0 TP1 target-only exact-depth runner.

The default mode is an inert plan. ``--check`` performs CPU-only static
identity checks. ``--execute`` additionally requires the exact acknowledgement
and owns the locks, idle checks, GPU process, parser, and terminal receipt.
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
import subprocess
import sys
from typing import Any, Iterator, Mapping


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
MANIFEST = LANE / "data/2026-08-25-qwen36-q4-0-tp1-mtp0-q8kv-exact-depth-r1.json"
PARSER = REPO / "scripts/parse-llama-bench-exact-depth.py"
HISTORICAL_QUALITY = (
    REPO / "data/qwen27-cycle-timeline/no-spec-normal-20260712T160033Z/"
    "qwen27-q4_0-kv8-no-spec-graph0-strict128-20260712T160033Z.json"
)

CAMPAIGN_ID = "qwen36-q4-0-tp1-mtp0-q8kv-exact-depth-20260825-r1"
STAGE_ID = "d1-exact-depths"
ACK = f"RUN {CAMPAIGN_ID} {STAGE_ID} r1"
RUN_ROOT = Path(
    "/home/steve/qwen36-matrix-runs/q4-0-tp1-mtp0-q8kv-exact-depth-20260825-r1"
)
MODEL = Path("/mnt/usb-models/models/qwen36-27b-mtp-gguf/Qwen3.6-27B-Q4_0.gguf")
BINARY = Path("/home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp/bin/llama-bench")
MODEL_SIZE = 16056476800
MODEL_SHA256 = "20c9c45d4d25b492b82117960b5f715ef9daff75e4e14c4fb878fa3793fb379a"
BINARY_SIZE = 564624
BINARY_SHA256 = "90d4d23363825219d6cff02d59b73c3912fd42071694e8e215ba8cfc5d058aff"
IMPL_SHA256 = "f963fc1504afeff14bdd389f65a00d9b581e40056bef0c9b81e17e89fc0d79d5"
PARSER_SHA256 = "bd32939350062e104a526536357e6f1055b683adc9c520c76e4e3d42e563f66e"
HISTORICAL_QUALITY_SHA256 = (
    "1a72aeda183a7cb8f3b9cfb1d705e2cd64d47f887c9fab342be91e7bad78c49f"
)
DEPTHS = (0, 2048, 4096, 8192, 16384, 24576, 32768)

ARGV = (
    str(BINARY),
    "-m",
    str(MODEL),
    "-dev",
    "SYCL0",
    "-ngl",
    "99",
    "-sm",
    "layer",
    "-p",
    "2048",
    "-n",
    "128",
    "-d",
    "0,2048,4096,8192,16384,24576,32768",
    "-b",
    "2048",
    "-ub",
    "512",
    "-fa",
    "on",
    "-ctk",
    "q8_0",
    "-ctv",
    "q8_0",
    "-t",
    "16",
    "--poll",
    "50",
    "-r",
    "5",
    "-o",
    "json",
)

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

CONTROLLED_ENV = {
    "HOME": "/home/steve",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "LD_LIBRARY_PATH": ONEAPI_LIBRARY_PATH,
    "ONEAPI_DEVICE_SELECTOR": "level_zero:*",
    "ZE_AFFINITY_MASK": "0",
    "ZES_ENABLE_SYSMAN": "1",
    "UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS": "1",
    "SYCL_CACHE_PERSISTENT": "0",
    "GGML_SYCL_ENABLE_GRAPH": "0",
    "GGML_SYCL_GRAPH_CACHE_SIZE": "0",
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

REJECTED_PREFIXES = (
    "GGML_",
    "LLAMA_",
    "SYCL_",
    "UR_",
    "ZE_",
    "ZES_",
    "ONEAPI_",
    "OMP_",
    "KMP_",
    "MKL_",
)
REJECTED_EXACT = {"LD_LIBRARY_PATH", "LIBRARY_PATH"}
GRAPH_OFF_MARKERS = (
    "GGML_SYCL_ENABLE_GRAPH: 0",
    "GGML_SYCL_GRAPH_CACHE_SIZE: 0",
)


class CampaignError(RuntimeError):
    """Raised when a frozen campaign gate fails."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CampaignError(f"cannot load JSON: {path}") from exc
    if not isinstance(value, dict):
        raise CampaignError(f"expected JSON object: {path}")
    return value


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def create_bytes(path: Path, data: bytes) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(data)
    except FileExistsError as exc:
        raise CampaignError(f"refusing to overwrite: {path}") from exc


def command(
    argv: list[str] | tuple[str, ...],
    *,
    env: Mapping[str, str] | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        check=False,
        capture_output=True,
        text=True,
        env=None if env is None else dict(env),
        timeout=timeout,
    )


def require_ok(result: subprocess.CompletedProcess[str], label: str) -> str:
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise CampaignError(f"{label} failed (rc={result.returncode}): {detail[:500]}")
    return result.stdout.strip()


def validate_manifest(value: Mapping[str, Any]) -> None:
    identity = value.get("run_identity") or {}
    binary = value.get("binary") or {}
    bench = value.get("benchmark_contract") or {}
    execution = value.get("execution_contract") or {}
    quality = value.get("quality_boundary") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-exact-depth-campaign.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and identity.get("artifact_id") == "qwen36-27b-unsloth-mtp-q4-0-20c9c45"
        and identity.get("artifact_revision") is None
        and identity.get("model_sha256") == MODEL_SHA256
        and identity.get("tensor_parallel_size") == 1
        and identity.get("mtp_depth") == 0
        and identity.get("speculation_profile") == "target only"
        and identity.get("graph_mode") == "off"
        and identity.get("kv_cache_dtype") == "q8_0"
        and identity.get("runtime_build_number") == 9976
        and identity.get("runtime_commit") == "e3546c7948e3af463d0b401e6421d5a4c2faf565"
        and binary.get("sha256") == BINARY_SHA256
        and binary.get("implementation_sha256") == IMPL_SHA256
        and tuple(bench.get("declared_depths") or ()) == DEPTHS
        and tuple(bench.get("argv") or ()) == ARGV
        and bench.get("parser_sha256") == PARSER_SHA256
        and bench.get("measurement_class") == "raw-engine"
        and bench.get("is_http_serving_metric") is False
        and bench.get("includes_quality_gate") is False
        and bench.get("speed_floor") is None
        and bench.get("cross_quant_transfer_allowed") is False
        and execution.get("exact_ack") == ACK
        and execution.get("run_root") == str(RUN_ROOT)
        and execution.get("create_only") is True
        and quality.get("current_packet_quality_state") == "not-tested"
        and quality.get("historical_support_sha256") == HISTORICAL_QUALITY_SHA256
    ):
        raise CampaignError("campaign manifest invariant failed")
    libraries = value.get("resolved_shared_libraries")
    if not isinstance(libraries, list) or not libraries:
        raise CampaignError("manifest has no resolved shared-library identity")
    sonames = [entry.get("soname") for entry in libraries if isinstance(entry, dict)]
    if len(sonames) != len(libraries) or len(set(sonames)) != len(sonames):
        raise CampaignError("manifest shared-library sonames are invalid or repeated")


def reject_inherited_environment(environment: Mapping[str, str]) -> list[str]:
    return sorted(
        key
        for key in environment
        if key in REJECTED_EXACT or key.startswith(REJECTED_PREFIXES)
    )


def effective_environment(run_root: Path) -> dict[str, str]:
    result = dict(CONTROLLED_ENV)
    result["XDG_CACHE_HOME"] = str(run_root / "xdg-cache")
    result["TMPDIR"] = str(run_root / "tmp")
    return result


def parse_ldd_output(output: str) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("linux-vdso"):
            continue
        if "not found" in line:
            raise CampaignError(f"unresolved shared library: {line}")
        if "=>" in line:
            soname, remainder = (part.strip() for part in line.split("=>", 1))
            path = remainder.split(" ", 1)[0]
        elif line.startswith("/"):
            path = line.split(" ", 1)[0]
            soname = Path(path).name
        else:
            raise CampaignError(f"unrecognized ldd row: {line}")
        if not path.startswith("/"):
            raise CampaignError(f"shared library is not absolute: {line}")
        if soname in resolved:
            raise CampaignError(f"duplicate ldd soname: {soname}")
        resolved[soname] = str(Path(path).resolve(strict=True))
    if not resolved:
        raise CampaignError("ldd returned no effective shared libraries")
    return resolved


def verify_artifact(path: Path, size: int, digest: str, label: str) -> None:
    if not path.is_file():
        raise CampaignError(f"missing {label}: {path}")
    if path.stat().st_size != size:
        raise CampaignError(f"{label} size changed: {path.stat().st_size}")
    observed = sha256_file(path)
    if observed != digest:
        raise CampaignError(f"{label} SHA-256 changed: {observed}")


def verify_libraries(
    manifest: Mapping[str, Any], environment: Mapping[str, str]
) -> list[dict[str, str]]:
    output = require_ok(command(["ldd", str(BINARY)], env=environment), "ldd")
    observed_paths = parse_ldd_output(output)
    expected_rows = manifest["resolved_shared_libraries"]
    expected = {row["soname"]: row for row in expected_rows}
    if set(observed_paths) != set(expected):
        added = sorted(set(observed_paths) - set(expected))
        missing = sorted(set(expected) - set(observed_paths))
        raise CampaignError(
            f"effective library set changed: added={added}, missing={missing}"
        )
    receipt: list[dict[str, str]] = []
    for soname in sorted(expected):
        path = Path(observed_paths[soname])
        if str(path) != expected[soname]["realpath"]:
            raise CampaignError(f"effective path changed for {soname}: {path}")
        digest = sha256_file(path)
        if digest != expected[soname]["sha256"]:
            raise CampaignError(f"effective library changed for {soname}: {digest}")
        receipt.append({"soname": soname, "realpath": str(path), "sha256": digest})
    return receipt


def verify_static() -> tuple[dict[str, Any], list[dict[str, str]]]:
    manifest = load_json(MANIFEST)
    validate_manifest(manifest)
    verify_artifact(MODEL, MODEL_SIZE, MODEL_SHA256, "model")
    verify_artifact(BINARY, BINARY_SIZE, BINARY_SHA256, "llama-bench")
    if sha256_file(PARSER) != PARSER_SHA256:
        raise CampaignError("exact-depth parser changed")
    if sha256_file(HISTORICAL_QUALITY) != HISTORICAL_QUALITY_SHA256:
        raise CampaignError("historical quality citation changed")
    environment = effective_environment(RUN_ROOT)
    libraries = verify_libraries(manifest, environment)
    impl = next(
        (row for row in libraries if row["soname"] == "libllama-bench-impl.so"),
        None,
    )
    if impl is None or impl["sha256"] != IMPL_SHA256:
        raise CampaignError("exact llama-bench implementation is not effective")
    return manifest, libraries


def verify_repo() -> str:
    branch = require_ok(
        command(["git", "-C", str(REPO), "branch", "--show-current"]), "Git branch"
    )
    if branch != "main":
        raise CampaignError(f"campaign requires main, got {branch!r}")
    status = require_ok(
        command(
            [
                "git",
                "-C",
                str(REPO),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ]
        ),
        "Git status",
    )
    if status:
        raise CampaignError("campaign requires a clean repository")
    head = require_ok(
        command(["git", "-C", str(REPO), "rev-parse", "HEAD"]), "Git HEAD"
    )
    remote = require_ok(
        command(
            [
                "git",
                "-C",
                str(REPO),
                "ls-remote",
                "--exit-code",
                "origin",
                "refs/heads/main",
            ],
            timeout=60,
        ),
        "live origin/main lookup",
    )
    fields = remote.split()
    if len(fields) != 2 or not re.fullmatch(r"[0-9a-f]{40}", fields[0]):
        raise CampaignError("live origin/main lookup returned an invalid identity")
    if fields[0] != head:
        raise CampaignError(
            f"local main is not pushed: local={head}, remote={fields[0]}"
        )
    return head


def nearest_existing(path: Path) -> Path:
    current = path
    while not current.exists():
        parent = current.parent
        if parent == current:
            raise CampaignError(f"no existing ancestor for {path}")
        current = parent
    return current


def verify_fresh_ext4() -> None:
    if RUN_ROOT.exists():
        raise CampaignError(f"create-only run root already exists: {RUN_ROOT}")
    existing = nearest_existing(RUN_ROOT.parent)
    fstype = require_ok(
        command(["findmnt", "-n", "-o", "FSTYPE", "-T", str(existing)]),
        "run-root filesystem",
    )
    if fstype != "ext4":
        raise CampaignError(f"run root must resolve to ext4, got {fstype!r}")


@contextlib.contextmanager
def campaign_locks() -> Iterator[list[str]]:
    lock_paths = [
        Path("/run/lock/muse-glimmer-gpu-exclusive.lock"),
        Path("/tmp/b70-benchmark.lock"),
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


def docker_ps() -> str:
    password_file = Path("/home/steve/SUDOPASSWORD.txt")
    if not password_file.is_file():
        raise CampaignError("sudo password file is unavailable for container idle scan")
    with password_file.open("rb") as password:
        result = subprocess.run(
            ["sudo", "-S", "-p", "", "docker", "ps", "-q"],
            stdin=password,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            check=False,
            timeout=30,
        )
    if result.returncode != 0:
        raise CampaignError("Docker running-container scan failed")
    return result.stdout.decode("utf-8", errors="strict").strip()


def verify_idle() -> None:
    if docker_ps():
        raise CampaignError("a Docker container is already running")
    processes = command(
        ["pgrep", "-af", r"[E]ngineCore|[v]llm serve|[l]lama-server|[l]lama-bench"]
    )
    if processes.returncode not in (0, 1):
        raise CampaignError("model-process scan failed")
    if processes.returncode == 0 and processes.stdout.strip():
        raise CampaignError("a model process is already running")
    render_nodes = sorted(Path("/dev/dri").glob("renderD*"))
    if not render_nodes:
        raise CampaignError("no render nodes are present")
    for node in render_nodes:
        users = command(["fuser", str(node)])
        if users.returncode not in (0, 1):
            raise CampaignError(f"render-node owner scan failed: {node}")
        if users.returncode == 0 and (users.stdout.strip() or users.stderr.strip()):
            raise CampaignError(f"a process already owns render node {node}")


def metadata(environment: Mapping[str, str]) -> dict[str, Any]:
    return {
        "schema": "llama-bench-exact-depth-metadata-v1",
        "receipt_id": CAMPAIGN_ID,
        "declared_depths": list(DEPTHS),
        "binary": {
            "path": str(BINARY),
            "sha256": BINARY_SHA256,
            "build_number": 9976,
            "commit": "e3546c7948e3af463d0b401e6421d5a4c2faf565",
            "build_tree_status": "dirty-build",
            "implementation_sha256": IMPL_SHA256,
        },
        "model": {
            "path": str(MODEL),
            "sha256": MODEL_SHA256,
            "repository": "unsloth/Qwen3.6-27B-MTP-GGUF",
            "revision": "checksum-pinned-no-captured-hugging-face-revision",
            "size_bytes": MODEL_SIZE,
            "quantization": "Q4_0",
            "embedded_mtp_capability": True,
        },
        "argv": list(ARGV),
        "env": dict(sorted(environment.items())),
        "cell_selectors": {
            "weight_revision": "qwen3.6-27b",
            "artifact_id": "qwen36-27b-unsloth-mtp-q4-0-20c9c45",
            "quantization": "Q4_0",
            "runtime_family": "llama.cpp SYCL",
            "runtime_build": "9976-e3546c794-dirty-binary-pinned",
            "tp": 1,
            "mtp": 0,
            "speculation_profile": "target only",
            "kv": "q8_0",
        },
        "graph": {
            "requested": False,
            "capture": {
                "count": 0,
                "source": "controlled environment and runtime stderr markers",
            },
            "replay": {
                "count": 0,
                "source": "controlled environment and runtime stderr markers",
            },
        },
    }


def verify_graph_off_log(text: str) -> None:
    missing = [marker for marker in GRAPH_OFF_MARKERS if marker not in text]
    if missing:
        raise CampaignError(f"runtime did not attest graph-off markers: {missing}")


def run_benchmark(run_root: Path, environment: Mapping[str, str]) -> int:
    stdout_path = run_root / "llama-bench.json"
    stderr_path = run_root / "llama-bench.stderr.log"
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        result = subprocess.run(
            ARGV,
            check=False,
            stdout=stdout,
            stderr=stderr,
            env=dict(environment),
        )
    if result.returncode != 0:
        raise CampaignError(f"llama-bench failed with rc={result.returncode}")
    verify_graph_off_log(stderr_path.read_text(encoding="utf-8", errors="replace"))
    try:
        raw = json.loads(stdout_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CampaignError("llama-bench stdout is not valid JSON") from exc
    if not isinstance(raw, list) or not raw:
        raise CampaignError("llama-bench stdout is not a nonempty JSON row array")
    return len(raw)


def run_parser(run_root: Path) -> tuple[dict[str, Any], str]:
    receipt_path = run_root / "exact-depth-receipt.json"
    result = command(
        [
            sys.executable,
            "-B",
            str(PARSER),
            "--bench-json",
            str(run_root / "llama-bench.json"),
            "--metadata",
            str(run_root / "metadata.json"),
            "--output",
            str(receipt_path),
            "--create",
        ],
        timeout=300,
    )
    output = require_ok(result, "exact-depth parser")
    try:
        summary = json.loads(output)
    except json.JSONDecodeError as exc:
        raise CampaignError("exact-depth parser returned invalid JSON") from exc
    if not (
        summary.get("status") == "created"
        and summary.get("exact_cell_ready") is True
        and summary.get("declared_depths") == list(DEPTHS)
        and summary.get("graph_classification") == "off"
    ):
        raise CampaignError("exact-depth parser summary gate failed")
    receipt = load_json(receipt_path)
    if not (
        receipt.get("status") == "passed"
        and (receipt.get("gate") or {}).get("exact_cell_ready") is True
        and len(receipt.get("cells") or []) == 7
        and (receipt.get("measurement") or {}).get("classification") == "raw-engine"
        and (receipt.get("measurement") or {}).get("is_http_serving_metric") is False
        and (receipt.get("measurement") or {}).get("includes_quality_gate") is False
    ):
        raise CampaignError("exact-depth receipt gate failed")
    return receipt, sha256_file(receipt_path)


def terminal_receipt(
    *,
    status: str,
    stage: str,
    started: str,
    repo_head: str,
    locks: list[str],
    libraries: list[dict[str, str]],
    detail: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema": "neural.download.qwen36-llama-exact-depth-terminal.v1",
        "campaign_id": CAMPAIGN_ID,
        "stage_id": STAGE_ID,
        "status": status,
        "stage": stage,
        "started_utc": started,
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "repo_head": repo_head,
        "run_root": str(RUN_ROOT),
        "locks": locks,
        "model_sha256": MODEL_SHA256,
        "binary_sha256": BINARY_SHA256,
        "implementation_sha256": IMPL_SHA256,
        "effective_shared_libraries": libraries,
        "measurement_class": "raw-engine",
        "is_http_serving_metric": False,
        "current_packet_quality_state": "not-tested",
        "historical_quality_citation": {
            "path": str(HISTORICAL_QUALITY.relative_to(REPO)),
            "sha256": HISTORICAL_QUALITY_SHA256,
            "transferred_to_current_cells": False,
        },
        "speed_floor": None,
        "detail": dict(detail),
    }


def execute(ack: str) -> dict[str, Any]:
    if ack != ACK:
        raise CampaignError(f"exact acknowledgement required: {ACK}")
    inherited = reject_inherited_environment(os.environ)
    if inherited:
        raise CampaignError(f"refusing inherited runtime environment: {inherited}")
    repo_head = verify_repo()
    verify_fresh_ext4()
    manifest, libraries = verify_static()
    del manifest
    environment = effective_environment(RUN_ROOT)
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    with campaign_locks() as locks:
        verify_idle()
        RUN_ROOT.mkdir(parents=True, exist_ok=False)
        stage = "created-run-root"
        try:
            (RUN_ROOT / "xdg-cache").mkdir()
            (RUN_ROOT / "tmp").mkdir()
            metadata_path = RUN_ROOT / "metadata.json"
            create_bytes(metadata_path, canonical_bytes(metadata(environment)))
            stage = "llama-bench"
            raw_rows = run_benchmark(RUN_ROOT, environment)
            stage = "parser"
            receipt, receipt_sha = run_parser(RUN_ROOT)
            detail = {
                "passed": True,
                "raw_row_count": raw_rows,
                "exact_depth_receipt": "exact-depth-receipt.json",
                "exact_depth_receipt_sha256": receipt_sha,
                "cell_count": len(receipt["cells"]),
                "declared_depths": list(DEPTHS),
                "graph_classification": receipt["graph"]["classification"],
            }
            terminal = terminal_receipt(
                status="passed",
                stage="complete",
                started=started,
                repo_head=repo_head,
                locks=locks,
                libraries=libraries,
                detail=detail,
            )
            create_bytes(RUN_ROOT / "terminal-receipt.json", canonical_bytes(terminal))
            return terminal
        except Exception as exc:
            failure = terminal_receipt(
                status="failed",
                stage=stage,
                started=started,
                repo_head=repo_head,
                locks=locks,
                libraries=libraries,
                detail={"passed": False, "reason": str(exc)},
            )
            terminal_path = RUN_ROOT / "terminal-receipt.json"
            if not terminal_path.exists():
                create_bytes(terminal_path, canonical_bytes(failure))
            raise


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="show the inert plan")
    mode.add_argument("--check", action="store_true", help="run static CPU checks")
    mode.add_argument("--execute", action="store_true", help="launch the frozen run")
    parser.add_argument("--ack", default="", help="exact execution acknowledgement")
    return parser


def main() -> int:
    args = make_parser().parse_args()
    try:
        manifest = load_json(MANIFEST)
        validate_manifest(manifest)
        if args.execute:
            result = execute(args.ack)
        elif args.check:
            _, libraries = verify_static()
            result = {
                "mode": "check",
                "status": "passed",
                "campaign_id": CAMPAIGN_ID,
                "effective_shared_library_count": len(libraries),
                "writes_performed": False,
            }
        else:
            result = {
                "mode": "plan",
                "status": "planned",
                "campaign_id": CAMPAIGN_ID,
                "exact_ack": ACK,
                "run_root": str(RUN_ROOT),
                "declared_depths": list(DEPTHS),
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

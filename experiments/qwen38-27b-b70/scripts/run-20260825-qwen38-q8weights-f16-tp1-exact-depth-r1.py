#!/usr/bin/env python3
"""Run the frozen Qwen3.8 Q8_0-weight/F16-KV TP1 exact-depth curve."""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterator


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
BASE_RUNNER = LANE / "scripts/run-20260825-qwen38-q4kxl-q8-tp1-exact-depth-r1.py"
BASE_MANIFEST = LANE / "data/2026-08-25-qwen38-q4kxl-q8-tp1-exact-depth-prereg.json"
MANIFEST = LANE / "data/2026-08-25-qwen38-q8weights-f16-tp1-exact-depth-prereg.json"
EXPECTED_BASE_RUNNER_SHA256 = (
    "c30e9cee51bd4f5083f4ab57efca794fa89caec2a0e0e1aaf427b02c00b78875"
)
EXPECTED_BASE_MANIFEST_SHA256 = (
    "86775bd326675c7d66d27695d2b9ec8bf8bdd320181efffac01eefc4bf572af4"
)
CAMPAIGN_ID = "qwen38-q8weights-f16-tp1-exact-depth-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"
SOURCE_HEAD = "fa0f3b25a47f346858a4d0d169f5181aa424b110"
DEPTHS = [0, 2048, 4096, 8192, 16384, 24576, 32768]
LOCK_PATHS = [
    Path("/run/lock/muse-glimmer-gpu-exclusive.lock"),
    Path("/tmp/b70-benchmark.lock"),
    Path("/tmp/b70-gpu0.lock"),
    Path(f"/run/user/{os.getuid()}/qwen36-b70-gpu-leases/gpu0.lock"),
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


if sha256_file(BASE_RUNNER) != EXPECTED_BASE_RUNNER_SHA256:
    raise RuntimeError("frozen exact-depth base runner changed")

_spec = importlib.util.spec_from_file_location(
    "qwen38_q4xl_exact_depth_base", BASE_RUNNER
)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot import {BASE_RUNNER}")
BASE = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = BASE
_spec.loader.exec_module(BASE)

GateError = BASE.GateError


def load_manifest() -> dict[str, Any]:
    if sha256_file(BASE_MANIFEST) != EXPECTED_BASE_MANIFEST_SHA256:
        raise GateError("frozen runtime-identity manifest changed")
    try:
        value = json.loads(MANIFEST.read_text(encoding="utf-8"))
        identity = json.loads(BASE_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"invalid campaign manifest: {exc}") from exc
    reference = (value.get("runtime") or {}).get(
        "effective_shared_libraries_from"
    ) or {}
    if not (
        reference.get("path") == str(BASE_MANIFEST.relative_to(REPO))
        and reference.get("sha256") == EXPECTED_BASE_MANIFEST_SHA256
        and reference.get("row_count") == 32
    ):
        raise GateError("runtime-identity reference changed")
    value["runtime"]["effective_shared_libraries"] = identity["runtime"][
        "effective_shared_libraries"
    ]
    return value


def validate_manifest(value: dict[str, Any]) -> None:
    selectors = value.get("selectors") or {}
    runtime = value.get("runtime") or {}
    lifecycle = value.get("lifecycle") or {}
    interpretation = value.get("interpretation") or {}
    model = value.get("model") or {}
    fit = value.get("fit_assessment") or {}
    if not (
        value.get("schema") == "neural.download.qwen38-llama-exact-depth-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and selectors.get("revision") == "qwen3.8-27b"
        and selectors.get("artifact_id") == "qwen38-27b-ggmlorg-q8-0-0669b98"
        and selectors.get("quantization") == "Q8_0"
        and selectors.get("tp") == 1
        and selectors.get("mtp") == 0
        and selectors.get("graph_mode") == "off"
        and selectors.get("kv") == "f16"
        and selectors.get("active_context_tokens") == DEPTHS
        and model.get("bytes") == 28595763552
        and model.get("sha256")
        == "f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8"
        and model.get("present_at_preregistration") is False
        and runtime.get("source_head") == SOURCE_HEAD
        and lifecycle.get("exact_ack") == ACK
        and lifecycle.get("output_fstype") == "ext4"
        and lifecycle.get("lock_paths") == [str(path) for path in LOCK_PATHS]
        and lifecycle.get("artifacts_are_create_only") is True
        and fit.get("risk") == "tight-unmeasured-fit"
        and interpretation.get("speed_floor") is None
        and interpretation.get("http_serving_metric") is False
        and interpretation.get("new_quality_gate") is False
        and interpretation.get("historical_featured_speeds_are_immutable") is True
    ):
        raise GateError("campaign manifest invariant failed")
    expected = [
        runtime["binary"]["path"],
        "-m",
        model["path"],
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
        "f16",
        "-ctv",
        "f16",
        "-t",
        "16",
        "--poll",
        "50",
        "-r",
        "5",
        "-o",
        "json",
    ]
    if value.get("argv") != expected:
        raise GateError("llama-bench argv differs from preregistration")
    libraries = runtime.get("effective_shared_libraries")
    if not isinstance(libraries, list) or len(libraries) != 32:
        raise GateError("exactly 32 effective shared-library rows are required")
    if len({row[0] for row in libraries if len(row) == 4}) != 32:
        raise GateError("shared-library inventory is malformed or duplicated")


def active_model_processes() -> list[str]:
    matches: list[str] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            comm = (entry / "comm").read_text().strip()
            cmdline = (
                (entry / "cmdline")
                .read_bytes()
                .replace(b"\0", b" ")
                .decode(errors="replace")
            )
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if (
            comm.startswith("llama-bench")
            or comm.startswith("llama-server")
            or "llama-batched-bench" in cmdline
            or "vllm.entrypoints" in cmdline
            or "vllm serve" in cmdline
            or "VLLM::EngineCore" in cmdline
        ):
            matches.append(f"{entry.name}:{comm}")
    return matches


@contextlib.contextmanager
def campaign_locks() -> Iterator[None]:
    handles = []
    try:
        LOCK_PATHS[-1].parent.mkdir(parents=True, exist_ok=True)
        for path in LOCK_PATHS:
            handle = path.open("a+b")
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise GateError(f"campaign lock is held: {path}") from exc
            handles.append(handle)
        yield
    finally:
        for handle in reversed(handles):
            handle.close()


_base_static_check = BASE.static_check


def static_check() -> dict[str, Any]:
    if sha256_file(BASE_RUNNER) != EXPECTED_BASE_RUNNER_SHA256:
        raise GateError("frozen exact-depth base runner changed")
    return _base_static_check()


# Reuse the already-certified lifecycle implementation, but replace every
# campaign-specific global and the two safety surfaces hardened after its run.
BASE.MANIFEST = MANIFEST
BASE.CAMPAIGN_ID = CAMPAIGN_ID
BASE.ACK = ACK
BASE.SOURCE_HEAD = SOURCE_HEAD
BASE.load_manifest = load_manifest
BASE.validate_manifest = validate_manifest
BASE.active_model_processes = active_model_processes
BASE.campaign_locks = campaign_locks
BASE.static_check = static_check

metadata = BASE.metadata
reject_inherited_runtime_environment = BASE.reject_inherited_runtime_environment
write_json_exclusive = BASE.write_json_exclusive
plan = BASE.plan
execute = BASE.execute


def main(argv: list[str] | None = None) -> int:
    return BASE.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())

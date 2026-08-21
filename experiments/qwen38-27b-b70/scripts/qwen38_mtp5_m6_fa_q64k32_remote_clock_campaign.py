#!/usr/bin/env python3
"""Fail-closed orchestration for the two-B70 remote Q64K32 clock screen.

This module is deliberately CPU/import safe.  Its source authorization switch
is false: ``supervise`` and ``worker`` cannot start a process until a later,
reviewed commit freezes the reference-host device identities and the captured
xpu-smi JSON schema.  ``audit`` and ``validate-terminal`` are read-only.
"""

from __future__ import annotations

import argparse
import copy
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import re
import signal
import socket
import stat
import subprocess
import sys
import time
from typing import Any
import statistics


SCHEMA_TERMINAL = "qwen38-q64k32-remote-clock-arm-terminal-v1"
SCHEMA_CAMPAIGN = "qwen38-q64k32-remote-clock-campaign-v1"
SCHEMA_RESTORATION = "qwen38-q64k32-remote-clock-restoration-terminal-v1"
REMOTE_HOSTNAME = "steve-TURIND8-2L2T"
REMOTE_REPO = Path("/home/steve/b70-optimization-lab")
REMOTE_PYTHON = Path("/home/steve/.venvs/vllm-xpu/bin/python")
CONTROL_STAGE = Path("/home/steve/staged-xpu-commitfix-graphfa-composite-20260820")
CANDIDATE_ROOT = Path("/home/steve/qwen38-m6-head256-q64k32-attn-override-20260821-r2")
CANDIDATE_STAGE = CANDIDATE_ROOT / "runtime"
CANDIDATE_MANIFEST = CANDIDATE_ROOT / "qwen38-m6-head256-q64k32-r2-candidate-stage.json"
CANDIDATE_GRAPH = CANDIDATE_ROOT / "qwen38-m6-head256-q64k32-r2-candidate.graph.sha256"
RESULT_ROOT = Path("/home/steve/qwen38-mtp5-m6-fa-q64k32-remote-clock-abba-20260821-r1")

# Launch authorization is intentionally source-scoped, not an environment or
# CLI override.  A future reviewed commit must freeze every value below.
CAMPAIGN_LAUNCH_AUTHORIZED = False
# The shell currently waits on the supervisor in the foreground; a separately
# reviewed driver-level ownership/cleanup state machine is required before the
# launch gate may be enabled, so a shell-only signal cannot restore clocks
# while a worker group is still alive.
DRIVER_SIGNAL_OWNERSHIP_AUTHORIZED = False
CLOCK_WRITER_EXCLUSION_AUTHORIZED = False
DRIVER_ENVIRONMENT_AUTHORIZED = False
AUTHORIZED_REMOTE_REPO_HEAD: str | None = None
AUTHORIZED_DEVICE_IDENTITIES: dict[int, dict[str, str]] | None = None
AUTHORIZED_XPU_SMI_QUERY_SCHEMA_SHA256: str | None = None
AUTHORIZED_XPU_SMI_FIELD_PATHS: dict[str, tuple[str | int, ...]] | None = None
AUTHORIZED_XPU_SMI_PATH: str | None = None
AUTHORIZED_XPU_SMI_SHA256: str | None = None
AUTHORIZED_XPU_SMI_VERSION: str | None = None
AUTHORIZED_STAGE_INVENTORY_SHA256: str | None = None
AUTHORIZED_SYSTEM_RUNTIME_LIBRARIES: dict[str, str] | None = None
EXPECTED_DEVICE_NAME = "Intel(R) Arc(TM) Pro B70 Graphics"

Q64_QUALIFIER_REL = Path(
    "experiments/qwen38-27b-b70/scripts/qwen38_mtp5_m6_fa_q64k32_operator.py"
)
BASE_QUALIFIER_REL = Path(
    "experiments/qwen38-27b-b70/scripts/qwen38_mtp5_m6_fa_operator.py"
)
PATCH_REL = Path(
    "experiments/qwen38-27b-b70/patches/"
    "vllm-xpu-kernels-qwen38-m6-head256-q64k32-chunk-prefill-r2-20260821.patch"
)
BUILD_HELPER_REL = Path(
    "experiments/qwen38-27b-b70/scripts/"
    "build-qwen38-m6-head256-q64k32-attn-override-r2-20260821.sh"
)
SOURCE_HASHES = {
    Q64_QUALIFIER_REL: "31862ea6a8b9e11a59d643e0d3500179d938261e62b93fb920439c664ce21fbc",
    BASE_QUALIFIER_REL: "0dd7b945ef35a11ff4d0a1ec085e604920524b996d539e089d89b4a019a5de1f",
    PATCH_REL: "9386432015f5c9cd330dd7cfb785a16f259cce8563f44da9f812dcceb342138a",
    BUILD_HELPER_REL: "11480161dce25cba56e00f2f48c95d74164bac1f5af2dbc945eddceff6d57d47",
}

RUNTIME_FILES = {
    "vllm_xpu_kernels/_vllm_fa2_C.abi3.so": (
        "33938cdd2436684dcb76108a4db43e4ab0314406ad537fcd3732a005f7d23739"
    ),
    "vllm_xpu_kernels/flash_attn_interface.py": (
        "869c79f5f678252c341cfb8fb5cf9ee34f95c3d2debf4d169b759510da432480"
    ),
    "vllm_xpu_kernels/libattn_stock.so": (
        "3cbd3ed2ff51a477e6746b3e5860c070d093fd2d29b0b7a58e6dd081e9ad1289"
    ),
}
CONTROL_DEVICE_SHA256 = (
    "604f1b328870f2c41ef1d05c4d6016c34d222033d905877b0f9a2ff0c66b2a0c"
)
CANDIDATE_DEVICE_SHA256 = (
    "01a5b35b5a9c6321b436b137f95403db9e45ce4aabb44257dc7e4f45c84aecf5"
)
CONTROL_GRAPH_SHA256 = (
    "47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da"
)
CANDIDATE_GRAPH_SHA256 = (
    "d662dba3927fac706ff221902f536b67178b6875f66604597a1f2fe98a4defc4"
)

FIXTURES = {
    128: {
        "fixture_seed": 380128,
        "fixture_sha256": "0acb368f76405cfab88e47944437d0399bce0866fe9452096d3d5e0a2c9570cd",
        "oracle_sha256": "5a9759d1bf2b3eeea8eb4b34ba40e259d7e356285b28f0edcd36bda4a92e2a2e",
    },
    1024: {
        "fixture_seed": 381024,
        "fixture_sha256": "c2ac934353a92c6925a93f75aad559a7c2d2f17c6bd5e4e3b5b2e8b6a2e5324d",
        "oracle_sha256": "cb1fff93c03d3b9b266a1fe132cd1d61917613332d1be78b95167f13d8d2aaa8",
    },
    1300: {
        "fixture_seed": 381300,
        "fixture_sha256": "d5044ce346d2b4f97745c42341c85572e205e95d3bee0bc1baa5c84403771c3a",
        "oracle_sha256": "9b55fe30569595d19e21222a66bdbe460f8f405174fcab2a4807f3f71af0f4d3",
    },
    2048: {
        "fixture_seed": 382048,
        "fixture_sha256": "d13d102de5b171b6052483b73988537ebfbc70344ea4627372f9445145de39c2",
        "oracle_sha256": "715ed4b1b1816431907ae149998d567c4e5a42fcb6018c762bbce75b6b1cd38b",
    },
}

# Device 0 sees default then fixed; device 1 sees the reverse.  A/B/B/A is
# stock/candidate/candidate/stock inside every independent clock block.
PLAN = tuple(
    {
        "ordinal": ordinal,
        "device": device,
        "clock": clock,
        "slot": slot,
        "role": role,
        "outer_arm_id": f"gpu{device}-{clock}-{suffix}",
        "inner_arm_id": f"gpu{device}-{suffix}",
    }
    for ordinal, (device, clock, slot, role, suffix) in enumerate(
        (
            *(
                (device, clock, slot, role, suffix)
                for device, clock in (
                    (0, "default"),
                    (1, "fixed"),
                    (0, "fixed"),
                    (1, "default"),
                )
                for slot, role, suffix in (
                    (1, "control", "a1"),
                    (2, "candidate", "b1"),
                    (3, "candidate", "b2"),
                    (4, "control", "a2"),
                )
            ),
        ),
        start=1,
    )
)


class ContractError(RuntimeError):
    """A fail-closed campaign contract was not satisfied."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ContractError(f"{path}: non-finite JSON constant {value}")

    def pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in rows:
            if key in result:
                raise ContractError(f"{path}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=reject_constant,
            object_pairs_hook=pairs,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractError(f"{path}: cannot read strict JSON: {error}") from error


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise ContractError(f"refusing to overwrite {path}")
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    encoded = (
        json.dumps(payload, allow_nan=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o444)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def require_result_root() -> Path:
    if RESULT_ROOT.resolve(strict=True) != RESULT_ROOT or not RESULT_ROOT.is_dir():
        raise ContractError("campaign result root is absent or noncanonical")
    return RESULT_ROOT


def _require_sha(value: Any, where: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ContractError(f"{where}: malformed SHA-256")
    return value


def graph_inventory(stage: Path) -> tuple[int, str]:
    package = stage / "vllm_xpu_kernels"
    rows: list[str] = []
    for path in sorted(
        item for item in package.rglob("*") if stat.S_ISREG(item.lstat().st_mode)
    ):
        rows.append(f"{sha256_file(path)}  {path.relative_to(stage)}\n")
    return len(rows), hashlib.sha256("".join(rows).encode()).hexdigest()


def stage_audit(stage: Path, role: str) -> dict[str, Any]:
    if stage.resolve(strict=True) != stage:
        raise ContractError(f"{role} stage is not canonical: {stage}")
    nodes = [stage, *stage.rglob("*")]
    directories: set[str] = set()
    regular_files: list[Path] = []
    for path in nodes:
        mode = path.lstat().st_mode
        if path.is_symlink() or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise ContractError(f"{role} stage contains a nonregular node: {path}")
        if mode & 0o222:
            raise ContractError(f"{role} stage contains a writable node: {path}")
        if path == stage:
            continue
        relative = str(path.relative_to(stage))
        if stat.S_ISDIR(mode):
            directories.add(relative)
        else:
            regular_files.append(path)
    if directories != {
        "vllm_xpu_kernels",
        "vllm_xpu_kernels/quantization",
    }:
        raise ContractError(f"{role} stage directory inventory differs")
    if len(regular_files) != 20 or any(
        path.relative_to(stage).parts[0] != "vllm_xpu_kernels" for path in regular_files
    ):
        raise ContractError(f"{role} stage regular-file inventory differs")
    expected = dict(RUNTIME_FILES)
    expected["vllm_xpu_kernels/libattn_kernels_xe_2.so"] = (
        CONTROL_DEVICE_SHA256 if role == "control" else CANDIDATE_DEVICE_SHA256
    )
    for relative, digest in expected.items():
        path = stage / relative
        if not path.is_file() or sha256_file(path) != digest:
            raise ContractError(f"{role} stage identity mismatch: {path}")
    count, graph_sha = graph_inventory(stage)
    expected_graph = (
        CONTROL_GRAPH_SHA256 if role == "control" else CANDIDATE_GRAPH_SHA256
    )
    if count != 20 or graph_sha != expected_graph:
        raise ContractError(
            f"{role} stage graph differs: files={count}, sha256={graph_sha}"
        )
    return {
        "role": role,
        "stage": str(stage),
        "files": expected,
        "regular_file_count": count,
        "graph_sha256": graph_sha,
    }


def source_audit(repo: Path) -> dict[str, Any]:
    if repo.resolve(strict=True) != repo:
        raise ContractError(f"repository is not canonical: {repo}")
    actual: dict[str, str] = {}
    for relative, expected in SOURCE_HASHES.items():
        path = repo / relative
        if not path.is_file():
            raise ContractError(f"missing source prerequisite: {path}")
        digest = sha256_file(path)
        if digest != expected:
            raise ContractError(f"source prerequisite changed: {path}")
        actual[str(relative)] = digest
    return actual


def _git_output(repo: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ContractError(f"read-only Git preflight failed: {error}") from error
    return result.stdout.strip()


def authorized_repo_audit(repo: Path) -> dict[str, Any]:
    require_launch_authorized()
    if socket.gethostname() != REMOTE_HOSTNAME:
        raise ContractError("host is not the authorized reference host")
    sources = source_audit(repo)
    head = _git_output(repo, "rev-parse", "HEAD")
    if (
        head != AUTHORIZED_REMOTE_REPO_HEAD
        or _git_output(repo, "branch", "--show-current") != "main"
        or _git_output(repo, "status", "--porcelain", "--untracked-files=normal")
        or _git_output(repo, "rev-parse", "origin/main") != head
    ):
        raise ContractError("remote main/HEAD/clean/origin identity differs")
    qualifier = _load_remote_qualifier(repo)
    try:
        control = qualifier.stage_identity(
            argparse.Namespace(
                role="control", stage=str(CONTROL_STAGE), stage_manifest=None
            )
        )
        candidate = qualifier.stage_identity(
            argparse.Namespace(
                role="candidate", stage=None, stage_manifest=str(CANDIDATE_MANIFEST)
            )
        )
    except qualifier.ContractError as error:
        raise ContractError(f"remote stage preflight failed: {error}") from error
    strict_stage_graphs = {
        "control": stage_audit(CONTROL_STAGE, "control"),
        "candidate": stage_audit(CANDIDATE_STAGE, "candidate"),
    }
    inventory_payload = {
        "control": control,
        "candidate": candidate,
        "sources": sources,
        "strict_stage_graphs": strict_stage_graphs,
    }
    encoded = json.dumps(
        inventory_payload, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode()
    inventory_sha = hashlib.sha256(encoded).hexdigest()
    if inventory_sha != AUTHORIZED_STAGE_INVENTORY_SHA256:
        raise ContractError("combined source/stage inventory differs")
    return {"repo_head": head, "stage_inventory_sha256": inventory_sha}


def require_launch_authorized() -> None:
    # This must be the first operation in every mutating/GPU-capable command.
    identities_complete = (
        isinstance(AUTHORIZED_DEVICE_IDENTITIES, dict)
        and set(AUTHORIZED_DEVICE_IDENTITIES) == {0, 1}
        and all(
            isinstance(identity, dict)
            and set(identity) == {"uuid", "bdf"}
            and isinstance(identity["uuid"], str)
            and bool(identity["uuid"])
            and isinstance(identity["bdf"], str)
            and re.fullmatch(
                r"[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]", identity["bdf"]
            )
            is not None
            for identity in AUTHORIZED_DEVICE_IDENTITIES.values()
        )
        and len(
            {identity["uuid"] for identity in AUTHORIZED_DEVICE_IDENTITIES.values()}
        )
        == 2
        and len({identity["bdf"] for identity in AUTHORIZED_DEVICE_IDENTITIES.values()})
        == 2
    )
    field_paths_complete = (
        isinstance(AUTHORIZED_XPU_SMI_FIELD_PATHS, dict)
        and set(AUTHORIZED_XPU_SMI_FIELD_PATHS)
        == {
            "devices",
            "entry_device_id",
            "entry_uuid",
            "entry_bdf",
            "entry_name",
            "min_mhz",
            "max_mhz",
        }
        and all(
            isinstance(path, tuple)
            and bool(path)
            and all(isinstance(item, str) or type(item) is int for item in path)
            for path in AUTHORIZED_XPU_SMI_FIELD_PATHS.values()
        )
    )
    system_runtime_complete = (
        isinstance(AUTHORIZED_SYSTEM_RUNTIME_LIBRARIES, dict)
        and bool(AUTHORIZED_SYSTEM_RUNTIME_LIBRARIES)
        and all(
            isinstance(name, str)
            and bool(name)
            and Path(name).name == name
            and isinstance(digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
            for name, digest in AUTHORIZED_SYSTEM_RUNTIME_LIBRARIES.items()
        )
    )
    if (
        CAMPAIGN_LAUNCH_AUTHORIZED is not True
        or DRIVER_SIGNAL_OWNERSHIP_AUTHORIZED is not True
        or CLOCK_WRITER_EXCLUSION_AUTHORIZED is not True
        or DRIVER_ENVIRONMENT_AUTHORIZED is not True
        or not isinstance(AUTHORIZED_REMOTE_REPO_HEAD, str)
        or re.fullmatch(r"[0-9a-f]{40}", AUTHORIZED_REMOTE_REPO_HEAD) is None
        or not identities_complete
        or not isinstance(AUTHORIZED_XPU_SMI_QUERY_SCHEMA_SHA256, str)
        or re.fullmatch(r"[0-9a-f]{64}", AUTHORIZED_XPU_SMI_QUERY_SCHEMA_SHA256) is None
        or not field_paths_complete
        or AUTHORIZED_XPU_SMI_PATH != "/usr/bin/xpu-smi"
        or not isinstance(AUTHORIZED_XPU_SMI_SHA256, str)
        or re.fullmatch(r"[0-9a-f]{64}", AUTHORIZED_XPU_SMI_SHA256) is None
        or not isinstance(AUTHORIZED_XPU_SMI_VERSION, str)
        or not AUTHORIZED_XPU_SMI_VERSION
        or not isinstance(AUTHORIZED_STAGE_INVENTORY_SHA256, str)
        or re.fullmatch(r"[0-9a-f]{64}", AUTHORIZED_STAGE_INVENTORY_SHA256) is None
        or not system_runtime_complete
    ):
        raise ContractError(
            "launch blocked: freeze remote HEAD, both UUID/BDF identities, xpu-smi "
            "telemetry schema, combined stage inventory, and mapped system runtime "
            "libraries, then implement driver-level active-supervisor signal "
            "ownership, clock-writer exclusion, and clean driver environment in "
            "source first"
        )


def authorized_system_runtime_inventory_sha256() -> str | None:
    if not isinstance(AUTHORIZED_SYSTEM_RUNTIME_LIBRARIES, dict):
        return None
    return hashlib.sha256(
        json.dumps(
            AUTHORIZED_SYSTEM_RUNTIME_LIBRARIES,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _json_shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_shape(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [_json_shape(item) for item in value]
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    raise ContractError("xpu-smi JSON contains an unsupported value type")


def _at_path(payload: Any, path: tuple[str | int, ...], where: str) -> Any:
    current = payload
    try:
        for component in path:
            current = current[component]
    except (KeyError, IndexError, TypeError) as error:
        raise ContractError(f"xpu-smi field path is absent for {where}") from error
    return current


def parse_clock_command(args: argparse.Namespace) -> dict[str, Any]:
    require_launch_authorized()
    receipt = Path(args.receipt)
    if (
        not receipt.is_absolute()
        or receipt.resolve(strict=True) != receipt
        or receipt.stat().st_mode & 0o222
    ):
        raise ContractError("xpu-smi composite receipt is noncanonical or writable")
    payload = load_json(receipt)
    shape = json.dumps(_json_shape(payload), sort_keys=True, separators=(",", ":"))
    shape_sha = hashlib.sha256(shape.encode()).hexdigest()
    if shape_sha != AUTHORIZED_XPU_SMI_QUERY_SCHEMA_SHA256:
        raise ContractError("xpu-smi effective-clock schema differs")
    assert AUTHORIZED_XPU_SMI_FIELD_PATHS is not None
    assert AUTHORIZED_DEVICE_IDENTITIES is not None
    required_paths = {
        "devices",
        "entry_device_id",
        "entry_uuid",
        "entry_bdf",
        "entry_name",
        "min_mhz",
        "max_mhz",
    }
    if set(AUTHORIZED_XPU_SMI_FIELD_PATHS) != required_paths:
        raise ContractError("authorized xpu-smi field-path inventory differs")
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != "qwen38-xpu-smi-config-discovery-raw-v1"
        or payload.get("device") != args.device
        or set(payload)
        != {
            "schema",
            "device",
            "captured_time_ns",
            "xpu_smi",
            "config",
            "discovery",
        }
        or type(payload.get("captured_time_ns")) is not int
        or payload["captured_time_ns"] <= 0
    ):
        raise ContractError("xpu-smi composite receipt envelope differs")
    if payload["xpu_smi"] != {
        "path": AUTHORIZED_XPU_SMI_PATH,
        "sha256": AUTHORIZED_XPU_SMI_SHA256,
        "version": AUTHORIZED_XPU_SMI_VERSION,
    }:
        raise ContractError("xpu-smi binary identity differs")
    devices = _at_path(payload, AUTHORIZED_XPU_SMI_FIELD_PATHS["devices"], "devices")
    if not isinstance(devices, list) or len(devices) != 2:
        raise ContractError("xpu-smi discovery did not expose exactly two devices")
    observed: dict[int, dict[str, str]] = {}
    for entry in devices:
        device_id = _at_path(
            entry,
            AUTHORIZED_XPU_SMI_FIELD_PATHS["entry_device_id"],
            "entry_device_id",
        )
        uuid = _at_path(
            entry, AUTHORIZED_XPU_SMI_FIELD_PATHS["entry_uuid"], "entry_uuid"
        )
        bdf = _at_path(entry, AUTHORIZED_XPU_SMI_FIELD_PATHS["entry_bdf"], "entry_bdf")
        name = _at_path(
            entry, AUTHORIZED_XPU_SMI_FIELD_PATHS["entry_name"], "entry_name"
        )
        if (
            type(device_id) is not int
            or device_id not in (0, 1)
            or device_id in observed
            or not isinstance(uuid, str)
            or not isinstance(bdf, str)
            or name != EXPECTED_DEVICE_NAME
        ):
            raise ContractError("xpu-smi discovery device entry differs")
        observed[device_id] = {"uuid": uuid, "bdf": bdf, "name": name}
    if set(observed) != {0, 1} or any(
        observed[index][field] != AUTHORIZED_DEVICE_IDENTITIES[index][field]
        for index in (0, 1)
        for field in ("uuid", "bdf")
    ):
        raise ContractError("xpu-smi exact two-device identity differs")
    minimum = _at_path(payload, AUTHORIZED_XPU_SMI_FIELD_PATHS["min_mhz"], "min_mhz")
    maximum = _at_path(payload, AUTHORIZED_XPU_SMI_FIELD_PATHS["max_mhz"], "max_mhz")
    if (
        type(minimum) is not int
        or type(maximum) is not int
        or minimum <= 0
        or maximum < minimum
    ):
        raise ContractError("xpu-smi frequency range differs")
    inventory = [{"device": index, **observed[index]} for index in (0, 1)]
    inventory_sha = hashlib.sha256(
        json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "device": args.device,
        "uuid": observed[args.device]["uuid"],
        "bdf": observed[args.device]["bdf"],
        "min_mhz": minimum,
        "max_mhz": maximum,
        "captured_time_ns": payload["captured_time_ns"],
        "device_inventory_sha256": inventory_sha,
        "schema_sha256": shape_sha,
        "receipt_sha256": sha256_file(receipt),
    }


def seal_clock_receipt_command(args: argparse.Namespace) -> dict[str, Any]:
    require_launch_authorized()
    result_root = require_result_root()
    config_path = Path(args.config)
    discovery_path = Path(args.discovery)
    output = Path(args.output)
    match = re.fullmatch(rf"clock-{args.device}-([a-z0-9-]+)\.json", output.name)
    if (
        output.parent != result_root
        or match is None
        or config_path
        != result_root / f".clock-{args.device}-{match.group(1)}.config.tmp.json"
        or discovery_path
        != result_root / f".clock-{args.device}-{match.group(1)}.discovery.tmp.json"
    ):
        raise ContractError("clock receipt paths differ from campaign root contract")
    result = {
        "schema": "qwen38-xpu-smi-config-discovery-raw-v1",
        "device": args.device,
        "captured_time_ns": time.time_ns(),
        "xpu_smi": {
            "path": AUTHORIZED_XPU_SMI_PATH,
            "sha256": AUTHORIZED_XPU_SMI_SHA256,
            "version": AUTHORIZED_XPU_SMI_VERSION,
        },
        "config": load_json(config_path),
        "discovery": load_json(discovery_path),
    }
    xpu_smi_path = Path(str(AUTHORIZED_XPU_SMI_PATH))
    if (
        xpu_smi_path.resolve(strict=True) != xpu_smi_path
        or sha256_file(xpu_smi_path) != AUTHORIZED_XPU_SMI_SHA256
    ):
        raise ContractError("xpu-smi executable changed before receipt seal")
    write_json_atomic(output, result)
    # Reparse the immutable combined packet before its raw temporary inputs can
    # be discarded by the driver.
    parse_clock_command(argparse.Namespace(device=args.device, receipt=str(output)))
    return result


def _load_remote_qualifier(repo: Path) -> Any:
    path = repo / Q64_QUALIFIER_REL
    if sha256_file(path) != SOURCE_HASHES[Q64_QUALIFIER_REL]:
        raise ContractError("remote Q64 qualifier SHA mismatch")
    specification = importlib.util.spec_from_file_location(
        "qwen38_q64k32_remote_qualifier", path
    )
    if specification is None or specification.loader is None:
        raise ContractError("cannot load remote Q64 qualifier")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    patch = repo / PATCH_REL
    helper = repo / BUILD_HELPER_REL
    control_graph = (
        repo / "repro/qwen38-27b-autoround-int4-b70/manifests/"
        "staged-xpu-commitfix-graphfa-composite-20260820.graph.sha256"
    )
    module.CANDIDATE_PATCH = patch
    module.BUILD_HELPER = helper
    module.EXPECTED_PHYSICAL_GPUS = (0, 1)
    module.BASE.CANDIDATE_PATCH = patch
    module.BASE.BUILD_HELPER = helper
    module.BASE.EXPECTED_PHYSICAL_GPUS = (0, 1)
    module.BASE.CONTROL_GRAPH_MANIFEST = control_graph
    return module


def mapped_system_runtime_identity() -> dict[str, Any]:
    """Bind the actual system runtime DSOs mapped by the worker process."""
    require_launch_authorized()
    assert AUTHORIZED_SYSTEM_RUNTIME_LIBRARIES is not None
    mappings: dict[str, set[Path]] = {
        name: set() for name in AUTHORIZED_SYSTEM_RUNTIME_LIBRARIES
    }
    try:
        lines = Path("/proc/self/maps").read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ContractError(f"cannot read worker process mappings: {error}") from error
    for line in lines:
        fields = line.split(maxsplit=5)
        if len(fields) < 6:
            continue
        mapped_text = fields[5]
        for basename in mappings:
            if mapped_text == basename or mapped_text.startswith(f"{basename} "):
                raise ContractError("required system runtime has a nonabsolute mapping")
            if Path(mapped_text.removesuffix(" (deleted)")).name != basename:
                continue
            if mapped_text.endswith(" (deleted)"):
                raise ContractError(f"required system runtime is deleted: {basename}")
            mapped = Path(mapped_text)
            try:
                canonical = mapped.resolve(strict=True)
            except (OSError, RuntimeError) as error:
                raise ContractError(
                    f"required system runtime is not canonical: {basename}"
                ) from error
            if not canonical.is_file():
                raise ContractError(
                    f"required system runtime is not a file: {basename}"
                )
            mappings[basename].add(canonical)
    libraries: list[dict[str, str]] = []
    for basename, expected_sha in sorted(AUTHORIZED_SYSTEM_RUNTIME_LIBRARIES.items()):
        paths = mappings[basename]
        if len(paths) != 1:
            raise ContractError(
                f"required system runtime mapping count differs for {basename}"
            )
        path = next(iter(paths))
        digest = sha256_file(path)
        if digest != expected_sha:
            raise ContractError(f"required system runtime changed: {basename}")
        libraries.append({"basename": basename, "path": str(path), "sha256": digest})
    return {
        "schema": "qwen38-q64k32-remote-runtime-map-v1",
        "host": socket.gethostname(),
        "process_id": os.getpid(),
        "authorized_libraries": dict(
            sorted(AUTHORIZED_SYSTEM_RUNTIME_LIBRARIES.items())
        ),
        "libraries": libraries,
        "campaign_script": str(Path(__file__).resolve(strict=True)),
        "campaign_script_sha256": sha256_file(Path(__file__).resolve(strict=True)),
    }


def validate_runtime_sidecar(path: Path, expected_device: int) -> dict[str, Any]:
    packet = load_json(path)
    required = {
        "schema",
        "host",
        "process_id",
        "physical_device",
        "authorized_libraries",
        "libraries",
        "campaign_script",
        "campaign_script_sha256",
    }
    if not isinstance(packet, dict) or set(packet) != required:
        raise ContractError(f"{path}: runtime-map keys differ")
    if (
        packet["schema"] != "qwen38-q64k32-remote-runtime-map-v1"
        or packet["host"] != REMOTE_HOSTNAME
        or type(packet["process_id"]) is not int
        or packet["process_id"] <= 1
        or packet["physical_device"] != expected_device
        or packet["campaign_script"] != str(Path(__file__).resolve(strict=True))
        or packet["campaign_script_sha256"]
        != sha256_file(Path(__file__).resolve(strict=True))
        or path.stat().st_mode & 0o222
    ):
        raise ContractError(f"{path}: runtime-map identity differs")
    if CAMPAIGN_LAUNCH_AUTHORIZED:
        if packet["authorized_libraries"] != AUTHORIZED_SYSTEM_RUNTIME_LIBRARIES:
            raise ContractError(f"{path}: runtime-map source authorization differs")
    authorized = packet["authorized_libraries"]
    libraries = packet["libraries"]
    if not isinstance(authorized, dict) or not isinstance(libraries, list):
        raise ContractError(f"{path}: runtime-map inventory differs")
    if [item.get("basename") for item in libraries if isinstance(item, dict)] != sorted(
        authorized
    ):
        raise ContractError(f"{path}: runtime-map basename inventory differs")
    for item in libraries:
        if not isinstance(item, dict) or set(item) != {"basename", "path", "sha256"}:
            raise ContractError(f"{path}: malformed runtime-map entry")
        mapped = Path(item["path"])
        if (
            mapped.name != item["basename"]
            or not mapped.is_absolute()
            or mapped.resolve(strict=True) != mapped
            or not mapped.is_file()
            or item["sha256"] != authorized.get(item["basename"])
            or sha256_file(mapped) != item["sha256"]
        ):
            raise ContractError(f"{path}: runtime-map file identity differs")
    return packet


def worker_command(args: argparse.Namespace) -> dict[str, Any]:
    require_launch_authorized()
    if socket.gethostname() != REMOTE_HOSTNAME:
        raise ContractError("worker is not running on the authorized reference host")
    row = _plan_row(args.ordinal)
    if (
        args.physical_gpu != row["device"]
        or args.role != row["role"]
        or args.outer_arm_id != row["outer_arm_id"]
        or args.inner_arm_id != row["inner_arm_id"]
        or args.campaign_slot != row["slot"]
    ):
        raise ContractError("worker arguments differ from preregistered ordinal")
    result_root = require_result_root()
    expected_output = result_root / f"arm-{args.ordinal:02d}.json"
    if Path(args.output) != expected_output:
        raise ContractError("worker output path differs from campaign contract")
    repo = Path(args.repo)
    authorized_repo_audit(repo)
    qualifier = _load_remote_qualifier(repo)
    namespace = argparse.Namespace(
        role=args.role,
        stage=str(CONTROL_STAGE) if args.role == "control" else None,
        stage_manifest=(None if args.role == "control" else str(CANDIDATE_MANIFEST)),
        physical_gpu=args.physical_gpu,
        arm_id=args.inner_arm_id,
        campaign_slot=args.campaign_slot,
        output=args.output,
        samples=40,
        launches_per_sample=100,
        stability_replays=32,
    )
    try:
        result = qualifier.run_xpu(namespace)
        runtime_identity = mapped_system_runtime_identity()
        runtime_identity["physical_device"] = args.physical_gpu
        write_json_atomic(Path(f"{args.output}.remote-runtime.json"), runtime_identity)
        return result
    except qualifier.ContractError as error:
        raise ContractError(f"remote Q64 worker failed: {error}") from error


def audit_command(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo)
    result: dict[str, Any] = {
        "schema": "qwen38-q64k32-remote-clock-audit-v1",
        "launch_authorized": CAMPAIGN_LAUNCH_AUTHORIZED,
        "driver_signal_ownership_authorized": DRIVER_SIGNAL_OWNERSHIP_AUTHORIZED,
        "clock_writer_exclusion_authorized": CLOCK_WRITER_EXCLUSION_AUTHORIZED,
        "driver_environment_authorized": DRIVER_ENVIRONMENT_AUTHORIZED,
        "expected_hostname": REMOTE_HOSTNAME,
        "observed_hostname": socket.gethostname(),
        "plan": list(PLAN),
        "fixtures": FIXTURES,
        "missing_authorization": [
            name
            for name, value in (
                ("remote_repo_head", AUTHORIZED_REMOTE_REPO_HEAD),
                ("device_identities", AUTHORIZED_DEVICE_IDENTITIES),
                ("xpu_smi_query_schema_sha256", AUTHORIZED_XPU_SMI_QUERY_SCHEMA_SHA256),
                ("xpu_smi_field_paths", AUTHORIZED_XPU_SMI_FIELD_PATHS),
                ("xpu_smi_path", AUTHORIZED_XPU_SMI_PATH),
                ("xpu_smi_sha256", AUTHORIZED_XPU_SMI_SHA256),
                ("xpu_smi_version", AUTHORIZED_XPU_SMI_VERSION),
                ("stage_inventory_sha256", AUTHORIZED_STAGE_INVENTORY_SHA256),
                ("system_runtime_libraries", AUTHORIZED_SYSTEM_RUNTIME_LIBRARIES),
            )
            if value is None
        ]
        + ([] if DRIVER_SIGNAL_OWNERSHIP_AUTHORIZED else ["driver_signal_ownership"])
        + ([] if CLOCK_WRITER_EXCLUSION_AUTHORIZED else ["clock_writer_exclusion"])
        + ([] if DRIVER_ENVIRONMENT_AUTHORIZED else ["driver_environment"]),
        "authorized_system_runtime_inventory_sha256": (
            authorized_system_runtime_inventory_sha256()
        ),
        "authorized_xpu_smi": (
            None
            if AUTHORIZED_XPU_SMI_PATH is None
            else {
                "path": AUTHORIZED_XPU_SMI_PATH,
                "sha256": AUTHORIZED_XPU_SMI_SHA256,
                "version": AUTHORIZED_XPU_SMI_VERSION,
            }
        ),
    }
    if args.require_host and socket.gethostname() != REMOTE_HOSTNAME:
        raise ContractError("audit host is not the preregistered reference host")
    result["source"] = source_audit(repo)
    if args.require_stages:
        result["control_stage"] = stage_audit(CONTROL_STAGE, "control")
        result["candidate_stage"] = stage_audit(CANDIDATE_STAGE, "candidate")
        if (
            not CANDIDATE_GRAPH.is_file()
            or sha256_file(CANDIDATE_GRAPH) != CANDIDATE_GRAPH_SHA256
        ):
            raise ContractError(
                "candidate graph-manifest artifact is absent or changed"
            )
    return result


def _parse_proc_stat(text: str) -> tuple[int, int]:
    # proc(5): comm is parenthesized and may itself contain spaces or `)`.
    close = text.rfind(")")
    if close < 2 or re.match(r"^[1-9][0-9]* \(", text[: close + 1]) is None:
        raise ContractError("malformed /proc stat prefix")
    tail = text[close + 1 :].split()
    if len(tail) < 20:
        raise ContractError("truncated /proc stat record")
    try:
        return int(tail[2]), int(tail[19])
    except ValueError as error:
        raise ContractError("nonintegral /proc stat identity") from error


def _proc_identity(pid: int) -> tuple[int, int]:
    return _parse_proc_stat(Path(f"/proc/{pid}/stat").read_text(encoding="utf-8"))


def _proc_start_ticks(pid: int) -> int:
    return _proc_identity(pid)[1]


def _group_absent(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    except OSError as error:
        return error.errno == errno.ESRCH
    return False


def _terminate_group(
    pgid: int, expected_start_ticks: int, grace_seconds: float
) -> dict[str, Any]:
    result = {
        "identity_safe": False,
        "term_sent": False,
        "kill_sent": False,
        "group_absent": False,
    }
    if _group_absent(pgid):
        result["identity_safe"] = True
        result["group_absent"] = True
        return result
    try:
        observed_start_ticks = _proc_start_ticks(pgid)
    except (FileNotFoundError, ProcessLookupError):
        # A dead group leader with live descendants still owns this PGID.
        result["identity_safe"] = True
    except (OSError, ValueError, ContractError):
        # Existing but unreadable/malformed identity is never safe to signal.
        return result
    else:
        if observed_start_ticks != expected_start_ticks:
            return result
        result["identity_safe"] = True
    try:
        os.killpg(pgid, signal.SIGTERM)
        result["term_sent"] = True
    except ProcessLookupError:
        result["group_absent"] = True
        return result
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if _group_absent(pgid):
            result["group_absent"] = True
            return result
        time.sleep(0.05)
    try:
        os.killpg(pgid, signal.SIGKILL)
        result["kill_sent"] = True
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline and not _group_absent(pgid):
        time.sleep(0.05)
    result["group_absent"] = _group_absent(pgid)
    return result


def _terminate_unreaped_fresh_group(
    process: subprocess.Popen[bytes], grace_seconds: float
) -> dict[str, Any]:
    """Clean a just-created session whose /proc start tick was unreadable.

    The child has not been polled or waited, so its PID cannot yet be reused;
    start_new_session=True therefore makes its PID a safe process-group target.
    """
    result = {
        "identity_safe": True,
        "term_sent": False,
        "kill_sent": False,
        "group_absent": False,
    }
    if _group_absent(process.pid):
        result["group_absent"] = True
        try:
            process.wait(timeout=grace_seconds)
        except (OSError, subprocess.TimeoutExpired):
            pass
        return result
    try:
        os.killpg(process.pid, signal.SIGTERM)
        result["term_sent"] = True
    except OSError:
        pass
    try:
        process.wait(timeout=grace_seconds)
    except (OSError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
            result["kill_sent"] = True
        except OSError:
            pass
        try:
            process.wait(timeout=grace_seconds)
        except (OSError, subprocess.TimeoutExpired):
            pass
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline and not _group_absent(process.pid):
        time.sleep(0.05)
    if not _group_absent(process.pid):
        try:
            os.killpg(process.pid, signal.SIGKILL)
            result["kill_sent"] = True
        except OSError:
            pass
        try:
            process.wait(timeout=grace_seconds)
        except (OSError, subprocess.TimeoutExpired):
            pass
    result["group_absent"] = _group_absent(process.pid)
    return result


def _plan_row(ordinal: int) -> dict[str, Any]:
    if ordinal < 1 or ordinal > len(PLAN):
        raise ContractError("campaign ordinal is outside 1..16")
    return dict(PLAN[ordinal - 1])


def supervise_command(args: argparse.Namespace) -> dict[str, Any]:
    require_launch_authorized()
    if args.timeout_seconds != 900.0 or args.grace_seconds != 10.0:
        raise ContractError("supervisor timeout/grace differs from frozen contract")
    if socket.gethostname() != REMOTE_HOSTNAME:
        raise ContractError(
            "supervisor is not running on the authorized reference host"
        )
    row = _plan_row(args.ordinal)
    authorization = authorized_repo_audit(REMOTE_REPO)
    result_root = require_result_root()
    terminal = Path(args.terminal)
    stderr = Path(args.stderr)
    success = Path(args.success)
    runtime_sidecar = Path(f"{success}.remote-runtime.json")
    late_signals = Path(f"{terminal}.signals-late.json")
    clock_receipt = Path(args.clock_receipt)
    failure = Path(f"{success}.failure.json")
    expected_prefix = result_root / f"arm-{row['ordinal']:02d}"
    if (
        terminal != Path(f"{expected_prefix}.terminal.json")
        or stderr != Path(f"{expected_prefix}.supervisor.log")
        or success != Path(f"{expected_prefix}.json")
        or clock_receipt
        != result_root / f"clock-{row['device']}-arm-{row['ordinal']}-pre.json"
    ):
        raise ContractError("supervisor artifact paths differ from campaign contract")
    for path in (terminal, stderr, success, failure, runtime_sidecar, late_signals):
        if path.exists() or path.with_name(f".{path.name}.tmp.{os.getpid()}").exists():
            raise ContractError(f"refusing existing arm artifact: {path}")
    if (
        not clock_receipt.is_file()
        or clock_receipt.stat().st_mode & 0o222
        or not clock_receipt.is_absolute()
    ):
        raise ContractError(
            "effective-clock receipt is absent, noncanonical, or writable"
        )
    clock_identity = parse_clock_command(
        argparse.Namespace(device=row["device"], receipt=str(clock_receipt))
    )
    expected_range = (400, 2800) if row["clock"] == "default" else (2800, 2800)
    if (clock_identity["min_mhz"], clock_identity["max_mhz"]) != expected_range:
        raise ContractError("effective-clock receipt differs from planned state")
    if terminal.parent.resolve(strict=True) != terminal.parent:
        raise ContractError("terminal parent is not canonical")
    command = list(args.command)
    if command[:1] == ["--"]:
        command.pop(0)
    if not command:
        raise ContractError("worker command is empty")
    expected_command = [
        str(REMOTE_PYTHON),
        "-B",
        str(Path(__file__).resolve()),
        "worker",
        "--repo",
        str(REMOTE_REPO),
        "--ordinal",
        str(row["ordinal"]),
        "--physical-gpu",
        str(row["device"]),
        "--role",
        row["role"],
        "--outer-arm-id",
        row["outer_arm_id"],
        "--inner-arm-id",
        row["inner_arm_id"],
        "--campaign-slot",
        str(row["slot"]),
        "--output",
        str(success),
    ]
    if command != expected_command:
        raise ContractError(
            "worker command differs from exact preregistered invocation"
        )
    command_sha = hashlib.sha256(("\0".join(command) + "\0").encode()).hexdigest()
    started = time.time_ns()
    receipt_paths: list[Path] = []
    before = terminal.with_name(f"{terminal.name}.phase-before-spawn.json")
    write_json_atomic(
        before,
        {
            "schema": "qwen38-q64k32-remote-clock-supervisor-phase-v1",
            "phase": "before-spawn",
            "time_ns": started,
            "supervisor_pid": os.getpid(),
            "plan": row,
            "command_sha256": command_sha,
        },
    )
    receipt_paths.append(before)
    process: subprocess.Popen[bytes] | None = None
    cleanup = {
        "identity_safe": False,
        "term_sent": False,
        "kill_sent": False,
        "group_absent": False,
    }
    status = "invalid"
    error: str | None = None
    returncode: int | None = None
    start_ticks: int | None = None
    pending_signals: list[int] = []
    watched_signals = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
    previous_handlers = {item: signal.getsignal(item) for item in watched_signals}

    def record_signal(signum: int, _frame: Any) -> None:
        pending_signals.append(signum)

    for item in watched_signals:
        signal.signal(item, record_signal)
    try:
        with stderr.open("xb") as stderr_stream:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=stderr_stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
            for _ in range(20):
                try:
                    start_ticks = _proc_start_ticks(process.pid)
                    break
                except (OSError, ValueError, ContractError):
                    time.sleep(0.01)
            if start_ticks is None:
                cleanup = _terminate_unreaped_fresh_group(process, args.grace_seconds)
                returncode = process.returncode
                raise ContractError("worker process identity could not be established")
            spawned = terminal.with_name(f"{terminal.name}.phase-spawned.json")
            write_json_atomic(
                spawned,
                {
                    "schema": "qwen38-q64k32-remote-clock-supervisor-phase-v1",
                    "phase": "spawned",
                    "time_ns": time.time_ns(),
                    "supervisor_pid": os.getpid(),
                    "worker_pid": process.pid,
                    "worker_pgid": process.pid,
                    "worker_start_ticks": start_ticks,
                    "plan": row,
                    "command_sha256": command_sha,
                },
            )
            receipt_paths.append(spawned)
            deadline = time.monotonic() + args.timeout_seconds
            while True:
                if pending_signals:
                    status = "interrupted"
                    cleanup = _terminate_group(
                        process.pid, start_ticks, args.grace_seconds
                    )
                    returncode = process.wait(timeout=args.grace_seconds)
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    status = "timeout"
                    cleanup = _terminate_group(
                        process.pid, start_ticks, args.grace_seconds
                    )
                    returncode = process.wait(timeout=args.grace_seconds)
                    break
                try:
                    returncode = process.wait(timeout=min(0.25, remaining))
                    cleanup["identity_safe"] = True
                    cleanup["group_absent"] = _group_absent(process.pid)
                    break
                except subprocess.TimeoutExpired:
                    continue
        os.chmod(stderr, 0o444)
        if returncode is not None and cleanup["group_absent"] is not True:
            cleanup = _terminate_group(process.pid, start_ticks, args.grace_seconds)
        if pending_signals and status not in {"timeout", "interrupted"}:
            status = "interrupted"
        if status not in {"timeout", "interrupted"}:
            if cleanup["group_absent"] is not True:
                status = "invalid"
                error = "worker leader exited with a live process group"
            elif (
                returncode == 0
                and success.is_file()
                and runtime_sidecar.is_file()
                and not failure.exists()
            ):
                status = "success"
            elif (
                isinstance(returncode, int)
                and returncode != 0
                and failure.is_file()
                and not success.exists()
            ):
                status = "worker-failure"
            else:
                status = "invalid"
                error = "worker exit/artifact state is inconsistent"
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as caught:
        error = f"{type(caught).__name__}: {caught}"
        if stderr.is_file():
            os.chmod(stderr, 0o444)
        if process is not None and start_ticks is not None:
            cleanup = _terminate_group(process.pid, start_ticks, args.grace_seconds)
            returncode = process.poll()
        elif process is not None:
            cleanup = _terminate_unreaped_fresh_group(process, args.grace_seconds)
            returncode = process.returncode
        elif process is None:
            cleanup["identity_safe"] = True
            cleanup["group_absent"] = True
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, watched_signals)
    pending_signals.extend(
        int(item)
        for item in signal.sigpending()
        if item in watched_signals and int(item) not in pending_signals
    )
    if pending_signals and status not in {"timeout", "interrupted"}:
        status = "interrupted"
    terminal_payload = {
        "schema": SCHEMA_TERMINAL,
        "status": status,
        "valid": status in {"success", "worker-failure", "timeout", "interrupted"}
        and cleanup["group_absent"],
        "plan": row,
        "host": socket.gethostname(),
        "authorization": authorization,
        "clock_identity": clock_identity,
        "process": {
            "supervisor_pid": os.getpid(),
            "pid": None if process is None else process.pid,
            "pgid": None if process is None else process.pid,
            "start_ticks": start_ticks,
            "returncode": returncode,
            "started_time_ns": started,
            "finished_time_ns": time.time_ns(),
            "command_sha256": command_sha,
        },
        "watchdog": {
            "timeout_seconds": args.timeout_seconds,
            "grace_seconds": args.grace_seconds,
            "cleanup": cleanup,
        },
        "artifacts": {
            "success": _artifact(success),
            "failure": _artifact(failure),
            "stderr": _artifact(stderr),
            "clock": _artifact(clock_receipt),
            "runtime": _artifact(runtime_sidecar),
        },
        "receipts": [_artifact(path) for path in receipt_paths],
        "error": error,
        "signals": pending_signals,
    }
    returned_payload = terminal_payload
    try:
        write_json_atomic(terminal, terminal_payload)
        post_publication_signals: list[int] = []
        while True:
            caught = signal.sigtimedwait(watched_signals, 0)
            if caught is None:
                break
            post_publication_signals.append(int(caught.si_signo))
        post_publication_signals.sort()
        if post_publication_signals:
            write_json_atomic(
                late_signals,
                {
                    "schema": "qwen38-q64k32-remote-clock-late-signal-v1",
                    "terminal_path": str(terminal.resolve(strict=True)),
                    "terminal_sha256": sha256_file(terminal),
                    "signals": post_publication_signals,
                    "time_ns": time.time_ns(),
                },
            )
            returned_payload = copy.deepcopy(terminal_payload)
            returned_payload["status"] = "interrupted"
            returned_payload["valid"] = False
    finally:
        for item, handler in previous_handlers.items():
            # Python can inherit SIG_IGN for a background job.  Never reopen a
            # publication-fence window that silently discards a late signal:
            # restore ignored watched signals to their terminating default.
            signal.signal(
                item, signal.SIG_DFL if handler == signal.SIG_IGN else handler
            )
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
    return returned_payload


def _artifact(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return {"path": str(path.resolve(strict=True)), "sha256": sha256_file(path)}


def restoration_command(args: argparse.Namespace) -> dict[str, Any]:
    require_launch_authorized()
    result_root = require_result_root()
    expected_terminals = [
        str(result_root / f"arm-{ordinal:02d}.terminal.json")
        for ordinal in range(1, 17)
    ]
    if (
        Path(args.output) != result_root / "campaign-restoration-terminal.json"
        or args.pre_run_0 != str(result_root / "clock-0-pre-run.json")
        or args.pre_run_1 != str(result_root / "clock-1-pre-run.json")
        or args.restored_0 != str(result_root / "clock-0-restore-effective.json")
        or args.restored_1 != str(result_root / "clock-1-restore-effective.json")
        or args.terminals != expected_terminals
    ):
        raise ContractError("restoration paths differ from campaign contract")
    # Restoration must remain publishable after clocks are restored even if
    # the repository becomes unavailable or dirty during an interrupted run.
    # Its source authorization is already frozen by require_launch_authorized.
    authorization = {
        "repo_head": AUTHORIZED_REMOTE_REPO_HEAD,
        "stage_inventory_sha256": AUTHORIZED_STAGE_INVENTORY_SHA256,
    }
    devices: list[dict[str, Any]] = []
    clock_errors: list[str] = []
    for device, pre_text, restored_text in (
        (0, args.pre_run_0, args.restored_0),
        (1, args.pre_run_1, args.restored_1),
    ):
        pre_path = Path(pre_text)
        restored_path = Path(restored_text)
        pre_identity: dict[str, Any] | None = None
        restored_identity: dict[str, Any] | None = None
        try:
            pre_identity = parse_clock_command(
                argparse.Namespace(device=device, receipt=str(pre_path))
            )
            restored_identity = parse_clock_command(
                argparse.Namespace(device=device, receipt=str(restored_path))
            )
            if (
                pre_identity["min_mhz"],
                pre_identity["max_mhz"],
            ) != (
                restored_identity["min_mhz"],
                restored_identity["max_mhz"],
            ):
                clock_errors.append(f"GPU{device} restored range differs from pre-run")
        except (ContractError, OSError) as error:
            clock_errors.append(f"GPU{device}: {error}")
        devices.append(
            {
                "device": device,
                "pre_run": pre_identity,
                "restored": restored_identity,
                "pre_run_artifact": _artifact(pre_path),
                "restored_artifact": _artifact(restored_path),
            }
        )
    if args.restore_rc != 0:
        clock_errors.append(f"shell restore status is {args.restore_rc}")
    arm_terminals: list[dict[str, Any] | None] = []
    terminal_packets: list[dict[str, Any]] = []
    campaign_errors: list[str] = []
    prefix_ended = False
    if len(args.terminals) != 16:
        campaign_errors.append("restoration requires exactly 16 arm-terminal paths")
    else:
        for ordinal, terminal_text in enumerate(args.terminals, start=1):
            terminal_path = Path(terminal_text)
            if not terminal_path.exists():
                prefix_ended = True
                arm_terminals.append(None)
                continue
            if prefix_ended:
                campaign_errors.append(
                    f"arm {ordinal}: terminal exists after a missing prefix entry"
                )
            try:
                terminal_packet = validate_terminal(terminal_path)
                if (
                    terminal_packet["plan"] != _plan_row(ordinal)
                    or terminal_packet["valid"] is not True
                ):
                    raise ContractError("arm terminal is not a valid planned result")
                if terminal_packets and terminal_packets[-1]["status"] != "success":
                    raise ContractError("arm terminal follows a stopping result")
                terminal_packets.append(terminal_packet)
                arm_terminals.append(_artifact(terminal_path))
            except (ContractError, OSError) as error:
                campaign_errors.append(f"arm {ordinal}: {error}")
                arm_terminals.append(_artifact(terminal_path))
    finished_time_ns = time.time_ns()
    if terminal_packets and finished_time_ns <= max(
        item["process"]["finished_time_ns"] for item in terminal_packets
    ):
        campaign_errors.append("restoration terminal time does not follow started arms")
    restored = not clock_errors
    campaign_complete = (
        len(terminal_packets) == 16
        and all(item["status"] == "success" for item in terminal_packets)
        and args.original_exit_code == 0
        and not campaign_errors
    )
    result = {
        "schema": SCHEMA_RESTORATION,
        "status": "restored" if restored else "restore-failed",
        "valid": not campaign_errors,
        "host": socket.gethostname(),
        "authorization": authorization,
        "original_exit_code": args.original_exit_code,
        "shell_restore_status": args.restore_rc,
        "devices": devices,
        "arm_terminals": arm_terminals,
        "terminal_prefix_count": len(terminal_packets),
        "terminal_prefix_statuses": [item["status"] for item in terminal_packets],
        "campaign_complete": campaign_complete,
        "clock_errors": clock_errors,
        "campaign_errors": campaign_errors,
        "finished_time_ns": finished_time_ns,
    }
    write_json_atomic(Path(args.output), result)
    return result


def validate_restoration(
    path: Path, *, require_complete: bool = False
) -> dict[str, Any]:
    packet = load_json(path)
    required = {
        "schema",
        "status",
        "valid",
        "host",
        "authorization",
        "original_exit_code",
        "shell_restore_status",
        "devices",
        "arm_terminals",
        "terminal_prefix_count",
        "terminal_prefix_statuses",
        "campaign_complete",
        "clock_errors",
        "campaign_errors",
        "finished_time_ns",
    }
    if not isinstance(packet, dict) or set(packet) != required:
        raise ContractError("restoration terminal keys differ")
    if (
        packet["schema"] != SCHEMA_RESTORATION
        or packet["status"] != "restored"
        or packet["valid"] is not True
        or packet["host"] != REMOTE_HOSTNAME
        or packet["shell_restore_status"] != 0
        or packet["clock_errors"] != []
        or packet["campaign_errors"] != []
        or type(packet["original_exit_code"]) is not int
        or not isinstance(packet["finished_time_ns"], int)
        or path.stat().st_mode & 0o222
    ):
        raise ContractError("restoration terminal is not a clean successful restore")
    authorization = packet["authorization"]
    if (
        not isinstance(authorization, dict)
        or set(authorization) != {"repo_head", "stage_inventory_sha256"}
        or re.fullmatch(r"[0-9a-f]{40}", str(authorization["repo_head"])) is None
        or re.fullmatch(r"[0-9a-f]{64}", str(authorization["stage_inventory_sha256"]))
        is None
    ):
        raise ContractError("restoration authorization identity differs")
    if CAMPAIGN_LAUNCH_AUTHORIZED and authorization != {
        "repo_head": AUTHORIZED_REMOTE_REPO_HEAD,
        "stage_inventory_sha256": AUTHORIZED_STAGE_INVENTORY_SHA256,
    }:
        raise ContractError("restoration authorization no longer matches source")
    if not isinstance(packet["devices"], list) or len(packet["devices"]) != 2:
        raise ContractError("restoration device inventory differs")
    identity_keys = {
        "device",
        "uuid",
        "bdf",
        "min_mhz",
        "max_mhz",
        "captured_time_ns",
        "device_inventory_sha256",
        "schema_sha256",
        "receipt_sha256",
    }
    for device, item in enumerate(packet["devices"]):
        if (
            not isinstance(item, dict)
            or set(item)
            != {
                "device",
                "pre_run",
                "restored",
                "pre_run_artifact",
                "restored_artifact",
            }
            or item["device"] != device
            or not isinstance(item["pre_run"], dict)
            or not isinstance(item["restored"], dict)
            or set(item["pre_run"]) != identity_keys
            or set(item["restored"]) != identity_keys
            or item["pre_run"]["device"] != device
            or item["restored"]["device"] != device
            or (
                item["pre_run"]["min_mhz"],
                item["pre_run"]["max_mhz"],
            )
            != (
                item["restored"]["min_mhz"],
                item["restored"]["max_mhz"],
            )
        ):
            raise ContractError("restoration range evidence differs")
        for name, identity_name in (
            ("pre_run_artifact", "pre_run"),
            ("restored_artifact", "restored"),
        ):
            artifact = item[name]
            if not isinstance(artifact, dict) or set(artifact) != {"path", "sha256"}:
                raise ContractError("restoration receipt artifact differs")
            receipt = Path(artifact["path"])
            if (
                not receipt.is_file()
                or receipt.stat().st_mode & 0o222
                or sha256_file(receipt) != artifact["sha256"]
                or artifact["sha256"] != item[identity_name]["receipt_sha256"]
            ):
                raise ContractError("restoration receipt changed")
            if CAMPAIGN_LAUNCH_AUTHORIZED:
                reparsed = parse_clock_command(
                    argparse.Namespace(device=device, receipt=str(receipt))
                )
                if reparsed != item[identity_name]:
                    raise ContractError("restoration receipt reparse differs")
    if (
        not isinstance(packet["arm_terminals"], list)
        or len(packet["arm_terminals"]) != 16
    ):
        raise ContractError("restoration arm-terminal inventory differs")
    validated_arms: list[dict[str, Any]] = []
    prefix_ended = False
    for ordinal, artifact in enumerate(packet["arm_terminals"], start=1):
        if artifact is None:
            prefix_ended = True
            continue
        if prefix_ended:
            raise ContractError("restoration arm terminals are not a contiguous prefix")
        if not isinstance(artifact, dict) or set(artifact) != {"path", "sha256"}:
            raise ContractError("restoration arm-terminal artifact differs")
        terminal_path = Path(artifact["path"])
        if (
            not terminal_path.is_file()
            or terminal_path.stat().st_mode & 0o222
            or sha256_file(terminal_path) != artifact["sha256"]
        ):
            raise ContractError("restoration arm-terminal artifact changed")
        arm = validate_terminal(terminal_path)
        if (
            arm["plan"] != _plan_row(ordinal)
            or arm["valid"] is not True
            or (validated_arms and validated_arms[-1]["status"] != "success")
        ):
            raise ContractError("restoration arm-terminal binding differs")
        validated_arms.append(arm)
    statuses = [item["status"] for item in validated_arms]
    complete = (
        len(validated_arms) == 16
        and all(item == "success" for item in statuses)
        and packet["original_exit_code"] == 0
    )
    if not complete and packet["original_exit_code"] == 0:
        raise ContractError("incomplete campaign has a zero original exit code")
    if (
        packet["terminal_prefix_count"] != len(validated_arms)
        or packet["terminal_prefix_statuses"] != statuses
        or packet["campaign_complete"] is not complete
    ):
        raise ContractError("restoration prefix summary differs")
    if validated_arms and packet["finished_time_ns"] <= max(
        item["process"]["finished_time_ns"] for item in validated_arms
    ):
        raise ContractError("restoration did not finish after all arm terminals")
    if require_complete and (not complete or packet["original_exit_code"] != 0):
        raise ContractError("restoration is clean but campaign is incomplete")
    return packet


def validate_terminal(path: Path) -> dict[str, Any]:
    if Path(f"{path}.signals-late.json").exists():
        raise ContractError(f"{path}: signal arrived at the publication fence")
    packet = load_json(path)
    keys = {
        "schema",
        "status",
        "valid",
        "plan",
        "host",
        "authorization",
        "clock_identity",
        "process",
        "watchdog",
        "artifacts",
        "receipts",
        "error",
        "signals",
    }
    if not isinstance(packet, dict) or set(packet) != keys:
        raise ContractError(f"{path}: terminal keys differ")
    if packet["schema"] != SCHEMA_TERMINAL or packet["host"] != REMOTE_HOSTNAME:
        raise ContractError(f"{path}: terminal schema/host differs")
    authorization = packet["authorization"]
    if (
        not isinstance(authorization, dict)
        or set(authorization) != {"repo_head", "stage_inventory_sha256"}
        or re.fullmatch(r"[0-9a-f]{40}", authorization.get("repo_head", "")) is None
        or re.fullmatch(
            r"[0-9a-f]{64}", authorization.get("stage_inventory_sha256", "")
        )
        is None
    ):
        raise ContractError(f"{path}: authorization identity differs")
    if CAMPAIGN_LAUNCH_AUTHORIZED and (
        authorization["repo_head"] != AUTHORIZED_REMOTE_REPO_HEAD
        or authorization["stage_inventory_sha256"] != AUTHORIZED_STAGE_INVENTORY_SHA256
    ):
        raise ContractError(f"{path}: authorization no longer matches source")
    row = packet["plan"]
    if not isinstance(row, dict) or row != _plan_row(row.get("ordinal", 0)):
        raise ContractError(f"{path}: terminal plan differs")
    if packet["status"] not in {
        "success",
        "worker-failure",
        "timeout",
        "interrupted",
        "invalid",
    }:
        raise ContractError(f"{path}: terminal status differs")
    if (
        not isinstance(packet["signals"], list)
        or any(
            item not in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
            for item in packet["signals"]
        )
        or (packet["status"] == "interrupted") != bool(packet["signals"])
    ):
        raise ContractError(f"{path}: signal inventory differs")
    process = packet["process"]
    process_keys = {
        "supervisor_pid",
        "pid",
        "pgid",
        "start_ticks",
        "returncode",
        "started_time_ns",
        "finished_time_ns",
        "command_sha256",
    }
    if not isinstance(process, dict) or set(process) != process_keys:
        raise ContractError(f"{path}: process identity keys differ")
    _require_sha(process["command_sha256"], f"{path}.command")
    if (
        type(process["supervisor_pid"]) is not int
        or process["supervisor_pid"] <= 1
        or not isinstance(process["started_time_ns"], int)
        or not isinstance(process["finished_time_ns"], int)
        or process["finished_time_ns"] < process["started_time_ns"]
    ):
        raise ContractError(f"{path}: process time range differs")
    if process["pid"] is None:
        if any(
            process[name] is not None for name in ("pgid", "start_ticks", "returncode")
        ):
            raise ContractError(f"{path}: absent process identity is inconsistent")
    else:
        if (
            not isinstance(process["pid"], int)
            or process["pid"] <= 1
            or process["pgid"] != process["pid"]
            or not isinstance(process["returncode"], int)
            or (
                process["start_ticks"] is not None
                and not isinstance(process["start_ticks"], int)
            )
            or (process["start_ticks"] is None and packet["status"] != "invalid")
        ):
            raise ContractError(f"{path}: spawned process identity differs")
    watchdog = packet["watchdog"]
    if not isinstance(watchdog, dict) or set(watchdog) != {
        "timeout_seconds",
        "grace_seconds",
        "cleanup",
    }:
        raise ContractError(f"{path}: watchdog keys differ")
    if watchdog["timeout_seconds"] != 900.0 or watchdog["grace_seconds"] != 10.0:
        raise ContractError(f"{path}: watchdog interval differs")
    cleanup = watchdog["cleanup"]
    if (
        not isinstance(cleanup, dict)
        or set(cleanup) != {"identity_safe", "term_sent", "kill_sent", "group_absent"}
        or any(not isinstance(value, bool) for value in cleanup.values())
    ):
        raise ContractError(f"{path}: cleanup state differs")
    if (
        cleanup.get("identity_safe") is not True
        or cleanup.get("group_absent") is not True
    ):
        raise ContractError(f"{path}: process group was not proved absent")
    artifacts = packet["artifacts"]
    if not isinstance(artifacts, dict) or set(artifacts) != {
        "success",
        "failure",
        "stderr",
        "clock",
        "runtime",
    }:
        raise ContractError(f"{path}: artifact keys differ")
    clock_identity = packet["clock_identity"]
    if (
        not isinstance(clock_identity, dict)
        or set(clock_identity)
        != {
            "device",
            "uuid",
            "bdf",
            "min_mhz",
            "max_mhz",
            "captured_time_ns",
            "device_inventory_sha256",
            "schema_sha256",
            "receipt_sha256",
        }
        or clock_identity["device"] != packet["plan"]["device"]
        or (clock_identity["min_mhz"], clock_identity["max_mhz"])
        != ((400, 2800) if packet["plan"]["clock"] == "default" else (2800, 2800))
        or re.fullmatch(r"[0-9a-f]{64}", clock_identity["schema_sha256"]) is None
        or re.fullmatch(r"[0-9a-f]{64}", clock_identity["device_inventory_sha256"])
        is None
        or re.fullmatch(r"[0-9a-f]{64}", clock_identity["receipt_sha256"]) is None
        or clock_identity["captured_time_ns"] > packet["process"]["started_time_ns"]
    ):
        raise ContractError(f"{path}: clock identity differs")
    if CAMPAIGN_LAUNCH_AUTHORIZED:
        assert AUTHORIZED_DEVICE_IDENTITIES is not None
        expected_device = AUTHORIZED_DEVICE_IDENTITIES[packet["plan"]["device"]]
        if (
            clock_identity["uuid"] != expected_device["uuid"]
            or clock_identity["bdf"] != expected_device["bdf"]
            or clock_identity["schema_sha256"] != AUTHORIZED_XPU_SMI_QUERY_SCHEMA_SHA256
        ):
            raise ContractError(f"{path}: clock identity no longer matches source")
    for name, item in artifacts.items():
        if item is None:
            continue
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ContractError(f"{path}: malformed {name} artifact")
        artifact = Path(item["path"])
        if (
            not artifact.is_absolute()
            or not artifact.is_file()
            or artifact.stat().st_mode & 0o222
            or sha256_file(artifact) != _require_sha(item["sha256"], name)
        ):
            raise ContractError(f"{path}: changed {name} artifact")
    if artifacts["clock"] is None or (
        artifacts["clock"]["sha256"] != clock_identity["receipt_sha256"]
    ):
        raise ContractError(f"{path}: clock receipt binding differs")
    if CAMPAIGN_LAUNCH_AUTHORIZED:
        reparsed_clock = parse_clock_command(
            argparse.Namespace(
                device=packet["plan"]["device"],
                receipt=artifacts["clock"]["path"],
            )
        )
        if reparsed_clock != clock_identity:
            raise ContractError(f"{path}: clock receipt reparse differs")
    receipts = packet["receipts"]
    if not isinstance(receipts, list) or len(receipts) not in (1, 2):
        raise ContractError(f"{path}: supervisor receipt inventory differs")
    phases: list[str] = []
    receipt_times: list[int] = []
    supervisor_pids: set[int] = set()
    for index, item in enumerate(receipts):
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ContractError(f"{path}: malformed supervisor receipt")
        receipt_path = Path(item["path"])
        if not receipt_path.is_file() or sha256_file(receipt_path) != _require_sha(
            item["sha256"], "receipt"
        ):
            raise ContractError(f"{path}: changed supervisor receipt")
        receipt = load_json(receipt_path)
        if receipt_path.stat().st_mode & 0o222:
            raise ContractError(f"{path}: writable supervisor receipt")
        phase = receipt.get("phase") if isinstance(receipt, dict) else None
        expected_receipt_keys = {
            "schema",
            "phase",
            "time_ns",
            "supervisor_pid",
            "plan",
            "command_sha256",
        }
        if phase == "spawned":
            expected_receipt_keys |= {"worker_pid", "worker_pgid", "worker_start_ticks"}
        if (
            not isinstance(receipt, dict)
            or set(receipt) != expected_receipt_keys
            or receipt.get("schema") != "qwen38-q64k32-remote-clock-supervisor-phase-v1"
        ):
            raise ContractError(f"{path}: supervisor receipt schema differs")
        phases.append(phase)
        if (
            type(receipt.get("time_ns")) is not int
            or receipt["time_ns"] <= 0
            or type(receipt.get("supervisor_pid")) is not int
            or receipt["supervisor_pid"] <= 1
        ):
            raise ContractError(f"{path}: supervisor receipt time/PID differs")
        receipt_times.append(receipt["time_ns"])
        supervisor_pids.add(receipt["supervisor_pid"])
        if (
            receipt.get("plan") != packet["plan"]
            or receipt.get("command_sha256") != packet["process"]["command_sha256"]
        ):
            raise ContractError(f"{path}: supervisor receipt binding differs")
        if index == 1 and (
            receipt.get("worker_pid") != packet["process"]["pid"]
            or receipt.get("worker_pgid") != packet["process"]["pgid"]
            or receipt.get("worker_start_ticks") != packet["process"]["start_ticks"]
        ):
            raise ContractError(f"{path}: spawned receipt process binding differs")
    if phases != (
        ["before-spawn"]
        if packet["process"]["start_ticks"] is None
        else ["before-spawn", "spawned"]
    ):
        raise ContractError(f"{path}: supervisor receipt phase order differs")
    if (
        len(supervisor_pids) != 1
        or supervisor_pids != {process["supervisor_pid"]}
        or receipt_times[0] != process["started_time_ns"]
        or any(
            current < previous
            for previous, current in zip(receipt_times, receipt_times[1:])
        )
        or receipt_times[-1] > process["finished_time_ns"]
    ):
        raise ContractError(f"{path}: supervisor receipt chronology differs")
    expected_valid = packet["status"] in {
        "success",
        "worker-failure",
        "timeout",
        "interrupted",
    }
    if packet["valid"] is not expected_valid:
        raise ContractError(f"{path}: terminal valid/status mismatch")
    if packet["status"] == "success" and packet["artifacts"]["success"] is None:
        raise ContractError(f"{path}: success terminal lacks success packet")
    if packet["status"] == "success" and (
        artifacts["failure"] is not None
        or artifacts["stderr"] is None
        or artifacts["clock"] is None
        or artifacts["runtime"] is None
        or process["returncode"] != 0
    ):
        raise ContractError(f"{path}: success artifact/return state differs")
    if packet["status"] == "success":
        runtime_packet = validate_runtime_sidecar(
            Path(artifacts["runtime"]["path"]), packet["plan"]["device"]
        )
        if runtime_packet["process_id"] != process["pid"]:
            raise ContractError(f"{path}: runtime-map process binding differs")
        if CAMPAIGN_LAUNCH_AUTHORIZED:
            authorized_repo_audit(REMOTE_REPO)
            qualifier = _load_remote_qualifier(REMOTE_REPO)
            success_path = Path(artifacts["success"]["path"])
            try:
                success_packet = qualifier._validate_run_packet(
                    qualifier.load_json(success_path), success_path
                )
                engagement_path = Path(success_packet["engagement"]["stderr_log_path"])
                if (
                    not engagement_path.is_file()
                    or qualifier.sha256_file(engagement_path)
                    != success_packet["engagement"]["stderr_log_sha256"]
                ):
                    raise qualifier.ContractError("engagement log changed")
                engagement = qualifier._engagement_evidence(
                    engagement_path.read_bytes(), success_packet["role"]
                )
                if engagement["marker_gate_passed"] is not True:
                    raise qualifier.ContractError("engagement marker differs")
            except qualifier.ContractError as error:
                raise ContractError(
                    f"{path}: success packet deep validation failed: {error}"
                ) from error
            if (
                success_packet["role"] != packet["plan"]["role"]
                or success_packet["arm_id"] != packet["plan"]["inner_arm_id"]
                or success_packet["campaign_slot"] != packet["plan"]["slot"]
                or success_packet["process"]["pid"] != process["pid"]
                or success_packet["process"]["start_ticks"] != process["start_ticks"]
            ):
                raise ContractError(f"{path}: success packet process/plan differs")
    if packet["status"] == "worker-failure" and (
        artifacts["success"] is not None
        or artifacts["failure"] is None
        or artifacts["stderr"] is None
        or artifacts["runtime"] is not None
        or process["returncode"] == 0
    ):
        raise ContractError(f"{path}: worker-failure artifact/return state differs")
    if packet["status"] == "worker-failure" and CAMPAIGN_LAUNCH_AUTHORIZED:
        authorized_repo_audit(REMOTE_REPO)
        qualifier = _load_remote_qualifier(REMOTE_REPO)
        failure_path = Path(artifacts["failure"]["path"])
        try:
            failure_packet = qualifier.validate_failure_packet(
                qualifier.load_json(failure_path), failure_path
            )
        except qualifier.ContractError as error:
            raise ContractError(
                f"{path}: failure packet deep validation failed: {error}"
            ) from error
        if (
            failure_packet["role"] != packet["plan"]["role"]
            or failure_packet["arm_id"] != packet["plan"]["inner_arm_id"]
            or failure_packet["campaign_slot"] != packet["plan"]["slot"]
            or failure_packet["process"]["pid"] != process["pid"]
            or failure_packet["process"]["start_ticks"] != process["start_ticks"]
        ):
            raise ContractError(f"{path}: failure packet process/plan differs")
    if path.stat().st_mode & 0o222:
        raise ContractError(f"{path}: terminal packet is writable")
    return packet


def validate_block_boundary_receipts(
    receipt_texts: list[str], terminals: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if len(receipt_texts) != 12:
        raise ContractError("comparison requires exactly 12 block-boundary receipts")
    evidence: list[dict[str, Any]] = []
    for block_index, first in enumerate(range(0, 16, 4), start=1):
        block = terminals[first : first + 4]
        active_device = block[0]["plan"]["device"]
        state = block[0]["plan"]["clock"]
        if any(
            item["plan"]["device"] != active_device or item["plan"]["clock"] != state
            for item in block
        ):
            raise ContractError("block-boundary terminal partition differs")
        inactive_device = 1 - active_device
        paths = [
            Path(text)
            for text in receipt_texts[(block_index - 1) * 3 : block_index * 3]
        ]
        contract = (
            ("inactive-pre", inactive_device, (400, 2800)),
            (
                "active-post",
                active_device,
                (400, 2800) if state == "default" else (2800, 2800),
            ),
            ("inactive-post", inactive_device, (400, 2800)),
        )
        identities: list[dict[str, Any]] = []
        for path, (phase, device, expected_range) in zip(paths, contract):
            identity = parse_clock_command(
                argparse.Namespace(device=device, receipt=str(path))
            )
            if (identity["min_mhz"], identity["max_mhz"]) != expected_range:
                raise ContractError(
                    f"block {block_index} {phase} effective range differs"
                )
            identities.append(identity)
            evidence.append(
                {
                    "block": block_index,
                    "phase": phase,
                    "device": device,
                    "clock_state": state,
                    "identity": identity,
                    "artifact": _artifact(path),
                }
            )
        first_start = block[0]["process"]["started_time_ns"]
        last_finish = block[-1]["process"]["finished_time_ns"]
        if (
            identities[0]["captured_time_ns"] >= first_start
            or identities[1]["captured_time_ns"] <= last_finish
            or identities[2]["captured_time_ns"] < identities[1]["captured_time_ns"]
        ):
            raise ContractError(f"block {block_index} clock receipt timing differs")
    return evidence


def validate_arm_post_receipts(
    receipt_texts: list[str], terminals: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if len(receipt_texts) != 16:
        raise ContractError("comparison requires exactly 16 arm-post receipts")
    evidence: list[dict[str, Any]] = []
    for index, (receipt_text, terminal) in enumerate(
        zip(receipt_texts, terminals), start=1
    ):
        row = terminal["plan"]
        identity = parse_clock_command(
            argparse.Namespace(device=row["device"], receipt=receipt_text)
        )
        expected_range = (400, 2800) if row["clock"] == "default" else (2800, 2800)
        if (identity["min_mhz"], identity["max_mhz"]) != expected_range or identity[
            "captured_time_ns"
        ] <= terminal["process"]["finished_time_ns"]:
            raise ContractError(f"arm {index} post-clock evidence differs")
        if (
            index < 16
            and identity["captured_time_ns"]
            >= terminals[index]["clock_identity"]["captured_time_ns"]
        ):
            raise ContractError(f"arm {index} post/pre clock chronology differs")
        path = Path(receipt_text)
        evidence.append(
            {
                "ordinal": index,
                "device": row["device"],
                "clock_state": row["clock"],
                "identity": identity,
                "artifact": _artifact(path),
            }
        )
    return evidence


def compare_command(args: argparse.Namespace) -> dict[str, Any]:
    require_launch_authorized()
    result_root = require_result_root()
    expected_terminals = [
        str(result_root / f"arm-{ordinal:02d}.terminal.json")
        for ordinal in range(1, 17)
    ]
    expected_arm_posts = [
        str(
            result_root / f"clock-{PLAN[ordinal - 1]['device']}-arm-{ordinal}-post.json"
        )
        for ordinal in range(1, 17)
    ]
    expected_boundaries: list[str] = []
    for block_index, first in enumerate(range(0, 16, 4), start=1):
        active = PLAN[first]["device"]
        inactive = 1 - active
        expected_boundaries.extend(
            (
                str(
                    result_root
                    / f"clock-{inactive}-block-{block_index}-inactive-pre.json"
                ),
                str(
                    result_root / f"clock-{active}-block-{block_index}-active-post.json"
                ),
                str(
                    result_root
                    / f"clock-{inactive}-block-{block_index}-inactive-post.json"
                ),
            )
        )
    if (
        Path(args.output) != result_root / "campaign-comparison.json"
        or Path(args.restoration_terminal)
        != result_root / "campaign-restoration-terminal.json"
        or Path(args.default_operator_comparison)
        != result_root / "default-clock-operator-comparison.json"
        or Path(args.fixed_operator_comparison)
        != result_root / "fixed-clock-operator-comparison.json"
        or args.terminals != expected_terminals
        or args.arm_post_receipts != expected_arm_posts
        or args.block_boundary_receipts != expected_boundaries
    ):
        raise ContractError("campaign comparison paths differ from contract")
    restoration_path = Path(args.restoration_terminal)
    validate_restoration(restoration_path, require_complete=True)
    terminal_paths = [Path(item) for item in args.terminals]
    if len(terminal_paths) != 16:
        raise ContractError("comparison requires exactly 16 terminal packets")
    terminals = [validate_terminal(path) for path in terminal_paths]
    if [item["plan"] for item in terminals] != list(PLAN):
        raise ContractError("terminal order differs from preregistered plan")
    if any(
        item["status"] != "success" or item["valid"] is not True for item in terminals
    ):
        raise ContractError("comparison requires 16 valid success terminals")
    process_identities = {
        (
            item["process"]["pid"],
            item["process"]["start_ticks"],
        )
        for item in terminals
    }
    if len(process_identities) != 16:
        raise ContractError("comparison requires 16 distinct worker processes")
    if (
        sorted(terminals, key=lambda item: item["process"]["started_time_ns"])
        != terminals
    ):
        raise ContractError("global terminal chronology differs from ordinals")
    for previous, current in zip(terminals, terminals[1:]):
        if (
            previous["process"]["finished_time_ns"]
            > current["process"]["started_time_ns"]
        ):
            raise ContractError("global arm processes overlap")
    boundary_receipts = validate_block_boundary_receipts(
        args.block_boundary_receipts, terminals
    )
    arm_post_receipts = validate_arm_post_receipts(args.arm_post_receipts, terminals)
    for block_index in range(4):
        active_boundary = boundary_receipts[block_index * 3 + 1]["identity"]
        last_arm_post = arm_post_receipts[block_index * 4 + 3]["identity"]
        if active_boundary["captured_time_ns"] <= last_arm_post["captured_time_ns"]:
            raise ContractError("block active-post receipt precedes final arm-post")
        if block_index < 3:
            inactive_post = boundary_receipts[block_index * 3 + 2]["identity"]
            next_arm_pre = terminals[(block_index + 1) * 4]["clock_identity"]
            if inactive_post["captured_time_ns"] >= next_arm_pre["captured_time_ns"]:
                raise ContractError("block inactive-post receipt follows next arm-pre")
    success_paths = [Path(item["artifacts"]["success"]["path"]) for item in terminals]
    success_packets: list[dict[str, Any]] = []
    common_runtime: dict[str, Any] | None = None
    for terminal, packet_path in zip(terminals, success_paths):
        packet = load_json(packet_path)
        row = terminal["plan"]
        runtime = packet.get("runtime_identity")
        run_process = packet.get("process")
        if (
            packet.get("role") != row["role"]
            or packet.get("arm_id") != row["inner_arm_id"]
            or packet.get("campaign_slot") != row["slot"]
            or not isinstance(runtime, dict)
            or runtime.get("physical_gpu") != row["device"]
            or runtime.get("hostname") != REMOTE_HOSTNAME
            or not isinstance(run_process, dict)
            or run_process.get("pid") != terminal["process"]["pid"]
            or run_process.get("start_ticks") != terminal["process"]["start_ticks"]
            or not isinstance(run_process.get("started_time_ns"), int)
            or not isinstance(run_process.get("finished_time_ns"), int)
            or run_process["started_time_ns"] < terminal["process"]["started_time_ns"]
            or run_process["finished_time_ns"] > terminal["process"]["finished_time_ns"]
        ):
            raise ContractError(f"{packet_path}: terminal/run identity binding differs")
        runtime_common = {
            key: runtime.get(key)
            for key in (
                "script_sha256",
                "base_qualifier_sha256",
                "campaign_driver_sha256",
                "lab_repo_head",
                "python",
                "torch_version",
                "xpu_device_count",
                "hostname",
                "device_name",
            )
        }
        if common_runtime is None:
            common_runtime = runtime_common
        elif runtime_common != common_runtime:
            raise ContractError(f"{packet_path}: cross-arm runtime identity differs")
        cases = packet.get("cases")
        if not isinstance(cases, list) or len(cases) != 4:
            raise ContractError(
                f"{packet_path}: missing exact four-case fixture inventory"
            )
        for case in cases:
            expected = FIXTURES.get(case.get("kv_length"))
            if expected is None or any(
                case.get(key) != value for key, value in expected.items()
            ):
                raise ContractError(f"{packet_path}: fixture identity differs")
        success_packets.append(packet)
    operator_comparisons: dict[str, dict[str, Any]] = {}
    for state, text in (
        ("default", args.default_operator_comparison),
        ("fixed", args.fixed_operator_comparison),
    ):
        comparison_path = Path(text)
        comparison = load_json(comparison_path)
        state_pairs = sorted(
            (
                (terminal["plan"]["device"], terminal["plan"]["slot"], path)
                for terminal, path in zip(terminals, success_paths)
                if terminal["plan"]["clock"] == state
            ),
            key=lambda item: (item[0], item[1]),
        )
        expected_state_paths = [
            str(path.resolve(strict=True)) for _, _, path in state_pairs
        ]
        expected_state_hashes = [
            sha256_file(Path(path)) for path in expected_state_paths
        ]
        passed = comparison.get("passed")
        expected_classification = (
            "q64k32-candidate-qualified-for-endpoint-campaign"
            if passed is True
            else "q64k32-candidate-rejected-at-operator-gate"
        )
        if (
            not isinstance(comparison, dict)
            or comparison.get("schema")
            != "qwen38-q64k32-remote-clock-operator-compare-v1"
            or type(passed) is not bool
            or comparison.get("classification") != expected_classification
            or comparison.get("clock_state") != state
            or comparison.get("packet_paths") != expected_state_paths
            or comparison.get("packet_sha256") != expected_state_hashes
        ):
            raise ContractError(f"{state} operator comparison identity differs")
        operator_comparisons[state] = {
            "path": str(comparison_path.resolve(strict=True)),
            "sha256": sha256_file(comparison_path),
            "schema": comparison.get("schema"),
            "classification": comparison.get("classification"),
            "passed": passed,
        }
    if not all(item["passed"] for item in operator_comparisons.values()):
        result = {
            "schema": SCHEMA_CAMPAIGN,
            "status": "operator-treatment-rejected",
            "valid": True,
            "terminal_paths": [
                str(path.resolve(strict=True)) for path in terminal_paths
            ],
            "terminal_sha256": [sha256_file(path) for path in terminal_paths],
            "restoration_terminal": {
                "path": str(restoration_path.resolve(strict=True)),
                "sha256": sha256_file(restoration_path),
            },
            "operator_comparisons": operator_comparisons,
            "block_boundary_receipts": boundary_receipts,
            "arm_post_receipts": arm_post_receipts,
            "clock_effects": None,
            "clock_by_policy_interactions": None,
            "fixed_clock_kv1300_all_device_role_lower_ci_positive": None,
            "remote_only": True,
            "absolute_timing_pooling_with_local_forbidden": True,
            "interpretation": (
                "At least one clock-state operator qualification rejected Q64K32; "
                "the treatment is closed before clock-effect interpretation."
            ),
        }
        write_json_atomic(Path(args.output), result)
        return result
    clock_rows: list[dict[str, Any]] = []
    bootstrap_by_cell: dict[tuple[int, str, int], list[float]] = {}
    for device in (0, 1):
        for role in ("control", "candidate"):
            for kv_length in FIXTURES:
                by_state: dict[str, list[list[float]]] = {}
                for state in ("default", "fixed"):
                    arms: list[list[float]] = []
                    for terminal, packet in zip(terminals, success_packets):
                        row = terminal["plan"]
                        if (
                            row["device"] != device
                            or row["clock"] != state
                            or row["role"] != role
                        ):
                            continue
                        case = next(
                            item
                            for item in packet["cases"]
                            if item["kv_length"] == kv_length
                        )
                        samples = case.get("graph_samples_us_per_call")
                        if not isinstance(samples, list) or len(samples) != 40:
                            raise ContractError(
                                "clock comparison requires exact 40-sample graph arrays"
                            )
                        if any(
                            not isinstance(value, (int, float)) or value <= 0
                            for value in samples
                        ):
                            raise ContractError(
                                "clock comparison found invalid graph timing"
                            )
                        arms.append([float(value) for value in samples])
                    if len(arms) != 2 or any(len(values) != 40 for values in arms):
                        raise ContractError(
                            "clock comparison requires two distinct 40-sample arms per cell"
                        )
                    by_state[state] = arms
                default_arm_medians = [
                    statistics.median(values) for values in by_state["default"]
                ]
                fixed_arm_medians = [
                    statistics.median(values) for values in by_state["fixed"]
                ]
                default_center = statistics.mean(default_arm_medians)
                fixed_center = statistics.mean(fixed_arm_medians)
                point = 100.0 * (default_center - fixed_center) / default_center
                generator = random.Random(
                    20260821
                    + device * 10000
                    + (1000 if role == "candidate" else 0)
                    + kv_length
                )
                bootstraps: list[float] = []
                for _ in range(10000):
                    centers: dict[str, float] = {}
                    for state in ("default", "fixed"):
                        selected_arms = [
                            generator.choice(by_state[state]) for _ in range(2)
                        ]
                        arm_medians = [
                            statistics.median(
                                [generator.choice(arm) for _ in range(40)]
                            )
                            for arm in selected_arms
                        ]
                        centers[state] = statistics.mean(arm_medians)
                    bootstraps.append(
                        100.0
                        * (centers["default"] - centers["fixed"])
                        / centers["default"]
                    )
                bootstraps.sort()
                bootstrap_by_cell[(device, role, kv_length)] = bootstraps
                clock_rows.append(
                    {
                        "device": device,
                        "role": role,
                        "kv_length": kv_length,
                        "fresh_process_arms_per_state": 2,
                        "samples_per_arm": 40,
                        "center": "mean of two fresh-process arm medians",
                        "bootstrap": "resample arms, then samples within selected arms",
                        "default_arm_medians_us_per_call": default_arm_medians,
                        "fixed_arm_medians_us_per_call": fixed_arm_medians,
                        "default_center_us_per_call": default_center,
                        "fixed_center_us_per_call": fixed_center,
                        "fixed_saving_percent": point,
                        "bootstrap_95_percent_ci": [
                            bootstraps[249],
                            bootstraps[9749],
                        ],
                    }
                )
    interaction_rows: list[dict[str, Any]] = []
    for device in (0, 1):
        for kv_length in FIXTURES:
            control = next(
                row
                for row in clock_rows
                if row["device"] == device
                and row["role"] == "control"
                and row["kv_length"] == kv_length
            )
            candidate = next(
                row
                for row in clock_rows
                if row["device"] == device
                and row["role"] == "candidate"
                and row["kv_length"] == kv_length
            )
            interaction_generator = random.Random(
                2026082100 + device * 10000 + kv_length
            )
            interactions = sorted(
                interaction_generator.choice(
                    bootstrap_by_cell[(device, "candidate", kv_length)]
                )
                - interaction_generator.choice(
                    bootstrap_by_cell[(device, "control", kv_length)]
                )
                for _ in range(10000)
            )
            interaction_rows.append(
                {
                    "device": device,
                    "kv_length": kv_length,
                    "fixed_clock_policy_interaction_percent": candidate[
                        "fixed_saving_percent"
                    ]
                    - control["fixed_saving_percent"],
                    "bootstrap_95_percent_ci": [
                        interactions[249],
                        interactions[9749],
                    ],
                }
            )
    hurdle_rows = [row for row in clock_rows if row["kv_length"] == 1300]
    clock_gate = all(row["bootstrap_95_percent_ci"][0] > 0 for row in hurdle_rows)
    result = {
        "schema": SCHEMA_CAMPAIGN,
        "status": "qualified" if clock_gate else "clock-treatment-rejected",
        "valid": True,
        "terminal_paths": [str(path.resolve(strict=True)) for path in terminal_paths],
        "terminal_sha256": [sha256_file(path) for path in terminal_paths],
        "restoration_terminal": {
            "path": str(restoration_path.resolve(strict=True)),
            "sha256": sha256_file(restoration_path),
        },
        "operator_comparisons": operator_comparisons,
        "block_boundary_receipts": boundary_receipts,
        "arm_post_receipts": arm_post_receipts,
        "clock_effects": clock_rows,
        "clock_by_policy_interactions": interaction_rows,
        "fixed_clock_kv1300_all_device_role_lower_ci_positive": clock_gate,
        "remote_only": True,
        "absolute_timing_pooling_with_local_forbidden": True,
        "interpretation": (
            "Invoke the frozen Q64 qualifier compare separately for the eight default-clock "
            "and eight fixed-clock success packets. Compare clock ratios only within the same "
            "remote device and role; do not pool absolute timings with the local GPU2 evidence."
        ),
    }
    write_json_atomic(Path(args.output), result)
    return result


def compare_operator_command(args: argparse.Namespace) -> dict[str, Any]:
    require_launch_authorized()
    result_root = require_result_root()
    ordinals = (
        (1, 2, 3, 4, 13, 14, 15, 16)
        if args.clock_state == "default"
        else (9, 10, 11, 12, 5, 6, 7, 8)
    )
    expected_packets = [
        str(result_root / f"arm-{ordinal:02d}.json") for ordinal in ordinals
    ]
    if (
        Path(args.output)
        != result_root / f"{args.clock_state}-clock-operator-comparison.json"
        or args.packets != expected_packets
    ):
        raise ContractError("operator comparison paths differ from campaign contract")
    repo = Path(args.repo)
    authorized_repo_audit(repo)
    qualifier = _load_remote_qualifier(repo)
    packet_paths = [Path(path) for path in args.packets]
    try:
        packets = [
            qualifier._validate_run_packet(qualifier.load_json(path), path)
            for path in packet_paths
        ]
        candidate_packets = [
            packet for packet in packets if packet["role"] == "candidate"
        ]
        manifest_references = {
            (
                packet["stage_identity"]["manifest_path"],
                packet["stage_identity"]["manifest_sha256"],
            )
            for packet in candidate_packets
        }
        if len(manifest_references) != 1:
            raise qualifier.ContractError("candidate manifest identity differs")
        manifest_text, manifest_sha = next(iter(manifest_references))
        manifest_path = Path(manifest_text)
        if (
            not manifest_path.is_file()
            or qualifier.sha256_file(manifest_path) != manifest_sha
        ):
            raise qualifier.ContractError("candidate manifest changed")
        current_identity = qualifier.validate_candidate_manifest(manifest_path)
        for packet in candidate_packets:
            for key in (
                "stage",
                "hashes",
                "manifest_path",
                "manifest_sha256",
                "artifact_path",
                "artifact_sha256",
                "graph_manifest_path",
                "graph_manifest_sha256",
            ):
                if packet["stage_identity"][key] != current_identity[key]:
                    raise qualifier.ContractError(
                        f"candidate manifest revalidation differs for {key}"
                    )
        for packet in packets:
            stderr_path = Path(packet["engagement"]["stderr_log_path"])
            if (
                not stderr_path.is_file()
                or qualifier.sha256_file(stderr_path)
                != packet["engagement"]["stderr_log_sha256"]
            ):
                raise qualifier.ContractError("stderr engagement log changed")
            evidence = qualifier._engagement_evidence(
                stderr_path.read_bytes(), packet["role"]
            )
            if (
                evidence["marker_gate_passed"] is not True
                or evidence["stderr_line_count"]
                != packet["engagement"]["stderr_line_count"]
            ):
                raise qualifier.ContractError("stderr policy marker evidence changed")
        chronological_devices = []
        for packet in sorted(
            packets, key=lambda item: item["process"]["started_time_ns"]
        ):
            device = packet["runtime_identity"]["physical_gpu"]
            if device not in chronological_devices:
                chronological_devices.append(device)
        if chronological_devices not in ([0, 1], [1, 0]):
            raise qualifier.ContractError("remote device chronology differs")
        virtual_map = {
            chronological_devices[0]: 2,
            chronological_devices[1]: 3,
        }
        virtual_packets = copy.deepcopy(packets)
        suffixes = {1: "a1", 2: "b1", 3: "b2", 4: "a2"}
        for packet in virtual_packets:
            actual = packet["runtime_identity"]["physical_gpu"]
            virtual = virtual_map[actual]
            packet["runtime_identity"]["physical_gpu"] = virtual
            packet["runtime_identity"]["ze_affinity_mask"] = str(virtual)
            packet["arm_id"] = f"gpu{virtual}-{suffixes[packet['campaign_slot']]}"
        inherited = qualifier.compare_packets(virtual_packets, 10000)
    except qualifier.ContractError as error:
        raise ContractError(f"remote Q64 comparison failed: {error}") from error
    result = {
        "schema": "qwen38-q64k32-remote-clock-operator-compare-v1",
        "passed": inherited["passed"],
        "classification": inherited["classification"],
        "clock_state": args.clock_state,
        "remote_only": True,
        "absolute_timing_pooling_with_local_forbidden": True,
        "physical_devices": [0, 1],
        "virtual_validation_device_map": {
            str(actual): virtual for actual, virtual in sorted(virtual_map.items())
        },
        "packet_paths": [str(path.resolve(strict=True)) for path in packet_paths],
        "packet_sha256": [sha256_file(path) for path in packet_paths],
        "inherited_comparison": inherited,
    }
    write_json_atomic(Path(args.output), result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command_name", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--repo", default=str(REMOTE_REPO))
    audit.add_argument("--require-host", action="store_true")
    audit.add_argument("--require-stages", action="store_true")
    validate = sub.add_parser("validate-terminal")
    validate.add_argument("packet")
    supervise = sub.add_parser("supervise")
    supervise.add_argument("--ordinal", type=int, required=True)
    supervise.add_argument("--terminal", required=True)
    supervise.add_argument("--stderr", required=True)
    supervise.add_argument("--success", required=True)
    supervise.add_argument("--clock-receipt", required=True)
    supervise.add_argument("--timeout-seconds", type=float, default=900.0)
    supervise.add_argument("--grace-seconds", type=float, default=10.0)
    supervise.add_argument("command", nargs=argparse.REMAINDER)
    worker = sub.add_parser("worker")
    worker.add_argument("--repo", default=str(REMOTE_REPO))
    worker.add_argument("--ordinal", type=int, required=True)
    worker.add_argument("--physical-gpu", type=int, choices=(0, 1), required=True)
    worker.add_argument("--role", choices=("control", "candidate"), required=True)
    worker.add_argument("--outer-arm-id", required=True)
    worker.add_argument("--inner-arm-id", required=True)
    worker.add_argument(
        "--campaign-slot", type=int, choices=(1, 2, 3, 4), required=True
    )
    worker.add_argument("--output", required=True)
    parse_clock = sub.add_parser("parse-clock-receipt")
    parse_clock.add_argument("--device", type=int, choices=(0, 1), required=True)
    parse_clock.add_argument("receipt")
    seal_clock = sub.add_parser("seal-clock-receipt")
    seal_clock.add_argument("--device", type=int, choices=(0, 1), required=True)
    seal_clock.add_argument("--config", required=True)
    seal_clock.add_argument("--discovery", required=True)
    seal_clock.add_argument("--output", required=True)
    restoration = sub.add_parser("seal-restoration")
    restoration.add_argument("--output", required=True)
    restoration.add_argument("--original-exit-code", type=int, required=True)
    restoration.add_argument("--restore-rc", type=int, required=True)
    restoration.add_argument("--pre-run-0", required=True)
    restoration.add_argument("--pre-run-1", required=True)
    restoration.add_argument("--restored-0", required=True)
    restoration.add_argument("--restored-1", required=True)
    restoration.add_argument("terminals", nargs=16)
    compare = sub.add_parser("compare-terminals")
    compare.add_argument("--output", required=True)
    compare.add_argument("--restoration-terminal", required=True)
    compare.add_argument("--default-operator-comparison", required=True)
    compare.add_argument("--fixed-operator-comparison", required=True)
    compare.add_argument("--block-boundary-receipts", nargs=12, required=True)
    compare.add_argument("--arm-post-receipts", nargs=16, required=True)
    compare.add_argument("terminals", nargs=16)
    operator_compare = sub.add_parser("compare-operator")
    operator_compare.add_argument("--repo", default=str(REMOTE_REPO))
    operator_compare.add_argument(
        "--clock-state", choices=("default", "fixed"), required=True
    )
    operator_compare.add_argument("--output", required=True)
    operator_compare.add_argument("packets", nargs=8)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command_name == "audit":
            print(json.dumps(audit_command(args), allow_nan=False, sort_keys=True))
        elif args.command_name == "validate-terminal":
            validate_terminal(Path(args.packet))
            print("PASS")
        elif args.command_name == "supervise":
            result = supervise_command(args)
            print(json.dumps(result, allow_nan=False, sort_keys=True))
            return 0 if result["status"] == "success" and result["valid"] is True else 1
        elif args.command_name == "worker":
            result = worker_command(args)
            print(json.dumps({"passed": True, "arm": result["arm_id"]}, sort_keys=True))
        elif args.command_name == "parse-clock-receipt":
            result = parse_clock_command(args)
            print(json.dumps(result, allow_nan=False, sort_keys=True))
        elif args.command_name == "seal-clock-receipt":
            result = seal_clock_receipt_command(args)
            print(json.dumps(result, allow_nan=False, sort_keys=True))
        elif args.command_name == "seal-restoration":
            result = restoration_command(args)
            print(json.dumps(result, allow_nan=False, sort_keys=True))
            return (
                0 if result["status"] == "restored" and result["valid"] is True else 1
            )
        elif args.command_name == "compare-terminals":
            result = compare_command(args)
            print(json.dumps(result, allow_nan=False, sort_keys=True))
            return 0 if result["status"] == "qualified" else 14
        else:
            result = compare_operator_command(args)
            print(json.dumps(result, allow_nan=False, sort_keys=True))
            return 0 if result["passed"] else 14
    except ContractError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

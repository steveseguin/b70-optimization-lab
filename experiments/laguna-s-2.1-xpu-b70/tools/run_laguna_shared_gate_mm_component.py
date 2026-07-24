#!/usr/bin/env python3
"""Fail-closed one-card leg for the Laguna shared-gate M=8 component gate.

This is deliberately an adapter, not an endpoint benchmark.  Imports do not
create a run root or touch torch.  Once this adapter owns its card directory,
all evidence is O_EXCL, canonical JSON, fsynced, and terminal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gate_laguna_shared_gate_mm_component as contract
import gate_laguna_shared_gate_mm_stage0 as stage0
import orchestrate_laguna_shared_gate_mm_component as coordinator

MAIN = Path("/home/steve/llm-optimizations")
VLLM = Path("/home/steve/src/deepseek-v4-vllm-xpu-dspark")
KERNEL = Path("/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc")
RUNNER = Path(__file__).resolve()
RESULT = "component-result.json"
PRE = "pre-tensor-identity-checkpoint.json"
STARTED = "tensor-work-started-checkpoint.json"
RUNTIME_BINDING = "runtime-card-binding-checkpoint.json"
SCOPE = "constructor-scope-proof.json"
DISPATCH = "dispatch-proof.json"
TIMING = "timing.json"


class ProvenExactnessFailure(RuntimeError):
    """Only a durable, observed raw-BF16 mismatch may use this classification."""


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def sha(path: Path) -> str:
    return contract.sha(path)


def canon(value: Any) -> bytes:
    return contract.canonical(value)


def git(repo: Path, *args: str) -> str:
    return contract.git(repo, *args)


def _write_all(fd: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        wrote = os.write(fd, data[offset:])
        require(wrote > 0, "short write while sealing component evidence")
        offset += wrote


def exclusive_json(path: Path, value: dict[str, Any]) -> None:
    """Canonical O_EXCL checkpoint writer; never creates a parent directory."""
    require(
        path.parent.is_dir() and not path.parent.is_symlink(),
        "checkpoint parent is unsafe",
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        _write_all(fd, canon(value) + b"\n")
        os.fsync(fd)
    finally:
        os.close(fd)
    parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def _clean(repo: Path) -> dict[str, Any]:
    status = git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    require(not status, f"dirty checkout: {repo}")
    return {
        "path": str(repo),
        "commit": git(repo, "rev-parse", "HEAD"),
        "clean": True,
        "status_porcelain": [],
        "status_sha256": hashlib.sha256(b"").hexdigest(),
    }


def _regular(path: Path, label: str) -> None:
    require(
        path.is_file() and not path.is_symlink(),
        f"required regular file missing: {label}",
    )


def _read_canonical(path: Path, label: str) -> dict[str, Any]:
    _regular(path, label)
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"{label} is not JSON") from error
    require(
        isinstance(value, dict) and raw == canon(value) + b"\n",
        f"{label} is not canonical JSON",
    )
    return value


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sysfs(physical: dict[str, Any]) -> dict[str, str]:
    drm = Path(physical["drm_device"])
    require(drm.name.startswith("card"), "invalid packet DRM device")
    link = Path("/sys/class/drm") / drm.name / "device"
    require(link.exists(), "DRM sysfs identity absent")
    device = link.resolve(strict=True)
    require(
        device.is_dir() and str(device).startswith("/sys/devices/"),
        "unsafe DRM sysfs target",
    )
    vendor = (device / "vendor").read_text().strip()
    product = (device / "device").read_text().strip()
    require(device.name == physical["pci_bdf_address"], "DRM/BDF binding drift")
    require(
        vendor == "0x8086" and product == "0xe223", "DRM target is not the expected B70"
    )
    return {
        "drm_device": str(drm),
        "pci_bdf_address": device.name,
        "vendor": vendor,
        "device": product,
        "sysfs_device": str(device),
    }


def _imported_dependency_paths() -> dict[str, Path]:
    """Every Python helper this runner imports before/while doing tensor work."""
    return {
        "contract": Path(contract.__file__).resolve(),
        "coordinator": Path(coordinator.__file__).resolve(),
        "runner": RUNNER,
        "stage0_fixture_generator": Path(stage0.__file__).resolve(),
        "stage0_runtime_adapter": MAIN
        / "experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_shared_gate_mm_stage0.py",
        "stage0_result_analyzer": MAIN
        / "experiments/laguna-s-2.1-xpu-b70/tools/analyze_laguna_shared_gate_mm_stage0.py",
    }


def _verify_runner_dependencies(packet: dict[str, Any]) -> dict[str, dict[str, str]]:
    tools = packet["tools"]
    keys = packet["runtime_dependencies"]["runner"]
    require(
        isinstance(keys, list) and len(keys) == len(set(keys)),
        "runtime dependency keys must be unique",
    )
    required = _imported_dependency_paths()
    require(
        set(keys) == set(required), "runtime dependency set is incomplete or escalated"
    )
    observed: dict[str, dict[str, str]] = {}
    for name in keys:
        record = tools.get(name)
        require(
            isinstance(record, dict) and set(record) >= {"path", "sha256"},
            f"missing tool record: {name}",
        )
        path = required[name]
        _regular(path, name)
        require(
            path == (MAIN / record["path"]).resolve(strict=True),
            f"tool path drift: {name}",
        )
        digest = sha(path)
        require(digest == record["sha256"], f"tool hash drift: {name}")
        observed[name] = {"path": str(path), "sha256": digest}
    # All packet tools are part of the authorization's frozen tooling surface.
    for name, record in tools.items():
        path = (MAIN / record["path"]).resolve(strict=True)
        _regular(path, f"packet tool {name}")
        require(sha(path) == record["sha256"], f"packet tool hash drift: {name}")
    return observed


def _lineage(packet: dict[str, Any], auth: Path) -> dict[str, Any]:
    main, vllm, kernel = _clean(MAIN), _clean(VLLM), _clean(KERNEL)
    track = packet["authorization_tracking"]
    require(track["repository"] == str(MAIN), "authorization repository drift")
    require(
        packet["source"]["main_tools_commit"] == track["tools_commit"],
        "source/tools commit drift",
    )
    head = main["commit"]
    require(
        git(MAIN, "rev-parse", head + "^") == track["tools_commit"],
        "authorization is not frozen-tools child",
    )
    changed = git(
        MAIN, "diff-tree", "--no-commit-id", "--name-only", "-r", head
    ).splitlines()
    require(
        changed == [track["packet_repo_path"]], "authorization child is not packet-only"
    )
    tracked = subprocess.run(
        ["git", "-C", str(MAIN), "show", f"{head}:{track['packet_repo_path']}"],
        check=True,
        capture_output=True,
    ).stdout
    require(
        tracked == auth.read_bytes(), "executed authorization differs from Git object"
    )
    require(vllm["commit"] == packet["source"]["vllm_commit"], "vLLM commit drift")
    require(
        kernel["commit"] == packet["source"]["kernel_commit"], "kernel commit drift"
    )
    for relative, digest in packet["source"]["files"].items():
        path = VLLM / relative
        _regular(path, "vLLM source " + relative)
        require(sha(path) == digest, "vLLM source hash drift: " + relative)
    return {
        "main": main,
        "vllm": vllm,
        "kernel": kernel,
        "authorization_head": head,
        "authorization_bytes_sha256": hashlib.sha256(tracked).hexdigest(),
    }


def _runtime_files(packet: dict[str, Any]) -> dict[str, Any]:
    runtime = packet["runtime"]
    require(
        sys.executable == runtime["python_executable"]
        and sys.version == runtime["python_version"],
        "Python runtime identity drift",
    )
    files: dict[str, dict[str, str]] = {}
    for name, record in runtime["files"].items():
        path = Path(record["path"])
        require(path.is_file(), "runtime identity file is absent: " + name)
        resolved = path.resolve(strict=True)
        require(
            resolved.is_file() and not resolved.is_symlink(),
            "runtime identity target is not a regular file: " + name,
        )
        actual = {
            "path": str(path),
            "resolved_path": str(resolved),
            "sha256": sha(resolved),
        }
        require(actual == record, "runtime file identity drift: " + name)
        files[name] = actual
    return {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "files": files,
    }


def _binaries_and_model(
    packet: dict[str, Any],
) -> tuple[dict[str, str], dict[str, str]]:
    import run_laguna_shared_gate_mm_stage0 as actual

    binaries: dict[str, str] = {}
    require(
        set(packet["binaries"]) == set(actual.EXPECTED_BINARY_PATHS), "binary set drift"
    )
    for name, path in actual.EXPECTED_BINARY_PATHS.items():
        _regular(path, "binary " + name)
        digest = sha(path)
        require(digest == packet["binaries"][name], "binary hash drift: " + name)
        binaries[name] = digest
    model = Path(packet["model"]["config_path"])
    require(
        model == Path("/mnt/fast-ai/llm-models/laguna-s-2.1/int4/config.json"),
        "model config path drift",
    )
    require(
        not str(model.resolve(strict=True)).startswith(("/media/", "/run/media/")),
        "USB model path rejected",
    )
    _regular(model, "model config")
    model_sha = sha(model)
    require(model_sha == packet["model"]["config_sha256"], "model config hash drift")
    return binaries, {"config_path": str(model), "config_sha256": model_sha}


def _expected_argv(auth: Path, fixture: Path, rank: int) -> list[str]:
    return [
        str(Path(sys.executable)),
        str(RUNNER),
        "--authorization",
        str(auth),
        "--fixture",
        str(fixture),
        "--rank",
        str(rank),
    ]


def _campaign_start(
    packet: dict[str, Any], packet_sha256: str
) -> tuple[dict[str, Any], str]:
    campaign = Path(packet["campaign_root"])
    require(
        campaign.is_dir() and not campaign.is_symlink(),
        "campaign root must be coordinator-owned",
    )
    path = campaign / "campaign-start-checkpoint.json"
    start = _read_canonical(path, "campaign start checkpoint")
    require(
        set(start)
        == {
            "format",
            "status",
            "created_utc",
            "packet_path",
            "packet_sha256",
            "rank_order",
            "device_preflight",
            "downstream",
        }
        and start["format"] == "laguna-shared-gate-m8-component-campaign-start-v1"
        and start["status"] == "campaign_root_acquired_before_rank_execution"
        and isinstance(start["created_utc"], str)
        and start["created_utc"].endswith("Z")
        and start["packet_path"] == packet["packet_path"]
        and start["packet_sha256"] == packet_sha256
        and start["rank_order"] == [0, 1, 2, 3]
        and start["downstream"] == contract.FALSE_ACTIONS,
        "campaign start checkpoint binding drift",
    )
    coordinator.validate_device_preflight(start["device_preflight"], packet)
    return start, sha(path)


def _preflight(
    packet: dict[str, Any], auth: Path, fixture_path: Path, rank: int
) -> dict[str, Any]:
    _regular(auth, "authorization")
    require(
        auth == Path(packet["packet_path"]).resolve(strict=True),
        "authorization path drift",
    )
    require(auth.parent == MAIN / "data", "authorization must be tracked data file")
    require(
        auth.read_bytes() == canon(packet) + b"\n",
        "authorization is not canonical bytes",
    )
    card = packet["cards"][rank]
    require(
        card["runner_argv"] == _expected_argv(auth, fixture_path, rank),
        "packet runner argv drift",
    )
    require(
        [str(Path(sys.executable)), str(RUNNER), *sys.argv[1:]] == card["runner_argv"],
        "runner argv drift",
    )
    require(
        fixture_path == Path(packet["stage0"]["fixture_path"]), "fixture argv drift"
    )
    _regular(fixture_path, "fixture")
    require(
        sha(fixture_path) == packet["stage0"]["fixture_sha256"], "fixture hash drift"
    )
    fixture = json.loads(fixture_path.read_text())
    stage0.validate_fixture_manifest(fixture)
    require(
        dict(os.environ) == card["environment"],
        "process environment differs from frozen env -i map",
    )
    require(
        os.environ["ONEAPI_DEVICE_SELECTOR"] == "level_zero:0"
        and os.environ["ZE_AFFINITY_MASK"] == str(rank),
        "rank selectors drift",
    )
    require(
        Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        == packet["boot_id"],
        "boot identity drift",
    )
    _verify_runner_dependencies(packet)
    lineage = _lineage(packet, auth)
    _runtime_files(packet)
    _binaries_and_model(packet)
    sysfs = _sysfs(card["physical"])
    packet_sha256 = sha(auth)
    start, start_sha256 = _campaign_start(packet, packet_sha256)
    expected = card["physical"]
    device_preflight = start["device_preflight"]
    filtered_probe = device_preflight["filtered"][rank]
    card_binding = {
        "packet_sha256": packet_sha256,
        "rank": rank,
        "oneapi_device_selector": "level_zero:0",
        "ze_affinity_mask": str(rank),
        "logical_device_id": 0,
        "physical": expected,
        "sysfs": {
            "drm_device": sysfs["drm_device"],
            "pci_bdf_address": sysfs["pci_bdf_address"],
            "vendor": sysfs["vendor"],
            "device": sysfs["device"],
        },
        "sealed_device_preflight": {
            "campaign_start_path": str(
                Path(packet["campaign_root"]) / "campaign-start-checkpoint.json"
            ),
            "campaign_start_sha256": start_sha256,
            "device_preflight_sha256": hashlib.sha256(
                canon(device_preflight)
            ).hexdigest(),
            "unfiltered_stdout_sha256": device_preflight["unfiltered"]["stdout_sha256"],
            "filtered_stdout_sha256": filtered_probe["stdout_sha256"],
        },
    }
    observed = {
        "argv": card["runner_argv"],
        "environment": dict(os.environ),
        "main_identity": lineage["main"],
        "vllm_identity": lineage["vllm"],
        "kernel_identity": lineage["kernel"],
        "runtime": packet["runtime"],
        "binaries": packet["binaries"],
        "model": packet["model"],
        "boot_id": packet["boot_id"],
        "card_binding": card_binding,
    }
    return {"fixture": fixture, "observed": observed}


def _acquire_card_root(
    packet: dict[str, Any], rank: int, observed: dict[str, Any], packet_sha256: str
) -> Path:
    campaign = Path(packet["campaign_root"])
    card_root = Path(packet["cards"][rank]["output_root"])
    require(
        campaign.is_dir() and not campaign.is_symlink(),
        "campaign root must be precreated by coordinator",
    )
    require(
        card_root.parent == campaign and card_root.name == f"card{rank}",
        "card root escapes frozen campaign",
    )
    require(
        not card_root.exists() and not card_root.is_symlink(), "card root is not fresh"
    )
    names = {entry.name for entry in campaign.iterdir()}
    expected_names = {"campaign-start-checkpoint.json"}
    expected_names.update(f"card{previous}" for previous in range(rank))
    expected_names.update(f"rank-{previous}-terminal.json" for previous in range(rank))
    require(
        names == expected_names,
        "campaign state before card acquisition is not exact",
    )
    for previous in range(rank):
        prior_root = campaign / f"card{previous}"
        require(
            prior_root.is_dir() and not prior_root.is_symlink(),
            f"prior card root is unsafe: {previous}",
        )
        _regular(
            campaign / f"rank-{previous}-terminal.json",
            f"prior rank terminal {previous}",
        )
    start = campaign / "campaign-start-checkpoint.json"
    require(
        start.is_file()
        and not start.is_symlink()
        and sha(start)
        == observed["card_binding"]["sealed_device_preflight"]["campaign_start_sha256"],
        "campaign start checkpoint is unsafe",
    )
    campaign_fd = os.open(campaign, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.mkdir(card_root.name, 0o755, dir_fd=campaign_fd)
        os.fsync(campaign_fd)
    finally:
        os.close(campaign_fd)
    checkpoint = {
        "format": "laguna-shared-gate-m8-component-pre-tensor-v2",
        "packet_sha256": packet_sha256,
        "rank": rank,
        "tensor_work_started": False,
        "observed": observed,
    }
    exclusive_json(card_root / PRE, checkpoint)
    return card_root


def _mkdir_runtime(root: Path) -> None:
    """Create only frozen runtime descendants after root ownership, no symlink traversal."""
    relatives = (
        "runtime/home",
        "runtime/tmp",
        "runtime/cache/huggingface",
        "runtime/cache/numba",
        "runtime/cache/pycache",
        "runtime/cache/sycl",
        "runtime/cache/torchinductor",
        "runtime/cache/transformers",
        "runtime/cache/triton",
        "runtime/cache/vllm",
        "runtime/cache/xdg",
        "runtime/cache/xdg-config",
        "runtime/cache/xdg-data",
        "runtime/cache/xdg-state",
    )
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for relative in relatives:
            fd = os.dup(root_fd)
            try:
                for part in Path(relative).parts:
                    try:
                        os.mkdir(part, 0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                    next_fd = os.open(
                        part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                    )
                    os.close(fd)
                    fd = next_fd
                os.fsync(fd)
            finally:
                os.close(fd)
        os.fsync(root_fd)
    finally:
        os.close(root_fd)


def _parse_runtime_uuid(raw_uuid_value: Any) -> tuple[uuid.UUID, bytes]:
    try:
        if isinstance(raw_uuid_value, str):
            runtime_uuid = uuid.UUID(raw_uuid_value)
            raw_uuid = runtime_uuid.bytes
        elif (
            type(raw_uuid_value).__module__ == "torch._C"
            and type(raw_uuid_value).__name__ == "_XPUuuid"
        ):
            octets = raw_uuid_value.bytes
            require(
                type(octets) is list,
                "Torch runtime XPU UUID bytes view is not a list",
            )
            require(len(octets) == 16, "runtime XPU UUID is not 16 bytes")
            require(
                all(type(value) is int and 0 <= value <= 255 for value in octets),
                "Torch runtime XPU UUID contains an invalid octet",
            )
            raw_uuid = bytes(octets)
            runtime_uuid = uuid.UUID(bytes=raw_uuid)
            require(
                str(raw_uuid_value).lower() == str(runtime_uuid).lower(),
                "Torch runtime XPU UUID text/bytes disagree",
            )
        elif isinstance(raw_uuid_value, (bytes, bytearray, memoryview)):
            raw_uuid = bytes(raw_uuid_value)
            require(len(raw_uuid) == 16, "runtime XPU UUID is not 16 bytes")
            runtime_uuid = uuid.UUID(bytes=raw_uuid)
        else:
            raise TypeError("unsupported runtime XPU UUID type")
    except (TypeError, ValueError, AttributeError) as error:
        raise RuntimeError("runtime XPU UUID is malformed") from error
    return runtime_uuid, raw_uuid


def _runtime_binding(
    torch: Any, card: dict[str, Any], observed_card: dict[str, Any]
) -> dict[str, Any]:
    require(
        torch.xpu.is_available()
        and torch.xpu.device_count() == 1
        and torch.xpu.current_device() == 0,
        "one-visible-XPU contract failed",
    )
    name = torch.xpu.get_device_name(0)
    require(name == stage0.EXPECTED_DEVICE_NAME, "unexpected visible XPU name")
    probe = torch.empty((), device="xpu")
    require(str(probe.device) == "xpu:0", "probe is not on logical xpu:0")
    require(
        os.environ["ONEAPI_DEVICE_SELECTOR"] == "level_zero:0"
        and os.environ["ZE_AFFINITY_MASK"] == str(card["rank"]),
        "runtime selector drift",
    )
    expected = observed_card["card_binding"]
    properties = torch.xpu.get_device_properties(0)
    require(properties is not None, "device properties unavailable")
    torch_runtime_uuid, torch_raw_uuid = _parse_runtime_uuid(properties.uuid)
    torch_runtime_uuid_text = str(torch_runtime_uuid).lower()
    runtime_uuid_bytes = torch_raw_uuid[::-1]
    runtime_uuid_text = str(uuid.UUID(bytes=runtime_uuid_bytes)).lower()
    require(
        runtime_uuid_text == card["physical"]["uuid"],
        "Torch runtime UUID does not bind to preflight physical card",
    )
    return {
        **expected,
        "visible_device_count": int(torch.xpu.device_count()),
        "current_device": int(torch.xpu.current_device()),
        "device_name": name,
        "tensor_device": str(probe.device),
        "torch_version": str(torch.__version__),
        "runtime_uuid": runtime_uuid_text,
        "runtime_uuid_bytes_hex": runtime_uuid_bytes.hex(),
        "torch_runtime_uuid": torch_runtime_uuid_text,
        "torch_runtime_uuid_bytes_hex": torch_raw_uuid.hex(),
        "runtime_uuid_mapping": "xpu_smi_uuid_is_reverse_of_torch_level_zero_bytes",
    }


def _remove_runtime_scratch(root: Path) -> None:
    """Remove only the adapter-owned cache tree before strict evidence sealing."""
    runtime = root / "runtime"
    if not runtime.exists():
        return
    require(
        runtime.is_dir() and not runtime.is_symlink(), "runtime scratch root is unsafe"
    )
    shutil.rmtree(runtime)
    require(not runtime.exists(), "runtime scratch cleanup incomplete")


def _epoch_envelope(
    entry: dict[str, Any], packet_sha256: str, rank: int
) -> dict[str, Any]:
    return {"packet_sha256": packet_sha256, "rank": rank, "entry": entry}


def _actual_exactness(
    packet: dict[str, Any],
    fixture: dict[str, Any],
    root: Path,
    rank: int,
    packet_sha256: str,
    *,
    post: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, dict[str, Any] | None]:
    import torch
    import run_laguna_shared_gate_mm_stage0 as actual

    mlp, laguna, forward_context, scope = actual._construct_real_mlp(torch)
    scope_payload: dict[str, Any] | None = None
    dispatch_payload: dict[str, Any] | None = None
    if not post:
        scope_payload = {"packet_sha256": packet_sha256, "rank": rank, "scope": scope}
        dispatch_payload = {
            "packet_sha256": packet_sha256,
            "rank": rank,
            "proof": actual._dispatch_proof(mlp, fixture, torch, forward_context),
        }
        exclusive_json(root / SCOPE, scope_payload)
        exclusive_json(root / DISPATCH, dispatch_payload)
    phase = "post" if post else "pre"
    count = (
        contract.PROTOCOL["exact_epochs_after"]
        if post
        else contract.PROTOCOL["exact_epochs_before"]
    )
    entries: list[dict[str, Any]] = []
    for epoch in fixture["epochs"][:count]:
        entry = actual._epoch_result(mlp, laguna, epoch, torch, forward_context)
        envelope = _epoch_envelope(entry, packet_sha256, rank)
        exclusive_json(
            root / f"{phase}-epochs" / f"epoch-{epoch['epoch']:03d}.json", envelope
        )
        entries.append(envelope)
        bad = [
            name
            for name, comparison in entry["comparisons"].items()
            if not (
                comparison["raw_uint16_equal"] is True
                and comparison["torch_equal"] is True
            )
        ]
        if bad:
            raise ProvenExactnessFailure(
                f"raw exactness mismatch epoch={epoch['epoch']} pairs={','.join(sorted(bad))}"
            )
    return entries, scope_payload, dispatch_payload


def _timing_fixture(
    fixture: dict[str, Any], torch: Any
) -> tuple[list[tuple[Any, Any, Any, Any, Any, Any, Any]], Any, dict[str, Any]]:
    import run_laguna_shared_gate_mm_stage0 as actual

    corpus: list[tuple[Any, Any, Any, Any, Any, Any, Any]] = []
    input_slots: list[int] = []
    weight_slots: list[int] = []
    control_slots: list[int] = []
    candidate_slots: list[int] = []
    for index, epoch in enumerate(fixture["epochs"][:47]):
        host = actual._load_epoch(epoch, torch)
        rows, weight = host["hidden_input"].to("xpu"), host["gate_weight"].to("xpu")
        rows_bmm, weight_t = rows.unsqueeze(1), weight.t()
        expanded = weight_t.unsqueeze(0).expand(8, -1, -1)
        control = torch.empty((8, 1, 256), dtype=torch.bfloat16, device="xpu")
        candidate = torch.empty((8, 256), dtype=torch.bfloat16, device="xpu")
        corpus.append((rows, weight, rows_bmm, weight_t, expanded, control, candidate))
        input_slots.append(rows.data_ptr())
        weight_slots.append(weight.data_ptr())
        control_slots.append(control.data_ptr())
        candidate_slots.append(candidate.data_ptr())
    all_slots = input_slots + weight_slots + control_slots + candidate_slots
    require(
        len(corpus) == 47
        and len(set(input_slots))
        == len(set(weight_slots))
        == len(set(control_slots))
        == len(set(candidate_slots))
        == 47
        and len(set(all_slots)) == len(all_slots),
        "timing corpus/buffers are not fully distinct",
    )
    evict = torch.zeros(
        contract.PROTOCOL["eviction_bytes_per_arm"] // 4,
        dtype=torch.float32,
        device="xpu",
    )
    return (
        corpus,
        evict,
        {
            "input_slots": sorted(input_slots),
            "weight_slots": sorted(weight_slots),
            "control_output_slots": sorted(control_slots),
            "candidate_output_slots": sorted(candidate_slots),
            "control_layout": _tensor_metadata(corpus[0][5]),
            "candidate_layout": _tensor_metadata(corpus[0][6]),
            "nonalias": True,
        },
    )


def _control(rows_bmm: Any, expanded: Any, out: Any, torch: Any) -> Any:
    return torch.bmm(rows_bmm, expanded, out=out)


def _candidate(rows: Any, weight_t: Any, out: Any, torch: Any) -> Any:
    return torch.mm(rows, weight_t, out=out)


def _tensor_metadata(tensor: Any) -> dict[str, Any]:
    """Concrete metadata proof; raw payloads are captured only outside timing."""
    return {
        "data_ptr": int(tensor.data_ptr()),
        "shape": list(tensor.shape),
        "stride": list(tensor.stride()),
        "dtype": str(tensor.dtype),
        "numel": int(tensor.numel()),
        "element_size": int(tensor.element_size()),
    }


def _timing_slot_proof(
    corpus: list[tuple[Any, Any, Any, Any, Any, Any, Any]],
) -> list[dict[str, Any]]:
    """Record live tensor identities and raw BF16 outside every timed arm."""
    import run_laguna_shared_gate_mm_stage0 as actual

    proofs: list[dict[str, Any]] = []
    for slot, (
        rows,
        weight,
        rows_bmm,
        weight_t,
        expanded,
        control,
        native,
    ) in enumerate(corpus):
        proof = {
            "slot": slot,
            "rows": _tensor_metadata(rows),
            "weight": _tensor_metadata(weight),
            "rows_bmm": _tensor_metadata(rows_bmm),
            "weight_t": _tensor_metadata(weight_t),
            "expanded": _tensor_metadata(expanded),
            "control": _tensor_metadata(control),
            "candidate": _tensor_metadata(native),
        }
        for label, tensor in (
            ("rows", rows),
            ("weight", weight),
            ("control", control),
            ("candidate", native),
        ):
            proof[label]["raw_bf16_le_sha256"] = actual._record_tensor(
                tensor, f"timing.{label}.{slot}", tuple(tensor.shape)
            )["raw_bf16_le_sha256"]
        proofs.append(proof)
    return proofs


def _cycles(
    corpus: list[tuple[Any, Any, Any, Any, Any, Any, Any]],
    candidate: bool,
    cycles: int,
    order: tuple[int, ...],
    torch: Any,
) -> None:
    for _ in range(cycles):
        for index in order:
            rows, _weight, rows_bmm, weight_t, expanded, control, native = corpus[index]
            if candidate:
                _candidate(rows, weight_t, native, torch)
            else:
                _control(rows_bmm, expanded, control, torch)


def _arm(
    corpus: list[tuple[Any, Any, Any, Any, Any, Any, Any]],
    evict: Any,
    candidate: bool,
    order: tuple[int, ...],
    torch: Any,
) -> dict[str, float | int]:
    evict.add_(1)
    torch.xpu.synchronize()
    start = time.perf_counter_ns()
    _cycles(
        corpus, candidate, contract.PROTOCOL["cycles_per_arm_per_block"], order, torch
    )
    torch.xpu.synchronize()
    elapsed = time.perf_counter_ns() - start
    require(elapsed > 0, "timed arm returned a nonpositive duration")
    return {
        "elapsed_ns": elapsed,
        "ms_per_cycle": elapsed
        / contract.PROTOCOL["cycles_per_arm_per_block"]
        / 1_000_000,
    }


def _timing(fixture: dict[str, Any], packet_sha256: str, rank: int) -> dict[str, Any]:
    import torch
    import run_laguna_shared_gate_mm_stage0 as actual

    corpus, evict, buffer_proof = _timing_fixture(fixture, torch)
    weight_bytes_each = corpus[0][1].numel() * corpus[0][1].element_size()
    eviction_bytes = evict.numel() * evict.element_size()
    preflight_rows: list[dict[str, Any]] = []
    with torch.no_grad():
        for index, (
            rows,
            weight,
            rows_bmm,
            weight_t,
            expanded,
            control,
            native,
        ) in enumerate(corpus):
            before = (
                _tensor_metadata(rows),
                control.data_ptr(),
                native.data_ptr(),
                tuple(control.stride()),
                tuple(native.stride()),
                weight.data_ptr(),
                tuple(weight.stride()),
                weight_t.data_ptr(),
                tuple(weight_t.stride()),
                tuple(expanded.stride()),
            )
            literal_bmm = torch.bmm(rows_bmm, expanded)
            literal_mm = torch.mm(rows, weight_t)
            returned_bmm = _control(rows_bmm, expanded, control, torch)
            returned_mm = _candidate(rows, weight_t, native, torch)
            require(
                returned_bmm.data_ptr() == control.data_ptr()
                and returned_mm.data_ptr() == native.data_ptr(),
                "out= did not retain its preallocated output",
            )
            literal_equal = actual._raw_equal(literal_bmm.squeeze(1), literal_mm, torch)
            control_equal = actual._raw_equal(
                control.squeeze(1), literal_bmm.squeeze(1), torch
            )
            candidate_equal = actual._raw_equal(native, literal_mm, torch)
            require(
                literal_equal and control_equal and candidate_equal,
                "outside-timing literal BMM/MM raw equality failed",
            )
            after = (
                _tensor_metadata(rows),
                control.data_ptr(),
                native.data_ptr(),
                tuple(control.stride()),
                tuple(native.stride()),
                weight.data_ptr(),
                tuple(weight.stride()),
                weight_t.data_ptr(),
                tuple(weight_t.stride()),
                tuple(expanded.stride()),
            )
            require(before == after, "timing preflight mutated storage/layout metadata")
            preflight_rows.append(
                {
                    "slot": index,
                    "control_out_supplied_ptr": control.data_ptr(),
                    "control_out_returned_ptr": returned_bmm.data_ptr(),
                    "candidate_out_supplied_ptr": native.data_ptr(),
                    "candidate_out_returned_ptr": returned_mm.data_ptr(),
                    "literal_raw_uint16_equal": literal_equal,
                    "control_out_raw_uint16_equal": control_equal,
                    "candidate_out_raw_uint16_equal": candidate_equal,
                    "input_metadata_unchanged": True,
                    "weight_metadata_unchanged": True,
                    "output_metadata_unchanged": True,
                }
            )
        buffer_proof["pre_timing_slots"] = _timing_slot_proof(corpus)
        fixed = tuple(range(47))
        # Each warm arm is explicitly bounded by a device synchronization.
        # This keeps preflight work out of warm-up and control warm-up out of
        # candidate warm-up; none of these boundaries is timed.
        torch.xpu.synchronize()
        _cycles(corpus, False, contract.PROTOCOL["warm_cycles_per_arm"], fixed, torch)
        torch.xpu.synchronize()
        _cycles(corpus, True, contract.PROTOCOL["warm_cycles_per_arm"], fixed, torch)
        torch.xpu.synchronize()
        blocks: list[dict[str, Any]] = []
        for block in range(31):
            rotation = (block * 11) % 47
            order = tuple((rotation + index) % 47 for index in range(47))
            a1 = _arm(corpus, evict, False, order, torch)
            b1 = _arm(corpus, evict, True, order, torch)
            b2 = _arm(corpus, evict, True, order, torch)
            a2 = _arm(corpus, evict, False, order, torch)
            control_ms = (
                (int(a1["elapsed_ns"]) + int(a2["elapsed_ns"]))
                / 2
                / contract.PROTOCOL["cycles_per_arm_per_block"]
                / 1_000_000
            )
            candidate_ms = (
                (int(b1["elapsed_ns"]) + int(b2["elapsed_ns"]))
                / 2
                / contract.PROTOCOL["cycles_per_arm_per_block"]
                / 1_000_000
            )
            blocks.append(
                {
                    "block": block,
                    "rotation": rotation,
                    "slot_order": list(order),
                    "A1_control_elapsed_ns": a1["elapsed_ns"],
                    "A1_control_ms": a1["ms_per_cycle"],
                    "B1_candidate_elapsed_ns": b1["elapsed_ns"],
                    "B1_candidate_ms": b1["ms_per_cycle"],
                    "B2_candidate_elapsed_ns": b2["elapsed_ns"],
                    "B2_candidate_ms": b2["ms_per_cycle"],
                    "A2_control_elapsed_ns": a2["elapsed_ns"],
                    "A2_control_ms": a2["ms_per_cycle"],
                    "paired_control_ms": control_ms,
                    "paired_candidate_ms": candidate_ms,
                    "saving_ms": control_ms - candidate_ms,
                }
            )
        # This post-timing sync and raw capture are deliberately after every
        # measured arm.  They prove fixed operands and preallocated storage
        # survived the full warm+ABBA protocol without polluting any clock.
        torch.xpu.synchronize()
        buffer_proof["post_timing_slots"] = _timing_slot_proof(corpus)
    savings = [float(row["saving_ms"]) for row in blocks]
    wins, median = sum(value > 0 for value in savings), statistics.median(savings)
    return {
        "packet_sha256": packet_sha256,
        "rank": rank,
        "passed": wins >= contract.PROTOCOL["minimum_wins"]
        and median >= contract.PROTOCOL["minimum_median_saving_ms"],
        "timing_label": "allocation_free_isolated_gate_GEMM_primitive",
        "target_layers_per_cycle": 47,
        "weight_bytes_each": weight_bytes_each,
        "distinct_weights": len(corpus),
        "preallocated_identical_inputs": True,
        "output_ring_slots_per_arm": len(corpus),
        "distinct_preallocated_output_buffers": True,
        "warm_cycles_per_arm": 20,
        "blocks": 31,
        "cycles_per_arm_per_block": 64,
        "calls_per_arm": 3008,
        "eviction_bytes_once_per_arm": eviction_bytes,
        "synchronization": "arm_boundaries_only",
        "arm_order": "A-B-B-A",
        "buffer_proof": buffer_proof,
        "preflight_proof": preflight_rows,
        "candidate_block_wins": wins,
        "median_saving_ms_per_cycle": median,
        "blocks_detail": blocks,
    }


def _checkpoint_paths() -> list[str]:
    return (
        [PRE, STARTED, RUNTIME_BINDING, SCOPE, DISPATCH]
        + [f"pre-epochs/epoch-{i:03d}.json" for i in range(128)]
        + [TIMING]
        + [f"post-epochs/epoch-{i:03d}.json" for i in range(32)]
    )


def _result(
    packet: dict[str, Any], rank: int, packet_sha256: str, observed: dict[str, Any]
) -> dict[str, Any]:
    card = packet["cards"][rank]
    return {
        "format": "laguna-shared-gate-m8-four-card-component-result-v1",
        "status": "component_failed_stop_before_counters",
        "passed": False,
        "rank": rank,
        "physical": card["physical"],
        "packet_path": packet["packet_path"],
        "packet_sha256": packet_sha256,
        "observed": observed,
        "tensor_work_started": False,
        "constructor_scope_proof": None,
        "dispatch_proof": None,
        "actual_forward_proof": None,
        "runtime_card_binding": None,
        "pre_exactness": [],
        "timing": None,
        "post_exactness": [],
        "checkpoints": _checkpoint_paths(),
        "checkpoint_sha256": {},
        "failure": None,
        "downstream": contract.FALSE_ACTIONS,
    }


def _seal_result(root: Path, result: dict[str, Any]) -> None:
    result["checkpoint_sha256"] = {
        relative: sha(root / relative)
        for relative in result["checkpoints"]
        if (root / relative).is_file()
    }
    exclusive_json(root / RESULT, result)


def _failure(
    error: BaseException,
    *,
    kind: str,
    phase: str,
    tensor_work_started: bool,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "phase": phase,
        "error_type": type(error).__name__,
        "message": str(error),
        "tensor_work_started": tensor_work_started,
    }


def _record_pre_tensor_failure(
    packet: dict[str, Any], auth: Path, rank: int, error: BaseException
) -> None:
    """Preserve a runner identity/tooling failure in the terminal campaign."""
    campaign = Path(packet["campaign_root"])
    require(
        campaign.is_dir() and not campaign.is_symlink(),
        "cannot preserve pre-tensor failure outside the frozen campaign",
    )
    exclusive_json(
        campaign / f"rank-{rank}-pre-tensor-failure.json",
        {
            "format": "laguna-shared-gate-m8-component-pre-tensor-failure-v1",
            "status": "component_failed_stop_before_counters",
            "created_utc": _utc(),
            "packet_path": packet["packet_path"],
            "packet_sha256": sha(auth),
            "rank": rank,
            "tensor_work_started": False,
            "failure": _failure(
                error,
                kind="pre_tensor_identity_or_tooling",
                phase="runner_preflight",
                tensor_work_started=False,
            ),
            "downstream": contract.FALSE_ACTIONS,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--rank", type=int, choices=range(4), required=True)
    args = parser.parse_args()
    require(
        args.authorization.is_file() and not args.authorization.is_symlink(),
        "authorization argv must name a regular non-symlink file",
    )
    auth = args.authorization.resolve(strict=True)
    packet = json.loads(auth.read_text())
    contract.validate(packet)
    try:
        preflight = _preflight(packet, auth, args.fixture, args.rank)
    except BaseException as error:
        _record_pre_tensor_failure(packet, auth, args.rank, error)
        raise
    packet_sha256 = sha(auth)
    root = _acquire_card_root(packet, args.rank, preflight["observed"], packet_sha256)
    result = _result(packet, args.rank, packet_sha256, preflight["observed"])
    phase = "card_evidence_setup"
    try:
        # These are the only two non-runtime directories needed by the fixed
        # 166-file inventory.  They are created only after O_EXCL root ownership.
        os.mkdir(root / "pre-epochs", 0o755)
        os.mkdir(root / "post-epochs", 0o755)
        phase = "tensor_work_marker"
        exclusive_json(
            root / STARTED,
            {
                "format": "laguna-shared-gate-m8-component-tensor-start-v2",
                "packet_sha256": packet_sha256,
                "rank": args.rank,
                "tensor_work_started": True,
            },
        )
        result["tensor_work_started"] = True
        _mkdir_runtime(root)
        # First torch/vLLM import follows the terminal durable marker.
        phase = "runtime_import_and_binding"
        import torch

        binding = _runtime_binding(
            torch, packet["cards"][args.rank], preflight["observed"]
        )
        runtime_binding = {
            "format": "laguna-shared-gate-m8-component-runtime-card-binding-v1",
            "packet_sha256": packet_sha256,
            "rank": args.rank,
            "binding": binding,
        }
        exclusive_json(root / RUNTIME_BINDING, runtime_binding)
        result["runtime_card_binding"] = runtime_binding
        phase = "pre_timing_exactness_and_dispatch"
        pre, scope, dispatch = _actual_exactness(
            packet, preflight["fixture"], root, args.rank, packet_sha256
        )
        require(
            scope is not None and dispatch is not None,
            "missing actual-forward scope/dispatch proof",
        )
        result["constructor_scope_proof"] = scope
        result["dispatch_proof"] = dispatch
        result["actual_forward_proof"] = {
            "binding": binding,
            "scope": scope["scope"],
            "packet_sha256": packet_sha256,
            "rank": args.rank,
        }
        result["pre_exactness"] = pre
        phase = "isolated_component_timing"
        timing = _timing(preflight["fixture"], packet_sha256, args.rank)
        exclusive_json(root / TIMING, timing)
        result["timing"] = timing
        phase = "post_timing_exact_replay"
        post, _, _ = _actual_exactness(
            packet, preflight["fixture"], root, args.rank, packet_sha256, post=True
        )
        result["post_exactness"] = post
        require(
            post == pre[:32],
            "post replay is not byte-identical to corresponding pre evidence",
        )
        phase = "card_terminal_classification"
        result["passed"] = bool(timing["passed"])
        if result["passed"]:
            result["status"] = "component-card-pass"
            result["failure"] = None
        else:
            result["status"] = "component_failed_stop_before_counters"
            result["failure"] = {
                "kind": "timing_threshold",
                "phase": "isolated_component_timing",
                "error_type": None,
                "message": "frozen per-card wins/median threshold not met",
                "tensor_work_started": True,
            }
    except ProvenExactnessFailure as error:
        result["status"] = "component_failed_stop_before_counters"
        result["passed"] = False
        result["failure"] = _failure(
            error,
            kind="proven_exactness",
            phase=phase,
            tensor_work_started=result["tensor_work_started"],
        )
    except BaseException as error:
        result["status"] = "component_failed_stop_before_counters"
        result["passed"] = False
        result["failure"] = _failure(
            error,
            kind="runtime_or_infrastructure",
            phase=phase,
            tensor_work_started=result["tensor_work_started"],
        )
    try:
        _remove_runtime_scratch(root)
    except BaseException as error:
        prior = result["failure"]
        result["status"] = "component_failed_stop_before_counters"
        result["passed"] = False
        result["failure"] = {
            "kind": "cleanup_failure",
            "phase": "runtime_scratch_cleanup",
            "error_type": type(error).__name__,
            "message": str(error),
            "tensor_work_started": result["tensor_work_started"],
            "prior_failure": prior,
        }
    _seal_result(root, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "passed": result["passed"],
                "result": str(root / RESULT),
            },
            sort_keys=True,
        )
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

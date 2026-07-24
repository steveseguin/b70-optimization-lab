#!/usr/bin/env python3
"""Offline verifier and final sealer for Laguna gate+up cold counters.

This program never launches a profiler, imports torch, or touches an XPU.  It
accepts only the exact packet-authorized 4-card/16-arm capture, recomputes every
exactness and performance decision, and seals a terminal result.  Analysis,
finalization, and final verification are deliberately separate phases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from statistics import fmean
from typing import Any

import gate_laguna_shared_gate_up_mm_component as component
import gate_laguna_shared_gate_up_mm_counters as contract
import laguna_shared_gate_up_counter_parser as counter_parser
import run_laguna_shared_gate_up_mm_counters as runner


ARMS = ("A1", "B1", "B2", "A2")
RANKS = (0, 1, 2, 3)
MEAN_FIELDS = counter_parser.MEAN_FIELDS
ANALYSIS_NAME = "analysis.json"
TERMINAL_NAME = "campaign-terminal.json"
FINAL_NAME = "counter-final-manifest.json"


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return contract.canonical(value)


def sha(path: Path) -> str:
    return contract.sha(path)


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def read_canonical(path: Path, label: str) -> dict[str, Any]:
    require(
        path.is_file() and not path.is_symlink(),
        f"{label} is missing, irregular, or symlinked: {path}",
    )
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"{label} is not JSON: {path}") from error
    require(
        isinstance(value, dict) and raw == canonical(value) + b"\n",
        f"{label} is not canonical JSON: {path}",
    )
    return value


def strict(value: object, fields: set[str], label: str) -> dict[str, Any]:
    require(
        isinstance(value, dict) and set(value) == fields,
        f"{label} schema drift",
    )
    return value


def durable_exclusive_json(path: Path, value: dict[str, Any]) -> None:
    require(
        not path.exists() and not path.is_symlink(),
        f"refusing to replace evidence: {path}",
    )
    payload = canonical(value) + b"\n"
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o644,
    )
    try:
        pending = memoryview(payload)
        while pending:
            written = os.write(descriptor, pending)
            require(written > 0, "short analyzer evidence write")
            pending = pending[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    parent = os.open(
        path.parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def downstream_after_analysis(passed: bool) -> dict[str, bool]:
    return {
        "counter_execution_performed": True,
        "counter_gate_evaluated": True,
        "endpoint_preregistration_construction_authorized": passed,
        "endpoint_authorized": False,
        "service_authorized": False,
        "model_generation_authorized": False,
        "model_generation_performed": False,
        "network_authorized": False,
        "network_access_performed": False,
        "payload_authorized": False,
        "payload_created": False,
        "submission_authorized": False,
        "submission_performed": False,
        "reboot_authorized": False,
    }


def validate_packet(
    path: Path,
    expected_sha256: str,
    root: Path,
) -> tuple[dict[str, Any], str]:
    packet, packet_sha = runner.tracked_packet(path, expected_sha256)
    require(
        packet.get("format") == "laguna-shared-gate-up-m8-counter-authorization-v2",
        "counter packet format drift",
    )
    require(
        packet.get("protocol") == contract.PROTOCOL
        and packet.get("acceptance") == contract.ACCEPTANCE,
        "counter protocol or acceptance drift",
    )
    require(
        counter_parser.METRIC_HEADER_SHA256
        == contract.EXPECTED["metric_header_sha256"],
        "counter parser metric-header identity drift",
    )
    require(
        packet.get("actions") == contract.expected_actions(True),
        "counter authorization action boundary drift",
    )
    require(
        packet.get("component_evidence") == contract.component_evidence(),
        "component predecessor evidence drift",
    )
    require(
        packet.get("tooling") == contract.mandatory_tools(),
        "counter tool identity drift",
    )
    require(
        packet.get("identity") == contract.runtime_identity(),
        "counter source/runtime/model/boot identity drift",
    )
    require(
        packet.get("campaign") == contract.campaign_paths(root, require_fresh=False),
        "packet campaign path/environment drift",
    )
    require(
        Path(packet["campaign"]["preflight_failure"]).exists() is False,
        "successful capture has a sibling preflight-failure seal",
    )
    return packet, packet_sha


def validate_file_entry(base: Path, name: str, value: object) -> Path:
    entry = strict(value, {"path", "sha256", "bytes"}, f"file entry {name}")
    path = base / name
    require(
        entry["path"] == str(path)
        and is_sha256(entry["sha256"])
        and isinstance(entry["bytes"], int)
        and not isinstance(entry["bytes"], bool)
        and entry["bytes"] >= 0,
        f"file entry metadata drift: {path}",
    )
    require(
        path.is_file()
        and not path.is_symlink()
        and sha(path) == entry["sha256"]
        and path.stat().st_size == entry["bytes"],
        f"file entry bytes drift: {path}",
    )
    return path


def validate_idle(value: object, label: str) -> dict[str, Any]:
    idle = strict(
        value,
        {"text", "sha256", "passed", "rows", "only_xpu_smi_self_rows"},
        label,
    )
    text = idle["text"]
    require(
        isinstance(text, str)
        and idle["sha256"] == hashlib.sha256(text.encode()).hexdigest()
        and idle["passed"] is True
        and idle["rows"] == 4
        and idle["only_xpu_smi_self_rows"] is True,
        f"{label} summary drift",
    )
    rows = [line.split() for line in text.splitlines() if line.strip()]
    require(
        rows and rows[0][:5] == ["PID", "Command", "DeviceID", "SHR", "MEM"],
        f"{label} xpu-smi header drift",
    )
    clients = rows[1:]
    require(len(clients) == 4, f"{label} does not contain four self rows")
    seen: dict[int, int] = {}
    for row in clients:
        require(
            len(row) >= 5
            and row[1] == "xpu-smi"
            and re.fullmatch(r"[0-3]", row[2]) is not None,
            f"{label} contains a non-idle client",
        )
        device = int(row[2])
        seen[device] = seen.get(device, 0) + 1
    require(
        seen == {0: 1, 1: 1, 2: 1, 3: 1},
        f"{label} self-row device mapping drift",
    )
    return idle


def validate_device(value: object, rank: int, label: str) -> dict[str, Any]:
    record = strict(
        value,
        {
            "rank",
            "expected",
            "filtered_text",
            "unfiltered_text",
            "filtered",
            "unfiltered",
            "uuid_bdf_binding_exact",
            "filtered_sha256",
            "unfiltered_sha256",
        },
        label,
    )
    expected = contract.CARDS[rank]
    filtered_text = record["filtered_text"]
    unfiltered_text = record["unfiltered_text"]
    require(
        record["rank"] == rank
        and record["expected"] == expected
        and record["uuid_bdf_binding_exact"] is True
        and isinstance(filtered_text, str)
        and isinstance(unfiltered_text, str)
        and record["filtered_sha256"]
        == hashlib.sha256(filtered_text.encode()).hexdigest()
        and record["unfiltered_sha256"]
        == hashlib.sha256(unfiltered_text.encode()).hexdigest(),
        f"{label} identity envelope drift",
    )
    try:
        parsed_filtered = json.loads(filtered_text)
        parsed_unfiltered = json.loads(unfiltered_text)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"{label} discovery transcript is not JSON") from error
    require(
        parsed_filtered == record["filtered"]
        and parsed_unfiltered == record["unfiltered"],
        f"{label} discovery transcript/record drift",
    )
    unfiltered = record["unfiltered"].get("device_list")
    filtered = record["filtered"].get("device_list")
    require(
        isinstance(unfiltered, list)
        and len(unfiltered) == 4
        and isinstance(filtered, list)
        and len(filtered) == 1,
        f"{label} discovery count drift",
    )
    by_id = {
        row.get("device_id"): row
        for row in unfiltered
        if isinstance(row, dict)
        and isinstance(row.get("device_id"), int)
        and not isinstance(row.get("device_id"), bool)
    }
    require(set(by_id) == set(RANKS), f"{label} unfiltered device IDs drift")
    for card in contract.CARDS:
        physical = by_id[card["rank"]]
        require(
            all(
                physical.get(field) == card[field]
                for field in (
                    "uuid",
                    "pci_bdf_address",
                    "drm_device",
                    "device_name",
                )
            ),
            f"{label} physical card mapping drift",
        )
    visible = filtered[0]
    require(
        isinstance(visible, dict)
        and visible.get("device_id") == 0
        and all(
            visible.get(field) == expected[field]
            for field in (
                "uuid",
                "pci_bdf_address",
                "drm_device",
                "device_name",
            )
        ),
        f"{label} filtered card binding drift",
    )
    return record


def validate_sudo_metadata(value: object, label: str) -> dict[str, Any]:
    metadata = strict(
        value,
        {"path", "mode", "uid", "regular_file", "content_not_recorded"},
        label,
    )
    require(
        metadata["path"] == str(runner.SUDO_PASSWORD)
        and metadata["mode"] == "0600"
        and isinstance(metadata["uid"], int)
        and metadata["regular_file"] is True
        and metadata["content_not_recorded"] is True,
        f"{label} drift",
    )
    return metadata


def validate_mount(value: object, label: str) -> dict[str, Any]:
    mount = strict(value, {"target", "source", "filesystem"}, label)
    require(
        mount
        == {
            "target": str(contract.ARTIFACT),
            "source": contract.EXPECTED["nvme_source"],
            "filesystem": contract.EXPECTED["nvme_fstype"],
        },
        f"{label} is not the frozen internal NVMe/ext4 mount",
    )
    return mount


def validate_source(
    value: object,
    packet: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    source = strict(
        value,
        {
            "captured_utc",
            "repositories",
            "packet_identity",
            "runner",
            "fixture",
        },
        label,
    )
    repositories = source["repositories"]
    require(
        isinstance(repositories, dict)
        and set(repositories) == {"main", "vllm", "kernels", "pti"},
        f"{label} repository inventory drift",
    )
    expected_paths = {
        "main": contract.MAIN,
        "vllm": contract.VLLM,
        "kernels": contract.KERNELS,
        "pti": contract.PTI,
    }
    expected_commits = {
        "main": runner.checked(
            ["git", "-C", str(contract.MAIN), "rev-parse", "HEAD"]
        ).strip(),
        "vllm": contract.EXPECTED["vllm_commit"],
        "kernels": contract.EXPECTED["kernel_commit"],
        "pti": contract.EXPECTED["pti_commit"],
    }
    empty_status_sha = hashlib.sha256(b"").hexdigest()
    for name in repositories:
        record = strict(
            repositories[name],
            {"path", "commit", "clean", "status_sha256"},
            f"{label} repository {name}",
        )
        require(
            record
            == {
                "path": str(expected_paths[name]),
                "commit": expected_commits[name],
                "clean": True,
                "status_sha256": empty_status_sha,
            },
            f"{label} repository state drift: {name}",
        )
    require(
        source["packet_identity"] == packet["identity"]
        and source["runner"]
        == {
            "path": str(runner.RUNNER),
            "sha256": packet["tooling"]["runner"]["sha256"],
        }
        and source["fixture"]
        == {
            "path": str(runner.FIXTURE),
            "sha256": packet["tooling"]["fixture"]["sha256"],
        },
        f"{label} packet/tool binding drift",
    )
    return source


def validate_runtime_tree(base: Path, environment: dict[str, str]) -> str:
    runtime = base / "runtime"
    require(
        runtime.is_dir()
        and not runtime.is_symlink()
        and runtime.resolve(strict=True).is_relative_to(base),
        f"private runtime root drift: {runtime}",
    )
    path_names = {
        "HOME",
        "TMPDIR",
        "TMP",
        "TEMP",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "PYTHONPYCACHEPREFIX",
        "SYCL_CACHE_DIR",
        "TORCHINDUCTOR_CACHE_DIR",
        "TRITON_CACHE_DIR",
        "NUMBA_CACHE_DIR",
        "HF_HOME",
        "TRANSFORMERS_CACHE",
        "VLLM_CACHE_ROOT",
    }
    for name in path_names:
        path = Path(environment[name])
        require(
            path.is_dir()
            and not path.is_symlink()
            and path.resolve(strict=True).is_relative_to(runtime),
            f"private runtime path drift: {name}",
        )
    for current, directories, files in os.walk(
        runtime, topdown=True, followlinks=False
    ):
        parent = Path(current)
        for name in directories:
            require(
                not (parent / name).is_symlink(),
                f"symlinked runtime directory: {parent / name}",
            )
        for name in files:
            child = parent / name
            require(
                child.is_file() and not child.is_symlink(),
                f"unsafe runtime cache file: {child}",
            )
    return str(runtime.relative_to(base.parent.parent))


def validate_fixture(
    value: object,
    *,
    rank: int,
    arm: str,
    packet: dict[str, Any],
    packet_sha: str,
    protocol_sha: str,
    command: list[str],
    environment: dict[str, str],
) -> dict[str, Any]:
    fields = {
        "format",
        "status",
        "created_utc",
        "authorization_sha256",
        "protocol_sha256",
        "fixture_source_sha256",
        "identity",
        "rank",
        "arm",
        "epoch",
        "geometry",
        "pair_order",
        "pairs",
        "selected_pair_invocations",
        "selected_gemm_calls",
        "control_primitives_per_pair",
        "candidate_primitives_per_pair",
        "completion_boundary_before_each_pair",
        "completion_boundary_after_each_pair",
        "eviction_bytes_before_each_pair",
        "input_sha256",
        "input_fixture_sha256",
        "boundary_sha256",
        "all_pair_output_sha256",
        "counter_execution_performed",
        "counter_gate_evaluated",
        "endpoint_preregistration_construction_authorized",
        "endpoint_authorized",
        "model_generation_performed",
        "payload_created",
        "submission_performed",
    }
    fixture = strict(value, fields, "fixture v2")
    treatment = "control" if arm.startswith("A") else "candidate"
    require(
        fixture["format"] == "laguna-shared-gate-up-mm-cold-counter-fixture-v2"
        and fixture["status"] == "fixture-complete"
        and fixture["rank"] == rank
        and fixture["arm"] == treatment
        and fixture["authorization_sha256"] == packet_sha
        and fixture["protocol_sha256"] == protocol_sha
        and fixture["fixture_source_sha256"] == packet["tooling"]["fixture"]["sha256"]
        and fixture["epoch"] == 30_000
        and fixture["pairs"] == 13
        and fixture["selected_pair_invocations"] == 13
        and fixture["selected_gemm_calls"] == 26
        and fixture["pair_order"] == ["gate_proj", "up_proj"],
        "fixture identity/cardinality drift",
    )
    require(
        fixture["geometry"]
        == {
            "rows": 8,
            "k": 3072,
            "n": 256,
            "dtype": "torch.bfloat16",
            "rows_contiguous": True,
            "gate_weight_contiguous": True,
            "up_weight_contiguous": True,
        }
        and fixture["control_primitives_per_pair"] == ["torch.bmm", "torch.bmm"]
        and fixture["candidate_primitives_per_pair"] == ["torch.mm", "torch.mm"]
        and fixture["completion_boundary_before_each_pair"] is True
        and fixture["completion_boundary_after_each_pair"] is True
        and fixture["eviction_bytes_before_each_pair"] == 128 * 1024 * 1024,
        "fixture geometry/primitive/cold protocol drift",
    )
    inputs = strict(
        fixture["input_sha256"],
        {"rows", "gate_weight", "up_weight", "combined"},
        "fixture input hashes",
    )
    require(
        all(is_sha256(inputs[name]) for name in inputs),
        "fixture input hash syntax drift",
    )
    input_body = {name: inputs[name] for name in ("rows", "gate_weight", "up_weight")}
    expected_combined = hashlib.sha256(
        json.dumps(
            input_body,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    require(
        inputs["combined"] == expected_combined
        and fixture["input_fixture_sha256"] == expected_combined,
        "fixture combined input hash drift",
    )
    boundary = strict(
        fixture["boundary_sha256"],
        {"gate", "up"},
        "fixture boundary hashes",
    )
    require(
        all(is_sha256(value) for value in boundary.values()),
        "fixture boundary hash syntax drift",
    )
    require(
        fixture["all_pair_output_sha256"]
        == [
            {
                "pair": str(index),
                "gate": boundary["gate"],
                "up": boundary["up"],
            }
            for index in range(13)
        ],
        "fixture repeated gate/up raw hashes drift",
    )
    identity = strict(
        fixture["identity"],
        {
            "captured_utc",
            "pid",
            "argv",
            "fixture",
            "component_contract",
            "component_runtime",
            "stage0_runtime",
            "model_config",
            "environment",
            "boot_id",
            "kernel_taint",
            "visible_torch_xpu_count",
            "visible_torch_xpu_name",
            "expected_physical_device",
            "mount",
            "subprocesses_started",
        },
        "fixture identity",
    )
    fixture_position = command.index(str(runner.FIXTURE))
    require(
        isinstance(identity["pid"], int)
        and not isinstance(identity["pid"], bool)
        and identity["pid"] > 0
        and identity["argv"] == command[fixture_position:]
        and identity["fixture"]
        == {
            "path": str(runner.FIXTURE),
            "sha256": packet["tooling"]["fixture"]["sha256"],
        }
        and identity["component_contract"]
        == {
            "path": str(
                contract.MAIN / packet["tooling"]["component_contract"]["path"]
            ),
            "sha256": packet["tooling"]["component_contract"]["sha256"],
        }
        and identity["component_runtime"]
        == {
            "path": str(contract.MAIN / packet["tooling"]["component_runtime"]["path"]),
            "sha256": packet["tooling"]["component_runtime"]["sha256"],
        }
        and identity["stage0_runtime"]
        == {
            "path": str(contract.MAIN / packet["tooling"]["stage0_runtime"]["path"]),
            "sha256": packet["tooling"]["stage0_runtime"]["sha256"],
        },
        "fixture source/argv identity drift",
    )
    require(
        identity["model_config"]
        == {
            "path": str(contract.MODEL_CONFIG),
            "sha256": contract.EXPECTED["model_config_sha256"],
        }
        and identity["environment"] == environment
        and identity["boot_id"] == contract.EXPECTED["boot_id"]
        and identity["kernel_taint"] == "0"
        and identity["visible_torch_xpu_count"] == 1
        and identity["visible_torch_xpu_name"] == contract.CARDS[rank]["device_name"]
        and identity["expected_physical_device"] == component.CARDS[rank]
        and identity["mount"]
        == {
            "target": "/mnt/fast-ai",
            "mount_point": "/",
            "source": contract.EXPECTED["nvme_source"],
            "filesystem": contract.EXPECTED["nvme_fstype"],
        }
        and identity["subprocesses_started"] == 0,
        "fixture runtime/card/mount identity drift",
    )
    require(
        fixture["counter_execution_performed"] is True
        and fixture["counter_gate_evaluated"] is False
        and fixture["endpoint_preregistration_construction_authorized"] is False
        and fixture["endpoint_authorized"] is False
        and fixture["model_generation_performed"] is False
        and fixture["payload_created"] is False
        and fixture["submission_performed"] is False,
        "fixture downstream authorization drift",
    )
    return fixture


def validate_preflight(
    value: object,
    *,
    rank: int,
    arm: str,
    packet: dict[str, Any],
    packet_sha: str,
    protocol_sha: str,
    environment: dict[str, str],
) -> dict[str, Any]:
    preflight = strict(
        value,
        {
            "format",
            "status",
            "rank",
            "arm",
            "treatment",
            "authorization_path",
            "authorization_sha256",
            "protocol_sha256",
            "source",
            "physical_device",
            "idle",
            "mount",
            "sudo_password_file",
            "environment",
        },
        "arm preflight",
    )
    treatment = "control" if arm.startswith("A") else "candidate"
    require(
        preflight["format"] == "laguna-shared-gate-up-m8-counter-arm-preflight-v1"
        and preflight["status"] == "passed"
        and preflight["rank"] == rank
        and preflight["arm"] == arm
        and preflight["treatment"] == treatment
        and preflight["authorization_path"] == packet["packet_path"]
        and preflight["authorization_sha256"] == packet_sha
        and preflight["protocol_sha256"] == protocol_sha
        and preflight["environment"] == environment,
        "arm preflight identity/environment drift",
    )
    validate_source(preflight["source"], packet, "arm preflight source")
    validate_device(preflight["physical_device"], rank, "arm physical device")
    validate_idle(preflight["idle"], "arm preflight idle")
    validate_mount(preflight["mount"], "arm preflight mount")
    validate_sudo_metadata(
        preflight["sudo_password_file"], "arm preflight sudo metadata"
    )
    return preflight


def validate_arm(
    path: Path,
    *,
    rank: int,
    arm: str,
    packet: dict[str, Any],
    packet_sha: str,
    protocol_sha: str,
) -> dict[str, Any]:
    base = path.parent
    manifest = read_canonical(path, f"rank {rank} arm {arm} manifest")
    expected_fields = {
        "format",
        "status",
        "completed_utc",
        "rank",
        "arm",
        "treatment",
        "authorization_path",
        "authorization_sha256",
        "protocol_sha256",
        "command",
        "environment",
        "cwd",
        "returncode",
        "unitrace_output_pid_suffix",
        "runtime_subtree",
        "files",
        "fixture",
        "counter_execution_performed",
        *runner.DOWNSTREAM_FALSE,
    }
    strict(manifest, expected_fields, "arm manifest")
    treatment = "control" if arm.startswith("A") else "candidate"
    environment = component.environment(str(base), rank)
    command = runner.unitrace_argv(
        rank,
        arm,
        base,
        packet["tooling"]["fixture"]["sha256"],
        packet_sha,
        protocol_sha,
    )
    runner.validate_unitrace_argv(
        command,
        rank=rank,
        treatment=treatment,
        fixture_sha=packet["tooling"]["fixture"]["sha256"],
        authorization_sha=packet_sha,
        protocol_sha=protocol_sha,
        fixture_output=base / "fixture.json",
    )
    require(
        manifest["format"] == "laguna-shared-gate-up-m8-counter-arm-manifest-v1"
        and manifest["status"] == "complete"
        and manifest["rank"] == rank
        and manifest["arm"] == arm
        and manifest["treatment"] == treatment
        and manifest["authorization_path"] == packet["packet_path"]
        and manifest["authorization_sha256"] == packet_sha
        and manifest["protocol_sha256"] == protocol_sha
        and manifest["command"] == command
        and manifest["environment"] == environment
        and manifest["cwd"] == str(base)
        and manifest["returncode"] == 0
        and manifest["counter_execution_performed"] is True
        and all(manifest[name] is False for name in runner.DOWNSTREAM_FALSE),
        "arm manifest identity/action drift",
    )
    suffix = manifest["unitrace_output_pid_suffix"]
    require(
        isinstance(suffix, str) and re.fullmatch(r"[1-9][0-9]*", suffix),
        "unitrace PID suffix drift",
    )
    expected_files = {
        "preflight.json",
        "stdout.log",
        "stderr.log",
        "fixture.json",
        f"unitrace.{suffix}",
        f"unitrace.metrics.{suffix}",
        "post-arm-idle.json",
    }
    require(
        isinstance(manifest["files"], dict)
        and set(manifest["files"]) == expected_files,
        "arm evidence file inventory drift",
    )
    files = {
        name: validate_file_entry(base, name, manifest["files"][name])
        for name in expected_files
    }
    require(
        files[f"unitrace.{suffix}"].stat().st_size > 0
        and files[f"unitrace.metrics.{suffix}"].stat().st_size > 0,
        "unitrace output is empty",
    )
    runtime = validate_runtime_tree(base, environment)
    require(
        manifest["runtime_subtree"]
        == {
            "path": str(base / "runtime"),
            "private": True,
            "excluded_from_evidence_hashes": True,
        },
        "arm runtime manifest drift",
    )
    expected_children = expected_files | {"runtime", "manifest.json"}
    require(
        {child.name for child in base.iterdir()} == expected_children,
        f"arm tree has extra or missing entries: rank={rank} arm={arm}",
    )
    preflight = validate_preflight(
        read_canonical(files["preflight.json"], "arm preflight"),
        rank=rank,
        arm=arm,
        packet=packet,
        packet_sha=packet_sha,
        protocol_sha=protocol_sha,
        environment=environment,
    )
    validate_idle(
        read_canonical(files["post-arm-idle.json"], "post-arm idle"),
        "post-arm idle",
    )
    fixture = validate_fixture(
        read_canonical(files["fixture.json"], "counter fixture"),
        rank=rank,
        arm=arm,
        packet=packet,
        packet_sha=packet_sha,
        protocol_sha=protocol_sha,
        command=command,
        environment=environment,
    )
    require(
        manifest["fixture"] == fixture and str(fixture["identity"]["pid"]) == suffix,
        "manifest/fixture/PID binding drift",
    )
    metrics = counter_parser.parse_metrics(files[f"unitrace.metrics.{suffix}"])
    timing = counter_parser.parse_timing_properties(
        files[f"unitrace.{suffix}"],
        expected_kernel_name=metrics["kernel_name"],
    )
    require(
        metrics["raw_pairs"] == 13
        and metrics["analyzed_pairs"] == 11
        and metrics["analyzed_gemm_samples"] == 22
        and timing["calls"] == 26
        and timing["auxiliary_timing_rows"].keys()
        == counter_parser.AUXILIARY_TIMING_CALLS.keys(),
        "parsed counter cardinality drift",
    )
    return {
        "rank": rank,
        "arm": arm,
        "treatment": treatment,
        "physical": preflight["physical_device"]["expected"],
        "manifest": {"path": str(path), "sha256": sha(path)},
        "runtime_exclusion": runtime,
        "fixture": fixture,
        "metrics": metrics,
        "timing": timing,
    }


def validate_intent(
    value: object,
    *,
    root: Path,
    packet: dict[str, Any],
    packet_sha: str,
    protocol_sha: str,
) -> dict[str, Any]:
    intent = strict(
        value,
        {
            "format",
            "status",
            "created_utc",
            "campaign_root",
            "authorization_path",
            "authorization_sha256",
            "protocol_sha256",
            "counter_execution_performed",
            *runner.DOWNSTREAM_FALSE,
        },
        "campaign intent",
    )
    require(
        intent["format"] == "laguna-shared-gate-up-m8-counter-campaign-intent-v1"
        and intent["status"] == "started"
        and intent["campaign_root"] == str(root)
        and intent["authorization_path"] == packet["packet_path"]
        and intent["authorization_sha256"] == packet_sha
        and intent["protocol_sha256"] == protocol_sha
        and intent["counter_execution_performed"] is False
        and all(intent[name] is False for name in runner.DOWNSTREAM_FALSE),
        "campaign intent contract drift",
    )
    return intent


def validate_open(
    value: object,
    *,
    root: Path,
    packet: dict[str, Any],
    packet_sha: str,
    protocol_sha: str,
) -> dict[str, Any]:
    opened = strict(
        value,
        {
            "format",
            "status",
            "created_utc",
            "campaign_root",
            "authorization_path",
            "authorization_sha256",
            "packet_actions",
            "protocol",
            "protocol_sha256",
            "acceptance",
            "component_evidence",
            "tooling",
            "identity",
            "campaign_specification",
            "campaign_intent",
            "source",
            "mount",
            "pre_root_preflight",
            "planned_cards",
            "planned_arms_per_card",
            "counter_execution_performed",
            *runner.DOWNSTREAM_FALSE,
        },
        "campaign open",
    )
    require(
        opened["format"] == "laguna-shared-gate-up-m8-counter-campaign-open-v1"
        and opened["status"] == "open"
        and opened["campaign_root"] == str(root)
        and opened["authorization_path"] == packet["packet_path"]
        and opened["authorization_sha256"] == packet_sha
        and opened["packet_actions"] == packet["actions"]
        and opened["protocol"] == packet["protocol"]
        and opened["protocol_sha256"] == protocol_sha
        and opened["acceptance"] == packet["acceptance"]
        and opened["component_evidence"] == packet["component_evidence"]
        and opened["tooling"] == packet["tooling"]
        and opened["identity"] == packet["identity"]
        and opened["campaign_specification"] == packet["campaign"]
        and opened["campaign_intent"]
        == {
            "path": packet["campaign"]["intent"],
            "sha256": sha(Path(packet["campaign"]["intent"])),
        }
        and opened["planned_cards"] == list(RANKS)
        and opened["planned_arms_per_card"] == list(ARMS)
        and opened["counter_execution_performed"] is False
        and all(opened[name] is False for name in runner.DOWNSTREAM_FALSE),
        "campaign-open contract drift",
    )
    validate_source(opened["source"], packet, "campaign-open source")
    validate_mount(opened["mount"], "campaign-open mount")
    pre_root = strict(
        opened["pre_root_preflight"],
        {"devices", "idle", "sudo_password_file"},
        "pre-root preflight",
    )
    require(
        isinstance(pre_root["devices"], list) and len(pre_root["devices"]) == 4,
        "pre-root device coverage drift",
    )
    for rank, device in enumerate(pre_root["devices"]):
        validate_device(device, rank, f"pre-root device {rank}")
    validate_idle(pre_root["idle"], "pre-root idle")
    validate_sudo_metadata(pre_root["sudo_password_file"], "pre-root sudo metadata")
    return opened


def validate_card(
    root: Path,
    *,
    rank: int,
    arm_entries: list[dict[str, Any]],
    packet_sha: str,
    protocol_sha: str,
) -> dict[str, Any]:
    card_root = root / f"card{rank}"
    card_path = card_root / "card.manifest.json"
    card = read_canonical(card_path, f"card {rank} manifest")
    strict(
        card,
        {
            "format",
            "status",
            "completed_utc",
            "rank",
            "authorization_sha256",
            "protocol_sha256",
            "arms",
            "post_card_idle",
            "counter_execution_performed",
            *runner.DOWNSTREAM_FALSE,
        },
        f"card {rank} manifest",
    )
    idle_path = card_root / "post-card-idle.json"
    require(
        card["format"] == "laguna-shared-gate-up-m8-counter-card-manifest-v1"
        and card["status"] == "complete"
        and card["rank"] == rank
        and card["authorization_sha256"] == packet_sha
        and card["protocol_sha256"] == protocol_sha
        and card["arms"] == arm_entries
        and card["post_card_idle"] == {"path": str(idle_path), "sha256": sha(idle_path)}
        and card["counter_execution_performed"] is True
        and all(card[name] is False for name in runner.DOWNSTREAM_FALSE),
        f"card {rank} closure drift",
    )
    validate_idle(
        read_canonical(idle_path, f"card {rank} post idle"),
        f"card {rank} post idle",
    )
    require(
        {child.name for child in card_root.iterdir()}
        == {
            *ARMS,
            "card.manifest.json",
            "post-card-idle.json",
        },
        f"card {rank} tree drift",
    )
    return {"rank": rank, "path": str(card_path), "sha256": sha(card_path)}


def validate_complete(
    value: object,
    *,
    root: Path,
    open_path: Path,
    packet: dict[str, Any],
    packet_sha: str,
    protocol_sha: str,
    cards: list[dict[str, Any]],
    arms: list[dict[str, Any]],
) -> dict[str, Any]:
    complete = strict(
        value,
        {
            "format",
            "status",
            "completed_utc",
            "campaign_root",
            "authorization_path",
            "authorization_sha256",
            "protocol_sha256",
            "campaign_open",
            "cards",
            "arms",
            "final_idle",
            "counter_execution_performed",
            *runner.DOWNSTREAM_FALSE,
        },
        "campaign complete",
    )
    final_idle = root / "final-idle.json"
    require(
        complete["format"] == "laguna-shared-gate-up-m8-counter-campaign-complete-v1"
        and complete["status"] == "complete"
        and complete["campaign_root"] == str(root)
        and complete["authorization_path"] == packet["packet_path"]
        and complete["authorization_sha256"] == packet_sha
        and complete["protocol_sha256"] == protocol_sha
        and complete["campaign_open"]
        == {"path": str(open_path), "sha256": sha(open_path)}
        and complete["cards"] == cards
        and complete["arms"] == arms
        and complete["final_idle"]
        == {"path": str(final_idle), "sha256": sha(final_idle)}
        and complete["counter_execution_performed"] is True
        and all(complete[name] is False for name in runner.DOWNSTREAM_FALSE),
        "campaign-complete closure drift",
    )
    validate_idle(
        read_canonical(final_idle, "campaign final idle"),
        "campaign final idle",
    )
    return complete


def validate_capture(
    root: Path,
    packet: dict[str, Any],
    packet_sha: str,
    *,
    phase: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    require(
        root.is_absolute()
        and root.resolve(strict=True) == root
        and root.parent == contract.RUNS
        and not root.is_symlink()
        and re.fullmatch(r"shared-gate-up-m8-counters-[0-9]{8}T[0-9]{6}Z", root.name)
        is not None,
        "campaign root identity drift",
    )
    require(
        not (root / "campaign.error.json").exists()
        and not (root / "analysis.error.json").exists()
        and not (root / "finalization.error.json").exists(),
        "campaign has a terminal capture/analysis/finalization error",
    )
    protocol_sha = canonical_sha(packet["protocol"])
    intent_path = root / "campaign.intent.json"
    open_path = root / "campaign.open.json"
    complete_path = root / "campaign.complete.json"
    validate_intent(
        read_canonical(intent_path, "campaign intent"),
        root=root,
        packet=packet,
        packet_sha=packet_sha,
        protocol_sha=protocol_sha,
    )
    validate_open(
        read_canonical(open_path, "campaign open"),
        root=root,
        packet=packet,
        packet_sha=packet_sha,
        protocol_sha=protocol_sha,
    )
    profiles: list[dict[str, Any]] = []
    arm_entries: list[dict[str, Any]] = []
    card_entries: list[dict[str, Any]] = []
    runtime_exclusions: list[str] = []
    for rank in RANKS:
        card_arms: list[dict[str, Any]] = []
        for arm in ARMS:
            manifest_path = root / f"card{rank}" / arm / "manifest.json"
            profile = validate_arm(
                manifest_path,
                rank=rank,
                arm=arm,
                packet=packet,
                packet_sha=packet_sha,
                protocol_sha=protocol_sha,
            )
            entry = {
                "rank": rank,
                "arm": arm,
                "treatment": profile["treatment"],
                "path": str(manifest_path),
                "sha256": sha(manifest_path),
            }
            profiles.append(profile)
            arm_entries.append(entry)
            card_arms.append(entry)
            runtime_exclusions.append(profile["runtime_exclusion"])
        card_entries.append(
            validate_card(
                root,
                rank=rank,
                arm_entries=card_arms,
                packet_sha=packet_sha,
                protocol_sha=protocol_sha,
            )
        )
    complete = validate_complete(
        read_canonical(complete_path, "campaign complete"),
        root=root,
        open_path=open_path,
        packet=packet,
        packet_sha=packet_sha,
        protocol_sha=protocol_sha,
        cards=card_entries,
        arms=arm_entries,
    )
    require(
        sorted(runtime_exclusions)
        == sorted(f"card{rank}/{arm}/runtime" for rank in RANKS for arm in ARMS),
        "private runtime exclusion inventory drift",
    )
    expected_root = {
        "campaign.intent.json",
        "campaign.open.json",
        "campaign.complete.json",
        "final-idle.json",
        "card0",
        "card1",
        "card2",
        "card3",
    }
    if phase in {"finalize", "terminal-only", "final"}:
        expected_root.add(ANALYSIS_NAME)
    if phase in {"terminal-only", "final"}:
        expected_root.add(TERMINAL_NAME)
    if phase == "final":
        expected_root.add(FINAL_NAME)
    require(
        {child.name for child in root.iterdir()} == expected_root,
        f"campaign root inventory drift in {phase} phase",
    )
    return complete, profiles, sorted(runtime_exclusions)


def average_profiles(profiles: list[dict[str, Any]]) -> dict[str, float]:
    require(profiles, "cannot average an empty profile set")
    return {
        field: fmean(profile["metrics"]["mean"][field] for profile in profiles)
        for field in MEAN_FIELDS
    }


def compare(
    candidate: dict[str, float],
    control: dict[str, float],
    *,
    guardrails: bool,
) -> dict[str, Any]:
    for field in (
        "GpuTime[ns]",
        "GPU_MEMORY_BYTE_READ[bytes]",
        "LOAD_STORE_CACHE_BYTE_READ[bytes]",
    ):
        require(
            math.isfinite(candidate[field])
            and math.isfinite(control[field])
            and control[field] > 0.0,
            f"invalid comparison denominator: {field}",
        )
    checks = {
        "candidate_gpu_time_lower": (candidate["GpuTime[ns]"] < control["GpuTime[ns]"])
    }
    if guardrails:
        acceptance = contract.ACCEPTANCE
        checks.update(
            {
                "gpu_memory_read_regression_within_2pct": (
                    candidate["GPU_MEMORY_BYTE_READ[bytes]"]
                    <= control["GPU_MEMORY_BYTE_READ[bytes]"]
                    * (1.0 + acceptance["maximum_gpu_memory_read_regression_fraction"])
                ),
                "lsc_read_regression_within_2pct": (
                    candidate["LOAD_STORE_CACHE_BYTE_READ[bytes]"]
                    <= control["LOAD_STORE_CACHE_BYTE_READ[bytes]"]
                    * (1.0 + acceptance["maximum_lsc_read_regression_fraction"])
                ),
                "thread_occupancy_decrease_within_0_5pp": (
                    candidate["XVE_THREADS_OCCUPANCY_ALL[%]"]
                    >= control["XVE_THREADS_OCCUPANCY_ALL[%]"]
                    - acceptance["maximum_thread_occupancy_decrease_percentage_points"]
                ),
                "xve_active_decrease_within_0_5pp": (
                    candidate["XVE_ACTIVE[%]"]
                    >= control["XVE_ACTIVE[%]"]
                    - acceptance["maximum_xve_active_decrease_percentage_points"]
                ),
                "xve_stall_increase_within_0_5pp": (
                    candidate["XVE_STALL[%]"]
                    <= control["XVE_STALL[%]"]
                    + acceptance["maximum_xve_stall_increase_percentage_points"]
                ),
            }
        )
    return {
        "control_mean": control,
        "candidate_mean": candidate,
        "delta": {field: candidate[field] - control[field] for field in MEAN_FIELDS},
        "gpu_time_ratio": candidate["GpuTime[ns]"] / control["GpuTime[ns]"],
        "guardrail_scope": (
            "gpu-time-plus-full-metric-guardrails" if guardrails else "gpu-time-only"
        ),
        "checks": checks,
        "passed": all(checks.values()),
    }


def analyze_profiles(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    by = {(profile["rank"], profile["arm"]): profile for profile in profiles}
    require(
        len(by) == 16 and set(by) == {(rank, arm) for rank in RANKS for arm in ARMS},
        "profile rank/arm coverage drift",
    )
    input_records = {
        canonical(profile["fixture"]["input_sha256"]) for profile in profiles
    }
    input_fixtures = {
        profile["fixture"]["input_fixture_sha256"] for profile in profiles
    }
    gate_outputs = {
        profile["fixture"]["boundary_sha256"]["gate"] for profile in profiles
    }
    up_outputs = {profile["fixture"]["boundary_sha256"]["up"] for profile in profiles}
    pair_outputs = {
        canonical(profile["fixture"]["all_pair_output_sha256"]) for profile in profiles
    }
    require(
        len(input_records)
        == len(input_fixtures)
        == len(gate_outputs)
        == len(up_outputs)
        == len(pair_outputs)
        == 1,
        "cross-arm/card raw input or gate/up output drift",
    )
    control_kernels = {
        profile["metrics"]["kernel_name"]
        for profile in profiles
        if profile["treatment"] == "control"
    }
    candidate_kernels = {
        profile["metrics"]["kernel_name"]
        for profile in profiles
        if profile["treatment"] == "candidate"
    }
    require(
        len(control_kernels) == len(candidate_kernels) == 1,
        "kernel identity differs within a treatment",
    )
    cards: dict[str, Any] = {}
    card_passes: list[bool] = []
    for rank in RANKS:
        first = compare(
            by[rank, "B1"]["metrics"]["mean"],
            by[rank, "A1"]["metrics"]["mean"],
            guardrails=False,
        )
        second = compare(
            by[rank, "B2"]["metrics"]["mean"],
            by[rank, "A2"]["metrics"]["mean"],
            guardrails=False,
        )
        aggregate = compare(
            average_profiles([by[rank, "B1"], by[rank, "B2"]]),
            average_profiles([by[rank, "A1"], by[rank, "A2"]]),
            guardrails=True,
        )
        passed = first["passed"] and second["passed"] and aggregate["passed"]
        cards[str(rank)] = {
            "physical": contract.CARDS[rank],
            "B1_vs_A1": first,
            "B2_vs_A2": second,
            "candidate_vs_control_aggregate": aggregate,
            "passed": passed,
        }
        card_passes.append(passed)
    global_result = compare(
        average_profiles(
            [profile for profile in profiles if profile["treatment"] == "candidate"]
        ),
        average_profiles(
            [profile for profile in profiles if profile["treatment"] == "control"]
        ),
        guardrails=False,
    )
    passed = all(card_passes) and global_result["passed"]
    summaries = [
        {
            "rank": profile["rank"],
            "arm": profile["arm"],
            "treatment": profile["treatment"],
            "manifest": profile["manifest"],
            "kernel_name": profile["metrics"]["kernel_name"],
            "metric_mean": profile["metrics"]["mean"],
            "selected_timing": profile["timing"]["selected"],
            "input_fixture_sha256": profile["fixture"]["input_fixture_sha256"],
            "gate_output_sha256": profile["fixture"]["boundary_sha256"]["gate"],
            "up_output_sha256": profile["fixture"]["boundary_sha256"]["up"],
        }
        for profile in profiles
    ]
    return {
        "passed": passed,
        "exactness": {
            "all_16_arms_raw_bit_exact": True,
            "input_sha256": json.loads(next(iter(input_records))),
            "input_fixture_sha256": next(iter(input_fixtures)),
            "gate_output_sha256": next(iter(gate_outputs)),
            "up_output_sha256": next(iter(up_outputs)),
            "all_13_gate_up_repeats_exact": True,
            "component_final_manifest_sha256": contract.EXPECTED[
                "component_manifest_sha256"
            ],
        },
        "control_kernel_name": next(iter(control_kernels)),
        "candidate_kernel_name": next(iter(candidate_kernels)),
        "retained_pair_indices": list(range(2, 13)),
        "cards": cards,
        "global_four_card_candidate_vs_control": global_result,
        "global_cannot_rescue": True,
        "profiles": summaries,
    }


def analysis_payload(
    root: Path,
    packet: dict[str, Any],
    packet_sha: str,
    complete: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    passed = decision["passed"]
    status = (
        "counter-passed-endpoint-preregistration-construction-next"
        if passed
        else "counter-failed-stop-before-endpoint"
    )
    complete_path = root / "campaign.complete.json"
    return {
        "format": "laguna-shared-gate-up-m8-counter-analysis-v2",
        "status": status,
        "passed": passed,
        "campaign_root": str(root),
        "authorization_path": packet["packet_path"],
        "authorization_sha256": packet_sha,
        "protocol_sha256": canonical_sha(packet["protocol"]),
        "campaign_complete": {
            "path": str(complete_path),
            "sha256": sha(complete_path),
            "status": complete["status"],
        },
        "decision": decision,
        "downstream": downstream_after_analysis(passed),
    }


def terminal_payload(
    root: Path,
    analysis: dict[str, Any],
    packet_sha: str,
) -> dict[str, Any]:
    analysis_path = root / ANALYSIS_NAME
    passed = analysis["passed"]
    return {
        "format": "laguna-shared-gate-up-m8-counter-terminal-v2",
        "status": analysis["status"],
        "passed": passed,
        "campaign_root": str(root),
        "authorization_sha256": packet_sha,
        "analysis": {
            "path": str(analysis_path),
            "sha256": sha(analysis_path),
        },
        "campaign_complete": analysis["campaign_complete"],
        "downstream": downstream_after_analysis(passed),
    }


def evidence_inventory(root: Path) -> tuple[dict[str, Any], list[str]]:
    files: dict[str, Any] = {}
    excluded_runtime: list[str] = []
    for current, directories, names in os.walk(root, topdown=True, followlinks=False):
        parent = Path(current)
        relative_parent = parent.relative_to(root)
        kept_directories: list[str] = []
        for name in directories:
            child = parent / name
            require(not child.is_symlink(), f"symlinked artifact directory: {child}")
            relative = child.relative_to(root)
            if name == "runtime" and relative.parts[-2] in ARMS:
                excluded_runtime.append(str(relative))
            else:
                kept_directories.append(name)
        directories[:] = kept_directories
        for name in names:
            child = parent / name
            require(
                child.is_file() and not child.is_symlink(),
                f"unsafe artifact file: {child}",
            )
            relative = str(
                (relative_parent / name) if str(relative_parent) != "." else Path(name)
            )
            if relative == FINAL_NAME:
                continue
            files[relative] = {
                "sha256": sha(child),
                "bytes": child.stat().st_size,
            }
    return dict(sorted(files.items())), sorted(excluded_runtime)


def final_manifest_payload(
    root: Path,
    packet_sha: str,
    analysis: dict[str, Any],
) -> dict[str, Any]:
    files, excluded_runtime = evidence_inventory(root)
    return {
        "format": "laguna-shared-gate-up-m8-counter-final-manifest-v2",
        "status": analysis["status"],
        "passed": analysis["passed"],
        "campaign_root": str(root),
        "authorization_sha256": packet_sha,
        "analysis_sha256": sha(root / ANALYSIS_NAME),
        "terminal_sha256": sha(root / TERMINAL_NAME),
        "files": files,
        "file_count": len(files),
        "excluded_runtime_subtrees": excluded_runtime,
        "exclusion_reason": "private transient runtime/cache trees are not counter evidence",
    }


def perform_analysis(
    root: Path,
    packet: dict[str, Any],
    packet_sha: str,
) -> dict[str, Any]:
    complete, profiles, _runtime = validate_capture(
        root, packet, packet_sha, phase="analyze"
    )
    decision = analyze_profiles(profiles)
    payload = analysis_payload(root, packet, packet_sha, complete, decision)
    require(
        Path(packet["campaign"]["analysis"]) == root / ANALYSIS_NAME,
        "packet analysis path drift",
    )
    durable_exclusive_json(root / ANALYSIS_NAME, payload)
    return payload


def perform_finalize(
    root: Path,
    packet: dict[str, Any],
    packet_sha: str,
) -> dict[str, Any]:
    terminal_path = root / TERMINAL_NAME
    phase = "terminal-only" if terminal_path.exists() else "finalize"
    complete, profiles, _runtime = validate_capture(
        root, packet, packet_sha, phase=phase
    )
    decision = analyze_profiles(profiles)
    expected_analysis = analysis_payload(root, packet, packet_sha, complete, decision)
    analysis = read_canonical(root / ANALYSIS_NAME, "sealed analysis")
    require(analysis == expected_analysis, "sealed analysis recomputation drift")
    expected_terminal = terminal_payload(root, analysis, packet_sha)
    if terminal_path.exists():
        require(
            read_canonical(terminal_path, "campaign terminal") == expected_terminal,
            "existing terminal seal drift",
        )
    else:
        durable_exclusive_json(terminal_path, expected_terminal)
    require(
        Path(packet["campaign"]["terminal"]) == terminal_path
        and Path(packet["campaign"]["final_manifest"]) == root / FINAL_NAME,
        "packet terminal/final path drift",
    )
    manifest = final_manifest_payload(root, packet_sha, analysis)
    durable_exclusive_json(root / FINAL_NAME, manifest)
    return manifest


def verify_final(
    root: Path,
    packet: dict[str, Any],
    packet_sha: str,
) -> dict[str, Any]:
    complete, profiles, _runtime = validate_capture(
        root, packet, packet_sha, phase="final"
    )
    decision = analyze_profiles(profiles)
    expected_analysis = analysis_payload(root, packet, packet_sha, complete, decision)
    analysis = read_canonical(root / ANALYSIS_NAME, "sealed analysis")
    require(analysis == expected_analysis, "final analysis recomputation drift")
    expected_terminal = terminal_payload(root, analysis, packet_sha)
    terminal = read_canonical(root / TERMINAL_NAME, "campaign terminal")
    require(terminal == expected_terminal, "final terminal binding drift")
    expected_manifest = final_manifest_payload(root, packet_sha, analysis)
    manifest = read_canonical(root / FINAL_NAME, "counter final manifest")
    require(manifest == expected_manifest, "counter final manifest rehash drift")
    return manifest


def maybe_seal_analysis_error(
    root: Path,
    packet: dict[str, Any],
    packet_sha: str,
    error: BaseException,
) -> None:
    error_path = root / "analysis.error.json"
    analysis_path = root / ANALYSIS_NAME
    require(
        root.parent == contract.RUNS
        and root == Path(packet["campaign"]["root"])
        and root.is_dir()
        and not root.is_symlink()
        and re.fullmatch(r"shared-gate-up-m8-counters-[0-9]{8}T[0-9]{6}Z", root.name)
        is not None,
        "refusing to seal an error outside the packet-authorized campaign",
    )
    if analysis_path.exists():
        try:
            existing = read_canonical(analysis_path, "existing analysis")
        except RuntimeError:
            existing = {}
        if (
            existing.get("format") == "laguna-shared-gate-up-m8-counter-analysis-v2"
            and existing.get("campaign_root") == str(root)
            and existing.get("authorization_sha256") == packet_sha
        ):
            return
    if (
        (root / "campaign.complete.json").is_file()
        and not error_path.exists()
        and not error_path.is_symlink()
    ):
        observed_analysis = None
        if analysis_path.exists() or analysis_path.is_symlink():
            observed_analysis = {
                "path": str(analysis_path),
                "regular_file": analysis_path.is_file(),
                "symlink": analysis_path.is_symlink(),
                "sha256": (
                    sha(analysis_path)
                    if analysis_path.is_file() and not analysis_path.is_symlink()
                    else None
                ),
                "bytes": (
                    analysis_path.stat().st_size
                    if analysis_path.is_file() and not analysis_path.is_symlink()
                    else None
                ),
            }
        durable_exclusive_json(
            error_path,
            {
                "format": "laguna-shared-gate-up-m8-counter-analysis-error-v1",
                "status": "counter-failed-stop-before-endpoint",
                "campaign_root": str(root),
                "authorization_path": packet["packet_path"],
                "authorization_sha256": packet_sha,
                "error": repr(error),
                "observed_analysis": observed_analysis,
                "counter_gate_evaluated": False,
                "endpoint_authorized": False,
                "model_generation_performed": False,
                "network_access_performed": False,
                "payload_created": False,
                "submission_performed": False,
            },
        )


def maybe_seal_finalization_error(
    root: Path,
    packet: dict[str, Any],
    packet_sha: str,
    error: BaseException,
) -> None:
    error_path = root / "finalization.error.json"
    analysis_path = root / ANALYSIS_NAME
    final_path = root / FINAL_NAME
    require(
        root.parent == contract.RUNS
        and root == Path(packet["campaign"]["root"])
        and root.is_dir()
        and not root.is_symlink()
        and re.fullmatch(r"shared-gate-up-m8-counters-[0-9]{8}T[0-9]{6}Z", root.name)
        is not None,
        "refusing to seal an error outside the packet-authorized campaign",
    )
    if not analysis_path.is_file() or analysis_path.is_symlink():
        return
    if final_path.exists():
        try:
            existing = read_canonical(final_path, "existing final manifest")
        except RuntimeError:
            existing = {}
        if (
            existing.get("format")
            == "laguna-shared-gate-up-m8-counter-final-manifest-v2"
            and existing.get("campaign_root") == str(root)
            and existing.get("authorization_sha256") == packet_sha
        ):
            return
    if not error_path.exists() and not error_path.is_symlink():
        observed = {}
        for name in (TERMINAL_NAME, FINAL_NAME):
            path = root / name
            if path.exists() or path.is_symlink():
                observed[name] = {
                    "path": str(path),
                    "regular_file": path.is_file(),
                    "symlink": path.is_symlink(),
                    "sha256": (
                        sha(path) if path.is_file() and not path.is_symlink() else None
                    ),
                    "bytes": (
                        path.stat().st_size
                        if path.is_file() and not path.is_symlink()
                        else None
                    ),
                }
        durable_exclusive_json(
            error_path,
            {
                "format": "laguna-shared-gate-up-m8-counter-finalization-error-v1",
                "status": "counter-failed-stop-before-endpoint",
                "campaign_root": str(root),
                "authorization_path": packet["packet_path"],
                "authorization_sha256": packet_sha,
                "analysis_sha256": sha(analysis_path),
                "error": repr(error),
                "observed_terminal_or_final": observed,
                "counter_gate_evaluated": False,
                "endpoint_authorized": False,
                "model_generation_performed": False,
                "network_access_performed": False,
                "payload_created": False,
                "submission_performed": False,
            },
        )


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group(required=True)
    mode.add_argument("--analyze", action="store_true")
    mode.add_argument("--finalize", action="store_true")
    mode.add_argument("--verify-final", action="store_true")
    cli.add_argument("--campaign-root", type=Path, required=True)
    cli.add_argument("--authorization-json", type=Path, required=True)
    cli.add_argument(
        "--expected-authorization-sha256",
        type=runner.sha_argument,
        required=True,
    )
    args = cli.parse_args()
    root: Path | None = None
    packet: dict[str, Any] | None = None
    packet_sha: str | None = None
    try:
        root = args.campaign_root.resolve(strict=True)
        packet, packet_sha = validate_packet(
            args.authorization_json,
            args.expected_authorization_sha256,
            root,
        )
        if args.analyze:
            perform_analysis(root, packet, packet_sha)
        elif args.finalize:
            perform_finalize(root, packet, packet_sha)
        else:
            verify_final(root, packet, packet_sha)
        return 0
    except Exception as error:
        sealing_error: BaseException | None = None
        try:
            if args.analyze and root is not None and packet is not None and packet_sha:
                maybe_seal_analysis_error(
                    root,
                    packet,
                    packet_sha,
                    error,
                )
            elif (
                args.finalize and root is not None and packet is not None and packet_sha
            ):
                maybe_seal_finalization_error(root, packet, packet_sha, error)
        except BaseException as secondary:
            sealing_error = secondary
        print(f"FAIL-CLOSED: {error}", file=sys.stderr)
        if sealing_error is not None:
            print(f"FAIL-CLOSED ERROR-SEAL FAILURE: {sealing_error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

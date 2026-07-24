#!/usr/bin/env python3
"""One-shot coordinator for the frozen four-card shared-gate component gate.

It is stdlib-only.  Before it can create the campaign root it binds the full
four-card ``xpu-smi discovery -j`` view and each packet-exact one-card view.
Only that complete, bounded preflight may acquire the one campaign root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gate_laguna_shared_gate_mm_component as contract


XPU_SMI = "/usr/bin/xpu-smi"
DISCOVERY_ARGV = [XPU_SMI, "discovery", "-j"]
DISCOVERY_TIMEOUT_SECONDS = 20
PREFLIGHT_FORMAT = "laguna-shared-gate-m8-component-device-preflight-v1"


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        count = os.write(fd, view)
        require(count > 0, "short write while sealing campaign evidence")
        view = view[count:]


def _directory_fd(path: Path) -> int:
    """Open one existing directory without following its final path component."""
    require(hasattr(os, "O_NOFOLLOW"), "platform lacks O_NOFOLLOW")
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        require(stat.S_ISDIR(os.fstat(fd).st_mode), "unsafe non-directory path")
    except BaseException:
        os.close(fd)
        raise
    return fd


def _exclusive_json_at(directory: int, name: str, value: dict[str, Any]) -> None:
    require(name not in {"", ".", ".."} and "/" not in name, "unsafe evidence filename")
    fd = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o644,
        dir_fd=directory,
    )
    try:
        write_all(fd, contract.canonical(value) + b"\n")
        os.fsync(fd)
    finally:
        os.close(fd)
    os.fsync(directory)


def exclusive_json(path: Path, value: dict[str, Any]) -> None:
    require(
        path.name not in {"", ".", ".."} and path.parent / path.name == path,
        "unsafe evidence filename",
    )
    directory = _directory_fd(path.parent)
    try:
        _exclusive_json_at(directory, path.name, value)
    finally:
        os.close(directory)


def _packet_mapping(packet: dict[str, Any]) -> list[dict[str, Any]]:
    cards = packet.get("cards")
    require(
        isinstance(cards, list) and len(cards) == 4, "packet lacks exactly four cards"
    )
    expected: list[dict[str, Any]] = []
    for rank, card in enumerate(cards):
        require(
            isinstance(card, dict) and card.get("rank") == rank,
            "packet card rank order drift",
        )
        physical = card.get("physical")
        require(
            physical == contract.CARDS[rank],
            f"packet physical mapping drift for rank {rank}",
        )
        expected.append({"rank": rank, **physical})
    return expected


def _discovery_mapping(
    payload: object, *, expected_count: int, context: str
) -> list[dict[str, Any]]:
    require(isinstance(payload, dict), f"{context} discovery is not an object")
    devices = payload.get("device_list")
    require(
        isinstance(devices, list) and len(devices) == expected_count,
        f"{context} discovery device count drift",
    )
    mapping: list[dict[str, Any]] = []
    for device in devices:
        require(isinstance(device, dict), f"{context} discovery device is malformed")
        logical = device.get("device_id")
        require(
            type(logical) is int, f"{context} discovery logical device id is malformed"
        )
        mapping.append(
            {
                "logical_device_id": logical,
                "uuid": device.get("uuid"),
                "pci_bdf_address": device.get("pci_bdf_address"),
                "drm_device": device.get("drm_device"),
            }
        )
    return mapping


def _run_discovery(env: dict[str, str], context: str) -> tuple[str, object]:
    try:
        completed = subprocess.run(
            DISCOVERY_ARGV,
            env=env,
            cwd=str(contract.MAIN),
            check=False,
            capture_output=True,
            text=True,
            timeout=DISCOVERY_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"{context} xpu-smi discovery timed out after {DISCOVERY_TIMEOUT_SECONDS}s"
        ) from error
    except OSError as error:
        raise RuntimeError(f"{context} xpu-smi discovery could not start") from error
    require(
        completed.returncode == 0,
        f"{context} xpu-smi discovery failed with exit {completed.returncode}",
    )
    require(
        isinstance(completed.stdout, str),
        f"{context} xpu-smi discovery stdout is not text",
    )
    try:
        return completed.stdout, json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"{context} xpu-smi discovery returned invalid JSON"
        ) from error


def _probe_evidence(stdout: str, mapping: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "stdout": stdout,
        "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
        "parsed_mapping": mapping,
    }


def _expected_unfiltered_mapping(
    expected: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "logical_device_id": entry["logical_device_id"],
            "uuid": entry["uuid"],
            "pci_bdf_address": entry["pci_bdf_address"],
            "drm_device": entry["drm_device"],
        }
        for entry in expected
    ]


def _expected_filtered_mapping(entry: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "logical_device_id": 0,
            "uuid": entry["uuid"],
            "pci_bdf_address": entry["pci_bdf_address"],
            "drm_device": entry["drm_device"],
        }
    ]


def _validate_probe_evidence(
    probe: object,
    *,
    environment: dict[str, str],
    expected_mapping: list[dict[str, Any]],
    context: str,
) -> None:
    require(
        isinstance(probe, dict)
        and set(probe) == {"environment", "stdout", "stdout_sha256", "parsed_mapping"},
        f"{context} preflight schema drift",
    )
    require(
        probe["environment"] == environment, f"{context} preflight environment drift"
    )
    stdout = probe["stdout"]
    require(isinstance(stdout, str), f"{context} preflight stdout is malformed")
    require(
        probe["stdout_sha256"] == hashlib.sha256(stdout.encode()).hexdigest(),
        f"{context} preflight stdout hash drift",
    )
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{context} preflight stdout is not JSON") from error
    mapping = _discovery_mapping(
        payload, expected_count=len(expected_mapping), context=f"{context} preflight"
    )
    require(
        probe["parsed_mapping"] == mapping,
        f"{context} preflight parsed mapping does not match stdout",
    )
    require(mapping == expected_mapping, f"{context} preflight exact mapping drift")


def validate_device_preflight(preflight: object, packet: dict[str, Any]) -> None:
    """Validate saved preflight evidence against packet mappings, not itself.

    Analyzer/finalizer code can call this with the decoded campaign-start
    record's ``device_preflight`` value.  It re-parses every saved stdout and
    binds it to the immutable packet mapping and exact environments.
    """
    expected = _packet_mapping(packet)
    require(
        isinstance(preflight, dict)
        and set(preflight)
        == {"format", "command", "packet_mapping", "unfiltered", "filtered"},
        "device preflight schema drift",
    )
    require(preflight["format"] == PREFLIGHT_FORMAT, "device preflight format drift")
    require(
        preflight["command"]
        == {"argv": DISCOVERY_ARGV, "timeout_seconds": DISCOVERY_TIMEOUT_SECONDS},
        "device preflight command identity drift",
    )
    require(
        preflight["packet_mapping"] == expected, "device preflight packet mapping drift"
    )
    coordinator_environment = packet.get("coordinator_environment")
    require(
        isinstance(coordinator_environment, dict),
        "packet coordinator environment is malformed",
    )
    unfiltered_environment = dict(coordinator_environment)
    unfiltered_environment.pop("ONEAPI_DEVICE_SELECTOR", None)
    unfiltered_environment.pop("ZE_AFFINITY_MASK", None)
    _validate_probe_evidence(
        preflight["unfiltered"],
        environment=unfiltered_environment,
        expected_mapping=_expected_unfiltered_mapping(expected),
        context="unfiltered",
    )
    filtered = preflight["filtered"]
    require(
        isinstance(filtered, list) and len(filtered) == 4,
        "filtered preflight count drift",
    )
    for expected_entry, card, probe in zip(
        expected, packet["cards"], filtered, strict=True
    ):
        rank = expected_entry["rank"]
        require(
            isinstance(probe, dict) and probe.get("rank") == rank,
            f"filtered preflight rank drift for {rank}",
        )
        environment = card.get("environment")
        require(
            environment == contract.environment(card.get("output_root"), rank),
            f"packet exact environment drift for rank {rank}",
        )
        probe_evidence = dict(probe)
        probe_evidence.pop("rank", None)
        _validate_probe_evidence(
            probe_evidence,
            environment=environment,
            expected_mapping=_expected_filtered_mapping(expected_entry),
            context=f"rank {rank} filtered",
        )


def device_preflight(packet: dict[str, Any]) -> dict[str, Any]:
    """Return durable evidence after binding every required physical/filtered view.

    This function intentionally creates no files.  A caller which receives an
    exception therefore has not acquired a campaign root.
    """
    expected = _packet_mapping(packet)
    coordinator_environment = packet.get("coordinator_environment")
    require(
        isinstance(coordinator_environment, dict),
        "packet coordinator environment is malformed",
    )
    unfiltered_environment = dict(coordinator_environment)
    unfiltered_environment.pop("ONEAPI_DEVICE_SELECTOR", None)
    unfiltered_environment.pop("ZE_AFFINITY_MASK", None)

    unfiltered_stdout, unfiltered_payload = _run_discovery(
        unfiltered_environment, "unfiltered"
    )
    unfiltered_mapping = _discovery_mapping(
        unfiltered_payload, expected_count=4, context="unfiltered"
    )
    expected_unfiltered = _expected_unfiltered_mapping(expected)
    require(
        sorted(unfiltered_mapping, key=lambda entry: entry["logical_device_id"])
        == expected_unfiltered,
        "unfiltered xpu-smi exact four-card mapping drift",
    )

    filtered: list[dict[str, Any]] = []
    for expected_entry, card in zip(expected, packet["cards"], strict=True):
        rank = expected_entry["rank"]
        environment = card.get("environment")
        require(
            environment == contract.environment(card.get("output_root"), rank),
            f"packet exact environment drift for rank {rank}",
        )
        stdout, payload = _run_discovery(environment, f"rank {rank} filtered")
        mapping = _discovery_mapping(
            payload, expected_count=1, context=f"rank {rank} filtered"
        )
        expected_filtered = _expected_filtered_mapping(expected_entry)
        require(
            mapping == expected_filtered, f"rank {rank} filtered xpu-smi mapping drift"
        )
        filtered.append(
            {
                "rank": rank,
                "environment": environment,
                **_probe_evidence(stdout, mapping),
            }
        )
    preflight = {
        "format": PREFLIGHT_FORMAT,
        "command": {
            "argv": DISCOVERY_ARGV,
            "timeout_seconds": DISCOVERY_TIMEOUT_SECONDS,
        },
        "packet_mapping": expected,
        "unfiltered": {
            "environment": unfiltered_environment,
            **_probe_evidence(unfiltered_stdout, unfiltered_mapping),
        },
        "filtered": filtered,
    }
    validate_device_preflight(preflight, packet)
    return preflight


def acquire_campaign_root(
    root: Path, packet: dict[str, Any], preflight: dict[str, Any]
) -> None:
    require(not root.exists() and not root.is_symlink(), "campaign root is not fresh")
    parent = root.parent
    require(
        parent.exists() and parent.is_dir() and not parent.is_symlink(),
        "campaign parent is absent or unsafe",
    )
    validate_device_preflight(preflight, packet)
    parent_fd = _directory_fd(parent)
    try:
        os.mkdir(root.name, 0o755, dir_fd=parent_fd)
        root_fd = os.open(
            root.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd
        )
        try:
            os.fsync(root_fd)
            os.fsync(parent_fd)
            _exclusive_json_at(
                root_fd,
                "campaign-start-checkpoint.json",
                {
                    "format": "laguna-shared-gate-m8-component-campaign-start-v1",
                    "status": "campaign_root_acquired_before_rank_execution",
                    "created_utc": utc(),
                    "packet_path": packet["packet_path"],
                    "packet_sha256": contract.sha(Path(packet["packet_path"])),
                    "rank_order": [0, 1, 2, 3],
                    "device_preflight": preflight,
                    "downstream": contract.FALSE_ACTIONS,
                },
            )
        finally:
            os.close(root_fd)
    finally:
        os.close(parent_fd)


def preflight_and_acquire_campaign_root(root: Path, packet: dict[str, Any]) -> None:
    """The only acquisition path: all live probes complete before mkdir."""
    failure_path = Path(packet["preflight_failure_path"])
    require(
        root.parent.is_dir()
        and not root.parent.is_symlink()
        and failure_path.parent == root.parent,
        "campaign/preflight-failure parent is absent or unsafe",
    )
    require(
        failure_path == root.parent / f"{root.name}-preflight-failure.json",
        "preflight failure path drift",
    )
    require(
        not root.exists()
        and not root.is_symlink()
        and not failure_path.exists()
        and not failure_path.is_symlink(),
        "campaign/preflight-failure paths are not fresh",
    )
    try:
        preflight = device_preflight(packet)
    except BaseException as error:
        exclusive_json(
            failure_path,
            {
                "format": "laguna-shared-gate-m8-component-device-preflight-failure-v1",
                "status": "component_failed_stop_before_counters",
                "created_utc": utc(),
                "packet_path": packet["packet_path"],
                "packet_sha256": contract.sha(Path(packet["packet_path"])),
                "campaign_root": str(root),
                "tensor_work_started": False,
                "failure": {
                    "phase": "pre_root_device_discovery",
                    "error_type": type(error).__name__,
                    "message": str(error),
                },
                "downstream": contract.FALSE_ACTIONS,
            },
        )
        raise
    acquire_campaign_root(root, packet, preflight)


def terminal(root: Path, name: str, value: dict[str, Any]) -> None:
    exclusive_json(root / name, value)


def _expected_argv(packet: dict[str, Any], args: argparse.Namespace) -> list[str]:
    return [
        str(contract.PYTHON),
        str(contract.MAIN / contract.TOOLS["coordinator"]),
        "--authorization",
        str(args.authorization),
        "--fixture",
        str(args.fixture),
        "--stage0-result",
        str(args.stage0_result),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--stage0-result", type=Path, required=True)
    args = parser.parse_args()
    authorization = args.authorization.resolve(strict=True)
    packet = json.loads(authorization.read_text())
    require(
        args.authorization == authorization and not authorization.is_symlink(),
        "authorization path aliases/symlinks are forbidden",
    )
    require(
        args.fixture == Path(packet["stage0"]["fixture_path"])
        and args.stage0_result == Path(packet["stage0"]["result_path"]),
        "coordinator argv evidence paths drift",
    )
    require(
        sys.argv == packet["coordinator_argv"][1:],
        "coordinator argv differs from frozen packet",
    )
    require(
        _expected_argv(packet, args) == packet["coordinator_argv"],
        "coordinator executable argv drift",
    )
    require(
        dict(os.environ) == packet["coordinator_environment"],
        "coordinator process environment differs from frozen env",
    )
    # All packet/Git/source/runtime/card checks and all five live discovery
    # probes happen before the campaign root exists or any child can start.
    contract.validate_execution_packet(packet, authorization)
    root = Path(packet["campaign_root"])
    preflight_and_acquire_campaign_root(root, packet)
    for card in packet["cards"]:
        rank = card["rank"]
        completed = subprocess.run(
            card["runner_argv"],
            env=card["environment"],
            cwd=str(contract.MAIN),
            check=False,
        )
        result_path = Path(card["result"])
        result_present = result_path.is_file() and not result_path.is_symlink()
        leg_valid = completed.returncode == 0 and result_present
        entry = {
            "format": "laguna-shared-gate-m8-component-leg-terminal-v1",
            "rank": rank,
            "completed_utc": utc(),
            "argv": card["runner_argv"],
            "environment": card["environment"],
            "exit_code": completed.returncode,
            "result_path": card["result"],
            "result_present": result_present,
            "result_sha256": contract.sha(result_path) if result_present else None,
            "status": "rank_zero_exit"
            if leg_valid
            else "rank_nonzero_or_invalid_result_stop",
            "downstream": contract.FALSE_ACTIONS,
        }
        terminal(root, f"rank-{rank}-terminal.json", entry)
        if not leg_valid:
            terminal(
                root,
                "campaign-terminal.json",
                {
                    "format": "laguna-shared-gate-m8-component-campaign-terminal-v1",
                    "status": "campaign_failed_stop_before_analyzer",
                    "completed_utc": utc(),
                    "failed_rank": rank,
                    "analyzer_invoked": False,
                    "downstream": contract.FALSE_ACTIONS,
                },
            )
            return 1
    analyzer = subprocess.run(
        packet["analyzer_argv"],
        env=packet["coordinator_environment"],
        cwd=str(contract.MAIN),
        check=False,
    )
    aggregate_path = Path(packet["aggregate_path"])
    rank_result_sha256 = {
        str(card["rank"]): contract.sha(Path(card["result"]))
        for card in packet["cards"]
    }
    terminal(
        root,
        "campaign-terminal.json",
        {
            "format": "laguna-shared-gate-m8-component-campaign-terminal-v1",
            "status": "component_aggregate_pending_final_seal"
            if analyzer.returncode == 0
            else "component_analyzer_failed_stop",
            "completed_utc": utc(),
            "failed_rank": None,
            "analyzer_invoked": True,
            "analyzer_argv": packet["analyzer_argv"],
            "analyzer_exit_code": analyzer.returncode,
            "packet_sha256": contract.sha(authorization),
            "aggregate_path": str(aggregate_path),
            "aggregate_sha256": contract.sha(aggregate_path)
            if analyzer.returncode == 0 and aggregate_path.is_file()
            else None,
            "rank_result_sha256": rank_result_sha256,
            "downstream": contract.FALSE_ACTIONS,
        },
    )
    if analyzer.returncode != 0:
        return 1
    finalizer = subprocess.run(
        packet["finalizer_argv"],
        env=packet["coordinator_environment"],
        cwd=str(contract.MAIN),
        check=False,
    )
    if finalizer.returncode != 0:
        return 1
    verifier = subprocess.run(
        packet["final_verifier_argv"],
        env=packet["coordinator_environment"],
        cwd=str(contract.MAIN),
        check=False,
    )
    return 0 if verifier.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

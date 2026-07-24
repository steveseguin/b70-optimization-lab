#!/usr/bin/env python3
"""Sequential coordinator for Laguna gather/finalize Phase-A evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import signal
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gate_laguna_m8_gather_finalize_component as contract

XPU_SMI = "/usr/bin/xpu-smi"
DISCOVERY_ARGV = [XPU_SMI, "discovery", "-j"]
PS_ARGV = [XPU_SMI, "ps", "-j"]
PROBE_TIMEOUT_SECONDS = 20
IDLE_SAMPLE_INTERVAL_SECONDS = 1.5


def require(ok: bool, why: str) -> None:
    if not ok:
        raise RuntimeError(why)


def utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _directory_fd(path: Path) -> int:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    require(stat.S_ISDIR(os.fstat(descriptor).st_mode), "unsafe directory")
    return descriptor


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        require(written > 0, "short evidence write")
        view = view[written:]


def _write_bytes(directory: int, name: str, payload: bytes) -> None:
    descriptor = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o644,
        dir_fd=directory,
    )
    try:
        _write_all(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.fsync(directory)


def _write_json(directory: int, name: str, value: dict[str, Any]) -> None:
    _write_bytes(directory, name, contract.canonical(value) + b"\n")


def exclusive_json(path: Path, value: dict[str, Any]) -> None:
    descriptor = _directory_fd(path.parent)
    try:
        _write_json(descriptor, path.name, value)
    finally:
        os.close(descriptor)


def exclusive_bytes(path: Path, payload: bytes) -> None:
    descriptor = _directory_fd(path.parent)
    try:
        _write_bytes(descriptor, path.name, payload)
    finally:
        os.close(descriptor)


def _mapping(payload: object, count: int) -> list[dict[str, Any]]:
    require(
        isinstance(payload, dict)
        and isinstance(payload.get("device_list"), list)
        and len(payload["device_list"]) == count,
        "discovery schema/count drift",
    )
    result = []
    for item in payload["device_list"]:
        require(
            isinstance(item, dict) and type(item.get("device_id")) is int,
            "malformed device identity",
        )
        result.append(
            {
                "logical_device_id": item["device_id"],
                "uuid": item.get("uuid"),
                "pci_bdf_address": item.get("pci_bdf_address"),
                "drm_device": item.get("drm_device"),
            }
        )
    return result


def _run_probe(argv: list[str], env: dict[str, str], label: str) -> str:
    try:
        completed = subprocess.run(
            argv,
            cwd=str(contract.MAIN),
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f"{label} unavailable") from error
    require(completed.returncode == 0, f"{label} exit {completed.returncode}")
    return completed.stdout


def _discovery(env: dict[str, str], count: int) -> tuple[str, list[dict[str, Any]]]:
    stdout = _run_probe(DISCOVERY_ARGV, env, "discovery")
    try:
        return stdout, _mapping(json.loads(stdout), count)
    except json.JSONDecodeError as error:
        raise RuntimeError("discovery non-JSON") from error


def _idle_snapshot(env: dict[str, str], phase: str) -> dict[str, Any]:
    stdout = _run_probe(PS_ARGV, env, "xpu-smi ps")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("xpu-smi ps non-JSON") from error
    require(
        isinstance(payload, dict)
        and set(payload) == {"process_list"}
        and payload["process_list"] == [],
        "selected XPU is not idle",
    )
    return {
        "phase": phase,
        "observed_utc": utc(),
        "argv": PS_ARGV,
        "stdout": stdout,
        "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
        "parsed": payload,
        "idle": True,
    }


def _strict_idle(env: dict[str, str]) -> dict[str, Any]:
    required_seconds = contract.PROTOCOL["strict_idle_seconds"]
    minimum_samples = contract.PROTOCOL["strict_idle_minimum_samples"]
    started_utc = utc()
    started = time.monotonic()
    samples: list[dict[str, Any]] = []
    while True:
        samples.append(_idle_snapshot(env, f"strict_idle_{len(samples)}"))
        elapsed = time.monotonic() - started
        if elapsed >= required_seconds and len(samples) >= minimum_samples:
            break
        time.sleep(IDLE_SAMPLE_INTERVAL_SECONDS)
    return {
        "environment": env,
        "started_utc": started_utc,
        "completed_utc": utc(),
        "elapsed_seconds": time.monotonic() - started,
        "required_seconds": required_seconds,
        "minimum_samples": minimum_samples,
        "sample_count": len(samples),
        "samples": samples,
        "passed": True,
    }


def device_preflight(packet: dict[str, Any]) -> dict[str, Any]:
    """Issue exactly five discovery probes: one unfiltered and four filtered."""
    expected = [{"rank": rank, **contract.CARDS[rank]} for rank in range(4)]
    unfiltered = dict(packet["coordinator_environment"])
    unfiltered.pop("ONEAPI_DEVICE_SELECTOR")
    unfiltered.pop("ZE_AFFINITY_MASK")
    stdout, found = _discovery(unfiltered, 4)
    target = [
        {
            key: card[key]
            for key in (
                "logical_device_id",
                "uuid",
                "pci_bdf_address",
                "drm_device",
            )
        }
        for card in expected
    ]
    require(
        sorted(found, key=lambda item: item["logical_device_id"]) == target,
        "unfiltered map drift",
    )
    filtered = []
    for card, expected_card in zip(packet["cards"], expected, strict=True):
        card_stdout, card_found = _discovery(card["environment"], 1)
        one = {
            "logical_device_id": 0,
            **{
                key: expected_card[key]
                for key in ("uuid", "pci_bdf_address", "drm_device")
            },
        }
        require(card_found == [one], f"rank {expected_card['rank']} map drift")
        filtered.append(
            {
                "rank": expected_card["rank"],
                "environment": card["environment"],
                "stdout": card_stdout,
                "stdout_sha256": hashlib.sha256(card_stdout.encode()).hexdigest(),
                "parsed_mapping": card_found,
            }
        )
    return {
        "format": "laguna-m8-gather-finalize-five-discovery-preflight-v3",
        "discovery_count": 5,
        "command": {
            "argv": DISCOVERY_ARGV,
            "timeout_seconds": PROBE_TIMEOUT_SECONDS,
        },
        "packet_mapping": expected,
        "unfiltered": {
            "environment": unfiltered,
            "stdout": stdout,
            "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
            "parsed_mapping": found,
        },
        "filtered": filtered,
    }


def _mkdir_at(parent: int, name: str) -> int:
    require(name not in {"", ".", ".."} and "/" not in name, "unsafe directory name")
    os.mkdir(name, 0o700, dir_fd=parent)
    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    try:
        require(
            stat.S_ISDIR(os.fstat(child).st_mode), "created path is not a directory"
        )
        return child
    except BaseException:
        os.close(child)
        raise


def _runtime_dirs(runtime_root: Path) -> None:
    require(
        runtime_root.is_absolute()
        and not runtime_root.exists()
        and not runtime_root.is_symlink()
        and runtime_root.parent.is_dir()
        and not runtime_root.parent.is_symlink(),
        "runtime root is not fresh or safe",
    )
    parent = _directory_fd(runtime_root.parent)
    try:
        root = _mkdir_at(parent, runtime_root.name)
        try:
            for name in ("home", "tmp"):
                child = _mkdir_at(root, name)
                os.close(child)
            cache = _mkdir_at(root, "cache")
            try:
                for name in (
                    "xdg",
                    "xdg-config",
                    "xdg-data",
                    "xdg-state",
                    "huggingface",
                    "transformers",
                    "vllm",
                    "triton",
                    "numba",
                    "pycache",
                    "sycl",
                    "torchinductor",
                ):
                    child = _mkdir_at(cache, name)
                    os.close(child)
                os.fsync(cache)
            finally:
                os.close(cache)
            os.fsync(root)
        finally:
            os.close(root)
        os.fsync(parent)
    finally:
        os.close(parent)


def _acquire(
    root: Path,
    packet: dict[str, Any],
    preflight: dict[str, Any],
    idle: dict[str, Any],
) -> None:
    parent_fd = _directory_fd(root.parent)
    try:
        os.mkdir(root.name, 0o755, dir_fd=parent_fd)
        root_fd = os.open(
            root.name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        try:
            _write_json(
                root_fd,
                "campaign-start-checkpoint.json",
                {
                    "format": "laguna-m8-gather-finalize-component-start-v3",
                    "status": contract.PHASE,
                    "counter_phase_required": True,
                    "packet_path": packet["packet_path"],
                    "packet_sha256": contract.sha(Path(packet["packet_path"])),
                    "rank_order": [0, 1, 2, 3],
                    "device_preflight": preflight,
                    "strict_idle": idle,
                    "downstream": contract.FALSE_ACTIONS,
                },
            )
        finally:
            os.close(root_fd)
    finally:
        os.close(parent_fd)


def _capture_process(
    argv: list[str],
    env: dict[str, str],
    timeout_seconds: int,
) -> dict[str, Any]:
    started_utc = utc()
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            argv,
            cwd=str(contract.MAIN),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as error:
        return {
            "started_utc": started_utc,
            "completed_utc": utc(),
            "elapsed_seconds": time.monotonic() - started,
            "exit_code": None,
            "timed_out": False,
            "launch_error": f"{type(error).__name__}: {error}",
            "stdout": b"",
            "stderr": b"",
        }
    timed_out = False

    def terminate_and_reap() -> tuple[bytes, bytes]:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            return process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                return process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                try:
                    return process.communicate(timeout=5)
                except subprocess.TimeoutExpired as final_error:
                    raise RuntimeError(
                        "unable to reap component process group"
                    ) from final_error

    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        stdout, stderr = terminate_and_reap()
    except BaseException:
        terminate_and_reap()
        raise
    return {
        "started_utc": started_utc,
        "completed_utc": utc(),
        "elapsed_seconds": time.monotonic() - started,
        "exit_code": 124 if timed_out else process.returncode,
        "timed_out": timed_out,
        "launch_error": None,
        "stdout": stdout,
        "stderr": stderr,
    }


def _capture_summary(capture: dict[str, Any]) -> dict[str, Any]:
    return {
        key: capture[key]
        for key in (
            "started_utc",
            "completed_utc",
            "elapsed_seconds",
            "exit_code",
            "timed_out",
            "launch_error",
        )
    } | {
        "stdout_sha256": hashlib.sha256(capture["stdout"]).hexdigest(),
        "stderr_sha256": hashlib.sha256(capture["stderr"]).hexdigest(),
    }


def _save_capture(root: Path, prefix: str, capture: dict[str, Any]) -> None:
    exclusive_bytes(root / f"{prefix}.stdout", capture["stdout"])
    exclusive_bytes(root / f"{prefix}.stderr", capture["stderr"])


def _phase_a_aggregate_valid(packet: dict[str, Any], path: Path) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
        if raw != contract.canonical(value) + b"\n":
            return False
    except (OSError, TypeError, ValueError):
        return False
    expected_keys = {
        "format",
        "status",
        "timing_exactness_passed",
        "counter_phase_required",
        "counter_phase_complete",
        "full_component_pass",
        "endpoint_authorized",
        "packet_sha256",
        "fixture_manifest",
        "cards",
        "downstream",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        return False
    if not (
        value["format"]
        == "laguna-m8-gather-finalize-four-card-timing-exactness-aggregate-v2"
        and value["status"] == "component_timing_pass_pending_mandatory_counters"
        and value["timing_exactness_passed"] is True
        and value["counter_phase_required"] is True
        and value["counter_phase_complete"] is False
        and value["full_component_pass"] is False
        and value["endpoint_authorized"] is False
        and value["packet_sha256"] == contract.sha(Path(packet["packet_path"]))
        and value["fixture_manifest"]
        == {
            "path": packet["fixture"]["path"],
            "sha256": packet["fixture"]["sha256"],
            "corpus_version": contract.FIXTURE_CORPUS_VERSION,
        }
        and value["downstream"] == contract.FALSE_ACTIONS
        and isinstance(value["cards"], list)
        and len(value["cards"]) == len(packet["cards"]) == 4
    ):
        return False
    card_keys = {
        "rank",
        "physical",
        "result_path",
        "result_sha256",
        "fixture_manifest_sha256",
        "fixture_count",
        "pre_epoch_sequence_sha256",
        "timing",
    }
    for rank, (summary, expected) in enumerate(
        zip(value["cards"], packet["cards"], strict=True)
    ):
        if not isinstance(summary, dict) or set(summary) != card_keys:
            return False
        result = Path(expected["result"])
        timing = summary["timing"]
        if not (
            summary["rank"] == rank == expected["rank"]
            and summary["physical"] == expected["physical"]
            and summary["result_path"] == str(result)
            and result.is_file()
            and not result.is_symlink()
            and summary["result_sha256"] == contract.sha(result)
            and summary["fixture_manifest_sha256"] == packet["fixture"]["sha256"]
            and summary["fixture_count"] == 305
            and isinstance(summary["pre_epoch_sequence_sha256"], str)
            and len(summary["pre_epoch_sequence_sha256"]) == 64
            and all(
                char in "0123456789abcdef"
                for char in summary["pre_epoch_sequence_sha256"]
            )
            and isinstance(timing, dict)
            and set(timing)
            == {
                "candidate_block_wins",
                "median_saving_ms_per_47_layer_cycle",
            }
            and type(timing["candidate_block_wins"]) is int
            and timing["candidate_block_wins"] >= packet["protocol"]["minimum_wins"]
            and timing["candidate_block_wins"] <= packet["protocol"]["abba_blocks"]
            and isinstance(timing["median_saving_ms_per_47_layer_cycle"], (int, float))
            and not isinstance(timing["median_saving_ms_per_47_layer_cycle"], bool)
            and math.isfinite(float(timing["median_saving_ms_per_47_layer_cycle"]))
            and timing["median_saving_ms_per_47_layer_cycle"]
            >= packet["protocol"]["minimum_median_saving_ms_per_47_layer_cycle"]
        ):
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    args = parser.parse_args()

    authorization = args.authorization.resolve(strict=True)
    require(
        args.authorization == authorization and not authorization.is_symlink(),
        "authorization aliases forbidden",
    )
    packet = json.loads(authorization.read_text())
    require(args.fixture == Path(packet["fixture"]["path"]), "fixture argv drift")
    require(
        sys.argv == packet["coordinator_argv"][1:]
        and dict(os.environ) == packet["coordinator_environment"],
        "coordinator argv/environment drift",
    )
    contract.validate_execution_packet(packet, authorization)
    contract.validate_fixture_manifest(args.fixture)

    root = Path(packet["campaign_root"])
    failure = Path(packet["preflight_failure_path"])
    require(
        not root.exists() and not failure.exists() and root.parent == failure.parent,
        "campaign paths not fresh",
    )
    try:
        preflight = device_preflight(packet)
        strict_idle_environment = dict(packet["coordinator_environment"])
        strict_idle_environment.pop("ONEAPI_DEVICE_SELECTOR")
        strict_idle_environment.pop("ZE_AFFINITY_MASK")
        idle = _strict_idle(strict_idle_environment)
    except BaseException as error:
        exclusive_json(
            failure,
            {
                "format": "laguna-m8-gather-finalize-preflight-failure-v3",
                "status": "component_failed_stop_before_runner",
                "counter_phase_required": True,
                "failure": {
                    "type": type(error).__name__,
                    "message": str(error),
                },
                "downstream": contract.FALSE_ACTIONS,
            },
        )
        raise

    _acquire(root, packet, preflight, idle)
    runner_timeout = packet["protocol"]["runner_timeout_seconds"]
    analyzer_timeout = packet["protocol"]["analyzer_timeout_seconds"]

    for card in packet["cards"]:
        rank = card["rank"]
        terminal = root / f"rank-{rank}-terminal.json"
        try:
            _runtime_dirs(Path(card["runtime_root"]))
            pre_idle = _idle_snapshot(card["environment"], f"before_rank_{rank}")
            capture = _capture_process(
                card["runner_argv"], card["environment"], runner_timeout
            )
            _save_capture(root, f"rank-{rank}-runner", capture)
            result = Path(card["result"])
            runner_valid = (
                capture["exit_code"] == 0
                and result.is_file()
                and not result.is_symlink()
            )
            post_idle = _idle_snapshot(card["environment"], f"after_rank_{rank}")
            validator_capture = None
            validator_valid = False
            if runner_valid:
                validator_capture = _capture_process(
                    card["validator_argv"],
                    packet["coordinator_environment"],
                    analyzer_timeout,
                )
                _save_capture(root, f"rank-{rank}-validator", validator_capture)
                validator_valid = validator_capture["exit_code"] == 0
            valid = runner_valid and validator_valid
            exclusive_json(
                terminal,
                {
                    "format": "laguna-m8-gather-finalize-leg-terminal-v3",
                    "rank": rank,
                    "status": (
                        "timing_exactness_validated_counter_phase_required"
                        if valid
                        else "rank_failed_stop"
                    ),
                    "counter_phase_required": True,
                    "pre_card_idle": pre_idle,
                    "post_card_idle": post_idle,
                    "runner": _capture_summary(capture),
                    "validator": (
                        _capture_summary(validator_capture)
                        if validator_capture is not None
                        else None
                    ),
                    "result_path": str(result),
                    "result_sha256": contract.sha(result) if runner_valid else None,
                    "downstream": contract.FALSE_ACTIONS,
                },
            )
            if not valid:
                return 1
        except BaseException as error:
            if not terminal.exists():
                exclusive_json(
                    terminal,
                    {
                        "format": "laguna-m8-gather-finalize-leg-terminal-v3",
                        "rank": rank,
                        "status": "rank_exception_failed_stop",
                        "counter_phase_required": True,
                        "failure": {
                            "type": type(error).__name__,
                            "message": str(error),
                        },
                        "downstream": contract.FALSE_ACTIONS,
                    },
                )
            return 1

    analyzer_capture = _capture_process(
        packet["analyzer_argv"],
        packet["coordinator_environment"],
        analyzer_timeout,
    )
    _save_capture(root, "four-card-analyzer", analyzer_capture)
    aggregate = Path(packet["aggregate_path"])
    analyzer_valid = analyzer_capture["exit_code"] == 0 and _phase_a_aggregate_valid(
        packet, aggregate
    )
    final_idle_environment = dict(packet["coordinator_environment"])
    final_idle_environment.pop("ONEAPI_DEVICE_SELECTOR")
    final_idle_environment.pop("ZE_AFFINITY_MASK")
    try:
        final_idle = _idle_snapshot(final_idle_environment, "after_four_card_phase_a")
    except BaseException as error:
        final_idle = {
            "phase": "after_four_card_phase_a",
            "idle": False,
            "failure": {
                "type": type(error).__name__,
                "message": str(error),
            },
        }
        analyzer_valid = False
    exclusive_json(
        root / "campaign-terminal.json",
        {
            "format": "laguna-m8-gather-finalize-campaign-terminal-v3",
            "status": (
                "component_timing_pass_pending_mandatory_counters"
                if analyzer_valid
                else "four_card_analyzer_failed_stop"
            ),
            "timing_exactness_passed": analyzer_valid,
            "counter_phase_required": True,
            "counter_phase_complete": False,
            "full_component_pass": False,
            "endpoint_authorized": False,
            "analyzer": _capture_summary(analyzer_capture),
            "aggregate_path": str(aggregate),
            "aggregate_sha256": (contract.sha(aggregate) if analyzer_valid else None),
            "final_idle": final_idle,
            "downstream": contract.FALSE_ACTIONS,
        },
    )
    return 0 if analyzer_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())

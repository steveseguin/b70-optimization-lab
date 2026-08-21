#!/usr/bin/env python3
"""Bounded no-clock runtime-map diagnostic for the reference-host Q64 operator."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import re
import signal
import socket
import subprocess
import sys
import time
from typing import Any


HERE = Path(__file__).resolve().parent
CAMPAIGN_PATH = HERE / "qwen38_mtp5_m6_fa_q64k32_remote_clock_campaign.py"
DRIVER_PATH = HERE / "run-20260821-qwen38-q64k32-remote-runtime-map-diagnostic.sh"
PASSIVE_EVIDENCE = (
    HERE.parent / "data/2026-08-21-qwen38-q64k32-remote-passive-enablement.json"
)
PASSIVE_EVIDENCE_SHA256 = (
    "adef0e354f4bf0b6e6f2df6d0cc363fc34ee0d41f22fe9994f9214ae87373a79"
)
CAMPAIGN_SHA256 = "7577f9313b60d4bb51b328eb63608ab8c3bf9af31b1e84e1390164f71ee1e2fb"
REMOTE_REPO = Path("/home/steve/b70-optimization-lab")
REMOTE_PYTHON = Path("/home/steve/.venvs/vllm-xpu/bin/python")
RESULT_ROOT = Path(
    "/home/steve/qwen38-q64k32-remote-runtime-map-diagnostic-20260821-r2"
)
EXPECTED_BOOT_ID = "a6cad22f-2685-43b7-8950-c0c771f73d99"
EXPECTED_STAGE_INVENTORY_SHA256 = (
    "0923804d40a14a19ee244ce4e38641a47d9c4327b0d5c700c7b6e2756ce1aa82"
)
DIAGNOSTIC_AUTHORIZED = True
TIMEOUT_SECONDS = 300.0
GRACE_SECONDS = 10.0
KV_LENGTH = 128
EXPECTED_FIXTURE_SHA256 = (
    "0acb368f76405cfab88e47944437d0399bce0866fe9452096d3d5e0a2c9570cd"
)
EXPECTED_ORACLE_SHA256 = (
    "5a9759d1bf2b3eeea8eb4b34ba40e259d7e356285b28f0edcd36bda4a92e2a2e"
)

PLAN = (
    {"ordinal": 1, "device": 0, "role": "control"},
    {"ordinal": 2, "device": 0, "role": "candidate"},
    {"ordinal": 3, "device": 1, "role": "candidate"},
    {"ordinal": 4, "device": 1, "role": "control"},
)

STATIC_RUNTIME_CANDIDATES = {
    "libsycl.so.8.0.0": "0336997fdfed9b2e6385e9f1cea2395eb5e130d3e5e9c943df5b0c10c1b5e57f",
    "libur_adapter_level_zero.so.0.12.0": (
        "ceecac1cb3124f15b9a319d4bfc156eed49068467564b8210f2f0330aa0911e8"
    ),
    "libur_loader.so.0.12.0": (
        "68e273791752638dfad1ce3bb002b0ed8d00ceee21e491cd46dd0668d716bfa0"
    ),
    "libze_intel_gpu.so.1.15.38646": (
        "dff06fa9ab58a84767d4225eceb6c3225995552836b0e28b986d852a2e4e0180"
    ),
    "libze_loader.so.1.28.6": (
        "5c156f00718f80f7e75964fa729e811c7b486778478d2fc318cc77751e1a0bbd"
    ),
}
STATIC_RUNTIME_CANDIDATE_PATHS = {
    "libsycl.so.8.0.0": "/home/steve/.venvs/vllm-xpu/lib/libsycl.so.8.0.0",
    "libur_adapter_level_zero.so.0.12.0": (
        "/home/steve/.venvs/vllm-xpu/lib/libur_adapter_level_zero.so.0.12.0"
    ),
    "libur_loader.so.0.12.0": (
        "/home/steve/.venvs/vllm-xpu/lib/libur_loader.so.0.12.0"
    ),
    "libze_intel_gpu.so.1.15.38646": (
        "/usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1.15.38646"
    ),
    "libze_loader.so.1.28.6": "/usr/lib/x86_64-linux-gnu/libze_loader.so.1.28.6",
}
EXPECTED_DEVICES = {
    0: {
        "uuid": "00000000-0000-0003-0000-0000e2238086",
        "bdf": "0000:03:00.0",
    },
    1: {
        "uuid": "00000000-0000-00e3-0000-0000e2238086",
        "bdf": "0000:e3:00.0",
    },
}
XPU_SMI = Path("/usr/bin/xpu-smi")
XPU_SMI_SHA256 = "01c7b83881e99754642b827ba05418d263aed615933e3df35821af7733eb8d83"
PYTHON_RESOLVED = Path("/usr/bin/python3.12")
PYTHON_SHA256 = "1643dacd9feaedc58f3cc581e4d22577dfe25c09b10282936186ccf0f2e61118"
TORCH_VERSION = "2.11.0+xpu"
TORCH_FILES = {
    "/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/__init__.py": (
        "0387d8b811b289287479c8bfdf4e1dac3a71b246f938d82da1331cf2dc8bf001"
    ),
    "/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib/libtorch.so": (
        "147be37e81800c47245287d4a10560a80d40790af61be33a13a4a926115ea7d6"
    ),
    "/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib/libtorch_xpu.so": (
        "ee584edab22b995637c5f6ec83fc10dea5931469c86cf2ad91952bb3e1108290"
    ),
    "/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib/libc10.so": (
        "a919fa044e546267eb455edc28fd55fd42e349e51b6c050a7d5484c9b05c0841"
    ),
}


def expected_passive_commands() -> list[list[str]]:
    commands = [[str(XPU_SMI), "discovery", "-j"]]
    commands.extend(
        [str(XPU_SMI), "config", "-d", str(device), "-t", "0", "-j"]
        for device in (0, 1)
    )
    for unit in ("xe-b70-minfreq.service", "xe-b70-minfreq.timer"):
        commands.append(
            [
                "/usr/bin/systemctl",
                "show",
                unit,
                "--no-pager",
                "-p",
                "LoadState",
                "-p",
                "ActiveState",
                "-p",
                "SubState",
                "-p",
                "FragmentPath",
                "-p",
                "MainPID",
            ]
        )
    commands.append(["/usr/bin/crontab", "-l"])
    return commands


class ContractError(RuntimeError):
    """Fail-closed diagnostic contract error."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    def pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in rows:
            if key in result:
                raise ContractError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ContractError(f"nonfinite JSON value: {value}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractError(f"cannot load strict JSON {path}: {error}") from error


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    encoded = (
        json.dumps(payload, allow_nan=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _load_campaign() -> Any:
    if sha256_file(CAMPAIGN_PATH) != CAMPAIGN_SHA256:
        raise ContractError("campaign source SHA differs")
    specification = importlib.util.spec_from_file_location(
        "qwen38_remote_map_campaign", CAMPAIGN_PATH
    )
    if specification is None or specification.loader is None:
        raise ContractError("cannot load frozen campaign source")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _git_output(*arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["/usr/bin/git", "-C", str(REMOTE_REPO), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ContractError(f"read-only Git preflight failed: {error}") from error
    return completed.stdout.strip()


def _run_passive(arguments: list[str], ok: tuple[int, ...] = (0,)) -> dict[str, Any]:
    if arguments not in expected_passive_commands():
        raise ContractError(f"command is outside passive allowlist: {arguments}")
    environment = {
        "HOME": "/home/steve",
        "USER": "steve",
        "LOGNAME": "steve",
        "LANG": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
        "ZES_ENABLE_SYSMAN": "1",
    }
    try:
        completed = subprocess.run(
            arguments,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ContractError(f"passive command failed: {arguments}: {error}") from error
    if completed.returncode not in ok:
        raise ContractError(
            f"passive command returned {completed.returncode}: {arguments}"
        )
    return {
        "argv": arguments,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
    }


def _strict_json_bytes(raw: bytes, where: str) -> Any:
    def pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in rows:
            if key in result:
                raise ContractError(f"{where}: duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ContractError(f"{where}: nonfinite JSON value: {value}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ContractError(f"{where}: invalid JSON: {error}") from error


def _scheduled_writer_scan() -> dict[str, Any]:
    forbidden_tokens = (b"xpu-smi", b"frequencyrange", b"xe-b70-minfreq")
    scheduled_matches: list[str] = []
    scheduled_files = [Path("/etc/crontab"), *sorted(Path("/etc/cron.d").glob("*"))]
    for root in (Path("/etc/systemd/system"), Path("/usr/lib/systemd/system")):
        if root.is_dir():
            scheduled_files.extend(path for path in root.rglob("*") if path.is_file())
    scheduled_inventory: list[dict[str, Any]] = []
    for path in scheduled_files:
        try:
            raw = path.read_bytes()
        except OSError as error:
            raise ContractError(
                f"cannot scan clock-writer source: {path}: {error}"
            ) from error
        writer_match = any(token in raw.lower() for token in forbidden_tokens)
        scheduled_inventory.append(
            {
                "path": str(path),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "writer_match": writer_match,
            }
        )
        if writer_match:
            scheduled_matches.append(str(path))
    return {
        "inventory_sha256": hashlib.sha256(
            json.dumps(
                scheduled_inventory,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
        "matches": scheduled_matches,
    }


def _live_writer_process_scan() -> list[int]:
    process_matches: list[int] = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            command = (proc / "cmdline").read_bytes().lower()
        except (FileNotFoundError, ProcessLookupError):
            continue
        except OSError as error:
            raise ContractError(
                f"cannot inspect live process {proc.name}: {error}"
            ) from error
        if (
            b"frequencyrange" in command
            or b"xe-b70-minfreq" in command
            or (b"xpu-smi" in command and b"config" in command)
        ):
            process_matches.append(int(proc.name))
    return process_matches


def passive_live_scan() -> dict[str, Any]:
    """Recheck boot, device normality/ranges, and passive clock writers."""
    if sha256_file(XPU_SMI) != XPU_SMI_SHA256:
        raise ContractError("passive scan xpu-smi identity differs")
    boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    if boot_id != EXPECTED_BOOT_ID:
        raise ContractError("passive scan boot identity differs")
    discovery_capture = _run_passive([str(XPU_SMI), "discovery", "-j"])
    executed_commands = [discovery_capture["argv"]]
    discovery = _strict_json_bytes(discovery_capture["stdout"], "xpu-smi discovery")
    entries = discovery.get("device_list") if isinstance(discovery, dict) else None
    if not isinstance(entries, list) or len(entries) != 2:
        raise ContractError("passive scan did not find exactly two devices")
    observed: dict[int, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or type(entry.get("device_id")) is not int:
            raise ContractError("passive scan device entry differs")
        device = entry["device_id"]
        if device not in EXPECTED_DEVICES or device in observed:
            raise ContractError("passive scan device index differs")
        if (
            entry.get("uuid") != EXPECTED_DEVICES[device]["uuid"]
            or entry.get("pci_bdf_address") != EXPECTED_DEVICES[device]["bdf"]
            or entry.get("device_state") != "normal"
            or entry.get("device_name") != "Intel(R) Arc(TM) Pro B70 Graphics"
        ):
            raise ContractError("passive scan B70 identity/state differs")
        observed[device] = {
            "uuid": entry["uuid"],
            "bdf": entry["pci_bdf_address"],
            "device_state": entry["device_state"],
        }
    configurations: list[dict[str, Any]] = []
    for device in (0, 1):
        capture = _run_passive(
            [str(XPU_SMI), "config", "-d", str(device), "-t", "0", "-j"]
        )
        executed_commands.append(capture["argv"])
        payload = _strict_json_bytes(capture["stdout"], f"xpu-smi config GPU{device}")
        try:
            tile = payload["tile_config_data"][0]
            minimum = tile["min_frequency"]
            maximum = tile["max_frequency"]
        except (KeyError, IndexError, TypeError) as error:
            raise ContractError("passive scan frequency fields differ") from error
        if (
            type(minimum) is not int
            or type(maximum) is not int
            or (minimum, maximum)
            != (
                400,
                2800,
            )
        ):
            raise ContractError("passive scan frequency range differs from 400,2800")
        configurations.append(
            {
                "device": device,
                "minimum_mhz": minimum,
                "maximum_mhz": maximum,
                "stdout_sha256": capture["stdout_sha256"],
                "stderr_sha256": capture["stderr_sha256"],
            }
        )
    unit_states: dict[str, dict[str, str]] = {}
    for unit in ("xe-b70-minfreq.service", "xe-b70-minfreq.timer"):
        capture = _run_passive(
            [
                "/usr/bin/systemctl",
                "show",
                unit,
                "--no-pager",
                "-p",
                "LoadState",
                "-p",
                "ActiveState",
                "-p",
                "SubState",
                "-p",
                "FragmentPath",
                "-p",
                "MainPID",
            ]
        )
        executed_commands.append(capture["argv"])
        state = {
            line.split("=", 1)[0]: line.split("=", 1)[1]
            for line in capture["stdout"].decode("utf-8").splitlines()
        }
        if state.get("LoadState") == "not-found" and "MainPID" not in state:
            state["MainPID"] = "0"
        if (
            state.get("LoadState") != "not-found"
            or state.get("ActiveState") != "inactive"
            or state.get("SubState") != "dead"
            or state.get("FragmentPath") != ""
            or state.get("MainPID", "0") != "0"
        ):
            raise ContractError(f"passive scan clock unit differs: {unit}")
        unit_states[unit] = state
    writer_sources = _scheduled_writer_scan()
    scheduled_matches = writer_sources["matches"]
    user_cron = _run_passive(["/usr/bin/crontab", "-l"], ok=(0, 1))
    executed_commands.append(user_cron["argv"])
    if user_cron["returncode"] == 1 and (
        user_cron["stdout_sha256"]
        != "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        or user_cron["stderr_sha256"]
        != "e9f79d01a6502f9cc14a17dd76affd70745edd75056cbebcf5f3c651d47b223e"
    ):
        raise ContractError("passive scan crontab rc1 outcome differs")
    if user_cron["returncode"] == 0 and any(
        token in user_cron["stdout"].lower()
        for token in (b"xpu-smi", b"frequencyrange", b"xe-b70-minfreq")
    ):
        scheduled_matches.append("user-crontab")
    process_matches = _live_writer_process_scan()
    if scheduled_matches or process_matches:
        raise ContractError("passive scan found a possible clock writer")
    return {
        "schema": "qwen38-q64k32-remote-live-scan-v1",
        "captured_time_ns": time.time_ns(),
        "boot_id": boot_id,
        "devices": [dict(device=device, **observed[device]) for device in (0, 1)],
        "discovery_stdout_sha256": discovery_capture["stdout_sha256"],
        "configurations": configurations,
        "clock_units": unit_states,
        "scheduled_source_inventory_sha256": writer_sources["inventory_sha256"],
        "user_crontab": {
            "returncode": user_cron["returncode"],
            "stdout_sha256": user_cron["stdout_sha256"],
            "stderr_sha256": user_cron["stderr_sha256"],
        },
        "read_only_commands": executed_commands,
        "scheduled_writer_matches": scheduled_matches,
        "process_writer_matches": process_matches,
        "passed": True,
    }


def diagnostic_preflight() -> dict[str, Any]:
    if DIAGNOSTIC_AUTHORIZED is not True:
        raise ContractError("runtime-map diagnostic is not authorized")
    if socket.gethostname() != "steve-TURIND8-2L2T":
        raise ContractError("runtime-map diagnostic requires the reference host")
    boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    if boot_id != EXPECTED_BOOT_ID:
        raise ContractError("runtime-map diagnostic boot identity differs")
    if sha256_file(PASSIVE_EVIDENCE) != PASSIVE_EVIDENCE_SHA256:
        raise ContractError("runtime-map passive evidence SHA differs")
    passive_evidence = load_json(PASSIVE_EVIDENCE)
    runtime_derivation = passive_evidence.get("runtime_static_derivation", {})
    static_map_sha = hashlib.sha256(
        json.dumps(
            STATIC_RUNTIME_CANDIDATES,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    if (
        passive_evidence.get("schema") != "qwen38-q64k32-remote-passive-enablement-v1"
        or passive_evidence.get("device_observation", {}).get("boot_id") != boot_id
        or passive_evidence.get("stage_freeze", {}).get("stage_inventory_sha256")
        != EXPECTED_STAGE_INVENTORY_SHA256
        or runtime_derivation.get("candidate_libraries") != STATIC_RUNTIME_CANDIDATES
        or runtime_derivation.get("candidate_paths") != STATIC_RUNTIME_CANDIDATE_PATHS
        or runtime_derivation.get("candidate_map_sha256") != static_map_sha
    ):
        raise ContractError("runtime-map passive evidence contract differs")
    head = _git_output("rev-parse", "HEAD")
    if (
        _git_output("branch", "--show-current") != "main"
        or _git_output("status", "--porcelain", "--untracked-files=normal")
        or _git_output("rev-parse", "origin/main") != head
    ):
        raise ContractError("runtime-map diagnostic requires clean main == origin/main")
    campaign = _load_campaign()
    derived = campaign.derive_stage_inventory(REMOTE_REPO)
    if derived["sha256"] != EXPECTED_STAGE_INVENTORY_SHA256:
        raise ContractError("runtime-map diagnostic stage inventory differs")
    return {
        "boot_id": boot_id,
        "repo_head": head,
        "stage_inventory_sha256": derived["sha256"],
        "campaign_sha256": CAMPAIGN_SHA256,
        "passive_evidence_sha256": PASSIVE_EVIDENCE_SHA256,
        "live_scan": passive_live_scan(),
    }


def _require_exact_keys(value: Any, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ContractError(f"{where}: keys differ")
    return value


def _require_sha(value: Any, where: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ContractError(f"{where}: SHA-256 differs")
    return value


def validate_live_scan(value: Any) -> dict[str, Any]:
    scan = _require_exact_keys(
        value,
        {
            "schema",
            "captured_time_ns",
            "boot_id",
            "devices",
            "discovery_stdout_sha256",
            "configurations",
            "clock_units",
            "scheduled_source_inventory_sha256",
            "user_crontab",
            "read_only_commands",
            "scheduled_writer_matches",
            "process_writer_matches",
            "passed",
        },
        "live scan",
    )
    if (
        scan["schema"] != "qwen38-q64k32-remote-live-scan-v1"
        or type(scan["captured_time_ns"]) is not int
        or scan["captured_time_ns"] <= 0
        or scan["boot_id"] != EXPECTED_BOOT_ID
        or scan["passed"] is not True
        or scan["scheduled_writer_matches"] != []
        or scan["process_writer_matches"] != []
        or scan["read_only_commands"] != expected_passive_commands()
    ):
        raise ContractError("live scan: result differs")
    expected_devices = [
        {
            "device": device,
            "uuid": EXPECTED_DEVICES[device]["uuid"],
            "bdf": EXPECTED_DEVICES[device]["bdf"],
            "device_state": "normal",
        }
        for device in (0, 1)
    ]
    if scan["devices"] != expected_devices:
        raise ContractError("live scan: device inventory differs")
    configurations = scan["configurations"]
    if not isinstance(configurations, list) or len(configurations) != 2:
        raise ContractError("live scan: configuration inventory differs")
    for device, configuration in enumerate(configurations):
        item = _require_exact_keys(
            configuration,
            {
                "device",
                "minimum_mhz",
                "maximum_mhz",
                "stdout_sha256",
                "stderr_sha256",
            },
            f"live scan GPU{device}",
        )
        if item["device"] != device or (item["minimum_mhz"], item["maximum_mhz"]) != (
            400,
            2800,
        ):
            raise ContractError(f"live scan GPU{device}: range differs")
        _require_sha(item["stdout_sha256"], f"live scan GPU{device} stdout")
        _require_sha(item["stderr_sha256"], f"live scan GPU{device} stderr")
    _require_sha(scan["discovery_stdout_sha256"], "live scan discovery")
    _require_sha(
        scan["scheduled_source_inventory_sha256"], "live scan scheduled sources"
    )
    user_crontab = _require_exact_keys(
        scan["user_crontab"],
        {"returncode", "stdout_sha256", "stderr_sha256"},
        "live scan user crontab",
    )
    if (
        user_crontab["returncode"] != 1
        or user_crontab["stdout_sha256"]
        != "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        or user_crontab["stderr_sha256"]
        != "e9f79d01a6502f9cc14a17dd76affd70745edd75056cbebcf5f3c651d47b223e"
    ):
        raise ContractError("live scan: user crontab outcome differs")
    expected_state = {
        "LoadState": "not-found",
        "ActiveState": "inactive",
        "SubState": "dead",
        "FragmentPath": "",
        "MainPID": "0",
    }
    if set(scan["clock_units"]) != {
        "xe-b70-minfreq.service",
        "xe-b70-minfreq.timer",
    }:
        raise ContractError("live scan: clock unit inventory differs")
    for unit, state in scan["clock_units"].items():
        if state != expected_state:
            raise ContractError(f"live scan: clock unit differs: {unit}")
    return scan


def validate_authorization(value: Any) -> dict[str, Any]:
    authorization = _require_exact_keys(
        value,
        {
            "boot_id",
            "repo_head",
            "stage_inventory_sha256",
            "campaign_sha256",
            "passive_evidence_sha256",
            "live_scan",
        },
        "authorization",
    )
    if (
        authorization["boot_id"] != EXPECTED_BOOT_ID
        or re.fullmatch(r"[0-9a-f]{40}", authorization["repo_head"] or "") is None
        or authorization["stage_inventory_sha256"] != EXPECTED_STAGE_INVENTORY_SHA256
        or authorization["campaign_sha256"] != CAMPAIGN_SHA256
        or authorization["passive_evidence_sha256"] != PASSIVE_EVIDENCE_SHA256
    ):
        raise ContractError("authorization: identity differs")
    validate_live_scan(authorization["live_scan"])
    return authorization


def scan_command(args: argparse.Namespace) -> dict[str, Any]:
    output = Path(args.output)
    if output != RESULT_ROOT / "preflight-live-scan.json" or output.exists():
        raise ContractError("live-scan output path differs")
    result = diagnostic_preflight()
    packet = {
        "schema": "qwen38-q64k32-remote-runtime-map-preflight-v1",
        "authorization": result,
        "clock_mutation_commands_invoked": False,
    }
    write_json_atomic(output, packet)
    return packet


def validate_preflight_scan(path: Path) -> dict[str, Any]:
    if path != RESULT_ROOT / "preflight-live-scan.json" or not path.is_file():
        raise ContractError("preflight live-scan path differs")
    if path.stat().st_mode & 0o222:
        raise ContractError("preflight live-scan is writable")
    packet = _require_exact_keys(
        load_json(path),
        {"schema", "authorization", "clock_mutation_commands_invoked"},
        "preflight live-scan packet",
    )
    if (
        packet["schema"] != "qwen38-q64k32-remote-runtime-map-preflight-v1"
        or packet["clock_mutation_commands_invoked"] is not False
    ):
        raise ContractError("preflight live-scan packet differs")
    validate_authorization(packet["authorization"])
    return packet


def _row(ordinal: int) -> dict[str, Any]:
    if ordinal < 1 or ordinal > len(PLAN):
        raise ContractError("diagnostic ordinal is outside 1..4")
    return dict(PLAN[ordinal - 1])


def _runtime_snapshot() -> dict[str, Any]:
    selected: dict[str, set[tuple[str, str, str, int, str, int]]] = {}
    try:
        lines = Path("/proc/self/maps").read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ContractError(f"cannot read runtime mappings: {error}") from error
    for line in lines:
        fields = line.split(maxsplit=5)
        if len(fields) < 6:
            continue
        mapped_text = fields[5]
        if mapped_text.endswith(" (deleted)"):
            basename = Path(mapped_text.removesuffix(" (deleted)")).name
            if re.match(r"^lib(?:sycl|ur_|ze_)", basename):
                raise ContractError(f"runtime mapping is deleted: {basename}")
            continue
        mapped = Path(mapped_text)
        if not mapped.is_absolute():
            continue
        if re.match(r"^lib(?:sycl|ur_|ze_)", mapped.name) is None:
            continue
        try:
            canonical = mapped.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise ContractError(f"runtime mapping is noncanonical: {mapped}") from error
        if not canonical.is_file():
            raise ContractError(f"runtime mapping is not a file: {canonical}")
        if re.match(r"^lib(?:sycl|ur_|ze_)", canonical.name) is None:
            raise ContractError(f"runtime mapping canonical basename differs: {mapped}")
        try:
            mapped_inode = int(fields[4])
        except ValueError as error:
            raise ContractError(f"runtime mapping inode differs: {mapped}") from error
        canonical_stat = canonical.stat()
        canonical_device = (
            f"{os.major(canonical_stat.st_dev):02x}:"
            f"{os.minor(canonical_stat.st_dev):02x}"
        )
        identity = (
            str(mapped),
            fields[3].lower(),
            mapped.name,
            mapped_inode,
            canonical_device,
            canonical_stat.st_ino,
        )
        if (
            fields[3].lower() != canonical_device
            or mapped_inode != canonical_stat.st_ino
        ):
            raise ContractError(f"runtime mapping device/inode differs: {mapped}")
        selected.setdefault(canonical.name, set()).add(identity)
    libraries: list[dict[str, Any]] = []
    for basename, identities in sorted(selected.items()):
        if len(identities) != 1:
            raise ContractError(f"runtime basename maps multiple paths: {basename}")
        mapped_path, mapped_device, mapped_basename, mapped_inode, device, inode = next(
            iter(identities)
        )
        path = Path(mapped_path).resolve(strict=True)
        libraries.append(
            {
                "basename": basename,
                "path": str(path),
                "mapped_basename": mapped_basename,
                "mapped_path": mapped_path,
                "mapped_device": mapped_device,
                "mapped_inode": mapped_inode,
                "canonical_device": device,
                "canonical_inode": inode,
                "sha256": sha256_file(path),
            }
        )
    expected_matches = {
        basename: any(
            item["basename"] == basename and item["sha256"] == digest
            for item in libraries
        )
        for basename, digest in sorted(STATIC_RUNTIME_CANDIDATES.items())
    }
    return {
        "libraries": libraries,
        "expected_static_candidates": dict(sorted(STATIC_RUNTIME_CANDIDATES.items())),
        "expected_matches": expected_matches,
    }


def validate_runtime_snapshot(value: Any, where: str) -> dict[str, Any]:
    snapshot = _require_exact_keys(
        value,
        {"libraries", "expected_static_candidates", "expected_matches"},
        where,
    )
    if snapshot["expected_static_candidates"] != dict(
        sorted(STATIC_RUNTIME_CANDIDATES.items())
    ):
        raise ContractError(f"{where}: static candidate inventory differs")
    libraries = snapshot["libraries"]
    if not isinstance(libraries, list):
        raise ContractError(f"{where}: library inventory differs")
    observed: dict[str, str] = {}
    previous: str | None = None
    for index, library in enumerate(libraries):
        item = _require_exact_keys(
            library,
            {
                "basename",
                "path",
                "mapped_basename",
                "mapped_path",
                "mapped_device",
                "mapped_inode",
                "canonical_device",
                "canonical_inode",
                "sha256",
            },
            f"{where}.libraries[{index}]",
        )
        basename = item["basename"]
        path = Path(item["path"])
        mapped_path = Path(item["mapped_path"])
        stat = path.stat() if path.is_file() else None
        canonical_device = (
            None
            if stat is None
            else f"{os.major(stat.st_dev):02x}:{os.minor(stat.st_dev):02x}"
        )
        if (
            not isinstance(basename, str)
            or re.match(r"^lib(?:sycl|ur_|ze_)", basename) is None
            or path.name != basename
            or not path.is_absolute()
            or not path.is_file()
            or path.resolve(strict=True) != path
            or not mapped_path.is_absolute()
            or mapped_path.name != item["mapped_basename"]
            or mapped_path.resolve(strict=True) != path
            or not isinstance(item["mapped_device"], str)
            or re.fullmatch(r"[0-9a-f]+:[0-9a-f]+", item["mapped_device"]) is None
            or type(item["mapped_inode"]) is not int
            or item["mapped_inode"] <= 0
            or item["canonical_device"] != canonical_device
            or item["mapped_device"] != canonical_device
            or type(item["canonical_inode"]) is not int
            or stat is None
            or item["canonical_inode"] != stat.st_ino
            or item["mapped_inode"] != stat.st_ino
            or (previous is not None and basename <= previous)
            or sha256_file(path) != _require_sha(item["sha256"], where)
        ):
            raise ContractError(f"{where}: mapped library differs")
        observed[basename] = item["sha256"]
        previous = basename
    expected_matches = {
        basename: observed.get(basename) == digest
        for basename, digest in sorted(STATIC_RUNTIME_CANDIDATES.items())
    }
    if snapshot["expected_matches"] != expected_matches:
        raise ContractError(f"{where}: static match summary differs")
    return snapshot


def validate_arm(path: Path, ordinal: int) -> dict[str, Any]:
    expected_path = RESULT_ROOT / f"arm-{ordinal:02d}.json"
    if path != expected_path or not path.is_file() or path.stat().st_mode & 0o222:
        raise ContractError(f"arm {ordinal}: artifact path/mode differs")
    packet = _require_exact_keys(
        load_json(path),
        {
            "schema",
            "passed",
            "authorization",
            "source_identity",
            "plan",
            "process",
            "stage_identity",
            "runtime_identity",
            "runtime_maps_before_first_operator",
            "runtime_maps_after_first_return_before_correctness",
            "correctness",
            "engagement",
            "clock_mutation_commands_invoked",
        },
        f"arm {ordinal}",
    )
    row = _row(ordinal)
    if (
        packet["schema"] != "qwen38-q64k32-remote-runtime-map-arm-v1"
        or packet["passed"] is not True
        or packet["plan"] != row
        or packet["clock_mutation_commands_invoked"] is not False
    ):
        raise ContractError(f"arm {ordinal}: result differs")
    validate_authorization(packet["authorization"])
    source = _require_exact_keys(
        packet["source_identity"],
        {"diagnostic_path", "diagnostic_sha256", "driver_path", "driver_sha256"},
        f"arm {ordinal}.source",
    )
    this_path = Path(__file__).resolve(strict=True)
    if (
        Path(source["diagnostic_path"]) != this_path
        or source["diagnostic_sha256"] != sha256_file(this_path)
        or Path(source["driver_path"]) != DRIVER_PATH
        or source["driver_sha256"] != sha256_file(DRIVER_PATH)
    ):
        raise ContractError(f"arm {ordinal}: source identity differs")
    process = _require_exact_keys(
        packet["process"],
        {"pid", "boot_id", "finished_time_ns"},
        f"arm {ordinal}.process",
    )
    if (
        type(process["pid"]) is not int
        or process["pid"] <= 1
        or process["boot_id"] != EXPECTED_BOOT_ID
        or type(process["finished_time_ns"]) is not int
        or process["finished_time_ns"] <= 0
        or packet["authorization"]["live_scan"]["captured_time_ns"]
        > process["finished_time_ns"]
    ):
        raise ContractError(f"arm {ordinal}: process identity differs")
    campaign = _load_campaign()
    qualifier = campaign._load_remote_qualifier(REMOTE_REPO)
    expected_identity = qualifier.stage_identity(_stage_namespace(row, path))
    if packet["stage_identity"] != expected_identity:
        raise ContractError(f"arm {ordinal}: stage identity differs")
    runtime = _require_exact_keys(
        packet["runtime_identity"],
        {
            "python_requested_path",
            "python_executable",
            "python_resolved_path",
            "python_sha256",
            "python_version",
            "torch_version",
            "torch_files",
            "logical_xpu_device_count",
            "logical_xpu_index",
            "physical_xpu_index",
            "device_properties",
            "worker_environment",
        },
        f"arm {ordinal}.runtime",
    )
    properties = runtime["device_properties"]
    stage = Path(expected_identity["stage"])
    expected_environment = {
        "HOME": "/home/steve",
        "USER": "steve",
        "LOGNAME": "steve",
        "SHELL": "/usr/bin/bash",
        "LANG": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(stage),
        "LD_LIBRARY_PATH": (
            f"{stage / 'vllm_xpu_kernels'}:"
            "/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:"
            "/home/steve/.venvs/vllm-xpu/lib"
        ),
        "ZE_AFFINITY_MASK": str(row["device"]),
        "VLLM_XPU_FA2_FORCE_CHUNK_DECODE": "1",
        qualifier.POLICY_ENV: "0" if row["role"] == "control" else "1",
        "QWEN38_RUNTIME_MAP_DRIVER": str(DRIVER_PATH),
        "QWEN38_RUNTIME_MAP_DRIVER_SHA256": source["driver_sha256"],
    }
    if (
        runtime["python_requested_path"] != str(REMOTE_PYTHON)
        or Path(runtime["python_executable"]) != REMOTE_PYTHON
        or runtime["python_resolved_path"] != str(PYTHON_RESOLVED)
        or runtime["python_sha256"] != PYTHON_SHA256
        or runtime["python_version"] != "3.12.3"
        or runtime["torch_version"] != TORCH_VERSION
        or runtime["torch_files"] != dict(sorted(TORCH_FILES.items()))
        or runtime["logical_xpu_device_count"] != 1
        or runtime["logical_xpu_index"] != 0
        or runtime["physical_xpu_index"] != row["device"]
        or runtime["worker_environment"] != expected_environment
        or not isinstance(properties, dict)
        or properties.get("name") != "Intel(R) Arc(TM) Pro B70 Graphics"
        or any(
            type(properties.get(name)) is not int or properties[name] <= 0
            for name in (
                "total_memory",
                "gpu_eu_count",
                "gpu_subslice_count",
                "max_work_group_size",
            )
        )
    ):
        raise ContractError(f"arm {ordinal}: runtime/device identity differs")
    if sha256_file(PYTHON_RESOLVED) != PYTHON_SHA256 or any(
        sha256_file(Path(path)) != digest for path, digest in TORCH_FILES.items()
    ):
        raise ContractError(f"arm {ordinal}: runtime files changed")
    validate_runtime_snapshot(
        packet["runtime_maps_before_first_operator"], f"arm {ordinal}.maps_before"
    )
    validate_runtime_snapshot(
        packet["runtime_maps_after_first_return_before_correctness"],
        f"arm {ordinal}.maps_after",
    )
    correctness = _require_exact_keys(
        packet["correctness"],
        {
            "kv_length",
            "fixture_seed",
            "fixture_sha256",
            "output_sha256",
            "oracle_sha256",
            "max_abs_diff",
            "atol",
            "rtol",
            "passed",
        },
        f"arm {ordinal}.correctness",
    )
    if (
        correctness["kv_length"] != KV_LENGTH
        or correctness["fixture_seed"] != 380000 + KV_LENGTH
        or correctness["passed"] is not True
        or not isinstance(correctness["max_abs_diff"], (int, float))
        or isinstance(correctness["max_abs_diff"], bool)
        or not math.isfinite(correctness["max_abs_diff"])
        or correctness["max_abs_diff"] < 0
        or correctness["max_abs_diff"] > qualifier.BASE.ATOL
        or correctness["fixture_sha256"] != EXPECTED_FIXTURE_SHA256
        or correctness["oracle_sha256"] != EXPECTED_ORACLE_SHA256
    ):
        raise ContractError(f"arm {ordinal}: correctness summary differs")
    _require_sha(correctness["output_sha256"], f"arm {ordinal} output")
    _require_sha(correctness["fixture_sha256"], f"arm {ordinal} fixture")
    _require_sha(correctness["oracle_sha256"], f"arm {ordinal} oracle")
    if (
        correctness["atol"] != qualifier.BASE.ATOL
        or correctness["rtol"] != qualifier.BASE.RTOL
    ):
        raise ContractError(f"arm {ordinal}: correctness tolerances differ")
    engagement = _require_exact_keys(
        packet["engagement"],
        {
            "policy_env",
            "policy_value",
            "marker_lines",
            "stderr_path",
            "stderr_sha256",
        },
        f"arm {ordinal}.engagement",
    )
    expected_policy = "0" if row["role"] == "control" else "1"
    expected_markers = [] if row["role"] == "control" else [qualifier.POLICY_MARKER]
    stderr_path = Path(engagement["stderr_path"])
    if (
        engagement["policy_env"] != qualifier.POLICY_ENV
        or engagement["policy_value"] != expected_policy
        or engagement["marker_lines"] != expected_markers
        or stderr_path != Path(f"{path}.operator-stderr.log")
        or not stderr_path.is_file()
        or stderr_path.stat().st_mode & 0o222
        or engagement["stderr_sha256"] != sha256_file(stderr_path)
        or stderr_path.read_text(encoding="utf-8").splitlines() != expected_markers
    ):
        raise ContractError(f"arm {ordinal}: engagement evidence differs")
    return packet


def _stage_namespace(row: dict[str, Any], output: Path) -> argparse.Namespace:
    campaign = _load_campaign()
    return argparse.Namespace(
        role=row["role"],
        stage=(str(campaign.CONTROL_STAGE) if row["role"] == "control" else None),
        stage_manifest=(
            None if row["role"] == "control" else str(campaign.CANDIDATE_MANIFEST)
        ),
        physical_gpu=row["device"],
        arm_id=f"gpu{row['device']}-{row['role']}-runtime-map",
        campaign_slot=1,
        output=str(output),
        samples=1,
        launches_per_sample=1,
        stability_replays=1,
    )


def worker_command(args: argparse.Namespace) -> dict[str, Any]:
    authorization = diagnostic_preflight()
    row = _row(args.ordinal)
    output = Path(args.output)
    expected_output = RESULT_ROOT / f"arm-{args.ordinal:02d}.json"
    if (
        args.device != row["device"]
        or args.role != row["role"]
        or output != expected_output
        or output.exists()
    ):
        raise ContractError("diagnostic worker arguments/artifact differ")
    campaign = _load_campaign()
    qualifier = campaign._load_remote_qualifier(REMOTE_REPO)
    namespace = _stage_namespace(row, output)
    try:
        identity = qualifier.stage_identity(namespace)
    except qualifier.ContractError as error:
        raise ContractError(f"diagnostic stage identity failed: {error}") from error
    stage = Path(identity["stage"])
    driver_text = os.environ.get("QWEN38_RUNTIME_MAP_DRIVER")
    driver_sha = os.environ.get("QWEN38_RUNTIME_MAP_DRIVER_SHA256")
    if (
        not driver_text
        or not driver_sha
        or Path(driver_text).resolve(strict=True) != DRIVER_PATH
        or sha256_file(DRIVER_PATH) != driver_sha
    ):
        raise ContractError("diagnostic driver path/SHA differs")
    expected_policy = "0" if row["role"] == "control" else "1"
    expected_environment = {
        "HOME": "/home/steve",
        "USER": "steve",
        "LOGNAME": "steve",
        "SHELL": "/usr/bin/bash",
        "LANG": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(stage),
        "LD_LIBRARY_PATH": (
            f"{stage / 'vllm_xpu_kernels'}:"
            "/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:"
            "/home/steve/.venvs/vllm-xpu/lib"
        ),
        "ZE_AFFINITY_MASK": str(row["device"]),
        "VLLM_XPU_FA2_FORCE_CHUNK_DECODE": "1",
        qualifier.POLICY_ENV: expected_policy,
        "QWEN38_RUNTIME_MAP_DRIVER": str(DRIVER_PATH),
        "QWEN38_RUNTIME_MAP_DRIVER_SHA256": driver_sha,
    }
    if (
        dict(os.environ) != expected_environment
        or Path(os.environ["PYTHONPATH"]).resolve(strict=True) != stage
        or Path(os.environ["LD_LIBRARY_PATH"].split(os.pathsep)[0]).resolve(strict=True)
        != stage / "vllm_xpu_kernels"
    ):
        raise ContractError("diagnostic worker environment differs")

    import torch  # pylint: disable=import-outside-toplevel

    python_resolved = Path(sys.executable).resolve(strict=True)
    if (
        python_resolved != PYTHON_RESOLVED
        or sha256_file(python_resolved) != PYTHON_SHA256
        or platform.python_version() != "3.12.3"
        or torch.__version__ != TORCH_VERSION
        or Path(torch.__file__).resolve(strict=True)
        != Path(next(iter(TORCH_FILES))).resolve(strict=True)
    ):
        raise ContractError("diagnostic Python/Torch identity differs")
    for path_text, digest in TORCH_FILES.items():
        if sha256_file(Path(path_text).resolve(strict=True)) != digest:
            raise ContractError(f"diagnostic Torch file differs: {path_text}")
    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        raise ContractError("diagnostic affinity-scoped XPU identity differs")
    torch.xpu.set_device(0)
    interface = __import__(
        "vllm_xpu_kernels.flash_attn_interface", fromlist=["flash_attn_varlen_func"]
    )
    extension = __import__("vllm_xpu_kernels._vllm_fa2_C", fromlist=["*"])
    if Path(interface.__file__).resolve() != Path(
        identity["files"]["interface"]["path"]
    ) or Path(extension.__file__).resolve() != Path(
        identity["files"]["extension"]["path"]
    ):
        raise ContractError("diagnostic imported stage identity differs")

    base = qualifier.BASE
    device_properties = base._device_properties(torch, 0)
    if device_properties.get("name") != "Intel(R) Arc(TM) Pro B70 Graphics":
        raise ContractError("diagnostic logical xpu:0 is not the expected B70")
    generator = torch.Generator(device="cpu").manual_seed(380000 + KV_LENGTH)
    q_cpu = torch.randn(
        base.ROWS,
        base.Q_HEADS,
        base.HEAD_DIM,
        dtype=torch.float16,
        generator=generator,
    )
    logical_blocks = (KV_LENGTH + base.BLOCK_SIZE - 1) // base.BLOCK_SIZE
    num_blocks = logical_blocks + 3
    block_order = torch.randperm(num_blocks, generator=generator)[:logical_blocks]
    k_cpu = torch.randn(
        num_blocks,
        base.BLOCK_SIZE,
        base.KV_HEADS,
        base.HEAD_DIM,
        dtype=torch.float16,
        generator=generator,
    )
    v_cpu = torch.randn(
        num_blocks,
        base.BLOCK_SIZE,
        base.KV_HEADS,
        base.HEAD_DIM,
        dtype=torch.float16,
        generator=generator,
    )
    logical_k = k_cpu[block_order].reshape(-1, base.KV_HEADS, base.HEAD_DIM)[:KV_LENGTH]
    logical_v = v_cpu[block_order].reshape(-1, base.KV_HEADS, base.HEAD_DIM)[:KV_LENGTH]
    expected = base._cpu_reference(torch, q_cpu, logical_k, logical_v)
    xpu = torch.device("xpu", 0)
    q = q_cpu.to(xpu)
    k_cache = k_cpu.to(xpu)
    v_cache = v_cpu.to(xpu)
    cu_q = torch.tensor([0, base.ROWS], dtype=torch.int32, device=xpu)
    seqused_k = torch.tensor([KV_LENGTH], dtype=torch.int32, device=xpu)
    block_table = block_order.to(dtype=torch.int32, device=xpu).view(1, -1)
    out = torch.empty_like(q)
    out.fill_(float("nan"))
    torch.xpu.synchronize()
    maps_before = _runtime_snapshot()
    stderr_path = Path(f"{output}.operator-stderr.log")
    stderr_temporary = Path(f"{stderr_path}.tmp")
    saved_stderr = os.dup(2)
    try:
        with stderr_temporary.open("xb") as stream:
            os.dup2(stream.fileno(), 2)
            try:
                returned = interface.flash_attn_varlen_func(
                    q,
                    k_cache,
                    v_cache,
                    base.ROWS,
                    cu_q,
                    KV_LENGTH,
                    seqused_k=seqused_k,
                    softmax_scale=base.HEAD_DIM**-0.5,
                    causal=True,
                    block_table=block_table,
                    out=out,
                    is_mix_batch=True,
                )
                torch.xpu.synchronize()
                maps_after = _runtime_snapshot()
                sys.stderr.flush()
                os.fsync(stream.fileno())
            finally:
                os.dup2(saved_stderr, 2)
    finally:
        os.close(saved_stderr)
    os.chmod(stderr_temporary, 0o444)
    os.replace(stderr_temporary, stderr_path)
    if returned.data_ptr() != out.data_ptr():
        raise ContractError("first operator return ignored the supplied output")
    actual = out.cpu()
    max_abs_diff = base._assert_close(
        torch, actual, expected, "runtime-map diagnostic KV 128 eager 0"
    )
    stderr_lines = stderr_path.read_text(encoding="utf-8").splitlines()
    marker_lines = [line for line in stderr_lines if qualifier.POLICY_ENV in line]
    expected_markers = [] if row["role"] == "control" else [qualifier.POLICY_MARKER]
    if marker_lines != expected_markers or stderr_lines != expected_markers:
        raise ContractError("runtime-map diagnostic operator stderr differs")
    packet = {
        "schema": "qwen38-q64k32-remote-runtime-map-arm-v1",
        "passed": True,
        "authorization": authorization,
        "source_identity": {
            "diagnostic_path": str(Path(__file__).resolve(strict=True)),
            "diagnostic_sha256": sha256_file(Path(__file__).resolve(strict=True)),
            "driver_path": str(DRIVER_PATH),
            "driver_sha256": driver_sha,
        },
        "plan": row,
        "process": {
            "pid": os.getpid(),
            "boot_id": EXPECTED_BOOT_ID,
            "finished_time_ns": time.time_ns(),
        },
        "stage_identity": identity,
        "runtime_identity": {
            "python_requested_path": str(REMOTE_PYTHON),
            "python_executable": sys.executable,
            "python_resolved_path": str(python_resolved),
            "python_sha256": PYTHON_SHA256,
            "python_version": platform.python_version(),
            "torch_version": torch.__version__,
            "torch_files": dict(sorted(TORCH_FILES.items())),
            "logical_xpu_device_count": torch.xpu.device_count(),
            "logical_xpu_index": 0,
            "physical_xpu_index": row["device"],
            "device_properties": device_properties,
            "worker_environment": expected_environment,
        },
        "runtime_maps_before_first_operator": maps_before,
        "runtime_maps_after_first_return_before_correctness": maps_after,
        "correctness": {
            "kv_length": KV_LENGTH,
            "fixture_seed": 380000 + KV_LENGTH,
            "fixture_sha256": base.fixture_digest(q_cpu, k_cpu, v_cpu, block_order),
            "output_sha256": base.tensor_digest(actual),
            "oracle_sha256": base.tensor_digest(expected),
            "max_abs_diff": max_abs_diff,
            "atol": base.ATOL,
            "rtol": base.RTOL,
            "passed": True,
        },
        "engagement": {
            "policy_env": qualifier.POLICY_ENV,
            "policy_value": expected_policy,
            "marker_lines": marker_lines,
            "stderr_path": str(stderr_path),
            "stderr_sha256": sha256_file(stderr_path),
        },
        "clock_mutation_commands_invoked": False,
    }
    write_json_atomic(output, packet)
    return packet


def _write_late_signal_receipt(
    terminal: Path, late_signals: Path, signums: list[int]
) -> None:
    if late_signals.exists() or not terminal.is_file():
        return
    try:
        write_json_atomic(
            late_signals,
            {
                "schema": "qwen38-q64k32-remote-runtime-map-late-signal-v1",
                "terminal_path": str(terminal.resolve(strict=True)),
                "terminal_sha256": sha256_file(terminal),
                "signals": sorted(set(signums)),
                "time_ns": time.time_ns(),
            },
        )
    except (OSError, ContractError):
        if late_signals.exists():
            return
        os._exit(125)


def _publish_terminal_with_signal_fence(
    terminal: Path,
    late_signals: Path,
    terminal_packet: dict[str, Any],
    watched: tuple[signal.Signals, ...],
    previous_mask: set[signal.Signals],
) -> dict[str, Any]:
    try:
        write_json_atomic(terminal, terminal_packet)

        def record_late(signum: int, _frame: Any) -> None:
            _write_late_signal_receipt(terminal, late_signals, [signum])

        for item in watched:
            signal.signal(item, record_late)
        drained: list[int] = []
        while True:
            caught = signal.sigtimedwait(watched, 0)
            if caught is None:
                break
            drained.append(int(caught.si_signo))
        if drained:
            _write_late_signal_receipt(terminal, late_signals, drained)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
    returned = dict(terminal_packet)
    if late_signals.exists():
        returned["status"] = "interrupted"
        returned["valid"] = False
    return returned


def supervise_command(args: argparse.Namespace) -> dict[str, Any]:
    pending: list[int] = []

    def record_signal(signum: int, _frame: Any) -> None:
        pending.append(signum)

    watched = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
    inherited_mask = signal.pthread_sigmask(signal.SIG_BLOCK, ())
    if any(item in inherited_mask for item in watched):
        raise ContractError("diagnostic supervisor inherited a blocked signal")
    for item in watched:
        signal.signal(item, record_signal)
    row = _row(args.ordinal)
    terminal = Path(args.terminal)
    output = RESULT_ROOT / f"arm-{args.ordinal:02d}.json"
    log = RESULT_ROOT / f"arm-{args.ordinal:02d}.supervisor.log"
    expected_terminal = RESULT_ROOT / f"arm-{args.ordinal:02d}.terminal.json"
    late_signals = Path(f"{terminal}.signals-late.json")
    command = list(args.command)
    if command[:1] == ["--"]:
        command.pop(0)
    expected_command = [
        str(REMOTE_PYTHON),
        "-B",
        str(Path(__file__).resolve()),
        "worker",
        "--ordinal",
        str(row["ordinal"]),
        "--device",
        str(row["device"]),
        "--role",
        row["role"],
        "--output",
        str(output),
    ]
    if command != expected_command:
        raise ContractError("diagnostic supervisor command differs")
    command_sha = hashlib.sha256(("\0".join(command) + "\0").encode()).hexdigest()
    supervisor_started = Path(f"{terminal}.phase-supervisor-started.json")
    before = Path(f"{terminal}.phase-before-spawn.json")
    spawned = Path(f"{terminal}.phase-spawned.json")
    preflight_receipt = Path(f"{terminal}.phase-preflight.json")
    if terminal != expected_terminal or any(
        path.exists()
        for path in (
            terminal,
            output,
            log,
            late_signals,
            supervisor_started,
            preflight_receipt,
            before,
            spawned,
        )
    ):
        raise ContractError("diagnostic supervisor artifact contract differs")
    supervisor_started_time_ns = time.time_ns()
    write_json_atomic(
        supervisor_started,
        {
            "schema": "qwen38-q64k32-remote-runtime-map-phase-v1",
            "phase": "supervisor-started",
            "time_ns": supervisor_started_time_ns,
            "supervisor_pid": os.getpid(),
            "plan": row,
            "command_sha256": command_sha,
        },
    )
    authorization: dict[str, Any] | None = None
    campaign: Any | None = None
    started_time_ns = supervisor_started_time_ns
    process: subprocess.Popen[bytes] | None = None
    start_ticks: int | None = None
    returncode: int | None = None
    cleanup = {
        "identity_safe": False,
        "term_sent": False,
        "kill_sent": False,
        "group_absent": False,
    }
    status = "invalid"
    error: str | None = None
    try:
        authorization = diagnostic_preflight()
        write_json_atomic(
            preflight_receipt,
            {
                "schema": "qwen38-q64k32-remote-runtime-map-phase-v1",
                "phase": "preflight-complete",
                "time_ns": time.time_ns(),
                "supervisor_pid": os.getpid(),
                "plan": row,
                "authorization": authorization,
            },
        )
        campaign = _load_campaign()
        started_time_ns = time.time_ns()
        write_json_atomic(
            before,
            {
                "schema": "qwen38-q64k32-remote-runtime-map-phase-v1",
                "phase": "before-spawn",
                "time_ns": started_time_ns,
                "supervisor_pid": os.getpid(),
                "plan": row,
                "command_sha256": command_sha,
            },
        )
        if pending:
            raise ContractError("diagnostic supervisor interrupted before worker spawn")
        with log.open("xb") as stream:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
            for _ in range(20):
                try:
                    start_ticks = campaign._proc_start_ticks(process.pid)
                    break
                except (OSError, ValueError, campaign.ContractError):
                    time.sleep(0.01)
            if start_ticks is None:
                cleanup = campaign._terminate_unreaped_fresh_group(
                    process, GRACE_SECONDS
                )
                raise ContractError("diagnostic worker identity unavailable")
            write_json_atomic(
                spawned,
                {
                    "schema": "qwen38-q64k32-remote-runtime-map-phase-v1",
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
            returncode, cleanup, watched_status = campaign._watch_owned_process(
                process,
                start_ticks,
                TIMEOUT_SECONDS,
                GRACE_SECONDS,
                lambda: bool(pending),
            )
            if watched_status is not None:
                status = watched_status
        os.chmod(log, 0o444)
        if pending and status not in {"timeout", "interrupted"}:
            status = "interrupted"
        if status not in {"timeout", "interrupted"}:
            if returncode == 0 and output.is_file() and cleanup["group_absent"]:
                validate_arm(output, row["ordinal"])
                status = "success"
            else:
                error = "diagnostic worker exit/artifact state differs"
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as caught:
        error = f"{type(caught).__name__}: {caught}"
        if process is not None and start_ticks is not None and campaign is not None:
            cleanup = campaign._terminate_group(process.pid, start_ticks, GRACE_SECONDS)
            returncode = process.poll()
        elif process is not None and campaign is not None:
            cleanup = campaign._terminate_unreaped_fresh_group(process, GRACE_SECONDS)
            returncode = process.returncode
        else:
            cleanup["identity_safe"] = True
            cleanup["group_absent"] = True
        if log.exists():
            os.chmod(log, 0o444)
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, watched)
    pending.extend(
        int(item)
        for item in signal.sigpending()
        if item in watched and int(item) not in pending
    )
    pending = sorted(set(pending))
    if pending and status not in {"timeout", "interrupted"}:
        status = "interrupted"
    terminal_packet = {
        "schema": "qwen38-q64k32-remote-runtime-map-terminal-v1",
        "status": status,
        "valid": status == "success" and cleanup["group_absent"] is True,
        "plan": row,
        "authorization": authorization,
        "process": {
            "supervisor_pid": os.getpid(),
            "worker_pid": None if process is None else process.pid,
            "worker_pgid": None if process is None else process.pid,
            "worker_start_ticks": start_ticks,
            "returncode": returncode,
            "started_time_ns": started_time_ns,
            "finished_time_ns": time.time_ns(),
            "command_sha256": command_sha,
        },
        "watchdog": {
            "timeout_seconds": TIMEOUT_SECONDS,
            "grace_seconds": GRACE_SECONDS,
            "cleanup": cleanup,
        },
        "signals": pending,
        "artifacts": {
            "output": _artifact(output),
            "log": _artifact(log),
            "supervisor_started": _artifact(supervisor_started),
            "before": _artifact(before),
            "spawned": _artifact(spawned),
            "preflight": _artifact(preflight_receipt),
        },
        "error": error,
    }
    return _publish_terminal_with_signal_fence(
        terminal,
        late_signals,
        terminal_packet,
        watched,
        previous_mask,
    )


def _artifact(path: Path) -> dict[str, str] | None:
    if not path.is_file():
        return None
    return {"path": str(path.resolve(strict=True)), "sha256": sha256_file(path)}


def validate_terminal(path: Path) -> dict[str, Any]:
    if Path(f"{path}.signals-late.json").exists():
        raise ContractError("diagnostic terminal has a late-signal receipt")
    packet = _require_exact_keys(
        load_json(path),
        {
            "schema",
            "status",
            "valid",
            "plan",
            "authorization",
            "process",
            "watchdog",
            "signals",
            "artifacts",
            "error",
        },
        "diagnostic terminal",
    )
    if (
        packet["schema"] != "qwen38-q64k32-remote-runtime-map-terminal-v1"
        or packet["status"] != "success"
        or packet["valid"] is not True
        or packet["signals"] != []
        or packet["error"] is not None
        or path.stat().st_mode & 0o222
    ):
        raise ContractError("diagnostic terminal is not a valid success")
    authorization = validate_authorization(packet["authorization"])
    ordinal = packet.get("plan", {}).get("ordinal")
    if type(ordinal) is not int or packet["plan"] != _row(ordinal):
        raise ContractError("diagnostic terminal plan differs")
    process = _require_exact_keys(
        packet["process"],
        {
            "supervisor_pid",
            "worker_pid",
            "worker_pgid",
            "worker_start_ticks",
            "returncode",
            "started_time_ns",
            "finished_time_ns",
            "command_sha256",
        },
        "diagnostic terminal process",
    )
    if (
        type(process["supervisor_pid"]) is not int
        or process["supervisor_pid"] <= 1
        or type(process["worker_pid"]) is not int
        or process["worker_pid"] <= 1
        or process["worker_pgid"] != process["worker_pid"]
        or type(process["worker_start_ticks"]) is not int
        or process["worker_start_ticks"] <= 0
        or process["returncode"] != 0
        or type(process["started_time_ns"]) is not int
        or type(process["finished_time_ns"]) is not int
        or process["finished_time_ns"] < process["started_time_ns"]
        or authorization["live_scan"]["captured_time_ns"] > process["started_time_ns"]
    ):
        raise ContractError("diagnostic terminal process identity differs")
    _require_sha(process["command_sha256"], "diagnostic terminal command")
    expected_worker_command = [
        str(REMOTE_PYTHON),
        "-B",
        str(Path(__file__).resolve()),
        "worker",
        "--ordinal",
        str(ordinal),
        "--device",
        str(packet["plan"]["device"]),
        "--role",
        packet["plan"]["role"],
        "--output",
        str(RESULT_ROOT / f"arm-{ordinal:02d}.json"),
    ]
    expected_command_sha = hashlib.sha256(
        ("\0".join(expected_worker_command) + "\0").encode()
    ).hexdigest()
    if process["command_sha256"] != expected_command_sha:
        raise ContractError("diagnostic terminal command identity differs")
    watchdog = _require_exact_keys(
        packet["watchdog"],
        {"timeout_seconds", "grace_seconds", "cleanup"},
        "diagnostic terminal watchdog",
    )
    cleanup = _require_exact_keys(
        watchdog["cleanup"],
        {"identity_safe", "term_sent", "kill_sent", "group_absent"},
        "diagnostic terminal cleanup",
    )
    if (
        watchdog["timeout_seconds"] != TIMEOUT_SECONDS
        or watchdog["grace_seconds"] != GRACE_SECONDS
        or cleanup["identity_safe"] is not True
        or cleanup["group_absent"] is not True
        or any(type(item) is not bool for item in cleanup.values())
    ):
        raise ContractError("diagnostic terminal watchdog differs")
    output = RESULT_ROOT / f"arm-{ordinal:02d}.json"
    expected_paths = {
        "output": output,
        "log": RESULT_ROOT / f"arm-{ordinal:02d}.supervisor.log",
        "supervisor_started": Path(f"{path}.phase-supervisor-started.json"),
        "preflight": Path(f"{path}.phase-preflight.json"),
        "before": Path(f"{path}.phase-before-spawn.json"),
        "spawned": Path(f"{path}.phase-spawned.json"),
    }
    artifacts = _require_exact_keys(
        packet["artifacts"], set(expected_paths), "diagnostic terminal artifacts"
    )
    for name, expected in expected_paths.items():
        artifact = _require_exact_keys(
            artifacts[name], {"path", "sha256"}, f"diagnostic {name} artifact"
        )
        if (
            Path(artifact["path"]) != expected
            or not expected.is_file()
            or expected.stat().st_mode & 0o222
            or artifact["sha256"] != sha256_file(expected)
        ):
            raise ContractError(f"diagnostic terminal {name} binding differs")
    before = load_json(expected_paths["before"])
    spawned = load_json(expected_paths["spawned"])
    supervisor_started = _require_exact_keys(
        load_json(expected_paths["supervisor_started"]),
        {"schema", "phase", "time_ns", "supervisor_pid", "plan", "command_sha256"},
        "diagnostic supervisor-started receipt",
    )
    preflight_receipt = _require_exact_keys(
        load_json(expected_paths["preflight"]),
        {"schema", "phase", "time_ns", "supervisor_pid", "plan", "authorization"},
        "diagnostic preflight receipt",
    )
    if (
        supervisor_started["schema"] != "qwen38-q64k32-remote-runtime-map-phase-v1"
        or supervisor_started["phase"] != "supervisor-started"
        or supervisor_started["supervisor_pid"] != process["supervisor_pid"]
        or supervisor_started["plan"] != packet["plan"]
        or supervisor_started["command_sha256"] != process["command_sha256"]
        or type(supervisor_started["time_ns"]) is not int
        or supervisor_started["time_ns"] > preflight_receipt["time_ns"]
        or preflight_receipt["schema"] != "qwen38-q64k32-remote-runtime-map-phase-v1"
        or preflight_receipt["phase"] != "preflight-complete"
        or preflight_receipt["supervisor_pid"] != process["supervisor_pid"]
        or preflight_receipt["plan"] != packet["plan"]
        or preflight_receipt["authorization"] != authorization
        or type(preflight_receipt["time_ns"]) is not int
        or preflight_receipt["time_ns"] > process["started_time_ns"]
    ):
        raise ContractError("diagnostic preflight receipt differs")
    for receipt, phase in ((before, "before-spawn"), (spawned, "spawned")):
        expected_keys = {
            "schema",
            "phase",
            "time_ns",
            "supervisor_pid",
            "plan",
            "command_sha256",
        }
        if phase == "spawned":
            expected_keys |= {"worker_pid", "worker_pgid", "worker_start_ticks"}
        _require_exact_keys(receipt, expected_keys, f"diagnostic {phase} receipt")
        if (
            receipt["schema"] != "qwen38-q64k32-remote-runtime-map-phase-v1"
            or receipt["phase"] != phase
            or receipt["supervisor_pid"] != process["supervisor_pid"]
            or receipt["plan"] != packet["plan"]
            or receipt["command_sha256"] != process["command_sha256"]
            or type(receipt["time_ns"]) is not int
        ):
            raise ContractError(f"diagnostic {phase} receipt differs")
    if (
        before["time_ns"] != process["started_time_ns"]
        or not before["time_ns"] < spawned["time_ns"] <= process["finished_time_ns"]
        or spawned["worker_pid"] != process["worker_pid"]
        or spawned["worker_pgid"] != process["worker_pgid"]
        or spawned["worker_start_ticks"] != process["worker_start_ticks"]
    ):
        raise ContractError("diagnostic receipt chronology/identity differs")
    arm = validate_arm(output, ordinal)
    if (
        arm["authorization"]["repo_head"] != authorization["repo_head"]
        or arm["authorization"]["stage_inventory_sha256"]
        != authorization["stage_inventory_sha256"]
        or arm["process"]["finished_time_ns"] > process["finished_time_ns"]
        or arm["process"]["pid"] != process["worker_pid"]
    ):
        raise ContractError("diagnostic terminal arm binding differs")
    return packet


def validate_cleanup_terminal(
    path: Path, expected_ordinal: int, expected_supervisor_pid: int
) -> dict[str, Any]:
    expected = [
        RESULT_ROOT / f"arm-{ordinal:02d}.terminal.json" for ordinal in range(1, 5)
    ]
    if path not in expected or not path.is_file() or path.stat().st_mode & 0o222:
        raise ContractError("diagnostic cleanup terminal path/mode differs")
    packet = _require_exact_keys(
        load_json(path),
        {
            "schema",
            "status",
            "valid",
            "plan",
            "authorization",
            "process",
            "watchdog",
            "signals",
            "artifacts",
            "error",
        },
        "diagnostic cleanup terminal",
    )
    status = packet["status"]
    if (
        packet["schema"] != "qwen38-q64k32-remote-runtime-map-terminal-v1"
        or status not in {"success", "timeout", "interrupted", "invalid"}
        or packet["plan"] != _row(expected_ordinal)
        or Path(f"{path}.signals-late.json").exists()
    ):
        raise ContractError("diagnostic cleanup terminal status differs")
    if status == "success":
        result = validate_terminal(path)
        if result["process"]["supervisor_pid"] != expected_supervisor_pid:
            raise ContractError("diagnostic cleanup supervisor ownership differs")
        return result
    if packet["valid"] is not False:
        raise ContractError("diagnostic cleanup negative validity differs")
    preflight_failed = packet["authorization"] is None
    if not preflight_failed:
        validate_authorization(packet["authorization"])
    process = _require_exact_keys(
        packet["process"],
        {
            "supervisor_pid",
            "worker_pid",
            "worker_pgid",
            "worker_start_ticks",
            "returncode",
            "started_time_ns",
            "finished_time_ns",
            "command_sha256",
        },
        "diagnostic cleanup process",
    )
    watchdog = _require_exact_keys(
        packet["watchdog"],
        {"timeout_seconds", "grace_seconds", "cleanup"},
        "diagnostic cleanup watchdog",
    )
    cleanup = _require_exact_keys(
        watchdog["cleanup"],
        {"identity_safe", "term_sent", "kill_sent", "group_absent"},
        "diagnostic cleanup state",
    )
    if (
        type(expected_supervisor_pid) is not int
        or expected_supervisor_pid <= 1
        or process["supervisor_pid"] != expected_supervisor_pid
        or watchdog["timeout_seconds"] != TIMEOUT_SECONDS
        or watchdog["grace_seconds"] != GRACE_SECONDS
        or cleanup["identity_safe"] is not True
        or cleanup["group_absent"] is not True
        or any(type(item) is not bool for item in cleanup.values())
        or type(process["started_time_ns"]) is not int
        or type(process["finished_time_ns"]) is not int
        or process["finished_time_ns"] < process["started_time_ns"]
        or not isinstance(packet["signals"], list)
        or any(type(item) is not int for item in packet["signals"])
        or (status == "interrupted" and not packet["signals"])
    ):
        raise ContractError("diagnostic cleanup did not prove group absence")
    expected_command = [
        str(REMOTE_PYTHON),
        "-B",
        str(Path(__file__).resolve()),
        "worker",
        "--ordinal",
        str(expected_ordinal),
        "--device",
        str(packet["plan"]["device"]),
        "--role",
        packet["plan"]["role"],
        "--output",
        str(RESULT_ROOT / f"arm-{expected_ordinal:02d}.json"),
    ]
    expected_command_sha = hashlib.sha256(
        ("\0".join(expected_command) + "\0").encode()
    ).hexdigest()
    if process["command_sha256"] != expected_command_sha:
        raise ContractError("diagnostic cleanup command identity differs")
    worker_pid = process["worker_pid"]
    if worker_pid is None:
        if any(
            process[name] is not None
            for name in ("worker_pgid", "worker_start_ticks", "returncode")
        ):
            raise ContractError("diagnostic cleanup unspawned identity differs")
    else:
        if (
            type(worker_pid) is not int
            or worker_pid <= 1
            or type(process["worker_pgid"]) is not int
            or process["worker_pgid"] != worker_pid
            or type(process["worker_start_ticks"]) is not int
            or process["worker_start_ticks"] <= 0
            or not _load_campaign()._group_absent(process["worker_pgid"])
        ):
            raise ContractError("diagnostic worker group is still present")
    expected_paths = {
        "output": RESULT_ROOT / f"arm-{expected_ordinal:02d}.json",
        "log": RESULT_ROOT / f"arm-{expected_ordinal:02d}.supervisor.log",
        "supervisor_started": Path(f"{path}.phase-supervisor-started.json"),
        "preflight": Path(f"{path}.phase-preflight.json"),
        "before": Path(f"{path}.phase-before-spawn.json"),
        "spawned": Path(f"{path}.phase-spawned.json"),
    }
    artifacts = _require_exact_keys(
        packet["artifacts"], set(expected_paths), "diagnostic cleanup artifacts"
    )
    for name, expected_path in expected_paths.items():
        artifact = artifacts[name]
        required = (
            name == "supervisor_started"
            or (not preflight_failed and name in {"preflight", "before"})
            or (worker_pid is not None and name in {"log", "spawned"})
        )
        if artifact is None:
            if required:
                raise ContractError(f"diagnostic cleanup {name} artifact is absent")
            continue
        bound = _require_exact_keys(
            artifact, {"path", "sha256"}, f"diagnostic cleanup {name} artifact"
        )
        if (
            Path(bound["path"]) != expected_path
            or not expected_path.is_file()
            or expected_path.stat().st_mode & 0o222
            or bound["sha256"] != sha256_file(expected_path)
        ):
            raise ContractError(f"diagnostic cleanup {name} artifact differs")
    supervisor_started = load_json(expected_paths["supervisor_started"])
    _require_exact_keys(
        supervisor_started,
        {"schema", "phase", "time_ns", "supervisor_pid", "plan", "command_sha256"},
        "diagnostic cleanup supervisor-started receipt",
    )
    if (
        supervisor_started["schema"] != "qwen38-q64k32-remote-runtime-map-phase-v1"
        or supervisor_started["phase"] != "supervisor-started"
        or supervisor_started["supervisor_pid"] != expected_supervisor_pid
        or supervisor_started["plan"] != packet["plan"]
        or supervisor_started["command_sha256"] != expected_command_sha
        or type(supervisor_started["time_ns"]) is not int
    ):
        raise ContractError("diagnostic cleanup supervisor-started receipt differs")
    if preflight_failed:
        if (
            status not in {"invalid", "interrupted"}
            or worker_pid is not None
            or process["started_time_ns"] != supervisor_started["time_ns"]
            or any(
                artifacts[name] is not None
                for name in {"output", "log", "preflight", "before", "spawned"}
            )
            or not isinstance(packet["error"], str)
            or not packet["error"]
        ):
            raise ContractError("diagnostic preflight-failure terminal differs")
        return packet
    preflight_receipt = load_json(expected_paths["preflight"])
    before = load_json(expected_paths["before"])
    for receipt, phase in (
        (supervisor_started, "supervisor-started"),
        (before, "before-spawn"),
    ):
        _require_exact_keys(
            receipt,
            {"schema", "phase", "time_ns", "supervisor_pid", "plan", "command_sha256"},
            f"diagnostic cleanup {phase} receipt",
        )
        if (
            receipt["schema"] != "qwen38-q64k32-remote-runtime-map-phase-v1"
            or receipt["phase"] != phase
            or receipt["supervisor_pid"] != expected_supervisor_pid
            or receipt["plan"] != packet["plan"]
            or receipt["command_sha256"] != expected_command_sha
            or type(receipt["time_ns"]) is not int
        ):
            raise ContractError(f"diagnostic cleanup {phase} receipt differs")
    _require_exact_keys(
        preflight_receipt,
        {"schema", "phase", "time_ns", "supervisor_pid", "plan", "authorization"},
        "diagnostic cleanup preflight receipt",
    )
    if (
        preflight_receipt["schema"] != "qwen38-q64k32-remote-runtime-map-phase-v1"
        or preflight_receipt["phase"] != "preflight-complete"
        or preflight_receipt["supervisor_pid"] != expected_supervisor_pid
        or preflight_receipt["plan"] != packet["plan"]
        or preflight_receipt["authorization"] != packet["authorization"]
        or type(preflight_receipt["time_ns"]) is not int
        or not supervisor_started["time_ns"]
        <= preflight_receipt["time_ns"]
        <= before["time_ns"]
        == process["started_time_ns"]
    ):
        raise ContractError("diagnostic cleanup receipt chronology differs")
    if worker_pid is not None:
        spawned = _require_exact_keys(
            load_json(expected_paths["spawned"]),
            {
                "schema",
                "phase",
                "time_ns",
                "supervisor_pid",
                "worker_pid",
                "worker_pgid",
                "worker_start_ticks",
                "plan",
                "command_sha256",
            },
            "diagnostic cleanup spawned receipt",
        )
        if (
            spawned["schema"] != "qwen38-q64k32-remote-runtime-map-phase-v1"
            or spawned["phase"] != "spawned"
            or spawned["supervisor_pid"] != expected_supervisor_pid
            or spawned["worker_pid"] != worker_pid
            or spawned["worker_pgid"] != process["worker_pgid"]
            or spawned["worker_start_ticks"] != process["worker_start_ticks"]
            or spawned["plan"] != packet["plan"]
            or spawned["command_sha256"] != expected_command_sha
            or type(spawned["time_ns"]) is not int
            or not process["started_time_ns"]
            < spawned["time_ns"]
            <= process["finished_time_ns"]
        ):
            raise ContractError("diagnostic cleanup spawned receipt differs")
    return packet


def compare_command(args: argparse.Namespace) -> dict[str, Any]:
    post_authorization = diagnostic_preflight()
    terminals = [Path(path) for path in args.terminals]
    expected = [
        RESULT_ROOT / f"arm-{ordinal:02d}.terminal.json" for ordinal in range(1, 5)
    ]
    output = Path(args.output)
    if (
        terminals != expected
        or output != RESULT_ROOT / "comparison.json"
        or output.exists()
    ):
        raise ContractError("diagnostic comparison paths differ")
    preflight_path = RESULT_ROOT / "preflight-live-scan.json"
    preflight = validate_preflight_scan(preflight_path)
    packets: list[dict[str, Any]] = []
    terminal_packets: list[dict[str, Any]] = []
    for ordinal, terminal in enumerate(terminals, 1):
        terminal_packets.append(validate_terminal(terminal))
        packets.append(validate_arm(RESULT_ROOT / f"arm-{ordinal:02d}.json", ordinal))
    repo_heads = {
        preflight["authorization"]["repo_head"],
        post_authorization["repo_head"],
        *(packet["authorization"]["repo_head"] for packet in packets),
        *(packet["authorization"]["repo_head"] for packet in terminal_packets),
    }
    if len(repo_heads) != 1:
        raise ContractError("diagnostic repo identity changed across the sequence")
    process_ids = [packet["process"]["pid"] for packet in packets]
    if len(set(process_ids)) != 4:
        raise ContractError("diagnostic did not use four distinct worker processes")
    for prior, following in zip(terminal_packets, terminal_packets[1:]):
        if (
            prior["process"]["finished_time_ns"]
            >= following["process"]["started_time_ns"]
        ):
            raise ContractError("diagnostic arm chronology overlaps or is reordered")
    if (
        preflight["authorization"]["live_scan"]["captured_time_ns"]
        >= terminal_packets[0]["process"]["started_time_ns"]
        or post_authorization["live_scan"]["captured_time_ns"]
        <= terminal_packets[-1]["process"]["finished_time_ns"]
    ):
        raise ContractError("diagnostic overall scan chronology differs")
    after_maps = [
        {
            item["basename"]: {"path": item["path"], "sha256": item["sha256"]}
            for item in packet["runtime_maps_after_first_return_before_correctness"][
                "libraries"
            ]
        }
        for packet in packets
    ]
    before_maps = [
        {
            item["basename"]: {"path": item["path"], "sha256": item["sha256"]}
            for item in packet["runtime_maps_before_first_operator"]["libraries"]
        }
        for packet in packets
    ]
    common = sorted(set.intersection(*(set(mapping) for mapping in after_maps)))
    stable_common = {
        name: after_maps[0][name]
        for name in common
        if all(mapping[name] == after_maps[0][name] for mapping in after_maps[1:])
    }
    expected_inventory = {
        name: {"path": STATIC_RUNTIME_CANDIDATE_PATHS[name], "sha256": digest}
        for name, digest in sorted(STATIC_RUNTIME_CANDIDATES.items())
    }
    static_candidate_matches = {
        name: stable_common.get(name) == identity
        for name, identity in expected_inventory.items()
    }
    exact_map_match = all(mapping == expected_inventory for mapping in after_maps)
    observed_names = set().union(*(set(mapping) for mapping in after_maps))
    map_deltas = []
    for ordinal, (before_map, after_map) in enumerate(
        zip(before_maps, after_maps, strict=True), 1
    ):
        map_deltas.append(
            {
                "ordinal": ordinal,
                "added": {
                    name: after_map[name]
                    for name in sorted(set(after_map) - set(before_map))
                },
                "removed": {
                    name: before_map[name]
                    for name in sorted(set(before_map) - set(after_map))
                },
                "changed": {
                    name: {"before": before_map[name], "after": after_map[name]}
                    for name in sorted(set(before_map) & set(after_map))
                    if before_map[name] != after_map[name]
                },
            }
        )
    result = {
        "schema": "qwen38-q64k32-remote-runtime-map-comparison-v1",
        "passed": exact_map_match,
        "classification": (
            "valid-no-clock-runtime-map-match"
            if exact_map_match
            else "valid-no-clock-runtime-map-mismatch"
        ),
        "authorization": {
            "repo_head": post_authorization["repo_head"],
            "stage_inventory_sha256": post_authorization["stage_inventory_sha256"],
            "preflight_live_scan_path": str(preflight_path),
            "preflight_live_scan_sha256": sha256_file(preflight_path),
            "post_live_scan": post_authorization["live_scan"],
        },
        "terminal_sha256": [sha256_file(path) for path in terminals],
        "arm_sha256": [
            sha256_file(RESULT_ROOT / f"arm-{ordinal:02d}.json")
            for ordinal in range(1, 5)
        ],
        "stable_common_runtime_libraries": stable_common,
        "expected_runtime_libraries": expected_inventory,
        "before_to_after_runtime_map_deltas": map_deltas,
        "static_candidate_matches": static_candidate_matches,
        "static_candidate_map_complete": exact_map_match,
        "missing_expected_basenames": sorted(set(expected_inventory) - observed_names),
        "unexpected_relevant_basenames": sorted(
            observed_names - set(expected_inventory)
        ),
        "clock_mutation_commands_invoked": False,
        "absolute_timing_or_endpoint_claim_authorized": False,
    }
    write_json_atomic(output, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight")
    scan = sub.add_parser("scan")
    scan.add_argument("--output", required=True)
    worker = sub.add_parser("worker")
    worker.add_argument("--ordinal", type=int, required=True)
    worker.add_argument("--device", type=int, choices=(0, 1), required=True)
    worker.add_argument("--role", choices=("control", "candidate"), required=True)
    worker.add_argument("--output", required=True)
    supervise = sub.add_parser("supervise")
    supervise.add_argument("--ordinal", type=int, required=True)
    supervise.add_argument("--terminal", required=True)
    supervise.add_argument("command_args", nargs=argparse.REMAINDER)
    validate = sub.add_parser("validate-terminal")
    validate.add_argument("packet")
    cleanup_validate = sub.add_parser("validate-cleanup-terminal")
    cleanup_validate.add_argument("packet")
    cleanup_validate.add_argument("--ordinal", type=int, required=True)
    cleanup_validate.add_argument("--supervisor-pid", type=int, required=True)
    compare = sub.add_parser("compare")
    compare.add_argument("--output", required=True)
    compare.add_argument("terminals", nargs=4)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "preflight":
            print(json.dumps(diagnostic_preflight(), allow_nan=False, sort_keys=True))
        elif args.command == "scan":
            print(json.dumps(scan_command(args), allow_nan=False, sort_keys=True))
        elif args.command == "worker":
            print(json.dumps(worker_command(args), allow_nan=False, sort_keys=True))
        elif args.command == "supervise":
            args.command = args.command_args
            result = supervise_command(args)
            print(json.dumps(result, allow_nan=False, sort_keys=True))
            return 0 if result["valid"] is True else 1
        elif args.command == "validate-terminal":
            validate_terminal(Path(args.packet))
            print("PASS")
        elif args.command == "validate-cleanup-terminal":
            validate_cleanup_terminal(
                Path(args.packet), args.ordinal, args.supervisor_pid
            )
            print("PASS")
        elif args.command == "compare":
            result = compare_command(args)
            print(json.dumps(result, allow_nan=False, sort_keys=True))
            return 0 if result["passed"] is True else 1
        else:
            raise ContractError("unknown diagnostic command")
    except ContractError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail-closed sequential cold-unitrace runner for Laguna gate+up M=8 pairs.

Nothing operational happens without ``--execute`` and a hash-pinned,
packet-only tracked authorization child.  The runner is deliberately terminal:
the first preflight, arm, profiler, or closure failure seals an error manifest
and returns; it never retries an arm or a campaign.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gate_laguna_shared_gate_up_mm_counters as contract
import gate_laguna_shared_gate_up_mm_component as component_contract


MAIN = Path("/home/steve/llm-optimizations")
TOOLS = MAIN / "experiments/laguna-s-2.1-xpu-b70/tools"
RUNNER = Path(__file__).resolve()
FIXTURE = TOOLS / "profile_laguna_shared_gate_up_mm_counter_fixture.py"
ARTIFACT = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1")
RUNS = ARTIFACT / "runs"
VLLM, KERNELS, PTI = contract.VLLM, contract.KERNELS, contract.PTI
UNITRACE = contract.UNITRACE
PYTHON = Path("/home/steve/.venvs/deepseek-v4-xpu/bin/python")
XPU_SMI = Path("/usr/bin/xpu-smi")
SUDO, KILL = Path("/usr/bin/sudo"), Path("/usr/bin/kill")
ENV, TIMEOUT = Path("/usr/bin/env"), Path("/usr/bin/timeout")
SUDO_PASSWORD = Path("/home/steve/SUDOPASSWORD.txt")
ARMS, RANKS = ("A1", "B1", "B2", "A2"), (0, 1, 2, 3)
PAIRS, SELECTED_GEMMS = 13, 26
EVICTION_BYTES = 128 * 1024 * 1024
TIMEOUT_SECONDS, TERM_GRACE_SECONDS, KILL_GRACE_SECONDS = 200, 5, 5
DOWNSTREAM_FALSE = {
    "counter_gate_evaluated": False,
    "endpoint_preregistration_construction_authorized": False,
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


class CampaignAlreadyStarted(RuntimeError):
    """The packet-frozen one-shot root exists and must never be reused."""


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def sha_argument(value: str) -> str:
    value = value.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise argparse.ArgumentTypeError("expected a 64-digit SHA-256")
    return value


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def exclusive_json(path: Path, value: dict[str, Any]) -> None:
    payload = (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            require(written > 0, "short evidence write")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def exclusive_bytes(path: Path, value: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        pending = memoryview(value)
        while pending:
            written = os.write(fd, pending)
            require(written > 0, "short evidence write")
            pending = pending[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def command(
    argv: list[str], *, env: dict[str, str] | None = None, timeout: int = 30
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, check=False, capture_output=True, text=True, env=env, timeout=timeout
    )


def checked(
    argv: list[str], *, env: dict[str, str] | None = None, timeout: int = 30
) -> str:
    result = command(argv, env=env, timeout=timeout)
    require(
        result.returncode == 0,
        f"command failed {result.returncode}: {argv!r}: {result.stderr.strip()}",
    )
    return result.stdout


def git_identity(repo: Path, *, pti: bool = False) -> dict[str, Any]:
    status = checked(
        [
            "git",
            "-C",
            str(repo),
            "status",
            "--porcelain=v1",
            "--untracked-files=no" if pti else "--untracked-files=all",
        ]
    )
    return {
        "path": str(repo),
        "commit": checked(["git", "-C", str(repo), "rev-parse", "HEAD"]).strip(),
        "clean": not status.strip(),
        "status_sha256": hashlib.sha256(status.encode()).hexdigest(),
    }


def nvme_identity() -> dict[str, str]:
    found = checked(
        [
            "findmnt",
            "--noheadings",
            "--output",
            "SOURCE,FSTYPE",
            "--target",
            str(ARTIFACT),
        ]
    )
    require(
        f"{contract.EXPECTED['nvme_source']} {contract.EXPECTED['nvme_fstype']}"
        in found,
        "artifact root is not internal NVMe/ext4",
    )
    require(
        ARTIFACT.is_dir()
        and RUNS.is_dir()
        and not ARTIFACT.is_symlink()
        and not RUNS.is_symlink(),
        "unsafe artifact/runs root",
    )
    return {
        "target": str(ARTIFACT),
        "source": contract.EXPECTED["nvme_source"],
        "filesystem": contract.EXPECTED["nvme_fstype"],
    }


def tracked_packet(path: Path, expected: str) -> tuple[dict[str, Any], str]:
    require(
        path.is_absolute() and path.is_file() and not path.is_symlink(),
        "authorization must be an absolute regular file",
    )
    require(
        path.parent == MAIN / "data" and path.suffix == ".json",
        "authorization must be a tracked data packet",
    )
    digest = sha(path)
    require(digest == expected, "authorization SHA mismatch")
    relative = path.relative_to(MAIN)
    require(
        command(
            ["git", "-C", str(MAIN), "ls-files", "--error-unmatch", str(relative)]
        ).returncode
        == 0,
        "authorization is not Git tracked",
    )
    packet = json.loads(path.read_text())
    require(
        packet.get("format") == "laguna-shared-gate-up-m8-counter-authorization-v2",
        "wrong authorization format",
    )
    require(packet.get("packet_path") == str(path), "authorization packet path drift")
    require(
        path.read_bytes()
        == json.dumps(
            packet, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        + b"\n",
        "authorization bytes are noncanonical",
    )
    require(
        checked(["git", "-C", str(MAIN), "show", f"HEAD:{relative}"]).encode()
        == path.read_bytes(),
        "authorization differs from HEAD",
    )
    tracking = packet.get("authorization_tracking")
    require(
        isinstance(tracking, dict)
        and tracking.get("repository") == str(MAIN)
        and tracking.get("packet_repo_path") == str(relative),
        "authorization tracking drift",
    )
    require(
        tracking.get("runner_requirement")
        == "runner must require this exact packet as the clean immediate packet-only Git child of the committed tool freeze",
        "packet-only lineage requirement drift",
    )
    tools_commit = tracking.get("tools_commit")
    require(
        isinstance(tools_commit, str)
        and checked(["git", "-C", str(MAIN), "rev-parse", "HEAD^"]).strip()
        == tools_commit,
        "HEAD parent is not the frozen tools commit",
    )
    changed = checked(
        [
            "git",
            "-C",
            str(MAIN),
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            "HEAD",
        ]
    ).splitlines()
    require(changed == [str(relative)], "authorization child is not packet-only")
    require(git_identity(MAIN)["clean"], "main source tree is dirty")
    return packet, digest


def validate_packet(
    packet: dict[str, Any],
    packet_sha: str,
    *,
    require_fresh_campaign: bool = True,
) -> dict[str, Any]:
    require(
        packet.get("actions", {}).get("counter_execution_authorized") is True,
        "packet does not authorize counter execution",
    )
    require(
        packet.get("protocol") == contract.PROTOCOL
        and packet.get("acceptance") == contract.ACCEPTANCE,
        "pair counter protocol/acceptance drift",
    )
    protocol = packet["protocol"]
    require(
        protocol["pairs_per_arm"] == PAIRS
        and protocol["unitrace"]["selected_gemm_calls"] == SELECTED_GEMMS,
        "pair/GEMM count drift",
    )
    evidence = contract.component_evidence()
    require(
        packet.get("component_evidence") == evidence,
        "sealed component final evidence drift",
    )
    tools = packet.get("tooling")
    current_tools = contract.mandatory_tools()
    require(
        isinstance(tools, dict) and tools == current_tools,
        "packet mandatory tool set/hash drift",
    )
    for name, entry in tools.items():
        require(
            isinstance(entry, dict) and set(entry) == {"path", "sha256"},
            f"tool record drift: {name}",
        )
        path = (MAIN / entry["path"]).resolve()
        require(
            path.is_file()
            and not path.is_symlink()
            and (path.is_relative_to(TOOLS) or name == "tooling_contract_note")
            and sha(path) == entry["sha256"],
            f"tool hash drift: {name}",
        )
    require(
        tools["runner"]["path"] == str(RUNNER.relative_to(MAIN))
        and tools["fixture"]["path"] == str(FIXTURE.relative_to(MAIN)),
        "runner/fixture packet binding drift",
    )
    require(
        tools["runner"]["sha256"] == sha(RUNNER), "runner source differs from packet"
    )
    require(
        packet_sha == sha(Path(packet["packet_path"])),
        "packet hash changed during validation",
    )
    campaign = packet.get("campaign")
    require(
        isinstance(campaign, dict)
        and isinstance(campaign.get("root"), str)
        and Path(campaign["root"]).is_absolute(),
        "packet lacks frozen campaign paths",
    )
    require(
        campaign
        == contract.campaign_paths(
            Path(campaign["root"]), require_fresh=require_fresh_campaign
        ),
        "packet campaign paths/environments drift",
    )
    require(
        packet.get("identity") == contract.runtime_identity(),
        "packet runtime identity drift",
    )
    require(
        packet.get("actions") == contract.expected_actions(True),
        "packet action boundary drift",
    )
    return evidence


def source_preflight(packet: dict[str, Any]) -> dict[str, Any]:
    repos = {
        "main": git_identity(MAIN),
        "vllm": git_identity(VLLM),
        "kernels": git_identity(KERNELS),
        "pti": git_identity(PTI, pti=True),
    }
    require(
        all(value["clean"] for value in repos.values()), "source repository is dirty"
    )
    require(
        repos["vllm"]["commit"] == contract.EXPECTED["vllm_commit"]
        and repos["kernels"]["commit"] == contract.EXPECTED["kernel_commit"]
        and repos["pti"]["commit"] == contract.EXPECTED["pti_commit"],
        "source commit drift",
    )
    require(sha(UNITRACE) == contract.EXPECTED["unitrace_sha256"], "unitrace SHA drift")
    require(sha(FIXTURE) == packet["tooling"]["fixture"]["sha256"], "fixture SHA drift")
    identity = packet.get("identity")
    require(
        isinstance(identity, dict)
        and identity.get("unitrace", {}).get("sha256")
        == contract.EXPECTED["unitrace_sha256"],
        "packet runtime identity drift",
    )
    return {
        "captured_utc": now(),
        "repositories": repos,
        "packet_identity": identity,
        "runner": {"path": str(RUNNER), "sha256": sha(RUNNER)},
        "fixture": {"path": str(FIXTURE), "sha256": sha(FIXTURE)},
    }


def xpu_env(rank: int | None) -> dict[str, str]:
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    if rank is not None:
        env.update(
            {"ONEAPI_DEVICE_SELECTOR": "level_zero:0", "ZE_AFFINITY_MASK": str(rank)}
        )
    return env


def device_preflight(rank: int) -> dict[str, Any]:
    unfiltered_text = checked([str(XPU_SMI), "discovery", "-j"], env=xpu_env(None))
    filtered_text = checked([str(XPU_SMI), "discovery", "-j"], env=xpu_env(rank))
    unfiltered, filtered = json.loads(unfiltered_text), json.loads(filtered_text)
    expected = contract.CARDS[rank]
    all_devices = unfiltered.get("device_list")
    one_device = filtered.get("device_list")
    require(
        isinstance(all_devices, list)
        and len(all_devices) == 4
        and isinstance(one_device, list)
        and len(one_device) == 1,
        "XPU discovery count drift",
    )
    expected_all = [
        {
            "device_id": row["rank"],
            "uuid": row["uuid"],
            "pci_bdf_address": row["pci_bdf_address"],
            "drm_device": row["drm_device"],
            "device_name": row["device_name"],
        }
        for row in contract.CARDS
    ]
    require(
        [{key: row.get(key) for key in expected_all[0]} for row in all_devices]
        == expected_all,
        "unfiltered four-card physical mapping drift",
    )
    observed = one_device[0]
    require(
        observed.get("device_id") == 0
        and all(
            observed.get(key) == expected[key]
            for key in ("uuid", "pci_bdf_address", "drm_device", "device_name")
        ),
        "filtered physical card binding drift",
    )
    return {
        "rank": rank,
        "expected": expected,
        "filtered_text": filtered_text,
        "unfiltered_text": unfiltered_text,
        "filtered": filtered,
        "unfiltered": unfiltered,
        "uuid_bdf_binding_exact": True,
        "filtered_sha256": hashlib.sha256(filtered_text.encode()).hexdigest(),
        "unfiltered_sha256": hashlib.sha256(unfiltered_text.encode()).hexdigest(),
    }


def idle_preflight() -> dict[str, Any]:
    text = checked([str(XPU_SMI), "ps"], env=xpu_env(None))
    lines = [line.split() for line in text.splitlines() if line.strip()]
    require(
        bool(lines) and lines[0][:5] == ["PID", "Command", "DeviceID", "SHR", "MEM"],
        "invalid xpu-smi ps header",
    )
    rows = lines[1:]
    require(len(rows) == 4, "expected exactly four xpu-smi self rows")
    seen: dict[int, int] = {}
    for row in rows:
        require(
            len(row) >= 5
            and row[1] == "xpu-smi"
            and re.fullmatch(r"[0-3]", row[2]) is not None,
            "non-idle XPU client observed",
        )
        seen[int(row[2])] = seen.get(int(row[2]), 0) + 1
    require(seen == {0: 1, 1: 1, 2: 1, 3: 1}, "xpu-smi self-row device mapping drift")
    return {
        "text": text,
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "passed": True,
        "rows": 4,
        "only_xpu_smi_self_rows": True,
    }


def sudo_metadata() -> dict[str, Any]:
    require(
        SUDO_PASSWORD.is_file() and not SUDO_PASSWORD.is_symlink(),
        "sudo secret path/type drift",
    )
    meta = SUDO_PASSWORD.stat()
    require(
        stat.S_IMODE(meta.st_mode) == 0o600
        and meta.st_uid == os.getuid()
        and meta.st_size > 0,
        "sudo secret metadata drift",
    )
    return {
        "path": str(SUDO_PASSWORD),
        "mode": "0600",
        "uid": meta.st_uid,
        "regular_file": True,
        "content_not_recorded": True,
    }


def private_runtime_paths(arm: Path) -> dict[str, Path]:
    root = arm / "runtime"
    values = {
        "HOME": root / "home",
        "TMPDIR": root / "tmp",
        "TMP": root / "tmp",
        "TEMP": root / "tmp",
        "XDG_CACHE_HOME": root / "cache/xdg",
        "XDG_CONFIG_HOME": root / "cache/xdg-config",
        "XDG_DATA_HOME": root / "cache/xdg-data",
        "XDG_STATE_HOME": root / "cache/xdg-state",
        "PYTHONPYCACHEPREFIX": root / "cache/pycache",
        "SYCL_CACHE_DIR": root / "cache/sycl",
        "TORCHINDUCTOR_CACHE_DIR": root / "cache/torchinductor",
        "TRITON_CACHE_DIR": root / "cache/triton",
        "NUMBA_CACHE_DIR": root / "cache/numba",
        "HF_HOME": root / "cache/huggingface",
        "TRANSFORMERS_CACHE": root / "cache/transformers",
        "VLLM_CACHE_ROOT": root / "cache/vllm",
    }
    require(
        set(values)
        >= {"HOME", "TMPDIR", "TMP", "TEMP", "SYCL_CACHE_DIR", "PYTHONPYCACHEPREFIX"},
        "private runtime path inventory drift",
    )
    return values


def create_private_runtime(arm: Path) -> dict[str, Path]:
    values = private_runtime_paths(arm)
    for path in set(values.values()):
        path.mkdir(parents=True, mode=0o700, exist_ok=False)
    return values


def unitrace_argv(
    rank: int,
    arm: str,
    arm_dir: Path,
    fixture_sha: str,
    authorization_sha: str,
    protocol_sha: str,
) -> list[str]:
    treatment = "control" if arm.startswith("A") else "candidate"
    environment = component_contract.environment(str(arm_dir), rank)
    require(
        {
            key: str(value) for key, value in private_runtime_paths(arm_dir).items()
        }.items()
        <= environment.items(),
        "component contract lacks private runtime paths",
    )
    assignments = [f"{key}={environment[key]}" for key in sorted(environment)]
    return [
        str(SUDO),
        "-S",
        "-p",
        "",
        "-E",
        "--",
        str(ENV),
        "-i",
        *assignments,
        str(TIMEOUT),
        "--signal=TERM",
        "--kill-after=5s",
        "180s",
        str(UNITRACE),
        "--device-timing",
        "--metric-query",
        "--group",
        "ComputeBasic",
        "--include-kernels",
        "gemm_kernel",
        "--verbose",
        "--pid",
        "--devices-to-sample",
        "0",
        "--output",
        "unitrace",
        str(PYTHON),
        str(FIXTURE),
        "--rank",
        str(rank),
        "--arm",
        treatment,
        "--expected-fixture-sha256",
        fixture_sha,
        "--authorization-sha256",
        authorization_sha,
        "--protocol-sha256",
        protocol_sha,
        "--out",
        str(arm_dir / "fixture.json"),
    ]


def validate_unitrace_argv(
    argv: list[str],
    *,
    rank: int,
    treatment: str,
    fixture_sha: str,
    authorization_sha: str,
    protocol_sha: str,
    fixture_output: Path,
) -> None:
    env_index = argv.index(str(ENV))
    timeout_index = argv.index(str(TIMEOUT))
    normalized = [
        *argv[: env_index + 2],
        "{sorted_child_environment_assignments}",
        *argv[timeout_index:],
    ]
    replacements = {
        "--rank": "{rank}",
        "--arm": "{treatment}",
        "--expected-fixture-sha256": "{fixture_sha256}",
        "--authorization-sha256": "{authorization_sha256}",
        "--protocol-sha256": "{protocol_sha256}",
        "--out": "{fixture_output}",
    }
    observed = {
        "--rank": str(rank),
        "--arm": treatment,
        "--expected-fixture-sha256": fixture_sha,
        "--authorization-sha256": authorization_sha,
        "--protocol-sha256": protocol_sha,
        "--out": str(fixture_output),
    }
    for flag, placeholder in replacements.items():
        position = normalized.index(flag) + 1
        require(
            normalized[position] == observed[flag],
            f"unitrace argv dynamic value drift: {flag}",
        )
        normalized[position] = placeholder
    require(
        normalized == contract.child_command_template(),
        "unitrace argv differs from the frozen packet template",
    )


def profiler_outputs(arm: Path) -> tuple[Path, Path, str]:
    names = sorted(
        path.name
        for path in arm.iterdir()
        if path.is_file() and path.name.startswith("unitrace")
    )
    timing = [name for name in names if re.fullmatch(r"unitrace\.\d+", name)]
    metrics = [name for name in names if re.fullmatch(r"unitrace\.metrics\.\d+", name)]
    require(
        len(names) == 2
        and len(timing) == len(metrics) == 1
        and timing[0].split(".")[1] == metrics[0].split(".")[2],
        "unitrace timing/metrics PID file closure drift",
    )
    suffix = timing[0].split(".")[1]
    timing_path, metrics_path = arm / timing[0], arm / metrics[0]
    require(
        all(
            path.is_file() and not path.is_symlink() and path.stat().st_size > 0
            for path in (timing_path, metrics_path)
        ),
        "unitrace profiler output is empty, irregular, or symlinked",
    )
    return timing_path, metrics_path, suffix


def group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def signal_group(pgid: int, sig: signal.Signals) -> None:
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        return
    except PermissionError:
        with SUDO_PASSWORD.open("rb") as secret:
            result = subprocess.run(
                [
                    str(SUDO),
                    "-S",
                    "-p",
                    "",
                    "--",
                    str(KILL),
                    "--signal",
                    sig.name.removeprefix("SIG"),
                    "--",
                    f"-{pgid}",
                ],
                stdin=secret,
                capture_output=True,
                check=False,
                timeout=10,
            )
        require(
            result.returncode == 0 or not group_exists(pgid),
            "privileged process-group cleanup failed",
        )


def require_group_gone(pgid: int, *, context: str) -> None:
    if group_exists(pgid):
        signal_group(pgid, signal.SIGTERM)
        deadline = time.monotonic() + TERM_GRACE_SECONDS
        while group_exists(pgid) and time.monotonic() < deadline:
            time.sleep(0.02)
    if group_exists(pgid):
        signal_group(pgid, signal.SIGKILL)
        deadline = time.monotonic() + KILL_GRACE_SECONDS
        while group_exists(pgid) and time.monotonic() < deadline:
            time.sleep(0.02)
    require(not group_exists(pgid), f"{context} process group survived cleanup")


def bounded(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    execution_state: dict[str, bool],
) -> tuple[bytes, bytes, int]:
    require(
        execution_state == {"profiler_process_started": False},
        "profiler execution-state envelope drift",
    )
    with SUDO_PASSWORD.open("rb") as stdin:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        execution_state["profiler_process_started"] = True
        require(
            os.getpgid(process.pid) == process.pid,
            "runner did not receive a private process group",
        )
        try:
            stdout, stderr = process.communicate(timeout=TIMEOUT_SECONDS)
            require(
                isinstance(process.returncode, int),
                "profiler supervisor did not produce a return code",
            )
            if group_exists(process.pid):
                require_group_gone(process.pid, context="completed profiler")
                raise RuntimeError(
                    "completed profiler left a live process-group descendant"
                )
            return stdout, stderr, process.returncode
        except subprocess.TimeoutExpired:
            signal_group(process.pid, signal.SIGTERM)
            try:
                stdout, stderr = process.communicate(timeout=TERM_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                signal_group(process.pid, signal.SIGKILL)
                try:
                    stdout, stderr = process.communicate(timeout=KILL_GRACE_SECONDS)
                finally:
                    require_group_gone(process.pid, context="timed-out profiler")
            else:
                require_group_gone(process.pid, context="timed-out profiler")
            return stdout, stderr, 124
        except BaseException:
            require_group_gone(process.pid, context="failed profiler")
            raise


def merge_execution_state(
    campaign_state: dict[str, bool],
    arm_state: dict[str, bool],
) -> None:
    require(
        set(campaign_state) == set(arm_state) == {"profiler_process_started"}
        and all(
            isinstance(value, bool)
            for value in (*campaign_state.values(), *arm_state.values())
        ),
        "profiler execution-state schema drift",
    )
    campaign_state["profiler_process_started"] = (
        campaign_state["profiler_process_started"]
        or arm_state["profiler_process_started"]
    )


def arm(
    root: Path,
    rank: int,
    name: str,
    packet: dict[str, Any],
    packet_sha: str,
    protocol_sha: str,
    campaign_execution_state: dict[str, bool],
) -> dict[str, Any]:
    treatment = "control" if name.startswith("A") else "candidate"
    arm_dir = root / f"card{rank}" / name
    arm_dir.mkdir(parents=True, mode=0o700)
    command_argv: list[str] = []
    stdout = stderr = b""
    returncode: int | None = None
    arm_execution_state = {"profiler_process_started": False}
    try:
        runtime = create_private_runtime(arm_dir)
        expected_environment = component_contract.environment(str(arm_dir), rank)
        planned = [
            entry
            for entry in packet["campaign"]["arms"]
            if entry.get("rank") == rank and entry.get("arm") == name
        ]
        require(
            planned
            == [
                {
                    "rank": rank,
                    "arm": name,
                    "arm_dir": str(arm_dir),
                    "fixture_output": str(arm_dir / "fixture.json"),
                    "environment": expected_environment,
                }
            ],
            "packet-frozen arm path/environment drift",
        )
        require(
            {key: str(value) for key, value in runtime.items()}.items()
            <= expected_environment.items(),
            "component contract/runtime tree drift",
        )
        preflight = {
            "format": "laguna-shared-gate-up-m8-counter-arm-preflight-v1",
            "status": "passed",
            "rank": rank,
            "arm": name,
            "treatment": treatment,
            "authorization_path": packet["packet_path"],
            "authorization_sha256": packet_sha,
            "protocol_sha256": protocol_sha,
            "source": source_preflight(packet),
            "physical_device": device_preflight(rank),
            "idle": idle_preflight(),
            "mount": nvme_identity(),
            "sudo_password_file": sudo_metadata(),
            "environment": expected_environment,
        }
        exclusive_json(arm_dir / "preflight.json", preflight)
        command_argv = unitrace_argv(
            rank,
            name,
            arm_dir,
            packet["tooling"]["fixture"]["sha256"],
            packet_sha,
            protocol_sha,
        )
        validate_unitrace_argv(
            command_argv,
            rank=rank,
            treatment=treatment,
            fixture_sha=packet["tooling"]["fixture"]["sha256"],
            authorization_sha=packet_sha,
            protocol_sha=protocol_sha,
            fixture_output=arm_dir / "fixture.json",
        )
        stdout, stderr, returncode = bounded(
            command_argv,
            cwd=arm_dir,
            env={
                "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
            },
            execution_state=arm_execution_state,
        )
        merge_execution_state(campaign_execution_state, arm_execution_state)
        exclusive_bytes(arm_dir / "stdout.log", stdout)
        exclusive_bytes(arm_dir / "stderr.log", stderr)
        require(returncode == 0, f"unitrace arm exited {returncode}")
        fixture_path = arm_dir / "fixture.json"
        require(
            fixture_path.is_file() and not fixture_path.is_symlink(),
            "fixture output is missing, irregular, or symlinked",
        )
        fixture_raw = fixture_path.read_bytes()
        fixture = json.loads(fixture_raw)
        require(
            fixture_raw == contract.canonical(fixture) + b"\n",
            "fixture output is not canonical JSON",
        )
        require(
            fixture.get("format") == "laguna-shared-gate-up-mm-cold-counter-fixture-v2"
            and fixture.get("status") == "fixture-complete"
            and fixture.get("rank") == rank
            and fixture.get("arm") == treatment
            and fixture.get("authorization_sha256") == packet_sha
            and fixture.get("protocol_sha256") == protocol_sha
            and fixture.get("fixture_source_sha256")
            == packet["tooling"]["fixture"]["sha256"]
            and fixture.get("selected_pair_invocations") == PAIRS
            and fixture.get("selected_gemm_calls") == SELECTED_GEMMS
            and fixture.get("pair_order") == ["gate_proj", "up_proj"]
            and fixture.get("identity", {}).get("environment") == expected_environment,
            "canonical fixture-v2 closure drift",
        )
        boundary = fixture.get("boundary_sha256")
        pair_hashes = fixture.get("all_pair_output_sha256")
        require(
            isinstance(boundary, dict)
            and set(boundary) == {"gate", "up"}
            and all(is_sha256(value) for value in boundary.values())
            and isinstance(pair_hashes, list)
            and pair_hashes
            == [
                {
                    "pair": str(index),
                    "gate": boundary["gate"],
                    "up": boundary["up"],
                }
                for index in range(PAIRS)
            ],
            "fixture pair-output exactness closure drift",
        )
        timing, metrics, suffix = profiler_outputs(arm_dir)
        require(
            str(fixture["identity"]["pid"]) == suffix,
            "unitrace PID does not bind the fixture process",
        )
        post_idle = idle_preflight()
        exclusive_json(arm_dir / "post-arm-idle.json", post_idle)
        evidence = [
            arm_dir / "preflight.json",
            arm_dir / "stdout.log",
            arm_dir / "stderr.log",
            arm_dir / "fixture.json",
            timing,
            metrics,
            arm_dir / "post-arm-idle.json",
        ]
        files = {
            path.name: {
                "path": str(path),
                "sha256": sha(path),
                "bytes": path.stat().st_size,
            }
            for path in evidence
        }
        manifest = {
            "format": "laguna-shared-gate-up-m8-counter-arm-manifest-v1",
            "status": "complete",
            "completed_utc": now(),
            "rank": rank,
            "arm": name,
            "treatment": treatment,
            "authorization_path": packet["packet_path"],
            "authorization_sha256": packet_sha,
            "protocol_sha256": protocol_sha,
            "command": command_argv,
            "environment": expected_environment,
            "cwd": str(arm_dir),
            "returncode": returncode,
            "unitrace_output_pid_suffix": suffix,
            "runtime_subtree": {
                "path": str(arm_dir / "runtime"),
                "private": True,
                "excluded_from_evidence_hashes": True,
            },
            "files": files,
            "fixture": fixture,
            "counter_execution_performed": True,
            **DOWNSTREAM_FALSE,
        }
        path = arm_dir / "manifest.json"
        exclusive_json(path, manifest)
        return {
            "rank": rank,
            "arm": name,
            "treatment": treatment,
            "path": str(path),
            "sha256": sha(path),
        }
    except BaseException as error:
        merge_execution_state(campaign_execution_state, arm_execution_state)
        for path, data in (
            (arm_dir / "stdout.log", stdout),
            (arm_dir / "stderr.log", stderr),
        ):
            if not path.exists():
                exclusive_bytes(path, data)
        exclusive_json(
            arm_dir / "arm.error.json",
            {
                "format": "laguna-shared-gate-up-m8-counter-arm-error-v1",
                "status": "partial-error",
                "failed_utc": now(),
                "rank": rank,
                "arm": name,
                "treatment": treatment,
                "authorization_path": packet["packet_path"],
                "authorization_sha256": packet_sha,
                "protocol_sha256": protocol_sha,
                "command": command_argv,
                "returncode": returncode,
                "error": repr(error),
                "counter_execution_performed": arm_execution_state[
                    "profiler_process_started"
                ],
                **DOWNSTREAM_FALSE,
            },
        )
        raise


def seal_pre_root_failure(
    path: Path,
    *,
    root: Path,
    packet: dict[str, Any],
    packet_sha: str,
    status: str,
    error: BaseException,
) -> None:
    require(
        path.parent == RUNS and not path.exists() and not path.is_symlink(),
        "packet preflight-failure path drift",
    )
    exclusive_json(
        path,
        {
            "format": "laguna-shared-gate-up-m8-counter-preflight-failure-v1",
            "status": status,
            "failed_utc": now(),
            "campaign_root": str(root),
            "authorization_path": packet["packet_path"],
            "authorization_sha256": packet_sha,
            "error": repr(error),
            "counter_execution_performed": False,
            **DOWNSTREAM_FALSE,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--authorization-json", type=Path, required=True)
    parser.add_argument(
        "--expected-authorization-sha256", type=sha_argument, required=True
    )
    args = parser.parse_args()
    require(
        args.execute, "refusing operational counter work without explicit --execute"
    )
    packet, packet_sha = tracked_packet(
        args.authorization_json, args.expected_authorization_sha256
    )
    campaign = packet.get("campaign")
    require(
        isinstance(campaign, dict)
        and isinstance(campaign.get("root"), str)
        and isinstance(campaign.get("preflight_failure"), str),
        "packet campaign paths are missing",
    )
    root = Path(campaign["root"])
    preflight_failure = Path(campaign["preflight_failure"])
    root_observed = False
    try:
        validate_packet(packet, packet_sha, require_fresh_campaign=False)
        require(
            args.campaign_root == root
            and root.is_absolute()
            and root.parent == RUNS
            and re.fullmatch(
                r"shared-gate-up-m8-counters-[0-9]{8}T[0-9]{6}Z", root.name
            )
            is not None
            and Path(campaign["intent"]) == root / "campaign.intent.json"
            and Path(campaign["abandoned"]) == root / "campaign.abandoned.json",
            "campaign root must equal the packet-frozen direct NVMe runs child",
        )
        if root.exists() or root.is_symlink():
            root_observed = True
            require(
                root.is_dir() and not root.is_symlink(),
                "existing packet-frozen campaign root is unsafe",
            )
            abandoned_path = Path(campaign["abandoned"])
            already_terminal = any(
                (root / name).exists() or (root / name).is_symlink()
                for name in (
                    "campaign.complete.json",
                    "campaign.error.json",
                    "campaign.abandoned.json",
                )
            )
            if not already_terminal:
                intent_path = Path(campaign["intent"])
                intent_present = intent_path.exists() or intent_path.is_symlink()
                intent_valid = False
                intent_error = None
                if intent_path.is_file() and not intent_path.is_symlink():
                    try:
                        intent_raw = intent_path.read_bytes()
                        intent = json.loads(intent_raw)
                        intent_valid = (
                            isinstance(intent, dict)
                            and intent_raw == contract.canonical(intent) + b"\n"
                            and intent.get("format")
                            == "laguna-shared-gate-up-m8-counter-campaign-intent-v1"
                            and intent.get("campaign_root") == str(root)
                            and intent.get("authorization_sha256") == packet_sha
                        )
                        if not intent_valid:
                            intent_error = "existing campaign intent drift"
                    except (OSError, TypeError, ValueError) as error:
                        intent_error = repr(error)
                elif intent_present:
                    intent_error = "existing campaign intent is irregular or symlinked"
                exclusive_json(
                    abandoned_path,
                    {
                        "format": "laguna-shared-gate-up-m8-counter-abandoned-v1",
                        "status": "counter-failed-abandoned-after-root-stop-before-endpoint",
                        "failed_utc": now(),
                        "campaign_root": str(root),
                        "authorization_path": packet["packet_path"],
                        "authorization_sha256": packet_sha,
                        "intent": (
                            {
                                "path": str(intent_path),
                                "sha256": (
                                    sha(intent_path)
                                    if intent_path.is_file()
                                    and not intent_path.is_symlink()
                                    else None
                                ),
                                "valid": intent_valid,
                                "error": intent_error,
                            }
                            if intent_present
                            else None
                        ),
                        "reason": "packet-frozen one-shot root already existed; no rerun performed",
                        "counter_execution_state": (
                            "unknown_after_campaign_intent"
                            if intent_present
                            else "not_started_before_campaign_intent"
                        ),
                        "counter_execution_performed": (
                            None if intent_present else False
                        ),
                        **DOWNSTREAM_FALSE,
                    },
                )
            raise CampaignAlreadyStarted(
                "packet-frozen campaign root already existed and is terminal"
            )
        require(
            not preflight_failure.exists()
            and not preflight_failure.is_symlink()
            and not root.is_symlink(),
            "campaign root/preflight-failure paths are not fresh",
        )
        mount, source = nvme_identity(), source_preflight(packet)
        pre_root = {
            "devices": [device_preflight(rank) for rank in RANKS],
            "idle": idle_preflight(),
            "sudo_password_file": sudo_metadata(),
        }
    except CampaignAlreadyStarted as error:
        print(f"FAIL-CLOSED: {error}", file=sys.stderr)
        return 2
    except BaseException as error:
        if root_observed:
            print(
                f"FAIL-CLOSED: existing one-shot campaign root is unusable: {error}",
                file=sys.stderr,
            )
            return 2
        seal_pre_root_failure(
            preflight_failure,
            root=root,
            packet=packet,
            packet_sha=packet_sha,
            status="counter-failed-stop-before-root",
            error=error,
        )
        raise
    protocol_sha = canonical_sha(packet["protocol"])
    intent_path = Path(packet["campaign"]["intent"])
    open_path = Path(packet["campaign"]["open"])
    cards: list[dict[str, Any]] = []
    arms: list[dict[str, Any]] = []
    campaign_execution_state = {"profiler_process_started": False}
    try:
        root.mkdir(mode=0o755)
        runs_fd = os.open(RUNS, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(runs_fd)
        finally:
            os.close(runs_fd)
        exclusive_json(
            intent_path,
            {
                "format": "laguna-shared-gate-up-m8-counter-campaign-intent-v1",
                "status": "started",
                "created_utc": now(),
                "campaign_root": str(root),
                "authorization_path": packet["packet_path"],
                "authorization_sha256": packet_sha,
                "protocol_sha256": protocol_sha,
                "counter_execution_performed": False,
                **DOWNSTREAM_FALSE,
            },
        )
        opened = {
            "format": "laguna-shared-gate-up-m8-counter-campaign-open-v1",
            "status": "open",
            "created_utc": now(),
            "campaign_root": str(root),
            "authorization_path": packet["packet_path"],
            "authorization_sha256": packet_sha,
            "packet_actions": packet["actions"],
            "protocol": packet["protocol"],
            "protocol_sha256": protocol_sha,
            "acceptance": packet["acceptance"],
            "component_evidence": packet["component_evidence"],
            "tooling": packet["tooling"],
            "identity": packet["identity"],
            "campaign_specification": packet["campaign"],
            "campaign_intent": {
                "path": str(intent_path),
                "sha256": sha(intent_path),
            },
            "source": source,
            "mount": mount,
            "pre_root_preflight": pre_root,
            "planned_cards": list(RANKS),
            "planned_arms_per_card": list(ARMS),
            "counter_execution_performed": False,
            **DOWNSTREAM_FALSE,
        }
        exclusive_json(open_path, opened)
        for rank in RANKS:
            entries = [
                arm(
                    root,
                    rank,
                    name,
                    packet,
                    packet_sha,
                    protocol_sha,
                    campaign_execution_state,
                )
                for name in ARMS
            ]
            arms.extend(entries)
            post_card_idle_path = root / f"card{rank}" / "post-card-idle.json"
            exclusive_json(post_card_idle_path, idle_preflight())
            card_path = root / f"card{rank}" / "card.manifest.json"
            exclusive_json(
                card_path,
                {
                    "format": "laguna-shared-gate-up-m8-counter-card-manifest-v1",
                    "status": "complete",
                    "completed_utc": now(),
                    "rank": rank,
                    "authorization_sha256": packet_sha,
                    "protocol_sha256": protocol_sha,
                    "arms": entries,
                    "post_card_idle": {
                        "path": str(post_card_idle_path),
                        "sha256": sha(post_card_idle_path),
                    },
                    "counter_execution_performed": True,
                    **DOWNSTREAM_FALSE,
                },
            )
            cards.append(
                {"rank": rank, "path": str(card_path), "sha256": sha(card_path)}
            )
        complete = Path(packet["campaign"]["complete"])
        final_idle_path = root / "final-idle.json"
        exclusive_json(final_idle_path, idle_preflight())
        exclusive_json(
            complete,
            {
                "format": "laguna-shared-gate-up-m8-counter-campaign-complete-v1",
                "status": "complete",
                "completed_utc": now(),
                "campaign_root": str(root),
                "authorization_path": packet["packet_path"],
                "authorization_sha256": packet_sha,
                "protocol_sha256": protocol_sha,
                "campaign_open": {
                    "path": str(open_path),
                    "sha256": sha(open_path),
                },
                "cards": cards,
                "arms": arms,
                "final_idle": {
                    "path": str(final_idle_path),
                    "sha256": sha(final_idle_path),
                },
                "counter_execution_performed": True,
                **DOWNSTREAM_FALSE,
            },
        )
        print(
            json.dumps(
                {
                    "status": "complete",
                    "campaign_root": str(root),
                    "campaign_complete_sha256": sha(complete),
                },
                sort_keys=True,
            )
        )
        return 0
    except BaseException as error:
        if not root.is_dir() or root.is_symlink():
            seal_pre_root_failure(
                preflight_failure,
                root=root,
                packet=packet,
                packet_sha=packet_sha,
                status="counter-failed-stop-during-root-transition",
                error=error,
            )
            raise
        error_path = root / "campaign.error.json"
        exclusive_json(
            error_path,
            {
                "format": "laguna-shared-gate-up-m8-counter-campaign-error-v1",
                "status": "partial-error",
                "failed_utc": now(),
                "campaign_root": str(root),
                "authorization_path": packet["packet_path"],
                "authorization_sha256": packet_sha,
                "protocol_sha256": protocol_sha,
                "campaign_open": (
                    {"path": str(open_path), "sha256": sha(open_path)}
                    if open_path.is_file() and not open_path.is_symlink()
                    else None
                ),
                "campaign_intent": (
                    {"path": str(intent_path), "sha256": sha(intent_path)}
                    if intent_path.is_file() and not intent_path.is_symlink()
                    else None
                ),
                "completed_cards": cards,
                "completed_arms": arms,
                "error": repr(error),
                "counter_execution_started": campaign_execution_state[
                    "profiler_process_started"
                ],
                "counter_execution_performed": campaign_execution_state[
                    "profiler_process_started"
                ],
                **DOWNSTREAM_FALSE,
            },
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())

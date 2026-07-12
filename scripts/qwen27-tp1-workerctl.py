#!/usr/bin/env python3
"""Control persistent, independent Qwen27 TP1 development workers.

Mutating commands are dry-run by default. This controller owns only processes
whose PID files it created and never treats persistent/warm work as promotion
evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "experiments/qwen27-dflash-sycl-b70/harness/workers.json"


def admitted_ram_cache(config: dict[str, Any], role: str) -> Path | None:
    """Return a byte-identical cached GGUF only after local identity admission."""
    common = config.get("common", {})
    if not common.get("prefer_ram_model_cache", False):
        return None
    source_key = "target_model" if role == "target" else "draft_model"
    sha_key = f"{role}_model_sha256"
    source = Path(config[source_key])
    expected_sha = config[sha_key]
    root = Path(common.get("ram_model_cache_root", "/dev/shm/qwen27-b70-model-cache"))
    cached = root / expected_sha / source.name
    metadata_path = cached.parent / "cache-entry.json"
    try:
        metadata = load_config(metadata_path)
        expected_size = source.stat().st_size
        actual_size = cached.stat().st_size
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None
    if (
        metadata.get("schema_version") != 1
        or metadata.get("format") != "byte-identical-gguf-ram-cache"
        or metadata.get("source", {}).get("sha256") != expected_sha
        or metadata.get("cached", {}).get("sha256") != expected_sha
        or metadata.get("cached", {}).get("size_bytes") != expected_size
        or actual_size != expected_size
    ):
        return None
    stat = cached.stat()
    admission = metadata.get("admission", {})
    if (
        admission.get("sha256") != expected_sha
        or admission.get("size_bytes") != stat.st_size
        or admission.get("mtime_ns") != stat.st_mtime_ns
        or admission.get("ctime_ns") != stat.st_ctime_ns
    ):
        return None
    return cached


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def worker_dir(config: dict[str, Any], worker: dict[str, Any]) -> Path:
    return Path(config["runtime_root"]) / "workers" / worker["name"]


def pid_state(path: Path) -> tuple[str, int | None]:
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return "absent", None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return "stale", pid
    except PermissionError:
        return "unverifiable", pid
    cmdline = proc_bytes(Path("/proc") / str(pid) / "cmdline")
    if b"llama-server" not in cmdline and b"serve-qwen36-27b-mtp-gguf-llamacpp.sh" not in cmdline:
        return "pid-reused-or-unowned", pid
    return "running", pid


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


def proc_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return b""


def foreign_llama_pids(gpu: int, managed_pid: int | None) -> list[int]:
    """Find llama processes that select this GPU or have ambiguous affinity."""
    found: list[int] = []
    proc = Path("/proc")
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == managed_pid:
            continue
        argv = [value for value in proc_bytes(entry / "cmdline").split(b"\0") if value]
        if not argv:
            continue
        executable = Path(os.fsdecode(argv[0])).name
        wrapper = any(
            Path(os.fsdecode(value)).name == "serve-qwen36-27b-mtp-gguf-llamacpp.sh"
            for value in argv[1:2]
        )
        if not executable.startswith("llama-") and not wrapper:
            continue
        environ = proc_bytes(entry / "environ").split(b"\0")
        affinity = f"ZE_AFFINITY_MASK={gpu}".encode()
        has_affinity = any(value.startswith(b"ZE_AFFINITY_MASK=") for value in environ)
        if affinity in environ or not has_affinity:
            found.append(pid)
    return sorted(found)


def selected_workers(config: dict[str, Any], name: str | None) -> list[dict[str, Any]]:
    workers = config["workers"]
    if name is None:
        return workers
    matches = [worker for worker in workers if worker["name"] == name]
    if not matches:
        raise ValueError(f"unknown worker: {name}")
    return matches


def resolved(config: dict[str, Any], worker: dict[str, Any]) -> dict[str, Any]:
    common = config["common"]
    profile = config["profiles"][worker["profile"]]
    common_extra = common.get("extra_llama_args", "").strip()
    profile_extra = profile.get("extra_llama_args", "").format(
        draft_model=config["draft_model"]
    ).strip()
    extra = " ".join(part for part in (common_extra, profile_extra) if part)
    target_model = admitted_ram_cache(config, "target") or Path(config["target_model"])
    draft_model = admitted_ram_cache(config, "draft") or Path(config["draft_model"])
    env = {
        "GPU_INDEX": str(worker["gpu"]),
        "ZE_AFFINITY_MASK": str(worker["gpu"]),
        "ONEAPI_DEVICE_SELECTOR": "level_zero:*",
        "PORT": str(worker["port"]),
        "HOST": str(common["host"]),
        "MODEL": str(target_model),
        "MODEL_ALIAS": config["model_alias"],
        "LLAMA_SERVER": config["binary"],
        "CTX_SIZE": str(common["ctx_size"]),
        "BATCH_SIZE": str(common["batch_size"]),
        "UBATCH_SIZE": str(common["ubatch_size"]),
        "N_PARALLEL": str(common["n_parallel"]),
        "FLASH_ATTN": str(common["flash_attn"]),
        "CACHE_TYPE_K": str(common["cache_type_k"]),
        "CACHE_TYPE_V": str(common["cache_type_v"]),
        "ENABLE_MTP": "1" if profile.get("enable_mtp", False) else "0",
        "SPEC_TYPE": str(profile.get("spec_type", "none")),
        "SPEC_N_MAX": str(profile.get("spec_n_max", profile.get("mtp_n_max", 3))),
        "SPEC_N_MIN": str(profile.get("spec_n_min", profile.get("mtp_n_min", 0))),
        "SPEC_P_MIN": str(profile.get("spec_p_min", profile.get("mtp_p_min", 0.0))),
        "DRAFT_MODEL": str(profile.get("draft_model", "")).format(
            draft_model=str(draft_model)
        ),
        "MTP_N_MAX": str(profile.get("mtp_n_max", 3)),
        "MTP_N_MIN": str(profile.get("mtp_n_min", 0)),
        "MTP_P_MIN": str(profile.get("mtp_p_min", 0.0)),
        "EXTRA_LLAMA_ARGS": extra,
        "OUT_DIR": str(worker_dir(config, worker)),
        "LOG": str(worker_dir(config, worker) / "server.log"),
    }
    env.update({str(k): str(v) for k, v in common.get("environment", {}).items()})
    command = [config["launcher"]]
    return {"environment": env, "command": command, "profile": profile}


def validate(config: dict[str, Any], config_path: Path) -> list[str]:
    errors: list[str] = []
    required = [
        "runtime_root", "launcher", "binary", "target_model", "draft_model",
        "common", "profiles", "workers",
    ]
    for key in required:
        if key not in config:
            errors.append(f"missing top-level key: {key}")
    if errors:
        return errors
    if config.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if len(config["workers"]) != 4:
        errors.append("exactly four TP1 workers are required")
    names = [worker.get("name") for worker in config["workers"]]
    gpus = [worker.get("gpu") for worker in config["workers"]]
    ports = [worker.get("port") for worker in config["workers"]]
    if len(set(names)) != len(names):
        errors.append("worker names must be unique")
    if sorted(gpus) != [0, 1, 2, 3]:
        errors.append("workers must map exactly once to physical GPUs 0,1,2,3")
    if len(set(ports)) != len(ports):
        errors.append("worker ports must be unique")
    for worker in config["workers"]:
        if worker.get("profile") not in config["profiles"]:
            errors.append(f"{worker.get('name')}: unknown profile {worker.get('profile')}")
    for name, profile in config["profiles"].items():
        if profile.get("spec_type") not in ("none", "draft-mtp", "draft-simple", "draft-dflash"):
            errors.append(f"{name}: unsupported spec_type {profile.get('spec_type')}")
    if config["common"].get("n_parallel") != 1:
        errors.append("n_parallel must remain 1 for independent TP1 workers")
    extra = config["common"].get("extra_llama_args", "")
    if "--cache-ram 0" not in extra:
        errors.append("common args must disable the prompt cache")
    if config["common"].get("environment", {}).get("SYCL_CACHE_PERSISTENT") == "1":
        errors.append("SYCL_CACHE_PERSISTENT=1 is forbidden on this B70 system")
    for key in ("launcher", "binary", "target_model", "draft_model"):
        if not Path(config[key]).is_file():
            errors.append(f"missing {key}: {config[key]}")
    if Path(config["launcher"]).is_file():
        launcher_text = Path(config["launcher"]).read_text(encoding="utf-8")
        for marker in ("draft-simple", "GGML_SYCL_ENABLE_GRAPH", "--ctx-checkpoints 0"):
            if marker not in launcher_text:
                errors.append(f"launcher is missing required behavior marker: {marker}")
    if not config_path.is_file():
        errors.append(f"missing config: {config_path}")
    harness_dir = config_path.parent
    model_pack_path = harness_dir / "model-pack-manifest.json"
    golden_path = harness_dir / "golden-corpus-manifest.json"
    try:
        model_pack = load_config(model_pack_path)
        if model_pack.get("source", {}).get("path") != config["target_model"]:
            errors.append("model-pack source path must match the worker target model")
        if model_pack.get("source", {}).get("sha256") != config["target_model_sha256"]:
            errors.append("model-pack source sha256 must match the worker target identity")
        if model_pack.get("draft_source", {}).get("sha256") != config["draft_model_sha256"]:
            errors.append("model-pack draft sha256 must match the worker draft identity")
        if model_pack.get("target_architecture") != "bmg-g31":
            errors.append("model-pack target_architecture must be bmg-g31")
        if model_pack.get("format_status") not in (
            "manifest-only", "byte-identical-ram-cache-implemented"
        ):
            errors.append("unsupported model-pack format_status")
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        errors.append(f"invalid model-pack manifest: {exc}")
    try:
        golden = load_config(golden_path)
        if golden.get("evidence_class") != "diagnostic-only":
            errors.append("golden corpus must be labeled diagnostic-only")
        if golden.get("promotion_eligible") is not False:
            errors.append("golden corpus must be ineligible for promotion")
        if golden.get("source_identity", {}).get("target_model_sha256") != config["target_model_sha256"]:
            errors.append("golden corpus target identity must match the worker target")
        forbidden = golden.get("reset_policy", {}).get("forbidden_for", [])
        for use in ("strict-realistic-promotion", "localmaxxing-submission", "headline-throughput"):
            if use not in forbidden:
                errors.append(f"golden reset policy must forbid {use}")
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        errors.append(f"invalid golden-corpus manifest: {exc}")
    return errors


def status_rows(config: dict[str, Any], workers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    host = config["common"]["host"]
    for worker in workers:
        state, pid = pid_state(worker_dir(config, worker) / "server.pid")
        rows.append({
            "name": worker["name"],
            "role": worker["role"],
            "profile": worker["profile"],
            "gpu": worker["gpu"],
            "port": worker["port"],
            "pid": pid,
            "pid_state": state,
            "port_open": port_open(host, worker["port"]),
            "foreign_llama_pids": foreign_llama_pids(worker["gpu"], pid),
            "evidence_class": "development-screen-only"
        })
    return rows


def render_command(config: dict[str, Any], worker: dict[str, Any]) -> str:
    item = resolved(config, worker)
    assignments = " ".join(
        f"{key}={shlex.quote(value)}" for key, value in sorted(item["environment"].items())
    )
    command = " ".join(shlex.quote(arg) for arg in item["command"])
    return f"{assignments} {command}"


def start_worker(config: dict[str, Any], worker: dict[str, Any], execute: bool) -> bool:
    directory = worker_dir(config, worker)
    pidfile = directory / "server.pid"
    state, pid = pid_state(pidfile)
    host = config["common"]["host"]
    foreign = foreign_llama_pids(worker["gpu"], pid)
    if state == "running":
        print(f"BLOCK {worker['name']}: managed pid {pid} is already running", file=sys.stderr)
        return False
    if port_open(host, worker["port"]):
        print(f"BLOCK {worker['name']}: port {worker['port']} is already open", file=sys.stderr)
        return False
    if foreign:
        print(
            f"BLOCK {worker['name']}: unmanaged llama process(es) explicitly pinned "
            f"to GPU {worker['gpu']}: {foreign}", file=sys.stderr,
        )
        return False
    command_text = render_command(config, worker)
    if not execute:
        print(f"DRY-RUN start {worker['name']}: {command_text}")
        return True
    directory.mkdir(parents=True, exist_ok=True)
    item = resolved(config, worker)
    environment = os.environ.copy()
    environment.update(item["environment"])
    stdout = (directory / "controller.stdout.log").open("ab")
    process = subprocess.Popen(
        item["command"], cwd=ROOT, env=environment, stdin=subprocess.DEVNULL,
        stdout=stdout, stderr=subprocess.STDOUT, start_new_session=True,
    )
    pidfile.write_text(f"{process.pid}\n", encoding="utf-8")
    identity = {
        "started_unix": time.time(),
        "worker": worker,
        "resolved": item,
        "evidence_class": "development-screen-only",
        "promotion_eligible": False,
    }
    (directory / "resolved-identity.json").write_text(
        json.dumps(identity, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"STARTED {worker['name']} pid={process.pid} log={directory / 'server.log'}")
    return True


def stop_worker(config: dict[str, Any], worker: dict[str, Any], execute: bool) -> bool:
    pidfile = worker_dir(config, worker) / "server.pid"
    state, pid = pid_state(pidfile)
    if state != "running" or pid is None:
        print(f"SKIP {worker['name']}: managed process is {state}")
        return True
    if not execute:
        print(f"DRY-RUN stop {worker['name']}: send SIGTERM to managed pid {pid}")
        return True
    os.kill(pid, signal.SIGTERM)
    print(f"STOP-SENT {worker['name']} pid={pid}")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("validate", "status", "render", "start", "stop")
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--worker")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    errors = validate(config, args.config)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    workers = selected_workers(config, args.worker)
    if args.command == "validate":
        print(f"OK: {args.config} defines four independent TP1 workers")
        return 0
    if args.command == "status":
        rows = status_rows(config, workers)
        if args.json:
            print(json.dumps(rows, indent=2, sort_keys=True))
        else:
            for row in rows:
                print(
                    f"{row['name']}: gpu={row['gpu']} port={row['port']} "
                    f"profile={row['profile']} pid={row['pid_state']} "
                    f"endpoint={'open' if row['port_open'] else 'closed'} "
                    f"foreign={row['foreign_llama_pids']} evidence=screen-only"
                )
        return 0
    if args.command == "render":
        for worker in workers:
            print(f"# {worker['name']} ({worker['role']})")
            print(render_command(config, worker))
        return 0
    action = start_worker if args.command == "start" else stop_worker
    return 0 if all(action(config, worker, args.execute) for worker in workers) else 1


if __name__ == "__main__":
    raise SystemExit(main())

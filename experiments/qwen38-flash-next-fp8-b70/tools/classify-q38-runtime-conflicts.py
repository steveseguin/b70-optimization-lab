#!/usr/bin/env python3
"""Classify live Qwen/vLLM owners with PID-identity and read-error receipts."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path


MODEL_PATH = "/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    ppid: int
    starttime: int


class ProcessReadError(RuntimeError):
    def __init__(self, pid: int, field: str, detail: str):
        super().__init__(detail)
        self.pid = pid
        self.field = field
        self.detail = detail


def read_required(path: Path, pid: int, field: str) -> bytes:
    try:
        return path.read_bytes()
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError) as exc:
        raise ProcessReadError(pid, field, f"{type(exc).__name__}: {exc}") from exc


def parse_stat(raw: bytes, pid: int, field: str) -> ProcessIdentity:
    text = raw.decode("utf-8", "replace").strip()
    right = text.rfind(")")
    if right < 0:
        raise ProcessReadError(pid, field, "missing closing comm parenthesis")
    parts = text[right + 1 :].split()
    if len(parts) < 20:
        raise ProcessReadError(pid, field, "fewer than 22 stat fields")
    try:
        parsed_pid = int(text.split(" ", 1)[0])
        ppid = int(parts[1])
        starttime = int(parts[19])
    except ValueError as exc:
        raise ProcessReadError(pid, field, f"invalid integer: {exc}") from exc
    if parsed_pid != pid:
        raise ProcessReadError(pid, field, f"stat PID {parsed_pid} does not match directory")
    return ProcessIdentity(pid=pid, ppid=ppid, starttime=starttime)


def read_identity(proc_dir: Path, pid: int, *, after: bool = False) -> ProcessIdentity:
    path = proc_dir / ("stat.after" if after and (proc_dir / "stat.after").exists() else "stat")
    return parse_stat(read_required(path, pid, "stat-after" if after else "stat"), pid,
                      "stat-after" if after else "stat")


def read_status_ppid(proc_dir: Path, pid: int) -> int:
    text = read_required(proc_dir / "status", pid, "status").decode("utf-8", "replace")
    values = [line.split(":", 1)[1].strip() for line in text.splitlines()
              if line.startswith("PPid:")]
    if len(values) != 1 or not values[0].isdigit():
        raise ProcessReadError(pid, "status", "requires exactly one numeric PPid")
    return int(values[0])


def read_command(proc_dir: Path, pid: int) -> tuple[list[str], str]:
    raw = read_required(proc_dir / "cmdline", pid, "cmdline")
    tokens = [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]
    comm = read_required(proc_dir / "comm", pid, "comm").decode("utf-8", "replace").strip()
    if not comm:
        raise ProcessReadError(pid, "comm", "empty comm")
    return tokens, comm


def has_script_token(proc_dir: Path, pid: int, tokens: list[str], script: Path) -> bool:
    expected = script.resolve()
    if any(Path(token).is_absolute() and Path(token).resolve() == expected for token in tokens):
        return True
    try:
        cwd = Path(os.readlink(proc_dir / "cwd"))
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError) as exc:
        raise ProcessReadError(pid, "cwd", f"{type(exc).__name__}: {exc}") from exc
    return any(not Path(token).is_absolute() and (cwd / token).resolve() == expected
               for token in tokens if token and not token.startswith("-"))


def adjacent(tokens: list[str], left: str, right: str) -> bool:
    return any(Path(tokens[index]).name == left and tokens[index + 1] == right
               for index in range(len(tokens) - 1))


def classify(tokens: list[str], comm: str) -> str | None:
    basenames = [Path(token).name for token in tokens]
    if comm.startswith("VLLM::Worker") or comm == "VLLM::Worker":
        return "vllm-named-worker"
    if comm in {"APIServer", "VLLM::APIServ", "VLLM::APIServer"}:
        return "vllm-named-api-server"
    if comm in {"EngineCore", "VLLM::EngineCor", "VLLM::EngineCore"}:
        return "vllm-named-engine-core"
    if adjacent(tokens, "vllm", "serve"):
        return "vllm-serve"
    if any(name == "api_server.py" for name in basenames) and any(
        "vllm" in token for token in tokens
    ):
        return "vllm-api-server"
    if any(tokens[index] == "-m" and tokens[index + 1].startswith("vllm.")
           for index in range(len(tokens) - 1)):
        return "vllm-python-module"
    if any(tokens[index] == "-m" and tokens[index + 1] == "torch.distributed.run"
           for index in range(len(tokens) - 1)):
        return "torch-distributed-run"
    if "xccl_probe.py" in basenames:
        return "xccl-probe"
    if MODEL_PATH in tokens and any(
        name.startswith("python") or name == "vllm" for name in basenames
    ):
        return "flash-next-model-owner"
    return None


def structurally_bound_exclusions(
    proc_root: Path,
    scanner_pid: int,
    supervisor_pid: int,
    supervisor_starttime: int,
    supervisor_script: Path,
) -> tuple[set[int], dict[str, object]]:
    scanner = read_identity(proc_root / str(scanner_pid), scanner_pid)
    supervisor_dir = proc_root / str(supervisor_pid)
    supervisor = read_identity(supervisor_dir, supervisor_pid)
    supervisor_status_ppid = read_status_ppid(supervisor_dir, supervisor_pid)
    supervisor_tokens, supervisor_comm = read_command(supervisor_dir, supervisor_pid)
    if scanner.ppid != supervisor_pid:
        raise ProcessReadError(scanner_pid, "binding", "scanner is not a direct child of supervisor")
    if supervisor.starttime != supervisor_starttime:
        raise ProcessReadError(supervisor_pid, "binding", "supervisor starttime changed or PID was reused")
    if supervisor.ppid != supervisor_status_ppid:
        raise ProcessReadError(supervisor_pid, "binding", "supervisor stat/status PPid mismatch")
    if not has_script_token(supervisor_dir, supervisor_pid, supervisor_tokens, supervisor_script):
        raise ProcessReadError(supervisor_pid, "binding", "exact supervisor script token is absent")
    supervisor_positive = classify(supervisor_tokens, supervisor_comm)

    parent_dir = proc_root / str(supervisor.ppid)
    parent = read_identity(parent_dir, supervisor.ppid)
    parent_status_ppid = read_status_ppid(parent_dir, supervisor.ppid)
    parent_tokens, parent_comm = read_command(parent_dir, supervisor.ppid)
    if parent.ppid != parent_status_ppid:
        raise ProcessReadError(parent.pid, "binding", "parent stat/status PPid mismatch")
    parent_positive = classify(parent_tokens, parent_comm)

    receipt = {
        "scanner": scanner.__dict__,
        "supervisor": {**supervisor.__dict__, "comm": supervisor_comm,
                       "script": str(supervisor_script.resolve()),
                       "runtime_positive": supervisor_positive},
        "direct_parent": {**parent.__dict__, "comm": parent_comm,
                          "runtime_positive": parent_positive},
        "excluded_pids": [scanner_pid, supervisor_pid, parent.pid],
    }
    return {scanner_pid, supervisor_pid, parent.pid}, receipt


def scan_process(
    proc_dir: Path, pid: int, excluded: set[int]
) -> tuple[dict[str, object] | None, dict[str, object] | None, dict[str, object] | None]:
    before: ProcessIdentity | None = None
    try:
        before = read_identity(proc_dir, pid)
        status_ppid = read_status_ppid(proc_dir, pid)
        tokens, comm = read_command(proc_dir, pid)
        after = read_identity(proc_dir, pid, after=True)
        if before != after:
            raise ProcessReadError(pid, "pid-reuse", "identity changed during scan")
        if before.ppid != status_ppid:
            raise ProcessReadError(pid, "ppid", "stat/status PPid mismatch")
        reason = classify(tokens, comm)
        # A runtime-positive process is always a conflict, even if its PID is
        # structurally excluded. Exclusion only suppresses non-runtime owners.
        if reason is not None:
            return ({"pid": pid, "ppid": before.ppid, "starttime": before.starttime,
                     "comm": comm, "reason": reason, "argv": tokens,
                     "was_structurally_excluded": pid in excluded}, None,
                    {**before.__dict__, "comm": comm,
                     "was_structurally_excluded": pid in excluded})
        return (None, None, {**before.__dict__, "comm": comm,
                             "was_structurally_excluded": pid in excluded})
    except ProcessReadError as exc:
        return (None, {"pid": exc.pid, "field": exc.field, "detail": exc.detail,
                       "observed_identity": before.__dict__ if before is not None else None,
                       "was_structurally_excluded": pid in excluded}, None)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proc-root", type=Path, default=Path("/proc"))
    parser.add_argument("--supervisor-pid", type=int, required=True)
    parser.add_argument("--supervisor-starttime", type=int, required=True)
    parser.add_argument("--supervisor-script", type=Path, required=True)
    parser.add_argument("--scanner-pid", type=int)
    parser.add_argument("--binding-only", action="store_true")
    args = parser.parse_args()

    live_proc = args.proc_root.resolve() == Path("/proc")
    if live_proc and args.scanner_pid is not None:
        parser.error("--scanner-pid is fixture-only")
    scanner_pid = os.getpid() if args.scanner_pid is None else args.scanner_pid
    conflicts: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    scanned_processes: list[dict[str, object]] = []
    binding: dict[str, object] | None = None
    excluded: set[int] = set()
    try:
        excluded, binding = structurally_bound_exclusions(
            args.proc_root, scanner_pid, args.supervisor_pid,
            args.supervisor_starttime, args.supervisor_script)
    except ProcessReadError as exc:
        errors.append({"pid": exc.pid, "field": exc.field, "detail": exc.detail,
                       "was_structurally_excluded": False})

    if not errors and not args.binding_only:
        try:
            proc_dirs = sorted(
                (path for path in args.proc_root.iterdir() if path.name.isdigit()),
                key=lambda path: int(path.name),
            )
        except OSError as exc:
            errors.append({"pid": None, "field": "proc-root",
                           "detail": f"{type(exc).__name__}: {exc}",
                           "was_structurally_excluded": False})
            proc_dirs = []
        for proc_dir in proc_dirs:
            pid = int(proc_dir.name)
            conflict, error, observed = scan_process(proc_dir, pid, excluded)
            if conflict is not None:
                conflicts.append(conflict)
            if error is not None:
                errors.append(error)
            if observed is not None:
                scanned_processes.append(observed)

    if errors and conflicts:
        status, rc = "error-and-conflict", 2
    elif errors:
        status, rc = "error", 2
    elif conflicts:
        status, rc = "conflict", 1
    else:
        status, rc = "clear", 0
    output = {
        "schema": "neural.download.q38-runtime-conflict-scan.v2",
        "proc_root": str(args.proc_root),
        "binding_only": args.binding_only,
        "binding": binding,
        "conflicts": conflicts,
        "errors": errors,
        "scanned_processes": scanned_processes,
        "status": status,
    }
    print(json.dumps(output, sort_keys=True, indent=2))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

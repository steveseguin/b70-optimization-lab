#!/usr/bin/env python3
"""Bounded executor for model-written Python, for the coding accuracy evals.

HumanEval and MBPP cannot be scored without running code the model wrote. This
module is the only place in the accuracy harness that does that, and it is
default-off: ``eval_laguna_accuracy`` refuses code-execution scorers unless
``--enable-code-execution`` is passed explicitly.

What this actually is
---------------------

This is a **robustness** boundary, not a security boundary, and the difference
matters on this host, which holds weeks of campaign evidence and a 72 GB
checkpoint. It reliably contains the failure modes a language model actually
produces -- infinite loops, runaway allocation, accidental recursion, a stray
``input()``, a test that spawns processes, a program that prints forever -- via:

* a fresh session (``setsid``) so the whole descendant tree can be killed;
* ``RLIMIT_CPU`` (hard CPU cap, independent of wall clock);
* ``RLIMIT_AS`` (address space);
* ``RLIMIT_NPROC`` (fork containment, auto-sized above the host's current
  *task* count so a legitimate single-process program can still fork);
* ``RLIMIT_FSIZE`` (bounds both file writes and the captured output, because
  stdout and stderr are files);
* ``RLIMIT_CORE`` zero;
* a wall-clock timeout followed by ``SIGKILL`` to the whole process group;
* a scrubbed environment (no inherited ``HF_*``, tokens, proxies, or caches),
  ``python -I`` isolated mode, and a throwaway working directory that is also
  ``HOME`` and ``TMPDIR``;
* a socket-neutering preamble prepended to the program.

It does **not** contain a deliberate attacker. The preamble is monkeypatching
inside the same interpreter and can be undone by code that wants to. There is no
filesystem namespace, so the program can read anything this user can read.

For a real boundary, pass ``use_network_namespace=True`` to wrap execution in
``unshare -n -r``. That was probed on 2026-08-03 and **failed** in the agent's
own restricted shell with ``write failed /proc/self/uid_map: Operation not
permitted``; whether it succeeds in an unrestricted login shell on this host is
NOT established. :func:`probe_network_namespace` answers that at runtime, and
:func:`run_untrusted_python` refuses rather than silently degrading if the
namespace was requested and is unavailable.

Nothing here loads a model, contacts an endpoint, or touches a device.
"""

from __future__ import annotations

import json
import os
import resource
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = "laguna-accuracy-sandbox-v1"

STATUS_PASSED = "PASSED"
STATUS_FAILED = "FAILED"
STATUS_TIMEOUT = "TIMEOUT"
STATUS_SIGNALLED = "SIGNALLED"
STATUS_REFUSED = "REFUSED"

# Prepended to every program. Defense in depth against a test that reaches for
# the network by accident (a doctest that fetches a URL, a solution that imports
# something which phones home). Not a security control.
NETWORK_PREAMBLE = """\
import socket as _socket


def _laguna_sandbox_denied(*_args, **_kwargs):
    raise OSError("network access is disabled in the Laguna accuracy sandbox")


_socket.socket = _laguna_sandbox_denied
_socket.create_connection = _laguna_sandbox_denied
_socket.socketpair = _laguna_sandbox_denied
_socket.getaddrinfo = _laguna_sandbox_denied
del _socket
"""


@dataclass(frozen=True)
class SandboxPolicy:
    """Every limit, in one recorded object. Written into the score record."""

    timeout_s: float = 10.0
    cpu_seconds: int = 10
    address_space_bytes: int = 2 * 1024 * 1024 * 1024
    file_size_bytes: int = 1 * 1024 * 1024
    extra_processes: int = 8
    disable_network: bool = True
    use_network_namespace: bool = False

    def as_record(self) -> dict[str, Any]:
        return {
            "timeout_s": self.timeout_s,
            "cpu_seconds": self.cpu_seconds,
            "address_space_bytes": self.address_space_bytes,
            "file_size_bytes": self.file_size_bytes,
            "extra_processes": self.extra_processes,
            "disable_network": self.disable_network,
            "use_network_namespace": self.use_network_namespace,
        }


@dataclass(frozen=True)
class SandboxResult:
    status: str
    returncode: int | None
    signal_name: str | None
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool
    duration_s: float
    detail: str | None = None

    @property
    def passed(self) -> bool:
        return self.status == STATUS_PASSED

    def as_record(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "returncode": self.returncode,
            "signal_name": self.signal_name,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "stdout_truncated": self.stdout_truncated,
            "stderr_truncated": self.stderr_truncated,
            "duration_s": self.duration_s,
            "detail": self.detail,
        }


def count_user_tasks(proc_root: Path = Path("/proc"), uid: int | None = None) -> int:
    """Count this user's *tasks*, for sizing ``RLIMIT_NPROC``.

    ``RLIMIT_NPROC`` is checked per real UID against every task the user already
    has, and on Linux a thread is a task. Counting only ``/proc/<pid>`` entries
    undercounts, because that lists thread-group leaders only -- which is how an
    earlier draft of this file produced a limit so low that a legitimate
    single-process program could not ``fork`` at all. Every thread under
    ``/proc/<pid>/task`` is counted instead.

    The limit is sized relative to the current count rather than set to a small
    absolute value, because an absolute value would fail the very first ``fork``
    on a busy host.
    """

    target = os.getuid() if uid is None else uid
    total = 0
    try:
        names = os.listdir(proc_root)
    except OSError:
        return 0
    for name in names:
        if not name.isdigit():
            continue
        entry = proc_root / name
        try:
            if entry.stat().st_uid != target:
                continue
            total += len(os.listdir(entry / "task"))
        except OSError:
            continue
    return total


def probe_network_namespace(timeout_s: float = 5.0) -> dict[str, Any]:
    """Report whether ``unshare -n -r`` actually works here.

    Runs ``unshare -n -r true``: a plain userspace command with no device, no
    model, no elevation. Returns a record rather than raising, so a caller can
    record the answer instead of assuming one.
    """

    binary = shutil.which("unshare")
    if binary is None:
        return {"available": False, "reason": "unshare is not on PATH"}
    try:
        completed = subprocess.run(
            [binary, "-n", "-r", "true"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return {"available": False, "reason": f"unshare failed to start: {error}"}
    if completed.returncode == 0:
        return {"available": True, "reason": None, "unshare_path": binary}
    return {
        "available": False,
        "reason": completed.stderr.decode("utf-8", errors="replace").strip()
        or f"unshare exited {completed.returncode}",
        "unshare_path": binary,
    }


def _limits(policy: SandboxPolicy, nproc_limit: int):
    def apply() -> None:  # pragma: no cover - runs in the forked child
        os.setsid()
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(
            resource.RLIMIT_CPU, (policy.cpu_seconds, policy.cpu_seconds)
        )
        resource.setrlimit(
            resource.RLIMIT_AS,
            (policy.address_space_bytes, policy.address_space_bytes),
        )
        resource.setrlimit(
            resource.RLIMIT_FSIZE,
            (policy.file_size_bytes, policy.file_size_bytes),
        )
        resource.setrlimit(resource.RLIMIT_NPROC, (nproc_limit, nproc_limit))

    return apply


def build_argv(
    policy: SandboxPolicy, python_executable: str, program_path: Path
) -> list[str]:
    """The exact argv, split out so it is testable without executing anything."""

    argv = [python_executable, "-I", str(program_path)]
    if policy.use_network_namespace:
        return ["unshare", "-n", "-r", *argv]
    return argv


def build_environment(workdir: Path) -> dict[str, str]:
    """A scrubbed environment. Nothing is inherited from the caller."""

    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(workdir),
        "TMPDIR": str(workdir),
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONUNBUFFERED": "1",
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }


def _read_capped(path: Path, cap: int) -> tuple[str, bool]:
    try:
        raw = path.read_bytes()
    except OSError:
        return "", False
    # ``>=`` rather than ``>``: RLIMIT_FSIZE stops the writer *at* the cap, so a
    # stream that reached exactly the cap was almost certainly cut short.
    if len(raw) >= cap:
        return raw[:cap].decode("utf-8", errors="replace"), True
    return raw.decode("utf-8", errors="replace"), False


def run_untrusted_python(
    source: str,
    *,
    policy: SandboxPolicy | None = None,
    python_executable: str | None = None,
    proc_root: Path = Path("/proc"),
) -> SandboxResult:
    """Run ``source`` under :class:`SandboxPolicy` and report what happened.

    ``PASSED`` means exit status zero. Everything else -- a failed assertion, a
    timeout, a signal, a refusal -- is a distinct status and is never collapsed
    into ``PASSED``.
    """

    policy = policy or SandboxPolicy()
    interpreter = python_executable or "python3"

    if policy.use_network_namespace:
        probe = probe_network_namespace()
        if not probe["available"]:
            return SandboxResult(
                status=STATUS_REFUSED,
                returncode=None,
                signal_name=None,
                stdout="",
                stderr="",
                stdout_truncated=False,
                stderr_truncated=False,
                duration_s=0.0,
                detail=(
                    "a network namespace was required but is unavailable: "
                    f"{probe['reason']}"
                ),
            )

    program = (NETWORK_PREAMBLE + "\n" + source) if policy.disable_network else source
    nproc_limit = count_user_tasks(proc_root) + policy.extra_processes
    workdir = Path(tempfile.mkdtemp(prefix="laguna-eval-sandbox-"))
    started = time.perf_counter()
    try:
        program_path = workdir / "program.py"
        program_path.write_text(program, encoding="utf-8")
        stdout_path = workdir / "stdout.txt"
        stderr_path = workdir / "stderr.txt"
        argv = build_argv(policy, interpreter, program_path)
        with (
            stdout_path.open("wb") as stdout_handle,
            stderr_path.open("wb") as stderr_handle,
        ):
            try:
                process = subprocess.Popen(  # noqa: S603 - argv is fully constructed
                    argv,
                    cwd=workdir,
                    env=build_environment(workdir),
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    preexec_fn=_limits(policy, nproc_limit),  # noqa: PLW1509
                    close_fds=True,
                )
            except OSError as error:
                return SandboxResult(
                    status=STATUS_REFUSED,
                    returncode=None,
                    signal_name=None,
                    stdout="",
                    stderr="",
                    stdout_truncated=False,
                    stderr_truncated=False,
                    duration_s=time.perf_counter() - started,
                    detail=f"sandbox process could not start: {error}",
                )
            timed_out = False
            try:
                process.wait(timeout=policy.timeout_s)
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_group(process)
        duration = time.perf_counter() - started
        cap = policy.file_size_bytes
        stdout, stdout_truncated = _read_capped(stdout_path, cap)
        stderr, stderr_truncated = _read_capped(stderr_path, cap)
        returncode = process.returncode
        if timed_out:
            status = STATUS_TIMEOUT
            detail = f"exceeded the {policy.timeout_s}s wall-clock limit"
            signal_name = None
        elif returncode is not None and returncode < 0:
            status = STATUS_SIGNALLED
            signal_name = signal.Signals(-returncode).name
            detail = f"terminated by {signal_name}"
        elif returncode == 0:
            status = STATUS_PASSED
            signal_name = None
            detail = None
        else:
            status = STATUS_FAILED
            signal_name = None
            detail = f"exited with status {returncode}"
        return SandboxResult(
            status=status,
            returncode=returncode,
            signal_name=signal_name,
            stdout=stdout,
            stderr=stderr,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            duration_s=duration,
            detail=detail,
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _kill_group(process: subprocess.Popen[bytes]) -> None:
    """SIGKILL the whole session, then reap. A fork bomb has no survivors."""

    try:
        group = os.getpgid(process.pid)
    except OSError:
        group = None
    if group is not None:
        try:
            os.killpg(group, signal.SIGKILL)
        except OSError:
            pass
    try:
        process.kill()
    except OSError:
        pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:  # pragma: no cover - defensive
        pass


def sandbox_report(policy: SandboxPolicy | None = None) -> dict[str, Any]:
    policy = policy or SandboxPolicy()
    return {
        "schema": SCHEMA,
        "policy": policy.as_record(),
        "network_namespace_probe": probe_network_namespace(),
        "boundary_class": "robustness, not security",
        "boundary_note": (
            "Contains loops, allocation, forks, output floods and accidental "
            "network use. Does not contain a deliberate attacker: there is no "
            "filesystem namespace and the socket preamble runs in the same "
            "interpreter as the program it restricts."
        ),
    }


def main() -> int:
    print(json.dumps(sandbox_report(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

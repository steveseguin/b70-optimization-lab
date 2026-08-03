#!/home/steve/.venvs/deepseek-v4-xpu/bin/python
"""Reproduce why post-setproctitle /proc/PID/environ is not an env proof.

This is deliberately CPU-only and records counts rather than environment
contents so the evidence cannot capture unrelated credentials.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path


SENTINEL_NAME = "LAGUNA_SETPROCTITLE_SENTINEL"
SENTINEL_VALUE = "present-before-and-after-title-change"
PROCESS_TITLE = "VLLM::Worker_Test"
VLLM_ROOT = "/home/steve/src/laguna-vllm-exact-small-portfolio-20260801"
EXPECTED_VLLM_COMMIT = "0c9dea8cf9aa46c1854d5bce8f4dfb180732b16d"
EXPECTED_SYSTEM_UTILS_SHA256 = (
    "f22b8d420dcfde31f92114d7f5b916797d5dcce4b840bfddfc99d287ce185452"
)
EXPECTED_DELEGATION = 'setproctitle.setproctitle(f"{prefix}::{name}")'
SIGNAL_TIMEOUT_SECONDS = 10.0


def summarize_proc_environ(pid: int) -> dict[str, int | bool]:
    payload = Path(f"/proc/{pid}/environ").read_bytes()
    entries = [part for part in payload.split(b"\0") if part]
    sentinel = f"{SENTINEL_NAME}={SENTINEL_VALUE}".encode()
    return {
        "byte_count": len(payload),
        "nul_separated_positions": len(payload.split(b"\0")),
        "nonempty_entries": len(entries),
        "sentinel_present": sentinel in entries,
    }


def run_child(
    pre_ready_fd: int, continue_fd: int, post_ready_fd: int, finish_fd: int
) -> int:
    import setproctitle

    before = os.getenv(SENTINEL_NAME)
    os.write(pre_ready_fd, b"1")
    os.read(continue_fd, 1)
    setproctitle.setproctitle(PROCESS_TITLE)
    after = os.getenv(SENTINEL_NAME)
    os.write(post_ready_fd, b"1")
    os.read(finish_fd, 1)
    json.dump(
        {
            "getenv_before_title": before,
            "getenv_after_title": after,
            "reported_process_title": setproctitle.getproctitle(),
        },
        sys.stdout,
        sort_keys=True,
    )
    sys.stdout.write("\n")
    return 0


def verify_static_vllm_equivalence() -> dict[str, str | int | bool]:
    source_path = Path(VLLM_ROOT) / "vllm/utils/system_utils.py"
    source_bytes = source_path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    commit = subprocess.run(
        ["git", "-C", VLLM_ROOT, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        env={"PATH": "/usr/bin:/bin"},
        text=True,
    ).stdout.strip()
    source_text = source_bytes.decode()
    delegation_line = next(
        (
            line_number
            for line_number, line in enumerate(source_text.splitlines(), 1)
            if EXPECTED_DELEGATION in line
        ),
        0,
    )
    if commit != EXPECTED_VLLM_COMMIT:
        raise RuntimeError(f"vLLM commit drift: {commit}")
    if source_sha256 != EXPECTED_SYSTEM_UTILS_SHA256:
        raise RuntimeError(f"vLLM system_utils.py drift: {source_sha256}")
    if delegation_line == 0:
        raise RuntimeError("frozen vLLM set_process_title delegation not found")
    return {
        "commit": commit,
        "system_utils_path": str(source_path),
        "system_utils_sha256": source_sha256,
        "delegation_line": delegation_line,
        "delegation": EXPECTED_DELEGATION,
        "static_equivalence_verified": True,
    }


def await_signal(fd: int, label: str, deadline: float) -> None:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError(f"timed out before {label}")
    readable, _, _ = select.select([fd], [], [], remaining)
    if not readable:
        raise TimeoutError(f"timed out waiting for {label}")
    if os.read(fd, 1) != b"1":
        raise RuntimeError(f"child did not signal {label}")


def run_parent() -> int:
    vllm_source = verify_static_vllm_equivalence()
    pre_ready_r, pre_ready_w = os.pipe()
    continue_r, continue_w = os.pipe()
    post_ready_r, post_ready_w = os.pipe()
    finish_r, finish_w = os.pipe()
    child_env = {
        "PATH": "/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
        SENTINEL_NAME: SENTINEL_VALUE,
    }

    proc = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--child",
            str(pre_ready_w),
            str(continue_r),
            str(post_ready_w),
            str(finish_r),
        ],
        env=child_env,
        pass_fds=(pre_ready_w, continue_r, post_ready_w, finish_r),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    for fd in (pre_ready_w, continue_r, post_ready_w, finish_r):
        os.close(fd)

    deadline = time.monotonic() + SIGNAL_TIMEOUT_SECONDS
    try:
        await_signal(pre_ready_r, "pre-title readiness", deadline)
        pre_title = summarize_proc_environ(proc.pid)
        os.write(continue_w, b"1")
        await_signal(post_ready_r, "post-title readiness", deadline)
        post_title = summarize_proc_environ(proc.pid)
        os.write(finish_w, b"1")
        remaining = max(0.001, deadline - time.monotonic())
        stdout, stderr = proc.communicate(timeout=remaining)
    finally:
        for fd in (pre_ready_r, continue_w, post_ready_r, finish_w):
            os.close(fd)
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    if proc.returncode != 0:
        raise RuntimeError(f"child failed with status {proc.returncode}: {stderr}")
    if stderr:
        raise RuntimeError(f"child emitted stderr: {stderr}")
    child = json.loads(stdout)
    invariants = {
        "pre_title_proc_has_sentinel": pre_title["sentinel_present"] is True,
        "post_title_proc_lacks_sentinel": post_title["sentinel_present"] is False,
        "child_getenv_before_retains_sentinel": (
            child["getenv_before_title"] == SENTINEL_VALUE
        ),
        "child_getenv_after_retains_sentinel": (
            child["getenv_after_title"] == SENTINEL_VALUE
        ),
        "reported_process_title_matches": (
            child["reported_process_title"] == PROCESS_TITLE
        ),
    }
    if not all(invariants.values()):
        raise RuntimeError(f"setproctitle reproduction invariant failed: {invariants}")
    result = {
        "format": "laguna-setproctitle-proc-environ-reproduction-v1",
        "python_executable": sys.executable,
        "setproctitle_version": importlib.metadata.version("setproctitle"),
        "process_title": PROCESS_TITLE,
        "vllm_static_equivalence": vllm_source,
        "sentinel_name": SENTINEL_NAME,
        "sentinel_value": SENTINEL_VALUE,
        "pre_title_proc_environ": pre_title,
        "post_title_proc_environ": post_title,
        "child_python_environment": child,
        "validated_invariants": invariants,
        "interpretation": (
            "Direct setproctitle reproduces the frozen vLLM wrapper's statically "
            "verified call. The child retains the sentinel in Python after the "
            "title change, but the post-title kernel-visible initial environment "
            "block is incomplete. Absence from /proc/PID/environ cannot prove "
            "selector loss."
        ),
    }
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def main() -> int:
    if len(sys.argv) == 6 and sys.argv[1] == "--child":
        return run_child(*(int(value) for value in sys.argv[2:]))
    if len(sys.argv) != 1:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name}")
    return run_parent()


if __name__ == "__main__":
    raise SystemExit(main())

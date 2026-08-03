#!/usr/bin/env python3
"""Adversarial CPU-only tests for the untrusted-code sandbox.

Every program executed here is written by this file, not by a model, and none of
them touches the network, a device, or anything outside a throwaway directory.
The point is to prove the containment mechanisms actually fire, because a
sandbox that has never been shown to stop anything is not a sandbox.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_laguna_sandbox as sandbox

PYTHON = sys.executable
FAST = sandbox.SandboxPolicy(timeout_s=15.0, cpu_seconds=5)


# ---------------------------------------------------------------------------
# construction, testable without executing anything
# ---------------------------------------------------------------------------


def test_build_argv_uses_isolated_mode_and_optionally_a_namespace() -> None:
    program = Path("/tmp/p.py")
    plain = sandbox.build_argv(sandbox.SandboxPolicy(), "/usr/bin/python3", program)
    assert plain == ["/usr/bin/python3", "-I", "/tmp/p.py"]
    namespaced = sandbox.build_argv(
        sandbox.SandboxPolicy(use_network_namespace=True), "/usr/bin/python3", program
    )
    assert namespaced[:3] == ["unshare", "-n", "-r"]
    assert namespaced[3:] == plain


def test_build_environment_inherits_nothing_from_the_caller(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HF_TOKEN", "secret")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy")
    monkeypatch.setenv("VLLM_XPU_LAGUNA_M8_QKNORM_ROPE", "1")
    env = sandbox.build_environment(tmp_path)
    assert "HF_TOKEN" not in env
    assert "HTTPS_PROXY" not in env
    assert not any(name.startswith("VLLM_") for name in env)
    assert env["HOME"] == str(tmp_path)
    assert env["TMPDIR"] == str(tmp_path)
    assert env["PATH"] == "/usr/bin:/bin"


def test_policy_record_is_complete() -> None:
    record = sandbox.SandboxPolicy().as_record()
    assert set(record) == {
        "timeout_s",
        "cpu_seconds",
        "address_space_bytes",
        "file_size_bytes",
        "extra_processes",
        "disable_network",
        "use_network_namespace",
    }


def test_count_user_tasks_counts_threads_not_just_processes(tmp_path: Path) -> None:
    """A thread is a task, and RLIMIT_NPROC counts tasks.

    Counting only ``/proc/<pid>`` directories undercounts a threaded host badly
    enough that the derived limit blocks the first fork of a legitimate program.
    """

    uid = os.getuid()
    for pid, threads in (("100", 3), ("200", 1)):
        task_dir = tmp_path / pid / "task"
        for index in range(threads):
            (task_dir / str(int(pid) + index)).mkdir(parents=True)
    (tmp_path / "not-a-pid").mkdir()
    assert sandbox.count_user_tasks(tmp_path, uid=uid) == 4
    # A different uid owns nothing here.
    assert sandbox.count_user_tasks(tmp_path, uid=uid + 12345) == 0


def test_count_user_tasks_survives_a_missing_proc(tmp_path: Path) -> None:
    assert sandbox.count_user_tasks(tmp_path / "nope") == 0


# ---------------------------------------------------------------------------
# containment
# ---------------------------------------------------------------------------


def test_a_correct_program_passes() -> None:
    result = sandbox.run_untrusted_python(
        "assert sum(range(5)) == 10", policy=FAST, python_executable=PYTHON
    )
    assert result.status == sandbox.STATUS_PASSED
    assert result.passed is True
    assert result.returncode == 0


def test_a_failing_assertion_is_FAILED_and_never_PASSED() -> None:
    result = sandbox.run_untrusted_python(
        "assert 1 == 2", policy=FAST, python_executable=PYTHON
    )
    assert result.status == sandbox.STATUS_FAILED
    assert result.passed is False
    assert "AssertionError" in result.stderr


def test_a_wall_clock_hang_is_killed() -> None:
    result = sandbox.run_untrusted_python(
        "import time\ntime.sleep(120)",
        policy=sandbox.SandboxPolicy(timeout_s=2.0, cpu_seconds=60),
        python_executable=PYTHON,
    )
    assert result.status == sandbox.STATUS_TIMEOUT
    assert result.duration_s < 30
    assert "wall-clock" in (result.detail or "")


def test_a_cpu_burn_is_killed_by_the_cpu_limit() -> None:
    result = sandbox.run_untrusted_python(
        "while True:\n    pass",
        policy=sandbox.SandboxPolicy(timeout_s=60.0, cpu_seconds=2),
        python_executable=PYTHON,
    )
    # The CPU limit fires well before the generous wall clock.
    assert result.status in (sandbox.STATUS_SIGNALLED, sandbox.STATUS_TIMEOUT)
    assert result.duration_s < 30
    assert result.passed is False


def test_runaway_allocation_hits_the_address_space_limit() -> None:
    result = sandbox.run_untrusted_python(
        "x = bytearray(64 * 1024 * 1024 * 1024)",
        policy=sandbox.SandboxPolicy(
            timeout_s=20.0, cpu_seconds=10, address_space_bytes=256 * 1024 * 1024
        ),
        python_executable=PYTHON,
    )
    assert result.passed is False
    assert result.status in (sandbox.STATUS_FAILED, sandbox.STATUS_SIGNALLED)


def test_network_access_is_denied() -> None:
    result = sandbox.run_untrusted_python(
        'import socket\nsocket.create_connection(("127.0.0.1", 18080), timeout=1)',
        policy=FAST,
        python_executable=PYTHON,
    )
    assert result.status == sandbox.STATUS_FAILED
    assert "network access is disabled" in result.stderr


def test_process_creation_is_capped_but_not_forbidden() -> None:
    """A fork bomb is bounded; a legitimate single-process program still runs.

    The limit is the host's current task count plus ``extra_processes``, so this
    asserts the cap holds rather than a specific number.
    """

    source = (
        "import os, time\n"
        "made = 0\n"
        "for _ in range(500):\n"
        "    try:\n"
        "        pid = os.fork()\n"
        "    except OSError:\n"
        "        break\n"
        "    if pid == 0:\n"
        "        time.sleep(1)\n"
        "        os._exit(0)\n"
        "    made += 1\n"
        "print(made)\n"
    )
    result = sandbox.run_untrusted_python(
        source,
        policy=sandbox.SandboxPolicy(timeout_s=30.0, cpu_seconds=10, extra_processes=8),
        python_executable=PYTHON,
    )
    assert result.status == sandbox.STATUS_PASSED
    assert int(result.stdout.strip()) < 500


def test_an_output_flood_is_bounded_and_flagged() -> None:
    result = sandbox.run_untrusted_python(
        'while True:\n    print("y" * 4096)',
        policy=sandbox.SandboxPolicy(
            timeout_s=30.0, cpu_seconds=10, file_size_bytes=32768
        ),
        python_executable=PYTHON,
    )
    assert len(result.stdout) <= 32768
    assert result.stdout_truncated is True
    assert result.passed is False


def test_stdin_is_closed_so_an_input_call_cannot_hang() -> None:
    result = sandbox.run_untrusted_python(
        "print(input())", policy=FAST, python_executable=PYTHON
    )
    assert result.status == sandbox.STATUS_FAILED
    assert "EOF" in result.stderr


def test_the_working_directory_is_private_and_removed() -> None:
    result = sandbox.run_untrusted_python(
        "import os\nopen('scratch.txt', 'w').write('x')\nprint(os.getcwd())\n",
        policy=FAST,
        python_executable=PYTHON,
    )
    assert result.status == sandbox.STATUS_PASSED
    workdir = Path(result.stdout.strip())
    assert workdir.name.startswith("laguna-eval-sandbox-")
    assert not workdir.exists()


def test_a_syntax_error_from_a_truncated_response_is_FAILED() -> None:
    result = sandbox.run_untrusted_python(
        "def solve(x):\n    return x +", policy=FAST, python_executable=PYTHON
    )
    assert result.status == sandbox.STATUS_FAILED
    assert "SyntaxError" in result.stderr


# ---------------------------------------------------------------------------
# refusals
# ---------------------------------------------------------------------------


def test_an_unavailable_network_namespace_is_refused_not_silently_downgraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sandbox,
        "probe_network_namespace",
        lambda *args, **kwargs: {"available": False, "reason": "denied by policy"},
    )
    result = sandbox.run_untrusted_python(
        "assert True",
        policy=sandbox.SandboxPolicy(use_network_namespace=True),
        python_executable=PYTHON,
    )
    assert result.status == sandbox.STATUS_REFUSED
    assert result.passed is False
    assert "denied by policy" in (result.detail or "")


def test_a_namespace_that_is_available_is_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sandbox,
        "probe_network_namespace",
        lambda *args, **kwargs: {"available": True, "reason": None},
    )
    argv = sandbox.build_argv(
        sandbox.SandboxPolicy(use_network_namespace=True), PYTHON, Path("/tmp/p.py")
    )
    assert argv[0] == "unshare"


def test_a_missing_interpreter_is_refused_not_reported_as_a_failure() -> None:
    result = sandbox.run_untrusted_python(
        "assert True",
        policy=FAST,
        python_executable="/nonexistent/python-does-not-exist",
    )
    assert result.status == sandbox.STATUS_REFUSED
    assert "could not start" in (result.detail or "")


def test_sandbox_report_states_the_boundary_class_honestly() -> None:
    report = sandbox.sandbox_report()
    assert report["schema"] == sandbox.SCHEMA
    assert report["boundary_class"] == "robustness, not security"
    assert "deliberate attacker" in report["boundary_note"]
    assert "available" in report["network_namespace_probe"]

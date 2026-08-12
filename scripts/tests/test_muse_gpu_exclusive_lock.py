import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time


REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "experiments/muse-glimmer-30b-b70/scripts/bringup-sweep.py"
FLEET = REPO / "scripts/serve-muse-glimmer-bf16-fleet.sh"


def load_runner():
    spec = importlib.util.spec_from_file_location("muse_bringup_sweep", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gpu_lock_excludes_another_process(tmp_path):
    runner = load_runner()
    lock_path = tmp_path / "gpu.lock"
    fd = runner.acquire_gpu_lock(str(lock_path))
    try:
        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import fcntl, os, sys; "
                    "fd=os.open(sys.argv[1], os.O_RDWR); "
                    "fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)"
                ),
                str(lock_path),
            ],
            capture_output=True,
            text=True,
        )
        assert probe.returncode != 0
        assert "BlockingIOError" in probe.stderr
    finally:
        os.close(fd)

    fd2 = runner.acquire_gpu_lock(str(lock_path))
    os.close(fd2)


def test_benchmark_and_production_use_same_lock_default():
    runner = load_runner()
    fleet_text = FLEET.read_text()
    expected = "/run/lock/muse-glimmer-gpu-exclusive.lock"
    assert runner.gpu_lock_path() == expected
    assert "muse-glimmer-gpu-exclusive.lock" in fleet_text
    assert "flock -n 9" in fleet_text


def test_production_refuses_benchmark_owned_lock(tmp_path):
    runner = load_runner()
    lock_path = tmp_path / "gpu.lock"
    fd = runner.acquire_gpu_lock(str(lock_path))
    try:
        env = dict(os.environ)
        env["MUSE_GPU_LOCK_PATH"] = str(lock_path)
        env["MUSE_GPU_LOCK_ALLOW_OVERRIDE"] = "1"
        env["LLAMA_SERVER"] = "/bin/false"
        fleet = subprocess.run(
            ["bash", str(FLEET)], env=env, capture_output=True, text=True, timeout=10,
        )
        assert fleet.returncode != 0
        assert "GPU host is already reserved" in fleet.stderr
        assert "benchmark pid=" in fleet.stderr
    finally:
        os.close(fd)


def test_server_child_inherits_lock_after_runner_fd_closes(tmp_path):
    runner = load_runner()
    lock_path = tmp_path / "gpu.lock"
    fd = runner.acquire_gpu_lock(str(lock_path))
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"], pass_fds=(fd,)
    )
    os.close(fd)
    try:
        time.sleep(0.1)
        try:
            runner.acquire_gpu_lock(str(lock_path))
        except RuntimeError as exc:
            assert "already reserved" in str(exc)
        else:
            raise AssertionError("child did not retain inherited GPU lock")
    finally:
        child.terminate()
        child.wait(timeout=5)

    fd2 = runner.acquire_gpu_lock(str(lock_path))
    os.close(fd2)


def test_lock_override_requires_explicit_test_gate(monkeypatch, tmp_path):
    runner = load_runner()
    monkeypatch.setenv("MUSE_GPU_LOCK_PATH", str(tmp_path / "alternate.lock"))
    monkeypatch.delenv("MUSE_GPU_LOCK_ALLOW_OVERRIDE", raising=False)
    try:
        runner.gpu_lock_path()
    except RuntimeError as exc:
        assert "canonical host lock" in str(exc)
    else:
        raise AssertionError("unguarded lock override was accepted")

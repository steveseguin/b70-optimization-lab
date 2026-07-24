"""CPU-only tamper tests for the shared gate+up counter runner.

These tests deliberately exercise only command construction, evidence writers,
and profiler-file closure validation.  They never invoke ``main`` or any
device, profiler, privilege, network, or tensor API.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("run_laguna_shared_gate_up_mm_counters.py")
SPEC = importlib.util.spec_from_file_location("gate_up_counter_runner", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def test_unitrace_argv_exactly_normalizes_to_frozen_template(tmp_path: Path) -> None:
    arm = tmp_path / "card2" / "B1"
    argv = runner.unitrace_argv(2, "B1", arm, SHA_A, SHA_B, SHA_C)

    runner.validate_unitrace_argv(
        argv,
        rank=2,
        treatment="candidate",
        fixture_sha=SHA_A,
        authorization_sha=SHA_B,
        protocol_sha=SHA_C,
        fixture_output=arm / "fixture.json",
    )

    env_index = argv.index(str(runner.ENV))
    timeout_index = argv.index(str(runner.TIMEOUT))
    assignments = argv[env_index + 2 : timeout_index]
    assert assignments == sorted(assignments)
    assert argv[argv.index("--arm") + 1] == "candidate"
    assert argv[argv.index("--devices-to-sample") + 1] == "0"


@pytest.mark.parametrize(
    ("position", "value", "message"),
    (
        ("--rank", "3", "--rank"),
        ("--arm", "candidate", "--arm"),
        ("--out", "/wrong/fixture.json", "--out"),
    ),
)
def test_unitrace_argv_rejects_dynamic_tampering(
    tmp_path: Path, position: str, value: str, message: str
) -> None:
    arm = tmp_path / "card0" / "A1"
    argv = runner.unitrace_argv(0, "A1", arm, SHA_A, SHA_B, SHA_C)
    argv[argv.index(position) + 1] = value

    with pytest.raises(RuntimeError, match=message):
        runner.validate_unitrace_argv(
            argv,
            rank=0,
            treatment="control",
            fixture_sha=SHA_A,
            authorization_sha=SHA_B,
            protocol_sha=SHA_C,
            fixture_output=arm / "fixture.json",
        )


def test_unitrace_argv_rejects_static_template_tampering(tmp_path: Path) -> None:
    arm = tmp_path / "card1" / "B2"
    argv = runner.unitrace_argv(1, "B2", arm, SHA_A, SHA_B, SHA_C)
    argv[argv.index("--group") + 1] = "WrongGroup"

    with pytest.raises(RuntimeError, match="frozen packet template"):
        runner.validate_unitrace_argv(
            argv,
            rank=1,
            treatment="candidate",
            fixture_sha=SHA_A,
            authorization_sha=SHA_B,
            protocol_sha=SHA_C,
            fixture_output=arm / "fixture.json",
        )


def test_profiler_outputs_requires_one_nonempty_regular_pid_pair(
    tmp_path: Path,
) -> None:
    arm = tmp_path / "A1"
    arm.mkdir()
    timing = arm / "unitrace.4242"
    metrics = arm / "unitrace.metrics.4242"
    timing.write_text("timing\n")
    metrics.write_text("metrics\n")

    observed_timing, observed_metrics, suffix = runner.profiler_outputs(arm)
    assert (observed_timing, observed_metrics, suffix) == (timing, metrics, "4242")


@pytest.mark.parametrize("kind", ("empty", "wrong-suffix", "extra", "symlink"))
def test_profiler_outputs_rejects_noncanonical_files(tmp_path: Path, kind: str) -> None:
    arm = tmp_path / kind
    arm.mkdir()
    (arm / "unitrace.7").write_text("timing\n")
    (arm / "unitrace.metrics.7").write_text("metrics\n")
    if kind == "empty":
        (arm / "unitrace.metrics.7").write_bytes(b"")
    elif kind == "wrong-suffix":
        (arm / "unitrace.metrics.7").rename(arm / "unitrace.metrics.8")
    elif kind == "extra":
        (arm / "unitrace.8").write_text("extra\n")
    else:
        (arm / "unitrace.metrics.7").unlink()
        (arm / "unitrace.metrics.7").symlink_to(arm / "unitrace.7")

    with pytest.raises(RuntimeError, match="unitrace"):
        runner.profiler_outputs(arm)


def test_exclusive_writers_are_canonical_durable_and_non_overwriting(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "evidence.json"
    payload = {"z": [1, 2], "a": True}
    runner.exclusive_json(evidence, payload)
    assert evidence.read_bytes() == b'{"a":true,"z":[1,2]}\n'
    assert json.loads(evidence.read_text()) == payload
    with pytest.raises(FileExistsError):
        runner.exclusive_json(evidence, {"replacement": True})

    blob = tmp_path / "stdout.log"
    runner.exclusive_bytes(blob, b"captured\x00bytes")
    assert blob.read_bytes() == b"captured\x00bytes"
    with pytest.raises(FileExistsError):
        runner.exclusive_bytes(blob, b"replacement")


def test_pure_action_boundary_remains_counter_only() -> None:
    expected = runner.contract.expected_actions(True)
    assert expected["counter_execution_authorized"] is True
    assert expected["counter_execution_performed"] is False
    for name in (
        "counter_gate_evaluated",
        "endpoint_authorized",
        "service_authorized",
        "model_generation_authorized",
        "network_authorized",
        "submission_authorized",
        "reboot_authorized",
    ):
        assert expected[name] is False
    assert runner.DOWNSTREAM_FALSE == {
        name: value
        for name, value in expected.items()
        if name
        not in {
            "component_passed",
            "tooling_frozen",
            "counter_execution_authorized",
            "counter_execution_performed",
        }
    }


def test_profiler_start_state_survives_a_supervisor_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = tmp_path / "sudo-secret"
    secret.write_bytes(b"unused")
    state = {"profiler_process_started": False}

    class FakeProcess:
        pid = 4242

        def communicate(self, timeout: int) -> tuple[bytes, bytes]:
            raise RuntimeError(f"synthetic supervisor failure after {timeout}")

    monkeypatch.setattr(runner, "SUDO_PASSWORD", secret)
    monkeypatch.setattr(
        runner.subprocess, "Popen", lambda *args, **kwargs: FakeProcess()
    )
    monkeypatch.setattr(runner.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(runner, "require_group_gone", lambda pgid, context: None)
    with pytest.raises(RuntimeError, match="synthetic supervisor failure"):
        runner.bounded(
            ["/never/executed"],
            cwd=tmp_path,
            env={},
            execution_state=state,
        )
    assert state == {"profiler_process_started": True}


def test_campaign_execution_state_cannot_lose_a_failed_first_arm() -> None:
    campaign = {"profiler_process_started": False}
    runner.merge_execution_state(campaign, {"profiler_process_started": True})
    assert campaign == {"profiler_process_started": True}
    runner.merge_execution_state(campaign, {"profiler_process_started": False})
    assert campaign == {"profiler_process_started": True}


def test_root_transition_failure_seal_is_packet_bound_and_exclusive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "RUNS", tmp_path)
    failure = tmp_path / "frozen-preflight-failure.json"
    root = tmp_path / "shared-gate-up-m8-counters-20990101T000000Z"
    packet = {"packet_path": "/repo/data/frozen.json"}
    runner.seal_pre_root_failure(
        failure,
        root=root,
        packet=packet,
        packet_sha=SHA_A,
        status="counter-failed-stop-during-root-transition",
        error=RuntimeError("synthetic mkdir failure"),
    )
    record = json.loads(failure.read_text())
    assert record["campaign_root"] == str(root)
    assert record["authorization_sha256"] == SHA_A
    assert record["counter_execution_performed"] is False
    assert record["model_generation_performed"] is False
    with pytest.raises(RuntimeError, match="preflight-failure path drift"):
        runner.seal_pre_root_failure(
            failure,
            root=root,
            packet=packet,
            packet_sha=SHA_A,
            status="counter-failed-stop-during-root-transition",
            error=RuntimeError("duplicate"),
        )

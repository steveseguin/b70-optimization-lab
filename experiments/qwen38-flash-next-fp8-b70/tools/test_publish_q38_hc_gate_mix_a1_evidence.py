#!/usr/bin/env python3
"""CPU-only transaction tests for HC gate-mix A1 evidence publication."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


MODULE_PATH = Path(__file__).with_name("publish-q38-hc-gate-mix-a1-evidence.py")
SPEC = importlib.util.spec_from_file_location("q38_gate_mix_publish", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def health(status: str = "pass", code: int = 0) -> dict:
    return {
        "schema_version": 1,
        "status": status,
        "classification": "qwen38_hc_gate_mix_exact_staged_a1_host_health",
        "runner_exit_code": code,
        "local_nvme_corrected": {
            "baseline": 100,
            "final": 100,
            "delta": 0,
            "required_delta": 0,
        },
        "root_port_corrected": {
            "baseline": 20,
            "final": 20,
            "delta": 0,
            "required_delta": 0,
        },
        "failure_reason": None,
    }


def paths(root: Path) -> tuple[Path, Path]:
    final = root / "result"
    return final.with_name(final.name + ".staging"), final


def test_pass_is_published_only_with_a_verified_manifest() -> None:
    with TemporaryDirectory() as temporary:
        stage, final = paths(Path(temporary))
        stage.mkdir()
        (stage / "payload.txt").write_text("exact\n", encoding="utf-8")
        outcome = MODULE.publish(stage, final, health())
        assert outcome["status"] == "pass"
        assert not stage.exists() and final.is_dir()
        receipt = json.loads((final / "final-health.json").read_text())
        assert receipt["status"] == "pass" and receipt["runner_exit_code"] == 0
        MODULE.verify_manifest(final, final / "SHA256SUMS")


def test_checksum_failure_cannot_publish_pass() -> None:
    with TemporaryDirectory() as temporary:
        stage, final = paths(Path(temporary))
        stage.mkdir()
        payload = stage / "payload.txt"
        payload.write_text("before\n", encoding="utf-8")

        def corrupt(_stage: Path, _manifest: Path) -> None:
            payload.write_text("after\n", encoding="utf-8")

        outcome = MODULE.publish(stage, final, health(), verify_hook=corrupt)
        assert outcome["requested_status"] == "pass"
        assert outcome["status"] == "failed_closed"
        receipt = json.loads((final / "final-health.json").read_text())
        assert receipt["status"] == "failed_closed"
        assert receipt["runner_exit_code"] == 70
        assert "checksum failure" in receipt["failure_reason"]
        MODULE.verify_manifest(final, final / "SHA256SUMS")


def test_existing_final_result_rejects_replay_without_clobber() -> None:
    with TemporaryDirectory() as temporary:
        stage, final = paths(Path(temporary))
        stage.mkdir()
        (stage / "payload.txt").write_text("first\n", encoding="utf-8")
        MODULE.publish(stage, final, health())
        first_manifest = (final / "SHA256SUMS").read_bytes()

        stage.mkdir()
        (stage / "payload.txt").write_text("replay\n", encoding="utf-8")
        with pytest.raises(FileExistsError):
            MODULE.publish(stage, final, health())
        assert stage.is_dir()
        assert (final / "SHA256SUMS").read_bytes() == first_manifest
        assert (final / "payload.txt").read_text(encoding="utf-8") == "first\n"


def test_symlink_in_staging_fails_before_publication() -> None:
    with TemporaryDirectory() as temporary:
        stage, final = paths(Path(temporary))
        stage.mkdir()
        target = stage / "payload.txt"
        target.write_text("exact\n", encoding="utf-8")
        (stage / "linked.txt").symlink_to(target)
        with pytest.raises(MODULE.PublicationError, match="symlink"):
            MODULE.publish(stage, final, health("failed_closed", 1))
        assert not final.exists()

#!/usr/bin/env python3
"""Fail-closed binding between speed evidence and independent quality gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "neural.download.promotion-attestation.v1"
REQUIRED_GATES = (
    "varied_task_quality_passed",
    "exact_or_target_oracle_passed",
    "deterministic_repeats_passed",
    "fresh_server_repeat_passed",
    "target_model_unchanged",
    "no_quality_loss",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_evidence_path(value: str, attestation_path: Path) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    repo_candidate = REPO_ROOT / candidate
    if repo_candidate.is_file():
        return repo_candidate
    return attestation_path.parent / candidate


def validate_promotion_attestation(
    attestation_path: Path,
    performance_path: Path,
    *,
    expected_model_revision: str | None = None,
    expected_runtime_revision: str | None = None,
) -> dict[str, Any]:
    """Validate an evidence-bound promotion decision or raise ``ValueError``."""
    data = json.loads(attestation_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    if data.get("schema") != SCHEMA:
        failures.append("schema_mismatch")

    performance = data.get("performance_evidence") or {}
    recorded_performance_path = performance.get("path")
    if not isinstance(recorded_performance_path, str):
        failures.append("performance_evidence_path_missing")
    else:
        resolved_performance_path = resolve_evidence_path(
            recorded_performance_path, attestation_path
        )
        if resolved_performance_path.resolve() != performance_path.resolve():
            failures.append("performance_evidence_path_mismatch")
    recorded_performance_hash = performance.get("sha256")
    actual_performance_hash = sha256_file(performance_path)
    if recorded_performance_hash != actual_performance_hash:
        failures.append("performance_evidence_hash_mismatch")

    identity = data.get("identity") or {}
    for key in ("model_revision", "runtime_revision", "optimization_identity"):
        if not isinstance(identity.get(key), str) or not identity[key].strip():
            failures.append(f"identity_{key}_missing")
    if (
        expected_model_revision
        and identity.get("model_revision") != expected_model_revision
    ):
        failures.append("model_revision_mismatch")
    if (
        expected_runtime_revision
        and identity.get("runtime_revision") != expected_runtime_revision
    ):
        failures.append("runtime_revision_mismatch")

    gates = data.get("gates") or {}
    for gate in REQUIRED_GATES:
        if gates.get(gate) is not True:
            failures.append(f"gate_{gate}_not_true")

    evidence = data.get("quality_evidence")
    if not isinstance(evidence, list) or not evidence:
        failures.append("quality_evidence_missing")
    else:
        supported_gates: set[str] = set()
        for index, item in enumerate(evidence):
            if not isinstance(item, dict):
                failures.append(f"quality_evidence_{index}_invalid")
                continue
            value = item.get("path")
            expected_hash = item.get("sha256")
            supports = item.get("supports")
            if not isinstance(value, str) or not isinstance(expected_hash, str):
                failures.append(f"quality_evidence_{index}_identity_missing")
                continue
            if (
                not isinstance(supports, list)
                or not supports
                or any(gate not in REQUIRED_GATES for gate in supports)
            ):
                failures.append(f"quality_evidence_{index}_supports_invalid")
            else:
                supported_gates.update(supports)
            path = resolve_evidence_path(value, attestation_path)
            if not path.is_file():
                failures.append(f"quality_evidence_{index}_missing")
            elif sha256_file(path) != expected_hash:
                failures.append(f"quality_evidence_{index}_hash_mismatch")
        for gate in REQUIRED_GATES:
            if gate not in supported_gates:
                failures.append(f"gate_{gate}_has_no_bound_evidence")

    if failures:
        raise ValueError(
            f"{attestation_path}: promotion attestation failed: "
            + ", ".join(failures)
        )
    return data

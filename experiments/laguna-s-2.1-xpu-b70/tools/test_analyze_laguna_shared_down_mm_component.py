"""CPU-only tamper tests for the shared-down component analyzer."""

from __future__ import annotations

import copy
import hashlib

import pytest

import analyze_laguna_shared_down_mm_component as analyzer


def digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def valid_raw_manifest() -> dict[str, dict[str, str]]:
    return {
        "down": {
            "control": digest("down"),
            "candidate": digest("down"),
        },
        "candidate_repeat": {
            "first": digest("down"),
            "repeat": digest("down"),
        },
        "shared_routed_add": {
            "control": digest("add"),
            "candidate": digest("add"),
        },
        "fixed_rank_sum": {
            "control": digest("sum"),
            "candidate": digest("sum"),
        },
        "aggregate": {
            "control": digest("aggregate"),
            "candidate": digest("aggregate"),
        },
    }


def test_raw_output_manifest_accepts_exact_control_candidate_pairs() -> None:
    manifest = valid_raw_manifest()
    assert analyzer.raw_output_manifest_exact(
        manifest,
        manifest["aggregate"]["candidate"],
    )


@pytest.mark.parametrize(
    ("boundary", "field"),
    [
        ("down", "candidate"),
        ("candidate_repeat", "repeat"),
        ("shared_routed_add", "candidate"),
        ("fixed_rank_sum", "candidate"),
        ("aggregate", "candidate"),
    ],
)
def test_raw_output_manifest_rejects_each_tampered_boundary(
    boundary: str,
    field: str,
) -> None:
    manifest = copy.deepcopy(valid_raw_manifest())
    manifest[boundary][field] = digest(f"tampered-{boundary}")
    assert not analyzer.raw_output_manifest_exact(
        manifest,
        manifest["aggregate"]["control"],
    )


def test_raw_output_manifest_rejects_broken_aggregate_link() -> None:
    manifest = valid_raw_manifest()
    assert not analyzer.raw_output_manifest_exact(
        manifest,
        digest("unlinked-output"),
    )


@pytest.mark.parametrize(
    ("epoch", "expected"),
    [
        (
            0,
            "f96f0561cf03392015105df2fe72c321f0534cc3aa54ad6bde3aeaf21b00934b",
        ),
        (
            31,
            "b39911acc2fe8f9b6a9a207d0838e31a2f28a986d0a2ae4a389c8b0b733c740b",
        ),
        (
            127,
            "3d24e1368cfc113a85d7ebd86a8343f3e7188453e014a647f3d94285cf76df58",
        ),
    ],
)
def test_deterministic_fixture_hash(epoch: int, expected: str) -> None:
    assert analyzer.deterministic_fixture_sha256(epoch) == expected

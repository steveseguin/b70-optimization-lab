#!/usr/bin/env python3
"""CPU-only fixtures for the current-stream event-profile analyzer."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_laguna_m8_current_stream_event as gate


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)


def token_hash(tokens: list[int]) -> str:
    return hashlib.sha256(
        json.dumps(tokens, separators=(",", ":")).encode()
    ).hexdigest()


def profile_payload(rank: int, total: int, values: dict[str, int]) -> dict:
    intervals = [
        {"index": index, "kind": kind, "duration_ns": values[kind]}
        for index, kind in enumerate(gate.EXPECTED_KINDS)
    ]
    return {
        "schema": gate.PROFILE_SCHEMA,
        "status": "complete",
        "rank": rank,
        "world_size": 4,
        "batch_descriptor": "BatchDescriptor(num_tokens=8)",
        "graphs": 146,
        "eager_breaks": 145,
        "boundary_categories": {"attention": 48, "collective": 97},
        "event_count": 292,
        "interval_count": 291,
        "total_duration_ns": total,
        "segment_kind_order_sha256": gate.KIND_ORDER_SHA256,
        "stream_identity": {"device_type": "xpu", "device_index": rank, "stream_id": 7},
        "intervals": intervals,
        "rank_local_only": True,
        "global_critical_path_validated": False,
        "collective_cross_stream_completion_validated": False,
        "diagnostic_only": True,
        "not_benchmark_or_submission_evidence": True,
    }


def arm_record(root: Path, arm: str) -> dict:
    graph = arm == "graph-event"
    profile_root = root / arm / "current-stream-event-profile" if graph else None
    tokens = list(range(gate.COMPLETION_TOKENS))
    return {
        "schema": gate.ARM_SCHEMA,
        "status": "complete",
        "diagnostic_only": True,
        "not_benchmark_or_submission_evidence": True,
        "single_generate_call": True,
        "fresh_process": True,
        "arm": arm,
        "graph": graph,
        "model": gate.EXPECTED_MODEL,
        "draft_model": gate.EXPECTED_DRAFT if graph else None,
        "vllm_root": gate.EXPECTED_VLLM_ROOT,
        "vllm_commit": gate.EXPECTED_VLLM_COMMIT,
        "kernel_root": gate.EXPECTED_KERNEL_ROOT,
        "kernel_commit": gate.EXPECTED_KERNEL_COMMIT,
        "kernel_identity": {
            name: {
                "path": str(
                    Path(gate.EXPECTED_KERNEL_ROOT) / "vllm_xpu_kernels" / name
                ),
                "sha256": digest,
            }
            for name, digest in gate.EXPECTED_KERNELS.items()
        },
        "prompt_sha256": "c" * 64,
        "prompt_tokens": 19,
        "completion_tokens": gate.COMPLETION_TOKENS,
        "cached_tokens": 0,
        "generation_wall_ns": 12345,
        "token_ids": tokens,
        "token_ids_sha256": token_hash(tokens),
        "text_sha256": "d" * 64,
        "finish_reason": "length",
        "event_root": str(profile_root) if graph else None,
        "event_rank_files": {} if graph else None,
        "compilation_config": (
            {
                "mode": "NONE",
                "cudagraph_mode": "PIECEWISE",
                "cudagraph_capture_sizes": [8],
                "max_cudagraph_capture_size": 8,
            }
            if graph
            else None
        ),
        "async_scheduling": not graph,
        "environment": gate.expected_environment(profile_root),
    }


def build_run(root: Path) -> tuple[dict, dict]:
    root.mkdir()
    root.chmod(0o700)
    q1, graph = arm_record(root, "q1"), arm_record(root, "graph-event")
    event_root = root / "graph-event" / "current-stream-event-profile"
    event_root.mkdir(parents=True)
    event_root.chmod(0o700)
    # Rank 2 is slowest by total.  The category maxima deliberately live on
    # other ranks, catching any invalid cross-rank category reduction.
    rows = {
        0: (800, {"graph": 1, "collective": 1, "attention": 1}),
        1: (900, {"graph": 1, "collective": 100, "attention": 1}),
        2: (1000, {"graph": 10, "collective": 20, "attention": 30}),
        3: (950, {"graph": 100, "collective": 1, "attention": 200}),
    }
    for rank, (total, values) in rows.items():
        path = event_root / f"rank{rank}.json"
        write_json(path, profile_payload(rank, total, values))
        graph["event_rank_files"][str(rank)] = {
            "path": str(path),
            "sha256": gate.sha256_file(path),
        }
    q1_path, graph_path = (
        root / "q1" / "driver.json",
        root / "graph-event" / "driver.json",
    )
    write_json(q1_path, q1)
    write_json(graph_path, graph)
    identity_path = root / "identity.txt"
    identity_path.write_text("frozen packet\n")
    identity_path.chmod(0o600)
    for name in gate.CHECK_NAMES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if name.endswith("workers.txt"):
            path.write_bytes(b"")
            path.chmod(0o600)
        else:
            write_json(
                path,
                {
                    "format": ("laguna-m8-gather-sharded-operational-preflight-v2"),
                    "status": "passed",
                    "idle": {"device_ids": [0, 1, 2, 3]},
                },
            )
    closure = {
        "schema": gate.CLOSURE_SCHEMA,
        "status": "complete",
        "diagnostic_only": True,
        "model_generation_count": 2,
        "network_access": False,
        "localmaxxing_submission_made": False,
        "identity": {
            "path": str(identity_path),
            "sha256": gate.sha256_file(identity_path),
        },
        "arms": {
            "q1": {"path": str(q1_path), "sha256": gate.sha256_file(q1_path)},
            "graph-event": {
                "path": str(graph_path),
                "sha256": gate.sha256_file(graph_path),
            },
        },
        "profiles": graph["event_rank_files"],
        "checks": {
            name: {
                "path": str(root / name),
                "sha256": gate.sha256_file(root / name),
            }
            for name in gate.CHECK_NAMES
        },
    }
    write_json(root / "closure.json", closure)
    return q1, graph


def test_validate_profiles_selects_single_slowest_rank_without_category_maxima(
    tmp_path,
):
    _q1, graph = build_run(tmp_path / "run")
    result = gate.validate_profiles(tmp_path / "run", graph)
    assert result["slowest_rank"] == 2
    assert result["slowest_rank_total_duration_ns"] == 1000
    assert result["selected_rank_kind_sums_ns"] == {
        "graph": 1460,
        "collective": 1940,
        "attention": 1440,
    }
    assert result["selected_rank_kind_sums_ns"]["attention"] != 48 * 200
    assert result["per_rank_kind_sums_ns"]["3"]["attention"] == 48 * 200


def test_shared_environment_contract_is_event_only(tmp_path):
    q1 = gate.expected_environment(None)
    graph = gate.expected_environment(tmp_path)
    event_key = "VLLM_XPU_LAGUNA_REPLAY_EVENT_PROFILE_ROOT"
    assert event_key not in q1
    assert graph[event_key] == str(tmp_path)
    assert graph["VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS"] == "0"
    forbidden = {
        "VLLM_XPU_LAGUNA_REPLAY_PROFILE_ROOT",
        "VLLM_XPU_LAGUNA_REPLAY_PROFILE_SAMPLES",
        "VLLM_XPU_LAGUNA_M8_EVIDENCE",
        "VLLM_XPU_LAGUNA_REPLAY_TRACE_SESSION",
        "VLLM_XPU_LAGUNA_REPLAY_TRACE_UNITRACE",
    }
    assert forbidden.isdisjoint(q1)
    assert forbidden.isdisjoint(graph)


def test_validate_profile_rejects_required_diagnostic_flag(tmp_path):
    payload = profile_payload(0, 100, {"graph": 1, "collective": 1, "attention": 1})
    payload["global_critical_path_validated"] = True
    with pytest.raises(SystemExit, match="global_critical_path_validated"):
        gate.validate_profile(payload, 0)


def test_validate_profile_rejects_kind_order_and_bool_duration(tmp_path):
    payload = profile_payload(0, 100, {"graph": 1, "collective": 1, "attention": 1})
    payload["intervals"][7]["kind"] = "graph"
    with pytest.raises(SystemExit, match="ordering drifted"):
        gate.validate_profile(payload, 0)
    payload = profile_payload(0, 100, {"graph": 1, "collective": 1, "attention": 1})
    payload["intervals"][0]["duration_ns"] = True
    with pytest.raises(SystemExit, match="non-negative integer"):
        gate.validate_profile(payload, 0)


def test_validate_profiles_requires_exact_four_rank_files(tmp_path):
    _q1, graph = build_run(tmp_path / "run")
    write_json(
        tmp_path
        / "run"
        / "graph-event"
        / "current-stream-event-profile"
        / "other.json",
        {},
    )
    with pytest.raises(SystemExit, match="exactly four rank files"):
        gate.validate_profiles(tmp_path / "run", graph)


def test_validate_profiles_rejects_cross_rank_descriptor_drift(tmp_path):
    _q1, graph = build_run(tmp_path / "run")
    path = (
        tmp_path / "run" / "graph-event" / "current-stream-event-profile" / "rank3.json"
    )
    payload = json.loads(path.read_text())
    payload["batch_descriptor"] = "BatchDescriptor(num_tokens=7)"
    write_json(path, payload)
    graph["event_rank_files"]["3"]["sha256"] = gate.sha256_file(path)
    with pytest.raises(SystemExit, match="descriptor drifted across ranks"):
        gate.validate_profiles(tmp_path / "run", graph)


def test_main_requires_exact_q1_token_and_text_parity(monkeypatch, tmp_path):
    root = tmp_path / "run"
    _q1, _graph = build_run(root)
    graph_path = root / "graph-event" / "driver.json"
    graph = json.loads(graph_path.read_text())
    graph["text_sha256"] = "e" * 64
    write_json(graph_path, graph)
    closure_path = root / "closure.json"
    closure = json.loads(closure_path.read_text())
    closure["arms"]["graph-event"]["sha256"] = gate.sha256_file(graph_path)
    write_json(closure_path, closure)
    out = tmp_path / "analysis.json"
    monkeypatch.setattr(Path, "is_relative_to", lambda _self, _other: True)
    monkeypatch.setattr(
        sys, "argv", ["analyze", "--run-dir", str(root), "--out", str(out)]
    )
    with pytest.raises(SystemExit, match="exact identity drifted at text_sha256"):
        gate.main()


def test_main_writes_rank_local_diagnostic_decision(monkeypatch, tmp_path):
    root = tmp_path / "run"
    build_run(root)
    out = tmp_path / "analysis.json"
    monkeypatch.setattr(Path, "is_relative_to", lambda _self, _other: True)
    monkeypatch.setattr(
        sys, "argv", ["analyze", "--run-dir", str(root), "--out", str(out)]
    )
    assert gate.main() == 0
    result = json.loads(out.read_text())
    assert result["status"] == "exact_event_profile_stop"
    assert result["global_critical_path_validated"] is False
    assert result["collective_cross_stream_completion_validated"] is False
    assert result["profile"]["slowest_rank"] == 2
    assert result["decision"]["largest_kind_on_selected_rank"] == "collective"
    assert result["decision"]["automatic_benchmark_or_submission_authorized"] is False


def test_closure_rejects_mutated_cleanup_evidence(tmp_path):
    root = tmp_path / "run"
    q1, graph = build_run(root)
    profile = gate.validate_profiles(root, graph)
    (root / "graph-event" / "post-workers.txt").write_text("stale worker\n")
    with pytest.raises(SystemExit, match="binding drifted"):
        gate.validate_closure(root, {"q1": q1, "graph-event": graph}, profile)

#!/usr/bin/env python3
"""CPU-only fixtures for the persistent KV-view diagnostic analyzer."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_laguna_persistent_kv_views as gate


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)


def token_hash(token_ids: list[int]) -> str:
    return hashlib.sha256(
        json.dumps(token_ids, separators=(",", ":")).encode()
    ).hexdigest()


def arm_record(root: Path, arm: str) -> dict:
    graph = arm in gate.GRAPH_ARMS
    candidate = arm == "graph-candidate"
    profile_root = root / arm / "replay-profile" if graph else None
    token_ids = list(range(gate.COMPLETION_TOKENS))
    return {
        "schema": "laguna-persistent-kv-view-arm-v1",
        "status": "complete",
        "diagnostic_only": True,
        "single_generate_call": True,
        "fresh_process": True,
        "arm": arm,
        "graph": graph,
        "kv_view_selector": int(candidate),
        "model": gate.EXPECTED_MODEL,
        "draft_model": None if arm == "q1" else gate.EXPECTED_DRAFT,
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
        "prompt_sha256": "a" * 64,
        "prompt_tokens": 17,
        "completion_tokens": gate.COMPLETION_TOKENS,
        "cached_tokens": 0,
        "generation_wall_ns": 1000 if arm == "graph-control" else 900,
        "token_ids": token_ids,
        "token_ids_sha256": token_hash(token_ids),
        "text_sha256": "b" * 64,
        "finish_reason": "length",
        "profile_root": str(profile_root) if graph else None,
        "profile_samples": gate.SAMPLES if graph else None,
        "profile_rank_files": {} if graph else None,
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
        "async_scheduling": arm == "q1",
        "environment": gate.expected_environment(arm, profile_root),
    }


def profile_payload(rank: int, base: int) -> dict:
    durations = {
        "graph": [10] * 146,
        "collective": [20] * 97,
        "attention": [30] * 48,
        "eager": [],
    }
    totals = {kind: sum(values) for kind, values in durations.items()}
    ordered = [
        [kind, duration]
        for kind in ("graph", "collective", "attention", "eager")
        for duration in durations[kind]
    ]
    records = []
    for sample in range(gate.SAMPLES):
        persistent = base < 100
        forward_ns = base + 300
        update_ns = base + 200
        records.append(
            {
                "sample": sample,
                "capture_replay_host_loop_ns": base + 5000,
                "debug_guard_ns": 0,
                "offloader_sync_ns": 10,
                "post_replay_synchronize_ns": base + 1000,
                "replay_host_total_ns": base + 6000,
                "static_signature_collect_ns": 100,
                "static_signature_compare_ns": 50,
                "whole_replay_completion_ns": 2 * base + 7000,
                "kv_view_prepare": {
                    "control_calls": 0 if persistent else 96,
                    "forward_calls": 48,
                    "forward_ns": forward_ns,
                    "persistent_builds": 0,
                    "persistent_calls": 96 if persistent else 0,
                    "persistent_hits": 96 if persistent else 0,
                    "total_calls": 96,
                    "total_ns": forward_ns + update_ns,
                    "update_calls": 48,
                    "update_ns": update_ns,
                },
                "segment_host_call_ns": durations,
                "segment_host_call_total_ns": totals,
                "segment_ordered_host_call_ns": ordered,
            }
        )
    return {
        "schema": "laguna-m8-breakable-replay-profile-v2",
        "status": "complete",
        "rank": rank,
        "samples": gate.SAMPLES,
        "graphs": 146,
        "eager_breaks": 145,
        "boundary_categories": {"attention": 48, "collective": 97},
        "batch_descriptor": "BatchDescriptor(num_tokens=8)",
        "segment_kind_order_sha256": gate.EXPECTED_SEGMENT_ORDER,
        "records": records,
    }


def build_profile_fixture(root: Path, arm: str, base: int) -> dict:
    profile_root = root / arm / "replay-profile"
    profile_root.mkdir(parents=True)
    profile_root.chmod(0o700)
    record = arm_record(root, arm)
    for rank in gate.RANKS:
        path = profile_root / f"rank{rank}.json"
        write_json(path, profile_payload(rank, base + rank))
        record["profile_rank_files"][str(rank)] = {
            "path": str(path),
            "sha256": gate.sha256_file(path),
        }
    return record


def build_parity_fixture(root: Path) -> None:
    parity_root = root / "parity"
    parity_root.mkdir(parents=True)
    parity_root.chmod(0o700)
    for rank in gate.RANKS:
        rows = [
            {
                "case": case,
                "q": q_width,
                "bitwise_equal": True,
                "control_sha256": f"{rank:01x}" * 64,
                "candidate_sha256": f"{rank:01x}" * 64,
                "control_fa_version": 2,
                "candidate_fa_version": 2,
            }
            for case in gate.ATTENTION_CASES
            for q_width in gate.Q_WIDTHS
        ]
        write_json(
            parity_root / f"rank{rank}.json",
            {
                "schema": "laguna-persistent-kv-view-attention-parity-v1",
                "status": "pass",
                "rank": rank,
                "device_name": "Intel(R) Arc(TM) Pro B70 Graphics",
                "visible_xpus": 1,
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
                "control_selector": 0,
                "candidate_selector": 1,
                "control_state_absent": True,
                "candidate_state_present": True,
                "candidate_view_identity_reused": True,
                "non_timing": True,
                "q_outputs": rows,
            },
        )


def test_arm_contract_accepts_all_four_arms(tmp_path):
    for arm in gate.ARMS:
        profile_root = (
            tmp_path / arm / "replay-profile" if arm in gate.GRAPH_ARMS else None
        )
        gate.validate_arm(arm_record(tmp_path, arm), arm, profile_root)


def test_arm_contract_rejects_selector_drift(tmp_path):
    record = arm_record(tmp_path, "graph-candidate")
    record["environment"]["VLLM_XPU_LAGUNA_M8_PERSISTENT_KV_CACHE_VIEWS"] = "0"
    with pytest.raises(SystemExit, match="environment drifted"):
        gate.validate_arm(
            record,
            "graph-candidate",
            tmp_path / "graph-candidate" / "replay-profile",
        )


def test_parity_accepts_q2_q8_on_all_cards(tmp_path):
    build_parity_fixture(tmp_path)
    identities = gate.validate_parity(tmp_path)
    assert set(identities) == {"0", "1", "2", "3"}


def test_parity_rejects_output_drift(tmp_path):
    build_parity_fixture(tmp_path)
    path = tmp_path / "parity" / "rank2.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["q_outputs"][4]["candidate_sha256"] = "f" * 64
    write_json(path, payload)
    with pytest.raises(SystemExit, match="mismatch"):
        gate.validate_parity(tmp_path)


def test_parity_rejects_selector_path_proof_drift(tmp_path):
    build_parity_fixture(tmp_path)
    path = tmp_path / "parity" / "rank1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["candidate_state_present"] = False
    write_json(path, payload)
    with pytest.raises(SystemExit, match="candidate_state_present"):
        gate.validate_parity(tmp_path)


def test_profile_accepts_full_four_rank_contract(tmp_path):
    record = build_profile_fixture(tmp_path, "graph-control", 100)
    result = gate.validate_profile_arm(tmp_path, "graph-control", record)
    assert result["segment_kind_order_sha256"] == gate.EXPECTED_SEGMENT_ORDER
    assert len(result["max_rank_samples"]) == gate.SAMPLES


def test_profile_rejects_sample_count_drift(tmp_path):
    record = build_profile_fixture(tmp_path, "graph-candidate", 90)
    path = tmp_path / "graph-candidate" / "replay-profile" / "rank3.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["records"].pop()
    write_json(path, payload)
    record["profile_rank_files"]["3"]["sha256"] = gate.sha256_file(path)
    with pytest.raises(SystemExit, match="exactly 31 replay rows"):
        gate.validate_profile_arm(tmp_path, "graph-candidate", record)


def test_profile_rejects_kv_preparation_contract_drift(tmp_path):
    record = build_profile_fixture(tmp_path, "graph-candidate", 90)
    path = tmp_path / "graph-candidate" / "replay-profile" / "rank0.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["records"][3]["kv_view_prepare"]["persistent_hits"] = 95
    write_json(path, payload)
    record["profile_rank_files"]["0"]["sha256"] = gate.sha256_file(path)
    with pytest.raises(SystemExit, match="KV preparation mode drifted"):
        gate.validate_profile_arm(tmp_path, "graph-candidate", record)


def test_profile_rejects_segment_order_drift(tmp_path):
    record = build_profile_fixture(tmp_path, "graph-control", 100)
    path = tmp_path / "graph-control" / "replay-profile" / "rank1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["segment_kind_order_sha256"] = "c" * 64
    write_json(path, payload)
    record["profile_rank_files"]["1"]["sha256"] = gate.sha256_file(path)
    with pytest.raises(SystemExit, match="segment-order identity drifted"):
        gate.validate_profile_arm(tmp_path, "graph-control", record)


def test_parity_runner_uses_real_selector_paths():
    source = (
        Path(__file__)
        .with_name("run_laguna_persistent_kv_view_parity.py")
        .read_text(encoding="utf-8")
    )
    assert "_XPUPersistentKVCacheViews" not in source
    assert (
        "from vllm_xpu_kernels.flash_attn_interface import flash_attn_varlen_func"
    ) in source
    assert "FlashAttentionImpl(**impl_args)" in source
    assert (
        source.count('os.environ["VLLM_XPU_LAGUNA_M8_PERSISTENT_KV_CACHE_VIEWS"]') == 2
    )
    assert "control_impl._xpu_persistent_kv_cache_views is not None" in source
    assert "candidate_impl._xpu_persistent_kv_cache_views is None" in source


def test_controller_isolates_and_audits_parity_process_groups():
    source = (
        Path(__file__)
        .with_name("run_laguna_persistent_kv_view_diagnostic.sh")
        .read_text(encoding="utf-8")
    )
    assert source.count("exec setsid /usr/bin/timeout") >= 2
    assert source.count('active_pg="$!"') >= 2
    assert "parity-post-workers-rank${rank}.txt" in source
    assert "parity_survivors" in source

#!/usr/bin/env python3
"""Synthetic ABI, parser, corruption, and identity tests for Q4 traces."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from qwen27_dflash_trace_format import (  # noqa: E402
    FEATURE_BYTES,
    FLAG_COMPLETE,
    HEADER_BYTES,
    HIDDEN_SIZE,
    N_LAYERS,
    ROW_BYTES,
    ROW_FLAG_GENERATED,
    ROW_FLAG_PROMPT,
    TARGET_LAYER_IDS,
    TraceHeader,
    pack_header,
    read_trace,
    sha256_file,
    write_row,
)


PARSER_PATH = SCRIPTS / "parse-qwen27-dflash-q4-target-trace.py"
SPEC = importlib.util.spec_from_file_location("qwen27_q4_trace_parser", PARSER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {PARSER_PATH}")
PARSER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PARSER
SPEC.loader.exec_module(PARSER)

COLLECTOR_PATH = SCRIPTS / "collect-qwen27-dflash-q4-training-corpus.py"
COLLECTOR_SPEC = importlib.util.spec_from_file_location(
    "qwen27_q4_trace_collector", COLLECTOR_PATH
)
if COLLECTOR_SPEC is None or COLLECTOR_SPEC.loader is None:
    raise RuntimeError(f"cannot import {COLLECTOR_PATH}")
COLLECTOR = importlib.util.module_from_spec(COLLECTOR_SPEC)
sys.modules[COLLECTOR_SPEC.name] = COLLECTOR
COLLECTOR_SPEC.loader.exec_module(COLLECTOR)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def make_trace(
    path: Path,
    *,
    target_sha: str,
    draft_sha: str,
    runtime_commit: str,
    runtime_patch_sha: str,
    prompt_sha: str,
    complete: bool = True,
    start_position: int = 0,
) -> None:
    row_count = 5
    header = TraceHeader(
        flags=FLAG_COMPLETE if complete else 0,
        request_ordinal=7,
        num_prompt_tokens=3,
        row_count=row_count,
        n_layers=N_LAYERS,
        hidden_size=HIDDEN_SIZE,
        target_model_sha256=target_sha,
        draft_model_sha256=draft_sha,
        runtime_commit=runtime_commit,
        runtime_dirty_patch_sha256=runtime_patch_sha,
        prompt_sha256=prompt_sha,
        target_layer_ids=TARGET_LAYER_IDS,
        payload_bytes=row_count * ROW_BYTES,
    )
    with path.open("wb") as handle:
        handle.write(pack_header(header))
        for index in range(row_count):
            features = torch.full(
                (N_LAYERS, HIDDEN_SIZE), float(index), dtype=torch.bfloat16
            )
            write_row(
                handle,
                token_id=100 + index,
                next_token_id=101 + index,
                position=start_position + index,
                flags=ROW_FLAG_PROMPT if index < 3 else ROW_FLAG_GENERATED,
                features_bf16=features,
            )


def make_collector(path: Path, payload_path: Path, prompt_sha: str) -> None:
    write_json(
        path,
        {
            "schema": "qwen27_dflash_q4_native_collector_summary_v1",
            "split": "heldout",
            "records": [
                {
                    "ordinal": 7,
                    "prompt_id": "synthetic-heldout",
                    "family": "synthetic-family",
                    "task": "synthetic-task",
                    "variant": "synthetic-variant",
                    "prompt_sha256": prompt_sha,
                    "request_id": "qwen27-dflash-q4-heldout-000007",
                    "payload": str(payload_path),
                    "payload_sha256": sha256_file(payload_path),
                }
            ],
        },
    )


def expect_failure(label: str, function, pattern: str) -> None:
    try:
        function()
    except (ValueError, OSError) as exc:
        if pattern not in str(exc):
            raise AssertionError(f"{label}: wrong failure: {exc}") from exc
        print(f"{label}=PASS ({exc})")
        return
    raise AssertionError(f"{label}: expected failure")


def main() -> int:
    plan_source = (
        ROOT
        / "data/qwen27-dflash-q4-adaptation-capture-20260713/capture-plan.json"
    )
    plan = json.loads(plan_source.read_text())
    active = plan["active_product"]
    prompt_sha = "ab" * 32
    with tempfile.TemporaryDirectory(prefix="qwen27-q4-trace-test-") as raw_tmp:
        tmp = Path(raw_tmp)
        plan_path = tmp / "plan.json"
        write_json(plan_path, plan)
        contract = plan["native_capture"]["required_server_contract"]
        session = {
            "schema": "qwen27_dflash_native_capture_session_v1",
            "capture_hook_active": True,
            "capture_dir": str(tmp),
            "capture_mode": "linear_target_no_speculation",
            "target_model_sha256": active["target_model_sha256"],
            "draft_model_sha256": active["draft_model_sha256"],
            "runtime_commit": active["runtime"]["commit"],
            "runtime_dirty_patch_sha256": active["runtime"][
                "dirty_patch_sha256"
            ],
            "reasoning": "off",
            **contract,
        }
        assert COLLECTOR.validate_session(plan, session, tmp / "session.json") == tmp
        wrong_session = dict(session, parallel=2)
        expect_failure(
            "parallel_session_mismatch_rejected",
            lambda: COLLECTOR.validate_session(
                plan, wrong_session, tmp / "session.json"
            ),
            "parallel slots",
        )
        control_path = COLLECTOR.publish_request_control(
            capture_dir=tmp,
            plan=plan,
            split="heldout",
            ordinal=7,
            prompt_hash=prompt_sha,
            request_id="qwen27-dflash-q4-heldout-000007",
            max_tokens=160,
        )
        control = json.loads(control_path.read_text())
        assert control["target_model_sha256"] == active["target_model_sha256"]
        expect_failure(
            "stale_request_control_rejected",
            lambda: COLLECTOR.publish_request_control(
                capture_dir=tmp,
                plan=plan,
                split="heldout",
                ordinal=8,
                prompt_hash=prompt_sha,
                request_id="qwen27-dflash-q4-heldout-000008",
                max_tokens=160,
            ),
            "stale native request control",
        )
        control_path.unlink()
        print("session_and_request_control=PASS")

        payload = tmp / "request-000007.qdft"
        make_trace(
            payload,
            target_sha=active["target_model_sha256"],
            draft_sha=active["draft_model_sha256"],
            runtime_commit=active["runtime"]["commit"],
            runtime_patch_sha=active["runtime"]["dirty_patch_sha256"],
            prompt_sha=prompt_sha,
        )
        assert payload.stat().st_size == HEADER_BYTES + 5 * ROW_BYTES
        assert FEATURE_BYTES == 5 * 5120 * 2
        header, rows = read_trace(payload)
        assert header.row_count == 5
        assert rows.input_token_ids.tolist() == [100, 101, 102, 103, 104]
        assert rows.sampled_next_token_ids.tolist() == [101, 102, 103, 104, 105]
        assert tuple(rows.aux_hidden_states.shape) == (5, 5, 5120)
        assert torch.equal(
            rows.aux_hidden_states[:, 0, 0],
            torch.arange(5, dtype=torch.bfloat16),
        )
        print("binary_roundtrip=PASS")

        collector = tmp / "collector.json"
        make_collector(collector, payload, prompt_sha)
        out_dir = tmp / "dataset"
        summary = PARSER.convert(
            plan_path=plan_path, collector_path=collector, out_dir=out_dir
        )
        assert summary["samples"] == 1
        assert summary["total_rows"] == 5
        sample_path = Path(summary["records"][0]["sample"])
        sample = torch.load(sample_path, map_location="cpu", weights_only=False)
        assert sample["format"] == "qwen36_eagle_sequence_v2"
        assert sample["schema_variant"] == "exact_q4_dflash_target_trace_v1"
        assert tuple(sample["aux_hidden_states"].shape) == (5, 5, 5120)
        assert sample["num_prompt_tokens"] == 3
        assert sample["loss_mask"].tolist() == [0, 0, 1, 1, 1]
        print("sequence_v2_conversion=PASS")

        truncated = tmp / "truncated.qdft"
        truncated.write_bytes(payload.read_bytes()[:-1])
        expect_failure(
            "truncated_payload_rejected",
            lambda: read_trace(truncated),
            "file size",
        )

        wrong_target = tmp / "wrong-target.qdft"
        make_trace(
            wrong_target,
            target_sha="ff" * 32,
            draft_sha=active["draft_model_sha256"],
            runtime_commit=active["runtime"]["commit"],
            runtime_patch_sha=active["runtime"]["dirty_patch_sha256"],
            prompt_sha=prompt_sha,
        )
        wrong_collector = tmp / "wrong-collector.json"
        make_collector(wrong_collector, wrong_target, prompt_sha)
        expect_failure(
            "target_identity_mismatch_rejected",
            lambda: PARSER.convert(
                plan_path=plan_path,
                collector_path=wrong_collector,
                out_dir=tmp / "wrong-dataset",
            ),
            "target model sha256",
        )

        wrong_runtime = tmp / "wrong-runtime.qdft"
        make_trace(
            wrong_runtime,
            target_sha=active["target_model_sha256"],
            draft_sha=active["draft_model_sha256"],
            runtime_commit="ee" * 20,
            runtime_patch_sha=active["runtime"]["dirty_patch_sha256"],
            prompt_sha=prompt_sha,
        )
        wrong_runtime_collector = tmp / "wrong-runtime-collector.json"
        make_collector(wrong_runtime_collector, wrong_runtime, prompt_sha)
        expect_failure(
            "runtime_identity_mismatch_rejected",
            lambda: PARSER.convert(
                plan_path=plan_path,
                collector_path=wrong_runtime_collector,
                out_dir=tmp / "wrong-runtime-dataset",
            ),
            "runtime commit",
        )

        bad_position = tmp / "bad-position.qdft"
        make_trace(
            bad_position,
            target_sha=active["target_model_sha256"],
            draft_sha=active["draft_model_sha256"],
            runtime_commit=active["runtime"]["commit"],
            runtime_patch_sha=active["runtime"]["dirty_patch_sha256"],
            prompt_sha=prompt_sha,
            start_position=1,
        )
        expect_failure(
            "prompt_reuse_position_rejected",
            lambda: read_trace(bad_position),
            "position zero",
        )

        incomplete = tmp / "incomplete.qdft"
        make_trace(
            incomplete,
            target_sha=active["target_model_sha256"],
            draft_sha=active["draft_model_sha256"],
            runtime_commit=active["runtime"]["commit"],
            runtime_patch_sha=active["runtime"]["dirty_patch_sha256"],
            prompt_sha=prompt_sha,
            complete=False,
        )
        expect_failure(
            "incomplete_trace_rejected",
            lambda: read_trace(incomplete),
            "not marked complete",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

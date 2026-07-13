#!/usr/bin/env python3
"""Convert exact native Q4 DFlash traces to offline training samples."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Sequence

import torch

from qwen27_dflash_trace_format import (
    ROW_FLAG_GENERATED,
    TARGET_LAYER_IDS,
    read_trace,
    sha256_file,
)


PLAN_SCHEMA = "qwen27_dflash_q4_adaptation_capture_plan_v1"
COLLECTOR_SCHEMA = "qwen27_dflash_q4_native_collector_summary_v1"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate exact-Q4 native target-feature traces and emit the "
            "qwen36_eagle_sequence_v2 subset used by DFlash training."
        )
    )
    parser.add_argument("--plan", required=True)
    parser.add_argument("--collector-summary", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument(
        "--hidden-dtype",
        choices=("bf16",),
        default="bf16",
        help="Only BF16 is accepted for the current trainer contract.",
    )
    return parser.parse_args(argv)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return payload


def require_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise ValueError(f"{label}: expected {expected!r}, got {actual!r}")


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")[:160]


def resolve_payload_path(record: dict[str, Any], collector_path: Path) -> Path:
    raw = record.get("payload") or record.get("payload_path")
    if not raw:
        trace_path = Path(str(record["trace"]))
        if not trace_path.is_absolute():
            trace_path = (collector_path.parent / trace_path).resolve()
        trace_meta = load_json(trace_path)
        raw = trace_meta.get("payload_path")
        if not raw:
            raise ValueError(f"{trace_path}: missing payload_path")
        payload_path = Path(str(raw))
        if not payload_path.is_absolute():
            payload_path = (trace_path.parent / payload_path).resolve()
        return payload_path
    payload_path = Path(str(raw))
    if not payload_path.is_absolute():
        payload_path = (collector_path.parent / payload_path).resolve()
    return payload_path


def convert_record(
    *,
    record: dict[str, Any],
    plan: dict[str, Any],
    collector_path: Path,
    out_dir: Path,
) -> dict[str, Any]:
    payload_path = resolve_payload_path(record, collector_path)
    expected_payload_sha = str(record.get("payload_sha256") or "")
    actual_payload_sha = sha256_file(payload_path)
    require_equal("payload sha256", actual_payload_sha, expected_payload_sha)
    header, rows = read_trace(payload_path)
    active = plan["active_product"]
    require_equal(
        "target model sha256",
        header.target_model_sha256,
        active["target_model_sha256"],
    )
    require_equal(
        "draft model sha256",
        header.draft_model_sha256,
        active["draft_model_sha256"],
    )
    require_equal(
        "runtime commit", header.runtime_commit, active["runtime"]["commit"]
    )
    require_equal(
        "runtime dirty patch sha256",
        header.runtime_dirty_patch_sha256,
        active["runtime"]["dirty_patch_sha256"],
    )
    require_equal(
        "prompt sha256", header.prompt_sha256, str(record["prompt_sha256"])
    )
    require_equal("request ordinal", header.request_ordinal, int(record["ordinal"]))
    require_equal("target layer IDs", header.target_layer_ids, TARGET_LAYER_IDS)

    generated_mask = rows.row_flags.bitwise_and(ROW_FLAG_GENERATED).ne(0)
    loss_mask = generated_mask.to(torch.int64)
    # The prompt's final row predicts the first generated token and is therefore
    # a valid response anchor even though its input token belongs to the prompt.
    if header.num_prompt_tokens - 1 < header.row_count:
        loss_mask[header.num_prompt_tokens - 1] = 1

    prompt_id = str(record.get("prompt_id") or f"request-{header.request_ordinal}")
    request_id = str(record.get("request_id") or prompt_id)
    sample = {
        "format": "qwen36_eagle_sequence_v2",
        "schema_variant": "exact_q4_dflash_target_trace_v1",
        "req_id": request_id,
        "request_metadata": {
            "source_suite": str(Path(plan["prompt_policy"]["suite"]).resolve()),
            "capture_plan_schema": str(plan["schema"]),
            "capture_identity": {
                "target_model_sha256": header.target_model_sha256,
                "draft_model_sha256": header.draft_model_sha256,
                "runtime_commit": header.runtime_commit,
                "runtime_dirty_patch_sha256": header.runtime_dirty_patch_sha256,
                "target_layer_input_ids": list(header.target_layer_ids),
                "capture_mode": "linear_target_no_speculation",
            },
            "metadata": {
                "task": record.get("task"),
                "variant": record.get("variant"),
            },
        },
        "prompt_id": prompt_id,
        "family": str(record.get("family") or "unknown"),
        "prompt_sha256": header.prompt_sha256,
        "input_ids": rows.input_token_ids,
        "positions": rows.positions,
        "loss_mask": loss_mask,
        "sampled_next_token_ids": rows.sampled_next_token_ids,
        "num_prompt_tokens": header.num_prompt_tokens,
        "source_files": [str(payload_path)] * header.row_count,
        "aux_hidden_states": rows.aux_hidden_states,
    }
    output_path = out_dir / (
        f"sample-{header.request_ordinal:06d}-{safe_name(request_id)}.pt"
    )
    torch.save(sample, output_path)
    return {
        "ordinal": header.request_ordinal,
        "prompt_id": prompt_id,
        "family": sample["family"],
        "prompt_sha256": header.prompt_sha256,
        "rows": header.row_count,
        "num_prompt_tokens": header.num_prompt_tokens,
        "generated_training_rows": int(loss_mask.sum().item()),
        "payload": str(payload_path),
        "payload_sha256": actual_payload_sha,
        "sample": str(output_path.resolve()),
    }


def convert(
    *, plan_path: Path, collector_path: Path, out_dir: Path
) -> dict[str, Any]:
    plan = load_json(plan_path)
    collector = load_json(collector_path)
    require_equal("plan schema", plan.get("schema"), PLAN_SCHEMA)
    require_equal("collector schema", collector.get("schema"), COLLECTOR_SCHEMA)
    if collector.get("split") not in ("train", "heldout"):
        raise ValueError("collector split must be train or heldout")
    records = collector.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("collector contains no trace records")
    out_dir.mkdir(parents=True, exist_ok=True)
    converted = [
        convert_record(
            record=record,
            plan=plan,
            collector_path=collector_path,
            out_dir=out_dir,
        )
        for record in records
    ]
    prompt_hashes = [record["prompt_sha256"] for record in converted]
    if len(prompt_hashes) != len(set(prompt_hashes)):
        raise ValueError("collector contains duplicate prompt hashes")
    summary = {
        "schema": "qwen27_dflash_q4_parsed_dataset_summary_v1",
        "classification": (
            "diagnostic_exact_q4_training_data_not_endpoint_not_localmaxxing"
        ),
        "plan": str(plan_path.resolve()),
        "collector_summary": str(collector_path.resolve()),
        "split": collector["split"],
        "target_model_sha256": plan["active_product"]["target_model_sha256"],
        "draft_model_sha256": plan["active_product"]["draft_model_sha256"],
        "runtime_commit": plan["active_product"]["runtime"]["commit"],
        "runtime_dirty_patch_sha256": plan["active_product"]["runtime"][
            "dirty_patch_sha256"
        ],
        "target_layer_input_ids": list(TARGET_LAYER_IDS),
        "samples": len(converted),
        "total_rows": sum(record["rows"] for record in converted),
        "generated_training_rows": sum(
            record["generated_training_rows"] for record in converted
        ),
        "records": converted,
        "localmaxxing_eligible": False,
    }
    summary_path = out_dir / "dataset-summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    summary = convert(
        plan_path=Path(args.plan).expanduser().resolve(),
        collector_path=Path(args.collector_summary).expanduser().resolve(),
        out_dir=Path(args.out_dir).expanduser().resolve(),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

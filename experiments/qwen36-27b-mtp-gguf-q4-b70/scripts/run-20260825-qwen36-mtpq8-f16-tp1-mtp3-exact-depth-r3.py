#!/usr/bin/env python3
"""R3 retry with an explicit minimal-token definition for display context zero."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from typing import Any


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
OVERLAY = LANE / "data/2026-08-25-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r3-prereg.json"
R2_MANIFEST = LANE / "data/2026-08-25-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r2-prereg.json"
R2_RUNNER = LANE / "scripts/run-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r2.py"
R2_VALIDATOR = LANE / "scripts/validate-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r2.py"
R2_FAILURE = LANE / "data/2026-08-25-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r2-depth0-failure.json"
R2_TERMINAL = Path("/mnt/fast-ai/bench-results/qwen36-mtpq8-f16-tp1-mtp3-exact-depth-20260825-r2/terminal-receipt.json")
CAMPAIGN_ID = "qwen36-mtpq8-f16-tp1-mtp3-exact-depth-20260825-r3"
RUN_ROOT = "/mnt/fast-ai/bench-results/qwen36-mtpq8-f16-tp1-mtp3-exact-depth-20260825-r3"
RUNNER_REL = "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r3.py"
VALIDATOR_REL = "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/validate-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r3.py"
ZERO_TOKEN_ID = 90
ZERO_TOKEN_HASH = "a84008063efed1c9b2748f2e71222aaa0449298aeabd82ca3314caf81d9c981e"
ZERO_RECEIPT_SCHEMA = "openai-token-zero-prior-context-benchmark-v1"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R2 = load_module(R2_RUNNER, "qwen36_mtp3_r2_for_r3")
BASE = R2.BASE
ORIGINAL_LOAD_JSON = BASE.load_json
ORIGINAL_RUN_DEPTH = BASE.Execution.run_depth


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def load_overlay() -> dict[str, Any]:
    value = json.loads(OVERLAY.read_text(encoding="utf-8"))
    zero = value.get("zero_context_semantics") or {}
    positive = value.get("positive_depth_contract") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-mtp3-exact-depth-r3-zero-context-overlay.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and zero.get("display_context_axis_tokens") == 0
        and zero.get("submitted_prompt_token_ids") == [ZERO_TOKEN_ID]
        and zero.get("submitted_prompt_token_ids_sha256") == ZERO_TOKEN_HASH
        and zero.get("expected_usage_prompt_tokens") == 1
        and zero.get("expected_cached_tokens") == 0
        and positive.get("depths") == [2048, 4096, 8192, 16384, 24576, 32768]
        and positive.get("delta_from_r2") is False
        and value.get("r3_lifecycle", {}).get("output_root") == RUN_ROOT
    ):
        raise RuntimeError("R3 overlay invariant failed")
    return value


def verify_references(value: dict[str, Any]) -> None:
    base, failure = value["base_packet"], value["r2_failure"]
    for path, expected, label in (
        (R2_MANIFEST, base["manifest_sha256"], "R2 manifest"),
        (R2_RUNNER, base["runner_sha256"], "R2 runner"),
        (R2_VALIDATOR, base["validator_sha256"], "R2 validator"),
        (R2_FAILURE, failure["failure_record_sha256"], "R2 failure record"),
        (R2_TERMINAL, failure["terminal_receipt_sha256"], "R2 terminal"),
    ):
        if not path.is_file() or sha256_file(path) != expected:
            raise RuntimeError(f"{label} changed: {path}")
    fixture_path = REPO / "data/qwen27-exact-depth/qwen36-6a9e13bd-exact-depth-v1.json"
    if sha256_file(fixture_path) != value["positive_depth_contract"]["fixture_sha256"]:
        raise RuntimeError("exact-depth fixture changed")
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    if fixture["cases"][1]["id"] != "depth-2048" or fixture["cases"][1]["prompt_token_ids"][0] != ZERO_TOKEN_ID:
        raise RuntimeError("minimal explicit token source drift")


def merge_manifest(value: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(R2.merge_manifest(R2.load_overlay()))
    merged["campaign_id"] = CAMPAIGN_ID
    merged["purpose"] += " R3 defines display x=0 as zero prior active context followed by one explicit ordinary token."
    merged["lifecycle"]["runner"] = RUNNER_REL
    merged["lifecycle"]["validator"] = VALIDATOR_REL
    merged["lifecycle"]["output_root"] = RUN_ROOT
    merged["lifecycle"]["exact_ack"] = f"RUN {CAMPAIGN_ID}"
    merged["zero_context_semantics"] = copy.deepcopy(value["zero_context_semantics"])
    merged["positive_depth_contract"] = copy.deepcopy(value["positive_depth_contract"])
    merged["retry_overlay"] = {
        "schema": value["schema"],
        "r2_terminal_receipt_sha256": value["r2_failure"]["terminal_receipt_sha256"],
        "r1_r2_rows_reused": False,
    }
    return merged


def load_json(path: Path) -> dict[str, Any]:
    if Path(path).resolve() == OVERLAY.resolve():
        return merge_manifest(load_overlay())
    return ORIGINAL_LOAD_JSON(path)


def zero_receipt(module, row: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
    details = usage.get("prompt_tokens_details") if isinstance(usage.get("prompt_tokens_details"), dict) else {}
    timing = module.metric_window(row["token_id_offsets_s"])
    checks = {
        "zero_prior_active_context": True,
        "one_explicit_prompt_token": usage.get("prompt_tokens") == 1,
        "cached_tokens_zero": details.get("cached_tokens") == 0,
        "completion_tokens_exact": usage.get("completion_tokens") == 128,
        "total_tokens_exact": usage.get("total_tokens") == 129,
        "stream_token_ids_exact": len(row["token_ids"]) == 128,
        "metric_events_exact": timing["timestamped_events"] == 100,
        "metric_intervals_exact": timing["inter_token_intervals"] == 99,
        "metric_span_positive": isinstance(timing["conventional_99_interval_tok_s"], (int, float)) and math.isfinite(timing["conventional_99_interval_tok_s"]) and timing["conventional_99_interval_tok_s"] > 0,
        "finish_reason_length": row["finish_reasons"] == ["length"],
        "done_seen": row["done_seen"] is True,
        "no_context_shift_reported": row["verbose_context_shift"] in {None, False},
        "llama_prompt_not_truncated": row["verbose_truncated"] is False,
        "llama_stop_is_limit": row["verbose_stop_type"] == "limit",
        "llama_cache_zero_if_reported": row["llama_cache_n"] in {None, 0},
    }
    payload = module.request_payload(model=manifest["server_contract"]["model_alias"], prompt_token_ids=[ZERO_TOKEN_ID], adapter="llama-server")
    return {
        "schema": ZERO_RECEIPT_SCHEMA,
        "status": "passed" if all(checks.values()) else "failed",
        "run_identity": {
            "model": manifest["server_contract"]["model_alias"],
            "display_context_axis_tokens": 0,
            "prior_active_context_tokens": 0,
            "submitted_prompt_tokens": 1,
            "configured_context_capacity": manifest["server_contract"]["context_capacity"],
            "case_id": "depth-0-minimal-explicit-token-90",
            "max_tokens": 128,
            "metric_events": 100,
            "metric_intervals": 99,
        },
        "fixture": {
            "fixture_sha256": manifest["fixture"]["sha256"],
            "original_depth_zero_prompt_token_ids_sha256": manifest["fixture"]["prompt_token_ids_sha256"][0],
            "minimal_explicit_prompt_token_id": ZERO_TOKEN_ID,
            "minimal_explicit_prompt_token_ids_sha256": ZERO_TOKEN_HASH,
            "token_source": manifest["zero_context_semantics"]["token_source"],
        },
        "request": module.request_summary(payload),
        "gate": {"passed": all(checks.values()), "checks": checks},
        "metric_window": timing,
        "context_semantics": {
            "display_x": 0,
            "definition": manifest["zero_context_semantics"]["definition"],
            "required_site_disclosure": manifest["zero_context_semantics"]["required_site_disclosure"],
            "literal_empty_prompt": False,
            "raw_engine_zero_token_invocation": False,
        },
        "response": {key: item for key, item in row.items() if key not in {"token_id_offsets_s", "returned_prompt_token_ids"}} | {
            "output_token_ids_sha256": module.token_ids_sha256(row["token_ids"]),
            "returned_prompt_token_ids_sha256": None if row["returned_prompt_token_ids"] is None else module.token_ids_sha256(row["returned_prompt_token_ids"]),
        },
    }


def run_depth_r3(self, arm: str, depth: int, candidate: bool) -> None:
    if depth != 0:
        return ORIGINAL_RUN_DEPTH(self, arm, depth, candidate)
    directory = self.root / arm / "depth-0"
    directory.mkdir()
    before = len(BASE.acceptance_rows(self.root / arm / "server.log")) if candidate else 0
    module = BASE.load_depth_client(BASE.referenced_path(self.m["clients"]["exact_depth"]["path"]))
    payload = module.request_payload(model=self.m["server_contract"]["model_alias"], prompt_token_ids=[ZERO_TOKEN_ID], adapter="llama-server")
    row = module.post_stream(
        base_url=f"http://127.0.0.1:{self.port}", payload=payload,
        timeout=self.m["lifecycle"]["request_timeout_seconds"], requested_adapter="llama-server",
        request_id="depth-zero-prior-context-minimal-token-90",
    )
    receipt = zero_receipt(module, row, self.m)
    BASE.write_json_x(directory / "exact-depth.json", receipt)
    with (directory / "exact-depth.stdout.json").open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True); stream.write("\n")
    if not receipt["gate"]["passed"]:
        raise BASE.GateError("zero-prior-context minimal-token receipt failed")
    if candidate:
        deadline = time.monotonic() + 30
        rows = BASE.acceptance_rows(self.root / arm / "server.log")
        while len(rows) <= before and time.monotonic() < deadline:
            time.sleep(0.2); rows = BASE.acceptance_rows(self.root / arm / "server.log")
        BASE.write_json_x(directory / "draft-counters.json", {"depth": 0, "rows_before": before, "rows_after": len(rows), "new_rows": rows[before:]})


OVERLAY_VALUE = load_overlay()
verify_references(OVERLAY_VALUE)
BASE.CAMPAIGN_ID = CAMPAIGN_ID
BASE.ACK = f"RUN {CAMPAIGN_ID}"
BASE.MANIFEST = OVERLAY
BASE.VALIDATOR = LANE / "scripts" / VALIDATOR_REL.split("/")[-1]
BASE.load_json = load_json
BASE.Execution.run_depth = run_depth_r3


def main() -> int:
    verify_references(load_overlay())
    return BASE.main()


if __name__ == "__main__":
    raise SystemExit(main())

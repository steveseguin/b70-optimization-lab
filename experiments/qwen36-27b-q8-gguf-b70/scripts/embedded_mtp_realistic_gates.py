#!/usr/bin/env python3
"""Strict offline gates for the once-only Qwen3.6 Q8 embedded-MTP suite.

The live wrapper uses the generic OpenAI streaming benchmark exactly once per
prompt.  This module recomputes the conventional 99-interval metric, binds the
12 responses to Prometheus deltas, reports the context-incompatible legacy
prefix comparison diagnostically, and proves full token/content equality to a
fresh matched control. It contains no network or device code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import embedded_mtp_vdr2_gates as sealed


MODEL_SHA256 = "9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8"
RUNTIME_SHA256 = "1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7"
SUITE_SHA256 = "df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac"
PREFIX_ORACLE_SHA256 = (
    "e07298632346a62f78af9d532593c15f8622b166104ee157bf383bed25228b9d"
)
SUITE_ID = "qwen36-27b-autoround-int4-b70-realistic-v1"
PROMPT_IDS = (
    "incident-retrospective",
    "code-review",
    "customer-email",
    "sql-debugging",
    "release-plan",
    "benchmark-analysis",
    "architecture-tradeoff",
    "bug-report-synthesis",
    "technical-guide",
    "risk-register",
    "performance-hypotheses",
    "decision-memo",
)
ALIASES = {
    "control": "qwen36-27b-mtp-q8-vdr2-realistic-control",
    "mtp3": "qwen36-27b-mtp-q8-vdr2-realistic-mtp3",
}
QUALITY_REFERENCE = "matched_fresh_control_v1"
LEGACY_PREFIX_ORACLE_IDENTITY = {"ctx_size": 4096, "max_tokens": 128}
CURRENT_REALISTIC_IDENTITY = {"ctx_size": 32768, "max_tokens": 512}
LEGACY_PREFIX_DIAGNOSTIC_CHECK = "legacy_prefix_oracle_match"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def positive_number(value: Any) -> bool:
    return finite_number(value) and value > 0


def token_ids(value: Any, maximum_count: int = 128) -> bool:
    return (
        isinstance(value, list)
        and 100 <= len(value) <= maximum_count
        and all(
            isinstance(token, int) and not isinstance(token, bool) and token >= 0
            for token in value
        )
    )


def longest_common_prefix_tokens(
    observed: Any, expected: Any, maximum_count: int = 128
) -> int | None:
    """Count equal leading token IDs for diagnostic legacy-oracle evidence."""
    if not isinstance(observed, list) or not isinstance(expected, list):
        return None
    compared = min(len(observed), len(expected), maximum_count)
    for index in range(compared):
        if observed[index] != expected[index]:
            return index
    return compared


def hard_row_checks_pass(checks: dict[str, bool]) -> bool:
    """Pass every row gate except the explicitly diagnostic legacy prefix."""
    diagnostic = checks.get(LEGACY_PREFIX_DIAGNOSTIC_CHECK)
    if not isinstance(diagnostic, bool):
        return False
    return all(
        value is True
        for name, value in checks.items()
        if name != LEGACY_PREFIX_DIAGNOSTIC_CHECK
    )


def unique_subsequence_positions(
    complete: list[int], streamed: list[int]
) -> list[int] | None:
    """Return the unique streamed-to-complete mapping, or fail closed."""
    complete_n = len(complete)
    streamed_n = len(streamed)
    if streamed_n > complete_n:
        return None
    counts = [[0] * (streamed_n + 1) for _ in range(complete_n + 1)]
    counts[complete_n][streamed_n] = 1
    for complete_i in range(complete_n - 1, -1, -1):
        counts[complete_i][streamed_n] = 1
        for streamed_i in range(streamed_n - 1, -1, -1):
            ways = counts[complete_i + 1][streamed_i]
            if complete[complete_i] == streamed[streamed_i]:
                ways += counts[complete_i + 1][streamed_i + 1]
            counts[complete_i][streamed_i] = min(2, ways)
    if counts[0][0] != 1:
        return None
    positions: list[int] = []
    complete_i = 0
    streamed_i = 0
    while streamed_i < streamed_n:
        if complete_i >= complete_n:
            return None
        skip = counts[complete_i + 1][streamed_i]
        match = 0
        if complete[complete_i] == streamed[streamed_i]:
            match = counts[complete_i + 1][streamed_i + 1]
        if match == 1 and skip == 0:
            positions.append(complete_i)
            complete_i += 1
            streamed_i += 1
        elif skip == 1 and match == 0:
            complete_i += 1
        else:
            return None
    return positions


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * pct
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    fraction = position - low
    return ordered[low] * (1.0 - fraction) + ordered[high] * fraction


def stats(values: list[float]) -> dict[str, float | int]:
    if not values:
        raise ValueError("cannot summarize an empty value list")
    return {
        "count": len(values),
        "p10": percentile(values, 0.10),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "min": min(values),
        "max": max(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def stats_match(observed: Any, expected: dict[str, float | int]) -> bool:
    if not isinstance(observed, dict) or set(expected) - set(observed):
        return False
    for key, value in expected.items():
        candidate = observed.get(key)
        if key == "count":
            if candidate != value:
                return False
        elif not finite_number(candidate) or not math.isclose(
            float(candidate), float(value), rel_tol=0, abs_tol=1e-12
        ):
            return False
    return True


def load_suite(path: Path) -> tuple[list[str], list[str]]:
    if sha256_file(path) != SUITE_SHA256:
        raise ValueError("fixed realistic suite SHA-256 mismatch")
    suite = read_object(path)
    prompts = suite.get("prompts")
    if (
        suite.get("suite_id") != SUITE_ID
        or not isinstance(prompts, list)
        or len(prompts) != len(PROMPT_IDS)
    ):
        raise ValueError("fixed realistic suite schema mismatch")
    ids: list[str] = []
    hashes: list[str] = []
    for entry in prompts:
        if not isinstance(entry, dict):
            raise ValueError("fixed realistic suite prompt is not an object")
        prompt_id = entry.get("id")
        prompt = entry.get("prompt")
        if not isinstance(prompt_id, str) or not isinstance(prompt, str) or not prompt:
            raise ValueError("fixed realistic suite prompt is incomplete")
        ids.append(prompt_id)
        hashes.append(hashlib.sha256(prompt.encode()).hexdigest())
    if tuple(ids) != PROMPT_IDS or len(set(hashes)) != len(hashes):
        raise ValueError("fixed realistic suite prompt identity mismatch")
    return ids, hashes


def load_prefix_oracle(path: Path) -> dict[str, Any]:
    if sha256_file(path) != PREFIX_ORACLE_SHA256:
        raise ValueError("integrated prefix oracle SHA-256 mismatch")
    oracle = read_object(path)
    identity = oracle.get("run_identity") or {}
    rows = oracle.get("rows")
    checks = {
        "baseline": (oracle.get("oracle_comparison") or {}).get("status")
        == "BASELINE_CAPTURE_READY",
        "intrinsic": (oracle.get("intrinsic_gate") or {}).get("passed") is True,
        "suite": identity.get("suite_sha256") == SUITE_SHA256,
        "model": identity.get("model_sha256") == MODEL_SHA256,
        "runtime": identity.get("runtime_sha256") == RUNTIME_SHA256,
        "ctx_size": identity.get("ctx_size")
        == LEGACY_PREFIX_ORACLE_IDENTITY["ctx_size"],
        "max_tokens": identity.get("max_tokens")
        == LEGACY_PREFIX_ORACLE_IDENTITY["max_tokens"],
        "seed": identity.get("seed") == 1,
        "greedy": identity.get("temperature") == 0 and identity.get("top_p") == 1,
        "prompt_order": identity.get("prompt_ids") == list(PROMPT_IDS),
        "rows": isinstance(rows, list) and len(rows) == len(PROMPT_IDS),
    }
    if not all(checks.values()):
        raise ValueError(f"integrated prefix oracle identity mismatch: {checks}")
    by_id: dict[str, dict[str, Any]] = {}
    assert isinstance(rows, list)
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("prompt_id"), str):
            raise ValueError("integrated prefix oracle row is malformed")
        prompt_id = row["prompt_id"]
        if (
            prompt_id in by_id
            or not token_ids(row.get("token_ids"))
            or len(row["token_ids"]) != 128
        ):
            raise ValueError("integrated prefix oracle token row is invalid")
        if not isinstance(row.get("content_sha256"), str):
            raise ValueError("integrated prefix oracle content hash is missing")
        by_id[prompt_id] = row
    if tuple(by_id) != PROMPT_IDS:
        raise ValueError("integrated prefix oracle row order mismatch")
    return oracle


def identity_argv(identity: dict[str, Any]) -> list[str]:
    argv = identity.get("argv")
    if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
        raise ValueError("server identity argv is not a string array")
    return argv


def argv_pair(argv: list[str], option: str) -> list[str]:
    return [argv[index + 1] for index in range(len(argv) - 1) if argv[index] == option]


def argv_without_pair(argv: list[str], option: str) -> list[str]:
    result: list[str] = []
    index = 0
    while index < len(argv):
        if argv[index] == option and index + 1 < len(argv):
            index += 2
        else:
            result.append(argv[index])
            index += 1
    return result


def request_identity_checks(
    data: dict[str, Any],
    mode: str,
    server_identity: dict[str, Any],
    server_gate: dict[str, Any],
    server_post_gate: dict[str, Any],
) -> dict[str, bool]:
    identity = data.get("run_identity") or {}
    suite_meta = identity.get("suite") or {}
    fresh = data.get("fresh_response_validity") or {}
    final_gate = data.get("realistic_final_gate") or {}
    accounting = data.get("metric_accounting") or {}
    argv = identity_argv(server_identity)
    return {
        "server_identity_mode": server_identity.get("mode") == mode,
        "server_model_sha256": server_identity.get("model_sha256") == MODEL_SHA256,
        "server_runtime_sha256": server_identity.get("runtime_sha256")
        == RUNTIME_SHA256,
        "server_alias_matches_benchmark": argv_pair(argv, "--alias") == [ALIASES[mode]]
        and identity.get("model") == ALIASES[mode],
        "server_gate_pre_passed": server_gate.get("mode") == mode
        and server_gate.get("passed") is True,
        "server_gate_post_passed": server_post_gate.get("mode") == mode
        and server_post_gate.get("passed") is True,
        "openai_text_completions": identity.get("api_mode") == "completions",
        "fixed_suite_metadata": suite_meta.get("suite_id") == SUITE_ID
        and suite_meta.get("version") == 1,
        "fixed_suite_hash": identity.get("suite_sha256") == SUITE_SHA256,
        "twelve_prompts": identity.get("prompt_count") == len(PROMPT_IDS),
        "max_tokens_512": identity.get("max_tokens") == 512,
        "greedy_seed_one": identity.get("seed") == 1
        and identity.get("temperature") == 0
        and identity.get("top_p") == 1,
        "ordinary_eos": identity.get("ignore_eos") is False,
        "request_controls": identity.get("request_extra")
        == {
            "cache_prompt": False,
            "id_slot": 0,
            "ignore_eos": False,
            "return_tokens": True,
            "verbose": True,
        },
        "one_scored_request_per_prompt": identity.get("generation_requests_per_prompt")
        == 1
        and identity.get("replay_requests") == 0,
        "scored_gate_passed": final_gate.get("passed") is True,
        "metric_events_100": final_gate.get("metric_tokens") == 100,
        "position_timing_source": final_gate.get("token_timing_source")
        == "llamacpp_oai_completion_verbose_token_ids",
        "fresh_valid": fresh.get("valid") is True,
        "fresh_once": fresh.get("each_prompt_run_once") is True,
        "no_acceleration_or_reuse": all(
            fresh.get(key) is False
            for key in (
                "history_acceleration",
                "ngram_history_acceleration",
                "response_reuse",
                "context_checkpoints_or_prefix_reuse",
            )
        ),
        "oracle_aligned_accounting": accounting
        == {
            "schema": "realistic-window-accounting-v2-oracle-aligned",
            "timestamped_events": 100,
            "inter_token_intervals": 99,
            "timing_source": "llamacpp_oai_completion_verbose_token_ids",
        },
    }


def gate_capture(args: argparse.Namespace) -> int:
    suite_ids, suite_hashes = load_suite(args.suite)
    prefix = load_prefix_oracle(args.prefix_oracle)
    prefix_identity = prefix.get("run_identity") or {}
    legacy_oracle_identity = {
        "ctx_size": prefix_identity.get("ctx_size"),
        "max_tokens": prefix_identity.get("max_tokens"),
    }
    prefix_by_id = {row["prompt_id"]: row for row in prefix["rows"]}
    data = read_object(args.input)
    forensic = read_object(args.forensic_input)
    server_identity = read_object(args.server_identity)
    server_gate = read_object(args.server_gate)
    server_post_gate = read_object(args.server_post_gate)
    forensic_server_identity = read_object(args.forensic_server_identity)
    forensic_server_gate = read_object(args.forensic_server_gate)
    forensic_server_post_gate = read_object(args.forensic_server_post_gate)
    checks = request_identity_checks(
        data,
        args.mode,
        server_identity,
        server_gate,
        server_post_gate,
    )
    scored_argv = identity_argv(server_identity)
    scored_context_values = argv_pair(scored_argv, "-c")
    current_gate_identity = {
        "ctx_size": (
            int(scored_context_values[0])
            if len(scored_context_values) == 1
            and scored_context_values[0].isdigit()
            else None
        ),
        "max_tokens": (data.get("run_identity") or {}).get("max_tokens"),
    }
    legacy_oracle_identity_compatible = (
        legacy_oracle_identity == current_gate_identity
    )
    checks["legacy_oracle_identity_recorded"] = (
        legacy_oracle_identity == LEGACY_PREFIX_ORACLE_IDENTITY
    )
    checks["current_gate_identity_recorded"] = (
        current_gate_identity == CURRENT_REALISTIC_IDENTITY
    )
    checks["legacy_oracle_identity_incompatible"] = (
        legacy_oracle_identity_compatible is False
    )
    rows = data.get("rows")
    forensic_rows = forensic.get("rows")
    checks["scored_rows_exactly_twelve"] = isinstance(rows, list) and len(rows) == 12
    checks["forensic_rows_exactly_twelve"] = (
        isinstance(forensic_rows, list) and len(forensic_rows) == 12
    )
    forensic_identity = forensic.get("run_identity") or {}
    forensic_argv = identity_argv(forensic_server_identity)
    scored_port = urlparse(str((data.get("run_identity") or {}).get("base_url"))).port
    forensic_port = urlparse(str(forensic_identity.get("base_url"))).port
    checks["fresh_forensic_identity"] = (
        forensic_identity.get("evidence_class") == "unscored-fresh-forensic-support"
        and forensic_identity.get("suite_sha256") == SUITE_SHA256
        and forensic_identity.get("max_tokens") == 512
        and forensic_identity.get("ignore_eos") is False
        and forensic_identity.get("generation_requests_per_prompt") == 1
        and forensic_identity.get("replay_requests") == 0
        and forensic_identity.get("model") == ALIASES[args.mode]
    )
    checks["scored_origin_bound_to_server"] = argv_pair(scored_argv, "--port") == [
        str(scored_port)
    ]
    checks["forensic_server_identity"] = (
        forensic_server_identity.get("mode") == args.mode
        and forensic_server_identity.get("model_sha256") == MODEL_SHA256
        and forensic_server_identity.get("runtime_sha256") == RUNTIME_SHA256
        and argv_pair(forensic_argv, "--alias") == [ALIASES[args.mode]]
        and argv_pair(forensic_argv, "--port") == [str(forensic_port)]
    )
    checks["forensic_server_gates"] = (
        forensic_server_gate.get("mode") == args.mode
        and forensic_server_gate.get("passed") is True
        and forensic_server_post_gate.get("mode") == args.mode
        and forensic_server_post_gate.get("passed") is True
    )
    checks["scored_gate_identity_log_binding"] = (
        server_identity.get("lifetime") == "scored"
        and server_gate.get("identity") == str(args.server_identity.resolve())
        and server_post_gate.get("identity") == str(args.server_identity.resolve())
        and isinstance(server_gate.get("log"), str)
        and server_gate.get("log") == server_post_gate.get("log")
    )
    checks["forensic_gate_identity_log_binding"] = (
        forensic_server_identity.get("lifetime") == "forensic"
        and forensic_server_gate.get("identity")
        == str(args.forensic_server_identity.resolve())
        and forensic_server_post_gate.get("identity")
        == str(args.forensic_server_identity.resolve())
        and isinstance(forensic_server_gate.get("log"), str)
        and forensic_server_gate.get("log") == forensic_server_post_gate.get("log")
    )
    checks["fresh_lifetime_ports_distinct"] = (
        isinstance(scored_port, int)
        and isinstance(forensic_port, int)
        and scored_port != forensic_port
    )
    checks["forensic_argv_matches_scored_except_port"] = argv_without_pair(
        forensic_argv, "--port"
    ) == argv_without_pair(scored_argv, "--port")
    checks["forensic_prepared_and_controls"] = (
        forensic_identity.get("api_mode") == "completions"
        and forensic_identity.get("prompt_count") == 12
        and forensic_identity.get("seed") == 1
        and forensic_identity.get("temperature") == 0
        and forensic_identity.get("top_p") == 1
        and forensic_identity.get("request_extra")
        == {
            "cache_prompt": False,
            "id_slot": 0,
            "ignore_eos": False,
            "return_tokens": True,
            "verbose": True,
        }
    )
    forensic_by_id = (
        {row.get("prompt_id"): row for row in forensic_rows if isinstance(row, dict)}
        if isinstance(forensic_rows, list)
        else {}
    )
    row_results = []
    d99_values: list[float] = []
    d127_values: list[float] = []
    full_values: list[float] = []
    native_values: list[float] = []
    client_values: list[float] = []
    ttft_values: list[float] = []
    per_prompt: dict[str, dict[str, Any]] = {}
    request_ids: list[str] = []
    forensic_request_ids: list[str] = []
    response_draft_tokens = 0
    response_accepted_tokens = 0
    for index, row in enumerate(rows if isinstance(rows, list) else []):
        prompt_id = row.get("prompt_id") if isinstance(row, dict) else None
        expected = prefix_by_id.get(prompt_id) or {}
        support = forensic_by_id.get(prompt_id) or {}
        ids = row.get("token_ids") if isinstance(row, dict) else None
        positions = (
            row.get("stream_complete_positions") if isinstance(row, dict) else None
        )
        offsets = row.get("token_id_offsets_s") if isinstance(row, dict) else None
        support_ids = support.get("token_ids") if isinstance(support, dict) else None
        expected_ids = expected.get("token_ids") if isinstance(expected, dict) else None
        legacy_prefix_compared_tokens = (
            min(128, len(support_ids)) if isinstance(support_ids, list) else 0
        )
        legacy_prefix_lcp_tokens = longest_common_prefix_tokens(
            support_ids, expected_ids
        )
        legacy_prefix_oracle_match = (
            bool(expected)
            and isinstance(support_ids, list)
            and isinstance(expected_ids, list)
            and legacy_prefix_compared_tokens > 0
            and support_ids[:legacy_prefix_compared_tokens]
            == expected_ids[:legacy_prefix_compared_tokens]
        )
        completion_n = row.get("completion_tokens") if isinstance(row, dict) else None
        position_offsets = (
            dict(zip(positions, offsets))
            if (
                isinstance(positions, list)
                and isinstance(offsets, list)
                and len(positions) == len(offsets)
            )
            else {}
        )
        d99 = d127 = full = None
        if 0 in position_offsets and 99 in position_offsets:
            duration99 = position_offsets[99] - position_offsets[0]
            if duration99 > 0:
                d99 = 99 / duration99
        if 0 in position_offsets and 127 in position_offsets:
            duration127 = position_offsets[127] - position_offsets[0]
            if duration127 > 0:
                d127 = 127 / duration127
        if (
            isinstance(completion_n, int)
            and 0 in position_offsets
            and completion_n - 1 in position_offsets
        ):
            duration_full = position_offsets[completion_n - 1] - position_offsets[0]
            if duration_full > 0:
                full = (completion_n - 1) / duration_full
        timings = row.get("timings") if isinstance(row, dict) else None
        timings = timings if isinstance(timings, dict) else {}
        native = timings.get("predicted_per_second")
        predicted_ms = timings.get("predicted_ms")
        draft_n = timings.get("draft_n")
        accepted_n = timings.get("draft_n_accepted")
        observed_matches_support = (
            isinstance(ids, list)
            and isinstance(positions, list)
            and isinstance(support_ids, list)
            and len(ids) == len(positions)
            and all(
                0 <= position < len(support_ids) and support_ids[position] == token
                for position, token in zip(positions, ids)
            )
        )
        request_payload = row.get("request_payload") if isinstance(row, dict) else None
        support_payload = support.get("request_payload")
        scored_verbose = row.get("final_verbose") or {}
        support_verbose = support.get("verbose") or {}
        usage = row.get("usage") or {}
        support_usage = support.get("usage") or {}
        support_timings = support.get("timings") or {}
        expected_stop_type = scored_verbose.get("stop_type")
        expected_finish = "length" if expected_stop_type == "limit" else "stop"
        support_stop_type = support_verbose.get("stop_type")
        support_expected_finish = "length" if support_stop_type == "limit" else "stop"
        elapsed = row.get("elapsed_s")
        ttft = row.get("ttft_s")
        post_ttft = row.get("post_ttft_s")
        client_rate = row.get("tok_s_after_ttft_full")
        prompt_tokens = row.get("prompt_tokens")
        row_checks = {
            "prompt_identity": index < 12
            and prompt_id == suite_ids[index]
            and row.get("prompt_sha256") == suite_hashes[index],
            "rendered_prompt_oracle": bool(expected)
            and row.get("rendered_prompt_sha256")
            == expected.get("rendered_prompt_sha256"),
            LEGACY_PREFIX_DIAGNOSTIC_CHECK: legacy_prefix_oracle_match,
            "request_payload_exact": request_payload
            == {
                "model": ALIASES[args.mode],
                "prompt": support.get("verbose", {}).get("prompt")
                if isinstance(support, dict)
                else None,
                "max_tokens": 512,
                "temperature": 0,
                "top_p": 1,
                "seed": 1,
                "stream": True,
                "stream_options": {"include_usage": True},
                "cache_prompt": False,
                "verbose": True,
                "return_tokens": True,
                "ignore_eos": False,
                "id_slot": 0,
            },
            "request_prompt_hash_bound": isinstance(request_payload, dict)
            and isinstance(request_payload.get("prompt"), str)
            and hashlib.sha256(request_payload["prompt"].encode()).hexdigest()
            == row.get("rendered_prompt_sha256"),
            "forensic_prompt_hash_bound": isinstance(
                support.get("verbose", {}).get("prompt"), str
            )
            and hashlib.sha256(support["verbose"]["prompt"].encode()).hexdigest()
            == row.get("rendered_prompt_sha256"),
            "scored_final_prompt_hash_bound": isinstance(
                scored_verbose.get("prompt"), str
            )
            and hashlib.sha256(scored_verbose["prompt"].encode()).hexdigest()
            == row.get("rendered_prompt_sha256"),
            "single_final_protocol": row.get("final_event_count") == 1
            and row.get("done_count") == 1
            and row.get("usage_event_count") == 1
            and row.get("final_timings_event_count") == 1
            and isinstance(row.get("partial_timings_events"), list)
            and len(row["partial_timings_events"]) <= 1,
            "response_id_consistent": isinstance(row.get("response_ids"), list)
            and len(row["response_ids"]) > 0
            and len(set(row["response_ids"])) == 1,
            "cache_zero_literal": row.get("cached_tokens") == 0
            and usage.get("prompt_tokens_details", {}).get("cached_tokens") == 0
            and timings.get("cache_n") == 0,
            "scored_final_protocol_empty": row.get("final_verbose_tokens") == []
            and row.get("final_verbose_content") == ""
            and row.get("final_payload_intentionally_empty") is True
            and scored_verbose.get("stop") is True
            and scored_verbose.get("id_slot") == 0
            and scored_verbose.get("truncated") is False
            and scored_verbose.get("tokens_predicted") == completion_n,
            "scored_stop_semantics": expected_stop_type in {"limit", "eos", "word"}
            and row.get("finish_reasons") == [expected_finish],
            "natural_length_bound": isinstance(completion_n, int)
            and not isinstance(completion_n, bool)
            and 100 <= completion_n <= 512,
            "forensic_length_bound": isinstance(support_ids, list)
            and len(support_ids) == completion_n
            and support.get("token_count") == completion_n,
            "positions_strict_unique": isinstance(positions, list)
            and isinstance(completion_n, int)
            and all(
                isinstance(position, int) and not isinstance(position, bool)
                for position in positions
            )
            and positions == sorted(set(positions))
            and positions
            and positions[0] >= 0
            and positions[-1] < completion_n,
            "position_arrays_same_length": isinstance(ids, list)
            and isinstance(positions, list)
            and isinstance(offsets, list)
            and len(ids) == len(positions) == len(offsets)
            and row.get("stream_token_id_count") == len(ids)
            and all(
                isinstance(token, int) and not isinstance(token, bool) and token >= 0
                for token in ids
            ),
            "observed_ids_match_forensic": observed_matches_support,
            "position_records_exact": row.get("stream_position_token_offsets")
            == [
                {
                    "complete_position": position,
                    "token_id": token,
                    "offset_s": offset,
                }
                for position, token, offset in zip(
                    positions or [], ids or [], offsets or []
                )
            ],
            "offsets_monotone_finite": isinstance(offsets, list)
            and all(finite_number(offset) and offset >= 0 for offset in offsets)
            and all(
                offsets[pos] <= offsets[pos + 1] for pos in range(len(offsets) - 1)
            ),
            "ttft_bound_to_position_zero": 0 in position_offsets
            and row.get("ttft_s") == position_offsets[0],
            "client_timing_arithmetic": positive_number(elapsed)
            and positive_number(ttft)
            and finite_number(post_ttft)
            and 0 < ttft < elapsed
            and math.isclose(
                float(post_ttft),
                float(elapsed) - float(ttft),
                rel_tol=0,
                abs_tol=1e-12,
            )
            and positive_number(client_rate)
            and math.isclose(
                float(client_rate),
                completion_n / float(post_ttft),
                rel_tol=1e-12,
                abs_tol=1e-12,
            ),
            "scored_content_matches_forensic": row.get("sha256")
            == support.get("content_sha256"),
            "scored_content_hash_recomputed": isinstance(row.get("content"), str)
            and hashlib.sha256(row["content"].encode()).hexdigest()
            == row.get("sha256"),
            "required_primary_timing_positions": d99 is not None,
            "native_timing_bound": timings.get("predicted_n") == completion_n
            and positive_number(predicted_ms)
            and positive_number(native)
            and math.isclose(
                float(native),
                1000 * completion_n / float(predicted_ms),
                rel_tol=1e-6,
                abs_tol=1e-6,
            ),
            "scored_usage_bound": usage.get("completion_tokens") == completion_n
            and usage.get("prompt_tokens") == prompt_tokens
            and isinstance(prompt_tokens, int)
            and not isinstance(prompt_tokens, bool)
            and prompt_tokens > 0
            and usage.get("total_tokens") == prompt_tokens + completion_n,
            "forensic_usage_timing_bound": (support.get("usage") or {}).get(
                "completion_tokens"
            )
            == completion_n
            and isinstance(support_usage.get("prompt_tokens"), int)
            and not isinstance(support_usage.get("prompt_tokens"), bool)
            and support_usage.get("prompt_tokens") > 0
            and support_usage.get("total_tokens")
            == support_usage.get("prompt_tokens") + completion_n
            and (support.get("usage") or {})
            .get("prompt_tokens_details", {})
            .get("cached_tokens")
            == 0
            and support_timings.get("predicted_n") == completion_n
            and positive_number(support_timings.get("predicted_ms"))
            and positive_number(support_timings.get("predicted_per_second"))
            and math.isclose(
                float(support_timings["predicted_per_second"]),
                1000 * completion_n / float(support_timings["predicted_ms"]),
                rel_tol=1e-6,
                abs_tol=1e-6,
            ),
            "forensic_row_identity": support.get("prompt_index") == index
            and support.get("prompt_id") == prompt_id
            and support.get("prompt_sha256") == row.get("prompt_sha256")
            and support.get("rendered_prompt_sha256")
            == row.get("rendered_prompt_sha256"),
            "forensic_tokens_valid": isinstance(support_ids, list)
            and len(support_ids) == completion_n
            and all(
                isinstance(token, int) and not isinstance(token, bool) and token >= 0
                for token in support_ids
            ),
            "forensic_content_hash_recomputed": isinstance(support.get("content"), str)
            and hashlib.sha256(support["content"].encode()).hexdigest()
            == support.get("content_sha256")
            and support.get("choice_text") == support.get("content"),
            "forensic_cache_zero": support_usage.get("prompt_tokens_details", {}).get(
                "cached_tokens"
            )
            == 0
            and support_timings.get("cache_n") == 0,
            "forensic_protocol": isinstance(support.get("response_id"), str)
            and bool(support.get("response_id"))
            and support_verbose.get("stop") is True
            and support_verbose.get("truncated") is False
            and support_verbose.get("tokens") == support_ids
            and support_verbose.get("content") == support.get("content")
            and support_verbose.get("tokens_predicted") == completion_n,
            "forensic_stop_semantics": support_stop_type in {"limit", "eos", "word"}
            and support.get("finish_reason") == support_expected_finish,
            "forensic_request_payload": isinstance(support_payload, dict)
            and support_payload
            == {
                "model": ALIASES[args.mode],
                "prompt": request_payload.get("prompt")
                if isinstance(request_payload, dict)
                else None,
                "max_tokens": 512,
                "temperature": 0,
                "top_p": 1,
                "seed": 1,
                "stream": False,
                "cache_prompt": False,
                "verbose": True,
                "return_tokens": True,
                "ignore_eos": False,
                "id_slot": 0,
            },
            "draft_fields": (
                isinstance(draft_n, int)
                and isinstance(accepted_n, int)
                and draft_n > 0
                and 0 <= accepted_n <= draft_n
                if args.mode == "mtp3"
                else "draft_n" not in timings and "draft_n_accepted" not in timings
            ),
        }
        if isinstance(row.get("request_id"), str):
            request_ids.append(row["request_id"])
        if isinstance(support.get("request_id"), str):
            forensic_request_ids.append(support["request_id"])
        if positive_number(d99):
            d99_values.append(float(d99))
            per_prompt[str(prompt_id)] = {
                "d99_interval_tok_s": float(d99),
                "d127_interval_tok_s": float(d127) if positive_number(d127) else None,
                "full_interval_tok_s": float(full) if positive_number(full) else None,
                "native_predicted_tok_s": float(native)
                if positive_number(native)
                else None,
                "client_full_after_ttft_tok_s": float(client_rate)
                if positive_number(client_rate)
                else None,
                "ttft_s": float(ttft) if positive_number(ttft) else None,
            }
        if positive_number(native):
            native_values.append(float(native))
        if positive_number(client_rate):
            client_values.append(float(client_rate))
        if positive_number(ttft):
            ttft_values.append(float(ttft))
        if positive_number(d127):
            d127_values.append(float(d127))
        if positive_number(full):
            full_values.append(float(full))
        if (
            args.mode == "mtp3"
            and isinstance(draft_n, int)
            and isinstance(accepted_n, int)
        ):
            response_draft_tokens += draft_n
            response_accepted_tokens += accepted_n
        row_results.append(
            {
                "prompt_id": prompt_id,
                "completion_tokens": completion_n,
                "legacy_prefix_diagnostic": {
                    "matched": legacy_prefix_oracle_match,
                    "lcp_tokens": legacy_prefix_lcp_tokens,
                    "compared_tokens": legacy_prefix_compared_tokens,
                },
                "missing_positions": sorted(
                    set(range(completion_n or 0)) - set(positions or [])
                ),
                "checks": row_checks,
                "passed": hard_row_checks_pass(row_checks),
            }
        )
    checks["prompt_order"] = (
        [row.get("prompt_id") for row in rows if isinstance(row, dict)]
        == list(PROMPT_IDS)
        if isinstance(rows, list)
        else False
    )
    checks["request_ids_unique"] = (
        len(request_ids) == 12 and len(set(request_ids)) == 12
    )
    checks["forensic_prompt_order"] = (
        [row.get("prompt_id") for row in forensic_rows if isinstance(row, dict)]
        == list(PROMPT_IDS)
        if isinstance(forensic_rows, list)
        else False
    )
    checks["forensic_request_ids_unique"] = (
        len(forensic_request_ids) == 12 and len(set(forensic_request_ids)) == 12
    )
    checks["all_rows_pass"] = len(row_results) == 12 and all(
        row["passed"] for row in row_results
    )
    control_checks: dict[str, Any] = {}
    if args.mode == "mtp3":
        if args.control_input is None or args.control_forensic_input is None:
            raise ValueError("mtp3 gate requires scored and forensic control inputs")
        control_forensic = read_object(args.control_forensic_input)
        control_by_id = {
            row["prompt_id"]: row
            for row in control_forensic.get("rows", [])
            if isinstance(row, dict) and isinstance(row.get("prompt_id"), str)
        }
        full_token_exact = all(
            isinstance(forensic_by_id.get(prompt), dict)
            and forensic_by_id[prompt].get("token_ids")
            == control_by_id.get(prompt, {}).get("token_ids")
            for prompt in PROMPT_IDS
        )
        full_content_exact = all(
            isinstance(forensic_by_id.get(prompt), dict)
            and forensic_by_id[prompt].get("content")
            == control_by_id.get(prompt, {}).get("content")
            and forensic_by_id[prompt].get("content_sha256")
            == control_by_id.get(prompt, {}).get("content_sha256")
            for prompt in PROMPT_IDS
        )
        full_exact = full_token_exact and full_content_exact
        control_checks = {
            "control_scored_sha256_bound": sha256_file(args.control_input)
            == args.expected_control_sha256,
            "control_forensic_sha256_bound": sha256_file(args.control_forensic_input)
            == args.expected_control_forensic_sha256,
            "full_candidate_control_token_ids_exact": full_token_exact,
            "full_candidate_control_content_exact": full_content_exact,
            "full_candidate_control_exact": full_exact,
            "observed_control_scored_sha256": sha256_file(args.control_input),
            "observed_control_forensic_sha256": sha256_file(
                args.control_forensic_input
            ),
        }
        checks.update(
            {
                key: value
                for key, value in control_checks.items()
                if key.endswith("_bound")
                or key.startswith("full_candidate_control_")
            }
        )
    elif any(
        value is not None
        for value in (
            args.control_input,
            args.control_forensic_input,
            args.expected_control_sha256,
            args.expected_control_forensic_sha256,
        )
    ):
        raise ValueError("control gate must not receive control-oracle inputs")
    all_full = len(row_results) == 12 and all(
        row.get("completion_tokens") == 512 for row in row_results
    )
    result = {
        "mode": args.mode,
        "input": str(args.input.resolve()),
        "input_sha256": sha256_file(args.input),
        "forensic_input": str(args.forensic_input.resolve()),
        "forensic_input_sha256": sha256_file(args.forensic_input),
        "suite_sha256": SUITE_SHA256,
        "prefix_oracle_sha256": PREFIX_ORACLE_SHA256,
        "legacy_oracle_identity": legacy_oracle_identity,
        "current_gate_identity": current_gate_identity,
        "legacy_oracle_identity_compatible": legacy_oracle_identity_compatible,
        "quality_reference": QUALITY_REFERENCE,
        "model_sha256": MODEL_SHA256,
        "runtime_sha256": RUNTIME_SHA256,
        "server_evidence": {
            "identity_sha256": sha256_file(args.server_identity),
            "pre_gate_sha256": sha256_file(args.server_gate),
            "post_gate_sha256": sha256_file(args.server_post_gate),
            "forensic_identity_sha256": sha256_file(args.forensic_server_identity),
            "forensic_pre_gate_sha256": sha256_file(args.forensic_server_gate),
            "forensic_post_gate_sha256": sha256_file(args.forensic_server_post_gate),
        },
        "policy": {
            "headline_requests_per_prompt": 1,
            "headline_replay_requests": 0,
            "separate_fresh_forensic_requests_per_prompt": 1,
            "ordinary_eos": True,
            "cached_tokens_required": 0,
            "timestamped_events": 100,
            "inter_token_intervals": 99,
        },
        "checks": checks,
        "rows": row_results,
        "per_prompt": per_prompt,
        "summary": {
            "d99_interval_tok_s": stats(d99_values) if d99_values else None,
            "d127_interval_tok_s": stats(d127_values) if d127_values else None,
            "full_interval_tok_s": stats(full_values) if full_values else None,
            "native_predicted_tok_s": stats(native_values) if native_values else None,
            "client_full_after_ttft_tok_s": stats(client_values)
            if client_values
            else None,
            "ttft_s": stats(ttft_values) if ttft_values else None,
            "response_draft_tokens": response_draft_tokens,
            "response_accepted_tokens": response_accepted_tokens,
            "all_rows_full_512": all_full,
        },
        "control_checks": control_checks,
        "passed": all(checks.values()),
    }
    atomic_write_json(args.output, result)
    return 0 if result["passed"] else 1


def integral_delta(before: float, after: float, name: str) -> int:
    delta = after - before
    if not math.isfinite(delta) or delta < 0 or not delta.is_integer():
        raise ValueError(f"counter {name} has invalid delta {delta}")
    return int(delta)


def gate_metrics_binding(args: argparse.Namespace) -> int:
    capture = read_object(args.capture)
    sealed_gate = read_object(args.sealed_gate)
    with tempfile.TemporaryDirectory() as raw:
        recomputed_path = Path(raw) / "sealed-recomputed.json"
        recompute_status = sealed.gate_metrics(
            argparse.Namespace(
                mode=args.mode,
                before=args.before,
                after=args.after,
                output=recomputed_path,
            )
        )
        recomputed = read_object(recomputed_path)
    before = sealed.parse_prometheus(args.before)
    after = sealed.parse_prometheus(args.after)
    predicted_name = "llamacpp:tokens_predicted_total"
    prompt_name = "llamacpp:prompt_tokens_total"
    predicted_before = sealed.metric_value(before, predicted_name)
    predicted_after = sealed.metric_value(after, predicted_name)
    prompt_before = sealed.metric_value(before, prompt_name)
    prompt_after = sealed.metric_value(after, prompt_name)
    predicted_delta = integral_delta(predicted_before, predicted_after, predicted_name)
    prompt_delta = integral_delta(prompt_before, prompt_after, prompt_name)
    rows = capture.get("rows")
    completion_sum = 0
    prompt_sum = 0
    response_draft_sum = 0
    response_accepted_sum = 0
    response_spec_fields_valid = True
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                response_spec_fields_valid = False
                continue
            completion = row.get("completion_tokens")
            prompt = row.get("prompt_tokens")
            if isinstance(completion, int) and not isinstance(completion, bool):
                completion_sum += completion
            if isinstance(prompt, int) and not isinstance(prompt, bool):
                prompt_sum += prompt
            timings = row.get("timings")
            timings = timings if isinstance(timings, dict) else {}
            draft_n = timings.get("draft_n")
            accepted_n = timings.get("draft_n_accepted")
            if args.mode == "control":
                response_spec_fields_valid = response_spec_fields_valid and (
                    "draft_n" not in timings and "draft_n_accepted" not in timings
                )
            else:
                valid = (
                    isinstance(draft_n, int)
                    and not isinstance(draft_n, bool)
                    and draft_n > 0
                    and isinstance(accepted_n, int)
                    and not isinstance(accepted_n, bool)
                    and 0 <= accepted_n <= draft_n
                )
                response_spec_fields_valid = response_spec_fields_valid and valid
                if valid:
                    response_draft_sum += draft_n
                    response_accepted_sum += accepted_n
    required_spec_checks = (
        ("all_spec_counters_zero", "accepted_positions_absent")
        if args.mode == "control"
        else (
            "drafts_positive",
            "draft_tokens_positive",
            "accepted_positive",
            "accepted_le_draft_tokens",
            "draft_tokens_ge_drafts",
            "draft_tokens_le_nmax_times_drafts",
            "positions_exactly_0_1_2",
            "positions_monotone",
            "positions_each_le_drafts",
            "positions_sum_to_accepted",
        )
    )
    checks = {
        "spec_gate_recomputed_passed": recompute_status == 0
        and recomputed.get("passed") is True,
        "sealed_gate_exactly_matches_recomputation": sealed_gate == recomputed,
        "sealed_spec_gate_passed": sealed_gate.get("passed") is True,
        "sealed_mode": sealed_gate.get("mode") == args.mode,
        "spec_counter_start_checks": all(
            sealed_gate.get("checks", {}).get(name) is True
            for name in (
                "draft_tokens_starts_zero",
                "accepted_tokens_starts_zero",
                "drafts_starts_zero",
                "positions_start_absent",
            )
        ),
        "spec_counter_algebra_explicit": all(
            sealed_gate.get("checks", {}).get(name) is True
            for name in required_spec_checks
        ),
        "twelve_capture_rows": isinstance(rows, list) and len(rows) == 12,
        "predicted_counter_starts_zero": predicted_before == 0,
        "prompt_counter_starts_zero": prompt_before == 0,
        "completion_sum_natural_100_to_512": 12 * 100 <= completion_sum <= 12 * 512,
        "predicted_delta_matches_responses": predicted_delta == completion_sum,
        "prompt_delta_matches_responses": prompt_delta == prompt_sum and prompt_sum > 0,
        "response_spec_fields_valid": response_spec_fields_valid,
        "response_draft_delta_matches_prometheus": sealed_gate.get("counters", {}).get(
            "draft_tokens"
        )
        == response_draft_sum,
        "response_accepted_delta_matches_prometheus": sealed_gate.get(
            "counters", {}
        ).get("accepted_tokens")
        == response_accepted_sum,
    }
    result = {
        "mode": args.mode,
        "capture": str(args.capture.resolve()),
        "capture_sha256": sha256_file(args.capture),
        "sealed_gate": str(args.sealed_gate.resolve()),
        "sealed_gate_sha256": sha256_file(args.sealed_gate),
        "metrics_before_sha256": sha256_file(args.before),
        "metrics_after_sha256": sha256_file(args.after),
        "checks": checks,
        "response_sums": {
            "completion_tokens": completion_sum,
            "prompt_tokens": prompt_sum,
            "draft_tokens": response_draft_sum,
            "accepted_tokens": response_accepted_sum,
        },
        "counter_deltas": {
            "tokens_predicted": predicted_delta,
            "prompt_tokens": prompt_delta,
        },
        "speculative": {
            "counters": sealed_gate.get("counters"),
            "accepted_per_position": sealed_gate.get("accepted_per_position"),
            "acceptance_ratio": sealed_gate.get("acceptance_ratio"),
            "accepted_per_verification": sealed_gate.get("accepted_per_verification"),
            "effective_tokens_per_target_verification": sealed_gate.get(
                "effective_tokens_per_target_verification"
            ),
        },
        "passed": all(checks.values()),
    }
    atomic_write_json(args.output, result)
    return 0 if result["passed"] else 1


def read_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text().splitlines():
        key, separator, value = line.partition("=")
        if not separator or not key or key in result:
            raise ValueError(f"invalid env evidence: {path}")
        result[key] = value
    return result


def ratio(numerator: Any, denominator: Any) -> float:
    if not positive_number(numerator) or not positive_number(denominator):
        raise ValueError("cannot calculate ratio from non-positive values")
    return float(numerator) / float(denominator)


def compare_arms(args: argparse.Namespace) -> int:
    control = read_object(args.control_capture_gate)
    candidate = read_object(args.candidate_capture_gate)
    control_metrics = read_object(args.control_metrics_gate)
    candidate_metrics = read_object(args.candidate_metrics_gate)
    cleanup_control = read_env(args.control_cleanup)
    cleanup_candidate = read_env(args.candidate_cleanup)
    cleanup_control_forensic = read_env(args.control_forensic_cleanup)
    cleanup_candidate_forensic = read_env(args.candidate_forensic_cleanup)
    cleanup_required = {
        "forced_kill": "0",
        "cleanup_survivor": "0",
        "port_closed": "1",
        "vram_returned": "1",
    }
    evidence_checks = {
        "control_capture": control.get("passed") is True,
        "candidate_capture": candidate.get("passed") is True,
        "control_capture_mode": control.get("mode") == "control",
        "candidate_capture_mode": candidate.get("mode") == "mtp3",
        "control_metrics": control_metrics.get("passed") is True,
        "candidate_metrics": candidate_metrics.get("passed") is True,
        "control_metrics_mode": control_metrics.get("mode") == "control",
        "candidate_metrics_mode": candidate_metrics.get("mode") == "mtp3",
        "control_metrics_capture_join": control_metrics.get("capture_sha256")
        == control.get("input_sha256"),
        "candidate_metrics_capture_join": candidate_metrics.get("capture_sha256")
        == candidate.get("input_sha256"),
        "same_suite": control.get("suite_sha256")
        == candidate.get("suite_sha256")
        == SUITE_SHA256,
        "same_prefix_oracle": control.get("prefix_oracle_sha256")
        == candidate.get("prefix_oracle_sha256")
        == PREFIX_ORACLE_SHA256,
        "control_quality_reference": control.get("quality_reference")
        == QUALITY_REFERENCE,
        "candidate_quality_reference": candidate.get("quality_reference")
        == QUALITY_REFERENCE,
        "control_legacy_oracle_identity_recorded": control.get(
            "legacy_oracle_identity"
        )
        == LEGACY_PREFIX_ORACLE_IDENTITY
        and control.get("current_gate_identity") == CURRENT_REALISTIC_IDENTITY,
        "candidate_legacy_oracle_identity_recorded": candidate.get(
            "legacy_oracle_identity"
        )
        == LEGACY_PREFIX_ORACLE_IDENTITY
        and candidate.get("current_gate_identity") == CURRENT_REALISTIC_IDENTITY,
        "control_legacy_oracle_identity_incompatible": control.get(
            "legacy_oracle_identity_compatible"
        )
        is False,
        "candidate_legacy_oracle_identity_incompatible": candidate.get(
            "legacy_oracle_identity_compatible"
        )
        is False,
        "same_model": control.get("model_sha256")
        == candidate.get("model_sha256")
        == MODEL_SHA256,
        "same_runtime": control.get("runtime_sha256")
        == candidate.get("runtime_sha256")
        == RUNTIME_SHA256,
        "candidate_bound_to_fresh_control": candidate.get("control_checks", {}).get(
            "full_candidate_control_token_ids_exact"
        )
        is True
        and candidate.get("control_checks", {}).get(
            "full_candidate_control_content_exact"
        )
        is True
        and candidate.get("control_checks", {}).get(
            "full_candidate_control_exact"
        )
        is True
        and candidate.get("control_checks", {}).get("observed_control_scored_sha256")
        == control.get("input_sha256")
        and candidate.get("control_checks", {}).get("observed_control_forensic_sha256")
        == control.get("forensic_input_sha256"),
        "control_once_only": control.get("policy", {}).get(
            "headline_requests_per_prompt"
        )
        == 1
        and control.get("policy", {}).get("headline_replay_requests") == 0
        and control.get("policy", {}).get("separate_fresh_forensic_requests_per_prompt")
        == 1,
        "candidate_once_only": candidate.get("policy", {}).get(
            "headline_requests_per_prompt"
        )
        == 1
        and candidate.get("policy", {}).get("headline_replay_requests") == 0
        and candidate.get("policy", {}).get(
            "separate_fresh_forensic_requests_per_prompt"
        )
        == 1,
        "control_cleanup": all(
            cleanup_control.get(key) == value for key, value in cleanup_required.items()
        ),
        "candidate_cleanup": all(
            cleanup_candidate.get(key) == value
            for key, value in cleanup_required.items()
        ),
        "control_forensic_cleanup": all(
            cleanup_control_forensic.get(key) == value
            for key, value in cleanup_required.items()
        ),
        "candidate_forensic_cleanup": all(
            cleanup_candidate_forensic.get(key) == value
            for key, value in cleanup_required.items()
        ),
    }
    control_spec = control_metrics.get("speculative", {})
    candidate_spec = candidate_metrics.get("speculative", {})
    evidence_checks.update(
        {
            "control_spec_counters_zero": control_spec.get("counters")
            == {"accepted_tokens": 0, "draft_tokens": 0, "drafts": 0},
            "candidate_spec_counters_positive": all(
                isinstance(candidate_spec.get("counters", {}).get(key), int)
                and candidate_spec["counters"][key] > 0
                for key in ("accepted_tokens", "draft_tokens", "drafts")
            ),
            "candidate_acceptance_valid": positive_number(
                candidate_spec.get("acceptance_ratio")
            )
            and candidate_spec["acceptance_ratio"] <= 1,
        }
    )
    if not all(evidence_checks.values()):
        result = {
            "evidence_checks": evidence_checks,
            "evidence_passed": False,
            "performance_passed": False,
            "classification": "INVALID_EVIDENCE",
            "realistic_policy_passed": False,
            "quality_reference": QUALITY_REFERENCE,
            "localmaxxing_submission_ready": False,
        }
        atomic_write_json(args.output, result)
        return 1

    control_summary = control["summary"]
    candidate_summary = candidate["summary"]
    control_d99 = control_summary["d99_interval_tok_s"]
    candidate_d99 = candidate_summary["d99_interval_tok_s"]
    control_d127 = control_summary["d127_interval_tok_s"]
    candidate_d127 = candidate_summary["d127_interval_tok_s"]
    control_client_full = control_summary["client_full_after_ttft_tok_s"]
    candidate_client_full = candidate_summary["client_full_after_ttft_tok_s"]
    control_full = control_summary["full_interval_tok_s"]
    candidate_full = candidate_summary["full_interval_tok_s"]
    control_native = control_summary["native_predicted_tok_s"]
    candidate_native = candidate_summary["native_predicted_tok_s"]
    d99_ratio = ratio(candidate_d99["median"], control_d99["median"])
    d127_complete = (
        control_d127.get("count") == candidate_d127.get("count") == 12
        if isinstance(control_d127, dict) and isinstance(candidate_d127, dict)
        else False
    )
    full_complete = (
        control_full.get("count") == candidate_full.get("count") == 12
        if isinstance(control_full, dict) and isinstance(candidate_full, dict)
        else False
    )
    d127_ratio = (
        ratio(candidate_d127["median"], control_d127["median"])
        if d127_complete
        else None
    )
    client_full_ratio = ratio(
        candidate_client_full["median"], control_client_full["median"]
    )
    full_ratio = (
        ratio(candidate_full["median"], control_full["median"])
        if full_complete
        else None
    )
    native_ratio = ratio(candidate_native["median"], control_native["median"])
    ttft_ratio = ratio(
        candidate_summary["ttft_s"]["median"],
        control_summary["ttft_s"]["median"],
    )
    prompt_ratios = {
        prompt_id: ratio(
            candidate["per_prompt"][prompt_id]["d99_interval_tok_s"],
            control["per_prompt"][prompt_id]["d99_interval_tok_s"],
        )
        for prompt_id in PROMPT_IDS
    }
    acceptance = candidate_spec["acceptance_ratio"]
    accepted_per_verify = candidate_spec.get("accepted_per_verification")
    full_native_ratio_disagreement = (
        abs(full_ratio - native_ratio) if full_ratio is not None else None
    )
    performance_checks = {
        "candidate_d99_median_at_least_18": candidate_d99["median"] >= 18.0,
        "candidate_native_median_at_least_18": candidate_native["median"] >= 18.0,
        "d99_median_gain_at_least_8pct": d99_ratio >= 1.08,
        "full_interval_gain_at_least_8pct": full_ratio is not None
        and full_ratio >= 1.08,
        "native_median_gain_at_least_8pct": native_ratio >= 1.08,
        "each_prompt_d99_gain_at_least_5pct": len(prompt_ratios) == 12
        and all(value >= 1.05 for value in prompt_ratios.values()),
        "ttft_regression_at_most_10pct": ttft_ratio <= 1.10,
        "acceptance_at_least_045": acceptance >= 0.45,
        "accepted_per_verify_at_least_125": positive_number(accepted_per_verify)
        and accepted_per_verify >= 1.25,
        "full_native_ratio_disagreement_at_most_0035": (
            full_native_ratio_disagreement is not None
            and full_native_ratio_disagreement <= 0.035
        ),
    }
    performance_passed = all(performance_checks.values())
    result = {
        "evidence_checks": evidence_checks,
        "evidence_passed": True,
        "performance_checks": performance_checks,
        "performance_passed": performance_passed,
        "classification": (
            "PASS_REALISTIC_MTP_WIN"
            if performance_passed
            else "VALID_REALISTIC_NO_MTP_WIN"
        ),
        "realistic_policy_passed": True,
        "quality_reference": QUALITY_REFERENCE,
        "legacy_oracle_identity": LEGACY_PREFIX_ORACLE_IDENTITY,
        "current_gate_identity": CURRENT_REALISTIC_IDENTITY,
        "legacy_oracle_identity_compatible": False,
        "localmaxxing_submission_ready": False,
        "submission_note": (
            "This packet is once-only, cache-zero, exact, and target-verified. "
            "Submission remains false until independent review and comparison "
            "against the matching current LocalMaxxing record."
        ),
        "primary_metric": {
            "name": "median_tok_s_1_100_intervals_after_ttft",
            "timestamped_events_per_prompt": 100,
            "inter_token_intervals_per_prompt": 99,
            "numerator_per_prompt": 99,
            "control": control_d99,
            "candidate": candidate_d99,
            "matched_d127_control": control_d127,
            "matched_d127_candidate": candidate_d127,
            "client_full_control": control_client_full,
            "client_full_candidate": candidate_client_full,
            "full_interval_control": control_full,
            "full_interval_candidate": candidate_full,
            "native_control": control_native,
            "native_candidate": candidate_native,
        },
        "ratios": {
            "d99_median_candidate_over_control": d99_ratio,
            "d127_median_candidate_over_control": d127_ratio,
            "client_full_median_candidate_over_control": client_full_ratio,
            "full_interval_median_candidate_over_control": full_ratio,
            "native_median_candidate_over_control": native_ratio,
            "full_native_ratio_disagreement": full_native_ratio_disagreement,
            "ttft_candidate_over_control": ttft_ratio,
            "per_prompt_candidate_over_control": prompt_ratios,
        },
        "acceptance": {
            "accepted_over_drafted": acceptance,
            "accepted_per_verification": accepted_per_verify,
            "effective_tokens_per_target_verification": candidate_spec.get(
                "effective_tokens_per_target_verification"
            ),
            "counters": candidate_spec.get("counters"),
            "accepted_per_position": candidate_spec.get("accepted_per_position"),
        },
        "scope": {
            "fixed_prompts": 12,
            "requests_per_prompt_per_arm": 1,
            "replay_requests": 0,
            "gpu_count": 1,
            "max_tokens": 512,
            "ctx_size": 32768,
            "ordinary_eos": True,
            "target_verified": True,
            "all_rows_full_512": control_summary.get("all_rows_full_512") is True
            and candidate_summary.get("all_rows_full_512") is True,
        },
    }
    atomic_write_json(args.output, result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    capture = commands.add_parser("gate-capture")
    capture.add_argument("--mode", choices=("control", "mtp3"), required=True)
    capture.add_argument("--input", type=Path, required=True)
    capture.add_argument("--forensic-input", type=Path, required=True)
    capture.add_argument("--suite", type=Path, required=True)
    capture.add_argument("--prefix-oracle", type=Path, required=True)
    capture.add_argument("--server-identity", type=Path, required=True)
    capture.add_argument("--server-gate", type=Path, required=True)
    capture.add_argument("--server-post-gate", type=Path, required=True)
    capture.add_argument("--forensic-server-identity", type=Path, required=True)
    capture.add_argument("--forensic-server-gate", type=Path, required=True)
    capture.add_argument("--forensic-server-post-gate", type=Path, required=True)
    capture.add_argument("--control-input", type=Path)
    capture.add_argument("--control-forensic-input", type=Path)
    capture.add_argument("--expected-control-sha256")
    capture.add_argument("--expected-control-forensic-sha256")
    capture.add_argument("--output", type=Path, required=True)
    capture.set_defaults(handler=gate_capture)

    metrics = commands.add_parser("gate-metrics-binding")
    metrics.add_argument("--mode", choices=("control", "mtp3"), required=True)
    metrics.add_argument("--before", type=Path, required=True)
    metrics.add_argument("--after", type=Path, required=True)
    metrics.add_argument("--capture", type=Path, required=True)
    metrics.add_argument("--sealed-gate", type=Path, required=True)
    metrics.add_argument("--output", type=Path, required=True)
    metrics.set_defaults(handler=gate_metrics_binding)

    compare = commands.add_parser("compare-arms")
    compare.add_argument("--control-capture-gate", type=Path, required=True)
    compare.add_argument("--candidate-capture-gate", type=Path, required=True)
    compare.add_argument("--control-metrics-gate", type=Path, required=True)
    compare.add_argument("--candidate-metrics-gate", type=Path, required=True)
    compare.add_argument("--control-cleanup", type=Path, required=True)
    compare.add_argument("--candidate-cleanup", type=Path, required=True)
    compare.add_argument("--control-forensic-cleanup", type=Path, required=True)
    compare.add_argument("--candidate-forensic-cleanup", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)
    compare.set_defaults(handler=compare_arms)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.handler(args)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"embedded-MTP realistic gate failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail-closed held-out speculation evaluator for OpenAI-compatible services.

The evaluator hashes the frozen candidate and invocation policy before reading
either pack.  It sends only prompts plus uniform generation controls, joins
request-scoped speculative-cycle telemetry, and writes JSON plus Markdown.
No model/runtime imports are used; ``--dry-run`` is a CPU-only transport stub.

Real endpoints must add ``spec_eval_trace`` (a list of cycle objects) and
``spec_eval_request`` (request-level provenance) to an SSE event.  Missing or
malformed telemetry is a hard gate failure.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import random
import statistics
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONTRACT = ROOT / "experiments/deepseek-v4-flash-reap-xpu-b70/quality/spec-eval-contract-v1.json"
DEFAULT_PACKS = (
    ROOT / "experiments/deepseek-v4-flash-reap-xpu-b70/quality/spec-eval-heldout-pack-a-v1.json",
    ROOT / "experiments/deepseek-v4-flash-reap-xpu-b70/quality/spec-eval-heldout-pack-b-v1.json",
)
MODES = ("target-only", "current-control", "candidate")
CONTRACT_MODE = {
    "target-only": "target_only_no_speculation",
    "current-control": "current_target_verified_mtp1",
    "candidate": "candidate",
}
SHORT_COUNTS = {"code": 12, "math_reasoning": 10, "mixed": 20, "tools_json_exact": 6}
PROTECTED_REQUEST_KEYS = {
    "model", "messages", "prompt", "temperature", "top_p", "stream",
    "stream_options", "seed", "max_tokens", "return_token_ids", "cache_salt",
}
FORBIDDEN_PAYLOAD_KEY_PARTS = ("label", "category", "prompt_id", "prompt_hash", "suite")
TRACE_TIMING_FIELDS = (
    "draft_time_ms", "policy_time_ms", "target_verifier_time_ms",
    "commit_time_ms", "rollback_time_ms", "other_time_ms",
)
ALLOWED_PROMPT_BUCKETS = {(32, 128), (129, 512), (513, 900)}
ALLOWED_OUTPUT_BUCKETS = {(8, 48), (96, 192), (256, 512)}


class GateError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha_value(value: Any) -> str:
    return sha_bytes(canonical_bytes(value))


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def percentile(values: Iterable[float], fraction: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    low = math.floor(position)
    high = math.ceil(position)
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def stats(values: Iterable[float]) -> dict[str, float | int | None]:
    rows = [float(value) for value in values]
    return {
        "count": len(rows),
        "p10": percentile(rows, 0.10),
        "median": statistics.median(rows) if rows else None,
        "mean": statistics.fmean(rows) if rows else None,
        "min": min(rows) if rows else None,
        "max": max(rows) if rows else None,
    }


def read_json_bytes_once(path: Path) -> tuple[bytes, Any]:
    # One read call is intentional: pack bytes are never reopened by this process.
    raw = path.read_bytes()
    return raw, json.loads(raw)


def nested_keys(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from nested_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from nested_keys(item)


def validate_request_extra(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GateError("request extras must be a JSON object")
    bad_protected = sorted(PROTECTED_REQUEST_KEYS & set(value))
    if bad_protected:
        raise GateError(f"request extras override protected keys: {bad_protected}")
    bad_metadata = sorted(
        key for key in nested_keys(value)
        if any(part in key.lower() for part in FORBIDDEN_PAYLOAD_KEY_PARTS)
    )
    if bad_metadata:
        raise GateError(f"request extras contain suite metadata-like keys: {bad_metadata}")
    return value


def verify_artifact_record(record: Any, label: str) -> dict[str, Any]:
    if not isinstance(record, dict) or not isinstance(record.get("path"), str) or not isinstance(record.get("sha256"), str):
        raise GateError(f"invalid frozen artifact record: {label}")
    path = Path(record["path"])
    if not path.is_file():
        raise GateError(f"frozen artifact missing: {label}: {path}")
    observed = file_sha(path)
    if observed != record["sha256"]:
        raise GateError(f"frozen artifact changed: {label}: {path}")
    if isinstance(record.get("bytes"), int) and path.stat().st_size != record["bytes"]:
        raise GateError(f"frozen artifact size changed: {label}: {path}")
    return {"path": str(path), "sha256": observed, "bytes": path.stat().st_size}


def validate_manifest(
    manifest: Any,
    contract: dict[str, Any],
    *,
    contract_file_sha256: str,
    dry_run: bool,
) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise GateError("candidate manifest must be a JSON object")
    direct_fields = set(contract["freeze_before_reveal"]["candidate_manifest_fields"])
    direct = direct_fields <= set(manifest)
    helper = {
        "candidate_identity", "controls", "candidate_artifacts", "allowed_policy_inputs", "contract"
    } <= set(manifest)
    if not direct and not helper:
        missing = sorted(direct_fields - set(manifest))
        raise GateError(f"manifest is neither direct-v1 nor freeze-helper-v1; direct fields missing: {missing}")
    if manifest.get("classification") == "deepseek_spec_eval_dry_run_fixture_only" and not dry_run:
        raise GateError("dry-run fixture manifest is forbidden for a real endpoint")
    if direct and not helper and not dry_run:
        raise GateError("real evaluations require an artifact-backed freeze-helper manifest")

    artifact_checks: list[dict[str, Any]] = []
    if helper:
        if manifest.get("holdout_seed_materialized") is not False:
            raise GateError("freeze-helper manifest must precede holdout materialization")
        artifact_checks.append(verify_artifact_record(manifest["contract"], "contract"))
        if artifact_checks[-1]["sha256"] != contract_file_sha256:
            raise GateError("manifest was frozen against different contract bytes")
        artifact_checks.append(verify_artifact_record(manifest["candidate_identity"], "candidate_identity"))
        controls = manifest["controls"]
        artifact_checks.append(verify_artifact_record(controls.get("target_only"), "target_only_control"))
        artifact_checks.append(verify_artifact_record(controls.get("current_mtp1"), "current_mtp1_control"))
        for index, record in enumerate(manifest["candidate_artifacts"]):
            artifact_checks.append(verify_artifact_record(record, f"candidate_artifact_{index}"))

    allowed = manifest.get("allowed_policy_inputs")
    if not isinstance(allowed, list) or any(not isinstance(value, str) for value in allowed):
        raise GateError("allowed_policy_inputs must be a list of strings")
    allowed_set = set(allowed)
    contract_allowed = set(contract["router_allowed_inputs"])
    forbidden = set(contract["router_forbidden_inputs"])
    if allowed_set - contract_allowed:
        raise GateError(f"manifest declares non-contract policy inputs: {sorted(allowed_set - contract_allowed)}")
    if allowed_set & forbidden:
        raise GateError(f"manifest declares forbidden policy inputs: {sorted(allowed_set & forbidden)}")

    if direct:
        policy_material = {
            "draft_router_policy_hashes": manifest["draft_router_policy_hashes"],
            "source_patch_hash": manifest["source_patch_hash"],
            "allowed_policy_inputs": sorted(allowed),
        }
    else:
        policy_material = {
            "candidate_identity": manifest["candidate_identity"],
            "candidate_artifacts": manifest["candidate_artifacts"],
            "allowed_policy_inputs": sorted(allowed),
        }
    return {
        "format": "direct-v1" if direct else "freeze-helper-v1",
        "allowed_policy_inputs": sorted(allowed_set),
        "policy_threshold_config_sha256": sha_value(policy_material),
        "artifact_rehash_checks": artifact_checks,
        "operator_attestations": manifest.get("operator_attestations") or {},
    }


def validate_pack(pack: Any, expected_pack: str) -> dict[str, Any]:
    if not isinstance(pack, dict) or pack.get("pack") != expected_pack:
        raise GateError(f"expected pack {expected_pack}")
    if pack.get("contract_id") != "deepseek-v4-flash-b70-spec-eval-v1":
        raise GateError(f"pack {expected_pack} contract mismatch")
    if pack.get("labels_must_not_be_sent_to_server") is not True:
        raise GateError(f"pack {expected_pack} does not prohibit label transmission")
    requests = pack.get("requests")
    if not isinstance(requests, list) or len(requests) != 64:
        raise GateError(f"pack {expected_pack} must contain 64 requests")
    if sha_value(requests) != pack.get("frozen_requests_sha256"):
        raise GateError(f"pack {expected_pack} frozen request hash mismatch")
    ids = [row.get("local_id") for row in requests]
    prompts = [row.get("prompt") for row in requests]
    if any(not isinstance(value, str) or not value for value in ids + prompts):
        raise GateError(f"pack {expected_pack} has missing IDs/prompts")
    if len(set(ids)) != 64 or len(set(prompts)) != 64:
        raise GateError(f"pack {expected_pack} IDs/prompts are not unique")
    short = [row for row in requests if row.get("long_context") is False]
    long = [row for row in requests if row.get("long_context") is True]
    if len(short) != 48 or len(long) != 16:
        raise GateError(f"pack {expected_pack} workload split is not 48+16")
    if Counter(str(row.get("category")) for row in short) != Counter(SHORT_COUNTS):
        raise GateError(f"pack {expected_pack} short category mix mismatch")
    if Counter(row.get("prompt_token_target") for row in long) != Counter({2048: 8, 4096: 8}):
        raise GateError(f"pack {expected_pack} long target mix mismatch")
    for row in requests:
        prompt_bucket = row.get("prompt_token_bucket")
        output_bucket = row.get("output_token_bucket")
        max_tokens = row.get("max_tokens")
        allowed_prompt_buckets = ALLOWED_PROMPT_BUCKETS | {(1792, 2304), (3840, 4352)}
        if not (isinstance(prompt_bucket, list) and tuple(prompt_bucket) in allowed_prompt_buckets and prompt_bucket[0] <= row.get("construction_tokenish_count", -1) <= prompt_bucket[1]):
            raise GateError(f"pack {expected_pack} invalid prompt bucket: {row.get('local_id')}")
        if not (isinstance(output_bucket, list) and tuple(output_bucket) in ALLOWED_OUTPUT_BUCKETS and isinstance(max_tokens, int) and output_bucket[0] <= max_tokens <= output_bucket[1]):
            raise GateError(f"pack {expected_pack} invalid output bucket: {row.get('local_id')}")
        if row.get("long_context") and float((row.get("diversity") or {}).get("unique_shingle_fraction", 0.0)) < 0.90:
            raise GateError(f"pack {expected_pack} long-context diversity too low: {row.get('local_id')}")
    long_lines = [
        line.strip() for row in long for line in row["prompt"].splitlines()
        if line.strip() and not line.startswith(("Read the following", "Task ", "Independent archive"))
    ]
    if max(Counter(long_lines).values(), default=0) != 1:
        raise GateError(f"pack {expected_pack} repeats long-context lines")
    if Counter(tuple(row["prompt_token_bucket"]) for row in short) != Counter({bucket: 16 for bucket in ALLOWED_PROMPT_BUCKETS}):
        raise GateError(f"pack {expected_pack} prompt bucket distribution mismatch")
    if Counter(tuple(row["output_token_bucket"]) for row in short) != Counter({bucket: 16 for bucket in ALLOWED_OUTPUT_BUCKETS}):
        raise GateError(f"pack {expected_pack} output bucket distribution mismatch")
    required_long_categories = {"prose", "code", "math_reasoning", "extraction", "adversarial_low_locality"}
    if set(str(row.get("category")) for row in long) != required_long_categories:
        raise GateError(f"pack {expected_pack} long-context category coverage mismatch")
    return {
        "suite_id": pack.get("suite_id"),
        "pack": expected_pack,
        "request_count": 64,
        "short_count": 48,
        "long_count": 16,
        "frozen_requests_sha256": pack["frozen_requests_sha256"],
        "minimum_unique_8gram_fraction": min(float(row["diversity"]["unique_shingle_fraction"]) for row in long),
    }


def parse_mode_map(values: list[str], label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise GateError(f"--{label} requires MODE=VALUE")
        mode, item = value.split("=", 1)
        if mode not in MODES or not item:
            raise GateError(f"invalid --{label}: {value}")
        if mode in result:
            raise GateError(f"duplicate --{label} for {mode}")
        result[mode] = item
    return result


def cached_tokens(usage: dict[str, Any]) -> int | None:
    details = usage.get("prompt_tokens_details")
    if not isinstance(details, dict):
        return None
    value = details.get("cached_tokens")
    return value if isinstance(value, int) else None


def real_post_stream(
    *, base_url: str, model: str, prompt: str, max_tokens: int, seed: int,
    timeout: int, request_id: str, cache_salt: str, request_extra: dict[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "top_p": 1,
        "seed": seed,
        "stream": True,
        "stream_options": {"include_usage": True},
        "return_token_ids": True,
        "cache_salt": cache_salt,
    }
    payload.update(request_extra)
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Request-Id": request_id},
        method="POST",
    )
    started_epoch = time.time()
    started = time.perf_counter()
    first_token_at: float | None = None
    token_ids: list[int] = []
    token_offsets: list[float] = []
    text_parts: list[str] = []
    usage: dict[str, Any] = {}
    traces: list[dict[str, Any]] = []
    trace_meta: dict[str, Any] = {}
    response_ids: list[str] = []
    response_request_id: str | None = None
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_request_id = response.headers.get("X-Request-Id")
            for raw in response:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                event = json.loads(data)
                if isinstance(event.get("id"), str):
                    response_ids.append(event["id"])
                if isinstance(event.get("usage"), dict):
                    usage = event["usage"]
                event_trace = event.get("spec_eval_trace")
                if isinstance(event_trace, list):
                    traces.extend(item for item in event_trace if isinstance(item, dict))
                if isinstance(event.get("spec_eval_request"), dict):
                    trace_meta.update(event["spec_eval_request"])
                for choice in event.get("choices") or []:
                    choice_ids = choice.get("token_ids")
                    if isinstance(choice_ids, list):
                        now = time.perf_counter()
                        if choice_ids and first_token_at is None:
                            first_token_at = now
                        token_ids.extend(int(value) for value in choice_ids)
                        token_offsets.extend([now - started] * len(choice_ids))
                    delta = choice.get("delta") or {}
                    text = delta.get("content") or delta.get("reasoning") or choice.get("text") or ""
                    if text:
                        text_parts.append(str(text))
    except urllib.error.URLError as exc:
        raise GateError(f"request {request_id} failed: {exc}") from exc
    ended = time.perf_counter()
    elapsed = ended - started
    completion = usage.get("completion_tokens")
    if not isinstance(completion, int):
        completion = len(token_ids)
    ttft = None if first_token_at is None else first_token_at - started
    return {
        "elapsed_s": elapsed,
        "request_started_epoch_s": started_epoch,
        "request_ended_epoch_s": time.time(),
        "ttft_s": ttft,
        "post_ttft_s": None if first_token_at is None else ended - first_token_at,
        "token_ids": token_ids,
        "token_id_offsets_s": token_offsets,
        "usage": usage,
        "completion_tokens": completion,
        "prompt_tokens": usage.get("prompt_tokens"),
        "cached_tokens": cached_tokens(usage),
        "output_sha256": hashlib.sha256("".join(text_parts).encode("utf-8")).hexdigest(),
        "response_id_first": response_ids[0] if response_ids else None,
        "response_id_last": response_ids[-1] if response_ids else None,
        "response_x_request_id": response_request_id,
        "spec_eval_trace": traces,
        "spec_eval_request": trace_meta,
    }


def mock_post(row: dict[str, Any], mode: str, request_id: str, allowed_inputs: list[str]) -> dict[str, Any]:
    prompt_hash = hashlib.sha256(row["prompt"].encode("utf-8")).digest()
    completion = min(row["max_tokens"], 24)
    token_ids = [100 + int.from_bytes(hashlib.sha256(prompt_hash + index.to_bytes(2, "big")).digest()[:3], "big") % 120000 for index in range(completion)]
    if mode == "target-only":
        group, draft_ms, policy_ms, target_ms, commit_ms = 1, 0.0, 0.0, 2.4, 0.04
    elif mode == "current-control":
        group, draft_ms, policy_ms, target_ms, commit_ms = 2, 0.55, 0.02, 2.0, 0.08
    else:
        group, draft_ms, policy_ms, target_ms, commit_ms = 3, 0.92, 0.08, 1.9, 0.11
    traces: list[dict[str, Any]] = []
    generated = 0
    cycle = 0
    prompt_tokens = int(row["construction_tokenish_count"])
    while generated < completion:
        emitted = min(group, completion - generated)
        proposed = 0 if mode == "target-only" else (1 if mode == "current-control" else 7)
        accepted = max(0, emitted - 1) if proposed else 0
        acceptance = [index < accepted for index in range(proposed)]
        rollback = 0.0 if proposed == accepted else (0.03 if proposed else 0.0)
        timings = {
            "draft_time_ms": draft_ms,
            "policy_time_ms": policy_ms,
            "target_verifier_time_ms": target_ms,
            "commit_time_ms": commit_ms,
            "rollback_time_ms": rollback,
            "other_time_ms": 0.01,
        }
        traces.append({
            "request_id": request_id,
            "cycle": cycle,
            "context_length": prompt_tokens + generated,
            "generated_position": generated,
            "proposed_depth": proposed,
            "per_position_acceptance": acceptance,
            "accepted_prefix_length": accepted,
            "emitted_tokens": emitted,
            "emitted_token_ids": token_ids[generated : generated + emitted],
            "rejection_or_bonus": "no_speculation" if proposed == 0 else ("bonus" if accepted == proposed else "rejection"),
            "policy_mode_and_pre_target_inputs": {
                "mode": CONTRACT_MODE[mode],
                "inputs_used": [] if mode == "target-only" else [value for value in allowed_inputs if value in {"context_length", "draft_confidence"}],
                "pre_target_only": True,
            },
            "timing_ms": timings,
            "draft_policy_verify_commit_time_ms": sum(timings.values()),
            "target_cycles": 1,
            "verifier_width": 1 if mode == "target-only" else proposed + 1,
            "accepted_tokens_target_verified": True,
            "stale_sentinel_detected": False,
        })
        generated += emitted
        cycle += 1
    ttft = 0.018
    rate = {"target-only": 42.0, "current-control": 82.0, "candidate": 92.0}[mode]
    post = completion / rate
    elapsed = ttft + post
    now = time.time()
    return {
        "elapsed_s": elapsed,
        "request_started_epoch_s": now,
        "request_ended_epoch_s": now + elapsed,
        "ttft_s": ttft,
        "post_ttft_s": post,
        "token_ids": token_ids,
        "token_id_offsets_s": [ttft + (index + 1) / rate for index in range(completion)],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion, "prompt_tokens_details": {"cached_tokens": 0}},
        "completion_tokens": completion,
        "prompt_tokens": prompt_tokens,
        "cached_tokens": 0,
        "output_sha256": hashlib.sha256(bytes(value % 256 for value in token_ids)).hexdigest(),
        "response_id_first": "mock-response",
        "response_id_last": "mock-response",
        "response_x_request_id": request_id,
        "spec_eval_trace": traces,
        "spec_eval_request": {
            "request_id": request_id,
            "target_verification_provenance": "unchanged_target_verified",
            "server_cache_history_ngram_response_reuse_disabled": True,
        },
    }


def leading_true(values: list[bool]) -> int:
    count = 0
    for value in values:
        if not value:
            break
        count += 1
    return count


def validate_trace(response: dict[str, Any], mode: str, request_id: str, allowed_inputs: set[str]) -> dict[str, Any]:
    errors: list[str] = []
    traces = response.get("spec_eval_trace")
    meta = response.get("spec_eval_request")
    if not isinstance(traces, list) or not traces:
        return {"passed": False, "errors": ["missing spec_eval_trace"], "cycles": []}
    if not isinstance(meta, dict):
        meta = {}
        errors.append("missing spec_eval_request")
    if meta.get("request_id") != request_id:
        errors.append("trace request_id mismatch")
    if meta.get("target_verification_provenance") != "unchanged_target_verified":
        errors.append("target-verification provenance missing")
    if meta.get("server_cache_history_ngram_response_reuse_disabled") is not True:
        errors.append("server reuse-disable assertion missing")
    prior_position = 0
    normalized: list[dict[str, Any]] = []
    forbidden_inputs = {"prompt_id_or_hash", "suite_category_label", "saved_output_or_target_trace", "future_target_token_or_logit", "benchmark_phrase_list", "manual_per_request_route"}
    for expected_cycle, cycle in enumerate(traces):
        prefix = f"cycle {expected_cycle}"
        required = {
            "request_id", "cycle", "context_length", "generated_position", "proposed_depth",
            "accepted_prefix_length", "emitted_tokens", "rejection_or_bonus",
            "policy_mode_and_pre_target_inputs", "draft_policy_verify_commit_time_ms",
            "target_cycles", "verifier_width", "per_position_acceptance", "timing_ms",
            "emitted_token_ids",
        }
        missing = required - set(cycle)
        if missing:
            errors.append(f"{prefix} missing {sorted(missing)}")
            continue
        if cycle["request_id"] != request_id or cycle["cycle"] != expected_cycle:
            errors.append(f"{prefix} identity/order mismatch")
        proposed = cycle["proposed_depth"]
        acceptance = cycle["per_position_acceptance"]
        if not isinstance(proposed, int) or proposed < 0 or not isinstance(acceptance, list) or len(acceptance) != proposed or any(type(value) is not bool for value in acceptance):
            errors.append(f"{prefix} invalid per-position acceptance")
            continue
        accepted_prefix = cycle["accepted_prefix_length"]
        if not isinstance(accepted_prefix, int) or not 0 <= accepted_prefix <= proposed:
            errors.append(f"{prefix} invalid accepted prefix length")
            continue
        if accepted_prefix != leading_true(acceptance) or any(acceptance[accepted_prefix:]):
            errors.append(f"{prefix} accepted prefix is not contiguous")
        if mode == "target-only" and proposed != 0:
            errors.append(f"{prefix} target-only proposed draft tokens")
        generated_position = cycle["generated_position"]
        if not isinstance(generated_position, int) or generated_position < 0:
            errors.append(f"{prefix} invalid generated position")
            generated_position = prior_position
        if generated_position != prior_position:
            errors.append(f"{prefix} generated position is discontinuous")
        emitted = cycle["emitted_tokens"]
        if not isinstance(emitted, int) or emitted <= 0:
            errors.append(f"{prefix} invalid emitted token count")
        else:
            emitted_ids = cycle["emitted_token_ids"]
            if not isinstance(emitted_ids, list) or len(emitted_ids) != emitted or any(not isinstance(value, int) for value in emitted_ids):
                errors.append(f"{prefix} emitted token IDs mismatch")
            prior_position += emitted
        if not isinstance(cycle["context_length"], int) or cycle["context_length"] < generated_position:
            errors.append(f"{prefix} invalid context length")
        if not isinstance(cycle["target_cycles"], int) or cycle["target_cycles"] < 1:
            errors.append(f"{prefix} invalid target cycle count")
        if not isinstance(cycle["verifier_width"], int) or cycle["verifier_width"] < proposed + 1:
            errors.append(f"{prefix} invalid verifier width")
        if cycle["rejection_or_bonus"] not in {"no_speculation", "rejection", "bonus", "early_eos"}:
            errors.append(f"{prefix} invalid rejection/bonus classification")
        policy = cycle["policy_mode_and_pre_target_inputs"]
        if not isinstance(policy, dict) or policy.get("mode") != CONTRACT_MODE[mode] or policy.get("pre_target_only") is not True:
            errors.append(f"{prefix} policy mode/pre-target assertion mismatch")
        else:
            used = policy.get("inputs_used")
            if not isinstance(used, list) or any(not isinstance(value, str) for value in used):
                errors.append(f"{prefix} invalid policy input list")
            elif set(used) - allowed_inputs or set(used) & forbidden_inputs:
                errors.append(f"{prefix} forbidden/unfrozen policy input")
        timing = cycle["timing_ms"]
        if not isinstance(timing, dict):
            errors.append(f"{prefix} missing timing breakdown")
        else:
            values = [timing.get(field) for field in TRACE_TIMING_FIELDS]
            if any(not isinstance(value, (int, float)) or value < 0 for value in values):
                errors.append(f"{prefix} invalid timing component")
            else:
                combined = float(cycle["draft_policy_verify_commit_time_ms"])
                if not math.isclose(combined, sum(float(value) for value in values), rel_tol=1e-5, abs_tol=1e-4):
                    errors.append(f"{prefix} timing total mismatch")
        if cycle.get("accepted_tokens_target_verified") is not True:
            errors.append(f"{prefix} target verification flag missing")
        if cycle.get("stale_sentinel_detected") is not False:
            errors.append(f"{prefix} stale sentinel flag missing/true")
        normalized.append(cycle)
    if prior_position != response.get("completion_tokens"):
        errors.append("trace emitted-token total differs from completion_tokens")
    completion = response.get("completion_tokens")
    token_ids = response.get("token_ids")
    offsets = response.get("token_id_offsets_s")
    emitted_ids = [token for cycle in normalized for token in cycle.get("emitted_token_ids", [])]
    if not isinstance(completion, int) or completion <= 0:
        errors.append("invalid completion_tokens")
    elif not isinstance(token_ids, list) or len(token_ids) != completion or any(not isinstance(value, int) for value in token_ids):
        errors.append("stream token IDs do not exactly cover completion_tokens")
    elif emitted_ids != token_ids:
        errors.append("cycle emitted token IDs differ from stream token IDs")
    if not isinstance(offsets, list) or not isinstance(token_ids, list) or len(offsets) != len(token_ids):
        errors.append("token offset count differs from stream token IDs")
    elif any(not isinstance(value, (int, float)) for value in offsets) or any(right < left for left, right in zip(offsets, offsets[1:])):
        errors.append("token offsets are invalid or nonmonotonic")
    return {"passed": not errors, "errors": errors, "cycles": normalized, "request_meta": meta}


def request_metrics(response: dict[str, Any]) -> dict[str, float | None]:
    completion = response.get("completion_tokens")
    elapsed = response.get("elapsed_s")
    post = response.get("post_ttft_s")
    offsets = response.get("token_id_offsets_s") or []
    metric = None
    if len(offsets) >= 100 and offsets[99] > offsets[0]:
        metric = 100.0 / (offsets[99] - offsets[0])
    return {
        "tok_s_wall_full": completion / elapsed if isinstance(completion, int) and completion > 0 and isinstance(elapsed, (int, float)) and elapsed > 0 else None,
        "tok_s_after_ttft_full": completion / post if isinstance(completion, int) and completion > 0 and isinstance(post, (int, float)) and post > 0 else None,
        "tok_s_1_100_after_ttft": metric,
    }


def summarize_mode(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cycles = [cycle for row in rows for cycle in row["trace_validation"].get("cycles", [])]
    completion = sum(int(row["completion_tokens"]) for row in rows if isinstance(row.get("completion_tokens"), int))
    elapsed = sum(float(row["elapsed_s"]) for row in rows if isinstance(row.get("elapsed_s"), (int, float)))
    target_cycles = sum(int(cycle["target_cycles"]) for cycle in cycles)
    emitted = sum(int(cycle["emitted_tokens"]) for cycle in cycles)
    draft_policy = sum(float(cycle["timing_ms"]["draft_time_ms"]) + float(cycle["timing_ms"]["policy_time_ms"]) for cycle in cycles)
    proposed_by_position: Counter[int] = Counter()
    accepted_by_position: Counter[int] = Counter()
    for cycle in cycles:
        for position, accepted in enumerate(cycle["per_position_acceptance"], start=1):
            proposed_by_position[position] += 1
            accepted_by_position[position] += int(accepted)
    categories: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        value = row["metrics"].get("tok_s_wall_full")
        if isinstance(value, (int, float)):
            categories["long_context" if row["long_context"] else row["category"]].append(float(value))
    return {
        "request_count": len(rows),
        "complete_wall_throughput_tok_s": completion / elapsed if elapsed else None,
        "tok_s_wall_full": stats(row["metrics"]["tok_s_wall_full"] for row in rows if row["metrics"]["tok_s_wall_full"] is not None),
        "tok_s_after_ttft_full": stats(row["metrics"]["tok_s_after_ttft_full"] for row in rows if row["metrics"]["tok_s_after_ttft_full"] is not None),
        "tok_s_1_100_after_ttft": stats(row["metrics"]["tok_s_1_100_after_ttft"] for row in rows if row["metrics"]["tok_s_1_100_after_ttft"] is not None),
        "ttft_ms": stats(float(row["ttft_s"]) * 1000 for row in rows if isinstance(row.get("ttft_s"), (int, float))),
        "target_cycles": target_cycles,
        "emitted_tokens": emitted,
        "emitted_tokens_per_target_cycle": emitted / target_cycles if target_cycles else None,
        "draft_plus_policy_ms_per_cycle": draft_policy / len(cycles) if cycles else None,
        "per_position_acceptance": {
            str(position): {
                "proposed": proposed_by_position[position],
                "accepted": accepted_by_position[position],
                "fraction": accepted_by_position[position] / proposed_by_position[position],
            }
            for position in sorted(proposed_by_position)
        },
        "category_wall_tok_s": {key: stats(values) for key, values in sorted(categories.items())},
        "timing_ms_per_cycle": {
            field: stats(float(cycle["timing_ms"][field]) for cycle in cycles)
            for field in TRACE_TIMING_FIELDS
        },
    }


def percent_change(candidate: float | None, control: float | None) -> float | None:
    if not isinstance(candidate, (int, float)) or not isinstance(control, (int, float)) or control == 0:
        return None
    return (candidate / control - 1.0) * 100.0


def paired_bootstrap_lower(differences: list[float], seed: int, samples: int = 2000) -> float | None:
    if not differences:
        return None
    rng = random.Random(seed)
    means = [statistics.fmean(rng.choice(differences) for _ in differences) for _ in range(samples)]
    return percentile(means, 0.025)


def comparisons(rows: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    by_key: dict[tuple[str, int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_key[(row["pack"], row["repetition"], row["local_id"])][row["mode"]] = row
    parity: dict[str, Any] = {}
    state_leak: dict[str, Any] = {}
    for mode in ("current-control", "candidate"):
        pairs = [value for value in by_key.values() if "target-only" in value and mode in value]
        matches = [pair[mode]["token_ids"] == pair["target-only"]["token_ids"] for pair in pairs]
        parity[mode] = {"compared": len(matches), "matched": sum(matches), "percent": 100.0 * sum(matches) / len(matches) if matches else None, "passed": bool(matches) and all(matches)}
    by_repeat: dict[tuple[str, str, str], list[list[int]]] = defaultdict(list)
    for row in rows:
        by_repeat[(row["mode"], row["pack"], row["local_id"])].append(row["token_ids"])
    for mode in MODES:
        groups = [values for (key_mode, _, _), values in by_repeat.items() if key_mode == mode]
        state_leak[mode] = {"groups": len(groups), "stable": sum(all(value == values[0] for value in values[1:]) for values in groups), "passed": bool(groups) and all(len(values) >= 2 and all(value == values[0] for value in values[1:]) for values in groups)}
    def compare_subset(subset: list[dict[str, Any]], subset_seed: int) -> dict[str, Any]:
        candidate_rows = [row for row in subset if row["mode"] == "candidate"]
        control_rows = [row for row in subset if row["mode"] == "current-control"]
        candidate = summarize_mode(candidate_rows) if candidate_rows else {}
        control = summarize_mode(control_rows) if control_rows else {}
        subset_by_key: dict[tuple[str, int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
        for row in subset:
            subset_by_key[(row["pack"], row["repetition"], row["local_id"])][row["mode"]] = row
        differences: list[float] = []
        mixed_candidate: list[float] = []
        mixed_control: list[float] = []
        for value in subset_by_key.values():
            if "candidate" in value and "current-control" in value:
                candidate_value = value["candidate"]["metrics"].get("tok_s_wall_full")
                control_value = value["current-control"]["metrics"].get("tok_s_wall_full")
                if isinstance(candidate_value, (int, float)) and isinstance(control_value, (int, float)):
                    differences.append(float(candidate_value) - float(control_value))
                    if value["candidate"]["category"] == "mixed" and not value["candidate"]["long_context"]:
                        mixed_candidate.append(float(candidate_value))
                        mixed_control.append(float(control_value))
        category_regressions: dict[str, float | None] = {}
        for category in set((candidate.get("category_wall_tok_s") or {})) | set((control.get("category_wall_tok_s") or {})):
            category_regressions[category] = percent_change(
                (candidate.get("category_wall_tok_s") or {}).get(category, {}).get("p10"),
                (control.get("category_wall_tok_s") or {}).get(category, {}).get("p10"),
            )
        return {
            "complete_wall_improvement_percent": percent_change(candidate.get("complete_wall_throughput_tok_s"), control.get("complete_wall_throughput_tok_s")),
            "median_decode_improvement_percent": percent_change((candidate.get("tok_s_after_ttft_full") or {}).get("median"), (control.get("tok_s_after_ttft_full") or {}).get("median")),
            "mixed_wall_improvement_percent": percent_change(statistics.median(mixed_candidate) if mixed_candidate else None, statistics.median(mixed_control) if mixed_control else None),
            "paired_bootstrap_mean_wall_tok_s_difference_95pct_lower": paired_bootstrap_lower(differences, subset_seed),
            "category_and_long_context_p10_change_percent": category_regressions,
        }

    overall = compare_subset(rows, seed)
    per_pack = {
        pack: compare_subset([row for row in rows if row["pack"] == pack], seed + ord(pack))
        for pack in ("A", "B")
    }
    return {
        "greedy_token_id_parity": parity,
        "repetition_output_stability": state_leak,
        "candidate_vs_current_control": overall,
        "candidate_vs_current_control_by_pack": per_pack,
    }


def render_human(result: dict[str, Any]) -> str:
    def rendered(value: Any) -> str:
        return f"{value:.3f}" if isinstance(value, (int, float)) else "n/a"

    contract = result["spec_eval_contract"]
    lines = [
        "# DeepSeek V4 Flash held-out speculation evaluation",
        "",
        f"- classification: `{result['run_identity']['classification']}`",
        f"- passed: `{result['gate']['passed']}`",
        f"- frozen config SHA-256: `{contract['frozen_config_sha256']}`",
        f"- policy/threshold SHA-256: `{contract['policy_threshold_config_sha256']}`",
        f"- pack SHA-256: A `{result['packs']['A']['file_sha256']}`, B `{result['packs']['B']['file_sha256']}`",
        f"- cached tokens all zero: `{result['gate']['cached_tokens_all_zero']}`",
        f"- greedy token-ID parity passed: `{result['gate']['greedy_token_id_parity_passed']}`",
        f"- request trace schema passed: `{result['gate']['request_trace_passed']}`",
        "",
        "## Mode summary",
        "",
        "| mode | complete wall tok/s | emitted/target cycle | draft+policy ms/cycle |",
        "|---|---:|---:|---:|",
    ]
    for mode in MODES:
        summary = result["summary_by_mode"].get(mode)
        if summary:
            lines.append(
                f"| {mode} | {rendered(summary['complete_wall_throughput_tok_s'])} | "
                f"{rendered(summary['emitted_tokens_per_target_cycle'])} | "
                f"{rendered(summary['draft_plus_policy_ms_per_cycle'])} |"
            )
    lines.extend(["", "## Anti-cheating", "", "Code-enforced assertions and operator attestations are separated in `spec_eval_contract.anti_cheating_assertions`; an operator attestation is never promoted to client-proven evidence.", ""])
    return "\n".join(lines)


def exclusive_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(text)


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--pack", type=Path, action="append", default=[])
    parser.add_argument("--mode", choices=("all", *MODES), default="all")
    parser.add_argument("--endpoint", action="append", default=[], help="MODE=http://host:port")
    parser.add_argument("--model", action="append", default=[], help="MODE=model-name")
    parser.add_argument("--default-model", default="deepseek-v4-flash")
    parser.add_argument("--request-extra-json", default="{}")
    parser.add_argument("--seed", type=int, default=20260719)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.repetitions < 2:
        raise GateError("contract requires at least two complete repetitions")
    request_extra = validate_request_extra(json.loads(args.request_extra_json))
    endpoints = parse_mode_map(args.endpoint, "endpoint")
    models = parse_mode_map(args.model, "model")
    active_modes = list(MODES if args.mode == "all" else (args.mode,))
    if not args.dry_run:
        missing_endpoints = [mode for mode in active_modes if mode not in endpoints]
        if missing_endpoints:
            raise GateError(f"missing endpoints for modes: {missing_endpoints}")

    # Freeze phase: contract, manifest, and all evaluator controls are loaded and
    # hashed before the first held-out pack byte is read.
    contract_raw, contract = read_json_bytes_once(args.contract)
    manifest_raw, manifest = read_json_bytes_once(args.candidate_manifest)
    if contract.get("contract_id") != "deepseek-v4-flash-b70-spec-eval-v1":
        raise GateError("unexpected contract identity")
    manifest_check = validate_manifest(
        manifest,
        contract,
        contract_file_sha256=sha_bytes(contract_raw),
        dry_run=args.dry_run,
    )
    evaluation_config = {
        "evaluator_sha256": file_sha(Path(__file__).resolve()),
        "mode": args.mode,
        "active_modes": active_modes,
        "endpoint_sha256_by_mode": {
            mode: hashlib.sha256(endpoints[mode].encode("utf-8")).hexdigest()
            for mode in sorted(endpoints)
        },
        "models": {mode: models.get(mode, args.default_model) for mode in active_modes},
        "request_extra": request_extra,
        "seed": args.seed,
        "repetitions": args.repetitions,
        "greedy": {"temperature": 0, "top_p": 1, "return_token_ids": True},
        "unique_cache_salt_per_request": True,
    }
    freeze_hashed_at = utc_now()
    frozen_config_sha = sha_value({"candidate_manifest": manifest, "evaluation_config": evaluation_config})

    pack_paths = tuple(args.pack) if args.pack else DEFAULT_PACKS
    if len(pack_paths) != 2:
        raise GateError("exactly two independent packs are required")
    packs: dict[str, dict[str, Any]] = {}
    pack_records: dict[str, Any] = {}
    pack_first_read_at: dict[str, str] = {}
    for expected_pack, path in zip(("A", "B"), pack_paths, strict=True):
        pack_first_read_at[expected_pack] = utc_now()
        raw, payload = read_json_bytes_once(path)
        pack_records[expected_pack] = payload
        pack_info = validate_pack(payload, expected_pack)
        pack_info.update({"path": str(path), "file_sha256": sha_bytes(raw), "first_read_at_utc": pack_first_read_at[expected_pack]})
        packs[expected_pack] = pack_info
    hashes_a = {hashlib.sha256(row["prompt"].encode("utf-8")).hexdigest() for row in pack_records["A"]["requests"]}
    hashes_b = {hashlib.sha256(row["prompt"].encode("utf-8")).hexdigest() for row in pack_records["B"]["requests"]}
    if hashes_a & hashes_b:
        raise GateError("pack A/B prompt overlap")

    rows: list[dict[str, Any]] = []
    seen_request_ids: set[str] = set()
    launch_order_by_pack = {
        "A": [mode for mode in MODES if mode in active_modes],
        "B": [mode for mode in reversed(MODES) if mode in active_modes],
    }
    for repetition in range(1, args.repetitions + 1):
        for pack_name in ("A", "B"):
            requests = list(pack_records[pack_name]["requests"])
            order_seed = int.from_bytes(hashlib.sha256(f"{frozen_config_sha}:{packs[pack_name]['file_sha256']}:{repetition}".encode()).digest()[:8], "big")
            random.Random(order_seed).shuffle(requests)
            for mode in launch_order_by_pack[pack_name]:
                for order_index, item in enumerate(requests):
                    request_id = str(uuid.uuid4())
                    cache_salt = str(uuid.uuid4())
                    if request_id in seen_request_ids:
                        raise GateError("UUID collision")
                    seen_request_ids.add(request_id)
                    if args.dry_run:
                        response = mock_post(item, mode, request_id, manifest_check["allowed_policy_inputs"])
                    else:
                        response = real_post_stream(
                            base_url=endpoints[mode], model=models.get(mode, args.default_model),
                            prompt=item["prompt"], max_tokens=item["max_tokens"], seed=args.seed,
                            timeout=args.timeout, request_id=request_id, cache_salt=cache_salt,
                            request_extra=request_extra,
                        )
                    trace_validation = validate_trace(response, mode, request_id, set(manifest_check["allowed_policy_inputs"]))
                    prompt_tokens = response.get("prompt_tokens")
                    bucket = item["prompt_token_bucket"]
                    prompt_bucket_passed = isinstance(prompt_tokens, int) and bucket[0] <= prompt_tokens <= bucket[1]
                    row = {
                        "pack": pack_name,
                        "repetition": repetition,
                        "launch_order_index": order_index,
                        "mode": mode,
                        "local_id": item["local_id"],
                        "category": item["category"],
                        "long_context": item["long_context"],
                        "prompt_sha256": hashlib.sha256(item["prompt"].encode("utf-8")).hexdigest(),
                        "prompt_token_bucket": bucket,
                        "output_token_bucket": item["output_token_bucket"],
                        "max_tokens": item["max_tokens"],
                        "request_id": request_id,
                        "cache_salt_sha256": hashlib.sha256(cache_salt.encode()).hexdigest(),
                        "request_payload_keys": sorted({"model", "messages", "max_tokens", "temperature", "top_p", "seed", "stream", "stream_options", "return_token_ids", "cache_salt", *request_extra}),
                        "suite_metadata_sent_to_server": False,
                        "prompt_tokens": prompt_tokens,
                        "prompt_token_bucket_passed": prompt_bucket_passed,
                        "completion_tokens": response.get("completion_tokens"),
                        "cached_tokens": response.get("cached_tokens"),
                        "elapsed_s": response.get("elapsed_s"),
                        "ttft_s": response.get("ttft_s"),
                        "post_ttft_s": response.get("post_ttft_s"),
                        "token_ids": response.get("token_ids"),
                        "token_id_offsets_s": response.get("token_id_offsets_s"),
                        "output_sha256": response.get("output_sha256"),
                        "response_id_first": response.get("response_id_first"),
                        "response_id_last": response.get("response_id_last"),
                        "response_x_request_id": response.get("response_x_request_id"),
                        "metrics": request_metrics(response),
                        "trace_validation": trace_validation,
                    }
                    rows.append(row)

    summary_by_mode = {mode: summarize_mode([row for row in rows if row["mode"] == mode]) for mode in active_modes}
    comparison = comparisons(rows, args.seed)
    cached_zero = all(row.get("cached_tokens") == 0 for row in rows)
    token_ids_present = all(isinstance(row.get("token_ids"), list) and row["token_ids"] for row in rows)
    prompt_buckets_pass = all(row["prompt_token_bucket_passed"] for row in rows)
    trace_pass = all(row["trace_validation"]["passed"] for row in rows)
    response_ids_match = all(row["response_x_request_id"] in (None, row["request_id"]) for row in rows)
    parity_pass = args.mode == "all" and all(comparison["greedy_token_id_parity"][mode]["passed"] for mode in ("current-control", "candidate"))
    repetition_pass = all(comparison["repetition_output_stability"].get(mode, {}).get("passed") is True for mode in active_modes)
    dev = contract["development_gate"]
    candidate_summary = summary_by_mode.get("candidate") or {}
    candidate_rows_mixed = [row for row in rows if row["mode"] == "candidate" and row["category"] == "mixed" and not row["long_context"]]
    mixed_cycles = [cycle for row in candidate_rows_mixed for cycle in row["trace_validation"].get("cycles", [])]
    mixed_emitted = sum(cycle["emitted_tokens"] for cycle in mixed_cycles)
    mixed_targets = sum(cycle["target_cycles"] for cycle in mixed_cycles)
    dev_gate = {
        "overall_emitted_tokens_per_target_cycle": candidate_summary.get("emitted_tokens_per_target_cycle"),
        "mixed_emitted_tokens_per_target_cycle": mixed_emitted / mixed_targets if mixed_targets else None,
        "draft_plus_policy_ms_per_cycle": candidate_summary.get("draft_plus_policy_ms_per_cycle"),
    }
    dev_gate["passed"] = (
        isinstance(dev_gate["overall_emitted_tokens_per_target_cycle"], (int, float))
        and dev_gate["overall_emitted_tokens_per_target_cycle"] >= dev["emitted_tokens_per_target_cycle_overall_minimum"]
        and isinstance(dev_gate["mixed_emitted_tokens_per_target_cycle"], (int, float))
        and dev_gate["mixed_emitted_tokens_per_target_cycle"] >= dev["emitted_tokens_per_target_cycle_mixed_minimum"]
        and isinstance(dev_gate["draft_plus_policy_ms_per_cycle"], (int, float))
        and dev_gate["draft_plus_policy_ms_per_cycle"] <= dev["draft_plus_policy_ms_per_cycle_maximum"]
    )
    promotion = contract["promotion_gate"]
    promotion_by_pack: dict[str, Any] = {}
    for pack_name, evidence in comparison["candidate_vs_current_control_by_pack"].items():
        category_changes = evidence["category_and_long_context_p10_change_percent"]
        checks = {
            "wall_improvement": isinstance(evidence["complete_wall_improvement_percent"], (int, float)) and evidence["complete_wall_improvement_percent"] >= promotion["improvement_over_same_build_mtp1_pack_wall_percent_minimum"],
            "median_decode_improvement": isinstance(evidence["median_decode_improvement_percent"], (int, float)) and evidence["median_decode_improvement_percent"] >= promotion["improvement_over_same_build_mtp1_median_decode_percent_minimum"],
            "mixed_improvement": isinstance(evidence["mixed_wall_improvement_percent"], (int, float)) and evidence["mixed_wall_improvement_percent"] >= promotion["mixed_workload_improvement_percent_minimum"],
            "paired_bootstrap_lower_above_zero": isinstance(evidence["paired_bootstrap_mean_wall_tok_s_difference_95pct_lower"], (int, float)) and evidence["paired_bootstrap_mean_wall_tok_s_difference_95pct_lower"] > 0,
            "category_and_long_p10_regression_within_limit": bool(category_changes) and all(isinstance(value, (int, float)) and value >= -promotion["category_or_long_context_p10_regression_percent_maximum"] for value in category_changes.values()),
        }
        promotion_by_pack[pack_name] = {"evidence": evidence, "checks": checks, "passed": all(checks.values())}
    promotion_gate = {
        "by_pack": promotion_by_pack,
        "independent_packs_present": set(promotion_by_pack) == {"A", "B"},
        "complete_repetitions_without_state_leak": args.repetitions >= 2 and repetition_pass,
        "correctness_and_cache_gates": cached_zero and trace_pass and parity_pass,
    }
    promotion_gate["client_evidence_passed"] = (
        args.mode == "all"
        and promotion_gate["independent_packs_present"]
        and promotion_gate["complete_repetitions_without_state_leak"]
        and promotion_gate["correctness_and_cache_gates"]
        and all(item["passed"] for item in promotion_by_pack.values())
    )
    client_gate_pass = cached_zero and token_ids_present and prompt_buckets_pass and trace_pass and response_ids_match and repetition_pass and (parity_pass if args.mode == "all" else True)
    code_assertions = {
        "candidate_and_policy_hashed_before_pack_read": True,
        "pack_bytes_read_once": True,
        "pack_hashes_and_frozen_request_hashes_verified": True,
        "pack_counts_mix_uniqueness_and_nonrepetition_verified": True,
        "request_order_randomized_after_freeze": True,
        "pack_b_request_mode_order_reversed": launch_order_by_pack["B"] == list(reversed(launch_order_by_pack["A"])),
        "suite_labels_categories_ids_hashes_not_in_payload": all(row["suite_metadata_sent_to_server"] is False for row in rows),
        "uniform_mode_configuration_no_per_prompt_overrides": True,
        "unique_random_request_ids_and_cache_salts": len(seen_request_ids) == len(rows),
        "cached_tokens_present_and_zero": cached_zero,
        "repeated_continuation_history_not_sent": True,
        "prompt_specific_or_forbidden_policy_inputs_rejected_from_manifest_and_trace": trace_pass,
        "target_verification_provenance_evidence_present": trace_pass,
        "per_position_acceptance_and_cycle_costs_present": trace_pass,
        "greedy_token_id_parity_100_percent": parity_pass,
        "two_complete_repetitions_output_stable": repetition_pass,
        "timeouts_fail_closed": True,
        "endpoint_prompt_token_buckets_passed": prompt_buckets_pass,
    }
    operator_only = {
        "candidate_was_not_inspected_or_changed_after_external_pack_reveal": "operator_attestation_required",
        "server_launch_actually_disabled_prefix_kv_history_ngram_and_response_reuse": "telemetry_attested_but_external_audit_required",
        "unchanged_target_same_build_and_true_target_verification": "trace_and_manifest_attested_but_external_audit_required",
        "router_implementation_has_no_hidden_forbidden_inputs_or_benchmark_phrase_list": "source_audit_required",
        "frozen_classifier_and_policy_hashes_match_loaded_worker_code": "worker_artifact_audit_required",
        "timeout_worker_restart_procedure_was_executed": "operator_required_if_timeout_occurs",
        "ordered_graph_capture_replay_minimum_128_crossing_positions_28_and_58": "separate_runtime_gate_required",
        "early_eos_cancellation_reset_alternating_context": "separate_runtime_gate_required",
        "exact_token_counts_use_the_frozen_target_tokenizer": "endpoint_usage_checked; tokenizer identity remains operator-audited",
        "pack_b_service_launch_order_was_reversed": "operator_or_external_runner_evidence_required",
        "target_logprob_positions_minimum_64": "separate_captured-logprob gate required",
    }
    result: dict[str, Any] = {
        "run_identity": {
            "created_at_utc": utc_now(),
            "classification": "cpu_dry_run_non_promotable" if args.dry_run else "heldout_endpoint_evaluation",
            "dry_run": args.dry_run,
            "mode": args.mode,
            "active_modes": active_modes,
            "repetitions": args.repetitions,
            "request_count": len(rows),
            "models": evaluation_config["models"],
        },
        "spec_eval_contract": {
            "contract_id": contract["contract_id"],
            "contract_sha256_raw": sha_bytes(contract_raw),
            "candidate_manifest_sha256_raw": sha_bytes(manifest_raw),
            "candidate_manifest_sha256_canonical": sha_value(manifest),
            "candidate_manifest_format": manifest_check["format"],
            "frozen_config_sha256": frozen_config_sha,
            "policy_threshold_config_sha256": manifest_check["policy_threshold_config_sha256"],
            "freeze_hashed_at_utc": freeze_hashed_at,
            "first_pack_read_at_utc": pack_first_read_at["A"],
            "manifest_hashed_before_pack_read_in_this_process": freeze_hashed_at <= pack_first_read_at["A"],
            "temporal_candidate_freeze_before_human_pack_reveal": "operator_attestation_required",
            "allowed_policy_inputs": manifest_check["allowed_policy_inputs"],
            "artifact_rehash_checks": manifest_check["artifact_rehash_checks"],
            "anti_cheating_assertions": {
                "code_enforced": code_assertions,
                "operator_attested_or_external_audit": operator_only,
                "manifest_operator_attestations": manifest_check["operator_attestations"],
            },
        },
        "packs": packs,
        "launch_order_by_pack": launch_order_by_pack,
        "summary_by_mode": summary_by_mode,
        "comparisons": comparison,
        "development_gate": dev_gate,
        "promotion_gate": promotion_gate,
        "gate": {
            "passed": client_gate_pass and (dev_gate["passed"] if "candidate" in active_modes else True) and not args.dry_run,
            "dry_run_schema_passed": client_gate_pass and (dev_gate["passed"] if "candidate" in active_modes else True),
            "client_promotion_evidence_passed": promotion_gate["client_evidence_passed"],
            "promotable": False,
            "promotable_note": "Operator/external runtime gates remain required even when client_promotion_evidence_passed is true.",
            "cached_tokens_all_zero": cached_zero,
            "token_ids_present_every_request": token_ids_present,
            "endpoint_prompt_token_buckets_passed": prompt_buckets_pass,
            "request_trace_passed": trace_pass,
            "response_request_ids_match": response_ids_match,
            "greedy_token_id_parity_passed": parity_pass,
            "repetition_output_stability_passed": repetition_pass,
            "operator_only_rules_are_not_client_proven": True,
        },
        "requests": rows,
    }
    summary_path = args.summary_out or args.out.with_suffix(".md")
    existing_outputs = [str(path) for path in (args.out, summary_path) if path.exists()]
    if existing_outputs:
        raise GateError(f"refusing to overwrite outputs: {existing_outputs}")
    exclusive_write(args.out, json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    exclusive_write(summary_path, render_human(result))
    print(json.dumps({
        "json": str(args.out), "summary": str(summary_path),
        "frozen_config_sha256": frozen_config_sha,
        "dry_run_schema_passed": result["gate"]["dry_run_schema_passed"],
        "promotable": result["gate"]["promotable"],
        "requests": len(rows),
    }, indent=2))
    return 0 if (result["gate"]["dry_run_schema_passed"] if args.dry_run else result["gate"]["passed"]) else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, json.JSONDecodeError, OSError, ValueError) as exc:
        raise SystemExit(f"spec-eval failed closed: {exc}")

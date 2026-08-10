#!/usr/bin/env python3
"""Build the reviewed Qwen3.6 27B Q8 embedded-MTP LocalMaxxing packet.

This is an offline derivation only.  It verifies the immutable failed source
run, the sealed matched-control supplement, and the exact scored row identity
before writing a queue entry.  It never reads credentials or contacts the API.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import statistics
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
LANE = HERE.parent
REPO = LANE.parents[1]

DEFAULT_RUN = Path(
    "/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/"
    "embedded-mtp-vdr2-realistic-gpu0-20260810T101337.129519194Z"
)
DEFAULT_SUPPLEMENT = Path(
    "/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/offline-supplemental/"
    "embedded-mtp-realistic-stale-oracle-final-20260810T101337.KjteSJ"
)
DEFAULT_OUT = (
    LANE
    / "localmaxxing"
    / ("qwen36-27b-mtp-q8_0-vdr2-embedded-mtp3-realistic-36tok-20260810.queue.json")
)
DEFAULT_AUDIT = (
    LANE
    / "localmaxxing"
    / (
        "qwen36-27b-mtp-q8_0-vdr2-embedded-mtp3-realistic-36tok-20260810.builder-audit.json"
    )
)
DEFAULT_API_REQUEST = (
    LANE
    / "localmaxxing"
    / (
        "qwen36-27b-mtp-q8_0-vdr2-embedded-mtp3-realistic-36tok-20260810.api-request.json"
    )
)

HF_ID = "unsloth/Qwen3.6-27B-MTP-GGUF"
MODEL_REVISION = "5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace"
MODEL_FILE = "Qwen3.6-27B-Q8_0.gguf"
MODEL_SIZE = 29_047_084_160
MODEL_SHA256 = "9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8"
RUNTIME_COMMIT = "15586e2d7165570fb3aa7c26e0d442e289ef69de"
RUNTIME_SHA256 = "1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7"
RUNTIME_MANIFEST_SHA256 = (
    "4119790a79c55d158e7257d4fa0d95be0ca34639807c1a71ce87b60d6fdc1b49"
)
SUITE_SHA256 = "df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac"
SUITE_ID = "qwen36-27b-autoround-int4-b70-realistic-v1"
RUN_MANIFEST_SHA256 = "8b0e18c529eabaf837bfb8fc2b2f7b5bc4f280c1952b741dc85e1fefc9425f89"
SUPPLEMENT_MANIFEST_SHA256 = (
    "d44cef315a2d88652bdaeb9694a718897f2d301f916a4d9d419f41190519a2c3"
)
COMPARISON_SHA256 = "41d754812311ad657f7f59b7f51794e7b394a82096587123280fdf76dc510ae3"
SUPPLEMENT_IDENTITY_SHA256 = (
    "d966b5d2996cee86faba0ef95b68afdabfcd95fb25d97078319680b8b922ae49"
)
COMPLETION_STATUS_SHA256 = (
    "3eaf8d2c72bc64e2440e42486ca69b3605d357cc6e782aae79fd21c059e03c7f"
)
RUN_STATUS_SHA256 = "4f8e9e45f8a9e1843b81eaf3bdf52a6b778d415d23bf985774a9d34a43f69bd5"
SCORED_CONTROL_SHA256 = (
    "16d87bf37f6654e5ac920849dc5c97288bea14d70904354780894d7b9fc7a29c"
)
FORENSIC_CONTROL_SHA256 = (
    "8af30d579a30aedf3cadaa8f0728d883acc7d0da188bd2b30125b472f37a2ad2"
)
SCORED_MTP3_SHA256 = "0ce2399561568c4d80d112f42457fc31acedbddac576f1900e64ba88ee1352e7"
FORENSIC_MTP3_SHA256 = (
    "886107c29af70fba5ce0919091d1122c5e0317a0811cce9169819d65076c49c0"
)
CONTROL_CAPTURE_GATE_SHA256 = (
    "708162bccf98fa77e94022ce42bb77ef1bb96581c090326669123dcfaf430ef0"
)
CONTROL_METRICS_GATE_SHA256 = (
    "e7b1847322fa08a74fd82c6627b070584f4622f62984b8f3d407c51a94f72e33"
)
MTP3_CAPTURE_GATE_SHA256 = (
    "95dad265e308c2a1787d81c7a874eb2a2a2cab7ce513a7d6e9ec02fa448987d6"
)
MTP3_METRICS_GATE_SHA256 = (
    "93974dab89d6f0f2a25e994803478160b8ea5606f52e683efa41a81aed254f0b"
)
PRIMARY_METRIC = "median_tok_s_1_100_intervals_after_ttft"
PRIMARY_VALUE = 36.04870684253697
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def require_hash(path: Path, expected: str) -> None:
    require(path.is_file(), f"required artifact is missing: {path}")
    observed = sha256_file(path)
    require(observed == expected, f"SHA-256 mismatch for {path}: {observed}")


def verify_manifest(root: Path, expected_sha: str, expected_entries: int) -> None:
    manifest = root / "artifacts.sha256"
    require_hash(manifest, expected_sha)
    lines = [line for line in manifest.read_text().splitlines() if line.strip()]
    require(len(lines) == expected_entries, f"unexpected manifest size: {manifest}")
    for line in lines:
        digest, separator, relative = line.partition("  ")
        require(separator == "  ", f"malformed manifest line: {line}")
        relative_path = Path(relative.removeprefix("./"))
        require(not relative_path.is_absolute(), f"absolute manifest path: {relative}")
        require(".." not in relative_path.parts, f"escaping manifest path: {relative}")
        require_hash(root / relative_path, digest)


def env_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text().splitlines():
        key, separator, value = line.partition("=")
        require(bool(key) and separator == "=", f"malformed env line in {path}")
        require(key not in result, f"duplicate env key in {path}: {key}")
        result[key] = value
    return result


def argv_values(argv: list[str], option: str) -> list[str]:
    return [argv[index + 1] for index in range(len(argv) - 1) if argv[index] == option]


def completion_length_policy(
    counts: list[int], *, metric_tokens: int = 100, max_tokens: int = 512
) -> dict[str, Any]:
    """Validate natural stops against the timed window, not the request cap."""
    if not counts or any(
        isinstance(value, bool) or not isinstance(value, int) for value in counts
    ):
        raise ValueError("completion lengths must be a nonempty integer list")
    if any(value < metric_tokens for value in counts):
        raise ValueError(
            f"every response must reach the {metric_tokens}-event primary window"
        )
    if any(value > max_tokens for value in counts):
        raise ValueError(f"completion length exceeds max_tokens={max_tokens}")
    return {
        "eligible": True,
        "minimumRequiredGeneratedTokens": metric_tokens,
        "minimumObservedGeneratedTokens": min(counts),
        "maximumRequestedGeneratedTokens": max_tokens,
        "allRowsReachedRequestMaximum": all(value == max_tokens for value in counts),
        "naturalStopsAfterPrimaryWindowAllowed": True,
    }


def validate_source(run_root: Path, supplement_root: Path) -> dict[str, Any]:
    verify_manifest(run_root, RUN_MANIFEST_SHA256, 132)
    verify_manifest(supplement_root, SUPPLEMENT_MANIFEST_SHA256, 6)

    run_status = run_root / "run-status.txt"
    require_hash(run_status, RUN_STATUS_SHA256)
    require(run_status.read_text().strip() == "FAIL", "source FAIL was not preserved")

    comparison_path = supplement_root / "comparison.json"
    completion_path = supplement_root / "completion-status.json"
    supplement_identity_path = supplement_root / "supplemental-identity.json"
    require_hash(comparison_path, COMPARISON_SHA256)
    require_hash(completion_path, COMPLETION_STATUS_SHA256)
    require_hash(supplement_identity_path, SUPPLEMENT_IDENTITY_SHA256)
    comparison = read_object(comparison_path)
    completion = read_object(completion_path)
    supplement_identity = read_object(supplement_identity_path)
    require(
        comparison.get("classification") == "PASS_REALISTIC_MTP_WIN",
        "bad comparison class",
    )
    require(
        comparison.get("evidence_passed") is True, "supplement evidence did not pass"
    )
    require(
        comparison.get("performance_passed") is True,
        "supplement performance did not pass",
    )
    require(
        comparison.get("realistic_policy_passed") is True,
        "realistic policy did not pass",
    )
    require(
        comparison.get("quality_reference") == "matched_fresh_control_v1",
        "bad quality reference",
    )
    require(
        comparison.get("legacy_oracle_identity_compatible") is False,
        "legacy oracle was treated as compatible",
    )
    require(
        completion.get("source_run_original_status_preserved") == "FAIL",
        "completion rewrote source status",
    )
    require(
        completion.get("source_run_unchanged") is True,
        "completion does not preserve source",
    )
    require(
        supplement_identity.get("source_run_original_status") == "FAIL",
        "identity rewrote source status",
    )
    require(
        supplement_identity.get("source_run_unchanged") is True,
        "identity does not preserve source",
    )

    files = {
        "scoredControl": run_root / "scored-control/scored.json",
        "forensicControl": run_root / "forensic-control/forensic.json",
        "scoredMtp3": run_root / "scored-mtp3/scored.json",
        "forensicMtp3": run_root / "forensic-mtp3/forensic.json",
    }
    expected_hashes = {
        "scoredControl": SCORED_CONTROL_SHA256,
        "forensicControl": FORENSIC_CONTROL_SHA256,
        "scoredMtp3": SCORED_MTP3_SHA256,
        "forensicMtp3": FORENSIC_MTP3_SHA256,
    }
    for name, path in files.items():
        require_hash(path, expected_hashes[name])

    gate_paths = {
        "controlCaptureGate": supplement_root / "control-capture-gate.json",
        "controlMetricsGate": supplement_root / "control-metrics-binding-gate.json",
        "mtp3CaptureGate": supplement_root / "mtp3-capture-gate.json",
        "mtp3MetricsGate": supplement_root / "mtp3-metrics-binding-gate.json",
    }
    gate_hashes = {
        "controlCaptureGate": CONTROL_CAPTURE_GATE_SHA256,
        "controlMetricsGate": CONTROL_METRICS_GATE_SHA256,
        "mtp3CaptureGate": MTP3_CAPTURE_GATE_SHA256,
        "mtp3MetricsGate": MTP3_METRICS_GATE_SHA256,
    }
    gates: dict[str, dict[str, Any]] = {}
    for name, path in gate_paths.items():
        require_hash(path, gate_hashes[name])
        gates[name] = read_object(path)
    require(
        gates["controlCaptureGate"].get("passed") is True, "control capture gate failed"
    )
    require(
        gates["controlCaptureGate"].get("mode") == "control",
        "control capture mode mismatch",
    )
    require(
        gates["controlMetricsGate"].get("passed") is True, "control metrics gate failed"
    )
    require(
        gates["controlMetricsGate"].get("mode") == "control",
        "control metrics mode mismatch",
    )
    require(
        gates["controlMetricsGate"].get("capture_sha256") == SCORED_CONTROL_SHA256,
        "control metrics/capture join mismatch",
    )
    require(gates["mtp3CaptureGate"].get("passed") is True, "MTP3 capture gate failed")
    require(
        gates["mtp3CaptureGate"].get("mode") == "mtp3", "MTP3 capture mode mismatch"
    )
    require(gates["mtp3MetricsGate"].get("passed") is True, "MTP3 metrics gate failed")
    require(
        gates["mtp3MetricsGate"].get("mode") == "mtp3", "MTP3 metrics mode mismatch"
    )
    require(
        gates["mtp3MetricsGate"].get("capture_sha256") == SCORED_MTP3_SHA256,
        "MTP3 metrics/capture join mismatch",
    )

    scored = read_object(files["scoredMtp3"])
    control = read_object(files["scoredControl"])
    rows = scored.get("rows")
    control_rows = control.get("rows")
    require(isinstance(rows, list) and len(rows) == 12, "candidate must have 12 rows")
    require(
        isinstance(control_rows, list) and len(control_rows) == 12,
        "control must have 12 rows",
    )
    require(
        [row.get("prompt_id") for row in rows] == list(PROMPT_IDS),
        "candidate prompt order mismatch",
    )
    require(
        [row.get("prompt_id") for row in control_rows] == list(PROMPT_IDS),
        "control prompt order mismatch",
    )
    require(
        all(
            row.get("token_ids") == other.get("token_ids")
            and row.get("content") == other.get("content")
            for row, other in zip(rows, control_rows)
        ),
        "candidate does not exactly match fresh control",
    )
    require(
        all(row.get("cached_tokens") == 0 for row in rows + control_rows),
        "cached_tokens must be zero",
    )
    completion_counts = [row.get("completion_tokens") for row in rows]
    natural_policy = completion_length_policy(completion_counts)
    require(
        completion_counts.count(512) == 11 and completion_counts.count(248) == 1,
        "unexpected output distribution",
    )
    customer_row = rows[PROMPT_IDS.index("customer-email")]
    require(customer_row.get("completion_tokens") == 248, "natural EOS row changed")
    require(
        customer_row.get("finish_reasons") == ["stop"],
        "248-token row was not an ordinary stop",
    )

    run_identity = scored.get("run_identity") or {}
    suite = run_identity.get("suite") or {}
    fresh = scored.get("fresh_response_validity") or {}
    gate = scored.get("realistic_final_gate") or {}
    require(run_identity.get("suite_sha256") == SUITE_SHA256, "suite SHA mismatch")
    require(
        suite.get("suite_id") == SUITE_ID and suite.get("version") == 1,
        "suite identity mismatch",
    )
    require(
        run_identity.get("generation_requests_per_prompt") == 1,
        "prompts were not once-only",
    )
    require(run_identity.get("replay_requests") == 0, "replay requests were present")
    require(run_identity.get("ignore_eos") is False, "ordinary EOS was disabled")
    require(run_identity.get("max_tokens") == 512, "request cap mismatch")
    require(
        run_identity.get("temperature") == 0 and run_identity.get("top_p") == 1,
        "request was not greedy",
    )
    require(
        fresh.get("valid") is True and fresh.get("cached_tokens_all_zero") is True,
        "fresh-response validity failed",
    )
    require(
        gate.get("passed") is True and gate.get("metric_tokens") == 100,
        "100-event gate failed",
    )

    identity = env_file(run_root / "run-identity.env")
    require(identity.get("model_repository") == HF_ID, "HF repository mismatch")
    require(identity.get("model_revision") == MODEL_REVISION, "HF revision mismatch")
    require(identity.get("model_size") == str(MODEL_SIZE), "model size mismatch")
    require(identity.get("model_sha256") == MODEL_SHA256, "model SHA mismatch")
    require(
        identity.get("llama_cpp_commit") == RUNTIME_COMMIT, "runtime commit mismatch"
    )
    require(
        identity.get("llama_server_sha256") == RUNTIME_SHA256, "runtime SHA mismatch"
    )
    require(
        identity.get("runtime_manifest_sha256") == RUNTIME_MANIFEST_SHA256,
        "runtime manifest mismatch",
    )

    server_identity_path = run_root / "scored-mtp3/server-identity.json"
    server_identity = read_object(server_identity_path)
    argv = server_identity.get("argv")
    require(
        isinstance(argv, list) and all(isinstance(value, str) for value in argv),
        "bad server argv",
    )
    require(server_identity.get("mode") == "mtp3", "server was not MTP3")
    require(
        server_identity.get("model_sha256") == MODEL_SHA256, "server model mismatch"
    )
    require(
        server_identity.get("runtime_sha256") == RUNTIME_SHA256,
        "server runtime mismatch",
    )
    required_pairs = {
        "-c": "32768",
        "-np": "1",
        "-b": "1024",
        "-ub": "1024",
        "-ctk": "f16",
        "-ctv": "f16",
        "-fa": "on",
        "--ctx-checkpoints": "0",
        "--cache-ram": "0",
        "--spec-type": "draft-mtp",
        "--spec-draft-n-max": "3",
        "--spec-draft-n-min": "0",
        "--spec-draft-p-split": "0.10",
        "--spec-draft-p-min": "0.00",
    }
    require(
        all(argv_values(argv, key) == [value] for key, value in required_pairs.items()),
        "server argument identity mismatch",
    )
    require(
        all(
            flag in argv
            for flag in (
                "--spec-draft-backend-sampling",
                "--no-context-shift",
                "--no-kv-unified",
                "--cont-batching",
            )
        ),
        "required server flags missing",
    )

    primary = (comparison.get("primary_metric") or {}).get("candidate") or {}
    require(
        math.isclose(
            float(primary.get("median")), PRIMARY_VALUE, rel_tol=0, abs_tol=1e-12
        ),
        "primary score mismatch",
    )
    require(primary.get("count") == 12, "primary score row count mismatch")
    require(
        (comparison.get("scope") or {}).get("target_verified") is True,
        "MTP was not target verified",
    )
    capture_summary = gates["mtp3CaptureGate"].get("summary") or {}
    require(
        math.isclose(
            float((capture_summary.get("d99_interval_tok_s") or {}).get("median")),
            PRIMARY_VALUE,
            rel_tol=0,
            abs_tol=1e-12,
        ),
        "capture and comparison disagree",
    )

    prompt_counts = [int(row["prompt_tokens"]) for row in rows]
    prompt_hashes = [str(row["prompt_sha256"]) for row in rows]
    output_hashes = [str(row["sha256"]) for row in rows]
    cached_counts = [int(row["cached_tokens"]) for row in rows]
    output_wall_values = [float(row["tok_s_wall_full"]) for row in rows]
    total_wall_values = [
        (int(row["prompt_tokens"]) + int(row["completion_tokens"]))
        / float(row["elapsed_s"])
        for row in rows
    ]
    ttft_values = [float(row["ttft_s"]) for row in rows]
    return {
        "comparison": comparison,
        "rows": rows,
        "promptCounts": prompt_counts,
        "completionCounts": completion_counts,
        "promptHashes": prompt_hashes,
        "outputHashes": output_hashes,
        "cachedCounts": cached_counts,
        "naturalPolicy": natural_policy,
        "medianOutputWallTokS": statistics.median(output_wall_values),
        "medianTotalWallTokS": statistics.median(total_wall_values),
        "medianTtftMs": statistics.median(ttft_values) * 1000.0,
        "serverIdentitySha256": sha256_file(server_identity_path),
        "paths": files,
        "gatePaths": gate_paths,
    }


def build_packet(
    run_root: Path, supplement_root: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source = validate_source(run_root, supplement_root)
    comparison = source["comparison"]
    primary = comparison["primary_metric"]
    acceptance = comparison["acceptance"]
    prompt_counts = source["promptCounts"]
    completion_counts = source["completionCounts"]
    label = (
        "qwen36-27b-mtp-q8_0-b70-llamacpp-vdr2-embedded-mtp3-realistic-36tok-20260810"
    )
    command = (
        "ONEAPI_DEVICE_SELECTOR=level_zero:* ZE_AFFINITY_MASK=0 "
        "ZES_ENABLE_SYSMAN=1 UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1 "
        "GGML_SYCL_ENABLE_VMM=1 GGML_SYCL_ENABLE_GRAPH=0 "
        "GGML_SYCL_GRAPH_CACHE_SIZE=0 GGML_SYCL_ENABLE_DNN=0 "
        "GGML_SYCL_ENABLE_OPT=1 GGML_SYCL_FA_ONEDNN=1 "
        "GGML_SYCL_FA_ONEDNN_MAX_KV=0 GGML_SYCL_ENABLE_MKL_FA=1 "
        "GGML_SYCL_ENABLE_FLASH_ATTN=1 llama-server "
        "-m Qwen3.6-27B-Q8_0.gguf "
        "-dev SYCL0 -ngl all -c 32768 -np 1 -b 1024 -ub 1024 "
        "-t 8 --threads-http 6 --poll 50 -lv 4 "
        "-ctk f16 -ctv f16 -fa on -fit on -fitt 1024 "
        "--spec-type draft-mtp --spec-draft-n-max 3 --spec-draft-n-min 0 "
        "--spec-draft-p-split 0.10 --spec-draft-p-min 0.00 "
        "--spec-draft-backend-sampling --spec-draft-device SYCL0 "
        "--spec-draft-ngl all --spec-draft-type-k f16 --spec-draft-type-v f16 "
        "--reasoning off --ctx-checkpoints 0 --cache-ram 0 "
        "--no-cache-idle-slots --no-context-shift --slots --metrics --jinja "
        "--no-kv-unified --cont-batching"
    )
    engine_flags: dict[str, Any] = {
        "apiMode": "completions",
        "attentionBackend": "llama.cpp SYCL/Level Zero flash attention",
        "apiAttentionBackend": "flash_attn",
        "kvCacheDtype": "f16/f16",
        "apiKvCacheDtype": "fp16",
        "flashAttn": True,
        "gpuLayers": -1,
        "commandSnippet": command,
        "concurrency": 1,
        "contextLength": 32768,
        "batch_size": 1024,
        "ubatch_size": 1024,
        "n_parallel": 1,
        "temperature": 0,
        "prefixCaching": False,
        "contextCheckpoints": 0,
        "responseReuse": False,
        "historyAccelerated": False,
        "freshResponseHeadlineValid": True,
        "headlineUse": "fresh-realistic-suite",
        "realisticSuiteGatePassed": True,
        "realisticSuiteCachedTokensAllZero": True,
        "realisticSuiteCachedTokens": source["cachedCounts"],
        "realisticSuiteId": SUITE_ID,
        "realisticSuiteVersion": 1,
        "realisticSuiteSha256": SUITE_SHA256,
        "realisticPromptTokenCounts": prompt_counts,
        "realisticOutputTokenCounts": completion_counts,
        "promptSha256": source["promptHashes"],
        "outputSha256": source["outputHashes"],
        "maxGeneratedTokens": 512,
        "naturalEosPolicy": source["naturalPolicy"],
        "allRowsFull512": False,
        "fullLengthLimitedRows": 11,
        "naturalEosRows": 1,
        "primaryMetricName": PRIMARY_METRIC,
        "primaryMetricAccounting": "inter-token-intervals",
        "metricWindowGeneratedTokens": 100,
        "metricWindowIntervals": 99,
        "tokenTimingSource": "llamacpp_oai_completion_verbose_token_ids",
        "tokSOutMedian": primary["candidate"]["median"],
        "tokSOutP10": primary["candidate"]["p10"],
        "tokSOutMean": primary["candidate"]["mean"],
        "tokSOutStdev": primary["candidate"]["stdev"],
        "tokSFullNaturalCompletionAfterTtftMedian": primary["client_full_candidate"][
            "median"
        ],
        "tokSFullIntervalNaturalCompletionMedian": primary["full_interval_candidate"][
            "median"
        ],
        "tokSNativeNaturalCompletionMedian": primary["native_candidate"]["median"],
        "tokSOutputWallMedian": source["medianOutputWallTokS"],
        "tokSTotalWallMedian": source["medianTotalWallTokS"],
        "ttftMsMedian": source["medianTtftMs"],
        "specDecoding": True,
        "mtpEnabled": True,
        "specMethod": "draft-mtp",
        "specNumTokens": 3,
        "specDraftNMin": 0,
        "specDraftPSplit": 0.10,
        "specDraftPMin": 0.0,
        "targetModelVerifiedAcceptedTokens": True,
        "specAcceptedTokens": acceptance["counters"]["accepted_tokens"],
        "specDraftTokens": acceptance["counters"]["draft_tokens"],
        "specVerifications": acceptance["counters"]["drafts"],
        "specAcceptanceRatio": acceptance["accepted_over_drafted"],
        "specAcceptedPerVerification": acceptance["accepted_per_verification"],
        "modelFile": MODEL_FILE,
        "modelFileBytes": MODEL_SIZE,
        "modelFileSha256": MODEL_SHA256,
        "llamaCppCommit": RUNTIME_COMMIT,
        "llamaServerSha256": RUNTIME_SHA256,
        "runtimeManifestSha256": RUNTIME_MANIFEST_SHA256,
        "q8ReorderVdrMmvq": 2,
        "qualityReference": "matched_fresh_control_v1",
        "candidateControlFullTokenContentExact": True,
        "sourceRunOriginalStatusPreserved": "FAIL",
        "sourceRunStatusSha256": RUN_STATUS_SHA256,
        "sourceRunArtifactManifestSha256": RUN_MANIFEST_SHA256,
        "supplementClassification": "PASS_REALISTIC_MTP_WIN",
        "supplementArtifactManifestSha256": SUPPLEMENT_MANIFEST_SHA256,
        "supplementComparisonSha256": COMPARISON_SHA256,
        "supplementIdentitySha256": SUPPLEMENT_IDENTITY_SHA256,
        "supplementCompletionStatusSha256": COMPLETION_STATUS_SHA256,
        "controlCaptureGateSha256": CONTROL_CAPTURE_GATE_SHA256,
        "controlMetricsBindingGateSha256": CONTROL_METRICS_GATE_SHA256,
        "mtp3CaptureGateSha256": MTP3_CAPTURE_GATE_SHA256,
        "mtp3MetricsBindingGateSha256": MTP3_METRICS_GATE_SHA256,
        "benchmarkJson": str(source["paths"]["scoredMtp3"]),
        "matchedControlBenchmarkJson": str(source["paths"]["scoredControl"]),
        "scoredMtp3Sha256": SCORED_MTP3_SHA256,
        "scoredControlSha256": SCORED_CONTROL_SHA256,
        "forensicMtp3Sha256": FORENSIC_MTP3_SHA256,
        "forensicControlSha256": FORENSIC_CONTROL_SHA256,
        "serverIdentitySha256": source["serverIdentitySha256"],
        "localmaxxingSubmissionAllowedUnderCurrentPolicy": True,
    }
    payload = {
        "hfId": HF_ID,
        "modelRevision": MODEL_REVISION,
        "engineName": "llama.cpp",
        "engineVersion": "10298 (15586e2d7) local Intel SYCL VDR2 embedded-MTP build",
        "backend": "xpu",
        "quantization": "Q8_0",
        "hardware": {
            "hwClass": "DISCRETE_GPU",
            "gpuName": "Intel Arc Pro B70",
            "gpuCount": 1,
            "vramGb": 32,
            "cpu": "AMD Ryzen Threadripper PRO 5955WX 16-Cores",
            "ramGb": 128,
            "os": "Ubuntu 24.04.4 LTS",
        },
        "contextLength": 32768,
        "batchSize": 1,
        "promptTokens": int(statistics.median(prompt_counts)),
        "outputTokens": int(statistics.median(completion_counts)),
        "tokSOut": PRIMARY_VALUE,
        "tokSTotal": source["medianTotalWallTokS"],
        "ttftMs": source["medianTtftMs"],
        "engineFlags": engine_flags,
        "notes": (
            "Qwen3.6 27B integrated publisher-MTP Q8_0 on one Intel Arc Pro B70. "
            "The fixed 12-prompt realistic suite used one cold request per prompt, "
            "cached_tokens=0 throughout, no prompt/KV/context/response/history reuse, "
            "and target-verified embedded MTP3. The primary score is the conventional "
            "median over 99 inter-token intervals between generated events 1 and 100. "
            "Candidate token IDs and content exactly match a fresh same-integrated-artifact "
            "non-spec control "
            "for all prompts. Eleven rows reached the 512-token request cap; customer-email "
            "ended normally at EOS after 248 tokens, after the required generated-token "
            "1/100 timing endpoints. The immutable measured source retains FAIL from an "
            "incompatible legacy "
            "4K/128 oracle; the separately sealed matched-control supplement is PASS."
        ),
    }
    queue = [{"label": label, "payload": payload}]
    audit = {
        "schema": "qwen36-embedded-mtp-localmaxxing-builder-audit-v1",
        "classification": "READY_FOR_AUTHENTICATED_DRY_RUN_NO_POST",
        "sourceRunOriginalStatusPreserved": "FAIL",
        "supplementClassificationPreserved": "PASS_REALISTIC_MTP_WIN",
        "derivedSubmissionPolicy": source["naturalPolicy"],
        "identity": {
            "hfId": HF_ID,
            "revision": MODEL_REVISION,
            "quantization": "Q8_0",
            "modelSha256": MODEL_SHA256,
            "runtimeCommit": RUNTIME_COMMIT,
            "runtimeSha256": RUNTIME_SHA256,
            "suiteSha256": SUITE_SHA256,
        },
        "sealedJoins": {
            "sourceRunManifestSha256": RUN_MANIFEST_SHA256,
            "sourceRunManifestEntries": 132,
            "supplementManifestSha256": SUPPLEMENT_MANIFEST_SHA256,
            "supplementManifestEntries": 6,
            "comparisonSha256": COMPARISON_SHA256,
            "completionStatusSha256": COMPLETION_STATUS_SHA256,
            "supplementIdentitySha256": SUPPLEMENT_IDENTITY_SHA256,
            "scoredControlSha256": SCORED_CONTROL_SHA256,
            "forensicControlSha256": FORENSIC_CONTROL_SHA256,
            "scoredMtp3Sha256": SCORED_MTP3_SHA256,
            "forensicMtp3Sha256": FORENSIC_MTP3_SHA256,
            "controlCaptureGateSha256": CONTROL_CAPTURE_GATE_SHA256,
            "controlMetricsBindingGateSha256": CONTROL_METRICS_GATE_SHA256,
            "mtp3CaptureGateSha256": MTP3_CAPTURE_GATE_SHA256,
            "mtp3MetricsBindingGateSha256": MTP3_METRICS_GATE_SHA256,
            "serverIdentitySha256": source["serverIdentitySha256"],
        },
        "primaryMetric": {"name": PRIMARY_METRIC, "value": PRIMARY_VALUE},
        "secondaryMetrics": {
            "tokSTotalDefinition": "median((prompt_tokens + completion_tokens) / request_elapsed_s)",
            "tokSTotal": source["medianTotalWallTokS"],
            "outputOnlyWallTokS": source["medianOutputWallTokS"],
            "ttftMs": source["medianTtftMs"],
        },
        "completionLengthDistribution": {"512": 11, "248": 1},
        "finalPostPerformed": False,
    }
    return queue, audit


def projected_api_request(queue: list[dict[str, Any]]) -> dict[str, Any]:
    """Use the production helper to render the exact no-secret POST body."""
    helper_path = REPO / "scripts/submit_localmaxxing_results.py"
    spec = importlib.util.spec_from_file_location("localmaxxing_submit", helper_path)
    require(
        spec is not None and spec.loader is not None, "cannot load submission helper"
    )
    helper = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(helper)
    payload = dict(queue[0]["payload"])
    payload["engineFlags"] = helper.api_engine_flags(payload["engineFlags"])
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--supplement-root", type=Path, default=DEFAULT_SUPPLEMENT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--audit-out", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--api-request-out", type=Path, default=DEFAULT_API_REQUEST)
    args = parser.parse_args()
    queue, audit = build_packet(args.run_root, args.supplement_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(queue, indent=2, sort_keys=True) + "\n")
    request = projected_api_request(queue)
    args.api_request_out.write_text(
        json.dumps(request, indent=2, sort_keys=True) + "\n"
    )
    audit["queuePath"] = str(args.out)
    audit["queueSha256"] = sha256_file(args.out)
    audit["apiRequestPath"] = str(args.api_request_out)
    audit["apiRequestSha256"] = sha256_file(args.api_request_out)
    audit["builderSha256"] = sha256_file(Path(__file__).resolve())
    args.audit_out.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    print(args.out)
    print(args.api_request_out)
    print(args.audit_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from receipt_qualification import require_qualifying
from packet49_submission import is_packet49, scope_problems as packet49_scope_problems


API_URL = "https://www.localmaxxing.com/api/speed-tests"
API_DRY_RUN_URL = f"{API_URL}/dry-run"
DEFAULT_KEY_PATH = Path.home() / ".config" / "localmaxxing" / "api_key"
REPO_ROOT = Path(__file__).resolve().parents[4]
PRIMARY_METRIC = (
    "median_of_prompt_class_medians_tok_s_1_100_intervals_after_ttft"
)
API_KV_CACHE_DTYPES = {"q8_0", "q4_0", "fp8", "fp16", "auto"}
API_ATTENTION_BACKENDS = {"flash_attn", "xformers", "sdpa", "triton"}
API_STRING_LIMITS = {
    "hfId": 256,
    "modelRevision": 128,
    "engineName": 64,
    "engineVersion": 512,
    "quantization": 64,
    "backend": 64,
    "notes": 2000,
}

# Owner decisions, 2026-10-15: only these pinned run-1 results use the October 13 scope.
# This is an eligibility exception, never a pass of the strict 512-cap gate.
OWNER_128_RULE = "packet45.speed3.owner-authorized-128-token-scope.2026-10-15"
OWNER_128_AUTHORIZATION = {
    "rule": OWNER_128_RULE,
    "date": "2026-10-15",
    "authorization_text": "authorized: submit under the same 128-token scope as the October 13 record.",
    "reference_submission": "cmv6pugme0020oa01fjrho6nx",
    "requested_max_new": 128,
    "scope": "same fixed realistic 12-prompt suite; cold; cached_tokens=0; 128 generated tokens per prompt; primary metric over 99 intervals between events 1 and 100",
}
OWNER_128_RAW_GATE = {
    "passed": False,
    "reason": "measurement preparation only; cap below fixed 512 and no promotion attestation; repeats/partial suites never qualify",
}


# SPEED6 PREPARE directive extends the same scope, not the strict 512-cap gate.
# No wildcard revisions, headline selection, or authorization-free pass marker.
OWNER_128_RESULTS = {
    "75d2c459d": {
        "label": "qwen38-flash-next-unsloth-iq3xxs-ownrt-tp2-mtp1-c4096-s24dr0-realistic-20261015",
        "engine_version": "own-xpu-runtime packet45-merged3 SPEED3 75d2c459d; device binary sha256 724e4dee068d38c561a97e0a2814c470b7f07cc9e5ec24f0297ebd904aed8fc8",
        "optimization_identity": "packet45-merged3-SPEED3-tp2-c4096-target24-24-draft-rank0-write-set-snapshot-K2-selected-kernels-native-controller-single-pass-draft-profiling",
        "target_split": [24, 24], "draft_rank": 0,
        "seal": "8460585fe53879223066a5d54799c9f105c73002adfc09fc9a743ceaee7e3fa8",
        "headline": 38.15715689731613,
    },
    "34c62b433": {
        "label": "qwen38-flash-next-unsloth-iq3xxs-ownrt-tp2-mtp1-c4096-s23dr1-realistic-20261015",
        "engine_version": "own-xpu-runtime packet45-merged3 SPEED6 34c62b433; device binary sha256 a68963d2e207ee6ad1aee0d0311bc319b2b2368f02132f48d67410951f12182b",
        "optimization_identity": "packet45-merged3-SPEED6-tp2-c4096-target23-25-draft-rank1-right-sized-scratch-prelaunch-arena-admission-write-set-snapshot-K2-selected-kernels-native-controller-single-pass-draft-profiling",
        "target_split": [23, 25], "draft_rank": 1,
        "seal": "9b6fa7f397151c380a25f79dc3cf08abca1c70853300d7159febbf9456b35fbf",
        "headline": 39.42200890284251,
    },
}


def owner_128_scope_problems(item: dict) -> list[str]:
    """Fail closed outside the exactly pinned owner-authorized run-1 headlines."""
    if is_packet49(item):
        return packet49_scope_problems(item, REPO_ROOT)
    payload = item.get("payload") or {}
    engine = payload.get("engineFlags") or {}
    problem = "invalid owner-authorized 128-token scope exception"
    if engine.get("realisticSuiteScopeException") != OWNER_128_AUTHORIZATION:
        return [problem + ": missing or different owner authorization"]
    identity = engine.get("promotionIdentity") or {}
    selected = OWNER_128_RESULTS.get(identity.get("runtime_revision"))
    if selected is None:
        return [problem + ": runtime is not owner-authorized"]
    expected = {
        "realisticSuiteGatePassed": False,
        "strict512TokenFinalGatePassed": False,
        "rawRealisticFinalGate": OWNER_128_RAW_GATE,
        "requestedMaxNew": 128,
        "realisticOutputTokenCounts": [128] * 12,
        "targetSplit": selected["target_split"], "draftRank": selected["draft_rank"], "deviceCards": [0, 1],
        "realisticSuiteId": "rapid-model-snapshots-b70-realistic-v1",
        "prefixCaching": False, "responseReuse": False, "contextCheckpoints": 0,
        "historyAccelerated": False, "targetModelVerifiedAcceptedTokens": True,
        "buildReceiptSha256": selected["seal"],
    }
    if any(engine.get(k) != v for k, v in expected.items()) or (
        item.get("label") != selected["label"]
        or payload.get("engineVersion") != selected["engine_version"]
        or identity.get("optimization_identity") != selected["optimization_identity"]
        or engine.get("freshRealisticSuiteGatePassed") is True
        or identity.get("model_revision") != "766911a6b7369840a91dbcd95f9f997acaab6cd6"
        or identity.get("suite_sha256") != "0ad543d1c1f379a0b6cee88e06236e495c45eee7ba12cfcef062b6e03303e812"
        or payload.get("tokSOut") != selected["headline"]
        or payload.get("outputTokens") != 128
        or payload.get("modelRevision") != identity.get("model_revision")
        or payload.get("hfId") != "unsloth/Qwen3.8-Flash-Next-GGUF"
        or payload.get("quantization") != "UD-IQ3_XXS (GGUF)"
        or payload.get("contextLength") != 4096
    ):
        return [problem + ": result identity, raw gate or measurement scope differs"]
    try:
        def bound_json(relative, digest):
            path = (REPO_ROOT / relative).resolve()
            if not path.is_relative_to(REPO_ROOT):
                raise ValueError("evidence outside repository")
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError("evidence digest mismatch")
            return json.loads(raw)
        att = bound_json(engine["promotionAttestation"], engine["promotionAttestationSha256"])
        perf = att["performance_evidence"]
        if perf["path"] != engine["benchmarkJson"]:
            raise ValueError("performance evidence path mismatch")
        result = bound_json(perf["path"], perf["sha256"])
        for evidence in (att, result):
            require_qualifying(evidence)
            scope = evidence["submission_scope"]
            if (scope["owner_authorization"] != OWNER_128_AUTHORIZATION
                or scope["raw_realistic_final_gate"] != OWNER_128_RAW_GATE
                or scope["strict_512_gate_passed"] is not False
                or scope["owner_exception_authorized"] is not True):
                raise ValueError("evidence authorization/raw gate mismatch")
        from promotion_evidence import validate_packet45_device_evidence
        validate_packet45_device_evidence(result, att["quality_evidence"],
                                         REPO_ROOT / engine["promotionAttestation"])
        if (result["artifacts_sha256"]["device/own-rt-iq3"]
                != selected["engine_version"].rsplit(" ", 1)[-1]
            or att["seal6_amendment"]["build_receipt_sha256"] != selected["seal"]):
            raise ValueError("device artifact or seal identity mismatch")
        for item_evidence in att["quality_evidence"]:
            window = bound_json(item_evidence["path"], item_evidence["sha256"])
            if (window["build_receipt_sha256"] != selected["seal"]
                or window["context"] != 4096 or window["card"] != 0
                or window["draft_rank"] != selected["draft_rank"]
                or window["target_split"] != selected["target_split"][0]
                or window["boot_id"] != engine.get("bootId")
                or window["dispatch_sha256"] != engine.get("dispatchSha256")):
                raise ValueError("device window identity mismatch")
        rows = result["rows"]
        if (result["promotionIdentity"] != identity or att["identity"] != identity
            or result["primary_metric"]["value_tok_s"] != payload["tokSOut"]
            or len(rows) != 12 or len({r["prompt_id"] for r in rows}) != 12
            or any(r["output_tokens"] != 128 or r["requested_max_new"] != 128
                   or r["cached_tokens"] != 0 for r in rows)
            or [r["prompt_sha256"] for r in rows] != engine["promptSha256"]
            or [r["output_sha256"] for r in rows] != engine["outputSha256"]):
            raise ValueError("performance rows/identity mismatch")
    except (KeyError, TypeError, ValueError, OSError) as error:
        return [problem + ": " + str(error)]
    return []


def preflight_payload(item: dict, *, allow_non_headline: bool = False) -> list[str]:
    try:
        require_qualifying(item)
    except ValueError as error:
        return [str(error)]
    label = str(item.get("label", ""))
    payload = item.get("payload") or {}
    engine = payload.get("engineFlags") or {}
    notes = str(payload.get("notes", ""))
    problems: list[str] = []

    history_markers = [
        bool(engine.get("historyAccelerated")),
        engine.get("freshResponseHeadlineValid") is False,
        str(engine.get("headlineUse", "")).lower()
        in {"diagnostic-only", "non-headline"},
        "history-accelerated" in label.lower(),
        "history-accelerated" in notes.lower(),
        "non-headline" in notes.lower(),
    ]
    ngram_markers = [
        "ngram" in label.lower(),
        "ngram" in notes.lower(),
        any(str(key).lower().startswith("ngram") for key in engine),
    ]
    if any(history_markers):
        problems.append("payload is labeled history-accelerated or non-headline")
    if any(ngram_markers) and not engine.get("freshResponseNgramValidated"):
        problems.append(
            "payload appears to be n-gram/history based without fresh-response validation"
        )

    if label.endswith("-fresh") or "-fresh-" in label:
        first_tok_s = engine.get("firstRequestTokSOut")
        tok_s = payload.get("tokSOut")
        cached = engine.get("firstRequestCachedTokens")
        if first_tok_s is not None and tok_s is not None:
            try:
                if abs(float(first_tok_s) - float(tok_s)) > 1e-6:
                    problems.append(
                        "fresh label has tokSOut different from firstRequestTokSOut"
                    )
            except (TypeError, ValueError):
                problems.append(
                    "fresh label has non-numeric tokSOut/firstRequestTokSOut"
                )
        if cached not in (None, 0):
            problems.append("fresh label has nonzero firstRequestCachedTokens")

    gate_passed = (
        engine.get("realisticSuiteGatePassed") is True
        or engine.get("freshRealisticSuiteGatePassed") is True
    )
    if (is_packet49(item) or "realisticSuiteScopeException" in engine
        or (engine.get("promotionIdentity") or {}).get("runtime_revision") in OWNER_128_RESULTS
        or label in {r["label"] for r in OWNER_128_RESULTS.values()}):
        exception_problems = owner_128_scope_problems(item)
        problems.extend(exception_problems)
        gate_passed = not exception_problems
    metric_name = str(engine.get("primaryMetricName", ""))
    if not gate_passed:
        problems.append("missing realistic-suite final gate pass marker")
    if metric_name != PRIMARY_METRIC:
        problems.append(f"primaryMetricName must be {PRIMARY_METRIC}")
    if engine.get("primaryMetricAccounting") != "inter-token-intervals":
        problems.append("primaryMetricAccounting must be inter-token-intervals")
    if engine.get("primaryMetricAggregation") != "median-of-prompt-class-medians":
        problems.append(
            "primaryMetricAggregation must be median-of-prompt-class-medians"
        )
    if engine.get("metricWindowGeneratedTokens") != 100:
        problems.append("metricWindowGeneratedTokens must be 100")
    if engine.get("metricWindowIntervals") != 99:
        problems.append("metricWindowIntervals must be 99")
    cached_all_zero = engine.get("realisticSuiteCachedTokensAllZero")
    if cached_all_zero is not True:
        problems.append("realistic suite must report cached_tokens=0 for every request")
    suite_id = engine.get("realisticSuiteId")
    if not isinstance(suite_id, str) or not suite_id:
        problems.append("missing realisticSuiteId")

    attestation = engine.get("promotionAttestation")
    attestation_sha256 = engine.get("promotionAttestationSha256")
    if attestation is not None or attestation_sha256 is not None:
        if not isinstance(attestation, str) or not attestation:
            problems.append("promotionAttestation must name a repository file")
        elif not isinstance(attestation_sha256, str) or len(attestation_sha256) != 64:
            problems.append("promotionAttestationSha256 must be a SHA-256 digest")
        else:
            attestation_path = (REPO_ROOT / attestation).resolve()
            if not attestation_path.is_relative_to(REPO_ROOT):
                problems.append("promotionAttestation must stay inside the repository")
            elif not attestation_path.is_file():
                problems.append("promotionAttestation file does not exist")
            else:
                actual_sha256 = hashlib.sha256(attestation_path.read_bytes()).hexdigest()
                if actual_sha256 != attestation_sha256:
                    problems.append(
                        "promotionAttestationSha256 does not match the repository file"
                    )

    for key, max_length in API_STRING_LIMITS.items():
        value = payload.get(key)
        if value is not None and len(str(value)) > max_length:
            problems.append(
                f"{key} exceeds the LocalMaxxing API limit of {max_length} characters"
            )

    try:
        projected_engine = api_engine_flags(engine)
    except (TypeError, ValueError) as exc:
        problems.append(f"engineFlags API projection failed: {exc}")
    else:
        if projected_engine.get("kvCacheDtype") not in API_KV_CACHE_DTYPES:
            problems.append(
                "projected kvCacheDtype is not accepted by the LocalMaxxing API"
            )
        if projected_engine.get("attentionBackend") not in API_ATTENTION_BACKENDS:
            problems.append(
                "projected attentionBackend is not accepted by the LocalMaxxing API"
            )

    for top_level_key, counts_key in (
        ("promptTokens", "realisticPromptTokenCounts"),
        ("outputTokens", "realisticOutputTokenCounts"),
    ):
        counts = engine.get(counts_key)
        if isinstance(counts, list) and counts:
            try:
                expected_median = int(statistics.median(int(value) for value in counts))
                actual_value = int(payload.get(top_level_key))
            except (TypeError, ValueError):
                problems.append(
                    f"{top_level_key} or {counts_key} contains a non-integer value"
                )
            else:
                if actual_value != expected_median:
                    problems.append(
                        f"{top_level_key} must equal the integer suite median "
                        f"{expected_median}"
                    )

    return [] if allow_non_headline else problems


def api_engine_flags(engine_flags: dict) -> dict:
    command = engine_flags.get("commandSnippet")
    if not command:
        model = engine_flags.get("modelPath") or "<model>"
        ctx = (
            engine_flags.get("ctx_size") or engine_flags.get("contextLength") or "<ctx>"
        )
        batch = engine_flags.get("batch_size") or "<batch>"
        ubatch = engine_flags.get("ubatch_size") or "<ubatch>"
        flash = engine_flags.get("flash_attn")
        command = (
            f"llama-server -m {model} -c {ctx} -ngl 99 -b {batch} "
            f"-ub {ubatch} -fa {flash}"
        )

    cache_k = engine_flags.get("cache_type_k")
    cache_v = engine_flags.get("cache_type_v")
    kv_cache = None
    if cache_k or cache_v:
        kv_cache = f"K={cache_k or '?'} V={cache_v or '?'}"
    actual_kv_cache_dtype = kv_cache or str(engine_flags.get("kvCacheDtype") or "f16")
    api_kv_cache_dtype = str(
        engine_flags.get("apiKvCacheDtype") or actual_kv_cache_dtype
    )

    extra = {
        "benchmarkJson": engine_flags.get("benchmarkJson"),
        "realisticSuiteGatePassed": engine_flags.get("realisticSuiteGatePassed"),
        "realisticSuiteCachedTokensAllZero": engine_flags.get(
            "realisticSuiteCachedTokensAllZero"
        ),
        "primaryMetricName": engine_flags.get("primaryMetricName"),
        "primaryMetricAccounting": engine_flags.get("primaryMetricAccounting"),
        "primaryMetricAggregation": engine_flags.get("primaryMetricAggregation"),
        "promotionAttestation": engine_flags.get("promotionAttestation"),
        "promotionAttestationSha256": engine_flags.get(
            "promotionAttestationSha256"
        ),
        "promotionIdentity": engine_flags.get("promotionIdentity"),
        "metricWindowGeneratedTokens": engine_flags.get("metricWindowGeneratedTokens"),
        "metricWindowIntervals": engine_flags.get("metricWindowIntervals"),
        "tokenTimingSource": engine_flags.get("tokenTimingSource"),
        "githubResultPacket": engine_flags.get("githubResultPacket"),
        "specMethod": engine_flags.get("specMethod"),
        "specNumTokens": engine_flags.get("specNumTokens"),
        "mtpEnabled": engine_flags.get("mtpEnabled"),
        "targetModelVerifiedAcceptedTokens": engine_flags.get(
            "targetModelVerifiedAcceptedTokens"
        ),
        "kvCacheDtypeActual": actual_kv_cache_dtype,
        "attentionBackendActual": engine_flags.get("attentionBackend"),
        "requestPolicy": "cache_prompt=false; no prefix/KV/history/response reuse",
    }
    if isinstance(engine_flags.get("realisticSuiteScopeException"), dict):
        # This early sorted entry survives the API's 1000-character cap.
        extra["authorizedScopeException"] = {
            "rule": engine_flags["realisticSuiteScopeException"].get("rule"),
            "date": engine_flags["realisticSuiteScopeException"].get("date"),
            "requestedCap": engine_flags.get("requestedMaxNew"),
            "strict512GatePassed": False,
        }
    extra_text = json.dumps(
        {k: v for k, v in extra.items() if v is not None},
        sort_keys=True,
    )
    if len(extra_text) > 1000:
        extra_text = extra_text[:997] + "..."

    actual_attention_backend = engine_flags.get("attentionBackend")
    attention_backend = engine_flags.get("apiAttentionBackend")
    if not attention_backend:
        attention_backend = (
            actual_attention_backend or "llama.cpp SYCL/Level Zero flash attention"
        )

    flash_attn_value = engine_flags.get("flashAttn")
    if flash_attn_value is None:
        flash_attn_value = str(engine_flags.get("flash_attn", "")).lower() == "on"

    concurrency = engine_flags.get("n_parallel") or engine_flags.get("concurrency") or 1
    gpu_layers = engine_flags.get("gpuLayers")
    if gpu_layers is None:
        gpu_layers = 99

    api_flags: dict[str, object] = {
        "commandSnippet": str(command),
        "kvCacheDtype": api_kv_cache_dtype,
        "flashAttn": bool(flash_attn_value),
        "attentionBackend": str(attention_backend),
        "concurrency": int(concurrency),
        "prefixCaching": bool(engine_flags.get("prefixCaching", False)),
        "specDecoding": bool(
            engine_flags.get("specDecoding", False)
            or engine_flags.get("mtpEnabled", False)
        ),
        "temperature": float(engine_flags.get("temperature") or 0),
        "topP": 1.0,
        "extraFlags": extra_text,
    }
    if "mtpEnabled" in engine_flags:
        api_flags["mtpEnabled"] = bool(engine_flags["mtpEnabled"])
    if gpu_layers is not None and int(gpu_layers) >= -1:
        api_flags["gpuLayers"] = int(gpu_layers)

    optional_integer_flags = {
        "tensorParallel": engine_flags.get("tensorParallel")
        or engine_flags.get("tensorParallelSize"),
        "pipelineParallel": engine_flags.get("pipelineParallel")
        or engine_flags.get("pipelineParallelSize"),
        "maxRunningSeqs": engine_flags.get("maxRunningSeqs")
        or engine_flags.get("maxNumSeqs"),
        "specNumTokens": engine_flags.get("specNumTokens"),
        "specDraftTp": engine_flags.get("specDraftTp"),
    }
    for key, value in optional_integer_flags.items():
        if value is not None:
            api_flags[key] = int(value)

    optional_float_flags = {
        "gpuMemUtil": engine_flags.get("gpuMemUtil")
        or engine_flags.get("gpuMemoryUtilization"),
    }
    for key, value in optional_float_flags.items():
        if value is not None:
            api_flags[key] = float(value)

    optional_string_flags = {
        "specMethod": engine_flags.get("specMethod"),
        "specModel": engine_flags.get("specModel") or engine_flags.get("draftModel"),
    }
    for key, value in optional_string_flags.items():
        if value:
            api_flags[key] = str(value)

    return api_flags


def post_payload(
    key: str,
    payload: dict,
    *,
    api_url: str = API_URL,
) -> tuple[int, str, int | None]:
    post_payload = dict(payload)
    engine_flags = post_payload.get("engineFlags")
    if isinstance(engine_flags, dict):
        post_payload["engineFlags"] = api_engine_flags(engine_flags)
    body = json.dumps(post_payload).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "curl/8.5.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.status, response.read().decode("utf-8"), None
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        retry_after_ms = None
        try:
            parsed = json.loads(text)
            retry_after_ms = parsed.get("retryAfterMs")
        except Exception:
            pass
        return exc.code, text, retry_after_ms


def parse_success_response(text: str, *, server_dry_run: bool = False) -> dict:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("success response was not JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("success response was not a JSON object")
    if server_dry_run:
        if parsed.get("valid") is not True:
            raise ValueError("server dry-run response did not report valid=true")
    else:
        if not isinstance(parsed.get("id"), str) or not parsed["id"]:
            raise ValueError("submission response did not include a nonempty id")
        if not isinstance(parsed.get("status"), str) or not parsed["status"]:
            raise ValueError("submission response did not include a nonempty status")
    return parsed


def print_success_response(text: str, *, server_dry_run: bool = False) -> None:
    parsed = parse_success_response(text, server_dry_run=server_dry_run)
    if server_dry_run:
        print(json.dumps({"valid": True}))
    else:
        print(json.dumps({"id": parsed["id"], "status": parsed["status"]}))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--payloads",
        default="/home/steve/localmaxxing_payloads.json",
        help="JSON payload queue",
    )
    parser.add_argument("--label", action="append", help="Submit only this label")
    parser.add_argument("--limit", type=int, help="Submit at most N payloads")
    parser.add_argument("--sleep-on-429", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--server-dry-run",
        action="store_true",
        help=(
            "Validate projected payloads against the authenticated "
            "LocalMaxxing dry-run endpoint without writing a result"
        ),
    )
    parser.add_argument(
        "--allow-non-headline",
        action="store_true",
        help=(
            "Inspect diagnostic/non-headline payloads such as warmed/history "
            "n-gram artifacts. This is restricted to --dry-run; real "
            "submissions fail closed."
        ),
    )
    args = parser.parse_args()
    if args.dry_run and args.server_dry_run:
        parser.error("--dry-run and --server-dry-run are mutually exclusive")

    queue = json.loads(Path(args.payloads).read_text())
    if args.label:
        labels = set(args.label)
        queue = [item for item in queue if item["label"] in labels]
        if not queue:
            print(
                f"no payloads matched --label filter(s): {', '.join(sorted(labels))}",
                file=sys.stderr,
            )
            return 2
    if args.limit is not None:
        queue = queue[: args.limit]

    blocked = []
    for item in queue:
        problems = preflight_payload(item, allow_non_headline=args.allow_non_headline)
        if problems:
            blocked.append((item.get("label", "<unlabeled>"), problems))
    if blocked:
        for label, problems in blocked:
            print(f"blocked {label}:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
        print(
            "one or more payloads are not submission-safe; fix the listed "
            "identity, accounting, or fresh-response problems before posting",
            file=sys.stderr,
        )
        return 2

    if args.allow_non_headline and not args.dry_run:
        print(
            "--allow-non-headline is restricted to --dry-run inspection; "
            "LocalMaxxing submissions must pass the realistic fresh-response gate",
            file=sys.stderr,
        )
        return 2

    if args.dry_run:
        print(json.dumps(queue, indent=2))
        return 0

    key = os.environ.get("LMX_API_KEY")
    if not key and DEFAULT_KEY_PATH.exists():
        key = DEFAULT_KEY_PATH.read_text().strip()
    if not key:
        print(
            f"LMX_API_KEY is required, or store it in {DEFAULT_KEY_PATH}",
            file=sys.stderr,
        )
        return 2

    for index, item in enumerate(queue, start=1):
        label = item["label"]
        api_url = API_DRY_RUN_URL if args.server_dry_run else API_URL
        status, text, retry_after_ms = post_payload(
            key,
            item["payload"],
            api_url=api_url,
        )
        print(f"{index}/{len(queue)} {label}: HTTP {status}")
        expected_status = 200 if args.server_dry_run else 201
        if status == expected_status:
            try:
                print_success_response(text, server_dry_run=args.server_dry_run)
            except ValueError as exc:
                print(f"invalid success response: {exc}", file=sys.stderr)
                print(text[:500], file=sys.stderr)
                return 1
            continue

        print(text[:1000], file=sys.stderr)
        if (
            not args.server_dry_run
            and status == 429
            and args.sleep_on_429
            and retry_after_ms
        ):
            sleep_s = max(1, int(retry_after_ms / 1000) + 2)
            print(f"rate limited; sleeping {sleep_s}s", file=sys.stderr)
            time.sleep(sleep_s)
            status, text, _ = post_payload(key, item["payload"])
            print(f"{index}/{len(queue)} {label} retry: HTTP {status}")
            if status != 201:
                print(text[:1000], file=sys.stderr)
                return 1
            try:
                print_success_response(text)
            except ValueError as exc:
                print(f"invalid success response: {exc}", file=sys.stderr)
                print(text[:500], file=sys.stderr)
                return 1
        else:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

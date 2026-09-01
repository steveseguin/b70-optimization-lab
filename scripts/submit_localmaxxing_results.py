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


API_URL = "https://www.localmaxxing.com/api/speed-tests"
API_DRY_RUN_URL = f"{API_URL}/dry-run"
DEFAULT_KEY_PATH = Path.home() / ".config" / "localmaxxing" / "api_key"
REPO_ROOT = Path(__file__).resolve().parents[1]
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


def preflight_payload(item: dict, *, allow_non_headline: bool = False) -> list[str]:
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

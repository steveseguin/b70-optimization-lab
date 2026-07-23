#!/usr/bin/env python3
import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


API_URL = "https://localmaxxing.com/api/benchmarks"
DEFAULT_KEY_PATH = Path.home() / ".config" / "localmaxxing" / "api_key"
API_KV_CACHE_DTYPES = {"q8_0", "q4_0", "fp8", "fp16", "auto"}
API_ATTENTION_BACKENDS = {"flash_attn", "xformers", "sdpa", "triton"}


def preflight_payload(item: dict, *, allow_non_headline: bool = False) -> list[str]:
    label = str(item.get("label", ""))
    payload = item.get("payload") or {}
    engine = payload.get("engineFlags") or {}
    notes = str(payload.get("notes", ""))
    problems: list[str] = []

    history_markers = [
        bool(engine.get("historyAccelerated")),
        engine.get("freshResponseHeadlineValid") is False,
        str(engine.get("headlineUse", "")).lower() in {"diagnostic-only", "non-headline"},
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
        problems.append("payload appears to be n-gram/history based without fresh-response validation")

    if label.endswith("-fresh") or "-fresh-" in label:
        first_tok_s = engine.get("firstRequestTokSOut")
        tok_s = payload.get("tokSOut")
        cached = engine.get("firstRequestCachedTokens")
        if first_tok_s is not None and tok_s is not None:
            try:
                if abs(float(first_tok_s) - float(tok_s)) > 1e-6:
                    problems.append("fresh label has tokSOut different from firstRequestTokSOut")
            except (TypeError, ValueError):
                problems.append("fresh label has non-numeric tokSOut/firstRequestTokSOut")
        if cached not in (None, 0):
            problems.append("fresh label has nonzero firstRequestCachedTokens")

    gate_passed = (
        engine.get("realisticSuiteGatePassed") is True
        or engine.get("freshRealisticSuiteGatePassed") is True
    )
    metric_name = str(engine.get("primaryMetricName", ""))
    if not gate_passed:
        problems.append("missing realistic-suite final gate pass marker")
    if metric_name != "median_tok_s_1_100_after_ttft":
        problems.append("primaryMetricName must be median_tok_s_1_100_after_ttft")
    cached_all_zero = engine.get("realisticSuiteCachedTokensAllZero")
    if cached_all_zero is not True:
        problems.append("realistic suite must report cached_tokens=0 for every request")
    suite_id = engine.get("realisticSuiteId")
    if not isinstance(suite_id, str) or not suite_id:
        problems.append("missing realisticSuiteId")

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
        ctx = engine_flags.get("ctx_size") or engine_flags.get("contextLength") or "<ctx>"
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
    actual_kv_cache_dtype = kv_cache or str(
        engine_flags.get("kvCacheDtype") or "f16"
    )
    api_kv_cache_dtype = str(
        engine_flags.get("apiKvCacheDtype") or actual_kv_cache_dtype
    )

    extra = {
        "benchmarkJson": engine_flags.get("benchmarkJson"),
        "realisticSuiteGatePassed": engine_flags.get("realisticSuiteGatePassed"),
        "realisticSuiteCachedTokensAllZero": engine_flags.get("realisticSuiteCachedTokensAllZero"),
        "primaryMetricName": engine_flags.get("primaryMetricName"),
        "tokenTimingSource": engine_flags.get("tokenTimingSource"),
        "githubResultPacket": engine_flags.get("githubResultPacket"),
        "specMethod": engine_flags.get("specMethod"),
        "specNumTokens": engine_flags.get("specNumTokens"),
        "targetModelVerifiedAcceptedTokens": engine_flags.get("targetModelVerifiedAcceptedTokens"),
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
            actual_attention_backend
            or "llama.cpp SYCL/Level Zero flash attention"
        )

    flash_attn_value = engine_flags.get("flashAttn")
    if flash_attn_value is None:
        flash_attn_value = str(engine_flags.get("flash_attn", "")).lower() == "on"

    concurrency = (
        engine_flags.get("n_parallel")
        or engine_flags.get("concurrency")
        or 1
    )
    gpu_layers = engine_flags.get("gpuLayers")
    if gpu_layers is None:
        gpu_layers = 99

    api_flags = {
        "commandSnippet": str(command),
        "gpuLayers": int(gpu_layers),
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
    return api_flags


def post_payload(key: str, payload: dict) -> tuple[int, str, int | None]:
    post_payload = dict(payload)
    engine_flags = post_payload.get("engineFlags")
    if isinstance(engine_flags, dict):
        post_payload["engineFlags"] = api_engine_flags(engine_flags)
    body = json.dumps(post_payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
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


def print_success_response(text: str) -> None:
    try:
        parsed = json.loads(text)
        print(json.dumps({"id": parsed.get("id"), "status": parsed.get("status")}))
    except Exception:
        print(text[:500])


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
        "--allow-non-headline",
        action="store_true",
        help=(
            "Inspect diagnostic/non-headline payloads such as warmed/history "
            "n-gram artifacts. This is restricted to --dry-run; real "
            "submissions fail closed."
        ),
    )
    args = parser.parse_args()

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
            "synthetic/warmed/history/non-headline payloads are not submit-safe; "
            "use --allow-non-headline with --dry-run only to inspect them",
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
        status, text, retry_after_ms = post_payload(key, item["payload"])
        print(f"{index}/{len(queue)} {label}: HTTP {status}")
        if 200 <= status < 300:
            print_success_response(text)
            continue

        print(text[:1000], file=sys.stderr)
        if status == 429 and args.sleep_on_429 and retry_after_ms:
            sleep_s = max(1, int(retry_after_ms / 1000) + 2)
            print(f"rate limited; sleeping {sleep_s}s", file=sys.stderr)
            time.sleep(sleep_s)
            status, text, _ = post_payload(key, item["payload"])
            print(f"{index}/{len(queue)} {label} retry: HTTP {status}")
            if not (200 <= status < 300):
                print(text[:1000], file=sys.stderr)
                return 1
            print_success_response(text)
        else:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

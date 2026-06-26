#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


API_URL = "https://localmaxxing.com/api/benchmarks"
DEFAULT_KEY_PATH = Path.home() / ".config" / "localmaxxing" / "api_key"


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

    return [] if allow_non_headline else problems


def post_payload(key: str, payload: dict) -> tuple[int, str, int | None]:
    body = json.dumps(payload).encode("utf-8")
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
            "Allow diagnostic/non-headline payloads such as warmed/history "
            "n-gram artifacts. Default is to fail closed."
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
            "pass --allow-non-headline only for deliberately labeled diagnostic artifacts",
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

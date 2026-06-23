#!/usr/bin/env python3
"""Deterministic text canaries for Gemma 4 OpenAI-compatible endpoints."""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable


def complete(base_url: str, model: str, prompt: str, max_tokens: int, timeout: int) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": 0,
        "top_p": 1,
        "stream": False,
    }
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0].get("text", "")


def normalize_text(text: str) -> str:
    text = text.strip().strip("`")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .\n\t")


def check_json(text: str) -> bool:
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return False
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError:
        return False
    return obj == {"answer": 42, "unit": "widgets"}


def check_sort(text: str) -> bool:
    norm = normalize_text(text).lower()
    norm = norm.replace(" and ", ", ")
    norm = re.sub(r"\s*,\s*", ", ", norm)
    return norm == "blue, green, orange, red"


def check_arithmetic(text: str) -> bool:
    norm = normalize_text(text)
    return bool(re.fullmatch(r"17", norm))


CASES: list[dict[str, Any]] = [
    {
        "name": "json",
        "prompt": (
            "Return exactly this JSON object and nothing else, with a numeric answer: "
            "{\"answer\":42,\"unit\":\"widgets\"}\nAnswer:"
        ),
        "max_tokens": 32,
        "check": check_json,
    },
    {
        "name": "sort",
        "prompt": (
            "Sort these colors alphabetically. Reply only with the comma-separated list: "
            "orange, blue, red, green\nAnswer:"
        ),
        "max_tokens": 32,
        "check": check_sort,
    },
    {
        "name": "arithmetic",
        "prompt": (
            "Compute exactly: (8 * 3) - (14 / 2). Reply with only the integer.\nAnswer:"
        ),
        "max_tokens": 16,
        "check": check_arithmetic,
    },
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18260")
    parser.add_argument("--model", default="gemma4-26b-a4b-q8")
    parser.add_argument("--repeats", type=int, default=32)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    for i in range(args.repeats):
        for case in CASES:
            started = time.perf_counter()
            text = complete(
                args.base_url, args.model, case["prompt"], case["max_tokens"], args.timeout
            )
            elapsed_s = time.perf_counter() - started
            ok = bool(case["check"](text))
            rows.append(
                {
                    "repeat": i,
                    "case": case["name"],
                    "ok": ok,
                    "elapsed_s": elapsed_s,
                    "text": text,
                    "normalized": normalize_text(text),
                }
            )
            if not ok:
                break
        if rows and not rows[-1]["ok"]:
            break

    summary = {
        "base_url": args.base_url,
        "model": args.model,
        "repeats_requested": args.repeats,
        "rows_completed": len(rows),
        "pass_all": all(row["ok"] for row in rows),
        "failures": [row for row in rows if not row["ok"]],
    }
    result = {"summary": summary, "rows": rows}
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    print(text)
    return 0 if summary["pass_all"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

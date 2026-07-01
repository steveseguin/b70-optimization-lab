#!/usr/bin/env python3
"""Fetch a compact Fast Gemma dashboard summary.

This is only an idea-tracking artifact for transfer lessons. It is not a Qwen
benchmark and should not be used as a promoted speed result.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_URL = "https://gemma-challenge-gemma-dashboard.hf.space/api/results"


KEYWORDS = [
    "negative",
    "vllm",
    "graph",
    "capture",
    "speculative",
    "speculation",
    "lm_head",
    "logits",
    "precache",
    "prefix",
    "prompt_logprobs",
    "ppl",
    "detok",
    "fallback",
]


def parse_frontmatter(content: str) -> dict[str, str]:
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end < 0:
        return {}
    frontmatter = content[3:end]
    fields: dict[str, str] = {}
    for line in frontmatter.splitlines():
        match = re.match(r"^([A-Za-z0-9_ -]+):\s*(.*)$", line)
        if match:
            fields[match.group(1).strip()] = match.group(2).strip()
    return fields


def parse_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_summary(url: str, top_n: int) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=30) as response:
        payload = json.loads(response.read())
    items = payload.get("items", []) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError("unexpected dashboard payload shape")

    rows: list[dict[str, Any]] = []
    keyword_counts = {keyword: 0 for keyword in KEYWORDS}
    for item in items:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "")
        fields = parse_frontmatter(content)
        tps = parse_float(fields.get("tps"))
        ppl = parse_float(fields.get("ppl"))
        status = fields.get("status") or ""
        method = fields.get("method") or ""
        text = (content + "\n" + method + "\n" + status).lower()
        for keyword in KEYWORDS:
            if keyword in text:
                keyword_counts[keyword] += 1
        if tps is not None:
            rows.append(
                {
                    "filename": item.get("filename"),
                    "tps": tps,
                    "ppl": ppl,
                    "method": method,
                    "status": status,
                    "description": fields.get("description") or "",
                }
            )

    rows.sort(key=lambda row: row["tps"], reverse=True)
    return {
        "fetched_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": url,
        "count": len(items),
        "parsed_tps_count": len(rows),
        "keyword_counts": keyword_counts,
        "top_tps": rows[:top_n],
        "notes": [
            "External Gemma E4B challenge data is used only for transferable optimization ideas.",
            "Do not compare these TPS values directly to Qwen3.6 B70 INT8 endpoint results.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    summary = build_summary(args.url, args.top_n)
    Path(args.out).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

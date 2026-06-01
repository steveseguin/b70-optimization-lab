#!/usr/bin/env python3
"""Extract vLLM XPU timing summaries from a benchmark log."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


TIMING_RE = re.compile(
    r"\[vllm-xpu-timing-summary\]\s+"
    r"rank=(?P<rank>\S+)\s+"
    r"label=(?P<label>.*?)\s+"
    r"count=(?P<count>\d+)\s+"
    r"total_ms=(?P<total_ms>[0-9.]+)\s+"
    r"avg_ms=(?P<avg_ms>[0-9.]+)\s+"
    r"max_ms=(?P<max_ms>[0-9.]+)"
)
THROUGHPUT_RE = re.compile(
    r"Throughput:\s+"
    r"(?P<requests>[0-9.]+)\s+requests/s,\s+"
    r"(?P<total>[0-9.]+)\s+total tokens/s,\s+"
    r"(?P<output>[0-9.]+)\s+output tokens/s"
)


def parse_log(path: Path) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    throughput: dict[str, float] | None = None
    for line in path.read_text(errors="replace").splitlines():
        if match := TIMING_RE.search(line):
            rows.append(
                {
                    "rank": match.group("rank"),
                    "label": match.group("label"),
                    "count": int(match.group("count")),
                    "total_ms": float(match.group("total_ms")),
                    "avg_ms": float(match.group("avg_ms")),
                    "max_ms": float(match.group("max_ms")),
                }
            )
        if match := THROUGHPUT_RE.search(line):
            throughput = {
                "requests_per_s": float(match.group("requests")),
                "total_tokens_per_s": float(match.group("total")),
                "output_tokens_per_s": float(match.group("output")),
            }
    rows.sort(key=lambda row: float(row["total_ms"]), reverse=True)
    return {"log": str(path), "throughput": throughput, "timing": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    parsed = parse_log(args.log)
    if args.json:
        args.json.write_text(json.dumps(parsed, indent=2, sort_keys=True) + "\n")

    throughput = parsed["throughput"]
    if throughput:
        print(
            "throughput "
            f"output={throughput['output_tokens_per_s']:.6f} "
            f"total={throughput['total_tokens_per_s']:.6f}"
        )
    for row in parsed["timing"][: args.top]:
        print(
            f"{row['total_ms']:12.6f} ms total "
            f"{row['avg_ms']:10.6f} ms avg "
            f"{row['count']:6d} calls "
            f"{row['label']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

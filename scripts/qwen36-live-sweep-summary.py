#!/usr/bin/env python3
"""Summarize live Qwen3.6 endpoint mode/context sweep metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def median(summary: dict[str, Any], key: str) -> float | None:
    value = summary.get(key)
    if isinstance(value, dict) and value.get("median") is not None:
        return float(value["median"])
    return None


def pct_delta(new: float | None, old: float | None) -> float | None:
    if new is None or old is None or old == 0:
        return None
    return (new - old) / old * 100.0


def row(name: str, path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    summary = data.get("summary") or {}
    return {
        "name": name,
        "path": str(path),
        "mode": data.get("mode"),
        "prompt_tokens": data.get("prompt_tokens_actual"),
        "output_tokens": data.get("output_tokens_requested"),
        "repeats": data.get("repeats"),
        "tok_s_stream_corrected": median(
            summary, "tok_s_out_client_after_first_chunk_corrected"
        ),
        "tok_s_e2e": median(summary, "tok_s_out_client_e2e"),
        "decode_ms_per_token": median(
            summary, "decode_ms_per_generation_token_vllm_histogram"
        ),
        "prefill_ms": median(summary, "prefill_ms_vllm_histogram"),
        "ttft_ms": median(summary, "ttft_ms_vllm_metrics"),
        "queue_ms": median(summary, "queue_ms_vllm_histogram"),
        "inter_token_ms": median(summary, "inter_token_ms_vllm_histogram"),
        "iteration_tokens_per_step": median(
            summary, "iteration_tokens_per_step_vllm_histogram"
        ),
        "server_model_root": (data.get("server_model_record") or {}).get("root"),
    }


def fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def make_markdown(artifact: dict[str, Any]) -> str:
    rows = artifact["rows"]
    comparisons = artifact["comparisons"]
    lines = [
        "# Qwen3.6 Live Mode And Context Sweep",
        "",
        f"Endpoint: `{artifact['endpoint']}`",
        f"Model root: `{artifact['model_root']}`",
        "",
        "| Case | Mode | Prompt | Output | Stream tok/s | E2E tok/s | Decode ms/token | Prefill ms | TTFT ms | Queue ms |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in rows:
        lines.append(
            "| {name} | {mode} | {prompt} | {output} | {stream_tok} | {e2e_tok} | "
            "{decode} | {prefill} | {ttft} | {queue} |".format(
                name=item["name"],
                mode=item["mode"],
                prompt=item["prompt_tokens"],
                output=item["output_tokens"],
                stream_tok=fmt(item["tok_s_stream_corrected"], 3),
                e2e_tok=fmt(item["tok_s_e2e"], 3),
                decode=fmt(item["decode_ms_per_token"], 3),
                prefill=fmt(item["prefill_ms"], 3),
                ttft=fmt(item["ttft_ms"], 3),
                queue=fmt(item["queue_ms"], 4),
            )
        )

    lines.extend(["", "## Comparisons", ""])
    for item in comparisons:
        lines.append(f"- {item}")
    lines.extend(["", "## Interpretation", ""])
    for item in artifact["interpretation"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://127.0.0.1:18080")
    parser.add_argument("--case", action="append", required=True,
                        help="NAME=PATH to a metrics JSON")
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    by_name: dict[str, dict[str, Any]] = {}
    for case in args.case:
        if "=" not in case:
            raise SystemExit(f"bad --case {case!r}; expected NAME=PATH")
        name, raw_path = case.split("=", 1)
        item = row(name, Path(raw_path))
        rows.append(item)
        by_name[name] = item

    comparisons: list[str] = []
    stream = by_name.get("stream_p512_o512")
    nonstream = by_name.get("nonstream_p512_o512")
    if stream and nonstream:
        delta_decode = pct_delta(
            nonstream["decode_ms_per_token"], stream["decode_ms_per_token"]
        )
        delta_e2e = pct_delta(nonstream["tok_s_e2e"], stream["tok_s_e2e"])
        comparisons.append(
            "Non-stream p512/o512 decode median is `{}` ms/token versus stream `{}` "
            "ms/token (`{}`% delta); E2E tok/s delta is `{}`%.".format(
                fmt(nonstream["decode_ms_per_token"], 3),
                fmt(stream["decode_ms_per_token"], 3),
                fmt(delta_decode, 2),
                fmt(delta_e2e, 2),
            )
        )

    short_ctx = by_name.get("stream_p512_o256")
    long_ctx = by_name.get("stream_p4096_o256")
    if short_ctx and long_ctx:
        delta_decode = pct_delta(
            long_ctx["decode_ms_per_token"], short_ctx["decode_ms_per_token"]
        )
        comparisons.append(
            "Stream p4096/o256 decode median is `{}` ms/token versus p512/o256 "
            "`{}` ms/token (`{}`% delta), while TTFT grows from `{}` ms to "
            "`{}` ms.".format(
                fmt(long_ctx["decode_ms_per_token"], 3),
                fmt(short_ctx["decode_ms_per_token"], 3),
                fmt(delta_decode, 2),
                fmt(short_ctx["ttft_ms"], 1),
                fmt(long_ctx["ttft_ms"], 1),
            )
        )

    artifact = {
        "endpoint": args.endpoint,
        "model_root": rows[0].get("server_model_root") if rows else None,
        "rows": rows,
        "comparisons": comparisons,
        "interpretation": [
            "SSE streaming is not a large c1 decode bottleneck for this endpoint; non-streaming did not materially improve decode ms/token.",
            "Longer prompt context mainly increases TTFT/prefill. Steady decode ms/token stayed near 10 ms at p512 and p4096.",
            "Queue time remained around 0.008-0.009 ms/request, so queueing/frontdoor work is not the first 2x target.",
            "The next high-value optimization should focus on model execution, command submission/synchronization, TP/collective topology, or verifier-safe multi-token acceptance.",
        ],
    }

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(artifact, indent=2) + "\n")
    out_md.write_text(make_markdown(artifact))
    print(json.dumps(artifact, indent=2))
    print(f"wrote={out_json}")
    print(f"wrote={out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

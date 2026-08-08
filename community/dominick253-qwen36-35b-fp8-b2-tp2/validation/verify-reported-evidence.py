#!/usr/bin/env python3
"""Fail-closed offline consistency checks for the PR #18 reported evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from pathlib import Path

AGGREGATE_METRICS = ("pp_throughput", "tg_throughput")
PER_REQUEST_METRICS = ("tg_req_throughput", "ttfr")


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def load(root: Path, name: str) -> dict:
    return json.loads((root / name).read_text(encoding="utf-8"))


def sha256(root: Path, name: str) -> str:
    return hashlib.sha256((root / name).read_bytes()).hexdigest()


def verify(evidence: Path, launcher: Path) -> None:
    summary = load(evidence, "benchmark-triple-summary.json")
    raw_runs = []
    for sweep in (1, 2, 3):
        name = f"benchmark-clean-r{sweep}.json"
        require(
            sha256(evidence, name) == summary["raw_sha256"][name],
            f"hash mismatch: {name}",
        )
        raw = load(evidence, name)
        raw_runs.append(raw)
        require(
            raw.get("version") == "0.4.1.dev1+ge9be34457", f"version mismatch: {name}"
        )
        require(len(raw.get("benchmarks", [])) == 5, f"unexpected row count: {name}")
        require(
            [row.get("concurrency") for row in raw["benchmarks"]] == [1, 2, 4, 8, 12],
            f"unexpected concurrency sweep: {name}",
        )
        for benchmark in raw["benchmarks"]:
            concurrency = benchmark["concurrency"]
            for metric in AGGREGATE_METRICS:
                values = benchmark[metric]["values"]
                require(len(values) == 5, f"unexpected repeat count: {name}/{metric}")
                require(
                    math.isclose(
                        statistics.fmean(values),
                        benchmark[metric]["mean"],
                        rel_tol=1e-12,
                        abs_tol=1e-12,
                    ),
                    f"mean mismatch: {name}/{concurrency}/{metric}",
                )
            for metric in PER_REQUEST_METRICS:
                values = benchmark[metric]["values"]
                require(
                    len(values) == 5 * concurrency,
                    f"unexpected per-request sample count: {name}/{metric}",
                )
                require(
                    math.isclose(
                        statistics.fmean(values),
                        benchmark[metric]["mean"],
                        rel_tol=1e-12,
                        abs_tol=1e-12,
                    ),
                    f"mean mismatch: {name}/{concurrency}/{metric}",
                )

        monitor = load(evidence, f"benchmark-clean-r{sweep}-monitor.json")
        require(
            monitor.get("benchmark_exit_code") == 0, f"benchmark failed: sweep {sweep}"
        )
        require(
            monitor.get("expected_requests") == 165,
            f"expected request drift: sweep {sweep}",
        )
        require(
            monitor.get("actual_requests") == 165,
            f"actual request drift: sweep {sweep}",
        )
        require(
            monitor.get("request_count_clean") is True,
            f"traffic gate failed: sweep {sweep}",
        )
        require(
            not any("error" in row for row in monitor.get("samples", [])),
            f"monitor errors: sweep {sweep}",
        )
        require(monitor.get("new_faults") == 0, f"reported fault delta: sweep {sweep}")
        require(
            monitor.get("faults_before") == monitor.get("faults_after"),
            f"fault count drift: sweep {sweep}",
        )

    for aggregate in summary["results"]:
        concurrency = aggregate["concurrency"]
        raw_rows = [
            next(row for row in raw["benchmarks"] if row["concurrency"] == concurrency)
            for raw in raw_runs
        ]
        mappings = {
            "prompt_tokens_per_second": "pp_throughput",
            "aggregate_generation_tokens_per_second": "tg_throughput",
            "per_request_generation_tokens_per_second": "tg_req_throughput",
            "time_to_first_response_ms": "ttfr",
        }
        for summary_key, raw_key in mappings.items():
            means = [row[raw_key]["mean"] for row in raw_rows]
            submitted = aggregate[summary_key]
            require(
                len(submitted["sweep_means"]) == 3,
                f"sweep count mismatch: {concurrency}/{summary_key}",
            )
            for actual, recorded in zip(means, submitted["sweep_means"], strict=True):
                require(
                    math.isclose(actual, recorded, rel_tol=0, abs_tol=5e-7),
                    f"sweep mean mismatch: {concurrency}/{summary_key}",
                )
            require(
                math.isclose(
                    statistics.fmean(means),
                    submitted["three_sweep_mean"],
                    rel_tol=0,
                    abs_tol=5e-7,
                ),
                f"aggregate mismatch: {concurrency}/{summary_key}",
            )

    quality = load(evidence, "quality-manifest.json")
    total_tokens = 0
    for artifact in quality["artifacts"]:
        name = artifact["artifact"]
        require(
            sha256(evidence, name) == artifact["artifact_sha256"],
            f"quality hash mismatch: {name}",
        )
        raw = load(evidence, name)
        require(
            raw.get("passed") is True and raw.get("failures") == 0,
            f"quality artifact failed: {name}",
        )
        require(
            len(raw["results"]) == len(artifact["responses"]),
            f"quality response count: {name}",
        )
        for result, submitted in zip(
            raw["results"], artifact["responses"], strict=True
        ):
            text = (
                (result.get("reasoning_content") or "")
                + "\n"
                + (result.get("text") or "")
            )
            total_tokens += result["completion_tokens"]
            require(result.get("errors") == [], f"reported quality errors: {name}")
            require(
                result["completion_tokens"] == submitted["completion_tokens"],
                f"token count mismatch: {name}",
            )
            require(
                result.get("finish_reason") == submitted["finish_reason"],
                f"finish mismatch: {name}",
            )
            require(
                text.count("!!!!") == submitted["bang4_occurrences"] == 0,
                f"bang run: {name}",
            )
            require(
                hashlib.sha256(text.encode()).hexdigest() == submitted["text_sha256"],
                f"text hash: {name}",
            )
            require(len(text) == submitted["characters"], f"character count: {name}")
            require(
                re.search(r"([!?.;,])\1{9,}", text) is None,
                f"punctuation collapse: {name}",
            )
    require(
        total_tokens == quality["total_completion_tokens"] == 11024,
        "quality token total mismatch",
    )

    launcher_text = launcher.read_text(encoding="utf-8")
    for required in (
        "sha256:3f0a8c60fbaf376ec09538f093cba91f171238b99c117445c0bcc6096272ec3e",
        "95a723d08a9490559dae23d0cff1d9466213d989",
        "CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296",
        "--tensor-parallel-size",
        "--kv-cache-dtype",
    ):
        require(required in launcher_text, f"safe launcher setting missing: {required}")


def main() -> int:
    packet = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence", type=Path, default=packet / "reported" / "evidence"
    )
    parser.add_argument(
        "--launcher", type=Path, default=packet / "vllm-qwen36-35b-fp8-b2-tp2.sh"
    )
    args = parser.parse_args()
    try:
        verify(args.evidence, args.launcher)
    except (KeyError, OSError, ValueError, VerificationError) as error:
        print(f"FAIL: {error}")
        return 1
    print(
        "PASS: contributor artifacts are internally consistent: 3 sweeps, "
        "495 reported requests, and 11,024 reported long-output tokens"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

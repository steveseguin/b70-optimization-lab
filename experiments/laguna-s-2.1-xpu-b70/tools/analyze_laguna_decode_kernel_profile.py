#!/usr/bin/env python
"""Aggregate device kernel time from a Laguna decode torch-profiler trace.

Answers one question: where does a width-12 decode step spend its device time?
Groups the captured window by kernel name and by a coarse role (MoE expert
GEMM, attention, collective, dequantisation, elementwise) so the gap between
measured decode throughput and the bandwidth ceiling can be attributed.

Usage: analyze_laguna_decode_kernel_profile.py TRACE [TRACE ...]
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# Kineto's own category names vary by backend and version, and the XPU device
# category is not a fixed string across builds. Excluding the host-side ones is
# stable where whitelisting device ones is not, so anything left with a real
# duration is treated as device activity and the observed categories are always
# printed for inspection.
HOST_CATEGORIES = {
    "cpu_op", "cpu_instant_event", "python_function", "user_annotation",
    "external_correlation", "overhead", "ac2g", "fwdbwd", "async_task",
    "cuda_runtime", "cuda_driver", "xpu_runtime", "xpu_driver",
    "mtia_runtime", "glow_runtime", "privateuse1_runtime", "privateuse1_driver",
    "cuda_profiler_range", "profiler_step",
    # 'trace' holds the profiler's own span markers ("PyTorch Profiler (0)",
    # "__xpu_profiler__ (0)"). They span the whole capture, so counting them as
    # device time swamps every real kernel -- observed at 99.7% of the total on
    # a real XPU trace before this exclusion.
    "trace",
}

ROLES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("collective", re.compile(r"ccl|allreduce|all_reduce|allgather|all_gather|"
                              r"reduce_scatter|reducescatter|all2all|alltoall", re.I)),
    ("moe-gemm", re.compile(r"grouped_gemm|moe|expert|gate_up|down_mm|w1|w2|w3", re.I)),
    # fmha must precede the gemm rule: the cutlass FMHA decode kernels carry
    # "gemm"-adjacent names but are attention, and misfiling them understates
    # attention by ~16% of device time.
    ("attention", re.compile(r"attn|attention|flash|fmha|paged|rope|qk_norm|"
                             r"kv_cache|reshape_and_cache|splitk|decode", re.I)),
    ("dequant", re.compile(r"dequant|awq|gptq|int4|unpack|woq", re.I)),
    ("gemm", re.compile(r"gemm|matmul|linear|mm_|xetla|cutlass|brgemm", re.I)),
    ("norm", re.compile(r"norm|rms|layernorm", re.I)),
    ("elementwise", re.compile(r"elementwise|add|mul|silu|swiglu|act|copy|cat|index", re.I)),
    ("memory", re.compile(r"memcpy|memset", re.I)),
)


def classify(name: str, category: str = "") -> str:
    if category == "collective_comm":
        return "collective"
    for role, pattern in ROLES:
        if pattern.search(name):
            return role
    return "other"


def load(path: Path) -> list[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        return json.load(handle).get("traceEvents", [])


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2

    by_name: dict[str, list[float]] = defaultdict(list)
    name_category: dict[str, str] = {}
    by_category: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))
    device_total = 0.0
    span_lo, span_hi = None, None

    for arg in argv[1:]:
        path = Path(arg)
        for event in load(path):
            if event.get("ph") != "X":
                continue
            duration = float(event.get("dur") or 0.0)
            if duration <= 0:
                continue
            category = (event.get("cat") or "").lower()
            total, count = by_category[category or "<none>"]
            by_category[category or "<none>"] = (total + duration, count + 1)
            if category in HOST_CATEGORIES:
                continue
            name = event.get("name") or "<anon>"
            name_category.setdefault(name, category)
            by_name[name].append(duration)
            device_total += duration
            start = float(event.get("ts") or 0.0)
            span_lo = start if span_lo is None else min(span_lo, start)
            span_hi = start + duration if span_hi is None else max(span_hi, start + duration)

    print("-- all trace categories (host ones are excluded from totals) --")
    for category, (total, count) in sorted(by_category.items(), key=lambda kv: -kv[1][0]):
        mark = "host" if category in HOST_CATEGORIES else "DEVICE"
        print(f"{category:>24}  {total / 1000:10.3f} ms  n={count:6d}  [{mark}]")
    print()

    if not by_name:
        print("no device kernel events found -- check that the XPU profiler "
              "activity was enabled and that the trace covers decode steps",
              file=sys.stderr)
        return 1

    by_role: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))
    for name, durations in by_name.items():
        role = classify(name, name_category.get(name, ""))
        total, count = by_role[role]
        by_role[role] = (total + sum(durations), count + len(durations))

    wall = (span_hi - span_lo) if span_lo is not None else 0.0
    print(f"device events      : {sum(len(v) for v in by_name.values())}")
    print(f"device time        : {device_total / 1000:.3f} ms")
    print(f"captured wall span : {wall / 1000:.3f} ms")
    if wall > 0:
        print(f"device occupancy   : {100 * device_total / wall:.1f}% "
              "(sum of kernel time over wall; >100% means overlapping ranks)")

    print("\n-- by role --")
    for role, (total, count) in sorted(by_role.items(), key=lambda kv: -kv[1][0]):
        share = 100 * total / device_total
        print(f"{role:>13}  {total / 1000:10.3f} ms  {share:5.1f}%  n={count}")

    print("\n-- top 25 kernels --")
    ranked = sorted(by_name.items(), key=lambda kv: -sum(kv[1]))[:25]
    for name, durations in ranked:
        total = sum(durations)
        share = 100 * total / device_total
        mean = total / len(durations)
        label = name if len(name) <= 68 else name[:65] + "..."
        role = classify(name, name_category.get(name, ""))
        print(f"{total / 1000:9.3f} ms {share:5.1f}%  n={len(durations):5d} "
              f"mean={mean:8.1f} us  [{role}] {label}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

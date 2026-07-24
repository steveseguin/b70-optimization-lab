#!/usr/bin/env python3
"""Fail-closed AB/BA analyzer for the Laguna M8 breakable-graph crossover.

This deliberately consumes only completed service-leg artifacts.  In particular,
endpoint-qualification roots are never timing evidence, and a graph leg needs
four independently logged 146-segment / 145-boundary topologies before it can
be compared with eager.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path("/home/steve/llm-optimizations")
TOOLS = ROOT / "experiments/laguna-s-2.1-xpu-b70/tools"
METRIC = "tok_s_1_100_after_ttft"
PROMPT_COUNT = 13
RECORD_FLOOR = 33.89498511171744
VLLM_COMMIT = "0ce373a3115fb4498c5e7a041d4fc9212fd6b5ca"
KERNEL_COMMIT = "4772f727590c51b72add79350b913d098cf67872"
MODEL = "/mnt/fast-ai/llm-models/laguna-s-2.1/int4"
DRAFT = "/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4"
TEACHER = (
    "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/"
    "bulletproof-q1-canonical-cb616c6-6fc06b0-20260722T142908Z/bench.json"
)
MIN_WINS = 9
MIN_CYCLE_SAVING_MS = 0.15
MAX_ACCEPTANCE_DELTA = 0.001
GRAPH_TOPOLOGY = "BreakableCUDAGraphCapture(graphs=146, eager_breaks=145)"


def _base() -> Any:
    spec = importlib.util.spec_from_file_location(
        "laguna_crossover_base",
        TOOLS / "analyze_shared_elementwise_qknorm_stack_crossover.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load shared Laguna crossover metric parser")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = _base()


def load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolved(value: str | Path) -> str:
    return str(Path(value).resolve())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def key_values(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            if key in result:
                raise ValueError(f"{path}: duplicate environment key {key}")
            result[key] = value
    return result


def recorded_checksums(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = line.split("  ", 1)
        if (
            len(fields) == 2
            and len(fields[0]) == 64
            and all(character in "0123456789abcdef" for character in fields[0])
        ):
            result[str(Path(fields[1]).resolve())] = fields[0]
    return result


def idle_interval_checks(directory: Path) -> dict[str, bool]:
    idle_dir = directory / "idle-interval"
    snapshots = sorted(idle_dir.glob("*.json"))
    expected_names = [
        f"{phase}-{index:02d}.json"
        for phase in ("prestart", "poststop")
        for index in range(13)
    ]
    payloads = {snapshot.name: load(snapshot) for snapshot in snapshots}
    summary_rows: dict[str, dict[str, str]] = {}
    for line in (idle_dir / "summary.txt").read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if fields:
            summary_rows[fields[0]] = dict(
                field.split("=", 1) for field in fields[1:] if "=" in field
            )
    payload_checks = all(
        payload.get("status") == "passed"
        and payload.get("format") == "laguna-m8-gather-sharded-operational-preflight-v2"
        and payload.get("idle", {}).get("accepted_mode") == "self_observer_rows"
        and payload.get("idle", {}).get("device_ids") == [0, 1, 2, 3]
        and payload.get("idle", {}).get("row_count") == 4
        and [
            row.get("device_id")
            for row in payload.get("idle", {})
            .get("sanitized_payload", {})
            .get("device_util_by_proc_list", [])
        ]
        == [0, 1, 2, 3]
        and all(
            row.get("process_name") == "xpu-smi"
            for row in payload.get("idle", {})
            .get("sanitized_payload", {})
            .get("device_util_by_proc_list", [])
        )
        for payload in payloads.values()
    )

    def observed_span(phase: str) -> float:
        first = payloads.get(f"{phase}-00.json", {}).get("observed_utc")
        last = payloads.get(f"{phase}-12.json", {}).get("observed_utc")
        if not isinstance(first, str) or not isinstance(last, str):
            return 0.0
        return (
            datetime.fromisoformat(last) - datetime.fromisoformat(first)
        ).total_seconds()

    def timestamps_strictly_increase(phase: str) -> bool:
        values = [
            payloads.get(f"{phase}-{index:02d}.json", {}).get("observed_utc")
            for index in range(13)
        ]
        if not all(isinstance(value, str) for value in values):
            return False
        times = [datetime.fromisoformat(value) for value in values]
        return all(
            right > left for left, right in zip(times[:-1], times[1:], strict=True)
        )

    return {
        "twenty_six_idle_snapshots": len(snapshots) == 26,
        "exact_snapshot_names": [snapshot.name for snapshot in snapshots]
        == sorted(expected_names),
        "all_idle_payloads_valid": len(payloads) == 26 and payload_checks,
        "prestart_observed_span_60_seconds": observed_span("prestart") >= 60.0,
        "poststop_observed_span_60_seconds": observed_span("poststop") >= 60.0,
        "prestart_timestamps_increase": timestamps_strictly_increase("prestart"),
        "poststop_timestamps_increase": timestamps_strictly_increase("poststop"),
        "prestart_60_seconds": int(
            summary_rows.get("prestart", {}).get("elapsed_seconds", "0")
        )
        >= 60,
        "prestart_13_snapshots": summary_rows.get("prestart", {}).get("snapshots")
        == "13",
        "poststop_60_seconds": int(
            summary_rows.get("poststop", {}).get("elapsed_seconds", "0")
        )
        >= 60,
        "poststop_13_snapshots": summary_rows.get("poststop", {}).get("snapshots")
        == "13",
    }


def validate_campaign_layout(
    *,
    a1: Path,
    b1: Path,
    b2: Path | None,
    a2: Path | None,
    out: Path,
    markdown_out: Path,
) -> Path:
    campaign = a1.parent.resolve()
    expected = {
        "a1": campaign / "A1-eager",
        "b1": campaign / "B1-graph",
        "b2": campaign / "B2-graph",
        "a2": campaign / "A2-eager",
    }
    require(a1.resolve() == expected["a1"], "A1 is outside the canonical campaign")
    require(b1.resolve() == expected["b1"], "B1 is outside the canonical campaign")
    full = b2 is not None or a2 is not None
    if full:
        require(
            b2 is not None and b2.resolve() == expected["b2"],
            "B2 is outside the canonical campaign",
        )
        require(
            a2 is not None and a2.resolve() == expected["a2"],
            "A2 is outside the canonical campaign",
        )
        require(out.resolve() == campaign / "full-analysis.json", "wrong full output")
        require(
            markdown_out.resolve() == campaign / "full-analysis.md",
            "wrong full markdown output",
        )
    else:
        require(not expected["b2"].exists(), "B2 exists before phase-1 continuation")
        require(not expected["a2"].exists(), "A2 exists before phase-1 continuation")
        require(
            out.resolve() == campaign / "phase1-analysis.json", "wrong phase-1 output"
        )
        require(
            markdown_out.resolve() == campaign / "phase1-analysis.md",
            "wrong phase-1 markdown output",
        )

    identity_path = campaign / "controller-identity.txt"
    identity = key_values(identity_path)
    controller_hashes = recorded_checksums(identity_path)
    controller_paths = [
        TOOLS / "run_laguna_m8_formal_graph_crossover.sh",
        TOOLS / "run_laguna_m8_formal_graph_crossover_leg.sh",
        TOOLS / "analyze_laguna_m8_graph_crossover.py",
        TOOLS / "compare_exact_runs.py",
    ]
    require(
        identity
        == {
            "schema": "laguna-m8-formal-graph-crossover-controller-v1",
            "order": "A1-eager,B1-graph,B2-graph,A2-eager",
            "phase1_stop": "true",
            "rescue_runs": "forbidden",
            "qualification_timing_inputs": "forbidden",
        },
        "controller identity drift",
    )
    require(
        controller_hashes
        == {str(path.resolve()): sha256(path) for path in controller_paths},
        "controller tool hashes drift",
    )
    return campaign


def exact_checks(report: dict[str, Any], bench_path: Path) -> dict[str, bool]:
    candidates = report.get("candidates")
    candidate = (
        candidates[0] if isinstance(candidates, list) and len(candidates) == 1 else {}
    )
    comparison = candidate.get("comparison", {}) if isinstance(candidate, dict) else {}
    return {
        "all_exact": report.get("all_exact") is True,
        "canonical_teacher": resolved(report.get("teacher", "")) == resolved(TEACHER),
        "candidate_path": resolved(candidate.get("candidate", ""))
        == resolved(bench_path),
        "exact_13": comparison.get("exact") is True
        and comparison.get("exact_count") == 13
        and comparison.get("total") == 13,
        "cache_zero": comparison.get("all_cached_zero") is True,
        "long_then_next": comparison.get("long_then_next", {}).get("passed") is True,
        "rollover": comparison.get("rollover", {}).get("count") == 1
        and comparison.get("rollover", {}).get("exact_count") == 1,
    }


def graph_log_checks(path: Path, graph: bool) -> dict[str, bool]:
    text = path.read_text(encoding="utf-8", errors="replace")
    captures = [
        line
        for line in text.splitlines()
        if "Captured audited breakable cudagraph" in line
    ]
    replays = [
        line
        for line in text.splitlines()
        if "Replayed audited breakable cudagraph" in line
    ]
    expected_ranks = {f"Worker_TP{rank}_EP{rank}" for rank in range(4)}
    common = {
        "no_capture_on_eager": (not captures and not replays) if not graph else True,
        "four_distinct_captures": len(captures) == 4
        and {
            next((rank for rank in expected_ranks if rank in line), "")
            for line in captures
        }
        == expected_ranks
        if graph
        else True,
        "four_distinct_replays": len(replays) == 4
        and {
            next((rank for rank in expected_ranks if rank in line), "")
            for line in replays
        }
        == expected_ranks
        if graph
        else True,
        "topology_146_145": all(GRAPH_TOPOLOGY in line for line in captures + replays)
        if graph
        else True,
    }
    return common


def run_summary(name: str, directory: Path, graph: bool) -> dict[str, Any]:
    # A timing leg must be a fresh dedicated benchmark root, never a qualifying root.
    forbidden = ("qualification", "endpoint", "actual-offline")
    require(
        not any(token in str(directory).lower() for token in forbidden),
        f"{name}: qualification/evidence root is not timing evidence",
    )
    bench_path = directory / "bench.json"
    bench = load(bench_path)
    identity_path = directory / "identity.txt"
    identity = key_values(identity_path)
    exact = load(directory / "exactness-vs-q1.json")
    env = key_values(directory / "service-environment.txt")
    recorded_tool_hashes = recorded_checksums(identity_path)
    expected_tool_paths = [
        TOOLS / "run_laguna_m8_formal_graph_crossover_leg.sh",
        TOOLS / "serve_laguna_m8_breakable_graph_nvme.sh",
        TOOLS / "serve_laguna_m8_eager_nvme.sh",
        TOOLS / "compare_exact_runs.py",
        ROOT / "scripts/bench-openai-realistic-suite.py",
        TOOLS / "capture_laguna_m8_idle_snapshot.py",
        Path("/home/steve/.venvs/deepseek-v4-xpu/bin/python"),
        Path("/home/steve/.venvs/deepseek-v4-xpu/bin/vllm"),
    ]
    expected_tool_hashes = {
        str(path.resolve()): sha256(path) for path in expected_tool_paths
    }
    cleanup = (directory / "cleanup-status.txt").read_text(encoding="utf-8")
    rows = bench.get("rows") if isinstance(bench.get("rows"), list) else []
    primary = bench.get("summary", {}).get(METRIC, {})
    require(
        primary.get("count") == PROMPT_COUNT,
        f"{name}: primary metric must contain 13 rows",
    )
    benchmark = BASE.benchmark_identity_summary(bench)
    freshness = BASE.freshness_summary(bench)
    metrics = BASE.metrics_summary(directory)
    actual_graph = "1" if graph else "0"
    required_env = {
        "ONEAPI_DEVICE_SELECTOR": "level_zero:0,1,2,3",
        "ZE_AFFINITY_MASK": "0,1,2,3",
        "VLLM_XPU_EXACT_SPEC_ATTN": "1",
        "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1",
        "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2": "1",
        "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE": "1",
        "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "1",
        "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "1",
        "VLLM_XPU_LAGUNA_M8_W1_N_TILE": "64",
        "VLLM_USE_AOT_COMPILE": "0",
        "VLLM_USE_BREAKABLE_CUDAGRAPH": actual_graph,
        "VLLM_XPU_ENABLE_XPU_GRAPH": actual_graph,
        "VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH": actual_graph,
        "XPU_GRAPH": actual_graph,
    }
    identity_checks = {
        "vllm_commit": identity.get("vllm_commit") == VLLM_COMMIT,
        "kernel_commit": identity.get("kernel_commit") == KERNEL_COMMIT,
        "local_nvme_models": identity.get("model") == MODEL
        and identity.get("draft") == DRAFT,
        "formal_schema": identity.get("schema")
        == "laguna-m8-formal-graph-crossover-leg-v1",
        "label_and_treatment": identity.get("label") == name[:2]
        and identity.get("treatment") == ("graph" if graph else "eager"),
        "runner_identity": len(
            [
                line
                for line in identity_path.read_text(encoding="utf-8").splitlines()
                if "  /" in line and len(line.split("  ", 1)[0]) == 64
            ]
        )
        == 8,
        "recorded_tool_hashes": recorded_tool_hashes == expected_tool_hashes,
        "selectors": identity.get("selector_stack")
        == "exact-m8-dflash7-w1routew2-routeinterleave-shared-elementwise-qknormrope-n64",
        "no_warmup": identity.get("no_warmup") == "true",
        "idle_preflight": identity.get("verified_idle_interval_seconds") == "60",
        "execution_mode": identity.get("graph_only_difference")
        == ("graph" if graph else "eager"),
    }
    exactness = exact_checks(exact, bench_path)
    topology = graph_log_checks(directory / "server.log", graph)
    idle_interval = idle_interval_checks(directory)
    zero_selectors = {
        "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH",
        "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM",
        "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK",
        "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION",
        "VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE",
        "VLLM_XPU_LAGUNA_M8_GATHER_SHARDED",
        "VLLM_XPU_LAGUNA_M8_REMOTE_ZERO",
        "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM",
        "VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM",
        "VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM",
        "VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM",
    }
    checks = {
        "benchmark_identity": benchmark["passed"],
        "fresh_cold_cache_zero": freshness["passed"],
        "clean_metrics_before": metrics["clean_before_pass"],
        "exact_q1_long_next_rollover": all(exactness.values()),
        "identity": all(identity_checks.values()),
        "actual_service_environment": all(
            env.get(k) == v for k, v in required_env.items()
        ),
        "experimental_selectors_disabled": all(
            env.get(name) == "0" for name in zero_selectors
        ),
        "diagnostics_absent": not any(
            key.startswith("VLLM_XPU_LAGUNA_M8_EVIDENCE") for key in env
        ),
        "clean_shutdown_and_idle": cleanup
        == "original_status=0\nstop_status=0\nworker_status=0\nidle_status=0\n",
        "verified_idle_intervals": all(idle_interval.values()),
        "graph_topology": all(topology.values()),
    }
    return {
        "name": name,
        "directory": str(directory.resolve()),
        "bench_path": str(bench_path.resolve()),
        "bench_sha256": sha256(bench_path),
        "quality_checks": checks,
        "quality_pass": all(checks.values()),
        "headline_tok_s": float(primary["median"]),
        "metrics": metrics,
        "identity": identity,
        "row_metrics": [
            {
                "prompt_id": r["prompt_id"],
                "prompt_sha256": r["prompt_sha256"],
                "tok_s": float(r[METRIC]),
            }
            for r in rows
        ],
        "exactness": exactness,
        "topology": topology,
    }


def pair(control: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    require(
        [(r["prompt_id"], r["prompt_sha256"]) for r in control["row_metrics"]]
        == [(r["prompt_id"], r["prompt_sha256"]) for r in candidate["row_metrics"]],
        "paired legs differ in prompt identity/order",
    )
    deltas = [
        b["tok_s"] - a["tok_s"]
        for a, b in zip(control["row_metrics"], candidate["row_metrics"], strict=True)
    ]
    pcts = [
        100.0 * delta / a["tok_s"]
        for delta, a in zip(deltas, control["row_metrics"], strict=True)
    ]
    cycle = (
        control["metrics"]["aggregate_cycle_ms"]
        - candidate["metrics"]["aggregate_cycle_ms"]
    )
    acceptance = (
        candidate["metrics"]["speculation"]["acceptance_rate"]
        - control["metrics"]["speculation"]["acceptance_rate"]
    )
    gates = {
        "candidate_headline_faster": candidate["headline_tok_s"]
        > control["headline_tok_s"],
        "candidate_wins_at_least_9_of_13_rows": sum(x > 0 for x in deltas) >= MIN_WINS,
        "paired_median_positive": statistics.median(pcts) > 0,
        "aggregate_cycle_saving_at_least_0_15_ms": cycle >= MIN_CYCLE_SAVING_MS,
        "acceptance_rate_delta_at_most_0_001": abs(acceptance) <= MAX_ACCEPTANCE_DELTA,
    }
    return {
        "gates": gates,
        "pass": all(gates.values()),
        "candidate_row_wins": sum(x > 0 for x in deltas),
        "median_paired_delta_pct": statistics.median(pcts),
        "aggregate_cycle_saving_ms": cycle,
        "acceptance_rate_delta": acceptance,
    }


def bundle(path: Path, teacher: str, candidates: list[str]) -> bool:
    report = load(path)
    reports = report.get("candidates", [])
    actual = [resolved(candidate.get("candidate", "")) for candidate in reports]
    expected = [resolved(candidate) for candidate in candidates]
    comparisons_pass = all(
        candidate.get("comparison", {}).get("exact") is True
        and candidate.get("comparison", {}).get("exact_count") == PROMPT_COUNT
        and candidate.get("comparison", {}).get("total") == PROMPT_COUNT
        and candidate.get("comparison", {}).get("all_cached_zero") is True
        and candidate.get("comparison", {}).get("long_then_next", {}).get("passed")
        is True
        and candidate.get("comparison", {}).get("rollover", {}).get("count") == 1
        and candidate.get("comparison", {}).get("rollover", {}).get("exact_count") == 1
        for candidate in reports
    )
    return (
        report.get("all_exact") is True
        and resolved(report.get("teacher", "")) == resolved(teacher)
        and actual == expected
        and comparisons_pass
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze preregistered Laguna M8 eager/graph ABBA crossover"
    )
    parser.add_argument("--a1", type=Path, required=True)
    parser.add_argument("--b1", type=Path, required=True)
    parser.add_argument("--b2", type=Path)
    parser.add_argument("--a2", type=Path)
    parser.add_argument("--all-vs-teacher", type=Path)
    parser.add_argument("--cross-leg", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    args = parser.parse_args()
    full = args.b2 is not None or args.a2 is not None
    require(
        (args.b2 is None) == (args.a2 is None), "B2 and A2 must be supplied together"
    )
    validate_campaign_layout(
        a1=args.a1,
        b1=args.b1,
        b2=args.b2,
        a2=args.a2,
        out=args.out,
        markdown_out=args.markdown_out,
    )
    require(
        not full or (args.all_vs_teacher is not None and args.cross_leg is not None),
        "full ABBA requires combined exactness reports",
    )
    runs = {
        "A1": run_summary("A1-eager", args.a1, False),
        "B1": run_summary("B1-graph", args.b1, True),
    }
    pairs = {"B1_vs_A1": pair(runs["A1"], runs["B1"])}
    phase1 = {
        "a1_quality": runs["A1"]["quality_pass"],
        "b1_quality": runs["B1"]["quality_pass"],
        **pairs["B1_vs_A1"]["gates"],
    }
    result: dict[str, Any] = {
        "schema": "laguna-m8-graph-crossover-v1",
        "analysis_mode": "phase1_a1_b1",
        "runs": runs,
        "pairs": pairs,
        "phase1_gates": phase1,
        "phase1_pass": all(phase1.values()),
        "record_floor_tok_s_strictly_greater_than": RECORD_FLOOR,
    }
    if full:
        runs.update(
            {
                "B2": run_summary("B2-graph", args.b2, True),
                "A2": run_summary("A2-eager", args.a2, False),
            }
        )
        pairs["B2_vs_A2"] = pair(runs["A2"], runs["B2"])
        combined = bundle(
            args.all_vs_teacher, TEACHER, [r["bench_path"] for r in runs.values()]
        )
        cross = bundle(
            args.cross_leg,
            runs["A1"]["bench_path"],
            [
                runs["B1"]["bench_path"],
                runs["B2"]["bench_path"],
                runs["A2"]["bench_path"],
            ],
        )
        b_low, a_low = (
            min(runs["B1"]["headline_tok_s"], runs["B2"]["headline_tok_s"]),
            min(runs["A1"]["headline_tok_s"], runs["A2"]["headline_tok_s"]),
        )
        gates = {
            "phase1_pass": result["phase1_pass"],
            "b2_quality": runs["B2"]["quality_pass"],
            "a2_quality": runs["A2"]["quality_pass"],
            "combined_teacher_exactness": combined,
            "cross_leg_exactness": cross,
            **{f"b2_vs_a2_{k}": v for k, v in pairs["B2_vs_A2"]["gates"].items()},
            "min_b_strictly_beats_min_a": b_low > a_low,
        }
        causal = all(gates.values())
        record = causal and b_low > RECORD_FLOOR
        result.update(
            {
                "analysis_mode": "full_abba",
                "full_abba_gates": gates,
                "full_abba_causal_pass": causal,
                "candidate_lower_start_tok_s": b_low,
                "control_lower_start_tok_s": a_low,
                "strict_preregistered_record_pass": record,
                "disposition": "record_candidate"
                if record
                else (
                    "exact_reproducible_candidate_below_record_floor"
                    if causal
                    else "negative_or_inconclusive_stop"
                ),
            }
        )
    else:
        result["disposition"] = (
            "phase1_pass_continue_to_full_abba"
            if result["phase1_pass"]
            else "phase1_failed_stop"
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.write_text(
        "# Laguna M8 graph crossover\n\n- Disposition: `"
        + result["disposition"]
        + "`\n- Phase 1 pass: `"
        + str(result["phase1_pass"])
        + "`\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"schema": result["schema"], "disposition": result["disposition"]},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

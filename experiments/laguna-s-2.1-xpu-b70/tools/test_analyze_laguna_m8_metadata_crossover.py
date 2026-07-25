from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from analyze_laguna_m8_metadata_crossover import (
    GRAPH_TOPOLOGY,
    PRACTICAL_FLOOR,
    TEACHER,
    bundle,
    exact_checks,
    full_disposition,
    graph_log_checks,
    idle_interval_checks,
    pair,
    practical_floor_gates,
    validate_campaign_layout,
)


def test_graph_log_requires_all_four_distinct_capture_and_replay_ranks(
    tmp_path: Path,
) -> None:
    lines = []
    for action in ("Captured", "Replayed"):
        lines.extend(
            f"(Worker_TP{rank}_EP{rank}) {action} audited breakable cudagraph {GRAPH_TOPOLOGY}"
            for rank in range(4)
        )
    path = tmp_path / "server.log"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert all(graph_log_checks(path, True).values())
    path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    assert not graph_log_checks(path, True)["four_distinct_replays"]


def test_graph_log_rejects_capture_when_graph_is_declared_off(tmp_path: Path) -> None:
    path = tmp_path / "server.log"
    path.write_text(
        f"Captured audited breakable cudagraph {GRAPH_TOPOLOGY}\n", encoding="utf-8"
    )
    assert not graph_log_checks(path, False)["no_capture_on_eager"]


def test_exact_checks_requires_canonical_teacher_and_long_next_rollover(
    tmp_path: Path,
) -> None:
    bench = tmp_path / "bench.json"
    bench.write_text("{}", encoding="utf-8")
    candidate = str(bench.resolve())
    report = {
        "all_exact": True,
        "teacher": TEACHER,
        "candidates": [
            {
                "candidate": candidate,
                "comparison": {
                    "exact": True,
                    "exact_count": 13,
                    "total": 13,
                    "all_cached_zero": True,
                    "long_then_next": {"passed": True},
                    "rollover": {"count": 1, "exact_count": 1},
                },
            }
        ],
    }
    assert all(exact_checks(report, bench).values())
    report["candidates"][0]["comparison"]["rollover"]["exact_count"] = 0
    assert not exact_checks(report, bench)["rollover"]


def test_pair_enforces_all_preregistered_performance_gates() -> None:
    def run(
        name: str, speed: float, cycle: float, acceptance: float
    ) -> dict[str, object]:
        rows = [
            {"prompt_id": str(i), "prompt_sha256": f"h{i}", "tok_s": speed}
            for i in range(13)
        ]
        return {
            "name": name,
            "headline_tok_s": speed,
            "row_metrics": rows,
            "metrics": {
                "aggregate_cycle_ms": cycle,
                "speculation": {"acceptance_rate": acceptance},
            },
        }

    result = pair(run("A", 33.9, 10.0, 0.9), run("B", 34.1, 9.8, 0.9005))
    assert result["pass"] is True
    bad = pair(run("A", 33.9, 10.0, 0.9), run("B", 34.1, 9.8, 0.902))
    assert bad["gates"]["acceptance_rate_delta_at_most_0_001"] is False


def test_pair_rejects_prompt_reordering() -> None:
    control = {
        "headline_tok_s": 34.0,
        "row_metrics": [{"prompt_id": "a", "prompt_sha256": "x", "tok_s": 34.0}],
        "metrics": {
            "aggregate_cycle_ms": 10.0,
            "speculation": {"acceptance_rate": 0.9},
        },
    }
    candidate = {
        **control,
        "headline_tok_s": 35.0,
        "row_metrics": [{"prompt_id": "b", "prompt_sha256": "x", "tok_s": 35.0}],
    }
    with pytest.raises(ValueError, match="prompt identity"):
        pair(control, candidate)


def test_bundle_accepts_noncanonical_cross_leg_teacher(tmp_path: Path) -> None:
    teacher = tmp_path / "a1.json"
    candidates = [tmp_path / name for name in ("b1.json", "b2.json", "a2.json")]
    report = {
        "all_exact": True,
        "teacher": str(teacher),
        "candidates": [
            {
                "candidate": str(candidate),
                "comparison": {
                    "exact": True,
                    "exact_count": 13,
                    "total": 13,
                    "all_cached_zero": True,
                    "long_then_next": {"passed": True},
                    "rollover": {"count": 1, "exact_count": 1},
                },
            }
            for candidate in candidates
        ],
    }
    path = tmp_path / "cross.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    assert bundle(path, str(teacher), [str(candidate) for candidate in candidates])


def test_idle_interval_rejects_failed_snapshot(tmp_path: Path) -> None:
    idle = tmp_path / "idle-interval"
    idle.mkdir()
    start = datetime(2026, 7, 24, tzinfo=UTC)
    for phase in ("prestart", "poststop"):
        for index in range(13):
            payload = {
                "format": "laguna-m8-gather-sharded-operational-preflight-v2",
                "status": "passed",
                "observed_utc": (start + timedelta(seconds=5 * index)).isoformat(),
                "idle": {
                    "accepted_mode": "self_observer_rows",
                    "device_ids": [0, 1, 2, 3],
                    "row_count": 4,
                    "sanitized_payload": {
                        "device_util_by_proc_list": [
                            {"device_id": device, "process_name": "xpu-smi"}
                            for device in range(4)
                        ]
                    },
                },
            }
            (idle / f"{phase}-{index:02d}.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
    (idle / "summary.txt").write_text(
        "prestart elapsed_seconds=60 snapshots=13\n"
        "poststop elapsed_seconds=60 snapshots=13\n",
        encoding="utf-8",
    )
    assert all(idle_interval_checks(tmp_path).values())
    failed = idle / "prestart-06.json"
    payload = json.loads(failed.read_text(encoding="utf-8"))
    payload["status"] = "failed"
    failed.write_text(json.dumps(payload), encoding="utf-8")
    assert not idle_interval_checks(tmp_path)["all_idle_payloads_valid"]


def test_campaign_layout_rejects_cross_parent_pair(tmp_path: Path) -> None:
    campaign = tmp_path / "campaign"
    other = tmp_path / "other"
    with pytest.raises(ValueError, match="B1 is outside"):
        validate_campaign_layout(
            a1=campaign / "A1-graph-metadata-off",
            b1=other / "B1-graph-metadata-on",
            b2=None,
            a2=None,
            out=campaign / "phase1-analysis.json",
            markdown_out=campaign / "phase1-analysis.md",
        )


def test_practical_floor_is_strict_and_separate_from_causal_pass() -> None:
    runs = {
        "B1": {"headline_tok_s": PRACTICAL_FLOOR},
        "B2": {"headline_tok_s": PRACTICAL_FLOOR + 1.0},
    }
    gates = practical_floor_gates(runs)
    assert gates["b1_strictly_above_practical_floor"] is False
    assert gates["b2_strictly_above_practical_floor"] is True
    record, disposition = full_disposition(
        causal=True,
        promotion_gates=gates,
        candidate_low=PRACTICAL_FLOOR,
    )
    assert record is False
    assert disposition == "exact_reproducible_candidate_below_practical_floor"

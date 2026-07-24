from __future__ import annotations

import json
from pathlib import Path

import analyze_laguna_m8_replay_trace as analyzer


TRACE = """
=== API Timing Summary ===

             Total Execution Time (ns):             10000000
    Total API Time for L0 backend (ns):               100000

=== Device Timing Summary ===

                Total Execution Time (ns):           10000000
    Total Device Time for L0 backend (ns):             9000000

=== Kernel Submission Summary ===

                Total Execution Time (ns):           10000000
    Total Device Time for L0 backend (ns):             9000000
"""


def write_arm(root: Path, arm: str) -> None:
    directory = root / arm
    directory.mkdir()
    driver = {
        "schema": "laguna-m8-replay-trace-arm-v1",
        "status": "complete",
        "diagnostic_only": True,
        "not_benchmark_evidence": True,
        "single_generate_call": True,
        "fresh_process": True,
        "arm": arm,
        "session": f"LagunaReplay{'a' if arm == 'eager' else 'b'}" + "0" * 31,
        "cached_tokens": 0,
        "completion_tokens": 128,
        "prompt_sha256": "prompt",
        "prompt_tokens": 32,
        "token_ids": [1, 2, 3],
        "token_ids_sha256": "tokens",
        "text_sha256": "text",
        "finish_reason": "length",
        "generation_wall_ns": 20_000_000 if arm == "eager" else 10_000_000,
    }
    (directory / "driver.json").write_text(json.dumps(driver))
    for rank in range(4):
        (directory / f"unitrace.{100 + rank}").write_text(TRACE)
    stderr = f"[INFO] Session {driver['session']} is paused\n"
    stdout = ""
    if arm == "graph":
        topology = "BreakableCUDAGraphCapture(graphs=146, eager_breaks=145)"
        for rank in range(4):
            stdout += (
                f"Worker_TP{rank}_EP{rank} Captured audited breakable cudagraph "
                f"{topology}\n"
            )
            stdout += (
                f"Worker_TP{rank}_EP{rank} Replayed audited breakable cudagraph "
                f"{topology}\n"
            )
        stdout += "Resumed audited Laguna PTI session at first graph replay\n"
    (directory / "stderr.log").write_text(stderr)
    (directory / "stdout.log").write_text(stdout)


def test_section_total_reads_device_total() -> None:
    assert (
        analyzer.section_total(
            TRACE,
            "Device Timing Summary",
            "Total Device Time for L0 backend (ns)",
        )
        == 9_000_000
    )


def test_main_accepts_exact_four_rank_pair(tmp_path: Path, monkeypatch) -> None:
    write_arm(tmp_path, "eager")
    write_arm(tmp_path, "graph")
    output = tmp_path / "analysis.json"
    monkeypatch.setattr(
        analyzer,
        "parse_args",
        lambda: type("Args", (), {"run_dir": tmp_path, "out": output})(),
    )
    assert analyzer.main() == 0
    result = json.loads(output.read_text())
    assert result["bitwise_exact"] is True
    assert result["wall_speedup"] == 2.0
    assert result["arms"]["graph"]["device_l0_ns"] == [9_000_000] * 4

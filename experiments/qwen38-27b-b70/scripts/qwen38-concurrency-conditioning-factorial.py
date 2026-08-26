#!/usr/bin/env python3
"""Run and combine a fixed within-server concurrency-conditioning factorial."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path


PHASES = (
    ("c64_before", "64"),
    ("conditioning_ladder", "1,2,4,8,16,32"),
    ("c64_after_1", "64"),
    ("c64_after_2", "64"),
)


def option_value(argv: list[str], name: str) -> str:
    try:
        return argv[argv.index(name) + 1]
    except (ValueError, IndexError) as exc:
        raise SystemExit(f"required option missing: {name}") from exc


def replace_option(argv: list[str], name: str, value: str) -> list[str]:
    updated = list(argv)
    try:
        updated[updated.index(name) + 1] = value
    except (ValueError, IndexError) as exc:
        raise SystemExit(f"required option missing: {name}") from exc
    return updated


def main() -> int:
    argv = sys.argv[1:]
    requested_out = Path(option_value(argv, "--out"))
    phase_dir = requested_out.parent / "conditioning-phases"
    phase_dir.mkdir(parents=True, exist_ok=False)
    harness = Path(__file__).resolve().parents[3] / "scripts" / "bench-openai-concurrency-oracle.py"
    if not harness.is_file():
        raise SystemExit(f"base concurrency harness missing: {harness}")

    phase_results: list[tuple[str, dict]] = []
    for phase, concurrency in PHASES:
        phase_out = phase_dir / f"{phase}.json"
        phase_stdout = phase_dir / f"{phase}.stdout.txt"
        phase_argv = replace_option(argv, "--concurrency", concurrency)
        phase_argv = replace_option(phase_argv, "--out", str(phase_out))
        completed = subprocess.run(
            [sys.executable, str(harness), *phase_argv],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        phase_stdout.write_text(completed.stdout)
        print(completed.stdout, end="", flush=True)
        if completed.returncode != 0:
            raise SystemExit(
                f"conditioning phase {phase} failed with {completed.returncode}"
            )
        phase_results.append((phase, json.loads(phase_out.read_text())))

    combined = copy.deepcopy(phase_results[0][1])
    combined["schema"] = "neural.download.concurrency-conditioning-factorial.v1"
    combined["reporting_boundary"] = (
        "Within-one-server measured phases in fixed order; no interpolation or "
        "extrapolation. Every batch retains its raw output-isolation evidence."
    )
    combined["config"]["conditioning_factorial"] = [
        {"phase": phase, "concurrency": concurrency}
        for phase, concurrency in PHASES
    ]
    combined["phase_classifications"] = {
        phase: result["classification"] for phase, result in phase_results
    }
    combined["batches"] = []
    for phase, result in phase_results:
        for batch in result["batches"]:
            tagged = copy.deepcopy(batch)
            tagged["conditioning_phase"] = phase
            combined["batches"].append(tagged)

    all_isolated = all(
        result["classification"] != "measured-output-variant"
        for _, result in phase_results
    )
    combined["classification"] = (
        "output-isolation-qualified-shape-variant"
        if all_isolated
        else "measured-output-variant"
    )
    requested_out.write_text(json.dumps(combined, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "classification": combined["classification"],
                "output": str(requested_out),
                "batches": [
                    {
                        "phase": row["conditioning_phase"],
                        "concurrency": row["concurrency"],
                        "aggregate_tok_s_wall": row["aggregate_tok_s_wall"],
                    }
                    for row in combined["batches"]
                ],
            },
            indent=2,
        )
    )
    return 0 if all_isolated else 3


if __name__ == "__main__":
    raise SystemExit(main())

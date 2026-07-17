#!/usr/bin/env python3
"""Combine clean-process M-width component path results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PATHS = (
    "segmented_m2",
    "segmented_fixed_width",
    "m2_chunks",
    "fixed_width",
    "generic_fused",
)
REQUIRED_PATHS = PATHS[:2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = {
        name: json.loads((args.run_dir / f"{name}.json").read_text())
        for name in PATHS
    }
    identities = {
        (
            row["width"],
            row["world_size"],
            row["corpus"],
            tuple(rank["xpu_extension_sha256"] for rank in row["ranks"]),
        )
        for row in rows.values()
    }
    if len(identities) != 1:
        raise SystemExit("path result identities do not match")
    for name, row in rows.items():
        if row["path"] != name:
            raise SystemExit(f"{name}: embedded path is {row['path']}")

    medians = {name: row["max_rank_wall_ms_median"] for name, row in rows.items()}
    wide_collective_saving = medians["segmented_m2"] - medians["m2_chunks"]
    fixed_width_saving = (
        medians["segmented_m2"] - medians["segmented_fixed_width"]
    )
    required_exact = all(rows[name]["passed"] for name in REQUIRED_PATHS)
    admission_pass = required_exact and fixed_width_saving >= 0.5
    sample = rows["fixed_width"]
    result = {
        "classification": "deepseek_v4_row_tiled_real_m2_corpus_width_economics",
        "passed": admission_pass,
        "scope": "TP4 allreduce plus MHC component geometry; not endpoint throughput or acceptance",
        "run_dir": str(args.run_dir.resolve()),
        "corpus": sample["corpus"],
        "world_size": sample["world_size"],
        "width": sample["width"],
        "allreduces": sample["allreduces"],
        "mhc_boundaries": sample["mhc_boundaries"],
        "changed_eager_epochs": sample["changed_eager_epochs"],
        "exact_replays": sample["exact_replays"],
        "timed_replays": sample["timed_replays"],
        "path_passes": {name: row["passed"] for name, row in rows.items()},
        "path_medians_ms": medians,
        "wide_collective_diagnostic_saving_ms": wide_collective_saving,
        "wide_collective_exact": rows["m2_chunks"]["passed"],
        "fixed_width_mhc_saving_ms": fixed_width_saving,
        "fixed_width_mhc_admission_threshold_ms": 0.5,
        "fixed_width_mhc_admission_pass": admission_pass,
        "generic_fused_diagnostic_saving_ms": (
            medians["m2_chunks"] - medians["generic_fused"]
        ),
        "path_results": {name: str(args.run_dir / f"{name}.json") for name in PATHS},
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    args.output.write_text(rendered + "\n")
    print(rendered)
    return 0 if admission_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())

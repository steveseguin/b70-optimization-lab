#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
base_runner=${script_dir}/run-20260830-qwen38-q4km-tp2-wdc-feasibility-r1.sh

export CAMPAIGN=qwen38-q4km-tp2-wdc-feasibility-20260830-r2
export PREREG=${repo}/experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-tp2-wdc-feasibility-r2-prereg.json
export EXPECTED_MODEL_SHA256=31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34
export EXPECTED_BENCH_SHA256=c2d55d3c7d55f0f309bc381ca9ca35b0d57193b8d64f8c2fb4bd98e631bd7248
export EXPECTED_BACKEND_SHA256=72beceb1906a130c3f5d064fb68a844b792ecdc28d3230935cdea9be259f4daf
export EXPECTED_BENCH_IMPL_SHA256=4a7094e725a42c8425dbd5f48b2fd9c5e4dc7a5e84044801e7db10d879fbe5d6
export EXPECTED_LIBLLAMA_SHA256=fef127ab3ce7fa5d530ca641a4e618622ddda31c9d765b0efb7557742b7ed291
export EXPECTED_LIBGGML_SHA256=d81df5455db5a4c28452b82ed88149fa0e0b2cfef19191d4da0751de5875db4e
export EXPECTED_LIBBASE_SHA256=c02e31736ede0af9867afb89d4f234a9908cd8c419d0962addf7a4d98adb2e5d
export EXPECTED_LIBCPU_SHA256=14a864bb492541497ba201a6c8c2a7b0c3dee7ae19eb7f4eab18170ec9bc99ab
export EXPECTED_SOURCE_COMMIT=4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126
export EXPECTED_SOURCE_DIFF_SHA256=9cee85631ded5eca3dd4576100496f147468f69aa99e0df147f54c0f64f49926

run_arm() {
  local arm=$1 attempt=$2
  printf '\n=== %s attempt %s ===\n' "${arm}" "${attempt}"
  ARM=${arm} ATTEMPT=${attempt} "${base_runner}"
}

run_arm control 1
run_arm candidate 1
run_arm candidate 2
run_arm control 2

python3 - "${OUT_DIR:-/mnt/fast-ai/bench-results}" "${CAMPAIGN}" <<'PY'
import json
import pathlib
import statistics
import sys

root = pathlib.Path(sys.argv[1])
campaign = sys.argv[2]
values = {"control": [], "candidate": []}
for arm in values:
    for attempt in (1, 2):
        path = root / f"{campaign}-{arm}-attempt{attempt}" / "summary.json"
        values[arm].append(json.loads(path.read_text())["aggregate_speed_tg"])

medians = {arm: statistics.median(speeds) for arm, speeds in values.items()}
gain = (medians["candidate"] / medians["control"] - 1.0) * 100.0
summary = {
    "classification": "raw-engine-mechanism-evidence-only",
    "quality_qualified": False,
    "attempts": values,
    "medians": medians,
    "relative_improvement_percent": gain,
    "minimum_advance_percent": 5.0,
    "advance_to_http_quality_validation": gain >= 5.0,
}
summary_path = root / f"{campaign}-aggregate-summary.json"
summary_path.write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
PY

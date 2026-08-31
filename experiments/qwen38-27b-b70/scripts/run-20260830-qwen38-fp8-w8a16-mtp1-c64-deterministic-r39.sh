#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
runner=${script_dir}/run-20260830-qwen38-fp8-w8a16-mtp1-c64-deterministic-r39-arm.sh
campaign=qwen38-fp8-w8a16-mtp1-c64-deterministic-20260830-r39
out_parent=${OUT_DIR:-/mnt/fast-ai/bench-results}

env ARM=control ATTEMPT=A PILOT=1 OUT_DIR="${out_parent}" "${runner}"
oracle=${out_parent}/${campaign}-control-A/oracle-digests.json
oracle_sha=$(sha256sum "${oracle}" | awk '{print $1}')

for spec in 'control B' 'candidate A' 'candidate B'; do
  read -r arm attempt <<<"${spec}"
  env ARM="${arm}" ATTEMPT="${attempt}" PILOT=0 OUT_DIR="${out_parent}" \
    ORACLE_DIGESTS="${oracle}" "${runner}"
done

python3 - "${out_parent}" "${campaign}" "${oracle}" "${oracle_sha}" \
  "${repo}/experiments/qwen38-27b-b70/data/2026-08-30-qwen38-fp8-w8a16-mtp1-c64-deterministic-r39-prereg.json" <<'PY'
import datetime as dt
import hashlib
import json
import pathlib
import statistics
import sys

parent, campaign, oracle_path, oracle_sha, prereg_path = sys.argv[1:]
parent = pathlib.Path(parent)
arms = {}
for arm, attempts in (("control", ("A", "B")), ("candidate", ("A", "B"))):
    arms[arm] = {}
    for attempt in attempts:
        root = parent / f"{campaign}-{arm}-{attempt}"
        arms[arm][attempt] = json.loads((root / "summary.json").read_text())

control_rates = [arms["control"][key]["aggregate_tok_s_c64"] for key in ("A", "B")]
candidate_rates = [arms["candidate"][key]["aggregate_tok_s_c64"] for key in ("A", "B")]
all_passed = all(
    arms[arm][attempt]["quality_passed"]
    for arm in arms for attempt in arms[arm]
)
control_median = statistics.median(control_rates)
candidate_median = statistics.median(candidate_rates)
qualified = all_passed and candidate_median > control_median
result = {
    "schema": "neural.download.qwen38-fp8-w8a16-mtp1-c64-r39-result.v1",
    "created_utc": dt.datetime.now(dt.UTC).isoformat(),
    "campaign": campaign,
    "classification": "qualified" if qualified else "failed-closed",
    "all_correctness_gates_passed": all_passed,
    "control_rates_tok_s": control_rates,
    "control_median_tok_s": control_median,
    "candidate_rates_tok_s": candidate_rates,
    "candidate_median_tok_s": candidate_median,
    "candidate_gain_percent": (candidate_median / control_median - 1) * 100,
    "requested_875_tok_s_objective_achieved": qualified and candidate_median >= 875,
    "preferred_1000_tok_s_objective_achieved": qualified and candidate_median >= 1000,
    "oracle_path": oracle_path,
    "oracle_sha256": oracle_sha,
    "prereg_path": prereg_path,
    "prereg_sha256": hashlib.sha256(pathlib.Path(prereg_path).read_bytes()).hexdigest(),
    "arms": arms,
    "reporting_boundary": "Measured c64 only; no interpolation or extrapolation.",
}
out = parent / f"{campaign}-result.json"
out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps(result, indent=2, sort_keys=True))
if not qualified:
    raise SystemExit(3)
PY

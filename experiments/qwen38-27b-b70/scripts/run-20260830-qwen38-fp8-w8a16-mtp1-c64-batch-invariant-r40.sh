#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
runner=${script_dir}/run-20260830-qwen38-fp8-w8a16-mtp1-c64-deterministic-r39-arm.sh
campaign=${CAMPAIGN:-qwen38-fp8-w8a16-mtp1-c64-batch-invariant-20260830-r40}
prereg=${PREREG:-${repo}/experiments/qwen38-27b-b70/data/2026-08-30-qwen38-fp8-w8a16-mtp1-c64-batch-invariant-r40-prereg.json}
out_parent=${OUT_DIR:-/mnt/fast-ai/bench-results}
control_image=${CONTROL_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-collective-work-wait-r15}
control_image_id=${CONTROL_IMAGE_ID:-sha256:d19f802ba702a9cb94b155f807a4674a0100702aee838323372f740d7168e34e}
candidate_image=${CANDIDATE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-rms-serial-r31}
candidate_image_id=${CANDIDATE_IMAGE_ID:-sha256:ba42e928e69c60d1c9102df6ec1c0e998e9dd8463f74d5dc0a8b4bb45108fa9b}
compilation_config=${COMPILATION_CONFIG:-'{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1}'}
common=(
  CAMPAIGN="${campaign}"
  PREREG="${prereg}"
  OUT_DIR="${out_parent}"
  BATCH_INVARIANT=1
  RMSNORM_BATCH_INVARIANT=1
  GDN_SERIAL_EXACT=1
  CONTROL_IMAGE="${control_image}"
  CONTROL_IMAGE_ID="${control_image_id}"
  CANDIDATE_IMAGE="${candidate_image}"
  CANDIDATE_IMAGE_ID="${candidate_image_id}"
  COMPILATION_CONFIG="${compilation_config}"
)

env "${common[@]}" ARM=control ATTEMPT=A PILOT=1 "${runner}"
oracle=${out_parent}/${campaign}-control-A/oracle-digests.json
for spec in 'control B' 'candidate A' 'candidate B'; do
  read -r arm attempt <<<"${spec}"
  env "${common[@]}" ARM="${arm}" ATTEMPT="${attempt}" PILOT=0 \
    ORACLE_DIGESTS="${oracle}" "${runner}"
done

python3 - "${out_parent}" "${campaign}" "${oracle}" "${prereg}" <<'PY'
import datetime as dt
import hashlib
import json
import pathlib
import statistics
import sys

parent, campaign, oracle_path, prereg_path = sys.argv[1:]
parent = pathlib.Path(parent)
arms = {
    arm: {
        attempt: json.loads(
            (parent / f"{campaign}-{arm}-{attempt}" / "summary.json").read_text()
        )
        for attempt in ("A", "B")
    }
    for arm in ("control", "candidate")
}
control = [arms["control"][attempt]["aggregate_tok_s_c64"] for attempt in ("A", "B")]
candidate = [arms["candidate"][attempt]["aggregate_tok_s_c64"] for attempt in ("A", "B")]
control_median = statistics.median(control)
candidate_median = statistics.median(candidate)
all_passed = all(row["quality_passed"] for group in arms.values() for row in group.values())
qualified = all_passed and candidate_median > control_median
result = {
    "schema": "neural.download.qwen38-fp8-w8a16-mtp1-c64-batch-invariant-result.v1",
    "created_utc": dt.datetime.now(dt.UTC).isoformat(),
    "campaign": campaign,
    "classification": "qualified" if qualified else "failed-closed",
    "all_correctness_gates_passed": all_passed,
    "control_rates_tok_s": control,
    "control_median_tok_s": control_median,
    "candidate_rates_tok_s": candidate,
    "candidate_median_tok_s": candidate_median,
    "candidate_gain_percent": (candidate_median / control_median - 1) * 100,
    "requested_875_tok_s_objective_achieved": qualified and candidate_median >= 875,
    "preferred_1000_tok_s_objective_achieved": qualified and candidate_median >= 1000,
    "oracle_path": oracle_path,
    "oracle_sha256": hashlib.sha256(pathlib.Path(oracle_path).read_bytes()).hexdigest(),
    "prereg_path": prereg_path,
    "prereg_sha256": hashlib.sha256(pathlib.Path(prereg_path).read_bytes()).hexdigest(),
    "arms": arms,
    "reporting_boundary": "Measured c64 only; no interpolation or extrapolation."
}
out = parent / f"{campaign}-result.json"
out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps(result, indent=2, sort_keys=True))
if not qualified:
    raise SystemExit(3)
PY

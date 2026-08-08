#!/usr/bin/env bash
# Maintainer-corrected wrapper for the contributor's llama-benchy workflow.
set -euo pipefail

BASE_URL="${BASE_URL:?Set BASE_URL, preferably to a loopback endpoint}"
MODEL="${MODEL:?Set MODEL to the served model name}"
RESULTS_DIR="${RESULTS_DIR:?Set RESULTS_DIR to a fresh artifact directory}"
LLAMA_BENCHY="${LLAMA_BENCHY:-llama-benchy}"

[[ "${BASE_URL}" =~ ^http://(127\.0\.0\.1|localhost):([0-9]+)$ ]] || {
  echo "BASE_URL must be an HTTP loopback URL with an explicit port" >&2
  exit 2
}
endpoint_port="${BASH_REMATCH[2]}"
((endpoint_port >= 1024 && endpoint_port <= 65535)) || {
  echo "BASE_URL port must be between 1024 and 65535" >&2
  exit 2
}
[[ "${MODEL}" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.:/-]*$ ]] || {
  echo "MODEL contains unsupported characters" >&2
  exit 2
}
model_slug="${MODEL//\//_}"
model_slug="${model_slug//:/_}"

mkdir -p "${RESULTS_DIR}"
timestamp="$(date +%Y%m%d-%H%M%S)"
result_json="${RESULTS_DIR}/${model_slug}-${timestamp}.json"
result_csv="${RESULTS_DIR}/${model_slug}-${timestamp}.csv"
[[ ! -e "${result_json}" && ! -e "${result_csv}" ]] || {
  echo "Refusing to overwrite an existing benchmark artifact" >&2
  exit 2
}

"${LLAMA_BENCHY}" \
  --base-url "${BASE_URL%/}/v1" \
  --model "${MODEL}" \
  --latency-mode generation \
  --depth 0 4096 8192 16384 32768 \
  --pp 2048 \
  --tg 1024 \
  --runs 5 \
  --format json \
  --save-result "${result_json}"

python3 - "${result_json}" "${result_csv}" <<'PY'
import csv
import json
import sys

source, destination = sys.argv[1:]
with open(source, encoding="utf-8") as handle:
    rows = json.load(handle).get("benchmarks", [])
if not rows:
    raise SystemExit("No benchmarks found in JSON")
with open(destination, "w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
PY

printf 'JSON: %s\nCSV: %s\n' "${result_json}" "${result_csv}"

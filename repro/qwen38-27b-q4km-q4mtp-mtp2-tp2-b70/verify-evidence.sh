#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../.." && pwd)
cd "${repo}"
manifest="${repo}/experiments/qwen38-27b-b70/data/qwen38-q4km-q4mtp-tp2-mtp2-20260830/manifest.json"
attestation="${repo}/experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-promotion-attestation.json"
performance="${repo}/experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-replication-r2-result.json"
python3 "${repo}/experiments/qwen38-27b-b70/scripts/verify-20260830-qwen38-q4km-q4mtp-tp2-mtp2-archive.py" "${manifest}"
python3 - "${attestation}" "${performance}" <<'PY'
import sys
from pathlib import Path
from scripts.promotion_evidence import validate_promotion_attestation
validate_promotion_attestation(
    Path(sys.argv[1]), Path(sys.argv[2]),
    expected_model_revision="0669b98607d47046c7c2b3f801011d54a08cfccf",
    expected_runtime_revision="4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126",
)
print("PASS promotion-attestation")
PY

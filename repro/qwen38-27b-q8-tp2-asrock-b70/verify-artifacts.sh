#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
patch_artifact="${repo_root}/patches/qwen36-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-lab-tp2-conv-silu-l2-20260815.diff.gz.b64"
sg16_patch="${repo_root}/patches/qwen38-27b-q8-tp2-asrock-b70/recurrent-quad-sg16-20260817.diff"
summary="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-15-q8-tp2-transfer-summary.json"

patch_sha=$(base64 -d "${patch_artifact}" | gzip -dc | sha256sum | awk '{print $1}')
[[ "${patch_sha}" == c8ae065cabf9e7b7f6b6a224673498ddf82b07aeb1d16a33d341368b9b3234d7 ]]
sg16_patch_sha=$(sha256sum "${sg16_patch}" | awk '{print $1}')
[[ "${sg16_patch_sha}" == 05ce95e18a211deeb20348ad6a2ffd4ca2dee828d7692c4a026f055156e9c86c ]]
python3 - "${summary}" <<'PY'
import json
import sys
d = json.load(open(sys.argv[1]))
assert d["model"]["sha256"] == "f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8"
assert d["validity"]["optimized_gate_passed"]
assert d["validity"]["cached_tokens_all_zero"]
assert d["validity"]["complete_output_hashes_exact"] == "12/12"
assert abs(d["optimized"]["conventional_99_interval_median_tok_s"] - 36.772932224864405) < 1e-12
print("base and SG16 source patches, model identity, result, and quality gates passed")
PY

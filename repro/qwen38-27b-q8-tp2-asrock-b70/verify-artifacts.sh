#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
patch_artifact="${repo_root}/patches/qwen38-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-qwen38-q8-tp2-20260816.diff.gz.b64"
summary="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-15-q8-tp2-transfer-summary.json"

patch_sha=$(base64 -d "${patch_artifact}" | gzip -dc | sha256sum | awk '{print $1}')
[[ "${patch_sha}" == 642032df8459e05bbaea00c3ff5f7e93d657c995979164a85eb9262747fa6b1e ]]
python3 - "${summary}" <<'PY'
import json
import sys
d = json.load(open(sys.argv[1]))
assert d["model"]["sha256"] == "f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8"
assert d["validity"]["optimized_gate_passed"]
assert d["validity"]["cached_tokens_all_zero"]
assert d["validity"]["complete_output_hashes_exact"] == "12/12"
assert abs(d["optimized"]["conventional_99_interval_median_tok_s"] - 36.772932224864405) < 1e-12
print("source patch, model identity, result, and quality gates passed")
PY

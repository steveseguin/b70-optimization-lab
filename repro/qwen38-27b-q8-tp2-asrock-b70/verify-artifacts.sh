#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
patch_artifact="${repo_root}/patches/qwen36-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-lab-tp2-dp4a2-20260815.diff.gz.b64"
sg16_patch="${repo_root}/patches/qwen38-27b-q8-tp2-asrock-b70/recurrent-quad-sg16-20260817.diff"
sg24_patch="${repo_root}/patches/qwen38-27b-q8-tp2-asrock-b70/recurrent-quad-sg24-20260817.diff"
summary="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-15-q8-tp2-transfer-summary.json"
promotion="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-17-q8-dp4a2-sg24-accepted.json"

patch_sha=$(base64 -d "${patch_artifact}" | gzip -dc | sha256sum | awk '{print $1}')
[[ "${patch_sha}" == f21e9b557c3d024527ac98d5f189cf7ea72fa8c38a5faf2a22ee339fd1988998 ]]
sg16_patch_sha=$(sha256sum "${sg16_patch}" | awk '{print $1}')
[[ "${sg16_patch_sha}" == 05ce95e18a211deeb20348ad6a2ffd4ca2dee828d7692c4a026f055156e9c86c ]]
sg24_patch_sha=$(sha256sum "${sg24_patch}" | awk '{print $1}')
[[ "${sg24_patch_sha}" == 863ad19b3df13c9edd1d0d9b595c04a2baa92e67efc6df82cd9beb2beea54db4 ]]
python3 - "${summary}" "${promotion}" <<'PY'
import json
import sys
d = json.load(open(sys.argv[1]))
p = json.load(open(sys.argv[2]))
assert d["model"]["sha256"] == "f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8"
assert d["validity"]["optimized_gate_passed"]
assert d["validity"]["cached_tokens_all_zero"]
assert d["validity"]["complete_output_hashes_exact"] == "12/12"
assert abs(d["optimized"]["conventional_99_interval_median_tok_s"] - 36.772932224864405) < 1e-12
assert p["status"] == "accepted"
assert p["source"]["clean_patch_chain_byte_match"] == "20/20 modified files"
assert p["quality"]["pass_all"] and p["quality"]["baseline_match_all"]
assert p["quality"]["verify_mismatch"] == 0
assert abs(p["realistic_endpoint"]["pooled_pair_statistics"]["primary_median_delta_percent"] - 0.800826625570128) < 1e-12
print("DP4A2 base, SG16, and SG24 source patches, model identity, matched performance result, and quality gates passed")
PY

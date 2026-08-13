#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)

patch_artifact="${repo_root}/patches/qwen36-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-lab-tp2-20260813.diff.gz.b64"
result_artifact="${repo_root}/data/qwen36-q8-tp2-asrock-b70-20260813/conv-stateio-final-full512-realistic.json.gz.b64"

patch_sha=$(base64 -d "${patch_artifact}" | gzip -dc | sha256sum | awk '{print $1}')
result_sha=$(base64 -d "${result_artifact}" | gzip -dc | sha256sum | awk '{print $1}')

[[ "${patch_sha}" == 7856dd62f711fb36cb2ae59191717eb15c2967ff49eb609bda5f6eea218736bd ]]
[[ "${result_sha}" == aa726e686469e5a8cc6d441f4f83a093f2345e83fcec6d182f96356d5f735858 ]]

base64 -d "${result_artifact}" | gzip -dc | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["realistic_final_gate"]["passed"]
assert d["realistic_final_gate"]["cached_tokens_all_zero"]
assert d["fresh_response_validity"]["valid"]
assert len(d["rows"]) == 12
assert all(r["completion_tokens"] == 512 for r in d["rows"])
assert len(set(d["prompt_sha256s"])) == 12
print("artifact hashes and final quality gates passed")
'

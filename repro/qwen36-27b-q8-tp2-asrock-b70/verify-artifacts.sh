#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)

patch_artifact="${repo_root}/patches/qwen36-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-lab-tp2-20260813.diff.gz.b64"
result_artifact="${repo_root}/data/qwen36-q8-tp2-asrock-b70-20260813/tail-finalfresh-realistic512.json.gz.b64"
summary_artifact="${repo_root}/data/qwen36-q8-tp2-asrock-b70-20260813/summary.json"

patch_sha=$(base64 -d "${patch_artifact}" | gzip -dc | sha256sum | awk '{print $1}')
result_sha=$(base64 -d "${result_artifact}" | gzip -dc | sha256sum | awk '{print $1}')

[[ "${patch_sha}" == 710b8628f6c94025d9a0516f77bddeeebccdd27d5bd3ebc4f79d2e623b1dd6c7 ]]
[[ "${result_sha}" == d98a21f150dbb5b6461a0cc95d84d579cef36084d1f9ed3984d9827cfcf3dbc8 ]]

base64 -d "${result_artifact}" | gzip -dc | python3 -c '
import json, sys
d = json.load(sys.stdin)
s = json.load(open(sys.argv[1]))
assert d["realistic_final_gate"]["passed"]
assert d["realistic_final_gate"]["cached_tokens_all_zero"]
assert d["fresh_response_validity"]["valid"]
assert len(d["rows"]) == 12
assert all(r["completion_tokens"] == 512 for r in d["rows"])
assert len(set(d["prompt_sha256s"])) == 12
assert d["output_sha256s"] == s["output_sha256s"]
assert s["model"]["sha256"] == "73f8260284708ed78ae266df672288b6ad1f2c73ec7ffeb7514b5cecdba646c9"
assert s["runtime"]["source_patch_uncompressed_sha256"] == sys.argv[2]
assert s["evidence"]["raw_result_sha256"] == sys.argv[3]
assert abs(s["benchmark"]["conventional_99_interval_tok_s"]["median"] - 35.69922490372522) < 1e-12
print("patch, raw result, readable summary, and final quality gates passed")
' "${summary_artifact}" "${patch_sha}" "${result_sha}"

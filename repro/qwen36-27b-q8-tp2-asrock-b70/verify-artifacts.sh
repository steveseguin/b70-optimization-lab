#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)

patch_artifact="${repo_root}/patches/qwen36-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-lab-tp2-20260814.diff.gz.b64"
result_artifact="${repo_root}/data/qwen36-q8-tp2-asrock-b70-20260814/directq8-imrope-clean-full-realistic512.json.gz.b64"
summary_artifact="${repo_root}/data/qwen36-q8-tp2-asrock-b70-20260814/summary.json"

patch_sha=$(base64 -d "${patch_artifact}" | gzip -dc | sha256sum | awk '{print $1}')
result_sha=$(base64 -d "${result_artifact}" | gzip -dc | sha256sum | awk '{print $1}')

[[ "${patch_sha}" == c917fcbf01b5af3ed45bb19532cfa0f337066b1330ffde6765564918e7a8d772 ]]
[[ "${result_sha}" == 9ff5d4ce56a2c7fabb78b743b7b38b7f80833418ceedc64de90360a0448f5c01 ]]

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
assert s["runtime"]["new_runtime_doors"] == {
    "GGML_SYCL_COMM_DIRECT_Q8": 2,
    "GGML_SYCL_FUSED_ROPE_SET_ROWS": 1,
}
assert abs(s["benchmark"]["conventional_99_interval_tok_s"]["median"] - 35.83221316356445) < 1e-12
print("patch, raw result, readable summary, and final quality gates passed")
' "${summary_artifact}" "${patch_sha}" "${result_sha}"

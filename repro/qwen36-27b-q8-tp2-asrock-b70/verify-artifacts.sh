#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)

patch_artifact="${repo_root}/patches/qwen36-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-lab-tp2-conv-silu-l2-20260815.diff.gz.b64"
result_artifact="${repo_root}/data/qwen36-q8-tp2-asrock-b70-20260814/conv-silu-l2-full-realistic512.json.gz.b64"
control_artifact="${repo_root}/data/qwen36-q8-tp2-asrock-b70-20260814/reduce-vec4-clean-control-full-realistic512.json.gz.b64"
summary_artifact="${repo_root}/data/qwen36-q8-tp2-asrock-b70-20260814/summary.json"

patch_sha=$(base64 -d "${patch_artifact}" | gzip -dc | sha256sum | awk '{print $1}')
result_sha=$(base64 -d "${result_artifact}" | gzip -dc | sha256sum | awk '{print $1}')
control_sha=$(base64 -d "${control_artifact}" | gzip -dc | sha256sum | awk '{print $1}')

[[ "${patch_sha}" == c8ae065cabf9e7b7f6b6a224673498ddf82b07aeb1d16a33d341368b9b3234d7 ]]
[[ "${result_sha}" == 04721d27e64b4dbfed9510bb64285092c464c885751437a3c63ac70087f70ab2 ]]
[[ "${control_sha}" == f0b41b32444a433b9cb0a93c995620f27a9aa9ea86da4d3ec6c97b6365f2e67d ]]

base64 -d "${control_artifact}" | gzip -dc | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["realistic_final_gate"]["passed"]
assert d["realistic_final_gate"]["cached_tokens_all_zero"]
assert d["fresh_response_validity"]["valid"]
assert len(d["rows"]) == 12
assert all(r["completion_tokens"] == 512 for r in d["rows"])
assert len(set(d["prompt_sha256s"])) == 12
'

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
    "GGML_SYCL_COMM_REDUCE_VEC4": 1,
    "GGML_SYCL_FUSED_QK_NORM_ROPE": 1,
    "GGML_SYCL_FUSED_CONV_SILU_L2": 1,
}
assert abs(s["benchmark"]["conventional_99_interval_tok_s"]["median"] - 36.347289793336984) < 1e-12
assert s["evidence"]["same_binary_control_sha256"] == sys.argv[4]
print("patch, candidate/control raw results, readable summary, and final quality gates passed")
' "${summary_artifact}" "${patch_sha}" "${result_sha}" "${control_sha}"

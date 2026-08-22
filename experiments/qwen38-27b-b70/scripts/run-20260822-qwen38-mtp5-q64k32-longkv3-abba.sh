#!/usr/bin/env bash
set -euo pipefail

# Clean-environment launcher for the Q64xK32 LONG-KV A-B-B-A campaign.
# Derived from the endpoint6 driver. Same sealed contract and stages, with
# two campaign-specific changes: (1) the 25-row long-KV suite (tiers 8/8/9,
# metric window at KV ~1300/1600/1900) replaces the short suite; (2) bench
# requests add ignore_eos:true through the sealed REQUEST_EXTRA_JSON channel
# (bench-only; the quality battery hardcodes its own kwargs), which makes
# the strict 100-event window structurally present on every row and removes
# the prompt-6 stochastic early-EOS failure mode that closed the endpoint
# campaign. Post-arm gates verify ignore_eos engagement mechanically:
# identity request_extra_json must match, all 25 rows must report exactly
# 512 completion tokens, zero cached tokens, and in-band prompt tokens.

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
driver=$(realpath -- "$0")
action=${1:-}

case "$action" in
  check|a1|b1|b2|a2) ;;
  *) printf 'usage: %s check|a1|b1|b2|a2\n' "$0" >&2; exit 2 ;;
esac

raw=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70
cache=/mnt/usb-models/llm-runtime/vllm-cache/qwen38-postrecovery-marginfree-mtp5-20260820
sealed="$raw/qwen38-postrecovery-marginfree-mtp5-25-spec-c-20260820/compile-cache-output-manifest.json"
suite="$raw/qwen38-longkv3-q64k32-suite-20260822/validation-suite.json"
quality_baseline="$raw/qwen38-marginfree-targetoracle-25-a-20260820/data/quality.json"
target_bench="$raw/qwen38-marginfree-targetoracle-25-a-20260820/data/bench.json"
runner="$repo/experiments/qwen36-27b-autoround-int4-b70/validation-20260815/run-arm.sh"
model=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan
base_stage=/home/steve/src/vllm-xpu-kernels
stock_stage=/home/steve/staged-xpu-commitfix-graphfa-composite-20260820
candidate_stage=/home/steve/qwen38-m6-head256-q64k32-attn-override-20260821-r3/runtime
oneccl=/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public
stock_graph_manifest="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/staged-xpu-commitfix-graphfa-composite-20260820.graph.sha256"
candidate_graph_manifest=/home/steve/qwen38-m6-head256-q64k32-attn-override-20260821-r3/qwen38-m6-head256-q64k32-r3-candidate.graph.sha256
model_manifest="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json"
model_verifier="$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py"
sealed_checker="$repo/repro/qwen38-27b-autoround-int4-b70/scripts/check-tp2-sealed-gates.py"

cache_manifest_sha=f3582440de9b252cc738648aa5b690fd324bec9afeb8d89e4b73d295071cb0ff
suite_sha=9a5c4a4e54762aa22e772fb5c6e5fd170c3428e97556f7565a2b1cd8af6d2a6e
quality_sha=45424f1d2dcbfda0a5ed75552cf799cac0e8fb6b8c5e1ddf2aba540b95c77e95
model_manifest_sha=731d851b39d37f3d58c5a74ad6a7cd3ade1c9e8543ef1612a5d55131ff8331b8
verifier_sha=5bca853ae644099cb18c58b458dd04dfcc0844d7644f074c4350539504d80ce9
stock_graph_manifest_sha=47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da
candidate_graph_manifest_sha=0642e0290a8c97f2b29b826ab3b8aee693d444df09cea7048d5d6f8da0fd98a9
target_bench_sha=045fd8b4fc9f1eda3bbc778e4b88a6ad7407ff4a50be879dc4e9780b37e0d6e8
native_sha=4dd336013d155aab004fb1c916118957cb9349b491938da65769f2d8af18ffb0
core_sha=5717476461048b5056a92926f2a52d73c121f69bdc75de22fd52720fb65b3007
moe_sha=ea4c20a8dff49fc07fd799d5a2a47e8b24266a256425b41e337f852492ee3c1b
fa_sha=33938cdd2436684dcb76108a4db43e4ab0314406ad537fcd3732a005f7d23739
stock_device_sha=604f1b328870f2c41ef1d05c4d6016c34d222033d905877b0f9a2ff0c66b2a0c
candidate_device_sha=979e91c1f11d9e6ede77c494803889e9f47dd881c2d02e1c290c5246c0dbb616
stock_dep_sha=3cbd3ed2ff51a477e6746b3e5860c070d093fd2d29b0b7a58e6dd081e9ad1289
interface_sha=869c79f5f678252c341cfb8fb5cf9ee34f95c3d2debf4d169b759510da432480
policy_marker='VLLM_XPU_FA2_M6_HEAD256_Q64K32_POLICY engaged'

# longkv3: fresh design succeeding the closed longkv1/2 series. Two
# changes from longkv2, both forced by its closure evidence: (1) tiers
# refit under the sealed max_model_len=2048 wall (targets 1250/1375/1500,
# +-35 bands, max prompt 1497 => 2009 total with the 512 window; metric
# windows at KV ~1300/1425/1550); (2) BOTH arms run with
# VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=0 — the chunkdiag-established
# mitigation for the multi-chunk persistent-scratch corruption (d5 green
# at dose 8; dose 25 here is gated by a1's own quality battery). The
# tested lever remains the Q64xK32 policy alone.
arm_label() { printf 'qwen38-q64k32-longkv3-%s-20260822' "$1"; }
request_extra_json='{"chat_template_kwargs":{"enable_thinking":false},"ignore_eos":true}'
arm_root_for() { printf '%s/%s' "$raw" "$(arm_label "$1")"; }

case "$action" in
  a1|a2) role=control ;;
  b1|b2) role=candidate ;;
  check) role=control ;;
esac
case "$action" in
  a1) predecessor=; quality=1 ;;
  b1) predecessor=a1; quality=1 ;;
  b2) predecessor=b1; quality=0 ;;
  a2) predecessor=b2; quality=0 ;;
  check) predecessor=; quality=0 ;;
esac

if [[ "$role" == "candidate" ]]; then
  stage=$candidate_stage
  graph_manifest=$candidate_graph_manifest
  graph_manifest_sha=$candidate_graph_manifest_sha
  device_sha=$candidate_device_sha
  policy=1
else
  stage=$stock_stage
  graph_manifest=$stock_graph_manifest
  graph_manifest_sha=$stock_graph_manifest_sha
  device_sha=$stock_device_sha
  policy=0
fi

verify_sha() {
  local path=$1 expected=$2 label=$3 actual
  if [[ ! -f "$path" ]]; then
    printf '%s is missing: %s\n' "$label" "$path" >&2
    exit 3
  fi
  actual=$(sha256sum -- "$path" | awk '{print $1}')
  if [[ "$actual" != "$expected" ]]; then
    printf '%s SHA mismatch: actual=%s expected=%s\n' \
      "$label" "$actual" "$expected" >&2
    exit 3
  fi
}

if [[ "$(git -C "$repo" branch --show-current)" != "main" ]]; then
  printf 'campaign launcher requires the main branch\n' >&2
  exit 3
fi
if [[ -n "$(git -C "$repo" status --porcelain --untracked-files=normal)" ]]; then
  printf 'campaign launcher requires a clean repository\n' >&2
  exit 3
fi
if [[ "$(git -C "$repo" rev-parse HEAD)" != "$(git -C "$repo" rev-parse origin/main)" ]]; then
  printf 'campaign launcher requires local main == origin/main\n' >&2
  exit 3
fi

verify_sha "$sealed" "$cache_manifest_sha" sealed-cache-manifest
verify_sha "$suite" "$suite_sha" validation-suite
verify_sha "$quality_baseline" "$quality_sha" quality-baseline
verify_sha "$target_bench" "$target_bench_sha" target-token-benchmark
verify_sha "$model_manifest" "$model_manifest_sha" model-manifest
verify_sha "$model_verifier" "$verifier_sha" model-verifier

verify_stage_tree() {
  local root=$1 dsha=$2 mpath=$3 msha=$4 tag=$5
  verify_sha "$mpath" "$msha" "$tag-graph-manifest"
  verify_sha "$root/vllm_xpu_kernels/_xpu_C.abi3.so" "$native_sha" "$tag-native-extension"
  verify_sha "$root/vllm_xpu_kernels/_C.abi3.so" "$core_sha" "$tag-core-extension"
  verify_sha "$root/vllm_xpu_kernels/_moe_C.abi3.so" "$moe_sha" "$tag-moe-extension"
  verify_sha "$root/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" "$fa_sha" "$tag-fa-extension"
  verify_sha "$root/vllm_xpu_kernels/libattn_kernels_xe_2.so" "$dsha" "$tag-device-library"
  verify_sha "$root/vllm_xpu_kernels/libattn_stock.so" "$stock_dep_sha" "$tag-stock-dependency"
  verify_sha "$root/vllm_xpu_kernels/flash_attn_interface.py" "$interface_sha" "$tag-python-interface"
}

verify_stage_tree "$stock_stage" "$stock_device_sha" \
  "$stock_graph_manifest" "$stock_graph_manifest_sha" stock
verify_stage_tree "$candidate_stage" "$candidate_device_sha" \
  "$candidate_graph_manifest" "$candidate_graph_manifest_sha" candidate

"$repo/scripts/canonical-tree-manifest.py" verify \
  --root "$cache/torch_compile_cache" \
  --manifest "$sealed" >/dev/null

if [[ "$action" == "check" ]]; then
  printf 'Q64xK32 endpoint campaign preflight passed\n'
  exit 0
fi

repo_head=$(git -C "$repo" rev-parse HEAD)
checker_args_for() {
  local graph_sha=$1
  printf '%s\n' \
    --expected-namespace b99160ae76 \
    --expected-outer-role backbone --expected-outer-role eagle_head \
    --expected-outer-loads 2 \
    --expected-aot-key dc9285c2585e6107e3a84c9b8339e3865a2930a77e21245f0d2e76b04b7d0ee6 \
    --expected-aot-key fc5b3e495f3d13b586de6fb38840cdf8917f296f8a22b4133caadfa24369ce62 \
    --expected-aot-loads 4 --expected-pad-markers 2 \
    --expected-suite-sha256 "$suite_sha" \
    --expected-model-dir "$model" \
    --expected-model-manifest-sha256 "$model_manifest_sha" \
    --expected-verify-script-sha256 "$verifier_sha" \
    --expected-cache-root "$cache" \
    --expected-cache-manifest-sha256 "$cache_manifest_sha" \
    --expected-graph-manifest-sha256 "$graph_sha" \
    --expected-native-sha256 "$native_sha" \
    --expected-core-sha256 "$core_sha" \
    --expected-moe-sha256 "$moe_sha" \
    --expected-fa-sha256 "$fa_sha" \
    --expected-repo-head "$repo_head" \
    --expected-quality-baseline-sha256 "$quality_sha"
}

label=$(arm_label "$action")
arm_root=$(arm_root_for "$action")
parity_peer=
parity_peer_sha=

if [[ -n "$predecessor" ]]; then
  prev_root=$(arm_root_for "$predecessor")
  prev_role=control
  [[ "$predecessor" == b1 || "$predecessor" == b2 ]] && prev_role=candidate
  if [[ "$prev_role" == "candidate" ]]; then
    prev_graph_manifest_sha=$candidate_graph_manifest_sha
  else
    prev_graph_manifest_sha=$stock_graph_manifest_sha
  fi
  if [[ ! -f "$prev_root/runner.exit-code" \
    || "$(tr -d '\n' < "$prev_root/runner.exit-code")" != "0" ]]; then
    printf 'arm %s did not finish with runner exit code 0\n' "$predecessor" >&2
    exit 4
  fi
  if ! jq -e '.status == "passed"' "$prev_root/tp2-sealed-gates.json" >/dev/null; then
    printf 'arm %s did not pass the sealed TP2 gate\n' "$predecessor" >&2
    exit 4
  fi
  if [[ ! -f "$prev_root/SHA256SUMS.pre-manifest" ]] \
    || ! sha256sum -c "$prev_root/SHA256SUMS.pre-manifest" >/dev/null; then
    printf 'arm %s artifact checksum set is missing or no longer exact\n' \
      "$predecessor" >&2
    exit 4
  fi
  prev_identity="$prev_root/run/identity.env"
  current_runner_sha=$(sha256sum -- "$runner" | awk '{print $1}')
  current_checker_sha=$(sha256sum -- "$sealed_checker" | awk '{print $1}')
  recorded_runner_sha=$(awk -F= \
    '$1 == "run_arm_script_sha256" {print substr($0, index($0, "=") + 1)}' \
    "$prev_identity")
  recorded_checker_sha=$(awk -F= \
    '$1 == "sealed_gate_checker_sha256" {print substr($0, index($0, "=") + 1)}' \
    "$prev_identity")
  recorded_driver_sha=$(awk -F= \
    '$1 == "campaign_driver_sha256" {print substr($0, index($0, "=") + 1)}' \
    "$prev_identity")
  if [[ "$recorded_runner_sha" != "$current_runner_sha" \
    || "$recorded_checker_sha" != "$current_checker_sha" \
    || "$recorded_driver_sha" != "$(sha256sum -- "$driver" | awk '{print $1}')" ]]; then
    printf 'arm %s was not produced by the current runner/checker/driver bytes\n' \
      "$predecessor" >&2
    exit 4
  fi
  # Quality-gated sequencing: b1 requires a1's quality pass; b2 requires b1's.
  prev_quality_flag=()
  if [[ "$action" == b1 || "$action" == b2 ]]; then
    prev_quality_flag=(--require-quality-pass)
  fi
  # The predecessor must also have passed its own role's marker gate; a
  # sealed-passing root with the wrong engagement count is a campaign stop.
  prev_server_log="$prev_root/run/server.stdout.log"
  if [[ ! -f "$prev_server_log" ]]; then
    printf 'arm %s server log is missing for marker regate\n' "$predecessor" >&2
    exit 4
  fi
  prev_marker_count=$(grep -Fc "$policy_marker" "$prev_server_log" || true)
  if [[ "$prev_role" == "candidate" && "$prev_marker_count" != "2" ]]; then
    printf 'arm %s candidate marker count %s != 2\n' \
      "$predecessor" "$prev_marker_count" >&2
    exit 4
  fi
  if [[ "$prev_role" == "control" && "$prev_marker_count" != "0" ]]; then
    printf 'arm %s control shows %s engagement markers\n' \
      "$predecessor" "$prev_marker_count" >&2
    exit 4
  fi
  mapfile -t prev_checker_args < <(checker_args_for "$prev_graph_manifest_sha")
  prev_recheck=$(mktemp /tmp/qwen38-q64k32-endpoint-recheck.XXXXXX.json)
  trap 'rm -f -- "$prev_recheck"' EXIT
  if ! /home/steve/.venvs/vllm-xpu/bin/python \
    "$sealed_checker" arm \
    --arm-root "$prev_root" "${prev_checker_args[@]}" "${prev_quality_flag[@]}" \
    --output "$prev_recheck"; then
    printf 'arm %s no longer passes the sealed campaign contract\n' \
      "$predecessor" >&2
    exit 4
  fi
  rm -f -- "$prev_recheck"
  trap - EXIT
  # Report-only exactness accounting vs a1 happens in this driver after the
  # arm completes; the runner receives no parity peer because sealed mode
  # would enforce full 25/25 token parity, which this campaign reports only.
  a1_bench="$(arm_root_for a1)/data/bench.json"
  a1_bench_sha=$(jq -r '.benchmark.sha256 // empty' \
    "$(arm_root_for a1)/tp2-sealed-gates.json")
  if [[ ! -f "$a1_bench" || ! "$a1_bench_sha" =~ ^[0-9a-f]{64}$ \
    || "$(sha256sum -- "$a1_bench" | awk '{print $1}')" != "$a1_bench_sha" ]]; then
    printf 'arm a1 benchmark is missing or altered\n' >&2
    exit 4
  fi
fi

if [[ -e "$arm_root" ]]; then
  printf 'refusing existing arm root: %s\n' "$arm_root" >&2
  exit 4
fi

driver_sha=$(sha256sum -- "$driver" | awk '{print $1}')
empty_diff=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
compilation_config='{"cache_dir":"/mnt/usb-models/llm-runtime/vllm-cache/qwen38-postrecovery-marginfree-mtp5-20260820/torch_compile_cache/b99160ae76","use_inductor_graph_partition":true,"pass_config":{"fuse_rope_kvcache_cat_mla":false},"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[6],"max_cudagraph_capture_size":6}'
aot_keys=dc9285c2585e6107e3a84c9b8339e3865a2930a77e21245f0d2e76b04b7d0ee6,fc5b3e495f3d13b586de6fb38840cdf8917f296f8a22b4133caadfa24369ce62

launch_env=(
  HOME=/home/steve
  USER=steve
  LOGNAME=steve
  SHELL=/bin/bash
  LANG=C.UTF-8
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
  BASE_STAGE="$base_stage"
  STAGE="$stage"
  ONECCL_INSTALL_DIR="$oneccl"
  MODEL_DIR="$model"
  LABEL="$label"
  VALIDATION_CAMPAIGN_DRIVER="$driver"
  VALIDATION_CAMPAIGN_DRIVER_SHA256="$driver_sha"
  VALIDATION_MODEL_MANIFEST="$model_manifest"
  VALIDATION_MODEL_VERIFY_SCRIPT="$model_verifier"
  VALIDATION_GRAPH_STAGE_MANIFEST="$graph_manifest"
  VALIDATION_FA_DEVICE_LIBRARY_SHA256="$device_sha"
  VALIDATION_FA2_M6_HEAD256_Q64K32_POLICY="$policy"
  VALIDATION_REQUIRE_XPU_MODULES_UNDER_STAGE=1
  VALIDATION_EXPECT_XPU_COUNT=4
  VALIDATION_EXPECT_VLLM_VERSION=0.20.2rc1.dev13+g9557d9108.d20260620
  VALIDATION_EXPECT_VLLM_DIFF_SHA256="$empty_diff"
  VALIDATION_EXPECT_KERNELS_DIFF_SHA256="$empty_diff"
  VALIDATION_EXPECT_REPO_HEAD="$repo_head"
  VALIDATION_HF_HOME=/mnt/usb-models/llm-cache/hf
  VALIDATION_TENSOR_PARALLEL_SIZE=2
  VALIDATION_PYTHONHASHSEED=0
  VALIDATION_NUM_SPECULATIVE_TOKENS=5
  VALIDATION_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=0
  VALIDATION_GDN_SPEC_PERSISTENT_SCRATCH=0
  VALIDATION_GDN_CAPTURE_NATIVE_SPEC=1
  VALIDATION_DDTREE_FULL_GRAPH=0
  VALIDATION_DDTREE_CAPTURE_GDN_CORE=0
  VALIDATION_ONEDNN_INT4_COMPLETION_BARRIER=1
  VALIDATION_ONEDNN_INT4_INPUT_DEPENDENCY=1
  VALIDATION_ONEDNN_INT4_INPUT_DEPENDENCY_SCOPE=all_target
  VALIDATION_ONEDNN_INT4_DETERMINISM_PAD=1
  VALIDATION_ONEDNN_INT8_COMPLETION_BARRIER=1
  VALIDATION_ONEDNN_INT8_INPUT_DEPENDENCY=1
  VALIDATION_LM_HEAD_INT8=1
  VALIDATION_DETERMINISTIC_GREEDY_MARGIN=0
  VALIDATION_DRAFT_LM_HEAD_INT4_FALLBACK_MARGIN=0
  VALIDATION_ENABLE_XPU_GRAPH=1
  'VALIDATION_VLLM_EXTRA_ARGS=--dtype float16'
  VALIDATION_VLLM_CACHE_ROOT="$cache"
  VALIDATION_COMPILE_CACHE_MANIFEST="$sealed"
  VALIDATION_COMPILATION_CONFIG_OVERRIDE="$compilation_config"
  VALIDATION_SUITE_OVERRIDE="$suite"
  VALIDATION_RUN_SMOKE=1
  VALIDATION_RUN_BENCH=1
  VALIDATION_RUN_QUALITY="$quality"
  VALIDATION_BENCH_MAX_TOKENS=512
  VALIDATION_BENCH_METRIC_TOKENS=100
  VALIDATION_REQUEST_EXTRA_JSON="$request_extra_json"
  VALIDATION_ENABLE_PACKET_TRACE=0
  VALIDATION_ENABLE_LAYER_TRACE=0
  VALIDATION_REQUIRE_TP2_SEALED_GATES=1
  VALIDATION_REQUIRE_COMPILE_CACHE_UNCHANGED=1
  VALIDATION_REQUIRE_NO_COMPILE_CACHE_WRITES=1
  VALIDATION_EXPECT_ONEDNN_INT4_DETERMINISM_PAD_MARKERS=2
  VALIDATION_EXPECT_COMPILE_CACHE_DIRECT_LOADS=2
  VALIDATION_EXPECT_AOT_DIRECT_LOADS=4
  VALIDATION_EXPECT_COMPILE_CACHE_NAMESPACE=b99160ae76
  VALIDATION_EXPECT_COMPILE_CACHE_OUTER_ROLES=backbone,eagle_head
  VALIDATION_EXPECT_AOT_CACHE_KEYS="$aot_keys"
  VALIDATION_EXPECT_SUITE_SHA256="$suite_sha"
  VALIDATION_EXPECT_QUALITY_BASELINE_SHA256="$quality_sha"
  VALIDATION_EXPECT_PARITY_PEER_BENCH_SHA256=
  VALIDATION_EXPECT_TARGET_TOKEN_BENCH_SHA256="$target_bench_sha"
  VALIDATION_EXPECT_MODEL_DIR="$model"
  VALIDATION_EXPECT_MODEL_MANIFEST_SHA256="$model_manifest_sha"
  VALIDATION_EXPECT_VERIFY_SCRIPT_SHA256="$verifier_sha"
  VALIDATION_EXPECT_CACHE_ROOT="$cache"
  VALIDATION_EXPECT_CACHE_MANIFEST_SHA256="$cache_manifest_sha"
  VALIDATION_EXPECT_GRAPH_MANIFEST_SHA256="$graph_manifest_sha"
  VALIDATION_EXPECT_NATIVE_SHA256="$native_sha"
  VALIDATION_EXPECT_CORE_SHA256="$core_sha"
  VALIDATION_EXPECT_MOE_SHA256="$moe_sha"
  VALIDATION_EXPECT_FA_SHA256="$fa_sha"
  VALIDATION_PARITY_PEER_BENCH=
  VALIDATION_TARGET_TOKEN_BENCH="$target_bench"
  VALIDATION_REQUIRE_TARGET_TOKEN_PARITY=0
)

set +e
env -i "${launch_env[@]}" \
  "$runner" spec-native-partition-exact-native 2,3 "$arm_root" \
  "$quality_baseline"
runner_rc=$?
set -e

server_log="$arm_root/run/server.stdout.log"
if [[ "$runner_rc" == "0" ]]; then
  if [[ ! -f "$server_log" ]]; then
    printf 'server log missing for marker gate: %s\n' "$server_log" >&2
    exit 5
  fi
  marker_count=$(grep -Fc "$policy_marker" "$server_log" || true)
  if [[ "$role" == "candidate" && "$marker_count" != "2" ]]; then
    printf 'candidate policy marker count %s != 2\n' "$marker_count" >&2
    exit 5
  fi
  if [[ "$role" == "control" && "$marker_count" != "0" ]]; then
    printf 'control shows %s policy engagement markers\n' "$marker_count" >&2
    exit 5
  fi
  # Long-KV campaign gates: the ignore_eos request contract must be recorded
  # in the arm identity and mechanically visible in the benchmark rows.
  recorded_extra=$(awk -F= \
    '$1 == "request_extra_json" {print substr($0, index($0, "=") + 1)}' \
    "$arm_root/run/identity.env")
  if [[ "$recorded_extra" != "$request_extra_json" ]]; then
    printf 'arm identity request_extra_json does not match the campaign value\n' >&2
    exit 5
  fi
  if ! jq -e '(.rows | length == 25)
      and (.rows | all(.completion_tokens == 512))
      and (.rows | all(.cached_tokens == 0))' \
      "$arm_root/data/bench.json" >/dev/null; then
    printf 'long-KV bench rows violate the 25x512-completion/0-cached contract\n' >&2
    exit 5
  fi
  if ! jq -e --slurpfile s "$suite" \
      '[.rows[].prompt_tokens] as $p
       | [$s[0].prompts[].prompt_token_band] as $b
       | [range(0; 25)] | all(. as $i
         | $p[$i] >= $b[$i][0] and $p[$i] <= $b[$i][1])' \
      "$arm_root/data/bench.json" >/dev/null; then
    printf 'long-KV bench prompt tokens left their frozen per-row bands\n' >&2
    exit 5
  fi
  printf 'arm %s complete: role=%s marker_count=%s longkv gates passed\n' \
    "$action" "$role" "$marker_count"
  if [[ -n "$predecessor" ]]; then
    parity=$(jq -n --slurpfile a "$a1_bench" --slurpfile b "$arm_root/data/bench.json" \
      '[($a[0].output_sha256s), ($b[0].output_sha256s)] | transpose | map(select(.[0] == .[1])) | length')
    printf 'report-only exact-output parity vs a1: %s/25\n' "$parity"
  fi
fi
exit "$runner_rc"

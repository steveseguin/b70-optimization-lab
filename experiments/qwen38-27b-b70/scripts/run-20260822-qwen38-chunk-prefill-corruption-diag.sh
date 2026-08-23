#!/usr/bin/env bash
set -euo pipefail

# Chunked-prefill corruption diagnostic (report-only, incumbent stock stage).
# Motivated by longkv2-a1: after this lane's first-ever multi-chunk prefills
# (prompts ~1250 tokens vs max_num_batched_tokens=1024), the stock control's
# quality long-context needle probe degenerated to 'B70_QWEN3!!!!...'. The
# positive control is already on record (endpoint5-a1: identical stack, 25
# single-chunk rows, needle green). This driver runs single independent
# arms on the incumbent stock stage with the sealed record gates OFF but
# every cache-protection and identity input still verified, and reads its
# evidence from data/quality.json and data/bench.json rather than the
# runner exit code:
#   d2 - one 2-chunk row (longkv tier1-row1) then the quality battery.
#        Needle FAIL => a single multi-chunk request corrupts cross-request
#        state. Needle PASS => dose-dependence, escalate to d4.
#   d4 - the eight tier1 2-chunk rows (full longkv suite truncated by the
#        bench naturally at row 9's 400) is NOT used; d4 instead reruns d2's
#        row with a separately built 8-row suite if and only if d2 passes.

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
driver=$(realpath -- "$0")
action=${1:-}

case "$action" in
  check|d2|d3|d6|d7|d4|d5) ;;
  *) printf 'usage: %s check|d2|d3|d6|d7|d4|d5\n' "$0" >&2; exit 2 ;;
esac

raw=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70
cache=/mnt/usb-models/llm-runtime/vllm-cache/qwen38-postrecovery-marginfree-mtp5-20260820
sealed="$raw/qwen38-postrecovery-marginfree-mtp5-25-spec-c-20260820/compile-cache-output-manifest.json"
suite="$raw/qwen38-longkv-chunk-diag-suite-20260822/validation-suite.json"
if [[ "${1:-}" == d4 || "${1:-}" == d5 ]]; then
  suite="$raw/qwen38-longkv-chunk-diag-d4-suite-20260822/validation-suite.json"
elif [[ "${1:-}" == d3 ]]; then
  suite="$raw/qwen38-longkv-chunk-diag-d3-4row-suite-20260822/validation-suite.json"
elif [[ "${1:-}" == d6 ]]; then
  suite="$raw/qwen38-longkv-chunk-diag-d6-6row-suite-20260822/validation-suite.json"
elif [[ "${1:-}" == d7 ]]; then
  suite="$raw/qwen38-longkv-chunk-diag-d7-7row-suite-20260822/validation-suite.json"
fi
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
suite_sha=0b66d5a6711a981480f09ba5956042a391da3082d3eb470d091fc89f2a37c6fc
if [[ "${1:-}" == d4 || "${1:-}" == d5 ]]; then
  suite_sha=6e51726f56bbb99ce86e2cf95f4e5d22ed4c141ce3a546d508cc03ae6fb37b6a
elif [[ "${1:-}" == d3 ]]; then
  suite_sha=6eafd43627337f698b5e662e197827993215ba578e7b9379161e6cd2ed229db4
elif [[ "${1:-}" == d6 ]]; then
  suite_sha=16fec1abab2c85ac2c621c28fb6c582381b81ee357c1bf3152d1f2df4f4c81d1
elif [[ "${1:-}" == d7 ]]; then
  suite_sha=28849c558c569dcf1eeaf314c5db2ea8f3e3e855c69e17b65cb26c6cadfa36dd
fi
# d5: identical exposure to d4 with the GDN spec persistent scratch OFF -
# a runtime allocation-strategy door (per-call scratch instead of a
# capture-time persistent pool), same compiled graphs and cache identity.
gdn_spec_persistent_scratch=1
if [[ "${1:-}" == d5 ]]; then
  gdn_spec_persistent_scratch=0
fi
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

# CHUNKDIAG_STAMP overrides the arm-date suffix for later reproduction runs
arm_label() { printf 'qwen38-chunkdiag-%s-%s' "$1" "${CHUNKDIAG_STAMP:-20260822}"; }
request_extra_json='{"chat_template_kwargs":{"enable_thinking":false},"ignore_eos":true}'
arm_root_for() { printf '%s/%s' "$raw" "$(arm_label "$1")"; }

role=control
predecessor=
quality=1

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
  VALIDATION_GDN_SPEC_PERSISTENT_SCRATCH="$gdn_spec_persistent_scratch"
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
  VALIDATION_REQUIRE_TP2_SEALED_GATES=0
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

# Diagnostic evidence capture: the finding lives in quality.json and
# bench.json, not the runner exit code (a needle failure makes the runner
# exit nonzero by design). Infra failure = no quality evidence.
server_log="$arm_root/run/server.stdout.log"
quality_json="$arm_root/data/quality.json"
bench_json="$arm_root/data/bench.json"
if [[ ! -f "$quality_json" ]]; then
  printf 'DIAG INFRA FAILURE: no quality evidence (runner rc=%s)\n' \
    "$runner_rc" >&2
  exit "$runner_rc"
fi
marker_count=$(grep -Fc "$policy_marker" "$server_log" || true)
printf 'diagnostic arm %s: stock stage, policy markers=%s (expect 0)\n' \
  "$action" "$marker_count"
if [[ -f "$bench_json" ]]; then
  jq -r '.rows[] | "bench row \(.prompt_id): prompt_tokens=\(.prompt_tokens) completion_tokens=\(.completion_tokens) cached=\(.cached_tokens) conv=\(.tok_s_1_100_intervals_after_ttft) preview=\(.text_preview | tostring | .[0:120])"' \
    "$bench_json"
else
  printf 'bench.json missing (bench rc nonzero before write)\n'
fi
jq -r '.long_context_case | "needle pass=\(.pass) prompt_tokens=\(.usage.prompt_tokens) content=\(.content | tostring | .[0:80])"' \
  "$quality_json"
jq -r '"quality exact_ok=\(.exact.exact_ok // .exact_ok) repeat_pass=\(.repeat_pass) baseline_match_all=\(.baseline_match_all)"' \
  "$quality_json" 2>/dev/null || true
printf 'diagnostic evidence captured (runner rc=%s)\n' "$runner_rc"
exit 0

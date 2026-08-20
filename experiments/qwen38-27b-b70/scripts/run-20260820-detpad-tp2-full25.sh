#!/usr/bin/env bash
set -euo pipefail

# Clean-environment launcher for the post-recovery Qwen3.8 composite-runtime
# TP2 full-25 validation pair. Arm B is refused until arm A passes every
# sealed-cache, engagement, freshness, and quality gate.

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
driver=$(realpath -- "$0")
action=${1:-}

if [[ "$action" != "check" && "$action" != "a" && "$action" != "b" ]]; then
  printf 'usage: %s check|a|b\n' "$0" >&2
  exit 2
fi

raw=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70
cache=/mnt/usb-models/llm-runtime/vllm-cache/qwen38-postrecovery-marginfree-mtp5-20260820
sealed="$raw/qwen38-postrecovery-marginfree-mtp5-25-spec-c-20260820/compile-cache-output-manifest.json"
suite="$raw/qwen38-postrecovery-marginfree-mtp5-25-spec-b-20260820/validation-suite.json"
quality_baseline="$raw/qwen38-marginfree-targetoracle-25-a-20260820/data/quality.json"
target_bench="$raw/qwen38-marginfree-targetoracle-25-a-20260820/data/bench.json"
arm_a_label=qwen38-detpad-composite4dd-marginfree-mtp5-25-spec-a2-20260820
arm_b_label=qwen38-detpad-composite4dd-marginfree-mtp5-25-spec-b2-20260820
arm_a="$raw/$arm_a_label"
arm_b="$raw/$arm_b_label"
runner="$repo/experiments/qwen36-27b-autoround-int4-b70/validation-20260815/run-arm.sh"
model=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan
base_stage=/home/steve/src/vllm-xpu-kernels
stage=/home/steve/staged-xpu-commitfix-graphfa-composite-20260820
oneccl=/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public
graph_manifest="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/staged-xpu-commitfix-graphfa-composite-20260820.graph.sha256"
model_manifest="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json"
model_verifier="$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py"
sealed_checker="$repo/repro/qwen38-27b-autoround-int4-b70/scripts/check-tp2-sealed-gates.py"
cache_manifest_sha=f3582440de9b252cc738648aa5b690fd324bec9afeb8d89e4b73d295071cb0ff
suite_sha=292dea6aaf60f53067fb63c9bc5aba15bd1c6e71c2601693e6750239edf9fa0c
quality_sha=45424f1d2dcbfda0a5ed75552cf799cac0e8fb6b8c5e1ddf2aba540b95c77e95
model_manifest_sha=731d851b39d37f3d58c5a74ad6a7cd3ade1c9e8543ef1612a5d55131ff8331b8
verifier_sha=5bca853ae644099cb18c58b458dd04dfcc0844d7644f074c4350539504d80ce9
graph_manifest_sha=47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da
target_bench_sha=045fd8b4fc9f1eda3bbc778e4b88a6ad7407ff4a50be879dc4e9780b37e0d6e8
native_sha=4dd336013d155aab004fb1c916118957cb9349b491938da65769f2d8af18ffb0
core_sha=5717476461048b5056a92926f2a52d73c121f69bdc75de22fd52720fb65b3007
moe_sha=ea4c20a8dff49fc07fd799d5a2a47e8b24266a256425b41e337f852492ee3c1b
fa_sha=33938cdd2436684dcb76108a4db43e4ab0314406ad537fcd3732a005f7d23739

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

verify_sha "$sealed" \
  "$cache_manifest_sha" \
  sealed-cache-manifest
verify_sha "$suite" \
  "$suite_sha" \
  validation-suite
verify_sha "$quality_baseline" \
  "$quality_sha" \
  quality-baseline
verify_sha "$target_bench" \
  "$target_bench_sha" \
  target-token-benchmark
verify_sha "$graph_manifest" \
  "$graph_manifest_sha" \
  composite-graph-manifest
verify_sha "$model_manifest" "$model_manifest_sha" model-manifest
verify_sha "$model_verifier" "$verifier_sha" model-verifier
verify_sha "$stage/vllm_xpu_kernels/_xpu_C.abi3.so" "$native_sha" native-extension
verify_sha "$stage/vllm_xpu_kernels/_C.abi3.so" "$core_sha" core-extension
verify_sha "$stage/vllm_xpu_kernels/_moe_C.abi3.so" "$moe_sha" moe-extension
verify_sha "$stage/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" "$fa_sha" fa-extension

"$repo/scripts/canonical-tree-manifest.py" verify \
  --root "$cache/torch_compile_cache" \
  --manifest "$sealed" >/dev/null

if [[ "$action" == "check" ]]; then
  printf 'sealed TP2 campaign preflight passed\n'
  exit 0
fi

repo_head=$(git -C "$repo" rev-parse HEAD)
checker_args=(
  --expected-namespace b99160ae76
  --expected-outer-role backbone --expected-outer-role eagle_head
  --expected-outer-loads 2
  --expected-aot-key dc9285c2585e6107e3a84c9b8339e3865a2930a77e21245f0d2e76b04b7d0ee6
  --expected-aot-key fc5b3e495f3d13b586de6fb38840cdf8917f296f8a22b4133caadfa24369ce62
  --expected-aot-loads 4 --expected-pad-markers 2
  --expected-suite-sha256 "$suite_sha"
  --expected-model-dir "$model"
  --expected-model-manifest-sha256 "$model_manifest_sha"
  --expected-verify-script-sha256 "$verifier_sha"
  --expected-cache-root "$cache"
  --expected-cache-manifest-sha256 "$cache_manifest_sha"
  --expected-graph-manifest-sha256 "$graph_manifest_sha"
  --expected-native-sha256 "$native_sha"
  --expected-core-sha256 "$core_sha"
  --expected-moe-sha256 "$moe_sha"
  --expected-fa-sha256 "$fa_sha"
  --expected-repo-head "$repo_head"
  --expected-quality-baseline-sha256 "$quality_sha"
)

if [[ "$action" == "a" ]]; then
  label=$arm_a_label
  arm_root=$arm_a
  quality=1
  parity_peer=
  parity_peer_sha=
else
  label=$arm_b_label
  arm_root=$arm_b
  quality=0
  parity_peer="$arm_a/data/bench.json"
  if [[ ! -f "$arm_a/runner.exit-code" \
    || "$(tr -d '\n' < "$arm_a/runner.exit-code")" != "0" ]]; then
    printf 'arm A did not finish with runner exit code 0\n' >&2
    exit 4
  fi
  if ! jq -e '.status == "passed"' "$arm_a/tp2-sealed-gates.json" \
    >/dev/null; then
    printf 'arm A did not pass the sealed TP2 gate\n' >&2
    exit 4
  fi
  if [[ ! -f "$parity_peer" ]]; then
    printf 'arm A benchmark is missing: %s\n' "$parity_peer" >&2
    exit 4
  fi
  if [[ ! -f "$arm_a/SHA256SUMS.pre-manifest" ]] \
    || ! sha256sum -c "$arm_a/SHA256SUMS.pre-manifest" >/dev/null; then
    printf 'arm A artifact checksum set is missing or no longer exact\n' >&2
    exit 4
  fi
  parity_peer_sha=$(jq -r '.benchmark.sha256 // empty' \
    "$arm_a/tp2-sealed-gates.json")
  if [[ ! "$parity_peer_sha" =~ ^[0-9a-f]{64}$ \
    || "$(sha256sum -- "$parity_peer" | awk '{print $1}')" \
      != "$parity_peer_sha" ]]; then
    printf 'arm A benchmark no longer matches its original sealed SHA\n' >&2
    exit 4
  fi
  a_identity="$arm_a/run/identity.env"
  current_runner_sha=$(sha256sum -- "$runner" | awk '{print $1}')
  current_checker_sha=$(sha256sum -- "$sealed_checker" | awk '{print $1}')
  recorded_runner_sha=$(awk -F= \
    '$1 == "run_arm_script_sha256" {print substr($0, index($0, "=") + 1)}' \
    "$a_identity")
  recorded_checker_sha=$(awk -F= \
    '$1 == "sealed_gate_checker_sha256" {print substr($0, index($0, "=") + 1)}' \
    "$a_identity")
  recorded_driver_sha=$(awk -F= \
    '$1 == "campaign_driver_sha256" {print substr($0, index($0, "=") + 1)}' \
    "$a_identity")
  if [[ "$recorded_runner_sha" != "$current_runner_sha" \
    || "$recorded_checker_sha" != "$current_checker_sha" \
    || "$recorded_driver_sha" != "$(sha256sum -- "$driver" | awk '{print $1}')" ]]; then
    printf 'arm A was not produced by the current runner/checker/driver bytes\n' >&2
    exit 4
  fi
  a_recheck=$(mktemp /tmp/qwen38-detpad-tp2-a-recheck.XXXXXX.json)
  trap 'rm -f -- "$a_recheck"' EXIT
  if ! /home/steve/.venvs/vllm-xpu/bin/python \
    "$sealed_checker" arm \
    --arm-root "$arm_a" "${checker_args[@]}" --require-quality-pass \
    --output "$a_recheck"; then
    printf 'arm A no longer passes the current sealed campaign contract\n' >&2
    exit 4
  fi
  rm -f -- "$a_recheck"
  trap - EXIT
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
  VALIDATION_GDN_SPEC_PERSISTENT_SCRATCH=1
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
  VALIDATION_EXPECT_SUITE_SHA256=292dea6aaf60f53067fb63c9bc5aba15bd1c6e71c2601693e6750239edf9fa0c
  VALIDATION_EXPECT_QUALITY_BASELINE_SHA256="$quality_sha"
  VALIDATION_EXPECT_PARITY_PEER_BENCH_SHA256="$parity_peer_sha"
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
  VALIDATION_PARITY_PEER_BENCH="$parity_peer"
  VALIDATION_TARGET_TOKEN_BENCH="$target_bench"
  VALIDATION_REQUIRE_TARGET_TOKEN_PARITY=0
)

exec env -i "${launch_env[@]}" \
  "$runner" spec-native-partition-exact-native 2,3 "$arm_root" \
  "$quality_baseline"

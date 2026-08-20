#!/usr/bin/env bash
set -euo pipefail

# Two-arm full-25 target/verifier request-selected replay diagnostic. T1 is
# quality-on. T2 requires an independently supplied T1 checksum-manifest SHA
# and exact T2/T1 token-array parity. Target A and B2 remain report-only.

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
driver=$(realpath -- "$0")
action=${1:-}
t1_checksum_manifest_expected=${2:-}

if [[ "$action" != "check" && "$action" != "t1" && "$action" != "t2" ]] \
  || { [[ "$action" == "t2" ]] \
    && { [[ $# -ne 2 ]] \
      || [[ ! "$t1_checksum_manifest_expected" =~ ^[0-9a-f]{64}$ ]]; }; } \
  || { [[ "$action" != "t2" ]] && [[ $# -ne 1 ]]; }; then
  printf 'usage: %s check | t1 | t2 T1_CHECKSUM_MANIFEST_SHA256\n' "$0" >&2
  exit 2
fi

raw=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70
cache=/mnt/usb-models/llm-runtime/vllm-cache/qwen38-postrecovery-marginfree-mtp5-20260820
sealed="$raw/qwen38-postrecovery-marginfree-mtp5-25-spec-c-20260820/compile-cache-output-manifest.json"
suite="$raw/qwen38-postrecovery-marginfree-mtp5-25-spec-b-20260820/validation-suite.json"
target="$raw/qwen38-marginfree-targetoracle-25-a-20260820"
b2="$raw/qwen38-detpad-composite4dd-marginfree-mtp5-25-spec-b2-20260820"
quality_baseline="$target/data/quality.json"
target_bench="$target/data/bench.json"
b2_bench="$b2/data/bench.json"
t1_label=qwen38-detpad-composite4dd-marginfree-mtp5-25-target-request-replay-bypass-t1-20260820
t2_label=qwen38-detpad-composite4dd-marginfree-mtp5-25-target-request-replay-bypass-t2-20260820
t1="$raw/$t1_label"
t2="$raw/$t2_label"
runner="$repo/experiments/qwen36-27b-autoround-int4-b70/validation-20260815/run-arm.sh"
model=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan
base_stage=/home/steve/src/vllm-xpu-kernels
stage=/home/steve/staged-xpu-commitfix-graphfa-composite-20260820
oneccl=/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public
vllm_source=/home/steve/src/vllm
vllm_marker_patch="$repo/patches/qwen38-27b-autoround-int4-b70/vllm-target-verifier-request-replay-bypass-marker-20260820.patch"
graph_manifest="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/staged-xpu-commitfix-graphfa-composite-20260820.graph.sha256"
model_manifest="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json"
model_verifier="$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py"
sealed_checker="$repo/repro/qwen38-27b-autoround-int4-b70/scripts/check-tp2-sealed-gates.py"
common_runner="$repo/experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh"
top_wrapper="$repo/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-fullgraph-transaction-candidate.sh"
serve_runner="$repo/experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh"
raw_gdn_compare="$repo/experiments/qwen38-27b-b70/data/2026-08-20-native-gdn-prefill-main-compare.json"

cache_manifest_sha=f3582440de9b252cc738648aa5b690fd324bec9afeb8d89e4b73d295071cb0ff
suite_sha=292dea6aaf60f53067fb63c9bc5aba15bd1c6e71c2601693e6750239edf9fa0c
quality_sha=45424f1d2dcbfda0a5ed75552cf799cac0e8fb6b8c5e1ddf2aba540b95c77e95
target_bench_sha=045fd8b4fc9f1eda3bbc778e4b88a6ad7407ff4a50be879dc4e9780b37e0d6e8
b2_bench_sha=96933a8211867479410375aaad7bd96bfb9f97d0edafc12af80dc9963805e721
target_checksum_manifest_sha=c71641eb785ba36a04209e5ab1e676a15ea0bf44be4c02faa8b73fa12a6b166e
b2_checksum_manifest_sha=e7726d02dd467442b03749e885bda619838c89451149d0dad979c0b290858d30
raw_gdn_compare_sha=61b9f0031e153d4841b139263d8a7afbef6004b8a8da3491affcf8688c329d1d
model_manifest_sha=731d851b39d37f3d58c5a74ad6a7cd3ade1c9e8543ef1612a5d55131ff8331b8
verifier_sha=5bca853ae644099cb18c58b458dd04dfcc0844d7644f074c4350539504d80ce9
graph_manifest_sha=47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da
native_sha=4dd336013d155aab004fb1c916118957cb9349b491938da65769f2d8af18ffb0
core_sha=5717476461048b5056a92926f2a52d73c121f69bdc75de22fd52720fb65b3007
moe_sha=ea4c20a8dff49fc07fd799d5a2a47e8b24266a256425b41e337f852492ee3c1b
fa_sha=33938cdd2436684dcb76108a4db43e4ab0314406ad537fcd3732a005f7d23739
vllm_head=44fc8fde09fc311d3099dab10366b672d9142ea4
vllm_diff_sha=4193f05e8f255cf07de81360eff031fdb2e468218c2660850d69c9f750369683
vllm_marker_patch_sha=e2185720388a3f92533e41224ecf9cfa0509a49c45f12f1a10f62a8debdef4ea
run_arm_sha=c9e1b2df20321d21b3c19286179c808a3af31dd326704f2f2d82d22dd61d5d85
checker_sha=58fd6ae654909c4109e4730732380adcbc8cc2c1ac927689c84ad6118361cc91
common_runner_sha=d2e1c996b23bfde0b2c9d4d6a0c15d390d5dfe02b1f51081e0e6f5e33f4d407e
top_wrapper_sha=991e21c1ddea6f0d3a044adaac78dca993f78bfd999819b7beb06e70ecd3e343
serve_runner_sha=f1d1503a4a1676eff7d61823a0cca66d1830a015446dc30058c3176d309c6dea

verify_sha() {
  local path=$1 expected=$2 description=$3 actual
  if [[ ! -f "$path" ]]; then
    printf '%s is missing: %s\n' "$description" "$path" >&2
    exit 3
  fi
  actual=$(sha256sum -- "$path" | awk '{print $1}')
  if [[ "$actual" != "$expected" ]]; then
    printf '%s SHA mismatch: actual=%s expected=%s\n' \
      "$description" "$actual" "$expected" >&2
    exit 3
  fi
}

if [[ "$(git -C "$repo" branch --show-current)" != "main" ]]; then
  printf 'target request replay-bypass launcher requires main\n' >&2
  exit 3
fi
if [[ -n "$(git -C "$repo" status --porcelain --untracked-files=normal)" ]]; then
  printf 'target request replay-bypass launcher requires a clean repository\n' >&2
  exit 3
fi
if [[ "$(git -C "$repo" rev-parse HEAD)" \
  != "$(git -C "$repo" rev-parse origin/main)" ]]; then
  printf 'target request replay-bypass launcher requires local main == origin/main\n' >&2
  exit 3
fi
if [[ "$(git -C "$vllm_source" rev-parse HEAD)" != "$vllm_head" \
  || "$(git -C "$vllm_source" status --porcelain --untracked-files=normal)" \
    != " M vllm/v1/worker/gpu_model_runner.py" \
  || "$(git -C "$vllm_source" diff --binary | sha256sum | awk '{print $1}')" \
    != "$vllm_diff_sha" ]]; then
  printf 'vLLM source is not the exact pinned marker-only identity\n' >&2
  exit 3
fi

verify_sha "$vllm_marker_patch" "$vllm_marker_patch_sha" vllm-marker-patch
if ! git -C "$vllm_source" apply --check --unidiff-zero --cached \
  "$vllm_marker_patch" \
  || ! git -C "$vllm_source" apply --check --unidiff-zero --reverse \
    "$vllm_marker_patch"; then
  printf 'vLLM marker patch does not reconstruct the exact live source delta\n' >&2
  exit 3
fi
verify_sha "$sealed" "$cache_manifest_sha" sealed-cache-manifest
verify_sha "$suite" "$suite_sha" validation-suite
verify_sha "$quality_baseline" "$quality_sha" quality-baseline
verify_sha "$target_bench" "$target_bench_sha" target-report-only-benchmark
verify_sha "$b2_bench" "$b2_bench_sha" b2-report-only-benchmark
verify_sha "$target/SHA256SUMS.pre-manifest" \
  "$target_checksum_manifest_sha" target-checksum-manifest
verify_sha "$b2/SHA256SUMS.pre-manifest" \
  "$b2_checksum_manifest_sha" b2-checksum-manifest
verify_sha "$raw_gdn_compare" "$raw_gdn_compare_sha" native-gdn-main-compare
verify_sha "$graph_manifest" "$graph_manifest_sha" composite-graph-manifest
verify_sha "$model_manifest" "$model_manifest_sha" model-manifest
verify_sha "$model_verifier" "$verifier_sha" model-verifier
verify_sha "$runner" "$run_arm_sha" arm-runner
verify_sha "$sealed_checker" "$checker_sha" sealed-checker
verify_sha "$common_runner" "$common_runner_sha" common-runner
verify_sha "$top_wrapper" "$top_wrapper_sha" top-candidate-wrapper
verify_sha "$serve_runner" "$serve_runner_sha" serve-runner
verify_sha "$stage/vllm_xpu_kernels/_xpu_C.abi3.so" "$native_sha" native-extension
verify_sha "$stage/vllm_xpu_kernels/_C.abi3.so" "$core_sha" core-extension
verify_sha "$stage/vllm_xpu_kernels/_moe_C.abi3.so" "$moe_sha" moe-extension
verify_sha "$stage/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" "$fa_sha" fa-extension

for reference in "$target" "$b2"; do
  if ! (cd "$reference" && sha256sum -c SHA256SUMS.pre-manifest >/dev/null); then
    printf 'immutable report-only reference checksum set failed: %s\n' \
      "$reference" >&2
    exit 3
  fi
done
if ! jq -e \
  '.status == "pass" and .valid == true
   and .summary.native_call_count == 12288
   and .summary.result_file_count == 8
   and .summary.aggregate_case_count == 48
   and .summary.pass_all == true
   and .summary.identity_equal == true
   and .summary.all_individual_results_passed == true
   and .summary.all_cross_process_reference_digests_equal == true' \
  "$raw_gdn_compare" >/dev/null; then
  printf 'native-GDN main comparison no longer proves its frozen negative result\n' >&2
  exit 3
fi
if [[ "$(tr -d '\n' < "$b2/runner.exit-code")" != "14" ]] \
  || ! jq -e '.status == "passed" and (.errors | length == 0)' \
    "$b2/tp2-sealed-gates.json" >/dev/null; then
  printf 'B2 no longer passes its sealed arm gate with recorded parity divergence\n' >&2
  exit 3
fi
"$repo/scripts/canonical-tree-manifest.py" verify \
  --root "$cache/torch_compile_cache" --manifest "$sealed" >/dev/null

if [[ "$action" == "check" ]]; then
  printf 'sealed target request replay-bypass preflight passed\n'
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
  --expected-sync-after-model-forward 0
  --expected-disable-spec-decode-cudagraph-replay 0
  --expected-decode-cudagraph-replay-eager-every-n-requests 1
  --expected-vllm-diff-sha256 "$vllm_diff_sha"
  --expected-report-only-b2-bench-sha256 "$b2_bench_sha"
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

if [[ "$action" == "t1" ]]; then
  label=$t1_label
  arm_root=$t1
  quality=1
  peer_bench=
  peer_sha=
else
  label=$t2_label
  arm_root=$t2
  quality=0
  peer_bench="$t1/data/bench.json"
  verify_sha "$t1/SHA256SUMS.pre-manifest" \
    "$t1_checksum_manifest_expected" t1-checksum-manifest
  if [[ ! -f "$t1/runner.exit-code" \
    || "$(tr -d '\n' < "$t1/runner.exit-code")" != "0" \
    || ! -f "$peer_bench" ]] \
    || ! (cd "$t1" && sha256sum -c SHA256SUMS.pre-manifest >/dev/null); then
    printf 'T1 did not complete its sealed quality-on arm\n' >&2
    exit 4
  fi
  t1_identity="$t1/run/identity.env"
  peer_sha=$(jq -r '.benchmark.sha256 // empty' "$t1/tp2-sealed-gates.json")
  if [[ ! "$peer_sha" =~ ^[0-9a-f]{64}$ \
    || "$(sha256sum -- "$peer_bench" | awk '{print $1}')" != "$peer_sha" \
    || "$(awk -F= '$1 == "run_arm_script_sha256" {print $2}' "$t1_identity")" \
      != "$run_arm_sha" \
    || "$(awk -F= '$1 == "sealed_gate_checker_sha256" {print $2}' "$t1_identity")" \
      != "$checker_sha" \
    || "$(awk -F= '$1 == "campaign_driver_sha256" {print $2}' "$t1_identity")" \
      != "$(sha256sum -- "$driver" | awk '{print $1}')" \
    || "$(awk -F= '$1 == "decode_cudagraph_replay_eager_every_n_requests" {print $2}' "$t1_identity")" \
      != "1" \
    || "$(awk -F= '$1 == "expected_decode_cudagraph_replay_eager_every_n_requests" {print $2}' "$t1_identity")" \
      != "1" \
    || -n "$(awk -F= '$1 == "disable_spec_decode_cudagraph_replay" {print $2}' "$t1_identity")" \
    || "$(awk -F= '$1 == "expected_disable_spec_decode_cudagraph_replay" {print $2}' "$t1_identity")" \
      != "0" \
    || "$(awk -F= '$1 == "draft_disable_cudagraphs" {print $2}' "$t1_identity")" \
      != "0" \
    || "$(awk -F= '$1 == "expected_vllm_diff_sha256" {print $2}' "$t1_identity")" \
      != "$vllm_diff_sha" ]]; then
    printf 'T1 is not bound to the current target request replay-bypass identity\n' >&2
    exit 4
  fi
  if ! jq -e \
    '(.rows | length) == 25
     and .rows[24].prompt_index == 24
     and .rows[24].prompt_id == "holdout--long-rollover-repository-audit"
     and (.rows[24].token_ids | length) == 512
     and any(.rows[24].token_ids[]; . != 0)' \
    "$peer_bench" >/dev/null; then
    printf 'T1 prompt 24 is malformed or the known all-zero catastrophe; T2 is forbidden\n' >&2
    exit 4
  fi
  t1_recheck=$(mktemp /tmp/qwen38-target-request-replay-t1-recheck.XXXXXX.json)
  trap 'rm -f -- "$t1_recheck"' EXIT
  if ! /home/steve/.venvs/vllm-xpu/bin/python "$sealed_checker" arm \
    --arm-root "$t1" "${checker_args[@]}" --require-quality-pass \
    --output "$t1_recheck"; then
    printf 'T1 no longer passes the current sealed treatment contract\n' >&2
    exit 4
  fi
  rm -f -- "$t1_recheck"
  trap - EXIT
fi

if [[ -e "$arm_root" ]]; then
  printf 'refusing existing target request replay-bypass arm root: %s\n' \
    "$arm_root" >&2
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
  VALIDATION_EXPECT_VLLM_DIFF_SHA256="$vllm_diff_sha"
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
  VALIDATION_DISABLE_SPEC_DECODE_CUDAGRAPH_REPLAY=0
  VALIDATION_EXPECT_DISABLE_SPEC_DECODE_CUDAGRAPH_REPLAY=0
  VALIDATION_DECODE_CUDAGRAPH_REPLAY_EAGER_EVERY_N_REQUESTS=1
  VALIDATION_EXPECT_DECODE_CUDAGRAPH_REPLAY_EAGER_EVERY_N_REQUESTS=1
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
  VALIDATION_SYNC_AFTER_MODEL_FORWARD=0
  VALIDATION_EXPECT_SYNC_AFTER_MODEL_FORWARD=0
  VALIDATION_REQUIRE_REPLAY_MICROSCOPE=0
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
  VALIDATION_EXPECT_TARGET_TOKEN_BENCH_SHA256="$target_bench_sha"
  VALIDATION_EXPECT_REPORT_ONLY_B2_BENCH_SHA256="$b2_bench_sha"
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
  VALIDATION_TARGET_TOKEN_BENCH="$target_bench"
  VALIDATION_REPORT_ONLY_B2_BENCH="$b2_bench"
  VALIDATION_REQUIRE_TARGET_TOKEN_PARITY=0
)
if [[ -n "$peer_bench" ]]; then
  launch_env+=(
    "VALIDATION_PARITY_PEER_BENCH=$peer_bench"
    "VALIDATION_EXPECT_PARITY_PEER_BENCH_SHA256=$peer_sha"
    "VALIDATION_EXPECT_PARITY_PEER_CHECKSUM_MANIFEST_SHA256=$t1_checksum_manifest_expected"
  )
fi

exec env -i "${launch_env[@]}" \
  "$runner" spec-native-partition-exact-native 2,3 "$arm_root" \
  "$quality_baseline"

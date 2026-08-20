#!/usr/bin/env bash
set -euo pipefail

# One-arm recurrence discriminator after the sealed A2/B2 pair failed 22/25.
# B2 is the mandatory peer because its final long-rollover response is sane;
# A2 is the report-only reference because its 512 token IDs were all zero.

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
driver=$(realpath -- "$0")
action=${1:-}

if [[ "$action" != "check" && "$action" != "c" ]]; then
  printf 'usage: %s check|c\n' "$0" >&2
  exit 2
fi

raw=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70
cache=/mnt/usb-models/llm-runtime/vllm-cache/qwen38-postrecovery-marginfree-mtp5-20260820
sealed="$raw/qwen38-postrecovery-marginfree-mtp5-25-spec-c-20260820/compile-cache-output-manifest.json"
suite="$raw/qwen38-postrecovery-marginfree-mtp5-25-spec-b-20260820/validation-suite.json"
quality_baseline="$raw/qwen38-marginfree-targetoracle-25-a-20260820/data/quality.json"
a2="$raw/qwen38-detpad-composite4dd-marginfree-mtp5-25-spec-a2-20260820"
b2="$raw/qwen38-detpad-composite4dd-marginfree-mtp5-25-spec-b2-20260820"
peer_bench="$b2/data/bench.json"
reference_bench="$a2/data/bench.json"
label=qwen38-detpad-composite4dd-marginfree-mtp5-25-spec-c1-20260820
arm_root="$raw/$label"
runner="$repo/experiments/qwen36-27b-autoround-int4-b70/validation-20260815/run-arm.sh"
model=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan
base_stage=/home/steve/src/vllm-xpu-kernels
stage=/home/steve/staged-xpu-commitfix-graphfa-composite-20260820
oneccl=/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public
graph_manifest="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/staged-xpu-commitfix-graphfa-composite-20260820.graph.sha256"
model_manifest="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json"
model_verifier="$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py"
sealed_checker="$repo/repro/qwen38-27b-autoround-int4-b70/scripts/check-tp2-sealed-gates.py"
common_runner="$repo/experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh"
top_wrapper="$repo/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-fullgraph-transaction-candidate.sh"
serve_runner="$repo/experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh"

cache_manifest_sha=f3582440de9b252cc738648aa5b690fd324bec9afeb8d89e4b73d295071cb0ff
suite_sha=292dea6aaf60f53067fb63c9bc5aba15bd1c6e71c2601693e6750239edf9fa0c
quality_sha=45424f1d2dcbfda0a5ed75552cf799cac0e8fb6b8c5e1ddf2aba540b95c77e95
model_manifest_sha=731d851b39d37f3d58c5a74ad6a7cd3ade1c9e8543ef1612a5d55131ff8331b8
verifier_sha=5bca853ae644099cb18c58b458dd04dfcc0844d7644f074c4350539504d80ce9
graph_manifest_sha=47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da
a2_bench_sha=865ab22ef080cb9823ebf8c06b262033cad45fff31cd29adf369d7257172efcb
b2_bench_sha=96933a8211867479410375aaad7bd96bfb9f97d0edafc12af80dc9963805e721
a2_checksum_manifest_sha=a9a162c959256add8520f2b538fc61f81991d9e56e6e609dea902e755c150158
b2_checksum_manifest_sha=e7726d02dd467442b03749e885bda619838c89451149d0dad979c0b290858d30
native_sha=4dd336013d155aab004fb1c916118957cb9349b491938da65769f2d8af18ffb0
core_sha=5717476461048b5056a92926f2a52d73c121f69bdc75de22fd52720fb65b3007
moe_sha=ea4c20a8dff49fc07fd799d5a2a47e8b24266a256425b41e337f852492ee3c1b
fa_sha=33938cdd2436684dcb76108a4db43e4ab0314406ad537fcd3732a005f7d23739
run_arm_sha=e89352d7d71a2d5b1c34b93a0b8bd2f024eab7584b6141acaeda74fc0a145b74
checker_sha=23ad35011198f1288b39fd8c4a3e77e4527229cfe94ce30a08334acecb7b043c
common_runner_sha=b6ad5add4d1932fe6c12d3c58f096b8940dae7ef0c1d45cf8d2c5ee15f9a474e
top_wrapper_sha=991e21c1ddea6f0d3a044adaac78dca993f78bfd999819b7beb06e70ecd3e343
serve_runner_sha=f1d1503a4a1676eff7d61823a0cca66d1830a015446dc30058c3176d309c6dea

verify_sha() {
  local path=$1 expected=$2 label_name=$3 actual
  if [[ ! -f "$path" ]]; then
    printf '%s is missing: %s\n' "$label_name" "$path" >&2
    exit 3
  fi
  actual=$(sha256sum -- "$path" | awk '{print $1}')
  if [[ "$actual" != "$expected" ]]; then
    printf '%s SHA mismatch: actual=%s expected=%s\n' \
      "$label_name" "$actual" "$expected" >&2
    exit 3
  fi
}

if [[ "$(git -C "$repo" branch --show-current)" != "main" ]]; then
  printf 'recurrence launcher requires the main branch\n' >&2
  exit 3
fi
if [[ -n "$(git -C "$repo" status --porcelain --untracked-files=normal)" ]]; then
  printf 'recurrence launcher requires a clean repository\n' >&2
  exit 3
fi
if [[ "$(git -C "$repo" rev-parse HEAD)" \
  != "$(git -C "$repo" rev-parse origin/main)" ]]; then
  printf 'recurrence launcher requires local main == origin/main\n' >&2
  exit 3
fi

verify_sha "$sealed" "$cache_manifest_sha" sealed-cache-manifest
verify_sha "$suite" "$suite_sha" validation-suite
verify_sha "$quality_baseline" "$quality_sha" quality-baseline
verify_sha "$peer_bench" "$b2_bench_sha" sane-b2-peer-benchmark
verify_sha "$reference_bench" "$a2_bench_sha" corrupt-a2-reference-benchmark
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
verify_sha "$a2/SHA256SUMS.pre-manifest" \
  "$a2_checksum_manifest_sha" a2-checksum-manifest
verify_sha "$b2/SHA256SUMS.pre-manifest" \
  "$b2_checksum_manifest_sha" b2-checksum-manifest

for prior in "$a2" "$b2"; do
  if [[ ! -f "$prior/SHA256SUMS.pre-manifest" ]] \
    || ! (cd "$prior" && sha256sum -c SHA256SUMS.pre-manifest >/dev/null); then
    printf 'prior arm checksum set is missing or no longer exact: %s\n' \
      "$prior" >&2
    exit 3
  fi
  if ! jq -e '.status == "passed" and (.errors | length == 0)' \
    "$prior/tp2-sealed-gates.json" >/dev/null; then
    printf 'prior arm no longer passes its sealed identity gate: %s\n' \
      "$prior" >&2
    exit 3
  fi
done
if [[ "$(tr -d '\n' < "$a2/runner.exit-code")" != "0" \
  || "$(tr -d '\n' < "$b2/runner.exit-code")" != "14" ]]; then
  printf 'prior A2/B2 runner status no longer matches 0/14\n' >&2
  exit 3
fi

"$repo/scripts/canonical-tree-manifest.py" verify \
  --root "$cache/torch_compile_cache" \
  --manifest "$sealed" >/dev/null

if [[ "$action" == "check" ]]; then
  printf 'sealed TP2 recurrence preflight passed\n'
  exit 0
fi

if [[ -e "$arm_root" ]]; then
  printf 'refusing existing recurrence root: %s\n' "$arm_root" >&2
  exit 4
fi

repo_head=$(git -C "$repo" rev-parse HEAD)
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
  VALIDATION_RUN_QUALITY=0
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
  VALIDATION_EXPECT_SUITE_SHA256="$suite_sha"
  VALIDATION_EXPECT_QUALITY_BASELINE_SHA256="$quality_sha"
  VALIDATION_EXPECT_PARITY_PEER_BENCH_SHA256="$b2_bench_sha"
  VALIDATION_EXPECT_TARGET_TOKEN_BENCH_SHA256="$a2_bench_sha"
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
  VALIDATION_PARITY_PEER_BENCH="$peer_bench"
  VALIDATION_TARGET_TOKEN_BENCH="$reference_bench"
  VALIDATION_REQUIRE_TARGET_TOKEN_PARITY=0
)

exec env -i "${launch_env[@]}" \
  "$runner" spec-native-partition-exact-native 2,3 "$arm_root" \
  "$quality_baseline"

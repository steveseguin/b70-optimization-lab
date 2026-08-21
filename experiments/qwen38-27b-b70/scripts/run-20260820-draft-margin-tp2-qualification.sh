#!/usr/bin/env bash
set -euo pipefail

# One treatment-only TP2 qualification. This is not a throughput arm and does
# not authorize a full-25 margin campaign.

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
driver=$(realpath -- "$0")
action=${1:-}
if [[ "$action" != "check" && "$action" != "q1" ]] || [[ $# -ne 1 ]]; then
  printf 'usage: %s check|q1\n' "$0" >&2
  exit 2
fi

raw=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70
cache=/mnt/usb-models/llm-runtime/vllm-cache/qwen38-postrecovery-marginfree-mtp5-20260820
sealed="$raw/qwen38-postrecovery-marginfree-mtp5-25-spec-c-20260820/compile-cache-output-manifest.json"
target="$raw/qwen38-marginfree-targetoracle-25-a-20260820"
quality_baseline="$target/data/quality.json"
label=qwen38-detpad-composite4dd-mtp5-draft-margin025-tp2-qualification-q1-20260820
arm_root="$raw/$label"
runner="$repo/experiments/qwen36-27b-autoround-int4-b70/validation-20260815/run-arm.sh"
checker="$repo/repro/qwen38-27b-autoround-int4-b70/scripts/check-tp2-sealed-gates.py"
common_runner="$repo/experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh"
top_wrapper="$repo/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-fullgraph-transaction-candidate.sh"
serve_runner="$repo/experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh"
suite="$repo/experiments/qwen38-27b-b70/data/2026-08-20-draft-margin-tp2-qualification-suite.json"
synthetic_support="$repo/experiments/qwen38-27b-b70/data/2026-08-20-int4-margin-equiv.json"
diagnostic_patch="$repo/experiments/qwen38-27b-b70/patches/vllm-qwen38-draft-head-int4-tp-safe-margin-qualification-20260820.patch"
target_marker_patch="$repo/patches/qwen38-27b-autoround-int4-b70/vllm-target-verifier-request-replay-bypass-marker-20260820.patch"
model=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan
model_manifest="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json"
model_verifier="$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py"
base_stage=/home/steve/src/vllm-xpu-kernels
stage=/home/steve/staged-xpu-commitfix-graphfa-composite-20260820
graph_manifest="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/staged-xpu-commitfix-graphfa-composite-20260820.graph.sha256"
oneccl=/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public
vllm_source=/home/steve/src/vllm

cache_manifest_sha=f3582440de9b252cc738648aa5b690fd324bec9afeb8d89e4b73d295071cb0ff
quality_sha=45424f1d2dcbfda0a5ed75552cf799cac0e8fb6b8c5e1ddf2aba540b95c77e95
suite_sha=271958be5264fa095e180bd196ac82e198c6c9ae7879ef83eb3f5fa4b63a1df7
synthetic_support_sha=bc34533363beca2dce193f85403ad24e40585117f6e2e6c8d2b577aea2d192be
diagnostic_patch_sha=f2cde099a74ad3fbd0a0292d5bb16029f8d00d662010b5a93833ce8273b8980d
target_marker_patch_sha=e2185720388a3f92533e41224ecf9cfa0509a49c45f12f1a10f62a8debdef4ea
model_manifest_sha=731d851b39d37f3d58c5a74ad6a7cd3ade1c9e8543ef1612a5d55131ff8331b8
verifier_sha=5bca853ae644099cb18c58b458dd04dfcc0844d7644f074c4350539504d80ce9
graph_manifest_sha=47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da
native_sha=4dd336013d155aab004fb1c916118957cb9349b491938da65769f2d8af18ffb0
core_sha=5717476461048b5056a92926f2a52d73c121f69bdc75de22fd52720fb65b3007
moe_sha=ea4c20a8dff49fc07fd799d5a2a47e8b24266a256425b41e337f852492ee3c1b
fa_sha=33938cdd2436684dcb76108a4db43e4ab0314406ad537fcd3732a005f7d23739
vllm_head=44fc8fde09fc311d3099dab10366b672d9142ea4
vllm_diff_sha=66f5823ca1f48545f1adef3731b165bc14975d374ff2899ce91272e94a30a852
run_arm_sha=1631d43b69e81b75344833f10652c5b333070537d91513c83ec32b14fa8d441f
checker_sha=f7b0c6992974e7c8a3f0039543d75c9eba9169cadd65246f24c3f7c694c4c035
common_runner_sha=ad87e9fea8b9cfc0d8bee54adb6b9aa93cfdfb8b5579a1a23cdec0b0ea2f4f22
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
  printf 'draft-margin qualification requires main\n' >&2
  exit 3
fi
if [[ -n "$(git -C "$repo" status --porcelain --untracked-files=normal)" ]]; then
  printf 'draft-margin qualification requires a clean repository\n' >&2
  exit 3
fi
if [[ "$(git -C "$repo" rev-parse HEAD)" \
  != "$(git -C "$repo" rev-parse origin/main)" ]]; then
  printf 'draft-margin qualification requires local main == origin/main\n' >&2
  exit 3
fi
expected_vllm_status=$' M vllm/model_executor/layers/vocab_parallel_embedding.py\n M vllm/v1/worker/gpu_model_runner.py'
if [[ "$(git -C "$vllm_source" rev-parse HEAD)" != "$vllm_head" \
  || "$(git -C "$vllm_source" status --porcelain --untracked-files=normal)" \
    != "$expected_vllm_status" \
  || "$(git -C "$vllm_source" diff --binary | sha256sum | awk '{print $1}')" \
    != "$vllm_diff_sha" ]]; then
  printf 'vLLM source is not the exact combined qualification identity\n' >&2
  exit 3
fi

verify_sha "$diagnostic_patch" "$diagnostic_patch_sha" diagnostic-source-patch
verify_sha "$target_marker_patch" "$target_marker_patch_sha" target-marker-patch
if ! git -C "$vllm_source" apply --check --unidiff-zero --cached \
    "$diagnostic_patch" \
  || ! git -C "$vllm_source" apply --check --unidiff-zero --reverse \
    "$diagnostic_patch" \
  || ! git -C "$vllm_source" apply --check --unidiff-zero --cached \
    "$target_marker_patch" \
  || ! git -C "$vllm_source" apply --check --unidiff-zero --reverse \
    "$target_marker_patch"; then
  printf 'tracked source artifacts do not reconstruct the live source delta\n' >&2
  exit 3
fi
verify_sha "$sealed" "$cache_manifest_sha" sealed-cache-manifest
verify_sha "$quality_baseline" "$quality_sha" quality-baseline
verify_sha "$suite" "$suite_sha" qualification-suite
verify_sha "$synthetic_support" "$synthetic_support_sha" synthetic-support
verify_sha "$graph_manifest" "$graph_manifest_sha" composite-graph-manifest
verify_sha "$model_manifest" "$model_manifest_sha" model-manifest
verify_sha "$model_verifier" "$verifier_sha" model-verifier
verify_sha "$runner" "$run_arm_sha" arm-runner
verify_sha "$checker" "$checker_sha" sealed-checker
verify_sha "$common_runner" "$common_runner_sha" common-runner
verify_sha "$top_wrapper" "$top_wrapper_sha" top-candidate-wrapper
verify_sha "$serve_runner" "$serve_runner_sha" serve-runner
verify_sha "$stage/vllm_xpu_kernels/_xpu_C.abi3.so" "$native_sha" native-extension
verify_sha "$stage/vllm_xpu_kernels/_C.abi3.so" "$core_sha" core-extension
verify_sha "$stage/vllm_xpu_kernels/_moe_C.abi3.so" "$moe_sha" moe-extension
verify_sha "$stage/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" "$fa_sha" fa-extension
if ! jq -e '.trials == 40 and .argmax_mismatches == 0' \
  "$synthetic_support" >/dev/null; then
  printf 'historical synthetic support is malformed\n' >&2
  exit 3
fi
"$repo/scripts/canonical-tree-manifest.py" verify \
  --root "$cache/torch_compile_cache" --manifest "$sealed" >/dev/null

if [[ "$action" == "check" ]]; then
  printf 'sealed draft-margin TP2 qualification preflight passed\n'
  exit 0
fi
if [[ -e "$arm_root" ]]; then
  printf 'refusing existing draft-margin qualification root: %s\n' \
    "$arm_root" >&2
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
  VALIDATION_DRAFT_LM_HEAD_INT4_FALLBACK_MARGIN=0.25
  VALIDATION_EXPECT_DRAFT_LM_HEAD_INT4_FALLBACK_MARGIN=0.25
  VALIDATION_REQUIRE_DRAFT_MARGIN_SCREEN=1
  VALIDATION_DRAFT_MARGIN_QUALIFICATION_MAX_CALLS=1024
  VALIDATION_DRAFT_MARGIN_SYNTHETIC_SUPPORT="$synthetic_support"
  VALIDATION_EXPECT_DRAFT_MARGIN_SYNTHETIC_SUPPORT_SHA256="$synthetic_support_sha"
  VALIDATION_ENABLE_XPU_GRAPH=1
  VALIDATION_DISABLE_SPEC_DECODE_CUDAGRAPH_REPLAY=0
  VALIDATION_EXPECT_DISABLE_SPEC_DECODE_CUDAGRAPH_REPLAY=0
  VALIDATION_DECODE_CUDAGRAPH_REPLAY_EAGER_EVERY_N_REQUESTS=0
  VALIDATION_EXPECT_DECODE_CUDAGRAPH_REPLAY_EAGER_EVERY_N_REQUESTS=0
  'VALIDATION_VLLM_EXTRA_ARGS=--dtype float16'
  VALIDATION_VLLM_CACHE_ROOT="$cache"
  VALIDATION_COMPILE_CACHE_MANIFEST="$sealed"
  VALIDATION_COMPILATION_CONFIG_OVERRIDE="$compilation_config"
  VALIDATION_SUITE_OVERRIDE="$suite"
  VALIDATION_RUN_SMOKE=0
  VALIDATION_RUN_BENCH=1
  VALIDATION_RUN_QUALITY=0
  VALIDATION_BENCH_MAX_TOKENS=128
  VALIDATION_BENCH_METRIC_TOKENS=32
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
  VALIDATION_REQUIRE_TARGET_TOKEN_PARITY=0
)

exec env -i "${launch_env[@]}" \
  "$runner" spec-native-partition-exact-native 2,3 "$arm_root" \
  "$quality_baseline"

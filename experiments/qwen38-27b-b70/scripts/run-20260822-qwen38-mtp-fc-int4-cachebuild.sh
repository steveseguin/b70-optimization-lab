#!/usr/bin/env bash
set -euo pipefail

# mtp.fc INT4 integration ladder, step: build the FRESH door-forked compile
# cache and validate the patch at runtime (gates 1-2 + quality gate 5 in one
# boot). Stock composite stage (has int4_gemm_w4a16) + the default-off vLLM
# patch turned ON via VLLM_XPU_MTP_FC_INT4=1. Sealed record gates OFF; this
# is a diagnostic build, not a promoted record. Writes enabled into a FRESH
# cache root so the door-forked namespace compiles clean. Reads evidence from
# data/*.json, not the runner exit code.
#
# Usage: run-20260822-qwen38-mtp-fc-int4-cachebuild.sh build OUTPUT_ROOT

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
driver=$(realpath -- "$0")
action=${1:-}
output_root=${2:-}
door=${3:-1}
[[ "$action" == build && -n "$output_root" && ( "$door" == 0 || "$door" == 1 ) ]] || {
  printf 'usage: %s build OUTPUT_ROOT [door=0|1]\n' "$0" >&2; exit 2; }

raw=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70
fresh_cache=/mnt/usb-models/llm-runtime/vllm-cache/qwen38-mtpfc-int4-20260822
suite="$raw/qwen38-postrecovery-marginfree-mtp5-25-spec-b-20260820/validation-suite.json"
suite_sha=292dea6aaf60f53067fb63c9bc5aba15bd1c6e71c2601693e6750239edf9fa0c
quality_baseline="$raw/qwen38-marginfree-targetoracle-25-a-20260820/data/quality.json"
quality_sha=45424f1d2dcbfda0a5ed75552cf799cac0e8fb6b8c5e1ddf2aba540b95c77e95
target_bench="$raw/qwen38-marginfree-targetoracle-25-a-20260820/data/bench.json"
target_bench_sha=045fd8b4fc9f1eda3bbc778e4b88a6ad7407ff4a50be879dc4e9780b37e0d6e8
runner="$repo/experiments/qwen36-27b-autoround-int4-b70/validation-20260815/run-arm.sh"
model=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan
base_stage=/home/steve/src/vllm-xpu-kernels
stage=/home/steve/staged-xpu-commitfix-graphfa-composite-20260820
oneccl=/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public
graph_manifest="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/staged-xpu-commitfix-graphfa-composite-20260820.graph.sha256"
graph_manifest_sha=47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da
model_manifest="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json"
model_manifest_sha=731d851b39d37f3d58c5a74ad6a7cd3ade1c9e8543ef1612a5d55131ff8331b8
model_verifier="$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py"
verifier_sha=5bca853ae644099cb18c58b458dd04dfcc0844d7644f074c4350539504d80ce9
native_sha=4dd336013d155aab004fb1c916118957cb9349b491938da65769f2d8af18ffb0
core_sha=5717476461048b5056a92926f2a52d73c121f69bdc75de22fd52720fb65b3007
moe_sha=ea4c20a8dff49fc07fd799d5a2a47e8b24266a256425b41e337f852492ee3c1b
fa_sha=33938cdd2436684dcb76108a4db43e4ab0314406ad537fcd3732a005f7d23739
device_sha=604f1b328870f2c41ef1d05c4d6016c34d222033d905877b0f9a2ff0c66b2a0c
# The default-off vLLM patch applied to /home/steve/src/vllm (tracked diff).
vllm_patch_diff_sha=95fca14c87dabbec6de40f2089985880fa2a604a47d4796123a3254eb5a0a49c
empty_diff=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
request_extra_json='{"chat_template_kwargs":{"enable_thinking":false}}'

[[ "$(git -C "$repo" branch --show-current)" == main ]] || { printf 'requires main\n' >&2; exit 3; }
[[ -z "$(git -C "$repo" status --porcelain --untracked-files=normal)" ]] || { printf 'requires clean lab repo\n' >&2; exit 3; }
[[ -x "$stage/vllm_xpu_kernels/_xpu_C.abi3.so" || -f "$stage/vllm_xpu_kernels/_xpu_C.abi3.so" ]] || { printf 'missing stage extension\n' >&2; exit 3; }
[[ -e "$output_root" ]] && { printf 'refusing existing output root: %s\n' "$output_root" >&2; exit 4; }

repo_head=$(git -C "$repo" rev-parse HEAD)
driver_sha=$(sha256sum -- "$driver" | awk '{print $1}')
label=qwen38-mtpfc-int4-cachebuild-20260822
# compilation config WITHOUT an explicit cache_dir: vLLM namespaces under
# VLLM_CACHE_ROOT using compile_factors, which now includes the door -> a
# clean fresh namespace, distinct from the sealed b99160ae76.
compilation_config='{"use_inductor_graph_partition":true,"pass_config":{"fuse_rope_kvcache_cat_mla":false},"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[6],"max_cudagraph_capture_size":6}'

launch_env=(
  HOME=/home/steve USER=steve LOGNAME=steve SHELL=/bin/bash LANG=C.UTF-8
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
  VALIDATION_REQUIRE_XPU_MODULES_UNDER_STAGE=1
  VALIDATION_EXPECT_XPU_COUNT=4
  VALIDATION_EXPECT_VLLM_VERSION=0.20.2rc1.dev13+g9557d9108.d20260620
  VALIDATION_EXPECT_VLLM_DIFF_SHA256="$vllm_patch_diff_sha"
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
  VLLM_XPU_MTP_FC_INT4="$door"
  'VALIDATION_VLLM_EXTRA_ARGS=--dtype float16'
  VALIDATION_VLLM_CACHE_ROOT="$fresh_cache"
  VALIDATION_COMPILE_CACHE_MANIFEST=
  VALIDATION_COMPILATION_CONFIG_OVERRIDE="$compilation_config"
  VALIDATION_SUITE_OVERRIDE="$suite"
  VALIDATION_RUN_SMOKE=1
  VALIDATION_RUN_BENCH=1
  VALIDATION_RUN_QUALITY=1
  VALIDATION_BENCH_MAX_TOKENS=512
  VALIDATION_BENCH_METRIC_TOKENS=100
  VALIDATION_REQUEST_EXTRA_JSON="$request_extra_json"
  VALIDATION_ENABLE_PACKET_TRACE=0
  VALIDATION_ENABLE_LAYER_TRACE=0
  VALIDATION_REQUIRE_TP2_SEALED_GATES=0
  VALIDATION_REQUIRE_COMPILE_CACHE_UNCHANGED=0
  VALIDATION_REQUIRE_NO_COMPILE_CACHE_WRITES=0
  VALIDATION_EXPECT_SUITE_SHA256="$suite_sha"
  VALIDATION_EXPECT_QUALITY_BASELINE_SHA256="$quality_sha"
  VALIDATION_EXPECT_PARITY_PEER_BENCH_SHA256=
  VALIDATION_EXPECT_TARGET_TOKEN_BENCH_SHA256="$target_bench_sha"
  VALIDATION_EXPECT_MODEL_DIR="$model"
  VALIDATION_EXPECT_MODEL_MANIFEST_SHA256="$model_manifest_sha"
  VALIDATION_EXPECT_VERIFY_SCRIPT_SHA256="$verifier_sha"
  VALIDATION_EXPECT_CACHE_ROOT="$fresh_cache"
  VALIDATION_EXPECT_GRAPH_MANIFEST_SHA256="$graph_manifest_sha"
  VALIDATION_EXPECT_NATIVE_SHA256="$native_sha"
  VALIDATION_EXPECT_CORE_SHA256="$core_sha"
  VALIDATION_EXPECT_MOE_SHA256="$moe_sha"
  VALIDATION_EXPECT_FA_SHA256="$fa_sha"
  VALIDATION_PARITY_PEER_BENCH=
  VALIDATION_TARGET_TOKEN_BENCH="$target_bench"
  VALIDATION_REQUIRE_TARGET_TOKEN_PARITY=0
)

printf 'mtp.fc INT4 cache-build: door ON, fresh cache %s, stock stage, GPUs 2,3\n' "$fresh_cache"
set +e
env -i "${launch_env[@]}" \
  "$runner" spec-native-partition-exact-native 2,3 "$output_root" "$quality_baseline"
rc=$?
set -e
printf 'runner rc=%s\n' "$rc"
server_log="$output_root/run/server.stdout.log"
if [[ -f "$server_log" ]]; then
  ns=$(grep -oE 'torch_compile_cache/[0-9a-f]+' "$server_log" | head -1)
  printf 'fresh cache namespace observed: %s\n' "${ns:-<none>}"
  grep -Ec 'VLLM_XPU_ONEDNN_INT4_INPUT_DEPENDENCY reached' "$server_log" \
    | xargs printf 'int4 input-dependency markers: %s\n'
fi
[[ -f "$output_root/data/quality.json" ]] && \
  printf 'quality.json present\n' || printf 'no quality.json\n'
exit "$rc"

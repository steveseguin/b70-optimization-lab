#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
vllm=/home/steve/src/vllm-current-main
kernels=/home/steve/src/vllm-xpu-kernels
python=/home/steve/.venvs/vllm-xpu/bin/python3
stage_root=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70
stage="${stage_root}/vllm_xpu_kernels"
model=/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8
tool="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/w13-m1-xpu-graph-gate.py"
summarizer="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/summarize-w13-m1-xpu-graph-census.py"
stage_manifest="${repo}/experiments/qwen38-flash-next-fp8-b70/data/runtime-stage-padding-guard-loadable.sha256"
result=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260901-moe-m1-w13-xpu-graph-census-a1
loader_suffix=/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib:/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib

model_revision=bcd9f01ddc9cff2316eb84281bebcd5b058bddce
expected_vllm=cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9
expected_kernels=e421889999bc1e5a5f11044d14548b9afdba644d
expected_tool=f8682c52b0d9df911bc84295df85be9f41f0429b17431388fea60a04a9484d6c
expected_summarizer=3118649c294c23fa37b8d84de77b34f0b2009775129a86b47257d69c64688869
expected_stage_manifest=9fa443fdb7a6d0042cf04f859cc6fd6a7bdc09943e16cafb4ea084573c892d2b
expected_fused_moe=4b376eb5e22e7972a1d70e4012999650ab961719d6309cbec27a6104fa64d0a0
expected_triton_moe=b8a461b712b88cf6ab5ba4f49029fddce3a501f7ff909b276b6de04b808da4c2
expected_modular_kernel=1e60aca6ed0dd4fcb46d577897ff1651f27a6130b3449d22265c0c791beec5d5
expected_model_index=0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6
expected_model_config=99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d
expected_shard2=6841fe21fa8a8a7a693c585efe65cd2732889095b696da88bda0cb287366910b
expected_shard3=974a2a2ab551f8f1405a4955ab32a8721c68c73dd85b382491d9f0e6a34ee752

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
digest() { sha256sum "$1" | cut -d' ' -f1; }
require_hash() {
  local path=$1 expected=$2 label=$3
  [[ -f "$path" && "$(digest "$path")" == "$expected" ]] || fail "$label drifted"
}

[[ $# == 0 ]] || fail "this frozen census takes no arguments"
[[ "${Q38_W13_CENSUS_VALIDATE_ONLY:-0}" =~ ^[01]$ ]] || fail "invalid validate-only selector"
[[ -x "$python" ]] || fail "vLLM XPU interpreter is missing"
require_hash "$tool" "$expected_tool" "W13 component gate"
require_hash "$summarizer" "$expected_summarizer" "W13 census summarizer"
require_hash "$stage_manifest" "$expected_stage_manifest" "runtime-stage manifest"
require_hash "${vllm}/vllm/model_executor/layers/fused_moe/fused_moe.py" "$expected_fused_moe" "fused MoE source"
require_hash "${vllm}/vllm/model_executor/layers/fused_moe/experts/triton_moe.py" "$expected_triton_moe" "Triton MoE source"
require_hash "${vllm}/vllm/model_executor/layers/fused_moe/modular_kernel.py" "$expected_modular_kernel" "modular MoE source"
require_hash "${model}/model.safetensors.index.json" "$expected_model_index" "model index"
require_hash "${model}/config.json" "$expected_model_config" "model config"
[[ "$(git -C "$vllm" rev-parse HEAD)" == "$expected_vllm" ]] || fail "vLLM head drifted"
[[ -z "$(git -C "$vllm" status --porcelain --untracked-files=no)" ]] || fail "vLLM tracked source is dirty"
[[ "$(git -C "$kernels" rev-parse HEAD)" == "$expected_kernels" ]] || fail "kernel head drifted"
[[ -z "$(git -C "$kernels" status --porcelain --untracked-files=no)" ]] || fail "kernel tracked source is dirty"
(cd "$stage" && sha256sum -c "$stage_manifest") >/dev/null || fail "runtime-stage files drifted"

if [[ "${Q38_W13_CENSUS_VALIDATE_ONLY:-0}" == 1 ]]; then
  printf 'PASS: frozen W13 graph census validates without GPU work\n'
  exit 0
fi

require_hash "${model}/model-00002-of-00131.safetensors" "$expected_shard2" "layer-0 gate/up shard"
require_hash "${model}/model-00003-of-00131.safetensors" "$expected_shard3" "layer-0 down shard"
read -r model_source model_type model_target < <(findmnt -nro SOURCE,FSTYPE,TARGET --target "$model")
[[ "$model_source" == /dev/sda2 && "$model_type" == fuseblk && "$model_target" == /mnt/usb-models ]] || fail "model is not on the frozen external filesystem"
read -r evidence_source evidence_type evidence_target < <(findmnt -nro SOURCE,FSTYPE,TARGET --target /mnt/usb-models)
[[ "$evidence_source" == /dev/sda2 && "$evidence_type" == fuseblk && "$evidence_target" == /mnt/usb-models ]] || fail "evidence drive is not mounted"
[[ ! -e "$result" ]] || fail "evidence root already exists"
[[ -z "$(pgrep -af 'vllm serve|VLLM::EngineCore|Worker_TP|w13-m1-xpu-graph-gate.py' || true)" ]] || fail "a model or W13 component process is active"

exec 9>/tmp/q38-w13-m1-xpu-graph-census-a1.lock
flock -n 9 || fail "another W13 graph census owns the lock"
mkdir -p "$result"
install -m 0644 "$0" "${result}/runner.sh"
xpu-smi discovery -j >"${result}/device-discovery.json"
jq -e '.device_list | length == 4 and all(.[]; .device_name == "Intel(R) Arc(TM) Pro B70 Graphics")' \
  "${result}/device-discovery.json" >/dev/null || fail "four-B70 discovery failed"

{
  printf 'boot_id=%s\n' "$(cat /proc/sys/kernel/random/boot_id)"
  printf 'model_revision=%s\n' "$model_revision"
  printf 'vllm_head=%s\n' "$expected_vllm"
  printf 'kernel_head=%s\n' "$expected_kernels"
  printf 'runner_sha256=%s\n' "$(digest "$0")"
  printf 'tool_sha256=%s\n' "$expected_tool"
  printf 'summarizer_sha256=%s\n' "$expected_summarizer"
  printf 'runtime_stage_manifest_sha256=%s\n' "$expected_stage_manifest"
  printf 'model_index_sha256=%s\n' "$expected_model_index"
  printf 'model_config_sha256=%s\n' "$expected_model_config"
  printf 'scope=layer0 EP-rank0 seed20260827 six W13-only candidates with matched fresh-process C/A/C\n'
} >"${result}/identity.txt"

run_arm() {
  local label=$1 config=$2 authority=${3:-} allow_failure=${4:-0}
  local log="${result}/${label}.jsonl" err="${result}/${label}.stderr"
  local -a command=(
    env -u ZE_AFFINITY_MASK
    ONEAPI_DEVICE_SELECTOR=level_zero:0
    VLLM_TARGET_DEVICE=xpu
    PYTHONHASHSEED=0
    PYTHONNOUSERSITE=1
    PYTHONSAFEPATH=1
    PYTHONDONTWRITEBYTECODE=1
    "PYTHONPATH=${stage_root}:${vllm}"
    "LD_LIBRARY_PATH=${stage}:${loader_suffix}"
    "$python" "$tool"
    --model-path "$model"
    --model-revision "$model_revision"
    --layer 0
    --ep-rank 0
    --seed 20260827
    --hidden-scale 0.01
    --capture-warmups 5
    --timing-warmups 10
    --timing-batches 15
    --iterations-per-batch 200
    --candidate-config-json "$config"
  )
  [[ -z "$authority" ]] || command+=(--control-authority-json "$authority")
  printf '%q ' timeout --signal=TERM --kill-after=30s 420s "${command[@]}" >>"${result}/commands.sh"
  printf '> %q 2> %q\n' "$log" "$err" >>"${result}/commands.sh"
  set +e
  timeout --signal=TERM --kill-after=30s 420s "${command[@]}" >"$log" 2>"$err"
  local rc=$?
  set -e
  printf '%s\n' "$rc" >"${result}/${label}.exit-code"
  if (( rc != 0 && allow_failure == 0 )); then
    fail "$label failed with rc ${rc}"
  fi
  return "$rc"
}

validate_arm() {
  local log=$1 config=$2 authority=$3
  jq -e --argjson expected_config "$config" --arg expected_authority "$authority" '
    .status == "pass" and
    .classification == "qwen38_flash_next_w13_m1_xpu_graph_component" and
    .identity.model_revision == "bcd9f01ddc9cff2316eb84281bebcd5b058bddce" and
    .identity.model_index_sha256 == "0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6" and
    .identity.model_config_sha256 == "99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d" and
    .identity.layer == 0 and .identity.ep_rank == 0 and .identity.seed == 20260827 and
    .config_receipt.requested == $expected_config and
    .config_receipt.w2_unchanged == true and
    .correctness.exact_replays == 100 and
    .correctness.config_local_eager_graph_equal == true and
    .correctness.matches_control_authority == true and
    .correctness.unique_eager_hashes == 100 and
    .correctness.unique_graph_hashes == 100 and
    .correctness.control_authority_path == (if $expected_authority == "" then null else $expected_authority end) and
    (.graph.event_median_us | isfinite) and .graph.event_median_us > 0 and
    .graph.timing_input_index == 0
  ' < <(tail -n 1 "$log") >/dev/null
}

candidate_names=(w13-warps4 w13-n32 w13-n128 w13-n256 w13-stage5 w13-k64)
candidate_configs=(
  '{"W1_CONFIG":{"num_warps":4}}'
  '{"W1_CONFIG":{"BLOCK_SIZE_N":32}}'
  '{"W1_CONFIG":{"BLOCK_SIZE_N":128}}'
  '{"W1_CONFIG":{"BLOCK_SIZE_N":256}}'
  '{"W1_CONFIG":{"num_stages":5}}'
  '{"W1_CONFIG":{"BLOCK_SIZE_K":64}}'
)

for index in "${!candidate_names[@]}"; do
  name=${candidate_names[$index]}
  config=${candidate_configs[$index]}
  before="${result}/${name}-control-before.jsonl"
  run_arm "${name}-control-before" '{}'
  validate_arm "$before" '{}' '' || fail "${name} control-before contract failed"
  if (( index == 0 )); then
    printf 'PASS: first actual one-XPU graph control smoke\n' | tee "${result}/first-smoke.txt"
  fi

  if run_arm "${name}-candidate" "$config" "$before" 1; then
    validate_arm "${result}/${name}-candidate.jsonl" "$config" "$before" || fail "${name} candidate contract failed"
  else
    printf 'REJECTED: %s candidate process failed; preserving stderr and continuing to matched control-after\n' "$name" \
      | tee "${result}/${name}-candidate-rejected.txt"
  fi

  run_arm "${name}-control-after" '{}' "$before"
  validate_arm "${result}/${name}-control-after.jsonl" '{}' "$before" || fail "${name} control-after contract failed"
done

"$python" "$summarizer" --result-dir "$result" >"${result}/summary.stdout.jsonl"
jq -e '
  .status == "complete" and
  .classification == "qwen38_w13_m1_xpu_graph_discovery_census" and
  (.rows | length) == 6 and
  .raw_rank_timings_pooled == false and
  .protected_results_changed == false
' "${result}/summary.json" >/dev/null || fail "census summary contract failed"
if jq -e '.confirmation_authorized == true' "${result}/summary.json" >/dev/null; then
  jq -e '
    .status == "frozen_not_executed" and
    .matrix.cells == 24 and .matrix.total_processes == 72 and
    .gates.raw_cross_rank_timings_may_be_pooled == false and
    .execution.authorized_now == false
  ' "${result}/confirmation-packet.json" >/dev/null || fail "confirmation packet contract failed"
fi
sha256sum "${result}/"* >"${result}/SHA256SUMS"
printf 'PASS: W13 graph discovery complete: %s\n' "$result"

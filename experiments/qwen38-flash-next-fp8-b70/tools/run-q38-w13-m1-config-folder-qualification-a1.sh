#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-q38-w13-m1-xpu-graph-confirmation-a2.sh"
adapter="${script_dir}/w13-m1-config-folder-gate.py"
summarizer="${script_dir}/summarize-w13-m1-config-folder-qualification-a1.py"
validator="${script_dir}/validate-q38-root-nvme-link-clearance-v1.py"
verifier="${script_dir}/verify-moe-m1-w13-n32-selection.py"
base_gate="${script_dir}/w13-m1-xpu-graph-gate.py"
phase_patch=/home/steve/llm-optimizations/patches/qwen38-flash-next-fp8-b70/vllm/0021-Add-opt-in-per-phase-Triton-MoE-configs.patch
clearance=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/host/20260901-root-nvme-link-clearance-v1.json
expected_base=bbe360b4aeb838beaed14afa17d1d30ce514ebcb156680f78e0cb232e17d9fcd
expected_adapter=ec9e8c3f1f99605d1a75bd93c1aa833aada18f4eef9d38d504eaf78ec5fff950
expected_summarizer=52e798b94836bc50d91266f5a6eda4d10edab76bec4fc6789203a1dad860163b
expected_validator=2293b3588a275e15a630b813d7a273e650eb64c49eaacedcf212f99fe485d5a5
expected_clearance=6746f0606443ec77ecffd5b8c69fbd1843fb009c0c1ed346e96d29fe14b39f6f
expected_verifier=a464b0f6a46e9149b33e5ccca772bf21385532693e78b691ca010a7833be2e6f
expected_base_gate=8828a3b42766a96f014299967af94cbde48410abd92d64183685dbf737ce05a1
expected_phase_patch=ad820bad443bba32f15b114ea76b4deb4dade754fe1bc362faddfef07eb6c519
expected_base_map=91e5d8b692da3febbba7cb07ee4fdab319909da0c82c1fda95b92dc42d680464
expected_candidate_map=a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be
expected_derived=656524e10a2f86cc064502156f37ab3423fd16ff3c089ceae1671dc58f520e25
derived=/dev/shm/q38-w13-m1-config-folder-qualification-a1-derived.sh
base_folder=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-warps8-m1
candidate_folder=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32
config_name='E=128,N=640,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=fp8_w8a8,block_shape=[128,128].json'
derived_owned=0

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
digest() { sha256sum "$1" | cut -d' ' -f1; }

derive() {
  Q38_W13_A2_SOURCE_ONLY=1 "$base" | awk \
    -v adapter="$adapter" -v adapter_hash="$expected_adapter" \
    -v summarizer="$summarizer" -v summarizer_hash="$expected_summarizer" \
    -v base_folder="$base_folder" -v candidate_folder="$candidate_folder" '
  {
    if ($0 == "run_arm() {") {
      in_run_arm = 1
    } else if ($0 == "validate_arm() {") {
      in_run_arm = 0
    }
    gsub(/confirmation-a2/, "config-folder-qualification-a1")
    gsub(/qwen38_w13_m1_xpu_graph_confirmation_a2/, "qwen38_w13_m1_config_folder_qualification_a1")
    if ($0 ~ /^tool=.*w13-m1-xpu-graph-gate.py/) {
      print "tool=\"" adapter "\""
      next
    }
    if ($0 ~ /^summarizer=.*summarize-w13-m1-xpu-graph-(confirmation-a2|config-folder-qualification-a1).py/) {
      print "summarizer=\"" summarizer "\""
      next
    }
    if ($0 ~ /^result=/) {
      print "result=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260902-moe-m1-w13-n32-config-folder-qualification-a1"
      next
    }
    if ($0 ~ /^cache_root=/) {
      print "cache_root=/dev/shm/q38-w13-n32-config-folder-qualification-a1"
      next
    }
    if ($0 ~ /^exec 9>\/tmp\/q38-w13/) {
      print "exec 9>/tmp/q38-w13-n32-config-folder-qualification-a1.lock"
      next
    }
    if ($0 ~ /^expected_tool=/) {
      print "expected_tool=" adapter_hash
      next
    }
    if ($0 ~ /^expected_summarizer=/) {
      print "expected_summarizer=" summarizer_hash
      next
    }
    if ($0 ~ /^\[\[ -z .*pgrep/ && $0 ~ /w13-m1-xpu-graph-gate.py/) {
      gsub(/w13-m1-xpu-graph-gate.py/, "w13-m1-xpu-graph-gate.py|w13-m1-config-folder-gate.py")
      print
      next
    }
    if ($0 ~ /^    if pgrep/ && $0 ~ /w13-m1-xpu-graph-gate.py/) {
      gsub(/w13-m1-xpu-graph-gate.py/, "w13-m1-config-folder-gate.py")
      print
      next
    }
    if (in_run_arm == 1 && $0 ~ /^  local log=/) {
      print
      print "  local folder role"
      print "  if [[ \"$config\" == \"{}\" ]]; then"
      print "    folder=\"" base_folder "\"; role=control"
      print "  else"
      print "    folder=\"" candidate_folder "\"; role=candidate"
      print "  fi"
      next
    }
    if ($0 == "    VLLM_TARGET_DEVICE=xpu") {
      print
      print "    \"VLLM_TUNED_CONFIG_FOLDER=${folder}\""
      next
    }
    if ($0 == "    --candidate-config-json \"$config\"") {
      print "    --folder-role \"$role\""
      print "    --tuned-config-folder \"$folder\""
      print
      next
    }
    if ($0 == "    .config_receipt.w2_unchanged == true and") {
      print
      print "    .folder_selection_receipt.status == \"pass\" and"
      print "    .folder_selection_receipt.selected_batch_key == 1 and"
      print "    .folder_selection_receipt.m1.w2.BLOCK_SIZE_N == 64 and"
      print "    .folder_selection_receipt.m1.w2.num_warps == 8 and"
      print "    .folder_selection_receipt.m1.w13.BLOCK_SIZE_N == (if $expected_config == {} then 64 else 32 end) and"
      print "    .folder_selection_receipt.role == (if $expected_config == {} then \"control\" else \"candidate\" end) and"
      next
    }
    if ($0 ~ /^  \.gates\.all_8_cells_exact == true and$/) {
      print
      print "  .gates.all_24_folder_selection_receipts_exact == true and"
      next
    }
    gsub(/W13 N32 graph confirmation A2 validates/, "W13 N32 config-folder qualification validates")
    gsub(/W13 N32 graph confirmation A2 complete/, "W13 N32 config-folder qualification complete")
    print
  }
  '
}

cleanup() {
  if (( derived_owned == 1 )); then
    rm -f "$derived"
  fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

[[ $# == 0 ]] || fail "this frozen config-folder qualification takes no arguments"
[[ "${Q38_W13_FOLDER_A1_SOURCE_ONLY:-0}" =~ ^[01]$ ]] || fail "invalid source-only selector"
[[ "${Q38_W13_FOLDER_A1_VALIDATE_ONLY:-0}" =~ ^[01]$ ]] || fail "invalid validate-only selector"
[[ "$(digest "$base")" == "$expected_base" ]] || fail "A2 runner wrapper drifted"
[[ "$(digest "$adapter")" == "$expected_adapter" ]] || fail "config-folder adapter drifted"
[[ "$(digest "$summarizer")" == "$expected_summarizer" ]] || fail "config-folder summarizer drifted"
[[ "$(digest "$validator")" == "$expected_validator" ]] || fail "clearance validator drifted"
[[ "$(digest "$verifier")" == "$expected_verifier" ]] || fail "selection verifier drifted"
[[ "$(digest "$base_gate")" == "$expected_base_gate" ]] || fail "base component gate drifted"
[[ "$(digest "$phase_patch")" == "$expected_phase_patch" ]] || fail "phase-config patch drifted"
[[ -d "$base_folder" && -d "$candidate_folder" ]] || fail "frozen config folder missing"
[[ "$(digest "${base_folder}/${config_name}")" == "$expected_base_map" ]] || fail "base config map drifted"
[[ "$(digest "${candidate_folder}/${config_name}")" == "$expected_candidate_map" ]] || fail "candidate config map drifted"

if ! { set -o noclobber; exec 8>"$derived"; }; then
  set +o noclobber
  fail "derived config-folder runner path already exists"
fi
set +o noclobber
derived_owned=1
derive >&8
exec 8>&-
chmod 0700 "$derived"
[[ "$(digest "$derived")" == "$expected_derived" ]] || fail "derived config-folder runner drifted"
bash -n "$derived"

if [[ "${Q38_W13_FOLDER_A1_SOURCE_ONLY:-0}" == 1 ]]; then
  cat "$derived"
  exit 0
fi
if [[ "${Q38_W13_FOLDER_A1_VALIDATE_ONLY:-0}" == 1 ]]; then
  Q38_W13_CONFIRM_VALIDATE_ONLY=1 "$derived"
  exit 0
fi

[[ -f "$clearance" && ! -L "$clearance" ]] || fail "root-NVMe link clearance is missing"
[[ "$(digest "$clearance")" == "$expected_clearance" ]] || fail "root-NVMe link clearance drifted"
"$validator" --clearance-json "$clearance" >/dev/null || fail "root-NVMe link clearance failed"

"$derived"

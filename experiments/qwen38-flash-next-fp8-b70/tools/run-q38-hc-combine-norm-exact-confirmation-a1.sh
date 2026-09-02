#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
gate="${script_dir}/hc-combine-norm-exact-xpu-graph-gate.py"
core="${script_dir}/hc_combine_norm_exact_staged.py"
summarizer="${script_dir}/summarize-hc-combine-norm-exact-confirmation.py"
clearance_validator="${script_dir}/validate-q38-root-nvme-link-clearance-v1.py"
clearance=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/host/20260901-root-nvme-link-clearance-v1.json
model=/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8
result_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260901-hc-combine-norm-exact-confirmation-a1
cache_root=/dev/shm/q38-hc-combine-norm-exact-confirmation-a1
python=/home/steve/.venvs/vllm-xpu/bin/python3
expected_gate=102df2a562685efbea03b8050102fe8d4063265907fcd9fb8be2106b4fd0379f
expected_core=4f07ca40099b16259ca6f82a226791732455dc9903b66c39691ba212f5d19354
expected_summarizer=7ab377898809bc4d22747b0139d82afdaa5772d3b66b5338c48efeae3267e51f
expected_clearance_validator=2293b3588a275e15a630b813d7a273e650eb64c49eaacedcf212f99fe485d5a5
model_revision=bcd9f01ddc9cff2316eb84281bebcd5b058bddce
nvme_aer_path=/sys/bus/pci/devices/0000:01:00.0/aer_dev_correctable
root_aer_path=/sys/bus/pci/devices/0000:00:03.1/aer_rootport_total_err_cor
# The endpoint counter file is multi-line; read its TOTAL_ERR_COR field, and
# the root-port total file's single value, exactly as the gate-mix runner does.
current_nvme_aer() { awk '$1 == "TOTAL_ERR_COR" {print $2}' "$nvme_aer_path"; }
current_root_aer() { awk 'NR == 1 {print $1}' "$root_aer_path"; }
owned_pgid=

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
digest() { sha256sum "$1" | cut -d' ' -f1; }

[[ $# == 0 ]] || fail "this frozen gate takes no arguments"
[[ "${Q38_HC_EXACT_VALIDATE_ONLY:-0}" =~ ^[01]$ ]] || fail "invalid validate-only selector"
[[ "$(digest "$gate")" == "$expected_gate" ]] || fail "gate drifted"
[[ "$(digest "$core")" == "$expected_core" ]] || fail "candidate core drifted"
[[ "$(digest "$summarizer")" == "$expected_summarizer" ]] || fail "summarizer drifted"
[[ "$(digest "$clearance_validator")" == "$expected_clearance_validator" ]] || \
  fail "root-NVMe clearance validator drifted"
bash -n "$0"
"$python" -B -c \
  'import ast, pathlib, sys; [ast.parse(pathlib.Path(p).read_text()) for p in sys.argv[1:]]' \
  "$gate" "$core" "$summarizer"

if [[ "${Q38_HC_EXACT_VALIDATE_ONLY:-0}" == 1 ]]; then
  printf 'PASS: HC exact-confirmation A1 static validation\n'
  exit 0
fi

[[ "${Q38_HC_EXACT_CONFIRMATION_AUTHORIZED:-}" == \
  "I_UNDERSTAND_THIS_USES_ONE_B70" ]] || fail "explicit one-B70 authorization is missing"
[[ "$(findmnt -nro SOURCE,FSTYPE,TARGET --target /mnt/usb-models)" == \
  "/dev/sda2 fuseblk /mnt/usb-models" ]] || fail "external mount identity drifted"
[[ -f "$clearance" && ! -L "$clearance" ]] || fail "root-NVMe link clearance is missing"
"$clearance_validator" --clearance-json "$clearance" >/dev/null || \
  fail "root-NVMe link clearance failed"
[[ -d "$model" && ! -L "$model" ]] || fail "external model path is missing or linked"
[[ -x "$python" ]] || fail "frozen Python interpreter is unavailable"
[[ -r "$nvme_aer_path" && -r "$root_aer_path" ]] || fail "AER counters are unavailable"
[[ ! -e "$result_dir" && ! -L "$result_dir" ]] || fail "result path already exists"
[[ ! -e "$cache_root" && ! -L "$cache_root" ]] || fail "cache path already exists"

nvme_aer_baseline=$(current_nvme_aer)
root_aer_baseline=$(current_root_aer)
[[ "$nvme_aer_baseline" =~ ^[0-9]+$ && "$root_aer_baseline" =~ ^[0-9]+$ ]] || \
  fail "AER baseline is invalid"

mkdir "$result_dir"
mkdir "$cache_root" || fail "could not create exclusive cache path"
printf 'nvme_aer=%s\nroot_aer=%s\n' "$nvme_aer_baseline" "$root_aer_baseline" \
  >"${result_dir}/aer-baseline.txt"
printf 'model=%s\nrevision=%s\ngate_sha256=%s\ncore_sha256=%s\nsummarizer_sha256=%s\n' \
  "$model" "$model_revision" "$expected_gate" "$expected_core" "$expected_summarizer" \
  >"${result_dir}/identity.txt"

terminate_owned_group() {
  local _
  if [[ "$owned_pgid" =~ ^[1-9][0-9]*$ ]] && kill -0 -- "-${owned_pgid}" 2>/dev/null; then
    kill -TERM -- "-${owned_pgid}" 2>/dev/null || true
    for _ in $(seq 1 25); do
      kill -0 -- "-${owned_pgid}" 2>/dev/null || break
      sleep 0.2
    done
    if kill -0 -- "-${owned_pgid}" 2>/dev/null; then
      kill -KILL -- "-${owned_pgid}" 2>/dev/null || true
    fi
  fi
  owned_pgid=
}

finalize() {
  local status=$1 nvme_aer=root_unavailable root_aer=root_unavailable
  terminate_owned_group
  if [[ -d "$result_dir" && ! -L "$result_dir" ]]; then
    [[ -r "$nvme_aer_path" ]] && nvme_aer=$(current_nvme_aer)
    [[ -r "$root_aer_path" ]] && root_aer=$(current_root_aer)
    if [[ ! -e "${result_dir}/final-health.txt" && ! -L "${result_dir}/final-health.txt" ]]; then
      printf 'runner_exit=%s\nnvme_aer_baseline=%s\nnvme_aer_final=%s\nroot_aer_baseline=%s\nroot_aer_final=%s\n' \
        "$status" "$nvme_aer_baseline" "$nvme_aer" "$root_aer_baseline" "$root_aer" \
        >"${result_dir}/final-health.txt"
    fi
    if [[ ! -e "${result_dir}/SHA256SUMS" && ! -L "${result_dir}/SHA256SUMS" ]]; then
      (
        cd "$result_dir"
        find . -maxdepth 1 -type f ! -name SHA256SUMS -printf '%P\0' |
          sort -z | xargs -0 -r sha256sum >SHA256SUMS
      )
    fi
  fi
}
trap 'finalize "$?"' EXIT
trap 'exit 130' INT TERM HUP

check_aer() {
  local nvme_aer root_aer
  nvme_aer=$(current_nvme_aer)
  root_aer=$(current_root_aer)
  [[ "$nvme_aer" == "$nvme_aer_baseline" && "$root_aer" == "$root_aer_baseline" ]] || \
    fail "corrected-event counter changed; refusing further component work"
}

aer_matches_baseline() {
  local nvme_aer root_aer
  nvme_aer=$(current_nvme_aer) || return 1
  root_aer=$(current_root_aer) || return 1
  [[ "$nvme_aer" == "$nvme_aer_baseline" && "$root_aer" == "$root_aer_baseline" ]]
}

run_arm() {
  local sentinel=$1 seed=$2 arm=$3 cell output error receipt code leader pgid
  local aer_abort=0 authority=()
  cell="${sentinel}-s${seed}"
  output="${result_dir}/${cell}-${arm}.jsonl"
  error="${result_dir}/${cell}-${arm}.stderr.log"
  receipt="${result_dir}/${cell}-${arm}.exit-code"
  [[ ! -e "$output" && ! -e "$error" && ! -e "$receipt" ]] || \
    fail "arm evidence path collision: ${cell}-${arm}"
  if [[ "$arm" != control-before ]]; then
    authority=(--control-authority-json "${result_dir}/${cell}-control-before.jsonl")
  fi
  check_aer
  setsid env -u ZE_AFFINITY_MASK \
    ONEAPI_DEVICE_SELECTOR=level_zero:0 \
    PYTHONNOUSERSITE=1 \
    PYTHONSAFEPATH=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LD_LIBRARY_PATH=/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib:/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib \
    XDG_CACHE_HOME="${cache_root}/xdg" \
    TRITON_CACHE_DIR="${cache_root}/triton" \
    TORCHINDUCTOR_CACHE_DIR="${cache_root}/torchinductor" \
    timeout --signal=TERM --kill-after=30s 1200s \
    "$python" "$gate" \
      --model-path "$model" \
      --model-revision "$model_revision" \
      --sentinel "$sentinel" \
      --seed "$seed" \
      --arm "$arm" \
      "${authority[@]}" >"$output" 2>"$error" &
  leader=$!
  owned_pgid=$leader
  pgid=$(ps -o pgid= -p "$leader" 2>/dev/null | tr -d ' ' || true)
  if [[ "$pgid" != "$leader" ]]; then
    terminate_owned_group
    set +e
    wait "$leader"
    code=$?
    set -e
    owned_pgid=
    printf '%s\n' "$code" >"$receipt"
    fail "${cell}-${arm} did not enter its owned process group"
  fi
  while kill -0 "$leader" 2>/dev/null; do
    sleep 1
    if ! aer_matches_baseline; then
      aer_abort=1
      printf 'nvme_aer=%s\nroot_aer=%s\n' \
        "$(current_nvme_aer)" "$(current_root_aer)" \
        >"${result_dir}/${cell}-${arm}.aer-abort.txt"
      terminate_owned_group
      break
    fi
  done
  set +e
  wait "$leader"
  code=$?
  set -e
  owned_pgid=
  printf '%s\n' "$code" >"$receipt"
  [[ "$aer_abort" == 0 ]] || fail "${cell}-${arm} stopped on a corrected-event increment"
  check_aer
  [[ "$code" == 0 ]] || fail "${cell}-${arm} failed with exit ${code}"
}

for sentinel in l0-attn l0-mlp l47-attn l47-mlp; do
  for seed in 20260826 20260827 20260830; do
    run_arm "$sentinel" "$seed" control-before
    run_arm "$sentinel" "$seed" candidate
    run_arm "$sentinel" "$seed" control-after
  done
done

set +e
"$python" "$summarizer" --result-dir "$result_dir" \
  >"${result_dir}/summary.stdout.json" 2>"${result_dir}/summary.stderr.log"
summary_code=$?
set -e
printf '%s\n' "$summary_code" >"${result_dir}/summary.exit-code"
check_aer
[[ "$summary_code" == 0 ]] || fail "candidate failed the frozen exact/material gate"
printf 'PASS: HC exact-confirmation A1\n'

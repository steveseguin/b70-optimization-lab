#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
runner_path="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/run-q38-hc-gate-mix-exact-staged-a1.sh"
vllm=/home/steve/src/vllm-current-main
python=/home/steve/.venvs/vllm-xpu/bin/python3
python_real=/home/steve/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12
torch_root=/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch
gate="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/hc-gate-mix-exact-staged-xpu-graph-gate.py"
core="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/hc_gate_mix_exact_staged.py"
authority="${vllm}/vllm/models/qwen4_exp/amd/ops/hc.py"
clearance_validator="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/validate-q38-root-nvme-link-clearance-v1.py"
publisher="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/publish-q38-hc-gate-mix-a1-evidence.py"
clearance=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/host/20260901-root-nvme-link-clearance-v1.json
result_final=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260901-hc-gate-mix-exact-staged-a1
result="${result_final}.staging"
frozen="${result}/frozen"
staged_gate="${frozen}/$(basename "$gate")"
staged_core="${frozen}/$(basename "$core")"
staged_validator="${frozen}/$(basename "$clearance_validator")"
staged_publisher="${frozen}/$(basename "$publisher")"
cache_root=/dev/shm/q38-hc-gate-mix-exact-staged-a1
nvme_aer_path=/sys/bus/pci/devices/0000:01:00.0/aer_dev_correctable
root_aer_path=/sys/bus/pci/devices/0000:00:03.1/aer_rootport_total_err_cor
loader=/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib:/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib

expected_self=5882efc7f9950be68664567e961d73fed2d726df0ed5e1f7acc5c4ad9aed0417
expected_gate=3af1fd48b573cbb11a54bcd8809bae74ab63571353d13343771534bc72bfce97
expected_core=02989e1fc50b3c95b677d5b7b4916d354ddc8c3e973c37b1cd75d538ea8d040e
expected_clearance_validator=2293b3588a275e15a630b813d7a273e650eb64c49eaacedcf212f99fe485d5a5
expected_publisher=fc8cf0244f091ce8b6526407982a991aaad6d8813d9349161d7e01e878b6a67e
expected_vllm=cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9
expected_authority=a2ed67ce6240a150a75247097f0a49b4652d5bf1f5db1cdaf34ad5ec52faa8da
expected_python=202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8
expected_torch_init=0387d8b811b289287479c8bfdf4e1dac3a71b246f938d82da1331cf2dc8bf001
expected_torch_version_file=ce01b6efd84e9f55d779a8b72568ca4f542f8e41a2b5276954a4a63c09999a5d
expected_python_version=3.12.13
expected_torch_version=2.11.0+xpu
expected_torch_git=70d99e998b4955e0049d13a98d77ae1b14db1f45
expected_torch_xpu=20250302

started=0
active_pgid=""
nvme_aer_baseline=""
root_aer_baseline=""
failure_reason=""

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
digest() { sha256sum "$1" | cut -d' ' -f1; }
require_hash() {
  local path=$1 expected=$2 label=$3
  [[ -f "$path" && ! -L "$path" ]] || fail "$label is not a regular file"
  [[ "$(digest "$path")" == "$expected" ]] || fail "$label drifted"
}
canonical_self_hash() {
  sed 's/^expected_self=.*/expected_self=SELF_HASH/' "$0" | sha256sum | cut -d' ' -f1
}
current_nvme_aer() { awk '$1 == "TOTAL_ERR_COR" {print $2}' "$nvme_aer_path"; }
current_root_aer() { awk 'NR == 1 {print $1}' "$root_aer_path"; }
active_runtime_processes() {
  pgrep -af 'vllm serve|VLLM::EngineCore|Worker_TP|vllm\.entrypoints\.openai\.api_server|hc-gate-mix-exact-staged-xpu-graph-gate\.py' || true
}

revalidate_execution_identity() {
  local source type target
  [[ "$(readlink -f -- "$0")" == "$runner_path" ]] || \
    fail "runner canonical path changed after admission"
  [[ "$(canonical_self_hash)" == "$expected_self" ]] || fail "runner source changed after admission"
  [[ "$(git -C "$vllm" rev-parse HEAD)" == "$expected_vllm" ]] || fail "vLLM head changed after admission"
  [[ -z "$(git -C "$vllm" status --porcelain --untracked-files=no)" ]] || \
    fail "vLLM tracked source changed after admission"
  require_hash "$authority" "$expected_authority" "live HC authority source"
  [[ -L "$python" && "$(readlink -f "$python")" == "$python_real" ]] || \
    fail "Python interpreter target changed after admission"
  [[ "$(digest "$python")" == "$expected_python" ]] || \
    fail "Python interpreter changed after admission"
  require_hash "$torch_root/__init__.py" "$expected_torch_init" "Torch package identity"
  require_hash "$torch_root/version.py" "$expected_torch_version_file" "Torch version identity"
  "$python" -B - "$expected_python_version" "$expected_torch_version" \
    "$expected_torch_git" "$expected_torch_xpu" <<'PY'
import sys
import torch

expected_python, expected_torch, expected_git, expected_xpu = sys.argv[1:]
assert sys.version.split()[0] == expected_python
assert torch.__version__ == expected_torch
assert torch.version.git_version == expected_git
assert str(torch.version.xpu) == expected_xpu
PY
  require_hash "$gate" "$expected_gate" "live XPU graph gate"
  require_hash "$core" "$expected_core" "live candidate core"
  require_hash "$clearance_validator" "$expected_clearance_validator" "live clearance validator"
  require_hash "$publisher" "$expected_publisher" "live evidence publisher"
  require_hash "$staged_gate" "$expected_gate" "staged XPU graph gate"
  require_hash "$staged_core" "$expected_core" "staged candidate core"
  require_hash "$staged_validator" "$expected_clearance_validator" "staged clearance validator"
  require_hash "$staged_publisher" "$expected_publisher" "staged evidence publisher"
  [[ "$(digest "$clearance")" == "$clearance_sha" && \
     "$(digest "${result}/clearance.json")" == "$clearance_sha" ]] || \
    fail "clearance receipt changed after immutable staging"
  "$python" "$staged_validator" --clearance-json "$clearance" >/dev/null || \
    fail "live root-NVMe clearance revalidation failed"
  read -r source type target < <(findmnt -nro SOURCE,FSTYPE,TARGET --target /mnt/usb-models)
  [[ "$source" == /dev/sda2 && "$type" == fuseblk && "$target" == /mnt/usb-models ]] || \
    fail "external evidence mount changed after admission"
  [[ -z "$(active_runtime_processes)" ]] || \
    fail "a Qwen/vLLM or gate process became active after admission"
  [[ "$(current_nvme_aer)" == "$nvme_aer_baseline" && \
     "$(current_root_aer)" == "$root_aer_baseline" ]] || \
    fail "corrected-event baseline changed after admission"
}

stop_active() {
  local _
  if [[ "$active_pgid" =~ ^[1-9][0-9]*$ ]] && kill -0 -- "-${active_pgid}" 2>/dev/null; then
    kill -TERM -- "-${active_pgid}" 2>/dev/null || true
    for _ in $(seq 1 50); do
      kill -0 -- "-${active_pgid}" 2>/dev/null || break
      sleep 0.1
    done
    kill -0 -- "-${active_pgid}" 2>/dev/null && \
      kill -KILL -- "-${active_pgid}" 2>/dev/null || true
  fi
  active_pgid=""
}

finalize() {
  local rc=$? status nvme_final root_final nvme_delta root_delta publish_rc=0
  local publication_output=""
  trap - EXIT INT TERM HUP
  set +e
  stop_active
  if (( started == 1 )); then
    if [[ -d "$cache_root" && ! -L "$cache_root" ]]; then
      find "$cache_root" -mindepth 1 -delete 2>/dev/null
      rmdir "$cache_root" 2>/dev/null
    fi
    nvme_final=$(current_nvme_aer 2>/dev/null || printf '%s' -1)
    root_final=$(current_root_aer 2>/dev/null || printf '%s' -1)
    if [[ "$nvme_final" =~ ^[0-9]+$ && "$root_final" =~ ^[0-9]+$ && \
          "$nvme_aer_baseline" =~ ^[0-9]+$ && "$root_aer_baseline" =~ ^[0-9]+$ && \
          "$nvme_final" -ge "$nvme_aer_baseline" && "$root_final" -ge "$root_aer_baseline" ]]; then
      nvme_delta=$((nvme_final - nvme_aer_baseline))
      root_delta=$((root_final - root_aer_baseline))
    else
      nvme_delta=-1
      root_delta=-1
    fi
    if (( nvme_delta != 0 || root_delta != 0 )); then
      [[ -n "$failure_reason" ]] || failure_reason="corrected-event counter changed"
      (( rc != 0 )) || rc=70
    fi
    if [[ -e "$cache_root" ]]; then
      [[ -n "$failure_reason" ]] || failure_reason="exclusive cache teardown failed"
      (( rc != 0 )) || rc=70
    fi
    status=failed_closed
    (( rc == 0 )) && status=pass
    [[ -n "$failure_reason" || "$status" == pass ]] || failure_reason="runner failed before completion"
    publication_output=$("$python" "${result}/frozen/$(basename "$publisher")" \
      --stage-dir "$result" --final-dir "$result_final" --status "$status" \
      --runner-exit-code "$rc" --nvme-baseline "$nvme_aer_baseline" \
      --nvme-final "$nvme_final" --nvme-delta "$nvme_delta" \
      --root-baseline "$root_aer_baseline" --root-final "$root_final" \
      --root-delta "$root_delta" --failure-reason "$failure_reason" 2>&1) || publish_rc=$?
    if (( publish_rc != 0 )); then
      printf 'FAIL: evidence publication: %s\n' "$publication_output" >&2
      [[ -n "$failure_reason" ]] || failure_reason="transactional evidence publication failed"
      (( rc != 0 )) || rc=70
    elif [[ "$status" == pass ]]; then
      printf 'PASS: HC gate-mix exact-staged A1 published: %s\n' "$result_final"
    fi
  fi
  exit "$rc"
}
trap finalize EXIT
trap 'failure_reason="interrupted"; exit 130' INT HUP
trap 'failure_reason="terminated"; exit 143' TERM

[[ $# == 0 ]] || fail "this frozen component runner takes no arguments"
[[ "${Q38_HC_GATE_MIX_A1_VALIDATE_ONLY:-0}" =~ ^[01]$ ]] || fail "invalid validate-only selector"
[[ "$(readlink -f -- "$0")" == "$runner_path" ]] || fail "runner canonical path drifted"
[[ "$(canonical_self_hash)" == "$expected_self" ]] || fail "runner source drifted"
require_hash "$gate" "$expected_gate" "XPU graph gate"
require_hash "$core" "$expected_core" "candidate core"
require_hash "$clearance_validator" "$expected_clearance_validator" "root-NVMe clearance validator"
require_hash "$publisher" "$expected_publisher" "evidence publisher"
require_hash "$authority" "$expected_authority" "live HC authority source"
require_hash "$torch_root/__init__.py" "$expected_torch_init" "Torch package identity"
require_hash "$torch_root/version.py" "$expected_torch_version_file" "Torch version identity"
[[ -L "$python" && "$(readlink -f "$python")" == "$python_real" ]] || fail "Python interpreter target drifted"
[[ "$(digest "$python")" == "$expected_python" ]] || fail "Python interpreter drifted"
[[ "$(git -C "$vllm" rev-parse HEAD)" == "$expected_vllm" ]] || fail "vLLM head drifted"
[[ -z "$(git -C "$vllm" status --porcelain --untracked-files=no)" ]] || fail "vLLM tracked source is dirty"
bash -n "$0"
"$python" -B - "$expected_python_version" "$expected_torch_version" \
  "$expected_torch_git" "$expected_torch_xpu" <<'PY'
import sys
import torch

expected_python, expected_torch, expected_git, expected_xpu = sys.argv[1:]
assert sys.version.split()[0] == expected_python
assert torch.__version__ == expected_torch
assert torch.version.git_version == expected_git
assert str(torch.version.xpu) == expected_xpu
PY
"$python" -B -c \
  'import ast, pathlib, sys; [ast.parse(pathlib.Path(p).read_text()) for p in sys.argv[1:]]' \
  "$gate" "$core" "$clearance_validator" "$publisher"

if [[ "${Q38_HC_GATE_MIX_A1_VALIDATE_ONLY:-0}" == 1 ]]; then
  printf 'PASS: HC gate-mix exact-staged A1 static validation\n'
  exit 0
fi

[[ "${Q38_HC_GATE_MIX_A1_AUTHORIZED:-}" == I_UNDERSTAND_THIS_USES_ONE_B70 ]] || \
  fail "explicit one-B70 authorization is missing"
read -r evidence_source evidence_type evidence_target < <(
  findmnt -nro SOURCE,FSTYPE,TARGET --target /mnt/usb-models
)
[[ "$evidence_source" == /dev/sda2 && "$evidence_type" == fuseblk && \
   "$evidence_target" == /mnt/usb-models ]] || fail "external evidence mount identity drifted"
[[ -f "$clearance" && ! -L "$clearance" ]] || fail "fixed root-NVMe clearance receipt is missing"
"$clearance_validator" --clearance-json "$clearance" >/dev/null || \
  fail "fixed root-NVMe clearance receipt failed"
[[ -r "$nvme_aer_path" && -r "$root_aer_path" ]] || fail "AER counters are unavailable"
[[ ! -e "$result_final" && ! -L "$result_final" ]] || fail "final evidence path already exists"
[[ ! -e "$result" && ! -L "$result" ]] || fail "staging evidence path already exists"
[[ ! -e "$cache_root" && ! -L "$cache_root" ]] || fail "cache path already exists"
[[ -z "$(active_runtime_processes)" ]] || fail "a Qwen/vLLM or gate process is active"

exec 7>/tmp/b70-benchmark.lock
flock -n 7 || fail "the host benchmark lock is held"
exec 8>/tmp/b70-gpu0.lock
flock -n 8 || fail "the GPU0 benchmark lock is held"
exec 9>/tmp/q38-hc-gate-mix-exact-staged-a1.lock
flock -n 9 || fail "another HC gate-mix A1 runner owns the lock"
[[ -z "$(active_runtime_processes)" ]] || fail "a Qwen/vLLM or gate process became active"

nvme_aer_baseline=$(current_nvme_aer)
root_aer_baseline=$(current_root_aer)
[[ "$nvme_aer_baseline" =~ ^[0-9]+$ && "$root_aer_baseline" =~ ^[0-9]+$ ]] || \
  fail "could not establish exact AER baselines"

mkdir "$result"
started=1
mkdir -m 0700 "$cache_root"
for directory in xdg triton torchinductor; do
  mkdir -m 0700 "${cache_root}/${directory}"
done

clearance_sha=$(digest "$clearance")
install -m 0444 "$clearance" "${result}/clearance.json.tmp"
[[ "$(digest "${result}/clearance.json.tmp")" == "$clearance_sha" && \
   "$(digest "$clearance")" == "$clearance_sha" ]] || fail "clearance receipt changed while copying"
mv "${result}/clearance.json.tmp" "${result}/clearance.json"
mkdir -m 0700 "$frozen"
install -m 0400 "$gate" "$staged_gate"
install -m 0400 "$core" "$staged_core"
install -m 0400 "$clearance_validator" "$staged_validator"
install -m 0400 "$publisher" "$staged_publisher"
chmod 0500 "$frozen"
revalidate_execution_identity

timeout 30s xpu-smi discovery -j >"${result}/device-discovery.json.tmp"
jq -e '
  .device_list | length == 4 and
  [.[].device_name] == [
    "Intel(R) Arc(TM) Pro B70 Graphics",
    "Intel(R) Arc(TM) Pro B70 Graphics",
    "Intel(R) Arc(TM) Pro B70 Graphics",
    "Intel(R) Arc(TM) Pro B70 Graphics"
  ] and
  [.[].pci_bdf_address] == [
    "0000:23:00.0", "0000:27:00.0", "0000:43:00.0", "0000:47:00.0"
  ]
' "${result}/device-discovery.json.tmp" >/dev/null || fail "four-B70 topology drifted"
mv "${result}/device-discovery.json.tmp" "${result}/device-discovery.json"

env -i \
  HOME=/home/steve \
  PATH=/home/steve/.venvs/vllm-xpu/bin:/opt/intel/oneapi/compiler/2025.3/bin:/usr/local/bin:/usr/bin:/bin \
  LD_LIBRARY_PATH="$loader" \
  ONEAPI_DEVICE_SELECTOR=level_zero:0 \
  PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 \
  "$python" - "${result}/selected-device.json.tmp" <<'PY'
import json
from pathlib import Path
import sys
import torch

count = torch.xpu.device_count()
if not torch.xpu.is_available() or count != 1:
    raise SystemExit(f"selector exposed {count} XPUs instead of one")
name = torch.xpu.get_device_name(0)
if name != "Intel(R) Arc(TM) Pro B70 Graphics":
    raise SystemExit(f"selected device identity drifted: {name}")
Path(sys.argv[1]).write_text(
    json.dumps(
        {
            "schema_version": 1,
            "status": "pass",
            "selector": "ONEAPI_DEVICE_SELECTOR=level_zero:0",
            "visible_xpu_count": count,
            "device_name": name,
        },
        indent=2,
        sort_keys=True,
    ) + "\n",
    encoding="utf-8",
)
PY
jq -e '
  .status == "pass" and .visible_xpu_count == 1 and
  .selector == "ONEAPI_DEVICE_SELECTOR=level_zero:0" and
  .device_name == "Intel(R) Arc(TM) Pro B70 Graphics"
' "${result}/selected-device.json.tmp" >/dev/null || fail "one-B70 selector receipt failed"
mv "${result}/selected-device.json.tmp" "${result}/selected-device.json"

[[ "$(current_nvme_aer)" == "$nvme_aer_baseline" && \
   "$(current_root_aer)" == "$root_aer_baseline" ]] || \
  fail "corrected-event counter changed during device admission"
[[ -z "$(active_runtime_processes)" ]] || fail "a Qwen/vLLM or gate process became active"

{
  printf 'vllm_head=%s\n' "$expected_vllm"
  printf 'authority_sha256=%s\n' "$expected_authority"
  printf 'gate_sha256=%s\n' "$expected_gate"
  printf 'core_sha256=%s\n' "$expected_core"
  printf 'runner_sha256=%s\n' "$(digest "$0")"
  printf 'python_sha256=%s\n' "$expected_python"
  printf 'python_version=%s\n' "$expected_python_version"
  printf 'torch_version=%s\n' "$expected_torch_version"
  printf 'torch_git=%s\n' "$expected_torch_git"
  printf 'torch_xpu=%s\n' "$expected_torch_xpu"
  printf 'clearance_sha256=%s\n' "$clearance_sha"
  printf 'nvme_aer_baseline=%s\n' "$nvme_aer_baseline"
  printf 'root_aer_baseline=%s\n' "$root_aer_baseline"
  printf 'timing_order=control,candidate,candidate,control\n'
  printf 'gate_invocations=1\n'
  printf 'endpoint_authorized=false\n'
} >"${result}/identity.txt.tmp"
mv "${result}/identity.txt.tmp" "${result}/identity.txt"

# This is the last operation before the sole gate process starts.  The gate
# imports its adjacent staged core, never either mutable live source path.
revalidate_execution_identity
setsid timeout --signal=TERM --kill-after=30s 1200s env -i \
  HOME=/home/steve \
  PATH=/home/steve/.venvs/vllm-xpu/bin:/opt/intel/oneapi/compiler/2025.3/bin:/usr/local/bin:/usr/bin:/bin \
  LD_LIBRARY_PATH="$loader" \
  ONEAPI_DEVICE_SELECTOR=level_zero:0 \
  PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 \
  XDG_CACHE_HOME="${cache_root}/xdg" \
  TRITON_CACHE_DIR="${cache_root}/triton" \
  TORCHINDUCTOR_CACHE_DIR="${cache_root}/torchinductor" \
  "$python" "$staged_gate" >"${result}/gate-result.json.tmp" \
  2>"${result}/gate.stderr.log.tmp" &
leader=$!
active_pgid=$leader
pgid=$(ps -o pgid= -p "$leader" 2>/dev/null | tr -d ' ' || true)
[[ "$pgid" == "$leader" ]] || {
  failure_reason="component did not enter its owned process group"
  stop_active
  fail "$failure_reason"
}

aer_abort=0
while kill -0 "$leader" 2>/dev/null; do
  sleep 1
  nvme_now=$(current_nvme_aer 2>/dev/null || printf '%s' invalid)
  root_now=$(current_root_aer 2>/dev/null || printf '%s' invalid)
  if [[ "$nvme_now" != "$nvme_aer_baseline" || "$root_now" != "$root_aer_baseline" ]]; then
    aer_abort=1
    failure_reason="corrected-event counter changed during the component gate"
    printf 'nvme_aer=%s\nroot_aer=%s\n' "$nvme_now" "$root_now" \
      >"${result}/aer-abort.txt.tmp"
    mv "${result}/aer-abort.txt.tmp" "${result}/aer-abort.txt"
    stop_active
    break
  fi
done
set +e
wait "$leader"
gate_rc=$?
set -e
active_pgid=""
printf '%s\n' "$gate_rc" >"${result}/gate.exit-code.tmp"
mv "${result}/gate.exit-code.tmp" "${result}/gate.exit-code"
mv "${result}/gate-result.json.tmp" "${result}/gate-result.json"
mv "${result}/gate.stderr.log.tmp" "${result}/gate.stderr.log"
(( aer_abort == 0 )) || fail "$failure_reason"
revalidate_execution_identity
[[ "$(current_nvme_aer)" == "$nvme_aer_baseline" && \
   "$(current_root_aer)" == "$root_aer_baseline" ]] || \
  fail "corrected-event counter changed at component postflight"
(( gate_rc == 0 )) || {
  failure_reason="component gate failed with exit ${gate_rc}"
  fail "$failure_reason"
}
jq -e '
  .status == "passed" and
  .classification == "qwen38_hc_gate_mix_exact_staged_xpu_graph_component" and
  .scope == {"calls_per_target_token":97,"dtype":"bfloat16","hc_count":4,"shape":[1,10240]} and
  .correctness.exact_replays == 100 and
  .correctness.unique_hashes == 100 and
  .correctness.eager_exact == true and
  .correctness.graph_exact == true and
  .correctness.inputs_unchanged == true and
  .timing.order == ["control", "candidate", "candidate", "control"] and
  .timing.required_control_drift_max_percent == 2.0 and
  .timing.required_improvement_min_percent == 3.0 and
  .timing.passed == true and
  .endpoint_authorized == false
' "${result}/gate-result.json" >/dev/null || {
  failure_reason="component result contract failed"
  fail "$failure_reason"
}
[[ -z "$(active_runtime_processes)" ]] || {
  failure_reason="component left an active process"
  fail "$failure_reason"
}
revalidate_execution_identity
printf 'GATE_PASS_PENDING_EVIDENCE_PUBLICATION\n'

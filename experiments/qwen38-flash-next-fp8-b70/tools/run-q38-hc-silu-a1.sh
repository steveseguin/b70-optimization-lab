#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
gate="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/benchmark-q38-hc-silu-a1.py"
postflight="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/verify-q38-four-b70-postflight.py"
kernel_patch="${repo}/patches/qwen38-flash-next-fp8-b70/vllm-xpu-kernels/0009-Add-exact-Qwen4Exp-HC-SiLU-XPU-kernel.patch"
vllm_patch="${repo}/patches/qwen38-flash-next-fp8-b70/vllm/0034-Add-default-off-native-XPU-HC-SiLU-dispatch.patch"
vllm_source=/mnt/fast-ai/qwen38-build/vllm-q38-hc-silu-a1-src
runtime=/mnt/fast-ai/qwen38-build/runtime-q38-hc-silu-a1
candidate_dso="${runtime}/vllm_xpu_kernels/_xpu_C.abi3.so"
runtime_manifest="${runtime}/MANIFEST.sha256"
venv=/home/steve/.venvs/vllm-xpu
python="${venv}/bin/python"
cmplr=/opt/intel/oneapi/compiler/2025.3
output=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260831-q38-hc-silu-a1
rejected_boot=c36480de-9150-4182-9888-08c85d2d9de4
runtime_state_dir="/run/user/$(id -u)"
full_load_marker="${runtime_state_dir}/q38-flash-next-full-load.boot-id"
component_state="${runtime_state_dir}/q38-flash-next-component-chain.state"
component_state_lock="${component_state}.lock"

expected_self=464a12832c9f423aab7a064340aa96feaefc39de19511e7ab853e84b99efdff1
expected_gate=a254a5567ca8251dac49c060a15b73ced16132a712045c09ccc36a12418efb71
expected_postflight=cb42de925a4361f69a8922dacfda41cd02b6520f70df81011db2dd6a2c9b8753
expected_kernel_patch=12e5c31dea78ffeba4aadc209a78ae06e0a3d6b9f4f04ef497734f148264e3fb
expected_vllm_patch=a83179f2bfbf49347dd235fdac988379dc3e1df766d7c1b585205b5e437ddde5
expected_dso=f3e4735c4046b7e15f4e5d597c01b73e6647ff2a8f7b9a2d577518479379841a
expected_manifest=e6b4bb20d0ed079ad454634eced171f7af2ce1c8d9ab56b6833375270820e28a
expected_python=202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8
expected_vllm_envs=7fb4dd35511ef9bee8780e7aafc8112712a8fa5d65797c9c4975241d25fcaefa
expected_vllm_hc=53149c1c6b6d67362e6aa961e90baad02af8dd19b124cdb49be7b2fbe8db7952

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

hash_regular() {
  local path=$1 expected=$2 label=$3
  [[ -f "$path" && ! -L "$path" ]] || fail "$label is not a regular non-symlink: $path"
  [[ "$(sha256sum "$path" | cut -d' ' -f1)" == "$expected" ]] || fail "$label hash drifted"
}

canonical_self_hash() {
  sed 's/^expected_self=.*/expected_self=SELF_HASH/' "$0" | sha256sum | cut -d' ' -f1
}

component_pids() {
  pgrep -f -- "$gate" | awk -v self="$$" '$1 != self' | LC_ALL=C sort -un || true
}

cleanup_log=/dev/null
cleanup_armed=0
component_claimed=0
cleanup_component() {
  local -a pids=()
  mapfile -t pids < <(component_pids)
  ((${#pids[@]})) || return 0
  printf 'terminating exact component processes: %s\n' "${pids[*]}" >>"$cleanup_log"
  kill -TERM "${pids[@]}" 2>/dev/null || true
  for _ in {1..40}; do
    mapfile -t pids < <(component_pids)
    ((${#pids[@]})) || return 0
    sleep 0.1
  done
  kill -KILL "${pids[@]}" 2>/dev/null || true
}
cleanup_on_exit() {
  if [[ "$cleanup_armed" == 1 ]]; then cleanup_component || true; fi
}
trap cleanup_on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

[[ $# == 0 ]] || fail "this frozen component runner takes no arguments"
[[ "$(canonical_self_hash)" == "$expected_self" ]] || fail "runner source hash drifted"
hash_regular "$gate" "$expected_gate" gate
hash_regular "$postflight" "$expected_postflight" postflight
hash_regular "$kernel_patch" "$expected_kernel_patch" kernel-patch
hash_regular "$vllm_patch" "$expected_vllm_patch" vllm-patch
hash_regular "$candidate_dso" "$expected_dso" candidate-dso
hash_regular "$runtime_manifest" "$expected_manifest" runtime-manifest
hash_regular "$vllm_source/vllm/envs.py" "$expected_vllm_envs" vllm-envs
hash_regular "$vllm_source/vllm/models/qwen4_exp/amd/ops/hc.py" "$expected_vllm_hc" vllm-hc
[[ -L "$python" && "$(readlink -f "$python")" == /home/steve/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12 ]] || fail "python target drifted"
[[ "$(sha256sum "$python" | cut -d' ' -f1)" == "$expected_python" ]] || fail "python hash drifted"
(cd "$runtime" && sha256sum -c MANIFEST.sha256) >/dev/null || fail "runtime manifest failed"
[[ -z "$(find "$runtime" -type d -name __pycache__ -print -quit)" ]] || fail "runtime contains Python cache files"
[[ "$(find "$runtime" -type f ! -name MANIFEST.sha256 | wc -l)" == "$(wc -l <"$runtime_manifest")" ]] || fail "runtime contains an unmanifested or missing file"
readelf -d "$candidate_dso" | rg -q 'Shared library: \[libsycl\.so\.8\]' || fail "candidate lacks pinned SYCL 8"
! readelf -d "$candidate_dso" | rg -q 'Shared library: \[libsycl\.so\.9\]' || fail "candidate mixes SYCL 9"

if [[ "${Q38_HC_SILU_A1_VALIDATE_ONLY:-}" == 1 ]]; then
  printf 'VALID: q38-hc-silu-a1 static identity\n'
  exit 0
fi

[[ "${Q38_RUN_HC_SILU_A1:-}" == I_UNDERSTAND_THIS_USES_ONE_GPU ]] || \
  fail "set Q38_RUN_HC_SILU_A1=I_UNDERSTAND_THIS_USES_ONE_GPU"
boot=$(tr -d '\n' </proc/sys/kernel/random/boot_id)
[[ "$boot" != "$rejected_boot" ]] || fail "the prior event-chain failure boot is ineligible"
[[ ! -e "$output" ]] || fail "refusing to overwrite $output"
[[ "$(awk '/MemAvailable/ {print $2}' /proc/meminfo)" -ge 110000000 ]] || fail "host memory is below the component floor"
[[ "$(awk '/SwapFree/ {print $2}' /proc/meminfo)" -ge 8000000 ]] || fail "free swap is below the component floor"
read -r source fstype target < <(findmnt -nro SOURCE,FSTYPE,TARGET --target /mnt/usb-models)
[[ "$source" == /dev/sda2 && "$fstype" == fuseblk && "$target" == /mnt/usb-models ]] || fail "evidence drive is not authenticated"

# Serialize against full-model work and any other GPU0 component before making
# the boot-consuming claim. These descriptors remain held for the entire run.
exec 7>/tmp/b70-benchmark.lock
flock -n 7 || fail "the host benchmark lock is held"
exec 8>/tmp/b70-gpu0.lock
flock -n 8 || fail "the GPU0 benchmark lock is held"
exec 9>"${full_load_marker}.lock"
flock -n 9 || fail "the Flash-Next full-load lifecycle lock is held"
if [[ -e "$full_load_marker" ]]; then
  full_load_boot=$(tr -d '\n' <"$full_load_marker")
  [[ "$full_load_boot" != "$boot" ]] || fail "a Flash-Next full load already consumed this boot"
fi
exec 10>"$component_state_lock"
flock -n 10 || fail "the Flash-Next component-chain lock is held"
if [[ -e "$component_state" ]]; then
  read -r prior_component_status prior_component_boot <"$component_state" || \
    fail "the component-chain state is malformed"
  [[ "$prior_component_boot" != "$boot" ]] || \
    fail "the Flash-Next component chain already consumed this boot: $prior_component_status"
fi
state_tmp="${component_state}.tmp.$$"
[[ ! -e "$state_tmp" ]] || fail "component-chain temporary state already exists"
printf 'hc-silu-attempted %s\n' "$boot" >"$state_tmp"
mv -f -- "$state_tmp" "$component_state"
component_claimed=1

journal_cursor=$(timeout 15s journalctl -b -k -n 0 --show-cursor --no-pager | sed -n 's/^-- cursor: //p' | tail -1)
[[ -n "$journal_cursor" ]] || fail "could not capture the pre-device kernel-journal cursor"
discovery_before=$(timeout 30s xpu-smi discovery -j)
mapfile -t bdfs < <(jq -r '.device_list[].pci_bdf_address' <<<"$discovery_before")
[[ "${bdfs[*]}" == "0000:23:00.0 0000:27:00.0 0000:43:00.0 0000:47:00.0" ]] || fail "B70 order/topology drifted"
[[ -z "$(component_pids)" ]] || fail "another HC-SiLU component process is active"
pgrep -af '(^|/)(vllm|python)( |.* )serve ' >/dev/null && fail "a model server is active"

mkdir -p "$output"
cleanup_log="$output/cleanup.log"
: >"$cleanup_log"
printf '%s\n' "$boot" >"$output/boot-id.txt"
printf '%s\n' "$journal_cursor" >"$output/journal-cursor-before.txt"
printf '%s\n' "$discovery_before" >"$output/discovery-before.json"
awk '/MemAvailable|SwapFree/ {print}' /proc/meminfo >"$output/memory-before.txt"

loader="${runtime}/vllm_xpu_kernels:${venv}/lib:${venv}/lib/python3.12/site-packages/torch/lib:${cmplr}/lib:${cmplr}/opt/compiler/lib"
cleanup_armed=1
set +e
timeout --signal=TERM --kill-after=20s 900s env -i \
  HOME=/home/steve \
  PATH="${cmplr}/bin:${venv}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
  LD_LIBRARY_PATH="$loader" \
  LIBRARY_PATH="${cmplr}/lib:${cmplr}/opt/compiler/lib" \
  OCL_ICD_FILENAMES="${cmplr}/lib/libintelocl.so" \
  PYTHONPATH="${vllm_source}:${runtime}" \
  PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 \
  VLLM_TARGET_DEVICE=xpu ZE_AFFINITY_MASK=0 \
  "$python" "$gate" --output-dir "$output/gate" --candidate-dso "$candidate_dso" \
  >"$output/gate.log" 2>&1
code=$?
set -e
printf '%s\n' "$code" >"$output/exit-code.txt"
if [[ -n "$(component_pids)" ]]; then
  cleanup_component
  cleanup_armed=0
  [[ -z "$(component_pids)" ]] || fail "component cleanup left a process"
  fail "component left a process; it was terminated"
fi
cleanup_armed=0
timeout 30s xpu-smi discovery -j >"$output/discovery-after.json"
mapfile -t bdfs_after < <(jq -r '.device_list[].pci_bdf_address' "$output/discovery-after.json")
[[ "${bdfs_after[*]}" == "0000:23:00.0 0000:27:00.0 0000:43:00.0 0000:47:00.0" ]] || fail "postflight B70 order/topology drifted"
timeout --signal=TERM --kill-after=10s 90s env -i \
  HOME=/home/steve \
  PATH="${cmplr}/bin:${venv}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
  LD_LIBRARY_PATH="$loader" \
  OCL_ICD_FILENAMES="${cmplr}/lib/libintelocl.so" \
  PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 \
  ZE_AFFINITY_MASK=0,1,2,3 \
  "$python" "$postflight" --output "$output/four-b70-postflight.json" \
  >"$output/four-b70-postflight.log" 2>&1 || fail "bounded four-B70 postflight failed"
timeout 15s journalctl -b -k --after-cursor "$journal_cursor" --no-pager >"$output/journal-window.txt" || \
  fail "could not capture the bounded kernel-journal window"
rg -i '(xe|i915|drm).*(reset|fault|timed out|timeout|wedg|hang|error)|guc.*(reset|fault|timed out|timeout|wedg|hang|error)|device.*(lost|reset)|cat[_ ]error|page fault|gpu hang' \
  "$output/journal-window.txt" >"$output/journal-fault-matches.txt" || true
[[ ! -s "$output/journal-fault-matches.txt" ]] || fail "postflight kernel-journal fault signature found"
awk '/MemAvailable|SwapFree/ {print}' /proc/meminfo >"$output/memory-after.txt"
[[ "$code" == 0 ]] || fail "component failed with exit $code"
[[ -s "$output/gate/summary.json" ]] || fail "component lacks a complete summary"
jq -e '.status == "passed" and .timing.passed == true and .endpoint_authorized == false' "$output/gate/summary.json" >/dev/null || fail "component summary contract failed"
(cd "$output" && find . -type f ! -name evidence.sha256 -printf '%P\n' | LC_ALL=C sort | xargs -r sha256sum) >"$output/evidence.sha256"
(cd "$output" && sha256sum -c evidence.sha256) >/dev/null
[[ "$component_claimed" == 1 ]] || fail "component-chain claim was not recorded"
state_tmp="${component_state}.tmp.$$"
[[ ! -e "$state_tmp" ]] || fail "component-chain completion state already exists"
printf 'hc-silu-passed %s\n' "$boot" >"$state_tmp"
mv -f -- "$state_tmp" "$component_state"
printf 'COMPLETE: %s\n' "$output/gate/summary.json"

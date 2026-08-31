#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
vllm=/home/steve/src/vllm-current-main
kernels=/home/steve/src/vllm-xpu-kernels
python=/home/steve/.venvs/vllm-xpu/bin/python3
stage_root=/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a2
stage="${stage_root}/vllm_xpu_kernels"
build_evidence=/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a2-evidence
build_evidence_manifest="${build_evidence}/finalizer-evidence.sha256"
stage_manifest="${build_evidence}/runtime-stage.sha256"
accepted_stage=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70/vllm_xpu_kernels
result=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/grouped-serving-stage-eeee7d6-a2-qualification
model=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
config_dir="${repo}/experiments/qwen38-flash-next-fp8-b70/configs/moe-warps8-m1"
config_file="${config_dir}/E=128,N=640,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=fp8_w8a8,block_shape=[128,128].json"
loader_suffix="/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib:/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib"

inspector="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/inspect-q38-grouped-serving-stage-a2.py"
test_runner="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/run-q38-grouped-serving-stage-tests-a2.py"
gdn_wrapper="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/check-q38-flash-next-gdn-history-serving-a2.py"
gdn_historical="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/check-q38-flash-next-gdn-history-replay.py"
fullshape="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/fullshape-triton-fp8-moe-gate.py"
resolver="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/verify-moe-m1-selection.py"
health="${repo}/scripts/check-qwen36-xpu-xccl-health.sh"
xccl_probe="${repo}/tools/xccl_probe.py"
repeat_xccl="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/repeat-xccl-allreduce-gate.py"

expected_vllm=797769b34b6db5c934609b75dc04cc61ec66e5f9
expected_kernels=eeee7d671abfa964626baa18da2174bb92cac80a
expected_kernel_chain=$'eeee7d671abfa964626baa18da2174bb92cac80a\n042c6e877b667f03087091ce3ab58b80903afc20\na6ee94fd8fadb97dc033921f1019ef18f14d5dd0\n359466a262489bdf4e1774e3572202dc82a00718\nad25aa9f69a2171612b9c6b83dfa82c69559f9e4'
expected_a1_build_driver=b5c29a50c3e6e3b737312fcb2392df9e5b252ef38cd038674c1bf11d4c3bd336
expected_finalizer=d23491b666d83e7f57008239cf17d54f11e77674ec25164c8ea560750cfe1e76
expected_builder=5cbdadc200626ed9da03b6aa4808a59ee848348c671ce76d4d7ada4a37ca464f
expected_cmake_wrapper=3583e90ce3a76689137884f5dde26d73eb31b4ba73d36fbda12060f23a49e9cc
expected_build_evidence=2c049273bfc9e8dd429e2f74969cb9c4917a6e23833fcb8e8584ba8944a62aee
expected_stage_manifest=a4e83ec34d91b70a666dc170fcc3bda75562592c58fce198f29cfa4d25755d0d
expected_native=8d6d41a2259b4d4eda53edd9524d113d9190ae1b093a150fd79aa72a5c28dd76
expected_gdn=6c9ba1f12838b3eaa27e91610f0344fbf11671bfee204c6a9a68564fc654c17e
expected_grouped=c8ba41d4978b0095648acee6782b7fd300ebc26403b5d1f2f7bcfb87b3430c42
expected_inspector=b37a2e15d61826d1deca3b3dab03028e18b6e7f1a77776bd52b09a6d6d6d40d4
expected_test_runner=0966e8495123c2cc9681efba7ccb188152d193ab4c753ff6b009e8a44f5f8507
expected_gdn_wrapper=3d4fbd42f11442e9928304665f8713814c3ae90ad27999e3acebaa9e27677912
expected_gdn_historical=ca0c5956b491c9fcd8698a02eaf00f96c1f050cc7db50ebbf91560bf85b7abfd
expected_fullshape=505ac4b230456bd5eb9d83d14d54b31dec88e0ec607cf557f434b4184ca71aa8
expected_resolver=cafe4b1998dabbe60b4877615d0f9342ec479245713f6fe964786e246d7f9c1a
expected_health=b15dd4c248d8c4d7035c2d180b9ecc5354b1b20bdabb0c47c540b5003a1cfb78
expected_xccl_probe=6ecd340651a6780fdbe0bd57d346540efe168bf2e3175d54e10dd8660ed5b30a
expected_repeat_xccl=491484f98c45af2ea9bc9054f9764489de7f2b328aea8d0c8e99dd0e7d7b838a
expected_hc_test=b3ae2f1ea20f7262a31f61130ed77e2d164db88b7517b9dd8e1333c016987e42
expected_config_test=0ead359fbc11ac35e1a22d4b2d146ecea2de71138838eb097bfdfcd5ae31fb3e
expected_hc_source=5d9f99945f2f01396afdece710e69b719139bf57fb2232cb831b467b8f64737f
expected_tuned=91e5d8b692da3febbba7cb07ee4fdab319909da0c82c1fda95b92dc42d680464
expected_moe_hash=eb1a25f96c14a3343494d2c240b9033b9dffd386d295c73b588b5e5b08d3b718

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

digest() {
  sha256sum "$1" | cut -d' ' -f1
}

require_hash() {
  local path=$1 expected=$2 label=$3
  [[ -f "$path" && ! -L "$path" ]] || fail "$label is absent or not a regular file"
  [[ "$(digest "$path")" == "$expected" ]] || fail "$label hash drifted"
}

refuse_active_work() {
  local active
  active=$(/usr/bin/python3 - <<'PY'
from pathlib import Path
import os

markers = (
    b"vllm serve",
    b"VLLM::EngineCore",
    b"Worker_TP",
    b"build-q38-grouped-serving-stage-a1.sh",
    b"finalize-q38-grouped-serving-stage-a2.sh",
    b"build-xpu-serving-eeee7d6-a1",
)
ancestors = set()
pid = os.getpid()
while pid > 1 and pid not in ancestors:
    ancestors.add(pid)
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().split()
        pid = int(fields[3])
    except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError, IndexError):
        break
hits = []
for entry in Path("/proc").iterdir():
    if not entry.name.isdigit() or int(entry.name) in ancestors:
        continue
    try:
        command = (entry / "cmdline").read_bytes().replace(b"\0", b" ")
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        continue
    if any(marker in command for marker in markers):
        hits.append(entry.name)
print(" ".join(sorted(hits, key=int)))
PY
)
  [[ -z "$active" ]] || fail "conflicting build or model process is active: pid $active"
}

refuse_render_owners() {
  local own=$$ proc pid descriptor target
  for proc in /proc/[0-9]*; do
    pid=${proc##*/}
    [[ "$pid" == "$own" ]] && continue
    for descriptor in "${proc}"/fd/*; do
      target=$(readlink "$descriptor" 2>/dev/null || true)
      [[ "$target" == /dev/dri/renderD* ]] && fail "render node is owned by pid $pid"
    done
  done
}

verify_static_identity() {
  local mount_source mount_fstype mount_target
  read -r mount_source mount_fstype mount_target < <(findmnt -nro SOURCE,FSTYPE,TARGET --target /mnt/fast-ai)
  [[ "$mount_source" == /dev/nvme0n1p2 && "$mount_fstype" == ext4 && "$mount_target" == / ]] || fail "candidate stage is not on authenticated NVMe/ext4"
  read -r mount_source mount_fstype mount_target < <(findmnt -nro SOURCE,FSTYPE,TARGET --target /mnt/usb-models)
  [[ "$mount_source" == /dev/sda2 && "$mount_fstype" == fuseblk && "$mount_target" == /mnt/usb-models ]] || fail "evidence drive is not authenticated"
  (( $(df --output=avail -B1 /mnt/usb-models | tail -1) >= 107374182400 )) || fail "evidence drive has less than 100 GiB free"
  (( $(awk '/MemAvailable/ {print $2 * 1024}' /proc/meminfo) >= 107374182400 )) || fail "host has less than 100 GiB available memory"
  (( $(awk '/SwapFree/ {print $2 * 1024}' /proc/meminfo) >= 7516192768 )) || fail "host has less than 7 GiB free swap"
  [[ "$(git -C "$vllm" rev-parse HEAD)" == "$expected_vllm" ]] || fail "vLLM head drifted"
  [[ -z "$(git -C "$vllm" status --porcelain --untracked-files=no)" ]] || fail "vLLM tracked source is dirty"
  [[ "$(git -C "$kernels" rev-parse HEAD)" == "$expected_kernels" ]] || fail "kernel head drifted"
  [[ "$(git -C "$kernels" rev-list --max-count=5 HEAD)" == "$expected_kernel_chain" ]] || fail "kernel chain drifted"
  [[ -z "$(git -C "$kernels" status --porcelain --untracked-files=no)" ]] || fail "kernel tracked source is dirty"
  [[ "$(git -C "$kernels" status --porcelain)" == '?? third_party/' ]] || fail "kernel untracked state drifted"
  require_hash "${repo}/experiments/qwen38-flash-next-fp8-b70/tools/build-q38-grouped-serving-stage-a1.sh" "$expected_a1_build_driver" "A1 build driver"
  require_hash "${repo}/experiments/qwen38-flash-next-fp8-b70/tools/finalize-q38-grouped-serving-stage-a2.sh" "$expected_finalizer" "A2 finalizer"
  require_hash "${repo}/scripts/build-vllm-xpu-kernels-xpu-c-only.sh" "$expected_builder" "native builder"
  require_hash /home/steve/.venvs/vllm-xpu/bin/cmake "$expected_cmake_wrapper" "activated CMake wrapper"
  require_hash "$build_evidence_manifest" "$expected_build_evidence" "A2 finalizer-evidence manifest"
  require_hash "$stage_manifest" "$expected_stage_manifest" "candidate stage manifest"
  require_hash "$inspector" "$expected_inspector" "stage inspector"
  require_hash "$test_runner" "$expected_test_runner" "focused-test runner"
  require_hash "$gdn_wrapper" "$expected_gdn_wrapper" "GDN A2 wrapper"
  require_hash "$gdn_historical" "$expected_gdn_historical" "historical GDN gate"
  require_hash "$fullshape" "$expected_fullshape" "MoE component gate"
  require_hash "$resolver" "$expected_resolver" "M1 resolver"
  require_hash "$health" "$expected_health" "XPU/XCCL health helper"
  require_hash "$xccl_probe" "$expected_xccl_probe" "XCCL probe"
  require_hash "$repeat_xccl" "$expected_repeat_xccl" "repeat XCCL gate"
  require_hash "${vllm}/tests/models/qwen4_exp/test_amd_hc_grouped_up.py" "$expected_hc_test" "HC focused tests"
  require_hash "${vllm}/tests/models/qwen4_exp/test_config.py" "$expected_config_test" "Qwen config tests"
  require_hash "${vllm}/vllm/models/qwen4_exp/amd/low_latency_gemm.py" "$expected_hc_source" "HC grouped source"
  require_hash "$config_file" "$expected_tuned" "M1 tuned map"
}

verify_stage_closure() {
  [[ "$(cat "${build_evidence}/a1-build-exit-code.txt")" == 0 ]] || fail "A1 native builder did not pass"
  [[ "$(cat "${build_evidence}/a1-tee-exit-code.txt")" == 0 ]] || fail "A1 log capture did not pass"
  (cd "$repo" && sha256sum -c "$build_evidence_manifest") >/dev/null || fail "A2 finalizer evidence closure failed"
  [[ "$(awk 'END {print NR}' "$stage_manifest")" == 18 ]] || fail "candidate stage is not 18 files"
  (cd "$stage" && sha256sum -c "$stage_manifest") >/dev/null || fail "candidate stage manifest failed"
  require_hash "${stage}/_xpu_C.abi3.so" "$expected_native" "candidate native extension"
  require_hash "${stage}/libgdn_attn_kernels_xe_2.so" "$expected_gdn" "candidate GDN library"
  require_hash "${stage}/libgrouped_gemm_xe_2.so" "$expected_grouped" "candidate grouped library"
  for library in _xpu_C.abi3.so libgdn_attn_kernels_xe_2.so libgrouped_gemm_xe_2.so; do
    readelf -d "${stage}/${library}" | grep -Fq 'Library runpath: [$ORIGIN]' || fail "$library lacks isolated runpath"
  done
}

run_logged() {
  local log=$1
  shift
  set +e
  "$@" >"$log" 2>&1
  local rc=$?
  set -e
  printf '%s\n' "$rc" >"${log}.exit-code"
  [[ "$rc" == 0 ]] || fail "command failed with rc=$rc; see $log"
}

stage_env=(
  env
  ONEAPI_DEVICE_SELECTOR=level_zero:0
  ZE_AFFINITY_MASK=0
  VLLM_TARGET_DEVICE=xpu
  PYTHONNOUSERSITE=1
  PYTHONSAFEPATH=1
  PYTHONDONTWRITEBYTECODE=1
  "PYTHONPATH=${stage_root}:${vllm}"
  "LD_LIBRARY_PATH=${stage}:${loader_suffix}"
)
accepted_env=(
  env
  ONEAPI_DEVICE_SELECTOR=level_zero:0
  ZE_AFFINITY_MASK=0
  VLLM_TARGET_DEVICE=xpu
  PYTHONNOUSERSITE=1
  PYTHONSAFEPATH=1
  PYTHONDONTWRITEBYTECODE=1
  "PYTHONPATH=${accepted_stage%/vllm_xpu_kernels}:${vllm}"
  "LD_LIBRARY_PATH=${accepted_stage}:${loader_suffix}"
)

[[ $# == 0 ]] || fail "this frozen qualification takes no arguments"
[[ "${Q38_GROUPED_STAGE_A2_VALIDATE_ONLY:-0}" =~ ^[01]$ ]] || fail "invalid validate-only selector"
if [[ "${Q38_GROUPED_STAGE_A2_VALIDATE_ONLY:-0}" == 0 ]]; then
  exec 9>/tmp/q38-grouped-serving-stage-a2-qualification.lock
  flock -n 9 || fail "another stage qualification owns the lock"
fi
refuse_active_work
verify_static_identity
verify_stage_closure
[[ ! -e "$result" ]] || fail "qualification evidence already exists: $result"
if [[ "${Q38_GROUPED_STAGE_A2_VALIDATE_ONLY:-0}" == 1 ]]; then
  printf 'PASS: grouped serving stage A2 qualification validates without GPU work\n'
  exit 0
fi
refuse_render_owners

mkdir -p "$result"
started_epoch=$(date +%s)
printf '%s\n' "$(cat /proc/sys/kernel/random/boot_id)" >"${result}/boot-id.txt"
timeout 30s xpu-smi discovery -j >"${result}/xpu-discovery-before.json" 2>"${result}/xpu-discovery-before.err"
jq -e '.device_list | length == 4 and all(.[]; .device_name == "Intel(R) Arc(TM) Pro B70 Graphics")' "${result}/xpu-discovery-before.json" >/dev/null || fail "four-card identity failed"

run_logged "${result}/accepted-schema.log" timeout --signal=TERM --kill-after=30s 180s "${accepted_env[@]}" "$python" "$inspector" dump --label accepted --output "${result}/accepted-schema.json"
verify_stage_closure
run_logged "${result}/candidate-schema.log" timeout --signal=TERM --kill-after=30s 180s "${stage_env[@]}" "$python" "$inspector" dump --label candidate --output "${result}/candidate-schema.json"
run_logged "${result}/schema-compare.log" timeout --signal=TERM --kill-after=30s 60s "$python" "$inspector" compare --accepted "${result}/accepted-schema.json" --candidate "${result}/candidate-schema.json" --output "${result}/schema-compare.json"
verify_stage_closure

run_logged "${result}/hc-focused-tests.log" timeout --signal=TERM --kill-after=30s 1800s "${stage_env[@]}" "$python" "$test_runner" --suite hc
verify_stage_closure
run_logged "${result}/qwen-config-tests.log" timeout --signal=TERM --kill-after=30s 600s "${stage_env[@]}" "$python" "$test_runner" --suite config
verify_stage_closure

run_logged "${result}/gdn-preflight.log" timeout --signal=TERM --kill-after=30s 180s "${stage_env[@]}" "$python" "$gdn_wrapper" preflight --physical-gpu 0
run_logged "${result}/gdn-smoke.log" timeout --signal=TERM --kill-after=30s 600s "${stage_env[@]}" "$python" "$gdn_wrapper" run --physical-gpu 0 --mode smoke --json-out "${result}/gdn-smoke.json"
verify_stage_closure
run_logged "${result}/gdn-qualification-r1.log" timeout --signal=TERM --kill-after=30s 3600s "${stage_env[@]}" "$python" "$gdn_wrapper" run --physical-gpu 0 --mode qualification --json-out "${result}/gdn-qualification-r1.json"
verify_stage_closure
run_logged "${result}/gdn-qualification-r2.log" timeout --signal=TERM --kill-after=30s 3600s "${stage_env[@]}" "$python" "$gdn_wrapper" run --physical-gpu 0 --mode qualification --json-out "${result}/gdn-qualification-r2.json"
run_logged "${result}/gdn-compare.log" timeout --signal=TERM --kill-after=30s 120s "$python" "$gdn_wrapper" compare --json "${result}/gdn-qualification-r1.json" "${result}/gdn-qualification-r2.json" --json-out "${result}/gdn-compare.json"
jq -e '.status == "pass" and .valid == true and .result_count == 2 and .summary.pass_all == true and .summary.all_canonical_chunk_digests_equal == true and (.comparisons | length == 2) and all(.comparisons[]; .passed == true and .identity_equal == true and all(.binding_equal[]; . == true))' "${result}/gdn-compare.json" >/dev/null || fail "GDN fresh-process comparison did not pass"
verify_stage_closure

run_logged "${result}/moe-m1-selection.log" timeout --signal=TERM --kill-after=30s 180s "${stage_env[@]}" env "VLLM_TUNED_CONFIG_FOLDER=${config_dir}" "$python" "$resolver" --config-file "$config_file" --vllm-source "$vllm" --output "${result}/moe-m1-selection.json"
jq -e '.status == "passed" and .requested_m == 1 and .selected_batch_key == 1 and .effective_config.num_warps == 8' "${result}/moe-m1-selection.json" >/dev/null || fail "M1 resolver receipt failed"
run_logged "${result}/moe-m1-real-weight.log" timeout --signal=TERM --kill-after=30s 1800s "${stage_env[@]}" env "VLLM_TUNED_CONFIG_FOLDER=${config_dir}" "$python" "$fullshape" --tokens 1 --ep-rank 0 --weights layer0-rank0-checkpoint --routing balanced-global --repeats 100 --warmups 10 --hidden-seed 20260827 --model-path "$model"
jq -e --arg expected "$expected_moe_hash" '.status == "pass" and .finite == true and .unique_output_sha256 == 1 and .output_sha256_first == $expected and .identity.resolved_config.num_warps == 8' < <(tail -1 "${result}/moe-m1-real-weight.log") >/dev/null || fail "M1 real-weight retained-output gate failed"
verify_stage_closure

run_logged "${result}/xpu-xccl-health.log" timeout --signal=TERM --kill-after=30s 300s env ROOT="$repo" PYTHON=/home/steve/.venvs/vllm-xpu/bin/python PHYSICAL_DEVICES=0,1,2,3 XCCL_DEVICES=0,1,2,3 XCCL_NPROC=4 TIMEOUT_S=120 FI_TCP_IFACE=lo CCL_KVS_IFACE=lo "$health"
[[ "$(grep -Ec '^ok 2097152\.0$' "${result}/xpu-xccl-health.log")" == 4 ]] || fail "single-card health receipts are incomplete"
for rank in 0 1 2 3; do
  grep -Fxq "rank ${rank} allreduce ok 4.0" "${result}/xpu-xccl-health.log" || fail "rank $rank health receipt is absent"
done
run_logged "${result}/xccl-repeat.log" timeout --signal=TERM --kill-after=30s 300s env ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 ZE_AFFINITY_MASK=0,1,2,3 CCL_ATL_TRANSPORT=ofi FI_TCP_IFACE=lo CCL_KVS_IFACE=lo "$python" -m torch.distributed.run --standalone --nproc_per_node=4 "$repeat_xccl" --rows 1 --hidden 2560 --dtype bfloat16 --repeats 100
grep '^{' "${result}/xccl-repeat.log" | jq -s -e 'length == 4 and all(.[]; .world_size == 4 and .finite == true and .unique_output_sha256 == 1 and .rows == 1 and .hidden == 2560 and .repeats == 100) and ([.[].rank] | sort == [0,1,2,3]) and ([.[].output_sha256_first] | unique | length == 1)' >/dev/null || fail "repeat XCCL qualification failed"
verify_stage_closure

timeout 30s xpu-smi discovery -j >"${result}/xpu-discovery-after.json" 2>"${result}/xpu-discovery-after.err"
cmp -s <(jq -S '.device_list | map([.device_id,.device_name,.pci_bdf_address,.drm_device])' "${result}/xpu-discovery-before.json") <(jq -S '.device_list | map([.device_id,.device_name,.pci_bdf_address,.drm_device])' "${result}/xpu-discovery-after.json") || fail "card identity changed during qualification"
set +e
journalctl -k --since "@${started_epoch}" --no-pager >"${result}/kernel-journal.log" 2>"${result}/kernel-journal.err"
journal_rc=$?
set -e
printf '%s\n' "$journal_rc" >"${result}/kernel-journal.exit-code"
[[ "$journal_rc" == 0 ]] || fail "kernel journal capture failed"
! grep -Eiq 'xe 0000:(23|27|43|47):00\.0.*(reset|fault|timeout|timed out|fatal|wedged|failed)|i915.*(reset|fault|timeout|timed out|fatal|wedged|failed)|xpu.*(reset|fault|timeout|timed out|fatal|wedged|failed)|out of memory|oom-kill|killed process' "${result}/kernel-journal.log" || fail "device or OOM event appeared during qualification"
refuse_render_owners
verify_static_identity
verify_stage_closure
find "$result" -type f ! -name qualification-evidence.sha256 -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >"${result}/qualification-evidence.sha256"
printf 'PASS: grouped serving stage A2 qualification completed at %s\n' "$result"

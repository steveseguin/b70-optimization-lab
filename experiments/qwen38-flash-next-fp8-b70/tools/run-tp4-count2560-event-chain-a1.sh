#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
vllm=/home/steve/src/vllm-current-main
kernels=/home/steve/src/vllm-xpu-kernels
venv=/home/steve/.venvs/vllm-xpu
cmplr=/opt/intel/oneapi/compiler/2025.3
gate="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/tp4-count2560-event-chain-gate.py"
stage_root=/mnt/fast-ai/qwen38-build/runtime-q38-count2560-eventchain-a1
stage="${stage_root}/vllm_xpu_kernels"
ccl_root=/mnt/fast-ai/qwen38-build/oneccl-q38-count2560-eventchain-a1-runtime
libccl="${ccl_root}/lib/libccl.so.1.0"
ccl_kernels="${ccl_root}/lib/ccl/kernels"
python="${venv}/bin/python"
torchrun="${venv}/bin/torchrun"
output=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260831-tp4-count2560-event-chain-a1

expected_gate=27bf56ef24f2fc09694525256583e6db6beafb97a85d0e4c2c82c1e9f91f03f5
expected_python=202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8
expected_python_real=/home/steve/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12
expected_torchrun=0d8056324b7819d01abb5e07e62286c56cbafec423edde8cf9ab2ae2a719912c
expected_libccl=164091ac6aced05bfc658ae1e1cd722153f099714e9cee6f437c62bdd3731c1c
expected_ccl_kernels=0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9
expected_stage_manifest=d74343884d156298e4a386304bffc3f0a38c840ee5bdc229a0ecc5db361a6d8a
expected_xpu=776a080846bfe26c92f10ecb80982f45137802cf10af4a7d66b9c0d6af1cd339
expected_vllm=797769b34b6db5c934609b75dc04cc61ec66e5f9
expected_kernel_head=e421889999bc1e5a5f11044d14548b9afdba644d

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

replica_cleanup_armed=0
cleanup_log=/dev/null

replica_pids() {
  {
    pgrep -f -- "$gate" || true
    pgrep -f -- "$torchrun" || true
  } | awk -v self="$$" '$1 != self' | LC_ALL=C sort -un
}

cleanup_replica_processes() {
  local -a pids=()
  mapfile -t pids < <(replica_pids)
  ((${#pids[@]})) || return 0
  printf 'terminating exact-path component processes: %s\n' "${pids[*]}" >>"$cleanup_log"
  kill -TERM "${pids[@]}" 2>/dev/null || true
  for _ in {1..20}; do
    mapfile -t pids < <(replica_pids)
    ((${#pids[@]})) || return 0
    sleep 0.1
  done
  printf 'force-stopping exact-path component processes: %s\n' "${pids[*]}" >>"$cleanup_log"
  kill -KILL "${pids[@]}" 2>/dev/null || true
}

cleanup_on_exit() {
  if [[ "$replica_cleanup_armed" == 1 ]]; then
    cleanup_replica_processes || true
  fi
}

trap cleanup_on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

hash_is() {
  local path=$1 expected=$2 label=$3
  [[ -f "$path" && ! -L "$path" ]] || fail "$label is absent or not a regular non-symlink: $path"
  [[ "$(sha256sum "$path" | cut -d' ' -f1)" == "$expected" ]] || fail "$label hash drifted"
}

hash_symlink_target_is() {
  local path=$1 expected_real=$2 expected=$3 label=$4
  [[ -L "$path" && -f "$path" ]] || fail "$label is absent or not a regular symlink: $path"
  [[ "$(readlink -f "$path")" == "$expected_real" ]] || fail "$label target drifted"
  [[ "$(sha256sum "$path" | cut -d' ' -f1)" == "$expected" ]] || fail "$label hash drifted"
}

[[ $# == 0 ]] || fail "this frozen runner takes no arguments"
[[ "${Q38_RUN_COUNT2560_EVENT_CHAIN_A1:-}" == I_UNDERSTAND_THIS_USES_ALL_FOUR_GPUS ]] || \
  fail "set Q38_RUN_COUNT2560_EVENT_CHAIN_A1=I_UNDERSTAND_THIS_USES_ALL_FOUR_GPUS"
[[ ! -e "$output" ]] || fail "refusing to overwrite $output"
[[ "$(git -C "$vllm" rev-parse HEAD)" == "$expected_vllm" ]] || fail "vLLM head drifted"
[[ -z "$(git -C "$vllm" status --porcelain --untracked-files=no)" ]] || fail "vLLM tracked tree is dirty"
[[ "$(git -C "$kernels" rev-parse HEAD)" == "$expected_kernel_head" ]] || fail "kernel head drifted"
[[ -z "$(git -C "$kernels" status --porcelain --untracked-files=no)" ]] || fail "kernel tracked tree is dirty"
hash_is "$gate" "$expected_gate" gate
hash_symlink_target_is "$python" "$expected_python_real" "$expected_python" python
hash_is "$torchrun" "$expected_torchrun" torchrun
hash_is "$libccl" "$expected_libccl" libccl
hash_is "$ccl_kernels/kernels.spv" "$expected_ccl_kernels" oneCCL-kernels
hash_is "$stage_root/runtime-stage.sha256" "$expected_stage_manifest" stage-manifest
hash_is "$stage/_xpu_C.abi3.so" "$expected_xpu" XPU-extension
(cd "$stage" && sha256sum -c "$stage_root/runtime-stage.sha256") >/dev/null || fail "stage manifest failed"
nm -D --defined-only "$libccl" | grep -Fq 'ccl_b70_replay_last_bf16_allreduce_q38_count2560_event_chain' || \
  fail "candidate libccl lacks the Qwen bridge symbol"
readelf -d "$stage/_xpu_C.abi3.so" | grep -Fq 'Library runpath: [$ORIGIN]' || fail "stage extension lacks isolated runpath"
read -r source fstype target < <(findmnt -nro SOURCE,FSTYPE,TARGET --target /mnt/usb-models)
[[ "$source" == /dev/sda2 && "$fstype" == fuseblk && "$target" == /mnt/usb-models ]] || fail "evidence drive is not authenticated"
pgrep -af '(^|/)(vllm|python)( |.* )serve ' >/dev/null && fail "a model server is active"
[[ "$(xpu-smi discovery -j | jq '.device_list | length')" == 4 ]] || fail "four B70s are not visible"

mkdir -p "$output"
printf '%s\n' "$(cat /proc/sys/kernel/random/boot_id)" >"$output/boot-id.txt"
printf '%s\n' "$expected_vllm" >"$output/vllm-head.txt"
printf '%s\n' "$expected_kernel_head" >"$output/kernel-head.txt"

loader="${stage}:${ccl_root}/lib:${venv}/lib:${venv}/lib/python3.12/site-packages/torch/lib:${cmplr}/lib:${cmplr}/opt/compiler/lib"
run_codes=()
for replica in 1 2; do
  replica_dir="${output}/replica-${replica}"
  mkdir "$replica_dir"
  cleanup_log="${replica_dir}/cleanup.log"
  : >"$cleanup_log"
  replica_cleanup_armed=1
  set +e
  timeout --signal=TERM --kill-after=20s 600s env -i \
    HOME=/home/steve \
    PATH="${cmplr}/bin:${venv}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    LIBRARY_PATH="${cmplr}/lib:${cmplr}/opt/compiler/lib" \
    LD_PRELOAD="$libccl" \
    LD_LIBRARY_PATH="$loader" \
    OCL_ICD_FILENAMES="${cmplr}/lib/libintelocl.so" \
    PYTHONPATH="${stage_root}:${vllm}" \
    PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 \
    OMP_NUM_THREADS=1 ZE_AFFINITY_MASK=0,1,2,3 \
    CCL_ATL_TRANSPORT=ofi FI_PROVIDER=tcp FI_TCP_IFACE=lo CCL_KVS_IFACE=lo \
    CCL_ZE_IPC_EXCHANGE=pidfd CCL_SEND=direct CCL_RECV=direct \
    CCL_TOPO_P2P_ACCESS=1 CCL_KERNEL_PATH="$ccl_kernels" \
    CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 \
    CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 \
    CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
    CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096 \
    B70_ONECCL_ENABLE_Q38_COUNT2560_EVENT_CHAIN=1 \
    "$torchrun" --standalone --nproc-per-node=4 \
      "$gate" --output "$replica_dir/result.json" \
      >"$replica_dir/torchrun.log" 2>&1
  code=$?
  set -e
  run_codes+=("$code")
  printf '%s\n' "$code" >"$replica_dir/exit-code.txt"
  if [[ -n "$(replica_pids)" ]]; then
    cleanup_replica_processes
    replica_cleanup_armed=0
    [[ -z "$(replica_pids)" ]] || fail "replica $replica cleanup left a process running"
    fail "replica $replica left a process running; it was terminated"
  fi
  replica_cleanup_armed=0
  [[ "$code" == 0 || "$code" == 1 ]] || fail "replica $replica ended abnormally with $code"
  [[ -s "$replica_dir/result.json" ]] || fail "replica $replica lacks a complete result"
done

"$python" - "$output" "${run_codes[0]}" "${run_codes[1]}" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
codes = [int(value) for value in sys.argv[2:]]
results = []
for replica in (1, 2):
    path = root / f"replica-{replica}" / "result.json"
    if not path.is_file():
        raise SystemExit(f"replica {replica} did not produce a result")
    results.append(json.loads(path.read_text(encoding="utf-8")))
correct = all(result.get("passed_correctness") is True for result in results)
performance = all(result.get("passed_performance_gate") is True for result in results)
collective_hash_sets = []
consumer_hash_sets = []
for result in results:
    collective_hash_sets.append({
        tuple(sorted(rank["final_collective_hashes"].items()))
        for rank in result["ranks"]
    })
    consumer_hash_sets.append({
        json.dumps(rank["final_consumer_hashes"], sort_keys=True)
        for rank in result["ranks"]
    })
stable_hashes = (
    all(len(values) == 1 for values in collective_hash_sets + consumer_hash_sets)
    and collective_hash_sets[0] == collective_hash_sets[1]
    and consumer_hash_sets[0] == consumer_hash_sets[1]
)
classification = (
    "component_pass_endpoint_candidate"
    if correct and performance and stable_hashes and codes == [0, 0]
    else "component_closed_no_endpoint"
)
summary = {
    "schema_version": 1,
    "status": "passed" if classification.endswith("candidate") else "closed",
    "classification": classification,
    "scope": "two fresh-process combined clone-elision plus event-chain component replicas; not model throughput",
    "replica_exit_codes": codes,
    "passed_correctness_both": correct,
    "passed_performance_both": performance,
    "cross_replica_hashes_stable": stable_hashes,
    "saved_ms": [result["saved_ms"] for result in results],
    "paired_median_saved_ms": [result["paired_median_saved_ms"] for result in results],
    "p90_saved_ms": [result["p90_saved_ms"] for result in results],
    "saved_percent": [result["saved_percent"] for result in results],
    "positive_pairs": [result["positive_pairs"] for result in results],
    "result_sha256": [
        hashlib.sha256((root / f"replica-{replica}" / "result.json").read_bytes()).hexdigest()
        for replica in (1, 2)
    ],
}
(root / "comparison.json").write_text(
    json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print(json.dumps(summary, sort_keys=True))
PY

(cd "$output" && find . -type f ! -name evidence.sha256 -printf '%P\n' | LC_ALL=C sort | xargs -r sha256sum) >"$output/evidence.sha256"
(cd "$output" && sha256sum -c evidence.sha256) >/dev/null
printf 'COMPLETE: %s\n' "$output/comparison.json"

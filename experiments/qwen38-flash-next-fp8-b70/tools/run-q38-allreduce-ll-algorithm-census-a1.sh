#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
probe="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/probe-xpu-graph-xccl-sequence.py"
python=/home/steve/.venvs/vllm-xpu/bin/python
torchrun=/home/steve/.venvs/vllm-xpu/bin/torchrun
venv=/home/steve/.venvs/vllm-xpu
cmplr=/opt/intel/oneapi/compiler/2025.3
libccl=/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0
kernels="${venv}/lib/ccl/kernels"
result=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260901-allreduce-ll-algorithm-census-a1

expected_probe=d8aa76c000a9796ea6ae0c6ec42888fde7d751d4c7c4a7e4e551bb2d27b6bdf6
expected_python=202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8
expected_torchrun=0d8056324b7819d01abb5e07e62286c56cbafec423edde8cf9ab2ae2a719912c
expected_libccl=43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700
expected_libsycl=0336997fdfed9b2e6385e9f1cea2395eb5e130d3e5e9c943df5b0c10c1b5e57f
expected_libfabric=d849d56fd3f8f2581b4b0c17c1564f8145911a313c2c011d694aaf21e5e86b27
expected_kernels=0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
digest() { sha256sum "$1" | cut -d' ' -f1; }
require_hash() {
  local path=$1 expected=$2
  [[ -f "$path" && "$(digest "$path")" == "$expected" ]] || fail "identity drift: $path"
}

[[ $# == 0 ]] || fail "this frozen census takes no arguments"
[[ "${Q38_ALLREDUCE_CENSUS_VALIDATE_ONLY:-0}" =~ ^[01]$ ]] || fail "invalid validate-only selector"
require_hash "$probe" "$expected_probe"
require_hash "$python" "$expected_python"
require_hash "$torchrun" "$expected_torchrun"
require_hash "$libccl" "$expected_libccl"
require_hash "${venv}/lib/libsycl.so.8" "$expected_libsycl"
require_hash "${venv}/lib/libfabric.so.1" "$expected_libfabric"
require_hash "${kernels}/kernels.spv" "$expected_kernels"
[[ ! -e "$result" ]] || fail "evidence root already exists"
[[ -z "$(pgrep -af 'vllm serve|VLLM::EngineCore|Worker_TP|llama-server' || true)" ]] || fail "model server is active"

if [[ "${Q38_ALLREDUCE_CENSUS_VALIDATE_ONLY:-0}" == 1 ]]; then
  printf 'PASS: allreduce LL algorithm census validates without GPU work\n'
  exit 0
fi

exec 9>/tmp/q38-allreduce-ll-algorithm-census.lock
flock -n 9 || fail "another collective census owns the lock"
mkdir -p "$result"
install -m 0644 "$0" "${result}/runner.sh"
xpu-smi discovery -j >"${result}/device-discovery.json"
jq -e '.device_list | length == 4' "${result}/device-discovery.json" >/dev/null || fail "four-B70 discovery failed"
{
  printf 'boot_id=%s\n' "$(cat /proc/sys/kernel/random/boot_id)"
  printf 'probe_sha256=%s\n' "$expected_probe"
  printf 'libccl_sha256=%s\n' "$expected_libccl"
  printf 'libccl_source_commit=4ceafd1\n'
  printf 'shape=BF16[1,2560]\n'
  printf 'collectives_per_graph=97\n'
  printf 'changing_input_replays=100\n'
  printf 'threshold_bytes=4096\n'
} >"${result}/identity.txt"

algorithms=(ring ring_markers twoshots recursive_doubling)
for algorithm in "${algorithms[@]}"; do
  log="${result}/${algorithm}.log"
  rc_file="${result}/${algorithm}.rc"
  printf '%q ' timeout --signal=TERM --kill-after=20s 300s env \
    CCL_SYCL_ALLREDUCE_LL="$algorithm" \
    LD_PRELOAD="$libccl" \
    "$torchrun" --standalone --nproc-per-node=4 "$probe" \
    --hidden 2560 --collectives 97 --replays 100 >>"${result}/commands.sh"
  printf '> %q 2>&1\n' "$log" >>"${result}/commands.sh"
  set +e
  timeout --signal=TERM --kill-after=20s 300s env \
    PATH="${cmplr}/bin:${venv}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    LD_LIBRARY_PATH="${venv}/lib:${venv}/lib/python3.12/site-packages/torch/lib:${cmplr}/lib:${cmplr}/opt/compiler/lib" \
    LD_PRELOAD="$libccl" \
    OCL_ICD_FILENAMES="${cmplr}/lib/libintelocl.so" \
    PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 \
    OMP_NUM_THREADS=1 ZE_AFFINITY_MASK=0,1,2,3 \
    CCL_ATL_TRANSPORT=ofi FI_PROVIDER=tcp FI_TCP_IFACE=lo CCL_KVS_IFACE=lo \
    CCL_ZE_IPC_EXCHANGE=pidfd CCL_SEND=direct CCL_RECV=direct \
    CCL_TOPO_P2P_ACCESS=1 CCL_KERNEL_PATH="$kernels" \
    CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 \
    CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 \
    CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
    CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096 \
    CCL_SYCL_ALLREDUCE_LL="$algorithm" \
    "$torchrun" --standalone --nproc-per-node=4 "$probe" \
      --hidden 2560 --collectives 97 --replays 100 >"$log" 2>&1
  rc=$?
  set -e
  printf '%s\n' "$rc" >"$rc_file"
done

"$python" - "$result" <<'PY'
import json
import statistics
import sys
from pathlib import Path

root = Path(sys.argv[1])
algorithms = ("ring", "ring_markers", "twoshots", "recursive_doubling")
arms = {}
for algorithm in algorithms:
    rc = int((root / f"{algorithm}.rc").read_text())
    rows = []
    for line in (root / f"{algorithm}.log").read_text(errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if value.get("classification") == "xpu_graph_xccl_target_step_sequence":
            rows.append(value)
    passed = (
        rc == 0
        and len(rows) == 4
        and sorted(row["rank"] for row in rows) == [0, 1, 2, 3]
        and all(row["unique_composite_hashes"] == 100 for row in rows)
    )
    means = [row["mean_us_per_graph"] for row in rows]
    arms[algorithm] = {
        "return_code": rc,
        "rank_rows": len(rows),
        "passed": passed,
        "rank_mean_us_per_97_collectives": means,
        "median_rank_mean_us_per_97_collectives": (
            statistics.median(means) if means else None
        ),
        "slowest_rank_mean_us_per_97_collectives": max(means) if means else None,
    }
summary = {
    "schema_version": 1,
    "status": "complete",
    "classification": "tp4_graph_97_collective_ll_algorithm_census",
    "arms": arms,
    "all_arms_passed_exact_graph_replay": all(row["passed"] for row in arms.values()),
    "protected_results_changed": False,
}
(root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY

sha256sum "${result}/"* >"${result}/SHA256SUMS"
printf 'PASS: allreduce LL algorithm census complete: %s\n' "$result"

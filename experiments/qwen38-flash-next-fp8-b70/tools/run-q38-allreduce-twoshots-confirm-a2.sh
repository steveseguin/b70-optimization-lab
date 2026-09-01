#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
probe="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/probe-xpu-graph-xccl-sequence.py"
torchrun=/home/steve/.venvs/vllm-xpu/bin/torchrun
python=/home/steve/.venvs/vllm-xpu/bin/python
venv=/home/steve/.venvs/vllm-xpu
cmplr=/opt/intel/oneapi/compiler/2025.3
libccl=/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0
kernels="${venv}/lib/ccl/kernels"
result=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260901-allreduce-twoshots-confirm-a2

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
digest() { sha256sum "$1" | cut -d' ' -f1; }
[[ $# == 0 ]] || fail "this frozen confirmation takes no arguments"
[[ "${Q38_ALLREDUCE_CONFIRM_VALIDATE_ONLY:-0}" =~ ^[01]$ ]] || fail "invalid validate-only selector"
[[ "$(digest "$probe")" == d8aa76c000a9796ea6ae0c6ec42888fde7d751d4c7c4a7e4e551bb2d27b6bdf6 ]] || fail "probe drifted"
[[ "$(digest "$torchrun")" == 0d8056324b7819d01abb5e07e62286c56cbafec423edde8cf9ab2ae2a719912c ]] || fail "torchrun drifted"
[[ "$(digest "$libccl")" == 43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700 ]] || fail "libccl drifted"
[[ "$(digest "${kernels}/kernels.spv")" == 0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9 ]] || fail "kernel package drifted"
[[ ! -e "$result" ]] || fail "evidence root already exists"
[[ -z "$(pgrep -af 'vllm serve|VLLM::EngineCore|Worker_TP|llama-server' || true)" ]] || fail "model server is active"
if [[ "${Q38_ALLREDUCE_CONFIRM_VALIDATE_ONLY:-0}" == 1 ]]; then
  printf 'PASS: twoshots confirmation validates without GPU work\n'
  exit 0
fi

exec 9>/tmp/q38-allreduce-twoshots-confirm.lock
flock -n 9 || fail "another collective confirmation owns the lock"
mkdir -p "$result"
install -m 0644 "$0" "${result}/runner.sh"
xpu-smi discovery -j >"${result}/device-discovery.json"
jq -e '.device_list | length == 4' "${result}/device-discovery.json" >/dev/null || fail "four-B70 discovery failed"
{
  printf 'boot_id=%s\n' "$(cat /proc/sys/kernel/random/boot_id)"
  printf 'probe_sha256=%s\n' "$(digest "$probe")"
  printf 'libccl_sha256=%s\n' "$(digest "$libccl")"
  printf 'protocol=three fresh ring/twoshots pairs; 97 collectives; 200 changing-input graph replays\n'
} >"${result}/identity.txt"

for trial in 1 2 3; do
  if ((trial % 2)); then algorithms=(ring twoshots); else algorithms=(twoshots ring); fi
  for algorithm in "${algorithms[@]}"; do
    label="trial-${trial}-${algorithm}"
    log="${result}/${label}.log"
    printf '%s %s\n' "$trial" "$algorithm" >>"${result}/launch-order.txt"
    timeout --signal=TERM --kill-after=20s 300s env \
      PATH="${cmplr}/bin:${venv}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
      LD_LIBRARY_PATH="${venv}/lib:${venv}/lib/python3.12/site-packages/torch/lib:${cmplr}/lib:${cmplr}/opt/compiler/lib" \
      LD_PRELOAD="$libccl" OCL_ICD_FILENAMES="${cmplr}/lib/libintelocl.so" \
      PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 \
      OMP_NUM_THREADS=1 ZE_AFFINITY_MASK=0,1,2,3 \
      CCL_ATL_TRANSPORT=ofi FI_PROVIDER=tcp FI_TCP_IFACE=lo CCL_KVS_IFACE=lo \
      CCL_ZE_IPC_EXCHANGE=pidfd CCL_SEND=direct CCL_RECV=direct \
      CCL_TOPO_P2P_ACCESS=1 CCL_KERNEL_PATH="$kernels" \
      CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 \
      CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 \
      CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
      CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096 CCL_SYCL_ALLREDUCE_LL="$algorithm" \
      "$torchrun" --standalone --nproc-per-node=4 "$probe" \
        --hidden 2560 --collectives 97 --replays 200 >"$log" 2>&1 || fail "$label failed"
    ! grep -Fq '|CCL_ERROR|' "$log" || fail "$label emitted a oneCCL error"
  done
done

"$python" - "$result" <<'PY'
import json
import statistics
import sys
from pathlib import Path

root = Path(sys.argv[1])
trials = {}
for trial in (1, 2, 3):
    arms = {}
    for algorithm in ("ring", "twoshots"):
        rows = []
        for line in (root / f"trial-{trial}-{algorithm}.log").read_text().splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("classification") == "xpu_graph_xccl_target_step_sequence":
                rows.append(row)
        if len(rows) != 4 or sorted(row["rank"] for row in rows) != [0, 1, 2, 3]:
            raise RuntimeError(f"trial {trial} {algorithm} rank evidence is incomplete")
        if not all(row["unique_composite_hashes"] == 200 for row in rows):
            raise RuntimeError(f"trial {trial} {algorithm} exact replay gate failed")
        means = [row["mean_us_per_graph"] for row in rows]
        arms[algorithm] = {
            "rank_mean_us_per_97_collectives": means,
            "slowest_rank_mean_us_per_97_collectives": max(means),
        }
    control = arms["ring"]["slowest_rank_mean_us_per_97_collectives"]
    candidate = arms["twoshots"]["slowest_rank_mean_us_per_97_collectives"]
    trials[str(trial)] = {
        "arms": arms,
        "latency_reduction_percent": 100.0 * (1.0 - candidate / control),
    }
reductions = [row["latency_reduction_percent"] for row in trials.values()]
qualified = statistics.median(reductions) >= 3.0 and sum(x >= 3.0 for x in reductions) >= 2
summary = {
    "schema_version": 1,
    "status": "complete",
    "classification": "tp4_graph_97_collective_twoshots_confirmation",
    "trials": trials,
    "median_latency_reduction_percent": statistics.median(reductions),
    "trials_passing_three_percent": sum(x >= 3.0 for x in reductions),
    "qualified_component_positive": qualified,
    "protected_results_changed": False,
}
(root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY
sha256sum "${result}/"* >"${result}/SHA256SUMS"
printf 'PASS: twoshots confirmation complete: %s\n' "$result"

#!/usr/bin/env bash
set -Eeuo pipefail

base=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/launch-tp4-ep4-piecewise-mtp0-4352.sh
expected_base=533be64e1c7584448c07a5f8895301a32288f4b0472948a91d87235e78c6f09f
resource_dir=/var/tmp/q38-piecewise-graph-a7-resource
derived_base="${resource_dir}/derived-launcher-compile1.sh"
expected_derived_base=33d53c462d0cf24bdce2f81c4323c86ba598df724b28e9badc461e9f48ced971
runtime_classifier=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/classify-q38-runtime-conflicts.py
expected_runtime_classifier=ecd18d133eef946bacf2750717bc458eca8e64dc1d97beabe060bdf314bf2ab3
runtime_conflict_receipt="${resource_dir}/runtime-conflicts-derived-base-prelaunch.json"
ack='RUN qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1'

[[ $# == 3 && "${1:-}" == "--execute" && "${2:-}" == "--ack" && \
   "${3:-}" == "$ack" ]] || {
  printf 'FAIL: graph-anchor attempt-7 wrapper requires the frozen acknowledgement\n' >&2
  exit 2
}
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]] || {
  printf 'FAIL: graph base launcher hash changed\n' >&2
  exit 1
}
[[ "$(sha256sum "$runtime_classifier" | cut -d' ' -f1)" == "$expected_runtime_classifier" ]] || {
  printf 'FAIL: runtime-conflict classifier hash changed\n' >&2
  exit 1
}
[[ -d "$resource_dir" && ! -e "$derived_base" ]] || {
  printf 'FAIL: fresh attempt-7 ext4 derived-launcher path required\n' >&2
  exit 1
}
[[ ! -e "$runtime_conflict_receipt" && ! -e "${runtime_conflict_receipt%.json}.err" ]] || {
  printf 'FAIL: fresh derived-base runtime-conflict receipts required\n' >&2
  exit 1
}
[[ -z "${REASONING_PARSER:-}" ]] || {
  printf 'FAIL: reasoning parser must be absent\n' >&2
  exit 1
}
for forbidden in XPU_GRAPH VLLM_XPU_GRAPH VLLM_XPU_FORCE_GRAPH_WITH_COMM \
  VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE; do
  [[ -z "${!forbidden+x}" ]] || {
    printf 'FAIL: legacy graph control %s must be absent\n' "$forbidden" >&2
    exit 1
  }
done

export MODEL_PATH=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70
export VLLM_SRC=/home/steve/src/vllm-current-main
export KERNELS_SRC=/home/steve/src/vllm-xpu-kernels
export VLLM_PYTHON=/home/steve/.venvs/vllm-xpu/bin/python
export VLLM_BIN=/home/steve/.venvs/vllm-xpu/bin/vllm
export RUN_PARENT=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70
export CACHE_PARENT=/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70
export ATTEMPT=7
export PORT=19684
export MAX_MODEL_LEN=4352
export MTP=0
export MTP_EXACT=0
export KV_CACHE_MEMORY_BYTES=201326592
unset REASONING_PARSER PYTHONOPTIMIZE

awk '
  $0 == "repo_root=$(cd -- \"${script_dir}/../../..\" && pwd)" {
    print "repo_root=/home/steve/llm-optimizations"
    next
  }
  index($0, "journalctl -k --since") {
    sub(/journalctl -k/, "timeout --signal=TERM --kill-after=5s 30s journalctl -k")
  }
  $0 ~ /^pgrep -af .*another vLLM server is running/ {
    print "runtime_classifier=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/classify-q38-runtime-conflicts.py"
    print "expected_runtime_classifier=ecd18d133eef946bacf2750717bc458eca8e64dc1d97beabe060bdf314bf2ab3"
    print "runtime_conflict_receipt=/var/tmp/q38-piecewise-graph-a7-resource/runtime-conflicts-derived-base-prelaunch.json"
    print "[[ \"$(sha256sum \"${runtime_classifier}\" | cut -d\047 \047 -f1)\" == \"${expected_runtime_classifier}\" ]] || fail \"runtime-conflict classifier hash changed\""
    print "runtime_supervisor_starttime=$(awk \047{print $22}\047 \"/proc/$$/stat\")"
    print "[[ \"${runtime_supervisor_starttime}\" =~ ^[1-9][0-9]*$ ]] || fail \"derived-base process identity unavailable\""
    print "set +e"
    print "\"${runtime_classifier}\" --supervisor-pid \"$$\" --supervisor-starttime \"${runtime_supervisor_starttime}\" --supervisor-script \"${BASH_SOURCE[0]}\" >\"${runtime_conflict_receipt}\" 2>\"${runtime_conflict_receipt%.json}.err\""
    print "runtime_scan_rc=$?"
    print "set -e"
    print "(( runtime_scan_rc == 0 )) || fail \"structured runtime-conflict scan was non-clear rc=${runtime_scan_rc}\""
    print "jq -e \047.schema == \"neural.download.q38-runtime-conflict-scan.v3\" and .status == \"clear\" and (.conflicts | length) == 0 and (.errors | length) == 0 and (.vanished_races | type) == \"array\" and all(.vanished_races[]; .classification == \"vanished_race\" and .field == \"stat\") and .binding.supervisor.pid > 0 and (.scanned_processes | length) > 0\047 \"${runtime_conflict_receipt}\" >/dev/null || fail \"structured runtime-conflict receipt was not clear\""
    next
  }
  { print }
  $0 == "export TORCHINDUCTOR_CACHE_DIR=\"${compile_cache_dir}/torchinductor\"" {
    print "export TORCHINDUCTOR_COMPILE_THREADS=1"
    print "\"${python}\" - <<\047PY\047 >\"${run_dir}/torchinductor-compile-threads.txt\""
    print "import os"
    print "import torch._inductor.config as inductor_config"
    print "assert os.environ.get(\047TORCHINDUCTOR_COMPILE_THREADS\047) == \0471\047"
    print "assert inductor_config.compile_threads == 1, inductor_config.compile_threads"
    print "print(\047torchinductor_compile_threads_env=1\047)"
    print "print(f\047torchinductor_compile_threads_effective={inductor_config.compile_threads}\047)"
    print "PY"
  }
  index($0, "diagnostics=none") {
    print "  printf \047torchinductor_compile_threads_env=1\\n\047"
    print "  printf \047torchinductor_compile_threads_effective=1\\n\047"
  }
' "$base" >"$derived_base"
chmod 0500 "$derived_base"
[[ "$(sha256sum "$derived_base" | cut -d' ' -f1)" == "$expected_derived_base" ]] || {
  printf 'FAIL: mechanically derived compile-thread launcher hash mismatch\n' >&2
  exit 1
}
[[ "$(stat -c '%U:%G:%a:%F' "$derived_base")" == 'steve:steve:500:regular file' ]] || {
  printf 'FAIL: derived compile-thread launcher identity mismatch\n' >&2
  exit 1
}

exec "$derived_base" "$@"

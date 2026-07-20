#!/usr/bin/env bash
set -euo pipefail

# Narrow PTI Level Zero tracing wrapper for the final vLLM executable only.
# The outer DeepSeek launcher sets the model/runtime identity before invoking
# this script through VLLM_CLI.
unitrace_bin="${UNITRACE_BIN:-/home/steve/src/pti-gpu/build-unitrace/unitrace}"
unitrace_session="${UNITRACE_SESSION:?set UNITRACE_SESSION to an alphanumeric name}"
unitrace_result_dir="${UNITRACE_RESULT_DIR:?set UNITRACE_RESULT_DIR}"
vllm_bin="${UNITRACE_VLLM_BIN:-/home/steve/.venvs/deepseek-v4-xpu/bin/vllm}"
unitrace_mode="${UNITRACE_MODE:-full}"

test -x "${unitrace_bin}"
test -x "${vllm_bin}"
mkdir -p "${unitrace_result_dir}"

trace_args=(
  --start-paused \
  --session "${unitrace_session}" \
  --follow-child-process 1 \
  --host-timing \
  --chrome-call-logging \
  --pid \
  --tid \
  --result-dir "${unitrace_result_dir}"
)
case "${unitrace_mode}" in
  host)
    ;;
  full)
    trace_args+=(--device-timing --kernel-submission --chrome-kernel-logging)
    ;;
  *)
    echo "invalid UNITRACE_MODE=${unitrace_mode}; expected host or full" >&2
    exit 2
    ;;
esac

exec "${unitrace_bin}" "${trace_args[@]}" "${vllm_bin}" "$@"

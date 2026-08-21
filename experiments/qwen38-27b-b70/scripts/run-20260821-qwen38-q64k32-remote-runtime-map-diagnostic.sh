#!/usr/bin/env bash
set -euo pipefail

# Four fresh-process, no-clock runtime-map observations. This is not the
# 16-arm operator/clock campaign and cannot mutate a clock or XPU setting.

repo=/home/steve/b70-optimization-lab
python=/home/steve/.venvs/vllm-xpu/bin/python
venv_lib=/home/steve/.venvs/vllm-xpu/lib
torch_lib=/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib
diagnostic=$repo/experiments/qwen38-27b-b70/scripts/qwen38_q64k32_remote_runtime_map_diagnostic.py
campaign=$repo/experiments/qwen38-27b-b70/scripts/qwen38_mtp5_m6_fa_q64k32_remote_clock_campaign.py
control=/home/steve/staged-xpu-commitfix-graphfa-composite-20260820
candidate=/home/steve/qwen38-m6-head256-q64k32-attn-override-20260821-r2/runtime
result=/home/steve/qwen38-q64k32-remote-runtime-map-diagnostic-20260821-r1

diagnostic_sha=19f938ac71780648cbbce91129876025c4eb0e8646dd213209b1052bd18268e2
campaign_sha=7577f9313b60d4bb51b328eb63608ab8c3bf9af31b1e84e1390164f71ee1e2fb
diagnostic_authorized=true

bash_bin=/usr/bin/bash
env_bin=/usr/bin/env
git_bin=/usr/bin/git
hostname_bin=/usr/bin/hostname
mkdir_bin=/usr/bin/mkdir
realpath_bin=/usr/bin/realpath
sha256sum_bin=/usr/bin/sha256sum
awk_bin=/usr/bin/awk
kill_bin=/usr/bin/kill
sleep_bin=/usr/bin/sleep
pwd_bin=/usr/bin/pwd
clean_path=/usr/bin:/bin
clean_marker=qwen38-q64k32-runtime-map-management-v1

die() { printf 'error: %s\n' "$*" >&2; exit 2; }
verify() {
  local path=$1 expected=$2 actual
  [[ -f $path && $expected =~ ^[0-9a-f]{64}$ ]] || die "unfrozen/missing source: $path"
  actual=$("$sha256sum_bin" -- "$path" | "$awk_bin" '{print $1}')
  [[ $actual == "$expected" ]] || die "source SHA mismatch: $path"
}
usage() {
  printf 'usage: %s preflight | run | compare\n' "$0" >&2
  exit 2
}

action=${1:-}
[[ $# -eq 1 ]] || usage
[[ $action == preflight || $action == run || $action == compare ]] || usage
[[ $action != run || $diagnostic_authorized == true ]] || die 'diagnostic is not authorized'

if [[ ${QWEN38_RUNTIME_MAP_DRIVER_CLEAN:-} != "$clean_marker" ]]; then
  case $0 in
    /*) clean_driver=$0 ;;
    *) clean_driver=$PWD/$0 ;;
  esac
  cd -- /home/steve || die 'cannot enter management directory'
  exec "$env_bin" -i \
    HOME=/home/steve USER=steve LOGNAME=steve SHELL="$bash_bin" LANG=C.UTF-8 \
    PATH="$clean_path" PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 \
    QWEN38_RUNTIME_MAP_DRIVER_CLEAN="$clean_marker" \
    "$bash_bin" "$clean_driver" "$@"
fi
mapfile -t exported_names < <(compgen -e)
for name in "${exported_names[@]}"; do
  case $name in
    HOME|LANG|LOGNAME|PATH|PWD|PYTHONDONTWRITEBYTECODE|PYTHONHASHSEED|QWEN38_RUNTIME_MAP_DRIVER_CLEAN|SHELL|SHLVL|USER) ;;
    *) die "unexpected management environment: $name" ;;
  esac
done
mapfile -t defined_names < <(declare -F | "$awk_bin" '{print $3}')
[[ ${#exported_names[@]} -eq 11 && ${#defined_names[@]} -eq 3 ]] || \
  die 'management environment inventory differs'
for name in "${defined_names[@]}"; do
  case $name in
    die|usage|verify) ;;
    *) die "unexpected management function: $name" ;;
  esac
done
[[ $HOME == /home/steve && $USER == steve && $LOGNAME == steve && \
   $SHELL == /usr/bin/bash && $LANG == C.UTF-8 && $PATH == "$clean_path" && \
   $PWD == /home/steve && $("$pwd_bin" -P) == /home/steve && \
   $PYTHONHASHSEED == 0 && $PYTHONDONTWRITEBYTECODE == 1 && \
   $QWEN38_RUNTIME_MAP_DRIVER_CLEAN == "$clean_marker" && $SHLVL == 1 ]] || \
  die 'management environment values differ'

[[ $("$hostname_bin") == steve-TURIND8-2L2T ]] || die 'wrong host'
[[ $("$realpath_bin" -e -- "$repo") == "$repo" ]] || die 'repo is noncanonical'
[[ $("$git_bin" -C "$repo" branch --show-current) == main ]] || die 'requires main'
[[ -z $("$git_bin" -C "$repo" status --porcelain --untracked-files=normal) ]] || \
  die 'requires clean repo'
head=$("$git_bin" -C "$repo" rev-parse HEAD)
[[ $head == "$("$git_bin" -C "$repo" rev-parse origin/main)" ]] || \
  die 'requires main == origin/main'
verify "$diagnostic" "$diagnostic_sha"
verify "$campaign" "$campaign_sha"
[[ -x $python ]] || die 'XPU Python is absent'

management_python() {
  "$env_bin" -i \
    HOME=/home/steve USER=steve LOGNAME=steve SHELL="$bash_bin" LANG=C.UTF-8 \
    PATH="$clean_path" PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 \
    "$python" -B "$diagnostic" "$@"
}

management_python preflight >/dev/null
if [[ $action == preflight ]]; then
  printf 'PASS: no-clock runtime-map diagnostic preflight\n'
  exit 0
fi
if [[ $action == compare ]]; then
  management_python compare --output "$result/comparison.json" \
    "$result/arm-01.terminal.json" "$result/arm-02.terminal.json" \
    "$result/arm-03.terminal.json" "$result/arm-04.terminal.json"
  exit
fi

active_supervisor_pid=
active_supervisor_terminal=
active_supervisor_ordinal=
supervisor_spawn_state=idle
deferred_signal=
driver_signal_exit_code=
cleanup_running=false

handle_driver_signal() {
  local signal_name=$1 exit_code=$2
  driver_signal_exit_code=$exit_code
  if [[ $supervisor_spawn_state == spawning ]]; then
    deferred_signal=$signal_name
  elif [[ -n $active_supervisor_pid ]]; then
    "$kill_bin" -s "$signal_name" "$active_supervisor_pid" 2>/dev/null || true
  else
    exit "$exit_code"
  fi
}
abort_if_driver_signaled() {
  [[ -z $driver_signal_exit_code ]] || exit "$driver_signal_exit_code"
}
quiesce_active_supervisor() {
  local counter=0 supervisor_rc=0 owned_pid=$active_supervisor_pid
  [[ -n $owned_pid ]] || return 0
  if "$kill_bin" -0 "$owned_pid" 2>/dev/null; then
    "$kill_bin" -s TERM "$owned_pid" 2>/dev/null || true
    while "$kill_bin" -0 "$owned_pid" 2>/dev/null && [[ $counter -lt 600 ]]; do
      "$sleep_bin" 0.05
      counter=$((counter + 1))
    done
  fi
  if "$kill_bin" -0 "$owned_pid" 2>/dev/null; then
    printf 'FATAL: diagnostic supervisor did not quiesce within 30 seconds\n' >&2
    return 1
  fi
  set +e
  wait "$owned_pid"
  supervisor_rc=$?
  set -e
  if ! management_python validate-cleanup-terminal "$active_supervisor_terminal" \
      --ordinal "$active_supervisor_ordinal" --supervisor-pid "$owned_pid" >/dev/null; then
    printf 'FATAL: supervisor terminal does not prove owned worker-group absence (rc=%s)\n' \
      "$supervisor_rc" >&2
    return 1
  fi
  active_supervisor_pid=
  active_supervisor_terminal=
  active_supervisor_ordinal=
  supervisor_spawn_state=idle
  return 0
}
cleanup_active_supervisor() {
  local original_rc=$?
  [[ $cleanup_running == false ]] || exit "$original_rc"
  cleanup_running=true
  trap '' INT TERM HUP
  trap - EXIT
  quiesce_active_supervisor || exit 125
  exit "$original_rc"
}
trap cleanup_active_supervisor EXIT
trap 'handle_driver_signal INT 130' INT
trap 'handle_driver_signal TERM 143' TERM
trap 'handle_driver_signal HUP 129' HUP

[[ ! -e $result && ! -L $result ]] || die 'diagnostic result root collision'
"$mkdir_bin" -- "$result"
management_python scan --output "$result/preflight-live-scan.json" >/dev/null
abort_if_driver_signaled

for ordinal in 1 2 3 4; do
  abort_if_driver_signaled
  case $ordinal in
    1) device=0; role=control ;;
    2) device=0; role=candidate ;;
    3) device=1; role=candidate ;;
    4) device=1; role=control ;;
  esac
  if [[ $role == control ]]; then
    stage=$control; policy=0
  else
    stage=$candidate; policy=1
  fi
  output=$(printf '%s/arm-%02d.json' "$result" "$ordinal")
  terminal=$(printf '%s/arm-%02d.terminal.json' "$result" "$ordinal")
  active_supervisor_terminal=$terminal
  active_supervisor_ordinal=$ordinal
  supervisor_spawn_state=spawning
  "$env_bin" -i \
    HOME=/home/steve USER=steve LOGNAME=steve SHELL="$bash_bin" LANG=C.UTF-8 \
    PATH="$clean_path" PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="$stage" \
    LD_LIBRARY_PATH="$stage/vllm_xpu_kernels:$torch_lib:$venv_lib" \
    ZE_AFFINITY_MASK="$device" \
    VLLM_XPU_FA2_FORCE_CHUNK_DECODE=1 \
    VLLM_XPU_FA2_M6_HEAD256_Q64K32_POLICY="$policy" \
    QWEN38_RUNTIME_MAP_DRIVER="$0" \
    QWEN38_RUNTIME_MAP_DRIVER_SHA256="$("$sha256sum_bin" -- "$0" | "$awk_bin" '{print $1}')" \
    "$python" -B "$diagnostic" supervise --ordinal "$ordinal" \
      --terminal "$terminal" -- \
      "$python" -B "$diagnostic" worker --ordinal "$ordinal" \
      --device "$device" --role "$role" --output "$output" &
  active_supervisor_pid=$!
  supervisor_spawn_state=owned
  if [[ -n $deferred_signal ]]; then
    "$kill_bin" -s "$deferred_signal" "$active_supervisor_pid" 2>/dev/null || true
    deferred_signal=
  fi
  set +e
  while true; do
    wait "$active_supervisor_pid"
    supervisor_rc=$?
    "$kill_bin" -0 "$active_supervisor_pid" 2>/dev/null || break
  done
  set -e
  abort_if_driver_signaled
  [[ $supervisor_rc -eq 0 ]] || exit "$supervisor_rc"
  management_python validate-terminal "$terminal" >/dev/null
  abort_if_driver_signaled
  active_supervisor_pid=
  active_supervisor_terminal=
  active_supervisor_ordinal=
  supervisor_spawn_state=idle
  abort_if_driver_signaled
done

abort_if_driver_signaled
management_python compare --output "$result/comparison.json" \
  "$result/arm-01.terminal.json" "$result/arm-02.terminal.json" \
  "$result/arm-03.terminal.json" "$result/arm-04.terminal.json"
abort_if_driver_signaled
exit 0

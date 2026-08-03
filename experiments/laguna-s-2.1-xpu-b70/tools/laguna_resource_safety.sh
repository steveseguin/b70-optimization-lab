#!/bin/bash
# Shared, CPU-testable fail-closed decisions for the one-shot Laguna swap24
# resource wrapper. The caller owns policy inputs and the recorded PGID.

laguna_process_group_exists() {
  (( $# == 1 )) && [[ "$1" =~ ^[1-9][0-9]*$ ]] || return 2
  kill -0 -- -"$1" 2>/dev/null
}

laguna_process_is_running() {
  (( $# == 1 )) && [[ "$1" =~ ^[1-9][0-9]*$ ]] || return 2
  local state
  state="$(ps -o stat= -p "$1" 2>/dev/null)" || return 1
  state="${state//[[:space:]]/}"
  [[ -n "$state" && "$state" != Z* ]]
}

laguna_wait_for_dedicated_group() {
  local pid="${1:-}" attempts="${2:-100}" delay="${3:-0.01}" index
  (( $# >= 1 && $# <= 3 )) \
    && [[ "$pid" =~ ^[1-9][0-9]*$ \
          && "$attempts" =~ ^[1-9][0-9]*$ \
          && "$delay" =~ ^(0|[0-9]+([.][0-9]+)?)$ ]] || return 2
  for (( index = 0; index < attempts; index++ )); do
    laguna_process_group_exists "$pid" && return 0
    laguna_process_is_running "$pid" || return 1
    sleep "$delay" || true
  done
  laguna_process_group_exists "$pid"
}

laguna_stop_process_bounded() {
  local pid="${1:-}" attempts="${2:-120}" delay="${3:-1}" forced=0 index
  (( $# >= 1 && $# <= 3 )) \
    && [[ "$pid" =~ ^[1-9][0-9]*$ \
          && "$attempts" =~ ^[1-9][0-9]*$ \
          && "$delay" =~ ^(0|[0-9]+([.][0-9]+)?)$ \
          && "$pid" != $$ ]] || return 2
  laguna_process_is_running "$pid" || return 0
  kill -TERM "$pid" 2>/dev/null || true
  for (( index = 0; index < attempts; index++ )); do
    laguna_process_is_running "$pid" || return 0
    sleep "$delay" || true
  done
  forced=1
  kill -KILL "$pid" 2>/dev/null || true
  for (( index = 0; index < attempts; index++ )); do
    laguna_process_is_running "$pid" || break
    sleep "$delay" || true
  done
  ! laguna_process_is_running "$pid" && (( forced == 0 ))
}

laguna_stop_process_group_bounded() {
  local pgid="${1:-}" attempts="${2:-120}" delay="${3:-1}" forced=0 index
  (( $# >= 1 && $# <= 3 )) \
    && [[ "$pgid" =~ ^[1-9][0-9]*$ \
          && "$attempts" =~ ^[1-9][0-9]*$ \
          && "$delay" =~ ^(0|[0-9]+([.][0-9]+)?)$ ]] || return 2
  local caller_pgid
  caller_pgid="$(ps -o pgid= -p $$ 2>/dev/null)" || return 2
  caller_pgid="${caller_pgid//[[:space:]]/}"
  [[ "$pgid" != "$caller_pgid" ]] || return 2

  kill -TERM -- -"$pgid" 2>/dev/null || true
  for (( index = 0; index < attempts; index++ )); do
    laguna_process_group_exists "$pgid" || return 0
    sleep "$delay" || true
  done
  forced=1
  kill -KILL -- -"$pgid" 2>/dev/null || true
  for (( index = 0; index < attempts; index++ )); do
    laguna_process_group_exists "$pgid" || break
    sleep "$delay" || true
  done
  ! laguna_process_group_exists "$pgid" && (( forced == 0 ))
}

laguna_swapoff_allowed() {
  (( $# == 7 )) || return 2
  local value
  for value in "${@:1:6}"; do
    [[ "$value" == 0 ]] || return 1
  done
  [[ "$7" == ACTIVE || "$7" == INACTIVE ]]
}

laguna_remove_allowed() {
  (( $# == 10 )) || return 2
  local value
  for value in "${@:1:8}"; do
    [[ "$value" == 0 ]] || return 1
  done
  [[ "$9" == INACTIVE && "${10}" == PRESENT ]]
}

laguna_cleanup_passes() {
  (( $# == 14 )) || return 2
  local value
  for value in "${@:1:11}"; do
    [[ "$value" == 0 ]] || return 1
  done
  [[ "${12}" == 1 \
     && "${13}" == /swap.img:8388604 && "${14}" == ABSENT ]]
}

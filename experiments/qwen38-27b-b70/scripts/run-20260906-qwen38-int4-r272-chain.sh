#!/usr/bin/env bash
# R272 chain: after pid $1 exits and no qwen38 container runs: (a) rank0 on cores 0-3, rank1 on 4-7 (distinct physical cores,
# SMT siblings 8-15 left to the engine core and API server); (b) rank0 0-3,8-11 and rank1 4-7,12-15 (cores plus their siblings);
# (c) control without binding on the same script.
S=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ -n "${1:-}" ]] && while kill -0 "$1" 2>/dev/null; do sleep 30; done
while docker ps --format '{{.Names}}' | grep -q qwen38; do sleep 30; done
EXTRA_ARGS="--numa-bind --numa-bind-nodes 0 0 --numa-bind-cpus 0-3 4-7" V2=0 DRAFT_HEAD_INT4=1 RUN=r272a "$S/run-20260906-qwen38-int4-r272-numa-bind-smoke.sh"
while docker ps --format '{{.Names}}' | grep -q qwen38; do sleep 30; done
EXTRA_ARGS="--numa-bind --numa-bind-nodes 0 0 --numa-bind-cpus 0-3,8-11 4-7,12-15" V2=0 DRAFT_HEAD_INT4=1 RUN=r272b "$S/run-20260906-qwen38-int4-r272-numa-bind-smoke.sh"
while docker ps --format '{{.Names}}' | grep -q qwen38; do sleep 30; done
EXTRA_ARGS="" V2=0 DRAFT_HEAD_INT4=1 RUN=r272c "$S/run-20260906-qwen38-int4-r272-numa-bind-smoke.sh"

#!/usr/bin/env bash
# Requeue after pid $1 exits: R265b (two-pass ladders, fresh root) then R267a (V1 + async scheduling smoke), which collided
# with an orphaned R265 ladder server the first time.
S=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ -n "${1:-}" ]] && while kill -0 "$1" 2>/dev/null; do sleep 30; done
while docker ps --format '{{.Names}}' | grep -q "qwen38"; do sleep 30; done
RUN=r265b bash "$S/run-20260906-qwen38-int4-r265-ladders-repeat2-tp2-mtp4.sh"
while docker ps --format '{{.Names}}' | grep -q "qwen38"; do sleep 30; done
ASYNC=1 V2=0 DRAFT_HEAD_INT4=1 RUN=r267a2 "$S/run-20260906-qwen38-int4-r267-async-scheduling-smoke.sh"

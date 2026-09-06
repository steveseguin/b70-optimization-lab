#!/usr/bin/env bash
# R267 chain: after pid $1 exits, run the async-scheduling smoke on V1 (r267a) then V2 (r267b).
S=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ -n "${1:-}" ]] && while kill -0 "$1" 2>/dev/null; do sleep 30; done
ASYNC=1 V2=0 DRAFT_HEAD_INT4=1 RUN=r267a "$S/run-20260906-qwen38-int4-r267-async-scheduling-smoke.sh"
ASYNC=1 V2=1 DRAFT_HEAD_INT4=0 RUN=r267b "$S/run-20260906-qwen38-int4-r267-async-scheduling-smoke.sh"

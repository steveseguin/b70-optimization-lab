#!/usr/bin/env bash
# After pid $1 (R274b/c chain) and no qwen38 container: R275b = R275 (capture sizes to 320, c16/c32/c64 two-pass) with GDN spec
# group 64 so the grouped branch (which syncs and cannot be captured) is not taken below 65 sequences.
S=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ -n "${1:-}" ]] && while kill -0 "$1" 2>/dev/null; do sleep 30; done
while docker ps --format '{{.Names}}' | grep -q qwen38; do sleep 30; done; sleep 20; while docker ps --format '{{.Names}}' | grep -q qwen38; do sleep 30; done
SPEC_GROUP_OVERRIDE=64 RUN=r275b bash "$S/run-20260906-qwen38-int4-r275-graph-sizes-320-c16-c64-ladders.sh"

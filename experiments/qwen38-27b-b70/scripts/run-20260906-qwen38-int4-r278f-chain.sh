#!/usr/bin/env bash
S=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ -n "${1:-}" ]] && while kill -0 "$1" 2>/dev/null; do sleep 30; done
while docker ps --format '{{.Names}}' | grep -q qwen38; do sleep 30; done; sleep 20; while docker ps --format '{{.Names}}' | grep -q qwen38; do sleep 30; done
bash "$S/run-20260906-qwen38-int4-r278f-launcher-chain-harness.sh"

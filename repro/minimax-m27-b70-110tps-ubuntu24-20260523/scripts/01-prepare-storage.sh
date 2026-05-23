#!/usr/bin/env bash
set -euo pipefail

FAST_AI_ROOT="${FAST_AI_ROOT:-/mnt/fast-ai}"

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  echo "Run with sudo: sudo FAST_AI_ROOT=$FAST_AI_ROOT bash $0" >&2
  exit 2
fi

mkdir -p \
  "$FAST_AI_ROOT/llm-models" \
  "$FAST_AI_ROOT/llm-cache/hf" \
  "$FAST_AI_ROOT/bench-results" \
  "$FAST_AI_ROOT/vllm-cache-exp" \
  "$FAST_AI_ROOT/src"

owner="${SUDO_USER:-$(logname 2>/dev/null || echo steve)}"
chown -R "$owner:$owner" "$FAST_AI_ROOT"

df -h "$FAST_AI_ROOT"


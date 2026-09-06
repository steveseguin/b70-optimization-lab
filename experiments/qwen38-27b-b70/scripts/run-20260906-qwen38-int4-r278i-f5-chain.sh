#!/usr/bin/env bash
S=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
w() { while docker ps --format '{{.Names}}' | grep -q qwen38; do sleep 30; done; sleep 20; while docker ps --format '{{.Names}}' | grep -q qwen38; do sleep 30; done; }
w; bash "$S/run-20260906-qwen38-int4-r278i-split-mixed-off.sh"
w; SPEC_GROUP_OVERRIDE=64 SPLIT_MIXED=1 bash "$S/run-20260906-qwen38-int4-r278f-launcher-chain-harness.sh"

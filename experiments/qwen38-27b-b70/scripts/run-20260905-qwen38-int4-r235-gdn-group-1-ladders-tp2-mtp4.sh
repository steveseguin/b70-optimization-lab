#!/usr/bin/env bash
# R235 (2026-09-05): R232 configuration with the GDN spec rows launched per sequence (VLLM_XPU_GDN_SPEC_GROUP=1), the limiting case after R233 (off: c64 57/64) and R229 (16: 63/64)
# Arg 1: pid to wait for.
[[ -n "${1:-}" ]] && while kill -0 "$1" 2>/dev/null; do sleep 15; done
set -uo pipefail
S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
for G in 1; do
  sed -e "s#-20260905-r232#-20260905-r23${G}g#; s#LADDERS_ONLY=1 VLLM_XPU_FA_SERIAL_SPEC_DECODE=1#LADDERS_ONLY=1 VLLM_XPU_GDN_SPEC_GROUP=${G} VLLM_XPU_FA_SERIAL_SPEC_DECODE=1#" $S/run-20260905-qwen38-int4-r232-r228-no-split-reductions-ladders-tp2-mtp4.sh > /tmp/r23-group-${G}.sh
  bash /tmp/r23-group-${G}.sh
done

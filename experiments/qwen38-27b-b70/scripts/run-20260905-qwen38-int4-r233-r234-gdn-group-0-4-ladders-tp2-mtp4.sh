#!/usr/bin/env bash
# R233/R234 (2026-09-05): R232 configuration (R228 + batch-invariant + split_reductions=false) with the GDN spec grouping off
# (VLLM_XPU_GDN_SPEC_GROUP=0, R233) and at 4 sequences (R234): does the grouped gather/scatter path itself perturb?
set -uo pipefail
S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
for G in 0 4; do
  sed -e "s#-20260905-r232#-20260905-r23${G}g#; s#LADDERS_ONLY=1 VLLM_XPU_FA_SERIAL_SPEC_DECODE=1#LADDERS_ONLY=1 VLLM_XPU_GDN_SPEC_GROUP=${G} VLLM_XPU_FA_SERIAL_SPEC_DECODE=1#" $S/run-20260905-qwen38-int4-r232-r228-no-split-reductions-ladders-tp2-mtp4.sh > /tmp/r23-group-${G}.sh
  bash /tmp/r23-group-${G}.sh
done

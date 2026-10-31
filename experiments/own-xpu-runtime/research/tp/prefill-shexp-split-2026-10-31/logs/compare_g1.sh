#!/usr/bin/env bash
# Gate 2 compares of phase g1 (CPU only).
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/prefill-shexp-split-2026-10-31
R=/dev/shm/prefill-shexp-split-20261031/runs-g1
A=/mnt/raid-models/ownrt-experiment-archives/2026-10-31
K=/mnt/raid-models/ownrt-experiment-archives/2026-10-29/ctx131072-runs-k2
bash $D/compare_phase.sh g1 $R \
  1:g-r1-a1:g-r1-b1 1:g-r1-a2:g-r1-b2 1:g-r1-a1:g-r1-a2 1:g-r1-a1:g-r1-u1 1:g-r1-a1:g-r1-d1 1:g-r1-a2:g-r1-u2 1:g-r1-a2:g-r1-d2 \
  1:$A/prefill-balance-runs-b1/b-r1-e1:g-r1-b1 \
  0:g-r0-a1:g-r0-b1 0:g-r0-a2:g-r0-b2 0:g-r0-a1:g-r0-a2 0:g-r0-a1:g-r0-u1 0:g-r0-a1:g-r0-d1 0:g-r0-a2:g-r0-u2 0:g-r0-a2:g-r0-d2 \
  0:$A/prefill-balance-runs-b2/c-r0-p1:g-r0-b1 0:$A/prefill-balance-runs-g1/g-r0-m:g-r0-bm \
  x1:$K/g-r1-one64k:g-r1-b1 x0:$K/g-r0-one64k:g-r0-b1 x0:$K/g-r0-one64k-m:g-r0-bm

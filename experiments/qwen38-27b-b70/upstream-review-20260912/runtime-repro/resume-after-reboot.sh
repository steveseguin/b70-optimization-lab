#!/usr/bin/env bash
# Run AFTER the reboot. Card e3:00.0 (Level Zero index 1) logged three copy-engine faults on the 2026-09-11 boot, all
# right after weight load (12:46 lab R300, 16:02 stock eager arm, 20:00 stock nightly async-off arm). What is left needs
# both cards: the three remaining phantom arms on today's nightly. (v0.29.0: all four arms done, no outliers;
# nightly-0912 compiled-async-on: done, no outliers.)
d=/mnt/fast-ai/bench-results/upstream-repro-20260912
N12=vllm/vllm-openai-xpu@sha256:5de5a541a49606ac0b497ab803fa0254001cff59bedbdd2514e237778f9ad7c3
while docker ps --format '{{.Names}}' | grep -qE 'upstream-|qwen3[58]'; do sleep 20; done; sleep 10
mv $d/phantom-nightly-0912/compiled-async-off $d/phantom-nightly-0912/compiled-async-off.hung-2000 2>/dev/null
IMG=$N12 TAG=nightly-0912 ARMS="compiled-async-off eager-async-on-1 eager-async-on-2" bash $d/run-phantom-v2.sh >$d/phantom-nightly-0912-rest.stdout 2>&1

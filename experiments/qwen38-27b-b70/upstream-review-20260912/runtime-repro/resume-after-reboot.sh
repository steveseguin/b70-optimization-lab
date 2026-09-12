#!/usr/bin/env bash
# Run AFTER the reboot. queue4 was stopped at 16:5x on 2026-09-12 when card e3:00.0 logged its second copy-engine
# fault of this boot during model load (12:46 R300 mtp1-b, 16:02 the stock eager phantom arm); the arm hung.
# Remaining work, in order: phantom v0.29.0 eager arms (the two compiled arms are done: no outliers), phantom on
# today's nightly (four arms), queue-DONE. Then relaunch the 4B torch-deterministic chain (last line).
d=/mnt/fast-ai/bench-results/upstream-repro-20260912
N12=vllm/vllm-openai-xpu@sha256:5de5a541a49606ac0b497ab803fa0254001cff59bedbdd2514e237778f9ad7c3
wait_free() { while docker ps --format '{{.Names}}' | grep -q upstream-; do sleep 20; done; sleep 10; }
mv $d/phantom-v0.29.0/eager-async-on-1 $d/phantom-v0.29.0/eager-async-on-1.hung-before-reboot 2>/dev/null
wait_free; IMG=vllm/vllm-openai-xpu:latest TAG=v0.29.0 ARMS="eager-async-on-1 eager-async-on-2" bash $d/run-phantom-v2.sh >$d/phantom-v0.29.0-eager.stdout 2>&1
wait_free; IMG=$N12 TAG=nightly-0912 bash $d/run-phantom-v2.sh >$d/phantom-nightly-0912.stdout 2>&1
echo done >$d/queue-DONE
nohup bash /home/steve/b70-optimization-lab/experiments/qwen35-4b-b70/scripts/run-20260912-qwen35-4b-torch-deterministic-chain.sh >/mnt/fast-ai/bench-results/qwen35-4b-torchdet-20260912-stdout.log 2>&1 &

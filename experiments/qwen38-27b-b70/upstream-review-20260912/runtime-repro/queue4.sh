#!/usr/bin/env bash
# queue4 (15:4x) = queue3 + the v0.29.0+PR53542 image arms (both runners, c1,12,64) before the nightly runs. The v0.29.0 MRV2/MRV1 runner already launched by queue2 keeps running; this waits for it.
# Then: width arm (MRV1, stock schedule, ladder c1,12,64 - the 12-user rung is the K=1 range that kernels issue #593
# needs) on v0.29.0 -> both arms on today's nightly -> width arm on today's nightly -> phantom v0.29.0 -> phantom nightly.
d=/mnt/fast-ai/bench-results/upstream-repro-20260912
N12=vllm/vllm-openai-xpu@sha256:5de5a541a49606ac0b497ab803fa0254001cff59bedbdd2514e237778f9ad7c3
until grep -q '=== done' $d/mrv2-dsd-v0.29.0/campaign.log 2>/dev/null; do sleep 20; done
wait_free() { while docker ps --format '{{.Names}}' | grep -q upstream-; do sleep 20; done; sleep 10; }
wait_free; IMG=vllm/vllm-openai-xpu:latest TAG=v0.29.0 ARMS=mrv1-dsd CONC=1,12,64 OUTPFX=width bash $d/run-mrv2-dsd-k0-v2.sh >$d/width-v0.29.0.stdout 2>&1
wait_free; IMG=upstream-repro/vllm-xpu:v0.29.0-pr53542 TAG=v0.29.0-pr53542 ARMS="mrv1-dsd mrv2-dsd" CONC=1,12,64 OUTPFX=width bash $d/run-mrv2-dsd-k0-v2.sh >$d/width-v0.29.0-pr53542.stdout 2>&1
wait_free; IMG=$N12 TAG=nightly-0912 bash $d/run-mrv2-dsd-k0-v2.sh >$d/mrv2-nightly-0912.stdout 2>&1
wait_free; IMG=$N12 TAG=nightly-0912 ARMS=mrv1-dsd CONC=1,12,64 OUTPFX=width bash $d/run-mrv2-dsd-k0-v2.sh >$d/width-nightly-0912.stdout 2>&1
wait_free; IMG=vllm/vllm-openai-xpu:latest TAG=v0.29.0 bash $d/run-phantom-v2.sh >$d/phantom-v0.29.0.stdout 2>&1
wait_free; IMG=$N12 TAG=nightly-0912 bash $d/run-phantom-v2.sh >$d/phantom-nightly-0912.stdout 2>&1
echo done >$d/queue-DONE

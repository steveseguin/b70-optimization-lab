#!/usr/bin/env bash
# After alias round 2: strict gates on R303 (the shipping candidate) under the REAL contract (no skip): 4B, 9B, then 27B.
R=/mnt/fast-ai/bench-results/rebase-v0290-20260912; lab=/home/steve/b70-optimization-lab
until [[ -e $R/alias-v2-DONE ]]; do sleep 30; done
while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|rebase-'; do sleep 20; done; sleep 10
IMAGE=neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r303 SKIP_IMAGE_CONTRACT=0 RB=r303 bash $lab/experiments/qwen35-4b-b70/scripts/run-20260912-rebase-v0290-strict-chain.sh > $R/r303-strict-4b9b.stdout 2>&1
while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|rebase-'; do sleep 20; done; sleep 10
touch /mnt/fast-ai/bench-results/rebase-v0290-identity2-20260912-DONE
IMAGE=neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r303 SKIP_IMAGE_CONTRACT=0 RB=r303 bash $lab/experiments/qwen38-27b-b70/scripts/run-20260912-rebase-v0290-27b-strict-chain.sh > $R/r303-strict-27b.stdout 2>&1
echo done > $R/r303-strict-DONE

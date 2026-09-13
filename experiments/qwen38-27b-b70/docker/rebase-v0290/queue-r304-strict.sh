#!/usr/bin/env bash
# After the R303 gates: strict gates on R304 (final candidate: + #53542 width fix) (the shipping candidate) under the REAL contract (no skip): 4B, 9B, then 27B.
R=/mnt/fast-ai/bench-results/rebase-v0290-20260912; lab=/home/steve/b70-optimization-lab
until [[ -e $R/r304-strict-DONE ]]; do sleep 30; done
while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|rebase-'; do sleep 20; done; sleep 10
IMAGE=neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r304 SKIP_IMAGE_CONTRACT=0 RB=r304 bash $lab/experiments/qwen35-4b-b70/scripts/run-20260912-rebase-v0290-strict-chain.sh > $R/r304-strict-4b9b.stdout 2>&1
while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|rebase-'; do sleep 20; done; sleep 10
touch /mnt/fast-ai/bench-results/rebase-v0290-identity2-20260912-DONE
IMAGE=neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r304 SKIP_IMAGE_CONTRACT=0 RB=r304 bash $lab/experiments/qwen38-27b-b70/scripts/run-20260912-rebase-v0290-27b-strict-chain.sh > $R/r304-strict-27b.stdout 2>&1
echo done > $R/r304-strict-DONE
# then: short-prompt harness on R304 (k=1..6) and the dynamic-schedule sanity (9B, schedule [[1,8,3],[9,16,1],[17,64,0]], c1/12/64: the width fix must hold)
while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|rebase-|upstream-'; do sleep 20; done; sleep 10
out=$R/alias-r304; mkdir -p $out; port=18163; name=rebase-alias3-r304; img=neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r304; id=$(docker image inspect $img --format '{{.Id}}')
( IMAGE=$img EXPECTED_IMAGE_ID=$id MODEL_DIR=/home/steve/llm-models/qwen35-4b-w4a16 PORT=$port CONTAINER_NAME=$name SERVED_MODEL_NAME=m VLLM_CACHE_DIR=$out/cache MTP_DEPTH=3 TENSOR_PARALLEL_SIZE=1 bash $lab/repro/qwen35-4b-w4a16-b70/scripts/run-qwen35-4b-w4a16-server.sh > $out/launcher.log 2>&1 ) &
for i in $(seq 1 150); do curl -fsS http://127.0.0.1:$port/health >/dev/null 2>&1 && break; sleep 10; done
python3 $lab/experiments/qwen35-4b-b70/probes/alias-harness-lab.py --base http://127.0.0.1:$port/v1 --model m --spec-tokens 3 --iters 30 --tag r304 > $out/harness.stdout 2>&1; echo "alias r304 harness exit $?" >> $out/campaign.log; grep -E '^(ALIAS|control)' $out/harness.stdout >> $out/campaign.log
docker logs $name > $out/server.log 2>&1; docker stop -t 60 $name >/dev/null 2>&1; sleep 5; docker rm -f $name >/dev/null 2>&1
IMG=$img TAG=r304 ARMS=mrv1-dsd CONC=1,12,64 OUTPFX=width bash /mnt/fast-ai/bench-results/upstream-repro-20260912/run-mrv2-dsd-k0-v2.sh > $R/width-r304.stdout 2>&1
echo done > $R/r304-all-DONE

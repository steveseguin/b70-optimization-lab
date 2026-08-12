#!/usr/bin/env bash
# Lane C v2 chain, hardened: no set -u around setvars, progress echoes,
# every phase leaves evidence. Harvest already complete (210 rows).
echo "[chain2] archived and disabled: drafter training is outside the active goal" >&2
exit 2
D=/mnt/fast-ai/bench-results/muse-glimmer-30b/distill
V=/mnt/usb-models/muse-venvs/muse-distill/bin/python
echo "[chain2] $(date '+%H:%M:%S') pausing production for extraction"
printf "/'\n" | sudo -S -p '' systemctl stop muse-glimmer-frontdoor.service muse-glimmer-bf16-fleet.service
sleep 3
set +u
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u 2>/dev/null || true
echo "[chain2] $(date '+%H:%M:%S') extraction starting"
ONEAPI_DEVICE_SELECTOR="level_zero:0,1" $V $D/extract-features-v3.py > $D/extract-v3.log 2>&1
echo "[chain2] $(date '+%H:%M:%S') extraction rc=$? shards=$(ls /mnt/usb-models/muse-glimmer-30b-extra/distill-features-v3 2>/dev/null | wc -l)"
export UR_L0_USE_IMMEDIATE_COMMANDLISTS=1 UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1 GGML_SYCL_ENABLE_VMM=1
ONEAPI_DEVICE_SELECTOR="level_zero:2,3" nohup /home/steve/src/llama.cpp-muse-100/build-sycl-b70-aot-bmg-g31/bin/llama-server \
  -m /mnt/usb-models/muse-glimmer-30b-extra/Muse-Glimmer-30B-BF16-00001-of-00002.gguf \
  --host 127.0.0.1 --port 19470 -ngl 99 -sm tensor -c 65536 --parallel 1 -b 1024 -ub 1024 --threads 8 \
  -fa on --jinja --cache-ram 8192 --alias muse-glimmer-30b-bf16 \
  --spec-type draft-dflash --spec-draft-model /mnt/fast-ai/llm-models/muse-glimmer-30b-gguf/dflash-bf16.gguf \
  --spec-draft-n-max 15 --spec-draft-p-min 0.15 --spec-draft-ngl 99 \
  > /mnt/fast-ai/bench-results/muse-glimmer-30b/servers/degraded-textlane-v2train.log 2>&1 &
for i in $(seq 1 60); do curl -sf -m 2 http://127.0.0.1:19470/health >/dev/null 2>&1 && break; sleep 5; done
echo "[chain2] $(date '+%H:%M:%S') degraded lane up; training"
ONEAPI_DEVICE_SELECTOR="level_zero:0,1" $V $D/train-drafter-v2.py > $D/train-v2.log 2>&1
echo "[chain2] $(date '+%H:%M:%S') training rc=$?"
tail -3 $D/train-v2.log
pkill -x llama-server; sleep 3
printf "/'\n" | sudo -S -p '' systemctl restart muse-glimmer-bf16-fleet.service muse-glimmer-frontdoor.service
sleep 10
echo "[chain2] $(date '+%H:%M:%S') done; fleet=$(systemctl is-active muse-glimmer-bf16-fleet.service)"

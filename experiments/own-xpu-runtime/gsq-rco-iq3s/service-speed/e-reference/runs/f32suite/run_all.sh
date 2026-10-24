#!/bin/bash
# Exact reference teacher-forced on each F32-engine suite output (prompt + engine tokens), sequentially.
set -u
M=/mnt/usb-models/llm-models/SC117-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-eec4e10a/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-00001-of-00002.gguf
cd /dev/shm/exactref/f32suite
for f in in-*.json; do id=${f#in-};id=${id%.json};mkdir -p out-$id;[ -s out-$id/done ] && continue
  /dev/shm/llref/build/exact-logits $M $f out-$id 16 > out-$id/log.txt 2>&1 && echo ok > out-$id/done || echo "FAIL $id"
done
echo ALLDONE > all.done

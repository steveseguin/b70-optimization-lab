#!/usr/bin/env bash
# 2026-10-17 head-256 prompt-attention tile variants (registered in notes/2026-10-17-fp8-prompt-attention-kernel.md).
# Gemma stopped once; the image's own library, then each stand-alone build (bind-mounted over the image's two files),
# timed on card 0 with the prompt kernel alone (--mix-batch 0), the image again at the end for drift; Gemma back
# unless a GPU fault line.
#   SUDO_ASKPASS=... systemd-run --user --unit=attn-variants ... bash run-20261017-attn-variants.sh
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
cd "$LAB"
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
IMAGE=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride}
D=$LAB/experiments/qwen38-27b-b70/data/2026-10-17-attn-bench
S=$LAB/experiments/qwen38-27b-b70/scripts
B=/mnt/fast-ai/builds/attn-variants-20261017
VARIANTS=${VARIANTS:-image control k64 q128 image2}
BENCH_ARGS=${BENCH_ARGS:---mix-batch 0 --reps 9}
KP=/opt/venv/lib/python3.12/site-packages/vllm_xpu_kernels
START=$(date '+%F %T')
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost)|soft lockup'
say() { echo "### $(date +%H:%M:%S) $*"; }
faults() { sudo -A journalctl -k --since "$START" --no-pager -o short-iso 2>/dev/null | grep -Ei "$FAULT_RE"; }
restore() {
  docker rm -f attn-bench >/dev/null 2>&1
  F=$(faults)
  if [[ -n $F ]]; then say "GPU FAULT LINES since $START; cards left empty, Gemma NOT restored"; echo "$F" | head -10; return; fi
  say "kernel log clean since $START; Gemma back on its throughput recipe"
  timeout 900 scripts/gemma4-26b-two-b70-recipe.sh throughput 2>&1 | grep -E '^backend|^frontdoor|timed out|died'
  say "attention bench complete"
}
mkdir -p "$D"
st="down down"
for i in $(seq 1 60); do
  st=$(curl -fsS -m 3 http://127.0.0.1:8000/v1/frontdoor/status 2>/dev/null | python3 -c 'import json,sys; f=json.load(sys.stdin)["frontdoor"]; print(f["active_generations"], f["queued_generations"])' 2>/dev/null || echo "down down")
  [[ $st == "0 0" || $st == "down down" ]] && break
  (( i % 6 == 1 )) && say "Gemma front door busy ($st active/queued); waiting"
  sleep 10
done
say "stopping the Gemma service (front door state: $st)"
sudo -A systemctl stop gemma4-26b-q8-quad-frontdoor.service gemma4-26b-q8-quad-backends.service
sudo -A systemctl reset-failed gemma4-26b-q8-quad-frontdoor.service gemma4-26b-q8-quad-backends.service 2>/dev/null
trap restore EXIT
for i in $(seq 1 30); do pgrep -x llama-server >/dev/null || break; sleep 2; done
pgrep -x llama-server >/dev/null && { say "ABORT: llama-server still running"; exit 2; }
sleep 5
# an arm is <variant>[@<n>] (a repeat of the same build); image* = the image's own library
for V in $VARIANTS; do
  MNT=""; W=${V%%@*}
  case $W in image*) ;; *) for f in _vllm_fa2_C.abi3.so libattn_kernels_xe_2.so; do
      [[ -f $B/$W/$f ]] || { say "ABORT: $B/$W/$f missing"; exit 2; }; MNT="$MNT -v $B/$W/$f:$KP/$f:ro"; done ;; esac
  say "timing $V ($BENCH_ARGS)"
  docker run --rm --name attn-bench --device /dev/dri:/dev/dri --group-add render --memory 6g --ulimit core=0 \
    -e ONEAPI_DEVICE_SELECTOR=level_zero:0 -v "$S/bench-chunk-prefill-attn.py:/tmp/b.py:ro" -v "$D:/out" $MNT \
    --workdir /tmp --entrypoint python3 "$IMAGE" /tmp/b.py --out "/out/attn-variant-${V/@/-}.json" $BENCH_ARGS \
    2>&1 | grep -v "^\s*$" | tail -40
  say "bench $V exit ${PIPESTATUS[0]}"
  [[ -n $(faults) ]] && { say "GPU fault line after $V; stopping"; exit 3; }
done

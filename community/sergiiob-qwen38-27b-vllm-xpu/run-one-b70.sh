#!/usr/bin/env bash
set -euo pipefail

# Safe, single-B70 launcher for the captured SergioB vLLM/XPU lane.
# It never changes the card power limit. The 8/10 GiB cgroup protects the
# reference host's 15 GiB of RAM. Long context requires an explicit opt-in.

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
IMAGE=${IMAGE:-vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f}
MODEL_DIR=${MODEL_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-gptq-int4-mtp}
MODE=${MODE:-nospec}
MAX_MODEL_LEN=${MAX_MODEL_LEN:-8192}
DEVICE_INDEX=${DEVICE_INDEX:-0}
PORT=${PORT:-18085}
NAME=${NAME:-q38-gptq-${MODE}}
PATCH_MODE=${PATCH_MODE:-off}
HOST_MEMORY=${HOST_MEMORY:-8g}
HOST_MEMORY_SWAP=${HOST_MEMORY_SWAP:-10g}

case "$MODE" in
  nospec)
    GPU_UTIL=${GPU_UTIL:-0.90}
    spec_args=()
    ;;
  mtp1|mtp2|mtp4)
    GPU_UTIL=${GPU_UTIL:-0.88}
    depth=${MODE#mtp}
    spec_args=(--speculative-config "{\"method\":\"mtp\",\"num_speculative_tokens\":${depth}}")
    ;;
  *)
    echo "MODE must be nospec, mtp1, mtp2, or mtp4" >&2
    exit 2
    ;;
esac

if (( MAX_MODEL_LEN > 8192 )) && [[ ${ALLOW_LONG_CONTEXT:-0} != 1 ]]; then
  echo "MAX_MODEL_LEN > 8192 requires ALLOW_LONG_CONTEXT=1" >&2
  exit 2
fi
if [[ $PATCH_MODE != off && $PATCH_MODE != reported ]]; then
  echo "PATCH_MODE must be off or reported" >&2
  exit 2
fi
if [[ ! -f "$MODEL_DIR/model.safetensors.index.json" ]]; then
  echo "Exact model is missing at $MODEL_DIR" >&2
  exit 2
fi
if docker container inspect "$NAME" >/dev/null 2>&1; then
  echo "Container $NAME already exists; stop/remove it explicitly first" >&2
  exit 2
fi
if ss -ltn "sport = :$PORT" | tail -n +2 | grep -q .; then
  echo "TCP port $PORT is already in use" >&2
  exit 2
fi

render_gid=$(stat -c '%g' /dev/dri/renderD128)
apply_patches=0
if [[ $PATCH_MODE == reported ]]; then
  apply_patches=1
fi

docker run -d --name "$NAME" \
  --memory "$HOST_MEMORY" --memory-swap "$HOST_MEMORY_SWAP" \
  -p "127.0.0.1:${PORT}:8000" \
  --device /dev/dri --group-add "$render_gid" \
  -v /dev/dri:/dev/dri:ro \
  -v "$MODEL_DIR":/model:ro \
  -v "$ROOT_DIR/reported/patch_mtp_nightly.py":/capture/patch_mtp_nightly.py:ro \
  -v "$ROOT_DIR/reported/patch_mtp_boundary.py":/capture/patch_mtp_boundary.py:ro \
  -e VLLM_TARGET_DEVICE=xpu \
  -e ZE_FLAT_DEVICE_HIERARCHY=COMPOSITE \
  -e ZE_AFFINITY_MASK="$DEVICE_INDEX" \
  -e B70_MTP_BF16_DRAFT=1 \
  -e VLLM_XPU_ENABLE_XPU_GRAPH=1 \
  -e PYTORCH_ALLOC_CONF=expandable_segments:True \
  -e APPLY_CAPTURED_PATCHES="$apply_patches" \
  --entrypoint bash \
  "$IMAGE" -lc \
  'set -e; if [[ $APPLY_CAPTURED_PATCHES == 1 ]]; then python /capture/patch_mtp_nightly.py; python /capture/patch_mtp_boundary.py; fi; exec vllm serve "$@"' \
  bash /model \
  --quantization gptq \
  --dtype float16 \
  --max-model-len "$MAX_MODEL_LEN" \
  --gpu-memory-utilization "$GPU_UTIL" \
  --kv-cache-dtype fp8 \
  --port 8000 \
  --max-num-seqs 64 \
  --max-num-batched-tokens 8192 \
  --no-enable-prefix-caching \
  --served-model-name qwen38 \
  --language-model-only \
  "${spec_args[@]}"

echo "Started $NAME on http://127.0.0.1:$PORT"
echo "Follow startup: docker logs -f $NAME"
echo "Stop safely: docker stop -t 20 $NAME && docker container rm $NAME"

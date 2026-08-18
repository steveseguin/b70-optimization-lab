#!/usr/bin/env bash
# Reproduction script for the Cold Fusion GAIN V1.1 MTP llama.cpp SYCL result.
# Contributor: dominick253
# Target: single Intel Arc Pro B70, 32 GiB
# Expected: ~38.4 tok/s decode at short context with MTP2, 94.4% draft acceptance
#
# PREREQUISITES:
#   1. Ubuntu 24.04+ or 26.04 with the `xe` GPU kernel driver loaded
#   2. Intel oneAPI Base Toolkit 2026.1.1 installed at /opt/intel/oneapi
#   3. libze-intel-gpu1 >= 26.27 installed
#   4. The Cold Fusion GAIN V1.1 MTP GGUF (SHA-256 in STATUS.md)
#
# This script does NOT automatically download the model or the l0graphshim.so.
# Both must be obtained from the contributor.
set -euo pipefail

MODEL_PATH="${MODEL_PATH:?set MODEL_PATH to the Q4_K_M MTP GGUF}"
PORT="${PORT:-8001}"
BUILD_DIR="${BUILD_DIR:-./build-sycl}"
LLAMA_CPP_DIR="${LLAMA_CPP_DIR:-/tmp/llama.cpp}"
LLAMA_CPP_COMMIT="60eeeb6082c1126bb8bc72902c83123cd056811b"

echo "=== Step 1: Clone and checkout llama.cpp b10472 ==="
if [[ ! -d "${LLAMA_CPP_DIR}/.git" ]]; then
  git clone https://github.com/ggml-org/llama.cpp "${LLAMA_CPP_DIR}"
fi
git -C "${LLAMA_CPP_DIR}" fetch origin
git -C "${LLAMA_CPP_DIR}" checkout "${LLAMA_CPP_COMMIT}"

echo "=== Step 2: Build llama-server with SYCL ==="
source /opt/intel/oneapi/setvars.sh --silent
mkdir -p "${BUILD_DIR}"
cmake -S "${LLAMA_CPP_DIR}" -B "${BUILD_DIR}" \
  -DGGML_SYCL=ON \
  -DF16=ON \
  -DGRAPH=ON \
  -DDNN=ON \
  -DNATIVE=ON \
  -DHOST_MEM_FALLBACK=OFF \
  -DCMAKE_BUILD_TYPE=Release
cmake --build "${BUILD_DIR}" --config Release -j"$(nproc)"
echo "Build complete: ${BUILD_DIR}/bin/llama-server"

echo "=== Step 3: Verify model SHA-256 ==="
EXPECTED_SHA="db466a9432a52b87a7b7560f432f0e1caafeb111dbe3d168acf74dfe143a637c"
ACTUAL_SHA=$(sha256sum "${MODEL_PATH}" | awk '{print $1}')
if [[ "${ACTUAL_SHA}" != "${EXPECTED_SHA}" ]]; then
  echo "WARNING: model SHA-256 mismatch"
  echo "  expected: ${EXPECTED_SHA}"
  echo "  actual:   ${ACTUAL_SHA}"
  echo "Continuing, but results may differ."
else
  echo "Model SHA-256 verified."
fi

echo "=== Step 4: Launch server ==="
LLAMA_SERVER="${BUILD_DIR}/bin/llama-server" \
MODEL_PATH="${MODEL_PATH}" \
PORT="${PORT}" \
GPU_INDEX="${GPU_INDEX:-0}" \
L0GRAPHSHIM="${L0GRAPHSHIM:-/opt/opencode-fixes/l0graphshim.so}" \
bash llama-qwen38-27b-coldfusion-mtp.sh &

SERVER_PID=$!
echo "Server PID: ${SERVER_PID}"
echo "Waiting for health..."
for i in $(seq 1 120); do
  if curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    echo "Server healthy after ${i}s."
    break
  fi
  sleep 2
done

echo "=== Step 5: Run quick decode probe ==="
# 51 generated tokens, thinking disabled, measure wall time
curl -s "http://127.0.0.1:${PORT}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen38-27b-gpu0",
    "messages": [{"role":"user","content":"Write a concise explanation of why the sky is blue. Stop after 51 tokens."}],
    "max_tokens": 51,
    "reasoning_effort": "none",
    "stream": true
  }' 2>/dev/null | tail -1

echo ""
echo "Done. Check server logs for decode timing (tg=X t/s lines)."
echo "Expected: ~38.4 tok/s with MTP2 active."
kill "${SERVER_PID}" 2>/dev/null || true

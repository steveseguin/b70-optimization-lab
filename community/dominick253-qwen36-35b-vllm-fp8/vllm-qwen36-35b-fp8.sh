#!/usr/bin/env bash
# Community recipe: Qwen3.6 35B A3B, BF16 checkpoint -> runtime FP8, TP2.
# Reviewed but not executed in the reference lab. See STATUS.md.
set -euo pipefail

IMAGE="${IMAGE:-docker.io/intel/llm-scaler-vllm@sha256:5d87be271e4db54539f1dbb29c071e9122f4e57b74594dbb26a55d27a569d780}"
CONTAINER_RUNTIME="${CONTAINER_RUNTIME:-}"
NAME="${NAME:-vllm-qwen36-35b-fp8}"
MODEL_HOST_DIR="${MODEL_HOST_DIR:-}"
MODEL="/model"
SERVED_NAME="${SERVED_NAME:-qwen36-35b-fp8}"
BIND_HOST="${BIND_HOST:-127.0.0.1}"
ALLOW_REMOTE_BIND="${ALLOW_REMOTE_BIND:-0}"
PORT="${PORT:-8001}"
TP="${TP:-2}"
MAX_LEN="${MAX_LEN:-262144}"
GPU_UTIL="${GPU_UTIL:-0.88}"
MAX_SEQS="${MAX_SEQS:-4}"
EAGER="${EAGER:-1}"
THINKING_BUDGET="${THINKING_BUDGET:-2048}"
ZE_AFFINITY_MASK="${ZE_AFFINITY_MASK:-0,1}"
ONEAPI_DEVICE_SELECTOR="${ONEAPI_DEVICE_SELECTOR:-level_zero:0,1}"
RESTART_POLICY="${RESTART_POLICY:-no}"
STARTUP_TIMEOUT_SECONDS="${STARTUP_TIMEOUT_SECONDS:-1210}"
MAMBA_SSM_CACHE_DTYPE="${MAMBA_SSM_CACHE_DTYPE:-}"
ALLOW_UNVERIFIED_FLOAT16_SSM="${ALLOW_UNVERIFIED_FLOAT16_SSM:-0}"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

if [ -z "${CONTAINER_RUNTIME}" ]; then
  if command -v docker >/dev/null 2>&1; then
    CONTAINER_RUNTIME=docker
  elif command -v podman >/dev/null 2>&1; then
    CONTAINER_RUNTIME=podman
  else
    die "neither docker nor podman is installed; set CONTAINER_RUNTIME if using another compatible CLI"
  fi
fi

command -v "${CONTAINER_RUNTIME}" >/dev/null 2>&1 \
  || die "container runtime not found: ${CONTAINER_RUNTIME}"

RUNTIME_KIND=$(basename "${CONTAINER_RUNTIME}")
case "${RUNTIME_KIND}" in
  docker|podman) ;;
  *) die "CONTAINER_RUNTIME must select a Docker- or Podman-compatible CLI named docker or podman" ;;
esac

for command_name in curl grep python3 ss; do
  command -v "${command_name}" >/dev/null 2>&1 \
    || die "required command not found: ${command_name}"
done

[ -n "${MODEL_HOST_DIR}" ] \
  || die "MODEL_HOST_DIR must point to the downloaded Qwen3.6-35B-A3B directory"
[ -d "${MODEL_HOST_DIR}" ] \
  || die "MODEL_HOST_DIR is not a directory: ${MODEL_HOST_DIR}"
[ -r "${MODEL_HOST_DIR}/config.json" ] \
  || die "MODEL_HOST_DIR does not contain a readable config.json: ${MODEL_HOST_DIR}"

if [ "${BIND_HOST}" = "localhost" ]; then
  BIND_HOST=127.0.0.1
fi

case "${BIND_HOST}" in
  127.0.0.1) ;;
  0.0.0.0)
    [ "${ALLOW_REMOTE_BIND}" = "1" ] || die \
      "BIND_HOST=${BIND_HOST} exposes an unauthenticated API; set ALLOW_REMOTE_BIND=1 to opt in"
    ;;
  *) die "BIND_HOST must be 127.0.0.1, localhost, or 0.0.0.0" ;;
esac

case "${BIND_HOST}" in
  0.0.0.0) CHECK_HOST=127.0.0.1 ;;
  *) CHECK_HOST="${BIND_HOST}" ;;
esac

for integer_setting in \
  "PORT=${PORT}" \
  "TP=${TP}" \
  "MAX_LEN=${MAX_LEN}" \
  "MAX_SEQS=${MAX_SEQS}" \
  "THINKING_BUDGET=${THINKING_BUDGET}" \
  "STARTUP_TIMEOUT_SECONDS=${STARTUP_TIMEOUT_SECONDS}"
do
  integer_value=${integer_setting#*=}
  case "${integer_value}" in
    ""|*[!0-9]*) die "${integer_setting%%=*} must be a nonnegative integer" ;;
  esac
done

case "${SERVED_NAME}" in
  ""|*[!A-Za-z0-9._/-]*)
    die "SERVED_NAME may contain only letters, digits, dot, underscore, slash, and hyphen"
    ;;
esac

case "${MAMBA_SSM_CACHE_DTYPE}" in
  "") ;;
  float16)
    [ "${ALLOW_UNVERIFIED_FLOAT16_SSM}" = "1" ] || die \
      "float16 SSM state is an unverified quality-changing mode; set ALLOW_UNVERIFIED_FLOAT16_SSM=1 to opt in"
    ;;
  *) die "MAMBA_SSM_CACHE_DTYPE must be empty (model/default) or float16" ;;
esac

case "${RUNTIME_KIND}" in
  podman)
    DEVICE_GROUP_ARGS=(--group-add keep-groups)
    SHM_ARGS=()
    ;;
  docker)
    command -v getent >/dev/null 2>&1 || die "required command not found: getent"
    RENDER_GID="${RENDER_GID:-$(getent group render | cut -d: -f3)}"
    [ -n "${RENDER_GID}" ] \
      || die "render group not found; set RENDER_GID explicitly after checking /dev/dri ownership"
    DEVICE_GROUP_ARGS=(--group-add "${RENDER_GID}")
    SHM_ARGS=(--shm-size=32g)
    ;;
esac

if ss -H -ltn "sport = :${PORT}" | grep -q .; then
  ss -H -ltnp "sport = :${PORT}" >&2 || true
  die "host port ${PORT} is already listening; identify and stop it explicitly or choose another PORT"
fi

if "${CONTAINER_RUNTIME}" container inspect "${NAME}" >/dev/null 2>&1; then
  die "container ${NAME} already exists; inspect it and explicitly stop/remove or choose another NAME"
fi

# Qwen3.6 recommended general-thinking sampling profile from the model card.
OVERRIDE_GEN='{"temperature":1.0,"top_p":0.95,"top_k":20,"min_p":0.0,"presence_penalty":1.5,"repetition_penalty":1.0}'
CHAT_TMPL='{"enable_thinking":true,"preserve_thinking":true}'
REASONING_CONFIG='{"reasoning_parser":"qwen3"}'

DOCKER_ARGS=(
  --restart "${RESTART_POLICY}"
  --publish "${BIND_HOST}:${PORT}:${PORT}"
  --ipc=host
  "${SHM_ARGS[@]}"
  --device=/dev/dri
  "${DEVICE_GROUP_ARGS[@]}"
  --volume "${MODEL_HOST_DIR}":/model:ro
  --env "ZE_AFFINITY_MASK=${ZE_AFFINITY_MASK}"
  --env "ONEAPI_DEVICE_SELECTOR=${ONEAPI_DEVICE_SELECTOR}"
  --env VLLM_ALLOW_LONG_MAX_MODEL_LEN=1
  --env VLLM_WORKER_MULTIPROC_METHOD=spawn
  --env VLLM_OFFLOAD_WEIGHTS_BEFORE_QUANT=1
  --env PYTORCH_ALLOC_CONF=expandable_segments:True
  --env TORCH_LLM_ALLREDUCE=1
  --env CCL_TOPO_P2P_ACCESS=1
  --env CCL_ATL_TRANSPORT=ofi
  --env CCL_ZE_IPC_EXCHANGE=pidfd
  --env UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
  --entrypoint /bin/bash
)

VLLM_ARGS=(
  --host 0.0.0.0
  --port "${PORT}"
  --served-model-name "${SERVED_NAME}"
  --tensor-parallel-size "${TP}"
  --dtype float16
  --quantization fp8
  --max-model-len "${MAX_LEN}"
  --block-size 128
  --gpu-memory-utilization "${GPU_UTIL}"
  --max-num-seqs "${MAX_SEQS}"
  --max-num-batched-tokens 8192
  --no-enable-prefix-caching
  --enable-auto-tool-choice
  --tool-call-parser qwen3_coder
  --reasoning-parser qwen3
  "--reasoning-config=${REASONING_CONFIG}"
  "--override-generation-config=${OVERRIDE_GEN}"
  "--default-chat-template-kwargs=${CHAT_TMPL}"
)

if [ "${EAGER}" = "1" ]; then
  VLLM_ARGS+=(--enforce-eager)
elif [ "${EAGER}" != "0" ]; then
  die "EAGER must be 0 or 1"
fi

if [ -n "${MAMBA_SSM_CACHE_DTYPE}" ]; then
  VLLM_ARGS+=(--mamba-ssm-cache-dtype "${MAMBA_SSM_CACHE_DTYPE}")
fi

VLLM_CMD=$(printf '%q ' vllm serve "${MODEL}" "${VLLM_ARGS[@]}")

CONTAINER_CREATED=0
cleanup_failed_launch() {
  cleanup_status=$?
  trap - ERR
  if [ "${CONTAINER_CREATED}" = "1" ]; then
    printf 'Launch or smoke check failed; stopping and removing newly created container %s.\n' \
      "${NAME}" >&2
    "${CONTAINER_RUNTIME}" stop -t 30 "${NAME}" >/dev/null 2>&1 || true
    "${CONTAINER_RUNTIME}" rm "${NAME}" >/dev/null 2>&1 || true
  fi
  exit "${cleanup_status}"
}

printf 'Starting %s from %s\n' "${SERVED_NAME}" "${MODEL_HOST_DIR}"
printf 'Image: %s\n' "${IMAGE}"
printf 'Container runtime: %s\n' "${CONTAINER_RUNTIME}"
printf 'Endpoint: http://%s:%s/v1/chat/completions\n' "${BIND_HOST}" "${PORT}"
printf 'TP: %s; devices: %s; configured max length: %s; max sequences: %s\n' \
  "${TP}" "${ZE_AFFINITY_MASK}" "${MAX_LEN}" "${MAX_SEQS}"
if [ -n "${MAMBA_SSM_CACHE_DTYPE}" ]; then
  printf 'WARNING: unverified SSM state/cache override: %s\n' "${MAMBA_SSM_CACHE_DTYPE}" >&2
else
  printf 'SSM state/cache: model configuration / vLLM default\n'
fi

trap cleanup_failed_launch ERR
"${CONTAINER_RUNTIME}" run -d \
  --name "${NAME}" \
  "${DOCKER_ARGS[@]}" \
  "${IMAGE}" -lc "${VLLM_CMD}"
CONTAINER_CREATED=1

START_TIME=$(date +%s)
while true; do
  if [ "$("${CONTAINER_RUNTIME}" inspect -f '{{.State.Running}}' "${NAME}" 2>/dev/null)" != "true" ]; then
    printf 'Engine process exited during startup. Recent logs:\n' >&2
    "${CONTAINER_RUNTIME}" logs "${NAME}" --tail 80 >&2 || true
    false
  fi

  if curl --fail --silent --show-error --max-time 5 \
    "http://${CHECK_HOST}:${PORT}/health" >/dev/null 2>&1; then
    break
  fi

  ELAPSED=$(( $(date +%s) - START_TIME ))
  if [ "${ELAPSED}" -ge "${STARTUP_TIMEOUT_SECONDS}" ]; then
    printf 'Engine did not pass the HTTP health check within %ss. Recent logs:\n' \
      "${STARTUP_TIMEOUT_SECONDS}" >&2
    "${CONTAINER_RUNTIME}" logs "${NAME}" --tail 80 >&2 || true
    false
  fi

  printf '[%ss] waiting for the HTTP health endpoint\n' "${ELAPSED}"
  sleep 20
done

printf 'Engine HTTP health check passed after %ss.\n' \
  "$(( $(date +%s) - START_TIME ))"

PLAIN_RESPONSE=$(curl --fail-with-body --silent --show-error --max-time 600 \
  --header 'Content-Type: application/json' \
  "http://${CHECK_HOST}:${PORT}/v1/chat/completions" \
  --data "{\"model\":\"${SERVED_NAME}\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly the single word HELLO.\"}],\"max_tokens\":20,\"chat_template_kwargs\":{\"enable_thinking\":false}}")

printf '%s' "${PLAIN_RESPONSE}" | python3 -c '
import json, sys
data = json.load(sys.stdin)
error = data.get("error")
if error:
    raise SystemExit(f"plain smoke returned API error: {error!r}")
try:
    content = data["choices"][0]["message"]["content"]
except (KeyError, IndexError, TypeError) as exc:
    raise SystemExit(f"plain smoke response shape invalid: {exc}")
if not isinstance(content, str) or "hello" not in content.casefold():
    raise SystemExit(f"plain smoke did not return HELLO: {content!r}")
print("Plain smoke passed: assistant content contains HELLO.")
'

THINKING_RESPONSE=$(curl --fail-with-body --silent --show-error --max-time 600 \
  --header 'Content-Type: application/json' \
  "http://${CHECK_HOST}:${PORT}/v1/chat/completions" \
  --data "{\"model\":\"${SERVED_NAME}\",\"messages\":[{\"role\":\"user\",\"content\":\"Solve 17*24 step by step and give the numerical answer.\"}],\"max_tokens\":500,\"thinking_token_budget\":${THINKING_BUDGET}}")

printf '%s' "${THINKING_RESPONSE}" | python3 -c '
import json, sys
data = json.load(sys.stdin)
error = data.get("error")
if error:
    raise SystemExit(f"thinking smoke returned API error: {error!r}")
try:
    message = data["choices"][0]["message"]
except (KeyError, IndexError, TypeError) as exc:
    raise SystemExit(f"thinking smoke response shape invalid: {exc}")
content = message.get("content") or ""
reasoning = message.get("reasoning_content") or ""
if not isinstance(content, str) or not isinstance(reasoning, str):
    raise SystemExit("thinking smoke content/reasoning fields are not strings")
if not reasoning.strip():
    raise SystemExit("thinking smoke returned no reasoning_content")
if "408" not in f"{reasoning}\n{content}":
    raise SystemExit("thinking smoke did not contain the expected answer 408")
print("Thinking smoke passed: reasoning is nonempty and response contains 408.")
'

trap - ERR
printf 'Startup and bounded smoke checks passed. This is not a benchmark or long-context validation.\n'

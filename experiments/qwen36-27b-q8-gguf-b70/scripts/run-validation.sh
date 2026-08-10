#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LANE="$ROOT/experiments/qwen36-27b-q8-gguf-b70"
MANIFEST="$LANE/model-manifest.json"
CANONICAL_RUNTIME_MANIFEST="$LANE/runtime-manifest.json"
VDR4_RUNTIME_MANIFEST="$LANE/runtime-manifest-q8-vdr4-control.json"
VDR2_RUNTIME_MANIFEST="$LANE/runtime-manifest-q8-vdr2-candidate.json"
RUNTIME_PROFILE="${RUNTIME_PROFILE-canonical-baseline}"

case "$RUNTIME_PROFILE" in
  canonical-baseline)
    RUNTIME_PROFILE_EXPECTED_MANIFEST="$CANONICAL_RUNTIME_MANIFEST"
    RUNTIME_PROFILE_EXPECTED_MANIFEST_SHA256="ebab7496fa6665c3f7e8e3dcfd8e18945b4cc5e365a009f5bbffd7c7e878ede6"
    RUNTIME_PROFILE_EXPECTED_Q8_VDR=4
    RUNTIME_PROFILE_DIAGNOSTIC=0
    ;;
  q8-vdr4-control)
    RUNTIME_PROFILE_EXPECTED_MANIFEST="$VDR4_RUNTIME_MANIFEST"
    RUNTIME_PROFILE_EXPECTED_MANIFEST_SHA256="d127dbaaf30e014cbae0dc59a3c0b0f61f329eabadffb74ce40e01264bee79cc"
    RUNTIME_PROFILE_EXPECTED_Q8_VDR=4
    RUNTIME_PROFILE_DIAGNOSTIC=1
    ;;
  q8-vdr2-candidate)
    RUNTIME_PROFILE_EXPECTED_MANIFEST="$VDR2_RUNTIME_MANIFEST"
    RUNTIME_PROFILE_EXPECTED_MANIFEST_SHA256="4119790a79c55d158e7257d4fa0d95be0ca34639807c1a71ce87b60d6fdc1b49"
    RUNTIME_PROFILE_EXPECTED_Q8_VDR=2
    RUNTIME_PROFILE_DIAGNOSTIC=1
    ;;
  *)
    echo "invalid RUNTIME_PROFILE=$RUNTIME_PROFILE; expected canonical-baseline, q8-vdr4-control, or q8-vdr2-candidate" >&2
    exit 2
    ;;
esac
RUNTIME_MANIFEST="${RUNTIME_MANIFEST:-$RUNTIME_PROFILE_EXPECTED_MANIFEST}"

GPU_INDEX="${GPU_INDEX:-0}"
PORT="${PORT:-19460}"
RUN_SCOPE="${RUN_SCOPE:-smoke}"
PROMOTION_PROFILE="${PROMOTION_PROFILE-goal1-baseline-ub128}"
FULL512_BAND="${FULL512_BAND:-realistic}"
PARALLEL_SLOTS="${PARALLEL_SLOTS:-1}"
KV_UNIFIED="${KV_UNIFIED:-0}"
CONT_BATCHING="${CONT_BATCHING:-1}"
BATCH_SIZE="${BATCH_SIZE:-1024}"
UBATCH_SIZE="${UBATCH_SIZE:-128}"
N_GPU_LAYERS="${N_GPU_LAYERS:-99}"
THREADS="${THREADS:-8}"
POLL="${POLL:-50}"
CACHE_TYPE_K="${CACHE_TYPE_K:-f16}"
CACHE_TYPE_V="${CACHE_TYPE_V:-f16}"
FLASH_ATTN="${FLASH_ATTN:-on}"
LOG_VERBOSITY="${LOG_VERBOSITY:-4}"
LANE_DNN_ENABLED="${LANE_DNN_ENABLED:-0}"
LANE_OPT_ENABLED="${LANE_OPT_ENABLED:-1}"
LANE_FA_ONEDNN="${LANE_FA_ONEDNN:-1}"
LANE_FA_ONEDNN_MAX_KV="${LANE_FA_ONEDNN_MAX_KV:-0}"
LANE_MKL_FA="${LANE_MKL_FA:-1}"
LANE_SYCL_FLASH_ATTN="${LANE_SYCL_FLASH_ATTN:-1}"
HTTP_THREADS="${HTTP_THREADS:-6}"
MODEL="${MODEL:-/mnt/usb-models/models/qwen36-27b-q8-gguf/Qwen3.6-27B-Q8_0.gguf}"
MODEL_ALIAS="${MODEL_ALIAS:-qwen36-27b-q8_0-target-only}"
VERIFY_MODEL_SHA256="${VERIFY_MODEL_SHA256:-1}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}"
GPU_IDLE_MAX_MIB="${GPU_IDLE_MAX_MIB:-256}"
REQUIRE_ALL_GPUS_IDLE="${REQUIRE_ALL_GPUS_IDLE:-1}"
MIN_HOST_AVAILABLE_KIB="${MIN_HOST_AVAILABLE_KIB:-33554432}"
MIN_LOADED_DELTA_MIB="${MIN_LOADED_DELTA_MIB:-25000}"
MAX_LOADED_USED_MIB="${MAX_LOADED_USED_MIB:-32000}"
CASE_ID="${CASE_ID:-}"
ORACLE_JSON="${ORACLE_JSON:-}"
ORACLE_JSON_SHA256="${ORACLE_JSON_SHA256:-}"
PREFIX_ORACLE_JSON="${PREFIX_ORACLE_JSON:-}"
SEALED_128_ORACLE="/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/qwen36-27b-q8_0-f16kv-short-dnn0-exact-20260808T232639Z/exact-tokens.json"
SEALED_128_ORACLE_SHA256="e4477808823cdf9bb182d5abc4788cee216011a0195cf49bf03a7bda35f5dbcc"
SEALED_128_SUITE="$ROOT/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json"
SEALED_128_CANARY_PROMPT_ID="incident-retrospective"
if [[ -z "${EVIDENCE_CLASS:-}" ]]; then
  if [[ "$RUN_SCOPE" == "promotion512" ]]; then
    EVIDENCE_CLASS="official-isolated"
  else
    EVIDENCE_CLASS="legacy-validation"
  fi
fi
PERFORMANCE_PROMOTABLE=0
case "$PROMOTION_PROFILE" in
  goal1-baseline-ub128) PROMOTION_EXPECTED_UBATCH_SIZE=128 ;;
  prefill-ub1024) PROMOTION_EXPECTED_UBATCH_SIZE=1024 ;;
  *)
    echo "invalid PROMOTION_PROFILE=$PROMOTION_PROFILE; expected goal1-baseline-ub128 or prefill-ub1024" >&2
    exit 2
    ;;
esac
if [[ "$RUN_SCOPE" != "promotion512" && "$PROMOTION_PROFILE" != "goal1-baseline-ub128" ]]; then
  echo "PROMOTION_PROFILE=$PROMOTION_PROFILE is only allowed with RUN_SCOPE=promotion512" >&2
  exit 2
fi
STAMP="$(date -u +%Y%m%dT%H%M%S.%NZ)"
LABEL="${LABEL:-qwen36-27b-q8_0-${CACHE_TYPE_K}kv-${RUN_SCOPE}-gpu${GPU_INDEX}-${FULL512_BAND}-${EVIDENCE_CLASS}}"
if [[ "$RUN_SCOPE" == "promotion512" ]]; then
  LABEL="${LABEL}-${PROMOTION_PROFILE}-ub${PROMOTION_EXPECTED_UBATCH_SIZE}"
fi
if (( RUNTIME_PROFILE_DIAGNOSTIC == 1 )); then
  LABEL="${LABEL}-${RUNTIME_PROFILE}-vdr${RUNTIME_PROFILE_EXPECTED_Q8_VDR}"
fi
RUN_DIR="${RUN_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/${LABEL}-${STAMP}}"

case "$RUN_SCOPE" in
  smoke|short|long|full|promotion512) ;;
  *)
    echo "invalid RUN_SCOPE=$RUN_SCOPE; expected smoke, short, long, full, or promotion512" >&2
    exit 2
    ;;
esac
case "$FULL512_BAND" in
  realistic|short|middle|near32k) ;;
  *)
    echo "invalid FULL512_BAND=$FULL512_BAND; expected realistic, short, middle, or near32k" >&2
    exit 2
    ;;
esac
if [[ "$RUN_SCOPE" != "promotion512" && "$FULL512_BAND" != "realistic" ]]; then
  echo "FULL512_BAND is only used by RUN_SCOPE=promotion512" >&2
  exit 2
fi
if [[ ! "$GPU_IDLE_MAX_MIB" =~ ^[0-9]+$ ]]; then
  echo "GPU_IDLE_MAX_MIB must be a nonnegative integer" >&2
  exit 2
fi
for numeric_name in READINESS_TIMEOUT_S MIN_HOST_AVAILABLE_KIB MIN_LOADED_DELTA_MIB MAX_LOADED_USED_MIB; do
  numeric_value="${!numeric_name}"
  if [[ ! "$numeric_value" =~ ^[0-9]+$ ]] || (( numeric_value <= 0 )); then
    echo "$numeric_name must be a positive integer" >&2
    exit 2
  fi
done
if (( RUNTIME_PROFILE_DIAGNOSTIC == 1 )); then
  [[ "$RUN_SCOPE" == "promotion512" ]] || {
    echo "RUNTIME_PROFILE=$RUNTIME_PROFILE is restricted to RUN_SCOPE=promotion512" >&2
    exit 2
  }
  [[ "$FULL512_BAND" == "short" ]] || {
    echo "RUNTIME_PROFILE=$RUNTIME_PROFILE is restricted to FULL512_BAND=short" >&2
    exit 2
  }
  [[ "$EVIDENCE_CLASS" == "parallel-functional-screen" ]] || {
    echo "RUNTIME_PROFILE=$RUNTIME_PROFILE requires EVIDENCE_CLASS=parallel-functional-screen" >&2
    exit 2
  }
  [[ "$REQUIRE_ALL_GPUS_IDLE" == "0" ]] || {
    echo "RUNTIME_PROFILE=$RUNTIME_PROFILE requires REQUIRE_ALL_GPUS_IDLE=0" >&2
    exit 2
  }
fi

[[ -f "$RUNTIME_PROFILE_EXPECTED_MANIFEST" ]] || {
  echo "runtime profile manifest not found: $RUNTIME_PROFILE_EXPECTED_MANIFEST" >&2
  exit 2
}
[[ -f "$RUNTIME_MANIFEST" ]] || {
  echo "runtime manifest not found: $RUNTIME_MANIFEST" >&2
  exit 2
}
resolved_runtime_manifest="$(readlink -f "$RUNTIME_MANIFEST")"
resolved_expected_runtime_manifest="$(readlink -f "$RUNTIME_PROFILE_EXPECTED_MANIFEST")"
if [[ "$resolved_runtime_manifest" != "$resolved_expected_runtime_manifest" ]]; then
  echo "RUNTIME_PROFILE=$RUNTIME_PROFILE requires RUNTIME_MANIFEST=$RUNTIME_PROFILE_EXPECTED_MANIFEST" >&2
  exit 2
fi
runtime_manifest_sha256="$(sha256sum "$RUNTIME_MANIFEST" | awk '{print $1}')"
if [[ ! "$RUNTIME_PROFILE_EXPECTED_MANIFEST_SHA256" =~ ^[0-9a-f]{64}$ ]] || \
   [[ "$runtime_manifest_sha256" != "$RUNTIME_PROFILE_EXPECTED_MANIFEST_SHA256" ]]; then
  echo "RUNTIME_PROFILE=$RUNTIME_PROFILE runtime manifest SHA-256 mismatch" >&2
  exit 2
fi
RUNTIME_PROFILE_CHECK_JSON="$(python3 - \
  "$RUNTIME_MANIFEST" "$RUNTIME_PROFILE" "$RUNTIME_PROFILE_EXPECTED_Q8_VDR" \
  "$RUNTIME_PROFILE_DIAGNOSTIC" "$RUNTIME_PROFILE_EXPECTED_MANIFEST_SHA256" <<'PY'
import json
import os
import re
import sys

manifest_path, profile, expected_vdr_raw, diagnostic_raw, expected_sha = sys.argv[1:]
expected_vdr = int(expected_vdr_raw)
diagnostic = diagnostic_raw == "1"
try:
    with open(manifest_path) as stream:
        manifest = json.load(stream)
except (OSError, json.JSONDecodeError) as exc:
    raise SystemExit(f"cannot read runtime profile manifest: {exc}")

binary_path = manifest.get("llama_server_path")
binary_sha = manifest.get("llama_server_sha256")
if not isinstance(binary_path, str) or not os.path.isabs(binary_path):
    raise SystemExit("runtime manifest llama_server_path must be absolute")
if not isinstance(binary_sha, str) or re.fullmatch(r"[0-9a-f]{64}", binary_sha) is None:
    raise SystemExit("runtime manifest llama_server_sha256 must be a lowercase SHA-256")

manifest_profile = manifest.get("runtime_profile")
controls = manifest.get("compile_time_controls")
manifest_vdr = (
    controls.get("GGML_SYCL_REORDER_Q8_0_VDR_MMVQ")
    if isinstance(controls, dict)
    else None
)
if diagnostic:
    if manifest_profile != profile:
        raise SystemExit(
            f"runtime manifest runtime_profile mismatch: expected {profile!r}, "
            f"observed {manifest_profile!r}"
        )
    if type(manifest_vdr) is not int or manifest_vdr != expected_vdr:
        raise SystemExit(
            "runtime manifest compile_time_controls."
            "GGML_SYCL_REORDER_Q8_0_VDR_MMVQ mismatch: "
            f"expected integer {expected_vdr}, observed {manifest_vdr!r}"
        )
    declared_vdr = manifest_vdr
    declared_vdr_source = (
        "runtime-manifest:compile_time_controls."
        "GGML_SYCL_REORDER_Q8_0_VDR_MMVQ"
    )
else:
    declared_vdr = expected_vdr
    declared_vdr_source = "frozen-canonical-manifest-and-source"

report = {
    "passed": True,
    "runtime_profile": profile,
    "diagnostic_profile": diagnostic,
    "runtime_manifest": os.path.realpath(manifest_path),
    "runtime_manifest_sha256": expected_sha,
    "manifest_runtime_profile": manifest_profile,
    "declared_q8_reorder_vdr_mmvq": declared_vdr,
    "declared_q8_reorder_vdr_mmvq_source": declared_vdr_source,
    "manifest_declared_q8_reorder_vdr_mmvq": manifest_vdr,
    "llama_server_path": os.path.normpath(binary_path),
    "llama_server_sha256": binary_sha,
}
print(json.dumps(report, sort_keys=True))
PY
)"
RUNTIME_DECLARED_Q8_VDR="$(python3 -c \
  'import json,sys; print(json.loads(sys.argv[1])["declared_q8_reorder_vdr_mmvq"])' \
  "$RUNTIME_PROFILE_CHECK_JSON")"
RUNTIME_PROFILE_MANIFEST_LLAMA_SERVER="$(python3 -c \
  'import json,sys; print(json.loads(sys.argv[1])["llama_server_path"])' \
  "$RUNTIME_PROFILE_CHECK_JSON")"
LLAMA_SERVER="${LLAMA_SERVER:-$RUNTIME_PROFILE_MANIFEST_LLAMA_SERVER}"
if [[ "$(readlink -m "$LLAMA_SERVER")" != "$(readlink -m "$RUNTIME_PROFILE_MANIFEST_LLAMA_SERVER")" ]]; then
  echo "RUNTIME_PROFILE=$RUNTIME_PROFILE requires LLAMA_SERVER=$RUNTIME_PROFILE_MANIFEST_LLAMA_SERVER" >&2
  exit 2
fi
if [[ "$RUN_SCOPE" == "promotion512" ]]; then
  if [[ "$UBATCH_SIZE" != "$PROMOTION_EXPECTED_UBATCH_SIZE" ]]; then
    echo "PROMOTION_PROFILE=$PROMOTION_PROFILE requires UBATCH_SIZE=$PROMOTION_EXPECTED_UBATCH_SIZE" >&2
    exit 2
  fi
  promotion_identity=(
    "$KV_UNIFIED" "$CONT_BATCHING" "$BATCH_SIZE" "$UBATCH_SIZE"
    "$N_GPU_LAYERS" "$THREADS" "$POLL" "$CACHE_TYPE_K" "$CACHE_TYPE_V"
    "$FLASH_ATTN" "$LANE_DNN_ENABLED" "$LANE_OPT_ENABLED"
    "$LANE_FA_ONEDNN" "$LANE_FA_ONEDNN_MAX_KV" "$LANE_MKL_FA"
    "$LANE_SYCL_FLASH_ATTN" "$HTTP_THREADS"
  )
  promotion_expected=(
    0 1 1024 "$PROMOTION_EXPECTED_UBATCH_SIZE" 99 8 50 f16 f16 on 0 1 1 0 1 1 6
  )
  if [[ "${promotion_identity[*]}" != "${promotion_expected[*]}" ]]; then
    echo "RUN_SCOPE=promotion512 requires the locked F16/DNN0/OPT1 Goal-1 baseline identity" >&2
    exit 2
  fi
  case "$EVIDENCE_CLASS" in
    official-isolated)
      [[ "$REQUIRE_ALL_GPUS_IDLE" == "1" ]] || {
        echo "official-isolated promotion requires all four GPUs idle" >&2
        exit 2
      }
      PERFORMANCE_PROMOTABLE=1
      ;;
    parallel-functional-screen)
      [[ "$REQUIRE_ALL_GPUS_IDLE" == "0" ]] || {
        echo "parallel-functional-screen requires REQUIRE_ALL_GPUS_IDLE=0" >&2
        exit 2
      }
      PERFORMANCE_PROMOTABLE=0
      ;;
    *)
      echo "promotion512 EVIDENCE_CLASS must be official-isolated or parallel-functional-screen" >&2
      exit 2
      ;;
  esac
  [[ "$MODEL_ALIAS" == "qwen36-27b-q8_0-target-only" ]] || {
    echo "promotion512 MODEL_ALIAS is locked" >&2
    exit 2
  }
  [[ "$LOG_VERBOSITY" == "4" ]] || {
    echo "promotion512 requires LOG_VERBOSITY=4" >&2
    exit 2
  }
  (( GPU_IDLE_MAX_MIB <= 256 )) || {
    echo "promotion512 GPU_IDLE_MAX_MIB cannot exceed 256" >&2
    exit 2
  }
  (( MIN_HOST_AVAILABLE_KIB >= 33554432 )) || {
    echo "promotion512 requires at least a 32-GiB MemAvailable floor" >&2
    exit 2
  }
  (( MIN_LOADED_DELTA_MIB >= 25000 )) || {
    echo "promotion512 loaded-VRAM delta floor cannot be below 25000 MiB" >&2
    exit 2
  }
  (( MAX_LOADED_USED_MIB <= 32000 )) || {
    echo "promotion512 loaded-VRAM ceiling cannot exceed 32000 MiB" >&2
    exit 2
  }
  [[ -f "$SEALED_128_ORACLE" && -f "$SEALED_128_SUITE" ]] || {
    echo "promotion512 sealed canary inputs are missing" >&2
    exit 2
  }
  actual_canary_sha="$(sha256sum "$SEALED_128_ORACLE" | awk '{print $1}')"
  [[ "$actual_canary_sha" == "$SEALED_128_ORACLE_SHA256" ]] || {
    echo "sealed 128-token canary oracle SHA-256 mismatch" >&2
    exit 2
  }
  if [[ "$FULL512_BAND" == "realistic" ]]; then
    PREFIX_ORACLE_JSON="${PREFIX_ORACLE_JSON:-$SEALED_128_ORACLE}"
    [[ -f "$PREFIX_ORACLE_JSON" ]] || {
      echo "sealed 128-token prefix oracle is missing: $PREFIX_ORACLE_JSON" >&2
      exit 2
    }
    actual_prefix_sha="$(sha256sum "$PREFIX_ORACLE_JSON" | awk '{print $1}')"
    if [[ "$actual_prefix_sha" != "$SEALED_128_ORACLE_SHA256" ]]; then
      echo "sealed 128-token prefix oracle SHA-256 mismatch" >&2
      exit 2
    fi
  fi
fi
if (( RUNTIME_PROFILE_DIAGNOSTIC == 1 && PERFORMANCE_PROMOTABLE != 0 )); then
  echo "diagnostic RUNTIME_PROFILE=$RUNTIME_PROFILE must remain performance_promotable=false" >&2
  exit 2
fi
if [[ "$RUN_SCOPE" != "promotion512" && "$EVIDENCE_CLASS" != "legacy-validation" ]]; then
  echo "non-promotion scopes require EVIDENCE_CLASS=legacy-validation" >&2
  exit 2
fi
if [[ -n "$PREFIX_ORACLE_JSON" && ( "$RUN_SCOPE" != "promotion512" || "$FULL512_BAND" != "realistic" ) ]]; then
  echo "PREFIX_ORACLE_JSON is only supported for promotion512/realistic" >&2
  exit 2
fi
if [[ ! "$GPU_INDEX" =~ ^[0-3]$ ]]; then
  echo "GPU_INDEX must be 0, 1, 2, or 3" >&2
  exit 2
fi
if [[ ! "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1024 || PORT > 65535 )); then
  echo "PORT must be an integer from 1024 through 65535" >&2
  exit 2
fi
if [[ "$PARALLEL_SLOTS" != "1" ]]; then
  echo "run-validation.sh is the c1 runner and requires PARALLEL_SLOTS=1" >&2
  exit 2
fi
if [[ "$REQUIRE_ALL_GPUS_IDLE" != "0" && "$REQUIRE_ALL_GPUS_IDLE" != "1" ]]; then
  echo "REQUIRE_ALL_GPUS_IDLE must be 0 or 1" >&2
  exit 2
fi
if [[ -n "$ORACLE_JSON" ]]; then
  [[ -f "$ORACLE_JSON" ]] || {
    echo "oracle JSON not found: $ORACLE_JSON" >&2
    exit 2
  }
  [[ "$ORACLE_JSON_SHA256" =~ ^[0-9a-f]{64}$ ]] || {
    echo "ORACLE_JSON_SHA256 is required with ORACLE_JSON" >&2
    exit 2
  }
  [[ "$(sha256sum "$ORACLE_JSON" | awk '{print $1}')" == "$ORACLE_JSON_SHA256" ]] || {
    echo "oracle JSON SHA-256 mismatch" >&2
    exit 2
  }
elif [[ -n "$ORACLE_JSON_SHA256" ]]; then
  echo "ORACLE_JSON_SHA256 requires ORACLE_JSON" >&2
  exit 2
fi

if [[ -z "${CTX_SIZE:-}" ]]; then
  case "$RUN_SCOPE" in
    smoke|short) CTX_SIZE=4096 ;;
    long|full|promotion512) CTX_SIZE=32768 ;;
  esac
fi
if [[ ! "$CTX_SIZE" =~ ^[0-9]+$ ]] || (( CTX_SIZE <= 0 )); then
  echo "CTX_SIZE must be a positive integer" >&2
  exit 2
fi
if [[ "$RUN_SCOPE" == "smoke" || "$RUN_SCOPE" == "short" ]] && (( CTX_SIZE > 4096 )); then
  echo "$RUN_SCOPE requires CTX_SIZE<=4096; use long or full for the 32K allocation gate" >&2
  exit 2
fi
if [[ "$RUN_SCOPE" == "long" || "$RUN_SCOPE" == "full" || "$RUN_SCOPE" == "promotion512" ]] && (( CTX_SIZE != 32768 )); then
  echo "$RUN_SCOPE requires CTX_SIZE=32768" >&2
  exit 2
fi
if [[ "$VERIFY_MODEL_SHA256" != "1" ]]; then
  echo "VERIFY_MODEL_SHA256=1 is required for this validation runner" >&2
  exit 2
fi

EXPECTED_SHA256="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["sha256"])' "$MANIFEST")"
EXPECTED_SIZE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["size_bytes"])' "$MANIFEST")"
EXPECTED_RUNTIME_SHA256="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["llama_server_sha256"])' "$RUNTIME_MANIFEST")"
if [[ ! -f "$MODEL" ]]; then
  echo "model not found: $MODEL" >&2
  exit 2
fi
ACTUAL_SIZE="$(stat -c %s "$MODEL")"
if [[ "$ACTUAL_SIZE" != "$EXPECTED_SIZE" ]]; then
  echo "model size mismatch: expected $EXPECTED_SIZE, got $ACTUAL_SIZE" >&2
  exit 2
fi
for required_command in awk chmod cmp cp curl dirname flock grep id journalctl jq \
  mkdir mktemp modinfo ps python3 readlink sha256sum sort ss timeout xargs xpu-smi; do
  command -v "$required_command" >/dev/null 2>&1 || {
    echo "required command not found: $required_command" >&2
    exit 2
  }
done

[[ "$RUN_DIR" == /* && "$RUN_DIR" != "/" ]] || {
  echo "RUN_DIR must be a non-root absolute path" >&2
  exit 2
}
[[ "$RUN_DIR" != *$'\n'* ]] || {
  echo "RUN_DIR must not contain a newline" >&2
  exit 2
}
mkdir -p "$(dirname "$RUN_DIR")"
if ! mkdir "$RUN_DIR"; then
  echo "RUN_DIR already exists or could not be created: $RUN_DIR" >&2
  exit 2
fi
printf '%s\n' "$RUNTIME_PROFILE_CHECK_JSON" > "$RUN_DIR/runtime-profile-check.json"
RUNTIME_PROFILE_CHECK_SHA256="$(sha256sum "$RUN_DIR/runtime-profile-check.json" | awk '{print $1}')"

exec {QWEN36_MODEL_FD}<"$MODEL"
flock -s -n "$QWEN36_MODEL_FD" || {
  echo "could not acquire the shared model-file lock" >&2
  exit 2
}
MODEL_FD_PATH="/proc/$$/fd/$QWEN36_MODEL_FD"
[[ "$MODEL" -ef "$MODEL_FD_PATH" ]] || {
  echo "model pathname does not match the pinned model descriptor" >&2
  exit 2
}
[[ "$(stat -Lc %s "$MODEL_FD_PATH")" == "$EXPECTED_SIZE" ]] || {
  echo "pinned model descriptor size does not match the manifest" >&2
  exit 2
}
export QWEN36_MODEL_FD

command -v flock >/dev/null 2>&1 || {
  echo "flock is required for the shared GPU lease" >&2
  exit 2
}
GPU_LEASE_DIR="/run/user/$(id -u)/qwen36-b70-gpu-leases"
mkdir -p "$GPU_LEASE_DIR"
GPU_LEASE_PATH="$GPU_LEASE_DIR/gpu${GPU_INDEX}.lock"
declare -A HELD_GPU_LEASE_PATHS=()
declare -A HELD_GPU_LEASE_FDS=()
inherited_selected_gpu_lease_fd="${QWEN36_GPU_LEASE_FD:-}"
if [[ "$EVIDENCE_CLASS" == "official-isolated" ]]; then
  lease_devices=(0 1 2 3)
else
  lease_devices=("$GPU_INDEX")
fi
for lease_gpu in "${lease_devices[@]}"; do
  lease_path="$GPU_LEASE_DIR/gpu${lease_gpu}.lock"
  lease_fd=""
  if [[ "$lease_gpu" == "$GPU_INDEX" && -n "$inherited_selected_gpu_lease_fd" ]]; then
    [[ "$inherited_selected_gpu_lease_fd" =~ ^[0-9]+$ ]] || {
      echo "QWEN36_GPU_LEASE_FD must be numeric" >&2
      exit 2
    }
    inherited_lease_path="$(readlink -f "/proc/$$/fd/$inherited_selected_gpu_lease_fd" 2>/dev/null || true)"
    [[ "$inherited_lease_path" == "$(readlink -f "$lease_path")" ]] || {
      echo "inherited GPU lease does not match GPU $GPU_INDEX" >&2
      exit 2
    }
    flock -n "$inherited_selected_gpu_lease_fd" || {
      echo "inherited GPU lease is not held" >&2
      exit 2
    }
    lease_fd="$inherited_selected_gpu_lease_fd"
  else
    exec {lease_fd}>"$lease_path"
    flock -n "$lease_fd" || {
      echo "GPU $lease_gpu is leased by another Qwen validation process" >&2
      exit 2
    }
  fi
  HELD_GPU_LEASE_PATHS[$lease_gpu]="$lease_path"
  HELD_GPU_LEASE_FDS[$lease_gpu]="$lease_fd"
done
QWEN36_GPU_LEASE_FD="${HELD_GPU_LEASE_FDS[$GPU_INDEX]}"
GPU_LEASE_PATH="${HELD_GPU_LEASE_PATHS[$GPU_INDEX]}"
export QWEN36_GPU_LEASE_FD
{
  echo "selected_gpu_index=$GPU_INDEX"
  echo "evidence_class=$EVIDENCE_CLASS"
  for lease_gpu in "${lease_devices[@]}"; do
    echo "gpu${lease_gpu}_lease_path=${HELD_GPU_LEASE_PATHS[$lease_gpu]}"
    echo "gpu${lease_gpu}_lease_fd=${HELD_GPU_LEASE_FDS[$lease_gpu]}"
  done
} > "$RUN_DIR/gpu-lease.env"

PORT_LEASE_DIR="/run/user/$(id -u)/qwen36-b70-port-leases"
mkdir -p "$PORT_LEASE_DIR"
PORT_LEASE_PATH="$PORT_LEASE_DIR/port${PORT}.lock"
if [[ -n "${QWEN36_PORT_LEASE_FD:-}" ]]; then
  [[ "$QWEN36_PORT_LEASE_FD" =~ ^[0-9]+$ ]] || {
    echo "QWEN36_PORT_LEASE_FD must be numeric" >&2
    exit 2
  }
  inherited_port_lease_path="$(readlink -f "/proc/$$/fd/$QWEN36_PORT_LEASE_FD" 2>/dev/null || true)"
  [[ "$inherited_port_lease_path" == "$(readlink -f "$PORT_LEASE_PATH")" ]] || {
    echo "inherited port lease does not match port $PORT" >&2
    exit 2
  }
  flock -n "$QWEN36_PORT_LEASE_FD" || {
    echo "inherited port lease is not held" >&2
    exit 2
  }
else
  exec {QWEN36_PORT_LEASE_FD}>"$PORT_LEASE_PATH"
  flock -n "$QWEN36_PORT_LEASE_FD" || {
    echo "port $PORT is leased by another Qwen validation process" >&2
    exit 2
  }
  export QWEN36_PORT_LEASE_FD
fi
printf 'port=%s\nlease_path=%s\nlease_fd=%s\n' \
  "$PORT" "$PORT_LEASE_PATH" "$QWEN36_PORT_LEASE_FD" \
  > "$RUN_DIR/port-lease.env"

ORACLE_JSON_SOURCE="$ORACLE_JSON"
PREFIX_ORACLE_JSON_SOURCE="$PREFIX_ORACLE_JSON"
SEALED_128_ORACLE_SNAPSHOT=""
if [[ "$RUN_SCOPE" == "promotion512" ]]; then
  mkdir "$RUN_DIR/oracle-snapshots"
  SEALED_128_ORACLE_SNAPSHOT="$RUN_DIR/oracle-snapshots/sealed-128-oracle.json"
  cp -- "$SEALED_128_ORACLE" "$SEALED_128_ORACLE_SNAPSHOT"
  chmod 0444 "$SEALED_128_ORACLE_SNAPSHOT"
  printf '%s  %s\n' "$SEALED_128_ORACLE_SHA256" "$SEALED_128_ORACLE_SNAPSHOT" |
    sha256sum -c - > "$RUN_DIR/sealed-128-oracle-snapshot.check.txt"
  if [[ -n "$PREFIX_ORACLE_JSON" ]]; then
    PREFIX_ORACLE_JSON="$SEALED_128_ORACLE_SNAPSHOT"
  fi
fi
if [[ -n "$ORACLE_JSON_SOURCE" ]]; then
  mkdir -p "$RUN_DIR/oracle-snapshots"
  ORACLE_JSON="$RUN_DIR/oracle-snapshots/comparison-oracle.json"
  cp -- "$ORACLE_JSON_SOURCE" "$ORACLE_JSON"
  chmod 0444 "$ORACLE_JSON"
  printf '%s  %s\n' "$ORACLE_JSON_SHA256" "$ORACLE_JSON" |
    sha256sum -c - > "$RUN_DIR/comparison-oracle-snapshot.check.txt"
fi
START_EPOCH="$(date +%s)"
SERVER_PID=""
SERVER_EXPECTED_RUNNING=0
BODY_COMPLETED=0
CLEANUP_FORCED=0
CLEANUP_SURVIVOR=0
PRE_GPU_USED_MIB=""
RUNTIME_BUNDLE_READY=0
RUNTIME_BUNDLE_REPORT_SHA256=""
RUNTIME_RESOLVED_MANIFEST_SHA256=""
HARNESS_MANIFEST_SHA256=""
MODEL_STAT_BASELINE_READY=0

check_host_memory() {
  local label="$1"
  local available_kib
  local swap_free_kib

  available_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
  swap_free_kib="$(awk '/^SwapFree:/ {print $2}' /proc/meminfo)"
  {
    echo "MemAvailable_kib=${available_kib:-unknown}"
    echo "SwapFree_kib=${swap_free_kib:-unknown}"
    echo "required_MemAvailable_kib=$MIN_HOST_AVAILABLE_KIB"
  } > "$RUN_DIR/host-memory-${label}.env"
  [[ -n "$available_kib" && "$available_kib" =~ ^[0-9]+$ ]] || return 1
  (( available_kib >= MIN_HOST_AVAILABLE_KIB ))
}

capture_model_stat() {
  local output="$1"
  python3 - "$MODEL" "$MODEL_FD_PATH" "$output" <<'PY'
import json
import os
import stat
import sys

model_path, model_fd_path, output_path = sys.argv[1:]
info = os.stat(model_fd_path, follow_symlinks=True)
payload = {
    "requested_path": model_path,
    "requested_path_resolved": os.path.realpath(model_path),
    "pinned_fd_path": model_fd_path,
    "pinned_path_resolved": os.path.realpath(model_fd_path),
    "device": info.st_dev,
    "inode": info.st_ino,
    "size_bytes": info.st_size,
    "mtime_ns": info.st_mtime_ns,
    "ctime_ns": info.st_ctime_ns,
    "mode": stat.S_IMODE(info.st_mode),
}
with open(output_path, "w") as output:
    json.dump(payload, output, indent=2, sort_keys=True)
    output.write("\n")
PY
}

verify_model_stat() {
  local label="$1"
  local observed="$RUN_DIR/model-stat-${label}.json"
  local check_log="$RUN_DIR/model-stat-${label}.check.log"

  (( MODEL_STAT_BASELINE_READY == 1 )) || {
    printf 'model stat baseline was not initialized\n' > "$check_log"
    return 1
  }
  [[ "$MODEL" -ef "$MODEL_FD_PATH" ]] || {
    printf 'model pathname no longer matches pinned descriptor\n' > "$check_log"
    return 1
  }
  capture_model_stat "$observed" || return 1
  if cmp -s "$RUN_DIR/model-stat-baseline.json" "$observed"; then
    printf 'model stat identity unchanged\n' > "$check_log"
    return 0
  fi
  printf 'model stat identity changed\n' > "$check_log"
  return 1
}

verify_harness_inputs() {
  local label="$1"
  local check_log="$RUN_DIR/harness-inputs-${label}.check.log"
  local observed_manifest_sha256

  [[ -n "$HARNESS_MANIFEST_SHA256" ]] || {
    printf 'harness manifest was not initialized\n' > "$check_log"
    return 1
  }
  observed_manifest_sha256="$(sha256sum "$RUN_DIR/harness-inputs.sha256" | awk '{print $1}')" || return 1
  if [[ "$observed_manifest_sha256" != "$HARNESS_MANIFEST_SHA256" ]]; then
    printf 'harness manifest digest changed\n' > "$check_log"
    return 1
  fi
  sha256sum -c "$RUN_DIR/harness-inputs.sha256" > "$check_log" 2>&1
}

cleanup() {
  local state
  local running=0

  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    state="$(ps -o stat= -p "$SERVER_PID" 2>/dev/null | awk '{print $1}')"
    [[ "$state" == Z* ]] || running=1
  fi
  if (( running == 1 )); then
    kill "$SERVER_PID" 2>/dev/null || true
    for _ in $(seq 1 30); do
      if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        break
      fi
      state="$(ps -o stat= -p "$SERVER_PID" 2>/dev/null | awk '{print $1}')"
      [[ "$state" == Z* ]] && break
      sleep 1
    done
    state="$(ps -o stat= -p "$SERVER_PID" 2>/dev/null | awk '{print $1}')"
    if kill -0 "$SERVER_PID" 2>/dev/null && [[ "$state" != Z* ]]; then
      CLEANUP_FORCED=1
      kill -KILL "$SERVER_PID" 2>/dev/null || true
      for _ in $(seq 1 10); do
        if ! kill -0 "$SERVER_PID" 2>/dev/null; then
          break
        fi
        state="$(ps -o stat= -p "$SERVER_PID" 2>/dev/null | awk '{print $1}')"
        [[ "$state" == Z* ]] && break
        sleep 1
      done
    fi
    state="$(ps -o stat= -p "$SERVER_PID" 2>/dev/null | awk '{print $1}')"
    if kill -0 "$SERVER_PID" 2>/dev/null && [[ "$state" != Z* ]]; then
      CLEANUP_SURVIVOR=1
    else
      wait "$SERVER_PID" 2>/dev/null || true
    fi
  elif [[ -n "$SERVER_PID" ]]; then
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}

verify_runtime_bundle_snapshot() {
  local label="$1"
  local check_log="$RUN_DIR/runtime-resolved-files-${label}.check.log"
  local ldd_output="$RUN_DIR/llama-server-ldd-${label}-post-oneapi.txt"
  local hashes_output="$RUN_DIR/runtime-resolved-files-${label}.sha256"
  local report_output="$RUN_DIR/runtime-bundle-${label}.json"
  local observed_report_sha256
  local observed_resolved_manifest_sha256

  if (( RUNTIME_BUNDLE_READY != 1 )); then
    printf 'runtime bundle baseline was not initialized\n' > "$check_log"
    return 1
  fi
  observed_report_sha256="$(sha256sum "$RUN_DIR/runtime-bundle-initial.json" | awk '{print $1}')" || return 1
  observed_resolved_manifest_sha256="$(sha256sum "$RUN_DIR/runtime-resolved-files.sha256" | awk '{print $1}')" || return 1
  if [[ "$observed_report_sha256" != "$RUNTIME_BUNDLE_REPORT_SHA256" ]] || \
     [[ "$observed_resolved_manifest_sha256" != "$RUNTIME_RESOLVED_MANIFEST_SHA256" ]]; then
    printf 'runtime bundle evidence manifest drifted\n' > "$check_log"
    return 1
  fi
  if ! sha256sum -c "$RUN_DIR/runtime-resolved-files.sha256" \
    > "$check_log" 2>&1; then
    return 1
  fi
  LLAMA_SERVER="$LLAMA_SERVER" \
  RUNTIME_MANIFEST="$RUNTIME_MANIFEST" \
    "$LANE/scripts/serve-target-only.sh" --verify-runtime-bundle \
      "$ldd_output" "$hashes_output" "$report_output" \
      "$RUN_DIR/runtime-bundle-initial.json" \
      >> "$check_log" 2>&1
}

seal_artifacts() {
  local seal_tmp

  (( CLEANUP_SURVIVOR == 0 )) || return 1
  seal_tmp="$(mktemp "${RUN_DIR}.artifacts.XXXXXX")" || return 1
  if ! (
    cd "$RUN_DIR"
    find . -type f ! -name artifacts.sha256 ! -name completion-status.json -print0 |
      sort -z | xargs -0 -r sha256sum
  ) > "$seal_tmp"; then
    rm -f "$seal_tmp"
    return 1
  fi
  if [[ ! -s "$seal_tmp" ]] || ! (
    cd "$RUN_DIR"
    sha256sum -c "$seal_tmp" >/dev/null
  ); then
    rm -f "$seal_tmp"
    return 1
  fi
  mv "$seal_tmp" "$RUN_DIR/artifacts.sha256" || return 1
  (
    cd "$RUN_DIR"
    sha256sum -c artifacts.sha256 >/dev/null
  )
}

on_exit() {
  original_status=$?
  local promotion_result_sha=""
  trap - EXIT INT TERM
  set +e
  server_alive_before_stop=0
  if (( SERVER_EXPECTED_RUNNING == 1 )) && \
     [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    server_state_before_stop="$(ps -o stat= -p "$SERVER_PID" 2>/dev/null | awk '{print $1}')"
    [[ "$server_state_before_stop" == Z* ]] || server_alive_before_stop=1
  fi
  cleanup
  final_status=$original_status
  if (( BODY_COMPLETED != 1 )); then
    final_status=1
  fi
  if (( SERVER_EXPECTED_RUNNING == 1 && server_alive_before_stop == 0 )); then
    final_status=1
  fi
  if command -v xpu-smi >/dev/null 2>&1; then
    timeout 20 xpu-smi stats -d "$GPU_INDEX" > "$RUN_DIR/xpu-smi-final.txt" 2>&1 || true
  fi
  journal_capture_ok=1
  if ! journalctl -k --since "@$START_EPOCH" --no-pager \
    > "$RUN_DIR/kernel-journal-since-start.txt" \
    2> "$RUN_DIR/kernel-journal-since-start.stderr.txt"; then
    journal_capture_ok=0
    final_status=1
  fi
  grep -Ei 'xe.*(reset|wedg|fault|hang|timedout|device lost)|GuC.*reset|Fault response|VM.*fault|PCIe.*AER|UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST' \
    "$RUN_DIR/kernel-journal-since-start.txt" \
    > "$RUN_DIR/device-error-scan.txt"
  device_scan_status=$?
  if (( device_scan_status > 1 )); then
    final_status=1
  fi
  server_scan_ok=1
  if [[ ! -r "$RUN_DIR/server.stdout.log" || ! -r "$RUN_DIR/server.identity.log" ]]; then
    : > "$RUN_DIR/server-error-scan.txt"
    server_scan_ok=0
    final_status=1
  else
    grep -Ei 'UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST|out of memory|segmentation fault|core dumped|Aborted' \
      "$RUN_DIR/server.stdout.log" "$RUN_DIR/server.identity.log" \
      > "$RUN_DIR/server-error-scan.txt" 2> "$RUN_DIR/server-error-scan.stderr.txt"
    server_scan_status=$?
    if (( server_scan_status > 1 )); then
      server_scan_ok=0
      final_status=1
    fi
  fi
  if (( CLEANUP_FORCED != 0 )); then
    echo "forced_kill=1" > "$RUN_DIR/cleanup-status.txt"
    final_status=1
  else
    echo "forced_kill=0" > "$RUN_DIR/cleanup-status.txt"
  fi
  if (( CLEANUP_SURVIVOR != 0 )); then
    echo "cleanup_survivor=1" >> "$RUN_DIR/cleanup-status.txt"
    final_status=1
  else
    echo "cleanup_survivor=0" >> "$RUN_DIR/cleanup-status.txt"
  fi
  echo "kernel_journal_capture_ok=$journal_capture_ok" >> "$RUN_DIR/cleanup-status.txt"
  echo "server_scan_ok=$server_scan_ok" >> "$RUN_DIR/cleanup-status.txt"
  if ss -H -ltn "sport = :$PORT" | grep -q .; then
    echo "port_closed=0" >> "$RUN_DIR/cleanup-status.txt"
    final_status=1
  else
    echo "port_closed=1" >> "$RUN_DIR/cleanup-status.txt"
  fi
  if [[ -s "$RUN_DIR/device-error-scan.txt" ]]; then
    final_status=1
  fi
  if [[ -s "$RUN_DIR/server-error-scan.txt" ]]; then
    final_status=1
  fi
  if ! verify_harness_inputs final; then
    final_status=1
  fi
  host_memory_final_ok=0
  if check_host_memory final; then
    host_memory_final_ok=1
  else
    final_status=1
  fi
  runtime_bundle_unchanged=0
  if verify_runtime_bundle_snapshot final; then
    runtime_bundle_unchanged=1
  else
    final_status=1
  fi
  model_stat_unchanged=0
  if (( MODEL_STAT_BASELINE_READY == 1 )) && verify_model_stat final; then
    model_stat_unchanged=1
  else
    final_status=1
  fi
  model_sha256_final_verified=0
  if [[ "$EVIDENCE_CLASS" == "official-isolated" ]] && \
     (( MODEL_STAT_BASELINE_READY == 1 )); then
    if printf '%s  %s\n' "$EXPECTED_SHA256" "$MODEL_FD_PATH" |
      sha256sum -c - > "$RUN_DIR/model-sha256-final.check.txt" 2>&1; then
      model_sha256_final_verified=1
    else
      final_status=1
    fi
  else
    printf 'not required or model baseline was not initialized\n' \
      > "$RUN_DIR/model-sha256-final.check.txt"
  fi
  final_used="$(awk -F '|' '/GPU Memory Used/{gsub(/[^0-9.]/, "", $3); print int($3); exit}' "$RUN_DIR/xpu-smi-final.txt" 2>/dev/null || true)"
  vram_returned=0
  if [[ -n "$final_used" && -n "$PRE_GPU_USED_MIB" ]]; then
    if (( final_used <= PRE_GPU_USED_MIB + GPU_IDLE_MAX_MIB )); then
      vram_returned=1
    fi
  fi
  if (( vram_returned == 0 )); then
    echo "vram_returned=0 pre_mib=${PRE_GPU_USED_MIB:-unknown} final_mib=${final_used:-unknown}" >> "$RUN_DIR/cleanup-status.txt"
    final_status=1
  else
    echo "vram_returned=1 pre_mib=$PRE_GPU_USED_MIB final_mib=$final_used" >> "$RUN_DIR/cleanup-status.txt"
  fi
  nonselected_final_idle=1
  if [[ "$EVIDENCE_CLASS" == "official-isolated" ]]; then
    for device in 0 1 2 3; do
      [[ "$device" == "$GPU_INDEX" ]] && continue
      if ! timeout 20 xpu-smi stats -d "$device" \
        > "$RUN_DIR/xpu-smi-final-gpu${device}.txt" 2>&1; then
        nonselected_final_idle=0
        continue
      fi
      nonselected_final_mib="$(awk -F '|' '/GPU Memory Used/{gsub(/[^0-9.]/, "", $3); print int($3); exit}' "$RUN_DIR/xpu-smi-final-gpu${device}.txt")"
      if [[ -z "$nonselected_final_mib" ]] || (( nonselected_final_mib > GPU_IDLE_MAX_MIB )); then
        nonselected_final_idle=0
      fi
    done
  fi
  if (( nonselected_final_idle == 0 )); then
    final_status=1
  fi
  echo "nonselected_final_idle=$nonselected_final_idle" >> "$RUN_DIR/cleanup-status.txt"
  echo "runtime_bundle_unchanged=$runtime_bundle_unchanged" >> "$RUN_DIR/cleanup-status.txt"
  echo "model_stat_unchanged=$model_stat_unchanged" >> "$RUN_DIR/cleanup-status.txt"
  echo "model_sha256_final_verified=$model_sha256_final_verified" >> "$RUN_DIR/cleanup-status.txt"
  echo "server_expected_running=$SERVER_EXPECTED_RUNNING" >> "$RUN_DIR/cleanup-status.txt"
  echo "server_alive_before_stop=$server_alive_before_stop" >> "$RUN_DIR/cleanup-status.txt"
  echo "host_memory_final_ok=$host_memory_final_ok" >> "$RUN_DIR/cleanup-status.txt"
  if [[ "$RUN_SCOPE" == "promotion512" ]]; then
    if [[ ! -s "$RUN_DIR/exact-tokens.json" || ! -s "$RUN_DIR/exact-result-gate.json" ]] || \
       ! jq -e '.passed == true and .checks.post_canary_passed == true' \
         "$RUN_DIR/exact-result-gate.json" >/dev/null || \
       ! jq -e '.intrinsic_gate.passed == true and .post_512_canary.passed == true' \
         "$RUN_DIR/exact-tokens.json" >/dev/null; then
      final_status=1
    else
      promotion_result_sha="$(sha256sum "$RUN_DIR/exact-tokens.json" | awk '{print $1}')"
      if [[ ! "$promotion_result_sha" =~ ^[0-9a-f]{64}$ ]]; then
        final_status=1
      fi
    fi
  fi
  if (( final_status == 0 )); then
    printf 'original_status=%s\npre_seal_status=0\ncompletion_marker_required=1\n' \
      "$original_status" > "$RUN_DIR/exit-status.txt"
    printf 'PRE_SEAL_PASS_PENDING_COMPLETION\n' > "$RUN_DIR/run-status.txt"
  else
    printf 'original_status=%s\nfinal_status=%s\n' \
      "$original_status" "$final_status" > "$RUN_DIR/exit-status.txt"
    printf 'FAIL\n' > "$RUN_DIR/run-status.txt"
  fi
  seal_ok=1
  rm -f "$RUN_DIR/artifacts.sha256" "$RUN_DIR/completion-status.json"
  if ! seal_artifacts; then
    seal_ok=0
    final_status=1
    printf 'original_status=%s\nfinal_status=%s\n' "$original_status" "$final_status" > "$RUN_DIR/exit-status.txt"
    printf 'FAIL\n' > "$RUN_DIR/run-status.txt"
    seal_artifacts || true
  fi
  if (( final_status == 0 && seal_ok == 1 )); then
    completion_tmp="$(mktemp "${RUN_DIR}.completion.XXXXXX")"
    manifest_sha="$(sha256sum "$RUN_DIR/artifacts.sha256" | awk '{print $1}')"
    run_status_sha="$(sha256sum "$RUN_DIR/run-status.txt" | awk '{print $1}')"
    exit_status_sha="$(sha256sum "$RUN_DIR/exit-status.txt" | awk '{print $1}')"
    result_sha=""
    post_canary_passed=0
    if [[ "$RUN_SCOPE" == "promotion512" ]]; then
      result_sha="$promotion_result_sha"
      if jq -e '.passed == true and .checks.post_canary_passed == true' \
        "$RUN_DIR/exact-result-gate.json" >/dev/null; then
        post_canary_passed=1
      fi
    fi
    if jq -n \
      --arg manifest_sha256 "$manifest_sha" \
      --arg run_status_sha256 "$run_status_sha" \
      --arg exit_status_sha256 "$exit_status_sha" \
      --arg evidence_class "$EVIDENCE_CLASS" \
      --arg harness_manifest_sha256 "$HARNESS_MANIFEST_SHA256" \
      --arg runtime_bundle_report_sha256 "$RUNTIME_BUNDLE_REPORT_SHA256" \
      --arg runtime_resolved_manifest_sha256 "$RUNTIME_RESOLVED_MANIFEST_SHA256" \
      --arg run_scope "$RUN_SCOPE" \
      --arg runtime_profile "$RUNTIME_PROFILE" \
      --argjson declared_q8_reorder_vdr_mmvq "$RUNTIME_DECLARED_Q8_VDR" \
      --arg runtime_manifest_sha256 "$runtime_manifest_sha256" \
      --arg runtime_profile_check_sha256 "$RUNTIME_PROFILE_CHECK_SHA256" \
      --arg promotion_profile "$PROMOTION_PROFILE" \
      --argjson promotion_expected_ubatch_size "$PROMOTION_EXPECTED_UBATCH_SIZE" \
      --arg full512_band "$FULL512_BAND" \
      --argjson gpu_index "$GPU_INDEX" \
      --arg result_sha256 "$result_sha" \
      --argjson post_512_canary_passed "$post_canary_passed" \
      --argjson performance_promotable "$PERFORMANCE_PROMOTABLE" \
      --argjson promotion_required "$([[ "$RUN_SCOPE" == "promotion512" ]] && echo 1 || echo 0)" \
      '{status:"PASS", evidence_valid:true, evidence_class:$evidence_class, performance_promotable:($performance_promotable == 1), run_scope:$run_scope, runtime_profile:$runtime_profile, declared_q8_reorder_vdr_mmvq:$declared_q8_reorder_vdr_mmvq, runtime_manifest_sha256:$runtime_manifest_sha256, runtime_profile_check:"runtime-profile-check.json", runtime_profile_check_sha256:$runtime_profile_check_sha256, promotion_profile:$promotion_profile, promotion_expected_ubatch_size:$promotion_expected_ubatch_size, full512_band:$full512_band, gpu_index:$gpu_index, result:(if $result_sha256 == "" then null else "exact-tokens.json" end), result_sha256:(if $result_sha256 == "" then null else $result_sha256 end), post_512_canary_passed:($post_512_canary_passed == 1), artifacts_manifest_verified:true, artifacts_manifest:"artifacts.sha256", artifacts_manifest_sha256:$manifest_sha256, pre_seal_run_status:"run-status.txt", pre_seal_run_status_sha256:$run_status_sha256, pre_seal_exit_status:"exit-status.txt", pre_seal_exit_status_sha256:$exit_status_sha256, harness_manifest_sha256:$harness_manifest_sha256, runtime_bundle_report_sha256:$runtime_bundle_report_sha256, runtime_resolved_manifest_sha256:$runtime_resolved_manifest_sha256}' \
      > "$completion_tmp" &&
      jq -e \
        --arg manifest_sha256 "$manifest_sha" \
        --arg run_status_sha256 "$run_status_sha" \
        --arg exit_status_sha256 "$exit_status_sha" \
        --arg evidence_class "$EVIDENCE_CLASS" \
        --arg run_scope "$RUN_SCOPE" \
        --arg runtime_profile "$RUNTIME_PROFILE" \
        --argjson declared_q8_reorder_vdr_mmvq "$RUNTIME_DECLARED_Q8_VDR" \
        --arg runtime_manifest_sha256 "$runtime_manifest_sha256" \
        --arg runtime_profile_check_sha256 "$RUNTIME_PROFILE_CHECK_SHA256" \
        --arg promotion_profile "$PROMOTION_PROFILE" \
        --argjson promotion_expected_ubatch_size "$PROMOTION_EXPECTED_UBATCH_SIZE" \
        --arg full512_band "$FULL512_BAND" \
        --argjson gpu_index "$GPU_INDEX" \
        --arg result_sha256 "$result_sha" \
        --argjson post_512_canary_passed "$post_canary_passed" \
        --arg harness_manifest_sha256 "$HARNESS_MANIFEST_SHA256" \
        --argjson performance_promotable "$PERFORMANCE_PROMOTABLE" \
        --argjson promotion_required "$([[ "$RUN_SCOPE" == "promotion512" ]] && echo 1 || echo 0)" '
          .status == "PASS"
          and .evidence_valid == true
          and .evidence_class == $evidence_class
          and .run_scope == $run_scope
          and .runtime_profile == $runtime_profile
          and .declared_q8_reorder_vdr_mmvq == $declared_q8_reorder_vdr_mmvq
          and .runtime_manifest_sha256 == $runtime_manifest_sha256
          and .runtime_profile_check == "runtime-profile-check.json"
          and .runtime_profile_check_sha256 == $runtime_profile_check_sha256
          and .promotion_profile == $promotion_profile
          and .promotion_expected_ubatch_size == $promotion_expected_ubatch_size
          and .full512_band == $full512_band
          and .gpu_index == $gpu_index
          and .result_sha256 == (if $result_sha256 == "" then null else $result_sha256 end)
          and .post_512_canary_passed == ($post_512_canary_passed == 1)
          and .performance_promotable == ($performance_promotable == 1)
          and (if $runtime_profile == "canonical-baseline" then
            true
          else
            .performance_promotable == false
          end)
          and .harness_manifest_sha256 == $harness_manifest_sha256
          and .artifacts_manifest_verified == true
          and .artifacts_manifest_sha256 == $manifest_sha256
          and .pre_seal_run_status_sha256 == $run_status_sha256
          and .pre_seal_exit_status_sha256 == $exit_status_sha256
          and (if $promotion_required == 1 then
            .result == "exact-tokens.json"
            and (.result_sha256 | type == "string" and test("^[0-9a-f]{64}$"))
            and .result_sha256 == $result_sha256
            and .post_512_canary_passed == true
          else true end)
        ' "$completion_tmp" >/dev/null &&
      [[ "$(sha256sum "$RUN_DIR/runtime-profile-check.json" | awk '{print $1}')" == "$RUNTIME_PROFILE_CHECK_SHA256" ]] &&
      [[ "$RUN_SCOPE" != "promotion512" || \
         "$(sha256sum "$RUN_DIR/exact-tokens.json" | awk '{print $1}')" == "$result_sha" ]] &&
      (cd "$RUN_DIR" && sha256sum -c artifacts.sha256 >/dev/null) &&
      mv "$completion_tmp" "$RUN_DIR/completion-status.json"; then
      :
    else
      rm -f "$completion_tmp" "$RUN_DIR/completion-status.json"
      final_status=1
      printf 'original_status=%s\nfinal_status=%s\n' "$original_status" "$final_status" > "$RUN_DIR/exit-status.txt"
      printf 'FAIL\n' > "$RUN_DIR/run-status.txt"
      rm -f "$RUN_DIR/artifacts.sha256"
      seal_artifacts || true
    fi
  fi
  exit "$final_status"
}
trap on_exit EXIT
trap 'exit 130' INT TERM

check_host_memory preflight || {
  echo "host MemAvailable is below the validation floor" >&2
  exit 1
}

capture_model_stat "$RUN_DIR/model-stat-before-initial-hash.json"
printf '%s  %s\n' "$EXPECTED_SHA256" "$MODEL_FD_PATH" | sha256sum -c - |
  tee "$RUN_DIR/model-sha256-check.txt"
capture_model_stat "$RUN_DIR/model-stat-after-initial-hash.json"
cmp -s "$RUN_DIR/model-stat-before-initial-hash.json" \
  "$RUN_DIR/model-stat-after-initial-hash.json" || {
  echo "model stat identity changed during initial SHA-256 verification" >&2
  exit 1
}
cp "$RUN_DIR/model-stat-after-initial-hash.json" "$RUN_DIR/model-stat-baseline.json"
MODEL_STAT_BASELINE_READY=1

command -v xpu-smi >/dev/null 2>&1 || { echo "xpu-smi is required" >&2; exit 2; }
xpu-smi discovery -j > "$RUN_DIR/xpu-smi-discovery.json"
xpu-smi -v > "$RUN_DIR/xpu-smi-version.txt" 2>&1 || true
uname -a > "$RUN_DIR/uname.txt"
LLAMA_SERVER="$LLAMA_SERVER" \
RUNTIME_MANIFEST="$RUNTIME_MANIFEST" \
  "$LANE/scripts/serve-target-only.sh" --verify-runtime-bundle \
    "$RUN_DIR/llama-server-ldd-initial-post-oneapi.txt" \
    "$RUN_DIR/runtime-resolved-files.sha256" \
    "$RUN_DIR/runtime-bundle-initial.json"
RUNTIME_BUNDLE_REPORT_SHA256="$(sha256sum "$RUN_DIR/runtime-bundle-initial.json" | awk '{print $1}')"
RUNTIME_RESOLVED_MANIFEST_SHA256="$(sha256sum "$RUN_DIR/runtime-resolved-files.sha256" | awk '{print $1}')"
RUNTIME_BUNDLE_READY=1
dpkg-query -W 2>/dev/null |
  grep -Ei 'intel.*(level-zero|oneapi|compute-runtime|igc)|xpu-smi|libze' \
    > "$RUN_DIR/accelerator-packages.txt" || true
jq -e --argjson device "$GPU_INDEX" '
  ([.device_list[] |
    select(.device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70"))) |
    {device_id, pci_bdf_address, uuid}] | length) == 4
  and ([.device_list[] |
    select(.device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70"))) |
    .device_id] | sort) == [0, 1, 2, 3]
  and ([.device_list[] |
    select(.device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70"))) |
    .pci_bdf_address] | unique | length) == 4
  and ([.device_list[] |
    select(.device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70"))) |
    .uuid] | unique | length) == 4
  and ([.device_list[] |
    select(.device_id == $device and .device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70")))] | length) == 1
' "$RUN_DIR/xpu-smi-discovery.json" >/dev/null
jq --argjson device "$GPU_INDEX" -r '
  .device_list[] | select(.device_id == $device) | "gpu_bdf=" + .pci_bdf_address + "\ngpu_uuid=" + .uuid + "\ngpu_name=" + .device_name
' "$RUN_DIR/xpu-smi-discovery.json" > "$RUN_DIR/gpu-identity.env"
GPU_BDF="$(awk -F= '$1 == "gpu_bdf" {print $2}' "$RUN_DIR/gpu-identity.env")"
if [[ -z "$GPU_BDF" || ! -e "/sys/bus/pci/devices/$GPU_BDF" ]]; then
  echo "selected GPU sysfs identity is missing: ${GPU_BDF:-unknown}" >&2
  exit 2
fi
readlink -f "/sys/bus/pci/devices/$GPU_BDF/driver" \
  > "$RUN_DIR/gpu-driver-sysfs-path.txt"
modinfo xe > "$RUN_DIR/xe-modinfo.txt" 2>&1 || true

for device in 0 1 2 3; do
  timeout 20 xpu-smi stats -d "$device" > "$RUN_DIR/xpu-smi-before-gpu${device}.txt"
  used="$(awk -F '|' '/GPU Memory Used/{gsub(/[^0-9.]/, "", $3); print int($3); exit}' "$RUN_DIR/xpu-smi-before-gpu${device}.txt")"
  if [[ -z "$used" ]]; then
    echo "could not parse GPU memory for device $device" >&2
    exit 2
  fi
  if [[ "$device" == "$GPU_INDEX" ]]; then
    PRE_GPU_USED_MIB="$used"
  fi
  if [[ "$device" == "$GPU_INDEX" || "$REQUIRE_ALL_GPUS_IDLE" == "1" ]]; then
    if (( used > GPU_IDLE_MAX_MIB )); then
      echo "GPU $device is not idle: ${used} MiB used" >&2
      exit 2
    fi
  fi
done

{
  echo "date_utc=$STAMP"
  echo "label=$LABEL"
  echo "run_scope=$RUN_SCOPE"
  echo "runtime_profile=$RUNTIME_PROFILE"
  echo "runtime_profile_diagnostic=$RUNTIME_PROFILE_DIAGNOSTIC"
  echo "declared_q8_reorder_vdr_mmvq=$RUNTIME_DECLARED_Q8_VDR"
  echo "runtime_profile_expected_manifest=$RUNTIME_PROFILE_EXPECTED_MANIFEST"
  echo "runtime_profile_expected_manifest_sha256=$RUNTIME_PROFILE_EXPECTED_MANIFEST_SHA256"
  echo "runtime_profile_check_sha256=$RUNTIME_PROFILE_CHECK_SHA256"
  echo "promotion_profile=$PROMOTION_PROFILE"
  echo "promotion_expected_ubatch_size=$PROMOTION_EXPECTED_UBATCH_SIZE"
  echo "evidence_class=$EVIDENCE_CLASS"
  echo "performance_promotable=$PERFORMANCE_PROMOTABLE"
  echo "gpu_index=$GPU_INDEX"
  echo "port=$PORT"
  echo "model=$MODEL"
  echo "model_pinned_fd=$QWEN36_MODEL_FD"
  echo "model_pinned_path=$(readlink -f "$MODEL_FD_PATH")"
  echo "model_bytes=$ACTUAL_SIZE"
  echo "expected_model_sha256=$EXPECTED_SHA256"
  echo "model_sha256_verified=$VERIFY_MODEL_SHA256"
  echo "model_alias=$MODEL_ALIAS"
  echo "llama_server=$LLAMA_SERVER"
  echo "llama_server_sha256=$EXPECTED_RUNTIME_SHA256"
  echo "runtime_manifest=$RUNTIME_MANIFEST"
  echo "runtime_manifest_sha256=$(sha256sum "$RUNTIME_MANIFEST" | awk '{print $1}')"
  echo "runtime_bundle_report_sha256=$RUNTIME_BUNDLE_REPORT_SHA256"
  echo "runtime_resolved_files_manifest_sha256=$RUNTIME_RESOLVED_MANIFEST_SHA256"
  echo "runtime_bundle_dependency_count=$(jq -r '.dependency_count' "$RUN_DIR/runtime-bundle-initial.json")"
  echo "runtime_bundle_origin_shared_object_count=$(jq -r '.origin_shared_object_count' "$RUN_DIR/runtime-bundle-initial.json")"
  echo "ctx_size=$CTX_SIZE"
  echo "full512_band=$FULL512_BAND"
  echo "parallel_slots=$PARALLEL_SLOTS"
  echo "ctx_size_per_slot=$CTX_SIZE"
  echo "kv_unified=$KV_UNIFIED"
  echo "cont_batching=$CONT_BATCHING"
  echo "batch_size=$BATCH_SIZE"
  echo "ubatch_size=$UBATCH_SIZE"
  echo "n_gpu_layers=$N_GPU_LAYERS"
  echo "threads=$THREADS"
  echo "poll=$POLL"
  echo "cache_type_k=$CACHE_TYPE_K"
  echo "cache_type_v=$CACHE_TYPE_V"
  echo "flash_attn=$FLASH_ATTN"
  echo "log_verbosity=$LOG_VERBOSITY"
  echo "sycl_dnn_enabled=$LANE_DNN_ENABLED"
  echo "sycl_opt_enabled=$LANE_OPT_ENABLED"
  echo "sycl_fa_onednn=$LANE_FA_ONEDNN"
  echo "sycl_fa_onednn_max_kv=$LANE_FA_ONEDNN_MAX_KV"
  echo "sycl_mkl_fa=$LANE_MKL_FA"
  echo "sycl_flash_attn=$LANE_SYCL_FLASH_ATTN"
  echo "http_threads=$HTTP_THREADS"
  echo "sycl_vmm_enabled=1"
  echo "sycl_graph_enabled=0"
  echo "speculation=none"
  echo "vision_projector=none"
  echo "case_id=${CASE_ID:-<scope-default>}"
  echo "oracle_json=${ORACLE_JSON:-<baseline-capture>}"
  echo "oracle_json_source=${ORACLE_JSON_SOURCE:-<baseline-capture>}"
  echo "oracle_json_sha256=${ORACLE_JSON_SHA256:-<none>}"
  echo "prefix_oracle_json=${PREFIX_ORACLE_JSON:-<none>}"
  echo "prefix_oracle_json_source=${PREFIX_ORACLE_JSON_SOURCE:-<none>}"
  echo "sealed_post_512_canary_oracle=$SEALED_128_ORACLE"
  echo "sealed_post_512_canary_oracle_sha256=$SEALED_128_ORACLE_SHA256"
  echo "sealed_post_512_canary_prompt_id=$SEALED_128_CANARY_PROMPT_ID"
  echo "require_all_gpus_idle=$REQUIRE_ALL_GPUS_IDLE"
  echo "gpu_idle_max_mib=$GPU_IDLE_MAX_MIB"
  echo "min_host_available_kib=$MIN_HOST_AVAILABLE_KIB"
  echo "min_loaded_delta_mib=$MIN_LOADED_DELTA_MIB"
  echo "max_loaded_used_mib=$MAX_LOADED_USED_MIB"
  echo "gpu_lease_path=$GPU_LEASE_PATH"
  echo "port_lease_path=$PORT_LEASE_PATH"
  cat "$RUN_DIR/gpu-identity.env"
} > "$RUN_DIR/run-identity.env"

harness_inputs=(
  "$MANIFEST"
  "$RUNTIME_MANIFEST"
  "$LANE/scripts/serve-target-only.sh"
  "$LANE/scripts/capture-exact-tokens.py"
  "$LANE/scripts/run-validation.sh"
  "$LANE/c2-long-context-suite-v1.json"
  "$ROOT/scripts/bench-openai-long-context-suite.py"
  "$SEALED_128_SUITE"
)
if [[ "$RUN_SCOPE" == "promotion512" ]]; then
  harness_inputs+=("$SEALED_128_ORACLE" "$SEALED_128_ORACLE_SNAPSHOT")
fi
if [[ "$RUN_SCOPE" == "long" || "$RUN_SCOPE" == "full" ]]; then
  harness_inputs+=(
    "$LANE/long-context-suite-v1.json"
    "$LANE/scripts/validate-long-context-result.py"
  )
fi
if [[ -n "$ORACLE_JSON" ]]; then
  harness_inputs+=("$ORACLE_JSON")
fi
if [[ -n "$ORACLE_JSON_SOURCE" ]]; then
  harness_inputs+=("$ORACLE_JSON_SOURCE")
fi
if [[ -n "$PREFIX_ORACLE_JSON" ]]; then
  harness_inputs+=("$PREFIX_ORACLE_JSON")
fi
if [[ -n "$PREFIX_ORACLE_JSON_SOURCE" ]]; then
  harness_inputs+=("$PREFIX_ORACLE_JSON_SOURCE")
fi
printf '%s\n' "${harness_inputs[@]}" | sort -u > "$RUN_DIR/harness-input-paths.txt"
while IFS= read -r harness_path; do
  sha256sum "$harness_path"
done < "$RUN_DIR/harness-input-paths.txt" > "$RUN_DIR/harness-inputs.sha256"
HARNESS_MANIFEST_SHA256="$(sha256sum "$RUN_DIR/harness-inputs.sha256" | awk '{print $1}')"
verify_harness_inputs initial || {
  echo "initial harness input verification failed" >&2
  exit 1
}

verify_runtime_bundle_snapshot pre-launch || {
  echo "runtime bundle changed before server launch" >&2
  exit 1
}
verify_model_stat pre-launch || {
  echo "model stat identity changed before server launch" >&2
  exit 1
}

GPU_INDEX="$GPU_INDEX" \
PORT="$PORT" \
MODEL="$MODEL" \
MODEL_ALIAS="$MODEL_ALIAS" \
LLAMA_SERVER="$LLAMA_SERVER" \
RUNTIME_MANIFEST="$RUNTIME_MANIFEST" \
CTX_SIZE="$CTX_SIZE" \
PARALLEL_SLOTS="$PARALLEL_SLOTS" \
KV_UNIFIED="$KV_UNIFIED" \
CONT_BATCHING="$CONT_BATCHING" \
BATCH_SIZE="$BATCH_SIZE" \
UBATCH_SIZE="$UBATCH_SIZE" \
N_GPU_LAYERS="$N_GPU_LAYERS" \
THREADS="$THREADS" \
POLL="$POLL" \
CACHE_TYPE_K="$CACHE_TYPE_K" \
CACHE_TYPE_V="$CACHE_TYPE_V" \
FLASH_ATTN="$FLASH_ATTN" \
LOG_VERBOSITY="$LOG_VERBOSITY" \
LANE_DNN_ENABLED="$LANE_DNN_ENABLED" \
LANE_OPT_ENABLED="$LANE_OPT_ENABLED" \
LANE_FA_ONEDNN="$LANE_FA_ONEDNN" \
LANE_FA_ONEDNN_MAX_KV="$LANE_FA_ONEDNN_MAX_KV" \
LANE_MKL_FA="$LANE_MKL_FA" \
LANE_SYCL_FLASH_ATTN="$LANE_SYCL_FLASH_ATTN" \
HTTP_THREADS="$HTTP_THREADS" \
LOG="$RUN_DIR/server.identity.log" \
SERVER_OUTPUT_LOG="$RUN_DIR/server.stdout.log" \
OUT_DIR="$RUN_DIR" \
  "$LANE/scripts/serve-target-only.sh" > "$RUN_DIR/server.stdout.log" 2>&1 &
SERVER_PID=$!
printf '%s\n' "$SERVER_PID" > "$RUN_DIR/server.pid"

deadline=$((SECONDS + READINESS_TIMEOUT_S))
until curl -fsS "http://127.0.0.1:${PORT}/v1/models" > "$RUN_DIR/models.json" 2> "$RUN_DIR/models.err"; do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "server exited before readiness; see $RUN_DIR/server.stdout.log" >&2
    exit 1
  fi
  if (( SECONDS >= deadline )); then
    echo "timed out waiting for port $PORT" >&2
    exit 1
  fi
  sleep 2
done
SERVER_EXPECTED_RUNNING=1

python3 - "$RUN_DIR/server.stdout.log" "$RUN_DIR/full-offload-check.json" <<'PY'
import json
import re
import sys

log_path, out_path = sys.argv[1:]
text = open(log_path, errors="replace").read()
pairs = [(int(a), int(b)) for a, b in re.findall(r"offloaded (\d+)/(\d+) layers to GPU", text)]
valid = [(a, b) for a, b in pairs if a == b and b >= 65]
result = {"all_pairs": pairs, "full_target_offload_pairs": valid, "passed": bool(valid)}
open(out_path, "w").write(json.dumps(result, indent=2) + "\n")
if not valid:
    raise SystemExit("no full target offload >=65 layers found")
PY

python3 - "$RUN_DIR/server.stdout.log" "$RUN_DIR/server.identity.log" "$RUN_DIR/server-config-check.json" \
  "$CTX_SIZE" "$PARALLEL_SLOTS" \
  "$KV_UNIFIED" "$RUN_SCOPE" "$RUNTIME_PROFILE" "$RUNTIME_DECLARED_Q8_VDR" \
  "$resolved_runtime_manifest" "$runtime_manifest_sha256" "$LLAMA_SERVER" \
  "$EXPECTED_RUNTIME_SHA256" "$PROMOTION_EXPECTED_UBATCH_SIZE" <<'PY'
import json
import os
import re
import sys

(
    log_path,
    identity_path,
    out_path,
    ctx_raw,
    slots_raw,
    kv_raw,
    run_scope,
    runtime_profile,
    declared_q8_vdr_raw,
    expected_runtime_manifest,
    expected_runtime_manifest_sha256,
    expected_llama_server,
    expected_llama_server_sha256,
    promotion_expected_ubatch_raw,
) = sys.argv[1:]
text = open(log_path, errors="replace").read()
identity_text = open(identity_path, errors="replace").read()
expected_ctx = int(ctx_raw)
expected_slots = int(slots_raw)
expected_ctx_seq = expected_ctx // expected_slots
expected_kv = "true" if int(kv_raw) else "false"
promotion_expected_ubatch = int(promotion_expected_ubatch_raw)
declared_q8_vdr = int(declared_q8_vdr_raw)

identity = {}
for line in identity_text.split("--- server ---", 1)[0].splitlines():
    if "=" in line:
        key, value = line.split("=", 1)
        identity[key] = value

runtime_identity_fields = {
    "runtime_manifest": os.path.realpath(identity.get("runtime_manifest", ""))
    == os.path.realpath(expected_runtime_manifest),
    "runtime_manifest_sha256": identity.get("runtime_manifest_sha256")
    == expected_runtime_manifest_sha256,
    "llama_server": os.path.realpath(identity.get("llama_server", ""))
    == os.path.realpath(expected_llama_server),
    "llama_server_sha256": identity.get("llama_server_sha256")
    == expected_llama_server_sha256,
    "runtime_bundle_verified": identity.get("runtime_bundle_verified") == "1",
}

def last_int(label: str) -> int | None:
    values = re.findall(rf"{re.escape(label)}\s*=\s*(\d+)", text)
    return int(values[-1]) if values else None

result = {
    "expected": {
        "n_seq_max": expected_slots,
        "n_ctx": expected_ctx,
        "n_ctx_seq": expected_ctx_seq,
        "n_slots": expected_slots,
        "n_ctx_slot": expected_ctx_seq,
        "kv_unified": expected_kv,
    },
    "observed": {
        "n_seq_max": last_int("n_seq_max"),
        "n_ctx": last_int("n_ctx"),
        "n_ctx_seq": last_int("n_ctx_seq"),
    },
}
slot_matches = re.findall(
    r"initializing, n_slots = (\d+), n_ctx_slot = (\d+), kv_unified = '([^']+)'",
    text,
)
result["observed"]["slot_config"] = slot_matches[-1] if slot_matches else None
result["runtime_profile"] = {
    "runtime_profile": runtime_profile,
    "declared_q8_reorder_vdr_mmvq": declared_q8_vdr,
    "expected_runtime_manifest": os.path.realpath(expected_runtime_manifest),
    "expected_runtime_manifest_sha256": expected_runtime_manifest_sha256,
    "expected_llama_server": os.path.realpath(expected_llama_server),
    "expected_llama_server_sha256": expected_llama_server_sha256,
    "server_identity_fields": runtime_identity_fields,
}
base_passed = (
    result["observed"]["n_seq_max"] == expected_slots
    and result["observed"]["n_ctx"] == expected_ctx
    and result["observed"]["n_ctx_seq"] == expected_ctx_seq
    and bool(slot_matches)
    and slot_matches[-1] == (str(expected_slots), str(expected_ctx_seq), expected_kv)
    and all(runtime_identity_fields.values())
)
result["base_passed"] = base_passed
promotion_passed = True
if run_scope == "promotion512":
    expected_identity = {
        "ctx_size": "32768",
        "parallel_slots": "1",
        "ctx_size_per_slot": "32768",
        "kv_unified": "0",
        "cont_batching": "1",
        "batch_size": "1024",
        "ubatch_size": str(promotion_expected_ubatch),
        "n_gpu_layers": "99",
        "threads": "8",
        "http_threads": "6",
        "flash_attn": "on",
        "cache_type_k": "f16",
        "cache_type_v": "f16",
        "speculation": "none",
        "reasoning": "off",
        "GGML_SYCL_ENABLE_VMM": "1",
        "GGML_SYCL_ENABLE_GRAPH": "0",
        "GGML_SYCL_ENABLE_DNN": "0",
        "GGML_SYCL_ENABLE_OPT": "1",
        "GGML_SYCL_FA_ONEDNN": "1",
        "GGML_SYCL_FA_ONEDNN_MAX_KV": "0",
        "GGML_SYCL_ENABLE_MKL_FA": "1",
        "GGML_SYCL_ENABLE_FLASH_ATTN": "1",
    }
    identity_fields = {
        key: identity.get(key) == value for key, value in expected_identity.items()
    }
    model_fd = identity.get("model_pinned_fd", "")
    identity_fields["pinned_model_fd_contract"] = (
        model_fd.isdigit()
        and identity.get("model_load_path") == f"/proc/self/fd/{model_fd}"
        and str(identity.get("model_pinned_path", "")).startswith("/")
    )
    argv = identity.get("argv", "")
    required_argv = (
        "-ngl 99", "-c 32768", "-np 1", "-b 1024",
        f"-ub {promotion_expected_ubatch}",
        "--threads-http 6", "-ctk f16", "-ctv f16", "-fa on",
        "--spec-type none", "--reasoning off", "--ctx-checkpoints 0",
        "--cache-ram 0", "--no-cache-idle-slots", "--no-context-shift",
        "--no-kv-unified", "--cont-batching", "--slots", "--metrics",
        "--jinja",
    )
    argv_fields = {value: value in argv for value in required_argv}
    kv_matches = re.findall(
        r"llama_kv_cache: size =\s*([0-9.]+) MiB \(\s*(\d+) cells,\s*(\d+) layers,\s*(\d+)/(\d+) seqs\), K \(([^)]+)\):\s*([0-9.]+) MiB, V \(([^)]+)\):\s*([0-9.]+) MiB",
        text,
    )
    rs_matches = re.findall(
        r"llama_memory_recurrent: size =\s*([0-9.]+) MiB \(\s*(\d+) cells,\s*(\d+) layers,\s*(\d+) seqs",
        text,
    )
    fit_matches = [
        (int(free), int(required))
        for free, required in re.findall(
            r"will leave\s+(\d+)\s+>=\s+(\d+) MiB of free device memory", text
        )
    ]
    kv = kv_matches[-1] if kv_matches else None
    rs = rs_matches[-1] if rs_matches else None
    fit_free_mib = fit_matches[-1][0] if fit_matches else None
    runtime_fields = {
        "f16_kv_2048_mib": bool(kv)
        and abs(float(kv[0]) - 2048.0) <= 0.1
        and kv[1:5] == ("32768", "16", "1", "1")
        and kv[5] == "f16"
        and abs(float(kv[6]) - 1024.0) <= 0.1
        and kv[7] == "f16"
        and abs(float(kv[8]) - 1024.0) <= 0.1,
        "one_slot_recurrent_state": bool(rs)
        and 149.0 <= float(rs[0]) <= 150.5
        and rs[1:] == ("1", "64", "1"),
        "post_fit_free_at_least_1024": isinstance(fit_free_mib, int)
        and fit_free_mib >= 1024,
        "prompt_cache_disabled": "prompt cache is disabled" in text,
        "context_checkpoints_disabled": "context checkpoints disabled" in text,
        "speculation_disabled": "no implementations specified for speculative decoding" in text,
    }
    result["promotion"] = {
        "expected_identity": expected_identity,
        "identity_fields": identity_fields,
        "argv_fields": argv_fields,
        "runtime_fields": runtime_fields,
        "observed_kv": kv,
        "observed_recurrent": rs,
        "fit_free_mib": fit_free_mib,
    }
    promotion_passed = (
        all(identity_fields.values())
        and all(argv_fields.values())
        and all(runtime_fields.values())
    )
result["promotion_passed"] = promotion_passed
result["passed"] = base_passed and promotion_passed
open(out_path, "w").write(json.dumps(result, indent=2) + "\n")
if not result["passed"]:
    raise SystemExit("server context/slot identity mismatch")
PY

if [[ "$RUN_SCOPE" == "promotion512" ]]; then
  selected_loaded_mib=""
  for device in 0 1 2 3; do
    if [[ "$device" != "$GPU_INDEX" && "$EVIDENCE_CLASS" != "official-isolated" ]]; then
      continue
    fi
    timeout 20 xpu-smi stats -d "$device" \
      > "$RUN_DIR/xpu-smi-loaded-gpu${device}.txt"
    loaded_mib="$(awk -F '|' '/GPU Memory Used/{gsub(/[^0-9.]/, "", $3); print int($3); exit}' "$RUN_DIR/xpu-smi-loaded-gpu${device}.txt")"
    [[ -n "$loaded_mib" ]] || {
      echo "could not parse loaded VRAM for GPU $device" >&2
      exit 1
    }
    if [[ "$device" == "$GPU_INDEX" ]]; then
      selected_loaded_mib="$loaded_mib"
    elif (( loaded_mib > GPU_IDLE_MAX_MIB )); then
      echo "nonselected GPU $device became active during isolated validation" >&2
      exit 1
    fi
  done
  [[ -n "$selected_loaded_mib" && -n "$PRE_GPU_USED_MIB" ]] || {
    echo "selected-GPU residency evidence is missing" >&2
    exit 1
  }
  selected_loaded_delta_mib=$((selected_loaded_mib - PRE_GPU_USED_MIB))
  {
    echo "gpu_index=$GPU_INDEX"
    echo "pre_mib=$PRE_GPU_USED_MIB"
    echo "loaded_mib=$selected_loaded_mib"
    echo "loaded_delta_mib=$selected_loaded_delta_mib"
    echo "required_delta_mib=$MIN_LOADED_DELTA_MIB"
    echo "maximum_loaded_mib=$MAX_LOADED_USED_MIB"
    echo "nonselected_idle_required=$([[ "$EVIDENCE_CLASS" == "official-isolated" ]] && echo 1 || echo 0)"
  } > "$RUN_DIR/loaded-residency.env"
  if (( selected_loaded_delta_mib < MIN_LOADED_DELTA_MIB ||
        selected_loaded_mib > MAX_LOADED_USED_MIB )); then
    echo "selected GPU does not meet the locked loaded-residency range" >&2
    exit 1
  fi
else
  timeout 20 xpu-smi stats -d "$GPU_INDEX" > "$RUN_DIR/xpu-smi-loaded-gpu${GPU_INDEX}.txt"
fi

check_host_memory loaded || {
  echo "host MemAvailable fell below the validation floor after model load" >&2
  exit 1
}

verify_harness_inputs pre-capture || {
  echo "harness inputs changed before capture" >&2
  exit 1
}
verify_runtime_bundle_snapshot pre-capture || {
  echo "runtime bundle changed before capture" >&2
  exit 1
}
verify_model_stat pre-capture || {
  echo "model stat identity changed before capture" >&2
  exit 1
}

if [[ "$RUN_SCOPE" == "smoke" || "$RUN_SCOPE" == "short" || "$RUN_SCOPE" == "full" || "$RUN_SCOPE" == "promotion512" ]]; then
  exact_max_tokens=128
  exact_suite="$ROOT/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json"
  exact_context_args=()
  if [[ "$RUN_SCOPE" == "promotion512" ]]; then
    exact_max_tokens=512
    if [[ "$FULL512_BAND" != "realistic" ]]; then
      exact_suite="$LANE/c2-long-context-suite-v1.json"
      exact_context_args=(
        --prompt-builder "$ROOT/scripts/bench-openai-long-context-suite.py"
        --band "$FULL512_BAND"
      )
    fi
  fi
  exact_args=(
    python3 "$LANE/scripts/capture-exact-tokens.py"
    --base-url "http://127.0.0.1:${PORT}"
    --suite "$exact_suite"
    "${exact_context_args[@]}"
    --max-tokens "$exact_max_tokens"
    --model-sha256 "$EXPECTED_SHA256"
    --runtime-sha256 "$EXPECTED_RUNTIME_SHA256"
    --cache-type-k "$CACHE_TYPE_K"
    --cache-type-v "$CACHE_TYPE_V"
    --ctx-size "$CTX_SIZE"
    --sycl-dnn-enabled "$LANE_DNN_ENABLED"
    --sycl-opt-enabled "$LANE_OPT_ENABLED"
    --out "$RUN_DIR/exact-tokens.json"
  )
  if [[ "$RUN_SCOPE" == "smoke" ]]; then
    exact_args+=(--max-prompts 1)
  fi
  if [[ "$RUN_SCOPE" == "promotion512" ]]; then
    exact_args+=(
      --ignore-eos
      --slot-id 0
      --require-exact-token-count
      --require-full-512-metric
      --require-post-512-canary
      --post-512-canary-suite "$SEALED_128_SUITE"
      --post-512-canary-oracle "$SEALED_128_ORACLE_SNAPSHOT"
      --post-512-canary-oracle-sha256 "$SEALED_128_ORACLE_SHA256"
      --post-512-canary-prompt-id "$SEALED_128_CANARY_PROMPT_ID"
    )
  fi
  if [[ -n "$ORACLE_JSON" ]]; then
    exact_args+=(--oracle-json "$ORACLE_JSON")
  fi
  if [[ -n "$PREFIX_ORACLE_JSON" ]]; then
    exact_args+=(--prefix-oracle-json "$PREFIX_ORACLE_JSON")
  fi
  "${exact_args[@]}" > "$RUN_DIR/exact-tokens.stdout.log" 2>&1
  if [[ "$RUN_SCOPE" == "promotion512" ]]; then
    python3 - \
      "$RUN_DIR/exact-tokens.json" "$RUN_DIR/exact-result-gate.json" \
      "$FULL512_BAND" "$([[ -n "$ORACLE_JSON" ]] && echo 1 || echo 0)" \
      "$SEALED_128_ORACLE_SNAPSHOT" "$SEALED_128_ORACLE_SHA256" <<'PY'
import json
import sys

result_path, out_path, band, has_oracle_raw, canary_oracle_path, canary_sha = sys.argv[1:]
data = json.load(open(result_path))
identity = data.get("run_identity") or {}
rows = data.get("rows") or []
intrinsic = data.get("intrinsic_gate") or {}
canary = data.get("post_512_canary") or {}
oracle = data.get("oracle_comparison") or {}
prefix = data.get("prefix_oracle_comparison")
has_oracle = has_oracle_raw == "1"
expected_rows = 12 if band == "realistic" else 2
checks = {
    "intrinsic_passed": intrinsic.get("passed") is True,
    "row_count": len(rows) == expected_rows,
    "max_tokens_512": identity.get("max_tokens") == 512,
    "ignore_eos": identity.get("ignore_eos") is True,
    "exact_count_required": identity.get("require_exact_token_count") is True,
    "full_512_required": identity.get("require_full_512_metric") is True,
    "post_canary_required": identity.get("require_post_512_canary") is True,
    "slot_zero": identity.get("slot_id") == 0,
    "band_matches": identity.get("band") == (None if band == "realistic" else band),
    "all_rows_512": all(row.get("token_count") == 512 for row in rows),
    "all_full_511_intervals": all(
        (row.get("full_512_metric") or {}).get("interval_count") == 511
        for row in rows
    ),
    "post_canary_passed": canary.get("passed") is True,
    "post_canary_snapshot_identity": (
        identity.get("post_512_canary_oracle_path") == canary_oracle_path
        and canary.get("oracle_path") == canary_oracle_path
        and identity.get("post_512_canary_oracle_sha256") == canary_sha
        and canary.get("oracle_sha256") == canary_sha
    ),
    "oracle_status": oracle.get("status") == (
        "PASS_ORACLE_EXACT" if has_oracle else "BASELINE_CAPTURE_READY"
    ),
    "prefix_status": (
        isinstance(prefix, dict)
        and prefix.get("passed") is True
        and prefix.get("status") == "PASS_PREFIX_ORACLE_EXACT"
        if band == "realistic"
        else prefix is None
    ),
}
gate = {"checks": checks, "passed": all(checks.values())}
open(out_path, "w").write(json.dumps(gate, indent=2, sort_keys=True) + "\n")
if not gate["passed"]:
    raise SystemExit("promotion512 exact-result gate failed")
PY
  fi
fi

if [[ "$RUN_SCOPE" == "long" || "$RUN_SCOPE" == "full" ]]; then
  long_args=(
    python3 "$ROOT/scripts/bench-openai-long-context-suite.py"
    --base-url "http://127.0.0.1:${PORT}"
    --model "$MODEL_ALIAS"
    --suite "$LANE/long-context-suite-v1.json"
    --max-tokens 128
    --request-extra-json '{"cache_prompt":false}'
    --out "$RUN_DIR/long-context-suite.json"
  )
  if [[ -n "$CASE_ID" ]]; then
    long_args+=(--case-id "$CASE_ID")
  fi
  "${long_args[@]}" > "$RUN_DIR/long-context-suite.stdout.log" 2>&1
  python3 "$LANE/scripts/validate-long-context-result.py" \
    --suite "$LANE/long-context-suite-v1.json" \
    --result "$RUN_DIR/long-context-suite.json" \
    --ctx-size "$CTX_SIZE" \
    --max-tokens 128 \
    --out "$RUN_DIR/long-context-validation.json"
fi

BODY_COMPLETED=1
echo "$RUN_DIR"

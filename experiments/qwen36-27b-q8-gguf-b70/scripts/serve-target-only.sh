#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
MANIFEST="$ROOT/experiments/qwen36-27b-q8-gguf-b70/model-manifest.json"
RUNTIME_MANIFEST="${RUNTIME_MANIFEST:-$ROOT/experiments/qwen36-27b-q8-gguf-b70/runtime-manifest.json}"

GPU_INDEX="${GPU_INDEX:-0}"
PORT="${PORT:-19460}"
HOST="${HOST:-127.0.0.1}"
MODEL="${MODEL:-/mnt/usb-models/models/qwen36-27b-q8-gguf/Qwen3.6-27B-Q8_0.gguf}"
MODEL_ALIAS="${MODEL_ALIAS:-qwen36-27b-q8_0-target-only}"
LLAMA_SERVER="${LLAMA_SERVER:-/dev/shm/llama.cpp-pr19-15586/build-sycl/bin/llama-server}"
CTX_SIZE="${CTX_SIZE:-32768}"
PARALLEL_SLOTS="${PARALLEL_SLOTS:-1}"
KV_UNIFIED="${KV_UNIFIED:-0}"
CONT_BATCHING="${CONT_BATCHING:-1}"
BATCH_SIZE="${BATCH_SIZE:-1024}"
UBATCH_SIZE="${UBATCH_SIZE:-128}"
N_GPU_LAYERS="${N_GPU_LAYERS:-99}"
THREADS="${THREADS:-8}"
HTTP_THREADS="${HTTP_THREADS:-6}"
POLL="${POLL:-50}"
LOG_VERBOSITY="${LOG_VERBOSITY:-4}"
LANE_DNN_ENABLED="${LANE_DNN_ENABLED:-0}"
LANE_OPT_ENABLED="${LANE_OPT_ENABLED:-1}"
LANE_FA_ONEDNN="${LANE_FA_ONEDNN:-1}"
LANE_FA_ONEDNN_MAX_KV="${LANE_FA_ONEDNN_MAX_KV:-0}"
LANE_MKL_FA="${LANE_MKL_FA:-1}"
LANE_SYCL_FLASH_ATTN="${LANE_SYCL_FLASH_ATTN:-1}"
FLASH_ATTN="${FLASH_ATTN:-on}"
CACHE_TYPE_K="${CACHE_TYPE_K:-f16}"
CACHE_TYPE_V="${CACHE_TYPE_V:-f16}"
OUT_DIR="${OUT_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/servers}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="${LOG:-$OUT_DIR/target-only-gpu${GPU_INDEX}-port${PORT}-${STAMP}.log}"
SERVER_OUTPUT_LOG="${SERVER_OUTPUT_LOG:-$LOG}"

source_oneapi() {
  if [[ ! -f /opt/intel/oneapi/setvars.sh ]]; then
    echo "oneAPI environment script is missing" >&2
    return 1
  fi
  set +u
  # shellcheck disable=SC1091
  source /opt/intel/oneapi/setvars.sh --force >/dev/null
  set -u
}

verify_runtime_bundle() {
  local ldd_output="$1"
  local hashes_output="$2"
  local report_output="$3"
  local reference_report="${4:-}"
  local manifest_runtime_sha256
  local actual_runtime_sha256

  manifest_runtime_sha256="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["llama_server_sha256"])' "$RUNTIME_MANIFEST")" || return 1
  actual_runtime_sha256="$(sha256sum "$LLAMA_SERVER" | awk '{print $1}')" || return 1
  if [[ ! "$manifest_runtime_sha256" =~ ^[0-9a-f]{64}$ ]] || \
     [[ "$actual_runtime_sha256" != "$manifest_runtime_sha256" ]]; then
    echo "llama-server SHA-256 does not match the runtime manifest" >&2
    return 1
  fi

  if ! LC_ALL=C ldd "$LLAMA_SERVER" > "$ldd_output" 2>&1; then
    echo "ldd failed for llama-server; retained output: $ldd_output" >&2
    return 1
  fi
  python3 - \
    "$RUNTIME_MANIFEST" "$LLAMA_SERVER" "$ldd_output" \
    "$hashes_output" "$report_output" "$reference_report" <<'PY'
import hashlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath

manifest_path, binary_raw, ldd_path, hashes_path, report_path, reference_path = sys.argv[1:]
sha_re = re.compile(r"[0-9a-f]{64}")


def fail(message):
    raise SystemExit(f"runtime bundle verification failed: {message}")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def expand_origin(value, origin, field):
    if not isinstance(value, str) or not value.startswith("$ORIGIN/"):
        fail(f"{field} must start with $ORIGIN/")
    relative = value[len("$ORIGIN/"):]
    parsed = PurePosixPath(relative)
    if not relative or parsed.is_absolute() or ".." in parsed.parts:
        fail(f"unsafe {field}: {value!r}")
    return os.path.normpath(os.path.join(origin, relative))


try:
    manifest = json.loads(Path(manifest_path).read_text())
except (OSError, json.JSONDecodeError) as exc:
    fail(f"cannot read runtime manifest: {exc}")

if manifest.get("runtime_bundle_schema_version") != 1:
    fail("runtime_bundle_schema_version must be 1")
objects = manifest.get("origin_shared_objects")
if not isinstance(objects, list) or not objects:
    fail("origin_shared_objects must be a nonempty array")

binary = os.path.abspath(binary_raw)
manifest_binary = manifest.get("llama_server_path")
if not isinstance(manifest_binary, str) or os.path.abspath(manifest_binary) != binary:
    fail(f"llama_server_path does not match LLAMA_SERVER: {manifest_binary!r} != {binary!r}")
if not os.path.isfile(binary):
    fail(f"llama-server is not a regular file: {binary}")
binary_resolved = os.path.realpath(binary)
binary_sha = sha256(binary_resolved)
expected_binary_sha = manifest.get("llama_server_sha256")
if not isinstance(expected_binary_sha, str) or not sha_re.fullmatch(expected_binary_sha):
    fail("llama_server_sha256 is missing or malformed")
if binary_sha != expected_binary_sha:
    fail("llama-server SHA-256 does not match the runtime manifest")

ldd_text = Path(ldd_path).read_text(errors="replace")
dependencies = []
unresolved = []
for raw_line in ldd_text.splitlines():
    line = raw_line.strip()
    if not line or line.startswith("linux-vdso.so"):
        continue
    if "=>" in line:
        soname, right = (part.strip() for part in line.split("=>", 1))
        if right == "not found" or right.startswith("not found "):
            unresolved.append(soname)
            continue
        match = re.match(r"(/.+?)\s+\(0x[0-9a-fA-F]+\)$", right)
        if not match:
            fail(f"cannot parse ldd dependency line: {raw_line!r}")
        loader_path = match.group(1)
    elif line.startswith("/"):
        match = re.match(r"(/.+?)\s+\(0x[0-9a-fA-F]+\)$", line)
        if not match:
            fail(f"cannot parse direct ldd dependency line: {raw_line!r}")
        loader_path = match.group(1)
        soname = os.path.basename(loader_path)
    else:
        fail(f"unexpected ldd output line: {raw_line!r}")
    if not os.path.isabs(loader_path):
        fail(f"ldd returned a non-absolute dependency path: {loader_path!r}")
    if not os.path.isfile(loader_path):
        fail(f"resolved dependency is not a regular file: {loader_path}")
    resolved_path = os.path.realpath(loader_path)
    if not os.path.isfile(resolved_path):
        fail(f"dependency realpath is not a regular file: {resolved_path}")
    dependencies.append({
        "soname": soname,
        "loader_path": loader_path,
        "resolved_path": resolved_path,
        "size_bytes": os.stat(resolved_path).st_size,
        "sha256": sha256(resolved_path),
    })
if unresolved:
    fail("unresolved ldd dependencies: " + ", ".join(sorted(unresolved)))
if not dependencies:
    fail("ldd returned no file-backed dependencies")
sonames = [entry["soname"] for entry in dependencies]
if len(sonames) != len(set(sonames)):
    fail("ldd returned duplicate dependency sonames")

origin = os.path.dirname(binary)
expected_origin = {}
for index, item in enumerate(objects):
    if not isinstance(item, dict):
        fail(f"origin_shared_objects[{index}] is not an object")
    soname = item.get("soname")
    expected_sha = item.get("sha256")
    expected_size = item.get("size_bytes")
    if not isinstance(soname, str) or not soname or "/" in soname:
        fail(f"invalid origin soname at index {index}")
    if soname in expected_origin:
        fail(f"duplicate origin soname in manifest: {soname}")
    if not isinstance(expected_sha, str) or not sha_re.fullmatch(expected_sha):
        fail(f"invalid SHA-256 for {soname}")
    if not isinstance(expected_size, int) or expected_size <= 0:
        fail(f"invalid size_bytes for {soname}")
    loader_path = expand_origin(item.get("loader_path"), origin, f"{soname}.loader_path")
    resolved_path = expand_origin(item.get("resolved_path"), origin, f"{soname}.resolved_path")
    expected_origin[soname] = {
        "loader_path": loader_path,
        "resolved_path": resolved_path,
        "size_bytes": expected_size,
        "sha256": expected_sha,
    }

observed_origin = {}
for entry in dependencies:
    try:
        inside_origin = os.path.commonpath((origin, entry["loader_path"])) == origin
    except ValueError:
        inside_origin = False
    if inside_origin:
        observed_origin[entry["soname"]] = entry
if set(observed_origin) != set(expected_origin):
    fail(
        "manifest/local ldd soname set mismatch: expected "
        f"{sorted(expected_origin)}, observed {sorted(observed_origin)}"
    )
for soname, expected in expected_origin.items():
    observed = observed_origin[soname]
    for field in ("loader_path", "resolved_path", "size_bytes", "sha256"):
        if observed[field] != expected[field]:
            fail(
                f"{soname} {field} mismatch: expected {expected[field]!r}, "
                f"observed {observed[field]!r}"
            )

dependencies.sort(key=lambda item: (item["soname"], item["loader_path"]))
manifest_sha = sha256(manifest_path)
report = {
    "passed": True,
    "runtime_bundle_schema_version": 1,
    "runtime_manifest": os.path.abspath(manifest_path),
    "runtime_manifest_sha256": manifest_sha,
    "binary": {
        "loader_path": binary,
        "resolved_path": binary_resolved,
        "size_bytes": os.stat(binary_resolved).st_size,
        "sha256": binary_sha,
    },
    "dependency_count": len(dependencies),
    "origin_shared_object_count": len(observed_origin),
    "origin_shared_object_sonames": sorted(observed_origin),
    "dependencies": dependencies,
}

if reference_path:
    try:
        reference = json.loads(Path(reference_path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read reference runtime report: {exc}")
    signature_fields = (
        "runtime_bundle_schema_version",
        "runtime_manifest_sha256",
        "binary",
        "dependency_count",
        "origin_shared_object_count",
        "origin_shared_object_sonames",
        "dependencies",
    )
    drift = [field for field in signature_fields if reference.get(field) != report.get(field)]
    if drift:
        fail("resolved runtime dependency graph drifted in fields: " + ", ".join(drift))
    report["reference_report"] = os.path.abspath(reference_path)
    report["reference_match"] = True

resolved_files = {binary_resolved}
resolved_files.update(entry["resolved_path"] for entry in dependencies)
for path in resolved_files:
    if "\n" in path or "\\" in path:
        fail(f"unsupported path in checksum manifest: {path!r}")
with open(hashes_path, "w") as stream:
    for path in sorted(resolved_files):
        stream.write(f"{sha256(path)}  {path}\n")
Path(report_path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
PY
}

if [[ "${1:-}" == "--verify-runtime-bundle" ]]; then
  if (( $# != 4 && $# != 5 )); then
    echo "usage: $0 --verify-runtime-bundle LDD_OUT HASHES_OUT REPORT_OUT [REFERENCE_REPORT]" >&2
    exit 2
  fi
  [[ -x "$LLAMA_SERVER" ]] || {
    echo "llama-server not executable: $LLAMA_SERVER" >&2
    exit 2
  }
  [[ -f "$RUNTIME_MANIFEST" ]] || {
    echo "runtime manifest not found: $RUNTIME_MANIFEST" >&2
    exit 2
  }
  source_oneapi
  verify_runtime_bundle "$2" "$3" "$4" "${5:-}"
  exit 0
elif (( $# != 0 )); then
  echo "unexpected arguments; this launcher normally takes no arguments" >&2
  exit 2
fi

if [[ ! "$GPU_INDEX" =~ ^[0-3]$ ]]; then
  echo "GPU_INDEX must be 0, 1, 2, or 3" >&2
  exit 2
fi
if [[ "$HOST" != "127.0.0.1" ]]; then
  echo "validation launcher requires HOST=127.0.0.1" >&2
  exit 2
fi
if [[ ! "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1024 || PORT > 65535 )); then
  echo "PORT must be an integer from 1024 through 65535" >&2
  exit 2
fi
if [[ ! "$LOG_VERBOSITY" =~ ^[3-5]$ ]]; then
  echo "LOG_VERBOSITY must be 3, 4, or 5" >&2
  exit 2
fi
for toggle_name in LANE_DNN_ENABLED LANE_OPT_ENABLED KV_UNIFIED CONT_BATCHING LANE_FA_ONEDNN LANE_MKL_FA LANE_SYCL_FLASH_ATTN; do
  toggle_value="${!toggle_name}"
  if [[ "$toggle_value" != "0" && "$toggle_value" != "1" ]]; then
    echo "$toggle_name must be 0 or 1" >&2
    exit 2
  fi
done
if [[ ! "$CTX_SIZE" =~ ^[0-9]+$ ]] || (( CTX_SIZE <= 0 )); then
  echo "CTX_SIZE must be a positive integer" >&2
  exit 2
fi
if [[ ! "$HTTP_THREADS" =~ ^[1-9][0-9]*$ ]]; then
  echo "HTTP_THREADS must be a positive integer" >&2
  exit 2
fi
if [[ ! "$PARALLEL_SLOTS" =~ ^[1-8]$ ]]; then
  echo "PARALLEL_SLOTS must be an integer from 1 through 8" >&2
  exit 2
fi
if (( CTX_SIZE % PARALLEL_SLOTS != 0 )); then
  echo "CTX_SIZE must be divisible by PARALLEL_SLOTS" >&2
  exit 2
fi
if [[ ! "$LANE_FA_ONEDNN_MAX_KV" =~ ^[0-9]+$ ]]; then
  echo "LANE_FA_ONEDNN_MAX_KV must be a nonnegative integer" >&2
  exit 2
fi

unexpected_env=()
while IFS='=' read -r name _; do
  case "$name" in
    GGML_*|SYCL_*|ZE_*|ZES_*|UR_*|ONEAPI_DEVICE_SELECTOR|LD_PRELOAD)
      unexpected_env+=("$name")
      ;;
    LLAMA_*)
      [[ "$name" == "LLAMA_SERVER" ]] || unexpected_env+=("$name")
      ;;
  esac
done < <(env)
if (( ${#unexpected_env[@]} > 0 )); then
  printf 'unexpected inherited runtime environment: %s\n' "${unexpected_env[*]}" >&2
  exit 2
fi

EXPECTED_SIZE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["size_bytes"])' "$MANIFEST")"
EXPECTED_RUNTIME_SHA256="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["llama_server_sha256"])' "$RUNTIME_MANIFEST")"
EXPECTED_RUNTIME_VERSION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["runtime_version_line"])' "$RUNTIME_MANIFEST")"
if [[ ! -f "$MODEL" ]]; then
  echo "model not found: $MODEL" >&2
  exit 2
fi
if [[ -n "${QWEN36_MODEL_FD:-}" ]]; then
  if [[ ! "$QWEN36_MODEL_FD" =~ ^[0-9]+$ ]] || \
     [[ ! -r "/proc/$$/fd/$QWEN36_MODEL_FD" ]]; then
    echo "QWEN36_MODEL_FD is not a readable inherited descriptor" >&2
    exit 2
  fi
else
  exec {QWEN36_MODEL_FD}<"$MODEL"
  export QWEN36_MODEL_FD
fi
MODEL_FD_PATH="/proc/$$/fd/$QWEN36_MODEL_FD"
if [[ ! "$MODEL" -ef "$MODEL_FD_PATH" ]]; then
  echo "model pathname does not match the pinned model descriptor" >&2
  exit 2
fi
flock -s -n "$QWEN36_MODEL_FD" || {
  echo "pinned model descriptor does not hold a shared lock" >&2
  exit 2
}
MODEL_LOAD_PATH="/proc/self/fd/$QWEN36_MODEL_FD"
ACTUAL_SIZE="$(stat -Lc %s "$MODEL_FD_PATH")"
if [[ "$ACTUAL_SIZE" != "$EXPECTED_SIZE" ]]; then
  echo "model size mismatch: expected $EXPECTED_SIZE, got $ACTUAL_SIZE" >&2
  exit 2
fi
if [[ ! -x "$LLAMA_SERVER" ]]; then
  echo "llama-server not executable: $LLAMA_SERVER" >&2
  exit 2
fi
ACTUAL_RUNTIME_SHA256="$(sha256sum "$LLAMA_SERVER" | awk '{print $1}')"
if [[ "$ACTUAL_RUNTIME_SHA256" != "$EXPECTED_RUNTIME_SHA256" ]]; then
  echo "llama-server SHA-256 mismatch" >&2
  exit 2
fi
command -v flock >/dev/null 2>&1 || {
  echo "flock is required for shared GPU/port leases" >&2
  exit 2
}
GPU_LEASE_DIR="/run/user/$(id -u)/qwen36-b70-gpu-leases"
PORT_LEASE_DIR="/run/user/$(id -u)/qwen36-b70-port-leases"
mkdir -p "$GPU_LEASE_DIR" "$PORT_LEASE_DIR"
GPU_LEASE_PATH="$GPU_LEASE_DIR/gpu${GPU_INDEX}.lock"
PORT_LEASE_PATH="$PORT_LEASE_DIR/port${PORT}.lock"
if [[ -n "${QWEN36_GPU_LEASE_FD:-}" ]]; then
  [[ "$QWEN36_GPU_LEASE_FD" =~ ^[0-9]+$ ]] || {
    echo "QWEN36_GPU_LEASE_FD must be numeric" >&2
    exit 2
  }
  [[ "$(readlink -f "/proc/$$/fd/$QWEN36_GPU_LEASE_FD" 2>/dev/null || true)" == "$(readlink -f "$GPU_LEASE_PATH")" ]] || {
    echo "inherited GPU lease does not match GPU $GPU_INDEX" >&2
    exit 2
  }
  flock -n "$QWEN36_GPU_LEASE_FD" || {
    echo "inherited GPU lease is not held" >&2
    exit 2
  }
else
  exec {QWEN36_GPU_LEASE_FD}>"$GPU_LEASE_PATH"
  flock -n "$QWEN36_GPU_LEASE_FD" || {
    echo "GPU $GPU_INDEX is leased by another Qwen process" >&2
    exit 2
  }
  export QWEN36_GPU_LEASE_FD
fi
if [[ -n "${QWEN36_PORT_LEASE_FD:-}" ]]; then
  [[ "$QWEN36_PORT_LEASE_FD" =~ ^[0-9]+$ ]] || {
    echo "QWEN36_PORT_LEASE_FD must be numeric" >&2
    exit 2
  }
  [[ "$(readlink -f "/proc/$$/fd/$QWEN36_PORT_LEASE_FD" 2>/dev/null || true)" == "$(readlink -f "$PORT_LEASE_PATH")" ]] || {
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
    echo "port $PORT is leased by another Qwen process" >&2
    exit 2
  }
  export QWEN36_PORT_LEASE_FD
fi
if ss -H -ltn "sport = :$PORT" | grep -q .; then
  echo "port already in use: $PORT" >&2
  exit 2
fi

source_oneapi

RUNTIME_GATE_TMP="$(mktemp -d "${TMPDIR:-/tmp}/qwen36-runtime-gate.XXXXXX")"
RUNTIME_GATE_LDD="$RUNTIME_GATE_TMP/llama-server-ldd-post-oneapi.txt"
RUNTIME_GATE_HASHES="$RUNTIME_GATE_TMP/runtime-resolved-files.sha256"
RUNTIME_GATE_REPORT="$RUNTIME_GATE_TMP/runtime-bundle-verification.json"
cleanup_runtime_gate_tmp() {
  rm -f -- "$RUNTIME_GATE_LDD" "$RUNTIME_GATE_HASHES" "$RUNTIME_GATE_REPORT"
  rmdir -- "$RUNTIME_GATE_TMP" 2>/dev/null || true
}
trap cleanup_runtime_gate_tmp EXIT
verify_runtime_bundle "$RUNTIME_GATE_LDD" "$RUNTIME_GATE_HASHES" "$RUNTIME_GATE_REPORT"

export ONEAPI_DEVICE_SELECTOR="level_zero:*"
export ZE_AFFINITY_MASK="$GPU_INDEX"
export ZES_ENABLE_SYSMAN=1
export UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
export GGML_SYCL_ENABLE_VMM=1
export GGML_SYCL_ENABLE_GRAPH=0
export GGML_SYCL_GRAPH_CACHE_SIZE=0
export GGML_SYCL_ENABLE_DNN="$LANE_DNN_ENABLED"
export GGML_SYCL_ENABLE_OPT="$LANE_OPT_ENABLED"
export GGML_SYCL_FA_ONEDNN="$LANE_FA_ONEDNN"
export GGML_SYCL_FA_ONEDNN_MAX_KV="$LANE_FA_ONEDNN_MAX_KV"
export GGML_SYCL_ENABLE_MKL_FA="$LANE_MKL_FA"
export GGML_SYCL_ENABLE_FLASH_ATTN="$LANE_SYCL_FLASH_ATTN"

RUNTIME_VERSION="$($LLAMA_SERVER --version 2>&1)"
if ! grep -Fqx "$EXPECTED_RUNTIME_VERSION" <<< "$RUNTIME_VERSION"; then
  echo "llama-server version mismatch" >&2
  exit 2
fi

for log_path in "$LOG" "$SERVER_OUTPUT_LOG"; do
  if [[ "$log_path" != /* || "$log_path" == "/" || "$log_path" == *$'\n'* ]]; then
    echo "log paths must be non-root absolute paths without newlines: $log_path" >&2
    exit 2
  fi
done
mkdir -p "$OUT_DIR" "$(dirname "$LOG")" "$(dirname "$SERVER_OUTPUT_LOG")"
server_cmd=(
  "$LLAMA_SERVER"
  -m "$MODEL_LOAD_PATH"
  --alias "$MODEL_ALIAS"
  --host "$HOST"
  --port "$PORT"
  -dev SYCL0
  -ngl "$N_GPU_LAYERS"
  -c "$CTX_SIZE"
  -np "$PARALLEL_SLOTS"
  -b "$BATCH_SIZE"
  -ub "$UBATCH_SIZE"
  -t "$THREADS"
  --threads-http "$HTTP_THREADS"
  --poll "$POLL"
  -lv "$LOG_VERBOSITY"
  -ctk "$CACHE_TYPE_K"
  -ctv "$CACHE_TYPE_V"
  -fa "$FLASH_ATTN"
  --spec-type none
  --reasoning off
  --ctx-checkpoints 0
  --cache-ram 0
  --no-cache-idle-slots
  --no-context-shift
  --slots
  --metrics
  --jinja
)
if [[ "$KV_UNIFIED" == "1" ]]; then
  server_cmd+=(--kv-unified)
else
  server_cmd+=(--no-kv-unified)
fi
if [[ "$CONT_BATCHING" == "1" ]]; then
  server_cmd+=(--cont-batching)
else
  server_cmd+=(--no-cont-batching)
fi
{
  echo "date_utc=$STAMP"
  echo "gpu_index=$GPU_INDEX"
  echo "host=$HOST"
  echo "port=$PORT"
  echo "model=$MODEL"
  echo "model_pinned_fd=$QWEN36_MODEL_FD"
  echo "model_pinned_path=$(readlink -f "$MODEL_FD_PATH")"
  echo "model_load_path=$MODEL_LOAD_PATH"
  echo "model_bytes=$ACTUAL_SIZE"
  echo "model_alias=$MODEL_ALIAS"
  echo "model_manifest=$MANIFEST"
  echo "llama_server=$LLAMA_SERVER"
  echo "llama_server_sha256=$ACTUAL_RUNTIME_SHA256"
  echo "runtime_manifest=$RUNTIME_MANIFEST"
  echo "runtime_manifest_sha256=$(sha256sum "$RUNTIME_MANIFEST" | awk '{print $1}')"
  echo "runtime_bundle_verified=1"
  echo "server_output_log=$SERVER_OUTPUT_LOG"
  echo "gpu_lease_path=$GPU_LEASE_PATH"
  echo "port_lease_path=$PORT_LEASE_PATH"
  printf '%s\n' "$RUNTIME_VERSION"
  echo "ctx_size=$CTX_SIZE"
  echo "parallel_slots=$PARALLEL_SLOTS"
  echo "ctx_size_per_slot=$((CTX_SIZE / PARALLEL_SLOTS))"
  echo "kv_unified=$KV_UNIFIED"
  echo "cont_batching=$CONT_BATCHING"
  echo "batch_size=$BATCH_SIZE"
  echo "ubatch_size=$UBATCH_SIZE"
  echo "n_gpu_layers=$N_GPU_LAYERS"
  echo "threads=$THREADS"
  echo "http_threads=$HTTP_THREADS"
  echo "log_verbosity=$LOG_VERBOSITY"
  echo "flash_attn=$FLASH_ATTN"
  echo "cache_type_k=$CACHE_TYPE_K"
  echo "cache_type_v=$CACHE_TYPE_V"
  echo "speculation=none"
  echo "vision_projector=none"
  echo "reasoning=off"
  echo "ONEAPI_DEVICE_SELECTOR=$ONEAPI_DEVICE_SELECTOR"
  echo "ZE_AFFINITY_MASK=$ZE_AFFINITY_MASK"
  echo "GGML_SYCL_ENABLE_VMM=$GGML_SYCL_ENABLE_VMM"
  echo "GGML_SYCL_ENABLE_GRAPH=$GGML_SYCL_ENABLE_GRAPH"
  echo "GGML_SYCL_ENABLE_DNN=$GGML_SYCL_ENABLE_DNN"
  echo "GGML_SYCL_ENABLE_OPT=$GGML_SYCL_ENABLE_OPT"
  echo "GGML_SYCL_FA_ONEDNN=$GGML_SYCL_FA_ONEDNN"
  echo "GGML_SYCL_FA_ONEDNN_MAX_KV=$GGML_SYCL_FA_ONEDNN_MAX_KV"
  echo "GGML_SYCL_ENABLE_MKL_FA=$GGML_SYCL_ENABLE_MKL_FA"
  echo "GGML_SYCL_ENABLE_FLASH_ATTN=$GGML_SYCL_ENABLE_FLASH_ATTN"
  printf 'argv='
  printf '%q ' "${server_cmd[@]}"
  printf '\n'
  echo "--- runtime bundle verification ---"
  cat "$RUNTIME_GATE_REPORT"
  echo "--- runtime resolved files ---"
  cat "$RUNTIME_GATE_HASHES"
  echo "--- post-oneAPI ldd ---"
  cat "$RUNTIME_GATE_LDD"
  echo "--- server ---"
} > "$LOG"

cleanup_runtime_gate_tmp
trap - EXIT
if [[ "$SERVER_OUTPUT_LOG" != "$LOG" ]]; then
  : > "$SERVER_OUTPUT_LOG"
fi
exec "${server_cmd[@]}" >> "$SERVER_OUTPUT_LOG" 2>&1

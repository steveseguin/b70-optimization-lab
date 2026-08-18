#!/usr/bin/env bash
set -uo pipefail

# Read-only readiness check for the Qwen3.8 AutoRound TP2/MTP3 replay.  This
# script never imports torch, opens a GPU device, builds source, or launches a
# server.  It is safe to run on a reference host to describe what can be
# transferred and on a low-RAM replay host before any workload is attempted.

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "$here/../../.." && pwd)
source_root=${SOURCE_ROOT:-/home/steve/src}
venv=${VENV:-/home/steve/.venvs/vllm-xpu}
model_dir=${MODEL_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround}
base_stage=${BASE_STAGE:-$source_root/vllm-xpu-kernels}
graph_stage=${STAGE:-$repo/experiments/qwen27_graphsafe_flash_attention/staged-package}
oneccl=${ONECCL_INSTALL_DIR:-/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public}
verify_model=${VERIFY_MODEL:-1}
failures=0
warnings=0

pass() { printf 'PASS  %s\n' "$*"; }
warn() { printf 'WARN  %s\n' "$*"; warnings=$((warnings + 1)); }
fail() { printf 'FAIL  %s\n' "$*"; failures=$((failures + 1)); }

check_sha() {
  local path=$1 expected=$2 label=$3 actual
  if [[ ! -f "$path" ]]; then
    fail "$label missing: $path"
    return
  fi
  actual=$(sha256sum "$path" | awk '{print $1}')
  if [[ "$actual" == "$expected" ]]; then
    pass "$label SHA256: $actual"
  else
    fail "$label SHA256 mismatch: expected=$expected actual=$actual path=$path"
  fi
}

check_tree() {
  local tree=$1 expected=$2 label=$3 head diff
  if [[ ! -d "$tree/.git" ]]; then
    fail "$label Git tree missing: $tree"
    return
  fi
  head=$(git -C "$tree" rev-parse HEAD 2>/dev/null || true)
  diff=$(git -C "$tree" diff --binary | sha256sum | awk '{print $1}')
  if [[ "$head" == "$expected" ]]; then
    pass "$label commit: $head"
  else
    fail "$label commit mismatch: expected=$expected actual=$head"
  fi
  if [[ "$diff" == e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 ]]; then
    pass "$label working tree is clean"
  else
    fail "$label working tree has an unrecorded binary diff: $diff"
  fi
}

printf 'Qwen3.8 AutoRound TP2/MTP3 read-only preflight\n'
printf 'repo=%s\nsource_root=%s\nvenv=%s\nmodel_dir=%s\nbase_stage=%s\ngraph_stage=%s\noneccl=%s\n' \
  "$repo" "$source_root" "$venv" "$model_dir" "$base_stage" "$graph_stage" "$oneccl"

mem_kib=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
swap_kib=$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)
avail_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
printf 'host_mem_total_kib=%s\nhost_mem_available_kib=%s\nhost_swap_total_kib=%s\n' \
  "$mem_kib" "$avail_kib" "$swap_kib"
if (( mem_kib < 24 * 1024 * 1024 )); then
  warn "host has less than 24 GiB RAM; do not launch until a measured low-RAM procedure and peak-RSS bound are supplied"
fi

check_tree "$source_root/vllm" \
  44fc8fde09fc311d3099dab10366b672d9142ea4 vLLM
check_tree "$source_root/vllm-xpu-kernels" \
  2dd55f380df753a10a88fcd9e96192561066e713 vLLM-XPU-kernels

if [[ -x "$venv/bin/python" ]]; then
  pass "Python environment exists: $venv"
  runtime=$(
    "$venv/bin/python" - <<'PY' 2>/dev/null || true
import importlib.metadata as m
import sys
names = ("torch", "triton-xpu", "transformers", "numpy", "vllm-xpu-kernels")
print("python=" + ".".join(map(str, sys.version_info[:3])))
for name in names:
    try:
        print(f"{name}={m.version(name)}")
    except m.PackageNotFoundError:
        print(f"{name}=MISSING")
PY
  )
  printf '%s\n' "$runtime"
  if grep -Fxq 'torch=2.11.0+xpu' <<<"$runtime"; then
    pass 'torch version is 2.11.0+xpu'
  else
    fail 'torch version is not 2.11.0+xpu'
  fi
  if grep -Fxq 'triton-xpu=3.7.0' <<<"$runtime"; then
    pass 'triton-xpu version is 3.7.0'
  else
    fail 'triton-xpu version is not 3.7.0'
  fi
else
  fail "Python environment missing: $venv"
fi

# The exact arm checks the ordinary XPU package as well as the isolated
# graph-safe FlashAttention overlay. Most expected hashes are shared with the
# historical manifest; two changed with the exact 2026-08-18 source identity.
while read -r expected recorded_path; do
  [[ -n "$expected" && -n "$recorded_path" ]] || continue
  binary=$(basename "$recorded_path")
  if [[ "$binary" == _xpu_C.abi3.so ]]; then
    expected=8f11e716910289c9e53b770fab14231c040ac5b08ea7830947390ac0fb674496
  elif [[ "$binary" == libgdn_attn_kernels_xe_2.so ]]; then
    expected=e7b9757a317157bb4a63159cc38ad3fc302135ca72954807d189420bbcf1595e
  fi
  check_sha "$base_stage/vllm_xpu_kernels/$binary" "$expected" \
    "XPU-runtime-$binary"
done < "$repo/repro/qwen36-27b-autoround-int4-b70/evidence/xpu-runtime-binaries.sha256"

# These hashes identify the retained AOT artifacts on the measuring host.  A
# rebuild is validated functionally and rebenchmarked; it is not expected to
# reproduce these host-dependent bytes.
check_sha "$graph_stage/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" \
  33938cdd2436684dcb76108a4db43e4ab0314406ad537fcd3732a005f7d23739 \
  graph-safe-FlashAttention-extension
check_sha "$graph_stage/vllm_xpu_kernels/libattn_kernels_xe_2.so" \
  604f1b328870f2c41ef1d05c4d6016c34d222033d905877b0f9a2ff0c66b2a0c \
  graph-safe-FlashAttention-device-library
check_sha "$graph_stage/vllm_xpu_kernels/libattn_stock.so" \
  3cbd3ed2ff51a477e6746b3e5860c070d093fd2d29b0b7a58e6dd081e9ad1289 \
  graph-safe-FlashAttention-stock-dependency
check_sha "$graph_stage/vllm_xpu_kernels/flash_attn_interface.py" \
  869c79f5f678252c341cfb8fb5cf9ee34f95c3d2debf4d169b759510da432480 \
  graph-safe-FlashAttention-Python-interface

check_sha "$oneccl/lib/libccl.so.1.0" \
  43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700 \
  oneCCL
check_sha "$oneccl/lib/ccl/kernels/kernels.spv" \
  0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9 \
  oneCCL-kernels

if [[ "$verify_model" == 1 ]]; then
  if MODEL_DIR="$model_dir" \
      MODEL_MANIFEST="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json" \
      "$repo/repro/qwen36-27b-autoround-int4-b70/scripts/download-model.sh" \
      >/dev/null; then
    pass 'model revision and every recorded file identity verified'
  else
    fail 'model verification failed'
  fi
else
  warn 'model hashing skipped because VERIFY_MODEL is not 1'
fi

if command -v xpu-smi >/dev/null; then
  devices=$(xpu-smi discovery 2>/dev/null | grep -c 'Arc(TM) Pro B70' || true)
  if [[ "$devices" == 2 ]]; then
    pass 'two Intel Arc Pro B70 devices discovered'
  else
    fail "expected two B70 devices, discovered $devices"
  fi
else
  fail 'xpu-smi is unavailable'
fi

printf 'SUMMARY failures=%s warnings=%s\n' "$failures" "$warnings"
if (( failures != 0 )); then
  exit 3
fi
exit 0

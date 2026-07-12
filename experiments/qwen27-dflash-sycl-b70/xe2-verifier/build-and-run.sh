#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="${XE2_VERIFIER_OUT:-/mnt/fast-ai/bench-results/qwen27-xe2-verifier}"
mkdir -p "$out"

# shellcheck disable=SC1091
set +u
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u

icpx -fsycl -fsycl-targets=spir64_gen \
  -Xs "-device ${XE2_DEVICE_TARGET:-bmg-g31}" \
  -O3 -DNDEBUG -std=c++17 \
  "$here/xe2-int4-int8-verifier.cpp" -o "$out/xe2-int4-int8-verifier"

if [[ "${XE2_COMPILE_ONLY:-0}" == 1 ]]; then
  echo "compiled=$out/xe2-int4-int8-verifier"
  exit 0
fi

: "${ZE_AFFINITY_MASK:?Set ZE_AFFINITY_MASK to one explicitly reserved B70}"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
log="$out/run-$stamp.log"
set +e
{
  status4=0
  status8=0
  "$out/xe2-int4-int8-verifier" 4 "${XE2_K:-5120}" "${XE2_N:-5120}" "${XE2_ITERS:-30}" || status4=$?
  "$out/xe2-int4-int8-verifier" 8 "${XE2_K:-5120}" "${XE2_N:-5120}" "${XE2_ITERS:-30}" || status8=$?
  echo "status_m4=$status4 status_m8=$status8"
  (( status4 == 0 && status8 == 0 ))
} | tee "$log"
status=${PIPESTATUS[0]}
set -e
echo "log=$log"
exit "$status"

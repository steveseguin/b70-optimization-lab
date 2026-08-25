#!/usr/bin/env bash
set -euo pipefail

out="${1:-}"
if [[ -z "${out}" ]]; then
  printf 'usage: %s /path/to/new-platform-receipt.txt\n' "$0" >&2
  exit 2
fi
if [[ -e "${out}" ]]; then
  printf 'refusing to overwrite existing receipt: %s\n' "${out}" >&2
  exit 2
fi
mkdir -p "$(dirname -- "${out}")"

{
  printf 'captured_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '\n[os-release]\n'
  cat /etc/os-release
  printf '\n[uname]\n'
  uname -a
  printf '\n[groups]\n'
  id
  printf '\n[dri]\n'
  ls -l /dev/dri
  printf '\n[intel-packages]\n'
  dpkg-query -W -f='${Package}\t${Version}\n' 2>/dev/null \
    | grep -E '^(intel-|libze|level-zero|xpu-smi|clinfo)' \
    | LC_ALL=C sort || true
  printf '\n[oneapi-compilers]\n'
  find /opt/intel/oneapi/compiler -mindepth 1 -maxdepth 1 -type d \
    -printf '%f\n' 2>/dev/null | LC_ALL=C sort || true
  printf '\n[icpx]\n'
  if [[ -f /opt/intel/oneapi/setvars.sh ]]; then
    set +u
    # shellcheck disable=SC1091
    source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
    set -u
    command -v icpx
    icpx --version
  else
    printf 'MISSING /opt/intel/oneapi/setvars.sh\n'
  fi
  printf '\n[sycl-ls]\n'
  sycl-ls 2>&1 || true
  printf '\n[clinfo-device-names]\n'
  clinfo 2>/dev/null | grep 'Device Name' || true
  printf '\n[xpu-smi]\n'
  xpu-smi discovery 2>&1 || true
} > "${out}"

sha256sum "${out}"

#!/usr/bin/env bash
set -euo pipefail

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  echo "Run with sudo: sudo bash $0" >&2
  exit 2
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates curl wget gnupg gpg-agent software-properties-common \
  build-essential git git-lfs cmake ninja-build pkg-config python3.12-dev \
  python3.12-venv python3-pip jq ripgrep pciutils usbutils hwloc numactl \
  clinfo intel-gpu-tools equivs linux-generic-hwe-24.04

git lfs install --system

if [ ! -f /usr/share/keyrings/oneapi-archive-keyring.gpg ]; then
  wget -qO- https://apt.repos.intel.com/oneapi/gpgkey \
    | gpg --dearmor -o /usr/share/keyrings/oneapi-archive-keyring.gpg
fi
cat >/etc/apt/sources.list.d/oneAPI.list <<'EOF'
deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main
EOF

if ! grep -Rqs 'ppa.launchpadcontent.net/kobuk-team/intel-graphics' /etc/apt/sources.list.d; then
  add-apt-repository -y ppa:kobuk-team/intel-graphics
fi

apt-get update
apt-get install -y --no-install-recommends \
  level-zero level-zero-devel

# Current known-good machine uses Intel oneAPI's Level Zero loader and a local
# empty libze1 dependency shim. Some PPA packages depend on the Ubuntu/PPA
# package name even when /usr/lib/x86_64-linux-gnu/libze_loader.so.1 is already
# provided by the oneAPI level-zero package.
if ! dpkg-query -W -f='${Status}' libze1 2>/dev/null | grep -q 'install ok installed'; then
  tmpdir="$(mktemp -d)"
  cat >"$tmpdir/libze1-control" <<'EOF'
Section: libs
Priority: optional
Standards-Version: 3.9.2
Package: libze1
Version: 1.28.2-local1
Maintainer: local <root@localhost>
Architecture: amd64
Depends: level-zero (>= 1.28.2)
Description: Local dependency shim for Intel Level Zero loader
 This package intentionally ships no files. The Intel oneAPI level-zero
 package already provides /usr/lib/x86_64-linux-gnu/libze_loader.so.1.
EOF
  (cd "$tmpdir" && equivs-build libze1-control)
  dpkg -i "$tmpdir"/libze1_1.28.2-local1_amd64.deb
  apt-mark hold libze1
fi

apt-get install -y --no-install-recommends \
  xpu-smi intel-opencl-icd libze-intel-gpu1 intel-ocloc \
  intel-igc-core-2 intel-igc-opencl-2 intel-metrics-discovery \
  intel-metrics-library libxpum1 \
  intel-oneapi-dpcpp-cpp-2025.3 intel-oneapi-dpcpp-cpp-2026.0 \
  intel-oneapi-mkl-devel intel-oneapi-dnnl-devel-2026.0

echo "Install complete. Reboot into the HWE kernel before building the Python stack."


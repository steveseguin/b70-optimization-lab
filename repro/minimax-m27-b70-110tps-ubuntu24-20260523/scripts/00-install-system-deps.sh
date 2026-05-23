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
  build-essential git git-lfs cmake ninja-build pkg-config ccache \
  python3.12-dev python3.12-venv python3-pip jq ripgrep fd-find \
  pciutils usbutils hwloc numactl clinfo intel-gpu-tools equivs \
  linux-generic-hwe-24.04

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
  level-zero level-zero-devel \
  xpu-smi intel-opencl-icd libze-intel-gpu1 intel-ocloc \
  intel-igc-core-2 intel-igc-opencl-2 intel-metrics-discovery \
  intel-metrics-library libxpum1 \
  intel-oneapi-dpcpp-cpp-2025.3 intel-oneapi-dpcpp-cpp-2026.0 \
  intel-oneapi-mkl-devel intel-oneapi-dnnl-devel-2026.0

echo
echo "Install complete."
echo "Reboot before building the Python/XPU stack:"
echo "  sudo reboot"


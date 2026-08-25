# Clean-host Intel/oneAPI certification runbook

Status: **ready to execute, not yet certified**. Do not change
`clean_host_tested` until every receipt below comes from a newly installed
supported OS. A container on an established GPU host does not validate the
kernel driver, device permissions, reboot behavior, or first-time recovery.

## Supported test boundary

- Ubuntu Desktop 24.04 LTS on an HWE kernel;
- one or more Intel Arc Pro B70 cards, with the package run restricted to one;
- Intel client GPU compute packages including Level Zero development and
  `intel-ocloc` for the BMG AOT build;
- Intel oneAPI Toolkit 2026.1, recorded by exact component versions;
- at least 64 GiB host RAM plus swap and 20 GB free model storage.

Use Intel's current primary instructions, not a copied third-party recipe:

- [Intel client-GPU packages for Ubuntu 24.04](https://dgpu-docs.intel.com/installation-guides/installing-packages-from-the-intel-ppa.html)
- [Intel oneAPI 2026.1 APT installation](https://www.intel.com/content/www/us/en/docs/oneapi-toolkit/installation-guide-linux/latest/install-oneapi-toolkit-with-apt.html)
- [Intel oneAPI 2026.1 release requirements](https://www.intel.com/content/www/us/en/developer/articles/release-notes/oneapi-toolkit/2026.html)

As of 2026-08-25, Intel's Ubuntu instructions require the 24.04 HWE kernel,
the `intel-graphics` PPA, and these compute/AOT packages:

```bash
sudo apt-get update
sudo apt-get install -y software-properties-common
sudo add-apt-repository -y ppa:kobuk-team/intel-graphics
sudo apt-get install -y \
  libze-intel-gpu1 libze1 intel-metrics-discovery intel-opencl-icd \
  clinfo intel-gsc libze-dev intel-ocloc
```

Follow Intel's oneAPI page to install `intel-oneapi-toolkit`. Do not pin a
package version copied from this lab's mixed established host. Record what APT
actually installs, reboot after driver/kernel changes, then log in normally so
render-group membership is effective.

## Required receipts

Choose portable paths; none of these commands require this lab's mount names:

```bash
export SOURCE_DIR=/path/to/new/llama.cpp-qwen38-tp1
export MODEL_DIR=/path/to/qwen3.8-27b-q4km
export BUILD_DIR="$SOURCE_DIR/build-sycl-aot-bmg-g31"
export RECEIPT_DIR=/path/to/qwen38-clean-host-receipts
mkdir -p "$RECEIPT_DIR"

repro/qwen38-27b-q4km-tp1-b70/clean-host-inventory.sh \
  "$RECEIPT_DIR/platform.txt"

SOURCE_DIR="$SOURCE_DIR" \
  repro/qwen38-27b-q4km-tp1-b70/restore-and-build.sh \
  2>&1 | tee "$RECEIPT_DIR/build.log"

MODEL_DIR="$MODEL_DIR" BUILD_DIR="$BUILD_DIR" \
  repro/qwen38-27b-q4km-tp1-b70/preflight.sh \
  2>&1 | tee "$RECEIPT_DIR/preflight.log"
```

Launch `run-server.sh` in one terminal, then run the health check and
`bench.sh` from the main guide in another. Preserve the benchmark JSON and
server log. Certification requires all of the following:

- the direct and ordinary model hashes equal `model-direct.json`;
- source restoration applies every repository patch without local edits;
- `sycl-ls`, `clinfo`, and `xpu-smi discovery` identify the B70 after reboot;
- the server becomes healthy on one explicitly selected GPU;
- the 12-prompt result reports zero cached tokens, 12/12 registered output
  hashes, and a passing realistic final gate;
- a second fresh server repeats those quality gates;
- exact package, kernel, compiler, runtime-binary, model, and result hashes are
  attached to the contribution.

Speed may differ on another CPU or motherboard. Do not fail certification
merely because tok/s differs, and do not claim parity unless the exact measured
value and workload are reported. Never interpolate a missing result.

## Recovery boundary

Use the beginner recovery checklist in the [main guide](README.md). If a
driver install, reboot, build, model verification, or endpoint gate fails,
preserve that failed receipt and fix one layer at a time. Do not edit away a
checksum, disable an output gate, make `/dev/dri` world-writable, or reuse a
partially built source directory.

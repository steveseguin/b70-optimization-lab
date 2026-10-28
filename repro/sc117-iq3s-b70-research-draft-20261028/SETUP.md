# Draft platform setup

The measured lane uses Linux x86-64 and three or four Intel Arc Pro B70 cards.
The compiler target is **intel_gpu_bmg_g31**; this AOT build is hardware-specific,
not a generic SPIR-V fallback package. Existing model/kernel assumptions are
SC117-specific. Other GPU families, Windows, WSL and other models are not qualified.

## Observed platform, not a clean-host certification

The packaging-time read-only inventory is in [toolchain-observed.json](toolchain-observed.json).
It records Ubuntu 24.04.4 LTS, kernel 7.0.0-39-generic, Python 3.12.3,
oneAPI compiler 2026.0.0, Level Zero and OpenSSL packages. It is a current
inventory, not proof that every installed package was identical at measurement
time. The retained measured build receipt separately pins compiler commands and
source dependencies. A package presence list is not an ABI compatibility test.

For a new machine, consult Intel's official [GPU installation choices](https://dgpu-docs.intel.com/installation-guides/index.html)
and [supported Xe hardware](https://dgpu-docs.intel.com/overview/supported-hardware/xe-driver-gpus.html).
Intel also documents [Open Middleware Xe](https://dgpu-docs.intel.com/installation-guides/installing-omix.html)
for Arc Pro B-series. Select a supported OS/driver combination before applying
this recipe. The observed custom host kernel is not a distribution-independent
installation instruction. This draft does not install or change drivers.

Install Intel oneAPI DPC++/C++ **2026.0.0** using the
[official compiler distribution](https://www.intel.com/content/www/us/en/developer/tools/oneapi/dpc-compiler-download.html).
Do not silently substitute whichever version a `latest` package currently gives.
The recorded compiler is `/opt/intel/oneapi/compiler/2026.0/bin/icpx`;
`--compiler` can select another explicit installation path, but a version change
requires new build/runtime qualification. The recorded build also needs Level
Zero headers/loader, OpenSSL headers/libcrypto, and GNU C++20 standard headers.

On an already configured compatible Debian/Ubuntu system, the non-driver build
prerequisites are available as:

```bash
sudo apt-get install git python3 curl build-essential libssl-dev libze-dev
/opt/intel/oneapi/compiler/2026.0/bin/icpx --version
python3 --version
dpkg-query -W libze1 libze-intel-gpu1 libze-dev libssl-dev libstdc++-13-dev
```

This is prerequisite guidance, not a complete version-locked installer. Review
the package manager's proposed changes; a new repository or missing historical
package version needs operator attention. The packaging work did not execute
these installation commands. No power, clock, swap, page-cache, reboot or driver
reset steps are prescribed.

## Runtime libraries and devices

The measured launches included compiler/SYCL, TCM, UMF, TBB, PTI, MKL, DNNL and
debugger library directories. The inventory records those original versioned
paths. Some may be transitive environment entries rather than actual loaded
dependencies. A minimal verified runtime closure is still pending; do not
claim all are necessary or omit them without checking dependency resolution.

The portable planner requires explicit canonical runtime library directories.
It intentionally does not inherit arbitrary diagnostic or preload settings.
After building, record `readelf -d` and dependency resolution for the trusted
locally built executable. Keep libze_loader and Intel compute runtime versions
with the result. A compiler version alone does not identify the runtime stack.

Enumerate PCI devices read-only (`lspci -D`) and map actual B70 BDFs; copied
example addresses do not identify another machine's cards. Device ownership,
baseline faults and memory/storage headroom must be checked by the separately
qualified local observer before a device run. There is no automatic admission
or service restart in this packet.

The token-ID recipe has no pip dependencies. Text/chat serving is a separate
unfinished packaging step; no unpinned tokenizers/Jinja2 environment is required
just to reproduce these fixed input arrays.

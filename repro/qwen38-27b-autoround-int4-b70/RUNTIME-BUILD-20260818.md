# Two-B70 XPU runtime rebuild — 2026-08-18

Status: source build and CPU-side import check passed; endpoint performance and
quality validation remain pending.

This host did not retain the measuring host's untracked XPU binaries. The
official `vllm-xpu-kernels 0.1.8` wheel supplied the unchanged base libraries,
while `_xpu_C` and the GDN device library were rebuilt from the exact promoted
source commit.

## Identity

- source: `steveseguin/vllm-xpu-kernels` commit
  `2dd55f380df753a10a88fcd9e96192561066e713`, clean tracked diff;
- compiler: Intel oneAPI DPC++ `2025.3.3.20260319`;
- Torch: `2.11.0+xpu`;
- AOT target: `bmg-g31-a0`;
- CMake lane: XPU-specific and GDN enabled, basic/FA2/MoE/MQA/allocator
  disabled;
- build parallelism: one job.

Exact command from the lab root:

```bash
CLEAN=1 \
BUILD_DIR=/home/steve/src/vllm-xpu-kernels/build/qwen38-autoround-bmg-g31-20260818 \
INSTALL_PREFIX=/home/steve/src/vllm-xpu-kernels/build/install-qwen38-autoround-bmg-g31-20260818 \
AOT_DEVICES=bmg-g31-a0 JOBS=1 GDN_KERNELS=ON MOE_KERNELS=OFF \
  scripts/build-vllm-xpu-kernels-xpu-c-only.sh
```

The complete runtime-package checksum gate is
[`manifests/xpu-runtime-bmg-g31-oneapi2025.3.3-20260818.sha256`](manifests/xpu-runtime-bmg-g31-oneapi2025.3.3-20260818.sha256).
The two rebuilt files are:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `_xpu_C.abi3.so` | 118,128,032 | `e47f5668e081defb5f574c6f9728093fd586ae1ba407ab65f4fccd84cc0bf79e` |
| `libgdn_attn_kernels_xe_2.so` | 2,824,400 | `c194e28dd902136df545b9c0bd3929d41968c31e84f5b3b2f5ae1dba9dbaeab7` |

The replaced wheel files were retained locally under
`build/wheel-original-qwen38-20260818/`; their hashes were `4486f102...` and
`818a6c4e...`, respectively.

## Low-memory observation

The single `chunk_gated_delta_rule_xe2.cpp` compiler process peaked near
14.2 GiB RSS and used swap, then completed successfully. Two build jobs are
unsafe on a 16 GiB host. The system remained responsive and no GPU process was
active. Offline compilation emitted register-spill warnings for several broad
type/shape variants; all requested AOT compilations and the final link reported
success. These warnings are not being interpreted as a performance result.

## Import-path gate

An initial CPU-side import deliberately caught an ABI mix: Python selected the
installed wheel's old `_xpu_C`, while `LD_LIBRARY_PATH` selected the rebuilt GDN
library. With the verified source package first on `PYTHONPATH`, the rebuilt
pair imported successfully, registered `int4_gemm_w4a16`, and enumerated both
B70s. `run-arm.sh` now enforces that same package identity so a strict run
cannot silently combine wheel and rebuilt components.

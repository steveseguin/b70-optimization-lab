# Qwen3.8 Flash-Next FP8 grouped full-serving stage A1 preregistration

Date: 2026-08-31
Status: frozen before build execution

## Purpose and boundary

The dynamic-M HC grouped-up source candidate is component-qualified, but its
two-file test stage is not a serving runtime: that `_xpu_C` was built with GDN
disabled. Flash-Next serving requires the GDN operations retained by the
accepted 18-file runtime. The component stage must never be placed on the
server `PYTHONPATH` or substituted for the serving package.

This build-only arm creates a new full serving stage without modifying the
accepted stage. It builds `_xpu_C` from clean kernel head
`eeee7d671abfa964626baa18da2174bb92cac80a` with both GDN and grouped/MoE
enabled, then copies the accepted 18-file package into a new local-NVMe stage
and replaces exactly three matched files:

- `_xpu_C.abi3.so`;
- `libgdn_attn_kernels_xe_2.so`;
- `libgrouped_gemm_xe_2.so`.

All other 15 runtime files must remain byte-identical to the accepted stage.
The output is a candidate hybrid stage, not a production replacement. This arm
performs no reboot, full checkpoint load, endpoint request, or speed test.

## Frozen inputs

- vLLM: clean `797769b34b6db5c934609b75dc04cc61ec66e5f9`;
- XPU kernels: clean `eeee7d671abfa964626baa18da2174bb92cac80a`;
- exact kernel chain:
  `eeee7d6 <- 042c6e8 <- a6ee94f <- 359466a <- ad25aa9`;
- accepted runtime:
  `/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70`;
- accepted 18-file manifest SHA-256:
  `9fa443fdb7a6d0042cf04f859cc6fd6a7bdc09943e16cafb4ea084573c892d2b`;
- generic low-memory builder SHA-256:
  `5cbdadc200626ed9da03b6aa4808a59ee848348c671ce76d4d7ada4a37ca464f`;
- default-off top-k patch SHA-256:
  `d4a7d9934e21a37ed21e812355e4241690992d5b81c27fe818dc9302f19d0ef9`;
- grouped-build contract patch SHA-256:
  `4126ebd2057173128fa5332646cc256d7f5daaa625ec86c18241fbc63e71a194`.
- frozen build driver SHA-256:
  `b5c29a50c3e6e3b737312fcb2392df9e5b252ef38cd038674c1bf11d4c3bd336`.

The native build is Release/Ninja, oneAPI 2025.3, Python 3.12/Torch XPU,
`bmg-g21-a0`, Xe2 on/Xe-default off, SYCL-TLA on, GDN on, MoE on,
XPU-specific on, and basic/FA2/MQA/allocator off. Two compile jobs are allowed;
the host had about 120 GiB available memory and 225 GiB free local NVMe when
the arm was first frozen. The driver requires at least 100 GiB available memory,
7 GiB free swap, and 150 GiB free on the exact NVMe/ext4 root; rejects an
active model server; and takes an exclusive lock covering the shared kernel
dependency build tree.

The reusable builder's default behavior is unchanged. This arm uses its new
optional dependency-source controls to place all FetchContent build state at
`/mnt/fast-ai/qwen38-build/deps-xpu-serving-eeee7d6-a1` while reading the
exact clean pinned oneDNN and SYCL-TLA source trees. It also rejects any active
CMake, Ninja, or oneAPI compiler process before claiming its build lock.
CMake 4.3.2, Ninja 1.13.0, oneAPI 2025.3.3, Python 3.12.13, Torch
2.11.0+xpu, patchelf 0.18.0, and their local executable hashes are bound and
captured. The accepted stage path is usable only when `/mnt/usb-models` is the
authenticated `/dev/sda2` `fuseblk` mount.
`Q38_GROUPED_STAGE_VALIDATE_ONLY=1` runs this entire preflight without creating
an output directory or starting CMake.

The otherwise-clean kernel checkout contains only the known untracked
`third_party/` directory. The driver requires that exact state, binds the clean
oneDNN `80afa710...` and SYCL-TLA `cd763790...` dependency trees, and rejects
any reference to the untracked root directory in generated compile commands.
Source heads, ancestry, dependency heads, tracked state, builder, patches,
accepted stage, and tools are rechecked before build, after build, and before
the final manifest. Generated CMake options and B70 AOT selection are validated
rather than merely hashed. Both builder and log-capture exit codes must pass.

Outputs are exclusive and must not preexist:

- build: `/mnt/fast-ai/qwen38-build/build-xpu-serving-eeee7d6-a1`;
- install: `/mnt/fast-ai/qwen38-build/install-xpu-serving-eeee7d6-a1`;
- stage: `/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a1`;
- evidence:
  `/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a1-evidence`.
- isolated FetchContent build state:
  `/mnt/fast-ai/qwen38-build/deps-xpu-serving-eeee7d6-a1`.

## Frozen interpretation

A successful build requires an exact 18-file runtime inventory, unchanged
hashes for the 15 untreated files, both GDN and grouped dependencies in the new
extension, `$ORIGIN` loader isolation, exact candidate-local GDN/grouped loader
resolution, exact venv SYCL 8 resolution, and complete build/cache/manifest
evidence. It authorizes only stage qualification.

Before any endpoint arm, a separate frozen qualification must prove normal
package loading, schema parity with the accepted extension plus the grouped
schema, SYCL 8 and candidate-local dependency resolution, the focused HC tests,
the retained GDN replay gate, the M1 MoE gate, and TP4 collective health. Only
then may a composite A30 endpoint be frozen. A30 will remain candidate-only;
causal promotion later needs a same-source/same-stage flag-off control and a
fresh flag-on repeat.

The accepted runtime, protected `5.515783 tok/s` MTP0 result, and approximately
`20.727 tok/s` MTP4 result remain unchanged.

## Pre-execution host interruption

Before this build was launched, boot `b998940e-...` ended as an unclean host
crash at 08:15. No native build, model process, endpoint, or reboot command had
been started by this arm, and all five exclusive output paths remained absent
after return. The prior journal ends hours before the reset; it contains two
corrected PCIe receive notices for the internal NVMe but no terminal fault,
OOM, orderly shutdown, or evidence sufficient to assign a cause. Do not claim
those corrected notices caused the reset.

On fresh boot `c36480de-9150-4182-9888-08c85d2d9de4`, the external drive was
not mounted and `/mnt/usb-models` resolved to the internal root. It was restored
as `/dev/sda2`/`fuseblk`, and the frozen validation-only preflight passed. The
build driver now authenticates both storage roots, so this mount failure would
stop rather than read or write the wrong filesystem. No full model load has
consumed this boot.

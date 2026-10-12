# Offline build-option provenance

Read-only CPU investigation. PCI sysfs text reports `0xe223`, revision `0x00`.
No device runtime was called. Binary hashes and fetched source hashes are in
`runtime-options.json`; fetched source was scratch under `build/options/` and was deleted at closeout.

| Packet 29 input | SYCL/UR Level Zero option | IGC/ocloc API option |
|---|---|---|
| `-O1`, `-O2`, `-O3` metadata | `-ze-opt-level=2` | `-ze-opt-level=O2` (letter O) |
| `-O0` metadata | `-ze-opt-disable` | `-cl-opt-disable` |
| either precise-div or precise-sqrt offload flag | `-ze-fp32-correctly-rounded-divide-sqrt` | `-cl-fp32-correctly-rounded-divide-sqrt` |

Both precise offload flags occur at packet29's recorded link, as well as its
compile. SYCL reads image compile options, maps these frontend flag strings
through UR, and appends the image optimization property. NEO changes the
numeric Level Zero optimization option to IGC's O-prefixed value. Installed
UR and SYCL binary strings contain these options; installed IGC contains both
spellings of the correctly rounded divide/sqrt option. This is stronger than
assuming default OpenCL math but is not a trace of an actual JIT invocation.
The offline API options chosen are therefore
`-ze-opt-level=O2 -cl-fp32-correctly-rounded-divide-sqrt`.

NEO `26.18.38308.1` exactly matches installed ocloc's release and resolves to
[82aab87fc932edc0558a0302d545a5bcc22edf41](https://github.com/intel/compute-runtime/tree/82aab87fc932edc0558a0302d545a5bcc22edf41).
Its [module code](https://github.com/intel/compute-runtime/blob/82aab87fc932edc0558a0302d545a5bcc22edf41/level_zero/core/source/module/module_imp.cpp)
implements option translation and adds the >4GB compiler option when the
product requires stateless addressing. Its
[offline compiler](https://github.com/intel/compute-runtime/blob/82aab87fc932edc0558a0302d545a5bcc22edf41/shared/offline_compiler/source/offline_compiler.cpp)
adds the same product-required option, bindless mode, cache policy and buffer
offset support according to target capabilities. The actual packet33 ocloc
internal-options dump contains `-cl-intel-greater-than-4GB-buffer-required`,
`-cl-intel-use-bindless-mode -cl-intel-use-bindless-advanced-mode`,
`-cl-store-cache-default=2 -cl-load-cache-default=4` and
`-cl-intel-has-buffer-offset-arg`. These must be retained when comparing
variants; removing >4GB to encourage A32 is not faithful to this baseline.

UR can additionally request >4GB via
`UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS`; its default is false in the read
source. This environment variable is disallowed by packet29's closed native
environment. The NEO product requirement is independent of that variable.
`SYCL_PROGRAM_COMPILE_OPTIONS` replaces embedded options and can suppress
precise arithmetic and opt-level propagation; use of it is not a safe casual
optimization. An explicitly qualified append option is preferable, and its
full resulting build options must be recorded.

Mapping references: pinned
[UR platform](https://github.com/oneapi-src/unified-runtime/blob/89d2582a8720e7507ccf531d508f52c1ab068f5c/source/adapters/level_zero/common/platform.cpp),
[UR program](https://github.com/oneapi-src/unified-runtime/blob/89d2582a8720e7507ccf531d508f52c1ab068f5c/source/adapters/level_zero/common/program.cpp),
and [SYCL program manager](https://github.com/intel/llvm/blob/3ae8b8c55b5f4a7c08f279044a2b4083501ce78e/sycl/source/detail/program_manager/program_manager.cpp).
These upstream commits are research inputs, not claimed installed source
identities. The installed binary string evidence corroborates the mapping.

Remaining uncertainty: no UR trace, module build log or driver dump was
captured on a card. Offline target options and kernel identities can be
reproduced, but byte identity with code JIT-compiled during the old timing
receipt is not proven. Driver-selected features and internal flags may differ.
Offline GEN is therefore a controlled code-generation study, with that limit.

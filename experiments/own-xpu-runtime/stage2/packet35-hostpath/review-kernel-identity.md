# Independent kernel identity review

The final audit passes: all four native executables contain exactly the same
24 SPIR-V module byte strings and 369 kernel entry-point names as packet 29.
All 30 submitted lambda source hashes and both registries also match.

This review reads source and ELF bytes on the CPU. It never executes a device
binary, loads Level Zero, discovers devices, or opens a device node.

`kernel_identity.py` compares packet 29 and packet 35 at three levels:

1. The exact kernel registry and K2 class registry file hashes.
2. The source hashes of each submitted device lambda, after each packet's actual
   source overlays. This includes packet 35's submission overlay. The initial
   audit finds 30 submitted lambda sites; template instantiations produce more
   entry points. The source closure and all changed host-source files are also
   recorded, so equal lambda bodies do not hide unreviewed helper changes.
3. Each embedded SPIR-V module's exact bytes and `OpEntryPoint` names in all four
   native executables. Packet 29 contains 24 modules and 369 entry points per
   executable. Comparing names alone would not prove unchanged arithmetic.

The parser reads the little-endian ELF64 section table and the
`__CLANG_OFFLOAD_BUNDLE__sycl-spir64` section, then walks SPIR-V instructions.
It rejects unknown/compressed formats, malformed instructions and unparsed
nonzero bytes. It does not call the SYCL loader. A module-byte mismatch fails
closed even when all entry-point names remain equal. There is no allowance for
an arithmetic change, renamed kernel or constant change.

`test_kernel_identity.py` changes one embedded `OpConstant` in a scratch copy.
The kernel names still compare equal, while the module identity fails. Its
three CPU checks also establish baseline parsing and non-ELF rejection. The
scratch directory is removed by the test.

The generated `kernel-identity.json` is the verdict. `passed: false` in a
source-only run means binary identity remains open; it must never be promoted
as a complete proof. These checks establish compiled device-code identity,
not real-device correctness, timings or a JIT-driver result. Device windows
remain coordinator work.

The first full comparison caught a real compiled-code discrepancy despite equal
source lambda hashes and kernel names: prepending the submission helper include
shifted one device assertion's `__LINE__` from 45 to 48. That changed one constant
and subsequent SPIR-V IDs in the packet7 module. The submission overlay now
restores `#line 1` after its helper include. Rebuilding restored exact module
bytes; the final proof uses no normalization or exception for that difference.
Diagnostic disassemblies were deleted after the fix.

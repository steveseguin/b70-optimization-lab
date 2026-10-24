# Primitive control upload

The actual unfused graph consumes 293 control tensors: 292 F32 and one F16
(`blk.1.ple_conv1d.weight`). None is shared with a GEMV or lookup. The other
BF16 tensors belong to GEMVs; they must retain proper matrix dispatch.
[manifest.json](manifest.json) binds every control to the frozen graph/census.

`upload.hpp` widens F16 or BF16 to F32 and copies F32 bytes unchanged. This
changes no finite value, adds no norm offset, and changes no source-model
descriptor. Future Engine wiring must use the F32 allocation size and effective
`Spec.grids` value together; source authentication remains on the original
type and bytes. Current controls need only 81,920 extra bytes for the F16
convolution. Native Engine wiring has not happened yet.

The CPU test passes all 65,536 half and all 65,536 BF16 bit patterns, preserves
262,144 F32 bytes, and rejects five malformed/unsupported uploads. Half NaNs
are checked by classification, not payload/sign parity. The remaining finite,
infinite and signed-zero values compare by exact FP32 bits against independent
`ldexp` equations. [cpu-proof.json](cpu-proof.json) pins compiler, dependencies,
binary and command. No weight payload or device was read.

The first attempt stopped before compilation because the shared compiler
coordinator requires a `build_engine.limits` callback. The corrected callback
uses this helper's own resource checks. The [failure](precompile-failure.json)
and [exact fix](compiler-coordinator-fix.patch) are retained. The second attempt
compiled once and passed; no arithmetic failure or retry occurred.

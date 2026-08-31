# Qwen3.8 Flash-Next grouped full-serving stage A1 result

Date: 2026-08-31
Status: native build passed; finalization failed closed

A1 completed all `711/711` native build steps and both pipeline receipts were
zero. The resulting matched `_xpu_C`, GDN, and grouped libraries are intact and
hash-bound in the structured result. No A1 stage directory was created.

The post-build gate then stopped before assembly because two of its frozen
expectations were wrong: activation of the vLLM build environment selected its
packaged CMake and Ninja, and CMake recorded the pinned oneDNN source as a
`PATH` cache entry. A1 had instead asserted the user-local CMake path and an
`UNINITIALIZED` oneDNN entry. The outer-shell failure message was not captured
in `build.log`; this classification is reconstructed from the exact A1 driver
and post-build cache, both of which are hash-bound. This is a procedural
finalization negative, not a compile, source, kernel, loader, quality, or
performance negative.

The accepted serving stage and all protected results remain unchanged. A1
authorizes no serving or speed claim. Its exact successful build may be consumed
only by the assembly-only A2 finalizer, which validates the complete A1 closure
and actual toolchain identities without recompiling.

Structured evidence:
[`20260831-grouped-serving-stage-a1-procedural-negative.json`](../data/20260831-grouped-serving-stage-a1-procedural-negative.json).
